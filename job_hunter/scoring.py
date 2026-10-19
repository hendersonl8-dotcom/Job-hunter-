"""How well a job fits you, as a 0-100 score you can see the reasons for.

Skills 70 points: of the skills the posting asks for, the weighted share you have.
Clearance 10: you hold TS/SCI, so a posting that requires a clearance is an edge.
Pay 10: meets your floor (10), unknown (5), below it (0).
Location 10: in your area or remote (10), otherwise (0).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from .models import Job
from .text import matches_location

CLEARANCE_RANK = {"": 0, "Public Trust": 1, "Secret": 2, "Top Secret": 3, "TS/SCI": 4}


@dataclass
class Fit:
    score: int
    track: str
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


class Profile:
    def __init__(self, data: dict):
        self.data = data
        self.clearance = data.get("clearance", "")
        self.min_salary = float(data.get("min_salary") or 0)
        self.locations = data.get("locations", [])
        self.allow_remote = data.get("allow_remote", True)

    @classmethod
    def load(cls, path: str | Path) -> "Profile":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    @cached_property
    def skills(self) -> dict[str, tuple[re.Pattern, bool, int]]:
        return {
            name: (re.compile("|".join(spec["aliases"]), re.I), spec.get("have", False), int(spec.get("weight", 1)))
            for name, spec in self.data.get("skills", {}).items()
        }

    @cached_property
    def tracks(self) -> dict[str, re.Pattern]:
        return {name: re.compile("|".join(words), re.I) for name, words in self.data.get("tracks", {}).items()}

    def track_for(self, job: Job) -> str:
        """The track whose title words match first, falling back to the description."""
        for text in (job.title, job.description[:1500]):
            hits = {name: len(p.findall(text)) for name, p in self.tracks.items()}
            best = max(hits, key=hits.get, default="")
            if best and hits[best]:
                return best
        return "Other"

    def score(self, job: Job) -> Fit:
        text = f"{job.title}\n{job.description}"
        matched, missing, have_weight, want_weight = [], [], 0, 0
        for name, (pattern, have, weight) in self.skills.items():
            if pattern.search(text):
                want_weight += weight
                if have:
                    have_weight += weight
                    matched.append(name)
                else:
                    missing.append(name)
        reasons = []
        skill_points = round(70 * have_weight / want_weight) if want_weight else 35
        reasons.append(f"Skills {skill_points}/70: you have {len(matched)} of {len(matched) + len(missing)} it mentions")

        required = CLEARANCE_RANK.get(job.clearance, 2 if job.clearance else 0)
        if not required:
            clearance_points = 5
            reasons.append("Clearance 5/10: none required")
        elif required <= CLEARANCE_RANK.get(self.clearance, 0):
            clearance_points = 10
            reasons.append(f"Clearance 10/10: wants {job.clearance}, you hold {self.clearance}")
        else:
            clearance_points = 0
            reasons.append(f"Clearance 0/10: wants {job.clearance}")

        if job.salary_max is None:
            pay_points = 5
            reasons.append("Pay 5/10: not listed")
        elif job.salary_max >= self.min_salary:
            pay_points = 10
            reasons.append(f"Pay 10/10: up to ${job.salary_max:,.0f}")
        else:
            pay_points = 0
            reasons.append(f"Pay 0/10: tops out at ${job.salary_max:,.0f}, under your ${self.min_salary:,.0f} floor")

        in_area = matches_location(job.location, self.locations, self.allow_remote) if job.location else True
        location_points = 10 if in_area else 0
        reasons.append(f"Location {location_points}/10: {job.location or 'not listed'}")

        return Fit(
            score=skill_points + clearance_points + pay_points + location_points,
            track=self.track_for(job),
            matched=matched,
            missing=missing,
            reasons=reasons,
        )
