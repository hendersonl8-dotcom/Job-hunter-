"""Filters for the Jobs tab: quick views like "Saved", and a minimum salary the user picks."""

from __future__ import annotations

from . import db

# Each quick view is the set of statuses it shows. "Open" leaves out jobs you've closed.
VIEWS = {
    "Open": [s for s in db.STATUSES if s not in ("Skipped", "Rejected")],
    "Saved": ["Saved"],
    "Applied": ["Applied", "Interviewing", "Offer"],
    "New": ["New"],
    "All": list(db.STATUSES),
}


def view_label(view: str, jobs: list[dict]) -> str:
    """The view's name with how many jobs are in it, e.g. "Saved (3)"."""
    return f"{view} ({sum(j['status'] in VIEWS[view] for j in jobs)})"


def meets_min_salary(job: dict, min_salary: float, hide_unlisted: bool = False) -> bool:
    """False only when the posting's top pay is under min_salary. Jobs with no pay listed pass unless hide_unlisted."""
    if job["salary_max"] is None:
        return not (hide_unlisted and min_salary > 0)
    return job["salary_max"] >= min_salary
