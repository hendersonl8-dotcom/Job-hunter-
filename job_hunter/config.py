"""Settings from config/settings.toml, with secrets from environment variables."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    database: Path
    profile: Path
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
    paths, usajobs, boards = data.get("paths", {}), data.get("usajobs", {}), data.get("boards", {})
    return Settings(
        database=ROOT / paths.get("database", "data/jobs.db"),
        profile=ROOT / paths.get("profile", "config/profile.json"),
        usajobs_keywords=usajobs.get("keywords", []),
        usajobs_location=usajobs.get("location", "Seattle, Washington"),
        usajobs_radius=int(usajobs.get("radius_miles", 60)),
        greenhouse_boards=boards.get("greenhouse", []),
        lever_boards=boards.get("lever", []),
        usajobs_api_key=os.environ.get("USAJOBS_API_KEY", ""),
        usajobs_email=os.environ.get("USAJOBS_EMAIL", ""),
    )
