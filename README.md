# Job Hunter

Finds Seattle-area jobs, scores each one against your skills, and lets you compare them side by side.

Pick any job and it tailors your resume and writes a cover letter for that posting with Claude, then walks you through applying.

## What it does

- **Pulls jobs** from USAJobs (federal jobs around Seattle, JBLM and Kitsap) and from any company job board hosted on Greenhouse or Lever.
- **Takes jobs you paste** from LinkedIn, Glassdoor, Indeed or anywhere else. It never scrapes LinkedIn or Glassdoor, because their terms forbid it and accounts that use bots get restricted.
- **Scores every job 0 to 100** and shows why: skills you have versus skills it asks for (70), clearance (10), pay against your floor (10), and location (10).
- **Sorts jobs into tracks:** IT / Systems Admin, Data Analyst, Project Manager, Quality / Operations.
- **Compares 2 to 4 jobs** side by side and tracks status (Saved, Applied, Interviewing and so on) with notes.
- **Tailors your resume** to a job in one click: it reorders and rewords your own bullets toward the posting, lists what it changed and why, lists what the posting wants that you can't claim yet, and exports Word and PDF.
- **Writes a cover letter** for the job from the same facts, exported as Word and PDF.
- **Apply button:** asks you to confirm before anything happens, hands you the tailored resume and cover letter to download, marks the job Applied with today's date, and opens the employer's application page. You do the final submit on their site, so nothing is ever sent in your name without you seeing it.

## Install on Windows

**As a regular app (no Python needed):** run `JobHunter-Setup.exe` (built by the *Windows installer* GitHub Actions job, or locally with `packaging\build.ps1`). It adds Job Hunter to the Start Menu and Desktop; double-click it and the app opens in its own window. Closing the window stops it. Your data stays in `%LOCALAPPDATA%\JobHunter`.

**From source:**

1. Install Python 3.11 or newer from https://www.python.org/downloads/ (tick **Add python.exe to PATH**).
2. Download this project (green **Code** button, **Download ZIP**, then unzip) or `git clone` it.
3. In PowerShell, in the project folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

That creates the virtual environment, installs the requirements and puts a **Job Hunter** shortcut on your Desktop. Double-click it to start the app, then open `http://localhost:8501` if the browser doesn't open by itself. Closing the black window stops the app. To update later, replace the project files (or `git pull`) and run the installer again; your data is not touched.

Prefer to do it by hand? `py -3 -m venv .venv`, then `.venv\Scripts\python -m pip install -r requirements.txt`, then `.venv\Scripts\streamlit run app.py`.

## Where your data lives

Your profile, master resume, job database, backups and every generated resume and letter are stored per user in `%LOCALAPPDATA%\JobHunter` (on Mac or Linux, `~/.local/share/job-hunter`), not in the project folder. Each person who signs in to the PC with their own Windows account gets their own copy, and updating or re-downloading the app never touches it. Set the `JOB_HUNTER_HOME` environment variable to use a different folder, for example to keep a second profile.

| File | What it is |
| --- | --- |
| `profile.json` | Your skills, clearance, pay floor and locations (scoring) |
| `resume.json` | Your master resume |
| `jobs.db` | Saved jobs, status, notes, outcomes, tailored resumes and letters |
| `backups\` | Timestamped copies of `jobs.db` |

**Upgrading from the older layout** (files in the project's `config\` and `data\` folders): on first launch the app copies your `profile.json`, `resume.json` and `jobs.db` into the new folder, after saving a backup of the database. The old files are left where they were, so nothing is lost; you can delete them once you're happy.

## Turn on resume tailoring and cover letters

Tailoring uses Claude (`claude-opus-5-5` by default, set in `config/settings.toml`). Create an API key at https://console.anthropic.com/, then:

```powershell
setx ANTHROPIC_API_KEY "sk-ant-..."
```

Reopen PowerShell and restart the app. Each tailored resume or cover letter costs roughly 10 to 20 cents. Without a key you can still download the untailored base resume for each track.

**Your facts stay yours.** Everything comes from `resume.json` in your data folder, your master resume. Edit it when something changes; the tailoring never takes job titles, employers, dates, education or contact details from Claude, and any number, skill or certification it writes that isn't in your master resume is flagged in yellow before you download. Your phone number and email are never sent to Claude.

If a request is declined by Claude's safety checks, it is retried automatically on a fallback model.

## Turn on USAJobs

1. Request a free key at https://developer.usajobs.gov/apirequest/.
2. Set it for your user account, then reopen PowerShell:

```powershell
setx USAJOBS_API_KEY "your-key"
setx USAJOBS_EMAIL "the-email-you-registered@example.com"
```

The search keywords, location and radius are in `config/settings.toml`, which is shared by everyone using this copy of the app.

## Load the Seattle shortlist

Open **Add a job** and press **Load seattle-sweep-2026-10-19** to add the 34 Seattle-area postings researched for you, scored against your profile. You can also upload any CSV with the same columns (title, employer, location, pay_min, pay_max, clearance, key_requirements, posting_url).

## Add company job boards

Many employers host their careers page on Greenhouse or Lever. Find the board name in the careers URL and add it to `config/settings.toml`:

- `boards.greenhouse.io/<name>` or `job-boards.greenhouse.io/<name>` goes in `greenhouse = ["<name>"]`
- `jobs.lever.co/<name>` goes in `lever = ["<name>"]`

Jobs outside your locations (set in your `profile.json`) are left out. A wrong board name shows a warning and the rest of the search still runs.

## Tune the scoring

`profile.json` in your data folder holds your clearance, pay floor, locations, the title words for each track, and your skills. Each skill has the words that detect it in a posting, whether you **have** it, and a **weight** from 1 to 3. When you earn something, such as Security+ or AZ-104, set `"have": true` and press **Re-score saved jobs**.

## Tests

```powershell
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest
```
