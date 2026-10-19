"""Look and feel: the logo, the fit-score colours and the light CSS the app adds on top of .streamlit/config.toml."""

from __future__ import annotations

import streamlit as st

# Same file as assets/logo.svg, inlined so the installed app never depends on a data folder being bundled.
LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="{size}" height="{size}">'
    '<rect width="64" height="64" rx="14" fill="#0F766E"/>'
    '<circle cx="32" cy="32" r="20" fill="none" stroke="#fff" stroke-width="3"/>'
    '<path d="M32 14 40 32 32 50 24 32Z" fill="#fff"/>'
    '<path d="M32 14 40 32H24Z" fill="#F59E0B"/>'
    '<circle cx="32" cy="32" r="3" fill="#0F766E"/></svg>'
)

# (minimum score, label, background, text). Dark text on pale fills keeps these readable in any Streamlit theme.
BANDS = [
    (75, "Strong fit", "#DCFCE7", "#14532D"),
    (55, "Worth a look", "#FEF3C7", "#78350F"),
    (0, "Long shot", "#E2E8F0", "#334155"),
]

STAGES = ["Saved", "Applied", "Interviewing", "Offer"]
STAGE_COLORS = {"Saved": "#64748B", "Applied": "#0F766E", "Interviewing": "#D97706", "Offer": "#15803D"}

CSS = """
<style>
.block-container {padding-top: 3.5rem;}
.jh-header {display:flex; align-items:center; gap:14px; margin-bottom:.25rem;}
.jh-header h1 {margin:0; padding:0; font-size:2rem;}
.jh-sub {color:#64748B; margin:0 0 1rem 0;}
.jh-badge {display:inline-block; padding:2px 10px; border-radius:999px; font-weight:600; font-size:.8rem;}
.jh-card {border:1px solid #E2E8F0; border-left-width:5px; border-radius:8px; padding:8px 10px;
          margin-bottom:8px; background:#fff; color:#0F172A;}
.jh-card .t {font-weight:600; line-height:1.25;}
.jh-card .c {color:#64748B; font-size:.85rem;}
.jh-stage {font-weight:700; padding-bottom:4px; margin-bottom:8px; border-bottom:3px solid;}
.jh-empty {color:#94A3B8; font-size:.85rem; font-style:italic;}
</style>
"""


def band(score: int) -> tuple[str, str, str]:
    """(label, background, text colour) for a fit score."""
    for minimum, label, bg, fg in BANDS:
        if score >= minimum:
            return label, bg, fg
    return BANDS[-1][1:]


def badge(score: int) -> str:
    label, bg, fg = band(score)
    return f'<span class="jh-badge" style="background:{bg};color:{fg}">{score} · {label}</span>'


def escape(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def header(subtitle: str) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        f'<div class="jh-header">{LOGO_SVG.format(size=44)}<h1>Job Hunter</h1></div>'
        f'<p class="jh-sub">{escape(subtitle)}</p>',
        unsafe_allow_html=True,
    )


def logo_uri() -> str:
    """The logo as a data URI, for st.logo and the browser icon."""
    from urllib.parse import quote
    return "data:image/svg+xml;utf8," + quote(LOGO_SVG.format(size=64))
