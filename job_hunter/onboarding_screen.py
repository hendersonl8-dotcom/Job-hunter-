"""The first-run screen: upload a resume, review what was found, save."""

from __future__ import annotations

from types import SimpleNamespace

import streamlit as st

from job_hunter import key_screen, keys, onboarding, role_suggestions
from job_hunter.config import Settings, load_search_prefs, save_search_prefs

has_api_key = keys.has_claude_key


def render(settings: Settings) -> None:
    st.title("Welcome to Job Hunter")
    st.write("Upload your resume and the app builds your profile and master resume from it. "
             "You review and edit everything before it is saved. Only facts in your resume are used.")

    st.subheader("1. Connect Claude")
    key_screen.claude_key_panel("welcome-")

    st.subheader("2. Upload your resume")
    upload = st.file_uploader("Your resume (PDF or Word)", type=["pdf", "docx"])
    if upload and st.button("Read my resume", type="primary", disabled=not has_api_key()):
        try:
            with st.spinner("Reading your resume..."):
                text = onboarding.extract_text(upload.name, upload.getvalue())
                facts, warnings = onboarding.verify(onboarding.extract(text), text)
        except Exception as exc:  # shown to the user; the upload stays so they can retry
            st.error(str(exc))
        else:
            st.session_state["onboarding"] = {"facts": facts.model_dump(), "warnings": warnings}

    state = st.session_state.get("onboarding")
    if not state:
        return
    facts = onboarding.ExtractedResume(**state["facts"])

    for w in state["warnings"]:
        st.warning(w)

    st.subheader("Review")
    c = facts.contact
    col1, col2 = st.columns(2)
    c.name = col1.text_input("Name", c.name)
    c.email = col2.text_input("Email", c.email)
    c.phone = col1.text_input("Phone", c.phone)
    c.location = col2.text_input("Location", c.location)
    c.clearance = col1.text_input("Security clearance (blank if none)", c.clearance)

    st.markdown("**What you are looking for**")
    col1, col2 = st.columns(2)
    locations = col1.text_area("Places to look (one per line, like Portland, OR)", "\n".join(facts.locations or ([c.location] if c.location else [])), height=100)
    min_salary = col2.number_input("Lowest pay you would accept (per year, $)", min_value=0, value=0, step=5000)
    allow_remote = st.checkbox("Include remote jobs", value=True)

    st.markdown("**Job families** (summaries are what your resume opens with)")
    kept = []
    for t in facts.tracks:
        with st.expander(t.name, expanded=True):
            if not st.checkbox("Look for this kind of job", value=True, key=f"keep-{t.name}"):
                continue
            kept.append(t)
            t.headline = st.text_input("Headline", t.headline, key=f"h-{t.name}")
            t.summary = st.text_area("Summary", t.summary, key=f"s-{t.name}")
            t.title_words = [w.strip() for w in st.text_input(
                "Job title words that match this family, comma separated", ", ".join(t.title_words), key=f"w-{t.name}").split(",") if w.strip()]

    facts.tracks = kept
    picked = _roles_step(facts, locations, min_salary, allow_remote)

    st.markdown("**Skills** (one per line)")
    skills_text = st.text_area("Skills", "\n".join(s.name for s in facts.skills), height=160, label_visibility="collapsed")
    wanted = [s.strip() for s in skills_text.splitlines() if s.strip()]
    by_name = {s.name: s for s in facts.skills}
    facts.skills = [by_name.get(n) or onboarding.Skill(name=n, group="Skills") for n in wanted]

    st.caption(f"Also found: {len(facts.experience)} roles, {len(facts.projects)} projects, "
               f"{len(facts.education)} education entries, {len(facts.certifications)} certifications. "
               "You can fine-tune the details later in resume.json in your data folder (see the README).")

    st.subheader("4. Federal jobs (optional)")
    usa_key, usa_email = key_screen.usajobs_panel(load_search_prefs(), "welcome-")

    if st.button("Save and start", type="primary"):
        if not facts.tracks or not facts.experience:
            st.error("Nothing to save yet: no job families or roles were found.")
            return
        locs = [x.strip() for x in locations.splitlines() if x.strip()]
        onboarding.save_json(settings.resume, onboarding.build_resume(facts))
        profile = onboarding.build_profile(facts, min_salary, locs, allow_remote)
        if picked:
            profile = role_suggestions.add_roles(profile, picked)
        onboarding.save_json(settings.profile, profile)
        save_search_prefs({**load_search_prefs(), **onboarding.search_prefs(profile),
                           "usajobs_api_key": usa_key, "usajobs_email": usa_email})
        for k in [k for k in st.session_state if k.startswith(("keep-", "role-", "welcome-"))]:
            st.session_state.pop(k)
        st.session_state.pop("onboarding", None)
        st.session_state.pop("onboarding_roles", None)
        st.rerun()


def _roles_step(facts, locations: str, min_salary: float, allow_remote: bool) -> list:
    """Ask which neighboring roles to look for, reusing the Roles I'd consider flow."""
    st.subheader("3. Other roles you'd consider")
    st.caption("Claude can suggest neighboring job titles your resume genuinely supports. Tick the ones you want; "
               "they become job families and search terms. This costs roughly 5 cents and is optional.")
    if st.button("Suggest roles", disabled=not has_api_key() or not facts.experience):
        locs = [x.strip() for x in locations.splitlines() if x.strip()]
        try:
            with st.spinner("Reading your resume..."):
                st.session_state["onboarding_roles"] = role_suggestions.suggest(
                    onboarding.build_resume(facts),
                    SimpleNamespace(data=onboarding.build_profile(facts, min_salary, locs, allow_remote)))
        except Exception as exc:  # shown so they can retry or skip
            st.error(str(exc))
    picked = []
    for i, role in enumerate(st.session_state.get("onboarding_roles") or []):
        if st.checkbox(f"**{role.title}**: {role.reason}", key=f"role-{i}"):
            picked.append(role)
        st.caption("From your resume: " + "; ".join(role.evidence))
    return picked
