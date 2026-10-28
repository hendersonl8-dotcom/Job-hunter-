"""Onboarding for someone who is not the original owner: a nurse's resume, not an IT one."""

import json
import sqlite3
from types import SimpleNamespace

import anthropic
import pytest

from job_hunter import db, keys, new_profile, onboarding, role_suggestions, userdata
from job_hunter.config import load_search_prefs, save_search_prefs
from job_hunter.find_screen import keywords_default
from job_hunter.models import Job
from job_hunter.scoring import Profile

NURSE_TEXT = """Maria Santos, RN, BSN
maria.santos@example.com | 503-555-0142 | Portland, OR
Registered Nurse, Providence St. Vincent Medical Center, 2019-2025
- Cared for 5 to 6 medical-surgical patients per shift, giving IV medications and wound care.
- Precepted 12 new graduate nurses and led the unit's fall-prevention project.
BSN, Oregon Health & Science University, 2019
BLS, ACLS, Epic charting, patient education, telemetry
"""


def nurse_facts():
    return onboarding.ExtractedResume(
        contact=onboarding.Contact(name="Maria Santos", email="maria.santos@example.com", phone="503-555-0142", location="Portland, OR"),
        tracks=[onboarding.Track(name="Registered Nurse", title_words=["registered nurse", "rn", "staff nurse"],
                                 headline="Medical-Surgical Registered Nurse", summary="Six years of bedside nursing.",
                                 search_terms=["registered nurse", "med surg nurse"]),
                onboarding.Track(name="Nurse Educator", title_words=["nurse educator", "clinical educator"],
                                 headline="Nurse Educator", summary="Precepted 12 new graduates.",
                                 search_terms=["clinical educator"])],
        skills=[onboarding.Skill(name="Epic", group="Tools", aliases=["Epic charting"]),
                onboarding.Skill(name="IV medications", group="Clinical", aliases=["IV therapy"]),
                onboarding.Skill(name="ACLS", group="Certifications"),
                onboarding.Skill(name="Wound care", group="Clinical"),
                onboarding.Skill(name="Terraform", group="Cloud")],
        experience=[onboarding.Role(title="Registered Nurse", org="Providence St. Vincent Medical Center", dates="2019-2025",
                                    bullets=["Cared for 5 to 6 medical-surgical patients per shift."])],
        locations=["Portland, OR"],
    )


def job(title, description, location="Portland, OR"):
    return Job(source="manual", external_id=title, title=title, company="Acme Health", location=location,
               description=description, url="https://example.com/" + title.replace(" ", "-"))


def test_nurse_resume_builds_a_profile_with_no_it_in_it():
    facts, warnings = onboarding.verify(nurse_facts(), NURSE_TEXT)
    assert [s.name for s in facts.skills] == ["Epic", "IV medications", "ACLS", "Wound care"]  # Terraform isn't on the resume
    assert any("Terraform" in w for w in warnings)
    profile = onboarding.build_profile(facts, 80000, ["Portland, OR"])
    assert set(profile["tracks"]) == {"Registered Nurse", "Nurse Educator"}
    assert set(profile["skills"]) == {"Epic", "IV medications", "ACLS", "Wound care"}
    dumped = json.dumps(profile).lower()
    for borrowed in ("active directory", "azure", "ts/sci", "seattle", "systems admin"):
        assert borrowed not in dumped
    assert profile["clearance"] == "" and profile["preferences"] == {"clearance_mode": "ignore"}
    assert profile["search_terms"] == ["Registered Nurse", "registered nurse", "med surg nurse", "Nurse Educator", "clinical educator"]


def test_nurse_profile_scores_and_sorts_nursing_jobs():
    facts, _ = onboarding.verify(nurse_facts(), NURSE_TEXT)
    profile = Profile(onboarding.build_profile(facts, 80000, ["Portland"]))
    rn = job("Registered Nurse - Med Surg", "Give IV therapy, wound care and chart in Epic. ACLS required.")
    it = job("Systems Administrator", "Manage Active Directory, Azure and Windows Server. Security+ required.")
    nurse_fit, it_fit = profile.score(rn), profile.score(it)
    assert nurse_fit.track == "Registered Nurse" and nurse_fit.matched == ["Epic", "IV medications", "ACLS", "Wound care"]
    assert nurse_fit.score > it_fit.score
    assert profile.track_for(job("Clinical Educator", "Teach staff")) == "Nurse Educator"
    assert nurse_fit.score >= 70  # no clearance on the posting or the resume doesn't drag the score down


def test_short_words_only_match_whole_words():
    profile = Profile(onboarding.build_profile(nurse_facts(), 0, []))
    assert profile.track_for(job("Learner Support Specialist", "internal training")) == "Other"  # 'rn' is not inside 'learner'
    assert profile.track_for(job("RN", "")) == "Registered Nurse"


