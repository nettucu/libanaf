import logging
import zipfile
from pathlib import Path
from typing import Any

import typer
from lxml.etree import ParseError, XMLSyntaxError
from pydantic import ValidationError

from libanaf.config import Configuration

from ..ubl.invoice import Invoice

config: dict[str, Any] = Configuration().load_config()
logger: logging.Logger = logging.getLogger(__name__)


def convert_xml_to_pdf(xml_path: Path, pdf_path: Path):
    """
    Convert an XML file to a PDF file. This is a placeholder function.
    """
    # TODO: Integrate actual service to convert XML to PDF
    invoice: Invoice | None = None
    with xml_path.open("r", encoding="utf8") as xml_file:
        try:
            # logger.debug(f"Processing {xml_path}")
            invoice = Invoice.from_xml(bytes(xml_file.read(), encoding="utf8"))
        except ValidationError as e:
            logger.error(f"Invoice {xml_path}: {e}")
        except XMLSyntaxError as e:
            logger.error(f"XML Syntax error {xml_path}: {e}")
        except ParseError as e:
            logger.error(f"XML Parse error {xml_path}: {e}")
        except Exception as e:
            logger.error(f"XML UNKNOWN error {xml_path}: {e}")

    if invoice is not None:
        fname = invoice.tofname()
        logger.debug(f"fname = {fname}")

    # with pdf_path.open("w") as pdf_file:
    #     pdf_file.write(f"PDF content for {xml_path}\n{content}")

def convert_invoices(download_dir: Path) -> None:
    for xml_file in download_dir.glob("*.xml"):
        pdf_file: Path = download_dir / (xml_file.stem + ".pdf")
        convert_xml_to_pdf(xml_file, pdf_file)

def unzip_invoices(download_dir: Path) -> None:
    for zip_file in download_dir.glob("*.zip"):
        try:
            with zipfile.ZipFile(zip_file, 'r') as zip_handle:
                for member_info in zip_handle.infolist():
                    if member_info.filename.startswith("semnatura"):
                        # ignore XML signature file
                        continue

                    new_dest = download_dir / (zip_file.stem + "_" + member_info.filename)
                    if not new_dest.exists():
                        typer.echo(f"Extracting {member_info.filename} to {new_dest}", color = True)
                        extracted = Path(zip_handle.extract(member=member_info, path=download_dir))
                        extracted.rename(new_dest)
        except zipfile.BadZipFile as e:
            # the zip file is malformed
            logger.error(f"Zip File {zip_file} is malformed: {e}. Moving on ...")


def process_invoices():
    """
    Process downloaded invoices: unpack the zip file and convert XML to PDF.
    """
    download_dir = Path(config['storage']['download_directory'])

    unzip_invoices(download_dir=download_dir)
    convert_invoices(download_dir=download_dir)
