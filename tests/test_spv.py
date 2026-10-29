"""Tests for the SPV (SPVWS2) cookie session, client and CLI — no live ANAF calls."""

import json
import re
import stat
import sys
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from libanaf.cli import app
from libanaf.config import AuthSettings, Settings, SpvSettings
from libanaf.exceptions import AnafRequestError, SpvSessionError
from libanaf.spv.client import SpvClient
from libanaf.spv.session import CookieJarSession, parse_cookies

BASE_URL = "https://webserviced.anaf.ro/SPVWS2/rest/"
LIST_OK = {
    "mesaje": [
        {
            "id": 111,
            "cif": "123",
            "tip": "RECIPISA ",
            "detalii": "recipisa D300",
            "data_creare": "15.10.2026 10:20:30",
            "id_solicitare": None,
        },
        {"id": "222", "cif": "123", "tip": "RASPUNS SOLICITARE", "data_creare": "16.10.2026", "id_solicitare": 9},
    ],
    "cui": "123, 456",
    "cnp": "0",
    "serial": "x",
    "titlu": "Lista mesaje",
}


class FakeSession:
    """SpvSession backed by an httpx MockTransport."""

    def __init__(self, handler) -> None:
        self.handler = handler

    def client(self) -> httpx.Client:
        return httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(self.handler), follow_redirects=True)


