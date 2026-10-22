"""How well a job fits you, as a 0-100 score you can see the reasons for.

Skills 70 points: of the skills the posting asks for, the weighted share you have.
Clearance 10: you hold TS/SCI, so a posting that requires a clearance is an edge.
Pay 10: meets your floor (10), unknown (5), below it (0).
Location 10: in your area or remote (10), otherwise (0).
Those are the default weights. Preferences (preferences.py) can change them and add remote,
employer type and seniority; the score is always rescaled to 0-100.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from . import preferences as prefs_mod
from .models import Job
from .text import matches_location

CLEARANCE_RANK = {"": 0, "Public Trust": 1, "Secret": 2, "Top Secret": 3, "TS/SCI": 4}


@dataclass
class Evidence:
    """The exact words in a posting that made a skill count."""

    skill: str
    have: bool
    phrase: str
    snippet: str  # the phrase with a little surrounding text
    start: int  # where the phrase begins inside the snippet


@dataclass
class Fit:
    score: int
    track: str
    hidden: str = ""  # why a never-show / must-have rule rules the job out
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
        self.prefs = prefs_mod.merged(data.get("preferences"))

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

    corrections = None  # optional: anything with rejected(job_key) -> set of skill names

    def evidence(self, job: Job, context: int = 60) -> list[Evidence]:
        """For each skill the posting seems to ask for, the first phrase that matched."""
        text = f"{job.title}\n{job.description}"
        found = []
        for name, (pattern, have, _weight) in self.skills.items():
            m = pattern.search(text)
            if not m:
                continue
            lo, hi = max(0, m.start() - context), min(len(text), m.end() + context)
            if lo:  # don't cut a word in half
                lo = text.rfind(" ", 0, lo) + 1
            if hi < len(text):
                end = text.find(" ", hi)
                hi = len(text) if end == -1 else end
            lead = "…" if lo else ""
            snippet = lead + text[lo:hi].replace("\n", " ") + ("…" if hi < len(text) else "")
            start = len(lead) + m.start() - lo
            phrase = snippet[start:start + m.end() - m.start()]
            found.append(Evidence(name, have, phrase, snippet, start))
        return found

    def hidden_reason(self, job: Job) -> str:
        """Small hook for other screens: why the user's rules rule this job out, or ""."""
        return prefs_mod.hidden_reason(self.prefs, job)

    def score(self, job: Job) -> Fit:
        text = f"{job.title}\n{job.description}"
        rejected = self.corrections.rejected(job.key) if self.corrections else set()
        matched, missing, have_weight, want_weight = [], [], 0, 0
        for name, (pattern, have, weight) in self.skills.items():
            if name not in rejected and pattern.search(text):
                want_weight += weight
                if have:
                    have_weight += weight
                    matched.append(name)
                else:
                    missing.append(name)
        w = self.prefs["weights"]
        reasons, earned = [], 0.0

        def add(name: str, fraction: float, why: str) -> None:
            nonlocal earned
            if w[name] <= 0:
                return
            points = fraction * w[name]
            earned += points
            reasons.append(f"{prefs_mod.LABELS[name]} {points:g}/{w[name]:g}: {why}")

        skill_fraction = have_weight / want_weight if want_weight else 0.5
        add("skills", skill_fraction, f"you have {len(matched)} of {len(matched) + len(missing)} it mentions")

        mode = self.prefs["clearance_mode"]
        required = CLEARANCE_RANK.get(job.clearance, 2 if job.clearance else 0)
        if mode == "ignore":
            pass
        elif not required:
            add("clearance", 0.5, "none required")
        elif mode == "hold" and required <= CLEARANCE_RANK.get(self.clearance, 0):
            add("clearance", 1.0, f"wants {job.clearance}, you hold {self.clearance}")
        elif mode == "grow":
            add("clearance", 0.5, f"wants {job.clearance}; you're ready to grow one")
        else:
            add("clearance", 0.0, f"wants {job.clearance}")

        if job.salary_max is None:
            add("pay", 0.5, "not listed")
        elif job.salary_max >= self.min_salary:
            add("pay", 1.0, f"up to ${job.salary_max:,.0f}")
        else:
            add("pay", 0.0, f"tops out at ${job.salary_max:,.0f}, under your ${self.min_salary:,.0f} floor")

        in_area = matches_location(job.location, self.locations, self.allow_remote) if job.location else True
        add("location", 1.0 if in_area else 0.0, job.location or "not listed")
        add("remote", *prefs_mod.remote_fraction(self.prefs, job))
        add("employer", *prefs_mod.employer_fraction(self.prefs, job))
        add("seniority", *prefs_mod.seniority_fraction(self.prefs, job))

        total = sum(w[k] for k in w if not (k == "clearance" and mode == "ignore"))
        score = round(100 * earned / total) if total else 0
        hidden = self.hidden_reason(job)
        if hidden:
            score = 0
            reasons.append(f"Ruled out ({hidden})")

        return Fit(
            score=score,
            track=self.track_for(job),
            hidden=hidden,
            matched=matched,
            missing=missing,
            reasons=reasons,
        )
