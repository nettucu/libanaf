import logging
from datetime import datetime, timezone

import jwt
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from libanaf.auth import AnafAuthClient
from libanaf.config import Settings, save_tokens
from libanaf.exceptions import AuthorizationError

logger = logging.getLogger(__name__)
console = Console()


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


def show_token(ctx: typer.Context) -> None:
    """Decode and display the claims from the stored JWT tokens.

    Reads the current access token and refresh token from settings and
    decodes both without signature verification, printing all claims in
    a Rich table. Timestamp claims (exp, iat, nbf, auth_time) are shown
    as both their raw integer value and a human-readable UTC datetime.
    Handles missing tokens and non-JWT (opaque) tokens gracefully.
    """
    settings: Settings = ctx.obj

    _print_token_panel(settings.connection.access_token, "Access Token")
    _print_token_panel(settings.connection.refresh_token, "Refresh Token")


# ── helpers ────────────────────────────────────────────────────────────────────

_TIMESTAMP_CLAIMS = {"exp", "iat", "nbf", "auth_time"}


def _print_token_panel(raw_token: str | None, title: str) -> None:
    """Decode a single JWT and render it as a named Rich panel.

    Args:
        raw_token: The raw JWT string, or ``None`` / empty if absent.
        title: Panel title shown in the Rich output.
    """
    if not raw_token:
        console.print(Panel(f"[yellow]No {title.lower()} found in settings.[/yellow]", title=title))
        return

    try:
        claims = jwt.decode(raw_token, options={"verify_signature": False})
    except jwt.exceptions.DecodeError:
        console.print(Panel(f"[yellow]Token is not a JWT (opaque token).[/yellow]\n{raw_token}", title=title))
        return

    table = Table(show_header=True, header_style="bold white on navy_blue", box=None, expand=True)
    table.add_column("Claim", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    for claim, value in sorted(claims.items()):
        if claim in _TIMESTAMP_CLAIMS and isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            table.add_row(claim, f"{value}  ({dt})")
        else:
            table.add_row(claim, str(value))

    console.print(Panel(table, title=title, padding=(1, 2)))
