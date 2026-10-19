from job_hunter.config import ROOT
from job_hunter.sources import jobs_from_csv

CSV = """﻿id,track,title,employer,location,pay_min,pay_max,pay_period,clearance,key_requirements,posting_url,date_posted,date_found,notes
1,IT,Systems Administrator,Serco Inc.,"Bremerton, WA",91702,152836,annual,Active TS/SCI,"Active Directory | Windows Server",https://example.com/1,2026-10-01,2026-10-19,Strong fit
2,Data,Data Analyst,Acme,"Seattle, WA",,,,,,,,,
,,,,,,,,,,,,,
"""


def test_jobs_from_csv():
    jobs = jobs_from_csv(CSV)
    assert len(jobs) == 2
    first = jobs[0]
    assert (first.title, first.company, first.clearance) == ("Systems Administrator", "Serco Inc.", "TS/SCI")
    assert (first.salary_min, first.salary_max, first.posted_at) == (91702, 152836, "2026-10-01")
    assert "- Active Directory" in first.description and first.apply_url == "https://example.com/1"
    assert jobs[1].salary_min is None and jobs[1].key != first.key


def test_bundled_shortlists_load():
    for path in (ROOT / "shortlists").glob("*.csv"):
        assert jobs_from_csv(path.read_text(encoding="utf-8"))
