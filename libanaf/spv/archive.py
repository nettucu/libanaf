"""Local archive of SPV message PDFs: ``<dir>/<cif>/<YYYY-MM>/<YYYY-MM-DD>_<tip>_<id>.pdf``."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from libanaf.exceptions import AnafRequestError
from libanaf.spv.client import SpvClient, SpvMessage

logger = logging.getLogger(__name__)


@dataclass
class ArchiveResult:
    """Outcome of :func:`download_new`.

    Attributes:
        total: Messages returned by SPV for the requested window.
        downloaded: Paths of the PDFs written by this run.
        failed: ``"<id>: <error>"`` for messages SPV refused to serve.
    """

    total: int = 0
    downloaded: list[Path] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


def message_path(target: Path, message: SpvMessage) -> Path:
    """Return the archive path of a message PDF.

    Args:
        target: Archive root directory.
        message: SPV inbox message.

    Returns:
        ``<target>/<cif>/<YYYY-MM>/<YYYY-MM-DD>_<tip>_<id>.pdf`` (spaces in ``tip`` become ``-``).
    """
    stamp = message.data_creare
    return (
        target / message.cif / f"{stamp:%Y-%m}" / f"{stamp:%Y-%m-%d}_{message.tip.replace(' ', '-')}_{message.id}.pdf"
    )


def stored_ids(target: Path) -> set[str]:
    """Return the message ids already archived under ``target``.

    Args:
        target: Archive root directory (may not exist yet).

    Returns:
        Set of ``id`` values taken from the file names.
    """
    return {p.stem.rsplit("_", 1)[-1] for p in target.rglob("*.pdf")} if target.exists() else set()


def download_new(client: SpvClient, target: Path, days: int = 60, cif: str | None = None) -> ArchiveResult:
    """Download inbox PDFs that are not archived yet.

    Args:
        client: SPV client with a valid session.
        target: Archive root directory.
        days: Look-back window in days (SPV keeps 60).
        cif: Optional CUI/CNP filter.

    Returns:
        What was listed, written and refused.

    Raises:
        SpvSessionError: When the session expires (from the client); files written so far are kept.
        AnafRequestError: When the inbox listing itself fails.
    """
    messages: list[SpvMessage] = client.list_messages(days, cif).mesaje
    known: set[str] = stored_ids(target)
    result = ArchiveResult(total=len(messages))
    for message in messages:
        if message.id in known:
            continue
        try:
            pdf: bytes = client.download(message.id)
        except AnafRequestError as e:
            logger.warning(f"SPV message {message.id} not downloaded: {e}")
            result.failed.append(f"{message.id}: {e}")
            continue
        path: Path = message_path(target, message)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pdf)
        result.downloaded.append(path)
    return result
