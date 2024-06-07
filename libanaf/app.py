import logging

import typer

from .auth import OAuthClient, authenticate
from .config import Configuration, setup_logging
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
    # authenticate()
    config = Configuration().load_config()
    client = OAuthClient(config["auth"]["client_id"], config["auth"]["client_secret"], config["auth"]["auth_url"], config["auth"]["token_url"], config["auth"]["redirect_uri"])
    token = client.get_access_token()
    logger.debug('token = %s' % token)

@app.command()
def invoice_list(
    zile: int = typer.Argument(default=60, help="Numărul de zile pentru care se face interogarea, format numeric, valorile acceptate de la 1 la 60"),
    cif: int = typer.Argument(default=19507820, help="CIF-ul (numeric) pentru care se doreste sa se obtina lista de mesaje disponibile"),
    filtru: Filter = typer.Option(default="P", help="Parametru folosit pentru filtrarea mesajelor. Valorile acceptate sunt: E, T, P, R")
) -> None:
    """Get the list of available invoices."""
    list_invoices(zile, cif, filtru)