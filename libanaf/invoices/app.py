from datetime import datetime
import logging
from typing import Annotated, Optional

import typer

from ..types import Filter
from .download import download
from .list import list_invoices
from .process import process_invoices
from .show import show_invoices

app = typer.Typer()

logger = logging.getLogger(__name__)


@app.command(name="list")
def invoices_list(
    days: Annotated[
        Optional[int],
        typer.Argument(
            help="Numărul de zile pentru care se face interogarea, format numeric, valorile acceptate de la 1 la 60"
        ),
    ] = 60,
    cif: Annotated[
        Optional[int],
        typer.Argument(help="CIF-ul (numeric) pentru care se doreste sa se obtina lista de mesaje disponibile"),
    ] = 19507820,
    filter: Annotated[
        Optional[Filter],
        typer.Option(help="Parametru folosit pentru filtrarea mesajelor. Valorile acceptate sunt: E, T, P, R"),
    ] = Filter.P,
) -> None:
    """Get the list of available invoices."""
    typer.echo(f"Starting invoice list for the last {days} days for CIF: {cif} and filter {filter}")
    list_invoices(days, cif, filter)


@app.command(name="show")
def show(
    invoice_number: Annotated[Optional[str], typer.Option("--invoice-number", "-i", help="Invoice Number")] = None,
    supplier_name: Annotated[Optional[str], typer.Option("--supplier-name", "-s", help="Supplier Name")] = None,
    start_date: Annotated[Optional[datetime], typer.Option("--start-date", "-sd", help="Start Date")] = None,
    end_date: Annotated[Optional[datetime], typer.Option("--end-date", "-ed", help="End Date")] = None,
):
    """
    Shows all matching invoices. Filtering options:
    - partial invoice_number
    - partial supplier_name
    - start_date / end_date in yyyy-mm-dd format
    (At least one of these filters is required.)
    """
    typer.echo(
        f"Starting show_invoices with params: invoice_number={invoice_number}, supplier_name={supplier_name}, start_date={start_date}, end_date={end_date}"
    )
    show_invoices(invoice_number, supplier_name, start_date, end_date)


@app.command(name="download")
def invoices_download(
    days: Annotated[
        Optional[int],
        typer.Argument(
            help="Numărul de zile pentru care se face interogarea, format numeric, valorile acceptate de la 1 la 60"
        ),
    ] = 60,
    cif: Annotated[
        Optional[int],
        typer.Argument(help="CIF-ul (numeric) pentru care se doreste sa se obtina lista de mesaje disponibile"),
    ] = 19507820,
    filter: Annotated[
        Optional[Filter],
        typer.Option(help="Parametru folosit pentru filtrarea mesajelor. Valorile acceptate sunt: E, T, P, R"),
    ] = Filter.P,
) -> None:
    """
    Download missing invoices and store them locally.
    """
    typer.echo(f"Starting invoice download for the last {days} days for CIF: {cif} and filter {filter}")
    download(days, cif, filter)


@app.command(name="process")
def invoices_process() -> None:
    """
    Processes all invoices in the download folder:
    1. Unzips the files and extract the XML of the invoices
    2. Uses the ANAF API to convert the files to PDF
    """
    typer.echo("Starting processing ...")
    process_invoices()

