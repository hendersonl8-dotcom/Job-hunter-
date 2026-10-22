"""Job lists saved as CSV, such as the Seattle shortlists researched in the project.

Columns used: title, employer, location, pay_min, pay_max, clearance,
key_requirements (separated by " | "), posting_url, date_posted and notes.
"""

from __future__ import annotations

import csv
import hashlib
import io

from ..models import Job
from ..text import detect_clearance
from .workmode import detect_work_mode


def _number(value: str) -> float | None:
    try:
        return float(value.replace(",", "").replace("$", "")) if value and value.strip() else None
    except ValueError:
        return None


def jobs_from_csv(text: str) -> list[Job]:
    jobs = []
    for row in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
        row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        title, company = row.get("title", ""), row.get("employer") or row.get("company", "")
        if not title:
            continue
        url = row.get("posting_url") or row.get("url", "")
        requirements = [r.strip() for r in row.get("key_requirements", "").split("|") if r.strip()]
        parts = []
        if requirements:
            parts.append("Requirements:\n" + "\n".join(f"- {r}" for r in requirements))
        if row.get("clearance"):
            parts.append(f"Clearance: {row['clearance']}")
        if row.get("notes"):
            parts.append(f"Notes: {row['notes']}")
        jobs.append(Job(
            source="shortlist",
            external_id=hashlib.sha1((url or f"{title}|{company}").encode()).hexdigest()[:16],
            title=title,
            company=company,
            location=row.get("location", ""),
            url=url,
            apply_url=url,
            description="\n\n".join(parts),
            salary_min=_number(row.get("pay_min", "")),
            salary_max=_number(row.get("pay_max", "")),
            clearance=detect_clearance(row.get("clearance", "")),
            posted_at=row.get("date_posted", ""),
            work_mode=detect_work_mode(row.get("location", ""), title, "\n\n".join(parts)),
        ))
    return jobs
