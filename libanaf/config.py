import json
import logging
import logging.config
import os
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field
from functools import lru_cache

import envtoml
from dotenv import load_dotenv, set_key


@dataclass(frozen=True)
class AuthConfig:
    """Authentication endpoints and credentials."""

    auth_url: str
    token_url: str
    revoke_url: str
    client_id: str
    client_secret: str
    redirect_uri: str


@dataclass(frozen=True)
class ConnectionConfig:
    """Tokens for maintaining an active session."""

    access_token: str | None
    refresh_token: str | None


@dataclass(frozen=True)
class EfacturaConfig:
    """e-Factura API endpoints and parameters."""

    upload_url: str
    upload_url_params: list[str]
    message_state_url: str
    message_state_url_params: list[str]
    message_list_url: str
    message_list_url_params: list[str]
    download_url: str
    download_url_params: list[str]
    xml_validate_url: str
    xml2pdf_url: str


@dataclass(frozen=True)
class StorageConfig:
    """Local storage configuration."""

    download_dir: Path


@dataclass(frozen=True)
class AppConfig:
    """Root container for all configuration sections."""

    auth: AuthConfig
    connection: ConnectionConfig
    efactura: EfacturaConfig
    storage: StorageConfig
    # Non-TOML configuration state
    env_config_file: Path = field(repr=False)


def save_tokens(config: AppConfig, tokens: dict[str, Any]) -> None:
    """Save the access and refresh tokens to the environment file."""
    set_key(config.env_config_file, "LIBANAF_ACCESS_TOKEN", tokens["access_token"])
    set_key(config.env_config_file, "LIBANAF_REFRESH_TOKEN", tokens["refresh_token"])


def _get_path_from_env(env_var: str, check_exists: bool = True) -> Path:
    """Get a path from an environment variable and validate it."""
    path_str = os.getenv(env_var)
    if not path_str:
        raise ValueError(f"Environment variable '{env_var}' must be set.")
    path = Path(path_str)
    if check_exists and not path.exists():
        raise FileNotFoundError(f"Path from '{env_var}' does not exist: {path}")
    return path


@lru_cache(maxsize=1)
def get_config(
    env: str = "localhost",
    config_file: str | Path | None = None,
    secrets_path: str | Path | None = None,
) -> AppConfig:
    """
    Load configuration from files and environment, returning a frozen AppConfig instance.

    Loading precedence:
    1. Arguments passed to this function.
    2. Environment variables (e.g., LIBANAF_CONFIG_FILE, LIBANAF_CLIENT_ID).
    3. Values from the TOML configuration file.

    The result is cached, so subsequent calls with the same arguments will not reload files.

    Args:
        env: The environment name (e.g., 'localhost', 'production').
        config_file: Path to the main TOML config file. Overrides LIBANAF_CONFIG_FILE env var.
        secrets_path: Path to the directory containing .env files. Overrides LIBANAF_SECRETS_PATH.

    Returns:
        An immutable, nested AppConfig object.
    """
    # 1. Determine configuration file paths
    config_file_path = Path(config_file or _get_path_from_env("LIBANAF_CONFIG_FILE"))
    secrets_dir_path = Path(secrets_path or _get_path_from_env("LIBANAF_SECRETS_PATH"))
    env_file_path = secrets_dir_path / f".env.{env}"

    if not env_file_path.exists():
        raise FileNotFoundError(f"Environment file for env '{env}' not found at: {env_file_path}")

    # 2. Load .env file to populate environment variables for envtoml
    load_dotenv(env_file_path)

    # 3. Load the base configuration from TOML, expanding any ${ENV_VAR} placeholders
    #    Assuming TOML keys match dataclass field names (e.g., 'url' not 'LIBANAF_AUTH_URL').
    #    envtoml will resolve ${ENV_VAR} placeholders within the TOML values.
    with open(config_file_path) as f:
        toml_config = envtoml.load(f)

    # 4. Build the dataclasses, allowing environment variables to override TOML values
    #    For fields that are *only* from env vars (like dynamic tokens), use os.getenv directly.
    auth_cfg = AuthConfig(**toml_config["auth"])
    conn_cfg = ConnectionConfig(**toml_config["connection"])
    efactura_cfg = EfacturaConfig(**toml_config["efactura"])
    storage_cfg = StorageConfig(download_dir=Path(toml_config["storage"]["download_dir"]))

    return AppConfig(
        auth=auth_cfg,
        connection=conn_cfg,
        efactura=efactura_cfg,
        storage=storage_cfg,
        env_config_file=env_file_path,
    )


def setup_logging(verbose: bool = False) -> None:
    """
    Setup logging for the CLI application.

    This should be called from the CLI entrypoint. It is not part of the
    core configuration loading to keep the library decoupled from logging setup.
    """
    logging_config_file = _get_path_from_env("LIBANAF_LOGGING_CONFIG_FILE")
    with open(logging_config_file) as f:
        logging_config: dict[str, Any] = json.load(f)

    if verbose:
        # For CLI, make console more verbose
        if "console" in logging_config.get("handlers", {}):
            logging_config["handlers"]["console"]["level"] = "DEBUG"
        # And enable detailed HTTP logging
        _setup_requests_logging()

    logging.config.dictConfig(logging_config)


def _setup_requests_logging() -> None:
    """Enable verbose logging for HTTP libraries."""
    try:
        import http.client as http_client
    except ImportError:
        import httplib as http_client  # type: ignore

    http_client.HTTPConnection.debuglevel = 1
    logging.getLogger("urllib3").setLevel(logging.DEBUG)
    logging.getLogger("httpx").setLevel(logging.DEBUG)
    logging.getLogger("httpcore").setLevel(logging.DEBUG)
