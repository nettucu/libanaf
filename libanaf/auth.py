import logging
import os
import threading
import webbrowser
from queue import Queue
from typing import Any

import jwt
import typer
from authlib.integrations.httpx_client import AsyncOAuth2Client
from werkzeug.serving import make_server
from werkzeug.wrappers import Request, Response
from libanaf.config import get_config, save_tokens, AppConfig

logger = logging.getLogger()


class LibANAF_AuthServer:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8000,
        use_ssl: bool = True,
        cert_file: str | None = None,
        key_file: str | None = None,
    ):
        """Initialize an auth callback server.

        Args:
            host: Hostname to bind to. Defaults to "localhost".
            port: Port number to bind to. Defaults to 8000.
            use_ssl: Whether to enable TLS/SSL. Defaults to True.
            cert_file: Path to the TLS certificate file when `use_ssl` is True.
            key_file: Path to the TLS private key file when `use_ssl` is True.

        Raises:
            RuntimeError: If `use_ssl` is True and either `cert_file` or `key_file` is not provided.
        """
        self.host = host
        self.port = port
        self.use_ssl = use_ssl

        if self.use_ssl and (cert_file is None or key_file is None):
            raise RuntimeError("When SSL is enabled, certificate file and key file are mandatory")

        self.cert_file = cert_file
        self.key_file = key_file

    def get_auth_response(self):
        @Request.application
        def code_request(request: Request):
            """Handle the redirect from ANAF with the authorization result.

            Puts the query params from the redirect into a queue so the
            server thread can shut down after a single request.

            Args:
                request: The Werkzeug `Request` for the incoming call.

            Returns:
                Response: A Werkzeug response describing success or error.
            """
            logger.debug(request)
            logger.debug(f"request.headers = {request.headers}")
            logger.debug(f"request.args = {request.args}")

            # the expected args are:
            # If ERROR  : ImmutableMultiDict([('error', 'access_denied'), ('state',  'Sg43J5I1BJFyYvBJ0YHarlBJMMt04j')]
            # If SUCCESS: ImmutableMultiDict([('code', '1734943ca3584363500f9dbc709838956ad2c8f55a21d38c4e2e0a9ba1f0e9ed'), ('state', '8eyMxuYVuvkbQkGPD1VxSbYfmMZXlt')])
            q.put(request.args)

            # we have received an error instead of an authorization code to get the token with
            if "error" in request.args:
                logger.error(f"Error received: {request.args['error']}")
                return Response(f"Error occured: {request.args['error']}", mimetype="text/plain")
            elif "code" in request.args:
                logger.debug(f"Auth code: {request.args['code']}")
                return Response(
                    f"Authorization code received: {request.args['code']}",
                    mimetype="text/plain",
                )

        logger.debug(f"Starting server on {self.host}:{self.port}, SSL={self.use_ssl}")
        if self.use_ssl:
            self.server = make_server(
                self.host,
                self.port,
                code_request,
                ssl_context=(self.cert_file, self.key_file),
            )
        else:
            self.server = make_server(self.host, self.port, code_request)

        # start a new Thread to receive just one request, the redirect to localhost
        q = Queue()
        t = threading.Thread(target=self.server.serve_forever)
        t.start()
        response = q.get(block=True)

        logger.debug("Shutting down the temporary web server ...")
        self.server.shutdown()
        t.join()

        return response


