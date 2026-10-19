"""SQLite storage for jobs, their fit score and where you are with each one."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from .models import Job
from .scoring import Fit

STATUSES = ["New", "Saved", "Skipped", "Applied", "Interviewing", "Offer", "Rejected"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    key          TEXT PRIMARY KEY,
    source       TEXT NOT NULL,
    external_id  TEXT NOT NULL,
    title        TEXT NOT NULL,
    company      TEXT NOT NULL,
    location     TEXT,
    url          TEXT,
    apply_url    TEXT,
    description  TEXT,
    salary_min   REAL,
    salary_max   REAL,
    clearance    TEXT,
    posted_at    TEXT,
    fetched_at   TEXT,
    score        INTEGER,
    track        TEXT,
    matched      TEXT,
    missing      TEXT,
    reasons      TEXT,
    status       TEXT NOT NULL DEFAULT 'New',
    notes        TEXT NOT NULL DEFAULT '',
    applied_at   TEXT
);
CREATE INDEX IF NOT EXISTS jobs_dupe ON jobs (lower(title), lower(company));
CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_key     TEXT NOT NULL REFERENCES jobs (key),
    kind        TEXT NOT NULL,  -- resume, cover_letter
    content     TEXT NOT NULL,  -- JSON
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS documents_job ON documents (job_key, kind);
CREATE TABLE IF NOT EXISTS outcomes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_key     TEXT NOT NULL REFERENCES jobs (key),
    kind        TEXT NOT NULL,  -- one of OUTCOMES
    happened_on TEXT NOT NULL,  -- ISO date
    note        TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS outcomes_job ON outcomes (job_key);
"""

OUTCOMES = ["Reply", "Interview", "Offer", "Rejection"]

_JOB_FIELDS = list(Job.__dataclass_fields__)


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
    if "applied_at" not in columns:  # databases created before the Apply button
        conn.execute("ALTER TABLE jobs ADD COLUMN applied_at TEXT")
        conn.commit()
    return conn


def upsert(conn: sqlite3.Connection, job: Job, fit: Fit) -> bool:
    """Insert or refresh a job. Returns True if it is new.

    Your status and notes are never overwritten. A job already saved from another
    source with the same title and company is treated as the same job.
    """
    existing = conn.execute("SELECT key FROM jobs WHERE key = ?", (job.key,)).fetchone()
    if not existing:
        existing = conn.execute(
            "SELECT key FROM jobs WHERE lower(title) = lower(?) AND lower(company) = lower(?)",
            (job.title, job.company),
        ).fetchone()
    values = asdict(job)
    values.update(
        score=fit.score,
        track=fit.track,
        matched=json.dumps(fit.matched),
        missing=json.dumps(fit.missing),
        reasons=json.dumps(fit.reasons),
    )
    if existing:
        values["key"] = existing["key"]
        columns = [c for c in values if c not in ("key", "source", "external_id")]
        conn.execute(
            f"UPDATE jobs SET {', '.join(f'{c} = :{c}' for c in columns)} WHERE key = :key",
            values,
        )
        conn.commit()
        return False
    values["key"] = job.key
    columns = list(values)
    conn.execute(
        f"INSERT INTO jobs ({', '.join(columns)}) VALUES ({', '.join(':' + c for c in columns)})",
        values,
    )
    conn.commit()
    return True


def all_jobs(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM jobs ORDER BY score DESC, fetched_at DESC").fetchall()
    jobs = []
    for row in rows:
        job = dict(row)
        for column in ("matched", "missing", "reasons"):
            job[column] = json.loads(job[column] or "[]")
        jobs.append(job)
    return jobs


def set_status(conn: sqlite3.Connection, key: str, status: str, notes: str | None = None) -> None:
    if status not in STATUSES:
        raise ValueError(f"Unknown status {status!r}")
    if notes is None:
        conn.execute("UPDATE jobs SET status = ? WHERE key = ?", (status, key))
    else:
        conn.execute("UPDATE jobs SET status = ?, notes = ? WHERE key = ?", (status, notes, key))
    conn.commit()


def rescore(conn: sqlite3.Connection, profile) -> int:
    """Re-run scoring on every saved job, e.g. after you edit profile.json."""
    count = 0
    for row in conn.execute("SELECT * FROM jobs").fetchall():
        job = Job(**{f: row[f] for f in _JOB_FIELDS})
        fit = profile.score(job)
        conn.execute(
            "UPDATE jobs SET score = ?, track = ?, matched = ?, missing = ?, reasons = ? WHERE key = ?",
            (fit.score, fit.track, json.dumps(fit.matched), json.dumps(fit.missing), json.dumps(fit.reasons), row["key"]),
        )
        count += 1
    conn.commit()
    return count


def save_document(conn: sqlite3.Connection, job_key: str, kind: str, content: dict) -> None:
    conn.execute("INSERT INTO documents (job_key, kind, content) VALUES (?, ?, ?)", (job_key, kind, json.dumps(content)))
    conn.commit()


def latest_document(conn: sqlite3.Connection, job_key: str, kind: str) -> dict | None:
    row = conn.execute(
        "SELECT content FROM documents WHERE job_key = ? AND kind = ? ORDER BY id DESC LIMIT 1", (job_key, kind)
    ).fetchone()
    return json.loads(row["content"]) if row else None


def mark_applied(conn: sqlite3.Connection, key: str, when: str) -> None:
    """Set the job to Applied, keeping the first date you applied if you press Apply again."""
    conn.execute(
        "UPDATE jobs SET status = 'Applied', applied_at = COALESCE(applied_at, ?) WHERE key = ?", (when, key)
    )
    conn.commit()


def record_outcome(conn: sqlite3.Connection, key: str, kind: str, when: str, note: str = "") -> None:
    """Log something that happened on an application. Does not change the job's status."""
    if kind not in OUTCOMES:
        raise ValueError(f"Unknown outcome {kind!r}")
    conn.execute(
        "INSERT INTO outcomes (job_key, kind, happened_on, note) VALUES (?, ?, ?, ?)", (key, kind, when, note)
    )
    conn.commit()


def outcomes_for(conn: sqlite3.Connection, key: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM outcomes WHERE job_key = ? ORDER BY happened_on, id", (key,)).fetchall()
    return [dict(row) for row in rows]


def delete_outcome(conn: sqlite3.Connection, outcome_id: int) -> None:
    conn.execute("DELETE FROM outcomes WHERE id = ?", (outcome_id,))
    conn.commit()


def application_rows(conn: sqlite3.Connection) -> list[dict]:
    """Every job you applied to, with its track, resume version and the outcomes logged so far."""
    rows = conn.execute(
        """
        SELECT j.key, j.title, j.company, j.track, j.status, j.applied_at,
               EXISTS (SELECT 1 FROM documents d WHERE d.job_key = j.key AND d.kind = 'resume') AS tailored,
               (SELECT group_concat(DISTINCT o.kind) FROM outcomes o WHERE o.job_key = j.key) AS logged
        FROM jobs j
        WHERE j.applied_at IS NOT NULL OR j.status IN ('Applied', 'Interviewing', 'Offer', 'Rejected')
        ORDER BY j.applied_at DESC, j.title
        """
    ).fetchall()
    return [dict(row) | {"logged": set((row["logged"] or "").split(",")) - {""}} for row in rows]
