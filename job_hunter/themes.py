"""Colour themes: the palettes, the saved choice, and the CSS that applies one.

The base Streamlit theme in .streamlit/config.toml stays Teal; every other theme is a CSS override
laid over it, so switching needs no restart.
"""

from __future__ import annotations

import json

from . import userdata

SETTINGS_FILE = "theme.json"
DEFAULT = "Teal"

# accent: buttons, links, logo; bg/panel: page and sidebar fill; text/muted: body and secondary text;
# card: pipeline card fill; line: card border; stages: Saved, Applied, Interviewing, Offer.
THEMES = {
    "Teal": dict(accent="#0F766E", accent2="#F59E0B", bg="#FFFFFF", panel="#F1F5F9", text="#0F172A",
                 muted="#64748B", card="#FFFFFF", line="#E2E8F0",
                 stages=("#64748B", "#0F766E", "#D97706", "#15803D")),
    "Navy": dict(accent="#1E40AF", accent2="#F59E0B", bg="#FFFFFF", panel="#EFF3FB", text="#0F172A",
                 muted="#64748B", card="#FFFFFF", line="#D6DEEF",
                 stages=("#64748B", "#1E40AF", "#D97706", "#15803D")),
    "Forest": dict(accent="#166534", accent2="#CA8A04", bg="#FFFFFF", panel="#F0F5EE", text="#14231A",
                   muted="#5F6F63", card="#FFFFFF", line="#D5E3D6",
                   stages=("#64748B", "#166534", "#CA8A04", "#0F766E")),
    "Purple": dict(accent="#6D28D9", accent2="#F59E0B", bg="#FFFFFF", panel="#F5F1FB", text="#1E1033",
                   muted="#6B6480", card="#FFFFFF", line="#E4DBF3",
                   stages=("#64748B", "#6D28D9", "#D97706", "#15803D")),
    "Dark": dict(accent="#2DD4BF", accent2="#FBBF24", bg="#0F172A", panel="#1E293B", text="#E2E8F0",
                 muted="#94A3B8", card="#1E293B", line="#334155",
                 stages=("#94A3B8", "#2DD4BF", "#FBBF24", "#4ADE80")),
}


def saved() -> str:
    try:
        name = json.loads((userdata.user_dir() / SETTINGS_FILE).read_text(encoding="utf-8")).get("theme")
    except (OSError, ValueError, AttributeError):
        return DEFAULT
    return name if name in THEMES else DEFAULT


def save(name: str) -> None:
    if name in THEMES:
        (userdata.user_dir() / SETTINGS_FILE).write_text(json.dumps({"theme": name}), encoding="utf-8")


def logo_fill(name: str) -> str:
    return THEMES[name]["accent"]


def css(name: str) -> str:
    """Variables for the cards and stage headings, plus Streamlit overrides for every theme but Teal."""
    t = THEMES.get(name, THEMES[DEFAULT])
    s = t["stages"]
    out = (f":root{{--jh-accent:{t['accent']}; --jh-muted:{t['muted']}; --jh-card:{t['card']}; "
           f"--jh-line:{t['line']}; --jh-text:{t['text']}; --jh-saved:{s[0]}; --jh-applied:{s[1]}; "
           f"--jh-interviewing:{s[2]}; --jh-offer:{s[3]};}}")
    if name == DEFAULT:
        return out
    return out + (
        f".stApp,[data-testid='stHeader']{{background:{t['bg']}; color:{t['text']};}}"
        f"[data-testid='stSidebar']{{background:{t['panel']};}}"
        f".stApp p,.stApp li,.stApp label,.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp span,"
        f".stApp [data-testid='stMarkdownContainer']{{color:{t['text']};}}"
        f".stApp a{{color:{t['accent']};}}"
        f".stApp button[kind='primary'],.stApp [data-testid='stBaseButton-primary']"
        f"{{background:{t['accent']}; border-color:{t['accent']}; color:{t['bg'] if name == 'Dark' else '#fff'};}}"
        f".stApp button[kind='secondary'],.stApp [data-testid='stBaseButton-secondary']"
        f"{{background:{t['panel']}; color:{t['text']}; border-color:{t['line']};}}"
        f".stApp input,.stApp textarea,.stApp [data-baseweb='select'] div,.stApp [data-baseweb='input']"
        f"{{background:{t['panel']}; color:{t['text']};}}"
        f"[data-testid='stExpander'],[data-testid='stExpander'] details{{border-color:{t['line']};}}"
        f".stApp [data-baseweb='tab-highlight']{{background:{t['accent']};}}"
    )
