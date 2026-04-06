"""Persistent failure counter for sync runs.

Tracks consecutive network failures across systemd invocations by storing
state in a small JSON file.  Auth failures (token expired) are handled
separately and do not use this counter.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SyncState:
    """Mutable state persisted between sync runs."""

    network_failures: int = 0


def _load(path: Path) -> SyncState:
    try:
        if path.exists():
            raw = json.loads(path.read_text())
            return SyncState(network_failures=int(raw.get("network_failures", 0)))
    except Exception as exc:
        logger.warning(f"Could not read sync state file {path}: {exc}")
    return SyncState()


def _save(path: Path, state: SyncState) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(state), indent=2))
    except Exception as exc:
        logger.warning(f"Could not write sync state file {path}: {exc}")


def record_network_failure(state_file: Path, threshold: int) -> bool:
    """Increment the consecutive network failure count.

    Args:
        state_file: Path to the JSON state file.
        threshold: Number of consecutive failures after which True is returned.

    Returns:
        bool: True when the failure count has reached (or exceeded) *threshold*.
    """
    state = _load(state_file)
    state.network_failures += 1
    _save(state_file, state)
    logger.warning(f"Network failure #{state.network_failures} recorded (threshold: {threshold})")
    return state.network_failures >= threshold


def record_success(state_file: Path) -> None:
    """Reset the consecutive network failure count after a successful sync.

    Args:
        state_file: Path to the JSON state file.
    """
    state = _load(state_file)
    if state.network_failures > 0:
        logger.info(f"Sync succeeded; resetting failure counter (was {state.network_failures})")
        _save(state_file, SyncState())
