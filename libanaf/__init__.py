"""libanaf — ANAF e-Factura SDK.

Install with ``pip install libanaf`` for library use.
Install with ``pip install libanaf[cli]`` to also get the CLI entry point.
"""

import logging

from libanaf.auth import AnafAuthClient, OAuthCallbackServer
from libanaf.config import get_settings, save_tokens
from libanaf.exceptions import AnafException, AnafRequestError, AuthorizationError
from libanaf.invoices.download import download
from libanaf.invoices.list import fetch_invoice_list
from libanaf.invoices.process import process_invoices
from libanaf.invoices.product_summary import ProductSummaryRow, build_product_summary_rows, summarize_products
from libanaf.invoices.query import collect_documents
from libanaf.invoices.summary import SummaryRow, build_summary_rows, summarize_invoices
from libanaf.types import Filter
from libanaf.ubl.credit_note import CreditNote
from libanaf.ubl.invoice import Invoice
from libanaf.ubl.ubl_document import parse_ubl_document

__all__ = [
    # Auth
    "AnafAuthClient",
    "OAuthCallbackServer",
    # Config
    "get_settings",
    "save_tokens",
    # Exceptions
    "AnafException",
    "AnafRequestError",
    "AuthorizationError",
    # Types
    "Filter",
    # Invoice API
    "fetch_invoice_list",
    "download",
    "process_invoices",
    "collect_documents",
    # Summary
    "SummaryRow",
    "build_summary_rows",
    "summarize_invoices",
    # Product summary
    "ProductSummaryRow",
    "build_product_summary_rows",
    "summarize_products",
    # UBL models
    "Invoice",
    "CreditNote",
    "parse_ubl_document",
]

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())
