"""Where each user's own files live, and the one-time move from the old shared folders.

Everything personal (profile, master resume, database, backups) lives in one folder per
user, outside the project, so updating or re-cloning the app never touches it:

    Windows  %LOCALAPPDATA%\\JobHunter        Linux/Mac  ~/.local/share/job-hunter

Set JOB_HUNTER_HOME to use another folder (for a second profile, or for tests).
The onboarding screen should call load_resume / save_resume / load_profile / save_profile.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .backup import backup_database

ROOT = Path(__file__).resolve().parent.parent
PROFILE_FILE, RESUME_FILE, DATABASE_FILE = "profile.json", "resume.json", "jobs.db"


def user_dir() -> Path:
    """The current user's data folder, created and filled on first use."""
    override = os.environ.get("JOB_HUNTER_HOME")
    if override:
        folder = Path(override).expanduser()
    elif os.name == "nt":
        folder = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "JobHunter"
    else:
        folder = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "job-hunter"
    folder.mkdir(parents=True, exist_ok=True)
    migrate_legacy(folder)
    return folder


def profile_path() -> Path:
    return user_dir() / PROFILE_FILE


def resume_path() -> Path:
    return user_dir() / RESUME_FILE


def database_path() -> Path:
    return user_dir() / DATABASE_FILE


def has_resume() -> bool:
    return resume_path().exists()


def load_resume() -> dict | None:
    """The master resume, or None until onboarding (or a migration) has created it."""
    path = resume_path()
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def save_resume(resume: dict) -> Path:
    return _write_json(resume_path(), resume)


def load_profile() -> dict:
    return json.loads(profile_path().read_text(encoding="utf-8"))


def save_profile(profile: dict) -> Path:
    return _write_json(profile_path(), profile)


def _write_json(path: Path, data: dict) -> Path:
    """Replace the file whole, keeping the previous version as <name>.bak."""
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def migrate_legacy(folder: Path, root: Path = ROOT) -> list[str]:
    """Copy what an older install kept inside the project into the user folder.

    Originals are left where they are, nothing is deleted, and nothing already in the
    user folder is overwritten. A database is backed up (backups\\) before it is copied.
    The project's config/profile.json is the starter scoring profile for everyone. The
    config/resume.json master resume is only carried over for someone who already has a
    database there, so a fresh install never starts with another person's resume.
    """
    done: list[str] = []
    old_db = root / "data" / DATABASE_FILE
    for name, source in (
        (PROFILE_FILE, root / "config" / PROFILE_FILE),
        (RESUME_FILE, root / "config" / RESUME_FILE if old_db.exists() else None),
    ):
        if source and source.exists() and not (folder / name).exists():
            shutil.copy2(source, folder / name)
            done.append(name)
    new_db = folder / DATABASE_FILE
    if old_db.exists() and old_db.stat().st_size and not new_db.exists():
        backup_database(old_db, "pre-move")
        shutil.copy2(old_db, new_db)
        done.append(DATABASE_FILE)
    return done
