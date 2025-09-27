"""Shared helpers for invoice reporting commands."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from ..ubl.cac import Party
from ..ubl.credit_note import CreditNote
from ..ubl.invoice import Invoice
from .query import gather_candidate_files, parse_and_filter_documents

DocumentType = Invoice | CreditNote


class DateValidationError(ValueError):
    """Raised when a start/end date combination is invalid."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def normalize_date(value: date | datetime | None) -> date | None:
    """Coerce `datetime` values to `date` for easier comparisons."""

    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def ensure_date_range(
    start: date | datetime | None,
    end: date | datetime | None,
) -> tuple[date | None, date | None]:
    """Return validated (start, end) dates or raise an error."""

    start_date = normalize_date(start)
    end_date = normalize_date(end)

    if (start_date is None) != (end_date is None):
        raise DateValidationError("both_required")
    if start_date and end_date and start_date > end_date:
        raise DateValidationError("start_after_end")

    return start_date, end_date


def collect_documents(
    directory: Path | str,
    *,
    invoice_number: str | None,
    supplier_name: str | None,
    start_date: date | None,
    end_date: date | None,
    allow_unfiltered: bool,
) -> list[DocumentType]:
    """Collect and parse documents that satisfy the supplied filters."""

    search_dir = Path(directory)

    if invoice_number or supplier_name:
        candidate_files = gather_candidate_files(search_dir, invoice_number, supplier_name, start_date, end_date)
    elif allow_unfiltered:
        candidate_files = set(search_dir.glob("*.xml"))
    else:
        return []

    return parse_and_filter_documents(candidate_files, start_date, end_date)


def extract_supplier_name(party: Party) -> str:
    """Return a human friendly supplier name from a `Party`."""

    details = party.get_display_str()
    name = details.get("name") or details.get("formatted") or "Unknown"
    return name.strip()


def format_currency(value: Decimal | float | int, currency: str) -> str:
    """Format numeric values with a currency suffix."""

    return f"{value:,.2f} {currency}"
