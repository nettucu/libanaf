import asyncio
import logging
import webbrowser
from pathlib import Path
from typing import Any

import jwt
from authlib.integrations.httpx_client import AsyncOAuth2Client

from libanaf.config import save_tokens
from libanaf.exceptions import AuthorizationError

from libanaf.auth.server import OAuthCallbackServer

logger = logging.getLogger(__name__)


class AnafAuthClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        auth_url: str,
        token_url: str,
        redirect_uri: str,
        access_token: str | Any = None,
        refresh_token: str | Any = None,
        cert_file: Path | None = None,
        key_file: Path | None = None,
    ) -> None:
        """Initialize the OAuth2 client wrapper.

        Args:
            client_id: OAuth2 client ID.
            client_secret: OAuth2 client secret.
            auth_url: Authorization endpoint URL.
            token_url: Token endpoint URL.
            redirect_uri: Redirect URI registered with the provider.
            access_token: Optional pre-existing access token (JWT string).
            refresh_token: Optional pre-existing refresh token.
            cert_file: Path to the TLS certificate file for the local callback server.
            key_file: Path to the TLS private key file for the local callback server.
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.auth_url = auth_url
        self.token_url = token_url
        self.redirect_uri = redirect_uri
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.cert_file = cert_file
        self.key_file = key_file
        self.oauth_state: str | None = None

        self._make_client()

    def update_token(self, token, refresh_token) -> None:
        """Persist refreshed tokens and rebuild the client.

        Authlib invokes this callback when the access token is refreshed.
        """
        logger.debug(f"Token received for update: {token}")
        logger.debug(f"Refresh token received for update: {refresh_token}")

        save_tokens(tokens=token)

        self.access_token = token["access_token"]
        self.refresh_token = token["refresh_token"]

        self._make_client()

    def _make_client(self) -> None:
        """Create or refresh the underlying `AsyncOAuth2Client` instance."""
        self.oauth: AsyncOAuth2Client = AsyncOAuth2Client(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope="",
            token_endpoint=self.token_url,
            update_token=self.update_token,
        )
        if self.access_token is not None:
            decoded = jwt.decode(self.access_token, options={"verify_signature": False})
            self.oauth.token = {
                "access_token": self.access_token,
                "token_type": decoded["token_type"],
                "expires_at": decoded["exp"],
                "refresh_token": self.refresh_token,
            }

    def start_local_server(self):
        """Start a one-shot local HTTPS callback server for the authorization flow.

        Delegates to ``OAuthCallbackServer.get_auth_response``, which blocks
        until ANAF redirects the browser to the local callback URL.

        Returns:
            ImmutableMultiDict: Query parameters from the redirect (``code`` or ``error``).
        """
        use_ssl = self.cert_file is not None and self.key_file is not None
        cert_str = str(self.cert_file) if self.cert_file else None
        key_str = str(self.key_file) if self.key_file else None
        auth_server = OAuthCallbackServer(use_ssl=use_ssl, cert_file=cert_str, key_file=key_str)
        return auth_server.get_auth_response()

    def get_authorization_code(self):
        """Build the authorization URL, open the browser, and wait for the redirect.

        Generates a PKCE-less authorization URL with ``token_content_type=jwt``,
        opens it in the default web browser, then blocks on ``start_local_server``
        until ANAF posts the authorization result back to the local callback.

        Returns:
            ImmutableMultiDict: Query parameters from the ANAF redirect; contains
                ``"code"`` on success or ``"error"`` on denial.
        """
        authorization_url, state = self.oauth.create_authorization_url(self.auth_url, token_content_type="jwt")
        self.oauth_state = state
        logger.debug(f"Authorization URL: {authorization_url}")
        logger.info(f"Opening web browser with the URL:\n{authorization_url}")
        webbrowser.open_new(authorization_url)
        return self.start_local_server()

    def get_client(self) -> AsyncOAuth2Client:
        """Return the configured Authlib OAuth2 client."""
        return self.oauth

    def get_access_token(self):
        """Run the consent flow and exchange the code for a token.

        Raises:
            AuthorizationError: If the authorization server returns an error
                or if the state parameter in the callback does not match the
                one generated at authorization-URL creation time (CSRF check).

        Returns:
            dict: The token payload returned by the token endpoint.
        """
        auth_response = self.get_authorization_code()

        if "error" in auth_response:
            logger.error(f"Authorization code error: {auth_response['error']}")
            raise AuthorizationError(auth_response["error"])

        returned_state = auth_response.get("state")
        if returned_state != self.oauth_state:
            logger.error(f"State mismatch: expected {self.oauth_state!r}, got {returned_state!r}")
            raise AuthorizationError("state_mismatch")

        auth_code = auth_response["code"]
        logger.debug(f"Authorization code: {auth_code}")

        token = asyncio.run(
            self.oauth.fetch_token(
                self.token_url,
                code=auth_code,
                client_secret=self.client_secret,
                token_content_type="jwt",
            )
        )
        logger.debug(f"Access token received: {token}")
        return token
