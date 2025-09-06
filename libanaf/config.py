import json
import logging
import logging.config
from typing import Any

import envtoml
from dotenv import load_dotenv, set_key

CONFIG_PATH: str = "conf/config.toml"
LOGGING_CONFIG_PATH: str = "conf/logging_py.json"
SECRETS_PATH: str = "secrets/.env"
TOKEN_FILE: str = "secrets/tokens.json"


class Configuration:
    def __new__(cls):
        """
        Singleton pattern to ensure that only one instance of the Configuration class is created.

        Returns:
            Configuration: The instance of the Configuration class.
        """
        if not hasattr(cls, "instance"):
            cls.instance = super().__new__(cls)

        return cls.instance

    def __init__(self) -> None:
        """
        Initialize the Configuration class.

        The constructor sets the config attribute to None. The actual configuration is loaded in the
        load_config method.
        """
        self.config = None

    def load_config(self, env: str = "localhost") -> dict[str, Any]:
        """
        Load the configuration from the file specified by CONFIG_PATH.

        The configuration is loaded using the envtoml library and stored in the self.config attribute.
        The configuration is loaded only once. If the configuration has already been loaded, the stored
        configuration is returned.

        Args:
            env (str): The environment to load the configuration for. Defaults to "localhost".

        Returns:
            dict[str, Any]: The configuration.
        """
        self.env = env
        if self.config is None:
            load_dotenv(SECRETS_PATH + "." + env)
            with open(CONFIG_PATH) as f:
                # self.config = tomllib.load(f)
                self.config = envtoml.load(f)

        return self.config

    def save_tokens(self, tokens: dict[str, Any]) -> None:
        """
        Save the access and refresh tokens to the environment file.

        Args:
            tokens (dict[str, Any]): A dictionary containing the access and refresh tokens.
        """
        set_key(SECRETS_PATH + "." + self.env, "ACCESS_TOKEN", tokens["access_token"])
        set_key(SECRETS_PATH + "." + self.env, "REFRESH_TOKEN", tokens["refresh_token"])
        # with open(TOKEN_FILE, "w") as f:
        #    json.dump(tokens, f)


def setup_logging(verbose: bool | None = True) -> None:
    """
    Setup the logging configuration.

    The logging configuration is loaded from the file specified by
    LOGGING_CONFIG_PATH. If verbose is True, the logging level for the console
    handler is set to DEBUG. The logging configuration is set using
    logging.config.dictConfig().

    If verbose is True, requests logging is also set up using
    _setup_requests_logging().

    Args:
        verbose (bool | None): If True, the logging level for the console handler
            is set to DEBUG. Defaults to True.
    """
    with open(LOGGING_CONFIG_PATH) as f:
        logging_config: dict[str, Any] = json.load(f)

    if verbose:
        logging_config["handlers"]["console"]["level"] = "DEBUG"

    logging.config.dictConfig(logging_config)
    if verbose:
        _setup_requests_logging()


def _setup_requests_logging() -> None:
    """
    Set up logging for the httpx, httpcore and urllib3 libraries.

    This function sets the logging level for the httpx, httpcore and urllib3 libraries to DEBUG and
    enables debugging for the http.client module. This allows for detailed logging of the HTTP
    requests and responses.

    """
    try:
        import http.client as http_client
    except ImportError:
        import httplib as http_client  # type: ignore

    http_client.HTTPConnection.debuglevel = 1
    log = logging.getLogger("urllib3")
    log.setLevel(logging.DEBUG)
    log = logging.getLogger("httpx")
    log.setLevel(logging.DEBUG)
    log = logging.getLogger("httpcore")
    log.setLevel(logging.DEBUG)
