"""Home tab charts: pipeline funnel, applications per week and response rate by track.

The data functions are plain Python over rows from the database, so they are easy to test.
Colours come from the profile's chosen theme (themes.THEMES).
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from . import charts, db

FUNNEL = ["Saved", "Applied", "Interviewing", "Offer"]
APPLIED_STATUSES = {"Applied", "Interviewing", "Offer", "Rejected"}
# Any of these logged on an application counts as the employer getting back to you.
RESPONSES = {"Reply", "Interview", "Offer", "Rejection"}


def _applied(row: dict) -> bool:
    return bool(row.get("applied_at")) or row["status"] in APPLIED_STATUSES


def funnel_counts(jobs: list[dict], apps: list[dict]) -> dict[str, int]:
    """How many jobs reached each stage. A job that got an offer also counts as applied and saved."""
    logged = {a["key"]: a["logged"] for a in apps}
    applied = [j for j in jobs if _applied(j)]
    interviewing = [j for j in applied if j["status"] in ("Interviewing", "Offer")
                    or logged.get(j["key"], set()) & {"Interview", "Offer"}]
    offers = [j for j in applied if j["status"] == "Offer" or "Offer" in logged.get(j["key"], set())]
    saved = [j for j in jobs if j["status"] in ("Saved", "Applied", "Interviewing", "Offer") or _applied(j)]
    return {"Saved": len(saved), "Applied": len(applied), "Interviewing": len(interviewing), "Offer": len(offers)}


def _parse(day: str | None) -> date | None:
    try:
        return datetime.fromisoformat(str(day)[:19]).date()
    except (TypeError, ValueError):
        return None


def applications_per_week(jobs: list[dict]) -> pd.DataFrame:
    """One row per week (Monday start) from the first application to this week, zeros included."""
    days = [d for d in (_parse(j.get("applied_at")) for j in jobs) if d]
    if not days:
        return pd.DataFrame(columns=["Week", "Applications"])
    monday = lambda d: d - timedelta(days=d.weekday())  # noqa: E731
    counts = Counter(monday(d) for d in days)
    week, last = min(counts), max(max(counts), monday(date.today()))
    rows = []
    while week <= last:
        rows.append({"Week": pd.Timestamp(week), "Applications": counts.get(week, 0)})
        week += timedelta(days=7)
    return pd.DataFrame(rows)


def response_by_track(apps: list[dict]) -> pd.DataFrame:
    """Per track: applications sent, how many got any response, and the percentage."""
    sent: Counter = Counter()
    heard: Counter = Counter()
    for a in apps:
        track = a["track"] or "Other"
        sent[track] += 1
        if a["logged"] & RESPONSES or a["status"] in ("Interviewing", "Offer", "Rejected"):
            heard[track] += 1
    rows = [{"Track": t, "Applied": n, "Responses": heard[t], "Response rate": round(100 * heard[t] / n)}
            for t, n in sent.items()]
    return pd.DataFrame(rows, columns=["Track", "Applied", "Responses", "Response rate"]).sort_values(
        ["Response rate", "Applied"], ascending=False, ignore_index=True)


def style(chart: alt.Chart, height: int = 240) -> alt.Chart:
    p = charts.palette()
    return (chart.properties(height=height)
            .configure_axis(labelColor=p["muted"], titleColor=p["muted"], gridColor=p["muted"], gridOpacity=0.2,
                            domainColor=p["muted"], tickColor=p["muted"])
            .configure_view(strokeWidth=0))


def funnel_chart(counts: dict[str, int]) -> alt.Chart:
    p = charts.palette()
    df = pd.DataFrame({"Stage": FUNNEL, "Jobs": [counts[s] for s in FUNNEL]})
    bars = alt.Chart(df).mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y("Stage:N", sort=FUNNEL, title=None),
        x=alt.X("Jobs:Q", title=None, axis=alt.Axis(tickMinStep=1)),
        color=alt.Color("Stage:N", sort=FUNNEL, legend=None,
                        scale=alt.Scale(domain=FUNNEL, range=charts.stage_colors())),
        tooltip=["Stage", "Jobs"])
    labels = bars.mark_text(align="left", dx=4, color=p["text"]).encode(text="Jobs:Q")
    return style(bars + labels, 200)


def weekly_chart(df: pd.DataFrame) -> alt.Chart:
    p = charts.palette()
    bars = alt.Chart(df).mark_bar(color=p["accent"], cornerRadiusEnd=3).encode(
        x=alt.X("yearmonthdate(Week):T", title="Week starting", axis=alt.Axis(format="%b %d")),
        y=alt.Y("Applications:Q", title=None, axis=alt.Axis(tickMinStep=1)),
        tooltip=[alt.Tooltip("Week:T", format="%b %d"), "Applications"])
    return style(bars)


def response_chart(df: pd.DataFrame) -> alt.Chart:
    p = charts.palette()
    bars = alt.Chart(df).mark_bar(color=p["accent2"], cornerRadiusEnd=4).encode(
        y=alt.Y("Track:N", sort=None, title=None),
        x=alt.X("Response rate:Q", title="% that got a response", scale=alt.Scale(domain=[0, 100])),
        tooltip=["Track", "Applied", "Responses", "Response rate"])
    labels = bars.mark_text(align="left", dx=4, color=p["text"]).encode(
        text=alt.Text("Response rate:Q", format=".0f"))
    return style(bars + labels, max(120, 40 * len(df)))


def render(conn, jobs: list[dict], profile=None) -> None:
    st.subheader("How it's going")
    if not any(j["status"] not in ("New", "Skipped") for j in jobs):
        charts.empty("Charts appear here once you save or apply to a job.")
        return
    apps = db.application_rows(conn)
    left, right = st.columns(2)
    with left:
        st.markdown("**Pipeline funnel**")
        st.altair_chart(funnel_chart(funnel_counts(jobs, apps)), width="stretch")
    with right:
        st.markdown("**Applications per week**")
        weekly = applications_per_week(jobs)
        if weekly.empty:
            charts.empty("No applications yet. Mark a job as applied and it shows up here.")
        else:
            st.altair_chart(weekly_chart(weekly), width="stretch")
    st.markdown("**Response rate by job track**")
    rates = response_by_track(apps)
    if rates.empty:
        charts.empty("No applications yet, so there is no response rate to show.")
    else:
        st.altair_chart(response_chart(rates), width="stretch")
        st.caption("A response is any reply, interview, offer or rejection you've logged or moved the job to.")
