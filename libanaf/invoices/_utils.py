from pathlib import Path


def is_invoice_downloaded(message: dict[str, str], download_dir: Path) -> bool:
    """
    Check if an invoice is already downloaded.
    """
    invoice_id: str = message["id"]
    id_solicitare: str = message["id_solicitare"]

    return ( (download_dir / f"{invoice_id}.zip").exists() or
            (download_dir / f"{id_solicitare}.zip").exists() or
            (download_dir / f"efactura_{id_solicitare}.zip").exists()
            )

