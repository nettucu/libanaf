from pathlib import Path

from lxml import etree
from rich.pretty import pprint

NSMAP: dict[str, str] = {
    "": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "ns4": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    "udt": "urn:oasis:names:specification:ubl:schema:xsd:UnqualifiedDataTypes-2",
    "ccts": "urn:un:unece:uncefact:documentation:2",
    "qdt": "urn:oasis:names:specification:ubl:schema:xsd:QualifiedDataTypes-2",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}


def main() -> None:
    xml_file = Path("/home/catalin/work/libanaf/dlds/3427868701_4268760695.xml")

    parser = etree.XMLParser()
    with xml_file.open("r", encoding="utf8") as stream:
        root = etree.fromstring(bytes(stream.read(), encoding="utf8"), parser)

    xml = etree.tostring(root, pretty_print=True)
    pprint(xml.decode())


if __name__ == "__main__":
    main()
