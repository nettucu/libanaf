
from pathlib import Path

from libanaf.invoices._utils import is_invoice_downloaded


def test_is_invoice_downloaded_true(tmp_path: Path):
    """Test that is_invoice_downloaded returns True when a file exists."""
    message = {"id": "123", "id_solicitare": "456"}
    download_dir = tmp_path

    # Test with the first possible filename
    (download_dir / "123.zip").touch()
    assert is_invoice_downloaded(message, download_dir) is True

    # Test with the second possible filename
    (download_dir / "456.zip").touch()
    assert is_invoice_downloaded(message, download_dir) is True

    # Test with the third possible filename
    (download_dir / "efactura_456.zip").touch()
    assert is_invoice_downloaded(message, download_dir) is True


def test_is_invoice_downloaded_false(tmp_path: Path):
    """Test that is_invoice_downloaded returns False when no file exists."""
    message = {"id": "123", "id_solicitare": "456"}
    download_dir = tmp_path

    assert is_invoice_downloaded(message, download_dir) is False
