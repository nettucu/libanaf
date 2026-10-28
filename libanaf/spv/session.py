"""Session providers for the ANAF SPV web service (SPVWS2).

SPVWS2 sits behind an F5 BIG-IP APM: the qualified certificate is only used once, during the
``/my.policy`` bootstrap, after which the APM cookies (``MRHSession``, ``LastMRH_Session``,
``F5_ST``) authorize every request. A session provider hands out an ``httpx.Client`` carrying
whatever that bootstrap produced, so the SPV client does not care how the session was obtained.

Today the only provider is :class:`CookieJarSession` (cookies bootstrapped in a browser with a
cloud certificate such as certSIGN vToken, then imported). A PKCS#11 provider can implement the
same :class:`SpvSession` protocol later.
"""

import json
import logging
import os
from pathlib import Path
from typing import Protocol

import httpx

from libanaf.exceptions import SpvSessionError

logger = logging.getLogger(__name__)


class SpvSession(Protocol):
    """Anything that can produce an ``httpx.Client`` authorized for SPVWS2."""

    def client(self) -> httpx.Client:
        """Return a client whose requests are accepted by SPVWS2."""
        ...


def parse_cookies(text: str) -> dict[str, str]:
    """Parse cookies exported from a browser.

    Accepts either a Netscape ``cookies.txt`` export (tab-separated, as written by
    "Get cookies.txt"-style extensions or ``curl -c``) or a raw ``Cookie`` header value
    copied from DevTools (``name=value; name2=value2``). Netscape rows for domains other
    than ``anaf.ro`` are ignored.

    Args:
        text: Exported cookie text.

    Returns:
        Mapping of cookie name to value.

    Raises:
        SpvSessionError: When no cookie could be parsed.
    """
    cookies: dict[str, str] = {}
    lines: list[str] = [line for line in text.strip().splitlines() if line.strip()]
    netscape_rows: list[list[str]] = [line.split("\t") for line in lines if line.count("\t") >= 6]

    if netscape_rows:
        for row in netscape_rows:
            # "#HttpOnly_" prefixes the domain for HttpOnly cookies; plain "#" lines are comments.
            domain: str = row[0].removeprefix("#HttpOnly_")
            if domain.startswith("#") or not domain.lstrip(".").endswith("anaf.ro"):
                continue
            cookies[row[5]] = row[6].strip()
    else:
        header: str = " ".join(lines).removeprefix("Cookie:").strip()
        for part in header.split(";"):
            name, sep, value = part.strip().partition("=")
            if sep and name:
                cookies[name] = value

    if not cookies:
        raise SpvSessionError("No ANAF cookies found in the provided text")
    return cookies


class CookieJarSession:
    """SPV session backed by browser cookies persisted to a local JSON file.

    The cookie file is a bearer credential: it is written with ``0600`` permissions and must
    never be committed or logged.
    """

    def __init__(self, cookie_file: Path, base_url: str, timeout: float) -> None:
        """Create the session provider.

        Args:
            cookie_file: Path of the JSON file holding the imported cookies.
            base_url: SPVWS2 REST base URL.
            timeout: Per-request timeout in seconds.
        """
        self.cookie_file: Path = cookie_file
        self.base_url: str = base_url
        self.timeout: float = timeout

    def save(self, cookies: dict[str, str]) -> None:
        """Persist cookies to ``cookie_file`` with owner-only permissions.

        Args:
            cookies: Mapping of cookie name to value.
        """
        self.cookie_file.parent.mkdir(parents=True, exist_ok=True)
        fd: int = os.open(self.cookie_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(cookies, f)
        os.chmod(self.cookie_file, 0o600)
        logger.info(f"Saved {len(cookies)} SPV cookies to {self.cookie_file}: {sorted(cookies)}")

    def load(self) -> dict[str, str]:
        """Load the persisted cookies.

        Returns:
            Mapping of cookie name to value.

        Raises:
            SpvSessionError: When no cookie file exists yet.
        """
        if not self.cookie_file.exists():
            raise SpvSessionError(f"No SPV session at {self.cookie_file}; run `libanaf spv import-cookies` first")
        with open(self.cookie_file) as f:
            return json.load(f)

    def client(self) -> httpx.Client:
        """Return an ``httpx.Client`` carrying the imported cookies.

        Returns:
            Client bound to ``base_url`` that follows redirects (the APM may insert a
            ``/my.policy_nonce`` revalidation hop).
        """
        return httpx.Client(
            base_url=self.base_url,
            cookies=self.load(),
            timeout=self.timeout,
            follow_redirects=True,
        )
