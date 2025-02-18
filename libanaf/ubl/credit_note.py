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
from libanaf.ubl.types import NSMAP_CREDIT_NOTE

"""
Pydantic Model for UBL CreditNote - incomplete (it's huge in reality)

The model itself is huge, will ammend over time based on the invoices I get :)

see: https://www.truugo.com/ubl/2.1/creditnote/
     https://docs.oasis-open.org/ubl/os-UBL-2.1/xsd/maindoc/UBL-Invoice-2.1.xsd
"""


class CreditNote(BaseXmlModel, tag="CreditNote", searc_mode="unordered", ns="", nsmap=NSMAP_CREDIT_NOTE):
    ubl_version_id: Optional[str] = element(tag="UBLVersionID", default=None, ns="cbc", nsmap=NSMAP_CREDIT_NOTE)
    customization_id: Optional[str] = element(tag="CustomizationID", default=None, ns="cbc", nsmap=NSMAP_CREDIT_NOTE)
    profile_id: Optional[str] = element(tag="ProfileID", default=None, ns="cbc", nsmap=NSMAP_CREDIT_NOTE)
    issue_date: datetime.date = element(tag="IssueDate", ns="cbc", nsmap=NSMAP_CREDIT_NOTE)
    credit_note_type_code: Optional[int] = element(
        tag="CreditNoteTypeCode", default=None, ns="cbc", nsmap=NSMAP_CREDIT_NOTE
    )
    note: Optional[str] = element(tag="Note", default=None, ns="cbc", nsmap=NSMAP_CREDIT_NOTE)
    tax_currency_code: Optional[str] = element(tag="TaxCurrencyCode", default=None, ns="cbc", nsmap=NSMAP_CREDIT_NOTE)


def parse(xml_file: Path) -> CreditNote:
    """
    Parse a XML CreditNote file and return the Pydantic XML model
    """
    with xml_file.open("r", encoding="utf-8") as file:
        note: CreditNote = CreditNote.from_xml(bytes(file.read(), encoding="utf8"))

    return note


if __name__ == "__main__":
    # xml_file = Path("/home/catalin/work/libanaf/dlds/3472340796_4291809720.xml")
    # xml_file = Path("/home/catalin/work/libanaf/dlds/3516049667_4314748999.xml")
    # xml_file = Path("/home/catalin/work/libanaf/dlds/3433627391_4271778395.xml")
    xml_file = Path("/home/catalin/work/libanaf/credit_note-4710432411.xml")
    note: CreditNote = parse(xml_file)
    pprint(note)
