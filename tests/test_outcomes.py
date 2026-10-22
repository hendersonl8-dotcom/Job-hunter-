import sqlite3

import pytest

from job_hunter import db, outcomes_tab
from job_hunter.models import Job
from job_hunter.scoring import Fit

OLD_SCHEMA = """
CREATE TABLE jobs (key TEXT PRIMARY KEY, source TEXT NOT NULL, external_id TEXT NOT NULL, title TEXT NOT NULL,
    company TEXT NOT NULL, location TEXT, url TEXT, apply_url TEXT, description TEXT, salary_min REAL, salary_max REAL,
    clearance TEXT, posted_at TEXT, fetched_at TEXT, score INTEGER, track TEXT, matched TEXT, missing TEXT, reasons TEXT,
    status TEXT NOT NULL DEFAULT 'New', notes TEXT NOT NULL DEFAULT '');
CREATE TABLE documents (id INTEGER PRIMARY KEY AUTOINCREMENT, job_key TEXT NOT NULL, kind TEXT NOT NULL,
    content TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')));
INSERT INTO jobs (key, source, external_id, title, company, track, status, notes)
    VALUES ('a:1', 'a', '1', 'SysAdmin', 'Acme', 'IT Admin', 'Interviewing', 'keep me');
"""


def add_job(conn, n, track, status="Applied", tailored=False):
    job = Job(source="t", external_id=str(n), title=f"Job {n}", company=f"Co {n}")
    db.upsert(conn, job, Fit(score=50, track=track, matched=[], missing=[], reasons=[]))
    db.set_status(conn, job.key, status)
    if tailored:
        db.save_document(conn, job.key, "resume", {})
    return job.key


def test_old_database_migrates_without_losing_data(tmp_path):
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript(OLD_SCHEMA)
    old.commit()
    old.close()
    conn = db.connect(path)
    job = conn.execute("SELECT * FROM jobs").fetchone()
    assert (job["title"], job["status"], job["notes"]) == ("SysAdmin", "Interviewing", "keep me")
    assert db.outcomes_for(conn, "a:1") == []
    db.record_outcome(conn, "a:1", "Interview", "2026-11-02")
    db.connect(path)  # reopening is harmless
    assert len(db.outcomes_for(conn, "a:1")) == 1


def test_record_and_delete_outcome():
    conn = db.connect(":memory:")
    key = add_job(conn, 1, "IT Admin")
    with pytest.raises(ValueError):
        db.record_outcome(conn, key, "Ghosted", "2026-11-01")
    db.record_outcome(conn, key, "Reply", "2026-11-01", "recruiter email")
    (row,) = db.outcomes_for(conn, key)
    assert row["note"] == "recruiter email"
    db.delete_outcome(conn, row["id"])
    assert db.outcomes_for(conn, key) == []


def test_rates_by_track_and_resume_version():
    conn = db.connect(":memory:")
    a = add_job(conn, 1, "IT Admin", tailored=True)
    b = add_job(conn, 2, "IT Admin")
    c = add_job(conn, 3, "Data Analyst", status="Rejected")
    d = add_job(conn, 4, "Data Analyst", status="Offer", tailored=True)
    add_job(conn, 5, "Data Analyst", status="Saved")  # never applied: not counted
    db.record_outcome(conn, a, "Interview", "2026-11-01")
    db.record_outcome(conn, b, "Reply", "2026-11-01")
    apps = db.application_rows(conn)
    assert len(apps) == 4

    by_track = {r["Group"]: r for r in outcomes_tab.summarize(apps, "track")}
    assert by_track["IT Admin"]["Applied"] == 2
    assert (by_track["IT Admin"]["Response"], by_track["IT Admin"]["Interview"], by_track["IT Admin"]["Offer"]) == (2, 1, 0)
    # a rejection is a response; an offer from status alone implies a response and an interview
    assert (by_track["Data Analyst"]["Response"], by_track["Data Analyst"]["Interview"], by_track["Data Analyst"]["Offer"]) == (2, 1, 1)
    assert by_track["Data Analyst"]["Offer rate"] == "50%"

    by_version = {r["Group"]: r for r in outcomes_tab.summarize(apps, "version")}
    assert by_version["Tailored"]["Applied"] == 2 and by_version["Tailored"]["Interview rate"] == "100%"
    assert by_version["Base resume"]["Applied"] == 2 and by_version["Base resume"]["Interview rate"] == "0%"


def test_edit_outcome():
    conn = db.connect(":memory:")
    key = add_job(conn, 1, "IT Admin")
    db.record_outcome(conn, key, "Reply", "2026-11-01")
    (row,) = db.outcomes_for(conn, key)
    db.update_outcome(conn, row["id"], "Interview", "2026-11-03", "phone screen")
    (row,) = db.outcomes_for(conn, key)
    assert (row["kind"], row["happened_on"], row["note"]) == ("Interview", "2026-11-03", "phone screen")
    with pytest.raises(ValueError):
        db.update_outcome(conn, row["id"], "Ghosted", "2026-11-03")
    assert db.application_rows(conn)[0]["logged"] == {"Interview"}


def test_company_research_is_shared_per_company_and_editable():
    from job_hunter import company_research as cr

    conn = db.connect(":memory:")
    add_job(conn, 1, "IT Admin")
    assert cr.get(conn, "Co 1")["about"] == "" and cr.researched(conn) == set()
    cr.save(conn, "Co 1", {"about": " Defense contractor ", "bogus": "x"})
    assert cr.get(conn, "  co 1 ")["about"] == "Defense contractor"
    assert cr.researched(conn) == {"co 1"}
    cr.save(conn, "CO 1", {"about": "Defense contractor", "questions": "Team size?"})
    notes = cr.get(conn, "Co 1")
    assert notes["questions"] == "Team size?" and notes["name"] == "Co 1"
    cr.save(conn, "Brand New Inc", {"news": "Won a Navy contract"})
    assert cr.companies(conn) == ["Brand New Inc", "Co 1"]
    cr.delete(conn, "co 1")
    assert cr.researched(conn) == {"brand new inc"}
    with pytest.raises(ValueError):
        cr.save(conn, "  ", {})
