#!/usr/bin/env python3
"""taxonomy — the normalizer tier: turn raw catalogue strings into clean nodes.

Facet values in the catalogue are opaque strings. Some are really SETS wearing a
compound-string costume ("Pali and Lan Na"), some are the same node spelled two ways
("th" / "Monolingual Thai"). Browsing on the raw string therefore both *fragments*
(Pali scattered across eight compounds) and *lumps* (75% of the corpus in one
"Pali and Lan Na" bucket). This module is where a value stops being a string and
becomes a normalized, multi-valued node — the precondition for honest facets,
orientation counts, and routing findings to the thing they're about.

Stdlib only. Start with language (the worst offender); place and genre_raw follow the
same alias→canonical, compound→components pattern.
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path

# ---- language -------------------------------------------------------------------
# One canonical node per language; every spelling/code the catalogue uses maps in.
# Lan Na (Kham Mueang, "Northern Thai") is kept distinct from central Thai on purpose.
_LANG_CANON = {
    "pali": "Pali",
    "lan na": "Lan Na", "lanna": "Lan Na", "northern thai": "Lan Na", "kham mueang": "Lan Na",
    "thai": "Thai", "th": "Thai", "central thai": "Thai",
    "lao": "Lao",
    "shan": "Shan", "tai yai": "Shan",
    "burmese": "Burmese", "myanmar": "Burmese",
    "tai lue": "Tai Lue", "lue": "Tai Lue",
    "mon": "Mon",
    "khmer": "Khmer",
    "sanskrit": "Sanskrit",
    "other": "Other",
}

# Display label per canonical node (a little context for the human; bots use the id).
LANGUAGE_LABELS = {
    "Pali": "Pali", "Lan Na": "Lan Na · Kham Mueang", "Thai": "Thai · Central",
    "Lao": "Lao", "Shan": "Shan · Tai Yai", "Burmese": "Burmese",
    "Tai Lue": "Tai Lue", "Mon": "Mon", "Khmer": "Khmer",
    "Sanskrit": "Sanskrit", "Other": "Other",
}

# Split a compound on "and", commas, "&", slashes, and hyphens ("Pali-Northern Thai").
_LANG_SPLIT = re.compile(r"\s+and\s+|\s*[,/&]\s*|\s*-\s*", re.IGNORECASE)


def language_components(raw):
    """['Pali','Lan Na'] from 'Pali and Lan Na'; ['Pali'] from 'Monolingual Pali';
    ['Thai'] from 'th'. Order-stable, de-duplicated, unknown tokens title-cased so a
    new spelling degrades to its own node instead of vanishing."""
    if not raw:
        return []
    s = raw.strip()
    # "Monolingual X" is just X; the mono-/compound distinction is recoverable from
    # the component count, so we don't need to keep the word.
    s = re.sub(r"^monolingual\s+", "", s, flags=re.IGNORECASE)
    out, seen = [], set()
    for tok in _LANG_SPLIT.split(s):
        t = tok.strip()
        if not t:
            continue
        canon = _LANG_CANON.get(t.lower(), t.title())
        if canon not in seen:
            seen.add(canon)
            out.append(canon)
    return out


def is_monolingual(raw):
    return len(language_components(raw)) == 1


# ---- script family --------------------------------------------------------------
# The scripts split into families the catalogue never names. Tham (Dhamma) is the
# sacred script family — Lanna, Lao and Lue are three regional hands of the SAME
# script tradition — so a "written in a Tham hand" roll-up gathers the shared
# manuscript-culture heritage that the eight leaf-level codes scatter.
_SCRIPT_FAMILY = {
    "tham_lanna": "Tham (Dhamma)", "tham_lao": "Tham (Dhamma)", "tham_lue": "Tham (Dhamma)",
    "shan": "Shan", "thai": "Thai", "thai_nithet": "Thai",
    "burmese": "Burmese", "khom": "Khom (Khmer)",
}
SCRIPT_FAMILY_LABELS = {
    "Tham (Dhamma)": "Tham · the Dhamma script family", "Shan": "Shan",
    "Thai": "Thai", "Burmese": "Burmese", "Khom (Khmer)": "Khom · Khmer script",
}


def script_family(script):
    """The script's family node ('Tham (Dhamma)' for tham_lanna/lao/lue), or the
    script title-cased if it stands alone. '' for empty."""
    if not script:
        return ""
    return _SCRIPT_FAMILY.get(script, script.replace("_", " ").title())


# ---- subgenre (the genre_raw middle tier, made a real node) ----------------------
# genre_raw folds 52 values into 13 normalized genres and is then shown as dead text.
# The recognised English labels ARE the subgenre tier — each a clean child of one
# genre — so we promote them to browsable nodes. The long tail of one-off Thai
# descriptions (the contributed haul's own titles) are NOT subgenres; they collapse
# to None so they don't pollute the axis.
_SUBGENRES = {
    "Jataka", "Sutta", "Buddhist Chronicle", "Vinaya", "Philology", "Astrology",
    "General Buddhism", "Tamnan", "Abhidhamma", "Custom / Ritual", "Anisong",
    "Didactics", "Secular History", "Law", "Chanting", "Buddhist Tale", "Folk Tale",
    "Secular Literary Work",
}
# Non-informative raw buckets: real values, but useless as a facet — drop them.
_SUBGENRE_NOISE = {"Undetermined", "Other", "Miscellany", ""}


def subgenre(genre_raw):
    """The canonical subgenre node for a genre_raw string, or None when the raw value
    is noise ('Undetermined') or a one-off contributed title (not a genre at all)."""
    if not genre_raw:
        return None
    g = genre_raw.strip()
    if g in _SUBGENRES:
        return g
    return None


# ---- geography: split the level-collision in provenance_province -----------------
# The province column mixes three geographic levels: real provinces, districts
# ("Sung Men District") and even temples ("Wat Chiang Man"). We classify each value
# and resolve it UP to its province where that's an administrative fact (districts)
# or an unambiguous, well-known temple. Anything we can't place honestly resolves to
# '' — better absent from the province facet than guessed.
CANONICAL_PROVINCES = {
    "Phrae", "Lampang", "Chiang Mai", "Nan", "Phayao", "Lamphun", "Chiang Rai",
    "Mae Hong Son", "Bangkok", "Tak", "Chiang Tung", "Kengtung",
}
# District → province (administrative fact). "Mueang District" is every province's
# central district, so it's genuinely ambiguous and left unresolved.
_DISTRICT_TO_PROVINCE = {
    "Sung Men District": "Phrae", "Ko Kha District": "Lampang", "Pua District": "Nan",
    "Wiang Sa District": "Nan", "Mae Sariang District": "Mae Hong Son",
    "Li District": "Lamphun", "Thoen District": "Lampang",
    "Tha Wang Pha District": "Nan", "Pai District": "Mae Hong Son",
    "Khun Yuam District": "Mae Hong Son", "Hang Dong District": "Chiang Mai",
    "Hang Dong Disctrict": "Chiang Mai", "Ban Hong District": "Lamphun",
    "Tha District": "Lamphun",
}
# Well-known temple → province, only where the location is unambiguous.
_TEMPLE_TO_PROVINCE = {
    "Wat Sung Men": "Phrae", "Wat Phra Bat Ming Mueang": "Phrae",
    "Wat Chiang Man": "Chiang Mai", "Wat Saen Mueang Ma": "Chiang Mai",
    "Wat Si Suphan": "Chiang Mai", "Wat  Cedi Luang Worawihan": "Chiang Mai",
    "Wat Si Khom Kham": "Phayao", "Wat Pang Mu": "Mae Hong Son",
    "Wat Lai Hin Luang": "Lampang",
}


def geo_level(raw):
    """'province' | 'district' | 'temple' | 'other' — the actual geographic level of a
    value mis-filed in the province column."""
    if not raw:
        return "other"
    s = raw.strip()
    if s in CANONICAL_PROVINCES:
        return "province"
    if "District" in s or "Disctrict" in s:
        return "district"
    if s.startswith("Wat "):
        return "temple"
    return "other"


def resolve_province(raw):
    """The canonical province a provenance string belongs to — itself if it IS a
    province, its parent province if it's a district or a well-known temple, else ''
    (unknown, kept out of the province facet rather than guessed)."""
    if not raw:
        return ""
    s = raw.strip()
    if s in CANONICAL_PROVINCES:
        return s
    return _DISTRICT_TO_PROVINCE.get(s) or _TEMPLE_TO_PROVINCE.get(s) or ""


# ---- date: the calendar era (the antique↔modern axis, hiding in a compound string) --
# date_text is "1198 (Cunlasakkalat (CS))" or "2516 (Buddhist Era (BE))" — the year and
# its era system fused. The era system IS the antique/modern signal: Cunlasakkarat is
# the old Lanna reckoning (18th–19th c.), Buddhist Era the modern one. Pulling it out
# gives a facet that splits the historical corpus from the living/modern one — the seam
# the whole project is built around.
ERA_LABELS = {
    "CS": "Cunlasakkarat (CS) · antique Lanna",
    "BE": "Buddhist Era (BE) · modern",
    "Other": "Other era",
}


def era_of(date_text):
    """'CS' | 'BE' | 'Other' | '' — the calendar system a date is recorded in. Undated
    and bare '?' return '' (no era node); they're simply absent from the era facet."""
    if not date_text:
        return ""
    s = date_text.strip()
    if s in ("Undated", "?"):
        return ""
    if "CS" in s or "Cunlasak" in s or "Culasak" in s:
        return "CS"
    if "BE" in s or "Buddhist Era" in s:
        return "BE"
    return "Other"


