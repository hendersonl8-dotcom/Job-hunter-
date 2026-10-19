# PyInstaller spec. Build with packaging/build.ps1 (run from the repo root).
from PyInstaller.utils.hooks import collect_all

datas = [("app.py", "."), ("config", "config"), ("shortlists", "shortlists"), (".streamlit", ".streamlit")]
binaries, hiddenimports = [], ["job_hunter"]
for pkg in ("streamlit", "pywebview", "webview", "anthropic", "docx", "fpdf", "pypdf", "pandas"):
    try:
        d, b, h = collect_all(pkg)
    except Exception:
        continue
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(["desktop.py"], pathex=["."], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports, noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="JobHunter", console=False,
          icon="packaging/icon.ico" if __import__("os").path.exists("packaging/icon.ico") else None)
coll = COLLECT(exe, a.binaries, a.datas, name="JobHunter")
