"""Job Hunter as a desktop app: runs Streamlit in the background and shows it in a native window.

    python desktop.py            # from source (needs pywebview)
    JobHunter.exe                # the packaged app (see packaging/)

The window is the only thing the user sees: it opens at once on a "Starting" screen, then switches to the
Home dashboard as soon as the server answers. There is no browser, address bar or console. Closing the window
stops the background server, and the server also stops by itself if this launcher dies (it watches a pipe).
If pywebview is missing (a from-source install where it could not be installed) it falls back to the browser.
"""

from __future__ import annotations

import os
import socket
import threading
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SERVE_FLAG = "--serve"
CHECK_FLAG = "--check"  # run the real app script once headlessly; exit code 0 = it loads
TITLE = "Job Hunter"

SPLASH = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{height:100%;margin:0;font-family:"Segoe UI",system-ui,sans-serif;background:#F8FAFC;color:#0F172A}
.w{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px}
h1{margin:0;font-size:28px;font-weight:600}p{margin:0;color:#64748B}
.s{width:34px;height:34px;border:4px solid #CCFBF1;border-top-color:#0F766E;border-radius:50%;animation:r 1s linear infinite}
@keyframes r{to{transform:rotate(360deg)}}</style></head>
<body><div class="w"><div class="s"></div><h1>Job Hunter</h1><p>Starting up&hellip;</p></div></body></html>"""

FAILED = """<!doctype html><html><body style="font-family:Segoe UI,sans-serif;padding:40px;color:#0F172A">
<h2>Job Hunter could not start.</h2><p>Close this window and try again. If it keeps happening, send the file
<code>{log}</code> to whoever set this up for you.</p></body></html>"""

# Desktop-only Streamlit settings: no top bar, no developer menu, no "Deploy" button.
DESKTOP_FLAGS = {"ui.hideTopBar": True, "client.toolbarMode": "minimal"}


def log_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / "JobHunter"
    base.mkdir(parents=True, exist_ok=True)
    return base / "desktop.log"


def exit_when_launcher_closes() -> None:
    """The launcher holds our stdin pipe open; EOF means it is gone, so stop the server too."""
    def watch() -> None:
        try:
            while os.read(0, 1024):
                pass
        except OSError:
            pass
        os._exit(0)

    threading.Thread(target=watch, daemon=True).start()


def app_root() -> Path:
    """Folder holding app.py: the unpacked bundle when packaged, else this folder."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve(port: int) -> None:
    """Run Streamlit in this process (the child started by main())."""
    exit_when_launcher_closes()
    # No console in the desktop app, so keep Streamlit's output in a log file for troubleshooting.
    sys.stdout = sys.stderr = open(log_path(), "w", encoding="utf-8", buffering=1)
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
        **DESKTOP_FLAGS,
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


def stop(server: subprocess.Popen) -> None:
    try:
        server.stdin.close()  # tells the server to exit (see exit_when_launcher_closes)
    except OSError:
        pass
    try:
        server.wait(timeout=3)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=5)


def browser_fallback(url: str, server: subprocess.Popen) -> int:
    import webbrowser

    if wait_until_up(url, server):
        webbrowser.open(url)
        server.wait()  # keep running until the server is stopped (e.g. Ctrl+C)
    return 0


def main() -> int:
    if CHECK_FLAG in sys.argv:
        return check()
    if SERVE_FLAG in sys.argv:
        serve(int(sys.argv[sys.argv.index(SERVE_FLAG) + 1]))
        return 0

    port = free_port()
    url = f"http://127.0.0.1:{port}"
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, SERVE_FLAG, str(port)]
    else:
        cmd = [sys.executable, str(Path(__file__).resolve()), SERVE_FLAG, str(port)]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    server = subprocess.Popen(cmd, creationflags=flags, stdin=subprocess.PIPE,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        try:
            import webview
        except ImportError:  # from-source install without pywebview: use the browser instead
            return browser_fallback(url, server)

        window = webview.create_window(TITLE, html=SPLASH, width=1280, height=860, min_size=(900, 600),
                                       background_color="#F8FAFC")

        def load_when_ready() -> None:
            if wait_until_up(url, server):
                window.load_url(url)
            else:
                window.load_html(FAILED.format(log=log_path()))

        webview.start(load_when_ready)
    finally:
        stop(server)
    return 0


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    sys.exit(main())
