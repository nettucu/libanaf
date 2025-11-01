
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from libanaf.auth import LibANAF_AuthClient
from libanaf.comms import make_auth_client
from libanaf.config import AppConfig, AuthConfig, ConnectionConfig, EfacturaConfig, StorageConfig


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
        connection=ConnectionConfig(access_token="dummy_access", refresh_token="dummy_refresh"),
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
        storage=StorageConfig(download_dir=tmp_path),
        env_config_file=env_file,
    )


@patch("libanaf.comms.LibANAF_AuthClient")
def test_make_auth_client(mock_auth_client_class, dummy_config: AppConfig):
    """Test that make_auth_client correctly instantiates LibANAF_AuthClient."""
    make_auth_client(dummy_config)

    mock_auth_client_class.assert_called_once_with(
        client_id=dummy_config.auth.client_id,
        client_secret=dummy_config.auth.client_secret,
        auth_url=dummy_config.auth.auth_url,
        token_url=dummy_config.auth.token_url,
        redirect_uri=dummy_config.auth.redirect_uri,
        access_token=dummy_config.connection.access_token,
        refresh_token=dummy_config.connection.refresh_token,
    )
