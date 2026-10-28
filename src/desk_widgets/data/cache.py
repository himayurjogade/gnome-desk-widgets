"""Last-good data on disk, so widgets still show something when offline."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def cache_dir() -> Path:
    """Directory holding the cache files."""
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "desk-widgets"


def save(key: str, payload: Any) -> None:
    """Store ``payload`` under ``key``, ignoring any write error."""
    path = cache_dir() / f"{key}.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"saved": time.time(), "data": payload}))
    except OSError as exc:
        log.warning("cache: cannot write %s (%s)", path, exc)


def load(key: str) -> tuple[Any | None, float]:
    """Return ``(payload, age_seconds)``, or ``(None, 0.0)`` if there is none."""
    path = cache_dir() / f"{key}.json"
    try:
        blob = json.loads(path.read_text())
        return blob["data"], max(time.time() - float(blob["saved"]), 0.0)
    except (OSError, ValueError, KeyError):
        return None, 0.0
