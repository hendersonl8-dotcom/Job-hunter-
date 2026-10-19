"""Job Hunter dashboard. Run with:  streamlit run app.py"""

from __future__ import annotations

import csv
import os
import re
from datetime import date

import pandas as pd
import streamlit as st

from job_hunter import cover_letter as letters
from job_hunter import db, export, onboarding, onboarding_screen, outcomes_tab
from job_hunter.backup import backup_database
from job_hunter import resume as resumes
from job_hunter.collect import CollectResult, collect, save_jobs
from job_hunter.config import ROOT, load_settings
from job_hunter.corrections import Corrections
from job_hunter.evidence_panel import evidence_panel
from job_hunter.scoring import Profile
from job_hunter.sources import job_from_paste, jobs_from_csv

st.set_page_config(page_title="Job Hunter", page_icon="🧭", layout="wide")


@st.cache_resource
def connection(path: str):
    return db.connect(path)


settings = load_settings()
if onboarding.needs_onboarding(settings.profile, settings.resume):
    onboarding_screen.render(settings)
    st.stop()
profile = Profile.load(settings.profile)
conn = connection(str(settings.database))
profile.corrections = Corrections(conn)
master = resumes.load_master(settings.resume)


def money(low, high) -> str:
    if low is None and high is None:
        return "Not listed"
    if low == high or high is None:
        return f"${low:,.0f}"
    return f"${low:,.0f} – ${high:,.0f}"


def file_stem(job: dict) -> str:
    name = master["contact"]["name"].replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9_-]+", "_", f"{name}_{job['company']}_{job['title']}")[:90]


def download_buttons(resume: dict, stem: str, prefix: str, what: str = "") -> None:
    c1, c2 = st.columns(2)
    c1.download_button(f"Download {what}Word", export.to_docx(resume), f"{stem}.docx",
                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"{prefix}-docx")
    c2.download_button(f"Download {what}PDF", export.to_pdf(resume), f"{stem}.pdf", "application/pdf", key=f"{prefix}-pdf")


def has_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def resume_panel(job: dict) -> dict:
    """Show the resume section and return the resume to send: tailored if there is one, else the base."""
    st.divider()
    st.subheader("Resume for this job")
    base = resumes.base_resume(master, job["track"])
    saved = db.latest_document(conn, job["key"], "resume")
    has_key = has_api_key()

    label = "Re-tailor my resume" if saved else "Tailor my resume to this job"
    if st.button(label, type="primary", disabled=not has_key, key=f"tailor-{job['key']}"):
        with st.spinner("Claude is tailoring your resume. This takes about a minute..."):
            try:
                tailored, raw, warnings = resumes.tailor(master, job, model=settings.claude_model,
                                                         effort=settings.claude_effort)
            except Exception as exc:
                st.error(f"Tailoring failed: {exc}")
            else:
                saved = {"resume": tailored, "changes": raw.changes, "gaps": raw.gaps, "warnings": warnings}
                db.save_document(conn, job["key"], "resume", saved)
    if not has_key:
        st.caption("Set ANTHROPIC_API_KEY to turn on tailoring (see the README)."
                   + ("" if saved else f" Meanwhile you can download your {job['track']} base resume below."))

    if not saved:
        st.markdown(f"**Base resume for the {job['track']} track**")
        download_buttons(base, file_stem(job) + "_base", f"base-{job['key']}")
        return base

    changes_tab, diff_tab, files_tab = st.tabs(["What changed", "Line by line", "Download"])
    with changes_tab:
        if saved["warnings"]:
            st.warning("Double-check these before sending; they aren't in your master resume:\n\n"
                       + "\n".join(f"- {w}" for w in saved["warnings"]))
        st.markdown("\n".join(f"- {c}" for c in saved["changes"]) or "No changes listed.")
        if saved["gaps"]:
            st.markdown("**The posting asks for things your resume can't honestly claim yet:**")
            st.markdown("\n".join(f"- {g}" for g in saved["gaps"]))
    with diff_tab:
        st.caption("Green lines are new or reworded for this job; red lines were cut or replaced.")
        colors = {"+": "rgba(46,160,67,0.2)", "-": "rgba(248,81,73,0.2)", " ": "transparent"}
        rows = "".join(
            f'<div style="background:{colors[kind]};padding:1px 6px;white-space:pre-wrap">'
            f'{"+ " if kind == "+" else "- " if kind == "-" else "  "}{text.replace("<", "&lt;")}</div>'
            for kind, text in resumes.diff(base, saved["resume"])
        )
        st.markdown(f'<div style="font-size:0.85rem">{rows}</div>', unsafe_allow_html=True)
    with files_tab:
        download_buttons(saved["resume"], file_stem(job), f"tailored-{job['key']}")
    return saved["resume"]


