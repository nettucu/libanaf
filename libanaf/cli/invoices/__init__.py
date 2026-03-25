"""CLI commands for invoice management."""

import typer

from libanaf.cli.invoices import download, list, pdf_render, process, product_summary, show, summary

app = typer.Typer()

app.command(name="list")(list.invoices_list)
app.command(name="show")(show.show)
app.command(name="summary")(summary.summary)
app.command(name="prod-summary")(product_summary.prod_summary)
app.command(name="download")(download.invoices_download)
app.command(name="process")(process.invoices_process)
app.command(name="render-pdf")(pdf_render.render_pdf)
