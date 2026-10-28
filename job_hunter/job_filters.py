"""Filters for the Jobs tab: quick views like "Saved", and a minimum salary the user picks."""

from __future__ import annotations

from . import db

# Each quick view is the set of statuses it shows. "Open" leaves out jobs you've closed.
VIEWS = {
    "Open": [s for s in db.STATUSES if s not in ("Skipped", "Rejected")],
    "Saved": ["Saved"],
    "Applied": ["Applied", "Interviewing", "Offer"],
    "New": ["New"],
    "All": list(db.STATUSES),
}


def view_label(view: str, jobs: list[dict]) -> str:
    """The view's name with how many jobs are in it, e.g. "Saved (3)"."""
    return f"{view} ({sum(j['status'] in VIEWS[view] for j in jobs)})"


def meets_min_salary(job: dict, min_salary: float, hide_unlisted: bool = False) -> bool:
    """False only when the posting's top pay is under min_salary. Jobs with no pay listed pass unless hide_unlisted."""
    if job["salary_max"] is None:
        return not (hide_unlisted and min_salary > 0)
    return job["salary_max"] >= min_salary


# --- Sorting ------------------------------------------------------------------------------------

SORTS = ["Best fit", "Newest", "Highest pay"]


def sort_jobs(jobs: list[dict], how: str) -> list[dict]:
    """Jobs in the order asked for. Ties fall back to fit; jobs with no date or no pay go last."""
    if how == "Newest":
        return sorted(jobs, key=lambda j: (j.get("posted_at") or j.get("fetched_at") or "", j["score"]), reverse=True)
    if how == "Highest pay":
        return sorted(jobs, key=lambda j: (j["salary_max"] is not None, j["salary_max"] or 0, j["score"]), reverse=True)
    return sorted(jobs, key=lambda j: -j["score"])


# --- New since last visit -----------------------------------------------------------------------

def new_since(jobs: list[dict], last_visit: str | None) -> list[dict]:
    """Jobs first fetched after last_visit (an ISO time). With no earlier visit nothing counts as new."""
    if not last_visit:
        return []
    return [j for j in jobs if (j.get("fetched_at") or "") > last_visit]


# --- Saved searches and the last-visit time, kept in the user's data folder ----------------------

SETTINGS_FILE = "jobs_view.json"


def _path():
    from . import userdata
    return userdata.user_dir() / SETTINGS_FILE


def load_view_settings() -> dict:
    import json
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"presets": {}, "last_visit": None}
    return {"presets": data.get("presets") or {}, "last_visit": data.get("last_visit")}


def save_view_settings(data: dict) -> None:
    import json
    _path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def save_preset(name: str, filters: dict) -> None:
    data = load_view_settings()
    data["presets"][name.strip()] = filters
    save_view_settings(data)


def delete_preset(name: str) -> None:
    data = load_view_settings()
    data["presets"].pop(name, None)
    save_view_settings(data)


def touch_last_visit(now: str) -> str | None:
    """Record this visit and return the previous one, so the badge compares against the last session."""
    data = load_view_settings()
    previous = data["last_visit"]
    data["last_visit"] = now
    save_view_settings(data)
    return previous


# --- Pipeline export ----------------------------------------------------------------------------

PIPELINE_STATUSES = ["Saved", "Applied", "Interviewing", "Offer"]
CSV_COLUMNS = ["Status", "Fit", "Title", "Company", "Location", "Pay low", "Pay high", "Applied", "Posted", "Link", "Notes"]


def pipeline_csv(jobs: list[dict]) -> str:
    """The jobs in the pipeline stages as CSV text for a spreadsheet, in stage order, best fit first."""
    import csv
    import io

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    for status in PIPELINE_STATUSES:
        for j in sorted((j for j in jobs if j["status"] == status), key=lambda j: -j["score"]):
            writer.writerow([status, j["score"], j["title"], j["company"], j["location"] or "",
                             "" if j["salary_min"] is None else int(j["salary_min"]),
                             "" if j["salary_max"] is None else int(j["salary_max"]),
                             j.get("applied_at") or "", j.get("posted_at") or "", j["url"] or "",
                             (j["notes"] or "").replace("\n", " ")])
    return out.getvalue()
