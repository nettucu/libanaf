import asyncio
import json
import logging
import zipfile
from pathlib import Path

import aiofiles
import typer
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

from libanaf.comms import make_auth_client
from libanaf.config import get_config, AppConfig

from ..ubl.ubl_document import parse_ubl_document

logger: logging.Logger = logging.getLogger(__name__)


async def get_pdf_path(xml_path: Path) -> Path:
    outfname = xml_path.stem + ".pdf"

    try:
        # Avoid async file IO; parsing directly from path is faster and sufficient here.
        document = parse_ubl_document(xml_path)

        if document is not None:
            fname = document.tofname()
            outfname = xml_path.stem + "_" + fname + ".pdf"

        # if invoice.has_attachment():
        #     invoice.write_attachment(xml_path.parent / outfname)
        #     return None

    except ValidationError as e:
        logger.error(f"Invoice {xml_path}: {e}", exc_info=e)
    except etree.XMLSyntaxError as e:
        logger.error(f"XML Syntax error {xml_path}: {e}", exc_info=e)
    except ParsingError as e:
        logger.error(f"XML Parse error {xml_path}: {e}", exc_info=e)
    except asyncio.CancelledError as e:
        # TODO: should we treat this specially or not ?
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
    """Calls the ANAF API service to convert XML invoices to PDF

    Args:
        xml (Path): The XML file to be uploaded
        pdf (Path): The output path of the PDF received
    """
    config: AppConfig = get_config()

    async with semaphore:
        await asyncio.sleep(0.5)

        url = config.efactura.xml2pdf_url
        headers = {"Content-Type": "text/plain"}
        async with aiofiles.open(xml) as f:
            data = await f.read()

        try:
            response: Response = await client.post(
                url=url, headers=headers, data=data, timeout=30.0
            )  # use 30s timeout for slow moving requests

            if response.status_code != 200:
                logger.error(f"Unexpected HTTP status code {response.status_code} {response.reason_phrase}")
                return f"Unexpected HTTP status code {response.status_code} {response.reason_phrase}"

            content_type = response.headers["content-type"]
            if any(s in content_type for s in ("application/json", "text/plain")):
                # we have a content_type which suggests the response is actually an error
                try:
                    message = response.json()
                    logger.error(f"Error received downloading: {url} - {message['eroare']}")
                    return message
                except json.JSONDecodeError:
                    # this should not happen
                    logger.error(f"Unknow error for url: {url}")
                    return f"Unknow error for url: {url}"

            # Theoretically here all should be well
            async with aiofiles.open(pdf, "wb") as pdf_file:
                await pdf_file.write(response.content)

            # progress.console.log(f"Processing {xml}")
            progress.update(task_id=taskid, file=xml, advance=1, refresh=True)
        except ReadTimeout as timeout:
            progress.console.log(
                f"[bold red]HTTP Timeout occured:[/bold red]. [bold cyan]Ignoring ...[/bold cyan] {timeout}"
            )
            await asyncio.sleep(5)  # sleep additional 5 seconds to cool ANAF down :)

    return f"SUCCESS: {xml}"


async def process_invoices_async(files_to_process: dict[Path, Path], semaphore: asyncio.Semaphore) -> None:
    console = Console()

    try:
        config: AppConfig = get_config()
        httpx_client: AsyncClient = make_auth_client(config).get_client()

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

    except HTTPStatusError as e:
        console.log(f"[bold red]HTTP error occurred:[/bold red] {e}")
    except ReadTimeout as e:
        console.log(f"[bold red]HTTP Timeout occured:[/bold red]. Ignoring ... {e}")
        await asyncio.sleep(5)  # sleep additional 5 seconds to cool ANAF down :)
    except Exception as e:
        logger.error(f"Unexpected ERROR {e}", exc_info=e, stack_info=True)
        console.print(f"[bold red]An error occurred:[/bold red] {e}")


def _format_xml_file(xml_path: Path) -> None:
    """Pretty-print an XML file using lxml similar to ``xmllint --format``.

    Args:
        xml_path (Path): Destination XML file that requires formatting.
    """

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
    """Extract invoices and format any XML payloads located in the download directory.

    Args:
        download_dir (Path): Directory containing raw invoice archives.
    """

    for zip_file in download_dir.glob("*.zip"):
        try:
            with zipfile.ZipFile(zip_file, "r") as zip_handle:
                for member_info in zip_handle.infolist():
                    if member_info.filename.startswith("semnatura"):
                        # ignore XML signature file
                        continue

                    new_dest = download_dir / (zip_file.stem + "_" + member_info.filename)
                    if not new_dest.exists():
                        typer.echo(
                            f"Extracting {member_info.filename} to {new_dest}",
                            color=True,
                        )
                        extracted = Path(zip_handle.extract(member=member_info, path=download_dir))
                        extracted.rename(new_dest)
                        if new_dest.suffix.lower() == ".xml":
                            _format_xml_file(new_dest)
        except zipfile.BadZipFile as e:
            # the zip file is malformed
            logger.error(f"Zip File {zip_file} is malformed: {e}. Moving on ...")


def process_invoices():
    """
    Process downloaded invoices: unpack the zip file and convert XML to PDF.
    """
    config: AppConfig = get_config()

    download_dir = config.storage.download_dir

    unzip_invoices(download_dir=download_dir)

    files_to_process: dict[Path, Path] = {}
    for xml_file in download_dir.glob("*.xml"):
        pdf_file: Path = asyncio.run(get_pdf_path(xml_file))
        if not pdf_file.exists():
            files_to_process[xml_file] = pdf_file

    semaphore = asyncio.Semaphore(2)
    asyncio.run(process_invoices_async(files_to_process=files_to_process, semaphore=semaphore))
