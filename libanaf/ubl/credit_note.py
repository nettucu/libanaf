from typing import Optional

from pydantic_xml import element

from libanaf.ubl.cac import CreditNoteLine
from libanaf.ubl.ubl_document import UBLDocument
from libanaf.ubl.ubl_types import NSMAP_CREDIT_NOTE


class CreditNote(UBLDocument, tag="CreditNote", search_mode="unordered", ns="", nsmap=NSMAP_CREDIT_NOTE):
    """
    Implementation of a subset of UBL CreditNote message type. It only implements a small subset of the

    see: https://www.truugo.com/ubl/2.1/creditnote/
    """

    credit_note_type_code: Optional[str] = element(tag="CreditNoteTypeCode", default=None, ns="cbc")
    credit_note_line: list[CreditNoteLine]
