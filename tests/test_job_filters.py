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
