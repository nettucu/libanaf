
from datetime import date
from pathlib import Path
from typing import cast

import pytest

from libanaf.ubl.credit_note import CreditNote
from libanaf.ubl.ubl_document import parse_ubl_document

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
SAMPLE_CREDIT_NOTE_PATH = FIXTURES_DIR / "credit_note-4710432411.xml"


def test_parse_credit_note():
    """Test parsing of a sample credit note."""
    credit_note: CreditNote = cast(CreditNote, parse_ubl_document(SAMPLE_CREDIT_NOTE_PATH))

    assert credit_note.id == "BVAG-2025 3011146"
    assert credit_note.document_currency_code == "RON"
    assert credit_note.issue_date == date(2025, 2, 11)
    assert credit_note.accounting_supplier_party.party.party_legal_entity.registration_name == "NASTIMED SERV SRL"
    assert credit_note.accounting_customer_party.party.party_legal_entity.registration_name == "CABINET MEDICAL INDIVIDUAL DE MEDICINA DENTARA DR.TRIFU MIHAELA"
    assert credit_note.legal_monetary_total.payable_amount == pytest.approx(699.01)
    assert credit_note.tax_total.tax_amount == pytest.approx(111.61)
