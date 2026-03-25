"""Invoice data pipeline — fetch, download, process, query, and summarize."""

from libanaf.invoices.download import download
from libanaf.invoices.list import fetch_invoice_list
from libanaf.invoices.process import process_invoices
from libanaf.invoices.product_summary import ProductSummaryRow, build_product_summary_rows, summarize_products
from libanaf.invoices.query import collect_documents
from libanaf.invoices.summary import SummaryRow, build_summary_rows, summarize_invoices

__all__ = [
    "fetch_invoice_list",
    "download",
    "process_invoices",
    "collect_documents",
    "SummaryRow",
    "build_summary_rows",
    "summarize_invoices",
    "ProductSummaryRow",
    "build_product_summary_rows",
    "summarize_products",
]
