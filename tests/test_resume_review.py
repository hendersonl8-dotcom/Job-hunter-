from types import SimpleNamespace

import pytest

from job_hunter import resume_review as rr
from job_hunter.config import ROOT
from job_hunter.scoring import Profile

MASTER = {
    "skills": {"Systems": ["Active Directory", "PowerShell"]},
    "experience": [{"title": "Help Desk Lead", "org": "Acme",
                    "bullets": ["Resolved 40 tickets a week and trained 5 technicians."]}],
    "certifications": ["AZ-900"],
}
PROFILE = Profile({"tracks": {"IT Support": ["help desk"]},
                   "skills": {"Security+": {"aliases": ["Security\\+"], "have": False, "weight": 2}}})


def output(**over):
    data = dict(
        scores=[rr.RoleScore(role="IT Support", score=140, reason="Solid.")],
        missing_keywords=[rr.MissingKeyword(term="Intune", roles=["IT Support"], advice="If true, add Intune."),
                          rr.MissingKeyword(term="PowerShell", advice="If true, add it.")],
        weak_bullets=[
            rr.WeakBullet(original="Resolved 40 tickets a week", problem="Passive", rewrite="Resolved 40 tickets a week."),
            rr.WeakBullet(original="Trained 5 technicians", problem="Vague", rewrite="Trained 12 technicians."),
            rr.WeakBullet(original="Worked on AD", problem="Vague", rewrite="Hardened AD and earned Security+."),
            rr.WeakBullet(original="Did cloud", problem="Vague", rewrite="Passed AZ-104 and ran Azure."),
        ],
        needs_number=[rr.NeedsNumber(original="Supported users", question="How many users?")],
    )
    data.update(over)
    return rr.ReviewOutput(**data)


def client(parsed, stop="end_turn", seen=None):
    def parse(**kw):
        if seen is not None:
            seen.update(kw)
        return SimpleNamespace(stop_reason=stop, parsed_output=parsed)
    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(parse=parse)))


def test_check_holds_back_unsupported_rewrites_and_drops_present_keywords():
    out, notes = rr.check(MASTER, output(), PROFILE)
    assert [k.term for k in out.missing_keywords] == ["Intune"]
    rewrites = [b.rewrite for b in out.weak_bullets]
    assert rewrites[0]                      # supported by the master resume
    assert rewrites[1:] == ["", "", ""]     # new number, Security+ skill, AZ-104 cert
    assert len(notes) == 3
    assert out.scores[0].score == 100       # clamped


def test_review_uses_client_and_gaps_in_prompt():
    seen = {}
    jobs = [{"missing": ["Security+", "Intune"], "status": "New"}, {"missing": ["Security+"], "status": "Saved"},
            {"missing": ["Kubernetes"], "status": "Skipped"}]
    out, notes, gaps = rr.review(MASTER, PROFILE, jobs, client=client(output(), seen=seen))
    assert gaps == [("Security+", 2), ("Intune", 1)]
    prompt = seen["messages"][0]["content"]
    assert "IT Support" in prompt and "Security+ (2)" in prompt and "jane@" not in prompt
    assert out.needs_number[0].question == "How many users?"


def test_review_errors():
    for stop, parsed in (("refusal", None), ("max_tokens", None)):
        with pytest.raises(RuntimeError):
            rr.review(MASTER, PROFILE, client=client(parsed, stop))
    with pytest.raises(ValueError):
        rr.review(MASTER, Profile({}), client=client(output()))


def test_real_profile_has_target_roles():
    assert rr.target_roles(Profile.load(ROOT / "config" / "profile.json"))
