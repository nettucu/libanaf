import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from httpx import AsyncClient, HTTPStatusError, Response
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
)

from libanaf.types import Filter
from libanaf.auth import AnafAuthClient
from libanaf.config import get_settings
from libanaf.exceptions import TokenExpiredError
from libanaf.failure_tracker import record_network_failure, record_success
from libanaf.invoices._retry import anaf_retrying
from libanaf.invoices.list import fetch_invoice_list
from libanaf.notifications import send_network_failure_alert, send_token_expired_alert


def is_invoice_downloaded(message: dict[str, str], download_dir: Path) -> bool:
    """Check whether an invoice archive is already present on disk.

    Args:
        message: Raw message dict from the ANAF API (must contain ``"id"`` and
            ``"id_solicitare"`` keys).
        download_dir: Directory to check for existing ZIP files.

    Returns:
        bool: ``True`` if any of the expected archive filenames already exist.
    """
    invoice_id: str = message["id"]
    id_solicitare: str = message["id_solicitare"]
    possible_filenames = [f"{invoice_id}.zip", f"{id_solicitare}.zip", f"efactura_{id_solicitare}.zip"]
    return any((download_dir / filename).exists() for filename in possible_filenames)

logger: logging.Logger = logging.getLogger(__name__)


async def download_invoice(
    client: AsyncClient, invoice_id: str, download_dir: Path, progress: Progress, task_id, semaphore: asyncio.Semaphore
):
    """Download a single invoice archive by ID.

    Issues a GET request to the ANAF download endpoint for the given
    `invoice_id`, writing the resulting ZIP content to `download_dir`.
    If the response indicates an error (JSON or text payload), the parsed
    message is returned instead of a file path. Concurrency is throttled
    via the provided ``semaphore``.

    Args:
        client: Initialized `httpx.AsyncClient` (OAuth2-enabled) to make requests.
        invoice_id: The invoice/message identifier to download.
        download_dir: Directory where the downloaded ZIP file is saved.
        progress: Rich `Progress` instance used to update overall progress.
        task_id: Progress task identifier to advance on successful download.
        semaphore: Semaphore limiting the number of concurrent downloads.

    Returns:
        Path | dict | str: The path to the saved ZIP on success; otherwise a
        parsed error payload (dict) or a short error description (str).

    Raises:
        OSError: If writing the downloaded file to disk fails.
        httpx.RequestError: On underlying transport errors while performing the request.
    """
    settings = get_settings()

    async with semaphore:
        await asyncio.sleep(0.1)
        url_base = settings.efactura.download_url
        url: str = f"{url_base}?id={invoice_id}"
        logger.debug(f"Downloading from: {url}")

        response: Response | None = None
        try:
            async for attempt in anaf_retrying(settings.retry, logger):
                with attempt:
                    response = await client.get(url)
                    response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to download {url} after retries: {e}")
            return f"Failed to download: {e}"

        if response is None:
            return f"Failed to get response for {url}"

        logger.debug(response.headers)
        if response.status_code != 200:
            logger.error(f"Unexpected HTTP status code {response.status_code} {response.reason_phrase}")
            return f"Unexpected HTTP status code {response.status_code} {response.reason_phrase}"

        content_type = response.headers["content-type"]
        if any(s in content_type for s in ("application/json", "text/plain")):
            try:
                message = response.json()
                logger.error(f"Error received downloading: {url} - {message['eroare']}")
                return message
            except json.JSONDecodeError:
                logger.error(f"Unknow error for url: {url}")
                return f"Unknow error for url: {url}"

        file_path: Path = download_dir / f"{invoice_id}.zip"
        with open(file_path, "wb") as file:
            file.write(response.content)
            progress.update(task_id, advance=1, refresh=True)

        return file_path


async def download_all_invoices(invoices_to_download: list[str], download_dir: Path) -> None:
    """Download a batch of invoices concurrently.

    Creates an authenticated HTTP client, sets up a progress display, and
    downloads all invoices listed in ``invoices_to_download`` with a
    concurrency limit of 5. Progress is reported via a single overall task.

    Args:
        invoices_to_download: List of invoice/message IDs to download.
        download_dir: Destination directory for the downloaded ZIP files.

    Raises:
        httpx.RequestError: If network/transport errors occur during requests.
        OSError: If saving any file to disk fails.
    """
    settings = get_settings()
    semaphore = asyncio.Semaphore(5)
    auth_client = AnafAuthClient(
        client_id=settings.auth.client_id,
        client_secret=settings.auth.client_secret,
        auth_url=settings.auth.auth_url,
        token_url=settings.auth.token_url,
        redirect_uri=settings.auth.redirect_uri,
        access_token=settings.connection.access_token,
        refresh_token=settings.connection.refresh_token,
        cert_file=settings.connection.tls_cert_file,
        key_file=settings.connection.tls_key_file,
    )

    async with auth_client.get_client() as client:
        with Progress(
            SpinnerColumn(),
            MofNCompleteColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.1f}%"),
            transient=False,
        ) as progress:
            overall_progress = progress.add_task("Overall progress", total=len(invoices_to_download))
            progress.start_task(overall_progress)

            tasks = [
                download_invoice(
                    client, invoice_id, download_dir, progress, task_id=overall_progress, semaphore=semaphore
                )
                for invoice_id in invoices_to_download
            ]

            results = await asyncio.gather(*tasks)
            logger.debug(f"Downloaded files: {results}")


