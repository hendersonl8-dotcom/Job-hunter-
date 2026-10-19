"""Settings from config/settings.toml, with secrets from environment variables.

Personal files (profile, resume, database) are in the per-user folder; see userdata.py."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import userdata

ROOT = userdata.ROOT


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
    usajobs_api_key: str = ""
    usajobs_email: str = ""


def load_settings(path: str | Path | None = None) -> Settings:
    path = Path(path or os.environ.get("JOB_HUNTER_SETTINGS", ROOT / "config" / "settings.toml"))
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    home = userdata.user_dir()
    paths, usajobs, boards = data.get("paths", {}), data.get("usajobs", {}), data.get("boards", {})
    claude = data.get("claude", {})
    return Settings(
        database=home / paths.get("database", userdata.DATABASE_FILE),
        profile=home / paths.get("profile", userdata.PROFILE_FILE),
        resume=home / paths.get("resume", userdata.RESUME_FILE),
        claude_model=claude.get("model", "claude-opus-5-5"),
        claude_effort=claude.get("effort", "high"),
        usajobs_keywords=usajobs.get("keywords", []),
        usajobs_location=usajobs.get("location", "Seattle, Washington"),
        usajobs_radius=int(usajobs.get("radius_miles", 60)),
        greenhouse_boards=boards.get("greenhouse", []),
        lever_boards=boards.get("lever", []),
        usajobs_api_key=os.environ.get("USAJOBS_API_KEY", ""),
        usajobs_email=os.environ.get("USAJOBS_EMAIL", ""),
    )
