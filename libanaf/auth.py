import logging
import threading
import webbrowser
from pathlib import Path
from queue import Queue
from typing import Any, Dict, Optional

import requests
from authlib.integrations.httpx_client import OAuth2Client
from werkzeug.serving import make_server
from werkzeug.wrappers import Request, Response

from libanaf.config import Configuration

logger = logging.getLogger()

class AuthServer:
    def __init__(self, use_ssl: bool):
        self.use_ssl = use_ssl

    def get_auth_code(self):
        @Request.application
        def code_request(request: Request):
            logger.debug(request)
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
        logger.info(f"Authorization URL: {authorization_url}")
        print(f"Please go to the following URL to authorize the application:\n{authorization_url}")

        auth_code = self.start_local_server()

        return auth_code

    def get_access_token(self):
        auth_code = self.get_authorization_code()
        logger.debug(f"Authorization code: {auth_code}")
        token = self.oauth.fetch_token(self.token_url, code=auth_code, client_secret=self.client_secret)
        logger.debug(f"Access token received: {token}")

        return token.get("access_token")

def authenticate() -> None:
    configuration = Configuration()
    config: Dict[str, Any] = configuration.load_config()

    auth_url: str = config["auth"]["auth_url"]
    token_url: str = config["auth"]["token_url"]
    client_id: str = config["auth"]["client_id"]
    client_secret: str = config["auth"]["client_secret"]
    redirect_uri: str = config["auth"]["redirect_uri"]

    session = OAuth2Session(client_id = client_id, redirect_uri= redirect_uri)
    auth_url, state = session.authorization_url(auth_url)

    query_params: Dict[str, str] = {
        'response_type': 'code',
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'token_content_type': 'jwt'
    }
    auth_full_url: str = f"{auth_url}?{urlencode(query_params)}"
    logger.info(f"Opening browser for authentication: [link={auth_full_url}]{auth_full_url}[/link]")
    webbrowser.open(auth_full_url)

    auth_code: str = input("Enter the authorization code: ")

    data: Dict[str, str] = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'client_secret': client_secret
    }
    response: requests.Response = requests.post(token_url, data=data)
    if response.status_code == 200:
        tokens: Dict[str, Any] = response.json()
        configuration.save_tokens(tokens)
        logger.info("Authentication successful")
    else:
        logger.error("Failed to authenticate", style="bold red")
        logger.error(response.text)
        logger.error(response.text)