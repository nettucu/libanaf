from .auth import LibANAF_AuthClient
from .config import Configuration


def make_auth_client() -> LibANAF_AuthClient:
    config = Configuration().load_config()
    auth_client = LibANAF_AuthClient(
        client_id=config["auth"]["LIBANAF_CLIENT_ID"],
        client_secret=config["auth"]["LIBANAF_CLIENT_SECRET"],
        auth_url=config["auth"]["LIBANAF_AUTH_URL"],
        token_url=config["auth"]["LIBANAF_TOKEN_URL"],
        redirect_uri=config["auth"]["LIBANAF_REDIRECT_URI"],
        access_token=config["connection"]["LIBANAF_ACCESS_TOKEN"],
        refresh_token=config["connection"]["LIBANAF_REFRESH_TOKEN"],
    )

    return auth_client
