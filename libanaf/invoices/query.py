"""Invoice document search and parsing utilities shared across CLI commands."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from pathlib import Path

from libanaf.ubl.credit_note import CreditNote
from libanaf.ubl.invoice import Invoice
from libanaf.ubl.ubl_document import parse_ubl_document

logger = logging.getLogger(__name__)

DateLike = date | datetime | None
DocumentType = Invoice | CreditNote


def compile_search_patterns(
    invoice_number: str | None,
    supplier_name: str | None,
) -> list[re.Pattern[str]]:
    """Compile case-insensitive regex patterns for XML invoice metadata."""
    patterns: list[re.Pattern[str]] = []
    if invoice_number:
        inv_esc = re.escape(invoice_number)
        patterns.append(re.compile(rf"<cbc:ID>[^<]*{inv_esc}[^<]*</cbc:ID>", re.IGNORECASE))
    if supplier_name:
        sup_esc = re.escape(supplier_name)
        patterns.append(
            re.compile(
                rf"<cbc:(Name|RegistrationName)>[^<]*{sup_esc}[^<]*</cbc:\1>",
                re.IGNORECASE,
            )
        )
    return patterns


def gather_candidate_files(
    dlds_dir: Path,
    invoice_number: str | None,
    supplier_name: str | None,
    start_date: DateLike,
    end_date: DateLike,
) -> set[Path]:
    """Collect XML files that match text filters before parsing."""
    if (start_date and end_date) and not (invoice_number or supplier_name):
        return set(dlds_dir.glob("*.xml"))

    patterns = compile_search_patterns(invoice_number, supplier_name)
    if not patterns:
        return set()

    candidate_files: set[Path] = set()
    for xml_path in dlds_dir.glob("*.xml"):
        try:
            text = xml_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.debug("Skipping %s: read error: %s", xml_path, exc)
            continue

        if any(pat.search(text) for pat in patterns):
            candidate_files.add(xml_path)

    return candidate_files


def parse_and_filter_documents(
    candidate_files: set[Path],
    start_date: date | None,
    end_date: date | None,
) -> list[DocumentType]:
    """Parse candidate files and filter documents by issue date."""
    results: list[DocumentType] = []
    for xml_file in sorted(candidate_files):
        try:
            doc = parse_ubl_document(xml_file)
        except Exception as exc:  # pragma: no cover - parsing failures logged elsewhere
            logger.error("Skipping %s, parse error: %s", xml_file, exc)
            continue

        if not isinstance(doc, DocumentType):
            continue

        if start_date and doc.issue_date < start_date:
            continue
        if end_date and doc.issue_date > end_date:
            continue

        results.append(doc)

    return results
