"""The Resume builder's logic: pick bullets from your master resume, reword them, and save drafts.

A draft only records choices (which sections and bullets are in, in what order, and any reworded
or added text). compose() turns a draft plus the master resume into the same resume dict the rest
of the app exports, so titles, employers, dates and contact details always come from the master.

Bullet ids: "m3" is the master's fourth bullet for that section, "c0" is the first point you added
yourself. Section keys: "role-0" is the first experience entry, "project-1" the second project.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import userdata

DRAFTS_DIR = "resume_drafts"


def section_key(kind: str, index: int) -> str:
    return f"{kind}-{index}"


def default_draft(master: dict, track: str | None = None) -> dict:
    """Everything in, in master order, with the track's headline and summary."""
    tracks = master.get("tracks", {})
    track = track if track in tracks else next(iter(tracks), "")
    pick = tracks.get(track, {})
    sections = {}
    for kind, items in (("role", master.get("experience", [])), ("project", master.get("projects", []))):
        for i, item in enumerate(items):
            sections[section_key(kind, i)] = {"on": True, "picked": [f"m{j}" for j in range(len(item.get("bullets", [])))]}
    return {
        "track": track,
        "headline": pick.get("headline", ""),
        "summary": pick.get("summary", ""),
        "sections": sections,
        "custom": {},
        "edits": {},
        "skills": {name: list(items) for name, items in master.get("skills", {}).items()},
        "certifications": list(master.get("certifications", [])),
        "education": list(range(len(master.get("education", [])))),
        "awards": list(master.get("awards", [])),
    }


def bullet_options(master: dict, draft: dict, kind: str, index: int) -> dict[str, str]:
    """Every bullet you can pick for one section, id -> current wording (your edit if you made one)."""
    items = master.get("experience" if kind == "role" else "projects", [])
    key = section_key(kind, index)
    edits = draft.get("edits", {})
    options = {f"m{j}": b for j, b in enumerate(items[index].get("bullets", []))}
    options.update({f"c{j}": b for j, b in enumerate(draft.get("custom", {}).get(key, []))})
    return {bid: edits.get(f"{key}:{bid}", text) for bid, text in options.items()}


def compose(master: dict, draft: dict) -> dict:
    """The resume dict (same shape as resume.base_resume) for this draft."""
    def entries(kind: str, items: list[dict]) -> list[dict]:
        out = []
        for i, item in enumerate(items):
            section = draft.get("sections", {}).get(section_key(kind, i), {"on": True, "picked": []})
            if not section.get("on", True):
                continue
            options = bullet_options(master, draft, kind, i)
            bullets = [options[b].strip() for b in section.get("picked", []) if b in options and options[b].strip()]
            out.append({**item, "bullets": bullets})
        return out

    skill_order = list(master.get("skills", {}))
    return {
        "contact": master["contact"],
        "headline": draft.get("headline", ""),
        "summary": draft.get("summary", ""),
        "skills": [{"name": name, "items": draft["skills"][name]}
                   for name in skill_order if draft.get("skills", {}).get(name)],
        "experience": entries("role", master.get("experience", [])),
        "projects": entries("project", master.get("projects", [])),
        "education": [e for i, e in enumerate(master.get("education", [])) if i in draft.get("education", [])],
        "certifications": list(draft.get("certifications", [])),
        "awards": list(draft.get("awards", [])),
    }


# Drafts are kept per profile, in <profile folder>\resume_drafts\<name>.json.

def drafts_dir() -> Path:
    return userdata.user_dir() / DRAFTS_DIR


def clean_draft_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9 _.-]+", "", name).strip(" .")[:80]


def list_drafts() -> list[str]:
    folder = drafts_dir()
    return sorted(p.stem for p in folder.glob("*.json")) if folder.exists() else []


def save_draft(name: str, draft: dict) -> Path:
    name = clean_draft_name(name)
    if not name:
        raise ValueError("Give the draft a name (letters, numbers and spaces).")
    return userdata.write_json(drafts_dir() / f"{name}.json", draft)


def load_draft(name: str) -> dict:
    return json.loads((drafts_dir() / f"{clean_draft_name(name)}.json").read_text(encoding="utf-8"))


def delete_draft(name: str) -> None:
    path = drafts_dir() / f"{clean_draft_name(name)}.json"
    path.unlink(missing_ok=True)
    path.with_suffix(".json.bak").unlink(missing_ok=True)

