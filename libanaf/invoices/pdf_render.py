"""Local PDF renderer for Romanian UBL e-invoices (FACTURA layout).

Generates a PDF styled as a standard Romanian FACTURA / NOTA DE CREDIT using
reportlab platypus.  No network calls — everything runs from the parsed UBL
model.

Public API
----------
    render_invoice_pdf(doc, output_path)
    render_invoice_pdf(doc, output_path, theme=PdfTheme(...))  # custom theme
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from libanaf.invoices.common import format_money as _fmt_money
from libanaf.ubl.credit_note import CreditNote
from libanaf.ubl.invoice import Invoice

logger = logging.getLogger(__name__)

DocumentType = Invoice | CreditNote

# ── Fonts ──────────────────────────────────────────────────────────────────────
FONT_N = "Helvetica"
FONT_B = "Helvetica-Bold"

# ── Page geometry ──────────────────────────────────────────────────────────────
_MARGIN = 12 * mm
_A4_W, _A4_H = A4
_USABLE_W = _A4_W - 2 * _MARGIN  # ≈ 527 pt

# ── 9-column item-table proportional widths (mm ratios from spec) ──────────────
_ITEM_RATIOS = [8, 20, 65, 12, 14, 28, 24, 18, 24]
_ITEM_COLS = [_USABLE_W * r / sum(_ITEM_RATIOS) for r in _ITEM_RATIOS]


# ── Theme ──────────────────────────────────────────────────────────────────────

@dataclass
class PdfTheme:
    """Colour and line-weight configuration for the invoice PDF.

    Designed to be toner-friendly: no solid dark fills, discrete pastel
    accents, light gray grid lines.
    """

    # ── Backgrounds ───────────────────────────────────────────────────────────
    # Very light blue-gray used for the title row and section column headers.
    header_bg: colors.Color = field(
        default_factory=lambda: colors.HexColor("#F8FAFB")
    )
    # Slightly darker accent used for column-header rows inside tables.
    section_header_bg: colors.Color = field(
        default_factory=lambda: colors.HexColor("#EEF2F5")
    )
    # Even rows in the items table get this subtle tint.
    alt_row_bg: colors.Color = field(
        default_factory=lambda: colors.HexColor("#F4F7F6")
    )
    # "Total de plata" row background — light green, easy on toner.
    total_highlight_bg: colors.Color = field(
        default_factory=lambda: colors.HexColor("#D1FAE5")
    )

    # ── Text ──────────────────────────────────────────────────────────────────
    primary: colors.Color = field(
        default_factory=lambda: colors.HexColor("#1F2937")
    )
    secondary: colors.Color = field(
        default_factory=lambda: colors.HexColor("#4B5563")
    )
    # Used for the large FACTURA / NOTA DE CREDIT heading.
    title: colors.Color = field(
        default_factory=lambda: colors.HexColor("#111827")
    )
    # Text colour inside the highlighted total row.
    total_highlight_text: colors.Color = field(
        default_factory=lambda: colors.HexColor("#065F46")
    )

    # ── Lines ─────────────────────────────────────────────────────────────────
    # Light gray used for all inner grid lines (0.5 pt).
    grid: colors.Color = field(
        default_factory=lambda: colors.HexColor("#D1D5DB")
    )
    # Slightly darker outer border.
    border: colors.Color = field(
        default_factory=lambda: colors.HexColor("#9CA3AF")
    )

    # ── Weights ───────────────────────────────────────────────────────────────
    grid_width: float = 0.5
    border_width: float = 0.75


DEFAULT_THEME = PdfTheme()


# ── Low-level helpers ──────────────────────────────────────────────────────────

def _p(
    text: str,
    font: str = FONT_N,
    size: int = 8,
    align: int = TA_LEFT,
    color: colors.Color = colors.HexColor("#1F2937"),
    leading_extra: int = 2,
) -> Paragraph:
    """Create a ``Paragraph`` with a one-off style. Newlines become ``<br/>``."""
    safe = escape(str(text)).replace("\n", "<br/>")
    style = ParagraphStyle(
        "auto",
        fontName=font,
        fontSize=size,
        leading=size + leading_extra,
        textColor=color,
        alignment=align,
    )
    return Paragraph(safe, style)


def _fmt_qty(value: float | int | None) -> str:
    if value is None:
        return ""
    s = f"{float(value):,.4f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "0"
    return f"{value:.0f}%"


# ── Domain helpers ─────────────────────────────────────────────────────────────

def _doc_type_label(is_credit: bool) -> str:
    return "NOTA DE CREDIT" if is_credit else "F A C T U R A"


def _supplier_name(doc: DocumentType) -> str:
    party = doc.accounting_supplier_party.party
    if party.party_name and party.party_name.name:
        return party.party_name.name
    if party.party_legal_entity and party.party_legal_entity.registration_name:
        return party.party_legal_entity.registration_name
    return "N/A"


def _customer_name(doc: DocumentType) -> str:
    party = doc.accounting_customer_party.party
    if party.party_name and party.party_name.name:
        return party.party_name.name
    if party.party_legal_entity and party.party_legal_entity.registration_name:
        return party.party_legal_entity.registration_name
    return "N/A"


def _party_info_lines(party) -> list[str]:
    """Return display lines for a Party (name, CIF, Reg.com, Sediul, Judet)."""
    d = party.get_display_str()
    lines: list[str] = [d.get("name", "N/A")]
    cif = d.get("cif", "")
    if cif and cif != "N/A":
        lines.append(f"CIF: {cif}")
    reg = d.get("reg_com", "")
    if reg and reg != "N/A":
        lines.append(f"Reg.com.: {reg}")
    addr = d.get("address", "")
    city = d.get("city", "")
    if addr:
        lines.append(f"Sediul: {addr}{(', ' + city) if city else ''}")
    county = d.get("county", "")
    if county:
        lines.append(f"Judet: {county}")
    return lines


def _payment_lines(doc: DocumentType) -> list[str]:
    lines: list[str] = []
    if doc.payment_means:
        for pm in doc.payment_means:
            d = pm.get_display_str()
            iban = d.get("iban", "")
            bank = d.get("bank", "")
            if iban and iban != "N/A":
                lines.append(f"Cont: {iban}")
            if bank and bank != "N/A":
                lines.append(f"Banca: {bank}")
    return lines


def _delivery_lines(doc: DocumentType) -> list[str]:
    """Return delivery address lines, or [] if no delivery address is present."""
    d = doc.delivery
    if d is None:
        return []
    loc = d.delivery_location
    if loc is None or loc.address is None:
        return []
    addr = loc.address
    parts: list[str] = []
    if addr.street_name:
        parts.append(addr.street_name)
    if addr.city_name:
        parts.append(addr.city_name)
    if addr.country_subentity:
        parts.append(addr.country_subentity)
    if not parts:
        return []
    lines: list[str] = ["", f"Adresa de Livrare: {', '.join(parts)}"]
    if d.delivery_party and d.delivery_party.party_name and d.delivery_party.party_name.name:
        lines.append(f"Destinatar: {d.delivery_party.party_name.name}")
    if d.actual_delivery_date:
        lines.append(f"Data livrare: {d.actual_delivery_date.strftime('%d/%m/%Y')}")
    return lines


# ── Section builders ───────────────────────────────────────────────────────────

def _build_title_bar(doc: DocumentType, is_credit: bool, t: PdfTheme) -> Table:
    """Section A — full-width title bar.

    Three columns: supplier name (left) | doc-type heading (centre) |
    customer name (right).  A second row carries the document meta-line.
    Light pastel background; no heavy ink.
    """
    col_w = _USABLE_W / 3
    doc_type = _doc_type_label(is_credit)
    sup = _supplier_name(doc)
    cus = _customer_name(doc)

    due_str = doc.due_date.strftime("%d/%m/%Y") if doc.due_date else "N/A"
    order_part = ""
    if doc.order_reference and doc.order_reference.id:
        order_part = f"   |   Nr. comanda {doc.order_reference.id}"
    subtitle = (
        f"Nr. {doc.id}   |   Data {doc.issue_date.strftime('%d/%m/%Y')}"
        f"   |   Scadenta {due_str}{order_part}"
    )

    data = [
        [
            _p(f"Furnizor\n{sup}", font=FONT_N, size=8, color=t.secondary),
            _p(doc_type, font=FONT_B, size=16, align=TA_CENTER, color=t.title),
            _p(f"Cumparator\n{cus}", font=FONT_N, size=8, align=TA_RIGHT, color=t.secondary),
        ],
        [
            "",
            _p(subtitle, font=FONT_N, size=7, align=TA_CENTER, color=t.secondary),
            "",
        ],
    ]

    table = Table(data, colWidths=[col_w, col_w, col_w])
    table.setStyle(TableStyle([
        # Both rows share the same pastel header background
        ("BACKGROUND",    (0, 0), (-1, -1), t.header_bg),
        # Outer border
        ("BOX",           (0, 0), (-1, -1), t.border_width, t.border),
        # Only a thin bottom line between the two rows
        ("LINEBELOW",     (0, 0), (-1, 0), t.grid_width, t.grid),
        # Remove vertical dividers inside the title row so it reads as one unit
        ("LINEBEFORE",    (1, 0), (1, 0), t.grid_width, t.grid),
        ("LINEBEFORE",    (2, 0), (2, 0), t.grid_width, t.grid),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING",    (0, 1), (-1, 1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    return table


def _build_info_table(doc: DocumentType, t: PdfTheme) -> Table:
    """Section B — 3-column info table (Furnizor | Detalii | Cumparator)."""
    col_w = _USABLE_W / 3

    sup_lines = _party_info_lines(doc.accounting_supplier_party.party) + _payment_lines(doc)
    cus_lines = _party_info_lines(doc.accounting_customer_party.party) + _delivery_lines(doc)

    due_str = doc.due_date.strftime("%d/%m/%Y") if doc.due_date else "N/A"
    det_lines = [
        f"Nr. factura: {doc.id}",
        f"Data emiterii: {doc.issue_date.strftime('%d/%m/%Y')}",
        f"Data scadenta: {due_str}",
    ]
    if doc.order_reference and doc.order_reference.id:
        det_lines.append(f"Nr. comanda: {doc.order_reference.id}")

    def _lp(lines: list[str]) -> Paragraph:
        return _p("\n".join(lines), size=8, color=t.primary)

    data = [
        [
            _p("FURNIZOR", font=FONT_B, size=8, align=TA_CENTER, color=t.primary),
            _p("DETALII FACTURA", font=FONT_B, size=8, align=TA_CENTER, color=t.primary),
            _p("CUMPARATOR", font=FONT_B, size=8, align=TA_CENTER, color=t.primary),
        ],
        [
            _lp(sup_lines),
            _lp(det_lines),
            _lp(cus_lines),
        ],
    ]

    table = Table(data, colWidths=[col_w, col_w, col_w])
    table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), t.section_header_bg),
        ("BOX",           (0, 0), (-1, -1), t.border_width, t.border),
        ("INNERGRID",     (0, 0), (-1, -1), t.grid_width, t.grid),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
    ]))
    return table


def _build_items_table(doc: DocumentType, is_credit: bool, t: PdfTheme) -> Table:
    """Section C — 9-column line-items table."""
    currency = getattr(doc, "document_currency_code", None) or "RON"
    sign = -1.0 if is_credit else 1.0

    def _hdr(text: str, align: int = TA_CENTER) -> Paragraph:
        return _p(text, font=FONT_B, size=7, align=align, color=t.primary)

    headers = [
        _hdr("#"),
        _hdr("Cod\nVamal"),
        _hdr("Denumire", align=TA_LEFT),
        _hdr("U.M."),
        _hdr("Cant."),
        _hdr("Pret unitar\n(fara TVA)"),
        _hdr("Valoare"),
        _hdr("Cota\nTVA%"),
        _hdr("Valoare\nTVA"),
    ]

    rows: list[list] = [headers]
    style_cmds: list[tuple] = [
        # Header row
        ("BACKGROUND",    (0, 0), (-1, 0), t.section_header_bg),
        ("FONTNAME",      (0, 0), (-1, 0), FONT_B),
        ("FONTSIZE",      (0, 0), (-1, 0), 7),
        ("TOPPADDING",    (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        # Outer border + grid
        ("BOX",           (0, 0), (-1, -1), t.border_width, t.border),
        ("INNERGRID",     (0, 0), (-1, -1), t.grid_width, t.grid),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        # Data rows
        ("FONTNAME",      (0, 1), (-1, -1), FONT_N),
        ("FONTSIZE",      (0, 1), (-1, -1), 8),
        ("TOPPADDING",    (0, 1), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 3),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
        ("TEXTCOLOR",     (0, 1), (-1, -1), t.primary),
    ]

    if isinstance(doc, Invoice):
        lines = doc.invoice_line
        qty_attr = "invoiced_quantity"
        unit_attr = "invoiced_quantity_unit_code"
    else:
        lines = doc.credit_note_line
        qty_attr = "credited_quantity"
        unit_attr = "credited_quantity_unit_code"

    for idx, line in enumerate(lines, start=1):
        cod_vamal = ""
        if line.item.commodity_classification:
            raw = line.item.commodity_classification.item_classification_code or ""
            cod_vamal = "" if raw == "None" else raw

        qty = float(getattr(line, qty_attr, 0.0) or 0.0)
        unit_code = getattr(line, unit_attr, None) or "H87"
        unit_price = float((line.price.price_amount if line.price else 0.0) or 0.0)
        base_value = float(line.line_extension_amount or 0.0)

        percent = 0.0
        if line.item.classified_tax_category and line.item.classified_tax_category.percent is not None:
            percent = line.item.classified_tax_category.percent
        vat_value = base_value * (percent / 100.0)

        qty *= sign
        unit_price *= sign
        base_value *= sign
        vat_value *= sign

        rows.append([
            _p(str(idx), size=8, align=TA_CENTER, color=t.secondary),
            _p(cod_vamal, size=7, color=t.secondary),
            _p(line.item.name, size=8, color=t.primary),
            _p(str(unit_code), size=8, align=TA_CENTER, color=t.secondary),
            _p(_fmt_qty(qty), size=8, align=TA_RIGHT, color=t.primary),
            _p(_fmt_money(unit_price, currency), size=8, align=TA_RIGHT, color=t.primary),
            _p(_fmt_money(base_value, currency), size=8, align=TA_RIGHT, color=t.primary),
            _p(_fmt_pct(percent), size=8, align=TA_CENTER, color=t.secondary),
            _p(_fmt_money(vat_value, currency), size=8, align=TA_RIGHT, color=t.primary),
        ])

        # Subtle alternating rows — every even data row gets a light tint
        if idx % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, idx), (-1, idx), t.alt_row_bg))

    table = Table(rows, colWidths=_ITEM_COLS, repeatRows=1)
    table.setStyle(TableStyle(style_cmds))
    return table


def _build_notes(doc: DocumentType, t: PdfTheme) -> Table | None:
    """Section D — optional notes box, rendered as a single-cell bordered table."""
    if not doc.note:
        return None
    text = "\n".join(n for n in doc.note if n and str(n).strip())
    if not text.strip():
        return None

    cell = _p(f"Note: {text}", size=8, color=t.secondary)
    table = Table([[cell]], colWidths=[_USABLE_W])
    table.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), t.grid_width, t.grid),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("BACKGROUND",    (0, 0), (-1, -1), t.header_bg),
    ]))
    return table


def _build_totals_footer(doc: DocumentType, is_credit: bool, t: PdfTheme) -> Table:
    """Section E — signature area (left) and totals mini-table (right)."""
    currency = getattr(doc, "document_currency_code", None) or "RON"
    sign = -1.0 if is_credit else 1.0

    lmt = doc.legal_monetary_total
    tax_total = getattr(doc, "tax_total", None)
    tax_amount = float(tax_total.tax_amount if tax_total else 0.0)

    total_no_vat = float(lmt.tax_exclusive_amount or 0.0) * sign
    total_vat = tax_amount * sign
    total_payable = float(lmt.payable_amount or 0.0) * sign

    totals_col_w = _USABLE_W * 0.42
    sig_col_w = _USABLE_W - totals_col_w
    lbl_w = totals_col_w * 0.54
    val_w = totals_col_w * 0.46

    def _lbl(text: str, bold: bool = False, color: colors.Color | None = None) -> Paragraph:
        return _p(text, font=FONT_B if bold else FONT_N, size=8,
                  color=color or t.primary)

    def _val(text: str, bold: bool = False, color: colors.Color | None = None) -> Paragraph:
        return _p(text, font=FONT_B if bold else FONT_N, size=8,
                  align=TA_RIGHT, color=color or t.primary)

    totals_data = [
        [_lbl("Total (fara TVA)"),  _val(_fmt_money(total_no_vat, currency))],
        [_lbl("TVA"),               _val(_fmt_money(total_vat, currency))],
        [
            _lbl("Total de plata", bold=True, color=t.total_highlight_text),
            _val(_fmt_money(total_payable, currency), bold=True, color=t.total_highlight_text),
        ],
    ]

    totals_inner = Table(totals_data, colWidths=[lbl_w, val_w])
    totals_inner.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (-1, -1), FONT_N),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        # Outer box + inner grid in light gray
        ("BOX",           (0, 0), (-1, -1), t.border_width, t.border),
        ("INNERGRID",     (0, 0), (-1, -2), t.grid_width, t.grid),
        # Separator line above the highlighted total row
        ("LINEABOVE",     (0, -1), (-1, -1), t.border_width, t.border),
        # Light green highlight for "Total de plata" — no heavy ink
        ("BACKGROUND",    (0, -1), (-1, -1), t.total_highlight_bg),
        ("FONTNAME",      (0, -1), (-1, -1), FONT_B),
        ("FONTSIZE",      (0, -1), (-1, -1), 9),
    ]))

    sig_text = _p(
        "Furnizor,\n\n___________________________"
        "\n\n\nCumparator,\n\n___________________________",
        size=8,
        color=t.secondary,
    )

    outer = Table([[sig_text, totals_inner]], colWidths=[sig_col_w, totals_col_w])
    outer.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    return outer


# ── Layout helpers ─────────────────────────────────────────────────────────────

class _FillToBottom(Flowable):
    """Expands to fill remaining page space minus *reserved* points.

    Insert this between the main content and the bottom section so that
    the bottom section is pushed to the foot of the page regardless of
    how much content precedes it.
    """

    def __init__(self, reserved: float) -> None:
        Flowable.__init__(self)
        self._reserved = reserved

    def wrap(self, availWidth: float, availHeight: float):
        self._h = max(0.0, availHeight - self._reserved)
        return availWidth, self._h

    def draw(self) -> None:
        pass


# ── Public API ─────────────────────────────────────────────────────────────────

def render_invoice_pdf(
    doc: DocumentType,
    output_path: Path,
    theme: PdfTheme | None = None,
) -> None:
    """Render a UBL Invoice or CreditNote to a PDF file.

    Args:
        doc: Parsed ``Invoice`` or ``CreditNote`` instance.
        output_path: Destination ``.pdf`` file path (parent dirs are created
            automatically).
        theme: Optional ``PdfTheme`` to override colours/weights.  Defaults to
            ``DEFAULT_THEME`` (toner-friendly pastel palette).
    """
    t = theme or DEFAULT_THEME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    is_credit = isinstance(doc, CreditNote)

    pdf = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=_MARGIN,
        rightMargin=_MARGIN,
        topMargin=_MARGIN,
        bottomMargin=_MARGIN,
    )

    # Build bottom-section flowables first so we can measure their height.
    notes = _build_notes(doc, t)
    totals = _build_totals_footer(doc, is_credit, t)

    _large = 2000.0
    bottom_h: float = 0.0
    if notes is not None:
        _, nh = notes.wrap(_USABLE_W, _large)
        bottom_h += nh + 2 * mm
    _, th = totals.wrap(_USABLE_W, _large)
    bottom_h += th

    story: list = []

    # A — title bar
    story.append(_build_title_bar(doc, is_credit, t))
    story.append(Spacer(1, 2 * mm))

    # B — info table
    story.append(_build_info_table(doc, t))
    story.append(Spacer(1, 3 * mm))

    # C — line items
    story.append(_build_items_table(doc, is_credit, t))

    # Flexible gap — pushes D+E to the bottom of the page
    story.append(_FillToBottom(reserved=bottom_h))

    # D — notes (optional), right above totals
    if notes is not None:
        story.append(notes)
        story.append(Spacer(1, 2 * mm))

    # E — totals + signatures
    story.append(totals)

    pdf.build(story)
    logger.info("PDF written: %s", output_path)
