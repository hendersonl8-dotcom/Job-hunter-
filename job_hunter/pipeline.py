"""The Home tab: where you stand at a glance, and your jobs laid out by stage."""

from __future__ import annotations

import streamlit as st

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


def card_html(job: dict, color: str) -> str:
    where = f" · {escape(job['location'])}" if job["location"] else ""
    return (f'<div class="jh-card" style="border-left-color:{color}">'
            f'<div class="t">{escape(job["title"])}</div>'
            f'<div class="c">{escape(job["company"])}{where}</div>'
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
                        f'{stage} ({counts[stage]})</div>', unsafe_allow_html=True)
            if not stages[stage]:
                st.markdown('<div class="jh-empty">Nothing here yet</div>', unsafe_allow_html=True)
            for job in stages[stage]:
                _card(conn, job, STAGE_COLORS[stage])

    closed = [j for j in jobs if j["status"] in ("Skipped", "Rejected")]
    if closed:
        with st.expander(f"Skipped and rejected ({len(closed)})"):
            for job in closed:
                st.markdown(f"**{escape(job['title'])}** · {escape(job['company'])} · {job['status']}")