def _json_handler(payload: dict, seen: list | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(200, json=payload)

    return handler


def test_parse_cookie_header() -> None:
    assert parse_cookies("Cookie: MRHSession=abc; F5_ST=1z2; LastMRH_Session=x=y") == {
        "MRHSession": "abc",
        "F5_ST": "1z2",
        "LastMRH_Session": "x=y",
    }


def test_parse_netscape_keeps_only_anaf() -> None:
    text = (
        "# Netscape HTTP Cookie File\n"
        "#HttpOnly_webserviced.anaf.ro\tFALSE\t/\tTRUE\t0\tMRHSession\tabc\n"
        ".anaf.ro\tTRUE\t/\tTRUE\t0\tF5_ST\tdef\n"
        ".google.com\tTRUE\t/\tTRUE\t0\tNID\tnope\n"
    )
    assert parse_cookies(text) == {"MRHSession": "abc", "F5_ST": "def"}


def test_parse_empty_raises() -> None:
    with pytest.raises(SpvSessionError):
        parse_cookies("   ")


def test_cookie_jar_roundtrip_is_private(tmp_path: Path) -> None:
    session = CookieJarSession(tmp_path / "s" / "c.json", BASE_URL, 5)
    session.save({"MRHSession": "abc"})
    assert stat.S_IMODE(session.cookie_file.stat().st_mode) == 0o600
    with session.client() as client:
        assert client.cookies["MRHSession"] == "abc"


def test_cookie_jar_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(SpvSessionError):
        CookieJarSession(tmp_path / "none.json", BASE_URL, 5).load()


def test_list_messages_parses() -> None:
    seen: list[httpx.Request] = []
    result = SpvClient(FakeSession(_json_handler(LIST_OK, seen))).list_messages(30, "123")
    assert seen[0].url.params["zile"] == "30" and seen[0].url.params["cif"] == "123"
    assert [m.id for m in result.mesaje] == ["111", "222"]
    assert result.mesaje[0].tip == "RECIPISA"
    assert result.mesaje[0].data_creare.hour == 10
    assert result.mesaje[1].id_solicitare == "9"


def test_list_messages_empty_is_not_error() -> None:
    payload = {"titlu": "Lista", "eroare": "Nu exista mesaje in ultimele 60 zile"}
    assert SpvClient(FakeSession(_json_handler(payload))).list_messages().mesaje == []


def test_list_messages_rights_error() -> None:
    payload = {"titlu": "Lista", "eroare": "Nu aveti drept de interogare pentru CUI=1"}
    with pytest.raises(AnafRequestError):
        SpvClient(FakeSession(_json_handler(payload))).list_messages()


def test_redirect_to_login_is_session_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/SPVWS2"):
            return httpx.Response(302, headers={"location": "/my.policy"})
        return httpx.Response(200, html="<html>login</html>")

    with pytest.raises(SpvSessionError):
        SpvClient(FakeSession(handler)).list_messages()


def test_html_200_on_rest_path_is_session_error() -> None:
    with pytest.raises(SpvSessionError):
        SpvClient(FakeSession(lambda r: httpx.Response(200, html="<html>login</html>"))).list_messages()


def test_download_pdf_and_error() -> None:
    pdf = SpvClient(FakeSession(lambda r: httpx.Response(200, content=b"%PDF-1.4 x"))).download("1")
    assert pdf.startswith(b"%PDF")
    with pytest.raises(AnafRequestError):
        SpvClient(FakeSession(_json_handler({"titlu": "x", "eroare": "id invalid"}))).download("1")


def test_request_drops_none_params() -> None:
    seen: list[httpx.Request] = []
    request_id = SpvClient(FakeSession(_json_handler({"id_solicitare": 42}, seen))).request(
        "D300", "123", an=2026, luna=9, motiv=None
    )
    assert request_id == "42"
    assert dict(seen[0].url.params) == {"tip": "D300", "cui": "123", "an": "2026", "luna": "9"}


def test_cli_import_and_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        auth=AuthSettings(client_id="c", client_secret="s", redirect_uri="https://r"),
        spv=SpvSettings(cookie_file=tmp_path / "c.json", download_dir=tmp_path / "out"),
    )
    monkeypatch.setattr(sys.modules["libanaf.cli.app"], "get_settings", lambda: settings)
    monkeypatch.setattr(sys.modules["libanaf.cli.app"], "setup_logging", lambda *a: None)

    runner = CliRunner()
    result = runner.invoke(app, ["spv", "import-cookies"], input="MRHSession=abc; F5_ST=def")
    assert result.exit_code == 0, result.output
    assert json.loads((tmp_path / "c.json").read_text()) == {"MRHSession": "abc", "F5_ST": "def"}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["cookie"]
        if request.url.path.endswith("listaMesaje"):
            return httpx.Response(200, json=LIST_OK)
        return httpx.Response(200, content=b"%PDF-1.4 " + request.url.params["id"].encode())

    real_client = httpx.Client
    monkeypatch.setattr(
        "libanaf.spv.session.httpx.Client",
        lambda **kw: real_client(**kw, transport=httpx.MockTransport(handler)),
    )
    result = runner.invoke(app, ["spv", "download"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "out/123/2026-10/2026-10-15_RECIPISA_111.pdf").read_bytes() == b"%PDF-1.4 111"
    assert (tmp_path / "out/123/2026-10/2026-10-16_RASPUNS-SOLICITARE_222.pdf").exists()

    result = runner.invoke(app, ["spv", "download"])
    assert "0 new" in result.output


def test_cli_list_request_and_expired_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        auth=AuthSettings(client_id="c", client_secret="s", redirect_uri="https://r"),
        spv=SpvSettings(cookie_file=tmp_path / "c.json", download_dir=tmp_path / "out"),
    )
    runner = CliRunner()
    monkeypatch.setattr(sys.modules["libanaf.cli.app"], "get_settings", lambda: settings)
    monkeypatch.setattr(sys.modules["libanaf.cli.app"], "setup_logging", lambda *a: None)

    result = runner.invoke(app, ["spv", "list"])
    assert result.exit_code == 1 and "import-cookies" in result.output

    CookieJarSession(settings.spv.cookie_file, BASE_URL, 5).save({"MRHSession": "abc"})

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("cerere"):
            return httpx.Response(200, json={"id_solicitare": 77})
        return httpx.Response(200, json=LIST_OK)

    real_client = httpx.Client
    monkeypatch.setattr(
        "libanaf.spv.session.httpx.Client",
        lambda **kw: real_client(**kw, transport=httpx.MockTransport(handler)),
    )
    result = runner.invoke(app, ["spv", "list", "--days", "10"])
    assert result.exit_code == 0 and "RECIPISA" in result.output
    summary = result.output.split("autorizate")[1]
    assert re.search(r"123\s.*✅.*\s2\s", summary) and re.search(r"456\s.*✅.*\s0\s", summary)

    result = runner.invoke(app, ["spv", "request", "Fisa Rol", "--cui", "123"])
    assert result.exit_code == 0 and "id_solicitare=77" in result.output


def test_download_new_skips_stored_and_reports_failures(tmp_path: Path) -> None:
    from libanaf.spv.archive import download_new, message_path

    first = SpvClient(FakeSession(_json_handler(LIST_OK))).list_messages().mesaje[0]
    stored = message_path(tmp_path, first)
    stored.parent.mkdir(parents=True)
    stored.write_bytes(b"%PDF-old")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("listaMesaje"):
            return httpx.Response(200, json=LIST_OK)
        return httpx.Response(200, json={"titlu": "x", "eroare": "id invalid"})

    result = download_new(SpvClient(FakeSession(handler)), tmp_path)
    assert result.total == 2 and result.downloaded == []
    assert len(result.failed) == 1 and result.failed[0].startswith("222:")
    assert stored.read_bytes() == b"%PDF-old"
