from job_hunter import config
from job_hunter.find_screen import split_lines
from job_hunter.sources import SEATTLE_BOARDS


def test_saved_search_prefs_reach_settings(monkeypatch):
    monkeypatch.delenv("USAJOBS_API_KEY", raising=False)
    monkeypatch.delenv("USAJOBS_EMAIL", raising=False)
    config.save_search_prefs({"usajobs_api_key": "k", "usajobs_email": "a@b.c", "keywords": ["data analyst"],
                              "location": "Tacoma, Washington", "boards": ["greenhouse:remitly", "lever:highspot"]})
    s = config.load_settings()
    assert (s.usajobs_api_key, s.usajobs_email) == ("k", "a@b.c")
    assert s.usajobs_keywords == ["data analyst"] and s.usajobs_location == "Tacoma, Washington"
    assert "remitly" in s.greenhouse_boards and s.lever_boards == ["highspot"]


def test_env_key_wins_over_saved(monkeypatch):
    monkeypatch.setenv("USAJOBS_API_KEY", "env")
    config.save_search_prefs({"usajobs_api_key": "saved"})
    assert config.load_settings().usajobs_api_key == "env"


def test_split_lines_and_board_list():
    assert split_lines("a\n b ,c\n\n") == ["a", "b", "c"]
    assert len(set(SEATTLE_BOARDS)) == len(SEATTLE_BOARDS)
