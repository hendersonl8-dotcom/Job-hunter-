"""Resume review: score the master resume against target roles and suggest fixes.

Claude proposes; nothing it says is trusted blindly. Every rewrite is run through the
same claim check the cover letter uses, so a suggestion never adds a number, certification
or not-yet-earned skill the master resume lacks. Missing keywords are only ever offered as
"if true, add X", and a keyword the resume already contains is dropped.
"""

from __future__ import annotations

import json
from collections import Counter
from types import SimpleNamespace

import anthropic
from pydantic import BaseModel, Field

from .cover_letter import check_facts
from .resume import FALLBACK_BETA, MODEL


class RoleScore(BaseModel):
    role: str
    score: int = Field(description="0-100: how well the resume reads for this role today")
    reason: str = Field(description="One or two sentences on what drives the score")


class MissingKeyword(BaseModel):
    term: str
    roles: list[str] = Field(default_factory=list, description="Target roles that look for it")
    advice: str = Field(description="Phrase as 'If true, add ...'. Never claim the person has it.")


class WeakBullet(BaseModel):
    original: str = Field(description="The bullet copied exactly from the resume")
    problem: str
    rewrite: str = Field(description="A stronger version using only facts already in the bullet or resume; no new numbers")


class NeedsNumber(BaseModel):
    original: str = Field(description="The bullet copied exactly from the resume")
    question: str = Field(description="What to measure, e.g. 'How many users or machines?'. Do not guess a value.")


class ReviewOutput(BaseModel):
    scores: list[RoleScore]
    missing_keywords: list[MissingKeyword]
    weak_bullets: list[WeakBullet]
    needs_number: list[NeedsNumber]


SYSTEM = """You review a job seeker's resume against the roles they are targeting.

Rules:
- Use only facts in the resume provided. Never invent or suggest inventing employers, titles, tools, certifications, numbers or results.
- Scores: one per target role, 0-100, how well the resume reads for that role right now.
- Missing keywords: terms these roles commonly look for that the resume does not contain. Always phrase advice as "If true, add ...". Never say the person has them.
- Weak bullets: bullets that are vague, passive or duty-only. Quote the original exactly. Rewrite using only facts already in the resume and add no numbers.
- Needs a number: bullets whose claim would be stronger with a figure (people, machines, time, money). Quote the original exactly and ask what to measure. Do not supply a value.
- Be selective: at most 8 keywords, 6 weak bullets and 6 needs-a-number items, most important first."""


def target_roles(profile) -> list[str]:
    return list(profile.data.get("tracks", {}))


def posting_gaps(jobs: list[dict], limit: int = 12) -> list[tuple[str, int]]:
    """Skills most often missing across saved, non-skipped postings."""
    counts = Counter(s for j in jobs if j.get("status") != "Skipped" for s in j.get("missing") or [])
    return counts.most_common(limit)


def _flat(master: dict) -> str:
    return json.dumps(master, ensure_ascii=False).lower()


def _prompt(master: dict, roles: list[str], gaps: list[tuple[str, int]]) -> str:
    resume = {k: v for k, v in master.items() if k not in ("contact", "_comment")}
    text = "Resume (JSON):\n" + json.dumps(resume, indent=1) + "\n\nTarget roles: " + ", ".join(roles)
    if gaps:
        text += "\n\nSkills most often missing across the person's saved postings: " + ", ".join(
            f"{name} ({n})" for name, n in gaps)
    return text


def check(master: dict, output: ReviewOutput, profile=None) -> tuple[ReviewOutput, list[str]]:
    """Drop or hold back anything the master resume does not support. Returns (output, notes)."""
    notes: list[str] = []
    source = _flat(master)
    out = output.model_copy(deep=True)
    out.scores = [s.model_copy(update={"score": max(0, min(100, s.score))}) for s in out.scores]

    kept = []
    for k in out.missing_keywords:
        if k.term.strip().lower() in source:
            continue  # already on the resume, so not missing
        kept.append(k)
    out.missing_keywords = kept

    bullets = []
    for b in out.weak_bullets:
        wording = check_facts(master, _as_letter(b.rewrite), profile)
        if wording:
            notes.append(f"Held back a rewrite because it adds something your resume lacks: {wording[0]}")
            b = b.model_copy(update={"rewrite": ""})
        bullets.append(b)
    out.weak_bullets = bullets
    return out, notes


def _as_letter(text: str):
    # check_facts only reads .paragraphs
    return SimpleNamespace(paragraphs=[text])


def review(master: dict, profile, jobs: list[dict] | None = None, client: anthropic.Anthropic | None = None,
           model: str = MODEL, effort: str = "medium") -> tuple[ReviewOutput, list[str], list[tuple[str, int]]]:
    """Review the master resume. Returns (checked output, notes, saved-posting skill gaps)."""
    roles = target_roles(profile)
    if not roles:
        raise ValueError("Your profile has no target roles yet. Add job families in profile.json first.")
    gaps = posting_gaps(jobs or [])
    client = client or anthropic.Anthropic()
    response = client.beta.messages.parse(
        model=model,
        max_tokens=8000,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        output_config={"effort": effort},
        output_format=ReviewOutput,
        system=[{"type": "text", "text": SYSTEM}],
        messages=[{"role": "user", "content": _prompt(master, roles, gaps)}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to review this resume. Try again.")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise RuntimeError("Claude's answer was cut off before the review was complete. Try again.")
    checked, notes = check(master, response.parsed_output, profile)
    return checked, notes, gaps
