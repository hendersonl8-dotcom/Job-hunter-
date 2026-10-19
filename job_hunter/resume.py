"""Resumes: the master facts, a base version per track, and a tailored version per job.

Tailoring asks Claude to reorder, trim and reword your own bullets toward one
posting. It never takes titles, employers, dates, education or contact details
from the model, and every number or skill it writes is checked against your
master resume so an invented fact shows up as a warning.
"""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

import anthropic
from pydantic import BaseModel, Field

MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class SkillGroup(BaseModel):
    name: str
    items: list[str]


class Role(BaseModel):
    source_index: int = Field(description="Index of this role in the master resume's experience list")
    bullets: list[str]


class Project(BaseModel):
    source_index: int = Field(description="Index of this project in the master resume's projects list")
    bullets: list[str]


class TailoredResume(BaseModel):
    headline: str
    summary: str
    skills: list[SkillGroup]
    experience: list[Role]
    projects: list[Project]
    certifications: list[str]
    changes: list[str] = Field(description="Plain-English list of what you changed for this job and why")
    gaps: list[str] = Field(description="Requirements in the posting the master resume cannot honestly cover")


SYSTEM = """You tailor a job seeker's resume to one job posting.

Rules:
- Use only facts in the master resume. Never invent employers, titles, dates, tools, certifications, numbers or results.
- You may reorder, merge, shorten and reword bullets, and mirror the posting's vocabulary where it truthfully describes the same work.
- Lead each role with the bullets most relevant to this posting; drop the least relevant so the resume fits on two pages (at most 6 bullets for the most relevant role, 4 for others).
- Keep every role in the master resume, referenced by its source_index. Keep projects that help this posting.
- Skills: group them, order by relevance to the posting, and list only skills the master resume supports.
- Certifications: keep the master list; put the most relevant first.
- Write a headline and a 2-3 sentence summary aimed at this posting. If the posting values a security clearance, say the clearance early.
- In changes, explain each meaningful change in one plain sentence. In gaps, list what the posting asks for that the master resume cannot honestly claim."""


