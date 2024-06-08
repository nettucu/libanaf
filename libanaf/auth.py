import logging
import threading
from pathlib import Path
from queue import Queue

import typer
from authlib.integrations.httpx_client import OAuth2Client
from werkzeug.serving import make_server
from werkzeug.wrappers import Request, Response

logger = logging.getLogger()

class AuthServer:
    def __init__(self, use_ssl: bool):
        self.use_ssl = use_ssl

    def get_auth_code(self):
        @Request.application
        def code_request(request: Request):
            logger.debug(request)
            logger.debug(f"request.headers = {request.headers}")
            logger.debug(f"request.args = {request.args}")
            q.put(request.args["code"])
            return Response("Authorization code received", 204)

        base_dir = Path(__file__).parent.parent
        cert_file = base_dir / 'secrets' / 'cert.pem'
        key_file = base_dir / 'secrets' / 'key.pem'
    
        q = Queue()
        self.server = make_server('localhost', 8000, code_request, ssl_context=(cert_file, key_file))
        t = threading.Thread(target = self.server.serve_forever)
        t.start()
        auth_code = q.get(block=True)
        self.server.shutdown()
        t.join()

        return auth_code


class OAuthClient:
    def __init__(self, client_id: str, client_secret: str,
                 auth_url: str, token_url: str, redirect_uri: str,
                 use_ssl: bool=True, debug: bool=True) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.auth_url = auth_url
        self.token_url = token_url
        self.redirect_uri = redirect_uri
        self.use_ssl = use_ssl
        self.oauth = OAuth2Client(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri, scope="")
        self.debug = debug

        if self.debug:
            logging.getLogger("requests_oauthlib").setLevel(logging.DEBUG)
            logging.getLogger("oauthlib").setLevel(logging.DEBUG)

    def start_local_server(self) -> str:
        auth_server = AuthServer(use_ssl = self.use_ssl)

        return auth_server.get_auth_code()

    def get_authorization_code(self) -> str:
        authorization_url, state = self.oauth.create_authorization_url(self.auth_url, token_content_type="jwt")
        self.oauth_state = self.oauth.state
        logger.debug(f"Authorization URL: {authorization_url}")

        typer.echo(f"Please go to the following URL to authorize the application:\n{authorization_url}")

        auth_code = self.start_local_server()
        return auth_code

    def get_access_token(self):
        auth_code = self.get_authorization_code()
        logger.debug(f"Authorization code: {auth_code}")
        token = self.oauth.fetch_token(self.token_url, code=auth_code, client_secret=self.client_secret)
        logger.debug(f"Access token received: {token}")

        return token.get("access_token")