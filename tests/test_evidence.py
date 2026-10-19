from job_hunter import db
from job_hunter.corrections import Corrections
from job_hunter.evidence_panel import highlighted
from job_hunter.scoring import Profile
from job_hunter.sources import job_from_paste

PROFILE = Profile(
    {
        "skills": {
            "SQL": {"aliases": ["\\bSQL\\b", "t-sql"], "have": True, "weight": 3},
            "Tableau": {"aliases": ["tableau"], "have": False, "weight": 2},
            "Git / CI": {"aliases": ["\\bgit\\b", "(ci|cd|build) pipelines?"], "have": True, "weight": 1},
        },
        "tracks": {},
    }
)


def test_evidence_quotes_the_matching_phrase():
    job = job_from_paste("Analyst", "Acme", "We need someone to write T-SQL queries and build Tableau dashboards.")
    by_skill = {e.skill: e for e in PROFILE.evidence(job)}
    sql = by_skill["SQL"]
    assert sql.phrase == "T-SQL"
    assert sql.snippet[sql.start:sql.start + len(sql.phrase)] == "T-SQL"
    assert "write T-SQL queries" in sql.snippet
    assert not by_skill["Tableau"].have


def test_snippet_trims_long_text_at_word_edges():
    filler = "word " * 40
    job = job_from_paste("Analyst", "Acme", f"{filler}tableau {filler}")
    e = PROFILE.evidence(job)[0]
    assert e.snippet.startswith("…") and e.snippet.endswith("…")
    assert e.snippet[e.start:e.start + len(e.phrase)] == "tableau"
    assert len(e.snippet) < 160


def test_generic_words_do_not_count():
    job = job_from_paste("Sales Rep", "Acme", "Grow our sales pipeline. Manage the customer database.")
    from job_hunter.config import load_settings

    real = Profile.load(load_settings().profile)
    names = {e.skill for e in real.evidence(job)}
    assert "SQL" not in names and "Git / CI" not in names


def test_correction_removes_skill_from_score_and_survives_rescore():
    conn = db.connect(":memory:")
    PROFILE.corrections = Corrections(conn)
    job = job_from_paste("Analyst", "Acme", "SQL and Tableau required.")
    before = PROFILE.score(job)
    assert "SQL" in before.matched
    db.upsert(conn, job, before)

    PROFILE.corrections.reject(job.key, "SQL")
    db.rescore(conn, PROFILE)
    after = PROFILE.score(job)
    assert "SQL" not in after.matched and "SQL" not in after.missing
    assert db.all_jobs(conn)[0]["matched"] == []

    PROFILE.corrections.restore(job.key, "SQL")
    assert "SQL" in PROFILE.score(job).matched
    PROFILE.corrections = None


def test_highlight_escapes_markdown():
    assert highlighted("pay $5 SQL *now*", 7, 3) == "pay \\$5 **SQL** \\*now\\*"
