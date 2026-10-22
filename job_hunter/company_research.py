"""Research notes kept per company, shared by every job you track at that company."""

from __future__ import annotations

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS company_research (
    company     TEXT PRIMARY KEY,  -- normalized name, see key()
    name        TEXT NOT NULL,     -- the name as you first saw it
    about       TEXT NOT NULL DEFAULT '',
    culture     TEXT NOT NULL DEFAULT '',
    news        TEXT NOT NULL DEFAULT '',
    contacts    TEXT NOT NULL DEFAULT '',
    fit         TEXT NOT NULL DEFAULT '',
    questions   TEXT NOT NULL DEFAULT '',
    links       TEXT NOT NULL DEFAULT '',
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# Field name -> (label, prompt shown in the empty box)
FIELDS = {
    "about": ("What they do", "Products, customers, size, where the team sits"),
    "culture": ("Culture and values", "Mission statements, Glassdoor themes, veteran programs"),
    "news": ("Recent news", "Contracts won, layoffs, new offices, leadership changes"),
    "contacts": ("People", "Recruiter, hiring manager, anyone you know there"),
    "fit": ("Why I fit", "Points to bring up in the letter or interview"),
    "questions": ("Questions to ask", "What you want to learn from them"),
    "links": ("Links", "Careers page, LinkedIn, articles; one per line"),
}


def key(company: str) -> str:
    """Normalize a company name so 'Amazon', 'amazon ' and 'AMAZON' share one set of notes."""
    return " ".join(company.lower().split())


def ensure(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def get(conn: sqlite3.Connection, company: str) -> dict:
    """The notes for a company, or empty notes if you haven't written any."""
    ensure(conn)
    row = conn.execute("SELECT * FROM company_research WHERE company = ?", (key(company),)).fetchone()
    if row:
        return dict(row)
    return {"company": key(company), "name": company.strip(), **{f: "" for f in FIELDS}, "updated_at": None}


def save(conn: sqlite3.Connection, company: str, notes: dict) -> None:
    """Replace the notes for a company. Unknown fields are ignored; missing ones become empty."""
    if not key(company):
        raise ValueError("Company name is empty")
    ensure(conn)
    values = {f: (notes.get(f) or "").strip() for f in FIELDS}
    conn.execute(
        f"""
        INSERT INTO company_research (company, name, {", ".join(FIELDS)})
        VALUES (?, ?, {", ".join("?" for _ in FIELDS)})
        ON CONFLICT (company) DO UPDATE SET
            {", ".join(f"{f} = excluded.{f}" for f in FIELDS)}, updated_at = datetime('now')
        """,
        (key(company), company.strip(), *values.values()),
    )
    conn.commit()


def delete(conn: sqlite3.Connection, company: str) -> None:
    ensure(conn)
    conn.execute("DELETE FROM company_research WHERE company = ?", (key(company),))
    conn.commit()


def researched(conn: sqlite3.Connection) -> set[str]:
    """Normalized names of companies that have at least one note filled in."""
    ensure(conn)
    filled = " OR ".join(f"{f} != ''" for f in FIELDS)
    return {r[0] for r in conn.execute(f"SELECT company FROM company_research WHERE {filled}")}


def companies(conn: sqlite3.Connection) -> list[str]:
    """Every company you track a job at or have notes on, one entry per company, sorted by name."""
    ensure(conn)
    names: dict[str, str] = {}
    for (name,) in conn.execute("SELECT name FROM company_research UNION ALL SELECT company FROM jobs"):
        if key(name):
            names.setdefault(key(name), name.strip())
    return sorted(names.values(), key=str.lower)
