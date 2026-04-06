"""CLI command for rendering invoices to PDF locally from UBL XML."""

import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from libanaf.config import get_settings
from libanaf.invoices.common import DateValidationError, ensure_date_range
from libanaf.invoices.pdf_render import render_invoice_pdf
from libanaf.invoices.query import collect_documents

logger = logging.getLogger(__name__)


def _open_pdf(path: Path, console: Console) -> None:
    """Open a PDF file with the desktop default viewer via xdg-open.

    Args:
        path: Path to the PDF file to open.
        console: Rich console for error output.
    """
    try:
        subprocess.run(["xdg-open", str(path)], check=True)
    except FileNotFoundError:
        console.print("[red]✗[/red] xdg-open not found — cannot open PDF.")
        logger.error("xdg-open not found")
    except subprocess.CalledProcessError as exc:
        console.print(f"[red]✗[/red] xdg-open failed for {path.name}: {exc}")
        logger.error("xdg-open failed for %s: %s", path, exc)


def _print_pdf(path: Path, printer: str | None, copies: int, console: Console) -> None:
    """Send a PDF file to a CUPS printer via lpr.

    Args:
        path: Path to the PDF file to print.
        printer: CUPS printer name. If ``None`` the system default is used.
        copies: Number of copies to print.
        console: Rich console for error output.
    """
    cmd = ["lpr"]
    if printer:
        cmd += ["-P", printer]
    if copies > 1:
        cmd += [f"-#{copies}"]
    cmd.append(str(path))

    try:
        subprocess.run(cmd, check=True)
        printer_label = printer or "default printer"
        console.print(f"🖨️  Sent to [cyan]{printer_label}[/cyan]: {path.name} ({copies} cop{'y' if copies == 1 else 'ies'})")
        logger.info("Printed %s to %s (%d copies)", path, printer_label, copies)
    except FileNotFoundError:
        console.print("[red]✗[/red] lpr not found — is CUPS installed?")
        logger.error("lpr not found")
    except subprocess.CalledProcessError as exc:
        console.print(f"[red]✗[/red] lpr failed for {path.name}: {exc}")
        logger.error("lpr failed for %s: %s", path, exc)


def render_pdf(
    invoice_number: Annotated[str | None, typer.Option("--invoice-number", "-i", help="Invoice Number")] = None,
    supplier_name: Annotated[str | None, typer.Option("--supplier-name", "-s", help="Supplier Name")] = None,
    start_date: Annotated[datetime | None, typer.Option("--start-date", "-sd", help="Start Date")] = None,
    end_date: Annotated[datetime | None, typer.Option("--end-date", "-ed", help="End Date")] = None,
    open_pdf: Annotated[bool, typer.Option("--open", help="Open each PDF with the default desktop viewer (xdg-open).")] = False,
    send_to_printer: Annotated[bool, typer.Option("--print", help="Send each PDF to a CUPS printer.")] = False,
    printer: Annotated[str | None, typer.Option("--printer", help="CUPS printer name. Defaults to the system default printer.")] = None,
    copies: Annotated[int, typer.Option("--copies", help="Number of copies to print (requires --print).", min=1)] = 1,
) -> None:
    """Generate PDF invoices locally from UBL XML files (no ANAF API call).

    Optionally open the result with --open or send it directly to a CUPS
    printer with --print [--printer NAME] [--copies N].
    """
    console = Console()

    if not any([invoice_number, supplier_name, (start_date and end_date)]):
        console.print(
            "❌ [bold red]Error: You must specify at least one filter, such as "
            "--invoice-number, --supplier-name, or both --start-date and --end-date.[/bold red]"
        )
        raise typer.Exit(code=1)

    try:
        start, end = ensure_date_range(start_date, end_date)
    except DateValidationError as exc:
        if exc.code == "both_required":
            console.print("❌ [bold red]Error: both --start-date and --end-date must be supplied together.[/bold red]")
        elif exc.code == "start_after_end":
            console.print("❌ [bold red]Error: --start-date must be before or equal to --end-date.[/bold red]")
        else:
            console.print("❌ [bold red]Error: invalid date range.[/bold red]")
        raise typer.Exit(code=1)

    settings = get_settings()
    dlds_dir = Path(settings.storage.download_dir).resolve()

    logger.info(
        "render-pdf: invoice_number=%s supplier_name=%s start=%s end=%s dir=%s open=%s print=%s printer=%s copies=%d",
        invoice_number,
        supplier_name,
        start,
        end,
        dlds_dir,
        open_pdf,
        send_to_printer,
        printer,
        copies,
    )

    documents = collect_documents(
        dlds_dir,
        invoice_number=invoice_number,
        supplier_name=supplier_name,
        start_date=start,
        end_date=end,
        allow_unfiltered=False,
    )

    if not documents:
        console.print("[yellow]No matching invoices or credit notes found.[/yellow]")
        return

    generated = 0
    skipped = 0
    ready_paths: list[Path] = []

    for doc in sorted(documents, key=lambda d: (d.issue_date, d.id)):
        try:
            fname = doc.tofname()
        except ValueError:
            fname = doc.id

        output_path = dlds_dir / f"{fname}_local.pdf"

        if output_path.exists():
            skipped += 1
            logger.debug("Skipping existing PDF: %s", output_path)
            ready_paths.append(output_path)
            continue

        try:
            render_invoice_pdf(doc, output_path)
            generated += 1
            console.print(f"[green]✓[/green] Generated: [cyan]{output_path.name}[/cyan]")
            ready_paths.append(output_path)
        except Exception as exc:
            console.print(f"[red]✗[/red] Failed to render {doc.id}: {exc}")
            logger.error("Failed to render PDF for %s: %s", doc.id, exc, exc_info=exc)

    console.print(f"\n[bold]Summary:[/bold] {generated} generated, {skipped} skipped (already exist).")

    for path in ready_paths:
        if open_pdf:
            _open_pdf(path, console)
        if send_to_printer:
            _print_pdf(path, printer, copies, console)
