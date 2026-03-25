"""Summarize locally stored invoices and credit notes.

Provides a data pipeline to collect and aggregate invoice documents
into structured summary rows. Display/rendering is handled by the CLI layer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from collections.abc import Sequence

from libanaf.config import Settings, get_settings
from libanaf.ubl.credit_note import CreditNote
from libanaf.ubl.invoice import Invoice
from libanaf.invoices.common import (
    ensure_date_range,
    extract_supplier_name,
)
from libanaf.invoices.query import collect_documents

logger = logging.getLogger(__name__)


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
    settings: Settings | None = None,
) -> list[SummaryRow]:
    """Collect and summarize matching invoices/credit notes from local storage.

    Args:
        invoice_number: Partial or full invoice number to filter by.
        supplier_name: Partial or full supplier name to filter by.
        start_date: Inclusive start date when combined with ``end_date``.
        end_date: Inclusive end date when combined with ``start_date``.
        settings: Optional settings override; uses cached settings if not provided.

    Returns:
        list[SummaryRow]: Sorted summary rows for matching documents (may be empty).

    Raises:
        DateValidationError: If only one of start/end date is provided, or start > end.
    """
    start, end = ensure_date_range(start_date, end_date)

    app_settings = settings or get_settings()
    dlds_dir = app_settings.storage.download_dir
    logger.debug("summary: using download dir %s", dlds_dir)

    search_dir = Path(dlds_dir).resolve()
    logger.debug(
        "summary collect_documents: dir=%s invoice_number=%s supplier_name=%s start_date=%s end_date=%s",
        search_dir,
        invoice_number,
        supplier_name,
        start_date,
        end_date,
    )
    documents = collect_documents(
        search_dir,
        invoice_number=invoice_number,
        supplier_name=supplier_name,
        start_date=start,
        end_date=end,
    )

    return build_summary_rows(documents)


def build_summary_rows(documents: Sequence[Invoice | CreditNote]) -> list[SummaryRow]:
    """Transform parsed documents into sorted summary rows.

    Args:
        documents: Parsed invoice/credit note documents.

    Returns:
        list[SummaryRow]: Rows sorted by invoice date then document number.
    """
    rows: list[SummaryRow] = []
    for document in documents:
        supplier_name = extract_supplier_name(document.accounting_supplier_party.party)
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
