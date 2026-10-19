"""Greenhouse public job boards: https://boards-api.greenhouse.io/v1/boards/<token>/jobs"""

from __future__ import annotations

import requests

from ..models import Job
from ..text import detect_clearance, html_to_text, parse_salary

API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def parse_greenhouse(payload: dict, token: str) -> list[Job]:
    jobs = []
    for item in payload.get("jobs", []):
        description = html_to_text(item.get("content", ""))
        low, high = parse_salary(description)
        url = item.get("absolute_url", "")
        jobs.append(
            Job(
                source="greenhouse",
                external_id=str(item["id"]),
                title=item.get("title", "").strip(),
                company=item.get("company_name") or token,
                location=(item.get("location") or {}).get("name", ""),
                url=url,
                apply_url=url,
                description=description,
                salary_min=low,
                salary_max=high,
                clearance=detect_clearance(description),
                posted_at=item.get("updated_at", ""),
            )
        )
    return jobs


def fetch_greenhouse(token: str, session: requests.Session | None = None, timeout: int = 30) -> list[Job]:
    http = session or requests.Session()
    response = http.get(API.format(token=token), params={"content": "true"}, timeout=timeout)
    response.raise_for_status()
    return parse_greenhouse(response.json(), token)
