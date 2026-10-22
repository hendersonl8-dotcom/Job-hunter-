"""What matters to you in a job: how much each factor counts, plus must-haves and never-shows.

Saved under "preferences" in the user's profile. Defaults reproduce the original scoring
(skills 70, clearance/pay/location 10 each; the new factors start at 0 so nothing changes
until the user moves a slider). Scores are rescaled to 0-100 whatever the weights add up to.
"""

from __future__ import annotations

import re

from .models import Job

WEIGHTS = {"skills": 70, "clearance": 10, "pay": 10, "location": 10, "remote": 0, "employer": 0, "seniority": 0}
LABELS = {"skills": "Skills", "clearance": "Clearance", "pay": "Pay", "location": "Location",
          "remote": "Remote / hybrid", "employer": "Employer type", "seniority": "Seniority"}
MAX_WEIGHT = {"skills": 100}  # every other factor tops out at 30

CLEARANCE_MODES = {"hold": "I hold a clearance", "grow": "I'm ready to grow one", "ignore": "Clearance doesn't matter"}
REMOTE_CHOICES = {"any": "No preference", "remote": "Fully remote", "hybrid": "Hybrid is fine", "onsite": "On-site"}
EMPLOYER_TYPES = ["federal", "contractor", "private"]
SENIORITY_LEVELS = ["entry", "mid", "senior", "lead"]

DEFAULTS = {
    "weights": dict(WEIGHTS),
    "clearance_mode": "hold",
    "remote": "any",
    "employer_types": [],  # empty = no preference
    "seniority": [],
    "must_have": [],
    "never_show": [],
}

CONTRACTORS = re.compile(r"\b(leidos|saic|booz allen|hii|huntington ingalls|peraton|caci|boeing|lockheed|northrop|raytheon|"
                         r"general dynamics|serco|saalex|netsimco|parsons|bae systems|l3harris|amentum|kbr|"
                         r"contractor|government contract)\b", re.I)
FEDERAL = re.compile(r"\b(department of|u\.?s\.? (navy|army|air force)|navy|army|naval|usajobs|federal|nasa|"
                     r"veterans affairs|\bva\b|dod|defense (logistics|information)|\bnavsea\b|\bnavfac\b)", re.I)
SENIOR_WORDS = {
    "entry": re.compile(r"\b(entry|junior|jr\.?|associate|intern|trainee|apprentice|i)\b|\bgs-?(5|7|9)\b|\blevel 1\b", re.I),
    "senior": re.compile(r"\b(senior|sr\.?|iii|iv|principal|staff|sme|gs-?(12|13|14))\b|\blevel (3|4)\b", re.I),
    "lead": re.compile(r"\b(lead|manager|director|head of|supervisor|architect|chief)\b", re.I),
    "mid": re.compile(r"\b(ii|mid|gs-?(10|11)|level 2)\b", re.I),
}


def merged(raw: dict | None) -> dict:
    """The saved preferences with every missing setting filled from the defaults."""
    raw = raw or {}
    out = {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULTS.items() if k != "weights"}
    out.update({k: raw[k] for k in out if k in raw})
    out["weights"] = {k: max(0, float(raw.get("weights", {}).get(k, v))) for k, v in WEIGHTS.items()}
    return out


def employer_type(job: Job) -> str:
    """federal, contractor or private, judged from the source, employer name and posting text."""
    if job.source == "usajobs":
        return "federal"
    head = f"{job.company} {job.title}"
    if CONTRACTORS.search(head):
        return "contractor"
    if FEDERAL.search(job.company):
        return "federal"
    if CONTRACTORS.search(job.description[:600]):
        return "contractor"
    return "private"


def seniority(job: Job) -> str:
    """entry, mid, senior or lead from the title, or "" when it doesn't say."""
    for level in ("lead", "senior", "entry", "mid"):
        if SENIOR_WORDS[level].search(job.title):
            return level
    return ""


def work_mode(job: Job) -> str:
    """remote, hybrid, onsite or "" (unknown). Uses the job's work_mode field, else the posting text."""
    mode = str(getattr(job, "work_mode", "") or "").lower()
    if mode in ("remote", "hybrid", "onsite", "on-site"):
        return "onsite" if mode == "on-site" else mode
    text = f"{job.location} {job.title}".lower()
    if "hybrid" in text:
        return "hybrid"
    if "remote" in text:
        return "remote"
    return ""


def hidden_reason(prefs: dict, job: Job) -> str:
    """Why this job is ruled out (a never-show term or a missing must-have), or ""."""
    text = f"{job.title}\n{job.company}\n{job.location}\n{job.description}".lower()
    for term in prefs["never_show"]:
        if term.strip() and term.strip().lower() in text:
            return f"never show: {term.strip()}"
    for term in prefs["must_have"]:
        if term.strip() and term.strip().lower() not in text:
            return f"missing must-have: {term.strip()}"
    return ""


def remote_fraction(prefs: dict, job: Job) -> tuple[float, str]:
    want, mode = prefs["remote"], work_mode(job)
    if want == "any":
        return 1.0, "no preference"
    if not mode:
        return 0.5, "not stated"
    if mode == want:
        return 1.0, mode
    near = {("remote", "hybrid"), ("hybrid", "remote"), ("hybrid", "onsite"), ("onsite", "hybrid")}
    return (0.5 if (want, mode) in near else 0.0), mode


def employer_fraction(prefs: dict, job: Job) -> tuple[float, str]:
    kind = employer_type(job)
    wanted = prefs["employer_types"]
    return (1.0 if not wanted or kind in wanted else 0.0), kind


def seniority_fraction(prefs: dict, job: Job) -> tuple[float, str]:
    level, wanted = seniority(job), prefs["seniority"]
    if not wanted:
        return 1.0, level or "not stated"
    if not level:
        return 0.5, "not stated"
    if level in wanted:
        return 1.0, level
    gap = min(abs(SENIORITY_LEVELS.index(level) - SENIORITY_LEVELS.index(w)) for w in wanted)
    return (0.5 if gap == 1 else 0.0), level
