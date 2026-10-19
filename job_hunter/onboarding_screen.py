"""The first-run screen: upload a resume, review what was found, save."""

from __future__ import annotations

import os

import streamlit as st

from job_hunter import onboarding
from job_hunter.config import Settings


def has_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def render(settings: Settings) -> None:
    st.title("Welcome to Job Hunter")
    st.write("Upload your resume and the app builds your profile and master resume from it. "
             "You review and edit everything before it is saved. Only facts in your resume are used.")

    if not has_api_key():
        st.warning("Reading a resume needs a Claude API key. Set ANTHROPIC_API_KEY (see the README), then reload.")

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
    locations = col1.text_input("Locations, comma separated", ", ".join(facts.locations or ([c.location] if c.location else [])))
    min_salary = col2.number_input("Lowest pay you would accept (per year, $)", min_value=0, value=0, step=5000)
    allow_remote = st.checkbox("Include remote jobs", value=True)

    st.markdown("**Job families** (summaries are what your resume opens with)")
    for t in facts.tracks:
        with st.expander(t.name, expanded=True):
            t.headline = st.text_input("Headline", t.headline, key=f"h-{t.name}")
            t.summary = st.text_area("Summary", t.summary, key=f"s-{t.name}")
            t.title_words = [w.strip() for w in st.text_input(
                "Job title words that match this family, comma separated", ", ".join(t.title_words), key=f"w-{t.name}").split(",") if w.strip()]

    st.markdown("**Skills** (one per line)")
    skills_text = st.text_area("Skills", "\n".join(s.name for s in facts.skills), height=160, label_visibility="collapsed")
    wanted = [s.strip() for s in skills_text.splitlines() if s.strip()]
    by_name = {s.name: s for s in facts.skills}
    facts.skills = [by_name.get(n) or onboarding.Skill(name=n, group="Skills") for n in wanted]

    st.caption(f"Also found: {len(facts.experience)} roles, {len(facts.projects)} projects, "
               f"{len(facts.education)} education entries, {len(facts.certifications)} certifications. "
               "You can fine-tune the details later in resume.json in your data folder (see the README).")

    if st.button("Save and start", type="primary"):
        if not facts.tracks or not facts.experience:
            st.error("Nothing to save yet: no job families or roles were found.")
            return
        locs = [x.strip() for x in locations.split(",") if x.strip()]
        onboarding.save_json(settings.resume, onboarding.build_resume(facts))
        onboarding.save_json(settings.profile, onboarding.build_profile(facts, min_salary, locs, allow_remote))
        st.session_state.pop("onboarding", None)
        st.rerun()
