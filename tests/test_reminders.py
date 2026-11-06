from datetime import date

from job_hunter import db, reminders
from job_hunter.models import Job
from job_hunter.scoring import Fit

TODAY = date(2026, 11, 20)


def add(conn, n, applied, status="Applied"):
    job = Job(source="t", external_id=str(n), title=f"Job {n}", company=f"Co {n}")
    db.upsert(conn, job, Fit(score=50, track="IT", matched=[], missing=[], reasons=[]))
    db.mark_applied(conn, job.key, applied)
    db.set_status(conn, job.key, status)
    return job.key


def test_due_after_threshold_only():
    conn = db.connect(":memory:")
    old, new = add(conn, 1, "2026-11-10"), add(conn, 2, "2026-11-18")
    keys = [j["key"] for j in reminders.due(conn, TODAY, 7)]
    assert keys == [old] and new not in keys
    assert reminders.due(conn, TODAY, 12) == []


def test_replies_and_other_statuses_are_not_due():
    conn = db.connect(":memory:")
    replied = add(conn, 1, "2026-11-01")
    db.record_outcome(conn, replied, "Reply", "2026-11-05")
    add(conn, 2, "2026-11-01", status="Interviewing")
    assert reminders.due(conn, TODAY, 7) == []


def test_snooze_and_followed_up():
    conn = db.connect(":memory:")
    k = add(conn, 1, "2026-11-01")
    reminders.snooze(conn, k, 4, TODAY)
    assert reminders.due(conn, TODAY, 7) == []
    assert reminders.due(conn, date(2026, 11, 24), 7)  # snooze over
    reminders.mark_followed_up(conn, k, TODAY)
    assert reminders.due(conn, date(2026, 11, 24), 7) == []  # clock restarted
    assert reminders.due(conn, date(2026, 11, 27), 7)


def test_days_setting_clamped_and_saved():
    assert reminders.load_days() == 7
    reminders.save_days(10)
    assert reminders.load_days() == 10
    reminders.save_days(999)
    assert reminders.load_days() == reminders.MAX_DAYS


def test_template_without_key():
    text = reminders.template({"title": "SysAdmin", "company": "Acme", "applied_days": 8}, "Logan")
    assert "SysAdmin" in text and "Acme" in text and text.rstrip().endswith("Logan")
