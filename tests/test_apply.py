import io
import sqlite3
from datetime import date
from types import SimpleNamespace

import pytest
from docx import Document

from job_hunter import cover_letter as letters
from job_hunter import db, export
from job_hunter import resume as resumes
from job_hunter.config import ROOT
from job_hunter.sources import job_from_paste
from job_hunter.scoring import Profile


@pytest.fixture
def master():
    return resumes.load_master(ROOT / "config" / "resume.json")


@pytest.fixture
def job():
    return {"key": "lever:1", "title": "IT Project Coordinator", "company": "Fabrikam", "location": "Bellevue, WA",
            "clearance": "Secret", "track": "Project Manager", "matched": ["Jira / Ticketing"], "missing": ["PMP / CAPM"],
            "description": "Coordinate infrastructure projects with stakeholders using Jira."}


def letter(**overrides):
    data = dict(
        greeting="Dear Hiring Manager,",
        paragraphs=[
            "I led the standup of three network enclaves (270 virtual machines) across two bases.",
            "I coordinated contractors through Jira work orders to build a 34-workstation operations center.",
            "I hold an active TS/SCI clearance and can start in January.",
        ],
        closing="Sincerely,",
    )
    data.update(overrides)
    return letters.CoverLetter(**data)


class FakeClient:
    def __init__(self, output, stop_reason="end_turn"):
        self.calls = []
        self.output, self.stop_reason = output, stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self.parse))

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(parsed_output=self.output, stop_reason=self.stop_reason)


def test_write_sends_resume_and_job_without_contact(master, job):
    client = FakeClient(letter())
    resume = resumes.base_resume(master, job["track"])
    result = letters.write(resume, job, client=client)
    call = client.calls[0]
    assert call["output_format"] is letters.CoverLetter
    assert call["fallbacks"] == "default"
    prompt = "".join(block["text"] for block in call["messages"][0]["content"])
    assert "IT Project Coordinator" in prompt and "operations center" in prompt
    assert "940-999-4151" not in prompt and "LoganHendersonNavy97" not in prompt
    assert result.greeting == "Dear Hiring Manager,"


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_write_raises_on_unusable_answer(master, job, stop_reason):
    with pytest.raises(RuntimeError):
        letters.write(resumes.base_resume(master, job["track"]), job, client=FakeClient(None, stop_reason))


def test_check_facts(master):
    assert letters.check_facts(master, letter()) == []
    invented = letter(paragraphs=["I managed a $2,000,000 budget."])
    assert any("2,000,000" in w for w in letters.check_facts(master, invented))


def test_document_and_exports(master, job):
    document = letters.as_document(letter(), master["contact"], job, today=date(2026, 10, 5))
    assert document["date"] == "October 5, 2026"
    assert document["subject"] == "Re: IT Project Coordinator"
    text = letters.as_text(document)
    assert text.startswith("October 5, 2026") and text.rstrip().endswith("Logan Henderson")
    doc = Document(io.BytesIO(export.letter_to_docx(document)))
    body = "\n".join(p.text for p in doc.paragraphs)
    assert "Dear Hiring Manager," in body and "Fabrikam" in body
    assert export.letter_to_pdf(document).startswith(b"%PDF")


def test_mark_applied_keeps_first_date():
    conn = db.connect(":memory:")
    profile = Profile.load(ROOT / "config" / "profile.json")
    job = job_from_paste("Analyst", "Acme", "SQL and Power BI", location="Seattle, WA")
    db.upsert(conn, job, profile.score(job))
    db.mark_applied(conn, job.key, "2026-10-19")
    db.mark_applied(conn, job.key, "2026-10-25")
    row = db.all_jobs(conn)[0]
    assert row["status"] == "Applied" and row["applied_at"] == "2026-10-19"


def test_connect_adds_applied_column_to_old_database(tmp_path):
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE jobs (key TEXT PRIMARY KEY, source TEXT NOT NULL, external_id TEXT NOT NULL, "
                "title TEXT NOT NULL, company TEXT NOT NULL, location TEXT, url TEXT, apply_url TEXT, "
                "description TEXT, salary_min REAL, salary_max REAL, clearance TEXT, posted_at TEXT, "
                "fetched_at TEXT, score INTEGER, track TEXT, matched TEXT, missing TEXT, reasons TEXT, "
                "status TEXT NOT NULL DEFAULT 'New', notes TEXT NOT NULL DEFAULT '')")
    old.commit()
    old.close()
    conn = db.connect(path)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
    assert "applied_at" in columns
