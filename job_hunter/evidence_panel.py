"""The 'why did it count that?' screen: the posting phrase behind each skill, with a one-click fix."""

from __future__ import annotations

import re

import streamlit as st

from . import db
from .models import Job


def _escape(text: str) -> str:
    return re.sub(r"([\\`*_{}\[\]()#+!|~$<>])", r"\\\1", text)


def highlighted(snippet: str, start: int, length: int) -> str:
    """Markdown for the snippet with the matched words in bold."""
    return f"{_escape(snippet[:start])}**{_escape(snippet[start:start + length])}**{_escape(snippet[start + length:])}"


def evidence_panel(conn, profile, job: dict) -> None:
    """Show each matched skill's phrase; 'Not a match' removes it from this job's score."""
    key = job["key"]
    record = Job(**{f: job[f] for f in Job.__dataclass_fields__})
    rejected = profile.corrections.rejected(key)
    # Corrected skills drop out of the score, so look at the whole posting to list them too.
    with st.expander("Where each skill came from"):
        items = profile.evidence(record)
        if not items:
            st.caption("No tracked skills found in this posting.")
        for item in items:
            text, button = st.columns([5, 1])
            ruled_out = item.skill in rejected
            label = f"~~{item.skill}~~" if ruled_out else f"**{item.skill}**"
            text.markdown(f"{label}: {highlighted(item.snippet, item.start, len(item.phrase))}")
            if ruled_out:
                if button.button("Count it", key=f"restore-{key}-{item.skill}"):
                    profile.corrections.restore(key, item.skill)
                    db.rescore(conn, profile)
                    st.rerun()
            elif button.button("Not a match", key=f"reject-{key}-{item.skill}"):
                profile.corrections.reject(key, item.skill)
                db.rescore(conn, profile)
                st.rerun()
