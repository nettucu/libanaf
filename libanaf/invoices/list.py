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

from ..auth import LibANAF_AuthClient  # Keep for type hinting
from ..comms import make_auth_client  # This will now take config
from ..config import AppConfig, get_config
from ..exceptions import AnafRequestError
from ..types import Filter

console = Console()

logger = logging.getLogger(__name__)


##
## {
# "mesaje": [
#     {
#         "data_creare": "202403290821",
#         "cif": "19507820",
#         "id_solicitare": "4225290319",
#         "detalii": "Factura cu id_incarcare=4225290319 emisa de cif_emitent=8939059 pentru cif_beneficiar=19507820",
#         "tip": "FACTURA PRIMITA",
#         "id": "3347056845"
#     },
##
async def fetch_invoice_list(
    days: int | None = 60, cif: int | None = 19507820, filter: Filter | None = Filter.P
) -> dict[str, str | list[dict[str, str]]]:
    config: AppConfig = get_config()
    # Apply dynamic config for retries if we were using tenacity.Retrying, but since we are using decorator,
    # we might need to rely on the hardcoded defaults requested 5s->10s->20s which matches min=5, multiplier=2 (5, 10, 20).
    # Wait, wait_exponential(multiplier=1, min=5) -> 5, 10, 20?
    # multiplier applied to 2^x.
    # attempt 1: 2^0 * mult = 1 * mult. If min=5, it waits 5.
    # attempt 2: 2^1 * mult = 2 * mult.
    # To get 5, 10, 20:
    #  x=0, wait=5.
    #  x=1, wait=10.
    #  x=2, wait=20.
    # This implies 5 * 2^x. So multiplier=5, exp_base=2.
    # tenacity wait_exponential(multiplier=5, ...)

    # Let's fix the decorator parameters above.

    base_url: str = config.efactura.message_list_url

    params: dict[str, str] = {"zile": str(days), "cif": str(cif)}
    if filter:
        params["filtru"] = filter.value

    # headers = {
    #     "Authorization": f"Bearer {access_token}"
    # }

    # response = requests.get(base_url, params=params, headers=headers)

    # RO23INGB0001000000000222
    # CC750124842
    # 651415973

    auth_client: LibANAF_AuthClient = make_auth_client(config)
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
            stop=stop_after_attempt(config.retry.count),
            wait=wait_exponential(
                multiplier=config.retry.backoff_factor, min=config.retry.delay, max=config.retry.max_delay
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
        # Raise generic error if API returns error field even with 200 OK
        raise AnafRequestError(f"ANAF API Error: {response_data['eroare']}")

    return response_data


def list_invoices(days: int | None = 60, cif: int | None = 19507820, filter: Filter | None = Filter.P) -> None:
    try:
        import asyncio

        loop: AbstractEventLoop = asyncio.get_event_loop()
        func: Callable[
            [int | None, int | None, Filter | None],
            Awaitable[dict[str, str | list[dict[str, str]]]],
        ] = fetch_invoice_list
        data: dict[str, str | list[dict[str, str]]] = loop.run_until_complete(func(days, cif, filter))

        # data = loop.run_until_complete(fetch_invoice_list(days, cif, filter))

        display_invoices(data)
    except AnafRequestError as e:
        # Re-raise to be handled by CLI app wrapper
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
        data_creare = datetime.strptime(mesaj["data_creare"], "%Y%m%d%H%M").strftime(
            "%Y-%m-%d %H:%M:%S"
        )  # mesaj["data_creare"]
        id_solicitare = mesaj["id_solicitare"]
        detalii = mesaj["detalii"]
        tip = mesaj["tip"]
        id_ = mesaj["id"]

        # Extract id_incarcare and cif_emitent from detalii
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
