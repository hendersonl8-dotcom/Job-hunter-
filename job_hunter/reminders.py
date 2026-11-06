"""Follow-up reminders: applied jobs with no reply after a few days, a snooze, and a short note to send.

Nothing here sends anything. The note is text you copy and send yourself. It lives in its own table,
created on first use, so no existing table changes.
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta

import streamlit as st

from pydantic import BaseModel, Field

from . import userdata
from .resume import FALLBACK_BETA, MODEL
DEFAULT_DAYS = 7
MIN_DAYS, MAX_DAYS = 3, 30
SNOOZE_CHOICES = {"2 days": 2, "4 days": 4, "1 week": 7}
SETTINGS_FILE = "followup_settings.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS followups (
    job_key        TEXT PRIMARY KEY REFERENCES jobs (key),
    snoozed_until  TEXT,  -- ISO date: hidden until then
    followed_up_at TEXT   -- ISO date of the last follow-up you sent
);
"""


def ensure(conn) -> None:
    conn.executescript(SCHEMA)


# --- The "days before a reminder" setting -----------------------------------------------------

def _settings_path():
    return userdata.user_dir() / SETTINGS_FILE


def load_days() -> int:
    try:
        days = int(json.loads(_settings_path().read_text(encoding="utf-8")).get("days", DEFAULT_DAYS))
    except (OSError, ValueError, TypeError, AttributeError):
        return DEFAULT_DAYS
    return min(MAX_DAYS, max(MIN_DAYS, days))


def save_days(days: int) -> None:
    userdata.write_json(_settings_path(), {"days": min(MAX_DAYS, max(MIN_DAYS, int(days)))})


# --- Who is due -------------------------------------------------------------------------------

