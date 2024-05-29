import logging
import webbrowser
from typing import Any, Dict
from urllib.parse import urlencode

import requests
from requests_oauthlib import OAuth2Session

from libanaf.config import Configuration

logger = logging.getLogger()

def authenticate() -> None:
    configuration = Configuration()
    config: Dict[str, Any] = configuration.load_config()

    auth_url: str = config["auth"]["auth_url"]
    token_url: str = config["auth"]["token_url"]
    client_id: str = config["auth"]["client_id"]
    client_secret: str = config["auth"]["client_secret"]
    redirect_uri: str = config["auth"]["redirect_uri"]

    session = OAuth2Session(client_id = client_id,redirect_uri= redirect_uri)
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