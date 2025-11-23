"""Produce a product-level summary for invoices and credit notes.

The feature aggregates every invoice line (or credit note line) that matches
the supplied filters, allocates document-level discounts across lines, and
renders the results in a Rich table ready for CLI output.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ..config import AppConfig, get_config
from ..types import UNIT_CODES
from ..ubl.cac import AllowanceCharge, CreditNoteLine, InvoiceLine
from ..ubl.credit_note import CreditNote
from ..ubl.invoice import Invoice
from .common import (
    DateValidationError,
    ensure_date_range,
    extract_supplier_name,
    format_currency,
)
from .query import collect_documents

logger = logging.getLogger(__name__)

CURRENCY_QUANT = Decimal("0.01")
DEFAULT_CONSOLE = Console()


@dataclass(frozen=True, slots=True)
class ProductSummaryRow:
    """Aggregated information for a single invoice or credit-note line."""

    company_id: str
    supplier: str
    document_number: str
    invoice_date: date
    currency: str
    total_invoice: Decimal
    total_payable: Decimal
    product: str
    product_code: str | None
    quantity: Decimal
    unit_of_measure: str | None
    unit_price: Decimal | None
    value: Decimal
    vat_rate: Decimal
    vat_value: Decimal
    discount_rate: Decimal
    discount_value: Decimal
    total_per_line: Decimal


def summarize_products(
    invoice_number: str | None,
    supplier_name: str | None,
    start_date: date | datetime | None,
    end_date: date | datetime | None,
    render_output: bool = True,
    *,
    config: AppConfig | None = None,
    output: Console | None = None,
) -> list[ProductSummaryRow] | None:
    """Render a Rich table with product-level figures for matching documents."""

    product_console = output or DEFAULT_CONSOLE

    try:
        start, end = ensure_date_range(start_date, end_date)
    except DateValidationError as exc:
        if exc.code == "both_required":
            product_console.print(
                "❌ [bold red]Error: both --start-date and --end-date must be supplied together.[/bold red]"
            )
        elif exc.code == "start_after_end":
            product_console.print("❌ [bold red]Error: --start-date must be before or equal to --end-date.[/bold red]")
        else:  # pragma: no cover - defensive branch
            product_console.print("❌ [bold red]Error: invalid date range.[/bold red]")
        raise typer.Exit(code=1)

    app_config = config or get_config()
    dlds_dir = app_config.storage.download_dir
    logger.debug(
        f"product-summary: collect_documents: dir {dlds_dir} "
        f"invoice_number={invoice_number} supplier_name={supplier_name} start={start} end={end}"
    )

    search_dir = Path(dlds_dir).resolve()
    documents = collect_documents(
        search_dir,
        invoice_number=invoice_number,
        supplier_name=supplier_name,
        start_date=start,
        end_date=end,
        allow_unfiltered=True,
    )

    if not documents:
        product_console.print("[yellow]No matching invoices or credit notes found.[/yellow]")
        return None

    logger.debug(f"product-summary collect_documents: parsed {len(documents)} documents")

    rows = build_product_summary_rows(documents)
    if render_output:
        render_product_summary(rows, console=product_console)

    return rows


def build_product_summary_rows(documents: Sequence[Invoice | CreditNote]) -> list[ProductSummaryRow]:
    """Transform parsed documents into product-level summary rows."""

    rows: list[ProductSummaryRow] = []
    for document in documents:
        rows.extend(_build_rows_for_document(document))

    return rows


def render_product_summary(rows: Iterable[ProductSummaryRow], *, console: Console | None = None) -> None:
    """Render the product summary rows using Rich."""

    target_console = console or DEFAULT_CONSOLE

    table = Table(
        show_header=True,
        header_style="bold white on navy_blue",
        title="Invoice Product Summary",
    )
    table.add_column("Supplier", style="green")
    table.add_column("Invoice Number", style="cyan")
    table.add_column("Date", justify="center")
    table.add_column("Total (Invoice)", justify="right", style="blue")
    table.add_column("Total Value (Payable)", justify="right", style="green")
    table.add_column("Product", style="white")
    table.add_column("Product Code", style="white")
    table.add_column("Quantity", justify="right", style="yellow")
    table.add_column("U.M.", style="yellow")
    table.add_column("Price", justify="right", style="white")
    table.add_column("Value", justify="right", style="white")
    table.add_column("VAT Rate", justify="right", style="white")
    table.add_column("VAT Value", justify="right", style="white")
    table.add_column("Discount Rate", justify="right", style="white")
    table.add_column("Discount Value", justify="right", style="white")
    table.add_column("Total Per Line", justify="right", style="magenta")

    for row in rows:
        table.add_row(
            row.supplier,
            row.document_number,
            row.invoice_date.isoformat(),
            format_currency(row.total_invoice, row.currency),
            format_currency(row.total_payable, row.currency),
            row.product,
            row.product_code or "-",
            _format_quantity(row.quantity),
            _format_unit(row.unit_of_measure),
            _format_price(row.unit_price, row.currency),
            format_currency(row.value, row.currency),
            f"{row.vat_rate:.2f}",
            format_currency(row.vat_value, row.currency),
            f"{abs(row.discount_rate):.2f}%",
            format_currency(abs(row.discount_value), row.currency),
            format_currency(row.total_per_line, row.currency),
        )

    target_console.print(table)


def _build_rows_for_document(document: Invoice | CreditNote) -> list[ProductSummaryRow]:
    """
    Builds a list of `ProductSummaryRow` instances for a given document,
    accurately calculating line totals from an inventory manager's perspective.

    This involves a multi-step process:
    1.  Calculate line-item values (`Value`, `Discount Value`, `Taxable Amount`)
        based on explicit line-level data only. Special logic is applied to
        handle discounts on credit lines correctly.
    2.  Sum the initial line calculations and compare them to the document's
        header totals (`TaxInclusiveAmount`).
    3.  If the totals do not match and document-level allowances exist,
        proportionally distribute the document-level allowances across the lines.
    4.  Perform a final reconciliation of all calculated values (`net`, `vat`)
        against the document's authoritative header totals (`TaxExclusiveAmount`,
        `TaxTotal`) to account for any remaining rounding differences. This ensures
        the final output is both arithmetically sound and compliant with the
        invoice totals.
    """
    currency = getattr(document, "document_currency_code", "RON")
    supplier_name = extract_supplier_name(document.accounting_supplier_party.party)
    sign = Decimal("-1") if isinstance(document, CreditNote) else Decimal("1")

    # Authoritative totals from the document header
    total_invoice = Decimal(document.legal_monetary_total.tax_inclusive_amount)
    total_payable = Decimal(document.legal_monetary_total.payable_amount)
    prepaid_amount = Decimal(document.legal_monetary_total.prepaid_amount)
    tax_exclusive_target = _get_tax_exclusive_amount(document)
    tax_total_target = Decimal(document.tax_total.tax_amount)

    # Prepare initial line computations based on line-level data only
    line_entries = _prepare_line_entries(document)
    if not line_entries:
        logger.debug(f"product-summary: document {document.id} has no invoice lines")
        return []

    # Check for document-level allowances and distribute them if totals don't match
    initial_nets = [entry.net_after_line for entry in line_entries]
    initial_vats = [(n * entry.vat_rate / 100) for n, entry in zip(initial_nets, line_entries, strict=True)]
    initial_sum = sum(n + v for n, v in zip(initial_nets, initial_vats, strict=True))

    # Use absolute tolerance for currency comparison (not relative)
    totals_diff = abs(initial_sum - total_payable)
    if totals_diff > Decimal("0.01"):
        # Before redistributing document-level discounts, check if line-level discounts
        # already account for the document AllowanceTotalAmount. If they do, skip redistribution
        # to avoid double-counting discounts.
        doc_allowances, doc_charges = _split_allowances(document.allowance_charge or [])
        doc_adjustment_total = doc_allowances + doc_charges

        if doc_adjustment_total != 0:
            # Sum line-level discounts to check if they already account for document-level amount
            line_level_discounts = sum(entry.line_discount_value for entry in line_entries)
            line_level_charges = sum(entry.line_charge_value for entry in line_entries)
            line_level_total = line_level_discounts + line_level_charges

            # If line-level adjustments already match document-level (within tolerance),
            # skip redistribution to avoid double-counting
            adjustment_diff = abs(line_level_total - doc_adjustment_total)
            if adjustment_diff <= Decimal("0.02"):
                logger.debug(
                    f"Skipping document-level redistribution for {document.id}: "
                    f"line-level adjustments ({line_level_total}) already account for "
                    f"document-level amount ({doc_adjustment_total}), diff={adjustment_diff}"
                )
            else:
                logger.debug(
                    f"Distributing document-level adjustment of {doc_adjustment_total} for {document.id}. "
                    f"Initial sum: {initial_sum}, Payable amount: {total_payable}, "
                    f"Line-level total: {line_level_total}"
                )
                weights = [entry.raw_amount.copy_abs() for entry in line_entries]
                adjustments = _distribute_difference(doc_adjustment_total, weights)
                for entry, adj in zip(line_entries, adjustments, strict=True):
                    entry.apply_document_adjustment(adj)

    # Finalize nets and vats, then reconcile with document totals
    final_nets = [entry.final_net for entry in line_entries]
    final_vats = [entry.final_vat() for entry in line_entries]

    adjusted_nets = _adjust_to_target([n * sign for n in final_nets], tax_exclusive_target * sign)
    adjusted_vats = _adjust_to_target([v * sign for v in final_vats], tax_total_target * sign)
    adjusted_totals = [n + v for n, v in zip(adjusted_nets, adjusted_vats, strict=True)]

    rows: list[ProductSummaryRow] = []
    for entry, net_val, vat_val, total_val in zip(
        line_entries, adjusted_nets, adjusted_vats, adjusted_totals, strict=True
    ):
        rows.append(
            ProductSummaryRow(
                company_id=document.accounting_supplier_party.party.company_id,
                supplier=supplier_name,
                document_number=document.id,
                invoice_date=document.issue_date,
                currency=currency,
                total_invoice=(total_invoice * sign).quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP),
                total_payable=(total_payable * sign).quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP),
                product=entry.product,
                product_code=entry.product_code,
                quantity=entry.quantity,
                unit_of_measure=entry.unit_of_measure,
                unit_price=entry.unit_price,
                value=(entry.raw_amount * sign).quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP),
                vat_rate=entry.vat_rate,
                vat_value=vat_val,
                discount_rate=entry.discount_rate(),
                discount_value=(entry.total_discount * sign).quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP),
                total_per_line=total_val,
            )
        )

    # Final check on the sum of calculated totals vs. the payable amount
    totals_sum = sum(row.total_per_line for row in rows)
    expected_total = (total_payable + prepaid_amount) * sign
    if not math.isclose(totals_sum, expected_total, rel_tol=CURRENCY_QUANT):
        logger.warning(
            f"Final totals mismatch for {document.id}: calculated sum {totals_sum} vs expected {expected_total}"
        )

    return rows


def _prepare_line_entries(document: Invoice | CreditNote) -> list[_LineComputation]:
    """
    Prepare line-item computations based on explicit line-level data.
    This calculates the net cost from an inventory manager's perspective.
    """
    entries: list[_LineComputation] = []
    for line in _iter_lines(document):
        quantity = _extract_quantity(line)
        unit_price = _extract_unit_price(line, quantity)
        raw_amount = (unit_price or Decimal("0")) * (quantity or Decimal("0"))

        line_discount, line_charge = _split_allowances(line.allowance_charge or [])

        # For credit lines (negative quantity), a discount reduces the credit amount.
        # This formula correctly applies discounts and charges based on the line's sign.
        # Get the sign of the quantity (+1 or -1).
        quantity_sign = Decimal("1").copy_sign(quantity) if quantity else Decimal("1")
        net_after_line = raw_amount + (line_discount + line_charge) * quantity_sign

        entries.append(
            _LineComputation(
                product=(line.item.name or "Unknown").strip(),
                product_code=line.item.seller_item_id.strip() if line.item.seller_item_id else None,
                quantity=quantity,
                unit_of_measure=_extract_unit_code(line),
                unit_price=unit_price,
                vat_rate=Decimal(str(_extract_vat_percent(line))),
                raw_amount=raw_amount,
                line_discount_value=line_discount,
                line_charge_value=line_charge,
                net_after_line=net_after_line,
            )
        )
    return entries


def _iter_lines(document: Invoice | CreditNote) -> Iterable[InvoiceLine | CreditNoteLine]:
    if isinstance(document, Invoice):
        yield from document.invoice_line
    else:
        yield from document.credit_note_line


def _extract_quantity(line: InvoiceLine | CreditNoteLine) -> Decimal:
    qty_str = "0"
    if isinstance(line, InvoiceLine) and line.invoiced_quantity is not None:
        qty_str = str(line.invoiced_quantity)
    elif isinstance(line, CreditNoteLine) and line.credited_quantity is not None:
        qty_str = str(line.credited_quantity)
    return Decimal(qty_str)


def _extract_unit_code(line: InvoiceLine | CreditNoteLine) -> str | None:
    if isinstance(line, InvoiceLine):
        return line.invoiced_quantity_unit_code
    return line.credited_quantity_unit_code


def _extract_unit_price(line: InvoiceLine | CreditNoteLine, quantity: Decimal) -> Decimal | None:
    if line.price and line.price.price_amount is not None:
        return Decimal(str(line.price.price_amount))

    # Fallback for malformed UBL where price is missing
    if quantity != 0 and line.line_extension_amount is not None:
        return Decimal(str(line.line_extension_amount)) / quantity

    return None


def _extract_vat_percent(line: InvoiceLine | CreditNoteLine) -> float:
    tax_category = line.item.classified_tax_category
    return tax_category.percent if (tax_category and tax_category.percent is not None) else 0.0


def _split_allowances(allowances: Iterable[AllowanceCharge]) -> tuple[Decimal, Decimal]:
    """Splits allowances into total discount (negative) and charge (positive) amounts."""
    discount_total = Decimal("0")
    charge_total = Decimal("0")
    for allowance in allowances:
        amount = Decimal(str(allowance.amount)).copy_abs()
        if allowance.charge_indicator:
            charge_total += amount
        else:
            discount_total -= amount
    return discount_total, charge_total


def _distribute_difference(total_difference: Decimal, weights: Sequence[Decimal]) -> list[Decimal]:
    if not weights:
        return []

    weight_sum = sum(weights)
    if weight_sum == 0:
        # Cannot distribute by weight, so distribute evenly.
        if len(weights) > 0:
            share = total_difference / len(weights)
            return [share] * len(weights)
        return []

    adjustments = [(total_difference * w) / weight_sum for w in weights]
    # Ensure the sum of adjustments exactly equals the total_difference
    current_sum = sum(adj.quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP) for adj in adjustments)
    remainder = total_difference - current_sum
    if remainder != 0 and adjustments:
        adjustments[-1] += remainder
    return adjustments


def _adjust_to_target(values: Sequence[Decimal], target: Decimal) -> list[Decimal]:
    if not values:
        return []

    rounded = [v.quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP) for v in values]
    difference = target - sum(rounded)

    if difference == 0:
        return rounded

    # Distribute the rounding difference, one cent at a time, to the lines
    # with the largest absolute values, to minimize relative error.
    step = CURRENCY_QUANT if difference > 0 else -CURRENCY_QUANT
    num_steps = int(abs(difference) / CURRENCY_QUANT)

    # Create a list of (index, absolute_value) tuples to sort
    indexed_abs_values = sorted(enumerate(values), key=lambda x: abs(x[1]), reverse=True)

    for i in range(num_steps):
        # Distribute to lines in order of magnitude
        target_index = indexed_abs_values[i % len(indexed_abs_values)][0]
        rounded[target_index] += step

    return rounded


def _get_tax_exclusive_amount(document: Invoice | CreditNote) -> Decimal:
    tax_exclusive = document.legal_monetary_total.tax_exclusive_amount
    if tax_exclusive is None:
        # Fallback for malformed UBL
        return Decimal(document.legal_monetary_total.payable_amount) - Decimal(document.tax_total.tax_amount)
    return Decimal(str(tax_exclusive))


def _format_price(amount: Decimal | None, currency: str) -> str:
    if amount is None:
        return "-"
    return f"{amount:.4f}"


def _format_unit(unit_code: str | None) -> str:
    if not unit_code:
        return "-"
    description = UNIT_CODES.get(unit_code)
    if description is None:
        return unit_code
    return f"{unit_code} ({description})"


def _format_quantity(amount: Decimal) -> str:
    # Normalize to remove trailing zeros, then format
    normalized = amount.normalize()
    return format(normalized, "f")


@dataclass(slots=True)
class _LineComputation:
    """Internal helper to manage line-level calculations."""

    product: str
    product_code: str | None
    quantity: Decimal
    unit_of_measure: str | None
    unit_price: Decimal | None
    vat_rate: Decimal
    raw_amount: Decimal  # Gross value (price * qty)
    line_discount_value: Decimal  # Explicit line-level discount (negative)
    line_charge_value: Decimal  # Explicit line-level charge (positive)
    net_after_line: Decimal  # Net after line-level allowances
    document_adjustment: Decimal = Decimal("0")

    def apply_document_adjustment(self, adjustment: Decimal) -> None:
        self.document_adjustment = adjustment

    @property
    def final_net(self) -> Decimal:
        """The final taxable amount for the line after all adjustments."""
        return self.net_after_line + self.document_adjustment

    @property
    def total_discount(self) -> Decimal:
        """The total discount for the line (line-level + distributed document-level)."""
        doc_discount = self.document_adjustment if self.document_adjustment < 0 else Decimal("0")
        return self.line_discount_value + doc_discount

    def final_vat(self) -> Decimal:
        """The final VAT amount for the line."""
        return self.final_net * self.vat_rate / Decimal("100")

    def discount_rate(self) -> Decimal:
        """The effective discount rate for the line."""
        if self.raw_amount == 0:
            return Decimal("0")

        # For credit lines, the basis for the rate is the absolute value
        # `total_discount` is negative, so we take its absolute value too.
        rate = (self.total_discount.copy_abs() / self.raw_amount.copy_abs()) * Decimal("100")
        return rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
