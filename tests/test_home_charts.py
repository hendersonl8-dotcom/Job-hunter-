from datetime import date

from job_hunter import home_charts as hc
from job_hunter import pay_fit


def job(key, status, track="IT", applied=None, lo=None, hi=None, score=70):
    return {"key": key, "title": key, "company": "Co", "status": status, "track": track, "applied_at": applied,
            "salary_min": lo, "salary_max": hi, "score": score}


def test_funnel_counts_offer_counts_every_stage():
    jobs = [job("a", "Saved"), job("b", "Applied", applied="2026-11-02"), job("c", "Offer"), job("d", "New")]
    apps = [{"key": "b", "logged": {"Interview"}}, {"key": "c", "logged": set()}]
    assert hc.funnel_counts(jobs, apps) == {"Saved": 3, "Applied": 2, "Interviewing": 2, "Offer": 1}


def test_applications_per_week_fills_gaps():
    df = hc.applications_per_week([job("a", "Applied", applied="2026-10-05"), job("b", "Applied", applied="2026-10-20")])
    assert list(df["Applications"])[:3] == [1, 0, 1] and len(df) >= 3
    assert hc.applications_per_week([job("a", "Saved")]).empty
    assert date.today()  # last week row reaches the current week


def test_response_rate_by_track():
    apps = [{"track": "IT", "status": "Applied", "logged": {"Reply"}}, {"track": "IT", "status": "Applied", "logged": set()},
            {"track": "Data", "status": "Rejected", "logged": set()}]
    df = hc.response_by_track(apps)
    assert dict(zip(df["Track"], df["Response rate"])) == {"Data": 100, "IT": 50}
    assert hc.response_by_track([]).empty


def test_pay_fit_points_skip_unlisted_pay_and_new_jobs():
    df, unlisted = pay_fit.points([job("a", "Saved", lo=80000, hi=100000), job("b", "Saved"), job("c", "New", hi=1)])
    assert list(df["Top pay"]) == [100000.0] and unlisted == 1
