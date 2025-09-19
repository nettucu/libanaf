from pathlib import Path


def is_invoice_downloaded(message: dict[str, str], download_dir: Path) -> bool:
    """
    Check if an invoice is already downloaded.
    """
    invoice_id: str = message["id"]
    id_solicitare: str = message["id_solicitare"]

    possible_filenames = [f"{invoice_id}.zip", f"{id_solicitare}.zip", f"efactura_{id_solicitare}.zip"]

    return any((download_dir / filename).exists() for filename in possible_filenames)
