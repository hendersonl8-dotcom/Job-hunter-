"""The Home tab: where you stand at a glance, and your jobs laid out by stage."""

from __future__ import annotations

import streamlit as st

from datetime import date

from . import db
from .theme import STAGE_COLORS, STAGES, badge, band, escape


def by_stage(jobs: list[dict]) -> dict[str, list[dict]]:
    """Jobs grouped into the pipeline stages, best fit first. New, Skipped and Rejected jobs are not in the pipeline."""
    return {stage: sorted((j for j in jobs if j["status"] == stage), key=lambda j: -j["score"]) for stage in STAGES}


def top_new(jobs: list[dict], pay_floor: float, limit: int = 5) -> list[dict]:
    """Best-scoring jobs you haven't looked at yet, leaving out ones that pay clearly under the floor."""
    fresh = [j for j in jobs if j["status"] == "New"
             and not (j["salary_max"] is not None and j["salary_max"] < pay_floor)]
    return sorted(fresh, key=lambda j: -j["score"])[:limit]


STAGE_HELP = {
    "Saved": "Worth applying to",
    "Applied": "Waiting to hear back",
    "Interviewing": "Prepare and follow up",
    "Offer": "Time to decide",
}


def next_step(jobs: list[dict], pay_floor: float, today: date | None = None) -> tuple[str, str, str]:
    """(label, what to do, why) for the single most useful thing to do now. The most advanced stage wins."""
    today = today or date.today()
    if not jobs:
        return ("Start here", "Find your first jobs", "Open **Find jobs** to search, or **Add a job** to paste one in.")
    stages = by_stage(jobs)
    if stages["Offer"]:
        j = stages["Offer"][0]
        return ("Do this next", f"Decide on the offer from {j['company']}", f"{j['title']} is at the Offer stage.")
    if stages["Interviewing"]:
        j = stages["Interviewing"][0]
        return ("Do this next", f"Prepare for your interview at {j['company']}", f"{j['title']} is at the Interviewing stage.")
    stale = [j for j in stages["Applied"] if _days_since(j.get("applied_at"), today) >= 7]
    if stale:
        j = max(stale, key=lambda j: _days_since(j.get("applied_at"), today))
        return ("Do this next", f"Follow up with {j['company']}",
                f"You applied {_days_since(j.get('applied_at'), today)} days ago and haven't heard back.")
    if stages["Saved"]:
        j = stages["Saved"][0]
        return ("Do this next", f"Apply to {j['title']} at {j['company']}",
                f"It's your best saved job (fit {j['score']}). Open it in the **Jobs** tab to tailor your resume.")
    picks = top_new(jobs, pay_floor, 1)
    if picks:
        j = picks[0]
        return ("Do this next", f"Look at {j['title']} at {j['company']}",
                f"It's the best match you haven't reviewed (fit {j['score']}). Save it if you like it.")
    if stages["Applied"]:
        return ("All caught up", "Nothing urgent. Your applications are out there.", "Check back in a few days, or find more jobs.")
    return ("Do this next", "Find more jobs", "Nothing new to review. Try **Find jobs** with a different search.")


def _days_since(day: str | None, today: date) -> int:
    try:
        return (today - date.fromisoformat((day or "")[:10])).days
    except ValueError:
        return 0


def next_html(label: str, action: str, why: str) -> str:
    return (f'<div class="jh-next"><div class="k">{escape(label)}</div>'
            f'<div class="m">{escape(action)}</div><div class="h">{escape(why).replace("**", "")}</div></div>')


def card_html(job: dict, color: str) -> str:
    where = f" · {escape(job['location'])}" if job["location"] else ""
    applied = f" · applied {escape(job['applied_at'][:10])}" if job["status"] == "Applied" and job.get("applied_at") else ""
    return (f'<div class="jh-card" style="border-left-color:{color}">'
            f'<div class="t">{escape(job["title"])}</div>'
            f'<div class="c">{escape(job["company"])}{where}{applied}</div>'
            f'<div style="margin-top:4px">{badge(job["score"])}</div></div>')


def _move(conn, key: str) -> None:
    db.set_status(conn, key, st.session_state[f"move-{key}"])


def _card(conn, job: dict, color: str) -> None:
    st.markdown(card_html(job, color), unsafe_allow_html=True)
    if job["url"]:
        st.link_button("Open posting", job["url"], key=f"open-{job['key']}")
    st.selectbox("Move to", db.STATUSES, index=db.STATUSES.index(job["status"]), key=f"move-{job['key']}",
                 on_change=_move, args=(conn, job["key"]), label_visibility="collapsed")


def render(conn, jobs: list[dict], pay_floor: float) -> None:
    if not jobs:
        st.info("Your pipeline is empty. Go to **Find jobs** to search, or **Add a job** to paste one in.")
        return

    st.markdown(next_html(*next_step(jobs, pay_floor)), unsafe_allow_html=True)

    stages = by_stage(jobs)
    counts = {s: len(stages[s]) for s in STAGES}
    new = sum(j["status"] == "New" for j in jobs)
    cols = st.columns(5)
    cols[0].metric("To review", new)
    for col, stage in zip(cols[1:], STAGES[1:]):
        col.metric(stage, counts[stage])

    picks = top_new(jobs, pay_floor)
    if picks:
        st.subheader("Best new matches")
        st.caption("Highest fit among jobs you haven't touched yet. Use the menu on a card to save it.")
        for col, job in zip(st.columns(len(picks)), picks):
            with col:
                _card(conn, job, band(job["score"])[1])

    st.subheader("Your pipeline")
    for col, stage in zip(st.columns(len(STAGES)), STAGES):
        with col:
            st.markdown(f'<div class="jh-stage" style="border-color:{STAGE_COLORS[stage]}">'
                        f'{stage} ({counts[stage]})</div>'
                        f'<div class="jh-stage-help">{STAGE_HELP[stage]}</div>', unsafe_allow_html=True)
            if not stages[stage]:
                st.markdown('<div class="jh-empty">Nothing here yet</div>', unsafe_allow_html=True)
            for job in stages[stage]:
                _card(conn, job, STAGE_COLORS[stage])

    closed = [j for j in jobs if j["status"] in ("Skipped", "Rejected")]
    if closed:
        with st.expander(f"Skipped and rejected ({len(closed)})"):
            for job in closed:
                st.markdown(f"**{escape(job['title'])}** · {escape(job['company'])} · {job['status']}")