def download(days: int | None = 60, cif: int | None = 19507820, filter: Filter | None = Filter.P) -> None:
    """Discover and download missing invoices.

    Queries the ANAF API for recent invoice messages using the given filters,
    determines which invoices are not yet present on disk, and downloads the
    missing ones to the configured download directory. Displays progress and
    reports errors to the console.

    Args:
        days: Number of past days to query for messages. Defaults to 30.
        cif: Company CIF used for filtering. Defaults to 19507820.
        filter: Additional filter applied to the message list (see `Filter`).
    """
    console = Console()
    settings = get_settings()
    download_dir = settings.storage.download_dir
    download_dir.mkdir(parents=True, exist_ok=True)

    try:
        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        func: Callable[[int | None, int | None, Filter | None], Awaitable[dict[str, str | list[dict[str, str]]]]] = (
            fetch_invoice_list
        )
        data: dict[str, str | list[dict[str, str]]] = loop.run_until_complete(func(days, cif, filter))
        messages: str | list[dict[str, str]] = data.get("mesaje", [])

        if not messages:
            console.print("[bold yellow]No messages found to download.[/bold yellow]")
            if settings.notification.email_to:
                record_success(settings.state.state_file)
            return

        invoices_to_download: list[str] = []
        if isinstance(messages, list):
            invoices_to_download = [
                message["id"] for message in messages if not is_invoice_downloaded(message, download_dir)
            ]

        if not invoices_to_download:
            console.print("[bold green]All invoices are already downloaded.[/bold green]")
            logger.info("All invoices are already downloaded.")
            if settings.notification.email_to:
                record_success(settings.state.state_file)
            return

        console.print(f"[bold blue]Downloading {len(invoices_to_download)} invoices...[/bold blue]")
        logger.info(f"Downloading {len(invoices_to_download)} invoices...")

        loop.run_until_complete(download_all_invoices(invoices_to_download, download_dir))
        console.print("[bold green]Downloaded all missing invoices.[/bold green]")
        logger.info("Downloaded all missing invoices.")
        if settings.notification.email_to:
            record_success(settings.state.state_file)

    except TokenExpiredError as e:
        logger.error(f"ANAF token expired — hard re-auth required: {e}", exc_info=e)
        console.print("[bold red]ANAF token expired:[/bold red] run 'libanaf auth' to re-authorize.")
        if settings.notification.email_to:
            send_token_expired_alert(
                to=settings.notification.email_to,
                error=str(e),
                smtp_host=settings.notification.smtp_host,
                smtp_port=settings.notification.smtp_port,
                smtp_user=settings.notification.smtp_user,
                smtp_password=settings.notification.smtp_password,
            )
    except HTTPStatusError as e:
        console.print(f"[bold red]HTTP error occurred:[/bold red] {e}")
        logger.error(f"HTTP error occurred: {e}", exc_info=e, stack_info=True)
        if settings.notification.email_to:
            threshold = settings.notification.network_failure_threshold
            if record_network_failure(settings.state.state_file, threshold):
                send_network_failure_alert(
                    to=settings.notification.email_to,
                    error=str(e),
                    failure_count=threshold,
                    smtp_host=settings.notification.smtp_host,
                    smtp_port=settings.notification.smtp_port,
                    smtp_user=settings.notification.smtp_user,
                    smtp_password=settings.notification.smtp_password,
                )
    except Exception as e:
        logger.error(f"Unexpected ERROR {e}", exc_info=e, stack_info=True)
        console.print(f"[bold red]An error occurred:[/bold red] {e}")
        if settings.notification.email_to:
            threshold = settings.notification.network_failure_threshold
            if record_network_failure(settings.state.state_file, threshold):
                send_network_failure_alert(
                    to=settings.notification.email_to,
                    error=str(e),
                    failure_count=threshold,
                    smtp_host=settings.notification.smtp_host,
                    smtp_port=settings.notification.smtp_port,
                    smtp_user=settings.notification.smtp_user,
                    smtp_password=settings.notification.smtp_password,
                )
