"""Shared chart helpers: colours that follow the chosen theme, and a standard empty message.

Use Streamlit's own charts (st.bar_chart, st.line_chart, st.scatter_chart) with palette() colours so
every chart matches the theme.
"""

from __future__ import annotations

import streamlit as st

from . import themes


def palette(name: str | None = None) -> dict:
    """accent, accent2, text, muted and the four pipeline stage colours for the current (or named) theme."""
    t = themes.THEMES[name or themes.saved()]
    saved, applied, interviewing, offer = t["stages"]
    return {"accent": t["accent"], "accent2": t["accent2"], "text": t["text"], "muted": t["muted"],
            "saved": saved, "applied": applied, "interviewing": interviewing, "offer": offer}


def stage_colors(name: str | None = None) -> list[str]:
    """Saved, Applied, Interviewing, Offer, in that order."""
    p = palette(name)
    return [p["saved"], p["applied"], p["interviewing"], p["offer"]]


def empty(message: str = "Nothing to chart yet. It fills in as you save and apply to jobs.") -> None:
    st.caption(message)
