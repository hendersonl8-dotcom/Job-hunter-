"""Job Hunter as a desktop app: runs Streamlit in the background and shows it in a native window.

    python desktop.py            # from source (needs pywebview)
    JobHunter.exe                # the packaged app (see packaging/)

The window is the only thing the user sees; closing it stops the background server.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SERVE_FLAG = "--serve"
CHECK_FLAG = "--check"  # run the real app script once headlessly; exit code 0 = it loads
TITLE = "Job Hunter"


def app_root() -> Path:
    """Folder holding app.py: the unpacked bundle when packaged, else this folder."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve(port: int) -> None:
    """Run Streamlit in this process (the child started by main())."""
    if sys.stdout is None:  # windowed exe has no console
        sys.stdout = sys.stderr = open(os.devnull, "w")
    from streamlit.web import bootstrap

    root = app_root()
    os.chdir(root)
    flags = {
        "server.headless": True,
        "server.port": port,
        "server.address": "127.0.0.1",
        "server.fileWatcherType": "none",
        "browser.gatherUsageStats": False,
        "global.developmentMode": False,
    }
    bootstrap.load_config_options(flag_options=flags)
    bootstrap.run(str(root / "app.py"), False, [], flags)


def wait_until_up(url: str, process: subprocess.Popen, timeout: float = 60) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline and process.poll() is None:
        try:
            urllib.request.urlopen(url + "/_stcore/health", timeout=1)
            return True
        except OSError:
            time.sleep(0.3)
    return False


def check() -> int:
    import tempfile

    os.environ["JOB_HUNTER_HOME"] = tempfile.mkdtemp()
    os.chdir(app_root())
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(app_root() / "app.py"), default_timeout=60).run()
    return 1 if at.exception else 0


def main() -> int:
    if CHECK_FLAG in sys.argv:
        return check()
    if SERVE_FLAG in sys.argv:
        serve(int(sys.argv[sys.argv.index(SERVE_FLAG) + 1]))
        return 0

    import webview

    port = free_port()
    url = f"http://127.0.0.1:{port}"
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, SERVE_FLAG, str(port)]
    else:
        cmd = [sys.executable, str(Path(__file__).resolve()), SERVE_FLAG, str(port)]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    server = subprocess.Popen(cmd, creationflags=flags)
    try:
        if not wait_until_up(url, server):
            webview.create_window(TITLE, html="<h2>Job Hunter could not start.</h2>")
        else:
            webview.create_window(TITLE, url, width=1280, height=860, min_size=(900, 600))
        webview.start()
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
    return 0


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    sys.exit(main())
