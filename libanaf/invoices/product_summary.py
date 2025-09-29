"""Produce a product-level summary for invoices and credit notes.

The feature aggregates every invoice line (or credit note line) that matches
the supplied filters, allocates document-level discounts across lines, and
renders the results in a Rich table ready for CLI output.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from collections.abc import Iterable, Sequence

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
    collect_documents as shared_collect_documents,
    ensure_date_range,
    extract_supplier_name,
    format_currency,
)

logger = logging.getLogger(__name__)

CURRENCY_QUANT = Decimal("0.01")
DEFAULT_CONSOLE = Console()


@dataclass(frozen=True, slots=True)
class ProductSummaryRow:
    """Aggregated information for a single invoice or credit-note line."""

    supplier: str
    document_number: str
    invoice_date: date
    currency: str
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
    *,
    config: AppConfig | None = None,
    output: Console | None = None,
) -> None:
    """Render a Rich table with product-level figures for matching documents."""

    product_console = output or DEFAULT_CONSOLE

    try:
        start, end = ensure_date_range(start_date, end_date)
    except DateValidationError as exc:
        if exc.code == "both_required":
            product_console.print(
                "[bold red]Error: both --start-date and --end-date must be supplied together.[/bold red]"
            )
        elif exc.code == "start_after_end":
            product_console.print("[bold red]Error: --start-date must be before or equal to --end-date.[/bold red]")
        else:  # pragma: no cover - defensive branch
            product_console.print("[bold red]Error: invalid date range.[/bold red]")
        raise typer.Exit(code=1)

    app_config = config or get_config()
    dlds_dir = app_config.storage.download_dir
    logger.debug(
        f"product-summary: using download dir {dlds_dir} "
        f"invoice_number={invoice_number} supplier_name={supplier_name} start={start} end={end}"
    )

    documents = collect_documents(
        dlds_dir,
        invoice_number=invoice_number,
        supplier_name=supplier_name,
        start_date=start,
        end_date=end,
    )

    if not documents:
        product_console.print("[yellow]No matching invoices or credit notes found.[/yellow]")
        return

    rows = build_product_summary_rows(documents)
    render_product_summary(rows, console=product_console)


def collect_documents(
    directory: Path | str,
    *,
    invoice_number: str | None,
    supplier_name: str | None,
    start_date: date | None,
    end_date: date | None,
) -> list[Invoice | CreditNote]:
    """Collect and parse documents that satisfy the supplied filters."""

    search_dir = Path(directory)
    logger.debug(f"product-summary collect_documents: dir={search_dir}")

    documents = shared_collect_documents(
        search_dir,
        invoice_number=invoice_number,
        supplier_name=supplier_name,
        start_date=start_date,
        end_date=end_date,
        allow_unfiltered=True,
    )
    logger.debug(f"product-summary collect_documents: parsed {len(documents)} documents")
    return documents


def build_product_summary_rows(documents: Sequence[Invoice | CreditNote]) -> list[ProductSummaryRow]:
    """Transform parsed documents into product-level summary rows."""

    rows: list[ProductSummaryRow] = []
    for document in documents:
        rows.extend(_build_rows_for_document(document))

    # rows.sort(key=lambda row: (row.invoice_date, row.document_number, row.product))
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
    table.add_column("Invoice Date", style="white")
    table.add_column("Total Value\n(Payable)", justify="right", style="magenta")
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
            format_currency(row.discount_value, row.currency),
            format_currency(row.total_per_line, row.currency),
        )

    target_console.print(table)


def _build_rows_for_document(document: Invoice | CreditNote) -> list[ProductSummaryRow]:
    currency = getattr(document, "document_currency_code", "RON")
    supplier_name = extract_supplier_name(document.accounting_supplier_party.party)
    total_payable = Decimal(str(document.legal_monetary_total.payable_amount))
    tax_exclusive = _get_tax_exclusive_amount(document)
    tax_total = Decimal(str(document.tax_total.tax_amount))
    sign = Decimal("-1") if isinstance(document, CreditNote) else Decimal("1")

    line_entries = _prepare_line_entries(document)
    if not line_entries:
        logger.debug(f"product-summary: document {document.id} has no invoice lines")
        return []

    net_values = [entry.net_after_line for entry in line_entries]
    net_sum = sum(net_values)
    adjustment_total = tax_exclusive - net_sum
    logger.debug(
        f"product-summary: document {document.id} net_sum={net_sum} "
        f"tax_exclusive={tax_exclusive} adjustment={adjustment_total}"
    )

    adjustments = _distribute_difference(adjustment_total, [entry.weight for entry in line_entries])
    for entry, adjustment in zip(line_entries, adjustments, strict=True):
        entry.apply_document_adjustment(adjustment)

    nets_signed = [entry.final_net * sign for entry in line_entries]
    vats_signed = [entry.final_vat() * sign for entry in line_entries]

    rounded_nets = _adjust_to_target(nets_signed, tax_exclusive * sign)
    rounded_vats = _adjust_to_target(vats_signed, tax_total * sign)
    totals_signed = [net + vat for net, vat in zip(rounded_nets, rounded_vats, strict=True)]

    total_payable_signed = (total_payable * sign).quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP)

    rows: list[ProductSummaryRow] = []
    for entry, net_value, vat_value, total_value in zip(
        line_entries, rounded_nets, rounded_vats, totals_signed, strict=True
    ):
        discount_rate = entry.discount_rate()
        discount_value = entry.total_discount.quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP)
        rows.append(
            ProductSummaryRow(
                supplier=supplier_name,
                document_number=document.id,
                invoice_date=document.issue_date,
                currency=currency,
                total_payable=total_payable_signed,
                product=entry.product,
                product_code=entry.product_code,
                quantity=entry.quantity,
                unit_of_measure=entry.unit_of_measure,
                unit_price=entry.unit_price,
                value=(entry.raw_amount * sign).quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP),
                vat_rate=entry.vat_rate,
                vat_value=vat_value,
                discount_rate=discount_rate,
                discount_value=discount_value,
                total_per_line=total_value,
            )
        )

    totals_sum = sum(row.total_per_line for row in rows)
    expected_total = total_payable_signed
    if totals_sum != expected_total:
        logger.warning(f"product-summary: rounding mismatch for {document.id} ({totals_sum} vs {expected_total})")

    return rows


def _prepare_line_entries(document: Invoice | CreditNote) -> list[_LineComputation]:
    entries: list[_LineComputation] = []
    for line in _iter_lines(document):
        raw_amount = Decimal(str(line.line_extension_amount))
        quantity = _extract_quantity(line)
        unit_code = _extract_unit_code(line)
        unit_price = _extract_unit_price(line, quantity)
        vat_percent = Decimal(str(_extract_vat_percent(line)))

        line_discount, line_charge = _split_allowances(line.allowance_charge or [])
        net_after_line = raw_amount + line_discount + line_charge

        product_name = (line.item.name or "Unknown").strip()
        product_code = line.item.seller_item_id.strip() if line.item.seller_item_id else None

        entries.append(
            _LineComputation(
                product=product_name,
                product_code=product_code,
                quantity=quantity,
                unit_of_measure=unit_code,
                unit_price=unit_price,
                vat_rate=vat_percent,
                raw_amount=raw_amount,
                discount_value=line_discount,
                charge_value=line_charge,
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
    if isinstance(line, InvoiceLine):
        return Decimal(str(line.invoiced_quantity))
    return Decimal(str(line.credited_quantity))


def _extract_unit_code(line: InvoiceLine | CreditNoteLine) -> str | None:
    if isinstance(line, InvoiceLine):
        return line.invoiced_quantity_unit_code
    return line.credited_quantity_unit_code


def _extract_unit_price(line: InvoiceLine | CreditNoteLine, quantity: Decimal) -> Decimal | None:
    if line.price and line.price.price_amount is not None:
        return Decimal(str(line.price.price_amount))

    if quantity == 0:
        return None

    return Decimal(str(line.line_extension_amount)) / quantity


def _extract_vat_percent(line: InvoiceLine | CreditNoteLine) -> float:
    tax_category = line.item.classified_tax_category
    return tax_category.percent if (tax_category and tax_category.percent is not None) else 0.0


def _split_allowances(allowances: Iterable[AllowanceCharge]) -> tuple[Decimal, Decimal]:
    discount_total = Decimal("0")
    charge_total = Decimal("0")
    for allowance in allowances:
        amount = Decimal(str(allowance.amount))
        if allowance.charge_indicator:
            charge_total += amount if amount >= 0 else -amount
        else:
            discount_total += amount if amount < 0 else -amount
    return discount_total, charge_total


def _distribute_difference(total_difference: Decimal, weights: Sequence[Decimal]) -> list[Decimal]:
    if not weights:
        return []

    weight_sum = sum(weights)
    if weight_sum == 0:
        # Single adjustment if we cannot rely on weights.
        adjustments = [Decimal("0")] * len(weights)
        adjustments[-1] = total_difference
        return adjustments

    adjustments: list[Decimal] = []
    accumulated = Decimal("0")
    for weight in weights[:-1]:
        share = (total_difference * weight) / weight_sum
        adjustments.append(share)
        accumulated += share

    adjustments.append(total_difference - accumulated)
    return adjustments


def _adjust_to_target(values: Sequence[Decimal], target: Decimal) -> list[Decimal]:
    if not values:
        return []

    rounded = [value.quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP) for value in values]
    difference = (target - sum(rounded)).quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP)

    if difference == 0:
        return rounded

    max_iterations = max(len(values) * 2, 128)
    for _ in range(max_iterations):
        if difference == 0:
            break

        step = CURRENCY_QUANT if difference > 0 else -CURRENCY_QUANT
        if difference > 0:
            candidates = [
                idx
                for idx, (original, rounded_val) in enumerate(zip(values, rounded, strict=True))
                if original > rounded_val
            ]
            candidates.sort(key=lambda idx: values[idx] - rounded[idx], reverse=True)
        else:
            candidates = [
                idx
                for idx, (original, rounded_val) in enumerate(zip(values, rounded, strict=True))
                if original < rounded_val
            ]
            candidates.sort(key=lambda idx: values[idx] - rounded[idx])

        if not candidates:
            candidates = [max(range(len(values)), key=lambda idx: abs(values[idx]))]

        idx = candidates[0]
        rounded[idx] += step
        difference -= step

    if difference != 0:
        rounded[-1] += difference

    return rounded


def _get_tax_exclusive_amount(document: Invoice | CreditNote) -> Decimal:
    tax_exclusive = document.legal_monetary_total.tax_exclusive_amount
    if tax_exclusive is None:
        return Decimal(str(document.legal_monetary_total.payable_amount)) - Decimal(str(document.tax_total.tax_amount))
    return Decimal(str(tax_exclusive))


def _format_price(amount: Decimal | None, currency: str) -> str:
    if amount is None:
        return "-"
    return f"{amount:.2f}"  # {currency}"


def _format_unit(unit_code: str | None) -> str:
    if not unit_code:
        return "-"
    description = UNIT_CODES.get(unit_code)
    if description is None:
        return unit_code
    return f"{unit_code} ({description})"


def _format_quantity(amount: Decimal) -> str:
    normalized = amount.normalize()
    return format(normalized, "f")


@dataclass(slots=True)
class _LineComputation:
    product: str
    product_code: str | None
    quantity: Decimal
    unit_of_measure: str | None
    unit_price: Decimal | None
    vat_rate: Decimal
    raw_amount: Decimal
    discount_value: Decimal
    charge_value: Decimal
    net_after_line: Decimal
    document_adjustment: Decimal = Decimal("0")

    def apply_document_adjustment(self, adjustment: Decimal) -> None:
        self.document_adjustment = adjustment

    @property
    def final_net(self) -> Decimal:
        return self.net_after_line + self.document_adjustment

    @property
    def total_discount(self) -> Decimal:
        document_component = self.document_adjustment if self.document_adjustment < 0 else Decimal("0")
        return self.discount_value + document_component

    @property
    def weight(self) -> Decimal:
        base = self.raw_amount.copy_abs()
        if base == 0:
            base = self.net_after_line.copy_abs()
        return base if base != 0 else Decimal("1")

    def final_vat(self) -> Decimal:
        return (self.final_net * self.vat_rate) / Decimal("100")

    def discount_rate(self) -> Decimal:
        if self.raw_amount == 0:
            return Decimal("0")
        rate = (self.total_discount / self.raw_amount) * Decimal("100")
        return rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
