"""Tell fully remote, hybrid and on-site postings apart from the location and posting text."""

from __future__ import annotations

import re

REMOTE, HYBRID, ONSITE = "remote", "hybrid", "onsite"
MODES = {REMOTE, HYBRID, ONSITE}

_HYBRID = re.compile(r"\bhybrid\b|\b\d\s*(?:-\s*\d\s*)?days?\s*(?:a|per|each|/)\s*(?:week|wk)\b[^.\n]{0,40}\b(?:office|onsite|on-site|in person)"
                     r"|\b(?:office|onsite|on-site)\b[^.\n]{0,30}\b\d\s*(?:-\s*\d\s*)?days?\s*(?:a|per|each|/)\s*(?:week|wk)\b", re.I)
_REMOTE = re.compile(r"\b(?:fully|100%|completely|entirely)[\s-]+remote\b|\bremote[\s-]+first\b|\bremote[\s-]+(?:position|role|job|opportunity)\b"
                     r"|\bthis (?:position|role|job) is remote\b|\bwork(?:ing)? (?:from home|remotely)\b|\btelecommut\w*\b|\bremote\s*\((?:us|usa|u\.s\.|united states)\)", re.I)
_ONSITE = re.compile(r"\bon[\s-]?site\b|\bin[\s-]office\b|\bno telework\b|\bnot eligible for (?:remote|telework)", re.I)


def detect_work_mode(location: str = "", title: str = "", description: str = "", declared: str = "") -> str:
    """Returns "remote", "hybrid", "onsite", or "" when the posting doesn't say."""
    declared = (declared or "").strip().lower().replace("-", "").replace(" ", "")
    if declared in MODES:
        return declared
    where = f"{location} {title}"
    if _HYBRID.search(where):
        return HYBRID
    if re.search(r"\bremote\b", where, re.I):
        return REMOTE
    if _HYBRID.search(description):
        return HYBRID
    if _REMOTE.search(description):
        return REMOTE
    if _ONSITE.search(description):
        return ONSITE
    return ""
