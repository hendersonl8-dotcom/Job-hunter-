"""The Roles I'd consider tab."""

from __future__ import annotations

import streamlit as st

from job_hunter import role_suggestions, userdata
from job_hunter.onboarding_screen import has_api_key
from job_hunter.unexpected import unexpected_matches


def render(settings, master: dict, profile, jobs: list[dict]) -> None:
    st.write("Reads your master resume and suggests neighboring job titles it genuinely supports. Tick the "
             "ones you want: they become new tracks and search terms. A run costs roughly 5 cents.")
    if not has_api_key():
        st.warning("Suggestions need a Claude API key. Set ANTHROPIC_API_KEY (see the README), then reload.")

    if st.button("Suggest roles", type="primary", disabled=not has_api_key()):
        try:
            with st.spinner("Reading your resume..."):
                st.session_state["role_suggestions"] = role_suggestions.suggest(
                    master, profile, model=settings.claude_model)
        except Exception as exc:  # shown to the user so they can retry
            st.error(str(exc))

    roles = st.session_state.get("role_suggestions")
    if roles is not None:
        if not roles:
            st.info("Nothing new the resume clearly supports beyond your current tracks.")
        picked = []
        for i, role in enumerate(roles):
            if st.checkbox(f"**{role.title}**: {role.reason}", key=f"role-{i}"):
                picked.append(role)
            st.caption("From your resume: " + "; ".join(role.evidence))
        if roles and st.button("Add ticked roles to my profile", disabled=not picked):
            userdata.write_json(settings.profile, role_suggestions.add_roles(profile.data, picked))
            st.session_state.pop("role_suggestions")
            st.success(f"Added {len(picked)} role(s). Reload to score against them; Find jobs will use the new search terms.")

    st.subheader("Unexpected matches")
    st.caption("Saved postings that score well on your skills but fit none of your tracks.")
    found = unexpected_matches(jobs)
    if not found:
        st.write("None yet.")
    for job, skills in found:
        st.markdown(f"- **{job['title']}**, {job['company']} (fit {job['score']}): matched {', '.join(skills)}")
