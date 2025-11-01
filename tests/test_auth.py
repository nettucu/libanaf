import pytest
from unittest.mock import MagicMock, patch
from werkzeug.datastructures import MultiDict

from libanaf.auth import LibANAF_AuthServer, LibANAF_AuthClient


def test_auth_server_init_ssl_error():
    """Test that LibANAF_AuthServer raises an error if SSL is enabled without cert/key."""
    with pytest.raises(RuntimeError, match="When SSL is enabled, certificate file and key file are mandatory"):
        LibANAF_AuthServer(use_ssl=True)


@patch("libanaf.auth.make_server")
def test_auth_server_get_auth_response(mock_make_server):
    """Test that LibANAF_AuthServer correctly handles a request and returns the response."""
    mock_server_instance = MagicMock()
    mock_make_server.return_value = mock_server_instance

    auth_server = LibANAF_AuthServer(use_ssl=False)

    # Mock the queue to return a predefined response
    with patch("libanaf.auth.Queue") as mock_queue_class:
        mock_queue_instance = MagicMock()
        mock_queue_instance.get.return_value = MultiDict([("code", "test_code")])
        mock_queue_class.return_value = mock_queue_instance


        response = auth_server.get_auth_response()

        assert response["code"] == "test_code"
        mock_server_instance.shutdown.assert_called_once()


def test_auth_client_init():
    """Test basic initialization of the LibANAF_AuthClient."""
    client = LibANAF_AuthClient(
        client_id="test_id",
        client_secret="test_secret",
        auth_url="https://auth.url",
        token_url="https://token.url",
        redirect_uri="https://redirect.uri",
    )
    assert client.client_id == "test_id"
    assert client.oauth is not None


@patch("jwt.decode")
def test_auth_client_init_with_token(mock_jwt_decode):
    """Test initialization of the LibANAF_AuthClient with an access token."""
    mock_jwt_decode.return_value = {
        "token_type": "Bearer",
        "exp": 1234567890,
    }

    client = LibANAF_AuthClient(
        client_id="test_id",
        client_secret="test_secret",
        auth_url="https://auth.url",
        token_url="https://token.url",
        redirect_uri="https://redirect.uri",
        access_token="dummy_token",
        refresh_token="dummy_refresh",
    )

    assert client.access_token == "dummy_token"
    assert client.oauth.token["access_token"] == "dummy_token"
    assert client.oauth.token["token_type"] == "Bearer"
    assert client.oauth.token["expires_at"] == 1234567890
    assert client.oauth.token["refresh_token"] == "dummy_refresh"
    mock_jwt_decode.assert_called_once_with("dummy_token", options={"verify_signature": False})


@patch("webbrowser.open_new")
@patch("libanaf.auth.LibANAF_AuthClient.start_local_server")
def test_get_authorization_code(mock_start_local_server, mock_open_new):
    """Test the get_authorization_code method."""
    mock_start_local_server.return_value = MultiDict([("code", "test_code")])

    client = LibANAF_AuthClient(
        client_id="test_id",
        client_secret="test_secret",
        auth_url="https://auth.url",
        token_url="https://token.url",
        redirect_uri="https://redirect.uri",
    )

    auth_response = client.get_authorization_code()

    assert auth_response["code"] == "test_code"
    mock_open_new.assert_called_once()
    mock_start_local_server.assert_called_once()


@patch("libanaf.auth.LibANAF_AuthClient.get_authorization_code")
def test_get_access_token(mock_get_auth_code):
    """Test the get_access_token method."""
    mock_get_auth_code.return_value = MultiDict([("code", "test_code")])

    client = LibANAF_AuthClient(
        client_id="test_id",
        client_secret="test_secret",
        auth_url="https://auth.url",
        token_url="https://token.url",
        redirect_uri="https://redirect.uri",
    )

    # Mock the event loop and the fetch_token method
    async def mock_fetch_token(*args, **kwargs):
        return {"access_token": "new_access_token"}

    client.oauth.fetch_token = MagicMock(side_effect=mock_fetch_token)

    token = client.get_access_token()

    assert token["access_token"] == "new_access_token"
    mock_get_auth_code.assert_called_once()
    client.oauth.fetch_token.assert_called_once()


@patch("typer.confirm")
@patch("libanaf.auth.LibANAF_AuthClient.get_authorization_code")
def test_get_access_token_with_retry(mock_get_auth_code, mock_confirm):
    """Test the retry logic in get_access_token."""
    # Simulate user denying the first time, and accepting the second time
    mock_get_auth_code.side_effect = [
        MultiDict([("error", "access_denied")]),
        MultiDict([("code", "test_code")]),
    ]
    mock_confirm.return_value = True

    client = LibANAF_AuthClient(
        client_id="test_id",
        client_secret="test_secret",
        auth_url="https://auth.url",
        token_url="https://token.url",
        redirect_uri="https://redirect.uri",
    )

    # Mock the event loop and the fetch_token method
    async def mock_fetch_token(*args, **kwargs):
        return {"access_token": "new_access_token"}

    client.oauth.fetch_token = MagicMock(side_effect=mock_fetch_token)

    token = client.get_access_token()

    assert token["access_token"] == "new_access_token"
    assert mock_get_auth_code.call_count == 2
    mock_confirm.assert_called_once()
