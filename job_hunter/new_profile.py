"""Start over with a different resume without losing the old one.

The current profile, master resume, search settings and job list are copied into
profiles/<date-time>/ in the user's data folder, then cleared so the welcome screen runs again.
The Claude key stays, since it belongs to the computer's owner. To go back, copy the files from
the archive folder into the data folder (see the README).
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime

from . import userdata
from .config import SEARCH_FILE


def start_new_profile(conn: sqlite3.Connection, now: datetime | None = None):
    """Archive, then clear, the current profile. Returns the archive folder."""
    home = userdata.user_dir()
    archive = home / "profiles" / (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    archive.mkdir(parents=True, exist_ok=True)
    names = (userdata.PROFILE_FILE, userdata.RESUME_FILE, SEARCH_FILE)
    for name in names:
        if (home / name).exists():
            shutil.copy2(home / name, archive / name)
    saved = sqlite3.connect(archive / userdata.DATABASE_FILE)
    try:
        conn.commit()
        conn.backup(saved)  # a consistent copy even though the app has the database open
    finally:
        saved.close()
    for name in names:
        for path in (home / name, home / (name + ".bak")):
            path.unlink(missing_ok=True)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
    conn.execute("PRAGMA foreign_keys = OFF")
    for table in tables:  # emptied rather than deleted: Windows won't delete a database the app has open
        conn.execute(f'DELETE FROM "{table}"')
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")
    return archive
