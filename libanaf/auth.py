import logging
import threading
import webbrowser
from pathlib import Path
from queue import Queue
from typing import Any

import jwt
import typer
from authlib.integrations.httpx_client import AsyncOAuth2Client
from werkzeug.serving import make_server
from werkzeug.wrappers import Request, Response

from libanaf.config import Configuration

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

        logger.debug("Starting server on localhost:8000")
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
        # TODO: do the update of the access token and refresh token
        logger.debug(token)
        logger.debug(refresh_token)

        config = Configuration()
        config.save_tokens(tokens=token)

        self.access_token = token["access_token"]
        self.refresh_token = token["refresh_token"]

        self._make_client()

    def _make_client(self) -> None:
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
        # TODO: the certificate and keyfile should not be hardcoded here
        basedir = Path(__file__).parent.parent
        cert_file = basedir / "secrets" / "cert.pem"
        key_file = basedir / "secrets" / "key.pem"

        auth_server = LibANAF_AuthServer(use_ssl=self.use_ssl, cert_file=cert_file, key_file=key_file)

        # the return type is a MultiDict from werkzeug
        return auth_server.get_auth_response()

    def get_authorization_code(self):
        authorization_url, state = self.oauth.create_authorization_url(self.auth_url, token_content_type="jwt")
        self.oauth_state = state
        logger.debug(f"Authorization URL: {authorization_url}")

        logger.info(f"Opening web browser with the URL:\n{authorization_url}")
        webbrowser.open_new(authorization_url)

        auth_code = self.start_local_server()
        return auth_code

    def get_client(self) -> AsyncOAuth2Client:
        return self.oauth

    def get_access_token(self):
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
        loop = asyncio.get_event_loop()
        token = loop.run_until_complete(
            self.oauth.fetch_token(
                self.token_url,
                code=auth_code,
                client_secret=self.client_secret,
                token_content_type="jwt",
            )
        )
        logger.debug(f"Access token received: {token}")

        return token
