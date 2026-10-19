import json
from pathlib import Path

import pytest

from job_hunter import db
from job_hunter.collect import collect
from job_hunter.config import ROOT, Settings
from job_hunter.scoring import Profile
from job_hunter.sources import job_from_paste
from job_hunter.sources.greenhouse import parse_greenhouse
from job_hunter.sources.lever import parse_lever
from job_hunter.sources.manual import source_from_url
from job_hunter.sources.usajobs import parse_usajobs
from job_hunter.text import detect_clearance, html_to_text, parse_salary

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def profile():
    return Profile.load(ROOT / "config" / "profile.json")


@pytest.mark.parametrize("text, expected", [
    ("Pay range: $95,000 - $120,000 per year.", (95000, 120000)),
    ("$85k–$110k DOE", (85000, 110000)),
    ("$44 - $55/hr on W2", (44 * 2080, 55 * 2080)),
    ("$23.80-$32.20 per hour", (23.80 * 2080, 32.20 * 2080)),
    ("Salary: $120,000", (120000, 120000)),
    ("$5,000 signing bonus. Pay $90,000 to $100,000.", (90000, 100000)),
    ("No pay listed", (None, None)),
])
def test_parse_salary(text, expected):
    low, high = parse_salary(text)
    if expected[0] is None:
        assert (low, high) == expected
    else:
        assert low == pytest.approx(expected[0]) and high == pytest.approx(expected[1])


@pytest.mark.parametrize("text, expected", [
    ("Must hold an active TS/SCI", "TS/SCI"),
    ("Top Secret clearance required", "Top Secret"),
    ("Ability to obtain a Secret clearance", "Secret"),
    ("Public Trust background check", "Public Trust"),
    ("Keep our secrets safe", ""),
])
def test_detect_clearance(text, expected):
    assert detect_clearance(text) == expected


def test_html_to_text_unescapes_greenhouse_content():
    assert html_to_text("&lt;p&gt;Hello &amp;amp; welcome&lt;/p&gt;&lt;ul&gt;&lt;li&gt;One&lt;/li&gt;&lt;/ul&gt;") == "Hello & welcome\n\nOne"


def test_parse_greenhouse():
    jobs = parse_greenhouse(fixture("greenhouse.json"), "contoso")
    sysadmin = jobs[0]
    assert sysadmin.key == "greenhouse:4012345"
    assert sysadmin.company == "Contoso Health"
    assert "Active Directory" in sysadmin.description and "<" not in sysadmin.description
    assert (sysadmin.salary_min, sysadmin.salary_max) == (95000, 120000)


def test_parse_lever_uses_structured_hourly_salary():
    job = parse_lever(fixture("lever.json"), "fabrikam")[0]
    assert job.title == "IT Project Coordinator"
    assert job.apply_url.endswith("/apply")
    assert (job.salary_min, job.salary_max) == (40 * 2080, 52 * 2080)
    assert job.clearance == "Secret"
    assert "PMP or CAPM" in job.description


def test_parse_usajobs():
    job = parse_usajobs(fixture("usajobs.json"))[0]
    assert job.title == "IT Specialist (SYSADMIN)"
    assert job.company == "Department of the Navy / Naval Sea Systems Command"
    assert job.clearance == "TS/SCI"
    assert (job.salary_min, job.salary_max) == (84000, 109000)
    assert "Apply STIGs" in job.description


def test_paste_detects_site_and_needs_text():
    assert source_from_url("https://www.linkedin.com/jobs/view/123") == "linkedin"
    assert source_from_url("https://www.glassdoor.com/job-listing/abc") == "glassdoor"
    assert source_from_url("https://careers.example.com/1") == "manual"
    with pytest.raises(ValueError):
        job_from_paste("Analyst", "Acme", "  ")


def test_score_explains_itself(profile):
    job = parse_usajobs(fixture("usajobs.json"))[0]
    fit = profile.score(job)
    assert fit.track == "IT / Systems Admin"
    assert "Linux" in fit.matched and "Security+" in fit.missing
    assert any("Clearance 10/10" in r for r in fit.reasons)
    assert any("Pay 10/10" in r for r in fit.reasons)
    assert 60 <= fit.score <= 100


def test_score_penalises_low_pay_and_far_away(profile):
    job = job_from_paste("Help Desk Technician", "Acme", "Help desk. Active Directory. $18/hr", location="Phoenix, AZ")
    fit = profile.score(job)
    assert any(r.startswith("Pay 0/10") for r in fit.reasons)
    assert any(r.startswith("Location 0/10") for r in fit.reasons)


def test_tracks(profile):
    assert profile.track_for(job_from_paste("Senior Data Analyst", "A", "SQL")) == "Data Analyst"
    assert profile.track_for(job_from_paste("Technical Program Manager", "A", "x")) == "Project Manager"
    assert profile.track_for(job_from_paste("Quality Assurance Inspector", "A", "x")) == "Quality / Operations"


def test_db_dedupes_and_keeps_your_status(profile):
    conn = db.connect(":memory:")
    job = parse_greenhouse(fixture("greenhouse.json"), "contoso")[0]
    assert db.upsert(conn, job, profile.score(job)) is True
    db.set_status(conn, job.key, "Saved", "Call recruiter")
    same_job_pasted = job_from_paste(job.title, job.company, job.description, url="https://www.linkedin.com/jobs/view/9")
    assert db.upsert(conn, same_job_pasted, profile.score(same_job_pasted)) is False
    rows = db.all_jobs(conn)
    assert len(rows) == 1 and rows[0]["status"] == "Saved" and rows[0]["notes"] == "Call recruiter"
    assert db.rescore(conn, profile) == 1


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def get(self, url, **kwargs):
        if "greenhouse" in url:
            return FakeResponse(fixture("greenhouse.json"))
        if "lever" in url and "missing" in url:
            return FakeResponse({}, status=404)
        if "lever" in url:
            return FakeResponse(fixture("lever.json"))
        return FakeResponse(fixture("usajobs.json"))


def test_collect_filters_area_and_reports_errors(profile):
    settings = Settings(
        database=Path(":memory:"), profile=ROOT / "config" / "profile.json",
        usajobs_keywords=["it specialist"], greenhouse_boards=["contoso"], lever_boards=["fabrikam", "missing"],
        usajobs_api_key="key", usajobs_email="me@example.com",
    )
    conn = db.connect(":memory:")
    result = collect(settings, conn, profile, session=FakeSession())
    assert result.added == 3  # USAJobs + Seattle sysadmin + Bellevue coordinator
    assert result.skipped_location == 1  # Austin
    assert len(result.errors) == 1 and "missing" in result.errors[0]
