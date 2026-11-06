"""A short first-run tour. It shows once; the marker file lives in the user's data folder."""

from __future__ import annotations

import streamlit as st

from . import userdata

MARKER = "tour_seen"

STEPS = [
    ("Welcome", "Job Hunter finds jobs that fit your resume, scores each one, rewrites your resume and "
                "writes a cover letter for the ones you pick, and keeps track of where you applied. "
                "This takes about a minute."),
    ("Home", "Your whole search on one page: new matches worth a look, and your jobs laid out as "
             "Saved, Applied, Interviewing and Offer. Each job has a fit score from 0 to 100. "
             "Use the menu on a card to move it along."),
    ("Find jobs", "Search public job boards in one click, for your own city or for remote work. "
                  "LinkedIn, Glassdoor and Indeed can't be searched here, so paste a posting from "
                  "them into **Add a job**."),
    ("Jobs and Compare", "The full list with filters and saved searches. Pick a job to see why it "
                         "scored the way it did, or put two to four side by side in **Compare**."),
    ("Tailor and apply", "Pick a job, then tailor your resume and write a cover letter for it. "
                         "Anything the posting wants that your resume can't back up is flagged, "
                         "never invented."),
    ("You stay in charge", "Nothing is ever sent for you. **Apply** asks you to confirm, then hands you "
                           "your files and the link so you can submit on the employer's site."),
    ("Make it yours", "Pick a **Colour theme** in the sidebar, switch **Profile** if someone else "
                      "shares this computer, and use **Take the tour again** whenever you like."),
]


def seen() -> bool:
    return (userdata.root_dir() / MARKER).exists()


def mark_seen() -> None:
    (userdata.root_dir() / MARKER).write_text("1", encoding="utf-8")


@st.dialog("Welcome to Job Hunter", width="large")
def _dialog() -> None:
    step = st.session_state.get("tour-step", 0)
    title, body = STEPS[step]
    st.progress((step + 1) / len(STEPS), text=f"Step {step + 1} of {len(STEPS)}")
    st.subheader(title)
    st.markdown(body)
    st.write("")
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
