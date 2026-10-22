"""Jobs you paste in from LinkedIn, Glassdoor, Indeed or anywhere else.

The app never fetches LinkedIn or Glassdoor pages; you paste the description text.
"""

from __future__ import annotations

import hashlib
from urllib.parse import urlparse

from ..models import Job
from ..text import detect_clearance, parse_salary
from .workmode import detect_work_mode

_SITES = {"linkedin.com": "linkedin", "glassdoor.com": "glassdoor", "indeed.com": "indeed"}


def source_from_url(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    for domain, name in _SITES.items():
        if host == domain or host.endswith("." + domain):
            return name
    return "manual"


def job_from_paste(title: str, company: str, description: str, url: str = "", location: str = "") -> Job:
    if not title.strip() or not description.strip():
        raise ValueError("A pasted job needs at least a title and the description text.")
    digest = hashlib.sha1((url.strip() or f"{title}|{company}|{description[:500]}").encode()).hexdigest()[:16]
    low, high = parse_salary(description)
    return Job(
        source=source_from_url(url),
        external_id=digest,
        title=title.strip(),
        company=company.strip(),
        location=location.strip(),
        url=url.strip(),
        apply_url=url.strip(),
        description=description.strip(),
        salary_min=low,
        salary_max=high,
        clearance=detect_clearance(description),
        work_mode=detect_work_mode(location, title, description),
    )