def letter_buttons(letter: dict, stem: str, prefix: str, what: str = "") -> None:
    c1, c2 = st.columns(2)
    c1.download_button(f"Download {what}Word", export.letter_to_docx(letter), f"{stem}_cover_letter.docx",
                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"{prefix}-docx")
    c2.download_button(f"Download {what}PDF", export.letter_to_pdf(letter), f"{stem}_cover_letter.pdf", "application/pdf",
                       key=f"{prefix}-pdf")


def cover_letter_panel(job: dict, resume: dict) -> dict | None:
    """Show the cover letter section and return the latest letter for this job, if any."""
    st.divider()
    st.subheader("Cover letter for this job")
    saved = db.latest_document(conn, job["key"], "cover_letter")
    label = "Rewrite the cover letter" if saved else "Write a cover letter for this job"
    if st.button(label, type="primary", disabled=not has_api_key(), key=f"letter-{job['key']}"):
        with st.spinner("Claude is writing your cover letter..."):
            try:
                letter = letters.write(resume, job, model=settings.claude_model, effort=settings.claude_effort)
            except Exception as exc:
                st.error(f"Writing the cover letter failed: {exc}")
            else:
                saved = {"letter": letters.as_document(letter, master["contact"], job),
                         "warnings": letters.check_facts(master, letter, profile)}
                db.save_document(conn, job["key"], "cover_letter", saved)
    if not has_api_key():
        st.caption("Set ANTHROPIC_API_KEY to turn on cover letters (see the README).")
    if not saved:
        return None
    if saved["warnings"]:
        st.warning("Double-check these before sending; they aren't in your master resume:\n\n"
                   + "\n".join(f"- {w}" for w in saved["warnings"]))
    with st.expander("Read the letter", expanded=False):
        st.text(letters.as_text(saved["letter"]))
    letter_buttons(saved["letter"], file_stem(job), f"letter-{job['key']}")
    return saved["letter"]


@st.dialog("Ready to apply?", width="large")
def apply_dialog(job: dict, resume: dict, letter: dict | None) -> None:
    tailored = db.latest_document(conn, job["key"], "resume") is not None
    st.markdown(f"You're about to apply to **{job['title']}** at **{job['company']}**.")
    resume_note = "tailored for this job" if tailored else f"your {job['track']} base resume (not tailored)"
    letter_note = "written for this job" if letter else "none yet"
    st.markdown(f"- Resume: {resume_note}\n- Cover letter: {letter_note}")
    if not tailored or not letter:
        st.caption("You can still apply, or cancel and use the buttons above first.")
    st.markdown("**Download what you'll upload:**")
    download_buttons(resume, file_stem(job), f"apply-resume-{job['key']}", "resume as ")
    if letter:
        letter_buttons(letter, file_stem(job), f"apply-letter-{job['key']}", "cover letter as ")

    confirmed = st.session_state.get(f"applied-{job['key']}")
    if not confirmed:
        st.markdown("Pressing **Yes, apply** marks this job as Applied with today's date and gives you the "
                    "link to the application page. Nothing is submitted for you; you send it on the employer's site.")
        c1, c2 = st.columns(2)
        if c1.button("Yes, apply", type="primary", key=f"confirm-{job['key']}"):
            db.mark_applied(conn, job["key"], date.today().isoformat())
            db.record_send(conn, job["key"], date.today().isoformat())
            st.session_state[f"applied-{job['key']}"] = True
            st.rerun(scope="fragment")
        if c2.button("Cancel", key=f"cancel-{job['key']}"):
            st.rerun()
    else:
        st.success("Marked as Applied. Open the application page, upload your files and submit.")
        if job.get("apply_url"):
            st.link_button("Open the application page", job["apply_url"], type="primary")
        else:
            st.caption("This job has no application link saved. Use the posting's own site.")
        if st.button("Done", key=f"done-{job['key']}"):
            st.session_state.pop(f"applied-{job['key']}", None)
            st.rerun()


