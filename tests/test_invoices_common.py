
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from libanaf.invoices.common import (
    DateValidationError,
    ensure_date_range,
    extract_supplier_name,
    format_currency,
    normalize_date,
)


def test_normalize_date():
    """Test that normalize_date correctly handles date, datetime, and None."""
    assert normalize_date(datetime(2025, 1, 1, 12, 30)) == date(2025, 1, 1)
    assert normalize_date(date(2025, 1, 1)) == date(2025, 1, 1)
    assert normalize_date(None) is None


def test_ensure_date_range_valid():
    """Test that ensure_date_range returns correct dates for valid ranges."""
    start, end = ensure_date_range(datetime(2025, 1, 1), datetime(2025, 1, 31))
    assert start == date(2025, 1, 1)
    assert end == date(2025, 1, 31)

    start, end = ensure_date_range(date(2025, 1, 1), date(2025, 1, 31))
    assert start == date(2025, 1, 1)
    assert end == date(2025, 1, 31)

    start, end = ensure_date_range(None, None)
    assert start is None
    assert end is None


def test_ensure_date_range_invalid():
    """Test that ensure_date_range raises errors for invalid ranges."""
    with pytest.raises(DateValidationError, match="both_required"):
        ensure_date_range(datetime(2025, 1, 1), None)

    with pytest.raises(DateValidationError, match="both_required"):
        ensure_date_range(None, datetime(2025, 1, 31))

    with pytest.raises(DateValidationError, match="start_after_end"):
        ensure_date_range(datetime(2025, 2, 1), datetime(2025, 1, 31))


def test_extract_supplier_name():
    """Test that extract_supplier_name correctly extracts the name."""
    mock_party = MagicMock()
    mock_party.get_display_str.return_value = {"name": "  Supplier Name  "}
    assert extract_supplier_name(mock_party) == "Supplier Name"

    mock_party.get_display_str.return_value = {"formatted": "Formatted Name"}
    assert extract_supplier_name(mock_party) == "Formatted Name"

    mock_party.get_display_str.return_value = {}
    assert extract_supplier_name(mock_party) == "Unknown"


def test_format_currency():
    """Test that format_currency correctly formats numeric values."""
    assert format_currency(Decimal("1234.56"), "RON") == "1,234.56"
    assert format_currency(1234.56, "RON") == "1,234.56"
    assert format_currency(1234, "RON") == "1,234.00"
