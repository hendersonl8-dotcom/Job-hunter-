"""Sidebar: keys, and starting a new profile."""

from __future__ import annotations

import streamlit as st

from job_hunter import key_screen, new_profile, theme

SESSION_PREFIXES = ("keep-", "role-", "welcome-", "find-", "board-", "tailor-", "letter-")


def render(conn) -> None:
    with st.sidebar:
        theme.render_theme_picker()
        with st.expander("Claude key"):
            key_screen.claude_key_panel("side-")
        with st.expander("Start a new profile"):
            st.caption("For a different person or a different resume. Your current profile, resume, search settings "
                       "and saved jobs are copied to a folder in your data folder first, then cleared.")
            sure = st.checkbox("Yes, start over with a new resume", key="new-profile-sure")
            if st.button("Start a new profile", disabled=not sure):
                archive = new_profile.start_new_profile(conn)
                for k in [k for k in st.session_state if k.startswith(SESSION_PREFIXES)]:
                    st.session_state.pop(k)
                for k in ("role_suggestions", "new-profile-sure"):
                    st.session_state.pop(k, None)
                st.session_state["new-profile-saved-to"] = str(archive)
                st.rerun()
