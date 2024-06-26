import logging
from asyncio import AbstractEventLoop
from datetime import datetime
from typing import Awaitable, Callable, List, Optional

from authlib.integrations.httpx_client import AsyncOAuth2Client
from httpx import HTTPStatusError, Response
from rich.console import Console
from rich.table import Table

from ..auth import LibANAF_AuthClient
from ..comms import make_auth_client
from ..config import Configuration
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
async def fetch_invoice_list(days: Optional[int] = 60, cif: Optional[int] = 19507820, filter: Optional[Filter] = Filter.P) -> dict[str, str | list[dict[str, str]]]:
    config = Configuration().load_config()
    # access_token = config["connection"]["access_token"]
    # "https://api.anaf.ro/prod/FCTEL/rest/listaMesajeFactura"
    base_url: str = config["efactura"]["message_list_url"]

    params: dict[str, str] = {
        "zile": str(days),
        "cif": str(cif)
    }
    if filter:
        params["filtru"] = filter.value

    # headers = {
    #     "Authorization": f"Bearer {access_token}"
    # }

    # response = requests.get(base_url, params=params, headers=headers)

    auth_client: LibANAF_AuthClient = make_auth_client()
    httpx: AsyncOAuth2Client = auth_client.get_client()

    response: Response = await httpx.get(url=base_url,params=params)
    response_data = response.json()

    if "eroare" in response_data:
        console.log(f"Error: {response_data['eroare']}", style="bold red")
        logger.error(f"Error: {response_data['eroare']}")

    return response_data


def list_invoices(days: Optional[int] = 60, cif: Optional[int] = 19507820, filter: Optional[Filter] = Filter.P) -> None:
    try:
        import asyncio
        loop: AbstractEventLoop = asyncio.get_event_loop()
        func: Callable[[Optional[int], Optional[int], Optional[Filter]], Awaitable[dict[str, str | list[dict[str, str]]]]] = fetch_invoice_list
        data: dict[str, str | list[dict[str, str]]] = loop.run_until_complete(func(days, cif, filter))

        # data = loop.run_until_complete(fetch_invoice_list(days, cif, filter))

        display_invoices(data)
    except HTTPStatusError as e:
        logger.error("ERROR getting the invoices list", e, stack_info=True)
    except Exception as e:
        logger.error("ERROR getting the invoices list", e, stack_info=True)


def display_invoices(data: dict) -> None:
    table = Table(title="Lista Mesaje Disponibile", title_justify="left")
    table.add_column("Data Creare", justify="center")
    table.add_column("Id Solicitare", justify="center")
    table.add_column("Id Incarcare", justify="center")
    table.add_column("CIF Emitent", justify="center")
    table.add_column("Tip", justify="center")
    table.add_column("Id", justify="center")

    for mesaj in data.get("mesaje", []):
        data_creare = datetime.strptime(mesaj["data_creare"], "%Y%m%d%H%M").strftime('%Y-%m-%d %H:%M:%S') # mesaj["data_creare"]
        id_solicitare = mesaj["id_solicitare"]
        detalii = mesaj["detalii"]
        tip = mesaj["tip"]
        id_ = mesaj["id"]

        # Extract id_incarcare and cif_emitent from detalii
        id_incarcare: str = ""
        cif_emitent : str = ""
        details_parts = detalii.split()
        for i, part in enumerate(details_parts):
            if part.startswith("id_incarcare="):
                id_incarcare = part.split("=")[1]
            if part.startswith("cif_emitent="):
                cif_emitent = part.split("=")[1]

        table.add_row(data_creare, id_solicitare, id_incarcare, cif_emitent, tip, id_)

    console.print(table)
