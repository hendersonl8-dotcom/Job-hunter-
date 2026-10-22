"""Ready-made Seattle-area company job boards the Find jobs screen can toggle.

The token is the last part of the board URL: boards.greenhouse.io/<token> or
jobs.lever.co/<token>. A company that has moved to another system just shows an
error for its own board; the others still run. Add more under "Other boards".
"""

from __future__ import annotations

SEATTLE_BOARDS: list[tuple[str, str, str]] = [
    # (source, token, company)
    ("greenhouse", "remitly", "Remitly"),
    ("greenhouse", "icertis", "Icertis"),
    ("greenhouse", "outreach", "Outreach"),
    ("greenhouse", "rover", "Rover"),
    ("greenhouse", "smartsheet", "Smartsheet"),
    ("greenhouse", "tanium", "Tanium"),
    ("greenhouse", "convoy", "Convoy"),
    ("greenhouse", "textio", "Textio"),
    ("lever", "highspot", "Highspot"),
    ("lever", "tripadvisor", "Tripadvisor"),
    ("lever", "zulily", "Zulily"),
    ("greenhouse", "zillowgroup", "Zillow"),
    ("greenhouse", "docusign", "DocuSign"),
]


def board_key(source: str, token: str) -> str:
    return f"{source}:{token}"