# ---- material family ------------------------------------------------------------
# palm-leaf vs paper: mulberry (saa) and khoi are two paper supports that pattern with
# the later, vernacular texts (a holasat almanac is paper; a Tipiṭaka is palm-leaf).
_MATERIAL_FAMILY = {"palm_leaf": "Palm-leaf", "mulberry_paper": "Paper", "khoi": "Paper"}


def material_family(material):
    if not material:
        return ""
    return _MATERIAL_FAMILY.get(material, material.replace("_", " ").title())


# ---- reverse membership (node -> the raw column values it gathers) ---------------
# For the family axes the members are a fixed inversion of the alias maps, so a node
# page (article) can select exactly the manuscripts its facet counts. Data-driven
# axes (language, province) are inverted at query time in wiki.py, since their raw
# values come from the catalogue.
def _invert(d):
    out = {}
    for raw, canon in d.items():
        out.setdefault(canon, []).append(raw)
    return out


SCRIPT_FAMILY_MEMBERS = _invert(_SCRIPT_FAMILY)      # "Tham (Dhamma)" -> [tham_lanna, …]
MATERIAL_FAMILY_MEMBERS = _invert(_MATERIAL_FAMILY)  # "Paper" -> [mulberry_paper, khoi]


# ---- tradition / source-domain --------------------------------------------------
# The top-level axis of the wichaa corpus: which living tradition a record belongs to.
# wichaa is the root; "Lanna manuscripts" is ONE node here, coequal with the amulet
# market, the St. Expedite cult, and museum heritage — the seam is provenance, not a
# manuscript-shaped spine (see manuscript-wiki/REROOT_PLAN.md). A record's tradition is
# a roll-up over its source_id: manuscript libraries → Lanna; Lazada → amulet market;
# museum APIs → heritage; the St.-Expedite provenances → that cult. New sources degrade
# to "Other" until mapped here, rather than vanishing.
_TRADITION_BY_SOURCE = {
    **{i: "Lanna manuscripts" for i in range(1, 23)},   # 1–22: Lanna/Tai manuscript libraries + contributed texts
    23: "Thai amulet market", 27: "Thai amulet market",  # Lazada TH / SG commerce
    24: "Museum heritage", 25: "Museum heritage", 26: "Museum heritage",  # Cleveland/Met/Smithsonian CC0
    28: "St. Expedite", 29: "St. Expedite", 30: "St. Expedite",  # OSM shrines / Commons / research
}

