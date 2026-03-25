"""CLI command for showing individual invoices/credit notes with Rich rendering."""

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, cast

import typer
from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from libanaf.config import get_settings
from libanaf.invoices.common import DateValidationError, ensure_date_range, format_money, format_percent
from libanaf.invoices.query import collect_documents
from libanaf.ubl.cac import CreditNoteLine, InvoiceLine, Party
from libanaf.ubl.credit_note import CreditNote
from libanaf.ubl.invoice import Invoice

logger = logging.getLogger(__name__)
console = Console()


def show(
    invoice_number: Annotated[str | None, typer.Option("--invoice-number", "-i", help="Invoice Number")] = None,
    supplier_name: Annotated[str | None, typer.Option("--supplier-name", "-s", help="Supplier Name")] = None,
    start_date: Annotated[datetime | None, typer.Option("--start-date", "-sd", help="Start Date")] = None,
    end_date: Annotated[datetime | None, typer.Option("--end-date", "-ed", help="End Date")] = None,
) -> None:
    """Show all matching invoices. Filtering options:
    - partial invoice_number
    - partial supplier_name
    - start_date / end_date in yyyy-mm-dd format
    (At least one of these filters is required.)
    """
    typer.echo(
        f"Starting show_invoices with params: invoice_number={invoice_number}, supplier_name={supplier_name}, "
        f"start_date={start_date}, end_date={end_date}"
    )

    if not any([invoice_number, supplier_name, (start_date and end_date)]):
        console.print(
            "❌ [bold red]Error: You must specify at least one filter, such as --invoice-number, "
            "--supplier-name, or both --start-date and --end-date.[/bold red]"
        )
        raise typer.Exit(code=1)

    try:
        start, end = ensure_date_range(start_date, end_date)
    except DateValidationError as exc:
        if exc.code == "both_required":
            console.print("❌ [bold red]Error: both --start-date and --end-date must be supplied together.[/bold red]")
        elif exc.code == "start_after_end":
            console.print("❌ [bold red]Error: --start-date must be before or equal to --end-date.[/bold red]")
        else:  # pragma: no cover - defensive branch
            console.print("❌ [bold red]Error: invalid date range.[/bold red]")
        raise typer.Exit(code=1)

    settings = get_settings()
    search_dir = Path(settings.storage.download_dir).resolve()
    logger.debug(f"show collect_documents: dir={search_dir}")

    documents = collect_documents(
        search_dir,
        invoice_number=invoice_number,
        supplier_name=supplier_name,
        start_date=start,
        end_date=end,
        allow_unfiltered=False,
    )

    if not documents:
        console.print("[yellow]No matching invoices or credit notes found.[/yellow]")
        return

    logger.debug(f"show collect_documents: parsed {len(documents)} documents")
    display_documents_pdf_style(documents)


def get_supplier_str(party: Party) -> str:
    """Format party information for display.

    Args:
        party: The ``Party`` object to format.

    Returns:
        str: A single, formatted string suitable for headers.
    """
    formatted, *_ = party.get_display_str().values()
    return formatted


def display_header(doc: Invoice | CreditNote) -> None:
    """Print a header section for a document using Rich.

    Args:
        doc: The ``Invoice`` or ``CreditNote`` to describe.
    """
    doc_id: str = doc.id
    doc_date: date = doc.issue_date
    due_date: date | None = doc.due_date

    supplier_party: Party = doc.accounting_supplier_party.party
    supplier = get_supplier_str(supplier_party)

    payment_means = ""
    if doc.payment_means:
        for p in doc.payment_means:
            formatted = p.get_display_str()["formatted"]
            payment_means = f"{payment_means}{formatted}\n"

    customer_party: Party = doc.accounting_customer_party.party
    customer = get_supplier_str(customer_party)

    due_date_str = due_date.strftime("%d/%m/%Y") if due_date is not None else "N/A"
    header_table = Table(
        title=f"FACTURA {doc_id} din {doc_date.strftime('%d/%m/%Y')} [right] Termen de plata: {due_date_str}[/right]",
        show_header=True,
        expand=True,
        header_style="bold white on navy_blue",
    )
    header_table.add_column("[bold]FURNIZOR[/bold]", justify="left")
    header_table.add_column("CLIENT", justify="left")
    header_table.add_row(f"{supplier}{payment_means}", customer)
    console.print(header_table)


