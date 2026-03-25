"""CLI command for processing downloaded invoice ZIPs."""

import logging

from libanaf.invoices.process import process_invoices

logger = logging.getLogger(__name__)


def invoices_process() -> None:
    """Process all invoices in the download folder:
    1. Unzips the files and extract the XML of the invoices
    2. Uses the ANAF API to convert the files to PDF
    """
    logger.info("Starting processing ...")
    process_invoices()