# Display gloss + canonical order (drives the peer-door grid and the tradition facet).
TRADITION_LABELS = {
    "Lanna manuscripts": "Lanna manuscripts · palm-leaf wichaa",
    "Thai amulet market": "Thai amulet market · living commerce",
    "St. Expedite": "St. Expedite · a global saint-cult",
    "Museum heritage": "Museum heritage · CC0 objects",
    "Other": "Other",
}
TRADITION_ORDER = ["Lanna manuscripts", "Thai amulet market", "St. Expedite", "Museum heritage"]


def tradition_of(source_id, method=""):
    """The tradition node a record belongs to, from its source_id. `method` is a
    fallback hint ('devotion' → St. Expedite) so freshly-added St.-Expedite sources
    still classify before this map is updated."""
    t = _TRADITION_BY_SOURCE.get(source_id)
    if t:
        return t
    if method == "devotion":
        return "St. Expedite"
    if method == "commerce":
        return "Thai amulet market"
    if method == "museum":
        return "Museum heritage"
    return "Other"


# ---- entity resolution ------------------------------------------------------------
# The axes above normalize *columns*. This tier resolves a record to a named ENTITY —
# a person, a deity, a place — and that is a different and more dangerous job, because
# an entity is identified by a name appearing in free text rather than by a column
# value. A substring test is not a resolver: it cannot tell the Buddha's son Rāhula
# (ราหุล / ราหุโล / ลาหูโร, usually inside the -ovāda compound) from Rāhu the eclipse
# graha (พระราหู, ราหูอมจันทร์), and the two share the ราห stem. Six manuscripts in the
# catalogue — ids 205, 1018, 2598, 2878, 3161, 3444 — are Rāhulovāda material that a
# naive Rahu query returns. See manuscript-crawler/docs/RAHU_SOURCING.md.
#
# The adjudication rule lives once, in the crawler seed that recorded it
# (crawler/rahu_seed.py), and is imported here rather than restated — two copies of a
# disambiguation rule is how the drift starts. If the crawler is not reachable this
# module FAILS CLOSED: no record resolves to an entity, rather than falling back to
# the string match the rule exists to prevent.

