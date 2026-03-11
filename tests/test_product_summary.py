from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from rich.console import Console

from libanaf.config import Settings
from libanaf.invoices.product_summary import (
    build_product_summary_rows,
    collect_documents,
    summarize_products,
)
from libanaf.ubl.ubl_document import parse_ubl_document, parse_ubl_document_from_string

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures"


@pytest.fixture()
def dummy_settings() -> Settings:
    from libanaf.config import AuthSettings, StorageSettings
    return Settings(
        auth=AuthSettings(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://redirect.example",
        ),
        storage=StorageSettings(download_dir=FIXTURES),
    )


def test_collect_documents_without_filters() -> None:
    documents = collect_documents(
        FIXTURES,
        invoice_number=None,
        supplier_name=None,
        start_date=None,
        end_date=None,
        allow_unfiltered=True,
    )

    ids = {doc.id for doc in documents}
    assert "FIMCGB8202" in ids
    assert "POKA W 9262655" in ids


def test_build_rows_distribute_document_discounts() -> None:
    xml_content = (FIXTURES / "invoice-discounts-gursk-4249721031_4705345743.xml").read_text()
    document = parse_ubl_document_from_string(xml_content)
    rows = build_product_summary_rows([document])

    totals = sum(row.total_per_line for row in rows)
    assert totals == Decimal(str(document.legal_monetary_total.payable_amount))

    rows_by_code = {row.product_code: row for row in rows if row.product_code}
    discounted_line = rows_by_code["FX4010SW-III"]
    assert discounted_line.value == Decimal("23809.96")
    assert discounted_line.total_per_line == Decimal("0.00")
    assert discounted_line.discount_value == Decimal("-23809.96")
    vat_line = rows_by_code["UXNF- SuperLine III"]
    assert vat_line.vat_rate == Decimal("19.0")
    assert vat_line.value == Decimal("17915.13")
    assert vat_line.discount_value == Decimal("-17915.13")


def test_build_rows_handles_credit_note() -> None:
    credit_note = parse_ubl_document(FIXTURES / "credit_note-4710432411.xml")
    rows = build_product_summary_rows([credit_note])

    assert len(rows) == 1
    row = rows[0]
    assert row.total_invoice == Decimal("-699.01")
    assert row.total_payable == Decimal("-699.01")
    assert row.value == Decimal("-587.40")
    assert row.vat_value == Decimal("-111.61")
    assert row.total_per_line == Decimal("-699.01")


def test_summarize_products_renders_table(dummy_settings: Settings) -> None:
    console = Console(record=True, width=320)
    summarize_products(
        invoice_number="FIMCGB8202",
        supplier_name=None,
        start_date=datetime(2025, 2, 1),
        end_date=datetime(2025, 2, 6),
        settings=dummy_settings,
        output=console,
    )

    text_output = console.export_text(clear=False)
    assert "Invoice Product Summary" in text_output
    assert "Total (Invoice)" in text_output
    assert "FX4010SW-III" in text_output
    assert "Total Per Line" in text_output
    assert "H87" in text_output