def history_panel(job: dict) -> None:
    history = db.document_history(conn, job["key"])
    if not history:
        return
    with st.expander(f"Version history ({len(history)})"):
        for doc in history:
            kind = "Resume" if doc["kind"] == "resume" else "Cover letter"
            sent = f" - sent {doc['sent_at']}" if doc["sent_at"] else ""
            st.markdown(f"**{kind}**, made {doc['created_at']}{sent}")
            content = doc["content"]
            if doc["kind"] == "cover_letter":
                st.text(letters.as_text(content["letter"]))
            else:
                st.text("\n".join(resumes.resume_lines(content["resume"])))


def apply_panel(job: dict, resume: dict, letter: dict | None) -> None:
    st.divider()
    if job["status"] == "Applied" and job.get("applied_at"):
        st.caption(f"You applied on {job['applied_at']}.")
    if st.button("Apply to this job", type="primary", key=f"apply-{job['key']}"):
        apply_dialog(job, resume, letter)


st.title("Job Hunter")
st.caption(f"Scoring against your profile: {profile.clearance or 'no'} clearance, pay floor ${profile.min_salary:,.0f}.")

jobs_tab, compare_tab, add_tab, find_tab, working_tab = st.tabs(
    ["Jobs", "Compare", "Add a job", "Find new jobs", "What's working"])

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
                "Location": j["location"], "Status": j["status"], "Applied": j.get("applied_at") or "",
                "Source": j["source"],
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
                evidence_panel(conn, profile, job)
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
            resume = resume_panel(job)
            letter = cover_letter_panel(job, resume)
            apply_panel(job, resume, letter)
            history_panel(job)

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

    st.divider()
    st.markdown("**Import a job list** saved as CSV, such as the Seattle shortlists from your project.")
    for path in sorted((ROOT / "shortlists").glob("*.csv")):
        if st.button(f"Load {path.stem}", key=f"load-{path.name}"):
            result = CollectResult()
            save_jobs(conn, profile, jobs_from_csv(path.read_text(encoding="utf-8")), result, filter_location=False)
            st.success(f"Loaded {result.found} jobs, {result.added} new. They're in the **Jobs** tab.")
    upload = st.file_uploader("Or upload a CSV", type="csv")
    if upload and st.button("Import uploaded list"):
        try:
            jobs = jobs_from_csv(upload.getvalue().decode("utf-8-sig"))
        except (UnicodeDecodeError, csv.Error) as exc:
            st.error(f"Couldn't read that file: {exc}")
        else:
            result = CollectResult()
            save_jobs(conn, profile, jobs, result, filter_location=False)
            st.success(f"Loaded {result.found} jobs, {result.added} new. They're in the **Jobs** tab.")

with find_tab:
    st.markdown(
        f"Searches USAJobs ({len(settings.usajobs_keywords)} keywords around {settings.usajobs_location}), "
        f"{len(settings.greenhouse_boards)} Greenhouse boards and {len(settings.lever_boards)} Lever boards "
        "from `config/settings.toml`."
    )
    if not (settings.usajobs_api_key and settings.usajobs_email):
        st.warning("USAJobs is off until you set USAJOBS_API_KEY and USAJOBS_EMAIL. See the README.")
    c1, c2, c3 = st.columns(3)
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
    if c3.button("Back up the database"):
        copy = backup_database(settings.database)
        st.success(f"Saved a copy to {copy}") if copy else st.info("Nothing to back up yet.")

with working_tab:
    outcomes_tab.render(conn)
