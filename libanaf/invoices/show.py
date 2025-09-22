"""Render and filter local UBL invoices/credit notes.

Provides helpers to list and display UBL `Invoice`/`CreditNote` documents
stored on disk, filter them by supplier, number and date range, and print
human-readable tables using Rich.
"""

import logging
from datetime import date, datetime
from typing import cast

import typer
from rich import box
from rich.console import Console, Group
from rich.table import Table
from rich.columns import Columns
from rich.panel import Panel
from rich.text import Text
from rich.align import Align

from ..config import get_config, AppConfig
from .query import gather_candidate_files, parse_and_filter_documents
from ..ubl.cac import Party, CreditNoteLine, InvoiceLine
from ..ubl.credit_note import CreditNote
from ..ubl.invoice import Invoice

logger = logging.getLogger(__name__)
console = Console()


def _coerce_to_date(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def show_invoices(
    invoice_number: str | None,
    supplier_name: str | None,
    start_date: date | datetime | None,
    end_date: date | datetime | None,
) -> None:
    """Show invoices from local storage filtered by criteria.

    Args:
        invoice_number: Partial or full invoice number to search in XML `<cbc:ID>`.
        supplier_name: Partial or full supplier name to search in XML `<cbc:Name|RegistrationName>`.
        start_date: Inclusive start date (YYYY-MM-DD) when combined with `end_date`.
        end_date: Inclusive end date (YYYY-MM-DD) when combined with `start_date`.

    Raises:
        typer.Exit: If no filters are provided.
    """
    logger.debug(
        f"show_invoices: invoice_number={invoice_number}, supplier_name={supplier_name}, start_date={start_date}, end_date={end_date}"
    )
    # 1) Validate at least one filter
    if not any([invoice_number, supplier_name, (start_date and end_date)]):
        console.print(
            "[bold red]Error: You must specify at least one filter, such as --invoice-number, --supplier-name, or both --start-date and --end-date.[/bold red]"
        )
        raise typer.Exit(code=1)

    start_date_obj = _coerce_to_date(start_date)
    end_date_obj = _coerce_to_date(end_date)

    config: AppConfig = get_config()
    dlds_dir = config.storage.download_dir

    # 2) Gather candidate files using pure Python scan (or fallback if only date range is used)
    candidate_files = gather_candidate_files(dlds_dir, invoice_number, supplier_name, start_date_obj, end_date_obj)
    logger.debug(f"Found {len(candidate_files)}")
    logger.debug(candidate_files)

    # 3) Parse and filter the candidate files (double-check date range, etc.)
    documents = parse_and_filter_documents(candidate_files, start_date_obj, end_date_obj)

    # 4) Display results
    # display_documents(documents)
    display_documents_pdf_style(documents)


def display_documents(docs: list[Invoice | CreditNote]) -> None:
    """Render a simple Rich table for each document.

    Shows supplier name, document ID/date, and line items with quantity and
    price. Intended as a compact, console-friendly view.

    Args:
        docs: Parsed `Invoice` or `CreditNote` instances to display.
    """
    if not docs:
        console.print("[bold red]No matching invoices/credit notes found.[/bold red]")
        return

    for doc in docs:
        # 1) Extract top-level info
        #    doc.accounting_supplier_party.party -> either has party_name or party_legal_entity
        party = doc.accounting_supplier_party.party
        if party.party_name and party.party_name.name:
            supplier_name = party.party_name.name
        elif party.party_legal_entity and party.party_legal_entity.registration_name:
            supplier_name = party.party_legal_entity.registration_name
        else:
            supplier_name = "Unknown"

        doc_id = doc.id
        issue_date_str = str(doc.issue_date)

        # 2) Build the Rich table for this document
        #    The title can have multiple lines by using \n
        table_title = f"{supplier_name}\n{doc_id}\n{issue_date_str}"
        table = Table(
            title=table_title,
            show_header=True,
            header_style="bold white on navy_blue",
            width=1200,
        )

        # 3) Add columns for item details
        table.add_column("Item Name", justify="left", style="cyan", no_wrap=True)
        table.add_column("Quantity", justify="right", style="green")
        table.add_column("Price", justify="right", style="magenta")

        # 4) Get line items, which differ for Invoice vs. CreditNote
        if isinstance(doc, Invoice):
            line_items = doc.invoice_line
            # quantity -> line.invoiced_quantity
        elif isinstance(doc, CreditNote):
            line_items = doc.credit_note_line
            # quantity -> line.credited_quantity
        else:
            raise ValueError(f"Unknown document type: {doc}")

        for line in line_items:
            item_name = line.item.name
            # Depending on doc type, quantity field differs
            if isinstance(doc, Invoice):
                line = cast(InvoiceLine, line)
                quantity_str = str(line.invoiced_quantity)
            else:
                line = cast(CreditNoteLine, line)
                quantity_str = str(line.credited_quantity)

            price_str = f"{line.price.price_amount:.2f}"  # pyright: ignore

            table.add_row(item_name, quantity_str, price_str)

        # 5) Print the table for this doc
        console.print(table)


def get_supplier_str(party: Party) -> str:
    """Format party information for display.

    Args:
        party: The `Party` object to format.

    Returns:
        str: A single, formatted string suitable for headers.
    """
    formatted, *_ = party.get_display_str().values()

    return formatted


def display_header(doc: Invoice | CreditNote) -> None:
    """Print a header section for a document using Rich.

    Includes supplier/customer information, document ID/date and due date
    along with payment means, mimicking a PDF-style header.

    Args:
        doc: The `Invoice` or `CreditNote` to describe.
    """
    # 1) Gather or compute top-level info
    # doc_type = doc.__class__.__name__  # "Invoice" or "CreditNote"
    doc_id: str = doc.id
    doc_date: date = doc.issue_date  # a datetime.date
    due_date: date | None = doc.due_date  # might be None if not set

    # For the supplier name & address:
    supplier_party: Party = doc.accounting_supplier_party.party
    supplier = get_supplier_str(supplier_party)

    payment_means = ""
    if doc.payment_means:
        for p in doc.payment_means:
            formatted = p.get_display_str()["formatted"]
            payment_means = f"{payment_means}{formatted}\n"
    else:
        payment_means = ""

    # For the customer name & address, similar
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

    # GURSK MEDICA SRL
    # CIF: RO25629635
    # Reg. com.: J23/1344/2012
    # Adresa: INTR. VLASCEANU DUMITRU, Voluntari
    # Judet: Ilfov
    # IBAN: RO51BACX0000000363717001
    # Banca: UNICREDIT BANK SA

    header_table.add_row(f"{supplier}{payment_means}", customer)

    console.print(header_table)


# ------------------------------
# Formatting helpers and renderer
# ------------------------------


def _format_money(value: float | None, currency: str | None) -> str:
    """Format money using English number formatting (1,234.56)."""
    if value is None:
        return ""
    cur = currency or "RON"
    return f"{value:,.2f} {cur}"


def _format_qty(value: float | int | None) -> str:
    if value is None:
        return ""
    return f"{float(value):,.2f}"


def _format_percent(value: float | None) -> str:
    if value is None:
        return "0%"
    return f"{value:.0f}%"


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

    # ---------- high level ----------
    def render(self, doc: Invoice | CreditNote) -> None:
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

    # ---------- builders ----------
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
        supplier_text = Text(doc.accounting_supplier_party.party.get_display_str()["formatted"])  # name, cif, address

        # PLATA under Furnizor
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

    # Detalii Document section removed per request
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

            # Prefer explicit line AllowanceCharge discounts if present; fallback to implied
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

            # VAT percent and value
            percent = (
                line.item.classified_tax_category.percent
                if line.item.classified_tax_category and line.item.classified_tax_category.percent is not None
                else 0.0
            )
            vat_value = base_value * (percent / 100.0)

            # Credit notes shown as negatives
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
                _format_money(unit_price, currency),
                _format_money(base_value, currency),
                _format_money(discount_value if discount_value != 0 else 0.0, currency),
                _format_money(vat_value, currency),
            )

        return table

    def _build_vat_summary(self, doc: Invoice | CreditNote) -> Panel | None:
        if isinstance(doc, Invoice):
            lines = doc.invoice_line
        else:
            lines = doc.credit_note_line

        # Group by percent
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
                _format_percent(p),
                _format_money(base, currency),
                _format_money(vat, currency),
            )

        t.add_row("", "", "")
        t.add_row(
            "Total",
            _format_money(total_base, currency),
            _format_money(total_vat, currency),
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
        # Prefer explicit document-level AllowanceCharge list if present
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
                    Text(_format_money(value, cur), style="bold"),
                )
            else:
                t.add_row(label, _format_money(value, cur))

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


def display_documents_pdf_style(docs: list[Invoice | CreditNote]) -> None:
    """Render each document as a PDF-like multi-section table.

    Produces a header and a detailed line-item table similar to an invoice
    PDF, including quantities, unit prices, values and VAT calculation.

    Args:
        docs: Parsed `Invoice` or `CreditNote` instances to display.
    """
    if not docs:
        console.print("[bold red]No matching documents found.[/bold red]")
        return

    renderer = InvoiceRenderer(console)
    for doc in docs:
        renderer.render(doc)
