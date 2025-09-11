"""UBL document base model and helpers.

Provides a Pydantic-XML base class for UBL documents (Invoices and
Credit Notes) plus utilities to parse a UBL XML file and to work with
embedded attachments.
"""

# ruff: noqa: UP045, UP035, UP006
# disabled some rules becasue of pydantic-xml usage

import datetime
import logging
from pathlib import Path
from typing import Optional, TypeVar
from lxml import etree  # pyright: ignore

from pydantic_xml import BaseXmlModel, element, wrapped

from libanaf.ubl.cac import (
    AccountingCustomerParty,
    AccountingSupplierParty,
    AdditionalDocumentReference,
    LegalMonetaryTotal,
    OrderReference,
    Party,
    PaymentMeans,
    TaxTotal,
)
from libanaf.ubl.ubl_types import NSMAP
from libanaf.utils import sanitize_file_name

UBLDocT = TypeVar("UBLDocT", bound="UBLDocument")

logger = logging.getLogger(__name__)


class UBLDocument(BaseXmlModel):
    """Base class for UBL documents (Invoice, CreditNote).

    Attributes:
        id: Unique identifier of the document.
        issue_date: Date the document was issued.
        document_currency_code: Document currency (ISO 4217).
        accounting_supplier_party: Supplier party information.
        accounting_customer_party: Customer party information.
        tax_total: Aggregated tax totals.
        legal_monetary_total: Monetary totals, including payable amount.
    """

    ubl_version_id: Optional[str] = element(tag="UBLVersionID", default=None, ns="cbc")
    customization_id: Optional[str] = element(tag="CustomizationID", default=None, ns="cbc")
    profile_id: Optional[str] = element(tag="ProfileID", default=None, ns="cbc")
    profile_excution_id: Optional[str] = element(tag="ProfileExecutionID", default=None, ns="cbc")
    id: str = element(tag="ID", ns="cbc")
    issue_date: datetime.date = element(tag="IssueDate", ns="cbc")
    issue_time: Optional[datetime.time] = element(tag="IssueTime", default=None, ns="cbc")
    due_date: Optional[datetime.date] = element(tag="DueDate", default=None, ns="cbc")
    note: Optional[list[str]] = element(tag="Note", default=None, ns="cbc")
    tax_point_date: Optional[str] = element(tag="TaxPointDate", default=None, ns="cbc")
    document_currency_code: str = element(tag="DocumentCurrencyCode", ns="cbc")
    tax_currency_code: Optional[str] = element(tag="TaxCurrencyCode", default=None, ns="cbc")
    ivoice_period: Optional[OrderReference] = None
    order_reference: Optional[OrderReference] = None
    contract_document_reference: Optional[str] = wrapped(
        "ContractDocumentReference",
        ns="cac",
        nsmap=NSMAP,
        default=None,
        entity=element(tag="ID", default=None, ns="cbc"),
    )
    additional_document_reference: Optional[AdditionalDocumentReference] = None
    accounting_supplier_party: AccountingSupplierParty
    accounting_customer_party: AccountingCustomerParty
    payment_means: Optional[list[PaymentMeans]] = None
    tax_total: TaxTotal
    legal_monetary_total: LegalMonetaryTotal

    def tofname(self) -> str:
        """Build a human-friendly filename for this document.

        The filename uses supplier name, issue date, document number, and
        the payable amount, sanitized for filesystem safety.

        Returns:
            str: A sanitized filename stem including amount (no extension).

        Raises:
            ValueError: If the supplier name is missing.
        """
        supplier_party: Party = self.accounting_supplier_party.party
        supplier_name = (
            supplier_party.party_name.name
            if supplier_party.party_name and supplier_party.party_name.name
            else supplier_party.party_legal_entity.registration_name
        )

        if not supplier_name:
            raise ValueError(f"Supplier name is missing for document ID: {self.id}")

        no = self.id
        dt = str(self.issue_date)
        amt = f"{self.legal_monetary_total.payable_amount:.2f}"

        return sanitize_file_name(supplier_name, dt, no, glue="_") + "_" + amt

    def has_attachment(self) -> bool:
        """Check whether the document has an embedded binary attachment.

        Returns:
            bool: True if an embedded binary document is present.
        """
        return (
            self.additional_document_reference is not None
            and self.additional_document_reference.attachment is not None
            and self.additional_document_reference.attachment.embedded_binary_document is not None
        )

    def write_attachment(self, destination: Path) -> None:
        """Write the embedded binary attachment to disk.

        Args:
            destination: Path where the attachment will be written.

        Raises:
            AttributeError: If the document has no embedded attachment.
            OSError: If writing to the destination path fails.
        """
        with open(destination, "wb") as dest:
            dest.write(self.additional_document_reference.attachment.embedded_binary_document)  # pyright: ignore


def parse_ubl_document(xml_file: str | Path) -> UBLDocument:
    """Parse a UBL XML file into a typed document model.

    Supports the following UBL document types based on the XML root:
    "Invoice" and "CreditNote".

    Args:
        xml_file: Path to the UBL XML file.

    Returns:
        UBLDocument: A parsed `Invoice` or `CreditNote` instance.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the document type is not supported.
    """
    logger.debug(f"Parsing UBL document: {xml_file}")
    if isinstance(xml_file, str):
        xml_file = Path(xml_file)

    if not xml_file.exists():
        raise FileNotFoundError(f"File {xml_file} does not exist")

    root = etree.parse(str(xml_file)).getroot()
    local_name = etree.QName(root).localname

    if local_name != "Invoice" and local_name != "CreditNote":
        raise ValueError(
            f"Unsupported UBL document type '{local_name}' in file {xml_file}. "
            "Supported types are: 'Invoice', 'CreditNote'."
        )

    ubl_document: UBLDocument
    if local_name == "Invoice":
        from libanaf.ubl.invoice import Invoice

        with xml_file.open("r", encoding="utf-8") as file:
            ubl_document = Invoice.from_xml(bytes(file.read(), encoding="utf-8"))
    elif local_name == "CreditNote":
        from libanaf.ubl.credit_note import CreditNote

        with xml_file.open("r", encoding="utf-8") as file:
            ubl_document = CreditNote.from_xml(bytes(file.read(), encoding="utf-8"))

    logger.debug(f"Successfully parsed UBL document: {xml_file}")
    return ubl_document  # pyright: ignore
