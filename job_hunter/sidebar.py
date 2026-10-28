"""Sidebar: who is using the app (profile switcher), keys, and starting a new profile."""

from __future__ import annotations

import streamlit as st

from job_hunter import key_screen, new_profile, profiles, theme

SESSION_PREFIXES = ("keep-", "role-", "welcome-", "find-", "board-", "tailor-", "letter-")


def _forget_screen_state() -> None:
    for k in [k for k in st.session_state if k.startswith(SESSION_PREFIXES)]:
        st.session_state.pop(k)
    for k in ("role_suggestions", "new-profile-sure"):
        st.session_state.pop(k, None)


def profile_switcher() -> None:
    """Pick who is using the app, or add a person. Call before the settings load so a switch takes effect."""
    names = profiles.list_profiles()
    current = profiles.active_profile()

    def switch():
        profiles.set_active(st.session_state["profile-pick"])
        _forget_screen_state()

    with st.sidebar:
        st.selectbox("Profile", names, index=names.index(current), key="profile-pick", on_change=switch,
                     help="Each profile has its own resume, saved jobs and settings.")
        with st.expander("Add a profile"):
            st.caption("For another person. They get their own resume, jobs and settings; nothing is shared "
                       "except the Claude key.")
            new_name = st.text_input("Name", key="profile-new-name")
            if st.button("Add profile", disabled=not new_name.strip()):
                try:
                    profiles.create_profile(new_name)
                except profiles.ProfileError as error:
                    st.error(str(error))
                else:
                    _forget_screen_state()
                    st.session_state.pop("profile-new-name", None)
                    st.rerun()


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
                _forget_screen_state()
                st.session_state["new-profile-saved-to"] = str(archive)
                st.rerun()
