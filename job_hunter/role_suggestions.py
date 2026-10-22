"""Roles I'd consider: neighboring job titles the master resume genuinely supports.

Claude proposes titles beyond the person's current tracks. Nothing is trusted blindly: every
suggestion must quote at least one phrase that is really on the resume, and a title already
covered by a track is dropped. Ticked roles become new tracks and search terms in the profile.
"""

from __future__ import annotations

import json
import re

import anthropic
from pydantic import BaseModel, Field

from .resume import FALLBACK_BETA, MODEL


class RoleSuggestion(BaseModel):
    title: str = Field(description="A job title, e.g. 'Cybersecurity Analyst'")
    reason: str = Field(description="One sentence on why this resume fits the role")
    evidence: list[str] = Field(description="1-3 short phrases copied exactly from the resume that support the role")
    search_terms: list[str] = Field(default_factory=list, description="2-4 job-board search phrases for this role")


class SuggestionOutput(BaseModel):
    roles: list[RoleSuggestion]


SYSTEM = """You suggest neighboring job titles for a job seeker, based only on their resume.

Rules:
- Suggest roles the resume genuinely supports: the person's real experience, tools and clearance must plausibly cover most of the role. Never suggest a role that would need credentials, degrees or experience the resume lacks.
- Look beyond the person's current target roles: adjacent titles such as security analyst, ISSO/ISSM, IT compliance, program analyst or systems engineer, when the resume supports them.
- Each role gets a one-sentence reason and 1-3 evidence phrases copied EXACTLY from the resume.
- At most 8 roles, best fit first. Do not repeat the roles already listed as current targets."""


def _flat(master: dict) -> str:
    return re.sub(r"\s+", " ", json.dumps(master, ensure_ascii=False)).lower()


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _prompt(master: dict, current: list[str]) -> str:
    resume = {k: v for k, v in master.items() if k not in ("contact", "_comment")}
    return ("Resume (JSON):\n" + json.dumps(resume, indent=1)
            + "\n\nCurrent target roles (do not repeat): " + (", ".join(current) or "none"))


def check(master: dict, output: SuggestionOutput, current: list[str]) -> list[RoleSuggestion]:
    """Keep only roles with evidence really on the resume and not already a track."""
    source = _flat(master)
    known = {_norm(t) for t in current}
    kept, seen = [], set()
    for role in output.roles:
        key = _norm(role.title)
        if not key or key in known or key in seen:
            continue
        proven = [e for e in role.evidence if e.strip() and re.sub(r"\s+", " ", e).strip().lower() in source]
        if not proven:
            continue
        seen.add(key)
        kept.append(role.model_copy(update={"evidence": proven}))
    return kept


def suggest(master: dict, profile, client: anthropic.Anthropic | None = None, model: str = MODEL,
            effort: str = "medium") -> list[RoleSuggestion]:
    current = list(profile.data.get("tracks", {}))
    client = client or anthropic.Anthropic()
    response = client.beta.messages.parse(
        model=model,
        max_tokens=4000,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        output_config={"effort": effort},
        output_format=SuggestionOutput,
        system=[{"type": "text", "text": SYSTEM}],
        messages=[{"role": "user", "content": _prompt(master, current)}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to suggest roles. Try again.")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise RuntimeError("Claude's answer was cut off. Try again.")
    return check(master, response.parsed_output, current)


def add_roles(profile_data: dict, chosen: list[RoleSuggestion]) -> dict:
    """A copy of the profile data with each chosen role as a track and its search terms added."""
    data = json.loads(json.dumps(profile_data))
    tracks, terms = data.setdefault("tracks", {}), data.setdefault("search_terms", [])
    have = {_norm(t) for t in terms}
    for role in chosen:
        if role.title not in tracks:
            words = [re.escape(t.lower()).replace("\\ ", " ") for t in [role.title, *role.search_terms]]
            tracks[role.title] = list(dict.fromkeys(words))
        for term in [role.title, *role.search_terms]:
            if _norm(term) not in have:
                have.add(_norm(term))
                terms.append(term)
    return data
