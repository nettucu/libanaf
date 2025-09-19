import logging

import typer
from typing import Annotated

from .auth import LibANAF_AuthClient
from .comms import make_auth_client
from .config import Configuration
from .invoices.app import app as invoices_app

app = typer.Typer()
app.add_typer(invoices_app, name="invoices")

logger = logging.getLogger()


@app.callback()
def main(
    ctx: typer.Context,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output")] = False,
) -> None:
    typer.echo("Starting the application ...")
    config = Configuration().setup()
    config.setup_logging(verbose)
    if verbose:
        logger.debug("Verbose mode enabled")


@app.command()
def auth() -> None:
    """Authenticate to ANAF portal and retrieve tokens."""
    auth_client: LibANAF_AuthClient = make_auth_client()
    token = auth_client.get_access_token()
    logger.debug(f"token = {token}")


if __name__ == "__main__":
    app()
