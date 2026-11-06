from datetime import date

from job_hunter import pipeline, theme


def job(status, score=80, applied_at=None, **kw):
    return {"status": status, "score": score, "title": "T", "company": "C", "location": "", "url": "",
            "salary_max": None, "applied_at": applied_at, **kw}


def test_next_step_priorities():
    today = date(2026, 11, 20)
    assert "Find your first" in pipeline.next_step([], 0, today)[1]
    assert "Decide" in pipeline.next_step([job("Offer"), job("Interviewing")], 0, today)[1]
    assert "Prepare" in pipeline.next_step([job("Interviewing"), job("Saved")], 0, today)[1]
    assert "Follow up" in pipeline.next_step([job("Applied", applied_at="2026-11-01"), job("Saved")], 0, today)[1]
    assert "Apply to" in pipeline.next_step([job("Applied", applied_at="2026-11-19"), job("Saved")], 0, today)[1]
    assert "Look at" in pipeline.next_step([job("New")], 0, today)[1]


def test_fit_chip_and_styles():
    assert theme.fit_label(90) == "🟢 Strong fit"
    assert theme.fit_label(60).startswith("🟡")
    assert "background-color:#DCFCE7" in theme.fit_styles(90)
    assert theme.status_styles("New") == ""
