
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import typer

from libanaf.cli.invoices.show import _format_qty, get_supplier_str, show
from libanaf.invoices.common import DateValidationError, format_money, format_percent


@patch("libanaf.cli.invoices.show.collect_documents")
@patch("libanaf.cli.invoices.show.display_documents_pdf_style")
@patch("libanaf.cli.invoices.show.get_settings")
def test_show_invoices(mock_get_settings, mock_display_docs, mock_collect_docs):
    """Test that show calls dependencies with correct arguments."""
    mock_settings = MagicMock()
    mock_settings.storage.download_dir = "/tmp"
    mock_get_settings.return_value = mock_settings
    mock_collect_docs.return_value = [MagicMock()]

    show(
        invoice_number="INV-001",
        supplier_name="Supplier",
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 1, 31),
    )

    mock_collect_docs.assert_called_once()
    mock_display_docs.assert_called_once_with(mock_collect_docs.return_value)


def test_show_invoices_no_filters():
    """Test that show exits if no filters are provided."""
    with pytest.raises(typer.Exit):
        show(None, None, None, None)


@patch("libanaf.cli.invoices.show.ensure_date_range")
def test_show_invoices_date_validation_error(mock_ensure_date_range):
    """Test that show handles DateValidationError."""
    mock_ensure_date_range.side_effect = DateValidationError("both_required")
    with pytest.raises(typer.Exit):
        show(None, None, datetime(2025, 1, 1), None)


def test_format_money():
    """Test the format_money function."""
    assert format_money(1234.56, "RON") == "1,234.56 RON"
    assert format_money(None, "RON") == ""


def test_format_qty():
    """Test the _format_qty function."""
    assert _format_qty(1234.56) == "1,234.56"
    assert _format_qty(None) == ""


def test_format_percent():
    """Test the format_percent function."""
    assert format_percent(19.0) == "19%"
    assert format_percent(None) == "0%"


def test_get_supplier_str():
    """Test the get_supplier_str function."""
    mock_party = MagicMock()
    mock_party.get_display_str.return_value = {"formatted": "Formatted Name"}
    assert get_supplier_str(mock_party) == "Formatted Name"
