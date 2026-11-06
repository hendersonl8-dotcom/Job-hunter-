"""The resume builder renders as a tab of the main app, sharing code with the standalone page."""

from __future__ import annotations

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from job_hunter import userdata

ROOT = Path(__file__).resolve().parent.parent
PROFILE = json.loads((ROOT / "config" / "profile.json").read_text(encoding="utf-8"))
MASTER = json.loads((ROOT / "config" / "resume.json").read_text(encoding="utf-8"))


def test_main_app_builder_tab_previews_resume():
    userdata.save_resume(MASTER)
    userdata.save_profile(PROFILE)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    assert not at.exception
    assert "Resume builder" in [t.label for t in at.tabs]
    first = MASTER["experience"][0]["bullets"][0]
    assert any(first in m.value for m in at.markdown)
    at.multiselect(key="rb-w-pick-role-0").set_value(["m1"]).run()
    assert not at.exception
    assert not any(first in m.value for m in at.markdown)
