import json

from job_hunter import preferences as prefs_mod
from job_hunter import userdata
from job_hunter.config import ROOT
from job_hunter.models import Job
from job_hunter.preferences_screen import save_preferences
from job_hunter.scoring import Profile


def profile(**prefs):
    data = json.loads((ROOT / "config" / "profile.json").read_text(encoding="utf-8"))
    data["preferences"] = prefs
    return Profile(data)


def job(**kw):
    base = dict(source="manual", external_id="1", title="Systems Administrator", company="Acme",
                location="Seattle, WA", description="Windows Server and Active Directory.")
    return Job(**{**base, **kw})


def test_defaults_match_original_weights():
    p = profile()
    assert p.prefs["weights"]["skills"] == 70 and p.prefs["weights"]["remote"] == 0
    assert 0 <= p.score(job()).score <= 100


def test_clearance_ready_to_grow_is_neutral_not_a_miss():
    wants = job(clearance="TS/SCI")
    no_clearance = {**json.loads((ROOT / "config" / "profile.json").read_text(encoding="utf-8")), "clearance": ""}
    hold = Profile({**no_clearance, "preferences": {"clearance_mode": "hold"}}).score(wants).score
    grow = Profile({**no_clearance, "preferences": {"clearance_mode": "grow"}}).score(wants).score
    assert grow > hold


def test_clearance_ignore_drops_the_factor():
    fit = profile(clearance_mode="ignore").score(job(clearance="Secret"))
    assert not any(r.startswith("Clearance") for r in fit.reasons)


def test_remote_preference_rewards_matching_mode():
    p = profile(weights={"remote": 20}, remote="remote")
    assert p.score(job(location="Remote")).score > p.score(job(location="Seattle, WA (on-site)")).score


def test_employer_type_and_seniority_classification():
    assert prefs_mod.employer_type(job(company="Leidos")) == "contractor"
    assert prefs_mod.employer_type(job(source="usajobs", company="Department of the Navy")) == "federal"
    assert prefs_mod.employer_type(job(company="Acme")) == "private"
    assert prefs_mod.seniority(job(title="Senior Systems Administrator")) == "senior"
    assert prefs_mod.seniority(job(title="Systems Administrator II")) == "mid"
    assert prefs_mod.seniority(job(title="Systems Administrator")) == ""


def test_employer_and_seniority_weights_change_the_score():
    p = profile(weights={"employer": 20, "seniority": 20}, employer_types=["contractor"], seniority=["entry"])
    good = p.score(job(company="SAIC", title="Junior Systems Administrator"))
    bad = p.score(job(company="Acme", title="Principal Systems Administrator"))
    assert good.score > bad.score


def test_never_show_and_must_have_zero_the_score():
    p = profile(never_show=["on-call"], must_have=["active directory"])
    off = p.score(job(description="Active Directory. Some on-call rotation."))
    assert off.score == 0 and "never show" in off.hidden
    assert p.score(job(description="Windows Server only")).hidden.startswith("missing must-have")
    assert p.score(job()).hidden == ""


def test_preferences_saved_in_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("JOB_HUNTER_HOME", str(tmp_path))
    save_preferences(prefs_mod.merged({"remote": "hybrid", "must_have": ["python"]}))
    saved = userdata.load_profile()["preferences"]
    assert saved["remote"] == "hybrid" and saved["must_have"] == ["python"]
    assert saved["weights"]["skills"] == 70 and "skills" in saved["weights"]
    assert "clearance" in userdata.load_profile()  # the rest of the profile is untouched


def test_remote_reads_work_mode_field_when_present():
    p = profile(weights={"remote": 20}, remote="remote")
    remote, onsite = job(location="Seattle, WA"), job(location="Seattle, WA")
    remote.work_mode, onsite.work_mode = "remote", "on-site"
    assert p.score(remote).score > p.score(onsite).score
