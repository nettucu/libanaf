"""CLI commands for the ANAF SPV web service (Spațiul Privat Virtual)."""

import logging
import sys
from pathlib import Path
from typing import Annotated, NoReturn

import typer
from rich.console import Console
from rich.table import Table

from libanaf.config import Settings
from libanaf.exceptions import AnafRequestError, SpvSessionError

app = typer.Typer()
console = Console()
logger = logging.getLogger(__name__)


def _session(settings: Settings):
    """Build the configured SPV session provider."""
    from libanaf.spv.session import CookieJarSession

    return CookieJarSession(settings.spv.cookie_file, settings.spv.base_url, settings.spv.timeout)


def _client(settings: Settings):
    """Build an SPV client on top of the configured session."""
    from libanaf.spv.client import SpvClient

    return SpvClient(_session(settings))


def _fail(error: Exception) -> NoReturn:
    """Print an SPV error and exit non-zero."""
    icon: str = "🔐" if isinstance(error, SpvSessionError) else "❌"
    console.print(f"{icon} {error}", style="red")
    raise typer.Exit(code=1)


@app.command(name="import-cookies")
def import_cookies(
    ctx: typer.Context,
    source: Annotated[
        Path | None,
        typer.Argument(help="Fișier cookies.txt (Netscape) sau header Cookie; implicit se citește din stdin"),
    ] = None,
) -> None:
    """Import the SPV session cookies from a browser where you logged in with the certificate.

    \b
    Pași (pe Windows/Mac, unde rulează aplicația vToken):
     1. Pornește vToken și deschide în Chrome/Edge/Firefox/Safari:
        https://webserviced.anaf.ro/SPVWS2/rest/listaMesaje?zile=60
        Alege certificatul, introdu codul din Authenticator, așteaptă lista JSON.
     2. Deschide DevTools (F12; Mac: Cmd+Opt+I; în Safari activează întâi
        Settings > Advanced > Show features for web developers), tabul Network.
     3. Reîncarcă pagina (F5 / Cmd+R), click pe cererea listaMesaje,
        Headers > Request Headers > Cookie: copiază valoarea
        (MRHSession=...; LastMRH_Session=...; F5_ST=...).
     4. Nu apăsa logout și nu șterge cookie-urile: asta închide sesiunea.

    \b
    Transfer pe Linux (alege una):
     Mac (Terminal):
       pbpaste | ssh zeppelin 'cd ~/work/libanaf && \\
         uv run libanaf spv import-cookies'
     Windows (PowerShell):
       Get-Clipboard | ssh zeppelin "cd ~/work/libanaf && \\
         uv run libanaf spv import-cookies"
     Manual: rulează `libanaf spv import-cookies` pe Linux,
       lipește valoarea, apoi Enter și Ctrl+D.
     Fișier: exportă cookies.txt (extensia "Get cookies.txt LOCALLY"),
       copiază-l și rulează `libanaf spv import-cookies cookies.txt`;
       apoi șterge fișierul de pe ambele mașini.

    \b
    Verificare: `libanaf spv list`.
    Cookie-urile dau acces la SPV ca o parolă: nu le trimite pe chat/email.
    Când sesiunea expiră, comenzile ies cu 🔐; repetă pașii.
    """
    from libanaf.spv.session import parse_cookies

    settings: Settings = ctx.obj
    text: str = source.read_text() if source else sys.stdin.read()
    try:
        cookies: dict[str, str] = parse_cookies(text)
    except SpvSessionError as e:
        _fail(e)
    _session(settings).save(cookies)
    console.print(f"✅ Saved {len(cookies)} cookies ({', '.join(sorted(cookies))}) to {settings.spv.cookie_file}")


@app.command(name="list")
def spv_list(
    ctx: typer.Context,
    days: Annotated[int, typer.Option(help="Numărul de zile (1–60)", min=1, max=60)] = 60,
    cif: Annotated[str | None, typer.Option(help="Filtrează după CUI/CNP")] = None,
) -> None:
    """List SPV inbox messages."""
    try:
        messages = _client(ctx.obj).list_messages(days, cif).mesaje
    except (AnafRequestError, SpvSessionError) as e:
        _fail(e)

    table = Table(title=f"📬 Mesaje SPV ({len(messages)})")
    for column in ("Data", "CIF", "Tip", "ID", "Solicitare", "Detalii"):
        table.add_column(column)
    for m in messages:
        table.add_row(f"{m.data_creare:%Y-%m-%d %H:%M}", m.cif, m.tip, m.id, m.id_solicitare or "", m.detalii)
    console.print(table)


@app.command(name="download")
def spv_download(
    ctx: typer.Context,
    days: Annotated[int, typer.Option(help="Numărul de zile (1–60)", min=1, max=60)] = 60,
    cif: Annotated[str | None, typer.Option(help="Filtrează după CUI/CNP")] = None,
    out_dir: Annotated[Path | None, typer.Option("--dir", help="Director destinație")] = None,
) -> None:
    """Download inbox PDFs not stored locally yet, as <dir>/<cif>/<YYYY-MM>/<date>_<tip>_<id>.pdf."""
    settings: Settings = ctx.obj
    target: Path = out_dir or settings.spv.download_dir
    client = _client(settings)
    try:
        messages = client.list_messages(days, cif).mesaje
    except (AnafRequestError, SpvSessionError) as e:
        _fail(e)

    existing: set[str] = {p.stem.rsplit("_", 1)[-1] for p in target.rglob("*.pdf")} if target.exists() else set()
    new = [m for m in messages if m.id not in existing]
    console.print(f"📬 {len(messages)} messages, {len(new)} new")

    for m in new:
        path: Path = (
            target / m.cif / f"{m.data_creare:%Y-%m}" / f"{m.data_creare:%Y-%m-%d}_{m.tip.replace(' ', '-')}_{m.id}.pdf"
        )
        try:
            pdf: bytes = client.download(m.id)
        except SpvSessionError as e:
            _fail(e)
        except AnafRequestError as e:
            console.print(f"⚠️ {e}", style="yellow")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pdf)
        console.print(f"✅ {path}")


@app.command(name="request")
def spv_request(
    ctx: typer.Context,
    tip: Annotated[str, typer.Argument(help='Tipul documentului, exact ca la ANAF (ex. "Fisa Rol", "D300")')],
    cui: Annotated[str, typer.Option(help="CUI/CNP")],
    an: Annotated[int | None, typer.Option(help="Anul")] = None,
    luna: Annotated[int | None, typer.Option(help="Luna")] = None,
    motiv: Annotated[str | None, typer.Option(help="Motiv (Adeverinte Venit)")] = None,
    numar_inregistrare: Annotated[str | None, typer.Option(help="Număr înregistrare (Duplicat Recipisa)")] = None,
    cui_pui: Annotated[str | None, typer.Option(help="CUI punct de lucru (Fisa Rol)")] = None,
    lunai: Annotated[int | None, typer.Option(help="Luna inițială (NeconcordanteD394)")] = None,
    lunas: Annotated[int | None, typer.Option(help="Luna finală (NeconcordanteD394)")] = None,
) -> None:
    """File a document request; the answer arrives later as an inbox message. Each call is a new request."""
    try:
        request_id: str = _client(ctx.obj).request(
            tip,
            cui,
            an=an,
            luna=luna,
            motiv=motiv,
            numar_inregistrare=numar_inregistrare,
            cui_pui=cui_pui,
            lunai=lunai,
            lunas=lunas,
        )
    except (AnafRequestError, SpvSessionError) as e:
        _fail(e)
    console.print(f"📨 Cerere trimisă: id_solicitare={request_id}")
