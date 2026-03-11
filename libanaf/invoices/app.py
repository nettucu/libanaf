import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ..config import get_config
from ..exceptions import AnafRequestError
from ..types import Filter
from .common import DateValidationError, ensure_date_range
from .download import download
from .list import list_invoices
from .pdf_render import render_invoice_pdf
from .process import process_invoices
from .product_summary import summarize_products
from .query import collect_documents
from .show import show_invoices
from .summary import summarize_invoices

app = typer.Typer()

logger = logging.getLogger(__name__)


@app.command(name="list")
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
        list_invoices(days, cif, filter)
    except AnafRequestError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"An unexpected error occurred: {e}", fg=typer.colors.RED)
        # We might want to see the traceback for unexpected errors if verbose, but standard user behavior is clean exit
        # For now, consistent behavior:
        raise typer.Exit(code=1)


@app.command(name="show")
def show(
    invoice_number: Annotated[str | None, typer.Option("--invoice-number", "-i", help="Invoice Number")] = None,
    supplier_name: Annotated[str | None, typer.Option("--supplier-name", "-s", help="Supplier Name")] = None,
    start_date: Annotated[datetime | None, typer.Option("--start-date", "-sd", help="Start Date")] = None,
    end_date: Annotated[datetime | None, typer.Option("--end-date", "-ed", help="End Date")] = None,
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


@app.command(name="summary")
def summary(
    invoice_number: Annotated[str | None, typer.Option("--invoice-number", "-i", help="Invoice Number")] = None,
    supplier_name: Annotated[str | None, typer.Option("--supplier-name", "-s", help="Supplier Name")] = None,
    start_date: Annotated[datetime | None, typer.Option("--start-date", "-sd", help="Start Date")] = None,
    end_date: Annotated[datetime | None, typer.Option("--end-date", "-ed", help="End Date")] = None,
):
    """Show a tabular summary of invoices/credit notes that match wildcard filters."""

    typer.echo(
        "Generating summary with params: "
        f"invoice_number={invoice_number}, supplier_name={supplier_name}, start_date={start_date}, end_date={end_date}"
    )
    logger.info(
        "Generating summary with params: "
        f"invoice_number={invoice_number}, supplier_name={supplier_name}, start_date={start_date}, end_date={end_date}"
    )
    summarize_invoices(invoice_number, supplier_name, start_date, end_date)


@app.command(name="prod-summary")
def prod_summary(
    invoice_number: Annotated[str | None, typer.Option("--invoice-number", "-i", help="Invoice Number")] = None,
    supplier_name: Annotated[str | None, typer.Option("--supplier-name", "-s", help="Supplier Name")] = None,
    start_date: Annotated[datetime | None, typer.Option("--start-date", "-sd", help="Start Date")] = None,
    end_date: Annotated[datetime | None, typer.Option("--end-date", "-ed", help="End Date")] = None,
) -> None:
    """Show a product-level summary for invoices or credit notes."""

    typer.echo(
        "Generating product summary with params: "
        f"invoice_number={invoice_number}, supplier_name={supplier_name}, start_date={start_date}, end_date={end_date}"
    )
    logger.info(
        "Generating product summary with params: "
        f"invoice_number={invoice_number}, supplier_name={supplier_name}, start_date={start_date}, end_date={end_date}"
    )
    summarize_products(invoice_number, supplier_name, start_date, end_date, render_output=True)


@app.command(name="download")
def invoices_download(
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
    """
    Download missing invoices and store them locally.
    """
    typer.echo(f"Starting invoice download for the last {days} days for CIF: {cif} and filter {filter}")
    logger.info(f"Starting invoice download for the last {days} days for CIF: {cif} and filter {filter}")
    download(days, cif, filter)


@app.command(name="process")
def invoices_process() -> None:
    """
    Processes all invoices in the download folder:
    1. Unzips the files and extract the XML of the invoices
    2. Uses the ANAF API to convert the files to PDF
    """
    typer.echo("Starting processing ...")
    logger.info("Starting processing ...")
    process_invoices()


@app.command(name="render-pdf")
def render_pdf(
    invoice_number: Annotated[str | None, typer.Option("--invoice-number", "-i", help="Invoice Number")] = None,
    supplier_name: Annotated[str | None, typer.Option("--supplier-name", "-s", help="Supplier Name")] = None,
    start_date: Annotated[datetime | None, typer.Option("--start-date", "-sd", help="Start Date")] = None,
    end_date: Annotated[datetime | None, typer.Option("--end-date", "-ed", help="End Date")] = None,
) -> None:
    """Generate PDF invoices locally from UBL XML files (no ANAF API call)."""
    console = Console()

    if not any([invoice_number, supplier_name, (start_date and end_date)]):
        console.print(
            "❌ [bold red]Error: You must specify at least one filter, such as "
            "--invoice-number, --supplier-name, or both --start-date and --end-date.[/bold red]"
        )
        raise typer.Exit(code=1)

    try:
        start, end = ensure_date_range(start_date, end_date)
    except DateValidationError as exc:
        if exc.code == "both_required":
            console.print("❌ [bold red]Error: both --start-date and --end-date must be supplied together.[/bold red]")
        elif exc.code == "start_after_end":
            console.print("❌ [bold red]Error: --start-date must be before or equal to --end-date.[/bold red]")
        else:
            console.print("❌ [bold red]Error: invalid date range.[/bold red]")
        raise typer.Exit(code=1)

    config = get_config()
    dlds_dir = Path(config.storage.download_dir).resolve()

    logger.info(
        "render-pdf: invoice_number=%s supplier_name=%s start=%s end=%s dir=%s",
        invoice_number,
        supplier_name,
        start,
        end,
        dlds_dir,
    )

    documents = collect_documents(
        dlds_dir,
        invoice_number=invoice_number,
        supplier_name=supplier_name,
        start_date=start,
        end_date=end,
        allow_unfiltered=False,
    )

    if not documents:
        console.print("[yellow]No matching invoices or credit notes found.[/yellow]")
        return

    generated = 0
    skipped = 0

    for doc in sorted(documents, key=lambda d: (d.issue_date, d.id)):
        try:
            fname = doc.tofname()
        except ValueError:
            fname = doc.id

        output_path = dlds_dir / f"{fname}_local.pdf"

        if output_path.exists():
            skipped += 1
            logger.debug("Skipping existing PDF: %s", output_path)
            continue

        try:
            render_invoice_pdf(doc, output_path)
            generated += 1
            console.print(f"[green]✓[/green] Generated: [cyan]{output_path.name}[/cyan]")
        except Exception as exc:
            console.print(f"[red]✗[/red] Failed to render {doc.id}: {exc}")
            logger.error("Failed to render PDF for %s: %s", doc.id, exc, exc_info=exc)

    console.print(
        f"\n[bold]Summary:[/bold] {generated} generated, {skipped} skipped (already exist)."
    )
