from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from libanaf.config import AppConfig, RetryConfig, get_config
from libanaf.invoices.list import fetch_invoice_list


@pytest.fixture
def mock_config():
    with patch("libanaf.invoices.list.get_config") as mock:
        config = MagicMock(spec=AppConfig)
        config.retry = RetryConfig(count=3, delay=0, backoff_factor=1, max_delay=1)  # 0 delay for speed
        config.efactura = MagicMock()
        config.efactura.message_list_url = "http://test.url"
        config.auth = MagicMock()
        mock.return_value = config
        yield mock


@pytest.mark.asyncio
async def test_fetch_invoice_list_retries(mock_config):
    with patch("libanaf.invoices.list.make_auth_client") as mock_auth_client:
        mock_client = AsyncMock()
        # Mock get to raise exception 2 times then succeed
        mock_client.get.side_effect = [
            httpx.NetworkError("Fail 1"),
            httpx.TimeoutException("Fail 2"),
            MagicMock(status_code=200, json=lambda: {"mesaje": []}),
        ]

        mock_auth_instance = MagicMock()
        mock_auth_instance.get_client.return_value = mock_client
        mock_auth_client.return_value = mock_auth_instance

        await fetch_invoice_list()

        assert mock_client.get.call_count == 3
