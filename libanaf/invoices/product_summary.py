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
from enum import Enum, auto
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ..config import AppConfig, get_config
from ..types import UNIT_CODES
from ..ubl.cac import CreditNoteLine, InvoiceLine
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


class _LineBaseType(Enum):
    """Enum to classify how LineExtensionAmount should be interpreted."""

    ALREADY_NET = auto()  # LineExtensionAmount is NET (SITEA pattern - EN 16931 compliant)
    GROSS_NEEDS_DISCOUNT = auto()  # LineExtensionAmount is GROSS (IMC pattern - needs discount applied)
    USE_DISTRIBUTION = auto()  # Fallback: distribute difference proportionally


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
    ensuring Total Per Line sums to TaxInclusiveAmount.

    Uses pattern detection to handle two common UBL patterns:
    - Pattern A (EN 16931 compliant): LineExtensionAmount is NET (after discounts)
    - Pattern B (non-compliant but common): LineExtensionAmount is GROSS (before discounts)
    """
    currency = getattr(document, "document_currency_code", "RON")
    supplier_name = extract_supplier_name(document.accounting_supplier_party.party)
    sign = Decimal("-1") if isinstance(document, CreditNote) else Decimal("1")

    # Header Totals
    total_invoice = Decimal(document.legal_monetary_total.tax_inclusive_amount)
    total_payable = Decimal(document.legal_monetary_total.payable_amount)
    prepaid_amount = Decimal(document.legal_monetary_total.prepaid_amount)
    tax_exclusive_target = _get_tax_exclusive_amount(document)
    tax_total_target = Decimal(document.tax_total.tax_amount)

    # 1. Parse lines
    line_entries = _prepare_line_entries(document)
    if not line_entries:
        return []

    # 2. Determine Base Calculation Strategy
    base_type = _detect_line_base_type(line_entries, tax_exclusive_target)
    logger.debug(f"Document {document.id}: Detected Line Base Type: {base_type.name}")

    # 3. Apply Strategy to determine 'Final Base' for each line
    for entry in line_entries:
        if base_type == _LineBaseType.ALREADY_NET:
            # SITEA case: LineExt is already net. Discount is informational or already deducted.
            entry.set_final_base(entry.line_ext_amount)

        elif base_type == _LineBaseType.GROSS_NEEDS_DISCOUNT:
            # IMC case: LineExt is Gross. We must subtract line discount.
            line_sign = Decimal("1").copy_sign(entry.line_ext_amount) if entry.line_ext_amount else Decimal("1")
            net_amount = entry.line_ext_amount - (entry.line_discount_abs * line_sign)
            entry.set_final_base(net_amount)

        else:
            # Fallback: Start with LineExt
            entry.set_final_base(entry.line_ext_amount)

    # 4. Reconcile Base with TaxExclusiveAmount
    current_base_sum = sum(e.final_net for e in line_entries)
    diff_base = tax_exclusive_target - current_base_sum

    if abs(diff_base) > Decimal("0.005"):
        logger.debug(f"Reconciling Base for {document.id}: Diff {diff_base}")
        weights = [e.line_ext_amount.copy_abs() for e in line_entries]
        adjustments = _distribute_difference(diff_base, weights)
        for entry, adj in zip(line_entries, adjustments, strict=True):
            entry.apply_adjustment(adj)

    # 5. Calculate VAT and Reconcile with TaxTotal
    initial_vats = [entry.calc_vat() for entry in line_entries]
    final_vats = _adjust_to_target(initial_vats, tax_total_target)

    # 6. Build Rows
    rows: list[ProductSummaryRow] = []
    for entry, vat_val in zip(line_entries, final_vats, strict=True):
        # Total per line = Base + VAT
        total_val = entry.final_net + vat_val

        # Calculate implied discount from final reconciled numbers
        # Discount should be negative (final_net - raw_amount)
        discount_calc = entry.final_net - entry.raw_amount

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
                # Value is the GROSS amount (Price × Quantity) before discounts
                value=(entry.raw_amount * sign).quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP),
                vat_rate=entry.vat_rate,
                vat_value=(vat_val * sign).quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP),
                discount_rate=entry.calc_discount_rate(discount_calc),
                discount_value=(discount_calc * sign).quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP),
                total_per_line=(total_val * sign).quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP),
            )
        )

    return rows


def _detect_line_base_type(entries: list[_LineComputation], target_tax_exclusive: Decimal) -> _LineBaseType:
    """
    Determine if the XML LineExtensionAmount is 'Gross' (needs discount subtraction)
    or 'Already Net' (matches TaxExclusiveAmount directly).
    """
    # Sum if we assume LineExt is ALREADY NET
    sum_as_net = sum(e.line_ext_amount for e in entries)
    diff_if_net = abs(sum_as_net - target_tax_exclusive)

    # Sum if we assume LineExt is GROSS (subtract specific line discounts)
    sum_as_gross = Decimal("0")
    for e in entries:
        line_sign = Decimal("1").copy_sign(e.line_ext_amount) if e.line_ext_amount else Decimal("1")
        net_amount = e.line_ext_amount - (e.line_discount_abs * line_sign)
        sum_as_gross += net_amount

    diff_if_gross = abs(sum_as_gross - target_tax_exclusive)

    logger.debug(
        f"Detection: Target={target_tax_exclusive} | "
        f"SumNet={sum_as_net} (diff={diff_if_net}) | "
        f"SumGross={sum_as_gross} (diff={diff_if_gross})"
    )

    if diff_if_net <= Decimal("0.05"):
        return _LineBaseType.ALREADY_NET
    if diff_if_gross <= Decimal("0.05"):
        return _LineBaseType.GROSS_NEEDS_DISCOUNT

    # If neither matches well, we have a document-level discount not in line allowances
    return _LineBaseType.USE_DISTRIBUTION


def _prepare_line_entries(document: Invoice | CreditNote) -> list[_LineComputation]:
    """
    Prepare line-item computations based on explicit line-level data.

    Special Logic:
    Detects invoice lines that are actually discounts (Negative Quantity + "Discount" in name)
    and distributes their value proportionally to the real product lines instead of
    returning them as separate entries.
    """
    all_entries: list[_LineComputation] = []

    # 1. First Pass: Parse all lines into objects
    for line in _iter_lines(document):
        quantity = _extract_quantity(line)
        unit_price = _extract_unit_price(line, quantity)
        line_ext = Decimal(str(line.line_extension_amount)) if line.line_extension_amount is not None else Decimal(0)

        # Sum up allowances from the line (absolute values)
        discount_abs = Decimal("0")
        if line.allowance_charge:
            for ac in line.allowance_charge:
                if ac.charge_indicator is False and ac.amount is not None:
                    discount_abs += Decimal(str(ac.amount)).copy_abs()

        raw_amount = (unit_price or Decimal("0")) * (quantity or Decimal("0"))

        entry = _LineComputation(
            product=(line.item.name or "Unknown").strip(),
            product_code=line.item.seller_item_id.strip() if line.item.seller_item_id else None,
            quantity=quantity,
            unit_of_measure=_extract_unit_code(line),
            unit_price=unit_price,
            vat_rate=Decimal(str(_extract_vat_percent(line))),
            raw_amount=raw_amount,
            line_ext_amount=line_ext,
            line_discount_abs=discount_abs,
        )
        # Initialize final_net with line_ext_amount for now (will be refined in build_rows)
        # But for the purpose of discount distribution, we need a base value.
        # We will use line_ext_amount as the "value" of the line.
        entry.set_final_base(line_ext)
        all_entries.append(entry)

    # 2. Second Pass: Separate "Real" lines from "Fake Discount" lines
    product_entries: list[_LineComputation] = []
    discount_entries: list[_LineComputation] = []

    for entry in all_entries:
        # Heuristic: If quantity is negative AND name contains "discount" or "reducere"
        # treat it as a financial adjustment, not a returned product.
        is_fake_discount = entry.quantity < 0 and (
            "discount" in entry.product.lower() or "reducere" in entry.product.lower()
        )

        if is_fake_discount:
            discount_entries.append(entry)
        else:
            product_entries.append(entry)

    # 3. Third Pass: Distribute the value of discount lines (if any)
    if discount_entries and product_entries:
        # Sum the total value of the discount lines (e.g. -112.40)
        # We use line_ext_amount because that captures the full value of that line
        total_special_discount = sum(e.line_ext_amount for e in discount_entries)

        logger.debug(f"Found {len(discount_entries)} discount lines totaling {total_special_discount}. Distributing...")

        # We distribute based on the absolute raw value of the real products
        weights = [e.raw_amount.copy_abs() for e in product_entries]

        # This function returns parts that sum exactly to total_special_discount
        adjustments = _distribute_difference(total_special_discount, weights)

        # Apply the adjustment to the real lines
        for entry, adj in zip(product_entries, adjustments, strict=True):
            # We apply this as an adjustment to the final net
            # Note: This adjustment happens BEFORE the main reconciliation logic in build_rows
            # so we are effectively modifying the "Base" of the line.
            entry.apply_adjustment(adj)

    # 4. Return only the real product entries
    return product_entries


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

    # Calculate raw shares
    raw_shares = [(total_difference * w) / weight_sum for w in weights]

    # Quantize
    adjustments = [s.quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP) for s in raw_shares]

    # Calculate remainder
    current_sum = sum(adjustments)
    remainder = total_difference - current_sum

    if remainder == 0:
        return adjustments

    # Distribute remainder to the items with largest weights to minimize relative error
    step = CURRENCY_QUANT if remainder > 0 else -CURRENCY_QUANT
    num_steps = int(abs(remainder) / CURRENCY_QUANT)

    # Sort indices by weight (descending)
    indexed_weights = sorted(enumerate(weights), key=lambda x: x[1], reverse=True)

    for i in range(num_steps):
        target_index = indexed_weights[i % len(indexed_weights)][0]
        adjustments[target_index] += step

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
    raw_amount: Decimal  # Price * Qty
    line_ext_amount: Decimal  # XML LineExtensionAmount (may be NET or GROSS)
    line_discount_abs: Decimal  # Explicit line-level discount (absolute value)

    final_net: Decimal = Decimal("0")

    def set_final_base(self, amount: Decimal) -> None:
        """Set the initial final net amount before reconciliation."""
        self.final_net = amount

    def apply_adjustment(self, adj: Decimal) -> None:
        """Apply a reconciliation adjustment to the final net amount."""
        self.final_net += adj

    def calc_vat(self) -> Decimal:
        """Calculate VAT based on final net amount."""
        return self.final_net * self.vat_rate / Decimal("100")

    def calc_discount_rate(self, discount_val: Decimal) -> Decimal:
        """Calculate discount rate as percentage of raw amount."""
        if self.raw_amount == 0:
            return Decimal("0")
        rate = (discount_val.copy_abs() / self.raw_amount.copy_abs()) * Decimal("100")
        return rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
