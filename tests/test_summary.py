from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
import typer
from rich.console import Console

from libanaf.config import (
    AppConfig,
    AuthConfig,
    ConnectionConfig,
    EfacturaConfig,
    StorageConfig,
)
from libanaf.invoices.summary import (
    build_summary_rows,
    collect_documents,
    summarize_invoices,
)


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
        storage=StorageConfig(download_dir=Path("tests/fixtures")),
        env_config_file=env_file,
    )


def test_collect_documents_filters_by_supplier() -> None:
    fixtures = Path("tests/fixtures")
    docs = collect_documents(
        fixtures,
        invoice_number=None,
        supplier_name="NASTIMED SERV SRL",
        start_date=None,
        end_date=None,
    )

    doc_ids = sorted(doc.id for doc in docs)
    assert doc_ids == ["BVAG-2025 3011146", "BVAG-2025 3011327"]


def test_build_summary_rows_orders_and_signs() -> None:
    fixtures = Path("tests/fixtures")
    docs = collect_documents(
        fixtures,
        invoice_number=None,
        supplier_name="NASTIMED SERV SRL",
        start_date=None,
        end_date=None,
    )

    rows = build_summary_rows(docs)
    assert [row.document_number for row in rows] == [
        "BVAG-2025 3011146",
        "BVAG-2025 3011327",
    ]
    assert rows[0].is_credit_note is True
    assert rows[0].payable_amount == pytest.approx(-699.01, rel=1e-6)
    assert rows[1].is_credit_note is False
    assert rows[1].payable_amount == pytest.approx(-242.0, rel=1e-6)


def test_summarize_invoices_requires_filter(dummy_config: AppConfig) -> None:
    console = Console(record=True)
    with pytest.raises(typer.Exit):
        summarize_invoices(
            invoice_number=None,
            supplier_name=None,
            start_date=None,
            end_date=None,
            config=dummy_config,
            output=console,
        )


def test_summarize_invoices_filters_by_date(dummy_config: AppConfig) -> None:
    console = Console(record=True, width=200)
    summarize_invoices(
        invoice_number=None,
        supplier_name="NASTIMED SERV SRL",
        start_date=datetime(2025, 2, 1),
        end_date=datetime(2025, 2, 12),
        config=dummy_config,
        output=console,
    )

    text_output = console.export_text(clear=False)
    assert "BVAG-2025 3011146" in text_output
    assert "BVAG-2025 3011327" not in text_output
