from pathlib import Path

import pytest

from job_hunter import db
from job_hunter.collect import collect, keep_by_mode, resolve_areas
from job_hunter.config import Settings
from job_hunter.models import Job
from job_hunter.scoring import Profile
from job_hunter.sources.workmode import detect_work_mode

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def profile():
    return Profile.load(ROOT / "config" / "profile.json")


@pytest.mark.parametrize("location,title,description,declared,expected", [
    ("Remote - US", "Sysadmin", "", "", "remote"),
    ("Seattle, WA", "Sysadmin (Hybrid)", "", "", "hybrid"),
    ("Seattle, WA", "Sysadmin", "This is a hybrid role, 3 days a week in the office.", "", "hybrid"),
    ("Seattle, WA", "Sysadmin", "We are a remote-first company. Fully remote position.", "", "remote"),
    ("Seattle, WA", "Sysadmin", "Use remote desktop and remote access tools.", "", ""),
    ("Seattle, WA", "Sysadmin", "Fully remote, with 2 days per week in the office.", "", "hybrid"),
    ("Keyport, WA", "Sysadmin", "On-site at the shipyard. No telework.", "", "onsite"),
    ("Anywhere", "Sysadmin", "", "Hybrid", "hybrid"),
])
def test_detect_work_mode(location, title, description, declared, expected):
    assert detect_work_mode(location, title, description, declared) == expected


def job(mode, location="Somewhere", n=[0]):
    n[0] += 1
    return Job(source="x", external_id=str(n[0]), title="t", company="c", location=location, work_mode=mode)


def test_keep_by_mode():
    assert keep_by_mode(job("remote"), "only") and not keep_by_mode(job("hybrid"), "only") and not keep_by_mode(job(""), "only")
    assert not keep_by_mode(job("remote"), "onsite") and keep_by_mode(job("hybrid"), "onsite") and keep_by_mode(job(""), "onsite")
    assert all(keep_by_mode(job(m), "include") for m in ("remote", "hybrid", "onsite", ""))


def test_resolve_areas_presets_and_custom():
    areas = resolve_areas(["San Diego", "Austin, Texas", "San Diego", " "])
    assert [a.name for a in areas] == ["San Diego", "Austin, Texas"]
    assert areas[1].usajobs_location == "Austin, Texas" and areas[1].terms == ("Austin",)


class Resp:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class Session:
    def __init__(self):
        self.calls = []

    def get(self, url, **kw):
        self.calls.append((url, kw.get("params")))
        item = lambda i, title, loc: {"id": i, "title": title, "company_name": "Co", "location": {"name": loc},
                                      "absolute_url": f"https://x/{i}", "content": "Windows Server PowerShell"}
        return Resp({"jobs": [item(1, "Sysadmin", "San Diego, CA"), item(2, "Sysadmin II", "Norfolk, VA"),
                              item(3, "Sysadmin III", "Remote - US"), item(4, "Sysadmin IV", "Austin, TX"),
                              item(5, "Sysadmin V", "Seattle, WA (Hybrid)")]})


def run(profile, **kw):
    settings = Settings(database=Path(":memory:"), profile=ROOT / "config" / "profile.json", greenhouse_boards=["co"], **kw)
    conn = db.connect(":memory:")
    result = collect(settings, conn, profile, session=Session())
    return result, {r["title"]: r for r in db.all_jobs(conn)}


def test_several_areas_keep_each_and_store_work_mode(profile):
    result, jobs = run(profile, areas=["San Diego", "Norfolk / Virginia Beach"])
    assert set(jobs) == {"Sysadmin", "Sysadmin II", "Sysadmin III"}  # not Austin, not Seattle
    assert jobs["Sysadmin III"]["work_mode"] == "remote" and jobs["Sysadmin"]["work_mode"] in ("", None)
    assert result.skipped_location == 2


def test_remote_only_and_onsite_modes(profile):
    _, jobs = run(profile, areas=["Seattle", "San Diego"], remote_mode="only")
    assert set(jobs) == {"Sysadmin III"}
    _, jobs = run(profile, areas=["Seattle", "San Diego"], remote_mode="onsite")
    assert set(jobs) == {"Sysadmin", "Sysadmin V"} and jobs["Sysadmin V"]["work_mode"] == "hybrid"


def test_remote_only_usajobs_search_has_no_place(profile):
    settings = Settings(database=Path(":memory:"), profile=ROOT / "config" / "profile.json", usajobs_keywords=["analyst"],
                        usajobs_api_key="k", usajobs_email="a@b.c", areas=["Seattle", "San Diego"], remote_mode="only")
    session = Session()
    collect(settings, db.connect(":memory:"), profile, session=session)
    (url, params), = session.calls
    assert params["RemoteIndicator"] == "True" and "LocationName" not in params
    settings.remote_mode = "include"
    session.calls.clear()
    collect(settings, db.connect(":memory:"), profile, session=session)
    assert [p["LocationName"] for _, p in session.calls] == ["Seattle, Washington", "San Diego, California"]


def test_old_database_gets_work_mode_column(tmp_path):
    import sqlite3
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE jobs (key TEXT PRIMARY KEY, source TEXT, external_id TEXT, title TEXT, company TEXT)")
    old.commit(); old.close()
    cols = {r["name"] for r in db.connect(path).execute("PRAGMA table_info(jobs)")}
    assert "work_mode" in cols