class LibANAF_AuthClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        auth_url: str,
        token_url: str,
        redirect_uri: str,
        use_ssl: bool = True,
        access_token: str | Any = None,
        refresh_token: str | Any = None,
    ) -> None:
        """Initialize the OAuth2 client wrapper.

        Args:
            client_id: OAuth2 client ID.
            client_secret: OAuth2 client secret.
            auth_url: Authorization endpoint URL.
            token_url: Token endpoint URL.
            redirect_uri: Redirect URI registered with the provider.
            use_ssl: Whether to use TLS/SSL for the local callback server. Defaults to True.
            access_token: Optional pre-existing access token (JWT string).
            refresh_token: Optional pre-existing refresh token.
        """
        self.client_id: str = client_id
        self.client_secret: str = client_secret
        self.auth_url: str = auth_url
        self.token_url: str = token_url
        self.redirect_uri: str = redirect_uri
        self.use_ssl: bool = use_ssl
        self.access_token: str | Any = access_token
        self.refresh_token: str | Any = refresh_token

        self._make_client()

    # Write a function to update the access token and refresh token when called from AsyncOAuth2Client
    # The function will be called when the token expired and it should be based on authlib Auto Update Token feature
    def update_token(self, token, refresh_token) -> None:
        """Persist refreshed tokens and rebuild the client.

        Authlib invokes this callback when the access token is refreshed.
        Saves the new tokens to the config and updates internal state.

        Args:
            token: The new token payload as provided by Authlib.
            refresh_token: The new refresh token value (may be present in `token`).
        """
        logger.debug(f"Token received for update: {token}")
        logger.debug(f"Refresh token received for update: {refresh_token}")

        config: AppConfig = get_config()  # Get the current config instance
        save_tokens(config, tokens=token)

        self.access_token = token["access_token"]
        self.refresh_token = token["refresh_token"]

        self._make_client()

    def _make_client(self) -> None:
        """Create or refresh the underlying `AsyncOAuth2Client` instance.

        If an `access_token` is available, initialize the Authlib client with a
        decoded token payload to set `token_type`, expiration, and refresh token.
        """
        self.oauth: AsyncOAuth2Client = AsyncOAuth2Client(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope="",
            token_endpoint=self.token_url,
            update_token=self.update_token,
        )
        if self.access_token is not None:
            # If an access token was passed (as string, we need to pass it to the authlib.AsyncOAuth2Client
            decoded = jwt.decode(self.access_token, options={"verify_signature": False})
            self.oauth.token = {
                "access_token": self.access_token,
                "token_type": decoded["token_type"],
                "expires_at": decoded["exp"],
                "refresh_token": self.refresh_token,
            }

    def start_local_server(self):
        """Start a one-shot local callback server for the authorization flow.

        Returns:
            werkzeug.datastructures.MultiDict: Query params from the redirect
            request, typically containing either `code` on success or `error`.
        """
        # Load certificate/key from environment (dotenv is already handled by Configuration)
        config: AppConfig = get_config()  # Get the current config instance

        cert_file_env = os.getenv("LIBANAF_TLS_CERT_FILE")
        key_file_env = os.getenv("LIBANAF_TLS_KEY_FILE")

        # Fallback to defaults under secrets/ if env vars are not set
        # The secrets_path is now part of the AppConfig's env_config_file's parent directory
        default_cert = config.env_config_file.parent / "cert.pem"
        default_key = config.env_config_file.parent / "key.pem"
        cert_file = cert_file_env or (str(default_cert) if default_cert.exists() else None)
        key_file = key_file_env or (str(default_key) if default_key.exists() else None)

        auth_server = LibANAF_AuthServer(use_ssl=self.use_ssl, cert_file=cert_file, key_file=key_file)

        # the return type is a MultiDict from werkzeug
        return auth_server.get_auth_response()

    def get_authorization_code(self):
        """Obtain an authorization code via browser-based consent flow.

        Opens the user's browser to the provider's authorization URL,
        starts a local callback server, and waits for the redirect.

        Returns:
            werkzeug.datastructures.MultiDict: Redirect query params containing
            either `code` and `state` on success or `error` on failure.
        """
        authorization_url, state = self.oauth.create_authorization_url(self.auth_url, token_content_type="jwt")
        self.oauth_state = state
        logger.debug(f"Authorization URL: {authorization_url}")

        logger.info(f"Opening web browser with the URL:\n{authorization_url}")
        webbrowser.open_new(authorization_url)

        auth_code = self.start_local_server()
        return auth_code

    def get_client(self) -> AsyncOAuth2Client:
        """Return the configured Authlib OAuth2 client.

        Returns:
            AsyncOAuth2Client: The underlying OAuth2 client instance.
        """
        return self.oauth

    def get_access_token(self):
        """Run the consent flow and exchange the code for a token.

        Handles retry on user-declined consent, then exchanges the received
        authorization code for an access token.

        Returns:
            dict: The token payload returned by the token endpoint.
        """
        import asyncio

        loop = True

        while loop:
            # MultiDict from werkzeug
            auth_response = self.get_authorization_code()

            if "error" in auth_response:
                logger.error(f"Authorization code error: {auth_response['error']} ")
                yesno = typer.confirm("Error received: retry ?: ", default=True)
                if yesno is False:
                    loop = False
            else:
                # assume we got the response we expected
                loop = False

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
