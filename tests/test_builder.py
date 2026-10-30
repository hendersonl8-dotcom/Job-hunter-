import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from job_hunter import builder, export, userdata

ROOT = Path(__file__).resolve().parent.parent
MASTER = json.loads((ROOT / "config" / "resume.json").read_text(encoding="utf-8"))


def test_default_draft_keeps_everything():
    draft = builder.default_draft(MASTER, "Data Analyst")
    resume = builder.compose(MASTER, draft)
    assert resume["headline"] == MASTER["tracks"]["Data Analyst"]["headline"]
    assert [r["bullets"] for r in resume["experience"]] == [r["bullets"] for r in MASTER["experience"]]
    assert resume["certifications"] == MASTER["certifications"]
    export.to_docx(resume), export.to_pdf(resume)


def test_picks_order_edits_and_own_points():
    draft = builder.default_draft(MASTER)
    draft["sections"]["role-1"] = {"on": True, "picked": ["m2", "c0", "m0"]}
    draft["sections"]["role-2"]["on"] = False
    draft["custom"]["role-1"] = ["My own point"]
    draft["edits"]["role-1:m0"] = "Reworded first point"
    resume = builder.compose(MASTER, draft)
    role = resume["experience"][1]
    assert role["title"] == MASTER["experience"][1]["title"]
    assert role["bullets"] == [MASTER["experience"][1]["bullets"][2], "My own point", "Reworded first point"]
    assert len(resume["experience"]) == len(MASTER["experience"]) - 1
    assert MASTER["experience"][1]["bullets"][0] != "Reworded first point"  # master untouched


def test_drafts_round_trip():
    draft = builder.default_draft(MASTER)
    builder.save_draft("Boeing / sys admin", draft)
    assert builder.list_drafts() == ["Boeing  sys admin"]
    assert builder.load_draft("Boeing  sys admin") == draft
    builder.delete_draft("Boeing  sys admin")
    assert builder.list_drafts() == []


def test_page_runs_and_previews():
    userdata.save_resume(MASTER)
    at = AppTest.from_file(str(ROOT / "resume_builder.py"), default_timeout=30).run()
    assert not at.exception
    first = MASTER["experience"][0]["bullets"][0]
    assert any(first in m.value for m in at.markdown)
    at.multiselect(key="rb-w-pick-role-0").set_value(["m1"]).run()
    assert not at.exception
    assert not any(first in m.value for m in at.markdown)
    at.text_area(key="rb-w-edit-role-0-m1").set_value("Edited wording here").run()
    assert any("Edited wording here" in m.value for m in at.markdown)


def test_page_without_resume_explains():
    at = AppTest.from_file(str(ROOT / "resume_builder.py"), default_timeout=30).run()
    assert not at.exception
    assert "no master resume" in at.info[0].value


def test_page_add_move_and_track():
    userdata.save_resume(MASTER)
    at = AppTest.from_file(str(ROOT / "resume_builder.py"), default_timeout=30).run()
    at.text_input(key="rb-w-new-role-0").set_value("Brand new point").run()
    at.button(key="rb-add-role-0").click().run()
    assert at.multiselect(key="rb-w-pick-role-0").value[-1] == "c0"
    assert any("Brand new point" in m.value for m in at.markdown)
    at.button(key="rb-up-role-0-c0").click().run()
    assert at.multiselect(key="rb-w-pick-role-0").value[-2] == "c0"
    at.selectbox(key="rb-w-track").set_value("Project Manager").run()
    assert at.text_input(key="rb-w-headline").value == MASTER["tracks"]["Project Manager"]["headline"]
    assert not at.exception
