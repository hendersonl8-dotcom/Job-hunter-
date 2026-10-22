"""Pull from every configured source, keep jobs in your areas, score and save them."""

from __future__ import annotations

import copy
import sqlite3
from dataclasses import dataclass, field

import requests

from . import db
from .config import Settings
from .models import Job
from .scoring import Profile
from .sources import AREAS, fetch_greenhouse, fetch_lever, fetch_usajobs
from .sources.areas import Area
from .text import matches_location


@dataclass
class CollectResult:
    found: int = 0
    added: int = 0
    skipped_location: int = 0
    errors: list[str] = field(default_factory=list)


def resolve_areas(names: list[str]) -> list[Area]:
    """Preset names become their presets; anything else is a custom place searched by that name."""
    areas = []
    for name in dict.fromkeys(n.strip() for n in names if n.strip()):
        areas.append(AREAS.get(name) or Area(name, name, (name.split(",")[0].strip(),)))
    return areas


def keep_by_mode(job: Job, remote_mode: str) -> bool:
    if remote_mode == "only":
        return job.work_mode == "remote"
    if remote_mode == "onsite":
        return job.work_mode != "remote"
    return True


def save_jobs(conn: sqlite3.Connection, profile: Profile, jobs: list[Job], result: CollectResult, filter_location: bool,
              terms: list[str] | None = None, remote_mode: str = "include") -> None:
    for job in jobs:
        if not keep_by_mode(job, remote_mode):
            result.skipped_location += 1
            continue
        if filter_location:
            if job.work_mode == "remote" and remote_mode != "onsite":
                in_place = True
            elif terms is None:  # one area from the profile, as before areas existed
                in_place = matches_location(job.location, profile.locations, profile.allow_remote)
            else:
                in_place = matches_location(job.location, terms, allow_remote=False)
            if not in_place:
                result.skipped_location += 1
                continue
        result.found += 1
        if db.upsert(conn, job, profile.score(job)):
            result.added += 1


def _scoring_profile(profile: Profile, areas: list[Area], remote_mode: str) -> Profile:
    """The profile as scored for this search: its places include the searched areas and remote follows the mode."""
    scored = copy.copy(profile)
    scored.locations = list(dict.fromkeys([*profile.locations, *(t for a in areas for t in a.terms)]))
    scored.allow_remote = remote_mode != "onsite"
    return scored


def collect(settings: Settings, conn: sqlite3.Connection, profile: Profile, session: requests.Session | None = None) -> CollectResult:
    http = session or requests.Session()
    result = CollectResult()
    mode = settings.remote_mode
    areas = resolve_areas(settings.areas)
    if areas:
        profile = _scoring_profile(profile, areas, mode)
        terms = [t for a in areas for t in a.terms]
        searches = [(a.usajobs_location, False) for a in areas]
    else:
        terms = None
        searches = [(settings.usajobs_location, False)]
    if mode == "only":
        searches = [("", True)]  # remote jobs anywhere, so no place to search

    if settings.usajobs_api_key and settings.usajobs_email:
        for keyword in settings.usajobs_keywords:
            for place, remote_only in searches:
                label = "remote" if remote_only else place
                try:
                    jobs = fetch_usajobs(keyword, settings.usajobs_api_key, settings.usajobs_email, place,
                                         settings.usajobs_radius, remote_only=remote_only, session=http)
                    save_jobs(conn, profile, jobs, result, filter_location=False, remote_mode=mode)
                except Exception as exc:  # one failing search should not stop the rest
                    result.errors.append(f"USAJobs '{keyword}' ({label}): {exc}")
    elif settings.usajobs_keywords:
        result.errors.append("USAJobs skipped: add your USAJobs key and email under 'USAJobs key' to turn it on.")

    # a board that fails (wrong name, moved to another system) only reports for itself
    for name in settings.greenhouse_boards:
        try:
            save_jobs(conn, profile, fetch_greenhouse(name, session=http), result, True, terms, mode)
        except Exception as exc:
            result.errors.append(f"Greenhouse '{name}': {exc}")

    for name in settings.lever_boards:
        try:
            save_jobs(conn, profile, fetch_lever(name, session=http), result, True, terms, mode)
        except Exception as exc:
            result.errors.append(f"Lever '{name}': {exc}")

    return result
