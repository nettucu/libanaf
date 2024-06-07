from datetime import datetime
from typing import Dict, Optional

import requests
from rich.console import Console
from rich.table import Table

from .config import Configuration
from .types import Filter

console = Console()

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


def list_invoices(zile: int, cif: int, filtru: Optional[Filter] = Filter.P) -> None:
    config = Configuration().load_config()
    access_token = config["connection"]["access_token"]
    base_url = "https://api.anaf.ro/prod/FCTEL/rest/listaMesajeFactura"

    params: Dict[str, str] = {
        "zile": str(zile),
        "cif": str(cif)
    }
    if filtru:
        params["filtru"] = filtru.value

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(base_url, params=params, headers=headers)
    response_data = response.json()

    if "eroare" in response_data:
        console.log(f"Error: {response_data['eroare']}", style="bold red")
        return

    table = Table(title="Lista Mesaje Disponibile")
    table.add_column("Data Creare", justify="center")
    table.add_column("Id Solicitare", justify="center")
    table.add_column("Id Incarcare", justify="center")
    table.add_column("CIF Emitent", justify="center")
    table.add_column("Tip", justify="center")
    table.add_column("Id", justify="center")

    for mesaj in response_data.get("mesaje", []):
        data_creare = datetime.strptime(mesaj["data_creare"], "%Y%m%d%H%M").strftime('%Y-%m-%d %H:%M:%S') # mesaj["data_creare"]
        id_solicitare = mesaj["id_solicitare"]
        detalii = mesaj["detalii"]
        tip = mesaj["tip"]
        id_ = mesaj["id"]

        # Extract id_incarcare and cif_emitent from detalii
        id_incarcare = ""
        cif_emitent = ""
        details_parts = detalii.split()
        for i, part in enumerate(details_parts):
            if part.startswith("id_incarcare="):
                id_incarcare = part.split("=")[1]
            if part.startswith("cif_emitent="):
                cif_emitent = part.split("=")[1]

        table.add_row(data_creare, id_solicitare, id_incarcare, cif_emitent, tip, id_)

    console.print(table)
