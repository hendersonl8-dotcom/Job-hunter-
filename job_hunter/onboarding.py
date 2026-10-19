"""First-run setup: build a profile and master resume from an uploaded resume.

Claude reads the resume text and returns structured facts. Nothing it returns is
trusted blindly: skills, numbers and contact details that do not appear in the
uploaded text are dropped or flagged, so the master resume only holds facts that
were really in the file. The user reviews and edits before anything is saved.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import anthropic
from pydantic import BaseModel, Field

from job_hunter import userdata
from job_hunter.resume import FALLBACK_BETA, MODEL

MAX_CHARS = 60000


class Contact(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    location: str = ""
    clearance: str = Field("", description="Security clearance exactly as the resume states it, else empty")


class Track(BaseModel):
    name: str = Field(description="A short job family the person fits, e.g. 'Data Analyst'")
    title_words: list[str] = Field(description="Plain job-title words that mark this family in postings")
    headline: str
    summary: str = Field(description="2-3 sentences using only facts in the resume")


class Skill(BaseModel):
    name: str
    group: str = Field(description="Short group name such as Systems, Cloud, Data, Tools")
    aliases: list[str] = Field(default_factory=list, description="Other spellings used in job postings")


class Role(BaseModel):
    title: str
    org: str
    location: str = ""
    dates: str = ""
    bullets: list[str]


class Project(BaseModel):
    name: str
    link: str = ""
    bullets: list[str]


class Education(BaseModel):
    name: str
    detail: str = ""
    dates: str = ""


class ExtractedResume(BaseModel):
    contact: Contact
    tracks: list[Track] = Field(description="One to four job families the resume supports")
    skills: list[Skill]
    experience: list[Role]
    projects: list[Project] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    awards: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list, description="Cities or regions the person lives in or is clearly targeting")


SYSTEM = """You read a job seeker's resume and extract it into structured facts.

Rules:
- Use only what the resume text says. Never invent employers, titles, dates, tools, certifications, numbers or results.
- Copy contact details, titles, employers, dates, education and certifications as written.
- Keep each role's bullets close to the original wording; you may fix obvious extraction breaks (a bullet split across lines).
- Skills: list tools, technologies and methods the resume names. Do not add skills it does not name.
- Tracks: one to four job families the resume honestly supports. Headline and summary use only facts from the resume.
- Leave a field empty when the resume does not say."""


def extract_text(name: str, data: bytes) -> str:
    """Plain text from an uploaded PDF or DOCX."""
    suffix = Path(name).suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader
        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
    elif suffix == ".docx":
        from docx import Document
        doc = Document(io.BytesIO(data))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            parts += [cell.text for row in table.rows for cell in row.cells]
        text = "\n".join(parts)
    else:
        raise ValueError("Upload a PDF or Word (.docx) resume.")
    text = text.strip()
    if len(text) < 80:
        raise ValueError("Could not read text from that file. If it is a scan, upload a version with selectable text.")
    return text[:MAX_CHARS]


def extract(text: str, client: anthropic.Anthropic | None = None, model: str = MODEL,
            effort: str = "medium") -> ExtractedResume:
    client = client or anthropic.Anthropic()
    response = client.beta.messages.parse(
        model=model,
        max_tokens=16000,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        output_config={"effort": effort},
        output_format=ExtractedResume,
        system=[{"type": "text", "text": SYSTEM}],
        messages=[{"role": "user", "content": "Resume text:\n\n" + text}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to read this resume. Try a different file.")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise RuntimeError("Claude's answer was cut off before the resume was complete. Try again.")
    return response.parsed_output


def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9+#]+", "", s.lower())


_NUMBER = re.compile(r"\d[\d,.]*")


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def verify(facts: ExtractedResume, text: str) -> tuple[ExtractedResume, list[str]]:
    """Drop or flag anything not backed by the uploaded text. Returns (facts, warnings)."""
    warnings: list[str] = []
    squashed = _squash(text)
    text_numbers = {_digits(n) for n in _NUMBER.findall(text)}
    facts = facts.model_copy(deep=True)

    kept = []
    for skill in facts.skills:
        if _squash(skill.name) and _squash(skill.name) in squashed:
            kept.append(skill)
        else:
            warnings.append(f"Dropped skill '{skill.name}': not found in your resume.")
    facts.skills = kept

    c = facts.contact
    if c.email and c.email.lower() not in text.lower():
        warnings.append(f"Cleared email '{c.email}': not found in your resume.")
        c.email = ""
    if c.phone and _digits(c.phone) not in _digits(text):
        warnings.append(f"Cleared phone '{c.phone}': not found in your resume.")
        c.phone = ""
    if c.clearance and _squash(c.clearance) not in squashed:
        warnings.append(f"Cleared clearance '{c.clearance}': not found in your resume.")
        c.clearance = ""

    def check_numbers(label: str, line: str) -> None:
        for token in _NUMBER.findall(line):
            if len(_digits(token)) > 1 and _digits(token) not in text_numbers:
                warnings.append(f"{label} mentions '{token.strip('.,')}', which is not in your resume. Check it.")

    for track in facts.tracks:
        check_numbers(f"Summary for {track.name}", track.summary)
    for role in facts.experience:
        for b in role.bullets:
            check_numbers(role.title, b)
        if _squash(role.org) and _squash(role.org) not in squashed:
            warnings.append(f"Employer '{role.org}' was not found word for word in your resume. Check it.")
    return facts, warnings


def build_resume(facts: ExtractedResume) -> dict:
    """The config/resume.json shape."""
    groups: dict[str, list[str]] = {}
    for s in facts.skills:
        groups.setdefault(s.group or "Skills", []).append(s.name)
    tracks = {t.name: {"headline": t.headline, "summary": t.summary} for t in facts.tracks}
    tracks.setdefault("Other", {"headline": facts.contact.name, "summary": ""})
    return {
        "contact": facts.contact.model_dump(),
        "tracks": tracks,
        "skills": groups,
        "experience": [r.model_dump() for r in facts.experience],
        "projects": [p.model_dump() for p in facts.projects],
        "education": [e.model_dump() for e in facts.education],
        "certifications": facts.certifications,
        "awards": facts.awards,
    }


def build_profile(facts: ExtractedResume, min_salary: float, locations: list[str],
                  allow_remote: bool = True) -> dict:
    """The config/profile.json shape."""
    skills = {
        s.name: {"aliases": [re.escape(a) for a in [s.name, *s.aliases] if a.strip()], "have": True, "weight": 2}
        for s in facts.skills
    }
    return {
        "clearance": facts.contact.clearance,
        "min_salary": int(min_salary),
        "locations": locations,
        "allow_remote": allow_remote,
        "tracks": {t.name: [re.escape(w) for w in t.title_words if w.strip()] for t in facts.tracks if t.title_words},
        "skills": skills,
    }


def needs_onboarding(profile_path: str | Path, resume_path: str | Path) -> bool:
    return not (Path(profile_path).is_file() and Path(resume_path).is_file())


def load_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path: str | Path, data: dict) -> None:
    """The one place onboarding writes config: into the user's data folder (see userdata.py)."""
    userdata.write_json(path, data)
