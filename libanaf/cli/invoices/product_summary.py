"""CLI command for product-level invoice summary with Rich rendering."""

import logging
from collections.abc import Iterable
from datetime import datetime
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from libanaf.invoices.common import DateValidationError, format_currency
from libanaf.invoices.product_summary import ProductSummaryRow, summarize_products

logger = logging.getLogger(__name__)
console = Console()


def prod_summary(
    invoice_number: Annotated[str | None, typer.Option("--invoice-number", "-i", help="Invoice Number")] = None,
    supplier_name: Annotated[str | None, typer.Option("--supplier-name", "-s", help="Supplier Name")] = None,
    start_date: Annotated[datetime | None, typer.Option("--start-date", "-sd", help="Start Date")] = None,
    end_date: Annotated[datetime | None, typer.Option("--end-date", "-ed", help="End Date")] = None,
) -> None:
    """Show a product-level summary for invoices or credit notes."""
    typer.echo(
        "Generating product summary with params: "
        f"invoice_number={invoice_number}, supplier_name={supplier_name}, "
        f"start_date={start_date}, end_date={end_date}"
    )
    logger.info(
        "Generating product summary with params: invoice_number=%s, supplier_name=%s, start_date=%s, end_date=%s",
        invoice_number,
        supplier_name,
        start_date,
        end_date,
    )

    try:
        rows = summarize_products(invoice_number, supplier_name, start_date, end_date)
    except DateValidationError as exc:
        if exc.code == "both_required":
            console.print(
                "❌ [bold red]Error: both --start-date and --end-date must be supplied together.[/bold red]"
            )
        elif exc.code == "start_after_end":
            console.print("❌ [bold red]Error: --start-date must be before or equal to --end-date.[/bold red]")
        else:  # pragma: no cover - defensive branch
            console.print("❌ [bold red]Error: invalid date range.[/bold red]")
        raise typer.Exit(code=1)

    if not rows:
        console.print("[yellow]No matching invoices or credit notes found.[/yellow]")
        return

    render_product_summary(rows)


def render_product_summary(rows: Iterable[ProductSummaryRow], *, output: Console | None = None) -> None:
    """Render the product summary rows using Rich.

    Args:
        rows: Product summary rows to display.
        output: Optional Rich Console to write to; defaults to module-level console.
    """
    target_console = output or console

    table = Table(
        show_header=True,
        header_style="bold white on navy_blue",
        title="Invoice Product Summary",
    )
    table.add_column("Supplier", style="green")
    table.add_column("Invoice Number", style="cyan")
    table.add_column("Date", justify="center")
    table.add_column("Total (Invoice)", justify="right", style="blue")
    table.add_column("Total Value (Payable)", justify="right", style="green")
    table.add_column("Product", style="white")
    table.add_column("Product Code", style="white")
    table.add_column("Quantity", justify="right", style="yellow")
    table.add_column("U.M.", style="yellow")
    table.add_column("Price", justify="right", style="white")
    table.add_column("Value", justify="right", style="white")
    table.add_column("VAT Rate", justify="right", style="white")
    table.add_column("VAT Value", justify="right", style="white")
    table.add_column("Discount Rate", justify="right", style="white")
    table.add_column("Discount Value", justify="right", style="white")
    table.add_column("Total Per Line", justify="right", style="magenta")

    for row in rows:
        from libanaf.invoices.product_summary import _format_price, _format_quantity, _format_unit

        table.add_row(
            row.supplier,
            row.document_number,
            row.invoice_date.isoformat(),
            format_currency(row.total_invoice, row.currency),
            format_currency(row.total_payable, row.currency),
            row.product,
            row.product_code or "-",
            _format_quantity(row.quantity),
            _format_unit(row.unit_of_measure),
            _format_price(row.unit_price, row.currency),
            format_currency(row.value, row.currency),
            f"{row.vat_rate:.2f}",
            format_currency(row.vat_value, row.currency),
            f"{abs(row.discount_rate):.2f}%",
            format_currency(abs(row.discount_value), row.currency),
            format_currency(row.total_per_line, row.currency),
        )

    target_console.print(table)
