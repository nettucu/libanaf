import json
import logging
import logging.config
from typing import Any, Dict, Optional

import envtoml
from dotenv import load_dotenv

CONFIG_PATH: str = "conf/config.toml"
LOGGING_CONFIG_PATH: str = "conf/logging_py.json"
SECRETS_PATH: str = "secrets/.env"
TOKEN_FILE: str = "secrets/tokens.json"


class Configuration(object):
    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super(Configuration, cls).__new__(cls)

        return cls.instance

    def __init__(self) -> None:
        self.config = None

    def load_config(self, env: str = "localhost") -> Dict[str, Any]:
        if self.config is None:
            load_dotenv(SECRETS_PATH + "." + env)
            with open(CONFIG_PATH, "r") as f:
                # self.config = tomllib.load(f)
                self.config = envtoml.load(f)

        return self.config

    def save_tokens(self, tokens: Dict[str, Any]) -> None:
        with open(TOKEN_FILE, "w") as f:
            json.dump(tokens, f)


def setup_logging(verbose: Optional[bool] = True) -> None:
    with open(LOGGING_CONFIG_PATH, "r") as f:
        logging_config: Dict[str, Any] = json.load(f)

    if verbose:
        logging_config["handlers"]["console"]["level"] = "DEBUG"

    logging.config.dictConfig(logging_config)
    if verbose:
        _setup_requests_logging()


def _setup_requests_logging() -> None:
    try:
        import http.client as http_client
    except ImportError:
        import httplib as http_client

    http_client.HTTPConnection.debuglevel = 1
    log = logging.getLogger("urllib3")
    log.setLevel(logging.DEBUG)
    log = logging.getLogger("httpx")
    log.setLevel(logging.DEBUG)
    log = logging.getLogger("httpcore")
    log.setLevel(logging.DEBUG)
