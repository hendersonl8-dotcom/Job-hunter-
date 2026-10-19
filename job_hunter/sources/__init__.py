"""Job sources. Each one turns a public API (or something you paste) into Job records.

LinkedIn and Glassdoor are paste-only on purpose: their terms forbid scraping and
automated applying, and accounts that use bots get restricted.
"""

from .greenhouse import fetch_greenhouse
from .lever import fetch_lever
from .manual import job_from_paste
from .seattle_boards import SEATTLE_BOARDS
from .shortlist import jobs_from_csv
from .usajobs import fetch_usajobs

__all__ = ["SEATTLE_BOARDS", "fetch_greenhouse", "fetch_lever", "fetch_usajobs", "job_from_paste", "jobs_from_csv"]
