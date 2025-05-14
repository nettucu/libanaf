from pathlib import Path
from typing import cast
from libanaf.ubl.invoice import Invoice
from libanaf.ubl.ubl_document import UBLDocument, parse_ubl_document


def test_parse_invoice():
    app_home = Path(__file__).parent.parent.resolve()
    sample_xml_file = app_home / "docs/samples/invoice-3444171368_4277109404.xml"

    invoice: Invoice = cast(Invoice, parse_ubl_document(sample_xml_file))
    assert invoice.id == "POKA W 9262655"


def test_all_ubl_documents():
    app_home = Path(__file__).parent.parent.resolve()
    for f in app_home.glob("dlds/*.xml"):
        try:
            ubl_document: UBLDocument = parse_ubl_document(f)
            assert ubl_document.id is not None
        except Exception as e:
            print(f"Failed file: {str(f)}")
            raise e
