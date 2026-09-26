"""Who made this page, as schema.org sees it.

The citation tags say "Peacock, Nan" because Zotero parses that field as a
personal name and splits it on the comma. JSON-LD wants the name in reading
order with the parts given separately. Both forms come from the same two words
here rather than being typed twice in different files and drifting apart.

A Manuscript node never takes an author. The palm-leaf texts in this corpus
were written by people whose names are mostly lost, and putting a living
cataloguer's name in that field would be a false claim about the object. The
page ABOUT a manuscript does have an author, and that is a separate node.
"""
from __future__ import annotations

import json
from pathlib import Path

import fleet

HERE = Path(__file__).resolve().parent
GIVEN, FAMILY = "Nan", "Peacock"
CITE_AUTHOR = f"{FAMILY}, {GIVEN}"
LEDGER = HERE / "data" / "page_dates.json"


def _roster():
    try:
        return fleet.load(HERE / "data" / "fleet.json")
    except Exception:
        return None


def person() -> dict:
    """The named human. sameAs carries the rest of the fleet, which is how a
    search engine ties twenty sites to one author rather than twenty strangers."""
    node = {"@type": "Person", "name": f"{GIVEN} {FAMILY}",
            "givenName": GIVEN, "familyName": FAMILY}
    r = _roster()
    if r:
        node["url"] = r["index"]
        node["sameAs"] = fleet.same_as(roster=r)
    return node


def publisher() -> dict:
    r = _roster()
    return fleet.publisher_ld(roster=r) if r else {"@type": "Organization",
                                                   "name": "wichaa"}


def dates(route: str) -> tuple[str, str]:
    """(first published, last modified) for a built route, read from the ledger
    site_meta keeps. Empty strings when the route has never been stamped —
    a date that is not known is left out rather than guessed at."""
    try:
        rec = json.loads(LEDGER.read_text(encoding="utf-8"))["routes"][route]
    except Exception:
        return "", ""
    return rec.get("first", ""), rec.get("modified", "")


def sign(node: dict, route: str = "", license_url: str = "") -> dict:
    """Add author, publisher and the two dates to an article-shaped node."""
    node["author"] = person()
    node["publisher"] = publisher()
    pub, mod = dates(route)
    if pub:
        node.setdefault("datePublished", pub)
    if mod:
        node.setdefault("dateModified", mod)
    if license_url:
        node.setdefault("license", license_url)
    return node


def webpage(url: str, name: str, route: str = "", license_url: str = "",
            about: dict | None = None) -> dict:
    """The record page, as distinct from the thing it describes."""
    node = {"@context": "https://schema.org", "@type": "WebPage",
            "url": url, "name": name}
    if about:
        node["about"] = about
    return sign(node, route, license_url)
