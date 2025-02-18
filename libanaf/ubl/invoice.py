import datetime
from pathlib import Path
from threading import local
from typing import List, Optional

from pydantic_xml import BaseXmlModel, element, wrapped
from rich.pretty import pprint
from rich.console import Console

from libanaf.ubl.cac import (
    AdditionalDocumentReference,
    InvoiceLine,
    CreditNoteLine,
    LegalMonetaryTotal,
    OrderReference,
    Party,
    PaymentMeans,
    TaxTotal,
)
from libanaf.ubl.ubl_types import NSMAP, NSMAP_CREDIT_NOTE

"""
Pydantic Model for UBL invoices - incomplete (it's huge in reality)

The model itself is huge, will ammend over time based on the invoices I get :)

see: https://www.truugo.com/ubl/2.1/invoice/
     https://docs.oasis-open.org/ubl/os-UBL-2.1/xsd/maindoc/UBL-Invoice-2.1.xsd
"""


class AccountingSupplierParty(BaseXmlModel, tag="AccountingSupplierParty", ns="cac"):  # , nsmap=NSMAP):
    party: Party


class AccountingCustomerParty(BaseXmlModel, tag="AccountingCustomerParty", ns="cac"):  # , nsmap=NSMAP):
    party: Party


class UBLDocument(BaseXmlModel, search_mode="unordered", ns=""):  # , nsmap=NSMAP):
    """Base class for UBL documents like Invoices or CreditNode"""

    ubl_version_id: Optional[str] = element(tag="UBLVersionID", default=None, ns="cbc")  # , nsmap=NSMAP)
    customization_id: Optional[str] = element(tag="CustomizationID", default=None, ns="cbc")  # , nsmap=NSMAP)
    id: str = element(tag="ID", ns="cbc")  # , nsmap=NSMAP)
    issue_date: datetime.date = element(tag="IssueDate", ns="cbc")  # , nsmap=NSMAP)
    issue_time: Optional[datetime.time] = element(tag="IssueTime", default=None, ns="cbc")  # , nsmap=NSMAP)
    note: Optional[List[str]] = element(tag="Note", default=None, ns="cbc")  # , nsmap=NSMAP)
    profile_id: Optional[str] = element(tag="ProfileID", default=None, ns="cbc")  # , nsmap=NSMAP)
    profile_excution_id: Optional[str] = element(tag="ProfileExecutionID", default=None, ns="cbc")  # , nsmap=NSMAP)
    tax_point_date: Optional[str] = element(tag="TaxPointDate", default=None, ns="cbc")  # , nsmap=NSMAP)
    document_currency_code: str = element(tag="DocumentCurrencyCode", ns="cbc")  # , nsmap=NSMAP)
    tax_currency_code: Optional[str] = element(tag="TaxCurrencyCode", default=None, ns="cbc")  # , nsmap=NSMAP)
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
    payment_means: Optional[
        list[PaymentMeans]
    ]  # = element(tag="PaymentMeans", default=None, ns="cac")  # , nsmap=NSMAP)
    tax_total: TaxTotal
    legal_monetary_total: LegalMonetaryTotal
    order_reference: Optional[OrderReference] = None

    def _sanitize_file_name(self, *dirty, glue: str = "_", replace_char: str = "-") -> str:
        import re

        parts: list[str] = list()
        for part in dirty:
            part = part.strip().replace(".", "")
            # part = re.sub(r"[[:space]]", replace_char, part)
            part = re.sub(r"[/\\?`&%*:|\"<>\x7F\x00-\x1F,.\s]", replace_char, part)
            pattern = replace_char + "+"
            part = re.sub(pattern, replace_char, part)

            parts.append(part)

        # dirty = dirty.strip().replace('.', '')
        # clean: str = re.sub(r"[/\\?%*:|\"<>\x7F\x00-\x1F.]\*", "-", dirty.strip())

        return glue.join(parts)

    def tofname(self) -> str:
        supplier_name: str | None = None
        supplier_party: Party = self.accounting_supplier_party.party
        if supplier_party.party_name is not None and supplier_party.party_name.name is not None:
            supplier_name = supplier_party.party_name.name
        elif supplier_party.party_legal_entity is not None:
            supplier_name = supplier_party.party_legal_entity.registration_name

        # supplier_name = supplier_name.replace('.', '')
        # supplier_name = ''.join(letter for letter in supplier_name if (letter.isalnum() or letter.isspace()))

        # supplier_name = supplier_name.strip()
        no: str = self.id  # .strip() #.replace(' ', '-')
        dt = str(self.issue_date)  # .strip()
        amt: str = "{:.2f}".format(self.legal_monetary_total.payable_amount)

        # return self._sanitize_file_name('_'.join([supplier_name, dt, no])) + '_' + amt
        if supplier_name is None:
            raise ValueError("Supplier name was not found")

        return self._sanitize_file_name(supplier_name, dt, no, glue="_") + "_" + amt

    def has_attachment(self) -> bool:
        return (
            self.additional_document_reference is not None
            and self.additional_document_reference.attachment is not None
            and self.additional_document_reference.attachment.embedded_binary_document is not None
        )

    def write_attachment(self, destination: Path) -> None:
        with open(destination, "wb") as dest:
            dest.write(self.additional_document_reference.attachment.embedded_binary_document)  # pyright: ignore


