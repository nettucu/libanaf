import logging
from typing import Annotated

import typer

from libanaf.config import get_settings, setup_logging
from libanaf.invoices.app import app as invoices_app
from libanaf.cli.auth import auth as auth_command

app = typer.Typer()
app.add_typer(invoices_app, name="invoices", help="Manage invoices")
app.command()(auth_command)

logger = logging.getLogger()


@app.callback()
def main(
    ctx: typer.Context,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output")] = False,
) -> None:
    if ctx.resilient_parsing:
        return
    settings = get_settings()
    ctx.obj = settings
    setup_logging(verbose, settings)
    if verbose:
        logger.debug("Verbose mode enabled")


if __name__ == "__main__":
    app()
