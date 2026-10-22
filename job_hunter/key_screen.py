"""Walks a person through adding their own keys, in the welcome screen and from the sidebar."""

from __future__ import annotations

import streamlit as st

from job_hunter import keys


def claude_key_panel(prefix: str = "") -> None:
    """Add or change the Claude key. It is checked, then saved on this computer only."""
    if keys.has_claude_key():
        st.success("Your Claude key is set. Resume reading, tailoring and cover letters are on.")
        label = "Use a different key"
    else:
        st.markdown(
            "Reading your resume, tailoring it and writing cover letters use Claude, billed to your own account "
            "(roughly 10 to 20 cents per tailored resume).\n\n"
            "1. Go to [console.anthropic.com](https://console.anthropic.com/) and sign in or create an account.\n"
            "2. Add a few dollars of credit under **Billing**.\n"
            "3. Open **API keys**, press **Create key**, and copy it (it starts with `sk-ant-`).\n"
            "4. Paste it below. It is saved on this computer only and is never shared.")
        label = "Claude API key"
    entered = st.text_input(label, type="password", key=f"{prefix}claude-key")
    if st.button("Check and save key", key=f"{prefix}claude-key-save", disabled=not entered.strip()):
        problem = keys.check_claude_key(entered)
        if problem:
            st.error(problem)
        else:
            keys.save_claude_key(entered)
            st.rerun()


def usajobs_panel(prefs: dict, prefix: str = "") -> tuple[str, str]:
    """Optional USAJobs key and email fields. Returns what was entered; the caller saves it."""
    st.markdown(
        "Optional: federal jobs on USAJobs need a free key from "
        "[developer.usajobs.gov](https://developer.usajobs.gov/apirequest/). Skip this if you don't want federal jobs; "
        "you can add it later in **Find jobs**.")
    key = st.text_input("USAJobs API key", value=prefs.get("usajobs_api_key", ""), type="password", key=f"{prefix}usa-key")
    email = st.text_input("Email you registered it with", value=prefs.get("usajobs_email", ""), key=f"{prefix}usa-email")
    return key.strip(), email.strip()
