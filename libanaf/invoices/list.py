import json
import logging
from asyncio import AbstractEventLoop
from collections.abc import Awaitable, Callable
from datetime import datetime

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from httpx import HTTPStatusError, Response
from rich.console import Console
from rich.table import Table

from libanaf.auth import AnafAuthClient
from libanaf.config import get_settings
from libanaf.exceptions import AnafRequestError
from libanaf.types import Filter

console = Console()

logger = logging.getLogger(__name__)


async def fetch_invoice_list(
    days: int | None = 60, cif: int | None = 19507820, filter: Filter | None = Filter.P
) -> dict[str, str | list[dict[str, str]]]:
    """Fetch the invoice message list from the ANAF e-Factura API.

    Builds an authenticated OAuth2 client and issues a GET request to the
    ``listaMesajeFactura`` endpoint. Retries on transient network or HTTP
    errors using exponential backoff configured from settings.

    Args:
        days: Number of past days to include in the query (1–60). Defaults to 60.
        cif: Company CIF to query. Defaults to 19507820.
        filter: Message type filter (E, T, P, R). Defaults to `Filter.P`.

    Returns:
        dict: Parsed JSON response containing a ``"mesaje"`` list of message dicts.

    Raises:
        AnafRequestError: On HTTP errors, timeouts, network errors, or when the
            API returns an ``"eroare"`` field in the response body.
    """
    settings = get_settings()

    base_url: str = settings.efactura.message_list_url

    params: dict[str, str] = {"zile": str(days), "cif": str(cif)}
    if filter:
        params["filtru"] = filter.value

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
    client: AsyncOAuth2Client = auth_client.get_client()

    try:
        from tenacity import (
            AsyncRetrying,
            before_sleep_log,
            retry_if_exception_type,
            stop_after_attempt,
            wait_exponential,
        )

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(settings.retry.count),
            wait=wait_exponential(
                multiplier=settings.retry.backoff_factor, min=settings.retry.delay, max=settings.retry.max_delay
            ),
            retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException, httpx.HTTPStatusError)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        ):
            with attempt:
                response: Response = await client.get(url=base_url, params=params)
                response.raise_for_status()
                response_data = response.json()
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Invalid JSON response: {e}")
        raise AnafRequestError(f"Invalid JSON received from ANAF: {e}") from e
    except HTTPStatusError as e:
        logger.error(f"HTTP Error: {e.response.status_code} - {e.response.text}")
        raise AnafRequestError(f"HTTP Error {e.response.status_code}: {e.response.text}") from e
    except httpx.TimeoutException as e:
        logger.error(f"Request timed out: {e}")
        raise AnafRequestError("Request timed out while connecting to ANAF.") from e
    except httpx.NetworkError as e:
        logger.error(f"Network error: {e}")
        raise AnafRequestError("Network error occurred. Please check your internet connection.") from e
    except httpx.RequestError as e:
        logger.error(f"Request failed: {e}")
        raise AnafRequestError(f"An error occurred while making the request: {e}") from e

    if "eroare" in response_data:
        console.log(f"Error: {response_data['eroare']}", style="bold red")
        logger.error(f"Error: {response_data['eroare']}")
        raise AnafRequestError(f"ANAF API Error: {response_data['eroare']}")

    return response_data


def list_invoices(days: int | None = 60, cif: int | None = 19507820, filter: Filter | None = Filter.P) -> None:
    """Fetch and display the ANAF invoice list in a Rich table.

    Thin synchronous wrapper around ``fetch_invoice_list`` that runs the
    coroutine on the current event loop and delegates rendering to
    ``display_invoices``.

    Args:
        days: Number of past days to query. Defaults to 60.
        cif: Company CIF to query. Defaults to 19507820.
        filter: Message type filter. Defaults to `Filter.P`.

    Raises:
        AnafRequestError: Propagated from ``fetch_invoice_list`` on API errors.
        Exception: Any other unexpected error is logged and re-raised.
    """
    try:
        import asyncio

        loop: AbstractEventLoop = asyncio.get_event_loop()
        func: Callable[
            [int | None, int | None, Filter | None],
            Awaitable[dict[str, str | list[dict[str, str]]]],
        ] = fetch_invoice_list
        data: dict[str, str | list[dict[str, str]]] = loop.run_until_complete(func(days, cif, filter))

        display_invoices(data)
    except AnafRequestError as e:
        logger.error(f"Failed to list invoices: {e}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error getting the invoices list: {e}", exc_info=True)
        raise e


def display_invoices(data: dict) -> None:
    table = Table(title="Lista Mesaje Disponibile", title_justify="left")
    table.add_column("Data Creare", justify="center")
    table.add_column("Id Solicitare", justify="center")
    table.add_column("Id Incarcare", justify="center")
    table.add_column("CIF Emitent", justify="center")
    table.add_column("Tip", justify="center")
    table.add_column("Id", justify="center")

    for mesaj in data.get("mesaje", []):
        data_creare = datetime.strptime(mesaj["data_creare"], "%Y%m%d%H%M").strftime("%Y-%m-%d %H:%M:%S")
        id_solicitare = mesaj["id_solicitare"]
        detalii = mesaj["detalii"]
        tip = mesaj["tip"]
        id_ = mesaj["id"]

        id_incarcare: str = ""
        cif_emitent: str = ""
        details_parts = detalii.split()
        for i, part in enumerate(details_parts):
            if part.startswith("id_incarcare="):
                id_incarcare = part.split("=")[1]
            if part.startswith("cif_emitent="):
                cif_emitent = part.split("=")[1]

        table.add_row(data_creare, id_solicitare, id_incarcare, cif_emitent, tip, id_)

    console.print(table)
