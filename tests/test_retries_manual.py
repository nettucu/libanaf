from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from libanaf.config import Settings, get_settings
from libanaf.invoices.list import fetch_invoice_list


@pytest.fixture
def mock_settings():
    with patch("libanaf.invoices.list.get_settings") as mock:
        settings = MagicMock()
        settings.retry.count = 3
        settings.retry.delay = 0
        settings.retry.backoff_factor = 1
        settings.retry.max_delay = 1
        settings.efactura.message_list_url = "http://test.url"
        settings.auth.client_id = "test"
        settings.auth.client_secret = "secret"
        settings.auth.auth_url = "https://auth.url"
        settings.auth.token_url = "https://token.url"
        settings.auth.redirect_uri = "https://redirect.url"
        settings.connection.access_token = None
        settings.connection.refresh_token = None
        settings.connection.tls_cert_file = None
        settings.connection.tls_key_file = None
        mock.return_value = settings
        yield mock


@pytest.mark.asyncio
async def test_fetch_invoice_list_retries(mock_settings):
    with patch("libanaf.invoices.list.AnafAuthClient") as mock_auth_client_class:
        mock_client = AsyncMock()
        mock_client.get.side_effect = [
            httpx.NetworkError("Fail 1"),
            httpx.TimeoutException("Fail 2"),
            MagicMock(status_code=200, json=lambda: {"mesaje": []}),
        ]

        mock_auth_instance = MagicMock()
        mock_auth_instance.get_client.return_value = mock_client
        mock_auth_client_class.return_value = mock_auth_instance

        await fetch_invoice_list()

        assert mock_client.get.call_count == 3
