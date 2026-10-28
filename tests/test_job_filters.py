from job_hunter import db, job_filters


def _job(status="New", salary_max=None):
    return {"status": status, "salary_max": salary_max}


def test_saved_view_shows_only_saved_jobs():
    jobs = [_job("Saved"), _job("New"), _job("Applied"), _job("Saved")]
    assert [j["status"] for j in jobs if j["status"] in job_filters.VIEWS["Saved"]] == ["Saved", "Saved"]
    assert job_filters.view_label("Saved", jobs) == "Saved (2)"


def test_open_view_hides_closed_jobs_and_all_view_covers_every_status():
    assert "Skipped" not in job_filters.VIEWS["Open"] and "Rejected" not in job_filters.VIEWS["Open"]
    assert set(job_filters.VIEWS["All"]) == set(db.STATUSES)


def test_min_salary_hides_low_pay_but_keeps_unlisted_by_default():
    assert job_filters.meets_min_salary(_job(salary_max=90_000), 80_000)
    assert not job_filters.meets_min_salary(_job(salary_max=60_000), 70_000)
    assert job_filters.meets_min_salary(_job(), 70_000)
    assert not job_filters.meets_min_salary(_job(), 70_000, hide_unlisted=True)
    assert job_filters.meets_min_salary(_job(), 0, hide_unlisted=True)


def _full(key, score=50, salary_max=None, fetched="2026-10-01T00:00:00+00:00", posted="", status="New"):
    return {"key": key, "score": score, "salary_min": salary_max, "salary_max": salary_max, "fetched_at": fetched,
            "posted_at": posted, "status": status, "title": key, "company": "Co", "location": None, "url": None,
            "notes": "", "applied_at": None}


def test_sorting_by_fit_date_and_pay():
    a = _full("a", 90, 80_000, posted="2026-09-01")
    b = _full("b", 70, 120_000, posted="2026-10-20")
    c = _full("c", 80, None, fetched="2026-10-05T00:00:00+00:00")
    keys = lambda how: [j["key"] for j in job_filters.sort_jobs([a, b, c], how)]
    assert keys("Best fit") == ["a", "c", "b"]
    assert keys("Newest") == ["b", "c", "a"]
    assert keys("Highest pay") == ["b", "a", "c"]


def test_new_since_last_visit():
    old, new = _full("old", fetched="2026-10-01T00:00:00+00:00"), _full("new", fetched="2026-10-10T00:00:00+00:00")
    assert [j["key"] for j in job_filters.new_since([old, new], "2026-10-05T00:00:00+00:00")] == ["new"]
    assert job_filters.new_since([old, new], None) == []


def test_presets_and_last_visit_persist(tmp_path, monkeypatch):
    monkeypatch.setenv("JOB_HUNTER_HOME", str(tmp_path))
    assert job_filters.touch_last_visit("t1") is None
    assert job_filters.touch_last_visit("t2") == "t1"
    job_filters.save_preset("Cleared IT", {"jobs-min-fit": 60})
    assert job_filters.load_view_settings()["presets"] == {"Cleared IT": {"jobs-min-fit": 60}}
    job_filters.delete_preset("Cleared IT")
    assert job_filters.load_view_settings()["presets"] == {}


def test_pipeline_csv_has_only_pipeline_jobs_in_stage_order():
    rows = job_filters.pipeline_csv([_full("n", status="New"), _full("s", status="Saved"), _full("o", 10, status="Offer")])
    lines = rows.strip().splitlines()
    assert lines[0].startswith("Status,Fit,Title")
    assert [l.split(",")[2] for l in lines[1:]] == ["s", "o"]
