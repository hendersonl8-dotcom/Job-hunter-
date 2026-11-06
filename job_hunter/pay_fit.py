"""Pay-vs-fit scatter for the Home tab: one dot per pipeline job; click a dot to open that job."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from . import charts, home_charts

PIPELINE = ("Saved", "Applied", "Interviewing", "Offer")


def points(jobs: list[dict]) -> tuple[pd.DataFrame, int]:
    """Rows for jobs in the pipeline with a listed pay, plus how many pipeline jobs list none."""
    rows, unlisted = [], 0
    for j in jobs:
        if j["status"] not in PIPELINE:
            continue
        pay = j["salary_max"] if j["salary_max"] is not None else j["salary_min"]
        if pay is None:
            unlisted += 1
            continue
        rows.append({"key": j["key"], "Job": f"{j['title']} · {j['company']}", "Fit": j["score"],
                     "Top pay": float(pay), "Status": j["status"]})
    return pd.DataFrame(rows, columns=["key", "Job", "Fit", "Top pay", "Status"]), unlisted


def chart(df: pd.DataFrame) -> alt.Chart:
    p = charts.palette()
    pick = alt.selection_point(name="pick", fields=["key"], on="click", clear="dblclick")
    dots = alt.Chart(df).mark_circle(size=140, opacity=0.85).encode(
        x=alt.X("Fit:Q", scale=alt.Scale(domain=[0, 100]), title="Fit score"),
        y=alt.Y("Top pay:Q", title="Top pay ($/yr)", axis=alt.Axis(format="$,.0f")),
        color=alt.Color("Status:N", scale=alt.Scale(domain=list(home_charts.FUNNEL), range=charts.stage_colors()),
                        legend=alt.Legend(orient="bottom", labelColor=p["text"], titleColor=p["muted"])),
        stroke=alt.condition(pick, alt.value(p["text"]), alt.value("transparent")),
        strokeWidth=alt.value(2),
        tooltip=["Job", "Fit", alt.Tooltip("Top pay:Q", format="$,.0f"), "Status"],
    ).add_params(pick)
    return home_charts.style(dots, 320)


def render(conn, jobs: list[dict], profile=None) -> None:
    st.subheader("Pay vs fit")
    df, unlisted = points(jobs)
    if df.empty:
        charts.empty("Save a job that lists its pay and it appears here as a dot."
                     + (f" {unlisted} pipeline job(s) list no pay." if unlisted else ""))
        return
    event = st.altair_chart(chart(df), width="stretch", on_select="rerun", key="pay-fit-chart")
    st.caption("Each dot is a job in your pipeline. Click one to see it below; double-click to clear."
               + (f" {unlisted} job(s) list no pay and are left out." if unlisted else ""))
    picked = (event.selection.get("pick") or []) if event else []
    keys = [p["key"] for p in picked if "key" in p]
    job = next((j for j in jobs if keys and j["key"] == keys[0]), None)
    if job:
        with st.container(border=True):
            st.markdown(f"**{job['title']}** · {job['company']}")
            st.write(f"Fit {job['score']} · {job['status']} · {job['location'] or 'location not listed'}")
            if job["url"]:
                st.link_button("Open posting", job["url"])
            st.caption("To edit it, tick it in the **Jobs** tab.")