def _load_rahu_rule():
    """The crawler's rahu_seed module, or None if the sibling project isn't there.

    Loaded straight off its path, NOT via sys.path — putting crawler/ on the import
    path would make its http.py shadow the stdlib `http` that wiki.py serves from.
    rahu_seed is stdlib-only and inert (no db, no network), so a file-load is safe."""
    # CATALOG_DB (set by wiki.py / the launchers) points at crawler/catalog.db, so its
    # parent IS the crawler package; otherwise use the standard sibling layout.
    env_db = os.environ.get("CATALOG_DB")
    candidates = []
    if env_db:
        candidates.append(Path(env_db).resolve().parent)
    candidates.append(Path(__file__).resolve().parent.parent / "manuscript-crawler" / "crawler")
    for c in candidates:
        path = c / "rahu_seed.py"
        if not path.exists():
            continue
        name = "_wichaa_rahu_seed"   # distinct, so we never collide with a real import
        try:
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            # Register BEFORE exec: @dataclass resolves field types through
            # sys.modules[cls.__module__], and dies on <3.10 if it isn't there.
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
            return mod
        except Exception:
            sys.modules.pop(name, None)
            return None
    return None


_RAHU = _load_rahu_rule()
RAHU_RULE_AVAILABLE = _RAHU is not None

# Entity key → the callable that decides membership from a manuscript row. Every new
# entity joins this table with its own adjudicator; nothing resolves by substring.
_ENTITY_RESOLVERS = {
    "phra_rahu": lambda row: bool(_RAHU) and _RAHU.is_phra_rahu(
        _row_get(row, "title_thai"), _row_get(row, "title_translit"),
        _row_get(row, "title_english"), genre=_row_get(row, "genre_normalized")),
}


def _row_get(row, key, default=""):
    """Field access that works for sqlite3.Row, dict, and plain mappings alike."""
    try:
        if hasattr(row, "get"):
            return row.get(key, default) or default
        return row[key] or default
    except (KeyError, IndexError):
        return default


def rahu_sense(*fields, genre=None):
    """'rahula' | 'rahu' | 'ambiguous' | None — which Rāhu a string names.
    None when the rule module is unreachable (fail closed; see above)."""
    if not _RAHU:
        return None
    return _RAHU.sense(*fields, genre=genre)


def is_phra_rahu(*fields, genre=None):
    """True only for Rāhu the eclipse graha. The Buddha's son and undecidable
    strings both return False, and so does an unreachable rule module."""
    return bool(_RAHU) and _RAHU.is_phra_rahu(*fields, genre=genre)


def entity_keys(row):
    """The entity nodes a manuscript row resolves to — an adjudicated set, never a
    substring match. Empty when nothing resolves or the rule module is missing."""
    return {key for key, resolves in _ENTITY_RESOLVERS.items() if resolves(row)}
