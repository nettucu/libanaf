from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from rich.console import Console

from libanaf.config import Settings
from libanaf.invoices.summary import (
    build_summary_rows,
    collect_documents,
    summarize_invoices,
)
from libanaf.cli.invoices.summary import render_summary

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


def test_collect_documents_filters_by_supplier() -> None:
    docs = collect_documents(
        FIXTURES,
        invoice_number=None,
        supplier_name="NASTIMED SERV SRL",
        start_date=None,
        end_date=None,
    )

    doc_ids = sorted(doc.id for doc in docs)
    assert doc_ids == ["BVAG-2025 3011146", "BVAG-2025 3011327"]


def test_build_summary_rows_orders_and_signs() -> None:
    docs = collect_documents(
        FIXTURES,
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


def test_summarize_invoices_returns_empty_for_no_results(dummy_settings: Settings) -> None:
    rows = summarize_invoices(
        invoice_number="NONEXISTENT-999",
        supplier_name=None,
        start_date=None,
        end_date=None,
        settings=dummy_settings,
    )
    assert rows == []


def test_summarize_invoices_filters_by_date(dummy_settings: Settings) -> None:
    console = Console(record=True, width=200)
    rows = summarize_invoices(
        invoice_number=None,
        supplier_name="NASTIMED SERV SRL",
        start_date=datetime(2025, 2, 1),
        end_date=datetime(2025, 2, 12),
        settings=dummy_settings,
    )
    render_summary(rows, output=console)

    text_output = console.export_text(clear=False)
    assert "BVAG-2025 3011146" in text_output
    assert "BVAG-2025 3011327" not in text_output
