"""Job Hunter dashboard. Run with:  streamlit run app.py"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from job_hunter import db
from job_hunter.collect import CollectResult, collect, save_jobs
from job_hunter.config import load_settings
from job_hunter.scoring import Profile
from job_hunter.sources import job_from_paste

st.set_page_config(page_title="Job Hunter", page_icon="🧭", layout="wide")


@st.cache_resource
def connection(path: str):
    return db.connect(path)


settings = load_settings()
profile = Profile.load(settings.profile)
conn = connection(str(settings.database))


def money(low, high) -> str:
    if low is None and high is None:
        return "Not listed"
    if low == high or high is None:
        return f"${low:,.0f}"
    return f"${low:,.0f} – ${high:,.0f}"


st.title("Job Hunter")
st.caption(f"Scoring against your profile: {profile.clearance or 'no'} clearance, pay floor ${profile.min_salary:,.0f}.")

jobs_tab, compare_tab, add_tab, find_tab = st.tabs(["Jobs", "Compare", "Add a job", "Find new jobs"])

jobs = db.all_jobs(conn)

with jobs_tab:
    if not jobs:
        st.info("No jobs yet. Use **Find new jobs** or paste one in **Add a job**.")
    else:
        tracks = sorted({j["track"] for j in jobs})
        c1, c2, c3, c4 = st.columns(4)
        track_filter = c1.multiselect("Track", tracks, default=tracks)
        status_filter = c2.multiselect("Status", db.STATUSES, default=[s for s in db.STATUSES if s not in ("Skipped", "Rejected")])
        min_score = c3.slider("Minimum fit", 0, 100, 0)
        hide_low_pay = c4.checkbox("Hide jobs under my pay floor", value=True)

        shown = [
            j for j in jobs
            if j["track"] in track_filter and j["status"] in status_filter and j["score"] >= min_score
            and not (hide_low_pay and j["salary_max"] is not None and j["salary_max"] < profile.min_salary)
        ]
        table = pd.DataFrame(
            [{
                "Fit": j["score"], "Title": j["title"], "Company": j["company"], "Track": j["track"],
                "Pay": money(j["salary_min"], j["salary_max"]), "Clearance": j["clearance"] or "None",
                "Location": j["location"], "Status": j["status"], "Source": j["source"],
            } for j in shown]
        )
        st.caption(f"{len(shown)} of {len(jobs)} jobs. Tick rows to compare them or see details.")
        picked = st.dataframe(
            table, hide_index=True, width="stretch", on_select="rerun", selection_mode="multi-row",
            column_config={"Fit": st.column_config.ProgressColumn("Fit", min_value=0, max_value=100, format="%d")},
        )
        st.session_state["picked"] = [shown[i]["key"] for i in picked.selection.rows]

        for key in st.session_state["picked"][:1]:
            job = next(j for j in jobs if j["key"] == key)
            st.divider()
            st.subheader(f"{job['title']} · {job['company']}")
            left, right = st.columns([2, 1])
            with left:
                st.markdown("**Why it scored " + str(job["score"]) + "**")
                st.markdown("\n".join(f"- {r}" for r in job["reasons"]))
                st.markdown("**You have:** " + (", ".join(job["matched"]) or "none of the tracked skills"))
                st.markdown("**It wants that you don't list yet:** " + (", ".join(job["missing"]) or "nothing"))
                with st.expander("Full description"):
                    st.text(job["description"] or "No description saved.")
            with right:
                if job["url"]:
                    st.link_button("Open posting", job["url"])
                with st.form(f"status-{key}"):
                    status = st.selectbox("Status", db.STATUSES, index=db.STATUSES.index(job["status"]))
                    notes = st.text_area("Notes", job["notes"])
                    if st.form_submit_button("Save"):
                        db.set_status(conn, key, status, notes)
                        st.rerun()

with compare_tab:
    keys = st.session_state.get("picked", [])
    if len(keys) < 2:
        st.info("Tick two to four jobs in the **Jobs** tab to compare them side by side.")
    else:
        chosen = [next(j for j in jobs if j["key"] == k) for k in keys[:4]]
        rows = {
            "Fit": [f"{j['score']}/100" for j in chosen],
            "Track": [j["track"] for j in chosen],
            "Pay": [money(j["salary_min"], j["salary_max"]) for j in chosen],
            "Clearance": [j["clearance"] or "None" for j in chosen],
            "Location": [j["location"] for j in chosen],
            "Skills you have": [", ".join(j["matched"]) for j in chosen],
            "Skills to add": [", ".join(j["missing"]) for j in chosen],
            "Status": [j["status"] for j in chosen],
            "Source": [j["source"] for j in chosen],
        }
        columns = [f"{j['title']} · {j['company']}" for j in chosen]
        st.dataframe(pd.DataFrame(rows, index=columns).T, width="stretch")
        best = max(chosen, key=lambda j: j["score"])
        st.success(f"Best fit: **{best['title']}** at **{best['company']}** ({best['score']}/100).")

with add_tab:
    st.markdown(
        "Paste a job from **LinkedIn, Glassdoor, Indeed** or anywhere else. "
        "The app doesn't fetch those sites; paste the description text so it can score it."
    )
    with st.form("add-job", clear_on_submit=True):
        url = st.text_input("Link to the posting")
        title = st.text_input("Job title")
        company = st.text_input("Company")
        location = st.text_input("Location", placeholder="Seattle, WA")
        description = st.text_area("Job description", height=260)
        if st.form_submit_button("Add and score"):
            try:
                job = job_from_paste(title, company, description, url=url, location=location)
            except ValueError as exc:
                st.error(str(exc))
            else:
                result = CollectResult()
                save_jobs(conn, profile, [job], result, filter_location=False)
                fit = profile.score(job)
                st.success(f"Added **{job.title}**: fit {fit.score}/100, {fit.track} track." if result.added
                           else f"Updated **{job.title}**, which was already saved: fit {fit.score}/100.")

with find_tab:
    st.markdown(
        f"Searches USAJobs ({len(settings.usajobs_keywords)} keywords around {settings.usajobs_location}), "
        f"{len(settings.greenhouse_boards)} Greenhouse boards and {len(settings.lever_boards)} Lever boards "
        "from `config/settings.toml`."
    )
    if not (settings.usajobs_api_key and settings.usajobs_email):
        st.warning("USAJobs is off until you set USAJOBS_API_KEY and USAJOBS_EMAIL. See the README.")
    c1, c2 = st.columns(2)
    if c1.button("Search now", type="primary"):
        with st.spinner("Searching job sources..."):
            result = collect(settings, conn, profile)
        st.success(f"Found {result.found} jobs in your area, {result.added} new.")
        if result.skipped_location:
            st.caption(f"Left out {result.skipped_location} board jobs outside your area.")
        for error in result.errors:
            st.warning(error)
    if c2.button("Re-score saved jobs"):
        st.success(f"Re-scored {db.rescore(conn, profile)} jobs with your current profile.")
