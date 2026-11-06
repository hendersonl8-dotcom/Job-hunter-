"""Resume builder as its own page (also available as a tab in the main app).

Run with:  streamlit run resume_builder.py --server.port 8502
It reads the active profile's master resume and never changes it; your picks are saved as drafts.
"""

from __future__ import annotations

import streamlit as st

from job_hunter import builder_tab, profiles, theme

st.set_page_config(page_title="Resume builder", page_icon="📝", layout="wide")
st.logo(theme.logo_uri())


def switch_profile() -> None:
    profiles.set_active(st.session_state["rb-profile"])
    builder_tab.reset({})  # an empty draft is rebuilt from the new profile's master resume


names = profiles.list_profiles()
with st.sidebar:
    st.selectbox("Profile", names, index=names.index(profiles.active_profile()), key="rb-profile",
                 on_change=switch_profile, help="Uses this profile's master resume. Same profiles as the main app.")

builder_tab.render(standalone=True)