def display_documents(docs: list[Invoice | CreditNote]) -> None:
    """Render a simple Rich table for each document.

    Args:
        docs: Parsed ``Invoice`` or ``CreditNote`` instances to display.
    """
    if not docs:
        console.print("[bold red]No matching invoices/credit notes found.[/bold red]")
        return

    for doc in docs:
        party = doc.accounting_supplier_party.party
        if party.party_name and party.party_name.name:
            supplier_name = party.party_name.name
        elif party.party_legal_entity and party.party_legal_entity.registration_name:
            supplier_name = party.party_legal_entity.registration_name
        else:
            supplier_name = "Unknown"

        doc_id = doc.id
        issue_date_str = str(doc.issue_date)

        table_title = f"{supplier_name}\n{doc_id}\n{issue_date_str}"
        table = Table(
            title=table_title,
            show_header=True,
            header_style="bold white on navy_blue",
            width=1200,
        )
        table.add_column("Item Name", justify="left", style="cyan", no_wrap=True)
        table.add_column("Quantity", justify="right", style="green")
        table.add_column("Price", justify="right", style="magenta")

        if isinstance(doc, Invoice):
            line_items = doc.invoice_line
        elif isinstance(doc, CreditNote):
            line_items = doc.credit_note_line
        else:
            raise ValueError(f"Unknown document type: {doc}")

        for line in line_items:
            item_name = line.item.name
            if isinstance(doc, Invoice):
                line = cast(InvoiceLine, line)
                quantity_str = str(line.invoiced_quantity)
            else:
                line = cast(CreditNoteLine, line)
                quantity_str = str(line.credited_quantity)

            price_str = f"{line.price.price_amount:.2f}"  # pyright: ignore

            table.add_row(item_name, quantity_str, price_str)

        console.print(table)


def display_documents_pdf_style(docs: list[Invoice | CreditNote]) -> None:
    """Render each document as a PDF-like multi-section table.

    Args:
        docs: Parsed ``Invoice`` or ``CreditNote`` instances to display.
    """
    if not docs:
        console.print("[bold red]No matching documents found.[/bold red]")
        return

    renderer = InvoiceRenderer(console)
    for doc in docs:
        renderer.render(doc)


def _format_qty(value: float | int | None) -> str:
    if value is None:
        return ""
    return f"{float(value):,.2f}"


