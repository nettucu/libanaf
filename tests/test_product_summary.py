from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from rich.console import Console

from libanaf.config import (
    AppConfig,
    AuthConfig,
    ConnectionConfig,
    EfacturaConfig,
    StorageConfig,
)
from libanaf.invoices.product_summary import (
    build_product_summary_rows,
    collect_documents,
    summarize_products,
)
from libanaf.ubl.ubl_document import parse_ubl_document, parse_ubl_document_from_string

FIXTURES = Path("tests/fixtures")


@pytest.fixture()
def dummy_config(tmp_path: Path) -> AppConfig:
    env_file = tmp_path / ".env.test"
    env_file.write_text("")

    return AppConfig(
        auth=AuthConfig(
            auth_url="https://auth.example",
            token_url="https://token.example",
            revoke_url="https://revoke.example",
            client_id="client",
            client_secret="secret",
            redirect_uri="https://redirect.example",
        ),
        connection=ConnectionConfig(access_token=None, refresh_token=None),
        efactura=EfacturaConfig(
            upload_url="https://upload.example",
            upload_url_params=[],
            message_state_url="https://state.example",
            message_state_url_params=[],
            message_list_url="https://list.example",
            message_list_url_params=[],
            download_url="https://download.example",
            download_url_params=[],
            xml_validate_url="https://validate.example",
            xml2pdf_url="https://xml2pdf.example",
        ),
        storage=StorageConfig(download_dir=FIXTURES),
        env_config_file=env_file,
    )


def test_collect_documents_without_filters() -> None:
    documents = collect_documents(
        FIXTURES,
        invoice_number=None,
        supplier_name=None,
        start_date=None,
        end_date=None,
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
    assert row.total_payable == Decimal("-699.01")
    assert row.value == Decimal("-587.40")
    assert row.vat_value == Decimal("-111.61")
    assert row.total_per_line == Decimal("-699.01")


def test_summarize_products_renders_table(dummy_config: AppConfig) -> None:
    console = Console(record=True, width=320)
    summarize_products(
        invoice_number="FIMCGB8202",
        supplier_name=None,
        start_date=datetime(2025, 2, 1),
        end_date=datetime(2025, 2, 6),
        config=dummy_config,
        output=console,
    )

    text_output = console.export_text(clear=False)
    assert "Invoice Product Summary" in text_output
    assert "FX4010SW-III" in text_output
    assert "Total Per Line" in text_output
    assert "H87 (Piece)" in text_output