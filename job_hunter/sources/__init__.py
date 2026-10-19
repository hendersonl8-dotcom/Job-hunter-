"""Job sources. Each one turns a public API (or something you paste) into Job records.

LinkedIn and Glassdoor are paste-only on purpose: their terms forbid scraping and
automated applying, and accounts that use bots get restricted.
"""

from .greenhouse import fetch_greenhouse
from .lever import fetch_lever
from .manual import job_from_paste
from .usajobs import fetch_usajobs

__all__ = ["fetch_greenhouse", "fetch_lever", "fetch_usajobs", "job_from_paste"]
