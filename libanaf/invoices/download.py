import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Optional
from collections.abc import Awaitable, Callable

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

from ..auth import LibANAF_AuthClient
from ..comms import make_auth_client
from ..config import Configuration
from ._utils import is_invoice_downloaded
from .list import fetch_invoice_list

logger: logging.Logger = logging.getLogger(__name__)
config: dict[str, Any] = Configuration().load_config()

#  165   0000: HTTP/1.1 200
#  167   0000: Date: Thu, 13 Jun 2024 16:44:19 GMT
#  169   0000: Content-Type: text/plain;charset=UTF-8
#  171   0000: Content-Length: 92
#  173   0000: Connection: keep-alive
#  175   0000: Strict-Transport-Security: max-age=31536000; includeSubDomains
#
#  196   19:44:19.267781 <= Recv data, 92 bytes (0x5c)
#  197   0000: {"eroare":"Pentru id=4596 nu exista inregistrata nici o factura"
#  198   0040: ,"titlu":"Descarcare mesaj"}


async def download_invoice(
    client: AsyncClient, invoice_id: str, download_dir: Path, progress: Progress, task_id, semaphore: asyncio.Semaphore
):
    """
    Download an invoice by ID and save it to the download directory.
    """
    async with semaphore:
        await asyncio.sleep(0.1)  # Add a delay of ~1 second before starting the download
        #  https://api.anaf.ro/prod/FCTEL/rest/descarcare?id={invoice_id}
        url_base = config["efactura"]["download_url"]
        url: str = f"{url_base}?id={invoice_id}"
        logger.debug(f"Downloading from: {url}")
        response: Response = await client.get(url)

        logger.debug(response.headers)
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

        file_path: Path = download_dir / f"{invoice_id}.zip"
        with open(file_path, "wb") as file:
            file.write(response.content)
            progress.update(task_id, advance=1, refresh=True)  # len(response.content))

        return file_path


async def download_all_invoices(invoices_to_download: list[str], download_dir: Path) -> None:
    semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent downloads
    auth_client: LibANAF_AuthClient = make_auth_client()
    # httpx: AsyncOAuth2Client = auth_client.get_client()

    async with auth_client.get_client() as client:
        with Progress(
            SpinnerColumn(),
            MofNCompleteColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.1f}%"),
            transient=False,
        ) as progress:
            # tasks = []
            overall_progress = progress.add_task("Overall progress", total=len(invoices_to_download))
            progress.start_task(overall_progress)

            tasks = [
                download_invoice(
                    client, invoice_id, download_dir, progress, task_id=overall_progress, semaphore=semaphore
                )
                for invoice_id in invoices_to_download
            ]
            # for invoice_id in invoices_to_download:
            #     # task_id = progress.add_task(f"Downloading {invoice_id}", total=100)
            #     task = download_invoice(client, invoice_id, download_dir, progress, task_id=None, semaphore=semaphore)
            #     tasks.append(task)

            results = await asyncio.gather(*tasks)
            logger.debug(f"Downloaded files: {results}")
            # for _ in results:
            #     progress.update(overall_progress, advance=1)


def download(days: int | None = 60, cif: int | None = 19507820, filter: Filter | None = Filter.P) -> None:
    """
    Download missing invoices and store them locally.
    """
    console = Console()
    download_dir = Path(config["storage"]["download_directory"])
    download_dir.mkdir(parents=True, exist_ok=True)

    try:
        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        func: Callable[[int | None, int | None, Filter | None], Awaitable[dict[str, str | list[dict[str, str]]]]] = (
            fetch_invoice_list
        )
        data: dict[str, str | list[dict[str, str]]] = loop.run_until_complete(func(days, cif, filter))
        # data = loop.run_until_complete(fetch_invoice_list(days, cif, filter))
        messages: str | list[dict[str, str]] = data.get("mesaje", [])

        if not messages:
            console.print("[bold yellow]No messages found to download.[/bold yellow]")
            return

        if isinstance(messages, list):  # noqa: E999
            invoices_to_download: list[str] = [
                message["id"] for message in messages if not is_invoice_downloaded(message, download_dir)
            ]

        if not invoices_to_download:
            console.print("[bold green]All invoices are already downloaded.[/bold green]")
            return

        console.print(f"[bold blue]Downloading {len(invoices_to_download)} invoices...[/bold blue]")

        loop.run_until_complete(download_all_invoices(invoices_to_download, download_dir))
        console.print("[bold green]Downloaded all missing invoices.[/bold green]")

    except HTTPStatusError as e:
        console.print(f"[bold red]HTTP error occurred:[/bold red] {e}")
    except Exception as e:
        logger.error(f"Unexpected ERROR {e}", exc_info=e, stack_info=True)
        console.print(f"[bold red]An error occurred:[/bold red] {e}")

    except HTTPStatusError as e:
        console.print(f"[bold red]HTTP error occurred:[/bold red] {e}")
    except Exception as e:
        logger.error(f"Unexpected ERROR {e}", exc_info=e, stack_info=True)
        console.print(f"[bold red]An error occurred:[/bold red] {e}")
