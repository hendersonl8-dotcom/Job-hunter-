"""Pull from every configured source, keep jobs in your area, score and save them."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

import requests

from . import db
from .config import Settings
from .models import Job
from .scoring import Profile
from .sources import fetch_greenhouse, fetch_lever, fetch_usajobs
from .text import matches_location


@dataclass
class CollectResult:
    found: int = 0
    added: int = 0
    skipped_location: int = 0
    errors: list[str] = field(default_factory=list)


def save_jobs(conn: sqlite3.Connection, profile: Profile, jobs: list[Job], result: CollectResult, filter_location: bool) -> None:
    for job in jobs:
        if filter_location and not matches_location(job.location, profile.locations, profile.allow_remote):
            result.skipped_location += 1
            continue
        result.found += 1
        if db.upsert(conn, job, profile.score(job)):
            result.added += 1


def collect(settings: Settings, conn: sqlite3.Connection, profile: Profile, session: requests.Session | None = None) -> CollectResult:
    http = session or requests.Session()
    result = CollectResult()

    if settings.usajobs_api_key and settings.usajobs_email:
        for keyword in settings.usajobs_keywords:
            try:
                jobs = fetch_usajobs(keyword, settings.usajobs_api_key, settings.usajobs_email,
                                     settings.usajobs_location, settings.usajobs_radius, session=http)
                save_jobs(conn, profile, jobs, result, filter_location=False)
            except Exception as exc:  # one failing search should not stop the rest
                result.errors.append(f"USAJobs '{keyword}': {exc}")
    elif settings.usajobs_keywords:
        result.errors.append("USAJobs skipped: set USAJOBS_API_KEY and USAJOBS_EMAIL to turn it on.")

    for name in settings.greenhouse_boards:
        try:
            save_jobs(conn, profile, fetch_greenhouse(name, session=http), result, filter_location=True)
        except Exception as exc:
            result.errors.append(f"Greenhouse '{name}': {exc}")

    for name in settings.lever_boards:
        try:
            save_jobs(conn, profile, fetch_lever(name, session=http), result, filter_location=True)
        except Exception as exc:
            result.errors.append(f"Lever '{name}': {exc}")

    return result
