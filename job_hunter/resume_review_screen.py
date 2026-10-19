"""The Resume review tab."""

from __future__ import annotations

import streamlit as st

from job_hunter import resume_review
from job_hunter.onboarding_screen import has_api_key


def render(settings, master: dict, profile, jobs: list[dict]) -> None:
    st.write("Scores your master resume against your target roles and lists missing keywords, weak bullets "
             "and claims that need a number. Suggestions never add a skill, certification or number you "
             "do not have; keywords are offered as \"if true, add\". A review costs roughly 5-10 cents.")
    if not has_api_key():
        st.warning("A review needs a Claude API key. Set ANTHROPIC_API_KEY (see the README), then reload.")

    if st.button("Review my resume", type="primary", disabled=not has_api_key()):
        try:
            with st.spinner("Reviewing your resume..."):
                result = resume_review.review(master, profile, jobs, model=settings.claude_model)
        except Exception as exc:  # shown to the user so they can retry
            st.error(str(exc))
        else:
            st.session_state["resume_review"] = result

    result = st.session_state.get("resume_review")
    if not result:
        return
    out, notes, gaps = result

    for note in notes:
        st.warning(note)

    st.subheader("Fit for each target role")
    for s in out.scores:
        st.progress(s.score / 100, text=f"{s.role}: {s.score}/100")
        st.caption(s.reason)

    st.subheader("Missing keywords")
    if out.missing_keywords:
        for k in out.missing_keywords:
            roles = f" ({', '.join(k.roles)})" if k.roles else ""
            st.markdown(f"- **{k.term}**{roles}: {k.advice}")
    else:
        st.write("Nothing obvious is missing.")
    if gaps:
        st.caption("Most often missing in your saved postings: " + ", ".join(f"{n} ({c})" for n, c in gaps))

    st.subheader("Weak bullets")
    for b in out.weak_bullets:
        with st.expander(b.original[:90]):
            st.write(b.problem)
            st.markdown("**Suggested:** " + b.rewrite if b.rewrite else "_No safe rewrite: it needed facts you have not given._")

    st.subheader("Claims that need a number")
    for n in out.needs_number:
        st.markdown(f"- {n.original}\n  - *{n.question}*")
