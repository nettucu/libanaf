import asyncio
import json
import logging
import zipfile
from pathlib import Path

import aiofiles
import httpx
from httpx import AsyncClient, HTTPStatusError, ReadTimeout, Response
from lxml import etree
from pydantic import ValidationError
from pydantic_xml import ParsingError
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
)

from libanaf.auth import AnafAuthClient
from libanaf.config import get_settings

from libanaf.ubl.ubl_document import parse_ubl_document

logger: logging.Logger = logging.getLogger(__name__)


async def get_pdf_path(xml_path: Path) -> Path:
    """Determine the output PDF path for a given XML invoice file.

    Parses the UBL document at ``xml_path`` to extract a human-friendly
    filename (supplier + number + date).  Falls back to the XML stem with
    a ``.pdf`` extension if parsing fails for any reason.

    Args:
        xml_path: Path to the UBL XML invoice file.

    Returns:
        Path: The resolved output PDF path (same directory as ``xml_path``).
    """
    outfname = xml_path.stem + ".pdf"

    try:
        document = parse_ubl_document(xml_path)

        if document is not None:
            fname = document.tofname()
            outfname = xml_path.stem + "_" + fname + ".pdf"

    except ValidationError as e:
        logger.error(f"Invoice {xml_path}: {e}", exc_info=e)
    except etree.XMLSyntaxError as e:
        logger.error(f"XML Syntax error {xml_path}: {e}", exc_info=e)
    except ParsingError as e:
        logger.error(f"XML Parse error {xml_path}: {e}", exc_info=e)
    except asyncio.CancelledError as e:
        logger.error(f"asyncio ERROR {xml_path}", exc_info=e)
        pass
    except Exception as e:
        logger.error(f"XML UNKNOWN error {xml_path}: {e}", exc_info=e)

    return xml_path.parent / outfname


async def convert_to_pdf(
    client: AsyncClient,
    xml: Path,
    pdf: Path,
    semaphore: asyncio.Semaphore,
    progress: Progress,
    taskid,
) -> str:
    """Call the ANAF API service to convert an XML invoice to PDF.

    Posts the content of ``xml`` to the ANAF xml2pdf endpoint with retry
    logic, writing the resulting PDF bytes to ``pdf``. Concurrency is
    throttled via ``semaphore``.

    Args:
        client: Authenticated `httpx.AsyncClient` to use for the request.
        xml: Path to the UBL XML file to convert.
        pdf: Destination path for the generated PDF.
        semaphore: Semaphore limiting concurrent conversions.
        progress: Rich `Progress` instance for reporting.
        taskid: Progress task identifier to advance on success.

    Returns:
        str: ``"SUCCESS: <xml>"`` on success, or a short error description.
    """
    settings = get_settings()

    async with semaphore:
        await asyncio.sleep(0.5)

        url = settings.efactura.xml2pdf_url
        headers = {"Content-Type": "text/plain"}
        async with aiofiles.open(xml) as f:
            data = await f.read()

        from tenacity import (
            AsyncRetrying,
            before_sleep_log,
            retry_if_exception_type,
            stop_after_attempt,
            wait_exponential,
        )

        response: Response | None = None
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(settings.retry.count),
                wait=wait_exponential(
                    multiplier=settings.retry.backoff_factor,
                    min=settings.retry.delay,
                    max=settings.retry.max_delay,
                ),
                retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException, httpx.HTTPStatusError)),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                reraise=True,
            ):
                with attempt:
                    response = await client.post(url=url, headers=headers, data=data, timeout=30.0)
                    response.raise_for_status()
        except Exception as e:
            logger.error(f"Error converting {xml}: {e}")
            return f"Error: {e}"

        if response is None:
            return f"Error: No response for {xml}"

        if response.status_code != 200:
            logger.error(f"Unexpected HTTP status code {response.status_code} {response.reason_phrase}")
            return f"Unexpected HTTP status code {response.status_code} {response.reason_phrase}"

        content_type = response.headers["content-type"]
        if any(s in content_type for s in ("application/json", "text/plain")):
            try:
                message = response.json()
                logger.error(f"Error received downloading: {url} - {message['eroare']}")
                return f"Error: {message.get('eroare', message)}"
            except json.JSONDecodeError:
                logger.error(f"Unknow error for url: {url}")
                return f"Unknow error for url: {url}"

        async with aiofiles.open(pdf, "wb") as pdf_file:
            await pdf_file.write(response.content)

        progress.update(task_id=taskid, file=xml, advance=1, refresh=True)

    return f"SUCCESS: {xml}"


