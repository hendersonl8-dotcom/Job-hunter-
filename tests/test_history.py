import sqlite3
from datetime import datetime

from job_hunter import cover_letter as letters
from job_hunter import db
from job_hunter.backup import KEEP, backup_database
from job_hunter.config import ROOT
from job_hunter.models import Job
from job_hunter.resume import load_master
from job_hunter.scoring import Fit, Profile


def add_job(conn):
    job = Job(source="manual", external_id="1", title="SysAdmin", company="Acme")
    db.upsert(conn, job, Fit(score=50, track="IT / Systems Admin", matched=[], missing=[], reasons=[]))
    return job.key


def test_history_marks_what_was_sent():
    conn = db.connect(":memory:")
    key = add_job(conn)
    db.save_document(conn, key, "resume", {"resume": "v1"})
    db.save_document(conn, key, "cover_letter", {"letter": "v1"})
    db.record_send(conn, key, "2026-10-20")
    db.save_document(conn, key, "resume", {"resume": "v2"})
    history = db.document_history(conn, key)
    assert [(d["kind"], d["content"], d["sent_at"]) for d in history] == [
        ("resume", {"resume": "v2"}, None),
        ("cover_letter", {"letter": "v1"}, "2026-10-20"),
        ("resume", {"resume": "v1"}, "2026-10-20"),
    ]


def test_send_without_documents_records_base_resume():
    conn = db.connect(":memory:")
    key = add_job(conn)
    db.record_send(conn, key, "2026-10-20")
    assert db.document_history(conn, key) == []
    assert conn.execute("SELECT resume_id, letter_id FROM sends").fetchone()[:] == (None, None)


def test_letter_check_flags_certs_and_unearned_skills():
    master = load_master(ROOT / "config" / "resume.json")
    profile = Profile.load(ROOT / "config" / "profile.json")
    clean = letters.CoverLetter(greeting="Hi", paragraphs=["I hold an active TS/SCI clearance."], closing="Thanks")
    assert letters.check_facts(master, clean, profile) == []
    bad = letters.CoverLetter(greeting="Hi", paragraphs=["I am CISSP certified and hold Security+."], closing="Thanks")
    warnings = letters.check_facts(master, bad, profile)
    assert any("CISSP" in w for w in warnings) and any("Security+" in w for w in warnings)


def test_backup_copies_database_and_prunes(tmp_path):
    path = tmp_path / "jobs.db"
    conn = db.connect(path)
    add_job(conn)
    conn.close()
    copy = backup_database(path, now=datetime(2026, 10, 20, 9, 0, 0))
    assert copy.parent == tmp_path / "backups"
    assert sqlite3.connect(copy).execute("SELECT count(*) FROM jobs").fetchone()[0] == 1
    for i in range(KEEP + 3):
        backup_database(path, now=datetime(2026, 10, 21, 9, 0, i))
    assert len(list((tmp_path / "backups").iterdir())) == KEEP
    assert backup_database(tmp_path / "missing.db") is None


def test_old_database_is_backed_up_before_migration(tmp_path):
    path = tmp_path / "jobs.db"
    old = sqlite3.connect(path)
    old.executescript("CREATE TABLE jobs (key TEXT PRIMARY KEY, source TEXT, external_id TEXT, title TEXT, company TEXT);"
                      "INSERT INTO jobs VALUES ('k','s','1','t','c');")
    old.commit()
    old.close()
    db.connect(path).close()
    copies = list((tmp_path / "backups").iterdir())
    assert len(copies) == 1 and "pre-migration" in copies[0].name
    assert sqlite3.connect(copies[0]).execute("SELECT count(*) FROM jobs").fetchone()[0] == 1
    db.connect(path).close()  # already migrated: no second copy
    assert len(list((tmp_path / "backups").iterdir())) == 1
