"""Does the fit score agree with how Logan would rank real postings?

tests/fixtures/ranking_postings.csv holds real Seattle-area postings (frozen copies from
the 2026-10-19 sweep) and ranking_expected.json holds the band each should land in.
The test prints an agreement report (run `pytest -s tests/test_ranking.py`) and only
fails if agreement drops below the baseline, so scoring changes can be measured
without blocking CI. Raise the BASELINE numbers as scoring improves.
"""

import json
from itertools import combinations
from pathlib import Path

import pytest

from job_hunter.config import ROOT
from job_hunter.scoring import Profile
from job_hunter.sources.shortlist import jobs_from_csv

FIXTURES = Path(__file__).parent / "fixtures"
BANDS = ["weak", "stretch", "good", "strong"]
CUTOFFS = [(80, "strong"), (65, "good"), (50, "stretch"), (0, "weak")]

# Floors set just under the agreement measured on 2026-10-19 scoring.
BASELINE = {"exact": 0.25, "within_one": 0.70, "pairwise": 0.60}


def band_for(score: int) -> str:
    return next(name for cutoff, name in CUTOFFS if score >= cutoff)


def load_cases():
    expected = {(e["title"], e["employer"]): e for e in json.loads((FIXTURES / "ranking_expected.json").read_text())["postings"]}
    jobs = jobs_from_csv((FIXTURES / "ranking_postings.csv").read_text(encoding="utf-8"))
    return [(job, expected[(job.title, job.company)]) for job in jobs]


def agreement(profile: Profile) -> tuple[dict, list]:
    cases = load_cases()
    rows = [(job, BANDS.index(exp["expected_band"]), profile.score(job).score) for job, exp in cases]
    got = [BANDS.index(band_for(score)) for _, _, score in rows]
    want = [w for _, w, _ in rows]
    n = len(rows)
    pairs = [(a, b) for a, b in combinations(rows, 2) if a[1] != b[1]]
    credit = 0.0
    for a, b in pairs:
        hi, lo = (a, b) if a[1] > b[1] else (b, a)
        credit += 1.0 if hi[2] > lo[2] else 0.5 if hi[2] == lo[2] else 0.0
    metrics = {
        "exact": sum(g == w for g, w in zip(got, want)) / n,
        "within_one": sum(abs(g - w) <= 1 for g, w in zip(got, want)) / n,
        "pairwise": credit / len(pairs),
    }
    detail = [(job.title, job.company, BANDS[w], band_for(s), s) for (job, w, s) in rows]
    return metrics, detail


@pytest.fixture
def profile():
    return Profile.load(ROOT / "config" / "profile.json")


def test_fixture_set_is_balanced():
    cases = load_cases()
    assert 15 <= len(cases) <= 20
    assert {e["expected_band"] for _, e in cases} == set(BANDS)
    assert len(cases) == len({(job.title, job.company) for job, _ in cases})


def test_scoring_agrees_with_expected_ranking(profile, capsys):
    metrics, detail = agreement(profile)
    with capsys.disabled():
        print("\nRanking agreement (" + str(len(detail)) + " postings)")
        for title, company, want, got, score in detail:
            print(f"  {'ok ' if want == got else 'off'} expected {want:<7} got {got:<7} {score:>3}  {title[:42]} ({company[:22]})")
        print("  " + "  ".join(f"{k} {v:.0%}" for k, v in metrics.items()))
    for name, floor in BASELINE.items():
        assert metrics[name] >= floor, f"{name} agreement {metrics[name]:.0%} fell below baseline {floor:.0%}"
