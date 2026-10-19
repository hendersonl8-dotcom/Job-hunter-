"""USAJobs search API (federal jobs, including JBLM, Kitsap and the VA).

Needs a free API key from https://developer.usajobs.gov/apirequest/ and the email
you registered it with.
"""

from __future__ import annotations

import requests

from ..models import Job
from ..text import HOURS_PER_YEAR, detect_clearance

API = "https://data.usajobs.gov/api/search"


def _annual(value: str, interval: str) -> float | None:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    return amount * HOURS_PER_YEAR if interval == "PH" else amount


def parse_usajobs(payload: dict) -> list[Job]:
    jobs = []
    for item in payload.get("SearchResult", {}).get("SearchResultItems", []):
        d = item.get("MatchedObjectDescriptor", {})
        details = (d.get("UserArea") or {}).get("Details") or {}
        pay = (d.get("PositionRemuneration") or [{}])[0]
        interval = pay.get("RateIntervalCode", "PA")
        description = "\n\n".join(
            part for part in [
                details.get("JobSummary", ""),
                "Duties:\n" + "\n".join(details.get("MajorDuties") or []) if details.get("MajorDuties") else "",
                d.get("QualificationSummary", ""),
            ] if part
        )
        clearance = details.get("SecurityClearance", "")
        clearance = detect_clearance(clearance) or ("" if clearance in ("", "Not Required", "Not Applicable") else clearance)
        apply_urls = d.get("ApplyURI") or []
        jobs.append(
            Job(
                source="usajobs",
                external_id=str(d.get("PositionID") or item.get("MatchedObjectId")),
                title=d.get("PositionTitle", ""),
                company=" / ".join(x for x in [d.get("DepartmentName", ""), d.get("OrganizationName", "")] if x),
                location=d.get("PositionLocationDisplay", ""),
                url=d.get("PositionURI", ""),
                apply_url=apply_urls[0] if apply_urls else d.get("PositionURI", ""),
                description=description,
                salary_min=_annual(pay.get("MinimumRange"), interval),
                salary_max=_annual(pay.get("MaximumRange"), interval),
                clearance=clearance or detect_clearance(description),
                posted_at=d.get("PublicationStartDate", ""),
            )
        )
    return jobs


def fetch_usajobs(
    keyword: str,
    api_key: str,
    email: str,
    location: str = "Seattle, Washington",
    radius_miles: int = 60,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> list[Job]:
    http = session or requests.Session()
    response = http.get(
        API,
        params={"Keyword": keyword, "LocationName": location, "Radius": radius_miles, "ResultsPerPage": 100},
        headers={"Host": "data.usajobs.gov", "User-Agent": email, "Authorization-Key": api_key},
        timeout=timeout,
    )
    response.raise_for_status()
    return parse_usajobs(response.json())
