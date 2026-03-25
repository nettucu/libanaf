"""CLI command for listing invoices from the ANAF API."""

import logging
from asyncio import AbstractEventLoop
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from libanaf.exceptions import AnafRequestError
from libanaf.invoices.list import fetch_invoice_list
from libanaf.types import Filter

console = Console()
logger = logging.getLogger(__name__)


def invoices_list(
    days: Annotated[
        int | None,
        typer.Argument(
            help="Numărul de zile pentru care se face interogarea, format numeric, valorile acceptate de la 1 la 60"
        ),
    ] = 30,
    cif: Annotated[
        int | None,
        typer.Argument(help="CIF-ul (numeric) pentru care se doreste sa se obtina lista de mesaje disponibile"),
    ] = 19507820,
    filter: Annotated[
        Filter | None,
        typer.Option(help="Parametru folosit pentru filtrarea mesajelor. Valorile acceptate sunt: E, T, P, R"),
    ] = Filter.P,
) -> None:
    """Get the list of available invoices."""
    typer.echo(f"Starting invoice list for the last {days} days for CIF: {cif} and filter {filter}")
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
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"An unexpected error occurred: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def display_invoices(data: dict) -> None:
    """Render the ANAF invoice message list in a Rich table.

    Args:
        data: Parsed JSON response from ``fetch_invoice_list``.
    """
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
        for part in details_parts:
            if part.startswith("id_incarcare="):
                id_incarcare = part.split("=")[1]
            if part.startswith("cif_emitent="):
                cif_emitent = part.split("=")[1]

        table.add_row(data_creare, id_solicitare, id_incarcare, cif_emitent, tip, id_)

    console.print(table)
