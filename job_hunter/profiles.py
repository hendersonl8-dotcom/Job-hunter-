"""Named profiles: one person per profile, each with a private subfolder under the data folder.

    <root>/profiles/<name>/   profile.json, resume.json, search.json, jobs.db, backups, ...
    <root>/keys.json          shared: the computer owner's Claude key
    <root>/active_profile.txt which profile the app opens

The first time a pre-profiles install runs, everything it kept in the root is moved into
profiles/Main (renamed, never rewritten). Nothing is ever deleted by switching or adding.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from . import userdata

BAD_CHARS = re.compile(r"[^A-Za-z0-9 _.-]")


class ProfileError(ValueError):
    """The name can't be used; the message is fit to show the person."""


def profiles_root(root: Path | None = None) -> Path:
    return (root or userdata.root_dir()) / userdata.PROFILES_DIR


def profile_dir(name: str, root: Path | None = None) -> Path:
    return profiles_root(root) / name


def list_profiles(root: Path | None = None) -> list[str]:
    folder = profiles_root(root)
    names = sorted((p.name for p in folder.iterdir() if p.is_dir()), key=str.lower) if folder.exists() else []
    return names or [userdata.DEFAULT_PROFILE]


def active_profile(root: Path | None = None) -> str:
    root = root or userdata.root_dir()
    marker = root / userdata.ACTIVE_FILE
    name = marker.read_text(encoding="utf-8").strip() if marker.exists() else ""
    names = list_profiles(root)
    if name in names:
        return name
    return userdata.DEFAULT_PROFILE if userdata.DEFAULT_PROFILE in names else names[0]


def set_active(name: str, root: Path | None = None) -> None:
    root = root or userdata.root_dir()
    if name not in list_profiles(root):
        raise ProfileError(f"There is no profile called {name}.")
    (root / userdata.ACTIVE_FILE).write_text(name, encoding="utf-8")


def clean_name(name: str) -> str:
    name = BAD_CHARS.sub("", (name or "")).strip(" .")
    if not name:
        raise ProfileError("Give the profile a name, using letters or numbers.")
    return name[:40]


def create_profile(name: str, root: Path | None = None, make_active: bool = True) -> str:
    """Make an empty profile (the welcome screen builds it from that person's resume)."""
    root = root or userdata.root_dir()
    name = clean_name(name)
    if any(p.name.lower() == name.lower() for p in profiles_root(root).glob("*")):
        raise ProfileError(f"A profile called {name} already exists.")
    profile_dir(name, root).mkdir(parents=True)
    if make_active:
        set_active(name, root)
    return name


def adopt_existing_data(root: Path) -> list[str]:
    """Move what a pre-profiles install kept in the root into profiles/Main. Runs once; never overwrites."""
    movable = [p for p in root.iterdir() if p.name not in userdata.SHARED]
    if not movable:
        return []
    target = profile_dir(userdata.DEFAULT_PROFILE, root)
    target.mkdir(parents=True, exist_ok=True)
    moved = []
    for item in movable:
        if not (target / item.name).exists():
            shutil.move(str(item), str(target / item.name))
            moved.append(item.name)
    return moved