def load_master(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def base_resume(master: dict, track: str) -> dict:
    """Your resume for a track, with nothing tailored: every bullet, track headline and summary."""
    tracks = master.get("tracks", {})
    pick = tracks.get(track) or tracks.get("Other") or {"headline": "", "summary": ""}
    return {
        "contact": master["contact"],
        "headline": pick["headline"],
        "summary": pick["summary"],
        "skills": [{"name": k, "items": v} for k, v in master.get("skills", {}).items()],
        "experience": [dict(role) for role in master.get("experience", [])],
        "projects": [dict(p) for p in master.get("projects", [])],
        "education": master.get("education", []),
        "certifications": master.get("certifications", []),
        "awards": master.get("awards", []),
    }


def assemble(master: dict, tailored: TailoredResume) -> dict:
    """Merge the model's choices with the fixed facts from the master resume."""
    roles = master.get("experience", [])
    projects = master.get("projects", [])
    experience, seen = [], set()
    for role in tailored.experience:
        if 0 <= role.source_index < len(roles) and role.source_index not in seen:
            seen.add(role.source_index)
            experience.append({**roles[role.source_index], "bullets": role.bullets})
    # A role the model dropped comes back untailored: a gap in your history looks worse than a long resume.
    for i, role in enumerate(roles):
        if i not in seen:
            experience.insert(min(i, len(experience)), dict(role))
    return {
        "contact": master["contact"],
        "headline": tailored.headline,
        "summary": tailored.summary,
        "skills": [g.model_dump() for g in tailored.skills],
        "experience": experience,
        "projects": [
            {**projects[p.source_index], "bullets": p.bullets}
            for p in tailored.projects if 0 <= p.source_index < len(projects)
        ],
        "education": master.get("education", []),
        "certifications": tailored.certifications,
        "awards": master.get("awards", []),
    }


_NUMBER = re.compile(r"\d[\d,.]*\+?%?")


def _norm_number(token: str) -> str:
    return token.rstrip(".,").replace(",", "")


def check_facts(master: dict, resume: dict) -> list[str]:
    """Warnings for numbers and skills in the tailored resume that the master resume doesn't contain."""
    source = json.dumps(master, ensure_ascii=False)
    source_numbers = {_norm_number(n) for n in _NUMBER.findall(source)}
    source_lower = source.lower()
    warnings = []
    texts = [resume["headline"], resume["summary"]]
    texts += [b for role in resume["experience"] for b in role["bullets"]]
    texts += [b for project in resume["projects"] for b in project["bullets"]]
    for text in texts:
        for number in _NUMBER.findall(text):
            if _norm_number(number) not in source_numbers:
                warnings.append(f"Check the number {number!r} in: {text}")
    for group in resume["skills"]:
        for item in group["items"]:
            if item.lower() not in source_lower:
                warnings.append(f"Check the skill {item!r}: it isn't in your master resume")
    for cert in resume["certifications"]:
        if cert.lower() not in source_lower:
            warnings.append(f"Check the certification {cert!r}: it isn't in your master resume")
    return warnings


def job_prompt(job: dict) -> str:
    return (
        f"Job title: {job['title']}\nCompany: {job['company']}\nLocation: {job.get('location', '')}\n"
        f"Clearance: {job.get('clearance') or 'not stated'}\n"
        f"Skills it asks for that the resume has: {', '.join(job.get('matched') or []) or 'none detected'}\n"
        f"Skills it asks for that the resume lacks: {', '.join(job.get('missing') or []) or 'none detected'}\n\n"
        f"Posting:\n{job.get('description', '')}"
    )


def tailor(master: dict, job: dict, client: anthropic.Anthropic | None = None, model: str = MODEL,
           effort: str = "high") -> tuple[dict, TailoredResume, list[str]]:
    """Tailor the master resume to one job. Returns (resume, model output, fact warnings)."""
    client = client or anthropic.Anthropic()
    master_for_model = {k: v for k, v in master.items() if k not in ("contact", "_comment")}
    response = client.beta.messages.parse(
        model=model,
        max_tokens=16000,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        output_config={"effort": effort},
        output_format=TailoredResume,
        system=[{"type": "text", "text": SYSTEM}],
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Master resume (JSON):\n" + json.dumps(master_for_model, indent=1),
                 "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": job_prompt(job)},
            ],
        }],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to tailor this resume. Try again or edit the posting text.")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise RuntimeError("Claude's answer was cut off before the resume was complete. Try again.")
    tailored = response.parsed_output
    resume = assemble(master, tailored)
    return resume, tailored, check_facts(master, resume)


def resume_lines(resume: dict) -> list[str]:
    """The resume as plain lines, for diffs and plain-text export."""
    lines = [resume["headline"], "", resume["summary"], "", "SKILLS"]
    lines += [f"{g['name']}: {', '.join(g['items'])}" for g in resume["skills"]]
    lines += ["", "EXPERIENCE"]
    for role in resume["experience"]:
        lines.append(f"{role['title']}, {role['org']} ({role['dates']})")
        lines += [f"- {b}" for b in role["bullets"]]
    if resume["projects"]:
        lines += ["", "PROJECTS"]
        for project in resume["projects"]:
            lines.append(project["name"])
            lines += [f"- {b}" for b in project["bullets"]]
    lines += ["", "CERTIFICATIONS"] + [f"- {c}" for c in resume["certifications"]]
    return lines


def diff(before: dict, after: dict) -> list[tuple[str, str]]:
    """Line diff as (kind, text) pairs, kind one of ' ', '+', '-'."""
    out = []
    for line in difflib.ndiff(resume_lines(before), resume_lines(after)):
        if line[:1] in (" ", "+", "-"):
            out.append((line[0], line[2:]))
    return out
