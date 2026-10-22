"""The "What's working" tab: log replies, interviews and offers, see response rates, and keep company research."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

import pandas as pd
import streamlit as st

from . import company_research, db


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
    else:
        _render_outcomes(conn, applications)
    st.divider()
    render_research(conn, applications)


def _render_outcomes(conn, applications: list[dict]) -> None:

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
    _render_edit_outcomes(conn, applications, labels)

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
    done = company_research.researched(conn)
    st.dataframe(
        pd.DataFrame([{
            "Title": a["title"], "Company": a["company"], "Track": a["track"], "Resume": resume_version(a),
            "Applied": a["applied_at"] or "", "Status": a["status"],
            "Logged": ", ".join(sorted(a["logged"])),
            "Research": "Yes" if company_research.key(a["company"]) in done else "",
        } for a in applications]),
        hide_index=True, width="stretch",
    )


def _render_edit_outcomes(conn, applications: list[dict], labels: dict[str, str]) -> None:
    """Fix or remove something you logged: wrong kind, wrong date, a note to add."""
    logged = [a["key"] for a in applications if a["logged"]]
    with st.expander("Edit what you've logged"):
        if not logged:
            st.caption("Nothing logged yet.")
            return
        key = st.selectbox("Application", logged, format_func=labels.get, key="edit-outcome-app")
        for row in db.outcomes_for(conn, key):
            with st.form(f"edit-outcome-{row['id']}"):
                c1, c2 = st.columns(2)
                kind = c1.selectbox("What happened", db.OUTCOMES, index=db.OUTCOMES.index(row["kind"])
                                    if row["kind"] in db.OUTCOMES else 0)
                when = c2.date_input("Date", value=date.fromisoformat(row["happened_on"]))
                note = st.text_input("Note", value=row["note"])
                save, remove = st.columns(2)
                if save.form_submit_button("Save changes"):
                    db.update_outcome(conn, row["id"], kind, when.isoformat(), note)
                    st.rerun()
                if remove.form_submit_button("Delete this entry"):
                    db.delete_outcome(conn, row["id"])
                    st.rerun()


def render_research(conn, applications: list[dict]) -> None:
    """Notes on each company: what they do, people, why you fit, questions to ask. Editable any time."""
    st.markdown("**Company research**")
    st.caption("Notes are kept per company, so every job you track there shares them.")
    known = company_research.companies(conn)
    applied = [a["company"] for a in applications]
    first = next((known.index(c) for c in applied if c in known), 0)
    c1, c2 = st.columns(2)
    picked = c1.selectbox("Company", known, index=first, key="research-company") if known else None
    typed = c2.text_input("Or type another company", key="research-new").strip()
    company = typed or picked
    if not company:
        st.info("Add a job or type a company name to start notes.")
        return

    notes = company_research.get(conn, company)
    slug = notes["company"]
    with st.form(f"research-{slug}"):
        st.markdown(f"Notes on **{notes['name'] or company}**")
        values = {}
        for field, (label, hint) in company_research.FIELDS.items():
            values[field] = st.text_area(label, value=notes[field], placeholder=hint, height=80,
                                         key=f"research-{slug}-{field}")
        if st.form_submit_button("Save notes"):
            company_research.save(conn, company, values)
            st.success(f"Saved notes on {company}.")
    if notes["updated_at"]:
        st.caption(f"Last saved {notes['updated_at']} (UTC).")
        if st.button("Delete these notes", key=f"research-delete-{slug}"):
            company_research.delete(conn, company)
            st.rerun()
