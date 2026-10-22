"""Ready-made search areas, mostly places a cleared Navy veteran finds work.

Each area has the place name USAJobs searches, the words a board job's location must
contain to count as "there", and company boards worth trying. Board tokens are
unverified: one that has moved or doesn't exist just shows an error for itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .seattle_boards import SEATTLE_BOARDS


@dataclass(frozen=True)
class Area:
    name: str
    usajobs_location: str
    terms: tuple[str, ...]
    boards: tuple[tuple[str, str, str], ...] = field(default_factory=tuple)  # (source, token, company)


AREAS: dict[str, Area] = {a.name: a for a in [
    Area("Seattle", "Seattle, Washington",
         ("Seattle", "Bellevue", "Redmond", "Kirkland", "Bothell", "Everett", "Lynnwood", "Renton", "Kent", "Tukwila", "Puget Sound"),
         tuple(SEATTLE_BOARDS)),
    Area("Kitsap / Bremerton", "Bremerton, Washington",
         ("Bremerton", "Silverdale", "Bangor", "Keyport", "Kitsap", "Poulsbo", "Port Orchard"),
         (("greenhouse", "andurilindustries", "Anduril"),)),
    Area("Tacoma / JBLM", "Tacoma, Washington",
         ("Tacoma", "Lakewood", "JBLM", "Joint Base Lewis", "Olympia", "Lacey", "DuPont", "Puyallup"),
         ()),
    Area("San Diego", "San Diego, California",
         ("San Diego", "Point Loma", "Coronado", "Chula Vista", "Carlsbad"),
         (("greenhouse", "andurilindustries", "Anduril"), ("lever", "shieldai", "Shield AI"),
          ("greenhouse", "saronic", "Saronic"), ("lever", "palantir", "Palantir"))),
    Area("Norfolk / Virginia Beach", "Norfolk, Virginia",
         ("Norfolk", "Virginia Beach", "Chesapeake", "Portsmouth", "Suffolk", "Hampton", "Newport News", "Little Creek"),
         (("lever", "palantir", "Palantir"), ("greenhouse", "andurilindustries", "Anduril"))),
    Area("Pearl Harbor / Honolulu", "Honolulu, Hawaii",
         ("Honolulu", "Pearl Harbor", "Oahu", "Kapolei", "Aiea"),
         ()),
    Area("Washington DC / Annapolis", "Washington, District of Columbia",
         ("Washington, DC", "Arlington", "Alexandria", "Annapolis", "Reston", "McLean", "Fairfax", "Crystal City"),
         (("lever", "palantir", "Palantir"), ("greenhouse", "andurilindustries", "Anduril"))),
]}
