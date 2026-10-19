"""The Find jobs screen: pick what to search, run the live sources, see what turned up."""

from __future__ import annotations

from dataclasses import replace

import streamlit as st

from job_hunter import db
from job_hunter.collect import collect
from job_hunter.config import Settings, load_search_prefs, save_search_prefs
from job_hunter.scoring import Profile
from job_hunter.sources import SEATTLE_BOARDS
from job_hunter.sources.seattle_boards import board_key

DEFAULT_KEYWORDS = ["information technology specialist", "system administrator", "data analyst", "project manager"]


def split_lines(text: str) -> list[str]:
    return [line.strip() for line in text.replace(",", "\n").splitlines() if line.strip()]


def render(settings: Settings, conn, profile: Profile) -> None:
    prefs = load_search_prefs()
    st.subheader("Find jobs")
    st.caption("Searches USAJobs and the company boards you tick, keeps jobs in your area and scores them against your profile.")

    keywords = st.text_area("Search terms (one per line)", height=120, key="find-keywords",
                            value="\n".join(settings.usajobs_keywords or DEFAULT_KEYWORDS))
    location = st.text_input("Location", value=settings.usajobs_location, key="find-location")

    with st.expander("USAJobs key (one time)", expanded=not (settings.usajobs_api_key and settings.usajobs_email)):
        st.markdown("Federal jobs (JBLM, Kitsap, VA) need a free key from "
                    "[developer.usajobs.gov](https://developer.usajobs.gov/apirequest/). Paste it once; it is saved on this computer only.")
        key = st.text_input("USAJobs API key", value=prefs.get("usajobs_api_key", ""), type="password")
        email = st.text_input("Email you registered it with", value=prefs.get("usajobs_email", ""))

    chosen = set(prefs.get("boards", []))
    st.markdown("**Seattle-area company boards**")
    cols = st.columns(3)
    picked = []
    for i, (source, token, name) in enumerate(SEATTLE_BOARDS):
        k = board_key(source, token)
        if cols[i % 3].checkbox(f"{name} ({source.title()})", value=k in chosen, key=f"board-{k}"):
            picked.append(k)
    other = st.text_input("Other boards (optional, like greenhouse:companyname or lever:companyname)",
                          value=", ".join(k for k in prefs.get("boards", []) if k not in {board_key(s, t) for s, t, _ in SEATTLE_BOARDS}))
    picked += [k.strip() for k in other.split(",") if k.strip().count(":") == 1]

    st.caption("LinkedIn and Glassdoor can't be searched here; paste those postings in **Add a job**.")

    if st.button("Search now", type="primary"):
        terms = split_lines(keywords)
        save_search_prefs({**prefs, "usajobs_api_key": key.strip(), "usajobs_email": email.strip(),
                           "keywords": terms, "location": location.strip(), "boards": picked})
        run = replace(
            settings,
            usajobs_api_key=key.strip() or settings.usajobs_api_key,
            usajobs_email=email.strip() or settings.usajobs_email,
            usajobs_keywords=terms, usajobs_location=location.strip() or settings.usajobs_location,
            greenhouse_boards=[k.split(":", 1)[1] for k in picked if k.startswith("greenhouse:")],
            lever_boards=[k.split(":", 1)[1] for k in picked if k.startswith("lever:")],
        )
        with st.spinner("Searching job sources..."):
            result = collect(run, conn, profile)
        st.success(f"Found {result.found} jobs in your area, {result.added} new. They're in the **Jobs** tab, best fit first.")
        if result.skipped_location:
            st.caption(f"Left out {result.skipped_location} board jobs outside your area.")
        for error in result.errors:
            st.warning(error)

    if st.button("Re-score saved jobs"):
        st.success(f"Re-scored {db.rescore(conn, profile)} jobs with your current profile.")