def _day(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def due(conn, today: date | None = None, days: int | None = None) -> list[dict]:
    """Applied jobs with no reply: waiting `days` or more since applying (or since the last follow-up),
    not snoozed, and with no reply, interview or rejection logged. Longest-waiting first."""
    ensure(conn)
    today, days = today or date.today(), days or load_days()
    rows = conn.execute(
        """
        SELECT j.key, j.title, j.company, j.url, j.applied_at, f.snoozed_until, f.followed_up_at
        FROM jobs j LEFT JOIN followups f ON f.job_key = j.key
        WHERE j.status = 'Applied' AND j.applied_at IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM outcomes o WHERE o.job_key = j.key)
        """
    ).fetchall()
    out = []
    for row in rows:
        start = _day(row["followed_up_at"]) or _day(row["applied_at"])
        if start is None:
            continue
        snoozed = _day(row["snoozed_until"])
        waiting = (today - start).days
        if waiting >= days and not (snoozed and snoozed > today):
            out.append(dict(row) | {"waiting": waiting, "applied_days": (today - (_day(row["applied_at"]) or start)).days})
    return sorted(out, key=lambda r: -r["waiting"])


def snooze(conn, key: str, days: int, today: date | None = None) -> None:
    ensure(conn)
    until = ((today or date.today()) + timedelta(days=days)).isoformat()
    conn.execute(
        "INSERT INTO followups (job_key, snoozed_until) VALUES (?, ?) "
        "ON CONFLICT(job_key) DO UPDATE SET snoozed_until = excluded.snoozed_until", (key, until))
    conn.commit()


def mark_followed_up(conn, key: str, today: date | None = None) -> None:
    """You sent a follow-up: the clock restarts from today, and any snooze is cleared."""
    ensure(conn)
    conn.execute(
        "INSERT INTO followups (job_key, followed_up_at) VALUES (?, ?) "
        "ON CONFLICT(job_key) DO UPDATE SET followed_up_at = excluded.followed_up_at, snoozed_until = NULL",
        (key, (today or date.today()).isoformat()))
    conn.commit()


# --- The note ---------------------------------------------------------------------------------

def template(job: dict, name: str = "") -> str:
    """A plain follow-up note, used when there is no Claude key."""
    return (
        f"Subject: Following up on my {job['title']} application\n\n"
        "Hello,\n\n"
        f"I applied for the {job['title']} role at {job['company']} about {job.get('applied_days', 'a few')} days ago "
        "and wanted to say I'm still very interested. If it would help, I'm glad to send anything else "
        "or answer questions about my background.\n\n"
        "Thank you for your time.\n\n"
        f"{name or 'Best regards'}"
    )


class FollowUpNote(BaseModel):
    subject: str
    body: str = Field(description="Under 90 words, signed with the person's name if given")


SYSTEM = ("You write a short follow-up email from a job seeker to a recruiter about an application with no reply yet. "
          "Polite, specific, confident, no pressure. Use only the facts given; invent nothing.")


def draft(job: dict, resume: dict | None = None, client=None, model: str = MODEL, effort: str = "low") -> str:
    """A short follow-up note written by Claude, the same way cover letters are. Raises on API errors."""
    import anthropic

    client = client or anthropic.Anthropic()
    facts = json.dumps({k: v for k, v in (resume or {}).items() if k in ("summary",)}
                       | {"name": (resume or {}).get("contact", {}).get("name", "")}, ensure_ascii=False)
    response = client.beta.messages.parse(
        model=model,
        max_tokens=2000,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        output_config={"effort": effort},
        output_format=FollowUpNote,
        system=[{"type": "text", "text": SYSTEM}],
        messages=[{"role": "user", "content": [{"type": "text", "text":
                   f"Job: {job['title']} at {job['company']}. Applied {job.get('applied_days', 'several')} days ago.\n"
                   f"About the person: {facts}"}]}],
    )
    if response.stop_reason in ("refusal", "max_tokens") or response.parsed_output is None:
        raise RuntimeError("Claude couldn't finish the note. Try again.")
    note = response.parsed_output
    return f"Subject: {note.subject}\n\n{note.body}"


def has_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def _master() -> dict:
    try:
        from .config import load_settings
        from .resume import load_master
        return load_master(load_settings().resume)
    except Exception:
        return {}


# --- The section on Home ------------------------------------------------------------------------

def render(conn, jobs=None, profile=None) -> None:
    """A self-contained expander listing applications that are due a follow-up."""
    items = due(conn)
    master = _master()
    with st.expander(f"Follow-ups due ({len(items)})", expanded=bool(items)):
        days = st.number_input("Remind me after (days with no reply)", MIN_DAYS, MAX_DAYS, load_days(), key="fu-days",
                               help="Counted from the day you applied, or from your last follow-up.")
        if int(days) != load_days():
            save_days(int(days))
            st.rerun()
        if not items:
            st.caption("Nothing waiting. Applied jobs with no reply show up here once they pass the limit.")
            return
        st.caption("Nothing is ever sent for you. Copy the note and send it yourself.")
        for job in items:
            k = job["key"]
            st.markdown(f"**{job['title']}**, {job['company']} · waiting {job['waiting']} days")
            c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
            if c1.button("Write note", key=f"fu-note-{k}"):
                name = (master or {}).get("contact", {}).get("name", "")
                if has_key():
                    try:
                        st.session_state[f"fu-text-{k}"] = draft(job, master)
                    except Exception as exc:  # network, key or API trouble: fall back, say why
                        st.warning(f"Claude couldn't write it ({exc}). Here's a plain template instead.")
                        st.session_state[f"fu-text-{k}"] = template(job, name)
                else:
                    st.session_state[f"fu-text-{k}"] = template(job, name)
            choice = c2.selectbox("Snooze", list(SNOOZE_CHOICES), key=f"fu-snz-{k}", label_visibility="collapsed")
            if c3.button("Snooze", key=f"fu-snooze-{k}"):
                snooze(conn, k, SNOOZE_CHOICES[choice])
                st.rerun()
            if c4.button("I followed up", key=f"fu-done-{k}"):
                mark_followed_up(conn, k)
                st.rerun()
            if f"fu-text-{k}" in st.session_state:
                st.text_area("Note (edit, then copy)", key=f"fu-text-{k}", height=220)
            if job.get("url"):
                st.link_button("Open posting", job["url"], key=f"fu-open-{k}")
