import json
import logging
import logging.config
import os
from pathlib import Path
from typing import Any

import envtoml
from dotenv import load_dotenv, set_key


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
        self.config: dict[str, Any] | None = None

        self.env: str = "localhost"
        self.config_file: Path | None = None
        self.logging_config_file: Path | None = None
        self.secrets_path: Path | None = None
        self.env_config_file: Path | None = None

    def setup(
        self,
        env: str = "localhost",
        config_file: Path | None = None,
        logging_config_file: Path | None = None,
        secrets_path: Path | None = None,
    ) -> "Configuration":
        """
        Setup the configuration paths and load the configuration. This methid should be called once
        at the beginning of the application.

        Args:
            env (str): The environment to load the configuration for. Defaults to "localhost".
            config_path (str | Path | None): The path to the configuration file. If None, defaults to CONFIG_PATH.
            logging_config_path (str | Path | None): The path to the logging configuration file. If None, defaults to LOGGING_CONFIG_PATH.
            secrets_path (str | Path | None): The path to the secrets file. If None, defaults to SECRETS_PATH.

        Returns:
            Configuration: The instance of the Configuration class.
        """
        if self.config is not None:
            return self

        # TODO: using env here to determine the config file is not very flexible, need to find a different way
        # TODO: the below code can raise Path errors if the env variables are not set, need to handle that

        self.env = env
        self.config_file = Path(config_file or os.getenv("LIBANAF_CONFIG_FILE"))
        self.logging_config_file = Path(logging_config_file or os.getenv("LIBANAF_LOGGING_CONFIG_FILE"))
        self.secrets_path = Path(secrets_path or os.getenv("LIBANAF_SECRETS_PATH"))
        self.env_config_file = Path(self.secrets_path / f".env.{self.env}")

        if not any(
            (
                self.config_file.exists(),
                self.env_config_file.exists(),
                self.logging_config_file.exists(),
                self.env_config_file.exists(),
            )
        ):
            raise ValueError("Configuration(s) paths not set")

        load_dotenv(self.env_config_file)
        with open(self.config_file) as f:
            # self.config = tomllib.load(f)
            # IMPORTANT: use envtoml to allow ${ENV_VAR} expansion in the toml file
            #            this file MUST be loaded after loading the .env file, which stores the secrets
            #            https://github.com/PyO3/envtoml
            self.config = envtoml.load(f)

        return self

    def get_config(self) -> dict[str, Any]:
        """
        Return the configuration dictionary loaded from the interpolated TOML file.

        Returns:
            dict[str, Any]: The configuration dictionary.
        """
        return self.config

    def save_tokens(self, tokens: dict[str, Any]) -> None:
        """
        Save the access and refresh tokens to the environment file.

        Args:
            tokens (dict[str, Any]): A dictionary containing the access and refresh tokens.
        """
        set_key(self.env_config_file, "LIBANAF_ACCESS_TOKEN", tokens["access_token"])
        set_key(self.env_config_file, "LIBANAF_REFRESH_TOKEN", tokens["refresh_token"])

    # TODO: should we move this to a different class ? or a different module ?
    #       The issue here is that this is a library, so perhaps we should not setup logging at all when used as a library
    #       when used as CLI, then we can setup logging, but perhaps we should do it in the CLI module ?
    def setup_logging(self, verbose: bool | None = True) -> None:
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
        with open(self.logging_config_file) as f:
            logging_config: dict[str, Any] = json.load(f)

        if verbose:
            logging_config["handlers"]["console"]["level"] = "DEBUG"

        logging.config.dictConfig(logging_config)
        if verbose:
            self._setup_requests_logging()

    def _setup_requests_logging(self) -> None:
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
