# One-step install for Windows. From this folder in PowerShell:
#   powershell -ExecutionPolicy Bypass -File .\install.ps1
# Creates the virtual environment, installs the requirements, and puts a "Job Hunter"
# shortcut on your Desktop. Safe to run again (it updates the requirements).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = $null
foreach ($candidate in @("py -3", "python")) {
    $exe = $candidate.Split(" ")[0]
    if (Get-Command $exe -ErrorAction SilentlyContinue) { $python = $candidate; break }
}
if (-not $python) {
    Write-Host "Python 3.11 or newer is not installed. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH'), then run this again."
    exit 1
}

Write-Host "Creating the virtual environment..."
Invoke-Expression "$python -m venv .venv"
if ($LASTEXITCODE -ne 0) { Write-Host "Could not create the virtual environment."; exit 1 }
Write-Host "Installing requirements (a minute or two the first time)..."
& .\.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
& .\.venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Host "Installing the requirements failed. Check your internet connection and run this again."; exit 1 }

# Launcher: starts the app and keeps its window open while you use it.
$launcher = Join-Path $PSScriptRoot "Job Hunter.cmd"
Set-Content -Path $launcher -Encoding ASCII -Value @(
    "@echo off",
    "cd /d ""%~dp0""",
    "title Job Hunter - close this window to stop the app",
    ".venv\Scripts\streamlit.exe run app.py"
)

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop "Job Hunter.lnk"))
$shortcut.TargetPath = $launcher
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.Save()

$data = Join-Path $env:LOCALAPPDATA "JobHunter"
Write-Host ""
Write-Host "Done. Double-click 'Job Hunter' on your Desktop to start it (it opens at http://localhost:8501)."
Write-Host "Your profile, resume and jobs are kept in $data, separate from this folder."
