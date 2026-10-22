"""The Preferences tab: how much each factor counts, plus must-haves and never-shows."""

from __future__ import annotations

import streamlit as st

from job_hunter import preferences as prefs_mod
from job_hunter import userdata


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def save_preferences(prefs: dict) -> None:
    """Write the preferences into the user's profile, leaving everything else in it alone."""
    profile = userdata.load_profile()
    profile["preferences"] = prefs
    userdata.save_profile(profile)


def render(profile) -> None:
    prefs = profile.prefs
    st.write("Say how much each thing counts toward a job's fit score. Set a slider to 0 to ignore it. "
             "Scores are rescaled to 0-100, so only the balance between sliders matters.")
    weights = {}
    cols = st.columns(2)
    for i, name in enumerate(prefs_mod.WEIGHTS):
        top = prefs_mod.MAX_WEIGHT.get(name, 30)
        with cols[i % 2]:
            weights[name] = st.slider(prefs_mod.LABELS[name], 0, top, int(prefs["weights"][name]), key=f"w-{name}")

    c1, c2 = st.columns(2)
    modes = list(prefs_mod.CLEARANCE_MODES)
    mode = c1.radio("Security clearance", modes, index=modes.index(prefs["clearance_mode"]),
                    format_func=prefs_mod.CLEARANCE_MODES.get,
                    help="\"Ready to grow\" treats a job that wants a clearance you lack as neutral, not a miss.")
    remotes = list(prefs_mod.REMOTE_CHOICES)
    remote = c2.radio("Where you want to work", remotes, index=remotes.index(prefs["remote"]),
                      format_func=prefs_mod.REMOTE_CHOICES.get)
    employers = c1.multiselect("Employer type", prefs_mod.EMPLOYER_TYPES, default=prefs["employer_types"],
                               help="Leave empty for no preference.")
    levels = c2.multiselect("Seniority", prefs_mod.SENIORITY_LEVELS, default=prefs["seniority"],
                            help="Leave empty for no preference.")
    must = st.text_area("Must-have (one per line)", "\n".join(prefs["must_have"]),
                        help="A job whose posting lacks any of these scores 0.")
    never = st.text_area("Never show (one per line)", "\n".join(prefs["never_show"]),
                         help="For example on-call, relocation, or a company you've ruled out.")

    if st.button("Save preferences", type="primary"):
        save_preferences({"weights": weights, "clearance_mode": mode, "remote": remote,
                          "employer_types": employers, "seniority": levels,
                          "must_have": _lines(must), "never_show": _lines(never)})
        st.success("Saved. New and re-scored jobs use these weights; reload the page to see it everywhere.")
    if st.button("Reset to defaults"):
        save_preferences(prefs_mod.merged(None))
        for name in prefs_mod.WEIGHTS:
            st.session_state.pop(f"w-{name}", None)
        st.rerun()