class Invoice(UBLDocument, tag="Invoice", search_mode="unordered", ns="", nsmap=NSMAP):
    due_date: Optional[datetime.date] = element(tag="DueDate", default=None, ns="cbc")  # , nsmap=NSMAP)
    invoice_type_code: Optional[str] = element(tag="InvoiceTypeCode", default=None, ns="cbc")  # , nsmap=NSMAP)
    invoice_line: List[InvoiceLine]


class CreditNote(UBLDocument, tag="CreditNote", search_mode="unordered", ns="", nsmap=NSMAP_CREDIT_NOTE):
    credit_note_type_code: Optional[str] = element(tag="CreditNoteTypeCode", default=None, ns="cbc")
    credit_note_line: List[CreditNoteLine]


def parse_ubl_invoice(xml_path: Path):
    """
    Parse a UBL XML invoice and extract relevant information using pydantic-xml.
    """
    with xml_path.open("r", encoding="utf-8") as file:
        invoice: Invoice = Invoice.from_xml(bytes(file.read(), encoding="utf8"))

    return invoice


def parse_ubl_credit_note(xml_path: Path):
    """
    Parse a UBL XML credit note and extract relevant information using pydantic-xml.
    """
    with xml_path.open("r", encoding="utf-8") as file:
        note: CreditNote = CreditNote.from_xml(bytes(file.read(), encoding="utf8"))

    return note


if __name__ == "__main__":
    console = Console()
    err_console = Console(stderr=True, style="bold red")
    # xml_file = Path("/home/catalin/work/libanaf/dlds/3472340796_4291809720.xml")
    # xml_file = Path("/home/catalin/work/libanaf/dlds/3516049667_4314748999.xml")
    # xml_file = Path("/home/catalin/work/libanaf/dlds/3433627391_4271778395.xml")

    with console.status("Parsing XML files"):
        for xml_file in Path("/home/catalin/work/libanaf/dlds").glob("*.xml"):
            # xml_file = Path("/home/catalin/work/libanaf/invoice-3444171368_4277109404.xml")
            # console.rule(f"[bold green] Parsing file {xml_file}")
            from lxml import etree

            root = etree.parse(str(xml_file)).getroot()
            local_name = etree.QName(root).localname

            try:
                if local_name == "Invoice":
                    invoice: Invoice = parse_ubl_invoice(xml_file)
                elif local_name == "CreditNote":
                    console.print(xml_file)
                    credit_note: CreditNote = parse_ubl_credit_note(xml_file)
                    pprint(credit_note)

                # console.print("SUCCESS")
            except Exception as e:
                err_console.print(f"ERROR parsing file {xml_file}")
                err_console.print(f"ERROR {str(e)}")
                pprint(e)
            # pprint(invoice)
