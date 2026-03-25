"""CLI command for rendering invoices to PDF locally from UBL XML."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from libanaf.config import get_settings
from libanaf.invoices.common import DateValidationError, ensure_date_range
from libanaf.invoices.pdf_render import render_invoice_pdf
from libanaf.invoices.query import collect_documents

logger = logging.getLogger(__name__)


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

    settings = get_settings()
    dlds_dir = Path(settings.storage.download_dir).resolve()

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

    console.print(f"\n[bold]Summary:[/bold] {generated} generated, {skipped} skipped (already exist).")
