import logging

import typer

from libanaf.auth import AnafAuthClient
from libanaf.config import Settings, save_tokens
from libanaf.exceptions import AuthorizationError

logger = logging.getLogger(__name__)


def auth(ctx: typer.Context) -> None:
    """Authenticate to ANAF portal and retrieve tokens."""
    settings: Settings = ctx.obj
    client = AnafAuthClient(
        client_id=settings.auth.client_id,
        client_secret=settings.auth.client_secret,
        auth_url=settings.auth.auth_url,
        token_url=settings.auth.token_url,
        redirect_uri=settings.auth.redirect_uri,
        access_token=settings.connection.access_token,
        refresh_token=settings.connection.refresh_token,
        cert_file=settings.connection.tls_cert_file,
        key_file=settings.connection.tls_key_file,
    )
    while True:
        try:
            token = client.get_access_token()
            save_tokens(token)
            logger.debug(f"token = {token}")
            break
        except AuthorizationError as e:
            if not typer.confirm(f"Authorization error: {e}. Retry?", default=True):
                raise typer.Exit(1)
