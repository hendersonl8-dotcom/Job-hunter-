import pytest


@pytest.fixture(autouse=True)
def user_home(tmp_path, monkeypatch):
    """Keep tests out of the real per-user data folder."""
    monkeypatch.setenv("JOB_HUNTER_HOME", str(tmp_path / "home"))
