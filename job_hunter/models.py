"""The one record every job source produces."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Job:
    source: str  # greenhouse, lever, usajobs, linkedin, glassdoor, manual
    external_id: str
    title: str
    company: str
    location: str = ""
    url: str = ""
    apply_url: str = ""
    description: str = ""
    salary_min: float | None = None  # always annual, in USD
    salary_max: float | None = None
    clearance: str = ""  # "", "Public Trust", "Secret", "Top Secret", "TS/SCI"
    posted_at: str = ""
    work_mode: str = ""  # "remote", "hybrid", "onsite" or "" when the posting does not say
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    @property
    def key(self) -> str:
        return f"{self.source}:{self.external_id}"
