import datetime
from pathlib import Path
from typing import List, Optional

from pydantic_xml import BaseXmlModel, element, wrapped
from rich.pretty import pprint

from libanaf.ubl.cac import (
    AdditionalDocumentReference,
    InvoiceLine,
    LegalMonetaryTotal,
    OrderReference,
    Party,
    PaymentMeans,
    TaxTotal,
)
from libanaf.ubl.types import NSMAP

"""
Pydantic Model for UBL invoices - incomplete (it's huge in reality)

The model itself is huge, will ammend over time based on the invoices I get :)

see: https://www.truugo.com/ubl/2.1/invoice/
     https://docs.oasis-open.org/ubl/os-UBL-2.1/xsd/maindoc/UBL-Invoice-2.1.xsd
"""

class AccountingSupplierParty(BaseXmlModel, tag='AccountingSupplierParty', ns='cac', nsmap=NSMAP):
    party: Party

class AccountingCustomerParty(BaseXmlModel, tag='AccountingCustomerParty', ns='cac', nsmap=NSMAP):
    party: Party


class Invoice(BaseXmlModel, tag='Invoice', search_mode='unordered', ns='', nsmap=NSMAP):
    ubl_version_id: Optional[str] = element(tag='UBLVersionID', default=None, ns='cbc', nsmap=NSMAP)
    customization_id: Optional[str] = element(tag='CustomizationID', default=None, ns='cbc', nsmap=NSMAP)
    profile_id: Optional[str] = element(tag='ProfileID', default=None, ns='cbc', nsmap=NSMAP)
    profile_excution_id: Optional[str] = element(tag='ProfileExecutionID', default=None, ns='cbc', nsmap=NSMAP)
    id: str = element(tag='ID', ns='cbc', nsmap=NSMAP)
    issue_date: datetime.date = element(tag='IssueDate', ns = 'cbc', nsmap=NSMAP)
    issue_time: Optional[datetime.time] = element(tag='IssueTime', default=None, ns = 'cbc', nsmap=NSMAP)
    due_date: Optional[datetime.date] = element(tag='DueDate', default=None, ns = 'cbc', nsmap=NSMAP)
    invoice_type_code: Optional[str] = element(tag='InvoiceTypeCode', default=None, ns = 'cbc', nsmap=NSMAP)
    note: Optional[List[str]] = element(tag='Note', default=None, ns='cbc', nsmap=NSMAP)
    tax_point_date: Optional[str] = element(tag='TaxPointDate', default=None, ns='cbc', nsmap=NSMAP)
    document_currency_code: str = element(tag='DocumentCurrencyCode', ns = 'cbc', nsmap=NSMAP)
    order_reference: Optional[OrderReference] = None
    contract_document_reference: Optional[str] = wrapped('ContractDocumentReference', ns='cac', nsmap=NSMAP, default=None,
                                              entity=element(tag='ID', default=None, ns='cbc', nsmap=NSMAP))
    additional_document_reference: Optional[AdditionalDocumentReference] = None
    tax_currency_code: Optional[str] = element(tag='DocumentCurrencyCode', default=None, ns = 'cbc', nsmap=NSMAP)
    accounting_supplier_party: AccountingSupplierParty
    accounting_customer_party: AccountingCustomerParty
    payment_means: List[PaymentMeans] = element(tag='PaymentMeans', default=None, ns='cac', nsmap=NSMAP)
    tax_total: TaxTotal
    legal_monetary_total: LegalMonetaryTotal
    invoice_line: List[InvoiceLine]

    def _sanitize_file_name(self, *dirty, glue: str = '_', replace_char: str = '-') -> str:
        import re

        parts: list[str] = list()
        for part in dirty:
            part = part.strip().replace('.', '')
            # part = re.sub(r"[[:space]]", replace_char, part)
            part = re.sub(r"[/\\?`&%*:|\"<>\x7F\x00-\x1F,.\s]", replace_char, part)
            pattern = replace_char + "+"
            part = re.sub(pattern, replace_char, part)

            parts.append(part)

        # dirty = dirty.strip().replace('.', '')
        # clean: str = re.sub(r"[/\\?%*:|\"<>\x7F\x00-\x1F.]\*", "-", dirty.strip())

        return glue.join(parts)

    def tofname(self) -> str:
        supplier_party: Party = self.accounting_supplier_party.party
        if supplier_party.party_name is not None and supplier_party.party_name.name is not None:
            supplier_name: str = supplier_party.party_name.name
        elif supplier_party.party_legal_entity is not None:
            supplier_name: str = supplier_party.party_legal_entity.registration_name


        # supplier_name = supplier_name.replace('.', '')
        # supplier_name = ''.join(letter for letter in supplier_name if (letter.isalnum() or letter.isspace()))

        # supplier_name = supplier_name.strip()
        no: str = self.id # .strip() #.replace(' ', '-')
        dt = str(self.issue_date) # .strip()
        amt: str = '{:.2f}'.format(self.legal_monetary_total.payable_amount)

        # return self._sanitize_file_name('_'.join([supplier_name, dt, no])) + '_' + amt
        return self._sanitize_file_name(supplier_name, dt, no, glue='_') + '_' + amt

    def has_attachment(self) -> bool:
        return self.additional_document_reference is not None and \
                self.additional_document_reference.attachment is not None and \
                self.additional_document_reference.attachment.embedded_binary_document is not None

    def write_attachment(self, destination: Path) -> None:
        with open(destination, 'wb') as dest:
            dest.write(self.additional_document_reference.attachment.embedded_binary_document)

def parse_ubl_invoice(xml_path: Path):
    """
    Parse a UBL XML invoice and extract relevant information using pydantic-xml.
    """
    with xml_path.open('r', encoding='utf-8') as file:
        invoice: Invoice = Invoice.from_xml(bytes(file.read(), encoding="utf8"))
    
    return invoice

if __name__ == "__main__":
    # xml_file = Path("/home/catalin/work/libanaf/dlds/3472340796_4291809720.xml")
    # xml_file = Path("/home/catalin/work/libanaf/dlds/3516049667_4314748999.xml")
    # xml_file = Path("/home/catalin/work/libanaf/dlds/3433627391_4271778395.xml")
    xml_file = Path("/home/catalin/work/libanaf/dlds/3444171368_4277109404.xml")
    invoice: Invoice = parse_ubl_invoice(xml_file)
    pprint(invoice)
