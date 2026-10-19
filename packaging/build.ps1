# Builds installer\JobHunter-Setup.exe. Run from the repo root in PowerShell:
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1
# Needs Python 3.11+ and Inno Setup 6 (winget install JRSoftware.InnoSetup).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

python -m venv .build-venv
& .\.build-venv\Scripts\python.exe -m pip install --quiet --upgrade pip
& .\.build-venv\Scripts\python.exe -m pip install --quiet -r requirements.txt -r packaging\requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
& .\.build-venv\Scripts\python.exe -m PyInstaller --noconfirm packaging\JobHunter.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
if (-not $iscc) { $iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
& $iscc packaging\installer.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
Write-Host "Built installer\JobHunter-Setup.exe"
