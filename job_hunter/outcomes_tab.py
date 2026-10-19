"""The "What's working" tab: log replies, interviews and offers, and see response rates."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

import pandas as pd
import streamlit as st

from . import db


def reached(application: dict) -> dict[str, bool]:
    """Which stages an application reached, from logged outcomes and from its status.

    Status counts too, so jobs you moved to Interviewing or Offer before outcome tracking
    existed still show up. A rejection is a response (they wrote back); an offer implies an interview.
    """
    logged, status = application["logged"], application["status"]
    offer = "Offer" in logged or status == "Offer"
    interview = "Interview" in logged or status == "Interviewing" or offer
    response = interview or "Reply" in logged or "Rejection" in logged or status == "Rejected"
    return {"Response": response, "Interview": interview, "Offer": offer}


def resume_version(application: dict) -> str:
    return "Tailored" if application["tailored"] else "Base resume"


def summarize(applications: list[dict], group: str) -> list[dict]:
    """Applied / response / interview / offer counts and rates per value of `group` ('track' or 'version')."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for app in applications:
        groups[resume_version(app) if group == "version" else app["track"]].append(app)
    rows = []
    for name, apps in sorted(groups.items()):
        counts = {stage: sum(reached(a)[stage] for a in apps) for stage in ("Response", "Interview", "Offer")}
        rows.append({
            "Group": name, "Applied": len(apps),
            **{stage: n for stage, n in counts.items()},
            **{f"{stage} rate": f"{n / len(apps):.0%}" for stage, n in counts.items()},
        })
    return rows


def render(conn) -> None:
    applications = db.application_rows(conn)
    if not applications:
        st.info("Nothing to track yet. Jobs show up here once you press **Apply** or set a job's status to Applied.")
        return

    st.markdown("**Log what happened**")
    labels = {a["key"]: f"{a['title']} · {a['company']} ({a['status']})" for a in applications}
    with st.form("log-outcome", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        key = c1.selectbox("Application", list(labels), format_func=labels.get)
        kind = c2.selectbox("What happened", db.OUTCOMES)
        when = c3.date_input("Date", value=date.today())
        note = st.text_input("Note (optional)")
        if st.form_submit_button("Log it"):
            db.record_outcome(conn, key, kind, when.isoformat(), note)
            st.rerun()

    total = len(applications)
    overall = {stage: sum(reached(a)[stage] for a in applications) for stage in ("Response", "Interview", "Offer")}
    cols = st.columns(4)
    cols[0].metric("Applied", total)
    for col, (stage, n) in zip(cols[1:], overall.items()):
        col.metric(stage + "s" if stage != "Response" else "Responses", f"{n} ({n / total:.0%})")
    if total < 10:
        st.caption("Small numbers so far; treat the rates as a hint, not a verdict.")

    st.markdown("**By role track**")
    st.dataframe(pd.DataFrame(summarize(applications, "track")).rename(columns={"Group": "Track"}),
                 hide_index=True, width="stretch")
    st.markdown("**By resume version**")
    st.caption("Tailored means a tailored resume was saved for that job; otherwise the base resume was the one available.")
    st.dataframe(pd.DataFrame(summarize(applications, "version")).rename(columns={"Group": "Resume"}),
                 hide_index=True, width="stretch")

    st.markdown("**Applications**")
    st.dataframe(
        pd.DataFrame([{
            "Title": a["title"], "Company": a["company"], "Track": a["track"], "Resume": resume_version(a),
            "Applied": a["applied_at"] or "", "Status": a["status"],
            "Logged": ", ".join(sorted(a["logged"])),
        } for a in applications]),
        hide_index=True, width="stretch",
    )
