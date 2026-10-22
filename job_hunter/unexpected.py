"""Unexpected matches: postings that score well on skills but fit none of your tracks."""

from __future__ import annotations

MIN_SCORE = 60
MIN_SKILLS = 3


def unexpected_skills(job: dict, min_score: int = MIN_SCORE, min_skills: int = MIN_SKILLS) -> list[str]:
    """The matched skills if this saved job is an unexpected match, else an empty list."""
    matched = job.get("matched") or []
    if job.get("track") == "Other" and job.get("score", 0) >= min_score and len(matched) >= min_skills:
        return list(matched)
    return []


def unexpected_matches(jobs: list[dict]) -> list[tuple[dict, list[str]]]:
    """Unexpected matches among saved jobs, best score first."""
    found = [(j, s) for j in jobs if j.get("status") != "Skipped" and (s := unexpected_skills(j))]
    return sorted(found, key=lambda pair: pair[0]["score"], reverse=True)
