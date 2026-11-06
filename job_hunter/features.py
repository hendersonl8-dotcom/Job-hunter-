"""Where the optional feature modules plug into the app.

Each module has its own file and a render(conn, jobs, profile) function. They are listed here once, so
a thread building one feature edits only its own module, not app.py. Order is the order on screen.
"""

from __future__ import annotations

from . import builder_tab, digest, goals, home_charts, interview_prep, networking, pay_fit, reminders, skill_gap

HOME_SECTIONS = [digest, reminders, goals, home_charts, pay_fit]
TOOLS_SECTIONS = [interview_prep, skill_gap, networking]


def render_home(conn, jobs: list[dict], profile) -> None:
    for module in HOME_SECTIONS:
        module.render(conn, jobs, profile)


def render_tools(conn, jobs: list[dict], profile) -> None:
    for module in TOOLS_SECTIONS:
        module.render(conn, jobs, profile)


def render_builder(conn, jobs: list[dict], profile) -> None:
    builder_tab.render(conn, jobs, profile)
