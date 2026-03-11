from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from libanaf.cli import app
from libanaf.config import Settings
from libanaf.exceptions import AuthorizationError

runner = CliRunner()


def _make_settings() -> Settings:
    """Create a minimal Settings object for testing."""
    from libanaf.config import AuthSettings
    return Settings(
        auth=AuthSettings(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="https://redirect.example",
        ),
    )


def test_auth_exits_on_denied_and_no_retry():
    """Test that auth command exits when user declines retry after AuthorizationError."""
    settings = _make_settings()

    with patch("libanaf.cli.app.get_settings", return_value=settings):
        with patch("libanaf.cli.app.setup_logging"):
            with patch("libanaf.cli.auth.AnafAuthClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.get_access_token.side_effect = AuthorizationError("access_denied")

                with patch("typer.confirm", return_value=False):
                    result = runner.invoke(app, ["auth"])
                    assert result.exit_code != 0


def test_auth_retries_on_denied():
    """Test that auth CLI retries on AuthorizationError when user confirms."""
    settings = _make_settings()
    success_token = {"access_token": "new_token", "refresh_token": "new_refresh"}

    with patch("libanaf.cli.app.get_settings", return_value=settings):
        with patch("libanaf.cli.app.setup_logging"):
            with patch("libanaf.cli.auth.AnafAuthClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                mock_client.get_access_token.side_effect = [
                    AuthorizationError("access_denied"),
                    success_token,
                ]

                with patch("libanaf.cli.auth.save_tokens") as mock_save:
                    with patch("typer.confirm", return_value=True):
                        result = runner.invoke(app, ["auth"])
                        assert mock_client.get_access_token.call_count == 2
                        mock_save.assert_called_once_with(success_token)
