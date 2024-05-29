import logging

import typer

from .auth import authenticate
from .config import setup_logging
from .list_invoices import list_invoices
from .types import Filter

app = typer.Typer()

logger = logging.getLogger()

@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
) -> None:
    setup_logging(verbose)
    if verbose:
        logger.debug("Verbose mode enabled")

@app.command()
def auth() -> None:
    """Authenticate to ANAF portal and retrieve tokens."""
    authenticate()

@app.command()
def invoice_list(
    zile: int = typer.Argument(default=60, help="Numărul de zile pentru care se face interogarea, format numeric, valorile acceptate de la 1 la 60"),
    cif: int = typer.Argument(default=19507820, help="CIF-ul (numeric) pentru care se doreste sa se obtina lista de mesaje disponibile"),
    filtru: Filter = typer.Option(default="P", help="Parametru folosit pentru filtrarea mesajelor. Valorile acceptate sunt: E, T, P, R")
) -> None:
    """Get the list of available invoices."""
    list_invoices(zile, cif, filtru)