def test_search_prefs_use_the_persons_own_places_and_terms():
    profile = onboarding.build_profile(nurse_facts(), 0, ["Portland, OR"], allow_remote=False)
    prefs = onboarding.search_prefs(profile)
    assert prefs == {"keywords": profile["search_terms"], "areas": ["Portland, OR"], "remote_mode": "onsite"}
    seattle = onboarding.search_prefs(onboarding.build_profile(nurse_facts(), 0, ["Bellevue", "Austin, TX"]))
    assert seattle["areas"] == ["Seattle", "Austin, TX"] and seattle["remote_mode"] == "include"


def test_find_jobs_starts_from_the_persons_terms_not_the_starter_it_list():
    settings = SimpleNamespace(usajobs_keywords=["system administrator"])
    mine = Profile(onboarding.build_profile(nurse_facts(), 0, []))
    assert "registered nurse" in keywords_default(settings, {}, mine)
    assert keywords_default(settings, {"keywords": ["x"]}, mine) == ["x"]
    original = Profile({"tracks": {}})  # the original profile has no 'generated' flag and keeps the toml list
    assert keywords_default(settings, {}, original) == ["system administrator"]


def test_roles_flow_adds_ticked_roles_for_a_nurse():
    facts, _ = onboarding.verify(nurse_facts(), NURSE_TEXT)
    master, profile = onboarding.build_resume(facts), onboarding.build_profile(facts, 0, [])
    out = role_suggestions.SuggestionOutput(roles=[
        role_suggestions.RoleSuggestion(title="Case Manager", reason="Patient education and care coordination.",
                                        evidence=["medical-surgical patients"], search_terms=["nurse case manager"]),
        role_suggestions.RoleSuggestion(title="Surgeon", reason="No.", evidence=["performed surgery"]),
    ])
    kept = role_suggestions.check(master, out, list(profile["tracks"]))
    assert [r.title for r in kept] == ["Case Manager"]
    added = role_suggestions.add_roles(profile, kept)
    assert "Case Manager" in added["tracks"] and "nurse case manager" in added["search_terms"]


def test_the_original_profile_is_untouched():
    from job_hunter.config import ROOT
    data = json.loads((ROOT / "config" / "profile.json").read_text())
    assert "generated" not in data and data["clearance"] == "TS/SCI"
    assert "Active Directory" in Profile(data).skills


def test_claude_key_is_checked_saved_and_loaded(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    assert "sk-ant-" in keys.check_claude_key("hello")
    ok = SimpleNamespace(models=SimpleNamespace(list=lambda **kw: []))
    assert keys.check_claude_key("sk-ant-abc", client=ok) == ""

    class Denied(anthropic.AuthenticationError):
        def __init__(self):
            Exception.__init__(self, "no")

    def refuse(**kw):
        raise Denied()

    assert "didn't accept" in keys.check_claude_key("sk-ant-abc", client=SimpleNamespace(models=SimpleNamespace(list=refuse)))
    assert not keys.has_claude_key()
    keys.save_claude_key(" sk-ant-abc ")
    assert keys.has_claude_key() and json.loads((userdata.root_dir() / "keys.json").read_text()) == {"anthropic_api_key": "sk-ant-abc"}
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    keys.load_into_env()
    assert keys.has_claude_key()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env")
    keys.load_into_env()  # an environment key wins
    assert keys.has_claude_key()
    import os
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-env"
    keys.forget_claude_key()
    assert not keys.has_claude_key()


def test_start_a_new_profile_archives_then_clears_but_keeps_the_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    userdata.save_profile({"clearance": "TS/SCI"})
    userdata.save_resume({"contact": {"name": "Logan"}})
    save_search_prefs({"keywords": ["x"]})
    keys.save_claude_key("sk-ant-keep")
    conn = db.connect(userdata.database_path())
    saved_job = job("Registered Nurse", "Epic")
    db.upsert(conn, saved_job, Profile({}).score(saved_job))
    db.record_outcome(conn, saved_job.key, "Reply", "2026-10-01")
    archive = new_profile.start_new_profile(conn)
    assert json.loads((archive / "profile.json").read_text()) == {"clearance": "TS/SCI"}
    assert json.loads((archive / "resume.json").read_text())["contact"]["name"] == "Logan"
    assert json.loads((archive / "search.json").read_text()) == {"keywords": ["x"]}
    assert sqlite3.connect(archive / "jobs.db").execute("SELECT COUNT(*) FROM jobs").fetchone() == (1,)
    assert sqlite3.connect(archive / "jobs.db").execute("SELECT COUNT(*) FROM outcomes").fetchone() == (1,)
    home = userdata.user_dir()
    assert not (home / "profile.json").exists() and not (home / "resume.json").exists() and not (home / "search.json").exists()
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == conn.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0] == 0
    assert onboarding.needs_onboarding(home / "profile.json", home / "resume.json")
    assert (userdata.root_dir() / "keys.json").exists()
