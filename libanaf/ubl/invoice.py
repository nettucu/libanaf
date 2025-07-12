import datetime
from typing import Optional

from pydantic_xml import element

from libanaf.ubl.cac import InvoiceLine
from libanaf.ubl.ubl_document import UBLDocument
from libanaf.ubl.ubl_types import NSMAP


class Invoice(UBLDocument, tag="Invoice", search_mode="unordered", ns="", nsmap=NSMAP):
    """
    Pydantic Model for UBL invoices - incomplete (it's huge in reality)

    The model itself is huge, will ammend over time based on the invoices I get :)

    see: https://www.truugo.com/ubl/2.1/invoice/
        https://docs.oasis-open.org/ubl/os-UBL-2.1/xsd/maindoc/UBL-Invoice-2.1.xsd
    """

    due_date: Optional[datetime.date] = element(tag="DueDate", default=None, ns="cbc")  # , nsmap=NSMAP)
    invoice_type_code: Optional[str] = element(tag="InvoiceTypeCode", default=None, ns="cbc")  # , nsmap=NSMAP)
    invoice_line: list[InvoiceLine]
