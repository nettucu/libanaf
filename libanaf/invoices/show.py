"""Render and filter local UBL invoices/credit notes.

Provides helpers to list and display UBL `Invoice`/`CreditNote` documents
stored on disk, filter them by supplier, number and date range, and print
human-readable tables using Rich.
"""

import logging
from datetime import date
from pathlib import Path
from typing import cast
import re

import typer
from rich import box
from rich.console import Console
from rich.table import Table
from rich.pretty import pprint

from libanaf.config import Configuration
from libanaf.ubl.cac import Party, CreditNoteLine, InvoiceLine
from libanaf.ubl.credit_note import CreditNote
from libanaf.ubl.invoice import Invoice
from libanaf.ubl.ubl_document import parse_ubl_document

logger = logging.getLogger(__name__)
console = Console()


def show_invoices(
    invoice_number: str | None, supplier_name: str | None, start_date: str | None, end_date: str | None
) -> None:
    """Show invoices from local storage filtered by criteria.

    Args:
        invoice_number: Partial or full invoice number to search in XML `<cbc:ID>`.
        supplier_name: Partial or full supplier name to search in XML `<cbc:Name>`.
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

    config = Configuration().load_config()
    dlds_dir = Path(config["storage"]["download_directory"])

    # 2) Gather candidate files using pure Python scan (or fallback if only date range is used)
    candidate_files = gather_candidate_files(dlds_dir, invoice_number, supplier_name, start_date, end_date)
    logger.debug(f"Found {len(candidate_files)}")
    logger.debug(candidate_files)

    # 3) Parse and filter the candidate files (double-check date range, etc.)
    documents = parse_and_filter_documents(candidate_files, start_date, end_date)

    # 4) Display results
    # display_documents(documents)
    display_documents_pdf_style(documents)


def _compile_search_patterns(invoice_number: str | None, supplier_name: str | None) -> list[re.Pattern[str]]:
    """Compile case-insensitive regex patterns for XML content search.

    - For invoice number, matches inside `<cbc:ID> ... </cbc:ID>`.
    - For supplier name, matches inside `<cbc:Name> ... </cbc:Name>`.

    Args:
        invoice_number: Invoice number fragment to search.
        supplier_name: Supplier name fragment to search.

    Returns:
        list[re.Pattern[str]]: Compiled regex patterns to test XML text.
    """
    patterns: list[re.Pattern[str]] = []
    if invoice_number:
        inv_esc = re.escape(invoice_number)
        patterns.append(re.compile(rf"<cbc:ID>[^<]*{inv_esc}[^<]*</cbc:ID>", re.IGNORECASE))
    if supplier_name:
        sup_esc = re.escape(supplier_name)
        patterns.append(re.compile(rf"<cbc:Name>[^<]*{sup_esc}[^<]*</cbc:Name>", re.IGNORECASE))

    return patterns


def gather_candidate_files(
    dlds_dir: Path, invoice_number: str | None, supplier_name: str | None, start_date: str | None, end_date: str | None
) -> set[Path]:
    """Collect XML files that match text filters before parsing.

    If only date range is provided, returns all `.xml` files from `dlds_dir`
    to let downstream logic filter by dates.

    Args:
        dlds_dir: Directory containing downloaded XML documents.
        invoice_number: Invoice number fragment to search in `<cbc:ID>`.
        supplier_name: Supplier name fragment to search in `<cbc:Name>`.
        start_date: Inclusive start date (YYYY-MM-DD) if paired with `end_date`.
        end_date: Inclusive end date (YYYY-MM-DD) if paired with `start_date`.

    Returns:
        set[Path]: Candidate XML file paths matching text filters.
    """
    # If only date range provided, we need to parse documents to filter by date
    if (start_date and end_date) and not (invoice_number or supplier_name):
        return set(dlds_dir.glob("*.xml"))

    patterns = _compile_search_patterns(invoice_number, supplier_name)
    if not patterns:
        # No textual filters; return empty set so later logic can decide based on dates
        return set()

    candidate_files: set[Path] = set()
    for xml_path in dlds_dir.glob("*.xml"):
        try:
            # Read as text once; XML files are typically small. Use errors='ignore' for robustness.
            text = xml_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.debug(f"Skipping {xml_path}: read error: {e}")
            continue

        for pat in patterns:
            if pat.search(text):
                candidate_files.add(xml_path)
                break  # short-circuit on first match (OR semantics)

    return candidate_files


def parse_and_filter_documents(
    candidate_files: set[Path],
    start_date: date | None,
    end_date: date | None,
) -> list[Invoice | CreditNote]:  # or list of UBLDocument but we cast to Invoice below
    """Parse candidate files and filter documents by date.

    Args:
        candidate_files: Set of XML paths to parse as UBL Invoice/CreditNote.
        start_date: Keep docs with `issue_date >= start_date` when provided.
        end_date: Keep docs with `issue_date <= end_date` when provided.

    Returns:
        list[Invoice | CreditNote]: Parsed and filtered documents.
    """

    results: list[Invoice | CreditNote] = []
    for xml_file in sorted(candidate_files):
        try:
            doc = parse_ubl_document(xml_file)
        except Exception as e:
            logger.error(f"Skipping {xml_file}, parse error: {e}")
            continue

        # Only keep if it's an Invoice
        if not isinstance(doc, Invoice | CreditNote):
            continue

        # Filter by date range if both are given
        if start_date and doc.issue_date < start_date:
            continue
        if end_date and doc.issue_date > end_date:
            continue

        results.append(doc)

    return results


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
        table = Table(title=table_title, show_header=True, header_style="bold white on navy_blue", width=1200)

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
        width=200,
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

    for doc in docs:
        pprint(doc)

        display_header(doc)

        # 3) Create the table
        #    We'll define columns matching your PDF sample:
        #    # | Denumire | U.M. | Cant. | Pret fara TVA RON | Valoare RON | Valoare TVA RON
        table = Table(
            title="",
            box=box.HEAVY_HEAD,
            show_header=True,
            header_style="bold white",
            expand=False,
            show_lines=True,
            width=200,
        )

        table.add_column("#", justify="right", style="bold")
        table.add_column("Denumire", style="cyan", no_wrap=False)
        table.add_column("U.M.", justify="center")
        table.add_column("Cant.", justify="right")
        table.add_column("Pret fara TVA\n(RON)", justify="right")
        table.add_column("Valoare\n(RON)", justify="right")
        table.add_column("Valoare TVA\n(RON)", justify="right")

        # 4) Iterate line items
        if isinstance(doc, Invoice):
            lines = doc.invoice_line
            quantity_field = "invoiced_quantity"
            quantity_unit_code_field = "invoiced_quantity_unit_code"
        else:  # CreditNote
            lines = doc.credit_note_line
            quantity_field = "credited_quantity"
            quantity_unit_code_field = "credited_quantity_unit_code"

        line_number = 1
        for line in lines:
            # item name
            item_name = line.item.name
            # For the example PDF, they show "H87" for U.M. (unit measure).
            # Possibly line.item has that data or line.price/baseQuantity? We'll assume "H87" is in line.item?
            unit_code = getattr(line, quantity_unit_code_field, "H87")  # or from line.item or line.price?

            # quantity
            quantity_value = getattr(line, quantity_field, 0)
            quantity_str = f"{quantity_value:.2f}"

            # price without VAT => line.price.price_amount, presumably
            unit_price = line.price.price_amount  # This might be your "Pret fara TVA" # pyright: ignore
            price_str = f"{unit_price:.2f}"

            # Valoare (RON) => line.line_extension_amount? or quantity * unit_price
            # Typically UBL has line_extension_amount, so let's assume:
            value_no_vat = line.line_extension_amount
            value_str = f"{value_no_vat:.2f}"

            # Valoare TVA => in your sample, sometimes it's 0.00 or 19% of value
            # If you need the actual tax from the line, you might pull from line.classified_tax_category.percent
            # or from doc.tax_total, or any location you store the line's VAT. We'll default to 0.00 for now.
            # vat_value = 0.00  # or compute from your data
            vat_value = (
                line.item.classified_tax_category.percent
                if line.item.classified_tax_category is not None
                and line.item.classified_tax_category.percent is not None
                else 0.00
            )
            vat_value = value_no_vat * vat_value / 100
            vat_str = f"{vat_value:.2f}"

            table.add_row(str(line_number), item_name, unit_code, quantity_str, price_str, value_str, vat_str)
            line_number += 1

        # 5) Show a final "Total invoice" row or not
        #    The sample PDF shows something like "Total 28,571.97" at the bottom.
        #    We'll add a row with blank cells, except the last one with total.
        doc_total = doc.legal_monetary_total.payable_amount
        table.add_row("", "", "", "", "Total", f"{doc_total:.2f}", "")

        # 6) Print the table for this doc
        console.print(table)