class InvoiceRenderer:
    """Render Invoice/CreditNote to a PDF-like Rich layout.

    - Uses Romanian labels
    - English numeric formatting (1,234.56)
    - CreditNotes are shown with negative values
    - Shows VAT per line, VAT summary by rate, totals and payment info
    - Shows document-level discounts/charges if present in LegalMonetaryTotal
    """

    def __init__(self, console: Console) -> None:
        self.console = console

    def render(self, doc: Invoice | CreditNote) -> None:
        """Render a single invoice or credit note to the console.

        Args:
            doc: The document to render.
        """
        title = self._build_title(doc)
        header_row = self._build_header_row(doc)
        lines_table = self._build_lines_table(doc)
        vat_summary = self._build_vat_summary(doc)
        totals = self._build_totals_panel(doc)
        footer = self._build_footer(doc)

        self.console.print(title)
        self.console.print(header_row)
        self.console.print(lines_table)
        if vat_summary is not None:
            self.console.print(Align.right(vat_summary))
        self.console.print(Align.right(totals))
        if footer is not None:
            self.console.print(footer)

    def _build_title(self, doc: Invoice | CreditNote) -> Panel:
        is_credit = isinstance(doc, CreditNote)
        doc_type = "NOTA DE CREDIT" if is_credit else "FACTURA"
        right = Text()
        if doc.due_date:
            right.append(f"Termen de plata: {doc.due_date.strftime('%d/%m/%Y')}")
        currency = getattr(doc, "document_currency_code", None) or "RON"
        left = Text(
            f"{doc_type} {doc.id} din {doc.issue_date.strftime('%d/%m/%Y')}  [ {currency} ]",
            style="bold",
        )
        content = Columns([left, Text(""), right], equal=False, expand=True)
        return Panel(content, title=doc_type, title_align="left", padding=(1, 2))

    def _build_header_row(self, doc: Invoice | CreditNote) -> Columns:
        """Build the top row with Furnizor (including PLATA underneath), Invoice details, and Client."""
        supplier_panel = self._build_supplier_panel(doc)
        details_panel = self._build_invoice_details_panel(doc)
        client_panel = self._party_panel(doc.accounting_customer_party.party, title="CLIENT")
        return Columns([supplier_panel, details_panel, client_panel], expand=True, equal=True)

    def _build_supplier_panel(self, doc: Invoice | CreditNote) -> Panel:
        supplier_text = Text(doc.accounting_supplier_party.party.get_display_str()["formatted"])

        payments_group = None
        if doc.payment_means:
            payments_text = Text()
            for pm in doc.payment_means:
                pm_str = pm.get_display_str()["formatted"]
                if pm_str and pm_str != "N/A":
                    payments_text.append(pm_str + "\n")
            if str(payments_text).strip():
                payments_group = Panel(payments_text, title="PLATA", padding=(0, 1))

        content = Group(supplier_text, payments_group) if payments_group else Group(supplier_text)
        return Panel(content, title="FURNIZOR", padding=(0, 1))

    def _build_invoice_details_panel(self, doc: Invoice | CreditNote) -> Panel:
        """Build the central panel with invoice metadata: number, dates, order ref."""
        t = Table(box=box.SIMPLE, show_header=False, expand=True, padding=(0, 0))
        t.add_column("", style="bold")
        t.add_column("")
        t.add_row("Nr. factura", str(doc.id))
        t.add_row("Data emiterii", doc.issue_date.strftime("%d/%m/%Y"))
        t.add_row("Scadenta", doc.due_date.strftime("%d/%m/%Y") if doc.due_date else "-")
        if doc.order_reference and doc.order_reference.id:
            t.add_row("Nr. comanda", str(doc.order_reference.id))
        return Panel(t, title="DETALII FACTURA", padding=(0, 1))

    def _party_panel(self, party: Party, title: str) -> Panel:
        text = party.get_display_str()["formatted"]
        return Panel(Text(text), title=title, padding=(0, 1))

    def _build_doc_meta(self, doc: Invoice | CreditNote) -> Panel | None:  # noqa: D401
        return None

    def _build_lines_table(self, doc: Invoice | CreditNote) -> Table:
        currency = getattr(doc, "document_currency_code", None) or "RON"
        is_credit = isinstance(doc, CreditNote)

        table = Table(
            title="",
            box=box.HEAVY_HEAD,
            show_header=True,
            header_style="bold white",
            expand=True,
            show_lines=False,
        )
        table.add_column("#", justify="right", style="bold", no_wrap=True)
        table.add_column("Denumire", style="cyan")
        table.add_column("U.M.", justify="center", no_wrap=True)
        table.add_column("Cant.", justify="right", no_wrap=True)
        table.add_column("Pret unitar (fara TVA)", justify="right", no_wrap=True)
        table.add_column("Valoare (fara TVA)", justify="right", no_wrap=True)
        table.add_column("Reducere", justify="right", no_wrap=True)
        table.add_column("Valoare TVA", justify="right", no_wrap=True)

        if isinstance(doc, Invoice):
            lines = doc.invoice_line
            qty_field = "invoiced_quantity"
            unit_field = "invoiced_quantity_unit_code"
        else:
            lines = doc.credit_note_line
            qty_field = "credited_quantity"
            unit_field = "credited_quantity_unit_code"

        for idx, line in enumerate(lines, start=1):
            name = line.item.name
            unit_code = (
                getattr(line, unit_field, None) or (line.price.base_quantity_unit_code if line.price else None) or "H87"
            )
            qty = getattr(line, qty_field, 0.0) or 0.0
            unit_price = (line.price.price_amount if line.price else None) or 0.0
            base_value = line.line_extension_amount or 0.0

            discount_value = 0.0
            try:
                if getattr(line, "allowance_charge", None):
                    for ac in line.allowance_charge:  # type: ignore[attr-defined]
                        if ac and ac.charge_indicator is False and ac.amount is not None:
                            discount_value += float(ac.amount)
            except Exception:
                discount_value = 0.0

            if discount_value == 0.0:
                implied_discount = (qty * unit_price) - base_value
                if abs(implied_discount) >= 0.005:
                    discount_value = implied_discount

            percent = (
                line.item.classified_tax_category.percent
                if line.item.classified_tax_category and line.item.classified_tax_category.percent is not None
                else 0.0
            )
            vat_value = base_value * (percent / 100.0)

            sign = -1.0 if is_credit else 1.0
            qty *= sign
            unit_price *= sign
            base_value *= sign
            vat_value *= sign
            discount_value *= sign

            table.add_row(
                str(idx),
                name,
                str(unit_code),
                _format_qty(qty),
                format_money(unit_price, currency),
                format_money(base_value, currency),
                format_money(discount_value if discount_value != 0 else 0.0, currency),
                format_money(vat_value, currency),
            )

        return table

    def _build_vat_summary(self, doc: Invoice | CreditNote) -> Panel | None:
        if isinstance(doc, Invoice):
            lines = doc.invoice_line
        else:
            lines = doc.credit_note_line

        groups: dict[float, dict[str, float]] = {}
        for line in lines:
            percent = (
                line.item.classified_tax_category.percent
                if line.item.classified_tax_category and line.item.classified_tax_category.percent is not None
                else 0.0
            )
            base = line.line_extension_amount or 0.0
            vat = base * (percent / 100.0)
            d = groups.setdefault(percent, {"base": 0.0, "vat": 0.0})
            d["base"] += base
            d["vat"] += vat

        if not groups:
            return None

        currency = getattr(doc, "document_currency_code", None) or "RON"
        is_credit = isinstance(doc, CreditNote)
        sign = -1.0 if is_credit else 1.0

        t = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold", expand=False)
        t.add_column("Cota TVA", justify="right")
        t.add_column("Baza", justify="right")
        t.add_column("TVA", justify="right")

        total_base = 0.0
        total_vat = 0.0
        for p in sorted(groups.keys()):
            base = groups[p]["base"] * sign
            vat = groups[p]["vat"] * sign
            total_base += base
            total_vat += vat
            t.add_row(
                format_percent(p),
                format_money(base, currency),
                format_money(vat, currency),
            )

        t.add_row("", "", "")
        t.add_row(
            "Total",
            format_money(total_base, currency),
            format_money(total_vat, currency),
        )
        return Panel(t, title="Rezumat TVA", padding=(0, 1))

    def _build_totals_panel(self, doc: Invoice | CreditNote) -> Panel:
        cur = getattr(doc, "document_currency_code", None) or "RON"
        is_credit = isinstance(doc, CreditNote)
        sign = -1.0 if is_credit else 1.0

        lmt = doc.legal_monetary_total
        tax_total = getattr(doc, "tax_total", None)
        tax_amount = tax_total.tax_amount if tax_total else None

        rows: list[tuple[str, float | None]] = []
        rows.append(("Total fara TVA", (lmt.tax_exclusive_amount or 0.0) * sign))
        if tax_amount is not None:
            rows.append(("Total TVA", (tax_amount or 0.0) * sign))
        if lmt.tax_inclusive_amount and abs(lmt.tax_inclusive_amount) > 0.0:
            rows.append(("Total cu TVA", (lmt.tax_inclusive_amount or 0.0) * sign))

        doc_discount = None
        doc_charge = None
        try:
            if getattr(doc, "allowance_charge", None):
                dsum = 0.0
                csum = 0.0
                for ac in doc.allowance_charge:  # type: ignore[attr-defined]
                    if not ac or ac.amount is None:
                        continue
                    if ac.charge_indicator is False:
                        dsum += float(ac.amount)
                    else:
                        csum += float(ac.amount)
                doc_discount = dsum if dsum != 0.0 else None
                doc_charge = csum if csum != 0.0 else None
        except Exception:
            doc_discount = None
            doc_charge = None

        if doc_discount is not None:
            rows.append(("Reduceri (document)", (doc_discount or 0.0) * sign * -1))
        elif lmt.allowance_total_amount and abs(lmt.allowance_total_amount) > 0.0001:
            rows.append(("Reduceri (document)", (lmt.allowance_total_amount or 0.0) * sign * -1))

        if doc_charge is not None:
            rows.append(("Majorari (document)", (doc_charge or 0.0) * sign))
        elif lmt.charge_total_amount and abs(lmt.charge_total_amount) > 0.0001:
            rows.append(("Majorari (document)", (lmt.charge_total_amount or 0.0) * sign))
        if lmt.prepaid_amount and abs(lmt.prepaid_amount) > 0.0001:
            rows.append(("Avansuri", (lmt.prepaid_amount or 0.0) * sign * -1))
        if lmt.payable_rounding_amount and abs(lmt.payable_rounding_amount) > 0.0001:
            rows.append(("Rotunjire", (lmt.payable_rounding_amount or 0.0) * sign))

        rows.append(("Total de plata", (lmt.payable_amount or 0.0) * sign))

        t = Table(box=box.SIMPLE_HEAVY, show_header=False, expand=False)
        t.add_column("", justify="left", style="bold")
        t.add_column("", justify="right")
        for label, value in rows:
            if label == "Total de plata":
                t.add_row(
                    Text(label, style="bold white on dark_green"),
                    Text(format_money(value, cur), style="bold"),
                )
            else:
                t.add_row(label, format_money(value, cur))

        return Panel(t, title="Totaluri", padding=(0, 1))

    def _build_footer(self, doc: Invoice | CreditNote) -> Panel | None:
        """Show Note only if there are additional notes; ignore attachments here."""
        items: list[str] = []
        if doc.note:
            for n in doc.note:
                if n and str(n).strip():
                    items.append(n)

        if not items:
            return None

        txt = Text("\n".join(items))
        return Panel(txt, title="Note", padding=(0, 1))
