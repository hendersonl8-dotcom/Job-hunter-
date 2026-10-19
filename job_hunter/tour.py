"""A short first-run tour. It shows once; the marker file lives in the user's data folder."""

from __future__ import annotations

import streamlit as st

from . import userdata

MARKER = "tour_seen"

STEPS = [
    ("Home", "Your whole search on one page: new matches worth a look, and your jobs laid out as "
             "Saved, Applied, Interviewing and Offer. Each job has a fit score from 0 to 100."),
    ("Find jobs", "Search public job boards in one click. You can also paste a posting from LinkedIn, "
                  "Glassdoor or Indeed in **Add a job**."),
    ("Jobs", "The full list with filters. Pick a job to see why it scored the way it did, tailor your "
             "resume, write a cover letter and apply."),
    ("You stay in charge", "Nothing is ever sent for you. **Apply** asks you to confirm, then hands you "
                           "your files and the link so you can submit on the employer's site."),
]


def seen() -> bool:
    return (userdata.user_dir() / MARKER).exists()


def mark_seen() -> None:
    (userdata.user_dir() / MARKER).write_text("1", encoding="utf-8")


@st.dialog("Welcome to Job Hunter", width="large")
def _dialog() -> None:
    step = st.session_state.get("tour-step", 0)
    title, body = STEPS[step]
    st.progress((step + 1) / len(STEPS), text=f"Step {step + 1} of {len(STEPS)}")
    st.subheader(title)
    st.markdown(body)
    c1, c2, c3 = st.columns([1, 1, 3])
    if step and c1.button("Back", key="tour-back"):
        st.session_state["tour-step"] = step - 1
        st.rerun(scope="fragment")
    if step < len(STEPS) - 1:
        if c2.button("Next", type="primary", key="tour-next"):
            st.session_state["tour-step"] = step + 1
            st.rerun(scope="fragment")
    elif c2.button("Get started", type="primary", key="tour-done"):
        mark_seen()
        st.session_state["tour-open"] = False
        st.rerun()
    if c3.button("Skip the tour", key="tour-skip"):
        mark_seen()
        st.session_state["tour-open"] = False
        st.rerun()


def maybe_show() -> None:
    """Open the tour the first time the app runs; the sidebar button reopens it any time."""
    if "tour-open" not in st.session_state:
        st.session_state["tour-open"] = not seen()
    if st.sidebar.button("Take the tour again"):
        st.session_state["tour-step"] = 0
        st.session_state["tour-open"] = True
    if st.session_state["tour-open"]:
        _dialog()
