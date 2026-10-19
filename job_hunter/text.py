"""Turning messy posting text into fields: plain text, pay, clearance, location."""

from __future__ import annotations

import html
import re

HOURS_PER_YEAR = 2080

_TAG = re.compile(r"<[^>]+>")
_BLOCK_TAG = re.compile(r"</?(p|div|br|li|ul|ol|h[1-6]|tr)\b[^>]*>", re.I)
_SPACES = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n\s*\n+")


def html_to_text(raw: str) -> str:
    """Strip HTML to readable text. Greenhouse double-escapes, so unescape first."""
    if not raw:
        return ""
    text = html.unescape(raw)
    text = _BLOCK_TAG.sub("\n", text)
    text = _TAG.sub("", text)
    text = html.unescape(text)
    text = _SPACES.sub(" ", text)
    text = _BLANK_LINES.sub("\n\n", text)
    return "\n".join(line.strip() for line in text.splitlines()).strip()


# $85,000 - $110,000 | $85k–$110k | $45.50 - $55/hr | $120,000 per year
_MONEY = r"\$\s?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s?([kK])?"
_RANGE = re.compile(_MONEY + r"(?:\s*(?:-|–|—|to)\s*" + _MONEY + r")?" + r"(\s*(?:/|per|an|a)\s*(?:hr|hour|year|yr|annum|annually))?", re.I)


def _amount(number: str, k: str | None) -> float:
    value = float(number.replace(",", ""))
    return value * 1000 if k else value


def parse_salary(text: str) -> tuple[float | None, float | None]:
    """Return the first plausible (min, max) annual salary found in text."""
    for m in _RANGE.finditer(text or ""):
        low = _amount(m.group(1), m.group(2))
        high = _amount(m.group(3), m.group(4)) if m.group(3) else low
        unit = (m.group(5) or "").lower()
        hourly = "h" in unit or (high < 300 and not unit)
        if hourly:
            if high < 10:  # "$5" style noise, not pay
                continue
            low, high = low * HOURS_PER_YEAR, high * HOURS_PER_YEAR
        if high < 20_000:  # signing bonuses, fees, small dollar amounts
            continue
        return min(low, high), max(low, high)
    return None, None


_CLEARANCES = [
    ("TS/SCI", re.compile(r"\bTS\s*/\s*SCI\b|top secret\s*/\s*sci|\bSCI\b eligib", re.I)),
    ("Top Secret", re.compile(r"\btop secret\b|\bTS clearance\b", re.I)),
    ("Secret", re.compile(r"\bsecret clearance\b|\bsecret (?:security )?clearance\b|\bactive secret\b|\bobtain (?:and maintain )?(?:a )?secret\b", re.I)),
    ("Public Trust", re.compile(r"\bpublic trust\b", re.I)),
]


def detect_clearance(text: str) -> str:
    for name, pattern in _CLEARANCES:
        if pattern.search(text or ""):
            return name
    return ""


def matches_location(location: str, wanted: list[str], allow_remote: bool = True) -> bool:
    loc = (location or "").lower()
    if not wanted:
        return True
    if allow_remote and "remote" in loc:
        return True
    return any(place.lower() in loc for place in wanted)
