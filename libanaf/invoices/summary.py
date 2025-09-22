"""Summarize locally stored invoices and credit notes.

Provides a console-friendly table with the main financial figures for the
documents that match a set of wildcard filters.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from collections.abc import Iterable, Sequence

import typer
from rich.console import Console
from rich.table import Table

from ..config import AppConfig, get_config
from ..ubl.cac import Party
from .query import gather_candidate_files, parse_and_filter_documents
from ..ubl.credit_note import CreditNote
from ..ubl.invoice import Invoice

logger = logging.getLogger(__name__)
DEFAULT_CONSOLE = Console()


@dataclass(frozen=True, slots=True)
class SummaryRow:
    """Structured information for a summary table row."""

    document_number: str
    supplier: str
    invoice_date: date
    due_date: date | None
    payable_amount: float
    currency: str
    is_credit_note: bool


def summarize_invoices(
    invoice_number: str | None,
    supplier_name: str | None,
    start_date: date | datetime | None,
    end_date: date | datetime | None,
    *,
    config: AppConfig | None = None,
    output: Console | None = None,
) -> None:
    """Render a Rich table summarising matching invoices/credit notes."""

    summary_console = output or DEFAULT_CONSOLE

    if not any([invoice_number, supplier_name]):
        summary_console.print(
            "[bold red]Error: provide at least one filter such as --invoice-number or --supplier-name.[/bold red]"
        )
        raise typer.Exit(code=1)

    start = _to_date(start_date)
    end = _to_date(end_date)

    if (start is None) != (end is None):
        summary_console.print("[bold red]Error: both --start-date and --end-date must be supplied together.[/bold red]")
        raise typer.Exit(code=1)

    if start and end and start > end:
        summary_console.print("[bold red]Error: --start-date must be before or equal to --end-date.[/bold red]")
        raise typer.Exit(code=1)

    app_config = config or get_config()
    dlds_dir = app_config.storage.download_dir
    logger.debug("summary: using download dir %s", dlds_dir)

    documents = collect_documents(
        dlds_dir,
        invoice_number=invoice_number,
        supplier_name=supplier_name,
        start_date=start,
        end_date=end,
    )

    if not documents:
        summary_console.print("[yellow]No matching invoices or credit notes found.[/yellow]")
        return

    rows = build_summary_rows(documents)
    render_summary(rows, console=summary_console)


def collect_documents(
    directory: Path | str,
    *,
    invoice_number: str | None,
    supplier_name: str | None,
    start_date: date | None,
    end_date: date | None,
) -> list[Invoice | CreditNote]:
    """Collect and parse documents that satisfy the supplied filters."""

    search_dir = Path(directory)
    logger.debug(
        "summary collect_documents: dir=%s invoice_number=%s supplier_name=%s start_date=%s end_date=%s",
        search_dir,
        invoice_number,
        supplier_name,
        start_date,
        end_date,
    )

    candidate_files = gather_candidate_files(search_dir, invoice_number, supplier_name, start_date, end_date)
    logger.debug("summary collect_documents: %d candidate files", len(candidate_files))

    documents = parse_and_filter_documents(candidate_files, start_date, end_date)
    logger.debug("summary collect_documents: %d parsed documents", len(documents))
    return documents


def build_summary_rows(documents: Sequence[Invoice | CreditNote]) -> list[SummaryRow]:
    """Transform parsed documents into sorted summary rows."""

    rows: list[SummaryRow] = []
    for document in documents:
        supplier_name = _extract_supplier_name(document.accounting_supplier_party.party)
        amount = document.legal_monetary_total.payable_amount
        if isinstance(document, CreditNote):
            amount *= -1.0

        row = SummaryRow(
            document_number=document.id,
            supplier=supplier_name,
            invoice_date=document.issue_date,
            due_date=document.due_date,
            payable_amount=amount,
            currency=getattr(document, "document_currency_code", "RON"),
            is_credit_note=isinstance(document, CreditNote),
        )
        rows.append(row)

    rows.sort(key=lambda r: (r.invoice_date, r.document_number))
    return rows


def render_summary(rows: Iterable[SummaryRow], *, console: Console | None = None) -> None:
    """Render the summary table to the supplied console."""

    target_console = console or DEFAULT_CONSOLE

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
            _format_amount(row.payable_amount, row.currency),
        )

    target_console.print(table)


def _format_amount(value: float, currency: str) -> str:
    return f"{value:,.2f} {currency}"


def _extract_supplier_name(party: Party) -> str:
    details = party.get_display_str()
    name = details.get("name") or details.get("formatted") or "Unknown"
    return name.strip()


def _to_date(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value
