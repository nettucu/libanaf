from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from os import cpu_count
from pathlib import Path
from typing import cast

import pytest

from libanaf.ubl.invoice import Invoice
from libanaf.ubl.ubl_document import UBLDocument, parse_ubl_document


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
SAMPLE_INVOICE_PATH = FIXTURES_DIR / "invoice-3444171368_4277109404.xml"
DLDS_DIR = REPO_ROOT / "dlds"
DLDS_XML_FILES = tuple(path.resolve() for path in sorted(DLDS_DIR.glob("*.xml")))

if not DLDS_XML_FILES:
    raise AssertionError("Expected at least one XML document under dlds/")

MAX_WORKERS = min(32, (cpu_count() or 1) * 2)


@pytest.fixture(scope="session")
def parsed_documents() -> Mapping[Path, UBLDocument]:
    results: dict[Path, UBLDocument] = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_path = {executor.submit(parse_ubl_document, path): path for path in DLDS_XML_FILES}
        for future in as_completed(future_to_path):
            path = future_to_path[future]
            try:
                results[path] = future.result()
            except Exception as exc:  # pragma: no cover - should fail the test on execution
                raise AssertionError(f"Failed to parse {path}") from exc

    return results


def test_parse_invoice() -> None:
    invoice: Invoice = cast(Invoice, parse_ubl_document(SAMPLE_INVOICE_PATH))

    assert invoice.id == "POKA W 9262655"
    assert invoice.document_currency_code == "RON"
    assert invoice.issue_date == date(2024, 5, 17)
    assert invoice.accounting_supplier_party.party.party_legal_entity.registration_name == "SC TEHNODENT POKA SRL"
    assert invoice.accounting_customer_party.party.party_legal_entity.registration_name == "TRIFU MIHAELA DR CMI MD"
    assert invoice.legal_monetary_total.payable_amount == pytest.approx(39.06)
    assert invoice.tax_total.tax_amount == pytest.approx(6.24)


@pytest.mark.parametrize("xml_path", DLDS_XML_FILES, ids=lambda path: path.stem)
def test_all_ubl_documents(xml_path: Path, parsed_documents: Mapping[Path, UBLDocument]) -> None:
    ubl_document = parsed_documents[xml_path]

    supplier = ubl_document.accounting_supplier_party.party
    customer = ubl_document.accounting_customer_party.party

    assert ubl_document.id.strip()
    assert ubl_document.document_currency_code.strip()
    assert isinstance(ubl_document.issue_date, date)
    assert supplier.party_legal_entity.registration_name
    assert customer.party_legal_entity.registration_name
    assert ubl_document.legal_monetary_total.payable_amount is not None
    if ubl_document.tax_total.currency_id is not None:
        assert ubl_document.tax_total.currency_id == ubl_document.document_currency_code

    generated_name = ubl_document.tofname()
    assert str(ubl_document.issue_date) in generated_name
    assert f"{ubl_document.legal_monetary_total.payable_amount:.2f}" in generated_name
