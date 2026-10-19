from job_hunter import pipeline, theme, tour


def job(status, score, **kw):
    return {"key": f"k{status}{score}", "title": "T", "company": "C", "location": "", "url": "", "status": status,
            "score": score, "salary_min": None, "salary_max": None, **kw}


def test_fit_bands():
    assert theme.band(90)[0] == "Strong fit"
    assert theme.band(75)[0] == "Strong fit"
    assert theme.band(60)[0] == "Worth a look"
    assert theme.band(10)[0] == "Long shot"


def test_pipeline_groups_by_stage_best_first():
    jobs = [job("Applied", 50), job("Applied", 80), job("New", 99), job("Skipped", 70), job("Offer", 60)]
    stages = pipeline.by_stage(jobs)
    assert [j["score"] for j in stages["Applied"]] == [80, 50]
    assert [j["score"] for j in stages["Offer"]] == [60]
    assert stages["Saved"] == [] and stages["Interviewing"] == []


def test_top_new_skips_low_pay_and_other_statuses():
    jobs = [job("New", 90, salary_max=40000), job("New", 80), job("Saved", 95), job("New", 70, salary_max=100000)]
    assert [j["score"] for j in pipeline.top_new(jobs, 70000)] == [80, 70]


def test_card_escapes_html():
    html = pipeline.card_html(job("Saved", 50, title="<script>x</script>"), "#000")
    assert "<script>" not in html


def test_tour_marker(monkeypatch, tmp_path):
    monkeypatch.setenv("JOB_HUNTER_HOME", str(tmp_path))
    assert not tour.seen()
    tour.mark_seen()
    assert tour.seen()
