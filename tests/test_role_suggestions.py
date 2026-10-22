from types import SimpleNamespace

from job_hunter import role_suggestions as rs
from job_hunter.scoring import Profile
from job_hunter.unexpected import unexpected_matches, unexpected_skills

MASTER = {"skills": {"Systems": ["Active Directory", "STIG compliance"]},
          "experience": [{"title": "IT Lead", "bullets": ["Audited 3 network enclaves for NIST compliance."]}]}
PROFILE = Profile({"tracks": {"IT Support": ["help desk"]}})


def client(parsed):
    def parse(**kw):
        return SimpleNamespace(stop_reason="end_turn", parsed_output=parsed)
    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(parse=parse)))


def role(title, evidence, terms=()):
    return rs.RoleSuggestion(title=title, reason="Fits.", evidence=list(evidence), search_terms=list(terms))


def test_suggest_drops_unsupported_known_and_duplicate_roles():
    out = rs.SuggestionOutput(roles=[
        role("Cybersecurity Analyst", ["STIG compliance", "made up phrase"], ["security analyst"]),
        role("Surgeon", ["performed surgery"]),                      # evidence not on resume
        role("IT Support", ["Active Directory"]),                    # already a track
        role("cybersecurity analyst", ["Active Directory"]),         # duplicate
    ])
    got = rs.suggest(MASTER, PROFILE, client=client(out))
    assert [r.title for r in got] == ["Cybersecurity Analyst"]
    assert got[0].evidence == ["STIG compliance"]


def test_add_roles_creates_tracks_and_terms_without_touching_the_original():
    data = {"tracks": {"IT Support": ["help desk"]}, "search_terms": ["help desk"]}
    new = rs.add_roles(data, [role("ISSO", ["NIST"], ["information system security officer"])])
    assert new["tracks"]["ISSO"] == ["isso", "information system security officer"]
    assert new["search_terms"] == ["help desk", "ISSO", "information system security officer"]
    assert "ISSO" not in data["tracks"]
    assert rs.add_roles(new, [role("ISSO", ["NIST"])])["search_terms"] == new["search_terms"]


def test_unexpected_matches_need_no_track_a_high_score_and_several_skills():
    strong = {"track": "Other", "score": 72, "matched": ["Linux", "Python", "SQL"], "status": "New"}
    jobs = [strong,
            {**strong, "track": "Data Analyst"},
            {**strong, "score": 40},
            {**strong, "matched": ["Linux"]},
            {**strong, "status": "Skipped"}]
    assert unexpected_skills(strong) == ["Linux", "Python", "SQL"]
    assert unexpected_matches(jobs) == [(strong, ["Linux", "Python", "SQL"])]
