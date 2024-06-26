

from .auth import LibANAF_AuthClient
from .config import Configuration


def make_auth_client() -> LibANAF_AuthClient:
    config = Configuration().load_config()
    auth_client = LibANAF_AuthClient(client_id=config["auth"]["client_id"],
                                     client_secret=config["auth"]["client_secret"],
                                     auth_url=config["auth"]["auth_url"],
                                     token_url=config["auth"]["token_url"],
                                     redirect_uri=config["auth"]["redirect_uri"],
                                     access_token=config["connection"]["access_token"],
                                     refresh_token=config["connection"]["refresh_token"])

    return auth_client
