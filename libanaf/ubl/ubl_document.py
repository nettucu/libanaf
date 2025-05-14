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


class UBLDocument(BaseXmlModel, tag="", search_mode="unordered", ns="", nsmap=NSMAP):
    """
    Base class for UBL documents like Invoices or Credit Notes.

    Attributes:
        id: The unique identifier of the document.
        issue_date: The date the document was issued.
        legal_monetary_total: The monetary total of the document.
    """

    ubl_version_id: Optional[str] = element(tag="UBLVersionID", default=None, ns="cbc")  # , nsmap=NSMAP)
    customization_id: Optional[str] = element(tag="CustomizationID", default=None, ns="cbc")  # , nsmap=NSMAP)
    profile_id: Optional[str] = element(tag="ProfileID", default=None, ns="cbc")  # , nsmap=NSMAP)
    profile_excution_id: Optional[str] = element(tag="ProfileExecutionID", default=None, ns="cbc")  # , nsmap=NSMAP)
    id: str = element(tag="ID", ns="cbc")  # , nsmap=NSMAP)
    issue_date: datetime.date = element(tag="IssueDate", ns="cbc")  # , nsmap=NSMAP)
    issue_time: Optional[datetime.time] = element(tag="IssueTime", default=None, ns="cbc")  # , nsmap=NSMAP)
    due_date: Optional[datetime.date] = element(tag="DueDate", default=None, ns="cbc")  # , nsmap=NSMAP)
    note: Optional[list[str]] = element(tag="Note", default=None, ns="cbc")  # , nsmap=NSMAP)
    tax_point_date: Optional[str] = element(tag="TaxPointDate", default=None, ns="cbc")  # , nsmap=NSMAP)
    document_currency_code: str = element(tag="DocumentCurrencyCode", ns="cbc")  # , nsmap=NSMAP)
    tax_currency_code: Optional[str] = element(tag="TaxCurrencyCode", default=None, ns="cbc")  # , nsmap=NSMAP)
    ivoice_period: Optional[OrderReference] = None
    order_reference: Optional[OrderReference] = None
    contract_document_reference: Optional[str] = wrapped(
        "ContractDocumentReference",
        ns="cac",
        nsmap=NSMAP,
        default=None,
        entity=element(tag="ID", default=None, ns="cbc"),  # , nsmap=NSMAP),
    )
    additional_document_reference: Optional[AdditionalDocumentReference] = None
    accounting_supplier_party: AccountingSupplierParty
    accounting_customer_party: AccountingCustomerParty
    payment_means: Optional[list[PaymentMeans]] = None
    tax_total: TaxTotal
    legal_monetary_total: LegalMonetaryTotal

    def tofname(self) -> str:
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
        return (
            self.additional_document_reference is not None
            and self.additional_document_reference.attachment is not None
            and self.additional_document_reference.attachment.embedded_binary_document is not None
        )

    def write_attachment(self, destination: Path) -> None:
        with open(destination, "wb") as dest:
            dest.write(self.additional_document_reference.attachment.embedded_binary_document)  # pyright: ignore


def parse_ubl_document(xml_file: str | Path) -> UBLDocument:
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
