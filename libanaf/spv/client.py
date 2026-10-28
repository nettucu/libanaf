"""Client for the ANAF SPV web service (SPVWS2): inbox listing, PDF download and report requests.

Endpoints (relative to ``SpvSettings.base_url``):

- ``listaMesaje?zile=N[&cif=CUI]`` — inbox messages from the last N days (SPV keeps 60).
- ``descarcare?id=ID`` — message PDF.
- ``cerere?tip=TIP&cui=CUI[&an&luna&motiv&numar_inregistrare&cui_pui&lunai&lunas]`` — asynchronous
  report request; the answer lands in the inbox with a matching ``id_solicitare``.

Errors come back as JSON ``{titlu, eroare}``; an expired session comes back as an HTML login page
(sometimes with HTTP 200) after redirects out of the REST prefix.
"""

import logging
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, Field, field_validator

from libanaf.exceptions import AnafRequestError, SpvSessionError
from libanaf.spv.session import SpvSession

logger = logging.getLogger(__name__)

PDF_MAGIC: bytes = b"%PDF"
# shortcut: ANAF signals "empty inbox" only through this error text; revisit if the wording changes.
NO_MESSAGES_PREFIX: str = "Nu exista mesaje"


class SpvMessage(BaseModel):
    """One SPV inbox message."""

    id: str
    cif: str
    tip: str
    detalii: str = ""
    data_creare: datetime
    id_solicitare: str | None = None

    @field_validator("id", "cif", "id_solicitare", mode="before")
    @classmethod
    def _to_str(cls, value: Any) -> str | None:
        return None if value is None else str(value)

    @field_validator("tip", mode="before")
    @classmethod
    def _strip(cls, value: str) -> str:
        # ANAF returns e.g. "DECLARATIE " with a trailing space.
        return value.strip()

    @field_validator("data_creare", mode="before")
    @classmethod
    def _parse_date(cls, value: str) -> datetime:
        fmt: str = "%d.%m.%Y %H:%M:%S" if " " in value.strip() else "%d.%m.%Y"
        return datetime.strptime(value.strip(), fmt)


class SpvMessageList(BaseModel):
    """Response of ``listaMesaje``."""

    mesaje: list[SpvMessage] = Field(default_factory=list)
    cui: str | None = None


class SpvClient:
    """Synchronous SPVWS2 client on top of a pluggable :class:`SpvSession`."""

    def __init__(self, session: SpvSession) -> None:
        """Create the client.

        Args:
            session: Provider of an authorized ``httpx.Client``.
        """
        self.session: SpvSession = session

    def _get(self, endpoint: str, params: dict[str, str]) -> httpx.Response:
        """Issue a GET and reject responses that are not SPV payloads.

        Args:
            endpoint: Endpoint name relative to the base URL (e.g. ``"listaMesaje"``).
            params: Query parameters.

        Returns:
            Response whose body is JSON or PDF.

        Raises:
            SpvSessionError: When ANAF redirected to the certificate login.
            AnafRequestError: On network errors or HTTP error statuses.
        """
        try:
            with self.session.client() as client:
                logger.info(f"Requesting SPV: GET {endpoint} params={params}")
                response: httpx.Response = client.get(endpoint, params=params)
        except httpx.HTTPError as e:
            raise AnafRequestError(f"SPV request {endpoint} failed: {e}") from e

        logger.info(f"SPV response: {response.status_code} for {response.url.path}")
        content_type: str = response.headers.get("content-type", "")
        is_payload: bool = response.content.startswith(PDF_MAGIC) or response.content.lstrip().startswith(b"{")
        if "/SPVWS2/rest/" not in response.url.path or ("html" in content_type and not is_payload):
            raise SpvSessionError(
                f"SPV session expired (landed on {response.url.path}); log in again and run "
                "`libanaf spv import-cookies`"
            )
        if response.is_error:
            raise AnafRequestError(f"SPV {endpoint} returned HTTP {response.status_code}")
        return response

    @staticmethod
    def _json(response: httpx.Response) -> dict[str, Any]:
        """Decode a JSON body.

        Raises:
            SpvSessionError: When the body is not JSON (login page served as text).
        """
        try:
            return response.json()
        except ValueError as e:
            raise SpvSessionError(f"SPV returned a non-JSON body; session likely expired: {e}") from e

    def list_messages(self, days: int = 60, cif: str | None = None) -> SpvMessageList:
        """List inbox messages.

        Args:
            days: Look-back window in days (1–60).
            cif: Optional CUI/CNP filter.

        Returns:
            Parsed message list; empty when SPV has no messages in the window.

        Raises:
            AnafRequestError: When SPV answers with an ``eroare``.
        """
        params: dict[str, str] = {"zile": str(days)}
        if cif:
            params["cif"] = cif
        data: dict[str, Any] = self._json(self._get("listaMesaje", params))
        if error := data.get("eroare"):
            if error.startswith(NO_MESSAGES_PREFIX):
                return SpvMessageList()
            raise AnafRequestError(f"SPV listaMesaje error: {error}")
        return SpvMessageList.model_validate(data)

    def download(self, message_id: str) -> bytes:
        """Download a message PDF.

        Args:
            message_id: ``id`` from :meth:`list_messages`.

        Returns:
            PDF bytes.

        Raises:
            AnafRequestError: When SPV answers with an ``eroare`` instead of a PDF.
        """
        response: httpx.Response = self._get("descarcare", {"id": message_id})
        if response.content.startswith(PDF_MAGIC):
            return response.content
        error: str = self._json(response).get("eroare", "unexpected response")
        raise AnafRequestError(f"SPV descarcare {message_id} error: {error}")

    def request(self, tip: str, cui: str, **params: str | int | None) -> str:
        """File a report request (``cerere``). Every call creates a new request at ANAF.

        Args:
            tip: Report type, verbatim (e.g. ``"Fisa Rol"``, ``"D300"``, ``"Duplicat Recipisa"``).
            cui: CUI/CNP the report is for.
            **params: Type-specific parameters (``an``, ``luna``, ``motiv``, ``numar_inregistrare``,
                ``cui_pui``, ``lunai``, ``lunas``); ``None`` values are dropped.

        Returns:
            The ``id_solicitare`` to match against inbox messages.

        Raises:
            AnafRequestError: When SPV rejects the request.
        """
        query: dict[str, str] = {"tip": tip, "cui": cui}
        query.update({k: str(v) for k, v in params.items() if v is not None})
        data: dict[str, Any] = self._json(self._get("cerere", query))
        if error := data.get("eroare"):
            raise AnafRequestError(f"SPV cerere {tip} error: {error}")
        return str(data["id_solicitare"])
