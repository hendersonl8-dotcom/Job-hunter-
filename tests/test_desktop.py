"""The desktop launcher's background server starts, and stops once the launcher's pipe closes."""

import subprocess
import sys
from pathlib import Path

import desktop

ROOT = Path(__file__).resolve().parent.parent


def test_server_stops_when_launcher_goes_away(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("JOB_HUNTER_HOME", str(tmp_path / "home"))
    port = desktop.free_port()
    server = subprocess.Popen([sys.executable, str(ROOT / "desktop.py"), desktop.SERVE_FLAG, str(port)],
                              stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert desktop.wait_until_up(f"http://127.0.0.1:{port}", server, timeout=60)
        server.stdin.close()  # what happens if the launcher crashes or is killed
        assert server.wait(timeout=10) == 0
    finally:
        if server.poll() is None:
            server.kill()
    assert (tmp_path / "JobHunter" / "desktop.log").exists()
