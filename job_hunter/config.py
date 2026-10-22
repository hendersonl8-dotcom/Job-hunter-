"""Settings from config/settings.toml, with secrets from environment variables.

Personal files (profile, resume, database) are in the per-user folder; see userdata.py."""

from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import userdata

ROOT = userdata.ROOT
SEARCH_FILE = "search.json"
REMOTE_MODES = ("onsite", "include", "only")


def load_search_prefs() -> dict:
    """What the Find jobs screen saved: USAJobs key and email, keywords, location, boards."""
    path = userdata.user_dir() / SEARCH_FILE
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_search_prefs(prefs: dict) -> Path:
    return userdata.write_json(userdata.user_dir() / SEARCH_FILE, prefs)


@dataclass
class Settings:
    database: Path
    profile: Path
    resume: Path = Path("resume.json")
    claude_model: str = "claude-opus-5-5"
    claude_effort: str = "high"
    usajobs_keywords: list[str] = field(default_factory=list)
    usajobs_location: str = "Seattle, Washington"
    usajobs_radius: int = 60
    greenhouse_boards: list[str] = field(default_factory=list)
    lever_boards: list[str] = field(default_factory=list)
    areas: list[str] = field(default_factory=list)  # preset names (sources/areas.py) or place names; empty = usajobs_location only
    remote_mode: str = "include"  # "onsite" (no remote), "include" (on-site plus remote), "only" (remote only)
    usajobs_api_key: str = ""
    usajobs_email: str = ""


def load_settings(path: str | Path | None = None) -> Settings:
    path = Path(path or os.environ.get("JOB_HUNTER_SETTINGS", ROOT / "config" / "settings.toml"))
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    home = userdata.user_dir()
    paths, usajobs, boards = data.get("paths", {}), data.get("usajobs", {}), data.get("boards", {})
    claude = data.get("claude", {})
    saved = load_search_prefs()
    return Settings(
        database=home / paths.get("database", userdata.DATABASE_FILE),
        profile=home / paths.get("profile", userdata.PROFILE_FILE),
        resume=home / paths.get("resume", userdata.RESUME_FILE),
        claude_model=claude.get("model", "claude-opus-5-5"),
        claude_effort=claude.get("effort", "high"),
        usajobs_keywords=saved.get("keywords") or usajobs.get("keywords", []),
        usajobs_location=saved.get("location") or usajobs.get("location", "Seattle, Washington"),
        usajobs_radius=int(usajobs.get("radius_miles", 60)),
        greenhouse_boards=_union(boards.get("greenhouse", []), _saved_boards(saved, "greenhouse")),
        lever_boards=_union(boards.get("lever", []), _saved_boards(saved, "lever")),
        areas=list(saved.get("areas") or []),
        remote_mode=saved.get("remote_mode") if saved.get("remote_mode") in REMOTE_MODES else "include",
        usajobs_api_key=os.environ.get("USAJOBS_API_KEY") or saved.get("usajobs_api_key", ""),
        usajobs_email=os.environ.get("USAJOBS_EMAIL") or saved.get("usajobs_email", ""),
    )


def _saved_boards(saved: dict, source: str) -> list[str]:
    return [key.split(":", 1)[1] for key in saved.get("boards", []) if key.startswith(source + ":")]


def _union(*lists: list[str]) -> list[str]:
    return list(dict.fromkeys(name for items in lists for name in items))
