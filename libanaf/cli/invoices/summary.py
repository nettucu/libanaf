"""CLI command for summarizing invoices in a Rich table."""

import logging
from collections.abc import Iterable
from datetime import datetime
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from libanaf.invoices.common import DateValidationError, format_currency
from libanaf.invoices.summary import SummaryRow, summarize_invoices

logger = logging.getLogger(__name__)
console = Console()


def summary(
    invoice_number: Annotated[str | None, typer.Option("--invoice-number", "-i", help="Invoice Number")] = None,
    supplier_name: Annotated[str | None, typer.Option("--supplier-name", "-s", help="Supplier Name")] = None,
    start_date: Annotated[datetime | None, typer.Option("--start-date", "-sd", help="Start Date")] = None,
    end_date: Annotated[datetime | None, typer.Option("--end-date", "-ed", help="End Date")] = None,
) -> None:
    """Show a tabular summary of invoices/credit notes that match wildcard filters."""
    typer.echo(
        "Generating summary with params: "
        f"invoice_number={invoice_number}, supplier_name={supplier_name}, "
        f"start_date={start_date}, end_date={end_date}"
    )
    logger.info(
        "Generating summary with params: invoice_number=%s, supplier_name=%s, start_date=%s, end_date=%s",
        invoice_number,
        supplier_name,
        start_date,
        end_date,
    )

    if not any([invoice_number, supplier_name]):
        console.print(
            "❌ [bold red]Error: provide at least one filter such as --invoice-number or --supplier-name.[/bold red]"
        )
        raise typer.Exit(code=1)

    try:
        rows = summarize_invoices(invoice_number, supplier_name, start_date, end_date)
    except DateValidationError as exc:
        if exc.code == "both_required":
            console.print(
                "[bold red]Error: both --start-date and --end-date must be supplied together.[/bold red]"
            )
        elif exc.code == "start_after_end":
            console.print("[bold red]Error: --start-date must be before or equal to --end-date.[/bold red]")
        else:  # pragma: no cover - defensive branch
            console.print("[bold red]Error: invalid date range.[/bold red]")
        raise typer.Exit(code=1)

    if not rows:
        console.print("[yellow]No matching invoices or credit notes found.[/yellow]")
        return

    render_summary(rows)


def render_summary(rows: Iterable[SummaryRow], *, output: Console | None = None) -> None:
    """Render the summary table to the supplied console.

    Args:
        rows: Summary rows to display.
        output: Optional Rich Console to write to; defaults to module-level console.
    """
    target_console = output or console

    table = Table(
        show_header=True,
        header_style="bold white on navy_blue",
        title="Invoices Summary",
    )
    table.add_column("Invoices Number", style="cyan", no_wrap=True)
    table.add_column("Supplier", style="green")
    table.add_column("Invoice Date", style="white")
    table.add_column("Due Date", style="white")
    table.add_column("Total Value (Payable)", justify="right", style="magenta")

    for row in rows:
        table.add_row(
            row.document_number,
            row.supplier,
            row.invoice_date.isoformat(),
            row.due_date.isoformat() if row.due_date else "N/A",
            format_currency(row.payable_amount, row.currency),
        )

    target_console.print(table)
