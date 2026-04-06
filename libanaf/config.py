import json
import logging
import logging.config
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import set_key
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseModel):
    """OAuth2 credentials and ANAF authorization endpoints."""
    client_id: str
    client_secret: str
    redirect_uri: str
    auth_url: str = "https://logincert.anaf.ro/anaf-oauth2/v1/authorize"
    token_url: str = "https://logincert.anaf.ro/anaf-oauth2/v1/token"
    revoke_url: str = "https://logincert.anaf.ro/anaf-oauth2/v1/revoke"


class ConnectionSettings(BaseModel):
    """Runtime session tokens and TLS certificate paths for the OAuth callback server."""
    access_token: str | None = None
    refresh_token: str | None = None
    tls_cert_file: Path | None = None
    tls_key_file: Path | None = None


class EfacturaSettings(BaseModel):
    """ANAF e-Factura REST API endpoint URLs."""
    upload_url: str = "https://api.anaf.ro/prod/FCTEL/rest/upload"
    message_state_url: str = "https://api.anaf.ro/prod/FCTEL/rest/stareMesaj"
    message_list_url: str = "https://api.anaf.ro/prod/FCTEL/rest/listaMesajeFactura"
    download_url: str = "https://api.anaf.ro/prod/FCTEL/rest/descarcare"
    xml_validate_url: str = "https://api.anaf.ro/prod/FCTEL/rest/validare/FACT1"
    xml2pdf_url: str = "https://api.anaf.ro/prod/FCTEL/rest/transformare/FACT1/DA"


class StorageSettings(BaseModel):
    """Local filesystem paths and default query parameters."""
    download_dir: Path = Path("dlds/")
    default_cif: int = 19507820


class RetrySettings(BaseModel):
    """Retry policy for HTTP requests to ANAF APIs."""
    count: int = 3
    delay: int = 5
    backoff_factor: int = 2
    max_delay: int = 20


class LogSettings(BaseModel):
    """Logging configuration paths."""
    config: Path | None = None
    file: Path | None = None


class NotificationSettings(BaseModel):
    """Email alert settings for sync failures."""

    email_to: str | None = None
    smtp_host: str = "localhost"
    smtp_port: int = 25
    smtp_user: str | None = None
    smtp_password: str | None = None
    network_failure_threshold: int = 5


class StateSettings(BaseModel):
    """Paths for persistent runtime state across sync runs."""

    state_file: Path = Path("state/sync_state.json")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LIBANAF_",
        env_nested_delimiter="__",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    auth: AuthSettings
    connection: ConnectionSettings = ConnectionSettings()
    efactura: EfacturaSettings = EfacturaSettings()
    storage: StorageSettings = StorageSettings()
    retry: RetrySettings = RetrySettings()
    log: LogSettings = LogSettings()
    notification: NotificationSettings = NotificationSettings()
    state: StateSettings = StateSettings()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    env_file = os.environ.get("LIBANAF_ENV_FILE", "secrets/.env")
    return Settings(_env_file=env_file)


def save_tokens(tokens: dict[str, Any]) -> None:
    """Save the access and refresh tokens to the environment file.

    Reads the target env-file path from the ``LIBANAF_ENV_FILE`` environment
    variable (defaulting to ``secrets/.env``) and writes the ``access_token``
    and ``refresh_token`` values using python-dotenv's ``set_key`` helper so
    that the file is updated in-place without disturbing other entries.

    Args:
        tokens: Mapping that must contain ``"access_token"`` and
            ``"refresh_token"`` string values, as returned by Authlib's
            ``fetch_token`` / ``refresh_token`` flows.
    """
    env_file = os.environ.get("LIBANAF_ENV_FILE", "secrets/.env")
    set_key(env_file, "LIBANAF_CONNECTION__ACCESS_TOKEN", tokens["access_token"])
    set_key(env_file, "LIBANAF_CONNECTION__REFRESH_TOKEN", tokens["refresh_token"])


def setup_logging(verbose: bool, settings: Settings) -> None:
    """Configure the Python logging subsystem.

    Loads a JSON logging config from ``settings.log.config`` when the file
    exists, optionally overriding the log-file ``filename`` handler entry
    with ``settings.log.file``.  In verbose mode the console handler is
    switched to ``DEBUG`` and HTTP-library debug logging is enabled.
    Falls back to ``basicConfig`` when no JSON config is found.

    Args:
        verbose: When ``True``, set the console handler to DEBUG level and
            enable low-level HTTP debug logging.
        settings: Application settings instance used to locate the JSON
            logging config and the target log file path.
    """
    if settings.log.config and settings.log.config.exists():
        with open(settings.log.config) as f:
            cfg: dict[str, Any] = json.load(f)
        if settings.log.file and "file" in cfg.get("handlers", {}):
            cfg["handlers"]["file"]["filename"] = str(settings.log.file)
        if verbose:
            if "console" in cfg.get("handlers", {}):
                cfg["handlers"]["console"]["level"] = "DEBUG"
            _setup_requests_logging()
        logging.config.dictConfig(cfg)
    else:
        level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(level=level)
        if verbose:
            _setup_requests_logging()


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
