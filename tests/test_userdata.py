import json
import sqlite3

from job_hunter import userdata
from job_hunter.config import load_settings


def legacy_install(root):
    (root / "config").mkdir(parents=True)
    (root / "data").mkdir()
    (root / "config" / "profile.json").write_text('{"clearance": "TS/SCI"}')
    (root / "config" / "resume.json").write_text('{"contact": {"name": "Logan"}}')
    db = sqlite3.connect(root / "data" / "jobs.db")
    db.execute("CREATE TABLE jobs (key TEXT)")
    db.execute("INSERT INTO jobs VALUES ('a')")
    db.commit()
    db.close()


def test_existing_install_moves_over_and_originals_stay(tmp_path):
    root, home = tmp_path / "repo", tmp_path / "home"
    legacy_install(root)
    home.mkdir()
    assert sorted(userdata.migrate_legacy(home, root)) == ["jobs.db", "profile.json", "resume.json"]
    assert json.loads((home / "resume.json").read_text())["contact"]["name"] == "Logan"
    assert sqlite3.connect(home / "jobs.db").execute("SELECT key FROM jobs").fetchall() == [("a",)]
    assert list((root / "data" / "backups").glob("jobs-*-pre-move.db"))  # backup taken first
    assert (root / "data" / "jobs.db").exists() and (root / "config" / "resume.json").exists()


def test_migration_never_overwrites_and_runs_once(tmp_path):
    root, home = tmp_path / "repo", tmp_path / "home"
    legacy_install(root)
    home.mkdir()
    (home / "resume.json").write_text('{"mine": true}')
    userdata.migrate_legacy(home, root)
    assert json.loads((home / "resume.json").read_text()) == {"mine": True}
    assert userdata.migrate_legacy(home, root) == []


def test_fresh_install_starts_empty_so_onboarding_runs(tmp_path):
    root, home = tmp_path / "repo", tmp_path / "home"
    (root / "config").mkdir(parents=True)
    (root / "config" / "profile.json").write_text("{}")
    (root / "config" / "resume.json").write_text('{"contact": {"name": "Someone"}}')
    home.mkdir()
    assert userdata.migrate_legacy(home, root) == []


def test_save_resume_keeps_previous_version(tmp_path):
    userdata.save_resume({"v": 1})
    userdata.save_resume({"v": 2})
    assert userdata.load_resume() == {"v": 2}
    assert json.loads((userdata.user_dir() / "resume.json.bak").read_text()) == {"v": 1}


def test_settings_point_into_user_folder():
    settings = load_settings()
    assert settings.database.parent == settings.profile.parent == settings.resume.parent == userdata.user_dir()
