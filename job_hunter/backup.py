"""Timestamped copies of the SQLite database, on demand and before migrations."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

KEEP = 20


def backup_database(path: str | Path, reason: str = "manual", now: datetime | None = None) -> Path | None:
    """Copy the database to <db folder>/backups/ and return the copy, or None if there is nothing to copy.

    Uses SQLite's own backup so the copy is consistent even while the app has the file open.
    Only the newest KEEP copies are kept.
    """
    path = Path(path)
    if str(path) == ":memory:" or not path.exists() or path.stat().st_size == 0:
        return None
    folder = path.parent / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    target = folder / f"{path.stem}-{stamp}-{reason}{path.suffix}"
    source, copy = sqlite3.connect(path), sqlite3.connect(target)
    try:
        source.backup(copy)
    finally:
        copy.close()
        source.close()
    for old in sorted(folder.glob(f"{path.stem}-*{path.suffix}"))[:-KEEP]:
        old.unlink()
    return target
