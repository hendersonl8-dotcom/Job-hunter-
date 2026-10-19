# PyInstaller spec. Build with packaging/build.ps1 (run from the repo root).
import os
from PyInstaller.utils.hooks import collect_all

ROOT = os.path.dirname(SPECPATH)  # spec paths resolve against the spec folder

datas = [(os.path.join(ROOT, n), n if os.path.isdir(os.path.join(ROOT, n)) else ".") for n in ("app.py", "config", "shortlists", ".streamlit")]
binaries, hiddenimports = [], ["job_hunter"]
for pkg in ("streamlit", "webview", "anthropic", "docx", "fpdf", "pypdf", "pandas"):
    try:
        d, b, h = collect_all(pkg)
    except Exception:
        continue
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis([os.path.join(ROOT, "desktop.py")], pathex=[ROOT], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports, noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="JobHunter", console=False,
          icon=os.path.join(SPECPATH, "icon.ico") if os.path.exists(os.path.join(SPECPATH, "icon.ico")) else None)
coll = COLLECT(exe, a.binaries, a.datas, name="JobHunter")
