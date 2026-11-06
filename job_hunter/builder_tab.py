"""The resume builder as a tab of the main app.

Scaffold: render() does nothing yet. The thread that builds this feature owns this file and its test.
"""

from __future__ import annotations


def render(conn, jobs: list[dict], profile) -> None:
    """Draw this feature. Called from job_hunter/features.py; jobs is db.all_jobs(conn)."""
    return None
