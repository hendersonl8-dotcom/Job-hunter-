# Job Hunter

Finds Seattle-area jobs, scores each one against your skills, and lets you compare them side by side.

This is step 2 of the plan. Step 3 adds one-click resume tailoring, and step 4 adds the Apply button with a tailored cover letter.

## What it does

- **Pulls jobs** from USAJobs (federal jobs around Seattle, JBLM and Kitsap) and from any company job board hosted on Greenhouse or Lever.
- **Takes jobs you paste** from LinkedIn, Glassdoor, Indeed or anywhere else. It never scrapes LinkedIn or Glassdoor, because their terms forbid it and accounts that use bots get restricted.
- **Scores every job 0 to 100** and shows why: skills you have versus skills it asks for (70), clearance (10), pay against your floor (10), and location (10).
- **Sorts jobs into tracks:** IT / Systems Admin, Data Analyst, Project Manager, Quality / Operations.
- **Compares 2 to 4 jobs** side by side and tracks status (Saved, Applied, Interviewing and so on) with notes.

## Run it on Windows

From PowerShell, in the project folder:

```powershell
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\streamlit run app.py
```

It opens in your browser at http://localhost:8501. Jobs are saved in `data\jobs.db`, which is not uploaded to GitHub.

## Turn on USAJobs

1. Request a free key at https://developer.usajobs.gov/apirequest/.
2. Set it for your user account, then reopen PowerShell:

```powershell
setx USAJOBS_API_KEY "your-key"
setx USAJOBS_EMAIL "the-email-you-registered@example.com"
```

The search keywords, location and radius are in `config/settings.toml`.

## Add company job boards

Many employers host their careers page on Greenhouse or Lever. Find the board name in the careers URL and add it to `config/settings.toml`:

- `boards.greenhouse.io/<name>` or `job-boards.greenhouse.io/<name>` goes in `greenhouse = ["<name>"]`
- `jobs.lever.co/<name>` goes in `lever = ["<name>"]`

Jobs outside your locations (set in `config/profile.json`) are left out. A wrong board name shows a warning and the rest of the search still runs.

## Tune the scoring

`config/profile.json` holds your clearance, pay floor, locations, the title words for each track, and your skills. Each skill has the words that detect it in a posting, whether you **have** it, and a **weight** from 1 to 3. When you earn something, such as Security+ or AZ-104, set `"have": true` and press **Re-score saved jobs**.

## Tests

```powershell
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest
```
