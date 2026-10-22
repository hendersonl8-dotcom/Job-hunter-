"""Lever public postings: https://api.lever.co/v0/postings/<company>?mode=json"""

from __future__ import annotations

from datetime import datetime, timezone

import requests

from ..models import Job
from ..text import HOURS_PER_YEAR, detect_clearance, html_to_text, parse_salary
from .workmode import detect_work_mode

API = "https://api.lever.co/v0/postings/{company}"


def _salary(item: dict, description: str) -> tuple[float | None, float | None]:
    salary = item.get("salaryRange") or {}
    if salary.get("min") or salary.get("max"):
        low = salary.get("min") or salary.get("max")
        high = salary.get("max") or low
        if "hour" in (salary.get("interval") or "").lower():
            low, high = low * HOURS_PER_YEAR, high * HOURS_PER_YEAR
        return float(low), float(high)
    return parse_salary(description)


def parse_lever(payload: list, company: str) -> list[Job]:
    jobs = []
    for item in payload:
        sections = [item.get("descriptionPlain", "")]
        for block in item.get("lists", []):
            sections.append(f"{block.get('text', '')}\n{html_to_text(block.get('content', ''))}")
        sections.append(item.get("additionalPlain", ""))
        description = "\n\n".join(s.strip() for s in sections if s and s.strip())
        low, high = _salary(item, description)
        created = item.get("createdAt")
        categories = item.get("categories") or {}
        title = item.get("text", "").strip()
        location = categories.get("location", "") or item.get("workplaceType", "")
        jobs.append(
            Job(
                source="lever",
                external_id=item["id"],
                title=title,
                company=company,
                location=location,
                url=item.get("hostedUrl", ""),
                apply_url=item.get("applyUrl") or item.get("hostedUrl", ""),
                description=description,
                salary_min=low,
                salary_max=high,
                clearance=detect_clearance(description),
                work_mode=detect_work_mode(location, title, description, item.get("workplaceType", "")),
                posted_at=datetime.fromtimestamp(created / 1000, timezone.utc).isoformat() if created else "",
            )
        )
    return jobs


def fetch_lever(company: str, session: requests.Session | None = None, timeout: int = 30) -> list[Job]:
    http = session or requests.Session()
    response = http.get(API.format(company=company), params={"mode": "json"}, timeout=timeout)
    response.raise_for_status()
    return parse_lever(response.json(), company)