async def process_invoices_async(files_to_process: dict[Path, Path], semaphore: asyncio.Semaphore) -> None:
    """Process a batch of XML→PDF conversions asynchronously.

    Builds an authenticated ANAF HTTP client, then fans out ``convert_to_pdf``
    coroutines for every entry in ``files_to_process``, using ``semaphore`` to
    cap concurrent requests.

    Args:
        files_to_process: Mapping of XML source path → PDF destination path.
        semaphore: Semaphore controlling maximum concurrent ANAF API calls.
    """
    console = Console()

    try:
        settings = get_settings()
        httpx_client: AsyncClient = AnafAuthClient(
            client_id=settings.auth.client_id,
            client_secret=settings.auth.client_secret,
            auth_url=settings.auth.auth_url,
            token_url=settings.auth.token_url,
            redirect_uri=settings.auth.redirect_uri,
            access_token=settings.connection.access_token,
            refresh_token=settings.connection.refresh_token,
            cert_file=settings.connection.tls_cert_file,
            key_file=settings.connection.tls_key_file,
        ).get_client()

        with Progress(
            SpinnerColumn(),
            MofNCompleteColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.1f}%"),
            transient=False,
        ) as progress:
            overall_progress = progress.add_task("Overall progress", total=len(files_to_process))
            progress.start_task(overall_progress)

            tasks = [
                convert_to_pdf(
                    client=httpx_client,
                    xml=_xml,
                    pdf=_pdf,
                    semaphore=semaphore,
                    progress=progress,
                    taskid=overall_progress,
                )
                for _xml, _pdf in files_to_process.items()
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)
            logger.debug(f"Processing results = {results}")

        console.print("[bold green]Processed all missing PDFs.[/bold green]")
        logger.info("Processed all missing PDFs.")

    except HTTPStatusError as e:
        console.log(f"[bold red]HTTP error occurred:[/bold red] {e}")
        logger.error(f"HTTP error occurred: {e}", exc_info=e, stack_info=True)
    except ReadTimeout as e:
        console.log(f"[bold red]HTTP Timeout occured:[/bold red]. Ignoring ... {e}")
        logger.error(f"HTTP Timeout occured: {e}", exc_info=e, stack_info=True)
        await asyncio.sleep(5)
    except Exception as e:
        logger.error(f"Unexpected ERROR {e}", exc_info=e, stack_info=True)
        console.print(f"[bold red]An error occurred:[/bold red] {e}")


def _format_xml_file(xml_path: Path) -> None:
    """Pretty-print an XML file using lxml similar to ``xmllint --format``."""
    parser = etree.XMLParser(remove_blank_text=True)

    try:
        tree = etree.parse(str(xml_path), parser=parser)
        tree.write(
            str(xml_path),
            pretty_print=True,
            encoding="utf-8",
            xml_declaration=True,
        )
    except (etree.XMLSyntaxError, OSError) as err:
        logger.warning(f"Failed to format XML file {xml_path}: {err}")


def unzip_invoices(download_dir: Path) -> None:
    """Extract invoice ZIP archives and format any embedded XML files.

    Iterates over all ``*.zip`` files in ``download_dir``, extracting each
    member (except signature files) to a flat location in the same directory,
    prefixing the member filename with the archive stem. Any extracted XML
    file is pretty-printed in-place using lxml.

    Args:
        download_dir: Directory containing the downloaded ZIP archives.
    """
    for zip_file in download_dir.glob("*.zip"):
        try:
            with zipfile.ZipFile(zip_file, "r") as zip_handle:
                for member_info in zip_handle.infolist():
                    if member_info.filename.startswith("semnatura"):
                        continue

                    new_dest = download_dir / (zip_file.stem + "_" + member_info.filename)
                    if not new_dest.exists():
                        logger.info(f"Extracting {member_info.filename} to {new_dest}")
                        extracted = Path(zip_handle.extract(member=member_info, path=download_dir))
                        extracted.rename(new_dest)
                        if new_dest.suffix.lower() == ".xml":
                            _format_xml_file(new_dest)
        except zipfile.BadZipFile as e:
            logger.error(f"Zip File {zip_file} is malformed: {e}. Moving on ...")


def process_invoices():
    """Process downloaded invoices: unzip archives and convert XML to PDF.

    Reads the download directory from settings, calls ``unzip_invoices`` to
    extract all ZIP files, then converts any XML files without a corresponding
    PDF to PDF via the ANAF API.
    """
    settings = get_settings()

    download_dir = settings.storage.download_dir

    unzip_invoices(download_dir=download_dir)

    files_to_process: dict[Path, Path] = {}
    for xml_file in download_dir.glob("*.xml"):
        pdf_file: Path = asyncio.run(get_pdf_path(xml_file))
        if not pdf_file.exists():
            files_to_process[xml_file] = pdf_file

    semaphore = asyncio.Semaphore(2)
    asyncio.run(process_invoices_async(files_to_process=files_to_process, semaphore=semaphore))
