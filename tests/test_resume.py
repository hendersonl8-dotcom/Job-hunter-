import io
from types import SimpleNamespace

import pytest
from docx import Document

from job_hunter import db, export
from job_hunter import resume as resumes
from job_hunter.config import ROOT


@pytest.fixture
def master():
    return resumes.load_master(ROOT / "config" / "resume.json")


@pytest.fixture
def job():
    return {
        "key": "usajobs:1", "title": "IT Specialist (SYSADMIN)", "company": "Department of the Navy",
        "location": "Silverdale, Washington", "clearance": "TS/SCI", "track": "IT / Systems Admin",
        "matched": ["Linux", "Windows Server"], "missing": ["Security+"],
        "description": "Administer Linux and Windows Server systems on classified networks.",
    }


def tailored_output(master, **overrides):
    roles = master["experience"]
    data = dict(
        headline="Systems Administrator | Active TS/SCI",
        summary="Systems administrator who stood up three network enclaves (270 virtual machines).",
        skills=[resumes.SkillGroup(name="Systems", items=["Linux (Ubuntu)", "Windows Server", "Active Directory"])],
        experience=[resumes.Role(source_index=i, bullets=r["bullets"][:3]) for i, r in enumerate(roles)],
        projects=[resumes.Project(source_index=0, bullets=master["projects"][0]["bullets"])],
        certifications=["Active TS/SCI security clearance"],
        changes=["Led with enclave and Linux work"],
        gaps=["Security+ certification"],
    )
    data.update(overrides)
    return resumes.TailoredResume(**data)


class FakeClient:
    def __init__(self, output, stop_reason="end_turn"):
        self.calls = []
        self.output, self.stop_reason = output, stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self.parse))

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(parsed_output=self.output, stop_reason=self.stop_reason)


def test_master_resume_is_complete(master):
    assert master["contact"]["name"] == "Logan Henderson"
    assert {"IT / Systems Admin", "Data Analyst", "Project Manager", "Quality / Operations", "Other"} <= set(master["tracks"])
    assert [r["dates"] for r in master["experience"]][-1] == "Nov 2019 – Sep 2023"


def test_base_resume_uses_track_and_falls_back(master):
    assert resumes.base_resume(master, "Data Analyst")["headline"].startswith("Data Analyst")
    assert resumes.base_resume(master, "Nonexistent")["headline"] == master["tracks"]["Other"]["headline"]


def test_assemble_keeps_facts_from_master(master):
    output = tailored_output(master, experience=[
        resumes.Role(source_index=1, bullets=["Led the standup of three network enclaves."]),
        resumes.Role(source_index=99, bullets=["Made up job"]),
    ])
    resume = resumes.assemble(master, output)
    titles = [r["title"] for r in resume["experience"]]
    assert titles == [r["title"] for r in master["experience"]]  # dropped roles come back, bad index ignored
    assert resume["experience"][1]["bullets"] == ["Led the standup of three network enclaves."]
    assert resume["contact"] == master["contact"] and resume["education"] == master["education"]


def test_check_facts_flags_invented_numbers_and_skills(master):
    honest = resumes.assemble(master, tailored_output(master))
    assert resumes.check_facts(master, honest) == []
    invented = resumes.assemble(master, tailored_output(
        master,
        summary="Managed 5,000 servers.",
        skills=[resumes.SkillGroup(name="Cloud", items=["Kubernetes"])],
        certifications=["CISSP"],
    ))
    warnings = resumes.check_facts(master, invented)
    assert any("5,000" in w for w in warnings)
    assert any("Kubernetes" in w for w in warnings)
    assert any("CISSP" in w for w in warnings)


def test_tailor_sends_job_and_returns_resume(master, job):
    client = FakeClient(tailored_output(master))
    resume, raw, warnings = resumes.tailor(master, job, client=client)
    call = client.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_format"] is resumes.TailoredResume
    assert call["fallbacks"] == "default" and call["betas"] == [resumes.FALLBACK_BETA]
    prompt = "".join(block["text"] for block in call["messages"][0]["content"])
    assert "IT Specialist (SYSADMIN)" in prompt and "Security+" in prompt
    assert "LoganHendersonNavy97" not in prompt  # contact details never go to the model
    assert resume["headline"].startswith("Systems Administrator") and raw.gaps == ["Security+ certification"]
    assert warnings == []


@pytest.mark.parametrize("stop_reason, output", [("refusal", None), ("max_tokens", None)])
def test_tailor_raises_on_unusable_answer(master, job, stop_reason, output):
    with pytest.raises(RuntimeError):
        resumes.tailor(master, job, client=FakeClient(output, stop_reason))


def test_diff_marks_added_and_removed_lines(master):
    base = resumes.base_resume(master, "IT / Systems Admin")
    tailored = resumes.assemble(master, tailored_output(master))
    kinds = {kind for kind, _ in resumes.diff(base, tailored)}
    assert {"+", "-"} <= kinds


def test_exports(master):
    resume = resumes.base_resume(master, "Project Manager")
    doc = Document(io.BytesIO(export.to_docx(resume)))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Logan Henderson" in text and "IT Project Manager" in text and "Nov 2019 – Sep 2023" in text
    pdf = export.to_pdf(resume)
    assert pdf.startswith(b"%PDF") and len(pdf) > 2000


def test_documents_round_trip():
    conn = db.connect(":memory:")
    assert db.latest_document(conn, "a:1", "resume") is None
    db.save_document(conn, "a:1", "resume", {"v": 1})
    db.save_document(conn, "a:1", "resume", {"v": 2})
    assert db.latest_document(conn, "a:1", "resume") == {"v": 2}
