"""Fetch the ANAF e-Factura invoice message list.

Provides an async function to query the ANAF ``listaMesajeFactura`` endpoint
with OAuth2 authentication and automatic retry on transient errors.
"""

import json
import logging

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.oauth2.rfc6749.errors import OAuth2Error
from httpx import HTTPStatusError, Response

from libanaf.auth import AnafAuthClient
from libanaf.config import get_settings
from libanaf.exceptions import AnafRequestError, TokenExpiredError
from libanaf.invoices._retry import anaf_retrying
from libanaf.types import Filter

logger = logging.getLogger(__name__)


async def fetch_invoice_list(
    days: int | None = 60, cif: int | None = 19507820, filter: Filter | None = Filter.P
) -> dict[str, str | list[dict[str, str]]]:
    """Fetch the invoice message list from the ANAF e-Factura API.

    Builds an authenticated OAuth2 client and issues a GET request to the
    ``listaMesajeFactura`` endpoint. Retries on transient network or HTTP
    errors using exponential backoff configured from settings.

    Args:
        days: Number of past days to include in the query (1–60). Defaults to 60.
        cif: Company CIF to query. Defaults to 19507820.
        filter: Message type filter (E, T, P, R). Defaults to ``Filter.P``.

    Returns:
        dict: Parsed JSON response containing a ``"mesaje"`` list of message dicts.

    Raises:
        AnafRequestError: On HTTP errors, timeouts, network errors, or when the
            API returns an ``"eroare"`` field in the response body.
    """
    settings = get_settings()

    base_url: str = settings.efactura.message_list_url

    params: dict[str, str] = {"zile": str(days), "cif": str(cif)}
    if filter:
        params["filtru"] = filter.value

    auth_client = AnafAuthClient(
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
    client: AsyncOAuth2Client = auth_client.get_client()

    try:
        async for attempt in anaf_retrying(settings.retry, logger):
            with attempt:
                response: Response = await client.get(url=base_url, params=params)
                response.raise_for_status()
                response_data = response.json()
    except OAuth2Error as e:
        logger.error(f"OAuth2 token error — refresh token likely expired: {e}")
        raise TokenExpiredError(f"ANAF OAuth2 token is expired and cannot be refreshed: {e}") from e
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Invalid JSON response: {e}")
        raise AnafRequestError(f"Invalid JSON received from ANAF: {e}") from e
    except HTTPStatusError as e:
        logger.error(f"HTTP Error: {e.response.status_code} - {e.response.text}")
        raise AnafRequestError(f"HTTP Error {e.response.status_code}: {e.response.text}") from e
    except httpx.TimeoutException as e:
        logger.error(f"Request timed out: {e}")
        raise AnafRequestError("Request timed out while connecting to ANAF.") from e
    except httpx.NetworkError as e:
        logger.error(f"Network error: {e}")
        raise AnafRequestError("Network error occurred. Please check your internet connection.") from e
    except httpx.RequestError as e:
        logger.error(f"Request failed: {e}")
        raise AnafRequestError(f"An error occurred while making the request: {e}") from e

    if "eroare" in response_data:
        logger.error(f"Error: {response_data['eroare']}")
        raise AnafRequestError(f"ANAF API Error: {response_data['eroare']}")

    return response_data
