import asyncio
import logging
from datetime import datetime, timezone
from typing import Annotated

import jwt
import typer
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.oauth2.rfc6749 import OAuth2Error
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from libanaf.auth import AnafAuthClient
from libanaf.auth.server import OAuthCallbackServer
from libanaf.auth.tls import ensure_tls_cert
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


def show_token(
    ctx: typer.Context,
    verify: Annotated[
        bool,
        typer.Option("--verify", help="Attempt a live refresh against ANAF to confirm the refresh token is valid."),
    ] = False,
) -> None:
    """Decode and display the claims from the stored JWT tokens.

    Reads the current access token and refresh token from settings and
    decodes both without signature verification, printing all claims in
    a Rich table. Timestamp claims (exp, iat, nbf, auth_time) are shown
    as both their raw integer value and a human-readable UTC datetime.
    Handles missing tokens and non-JWT (opaque) tokens gracefully.

    ANAF's refresh token is opaque (not a JWT) by design, so its validity
    cannot be determined by local decoding. Pass ``--verify`` to actually
    exchange it against the token endpoint instead.
    """
    settings: Settings = ctx.obj

    _print_token_panel(settings.connection.access_token, "Access Token")
    _print_token_panel(settings.connection.refresh_token, "Refresh Token")

    if verify:
        _verify_refresh_token(settings)


def test_tls_server(ctx: typer.Context) -> None:
    """Start the local HTTPS callback server standalone, for TLS verification without the full ANAF flow.

    Ensures/generates the self-signed cert, starts the same
    ``OAuthCallbackServer`` used during ``auth``, and prints a URL to open
    manually in a browser. Blocks until that request arrives, then prints
    the received query parameters. Useful for isolating TLS/browser issues
    (e.g. ``ERR_SSL_PROTOCOL_ERROR``) from ANAF-side authorization problems.
    """
    settings: Settings = ctx.obj
    cert_path, key_path = ensure_tls_cert(settings.connection.tls_cert_file, settings.connection.tls_key_file)

    console.print(f"[cyan]Using cert:[/cyan] {cert_path}\n[cyan]Using key:[/cyan]  {key_path}")
    console.print(
        "[bold]Open this URL in the browser you're testing "
        "(accept the self-signed cert warning):[/bold]\n"
        "https://localhost:8000/callback?code=test-tls-verification"
    )

    server = OAuthCallbackServer(use_ssl=True, cert_file=str(cert_path), key_file=str(key_path))
    response = server.get_auth_response()

    console.print(Panel(f"[green]TLS handshake OK. Received:[/green] {dict(response)}", title="Test TLS Server"))


# ── helpers ────────────────────────────────────────────────────────────────────

_TIMESTAMP_CLAIMS = {"exp", "iat", "nbf", "auth_time"}


def _verify_refresh_token(settings: Settings) -> None:
    """Exchange the stored refresh token against ANAF's token endpoint to confirm it is live.

    ANAF rotates refresh tokens on use, so a successful check replaces the
    stored refresh token with a new one (via ``save_tokens``) and invalidates
    the old one. Prompts for confirmation before making the live call.

    Args:
        settings: Application settings holding auth config and the current refresh token.
    """
    if not settings.connection.refresh_token:
        console.print(Panel("[yellow]No refresh token to verify.[/yellow]", title="Verify Refresh Token"))
        return

    if not typer.confirm(
        "This calls ANAF live and will rotate the refresh token (old one becomes invalid). Continue?",
        default=False,
    ):
        raise typer.Exit(0)

    client = AsyncOAuth2Client(
        client_id=settings.auth.client_id,
        client_secret=settings.auth.client_secret,
        token_endpoint=settings.auth.token_url,
    )
    try:
        token = asyncio.run(
            client.refresh_token(settings.auth.token_url, refresh_token=settings.connection.refresh_token)
        )
    except OAuth2Error as e:
        console.print(Panel(f"[red]Refresh token is INVALID or expired:[/red] {e}", title="Verify Refresh Token"))
        return
    except Exception as e:
        console.print(Panel(f"[red]Verification failed: {e}[/red]", title="Verify Refresh Token"))
        return

    save_tokens(token)
    console.print(Panel("[green]Refresh token is VALID. New tokens saved.[/green]", title="Verify Refresh Token"))


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
