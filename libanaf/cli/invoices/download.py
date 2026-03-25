"""CLI command for downloading invoices from the ANAF API."""

import logging
from typing import Annotated

import typer

from libanaf.invoices.download import download
from libanaf.types import Filter

logger = logging.getLogger(__name__)


def invoices_download(
    days: Annotated[
        int | None,
        typer.Argument(
            help="Numărul de zile pentru care se face interogarea, format numeric, valorile acceptate de la 1 la 60"
        ),
    ] = 30,
    cif: Annotated[
        int | None,
        typer.Argument(help="CIF-ul (numeric) pentru care se doreste sa se obtina lista de mesaje disponibile"),
    ] = 19507820,
    filter: Annotated[
        Filter | None,
        typer.Option(help="Parametru folosit pentru filtrarea mesajelor. Valorile acceptate sunt: E, T, P, R"),
    ] = Filter.P,
) -> None:
    """Download missing invoices and store them locally."""
    logger.info(f"Starting invoice download for the last {days} days for CIF: {cif} and filter {filter}")
    download(days, cif, filter)
