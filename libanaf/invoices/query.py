"""Invoice document search and parsing utilities shared across CLI commands."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path

from libanaf.ubl.credit_note import CreditNote
from libanaf.ubl.invoice import Invoice
from libanaf.ubl.ubl_document import parse_ubl_document

logger = logging.getLogger(__name__)

DateLike = date | datetime | None
DocumentType = Invoice | CreditNote


def _parse_and_filter_file(
    xml_path: Path,
    invoice_number: str | None,
    supplier_name: str | None,
    start_date: DateLike,
    end_date: DateLike,
) -> DocumentType | None:
    """
    Parse a single XML file and return the document if it matches the filters.
    """
    try:
        doc = parse_ubl_document(xml_path)
    except Exception as exc:
        logger.error("❌ Skipping %s, parse error: %s", xml_path, exc)
        return None

    if not isinstance(doc, DocumentType):
        return None

    if start_date and doc.issue_date < start_date:
        return None
    if end_date and doc.issue_date > end_date:
        return None
    if invoice_number and invoice_number.lower() not in doc.id.lower():
        return None
    if supplier_name:
        supplier = doc.accounting_supplier_party.party
        if (
            supplier.party_name is not None
            and supplier.party_name.name is not None
            and supplier_name.lower() not in supplier.party_name.name.lower()
        ):
            return None
        if (
            supplier.party_legal_entity is not None
            and supplier.party_legal_entity.registration_name is not None
            and supplier_name.lower() not in supplier.party_legal_entity.registration_name.lower()
        ):
            return None

    return doc


def collect_documents(
    dlds_dir: Path,
    invoice_number: str | None,
    supplier_name: str | None,
    start_date: DateLike,
    end_date: DateLike,
    allow_unfiltered: bool = True,
) -> list[DocumentType]:
    """
    Collect and parse documents that satisfy the supplied filters in parallel.
    """
    if not (allow_unfiltered or invoice_number or supplier_name or (start_date and end_date)):
        return []

    results: list[DocumentType] = []
    xml_files = sorted(list(dlds_dir.glob("*.xml")))

    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_doc = {
            executor.submit(
                _parse_and_filter_file,
                xml_path,
                invoice_number,
                supplier_name,
                start_date,
                end_date,
            ): xml_path
            for xml_path in xml_files
        }
        for future in as_completed(future_to_doc):
            doc = future.result()
            if doc:
                results.append(doc)

    return results
