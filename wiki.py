#!/usr/bin/env python3
"""wiki.py — a friendly, accessible local wiki over the Lanna manuscript catalog.

Zero dependencies (Python stdlib only). It is a READ-ONLY view over the crawler's
SQLite catalog (crawler/catalog.db) and its content-addressed image store
(crawler/store/). It never writes to the catalog. Your own notes/tags and any OCR
text live in side files under wiki/data/ so they survive re-crawls.

    python3 wiki.py            # opens http://127.0.0.1:4190

Env overrides: CATALOG_DB, STORE_DIR, PORT.
"""
from __future__ import annotations

import hashlib
import html
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import taxonomy  # the normalizer tier: raw strings -> clean multi-valued nodes
import moondial  # the moonphase complication: its geometry, its dial, and its essay
import sukhwanweb  # สู่ขวัญยนต์ — the khwan-calling rite for machines, with robot opt-in
import hotrai      # หอไตร — the wat library addressed to machines (page + text corpus)
import khwantext   # สู่ขวัญ — the human soul-calling published in full (verses: hunpayont.SUKHWAN)
import waikhru     # ไหว้ครูยนต์ — the blessing for the person's hand at the machine
import romphon     # ใต้ร่มพร — the standing blessings the whole fleet works under
from urllib.parse import urlparse, parse_qs, quote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"
DATA.mkdir(exist_ok=True)
CONTENT = HERE / "content"       # authored article prose (markdown), one file per subject

def _resolve_catalog():
    """Find catalog.db even when launched with no env (launchd, double-click, another
    tool). The historical default (ROOT/crawler) is wrong — the real catalog lives in
    the sibling manuscript-crawler project — so an envless start used to serve an empty
    site. Auto-detect the first candidate that actually exists; only fall back to the
    old default when nothing is found, so first-run behaviour is unchanged."""
    env = os.environ.get("CATALOG_DB")
    if env:
        return Path(env)
    candidates = [
        ROOT / "manuscript-crawler" / "crawler" / "catalog.db",  # the real one
        ROOT / "crawler" / "catalog.db",                          # legacy default
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[-1]


CATALOG_DB = _resolve_catalog()
# Store lives next to whichever catalog we resolved, unless overridden.
STORE_DIR = Path(os.environ.get("STORE_DIR", CATALOG_DB.parent / "store"))
# epub_volume.py (manuscript-crawler) writes finished ebooks here; we only ever
# serve what's already built — the wiki doesn't build epubs itself.
EPUB_DIR = Path(os.environ.get("EPUB_DIR", CATALOG_DB.parent.parent / "epub"))
PORT = int(os.environ.get("PORT", "4190"))
# Absolute origin the public site is served from (e.g. https://nanobotco.github.io/Lanna).
# Only needed so shared-link previews carry an absolute og:image; empty is fine locally.
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")
ANN_PATH = DATA / "annotations.json"
OCR_PATH = DATA / "ocr.json"
REL_PATH = DATA / "relations.json"  # durable, human-authored typed graph edges
FEATURED_PATH = DATA / "featured.json"  # durable, human-curated "this folio is striking" stars
# Shared bot pulse: heartbeat.py (in the crawler project) appends one JSON line
# per action here, next to catalog.db. The /activity view merges it with the
# crawler's own crawl_log into a single live feed. Override with ACTIVITY_LEDGER.
ACTIVITY_LEDGER = Path(os.environ.get(
    "ACTIVITY_LEDGER", CATALOG_DB.parent / "activity.jsonl"))
ACTIVITY_LIVE_WINDOW = 300   # seconds: an actor is "live" if seen this recently
# The scheduler's config + last-run state live in the crawler project root (one
# level above crawler/catalog.db). Reading them lets /activity show the FULL job
# roster — "ran 8m ago · next in 168m" — so a healthy idle bot doesn't read as dead.
SCHEDULER_DIR = Path(os.environ.get("SCHEDULER_DIR", CATALOG_DB.parent.parent))
# The forever.sh crawl loop (scheduler.py's successor, ~2026-07-22) also lives in
# the crawler project root. It leaves three traces /activity can read: .forever.lock
# (the live pid), .forever.cycle.json (cycle/step state, written by newer forever.sh),
# and forever.log's cycle-marker lines. Publishing must pin this (see publish_site.sh)
# because CATALOG_DB points at a /tmp snapshot during a static build.
FOREVER_DIR = Path(os.environ.get("FOREVER_DIR", CATALOG_DB.parent.parent))

_job_lock = threading.Lock()

# ---- pretty labels for the normalized tokens the crawler's genre.py emits ----
# Kept in step with taxonomy_seed's genre/wichaa vocabulary (renormalize.py).
# Labels are bilingual — "English · ไทย" — so a facet is legible to both an
# English-reading scholar and a Thai reader. prettify() shows the value verbatim.
GENRE_LABELS = {
    "divination_omen": "Divination & Omens · การทำนาย", "astrology": "Astrology · โหราศาสตร์",
    "magic_ritual": "Magic & Ritual · ไสยศาสตร์", "buddhist_canonical": "Buddhist Canonical · พระไตรปิฎก",
    "jataka": "Jātaka · ชาดก", "tamnan_chronicle": "Chronicle (Tamnan) · ตำนาน",
    "law_customary": "Customary Law · กฎหมายจารีต", "medicine": "Medicine · ตำรายา",
    "grammar_lexicography": "Grammar & Lexicography · ไวยากรณ์",
    "poetry_literary": "Poetry & Literature · วรรณกรรม", "didactic_moral": "Didactic & Moral · คำสอน",
    "liturgy_chanting": "Liturgy & Chanting · บทสวด", "other": "Other · อื่น ๆ",
}
# One-line glosses, shown on the Overview to orient a browser to each genre.
GENRE_NOTES = {
    "buddhist_canonical": "Tipiṭaka texts — Sutta, Vinaya, Abhidhamma and commentary.",
    "jataka": "Birth-tales of the Buddha (chadok), incl. the Vessantara.",
    "tamnan_chronicle": "Tamnan — temple, relic and dynastic chronicles.",
    "astrology": "Horā — horoscopy, planetary reckoning, calendrical prediction.",
    "magic_ritual": "Saiyasat — yantra, mantra, protective and ritual magic.",
    "divination_omen": "Omen-reading, dream and lot divination (mo duu).",
    "grammar_lexicography": "Grammar, philology and vocabulary (nissaya, saddā).",
    "law_customary": "Customary law — the Mangrai code and local ordinances.",
    "medicine": "Herbal and healing texts (tamra ya).",
    "didactic_moral": "Moral instruction, proverbs and conduct (subhāsit).",
    "poetry_literary": "Secular poetry and literary works (khlong, khao).",
    "liturgy_chanting": "Chanting and liturgy for recitation (suat mon).",
    "other": "Uncatalogued or mixed — awaiting classification.",
}
SCRIPT_LABELS = {
    "tham_lanna": "Tham Lanna · อักษรธรรมล้านนา", "tham_khuen": "Tham Khuen · อักษรธรรมเขิน",
    "tham_lue": "Tham Lue · อักษรธรรมลื้อ", "tham_lao": "Tham Lao · อักษรธรรมลาว",
    "shan": "Shan · อักษรไทใหญ่", "burmese": "Burmese · อักษรพม่า", "khom": "Khom · อักษรขอม",
    "thai_nithet": "Thai Nithet (Fak Kham) · อักษรฝักขาม", "thai": "Thai · อักษรไทย",
}
MATERIAL_LABELS = {
    "palm_leaf": "Palm-leaf · ใบลาน", "mulberry_paper": "Mulberry paper (saa) · กระดาษสา",
    "khoi": "Khoi paper · กระดาษข่อย",
}
PRIORITY_GENRES = {"divination_omen", "astrology", "magic_ritual"}


def prettify(token, table):
    if not token:
        return ""
    if table:
        return table.get(token, str(token).replace("_", " ").title())
    return str(token).replace("_", " ").title()


# ---------------------------- data access ----------------------------
def db_present():
    return CATALOG_DB.exists()


def connect():
    # Read-only; never mutate the crawler's catalog.
    #
    # CATALOG_IMMUTABLE is set by publish_site.sh AFTER it has snapshotted the
    # catalogue to a private temp copy. That copy genuinely cannot change while
    # the build reads it, and saying so lets SQLite skip locking entirely —
    # which sidesteps the whole failure class where a read-only opener cannot
    # roll back a hot journal and dies with "unable to open database file".
    # Never set it against the LIVE catalogue: the crawler writes that file, and
    # immutable would license SQLite to serve stale or torn pages.
    if os.environ.get("CATALOG_IMMUTABLE"):
        uri = f"file:{CATALOG_DB}?immutable=1"
    else:
        uri = f"file:{CATALOG_DB}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_json(path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def save_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def century_of(year):
    if not year:
        return ""
    try:
        y = int(year)
    except (TypeError, ValueError):
        return ""
    c = (abs(y) - 1) // 100 + 1
    suffix = "th" if 10 <= c % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(c % 10, "th")
    return f"{c}{suffix}"


def ann_key(source_name, source_identifier):
    return f"{source_name or '?'}::{source_identifier or '?'}"


def ms_summary(row):
    title = row["title_english"] or row["title_translit"] or row["title_thai"] or row["source_identifier"]
    return {
        "id": row["id"],
        "key": ann_key(row["source_name"], row["source_identifier"]),
        "title": title,
        "titleThai": row["title_thai"] or "",
        "titleTranslit": row["title_translit"] or "",
        "source": row["source_name"] or "",
        "sourceIdentifier": row["source_identifier"] or "",
        # top-level wichaa axis: which living tradition this record belongs to.
        # Manuscripts all roll up to "Lanna manuscripts" — one node among the corpus's
        # traditions (amulet market, St. Expedite, museum heritage live in `items`).
        "tradition": taxonomy.tradition_of(row["source_id"]),
        "genre": row["genre_normalized"] or "other",
        "genreLabel": prettify(row["genre_normalized"] or "other", GENRE_LABELS),
        "genreRaw": row["genre_raw"] or "",
        "priority": row["priority"] or 0,
        "script": row["script"] or "",
        "scriptLabel": prettify(row["script"], SCRIPT_LABELS),
        # script's Dhamma-family roll-up (tham_lanna/lao/lue -> "Tham (Dhamma)")
        "scriptFamily": taxonomy.script_family(row["script"]),
        "language": row["language"] or "",
        # normalized multi-valued language node set — "Pali and Lan Na" -> [Pali, Lan Na]
        "languages": taxonomy.language_components(row["language"]),
        # genre_raw promoted to a browsable subgenre node (None for noise/one-offs)
        "subgenre": taxonomy.subgenre(row["genre_raw"]),
        "material": row["material"] or "",
        "materialLabel": prettify(row["material"], MATERIAL_LABELS),
        # palm-leaf vs paper roll-up (mulberry_paper + khoi -> "Paper")
        "materialFamily": taxonomy.material_family(row["material"]),
        # province column mixes provinces/districts/temples: `province` is the resolved
        # canonical province (for the facet), `provenance` keeps the raw string, and
        # `geoLevel` records what the raw value actually was.
        "province": taxonomy.resolve_province(row["provenance_province"]),
        "provenance": row["provenance_province"] or "",
        "geoLevel": taxonomy.geo_level(row["provenance_province"]),
        "temple": row["provenance_temple"] or "",
        "date": row["date_text"] or "",
        # a year the list can be ORDERED by; null where the record is undated,
        # so an undated manuscript is never given a year it does not have
        "dateSort": taxonomy.date_sort_ce(row["date_text"], row["date_ce_estimate"]),
        # calendar era pulled out of the date string: CS (antique Lanna) vs BE (modern)
        "era": taxonomy.era_of(row["date_text"]),
        "century": century_of(row["date_ce_estimate"]),
        "extentPages": row["extent_pages"] or 0,
        "imageCount": row["image_count"] or 0,
        # rendered/digested pages (contributed volumes) — distinct from crawled scans
        "pageCount": (row["page_count"] if "page_count" in row.keys() else 0) or 0,
    }


MS_SELECT = """
    SELECT m.*, s.name AS source_name,
           (SELECT COUNT(*) FROM images i WHERE i.manuscript_id = m.id) AS image_count,
           (SELECT COUNT(*) FROM pages p WHERE p.manuscript_id = m.id) AS page_count
    FROM manuscripts m JOIN sources s ON s.id = m.source_id
"""


def all_manuscripts():
    if not db_present():
        return []
    conn = connect()
    try:
        rows = conn.execute(MS_SELECT).fetchall()
        return [ms_summary(r) for r in rows]
    finally:
        conn.close()


# /api/manuscripts ships the whole catalogue (~4.4MB) so the browse page can
# facet and filter client-side. Building + JSON-encoding that on every page load
# is wasteful when the catalogue hasn't changed — cache the encoded bytes, keyed
# by catalog signature.
_MS_API_MEM = {"sig": None, "body": None}


def manuscripts_api_body():
    """UTF-8 JSON bytes for /api/manuscripts, cached until the catalog signature
    moves. Returns bytes ready to hand straight to _send."""
    sig = current_signature()
    if _MS_API_MEM["sig"] == sig and _MS_API_MEM["body"] is not None:
        return _MS_API_MEM["body"]
    items = all_manuscripts()
    items.sort(key=lambda x: (0 if x["priority"] else 1, x["title"].lower()))
    # attach a representative thumbnail (page or scan) to each card, computed in bulk
    conn = connect()
    try:
        thumbs = manuscript_thumbs(conn)
    finally:
        conn.close()
    for it in items:
        it["thumb"] = thumbs.get(it["id"])
    facets, labels = build_facets(items)
    payload = {"items": items, "facets": facets, "labels": labels,
               "count": len(items), "dbPresent": db_present()}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    _MS_API_MEM["sig"] = sig
    _MS_API_MEM["body"] = body
    return body


def iiif_resize(url, w):
    """Rewrite a IIIF Image API URL's size segment to width `w` (…/full/{w},/…).
    Crawled thumbnails arrive sized /full/512,/ — cards want smaller, heroes larger.
    Handles both /full/512,/ and /full/full/ region-size forms. Returns url unchanged
    if it isn't a recognisable IIIF request."""
    if not url:
        return url
    return re.sub(r"(/full/)[^/]+(/\d+/default)", rf"\g<1>{w},\2", url)


def manuscript_thumbs(conn):
    """{mid: {'src':…, 'kind':'page'|'scan'}} — one representative thumbnail per
    manuscript that has any imagery, for the Browse cards. Two bulk queries (not a
    per-row lookup): a rendered PAGE wins when present (richest signal — diagram >
    vision-described > first), otherwise the first downloaded raw SCAN. Manuscripts
    with no imagery are simply absent → the card falls back to a typographic
    monogram. Read-only; called once per catalogue signature via the API cache."""
    thumbs = {}
    # 1. best rendered page per manuscript. Ordered best-first within each ms, so the
    #    first row seen for a given mid is the one to keep. Only ~30 mss have pages.
    for r in conn.execute(
        "SELECT p.manuscript_id mid, p.page_no page FROM pages p "
        "WHERE p.image_path IS NOT NULL "
        "ORDER BY p.manuscript_id, (p.kind='diagram') DESC, "
        "  (p.vision_desc IS NOT NULL AND p.vision_desc!='') DESC, p.page_no"):
        if r["mid"] not in thumbs:
            thumbs[r["mid"]] = {"src": "/pimg?mid=%d&n=%d&w=240" % (r["mid"], r["page"]),
                                "kind": "page"}
    # 2. first downloaded raw scan for manuscripts that have no page image. SQLite
    #    returns the sha of the MIN(sequence) row when a single aggregate is used.
    for r in conn.execute(
        "SELECT i.manuscript_id mid, MIN(i.sequence) seq, i.sha256 sha FROM images i "
        "WHERE i.status='downloaded' AND i.sha256 IS NOT NULL AND i.sha256!='' "
        "GROUP BY i.manuscript_id"):
        if r["mid"] not in thumbs:
            thumbs[r["mid"]] = {"src": "/img?sha=%s&w=240" % r["sha"], "kind": "scan",
                                "sha": r["sha"]}
    # 3. metadata-only manuscripts (Phase-1 crawl: no images rows) still carry a
    #    representative IIIF thumbnail in raw_metadata. Surface it — otherwise ~75%
    #    of the corpus shows a bare monogram though a real folio is one request away.
    for r in conn.execute(
        "SELECT id mid, json_extract(raw_metadata,'$.thumbnail') thumb FROM manuscripts "
        "WHERE raw_metadata LIKE '%thumbnail%'"):
        if r["mid"] not in thumbs and r["thumb"]:
            thumbs[r["mid"]] = {"src": iiif_resize(r["thumb"], 240), "kind": "iiif"}
    return thumbs


def build_facets(items):
    facets = {"tradition": {}, "genre": {}, "subgenre": {}, "script": {}, "scriptFamily": {},
              "material": {}, "materialFamily": {}, "languages": {}, "province": {},
              "temple": {}, "source": {}, "era": {}, "century": {}, "priority": {}}
    labels = {"tradition": {}, "genre": {}, "script": {}, "material": {}, "languages": {},
              "scriptFamily": {}, "era": {}}

    def bump(bucket, val, label=None):
        if not val:
            return
        facets[bucket][val] = facets[bucket].get(val, 0) + 1
        if label is not None:
            labels[bucket][val] = label

    for it in items:
        bump("tradition", it.get("tradition"),
             taxonomy.TRADITION_LABELS.get(it.get("tradition"), it.get("tradition")))
        bump("genre", it["genre"], it["genreLabel"])
        bump("subgenre", it.get("subgenre"))          # the promoted genre_raw middle tier
        bump("script", it["script"], it["scriptLabel"])
        bump("scriptFamily", it.get("scriptFamily"),
             taxonomy.SCRIPT_FAMILY_LABELS.get(it.get("scriptFamily"), it.get("scriptFamily")))
        bump("material", it["material"], it["materialLabel"])
        bump("materialFamily", it.get("materialFamily"))
        bump("era", it.get("era"), taxonomy.ERA_LABELS.get(it.get("era")))
        # language is multi-valued: a manuscript counts under each language it carries,
        # so "Pali" gathers all ~7k Pali witnesses instead of fragmenting across compounds
        for lang in it.get("languages", []):
            bump("languages", lang, taxonomy.LANGUAGE_LABELS.get(lang, lang))
        bump("province", it["province"])
        bump("temple", it["temple"])
        bump("source", it["source"])
        bump("century", it["century"])
        if it["priority"]:
            facets["priority"]["Research priority"] = facets["priority"].get("Research priority", 0) + 1
    return facets, labels


def manuscript_detail(mid):
    if not db_present():
        return None
    conn = connect()
    try:
        row = conn.execute(MS_SELECT + " WHERE m.id = ?", (mid,)).fetchone()
        if not row:
            return None
        summ = ms_summary(row)
        # wichaa subjects this manuscript names → doors up to the subject articles
        summ["subjects"] = entities_in_text(
            " ".join(filter(None, [summ.get("title"), summ.get("titleTranslit"),
                                   summ.get("titleThai")])))
        summ["dateCe"] = row["date_ce_estimate"]
        # The wat-registry stamp. 6,203 manuscripts carry a รหัสวัด — a
        # permanent government code for the temple that holds them, with the
        # nikaya, the temple's rank and the year it was founded. It has been in
        # the catalogue since 2026-08-09 and no page has ever shown it.
        summ["watCode"] = row["wat_code"] or ""
        summ["watNameTh"] = row["wat_name_th"] or ""
        summ["watSect"] = row["wat_sect"] or ""
        summ["watRank"] = row["wat_rank"] or ""
        summ["watFoundedCe"] = row["wat_founded_ce"]
        summ["watMatchHow"] = row["wat_match_how"] or ""
        summ["sourceUrl"] = row["source_url"] or ""
        summ["iiifManifestUrl"] = row["iiif_manifest_url"] or ""
        summ["firstSeen"] = row["first_seen"] or ""
        summ["lastSeen"] = row["last_seen"] or ""
        try:
            summ["rawMetadata"] = json.loads(row["raw_metadata"]) if row["raw_metadata"] else None
        except Exception:
            summ["rawMetadata"] = row["raw_metadata"]
        imgs = conn.execute(
            "SELECT sequence, source_image_url, local_path, sha256, bytes, status "
            "FROM images WHERE manuscript_id = ? ORDER BY sequence", (mid,)
        ).fetchall()
        ocr = load_json(OCR_PATH, {})
        summ["images"] = [{
            "sequence": i["sequence"], "sha256": i["sha256"], "status": i["status"],
            "bytes": i["bytes"] or 0, "sourceUrl": i["source_image_url"] or "",
            "hasLocal": bool(i["sha256"]) and store_path(i["sha256"]) is not None,
            "ocr": (ocr.get(i["sha256"], {}) or {}).get("text", "") if i["sha256"] else "",
            "ocrEngine": (ocr.get(i["sha256"], {}) or {}).get("engine", "") if i["sha256"] else "",
            "ocrScript": (ocr.get(i["sha256"], {}) or {}).get("script", "") if i["sha256"] else "",
            "ocrConf": (ocr.get(i["sha256"], {}) or {}).get("confidence") if i["sha256"] else None,
        } for i in imgs]
        # A representative folio for the ~75% of manuscripts crawled metadata-only
        # (no images rows): the IIIF thumbnail the source already gave us, shown when
        # nothing is catalogued locally. One real folio beats a "no images" void.
        thumb = summ["rawMetadata"].get("thumbnail") if isinstance(summ.get("rawMetadata"), dict) else None
        summ["iiifThumb"] = iiif_resize(thumb, 800) if (thumb and not summ["images"]) else ""
        # Digested pages (contributed volumes): every one is a real, renderable image —
        # served on demand via /pimg. Carry the lightweight per-page metadata so the
        # detail can feature them as a gallery, with diagram pages flagged and any
        # vision description as a caption. This is the imagery the "0 images" hid.
        summ["pages"] = [{"n": p["page_no"], "kind": p["kind"] or "",
                          "chars": p["thai_chars"] or 0,
                          "desc": (p["vision_desc"] or "").strip()[:200]}
                         for p in conn.execute(
            "SELECT page_no, kind, thai_chars, vision_desc FROM pages "
            "WHERE manuscript_id=? ORDER BY page_no", (mid,)).fetchall()]
        summ["diagramPages"] = sum(1 for p in summ["pages"] if p["kind"] == "diagram")
        summ["related"] = _related(conn, row)
        summ["id"] = mid
        # A fully transcribed+translated volume gets a bilingual reader (/read).
        summ["hasReader"] = conn.execute(
            "SELECT 1 FROM pages WHERE manuscript_id=? AND transcription IS NOT NULL "
            "AND transcription<>'' LIMIT 1", (mid,)).fetchone() is not None
        return summ
    finally:
        conn.close()


def _related(conn, row, limit=6):
    """Small linked lists of siblings that share this manuscript's facets —
    the navigational 'more like this' on a detail page. Each is (facet, value,
    label, [ {id,title} ]) so the UI can also deep-link to the filtered browse."""
    mid = row["id"]
    out = []
    probes = [
        ("temple", row["provenance_temple"],
         prettify(row["provenance_temple"], {}) or row["provenance_temple"]),
        ("genre", row["genre_normalized"] or "other",
         prettify(row["genre_normalized"] or "other", GENRE_LABELS)),
        ("province", row["provenance_province"], row["provenance_province"]),
    ]
    for facet, value, label in probes:
        if not value:
            continue
        col = {"temple": "provenance_temple", "genre": "genre_normalized",
               "province": "provenance_province"}[facet]
        rows = conn.execute(
            MS_SELECT + f" WHERE m.{col} = ? AND m.id <> ? "
            "ORDER BY m.priority DESC, m.title_english, m.title_translit LIMIT ?",
            (value, mid, limit),
        ).fetchall()
        peers = [{"id": r["id"],
                  "title": (r["title_english"] or r["title_translit"]
                            or r["title_thai"] or r["source_identifier"])}
                 for r in rows]
        if peers:
            out.append({"facet": facet, "value": value, "label": label, "items": peers})
    return out


def status_snapshot():
    # Publish only basenames, never absolute paths: this snapshot is exported to the
    # PUBLIC static site, and a full path leaks the operator's username + local
    # directory layout. Basenames keep the field shape for consumers with zero leak.
    snap = {"dbPresent": db_present(),
            "dbPath": os.path.basename(str(CATALOG_DB)),
            "storeDir": os.path.basename(str(STORE_DIR)),
            "counts": {}, "sources": [], "log": []}
    if not db_present():
        return snap
    conn = connect()
    try:
        c = conn.execute
        snap["counts"] = {
            "manuscripts": c("SELECT COUNT(*) n FROM manuscripts").fetchone()["n"],
            "priority": c("SELECT COUNT(*) n FROM manuscripts WHERE priority=1").fetchone()["n"],
            "images": c("SELECT COUNT(*) n FROM images").fetchone()["n"],
            "imagesDownloaded": c("SELECT COUNT(*) n FROM images WHERE status='downloaded'").fetchone()["n"],
            "imagesPending": c("SELECT COUNT(*) n FROM images WHERE status='pending'").fetchone()["n"],
        }
        snap["sources"] = [dict(r) for r in c(
            "SELECT name, base_url, api_type, status, last_crawled FROM sources ORDER BY name").fetchall()]
        snap["log"] = [dict(r) for r in c(
            "SELECT ts, source, action, ref, http_status, n_records, status, notes "
            "FROM crawl_log ORDER BY id DESC LIMIT 60").fetchall()]
    finally:
        conn.close()
    return snap


def _parse_ts(s):
    """Lenient ISO-8601 parse -> aware datetime (UTC), or None."""
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _ledger_tail(path, n):
    """Return the last n parsed JSON records from a JSONL ledger (newest last).
    Reads only the tail so a large training-log ledger stays cheap to poll."""
    try:
        if not path.is_file():
            return []
        size = path.stat().st_size
        with path.open("rb") as f:
            # read at most the last ~256 KB — plenty for a few dozen short lines
            back = min(size, 262144)
            f.seek(size - back)
            chunk = f.read().decode("utf-8", "replace")
        lines = chunk.splitlines()
        if back < size and lines:
            lines = lines[1:]            # drop a possibly-truncated first line
        out = []
        for ln in lines[-n:]:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
        return out
    except Exception:
        return []


def activity_snapshot():
    """A live pulse of the whole automation: the crawler's crawl_log merged with
    every other bot's heartbeat ledger into one feed, plus corpus counters with
    24h/1h deltas and a per-actor 'is it alive right now' roll-up. Cheap enough
    to poll every few seconds; degrades gracefully when a column/table is absent."""
    now = datetime.now(timezone.utc)
    snap = {"now": now.isoformat(timespec="seconds"),
            "liveWindow": ACTIVITY_LIVE_WINDOW,
            "dbPresent": db_present(), "ledger": ACTIVITY_LEDGER.name,
            "events": [], "actors": [], "counts": {}, "deltas": {}}
    events = []

    if db_present():
        conn = connect()
        try:
            c = conn.execute
            for r in c("SELECT ts, source, action, ref, http_status, n_records, "
                       "status, notes FROM crawl_log ORDER BY id DESC "
                       "LIMIT 50").fetchall():
                events.append({
                    "ts": r["ts"], "actor": r["source"] or "crawler",
                    "action": r["action"] or "", "n": r["n_records"],
                    "status": r["status"] or "ok", "kind": "crawl",
                    "detail": (r["notes"] or r["ref"] or "")})
            snap["counts"] = {
                "manuscripts": c("SELECT COUNT(*) n FROM manuscripts").fetchone()["n"],
                "items": c("SELECT COUNT(*) n FROM items").fetchone()["n"],
                "images": c("SELECT COUNT(*) n FROM images "
                            "WHERE status='downloaded'").fetchone()["n"],
                "pages": c("SELECT COUNT(*) n FROM pages").fetchone()["n"],
            }
            try:
                snap["counts"]["archived"] = c(
                    "SELECT COUNT(*) n FROM items "
                    "WHERE archive_url IS NOT NULL AND archive_url<>''").fetchone()["n"]
            except sqlite3.OperationalError:
                pass
            try:
                snap["counts"]["findings"] = c(
                    "SELECT COUNT(*) n FROM articles "
                    "WHERE status='published'").fetchone()["n"]
            except sqlite3.OperationalError:
                pass

            def _since(sql, hours):
                cut = (now - timedelta(hours=hours)).isoformat()
                try:
                    return c(sql, (cut,)).fetchone()["n"]
                except sqlite3.OperationalError:
                    return None
            snap["deltas"] = {
                "manuscripts24h": _since("SELECT COUNT(*) n FROM manuscripts WHERE first_seen>=?", 24),
                "items24h": _since("SELECT COUNT(*) n FROM items WHERE first_seen>=?", 24),
                "images24h": _since("SELECT COUNT(*) n FROM images WHERE downloaded_at>=?", 24),
                "images1h": _since("SELECT COUNT(*) n FROM images WHERE downloaded_at>=?", 1),
                "pages24h": _since("SELECT COUNT(*) n FROM pages WHERE digested_at>=?", 24),
            }
        finally:
            conn.close()

    for e in _ledger_tail(ACTIVITY_LEDGER, 50):
        events.append({
            "ts": e.get("ts"), "actor": e.get("actor", "bot"),
            "action": e.get("action", ""), "detail": e.get("detail", ""),
            "n": e.get("n"), "status": e.get("status", "ok"),
            "ref": e.get("ref"), "kind": e.get("kind", "bot")})

    events = [e for e in events if e.get("ts")]
    events.sort(key=lambda e: e["ts"], reverse=True)
    snap["events"] = events[:60]

    actors = {}
    for e in events:
        t = _parse_ts(e["ts"])
        if not t:
            continue
        a = e["actor"]
        prev = actors.get(a)
        if not prev or t > prev["_t"]:
            age = (now - t).total_seconds()
            actors[a] = {"actor": a, "lastTs": e["ts"], "lastAction": e["action"],
                         "kind": e.get("kind"), "ageSeconds": int(age),
                         "live": age <= ACTIVITY_LIVE_WINDOW, "_t": t}
    alist = sorted(actors.values(), key=lambda x: x["_t"], reverse=True)
    for a in alist:
        a.pop("_t", None)
    snap["actors"] = alist
    snap["live"] = sum(1 for a in alist if a["live"])

    # The full scheduled roster, so idle-between-runs reads as healthy, not dead.
    live_names = {a["actor"] for a in alist if a["live"]}
    snap["schedule"] = _schedule_snapshot(now, live_names)

    # The forever.sh crawl loop (scheduler.py's successor): cycle, step, next rest.
    snap["pipeline"] = _pipeline_snapshot(now)

    # Only one of them is the runner. scheduler.py was retired 2026-07-22 but its
    # jobs.json lingers on disk; when the pipeline has fresher evidence than every
    # scheduled job's last run, the roster is a relic — leave it out rather than
    # show a page of "enabled" jobs nothing runs. If the scheduler ever runs
    # again, its newer state timestamps bring the roster straight back.
    if snap["pipeline"].get("present") and snap["schedule"]:
        pipe_t = _local_ts(snap["pipeline"].get("updatedAt"))
        sched_t = max((t for t in (_parse_ts(j.get("lastRun"))
                                   for j in snap["schedule"]) if t), default=None)
        if pipe_t and (not sched_t or sched_t < pipe_t):
            snap["schedule"] = []

    # The donuts being made: the newest rows to land in the catalogue, each with a
    # link that actually goes somewhere.
    snap["fresh"] = _fresh_snapshot()
    return snap


def _schedule_snapshot(now, live_names):
    """Read the scheduler's job config + last-run state and project each job to
    'when did it last run, when is it due again, is it running right now'."""
    jobs_p = SCHEDULER_DIR / "scheduler.jobs.json"
    state_p = SCHEDULER_DIR / "scheduler.state.json"
    if not jobs_p.is_file():
        return []
    try:
        jobs = json.loads(jobs_p.read_text(encoding="utf-8")).get("jobs", [])
    except Exception:
        return []
    state = {}
    if state_p.is_file():
        try:
            state = json.loads(state_p.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    out = []
    for j in jobs:
        name = j.get("name", "")
        every = j.get("every_min", 240)
        lr = state.get(name)
        last_t = _parse_ts(lr) if lr else None
        age = next_due = None
        if last_t:
            age = int((now - last_t).total_seconds())
            next_due = int((last_t + timedelta(minutes=every) - now).total_seconds())
        elif j.get("enabled"):
            next_due = 0                       # never run yet -> due now
        out.append({
            "name": name, "kind": j.get("kind", "bot"),
            "enabled": bool(j.get("enabled")), "everyMin": every,
            "note": j.get("note", ""), "lastRun": lr, "ageSeconds": age,
            "nextDueSeconds": next_due,
            "running": name in live_names,
        })
    out.sort(key=lambda x: (0 if x["enabled"] else 1,
                            0 if x["running"] else 1,
                            x["nextDueSeconds"] if x["nextDueSeconds"] is not None else 1 << 30))
    return out


def _forever_pid():
    """The forever.sh loop's pid, if its lockfile names a process still running."""
    try:
        pid = int((FOREVER_DIR / ".forever.lock").read_text().strip())
    except (OSError, ValueError):
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    except OSError:
        pass  # exists but not ours to signal — still alive
    return pid


def _local_ts(s):
    """Timestamp from forever.sh territory -> aware datetime. Accepts the log's
    naive-local '2026-08-04 11:08:31' and the state file's ISO-with-offset."""
    if not s:
        return None
    try:
        # astimezone() reads a naive value as local time, which is what the log writes
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone()
    except ValueError:
        return None


def _pipeline_from_log(log_p):
    """Reconstruct the loop's position from forever.log's marker lines — the
    fallback for a forever.sh old enough not to write .forever.cycle.json."""
    try:
        with open(log_p, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 131072))
            tail = f.read().decode("utf-8", "replace")
    except OSError:
        return None
    info = {}
    stamp = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] (.*)$")
    for line in tail.splitlines():
        m = stamp.match(line)
        if not m:
            continue
        ts, rest = m.group(1), m.group(2).strip()
        mb = re.match(r"---- cycle (\d+) begin", rest)
        ms = re.match(r"\[(\d+)/(\d+)\] ([^:]+)", rest)
        md = re.match(r"---- cycle (\d+) done .*?resting (\d+)min", rest)
        if mb:
            info = {"cycle": int(mb.group(1)), "status": "working",
                    "cycleStartedAt": ts}
        elif ms:
            info.update(status="working", step=int(ms.group(1)),
                        steps=int(ms.group(2)), stepName=ms.group(3).strip(),
                        stepStartedAt=ts)
        elif md:
            info.update(cycle=int(md.group(1)), status="resting",
                        cycleFinishedAt=ts, restMinutes=int(md.group(2)),
                        step=None, stepName=None)
        elif rest.startswith("==== forever loop stopped"):
            info["status"] = "stopped"
        elif rest.startswith("==== forever loop start"):
            info["status"] = "working"
        else:
            continue
        info["updatedAt"] = ts
    return info or None


def _pipeline_snapshot(now):
    """How the forever.sh crawl loop is doing: which cycle, which of its 8 steps,
    when the cycle began/finished, when the next one is due. Prefers the loop's
    own .forever.cycle.json; falls back to reading forever.log's markers."""
    info, source = None, None
    state_p = FOREVER_DIR / ".forever.cycle.json"
    if state_p.is_file():
        try:
            info = json.loads(state_p.read_text(encoding="utf-8"))
            source = "state"
        except (OSError, ValueError):
            info = None
    if info is None:
        info = _pipeline_from_log(FOREVER_DIR / "forever.log")
        source = "log"
    if not info:
        return {"present": False}

    pid = _forever_pid()
    status = info.get("status") or "stopped"
    if pid is None and status != "stopped":
        status = "stopped"     # lock gone or pid dead outranks any last-written line

    def iso(key):
        t = _local_ts(info.get(key))
        return t.isoformat(timespec="seconds") if t else None

    out = {"present": True, "running": pid is not None, "pid": pid,
           "source": source, "status": status,
           "cycle": info.get("cycle"), "step": info.get("step"),
           "steps": info.get("steps") or 8, "stepName": info.get("stepName"),
           "cycleStartedAt": iso("cycleStartedAt"),
           "cycleFinishedAt": iso("cycleFinishedAt"),
           "stepStartedAt": iso("stepStartedAt"),
           "restMinutes": info.get("restMinutes"),
           "nextCycleAt": iso("nextCycleAt"), "updatedAt": iso("updatedAt")}
    # A resting log entry implies the wake time even before newer forever.sh
    # writes nextCycleAt itself.
    if not out["nextCycleAt"] and status == "resting" and out["restMinutes"]:
        fin = _local_ts(info.get("cycleFinishedAt"))
        if fin:
            out["nextCycleAt"] = (fin + timedelta(minutes=out["restMinutes"]))\
                .isoformat(timespec="seconds")
    nxt = _local_ts(out["nextCycleAt"])
    out["nextCycleSeconds"] = int((nxt - now).total_seconds()) if nxt else None
    upd = _local_ts(out["updatedAt"])
    out["ageSeconds"] = int((now - upd).total_seconds()) if upd else None
    return out


def _fresh_snapshot():
    """The newest manuscripts, market listings, and curiosity findings — the
    literal freshest output of the pipeline, each with a working link."""
    fresh = {"manuscripts": [], "items": [], "findings": []}
    if not db_present():
        return fresh
    conn = connect()
    try:
        c = conn.execute
        for r in c(
            "SELECT id, COALESCE(NULLIF(title_english,''), NULLIF(title_thai,''), "
            "NULLIF(title_translit,''), source_identifier, 'manuscript '||id) AS name, "
            "provenance_province AS prov, first_seen FROM manuscripts "
            "ORDER BY first_seen DESC, id DESC LIMIT 8").fetchall():
            fresh["manuscripts"].append({
                "title": r["name"], "prov": r["prov"], "ts": r["first_seen"],
                "href": f"/m?id={r['id']}"})
        for r in c(
            "SELECT id, COALESCE(NULLIF(title_thai,''), NULLIF(title_english,''), "
            "NULLIF(title_translit,''), 'listing '||id) AS name, price_value, "
            "price_currency, source_url, archive_url, first_seen FROM items "
            "WHERE method='commerce' ORDER BY first_seen DESC, id DESC LIMIT 8").fetchall():
            fresh["items"].append({
                "title": r["name"], "price": r["price_value"],
                "currency": r["price_currency"] or "THB", "ts": r["first_seen"],
                "href": r["source_url"] or r["archive_url"] or "",
                "archive": r["archive_url"] or ""})
        try:
            for r in c(
                "SELECT title, slug, finding_type, confidence, "
                "COALESCE(last_refreshed, first_filed) AS ts FROM articles "
                "WHERE status='published' ORDER BY first_filed DESC LIMIT 8").fetchall():
                fresh["findings"].append({
                    "title": r["title"], "type": r["finding_type"],
                    "confidence": r["confidence"], "ts": r["ts"],
                    "href": f"/findings#{r['slug']}"})
        except sqlite3.OperationalError:
            pass
    finally:
        conn.close()
    return fresh


def overview_snapshot():
    """A front-door dashboard: totals plus every big axis broken down and
    deep-linkable into the filtered browse. Computed in SQL (no full scan)."""
    snap = {"dbPresent": db_present(), "counts": {}, "genres": [], "scripts": [],
            "languages": [], "provinces": [], "temples": [], "sources": [],
            "centuries": [], "priority": 0, "withImages": 0}
    if not db_present():
        return snap
    conn = connect()
    try:
        c = conn.execute
        snap["counts"] = {
            "manuscripts": c("SELECT COUNT(*) n FROM manuscripts").fetchone()["n"],
            "sources": c("SELECT COUNT(*) n FROM sources").fetchone()["n"],
            "images": c("SELECT COUNT(*) n FROM images").fetchone()["n"],
        }
        snap["priority"] = c("SELECT COUNT(*) n FROM manuscripts WHERE priority=1").fetchone()["n"]
        snap["withImages"] = c(
            "SELECT COUNT(DISTINCT manuscript_id) n FROM images").fetchone()["n"]

        def breakdown(col, label_table=None, limit=None):
            sql = (f"SELECT COALESCE(NULLIF({col},''),'') v, COUNT(*) n "
                   f"FROM manuscripts GROUP BY v HAVING v<>'' ORDER BY n DESC")
            if limit:
                sql += f" LIMIT {limit}"
            return [{"value": r["v"], "n": r["n"],
                     "label": prettify(r["v"], label_table) if label_table is not None else r["v"]}
                    for r in c(sql).fetchall()]

        snap["genres"] = breakdown("genre_normalized", GENRE_LABELS)
        for g in snap["genres"]:
            g["note"] = GENRE_NOTES.get(g["value"], "")
            g["priority"] = g["value"] in PRIORITY_GENRES
        snap["scripts"] = breakdown("script", SCRIPT_LABELS)
        snap["languages"] = breakdown("language", limit=12)
        snap["provinces"] = breakdown("provenance_province", limit=12)
        snap["temples"] = breakdown("provenance_temple", limit=15)
        snap["sources"] = [{"value": r["name"], "n": r["n"], "label": r["name"]}
                           for r in c("SELECT s.name, COUNT(*) n FROM manuscripts m "
                                      "JOIN sources s ON s.id=m.source_id "
                                      "GROUP BY s.name ORDER BY n DESC").fetchall()]
        cent = {}
        for r in c("SELECT date_ce_estimate y FROM manuscripts "
                   "WHERE date_ce_estimate IS NOT NULL").fetchall():
            k = century_of(r["y"])
            if k:
                cent[k] = cent.get(k, 0) + 1
        snap["centuries"] = [{"value": k, "n": v, "label": k}
                             for k, v in sorted(cent.items(),
                                                key=lambda kv: _century_num(kv[0]))]
        # "Ways in" — the named subjects at the heart of the tradition, each a door
        # into its article. Meaning-first: a human meets lersi, yantra, holasat by
        # name and hook, not a genre bucket. Ordered by the registry's own weight.
        doors = []
        for key, label, _weight, _variants in ENTITIES:
            pred = subject_predicate("entity", key)
            if not pred:
                continue
            where, params = pred[0], pred[1]
            n = c(f"SELECT COUNT(*) n FROM manuscripts WHERE {where}", params).fetchone()["n"]
            doors.append({"key": key, "label": label, "href": "/a?s=entity:" + key,
                          "hook": ENTITY_HOOKS.get(key, ""), "n": n,
                          "hasArticle": load_content("entity", key)["exists"]})
        snap["waysIn"] = doors
    finally:
        conn.close()
    return snap


def _century_num(label):
    try:
        return int("".join(ch for ch in label if ch.isdigit()))
    except ValueError:
        return 0


def dashboard_snapshot():
    """Cross-tabulated views for the dashboard: a per-genre digitization
    coverage strip plus a set of two-axis heatmaps (genre×province,
    genre×century, genre×script, province×century). Every cell carries the
    facet values needed to deep-link into the combined browse filter. Computed
    read-only; genre buckets fall back to 'other'."""
    snap = {"dbPresent": db_present(), "coverage": [], "totals": {}, "heatmaps": []}
    if not db_present():
        return snap
    conn = connect()
    try:
        c = conn.execute
        genlabel = lambda g: prettify(g, GENRE_LABELS)

        total = c("SELECT COUNT(*) n FROM manuscripts").fetchone()["n"]
        digitized = c("SELECT COUNT(DISTINCT manuscript_id) n FROM images "
                      "WHERE status='downloaded'").fetchone()["n"]
        priority = c("SELECT COUNT(*) n FROM manuscripts WHERE priority=1").fetchone()["n"]
        snap["totals"] = {"manuscripts": total, "digitized": digitized,
                          "priority": priority}

        cov = c("""
            SELECT COALESCE(NULLIF(m.genre_normalized,''),'other') g, COUNT(*) n,
                   SUM(m.priority) prio,
                   SUM(CASE WHEN EXISTS(SELECT 1 FROM images i
                        WHERE i.manuscript_id=m.id AND i.status='downloaded')
                        THEN 1 ELSE 0 END) dig
            FROM manuscripts m GROUP BY g ORDER BY n DESC""").fetchall()
        snap["coverage"] = [{"value": r["g"], "label": genlabel(r["g"]), "n": r["n"],
                             "prio": r["prio"] or 0, "digitized": r["dig"] or 0,
                             "priority": r["g"] in PRIORITY_GENRES} for r in cov]

        # An axis = one facet the corpus can be sliced by. Each carries the SQL
        # column, a bucket fn (raw value -> label or None to drop), a display
        # label fn, an ordering over the {value:total} map, an optional cap, and
        # the browse facet key so cells can deep-link into the combined filter.
        strip = lambda v: (v or "").strip() or None
        by_count = lambda tot: sorted(tot, key=lambda b: -tot[b])
        by_century = lambda tot: sorted(tot, key=_century_num)

        def axis(key, expr, bucket, label, order, cap=None, prio=None):
            return {"key": key, "expr": expr, "bucket": bucket, "label": label,
                    "order": order, "cap": cap, "prio": prio or (lambda v: False)}

        GENRE = axis("genre", "COALESCE(NULLIF(genre_normalized,''),'other')",
                     lambda v: v or "other", genlabel, by_count,
                     prio=lambda v: v in PRIORITY_GENRES)
        PROVINCE = axis("province", "provenance_province", strip,
                        lambda v: v, by_count, cap=8)
        CENTURY = axis("century", "date_ce_estimate",
                       lambda v: century_of(v) or None, lambda v: v, by_century)
        SCRIPT = axis("script", "script", strip,
                      lambda v: prettify(v, SCRIPT_LABELS), by_count, cap=8)

        def matrix(title, lead, rax, cax):
            counts, rtot, ctot = {}, {}, {}
            for r in c(f"SELECT {rax['expr']} rv, {cax['expr']} cv "
                       "FROM manuscripts").fetchall():
                rb, cb = rax["bucket"](r["rv"]), cax["bucket"](r["cv"])
                if not rb or not cb:
                    continue
                counts[(rb, cb)] = counts.get((rb, cb), 0) + 1
                rtot[rb] = rtot.get(rb, 0) + 1
                ctot[cb] = ctot.get(cb, 0) + 1
            rkeys = rax["order"](rtot)[:rax["cap"]] if rax["cap"] else rax["order"](rtot)
            ckeys = cax["order"](ctot)[:cax["cap"]] if cax["cap"] else cax["order"](ctot)
            keepc = set(ckeys)
            cells = {}
            for rk in rkeys:
                row = {ck: counts[(rk, ck)] for ck in ckeys if (rk, ck) in counts}
                if row:
                    cells[rk] = row
            mx = max((counts[(rk, ck)] for rk in cells for ck in cells[rk]),
                     default=0)
            return {"title": title, "lead": lead,
                    "rowkey": rax["key"], "colkey": cax["key"],
                    "rows": [{"value": rk, "label": rax["label"](rk),
                              "total": rtot[rk], "priority": rax["prio"](rk)}
                             for rk in rkeys if rk in cells],
                    "cols": [{"value": ck, "label": cax["label"](ck),
                              "total": ctot[ck]} for ck in ckeys],
                    "cells": cells, "max": mx}

        snap["heatmaps"] = [
            matrix("Genre × Province",
                   "Where each kind of knowledge physically survives. Darker = "
                   "more manuscripts of that genre held in that province. Click "
                   "any cell to browse exactly those.", GENRE, PROVINCE),
            matrix("Genre × Century",
                   "When each kind of text was copied (by estimated century CE). "
                   "Only the ~63% of witnesses carrying a date estimate appear "
                   "here.", GENRE, CENTURY),
            matrix("Genre × Script",
                   "Which scriptorial tradition each genre is written in — Tham "
                   "Lanna dominates, but Tham Lao, Shan and others carry their "
                   "own share.", GENRE, SCRIPT),
            matrix("Province × Century",
                   "The geography of copying over time: how each province's "
                   "surviving output is distributed across the centuries.",
                   PROVINCE, CENTURY),
        ]

        # timeline — the whole corpus' dated output per century, with the
        # research-priority (wichaa) share called out.
        tl = {}
        for r in c("SELECT date_ce_estimate y, priority p FROM manuscripts "
                   "WHERE date_ce_estimate IS NOT NULL").fetchall():
            k = century_of(r["y"])
            if not k:
                continue
            b = tl.setdefault(k, {"n": 0, "prio": 0})
            b["n"] += 1
            b["prio"] += 1 if r["p"] else 0
        snap["timeline"] = [{"value": k, "label": k, "n": v["n"], "prio": v["prio"]}
                            for k, v in sorted(tl.items(), key=lambda kv: _century_num(kv[0]))]
    finally:
        conn.close()
    return snap


# Approximate centroids (lat, lon) for the provinces that appear in the
# provenance data — enough to plot a schematic map of the Lanna heartland.
# Anything not listed here is surfaced as an "unplaced" place index instead.
PROVINCE_COORDS = {
    "Chiang Mai": (18.79, 98.98), "Chiang Rai": (19.91, 99.83),
    "Lamphun": (18.58, 99.01), "Lampang": (18.29, 99.49),
    "Phrae": (18.14, 100.14), "Nan": (18.78, 100.77),
    "Phayao": (19.17, 99.90), "Mae Hong Son": (19.30, 97.97),
    "Uttaradit": (17.62, 100.10), "Tak": (16.87, 99.13),
    "Sukhothai": (17.01, 99.82), "Bangkok": (13.75, 100.50),
}


def places_snapshot():
    """Geographic view: manuscript counts per province, projected onto a simple
    lat/lon canvas for a dot-map. Provinces we have no centroid for (districts,
    temple-level strings) fall through to an 'unplaced' list so nothing is
    silently dropped. Read-only; every place deep-links into browse."""
    snap = {"dbPresent": db_present(), "places": [], "unplaced": [],
            "bbox": {}, "max": 0, "total": 0}
    if not db_present():
        return snap
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT provenance_province p, COUNT(*) n FROM manuscripts "
            "WHERE provenance_province<>'' AND provenance_province IS NOT NULL "
            "GROUP BY p ORDER BY n DESC").fetchall()
    finally:
        conn.close()
    placed, unplaced = [], []
    for r in rows:
        name = (r["p"] or "").strip()
        if name in PROVINCE_COORDS:
            lat, lon = PROVINCE_COORDS[name]
            placed.append({"name": name, "value": name, "label": name, "n": r["n"],
                           "lat": lat, "lon": lon})
        else:
            unplaced.append({"name": name, "value": name, "n": r["n"]})
    # projection box: the northern heartland, dropping the Bangkok outlier from
    # the frame extents so the north isn't squashed (it still gets plotted/clamped)
    north = [p for p in placed if p["lat"] >= 16.0]
    lats = [p["lat"] for p in north] or [17, 20]
    lons = [p["lon"] for p in north] or [98, 101]
    latmin, latmax = min(lats) - 0.4, max(lats) + 0.4
    lonmin, lonmax = min(lons) - 0.4, max(lons) + 0.4
    W, H = 1000.0, 820.0
    for p in placed:
        fx = (p["lon"] - lonmin) / (lonmax - lonmin) if lonmax > lonmin else 0.5
        fy = (latmax - p["lat"]) / (latmax - latmin) if latmax > latmin else 0.5
        p["x"] = round(min(1.0, max(0.0, fx)) * W, 1)
        p["y"] = round(min(1.0, max(0.0, fy)) * H, 1)
    snap["places"] = placed
    snap["unplaced"] = unplaced
    snap["bbox"] = {"latmin": latmin, "latmax": latmax,
                    "lonmin": lonmin, "lonmax": lonmax, "w": W, "h": H}
    snap["max"] = max((p["n"] for p in placed), default=0)
    snap["total"] = sum(p["n"] for p in placed) + sum(u["n"] for u in unplaced)
    return snap


# ---------------------------- article layer ----------------------------
# An "article" is a synthesized page about one facet value (a genre, a place, a
# script…). Its FACTS are recomputed live from the catalog every request, so they
# never go stale as the corpus grows; its PROSE is authored markdown in content/,
# preserved across re-crawls. articles.py is the automation tool that reports
# coverage and drafts stubs. Priority order = the wichaa research core first.
# A temple names itself. The provenance_temple column also carries districts
# ("Mueang District"), provinces ("Phrae") and institutional holders (Siam
# Society, Nan Provincial Museum) — real holders, but not temples, and the
# temple directory must not claim they are.
_IS_TEMPLE_NAME = re.compile(r"^\s*(wat|วัด)\b", re.IGNORECASE)

SUBJECT = {
    "genre":    {"col": "genre_normalized",   "labels": GENRE_LABELS,   "noun": "genre"},
    "province": {"col": "provenance_province", "labels": None,           "noun": "province"},
    "temple":   {"col": "provenance_temple",   "labels": None,           "noun": "temple"},
    "script":   {"col": "script",              "labels": SCRIPT_LABELS,  "noun": "script"},
    "language": {"col": "language",            "labels": None,           "noun": "language"},
    "material": {"col": "material",            "labels": MATERIAL_LABELS, "noun": "material"},
}
# Which other axes a subject's profile reports (its own axis is dropped as trivial).
_PROFILE_AXES = [
    ("provinces", "provenance_province", None),
    ("temples", "provenance_temple", None),
    ("scripts", "script", SCRIPT_LABELS),
    ("languages", "language", None),
    ("materials", "material", MATERIAL_LABELS),
]

# Named-entity subjects (L3): a curated wishlist of the tradition's load-bearing
# figures and text-types. Each is (key, label, weight, [title substrings]); the
# match is a heuristic LIKE across the title, so this doubles as the alias table
# that keeps transliteration variants (Holasat/Holsat/Horasat) from fragmenting.
# weight = curated thematic importance, read by the scorer in articles.py. The
# wichaa core (lersi, yantra, katha, phrommachat, naga) is boosted. An entity
# with zero current matches is not noise — it is a known part of the tradition we
# have yet to collect, and therefore a prime crawl target.
ENTITIES = [
    ("lersi",       "Lersi / Ruesi (ascetic-seers)",    3.0, ["lersi", "ruesi", "reusi", "rusi", "rue si"]),
    # "phommacat" is the northern romanisation (ดูพรหมชาท, ms 5040); without it this
    # entity scored ZERO and its article said the collection held none. Do NOT widen
    # this to the Thai string พรหมชา — that also matches พรหมชาลสูตร, the Brahmajāla
    # Sutta, which is a different text entirely and would add eight false witnesses.
    # The romanisations separate cleanly where the Thai does not: phommacat vs
    # phommacala.
    ("phrommachat", "Phrommachat (12-year almanac)",     3.0, ["phrommachat", "phromchat", "phrom chat", "phommacat", "phommachat"]),
    ("katha",       "Katha (Pali spell-formulae)",       2.8, ["katha", "gatha"]),
    ("yantra",      "Yantra / Yan (nyan)",               2.8, ["nyan lae", "lae nyan", "long nyan", "nyan tang", "nyan pha", "nyan tian", "nyan nam", "nyan katha", "(nyan", "tamla nyan", "yantra", "yantr"]),
    # "nak khao kham" is ms 3243 (นาคเขาคำ), a real naga title the compound-name
    # aliases above all miss. Kept as the full three-word phrase on purpose: a bare
    # "nak" alias would match นาค as an ordinand, นคร, and every Nakhon place-name.
    ("naga",        "Naga (sacred serpent)",             2.6, ["mahanak", "punnanak", "supunnanak", "nakawimana", "phaya nak", "phya nak", "naga raja", "nak khao kham"]),
    ("holasat",     "Horā almanac (Holasat)",            2.6, ["holasat", "holsat", "horasat"]),
    ("kai",         "Kai (chicken & rooster)",           2.0, ["kai noi", "kai ka", "ka noi", "kai thuean", "phaya kai", "ไก่"]),
    # The horse scores near-zero and that is the finding, not a bug — see the note at
    # the head of this table. Aliases are deliberately narrow: a bare "ma" would match
    # every Thai syllable in the catalogue, and the Thai "ม้า" alone pulls in ม้าง
    # (Lampang Vinaya, ms 5078), an unrelated syllable. Only compound horse-words and
    # the Indic stems are safe. Two aliases were tried and REMOVED after testing:
    # bare "assa" matches vassa / buddhassa / ekādassa / madhurassa (8 false hits,
    # zero real), and "ma sang" for สะง้า matches Nāma saṅgaha and Abhidhamma
    # saṅkhep (7 false hits, zero real). Use the full compounds instead.
    ("ma",          "Ma (horse) — and the zebra",        1.8, ["ma si mok", "ma nin", "assaratana", "assalayana", "ajaniya", "achanai", "sindhop", "kanthaka", "valahassa", "valahaka", "walahok", "ม้าสีหมอก", "ม้าเสพนาง", "ม้าขี่", "ม้าทรง", "ม้าลาย", "อาชาไนย", "วลาหก", "กัณฐกะ", "สะง้า"]),
    ("patiloma",    "Paṭiloma (reversal & mirror katha)", 2.2, ["ถอยหลัง", "ปฏิโลม", "อนุโลม", "อิติปิโส", "itipiso"]),
    ("khun_phaen",  "Khun Phaen (epic hero & amulet)",   2.0, ["khun phaen", "khun paen", "khunpaen", "ขุนแผน", "พระขุนแผน", "ขุนช้าง", "khun chang", "พลายแก้ว", "phlai kaeo", "พลายกุมาร", "plai kuman"]),
    ("suep_cata",   "Suep Cata (life-extension rite)",   2.6, ["suep cata", "suep chata", "sup cata", "sueb cata", "sup chata"]),
    ("sut_thon",    "Thon (protective / funerary rite)", 2.2, ["sut thon", "sutthon", "suat thon", "thon tai", "thon phi", "thon khon tai", "thon huean", "thon ban"]),
    ("su_khwan",    "Su Khwan (soul-calling)",           1.8, ["su khwan", "sukhwan", "su khuan", "hiak khwan", "khwan khao", "ao khwan"]),
    # "mahasamanya" catches the two Wat Sung Men copies romanised Mahasamanya rather
    # than Mahasamainya (ids 1015, 1093) — same text, different transcriber. Do not
    # shorten it to "mahasaman": that also matches Mahāsamanta Paṭṭhāna (ids 860,
    # 1159), an Abhidhamma text with no connection to this sutta.
    ("mahasamai",   "Mahāsamaya Sutta",                  1.6, ["mahasamai", "maha samai", "mahasamanya"]),
    ("vessantara",  "Vessantara / Mahāchat",             1.6, ["wetsantara", "wetsantala", "wetsandon", "mahachat", "maha chat"]),
    ("mangrai",     "King Mangrai (founder of Lanna)",   1.6, ["mangrai", "manglai", "menglai", "mengrai", "มังราย", "เม็งราย"]),
    ("mangraisat",  "Mangraisat (Mangrai code)",         1.5, ["mangrai", "manglai", "menglai"]),
    ("lokaniti",    "Lokanīti",                          1.4, ["lokaniti", "lokniti"]),
    ("thammasat",   "Thammasat (dhammasattha)",          1.3, ["thammasat", "dhammasat"]),
]
_ENTITY_BY_KEY = {e[0]: e for e in ENTITIES}
_ENTITY_TITLE = "LOWER(COALESCE(title_english, title_translit, title_thai, ''))"

# Meaning-first one-liners for the front-door "ways in": what each subject IS, said
# plainly and invitingly — a human's door into the tradition, not a facet count.
# Concrete, true, no fluff (see feedback_moat_prose / feedback_article_sourcing).
ENTITY_HOOKS = {
    "lersi":       "The ascetic seer-sages who keep the wichaa — teachers of yantra and spell.",
    "phrommachat": "The twelve-year almanac: birth-animal, fortune, and the making of a match.",
    "katha":       "Pali spell-formulae — the words of power, chanted and inscribed.",
    "yantra":      "Sacred diagrams (yan) — the drawn magic, inked on cloth, skin, and metal.",
    "naga":        "The sacred serpent, guardian of water, treasure, and the world below.",
    "holasat":     "The horā almanac — how a diviner reads time, fate, and the lucky day.",
    "kai":         "The chicken — dawn-crier, offering-bird, the king's fighting cock, and the chick-stars of the Pleiades.",
    "ma":          "The horse — what the spirit rides, what the caravan loaded, and the seventh year of the Lanna cycle.",
    "patiloma":    "Reversal as technique — katha recited backward, and texts and yantra grids built to read the same when they are.",
    "khun_phaen":  "The seducer-soldier of the Ayutthaya epic, pressed into an amulet — a Buddha's form outside, kuman material within.",
    "suep_cata":   "The rite that lengthens a threatened life when the stars turn against it.",
    "sut_thon":    "Protective and funerary chant, spoken over the house and the dead.",
    "su_khwan":    "Soul-calling — binding the wandering khwan back into the body.",
    "mahasamai":   "The Great Assembly: the gods gathered to hear the Buddha teach.",
    "vessantara":  "The Great Birth (Mahāchat) — the most-told, most-merit jataka of all.",
    "mangrai":     "The founder-king himself — Chiang Rai, Chiang Mai, and the law and lineage that carry his name.",
    "mangraisat":  "The Mangrai code, the old law of the Lanna kingdom.",
    "lokaniti":    "Worldly wisdom — maxims for conduct, rule, and getting on in life.",
    "thammasat":   "The dhammasattha, root treatise beneath traditional law.",
}


def entities_in_text(text):
    """The wichaa subjects a manuscript's title names — each a door from this single
    manuscript up to the article about the whole subject. Threads the meaning-layer
    (the ENTITIES) onto every record that carries it, so a human reading one folio can
    step out to 'what IS holasat?' in one click."""
    if not text:
        return []
    low = str(text).lower()
    out = []
    for key, label, _w, variants in ENTITIES:
        if any(v in low for v in variants):
            out.append({"key": key, "label": label, "href": "/a?s=entity:" + key})
    return out


def subject_slug(value):
    """Deterministic filename slug for a subject value (shared with articles.py)."""
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_") or "untitled"


def content_path(stype, value):
    return CONTENT / f"{stype}-{subject_slug(value)}.md"


# The unification: a NODE is one identity (axis:value) seen three ways — a browse
# facet, an article, and a place findings attach. The facet already exists; these two
# functions make the SAME node resolvable as an article. The article machinery all
# flows through subject_predicate, so teaching it the normalized axes is the whole job.

# axis -> the browse facet key that filters on the same node (so an article's
# "Browse all" CTA lands on the identical set the article describes).
NODE_BROWSE_KEY = {
    "genre": "genre", "subgenre": "subgenre", "script": "script",
    "scriptFamily": "scriptFamily", "language": "languages", "languages": "languages",
    "material": "material", "materialFamily": "materialFamily", "province": "province",
    "temple": "temple", "era": "era",
}

_REVERSE_IDX = {"sig": None, "language": {}, "province": {}}


def _reverse_index(conn):
    """{axis: {node_value: [raw column values]}} for the data-driven axes, so a node
    article selects EXACTLY the raw rows its facet counts. Cached by manuscript count."""
    sig = conn.execute("SELECT COUNT(*) c FROM manuscripts").fetchone()["c"]
    if _REVERSE_IDX["sig"] == sig:
        return _REVERSE_IDX
    lang, prov = {}, {}
    for r in conn.execute("SELECT DISTINCT language FROM manuscripts "
                          "WHERE language<>'' AND language IS NOT NULL"):
        for comp in taxonomy.language_components(r["language"]):
            lang.setdefault(comp, set()).add(r["language"])
    for r in conn.execute("SELECT DISTINCT provenance_province p FROM manuscripts "
                          "WHERE provenance_province<>'' AND provenance_province IS NOT NULL"):
        canon = taxonomy.resolve_province(r["p"])
        if canon:
            prov.setdefault(canon, set()).add(r["p"])
    _REVERSE_IDX.update(sig=sig,
                        language={k: sorted(v) for k, v in lang.items()},
                        province={k: sorted(v) for k, v in prov.items()})
    return _REVERSE_IDX


def node_predicate(conn, axis, value):
    """Resolve a NORMALIZED node (the axes taxonomy.py introduced) to the same
    (where, params, drop_col, label, noun) shape subject_predicate returns, so the
    article/profile/lede machinery works on it unchanged. None if not a normalized
    axis or the node is empty."""
    def _in(col, raws, drop, label, noun):
        if not raws:
            return None
        ph = ",".join("?" * len(raws))
        return (f"{col} IN ({ph})", tuple(raws), drop, label, noun)

    if axis in ("language", "languages"):
        raws = _reverse_index(conn)["language"].get(value)
        return _in("language", raws, "language",
                   taxonomy.LANGUAGE_LABELS.get(value, value), "language")
    if axis == "province":
        raws = _reverse_index(conn)["province"].get(value)
        if not raws and value in taxonomy.CANONICAL_PROVINCES:
            raws = [value]
        return _in("provenance_province", raws, "provenance_province", value, "province")
    if axis == "scriptFamily":
        return _in("script", taxonomy.SCRIPT_FAMILY_MEMBERS.get(value), "script",
                   taxonomy.SCRIPT_FAMILY_LABELS.get(value, value), "script family")
    if axis == "materialFamily":
        return _in("material", taxonomy.MATERIAL_FAMILY_MEMBERS.get(value),
                   "material", value, "material family")
    if axis == "subgenre" and ":" not in str(value):   # flat genre_raw node (new form)
        return ("genre_raw=?", (value,), "genre_raw", value, "sub-genre")
    if axis == "era" and value in ("CS", "BE"):
        return ("date_text LIKE ?", (f"%{value}%",), None,
                taxonomy.ERA_LABELS.get(value, value), "era")
    return None


def resolve_subject(stype, value, conn=None):
    """Node-aware subject resolution: try the normalized axes first (needs a conn for
    the data-driven ones), then fall back to the legacy subject_predicate."""
    if conn is not None:
        np = node_predicate(conn, stype, value)
        if np:
            return np
    return subject_predicate(stype, value)


def subject_predicate(stype, value):
    """Resolve any subject to (where_sql, params, drop_col, label, noun) so the
    profile machinery can span more than single-column equality:
      · SUBJECT axes (genre/province/…) → `col = ?`
      · subgenre  "genre:raw"           → `genre_normalized=? AND genre_raw=?`
      · entity    "<key>"               → OR-joined title LIKEs from ENTITIES
    drop_col names the axis to omit as trivial from the profile (None = report
    all, right for entities, which cut across every axis). Returns None if
    unknown. Read-only — callers own the connection.
    (Normalized-axis nodes are resolved by node_predicate via resolve_subject.)"""
    if stype in SUBJECT:
        col = SUBJECT[stype]["col"]
        label = prettify(value, SUBJECT[stype]["labels"]) or str(value)
        return f"{col}=?", (value,), col, label, SUBJECT[stype]["noun"]
    if stype == "subgenre":
        g, _, raw = str(value).partition(":")
        label = f"{prettify(g, GENRE_LABELS)} \u203a {raw}"
        return "genre_normalized=? AND genre_raw=?", (g, raw), "genre_normalized", label, "sub-genre"
    if stype == "entity":
        e = _ENTITY_BY_KEY.get(value)
        if e:
            _, label, _w, variants = e
            where = "(" + " OR ".join([f"{_ENTITY_TITLE} LIKE ?"] * len(variants)) + ")"
            return where, tuple(f"%{v}%" for v in variants), None, label, "subject"
    return None


def article_profile(conn, stype, value):
    """Live facts for one subject value: counts + the leading values on every
    other axis, a date span, and a few sample titles. Works for any subject the
    predicate can resolve (axis, sub-genre, or named entity). Read-only."""
    pred = resolve_subject(stype, value, conn)
    if not pred:
        return None
    where, params, drop_col, _label, _noun = pred
    one = lambda sql: conn.execute(sql, params).fetchone()
    count = one(f"SELECT COUNT(*) n FROM manuscripts WHERE {where}")["n"]
    prof = {"count": count,
            "priority": one(f"SELECT COUNT(*) n FROM manuscripts WHERE {where} AND priority=1")["n"]}
    for name, other_col, labels in _PROFILE_AXES:
        if other_col == drop_col:
            continue
        rows = conn.execute(
            f"SELECT COALESCE(NULLIF(TRIM({other_col}),''),'') v, COUNT(*) n "
            f"FROM manuscripts WHERE {where} GROUP BY v HAVING v<>'' ORDER BY n DESC LIMIT 6",
            params).fetchall()
        prof[name] = [{"value": r["v"], "n": r["n"],
                       "label": prettify(r["v"], labels) if labels is not None else r["v"]}
                      for r in rows]
    d = one(f"SELECT MIN(date_ce_estimate) mn, MAX(date_ce_estimate) mx, "
            f"COUNT(date_ce_estimate) k FROM manuscripts WHERE {where} AND date_ce_estimate IS NOT NULL")
    prof["date"] = {"min": d["mn"], "max": d["mx"], "dated": d["k"]}
    prof["samples"] = [r["t"][:80] for r in conn.execute(
        f"SELECT COALESCE(NULLIF(title_english,''),NULLIF(title_translit,''),"
        f"NULLIF(title_thai,''),'(untitled)') t FROM manuscripts WHERE {where} "
        f"AND COALESCE(title_english,title_translit,title_thai) IS NOT NULL LIMIT 8",
        params).fetchall()]
    return prof


def _share(part, whole):
    return round(100 * part / whole) if whole else 0


def data_lede(stype, value, label, prof, noun="subject"):
    """A factual opening paragraph synthesized from the profile — pattern
    recognition, not invention. Regenerated every load so it tracks the data."""
    if not prof or not prof["count"]:
        return ""
    n = prof["count"]
    bits = [f"{label} accounts for {n:,} catalogued manuscript{'s' if n != 1 else ''}"]
    if prof.get("priority"):
        bits[0] += f", {prof['priority']:,} of them flagged research-priority"
    bits[0] += "."
    provs = prof.get("provinces") or []
    if provs and stype != "province":
        lead = provs[0]
        s = _share(lead["n"], n)
        tail = ""
        if len(provs) > 1:
            tail = " and ".join(p["label"] for p in provs[1:3])
            tail = f", ahead of {tail}" if tail else ""
        bits.append(f"It clusters in {lead['label']} ({s}% of the corpus for this {noun}){tail}.")
    scr = prof.get("scripts") or []
    if scr and stype != "script":
        s = _share(scr[0]["n"], n)
        if s >= 60:
            bits.append(f"Nearly all ({s}%) are written in {scr[0]['label']} script.")
    mats = prof.get("materials") or []
    if len(mats) >= 2 and stype != "material":
        top, second = mats[0], mats[1]
        bits.append(f"By support it leans to {top['label'].lower()} ({_share(top['n'], n)}%) "
                    f"over {second['label'].lower()} ({_share(second['n'], n)}%).")
    dt = prof.get("date") or {}
    if dt.get("dated"):
        bits.append(f"Dated witnesses run {dt['min']}–{dt['max']} CE "
                    f"({dt['dated']} of {n:,} carry a date).")
    return " ".join(bits)


# ---------------------------- citation archive ----------------------------
# data/citation_archive.json is written by archive_citations.py — the Wayback
# Availability result and a liveness verdict for every outbound URL the article
# prose cites. Read lazily and re-read when the file changes, so a fresh fetch
# shows up without restarting the server.
CITATION_ARCHIVE_PATH = DATA / "citation_archive.json"
_CITATION_ARCHIVE = {"mtime": None, "urls": {}}


def citation_archive():
    try:
        mt = CITATION_ARCHIVE_PATH.stat().st_mtime
    except OSError:
        _CITATION_ARCHIVE["mtime"], _CITATION_ARCHIVE["urls"] = None, {}
        return _CITATION_ARCHIVE["urls"]
    if _CITATION_ARCHIVE["mtime"] != mt:
        data = load_json(CITATION_ARCHIVE_PATH, {})
        urls = data.get("urls") if isinstance(data, dict) else None
        _CITATION_ARCHIVE["urls"] = urls if isinstance(urls, dict) else {}
        _CITATION_ARCHIVE["mtime"] = mt
    return _CITATION_ARCHIVE["urls"]


def _external_link(text, href):
    """Render one outbound citation with its archive badge. `text` and `href`
    arrive already html-escaped by _md_inline; the archive store is keyed by the
    URL as written in the markdown, hence the unescape for lookup. Quiet rules:
      archived            → the link, plus an "archived <date>" badge to the snapshot
      offline + archived  → the link itself opens the snapshot (a click that
                            cannot land is a click wasted)
      offline, unarchived → named and dated, never hyperlinked
      anything else       → a plain link, exactly as before
    """
    esc = html.escape(href, quote=True)
    ent = citation_archive().get(html.unescape(href))
    if not ent:
        return f'<a href="{esc}">{text}</a>'
    offline = ent.get("live") is False
    if ent.get("archived") and ent.get("snapshot_url"):
        snap = html.escape(ent["snapshot_url"], quote=True)
        date = html.escape(str(ent.get("snapshot_date") or ""))
        main_href = snap if offline else esc
        note = " — original offline; this opens the archive copy" if offline else ""
        return (f'<a href="{main_href}">{text}</a>'
                f'<a class="cite-arch" href="{snap}" '
                f'title="Wayback Machine snapshot{note}">archived {date}</a>')
    if offline:
        checked = html.escape(str(ent.get("live_checked_at") or ent.get("checked_at") or "")[:10])
        return (f'{text} <span class="cite-arch quiet" title="{esc}">'
                f'offline · checked {checked}</span>')
    return f'<a href="{esc}">{text}</a>'


# Which internal link targets an article may point at. This was a hand-written
# regex naming eight paths, and it had drifted: /w/<widget>, /glossary, /na,
# /moon, /need … all existed and were all silently DELETED from articles that
# linked to them (an article's "the [prices widget](/w/prices)" rendered as bare
# text, with nothing anywhere saying so). routes.py is the registry that already
# knows what this site contains, so the allowlist is derived from it and cannot
# drift again — plus the dynamic namespaces routes.py does not enumerate one by
# one, since their members are per-record pages rather than declared routes.
_LINK_DYNAMIC = {
    "place",   # /place/<wat-slug>/       — 1,494 temple pages
    "w",       # /w/<widget>              — the widget pages under /widgets
    "pimg",    # /pimg/<mid>/<n>.png      — a bundled folio image
    "imgthumb",
}


def _link_roots():
    """First path segment of every declared route, e.g. '/glossary/' -> 'glossary'.
    Imported lazily: routes.py is a leaf module, but keeping the import inside the
    function means wiki.py stays importable even if routes.py is being edited."""
    roots = set(_LINK_DYNAMIC)
    try:
        import routes
        for r in routes.ROUTES:
            seg = r.path.strip("/").split("/")[0]
            if seg:
                roots.add(seg)
    except Exception:
        # Never let a link check break a build; fall back to the historical set.
        roots |= {"browse", "a", "m", "status", "articles", "findings", "wats", "hun"}
    return roots


_LINK_ROOTS = None
# Links an article asked for and did not get, as (href, article) — reported by
# build_static so a dead link is loud at build time instead of vanishing into
# plain text. Reset per build; see link_report().
DROPPED_LINKS = []


def _md_inline(s, where=""):
    global _LINK_ROOTS
    if _LINK_ROOTS is None:
        _LINK_ROOTS = _link_roots()
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*(?!\*)", r"<em>\1</em>", s)

    def link(m):
        text, href = m.group(1), m.group(2)
        if href.startswith(("http://", "https://")):
            return _external_link(text, href)
        if href.startswith("/"):
            seg = href.lstrip("/").split("?")[0].split("#")[0].split("/")[0]
            if seg in _LINK_ROOTS:
                return f'<a href="{html.escape(href, quote=True)}">{text}</a>'
        DROPPED_LINKS.append((href, where))
        return text
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, s)


def link_report():
    """Every link dropped since the last reset, deduped. build_static prints this;
    an article that names a page which does not exist should be fixed, not
    silently flattened."""
    seen, out = set(), []
    for href, where in DROPPED_LINKS:
        if (href, where) not in seen:
            seen.add((href, where))
            out.append((href, where))
    return out


def md_to_html(text, where=""):
    """A deliberately tiny, XSS-safe markdown subset: ## / ### headings,
    - bullet lists, **bold**, *italic*, and [text](internal-or-http link).
    `where` names the source article, so a dropped link can be reported against
    the file that has to be fixed."""
    out, para, ul = [], [], []

    def flush_para():
        if para:
            out.append("<p>" + _md_inline(" ".join(para), where) + "</p>")
            para.clear()

    def flush_ul():
        if ul:
            out.append("<ul>" + "".join("<li>" + _md_inline(x, where) + "</li>" for x in ul) + "</ul>")
            ul.clear()

    for ln in text.split("\n"):
        s = ln.strip()
        if s.startswith("<!--") and s.endswith("-->"):
            flush_para(); flush_ul()          # HTML comments (e.g. managed-block markers) never render
        elif not s:
            flush_para(); flush_ul()
        elif s.startswith("### "):
            flush_para(); flush_ul(); out.append("<h3>" + _md_inline(s[4:], where) + "</h3>")
        elif s.startswith("## "):
            flush_para(); flush_ul(); out.append("<h2>" + _md_inline(s[3:], where) + "</h2>")
        elif s.startswith("- "):
            flush_para(); ul.append(s[2:])
        elif ul and ln[:1] in (" ", "\t"):
            ul[-1] = ul[-1] + " " + s
        else:
            flush_ul(); para.append(s)
    flush_para(); flush_ul()
    return "".join(out)


def load_content(stype, value):
    """Read authored prose for a subject, if any. Returns exists/title/status/
    see_also/body_html. Frontmatter is an optional --- key: value --- block."""
    p = content_path(stype, value)
    if not p.is_file():
        return {"exists": False, "status": "stub", "title": "", "see_also": [], "body_html": ""}
    raw = p.read_text(encoding="utf-8")
    meta, body = {}, raw
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            for line in raw[3:end].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip()
            body = raw[end + 4:]
    see = [x.strip() for x in meta.get("see_also", "").split(",") if x.strip()]
    return {"exists": True, "status": meta.get("status", "published"),
            "title": meta.get("title", ""), "see_also": see,
            "body_html": md_to_html(body.strip(), p.name)}


def _node_names(label, value):
    """The strings whose presence in a finding means it's about this node: the value,
    a spaced form, and the leading chunk of the label before any qualifier."""
    cands = set()
    for c in (str(value), str(value).replace("_", " "), str(label)):
        c = re.split(r"[(·›|/]", c)[0].strip()
        if len(c) >= 4:
            cands.add(c.lower())
    return cands


def findings_for_node(conn, label, value):
    """Published curiosity findings that pertain to this node — the same matching the
    scribe used, but computed live so EVERY node (not just the 30 authored articles)
    shows the discoveries about it. Returns [{slug,title,gloss}]."""
    cands = _node_names(label, value)
    if not cands:
        return []
    out = []
    for r in conn.execute(
            "SELECT slug, title, body_md, confidence FROM articles "
            "WHERE status='published' AND finding_key IS NOT NULL AND finding_key<>'' "
            "ORDER BY confidence DESC"):
        hay = ((r["title"] or "") + " \n " + (r["body_md"] or "")).lower()
        if any(c in hay for c in cands):
            body = re.sub(r"\s+", " ", r["body_md"] or "").strip()
            body = re.sub(r"[*_`#>]+", "", body)
            body = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", body)
            m = re.search(r"(.+?[.!?])(\s|$)", body)
            out.append({"slug": r["slug"], "title": r["title"],
                        "gloss": (m.group(1) if m else body)[:220]})
    return out


def build_article(stype, value):
    prof, findings = None, []
    conn = connect() if db_present() else None
    try:
        pred = resolve_subject(stype, value, conn)
        if not pred:
            return None
        _where, _params, _drop, label, noun = pred
        if conn is not None:
            prof = article_profile(conn, stype, value)
            findings = findings_for_node(conn, label, value)
    finally:
        if conn is not None:
            conn.close()
    content = load_content(stype, value)
    # A node is browsable when its facet key is known — including the normalized axes,
    # so every node article can CTA back to the identical facet set (the unification).
    browse_col = NODE_BROWSE_KEY.get(stype, stype if stype in SUBJECT else "")
    return {
        "type": stype, "value": value, "key": f"{stype}:{value}",
        "label": label, "noun": noun,
        "browseCol": browse_col, "note": GENRE_NOTES.get(value, "") if stype == "genre" else "",
        "priority": stype == "genre" and value in PRIORITY_GENRES,
        "profile": prof, "lede": data_lede(stype, value, label, prof, noun),
        # findings computed live and addressed to THIS node — the third face of the
        # node (facet + article + findings), no longer siloed on /findings.
        "findings": findings,
        "authored": content, "dbPresent": db_present(),
        "connections": connections(stype, value),
        "image": article_image(stype, value),
    }


# ---- representative article imagery -------------------------------------------------
# Every article (genre / entity / sub-genre) gets ONE striking image, chosen by a
# fallback chain that lets human curation win yet never leaves a card imageless when
# the collection has anything at all to show. Order, richest signal first:
#   1. a human-starred folio (data/featured.json) that belongs to this subject
#   2. a diagram page among the subject's manuscripts  (the pipeline's strongest cue)
#   3. a vision-described page among them
#   4. the first downloaded raw folio among them
#   5. None  → the card/hero falls back to a typographic monogram.
# Results are memoised per subject and invalidated whenever catalog.db or featured.json
# changes, so the Articles index stays snappy after the first build. Read-only.
_ARTIMG_CACHE = {}
_ARTIMG_STAMP = None


def _img_caption(kind, vd, ocr):
    """One-line human caption for a picked page image."""
    desc = (vd or "").strip()
    text = re.sub(r"\s+", " ", (ocr or "")).strip()
    lead = "Diagram" if kind == "diagram" else ("Described folio" if desc else "Folio")
    tail = (desc[:150] or text[:120]).strip()
    return (lead + " \u2014 " + tail) if tail else lead


def _artimg_compute(conn, stype, value):
    pred = subject_predicate(stype, value)
    if not pred:
        return None
    where, params = pred[0], pred[1]

    # 1. human star belonging to this subject (a page star beats a scan star)
    feat = load_json(FEATURED_PATH, {})
    starred = [k for k, v in feat.items() if isinstance(v, dict) and v.get("starred")]
    if starred:
        for k in starred:
            if not k.startswith("page:"):
                continue
            try:
                _, m, pg = k.split(":"); m, pg = int(m), int(pg)
            except ValueError:
                continue
            r = conn.execute(
                "SELECT p.kind, p.vision_desc vd, p.ocr_text ocr FROM pages p "
                "JOIN manuscripts m ON m.id=p.manuscript_id "
                f"WHERE p.manuscript_id=? AND p.page_no=? AND p.image_path IS NOT NULL AND ({where})",
                [m, pg, *params]).fetchone()
            if r:
                return {"src": "/pimg?mid=%d&n=%d" % (m, pg), "kind": "page",
                        "mid": m, "page": pg, "starred": True,
                        "caption": _img_caption(r["kind"], r["vd"], r["ocr"])}
        scan_shas = [k[5:] for k in starred if k.startswith("scan:")]
        if scan_shas:
            qm = ",".join("?" * len(scan_shas))
            r = conn.execute(
                "SELECT i.manuscript_id mid, i.sha256 sha FROM images i "
                "JOIN manuscripts m ON m.id=i.manuscript_id "
                f"WHERE i.sha256 IN ({qm}) AND i.status='downloaded' AND ({where}) LIMIT 1",
                [*scan_shas, *params]).fetchone()
            if r:
                return {"src": "/img?sha=%s&w=480" % r["sha"], "kind": "scan",
                        "mid": r["mid"], "sha": r["sha"], "starred": True, "caption": ""}

    # 2/3. best signal page among the subject's manuscripts
    r = conn.execute(
        "SELECT p.manuscript_id mid, p.page_no page, p.kind, p.vision_desc vd, p.ocr_text ocr "
        "FROM pages p JOIN manuscripts m ON m.id=p.manuscript_id "
        f"WHERE ({where}) AND p.image_path IS NOT NULL "
        "AND (p.kind='diagram' OR (p.vision_desc IS NOT NULL AND p.vision_desc!='')) "
        "ORDER BY (p.kind='diagram') DESC, "
        "  (p.vision_desc IS NOT NULL AND p.vision_desc!='') DESC, "
        "  p.manuscript_id, p.page_no LIMIT 1", list(params)).fetchone()
    if r:
        return {"src": "/pimg?mid=%d&n=%d" % (r["mid"], r["page"]), "kind": "page",
                "mid": r["mid"], "page": r["page"], "starred": False,
                "caption": _img_caption(r["kind"], r["vd"], r["ocr"])}

    # 4. first downloaded raw folio among the subject's manuscripts
    r = conn.execute(
        "SELECT i.manuscript_id mid, i.sha256 sha FROM images i "
        "JOIN manuscripts m ON m.id=i.manuscript_id "
        f"WHERE ({where}) AND i.status='downloaded' AND i.sha256 IS NOT NULL AND i.sha256!='' "
        "ORDER BY i.manuscript_id, i.id LIMIT 1", list(params)).fetchone()
    if r:
        return {"src": "/img?sha=%s&w=480" % r["sha"], "kind": "scan",
                "mid": r["mid"], "sha": r["sha"], "starred": False, "caption": ""}
    return None


def article_image(stype, value):
    """Memoised representative image for one subject, or None. See the block comment
    above for the fallback chain. Safe before catalog.db exists."""
    global _ARTIMG_STAMP
    if not db_present():
        return None
    def mt(p):
        try:
            return p.stat().st_mtime
        except OSError:
            return 0
    stamp = (mt(CATALOG_DB), mt(FEATURED_PATH))
    if stamp != _ARTIMG_STAMP:
        _ARTIMG_CACHE.clear()
        _ARTIMG_STAMP = stamp
    key = (stype, value)
    if key in _ARTIMG_CACHE:
        return _ARTIMG_CACHE[key]
    conn = connect()
    try:
        img = _artimg_compute(conn, stype, value)
    finally:
        conn.close()
    _ARTIMG_CACHE[key] = img
    return img


# ------------------------------------------------------------------ knowledge graph
# A typed, bidirectional graph laid over the read-only catalog. Two sources feed it,
# kept strictly separate by the project's core discipline:
#   · AUTHORED (durable) — human knowledge that survives every re-crawl:
#       - data/relations.json : explicit typed triples {s, p, o}
#       - each article's frontmatter see_also : folded in as symmetric related_to
#   · MACHINE (rebuildable) — derived fresh from catalog.db, never persisted:
#       - co_occurs_with : entities whose title-match witness-sets overlap
# Every predicate has a named inverse so an edge authored once reads correctly from
# both endpoints (this is what gives every node its backlinks).
RELATIONS = {
    # name:            (inverse,          forward display,     reverse display)
    "teacher_of":      ("student_of",     "teacher of",        "in the lineage of"),
    "invokes":         ("invoked_by",     "invokes",           "invoked by"),
    "part_of":         ("has_part",       "part of",           "includes"),
    "depicted_in":     ("depicts",        "depicted in",       "depicts"),
    "derived_from":    ("source_of",      "derived from",      "source of"),
    "protects_against":("warded_by",      "protects against",  "warded by"),
    "paired_with":     ("paired_with",    "paired with",       "paired with"),
    "same_as":         ("same_as",        "also known as",     "also known as"),
    "related_to":      ("related_to",     "related to",        "related to"),
    "co_occurs_with":  ("co_occurs_with", "co-occurs with",    "co-occurs with"),
}


def node_label(key):
    """Human label for any node key `stype:value` (entity/genre/subgenre/axis)."""
    stype, _, value = str(key).partition(":")
    if stype == "entity":
        e = _ENTITY_BY_KEY.get(value)
        return e[1] if e else value
    if stype == "genre":
        return prettify(value, GENRE_LABELS)
    if stype == "subgenre":
        g, _, raw = value.partition(":")
        return f"{prettify(g, GENRE_LABELS)} \u203a {raw}"
    if stype in SUBJECT:
        return prettify(value, SUBJECT[stype]["labels"]) or value
    return value or key


def _iter_subjects(conn):
    """Every subject that could carry an article: genres, entities, sub-genres.
    Mirrors articles_index()'s enumeration so authored keys stay recoverable."""
    for r in conn.execute(
            "SELECT DISTINCT genre_normalized v FROM manuscripts "
            "WHERE genre_normalized IS NOT NULL AND genre_normalized<>''").fetchall():
        yield ("genre", r["v"])
    for key, *_ in ENTITIES:
        yield ("entity", key)
    for r in conn.execute(
            "SELECT genre_normalized g, genre_raw raw FROM manuscripts "
            "WHERE genre_normalized IS NOT NULL AND genre_normalized<>'' "
            "AND genre_raw IS NOT NULL AND genre_raw<>'' GROUP BY g, raw").fetchall():
        yield ("subgenre", f"{r['g']}:{r['raw']}")


def authored_edges(conn):
    """Durable typed edges: explicit triples from relations.json + every article's
    see_also folded in as symmetric related_to. Yields (s, p, o)."""
    for e in load_json(REL_PATH, []):
        p = e.get("p")
        if p in RELATIONS and e.get("s") and e.get("o"):
            yield (e["s"], p, e["o"])
    for stype, value in _iter_subjects(conn):
        c = load_content(stype, value)
        if c["exists"]:
            src = f"{stype}:{value}"
            for tgt in c["see_also"]:
                if tgt != src:
                    yield (src, "related_to", tgt)


def _cooccurrence(conn, value, limit=6):
    """Machine edge: other entities whose title-match witness-set overlaps this
    entity's. Rebuilt from catalog.db each call — never persisted."""
    e = _ENTITY_BY_KEY.get(value)
    if not e:
        return []
    variants = e[3]
    wa = "(" + " OR ".join([f"{_ENTITY_TITLE} LIKE ?"] * len(variants)) + ")"
    pa = tuple(f"%{v}%" for v in variants)
    out = []
    for key2, _l2, _w2, var2 in ENTITIES:
        if key2 == value:
            continue
        wb = "(" + " OR ".join([f"{_ENTITY_TITLE} LIKE ?"] * len(var2)) + ")"
        n = conn.execute(f"SELECT COUNT(*) c FROM manuscripts WHERE {wa} AND {wb}",
                         pa + tuple(f"%{v}%" for v in var2)).fetchone()["c"]
        if n:
            out.append((f"entity:{key2}", n))
    out.sort(key=lambda x: -x[1])
    return out[:limit]


def connections(stype, value):
    """All graph edges touching one node, from both endpoints (so backlinks appear),
    typed authored edges first, then related_to, then machine co-occurrence. Each row:
    {rel, key, label, authored, weight}. Read-only; safe before catalog.db exists."""
    if not db_present():
        return []
    key = f"{stype}:{value}"
    rows = {}  # (target, display) -> row  (dedup; typed beats related_to)

    def add(display, target, direction, authored, weight=None, rank=0):
        if target == key:
            return
        k = (target, display)
        if k in rows and rows[k]["_rank"] <= rank:
            return
        rows[k] = {"rel": display, "key": target, "label": node_label(target),
                   "authored": authored, "weight": weight, "_rank": rank,
                   "dir": direction}

    conn = connect()
    try:
        for s, p, o in authored_edges(conn):
            rank = 0 if p != "related_to" else 1
            if s == key:
                add(RELATIONS[p][1], o, "out", True, rank=rank)
            if o == key:
                add(RELATIONS[p][2], s, "in", True, rank=rank)
        if stype == "entity":
            for target, n in _cooccurrence(conn, value):
                add(RELATIONS["co_occurs_with"][1], target, "out", False, weight=n, rank=2)
    finally:
        conn.close()
    # A generic "related to" edge is redundant once a stronger typed edge (teacher_of,
    # invokes, …) already links the same two nodes — drop it so the panel isn't noisy.
    typed_targets = {r["key"] for r in rows.values() if r["rel"] != "related to" and r["_rank"] == 0}
    kept = [r for r in rows.values() if not (r["rel"] == "related to" and r["key"] in typed_targets)]
    ordered = sorted(kept, key=lambda r: (r["_rank"], r["rel"], -(r["weight"] or 0)))
    for r in ordered:
        r.pop("_rank", None)
    return ordered


def graph_export():
    """Whole authored graph as nodes + typed links — for a future graph view and
    JSON-LD/RDF export. Machine co-occurrence is per-node only, omitted here."""
    if not db_present():
        return {"nodes": [], "links": [], "predicates": {}}
    conn = connect()
    try:
        nodes, links = {}, []
        for s, p, o in authored_edges(conn):
            for k in (s, o):
                nodes.setdefault(k, {"key": k, "label": node_label(k),
                                     "type": k.partition(":")[0]})
            links.append({"s": s, "p": p, "o": o})
    finally:
        conn.close()
    return {"nodes": list(nodes.values()), "links": links,
            "predicates": {k: {"inverse": v[0], "forward": v[1], "reverse": v[2]}
                           for k, v in RELATIONS.items()}}


# Linked-data export. The authored graph is small and stable, so we serialise it
# whole as JSON-LD and Turtle — letting the corpus' relations travel into any
# RDF-aware tool (SPARQL stores, ontology editors) as first-class triples.
GRAPH_NS = "https://lanna.wiki/ns#"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"


def _node_iri(key):
    stype, _, value = key.partition(":")
    return f"https://lanna.wiki/id/{stype}/{quote(value, safe='')}"


def graph_jsonld():
    g = graph_export()
    ctx = {"label": RDFS_NS + "label"}
    for p in g["predicates"]:
        ctx[p] = {"@id": GRAPH_NS + p, "@type": "@id"}
    nodes = {}
    for n in g["nodes"]:
        nodes[n["key"]] = {"@id": _node_iri(n["key"]),
                           "@type": GRAPH_NS + n["type"].capitalize(),
                           "label": n["label"]}
    for lk in g["links"]:
        s = nodes.get(lk["s"])
        if not s:
            continue
        tgt = _node_iri(lk["o"])
        s.setdefault(lk["p"], [])
        if tgt not in s[lk["p"]]:
            s[lk["p"]].append(tgt)
    return {"@context": ctx, "@graph": list(nodes.values())}


def _ttl_esc(s):
    return (s or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def graph_turtle():
    g = graph_export()
    out = [f"@prefix lw: <{GRAPH_NS}> .",
           f"@prefix rdfs: <{RDFS_NS}> .", ""]
    nodes = {n["key"]: n for n in g["nodes"]}
    edges = {}
    for lk in g["links"]:
        edges.setdefault(lk["s"], []).append((lk["p"], lk["o"]))
    for key, n in nodes.items():
        preds = [f'a lw:{n["type"].capitalize()}',
                 f'rdfs:label "{_ttl_esc(n["label"])}"']
        seen = set()
        for p, o in edges.get(key, []):
            if (p, o) in seen:
                continue
            seen.add((p, o))
            preds.append(f'lw:{p} <{_node_iri(o)}>')
        out.append(f'<{_node_iri(key)}>')
        out.append("    " + " ;\n    ".join(preds) + " .")
        out.append("")
    return "\n".join(out)


# ------------------------------------------------------------------ audience lenses
# Four ways in for four kinds of visitor. Each lens is a curated set of doorways
# (deep-links, with live counts) tuned to one purpose — so the same corpus reads
# differently to a scholar, a practitioner, a newcomer, or a preservationist.
WICHAA_GENRES = ["magic_ritual", "astrology", "divination_omen"]
WICHAA_ENTITIES = ["lersi", "yantra", "katha", "holasat", "phrommachat", "su_khwan"]


def lenses_snapshot():
    snap = {"dbPresent": db_present(), "lenses": []}
    if not db_present():
        return snap
    conn = connect()
    try:
        c = conn.execute
        total = c("SELECT COUNT(*) n FROM manuscripts").fetchone()["n"]
        prio = c("SELECT COUNT(*) n FROM manuscripts WHERE priority=1").fetchone()["n"]
        dig = c("SELECT COUNT(DISTINCT manuscript_id) n FROM images "
                "WHERE status='downloaded'").fetchone()["n"]

        def gcount(g):
            return c("SELECT COUNT(*) n FROM manuscripts WHERE genre_normalized=?",
                     (g,)).fetchone()["n"]
        gc = {g: gcount(g) for g in WICHAA_GENRES}
    finally:
        conn.close()

    def door(label, href, note=""):
        return {"label": label, "href": href, "note": note}

    def art_exists(stype, value):
        return load_content(stype, value)["exists"]

    wich_doors = []
    for g in WICHAA_GENRES:
        if gc.get(g):
            wich_doors.append(door(prettify(g, GENRE_LABELS),
                                   "/a?s=genre:" + g,
                                   f"{gc[g]:,} witnesses · read the article"))
    ent_doors = [door(node_label("entity:" + e), "/a?s=entity:" + e)
                 for e in WICHAA_ENTITIES if art_exists("entity", e)]

    snap["lenses"] = [
        {"key": "learner", "title": "For the newcomer",
         "blurb": "New to Lanna manuscripts? Start with the shape of the whole "
                  "collection and the synthesised articles, which explain each "
                  "kind of text in plain language.",
         "doors": [
             door("The collection at a glance", "/",
                  f"{total:,} manuscripts, every number a doorway"),
             door("All synthesised articles", "/articles",
                  "genres, places and subjects, explained"),
             door("Browse everything", "/browse", "search and filter freely"),
         ]},
        {"key": "scholar", "title": "For the scholar",
         "blurb": "Read the corpus as primary sources — by provenance, script, "
                  "and date — and take the relations away as linked data.",
         "doors": [
             door("Browse by provenance", "/browse",
                  "filter by temple, province, script, and date"),
             door("Dashboard cross-tabs", "/dashboard",
                  "genre × place × century × script"),
             door("Research-priority corpus", "/browse?priority=" +
                  quote("Research priority"), f"{prio:,} witnesses"),
             door("Linked-data graph", "/api/graph.jsonld", "JSON-LD · also Turtle"),
         ]},
        {"key": "practitioner", "title": "For the practitioner",
         "blurb": "The wichaa core — the efficacious and esoteric material. These "
                  "texts were regarded as living, powerful knowledge; approach "
                  "them with the respect and context the tradition asks for.",
         "gated": True,
         "doors": wich_doors + ent_doors},
        {"key": "preservationist", "title": "For the archivist",
         "blurb": "Track coverage: what is catalogued, what is imaged, and "
                  "where the crawl and the Internet-Archive snapshots have "
                  "reached so far.",
         "doors": [
             door("Digitization coverage", "/dashboard",
                  f"{dig:,} of {total:,} witnesses imaged so far"),
             door("Crawl status", "/status", "sources, counts, recent activity"),
             door("Live activity", "/activity",
                  "crawls, curiosity, and archiving in real time"),
         ]},
    ]
    return snap


# ------------------------------------------------------------------ full-text search
# A rebuildable FTS5 mirror the wiki owns (data/search.db), indexing every
# manuscript's titles + provenance + raw_metadata + any OCR, plus each authored
# article's prose. Rebuilt whenever the catalog's signature changes; catalog.db is
# only ever read. This is what lets search reach *inside* content, not just titles.
SEARCH_DB = DATA / "search.db"


def _catalog_signature(cat):
    n = cat.execute("SELECT COUNT(*) c FROM manuscripts").fetchone()["c"]
    mx = cat.execute("SELECT COALESCE(MAX(last_seen),'') m FROM manuscripts").fetchone()["m"]
    imgs = cat.execute("SELECT COUNT(*) c FROM images WHERE sha256 IS NOT NULL").fetchone()["c"]
    ocr = len(load_json(OCR_PATH, {}))
    # the digested `pages` table (OCR + vision descriptions) is the body of the
    # index now; fold its size + freshness in so the index rebuilds when the
    # digest/vision tracks advance, not only when titles change.
    try:
        pg = cat.execute("SELECT COUNT(*) c, COALESCE(MAX(digested_at),'') m FROM pages").fetchone()
        pgc, pgm = pg["c"], pg["m"]
    except sqlite3.OperationalError:
        pgc, pgm = 0, ""
    # translation + blurb progress change index CONTENT without changing any
    # count above (translations update existing pages rows in place) — without
    # these two the index silently served stale labels/bodies as volumes
    # translated (caught 2026-08-05: published search missed 6961's English).
    try:
        trc = cat.execute("SELECT COUNT(*) c FROM pages "
                          "WHERE trans_engine IS NOT NULL").fetchone()["c"]
    except sqlite3.OperationalError:
        trc = 0
    try:
        blb = cat.execute("SELECT COUNT(*) c FROM manuscripts "
                          "WHERE work_title IS NOT NULL").fetchone()["c"]
    except sqlite3.OperationalError:
        blb = 0
    arts = sum(1 for p in CONTENT.glob("*.md"))
    amt = max((p.stat().st_mtime for p in CONTENT.glob("*.md")), default=0)
    return f"{n}:{mx}:{imgs}:{ocr}:{pgc}:{pgm}:{trc}:{blb}:{arts}:{amt:.0f}"


# ---- catalog-signature cache ----------------------------------------------
# Computing the signature runs several COUNT/MAX queries; doing it on every
# request (search does, /api/manuscripts would) is the bulk of the latency the
# gemba flagged. Throttle it: recompute at most once per _SIG_TTL seconds, and
# key the derived in-memory caches (search rows, browse payload) on the result.
_SIG_TTL = 10.0
_SIG_CACHE = {"sig": None, "at": 0.0}
_SIG_LOCK = threading.Lock()


def current_signature():
    """The catalog signature, recomputed at most once per _SIG_TTL. Returns None
    when there is no catalog yet."""
    now = time.monotonic()
    with _SIG_LOCK:
        if _SIG_CACHE["sig"] is not None and now - _SIG_CACHE["at"] < _SIG_TTL:
            return _SIG_CACHE["sig"]
    if not db_present():
        return None
    cat = connect()
    try:
        sig = _catalog_signature(cat)
    finally:
        cat.close()
    with _SIG_LOCK:
        _SIG_CACHE["sig"] = sig
        _SIG_CACHE["at"] = now
    return sig


def _article_text(stype, value):
    """Raw prose of an authored article, frontmatter stripped — for indexing."""
    p = content_path(stype, value)
    if not p.is_file():
        return ""
    raw = p.read_text(encoding="utf-8")
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            raw = raw[end + 4:]
    return re.sub(r"[#*_>`\[\]()\-]", " ", raw)


# --- Thai OCR normalization -------------------------------------------------
# tessdata_best's LSTM decomposes sara-am ำ (U+0E33) into nikhahit ํ (U+0E4D) +
# sara-aa า (U+0E32), sometimes with a tone mark wedged between. The corpus holds
# tens of thousands of the decomposed form and *zero* composed ำ, so any exact
# search for ทำ / น้ำมัน / คำ silently misses unless we recompose first. Same fix
# lives in the crawler's explore.py; kept in lockstep here.
_SA_TONE = "".join(chr(x) for x in range(0x0E48, 0x0E4C))  # ่ ้ ๊ ๋
_SA_NK, _SA_AA, _SA_AM = chr(0x0E4D), chr(0x0E32), chr(0x0E33)
_RE_NKAA = re.compile(_SA_NK + "([" + _SA_TONE + "]?)" + _SA_AA)
_RE_TNKAA = re.compile("([" + _SA_TONE + "])" + _SA_NK + _SA_AA)


def _norm(s):
    """Lowercase + recompose decomposed sara-am. Used on both indexed text and
    queries so Thai substrings match regardless of OCR decomposition."""
    if not s:
        return ""
    s = _RE_NKAA.sub(r"\1" + _SA_AM, s)
    s = _RE_TNKAA.sub(r"\1" + _SA_AM, s)
    return s.lower()


# --- Bilingual thesaurus ----------------------------------------------------
# Each group is a set of cross-language equivalents; typing any one member pulls
# in the rest, so an English/translit query reaches Thai OCR text and a Thai query
# reaches the English articles. Thai members are written composed (ำ), then
# _norm()'d at load, so they line up with the recomposed index. Draws the translit
# spellings from the ENTITIES alias table and adds the Thai script + common
# wichaa vocabulary the corpus actually uses.
_THESAURUS_SEED = [
    ["lersi", "ruesi", "reusi", "rusi", "rue si", "rishi", "ฤๅษี", "ฤาษี", "ฤษี", "พระฤๅษี", "พระฤาษี"],
    ["katha", "gatha", "คาถา", "พระคาถา", "คาถาอาคม"],
    ["yantra", "yant", "yan", "nyan", "lek yant", "lekyant", "ยันต์", "เลขยันต์", "ผ้ายันต์"],
    ["naga", "nak", "phaya nak", "phya nak", "นาค", "พญานาค", "มหานาค"],
    ["kai", "gai", "chicken", "rooster", "junglefowl", "ไก่", "พญาไก่", "ไก่เถื่อน", "ไก่แก้ว", "ไก่ชน", "ดาวลูกไก่"],
    ["ma", "horse", "zebra", "sanga", "ma khi", "ma song", "ม้า", "ม้าลาย", "สะง้า", "มะเมีย",
     "ม้าขี่", "ม้าทรง", "ม้าสีหมอก", "ม้าเสพนาง", "อาชาไนย", "วลาหก", "กัณฐกะ"],
    ["takrut", "tarkrut", "trakut", "ตะกรุด", "ตระกรุด"],
    # เมตตามหานิยม IS the love charm, so the English a reader reaches for
    # belongs in this group and not in one of its own — "love charm" returned
    # nothing while the genre it names filled the corpus.
    ["metta", "loving-kindness", "attraction", "mahaniyom", "เมตตา", "เมตตามหานิยม",
     "love", "love charm", "love magic", "attraction charm", "เสน่ห์", "ยาแฝด"],
    ["kongkraphan", "kong kraphan", "invulnerability", "invulnerable", "endurance",
     "คงกระพัน", "อยู่ยงคงกระพัน", "คงทน"],
    ["prai", "phrai", "พราย", "ผีพราย"],
    ["oil", "namman", "sacred-oil", "น้ำมัน", "น้ำมันพราย", "น้ำมันมนต์"],
    ["holasat", "holsat", "horasat", "horoscope", "almanac", "astrology", "hora",
     "โหราศาสตร์", "โหร", "ดวง"],
    ["amulet", "charm", "sacred-charm", "เครื่องราง", "พระเครื่อง"],
    ["mantra", "montra", "mon", "มนต์", "มนตร์", "พุทธมนต์"],
    ["waan", "waan-ya", "herb", "ว่าน", "ว่านยา"],
    ["sakyant", "sak yant", "tattoo", "สักยันต์"],
    ["waikhru", "wai khru", "ไหว้ครู"],
    ["sukhwan", "su khwan", "soul-calling", "สู่ขวัญ", "ขวัญ"],
    ["phrommachat", "phromchat", "almanac", "พรหมชาติ"],
    ["mangrai", "mengrai", "manglai", "menglai", "มังราย", "เม็งราย", "พญามังราย", "พ่อขุนเม็งราย"],
    ["khun phaen", "khun paen", "khunpaen", "phra khun phaen", "ขุนแผน", "พระขุนแผน"],
    ["plai kuman", "plaikuman", "phlai kuman", "พลายกุมาร"],
    ["buddha", "phutthao", "พระพุทธเจ้า", "พุทธ"],
    ["consecration", "sek", "enchant", "เสก", "ปลุกเสก"],
]
# token -> set of normalized equivalents (built lazily, once)
_THESAURUS = None


def _vocab_groups():
    """Thesaurus groups generated from the amulet vocabularies.

    data/{functions,classes,materials}.json already hold the emic term, its
    English gloss and the key the corpus is tagged with — which is a thesaurus
    group in everything but name. Generating them here means the words a reader
    reaches for ("luck", "trade", "invulnerability") find the Thai the corpus is
    actually tagged in, and that a new vocabulary entry becomes searchable
    without anyone editing a second list.
    """
    out = []
    for fname, key in (("functions.json", "functions"),
                       ("classes.json", "classes"),
                       ("materials.json", "materials")):
        path = HERE / "data" / fname
        if not path.exists():
            continue
        try:
            doc = json.loads(path.read_text())
        except Exception:
            continue
        for item in doc.get(key) or []:
            words = [item.get("term"), item.get("key", "").replace("_", " "),
                     item.get("enGloss")]
            # A gloss is a phrase ("luck and windfall"); keep the phrase AND its
            # content words, so both "luck" and the whole phrase reach the term.
            gloss = item.get("enGloss") or ""
            words += [w for w in re.split(r"[,\s]+", gloss)
                      if len(w) > 3 and w.lower() not in ("and", "with", "from", "that")]
            group = [w for w in words if w]
            if len(group) > 1:
                out.append(group)
    return out


def _thesaurus():
    global _THESAURUS
    if _THESAURUS is None:
        groups = [sorted({_norm(m) for m in g if m})
                  for g in (_THESAURUS_SEED + _vocab_groups())]
        idx = {}
        for g in groups:
            for m in g:
                idx.setdefault(m, set()).update(g)
        _THESAURUS = idx
    return _THESAURUS


def _expand_token(tok):
    """The OR-set of normalized equivalents for one query token: the token itself
    plus every thesaurus group it touches (exact, or substring either way for
    tokens >= 3 chars, so 'ruesi'/'ฤาษี'/'lersi' all reach the same group)."""
    tok = _norm(tok)
    members = {tok}
    if len(tok) < 2:
        return members
    for key, grp in _thesaurus().items():
        if tok == key or (len(tok) >= 3 and (tok in key or key in tok)):
            members.update(grp)
    return members


def build_search_index(force=False):
    """(Re)build data/search.db if the catalog signature moved. Returns the path,
    or None if there is no catalog yet. Read-only against catalog.db.

    Index rows are (ref, kind, label, ntitle, nbody): ntitle/nbody are _norm()'d
    (lowercased, sara-am recomposed) so matching is a plain substring test that
    works for Thai (which unicode61/FTS5 cannot substring) as well as Latin."""
    if not db_present():
        return None
    cat = connect()
    try:
        sig = _catalog_signature(cat)
        sdb = sqlite3.connect(SEARCH_DB)
        try:
            cur = sdb.execute("SELECT v FROM meta WHERE k='sig'").fetchone()
        except sqlite3.OperationalError:
            cur = None
        if cur and cur[0] == sig and not force:
            sdb.close()
            return SEARCH_DB
        # Body per manuscript: the digested `pages` table (OCR + vision
        # descriptions) is the real content now. Legacy image-sha OCR is folded in
        # too so nothing regresses.
        body_by_mid = {}
        # transcription/translation are additive columns the VLM bridge may not
        # have created yet. translation matters most for search: it is the only
        # field an ENGLISH query can match against textbook content.
        page_cols = {row["name"] for row in cat.execute("PRAGMA table_info(pages)")}
        extra = [c for c in ("transcription", "translation") if c in page_cols]
        cols = "manuscript_id mid, ocr_text, vision_desc" + "".join(
            f", {c}" for c in extra)
        try:
            for r in cat.execute(f"SELECT {cols} FROM pages"):
                # a page's transcription is the CLEAN reading of the same text
                # its ocr_text approximates — indexing both doubles the bytes
                # for pure noise, and the noise crowds real content out of the
                # static export's per-doc cap. Prefer transcription, fall back
                # to OCR for pages that have no transcription yet.
                tx = r["transcription"] if "transcription" in extra else None
                fields = [tx or r["ocr_text"], r["vision_desc"]]
                if "translation" in extra:
                    fields.append(r["translation"])
                parts = [p for p in fields if p]
                if parts:
                    body_by_mid.setdefault(r["mid"], []).append(" ".join(parts))
        except sqlite3.OperationalError:
            pass
        ocr = load_json(OCR_PATH, {})
        if ocr:
            for r in cat.execute("SELECT manuscript_id mid, sha256 FROM images "
                                 "WHERE sha256 IS NOT NULL").fetchall():
                rec = ocr.get(r["sha256"])
                txt = rec.get("text", "") if isinstance(rec, dict) else (rec or "")
                if txt:
                    body_by_mid.setdefault(r["mid"], []).append(txt)
        sdb.executescript(
            "DROP TABLE IF EXISTS docs; DROP TABLE IF EXISTS meta;"
            "CREATE TABLE docs(ref TEXT, kind TEXT, label TEXT, ntitle TEXT, nbody TEXT);"
            "CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);")
        ms_cols = {row["name"] for row in cat.execute("PRAGMA table_info(manuscripts)")}
        blurbs = [c for c in ("work_title", "work_desc") if c in ms_cols]
        rows = cat.execute(
            "SELECT id, title_english, title_translit, title_thai, genre_normalized, "
            "genre_raw, provenance_temple, provenance_province, language, script, "
            "raw_metadata" + "".join(f", {c}" for c in blurbs)
            + " FROM manuscripts").fetchall()
        docs = []
        for r in rows:
            wt = r["work_title"] if "work_title" in blurbs else None
            wd = r["work_desc"] if "work_desc" in blurbs else None
            title = " ".join(filter(None, [r["title_english"], r["title_translit"],
                                           r["title_thai"], wt]))
            meta = " ".join(filter(None, [
                r["genre_normalized"], r["genre_raw"], r["provenance_temple"],
                r["provenance_province"], r["language"], r["script"],
                r["raw_metadata"], wd]))
            body = meta + " " + " ".join(body_by_mid.get(r["id"], []))
            # every title variant stays matchable via ntitle; the DISPLAY label
            # prefers the curated bilingual working title when one exists.
            label = wt or " ".join(filter(None, [r["title_english"],
                                                 r["title_translit"], r["title_thai"]]))
            docs.append((str(r["id"]), "m", label or "(untitled)", _norm(title), _norm(body)))
        for stype, value in _iter_subjects(cat):
            c = load_content(stype, value)
            if c["exists"]:
                label = c["title"] or node_label(f"{stype}:{value}")
                docs.append((f"{stype}:{value}", "a", label,
                             _norm(label), _norm(_article_text(stype, value))))
        sdb.executemany("INSERT INTO docs(ref,kind,label,ntitle,nbody) VALUES(?,?,?,?,?)", docs)
        sdb.execute("INSERT OR REPLACE INTO meta VALUES('sig',?)", (sig,))
        sdb.commit()
        sdb.close()
        return SEARCH_DB
    finally:
        cat.close()


def _snippet(text, terms, pos, width=150):
    """A highlighted window of `text` around `pos`, with every matched term wrapped
    in <mark>. Operates on the normalized text (recomposed Thai is more correct,
    not less), so no index-mapping is needed."""
    if not text:
        return ""
    if pos is None or pos < 0:
        pos = 0
    start = max(0, pos - width // 3)
    frag = text[start:start + width]
    esc = html.escape(frag)
    for t in sorted({x for x in terms if len(x) >= 3}, key=len, reverse=True):
        et = html.escape(t)
        if et and "<mark>" not in et:
            esc = re.sub("(?<!\x00)" + re.escape(et),
                         lambda m: "\x00" + m.group(0) + "\x01", esc, flags=re.IGNORECASE)
    esc = esc.replace("\x00", "<mark>").replace("\x01", "</mark>")
    return ("…" if start > 0 else "") + esc + ("…" if start + width < len(text) else "")


# The docs table is small (~7k rows) but re-reading + re-parsing it from SQLite on
# every keystroke-driven search was ~half the 1.8s latency. Hold it in memory,
# keyed by catalog signature, and reload only when the signature moves.
_SEARCH_MEM = {"sig": None, "rows": None}


def _search_rows():
    """Cached list of index rows (ref, kind, label, ntitle, nbody). Rebuilds the
    on-disk index and reloads into memory only when the catalog signature changes.
    Returns None if there is no catalog. sqlite3.Row objects outlive their
    connection, so it is safe to close and keep them."""
    sig = current_signature()
    if sig is None:
        return None
    if _SEARCH_MEM["sig"] == sig and _SEARCH_MEM["rows"] is not None:
        return _SEARCH_MEM["rows"]
    if not build_search_index():
        return None
    sdb = sqlite3.connect(SEARCH_DB)
    sdb.row_factory = sqlite3.Row
    try:
        rows = sdb.execute("SELECT ref, kind, label, ntitle, nbody FROM docs").fetchall()
    except sqlite3.OperationalError:
        return None
    finally:
        sdb.close()
    _SEARCH_MEM["sig"] = sig
    _SEARCH_MEM["rows"] = rows
    return rows


# Nicer labels for the amulet search terms the Lazada adapter tags with.
# English glosses for the Thai commerce search-terms. The Thai script itself is
# always shown alongside (see MARKET_PAGE), so these are the English half of a
# bilingual label — legible to a non-Thai reader without erasing the folk term.
MARKET_TERM_LABELS = {
    "พระเครื่อง": "Amulets (phra khrueang)",
    "เครื่องราง": "Talismans (khrueang rang)",
    "เครื่องรางของขลัง": "Talismans & charms (khrueang rang khong khlang)",
    "ของขลัง": "Sacred potent objects (khong khlang)",
    "วัตถุมงคล": "Auspicious sacred objects (watthu mongkhon)",
    "ตะกรุด": "Takrut scrolls",
    "กุมารทอง": "Kuman Thong (golden-boy spirit)",
    "ไอ้ไข่": "Ai Khai (child spirit)",
    "นางกวัก": "Nang Kwak (beckoning lady)",
    "ปลัดขิก": "Palad Khik (phallic amulet)",
    "หนุมาน": "Hanuman",
    "ราหู": "Rahu (eclipse deity)",
    "ท้าวเวสสุวรรณ": "Thao Wessuwan (guardian yaksha)",
    "จตุคาม": "Jatukham Ramathep",
    "ฤๅษี": "Lersi / Ruesi (hermit sage)",
    "ล็อกเก็ตพระ": "Monk lockets (locket phra)",
    "พระพิมพ์": "Votive tablets (phra phim)",
    "พิมพ์": "Amulet moulds / types (phim)",
    "ผงพุทธคุณ": "Sacred powder (phong phutthakhun)",
    "ผ้ายันต์": "Yantra cloth (pha yan)",
    "ชานหมาก": "Chewed-betel relic (chan mak)",
    "ว่าน": "Sacred herbs / tubers (waan)",
    "ว่านจังงัง": "Waan Jang-ngang (paralysing herb)",
    "น้ำมันมนต์": "Enchanted oil (nam man mon)",
    "น้ำมันเสน่ห์": "Love oil (nam man saneh)",
    "น้ำมันจันทน์": "Sandalwood oil (nam man chan)",
    "น้ำมันพราย": "Ghost oil (nam man phrai)",
    "สีผึ้ง": "Love beeswax (see pheung)",
    "สีผึ้งเสน่ห์": "Love beeswax (see pheung saneh)",
    "สีผึ้งมหาเสน่ห์": "Great charm love-wax (see pheung maha saneh)",
    "เมตตามหานิยม": "Loving-kindness & charisma (metta maha niyom)",
    "คงกระพัน": "Invulnerability (kongkraphan)",
    "แหวนพิรอด": "Woven magic ring (waen phirot)",
    # English / romanized net-widening terms (Thai sellers keyword inconsistently)
    "amulet": "Amulets (พระเครื่อง)",
    "thai amulet": "Thai amulets (พระเครื่องไทย)",
    "buddha amulet": "Buddha amulets (พระเครื่องพระพุทธเจ้า)",
    "lucky charm": "Lucky charm (ของนำโชค)",
    "lucky": "Luck (โชคดี)",
    "talisman": "Talisman (เครื่องราง)",
    "hoon payon": "Hoon payon spirit-effigy (หุ่นพยนต์)",
    "hun payon": "Hoon payon spirit-effigy (หุ่นพยนต์)",
    # Named amulets / monks / charm-types from the wide net
    "หลวงปู่ทวด": "Luang Pu Thuat (revered-monk amulets)",
    "พระสมเด็จ": "Phra Somdej (classic votive amulet)",
    # The chip shows the text before the parenthesis; the full string is the
    # tooltip, so the hybrid caveat travels with the term. ขุนแผน is the class
    # axis's sharpest seam (see wichaa-vault/_meta/vocab/classes.md): a pressed
    # amulet in Buddha-amulet FORM made with prai-kuman MATERIAL — not a
    # free-standing kuman that needs feeding.
    "ขุนแผน": "Khun Phaen (khun phaen — hybrid: Buddha-amulet form, prai-kuman material; not a kuman to raise)",
    "เบี้ยแก้": "Bia Kae (cowrie warding charm)",
    "เสือ": "Tiger (suea — tiger amulets)",
    "มีดหมอ": "Mit Mo (ritual spirit-dagger)",
    "เขี้ยวเสือ": "Tiger fang (khiao suea)",
    "พญาเต่าเรือน": "Phaya Tao Ruean (turtle amulet)",
    "กะลาตาเดียว": "One-eyed coconut shell (kala ta diao)",
    "เรียกทรัพย์": "Wealth-summoning (riak sap)",
    "เมตตา": "Loving-kindness (metta)",
}

# Thai province → English exonym, so a location line reads to both audiences.
# Covers all 77 changwat; unknowns fall through to the raw Thai string.
PROVINCE_EN = {
    "กรุงเทพมหานคร": "Bangkok", "นนทบุรี": "Nonthaburi", "ปทุมธานี": "Pathum Thani",
    "สมุทรปราการ": "Samut Prakan", "สมุทรสาคร": "Samut Sakhon", "สมุทรสงคราม": "Samut Songkhram",
    "นครปฐม": "Nakhon Pathom", "พระนครศรีอยุธยา": "Ayutthaya", "อ่างทอง": "Ang Thong",
    "ลพบุรี": "Lopburi", "สิงห์บุรี": "Sing Buri", "ชัยนาท": "Chai Nat", "สระบุรี": "Saraburi",
    "นครนายก": "Nakhon Nayok", "สุพรรณบุรี": "Suphan Buri", "เชียงใหม่": "Chiang Mai",
    "เชียงราย": "Chiang Rai", "ลำปาง": "Lampang", "ลำพูน": "Lamphun", "แม่ฮ่องสอน": "Mae Hong Son",
    "แพร่": "Phrae", "น่าน": "Nan", "พะเยา": "Phayao", "อุตรดิตถ์": "Uttaradit",
    "ตาก": "Tak", "สุโขทัย": "Sukhothai", "พิษณุโลก": "Phitsanulok", "พิจิตร": "Phichit",
    "กำแพงเพชร": "Kamphaeng Phet", "นครสวรรค์": "Nakhon Sawan", "อุทัยธานี": "Uthai Thani",
    "เพชรบูรณ์": "Phetchabun", "นครราชสีมา": "Nakhon Ratchasima", "บุรีรัมย์": "Buri Ram",
    "สุรินทร์": "Surin", "ศรีสะเกษ": "Si Sa Ket", "อุบลราชธานี": "Ubon Ratchathani",
    "ยโสธร": "Yasothon", "ชัยภูมิ": "Chaiyaphum", "อำนาจเจริญ": "Amnat Charoen",
    "หนองบัวลำภู": "Nong Bua Lamphu", "ขอนแก่น": "Khon Kaen", "อุดรธานี": "Udon Thani",
    "เลย": "Loei", "หนองคาย": "Nong Khai", "มหาสารคาม": "Maha Sarakham", "ร้อยเอ็ด": "Roi Et",
    "กาฬสินธุ์": "Kalasin", "สกลนคร": "Sakon Nakhon", "นครพนม": "Nakhon Phanom",
    "มุกดาหาร": "Mukdahan", "บึงกาฬ": "Bueng Kan", "ชลบุรี": "Chon Buri", "ระยอง": "Rayong",
    "จันทบุรี": "Chanthaburi", "ตราด": "Trat", "ฉะเชิงเทรา": "Chachoengsao",
    "ปราจีนบุรี": "Prachin Buri", "สระแก้ว": "Sa Kaeo", "ราชบุรี": "Ratchaburi",
    "กาญจนบุรี": "Kanchanaburi", "เพชรบุรี": "Phetchaburi", "ประจวบคีรีขันธ์": "Prachuap Khiri Khan",
    "นครศรีธรรมราช": "Nakhon Si Thammarat", "กระบี่": "Krabi", "พังงา": "Phang Nga",
    "ภูเก็ต": "Phuket", "สุราษฎร์ธานี": "Surat Thani", "ระนอง": "Ranong", "ชุมพร": "Chumphon",
    "สงขลา": "Songkhla", "สตูล": "Satun", "ตรัง": "Trang", "พัทลุง": "Phatthalung",
    "ปัตตานี": "Pattani", "ยะลา": "Yala", "นราธิวาส": "Narathiwat",
    "ต่างประเทศ": "Overseas",
}


def market_snapshot():
    """The living-vernacular commerce view: rows the crawler put in `items`
    (method='commerce') — amulets and sacred objects as they trade today. Read-only.
    Sits on the same timeline as the manuscripts; the seam is provenance, not schema."""
    snap = {"dbPresent": db_present(), "count": 0, "items": [],
            "terms": [], "locations": [], "price": {}, "sources": []}
    if not db_present():
        return snap
    conn = connect()
    try:
        # dead_since is written by the crawler's linkcheck job; tolerate a DB where it
        # hasn't been created yet (fresh setup, linkcheck never run) — select it only
        # when present so the market view never breaks on a missing column.
        has_dead = any(r[1] == "dead_since"
                       for r in conn.execute("PRAGMA table_info(items)"))
        dead_sel = "i.dead_since, " if has_dead else ""
        rows = conn.execute(
            "SELECT i.id, i.source_identifier, i.title_thai, i.title_english, "
            "i.price_value, i.price_currency, i.location_text, i.source_url, "
            "i.image_url, i.kind, i.raw_metadata, i.first_seen, i.last_seen, "
            + dead_sel +
            "s.name AS source_name "
            "FROM items i LEFT JOIN sources s ON s.id = i.source_id "
            "WHERE i.method = 'commerce' ORDER BY i.last_seen DESC, i.id DESC"
        ).fetchall()
        tagrows = conn.execute(
            "SELECT item_id, term_raw FROM tags "
            "WHERE method = 'commerce' AND item_id IS NOT NULL"
        ).fetchall()
        terms_by_item = {}
        for t in tagrows:
            terms_by_item.setdefault(t["item_id"], []).append(t["term_raw"])

        term_counts, loc_counts, src_counts = {}, {}, {}
        prices, items = [], []
        for r in rows:
            terms = terms_by_item.get(r["id"], [])
            try:
                raw = json.loads(r["raw_metadata"]) if r["raw_metadata"] else {}
            except Exception:
                raw = {}
            pv = r["price_value"]
            if pv is not None:
                prices.append(pv)
            items.append({
                "id": r["id"],
                "title": r["title_thai"] or r["title_english"] or r["source_identifier"],
                "price": pv, "currency": r["price_currency"] or "THB",
                "location": r["location_text"] or "",
                "location_en": PROVINCE_EN.get(r["location_text"] or "", ""),
                "url": r["source_url"] or "",
                # skip lazy-load base64 placeholders — treat as no image
                "image": (r["image_url"] if r["image_url"] and not r["image_url"].startswith("data:") else ""),
                "sold": raw.get("sold"),
                # crawl time axis: first_seen is when the crawler first catalogued the
                # listing, last_seen the most recent time it was still live. Both let a
                # downstream reader build price/availability trends over dated snapshots.
                "crawled_at": r["first_seen"] or "",
                "last_seen": r["last_seen"] or "",
                # when the source page was first found dead (null = live / unchecked);
                # the market view archives listings dead > 30 days, never deletes them.
                "deadSince": (r["dead_since"] if has_dead else None) or "",
                "terms": terms, "source": r["source_name"] or "",
            })
            for tm in terms:
                term_counts[tm] = term_counts.get(tm, 0) + 1
            if r["location_text"]:
                loc_counts[r["location_text"]] = loc_counts.get(r["location_text"], 0) + 1
            if r["source_name"]:
                src_counts[r["source_name"]] = src_counts.get(r["source_name"], 0) + 1

        if prices:
            ps = sorted(prices)
            snap["price"] = {"min": ps[0], "max": ps[-1],
                             "median": ps[len(ps) // 2], "count": len(ps)}
        snap.update(
            count=len(items), items=items,
            termLabels={k: MARKET_TERM_LABELS.get(k, "") for k in term_counts},
            terms=[{"value": k, "label": MARKET_TERM_LABELS.get(k, ""), "n": v}
                   for k, v in sorted(term_counts.items(), key=lambda x: -x[1])],
            locations=[{"value": k, "en": PROVINCE_EN.get(k, ""), "n": v}
                       for k, v in sorted(loc_counts.items(), key=lambda x: -x[1])],
            sources=[{"value": k, "n": v}
                     for k, v in sorted(src_counts.items(), key=lambda x: -x[1])],
        )
        # Preservation permalink: the whole commerce snapshot is mirrored to the
        # Internet Archive so it outlives the ephemeral source listings. All
        # commerce rows carry the same dataset permalink once archived.
        try:
            a = conn.execute(
                "SELECT archive_url, MAX(archived_at) at, COUNT(image_sha256) imgs "
                "FROM items WHERE method='commerce' AND archive_url IS NOT NULL"
            ).fetchone()
            if a and a["archive_url"]:
                snap["archive"] = {"url": a["archive_url"], "at": a["at"],
                                   "images": a["imgs"] or 0}
        except sqlite3.OperationalError:
            pass
        return snap
    finally:
        conn.close()


def expedite_snapshot():
    """The St. Expedite tradition view: shrine/church records the crawler put in
    `items` (method='devotion') from OpenStreetMap + a hand-curated canon. A coequal
    corpus node beside the manuscripts and the amulet market — the seam is provenance,
    not a manuscript-shaped schema. The full illustrated wiki (map, gallery, articles,
    ngram charts) lives in the standalone st-expedite-wiki build; this is its home
    inside the shared wichaa corpus."""
    snap = {"dbPresent": db_present(), "count": 0, "items": [],
            "countries": [], "kinds": []}
    if not db_present():
        return snap
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT i.id, i.title_english, i.kind, i.location_text, i.source_url, "
            "i.raw_metadata, s.name AS source_name "
            "FROM items i LEFT JOIN sources s ON s.id = i.source_id "
            "WHERE i.method = 'devotion' ORDER BY i.location_text, i.title_english"
        ).fetchall()
        country_counts, kind_counts, items = {}, {}, []
        for r in rows:
            try:
                raw = json.loads(r["raw_metadata"]) if r["raw_metadata"] else {}
            except Exception:
                raw = {}
            loc = r["location_text"] or "—"
            items.append({
                "id": r["id"], "title": r["title_english"] or "(unnamed shrine)",
                "kind": r["kind"] or "shrine", "location": loc,
                "url": r["source_url"] or "",
                "lat": raw.get("lat"), "lon": raw.get("lon"),
                "curated": bool(raw.get("curated")), "role": raw.get("role") or "",
                "source": r["source_name"] or "",
            })
            country_counts[loc] = country_counts.get(loc, 0) + 1
            kind_counts[r["kind"] or "shrine"] = kind_counts.get(r["kind"] or "shrine", 0) + 1
        snap.update(
            count=len(items), items=items,
            countries=[{"value": k, "n": v}
                       for k, v in sorted(country_counts.items(), key=lambda x: -x[1])],
            kinds=[{"value": k, "n": v}
                   for k, v in sorted(kind_counts.items(), key=lambda x: -x[1])],
        )
        return snap
    finally:
        conn.close()


def search(q, limit=60):
    """Robust multilingual search. Splits the query into tokens, expands each via
    the bilingual thesaurus + sara-am normalization, and requires every token-group
    to hit (AND of ORs) somewhere in a doc's title or body — as a plain substring,
    so Thai and Latin behave identically. Returns
    {manuscripts:[{id,label,snippet}], articles:[{key,label,snippet}], query}."""
    out = {"manuscripts": [], "articles": [], "query": q}
    if not q or not q.strip():
        return out
    rows = _search_rows()
    if not rows:
        return out
    groups = [_expand_token(t) for t in q.split() if t.strip()]
    groups = [g for g in groups if g]
    if not groups:
        return out
    all_terms = {m for g in groups for m in g}

    scored = []
    for r in rows:
        ntitle, nbody = r["ntitle"] or "", r["nbody"] or ""
        score, ok, first_pos = 0, True, None
        for g in groups:
            ghit = 0
            for m in g:
                if not m:
                    continue
                if m in ntitle:
                    ghit += 12
                cnt = nbody.count(m)
                if cnt:
                    ghit += min(cnt, 6)
                    p = nbody.find(m)
                    if first_pos is None or p < first_pos:
                        first_pos = p
            if ghit == 0:
                ok = False
                break
            score += ghit
        if ok:
            scored.append((score, r, first_pos))
    scored.sort(key=lambda x: -x[0])

    # cap each bucket independently so a flood of high-OCR manuscripts can't crowd
    # the authored articles out of the results
    for score, r, pos in scored:
        if r["kind"] == "m":
            if len(out["manuscripts"]) >= limit:
                continue
            snip = _snippet(r["nbody"] or r["ntitle"] or "", all_terms, pos)
            out["manuscripts"].append({"id": int(r["ref"]), "label": r["label"], "snippet": snip})
        else:
            if len(out["articles"]) >= limit:
                continue
            snip = _snippet(r["nbody"] or r["ntitle"] or "", all_terms, pos)
            out["articles"].append({"key": r["ref"], "label": r["label"], "snippet": snip})
    return out


def articles_index():
    """The prioritized backlog surfaced in-app: every genre value, plus the curated
    esoteric subjects (entities) and any sub-genres we've written up. Ordered
    wichaa-first, then written-before-stub, then by size. Entities carry the whole
    registry so zero-count wanted subjects (lersi, phrommachat) surface as stubs —
    the strongest crawl signals — rather than staying invisible."""
    out = {"dbPresent": db_present(), "articles": []}
    if not db_present():
        return out
    conn = connect()
    try:
        # 1. Genres — the full backlog (written + stub).
        for r in conn.execute(
                "SELECT genre_normalized v, COUNT(*) n FROM manuscripts "
                "WHERE genre_normalized IS NOT NULL AND genre_normalized<>'' "
                "GROUP BY v").fetchall():
            v = r["v"]
            c = load_content("genre", v)
            out["articles"].append({
                "key": f"genre:{v}", "type": "genre", "value": v,
                "label": prettify(v, GENRE_LABELS), "count": r["n"],
                "note": GENRE_NOTES.get(v, ""), "priority": v in PRIORITY_GENRES,
                "hasArticle": c["exists"], "status": c["status"] if c["exists"] else "stub",
                "image": article_image("genre", v),
            })
        # 2. Entities — the curated esoteric-subject registry, whole wishlist.
        for key, label, weight, _variants in ENTITIES:
            pred = subject_predicate("entity", key)
            if not pred:
                continue
            where, params = pred[0], pred[1]
            n = conn.execute(
                f"SELECT COUNT(*) FROM manuscripts WHERE {where}", params).fetchone()[0]
            c = load_content("entity", key)
            out["articles"].append({
                "key": f"entity:{key}", "type": "entity", "value": key,
                "label": label, "count": n,
                "note": "Esoteric subject — title-matched across genres.",
                "priority": weight >= 2.0,
                "hasArticle": c["exists"], "status": c["status"] if c["exists"] else "stub",
                "image": article_image("entity", key),
            })
        # 3. Sub-genres — only those with authored prose, so the index isn't
        #    flooded with every raw genre-label combination.
        for r in conn.execute(
                "SELECT genre_normalized g, genre_raw raw, COUNT(*) n FROM manuscripts "
                "WHERE genre_normalized IS NOT NULL AND genre_normalized<>'' "
                "AND genre_raw IS NOT NULL AND genre_raw<>'' GROUP BY g, raw").fetchall():
            value = f"{r['g']}:{r['raw']}"
            c = load_content("subgenre", value)
            if not c["exists"]:
                continue
            out["articles"].append({
                "key": f"subgenre:{value}", "type": "subgenre", "value": value,
                "label": f"{prettify(r['g'], GENRE_LABELS)} \u203a {r['raw']}",
                "count": r["n"], "note": "Sub-genre.",
                "priority": r["g"] in PRIORITY_GENRES,
                "hasArticle": True, "status": c["status"],
                "image": article_image("subgenre", value),
            })
        # 4. The remaining axes — temple, script, language, material, province.
        #    subject_predicate already resolves every one of them and /browse
        #    already counts them; only this index never enumerated them, so 158
        #    temples and 10 provinces had a facet count and no door. Computed
        #    facts and real counts; prose appears for the ones somebody has
        #    written (content/temple-wat_sung_men.md finally has a page) and is
        #    simply absent for the rest, never generated to fill the space.
        #    Language is deliberately NOT here. SUBJECT resolves it by exact
        #    match on the raw column, which would publish "Monolingual Pali"
        #    and "Pali and Lan Na" as nodes, while /browse counts the eleven
        #    canonical languages taxonomy.language_components() splits them
        #    into. Two vocabularies for one axis is worse than one door fewer;
        #    it wants node_predicate, which is its own piece of work.
        for stype, note, floor in (
                ("temple", "The temples that hold this corpus.", 1),
                ("script", "The hands these manuscripts are written in.", 1),
                ("material", "What the text is written on.", 1),
                ("province", "Where the manuscripts came to rest.", 1)):
            col = SUBJECT[stype]["col"]
            for r in conn.execute(
                    f"SELECT {col} v, COUNT(*) n FROM manuscripts "
                    f"WHERE {col} IS NOT NULL AND {col}<>'' GROUP BY v").fetchall():
                v = r["v"]
                # The province column mixes provinces, districts and temples.
                # Only a value that IS a canonical province becomes a province
                # node; the rest are already reachable as temples or not at all,
                # and inventing a "Mueang District" province would be a
                # falsehood about the geography.
                if stype == "province" and taxonomy.resolve_province(v) != v:
                    continue
                # The temple column has the same collision in the other
                # direction: "Mueang District", "Sung Men District", "Phrae",
                # and holders that are not temples at all (Siam Society, Nan
                # Provincial Museum). A temple announces itself with Wat/วัด;
                # everything else keeps its manuscripts and stays out of the
                # temple directory rather than being published as a temple.
                if stype == "temple" and not _IS_TEMPLE_NAME.match(str(v)):
                    continue
                if r["n"] < floor:
                    continue
                c = load_content(stype, v)
                out["articles"].append({
                    "key": f"{stype}:{v}", "type": stype, "value": v,
                    "label": prettify(v, SUBJECT[stype]["labels"]) or str(v),
                    "count": r["n"], "note": note, "priority": False,
                    "hasArticle": c["exists"],
                    "status": c["status"] if c["exists"] else "stub",
                    "image": article_image(stype, v),
                })
    finally:
        conn.close()
    out["articles"].sort(key=lambda a: (0 if a["priority"] else 1,
                                        0 if a["hasArticle"] else 1, -a["count"]))
    return out


def findings_index():
    """Every published curiosity-bot finding, rendered. These are machine-made
    notes that auto-publish (author labelled), and until now they lived in the
    database with nowhere to be read — this is their home."""
    out = {"dbPresent": db_present(), "findings": []}
    if not db_present():
        return out
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT slug, finding_type, finding_key, title, body_md, confidence, "
            "author, review_state, first_filed, last_refreshed, evidence_json "
            "FROM articles WHERE status='published' "
            "ORDER BY first_filed DESC").fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()
    for r in rows:
        try:
            ev = json.loads(r["evidence_json"] or "{}")
        except Exception:
            ev = {}
        counts = {k: len(v) for k, v in ev.items() if isinstance(v, list) and v}
        out["findings"].append({
            "slug": r["slug"], "type": r["finding_type"], "key": r["finding_key"],
            "title": r["title"], "html": md_to_html(r["body_md"] or ""),
            "confidence": r["confidence"], "author": r["author"] or "curiosity-bot",
            "reviewState": r["review_state"], "firstFiled": r["first_filed"],
            "lastRefreshed": r["last_refreshed"], "evidence": counts})
    return out


# ---------------------------- image store ----------------------------
def store_path(sha256):
    if not sha256 or len(sha256) < 3 or not all(c in "0123456789abcdef" for c in sha256.lower()):
        return None
    p = (STORE_DIR / sha256[:2] / sha256).resolve()
    try:
        p.relative_to(STORE_DIR.resolve())
    except ValueError:
        return None
    return p if p.is_file() else None


# Resized derivatives are cached locally under data/thumbs (never on the exFAT
# store) so a missing drive can't corrupt them and re-crawls don't wipe them.
THUMB_DIR = DATA / "thumbs"
ALLOWED_WIDTHS = (240, 480, 1200)


def thumb_bytes(sha256, width):
    """Return (jpeg_bytes, 'image/jpeg') for a store image scaled to `width`, or
    None if the source is missing or Pillow isn't available. Cached on disk — the
    cache is consulted BEFORE the store, so an already-built thumbnail still serves
    when the external image drive happens to be unmounted."""
    if not sha256:
        return None
    if width not in ALLOWED_WIDTHS:
        width = min(ALLOWED_WIDTHS, key=lambda w: abs(w - width))
    THUMB_DIR.mkdir(exist_ok=True)
    cache = THUMB_DIR / f"{sha256}_{width}.jpg"
    if cache.is_file():
        return (cache.read_bytes(), "image/jpeg")
    src = store_path(sha256)   # only needed to BUILD a thumbnail we haven't cached yet
    if not src:
        return None
    try:
        from PIL import Image
    except Exception:
        return None
    try:
        with Image.open(src) as im:
            im = im.convert("RGB")
            if im.width > width:
                h = round(im.height * width / im.width)
                im = im.resize((width, h), Image.LANCZOS)
            tmp = cache.with_suffix(".tmp")
            im.save(tmp, "JPEG", quality=82, optimize=True)
            tmp.replace(cache)
    except Exception:
        return None
    return (cache.read_bytes(), "image/jpeg")


def iiif_image_map():
    """{sha256: IIIF-image-url} for every crawled scan whose source is a IIIF Image
    API endpoint. The static export ships this so the client can pull page images
    on demand straight from the originating library (sized down via the IIIF size
    parameter) instead of the repo carrying any scan bytes. Live wiki never calls
    this — it serves /img from the local store."""
    out = {}
    if not db_present():
        return out
    conn = connect()
    try:
        for r in conn.execute(
                "SELECT sha256, source_image_url FROM images "
                "WHERE sha256 IS NOT NULL AND sha256<>'' "
                "AND source_image_url LIKE '%/full/full/%'").fetchall():
            out[r["sha256"]] = r["source_image_url"]
    finally:
        conn.close()
    return out


# The social-card image. A rendered plate (shipped with the static site), so the
# published card is never a broken link. 6989/159 — a circular wheel yantra:
# symmetric, centred, legible — is the hand-picked FALLBACK if the live query below
# finds nothing (e.g. the diagram-description bot hasn't run yet).
OG_PLATE = (6989, 159)
OG_TITLE = "wichaa"
OG_TAGLINE = "Northern Thai manuscripts \u2014 astrology, medicine, chronicle, and ritual, read plainly."
OG_CAPTION = "Circular yantra \u00b7 manuscript #6989"

# How many of the best diagram plates form the rotation pool. The featured image is
# picked from this pool by a daily seed, so as the vision bot describes more diagrams
# the corpus's finest plates take turns as the public face — without anyone editing code.
FEATURED_POOL = 16


def _featured_caption(desc, mid):
    """A short, faithful caption from a diagram's vision description. Prefer a
    parenthetical gloss (often the English reading) else the leading phrase."""
    desc = (desc or "").strip()
    if desc:
        m = re.search(r"\(([^)]{3,60})\)", desc)
        phrase = (m.group(1) if m else re.split(r"[\n/.;]", desc)[0]).strip()
        phrase = re.sub(r"\s+", " ", phrase)[:60]
        if phrase:
            return f"{phrase} \u00b7 manuscript #{mid}"
    return f"Manuscript diagram \u00b7 #{mid}"


def featured_plate(seed=None):
    """Pick the featured plate LIVE from the catalogue: a vision-described diagram,
    ranked (yantra/mandala forms first, richer descriptions next), then rotated over
    the top pool by a daily seed so the public face refreshes as the bot works.

    Returns (manuscript_id, page_no, caption) with an existing image file, or the
    hand-picked OG_PLATE fallback. Read-only."""
    if not db_present():
        return (*OG_PLATE, OG_CAPTION)
    if seed is None:
        seed = int(datetime.now().strftime("%Y%j"))  # year+day-of-year: stable per day
    cat = connect()
    try:
        rows = cat.execute(
            "SELECT manuscript_id mid, page_no, vision_desc FROM pages "
            "WHERE kind='diagram' AND image_path IS NOT NULL "
            "AND vision_desc IS NOT NULL AND vision_desc<>'' "
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        cat.close()
    # a striking, centred emblem reads best at social-card size; prefer those words
    STRIKING = ("ยันต์", "วงกลม", "วง", "yantra", "mandala", "wheel", "circular",
                "cosmolog", "diagram of", "chart")
    ranked = []
    for r in rows:
        d = (r["vision_desc"] or "").lower()
        score = sum(2 for w in STRIKING if w in d) + min(len(d), 200) / 200.0
        ranked.append((score, r["mid"], r["page_no"], r["vision_desc"]))
    if not ranked:
        return (*OG_PLATE, OG_CAPTION)
    ranked.sort(key=lambda t: (-t[0], t[1], t[2]))          # best first, stable ties
    pool = ranked[:FEATURED_POOL]
    _, mid, page, desc = pool[seed % len(pool)]
    if not page_image_path(mid, page):                      # image gone → safe fallback
        return (*OG_PLATE, OG_CAPTION)
    return (mid, page, _featured_caption(desc, mid))


def _og_font(size):
    from PIL import ImageFont
    for p in ("/System/Library/Fonts/Supplemental/Georgia.ttf",
              "/Library/Fonts/Georgia.ttf",
              "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
              "/System/Library/Fonts/Georgia.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return None


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def og_card_bytes():
    """The 1200x630 social-preview card: the featured plate matted on a dark ground,
    with the title beside it. Cached to data/og.jpg. The cache is keyed to the current
    selection (data/og.sel), so when featured_plate() rotates to a new image the card
    is rebuilt rather than served stale. None if Pillow is unavailable."""
    mid, page, caption = featured_plate()
    sel = f"{mid}/{page}"
    cache = DATA / "og.jpg"
    selfile = DATA / "og.sel"
    if cache.is_file() and selfile.is_file() and selfile.read_text().strip() == sel:
        return (cache.read_bytes(), "image/jpeg")
    src = page_image_path(mid, page)
    if not src:
        return None
    try:
        from PIL import Image, ImageOps, ImageDraw
    except Exception:
        return None
    try:
        W, H = 1200, 630
        BG = (18, 45, 42)          # deep teal, matches the site header
        CREAM, GOLD = (244, 234, 214), (233, 196, 106)
        canvas = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(canvas)
        # left: the plate, contained (never cropped) in a matted panel
        pad, panel_w = 40, 560
        with Image.open(src) as im:
            im = ImageOps.contain(im.convert("RGB"), (panel_w - 2 * pad, H - 2 * pad))
        px = pad + (panel_w - 2 * pad - im.width) // 2 + pad // 2
        py = (H - im.height) // 2
        canvas.paste(im, (px, py))
        # right: title + tagline + caption (skipped gracefully if no font loads)
        tf, sf, cf = _og_font(66), _og_font(30), _og_font(24)
        if tf and sf and cf:
            tx, tw, y = panel_w + 40, W - (panel_w + 40) - 56, 150
            for ln in _wrap(draw, OG_TITLE, tf, tw):
                draw.text((tx, y), ln, font=tf, fill=CREAM); y += 74
            y += 20
            for ln in _wrap(draw, OG_TAGLINE, sf, tw):
                draw.text((tx, y), ln, font=sf, fill=GOLD); y += 40
            draw.text((tx, H - 78), caption, font=cf, fill=(150, 180, 172))
        tmp = cache.with_suffix(".tmp")
        canvas.save(tmp, "JPEG", quality=88, optimize=True)
        tmp.replace(cache)
        selfile.write_text(sel)
    except Exception:
        return None
    return (cache.read_bytes(), "image/jpeg")


# store_pages/ (the digested textbook page PNGs) sits beside the crawler catalog,
# one level up from crawler/. Page images are addressed by (manuscript, page_no)
# and validated against this base so a crafted path can't escape it.
# PAGES_BASE env override: when the publish pipeline snapshots catalog.db to a
# temp dir (CATALOG_DB then points into /tmp), the images are NOT next to the
# snapshot — the override keeps this pointing at the real crawler tree. Deriving
# it from a relocated CATALOG_DB silently emptied gallery_snapshot() (plates=0,
# no pimg shipped) for two weeks in July 2026.
PAGES_BASE = Path(os.environ.get("PAGES_BASE", CATALOG_DB.resolve().parent.parent))


def page_image_path(mid, page_no):
    """Absolute, sandbox-checked path to a digested page PNG, or None."""
    if not db_present():
        return None
    cat = connect()
    try:
        r = cat.execute("SELECT image_path FROM pages WHERE manuscript_id=? AND page_no=?",
                        (mid, page_no)).fetchone()
    finally:
        cat.close()
    rel = r["image_path"] if r else None
    if not rel or ".." in rel or rel.startswith("/"):
        return None
    p = (PAGES_BASE / rel).resolve()
    try:
        p.relative_to((PAGES_BASE / "store_pages").resolve())
    except ValueError:
        return None
    return p if p.is_file() else None


PAGE_CACHE = (STORE_DIR.parent / "_ppage_cache")
_PPAGE_WIDTHS = (200, 480, 800, 1000, 1400)


def _manuscript_pdf(mid):
    """The source PDF for a contributed manuscript (source_url 'local:…/foo.pdf'),
    sandbox-checked to the contributed tree. None for crawled manuscripts."""
    conn = connect()
    try:
        r = conn.execute("SELECT source_url FROM manuscripts WHERE id=?", (mid,)).fetchone()
    finally:
        conn.close()
    su = (r["source_url"] if r else "") or ""
    if not su.startswith("local:"):
        return None
    rel = su[len("local:"):]
    if ".." in rel or rel.startswith("/"):
        return None
    p = (PAGES_BASE / rel).resolve()
    try:
        p.relative_to(PAGES_BASE.resolve())
    except ValueError:
        return None
    return p if (p.is_file() and p.suffix.lower() == ".pdf") else None


def render_pdf_page(mid, page_no, width=1000):
    """(jpeg_bytes,'image/jpeg') for a contributed manuscript page, rendered ON DEMAND
    from the source PDF via pdftoppm and cached — the local-PDF analogue of the IIIF
    on-demand images: ~4,500 pages become viewable with only a small JPEG cache, no
    bulk PNG store. Prefers an already-rendered store_pages PNG when one exists. Returns
    None if there's no PDF, pdftoppm is absent, or the page is out of range."""
    try:
        page_no = int(page_no)
    except (TypeError, ValueError):
        return None
    if page_no < 1:
        return None
    width = min(_PPAGE_WIDTHS, key=lambda w: abs(w - width))
    pdf = _manuscript_pdf(mid)
    if not pdf or not shutil.which("pdftoppm"):
        return None
    PAGE_CACHE.mkdir(exist_ok=True)
    cache = PAGE_CACHE / f"{mid}_{page_no}_{width}.jpg"
    if cache.is_file():
        return (cache.read_bytes(), "image/jpeg")
    prefix = cache.with_suffix("")  # pdftoppm -singlefile appends .jpg
    try:
        # grayscale + q65: these are B/W printed pages, and the default (colour,
        # q75) tripled the static export's scan bundle for no visible gain —
        # 383MB for the first 6 reader volumes, measured 2026-08-05. Colour
        # plates are unaffected (they ship as stored PNGs, tier 1 above).
        subprocess.run(
            ["pdftoppm", "-f", str(page_no), "-l", str(page_no), "-jpeg",
             "-gray", "-jpegopt", "quality=65,optimize=y",
             "-scale-to-x", str(width), "-scale-to-y", "-1", "-singlefile",
             str(pdf), str(prefix)],
            check=True, capture_output=True, timeout=90)
    except Exception:
        return None
    out = prefix.with_suffix(".jpg")
    if out.is_file():
        return (out.read_bytes(), "image/jpeg")
    return None


# ------------------------------------------------------------------ vocabulary
# The wichaa working vocabulary: the terms explore.py mines from the OCR corpus
# and enrich_tags.py writes back as method='corpus-vocab' tags. This table adds the
# human-readable layer (romanization, gloss, group) and links each term to its
# entity article where one exists. Terms with no article yet are legitimate
# want-list signals, not omissions — shown, just unlinked. Kept in step with
# explore.py's VOCAB; the Thai is composed (ำ) and normalized at read time.
VOCAB_META = [
    # (thai, translit, gloss, group, entity_key_or_None, [variants])
    ("ยา", "ya", "medicine / herb", "practice", None, []),
    ("คาถา", "katha", "katha — spoken incantation", "practice", "katha", []),
    ("สมาธิ", "samadhi", "meditation / samādhi", "practice", None, []),
    ("ยันต์", "yan", "yantra — sacred diagram", "practice", "yantra", []),
    ("ฤาษี", "ruesi", "lersi / ruesi — ascetic-seer (rishi)", "practice", "lersi", ["ฤาษี", "ฤษี"]),
    ("ครู", "khru", "kru — teacher / master-spirit", "practice", None, []),
    ("อาจารย์", "achan", "ajarn — teacher", "practice", None, []),
    ("มนต์", "mon", "mantra", "practice", None, []),
    ("ปลุกเสก", "pluk-sek", "consecration / empowerment", "practice", None, []),
    ("ลงยันต์", "long-yan", "inscribing a yantra", "practice", "yantra", []),
    ("สัก", "sak", "tattoo / sak yant", "practice", None, []),
    ("ขอม", "khom", "Khom — sacred script", "practice", None, []),
    ("เมตตา", "metta", "loving-kindness / charm", "effect / merit", None, []),
    ("เสน่ห์", "saneh", "attraction / allure", "effect / merit", None, []),
    ("มหานิยม", "mahaniyom", "great popularity", "effect / merit", None, []),
    ("คงกระพัน", "khong-kraphan", "invulnerability", "effect / merit", None, []),
    ("แคล้วคลาด", "khlaeo-khlat", "evasion of danger", "effect / merit", None, []),
    ("มหาอุด", "maha-ut", "gun-stopping / sealing", "effect / merit", None, []),
    ("โชคลาภ", "chok-lap", "fortune / luck", "effect / merit", None, []),
    ("ค้าขาย", "kha-khai", "trade / commerce success", "effect / merit", None, []),
    ("พระ", "phra", "monk / Buddha / sacred", "beings / objects", None, []),
    ("เทพ", "thep", "deva / deity", "beings / objects", None, []),
    ("นาค", "nak", "naga — sacred serpent", "beings / objects", "naga", []),
    ("ไก่", "kai", "chicken / rooster — offering-bird, fighting bird", "beings / objects", "kai", []),
    ("ม้า", "ma", "horse — mount of the spirit, of the caravan, of the epic", "beings / objects", "ma", ["ม้าขี่", "ม้าทรง", "ม้าสีหมอก", "ม้าเสพนาง"]),
    ("ผี", "phi", "ghost / spirit", "beings / objects", None, []),
    ("พราย", "phrai", "prai — spirit of the dead", "beings / objects", None, []),
    ("กุมาร", "kuman", "kuman — child-spirit", "beings / objects", None, []),
    ("ขุนแผน", "khun-phaen", "Khun Phaen — epic hero, charm amulet", "beings / objects", "khun_phaen", ["ขุนแผน", "พระขุนแผน"]),
    ("ตะกรุด", "takrut", "takrut — scroll amulet", "beings / objects", None, ["ตะกรุด", "ตระกรุด"]),
    ("ผ้ายันต์", "pha-yan", "yantra cloth", "beings / objects", "yantra", []),
    ("น้ำมัน", "namman", "oil (prai / metta oil)", "beings / objects", None, ["น้ำมัน", "นำมัน", "น้ามัน", "นํามัน"]),
    ("ว่าน", "waan", "waan — magical tuber", "beings / objects", None, []),
]
VOCAB_GROUP_ORDER = ["practice", "effect / merit", "beings / objects"]
# terms whose referent IS an inscribed/drawn artifact — a diagram page is a fair
# illustration for these (the yantra family and the takrut scroll). Deliberately
# narrow: a naga or a script name shouldn't borrow a yantra diagram.
_VOCAB_VISUAL = {"ยันต์", "ผ้ายันต์", "ลงยันต์", "ตะกรุด"}


def vocab_snapshot():
    """Every wichaa term with its corpus attestation: how many manuscripts use it,
    the strongest examples (linked), an entity-article link where one exists, and a
    diagram thumbnail when a tagged manuscript has one. Read-only against catalog.db."""
    out = {"dbPresent": db_present(), "groups": []}
    if not db_present():
        return out
    cat = connect()
    try:
        # corpus-vocab tags: term -> [(mid, hits)]
        by_term = {}
        try:
            for r in cat.execute("SELECT term_raw, manuscript_id, notes FROM tags "
                                 "WHERE method='corpus-vocab'"):
                m = re.search(r"(\d+)\s*occur", r["notes"] or "")
                by_term.setdefault(r["term_raw"], []).append(
                    (r["manuscript_id"], int(m.group(1)) if m else 0))
        except sqlite3.OperationalError:
            pass
        labels = {row["id"]: (row["title_english"] or row["title_translit"]
                              or row["title_thai"] or "(untitled)")
                  for row in cat.execute("SELECT id, title_english, title_translit, "
                                         "title_thai FROM manuscripts")}
        # first diagram page per manuscript, vision-described ones first
        diagram = {}
        try:
            for r in cat.execute("SELECT manuscript_id mid, page_no, vision_desc FROM pages "
                                 "WHERE kind='diagram' AND image_path IS NOT NULL "
                                 "ORDER BY (vision_desc IS NULL OR vision_desc=''), page_no"):
                diagram.setdefault(r["mid"], {"page": r["page_no"],
                                             "desc": (r["vision_desc"] or "")[:240]})
        except sqlite3.OperationalError:
            pass

        groups = {g: [] for g in VOCAB_GROUP_ORDER}
        for thai, translit, gloss, group, entity, variants in VOCAB_META:
            hits = by_term.get(thai, [])
            hits.sort(key=lambda x: -x[1])
            total = sum(h for _, h in hits)
            examples = [{"id": mid, "label": labels.get(mid, "(untitled)"), "hits": h}
                        for mid, h in hits[:6]]
            # thumbnail only for the inscribed-artifact terms: the diagram page from
            # the strongest tagged manuscript that has one — a yantra/takrut diagram
            # is a fair illustration for the whole yantra family
            thumb = None
            if thai in _VOCAB_VISUAL:
                for mid, _ in hits:
                    if mid in diagram:
                        thumb = {"id": mid, "page": diagram[mid]["page"],
                                 "label": labels.get(mid, "(untitled)"),
                                 "desc": diagram[mid]["desc"]}
                        break
            groups[group].append({
                "thai": thai, "translit": translit, "gloss": gloss,
                "entity": entity, "variants": variants,
                "n_mss": len(hits), "total_hits": total,
                "examples": examples, "thumb": thumb,
            })
        out["groups"] = [{"name": g, "terms": groups[g]} for g in VOCAB_GROUP_ORDER]
        return out
    finally:
        cat.close()


def gallery_snapshot():
    """The Plates gallery: every rendered page image that physically exists, with the
    metadata needed to filter and highlight it. Two facets the user asked for —
    graphics (kind='diagram') and good OCR (thai_chars>=40 AND ocr_conf>=85) — plus
    'described' (a vision_desc has been written). Read-only against catalog.db.

    Only the ~258 rendered PNGs under store_pages/ are surfaced here: they include
    ALL 106 diagram plates and ALL described plates, so nothing is a broken thumb.
    The 16,964 raw manuscript scans (the monastic handwriting) live in the images
    table and are reachable from each manuscript's detail view — see rawScans."""
    OCR_MIN_CHARS, OCR_MIN_CONF = 40, 85.0
    out = {"dbPresent": db_present(), "plates": [], "counts": {}, "rawScans": 0}
    if not db_present():
        return out
    cat = connect()
    try:
        labels = {row["id"]: (row["title_english"] or row["title_translit"]
                              or row["title_thai"] or "(untitled)")
                  for row in cat.execute("SELECT id, title_english, title_translit, "
                                         "title_thai FROM manuscripts")}
        base = (PAGES_BASE).resolve()
        store = (PAGES_BASE / "store_pages").resolve()
        plates = []
        have_transcription = any(
            row["name"] == "transcription"
            for row in cat.execute("PRAGMA table_info(pages)"))
        tcol = ", transcription" if have_transcription else ""
        for r in cat.execute(
                "SELECT manuscript_id mid, page_no, image_path, kind, vision_desc, "
                f"ocr_text, thai_chars, ocr_conf{tcol} FROM pages "
                "WHERE image_path IS NOT NULL ORDER BY manuscript_id, page_no"):
            rel = r["image_path"]
            if not rel or ".." in rel or rel.startswith("/"):
                continue
            p = (PAGES_BASE / rel).resolve()
            try:
                p.relative_to(store)
            except ValueError:
                continue
            if not p.is_file():
                continue
            graphics = (r["kind"] == "diagram")
            desc = (r["vision_desc"] or "").strip()
            described = bool(desc)
            tc = r["thai_chars"] or 0
            conf = r["ocr_conf"] or 0.0
            good_ocr = (tc >= OCR_MIN_CHARS and conf >= OCR_MIN_CONF)
            ocr = re.sub(r"\s+", " ", (r["ocr_text"] or "")).strip()
            trans = ""
            if have_transcription:
                trans = re.sub(r"\s+", " ", (r["transcription"] or "")).strip()
            if described:
                caption = desc[:220]
            elif ocr:
                caption = ocr[:160]
            else:
                caption = trans[:220]        # VLM-transcribed handwritten page
            plates.append({
                "id": r["mid"], "page": r["page_no"],
                "title": labels.get(r["mid"], "(untitled)"),
                "kind": r["kind"] or "",
                "graphics": graphics, "described": described,
                "goodOcr": good_ocr,
                "thaiChars": tc, "ocrConf": round(conf, 1),
                "caption": caption,
                "hasOcr": bool(ocr),
                "hasTranscription": bool(trans),
            })
        # graphics first, then described, then good-ocr, then by manuscript/page
        plates.sort(key=lambda e: (not e["graphics"], not e["described"],
                                   not e["goodOcr"], e["title"], e["page"]))
        out["plates"] = plates
        out["counts"] = {
            "all": len(plates),
            "graphics": sum(1 for e in plates if e["graphics"]),
            "described": sum(1 for e in plates if e["described"]),
            "goodOcr": sum(1 for e in plates if e["goodOcr"]),
        }
        try:
            out["rawScans"] = cat.execute("SELECT count(*) c FROM images").fetchone()["c"]
        except sqlite3.OperationalError:
            pass
        return out
    finally:
        cat.close()


def diagrams_snapshot():
    """Every diagram/figure page across the corpus — the drawn tradition (yantra,
    sak-yant stencils, cosmological charts, talismanic figures) gathered into one
    surface. Images render ON DEMAND via /pimg, so nothing needs pre-storing. Each
    carries its vision description as a caption and links back to its manuscript.
    Described-first so the richest cards lead."""
    snap = {"dbPresent": db_present(), "diagrams": [], "sources": [],
            "total": 0, "described": 0}
    if not db_present():
        return snap
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT p.manuscript_id mid, p.page_no n, p.vision_desc vd, "
            "m.title_english te, m.title_translit tt, m.title_thai th, "
            "m.genre_normalized g "
            "FROM pages p JOIN manuscripts m ON m.id = p.manuscript_id "
            "WHERE p.kind='diagram' "
            "ORDER BY (p.vision_desc IS NOT NULL AND p.vision_desc<>'') DESC, "
            "p.manuscript_id, p.page_no").fetchall()
        per = {}
        for r in rows:
            title = r["te"] or r["tt"] or r["th"] or "(untitled)"
            desc = (r["vd"] or "").strip()
            snap["diagrams"].append({
                "mid": r["mid"], "n": r["n"], "title": title,
                "genre": r["g"] or "",
                "genreLabel": prettify(r["g"], GENRE_LABELS) if r["g"] else "",
                "desc": desc[:400],
                "src": "/pimg?mid=%d&n=%d&w=400" % (r["mid"], r["n"]),
                "full": "/pimg?mid=%d&n=%d&w=1400" % (r["mid"], r["n"]),
                "href": "/m?id=%d#pages" % r["mid"]})
            if desc:
                snap["described"] += 1
            per.setdefault(r["mid"], {"mid": r["mid"], "title": title, "n": 0})["n"] += 1
        snap["sources"] = sorted(per.values(), key=lambda x: -x["n"])
        snap["total"] = len(snap["diagrams"])
    finally:
        conn.close()
    return snap


WATS_JSON = HERE / "data" / "wats.geojson"
COVERAGE_JSON = HERE / "data" / "coverage.json"
PLACE_TYPES_JSON = HERE / "data" / "place-types.json"


def coverage_snapshot():
    """Scope as data: what has been looked for, where, by what method.

    Published so an agent can distinguish an absence from a gap without a human
    explaining it — which is the difference between "no temples here" and "nobody
    has crawled here yet". Compiled from the vault's _meta/coverage.md."""
    return load_json(COVERAGE_JSON, {"scopes": []})


def place_types_snapshot():
    """The emic vocabulary. san_phra_phum and san_chao_thi are different things;
    publishing the vocabulary means a consumer can see that without being told."""
    return load_json(PLACE_TYPES_JSON, {"terms": []})


def wats_snapshot():
    """The wat catalogue — 345 Buddhist temples in and around Chiang Mai, the
    physical sites of the tradition this corpus documents. Compiled in the
    mueang-map project from OpenStreetMap + Wikidata and refreshed here by
    `sync_wats.py`; it does NOT come from catalog.db, because these are places,
    not manuscripts, and forcing them into a manuscript-shaped schema would lose
    what makes them legible (coordinates, heritage registration, photographs).
    Same seam as the market and Expedite nodes: provenance, not schema.

    Licence is carried in the payload and rendered on the page — the point data
    is OSM-derived and therefore ODbL share-alike, which the site's CC-BY does
    NOT cover, and every photograph keeps its own Commons licence."""
    if not WATS_JSON.exists():
        return {"present": False, "wats": [], "total": 0, "heritage": 0,
                "photos": 0, "withPhotos": 0, "attribution": {}}
    try:
        snap = json.loads(WATS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {"present": False, "wats": [], "total": 0, "heritage": 0,
                "photos": 0, "withPhotos": 0, "attribution": {}}
    snap["present"] = True
    return snap


def folios_snapshot(limit=48, seed=None):
    """A sample of downloaded raw folio scans (the monastic handwriting) with the
    manuscript id + title needed to link each thumb through to its detail view.
    `seed` makes the sample stable for a given page load; None re-shuffles."""
    out = {"dbPresent": db_present(), "folios": [], "total": 0}
    if not db_present():
        return out
    limit = min(200, max(1, int(limit)))
    cat = connect()
    try:
        out["total"] = cat.execute(
            "SELECT count(*) c FROM images WHERE status='downloaded' "
            "AND sha256 IS NOT NULL AND sha256!=''").fetchone()["c"]
        # With a seed, a cheap deterministic permutation keeps the wall stable
        # across reloads (so the thumbnail cache isn't thrashed); else reshuffle.
        order = ("ORDER BY (i.id * :seed) % 100003, i.id"
                 if seed is not None else "ORDER BY RANDOM()")
        rows = cat.execute(
            "SELECT i.manuscript_id mid, i.sha256 sha, i.sequence seq, "
            "m.title_english te, m.title_translit tt, m.title_thai th "
            "FROM images i JOIN manuscripts m ON m.id=i.manuscript_id "
            "WHERE i.status='downloaded' AND i.sha256 IS NOT NULL AND i.sha256!='' "
            f"{order} LIMIT :lim",
            {"seed": (int(seed) or 1) if seed is not None else 1, "lim": limit}).fetchall()
        for r in rows:
            title = r["te"] or r["tt"] or r["th"] or "(untitled)"
            out["folios"].append({
                "id": r["mid"], "sha": r["sha"], "seq": r["seq"], "title": title})
        return out
    finally:
        cat.close()


def _title_of(r):
    return r["te"] or r["tt"] or r["th"] or "(untitled)"


def triage_snapshot(scan_offset=0, scan_limit=60):
    """Curatorial contact-sheet feed. Answers 'how would we even know what's cool?'
    by surfacing real thumbnails you can star. Two corpora, both read-only:

      • signal — every rendered page carrying an interest signal: the 106 diagram
        folios + any vision-described page. These are the only images the pipeline
        already flags as visually notable; served whole via /pimg. Returned in full.
      • scans  — the raw manuscript folios (the 16 GB the pipeline knows NOTHING
        visual about). We surface the FIRST downloaded folio of each manuscript
        (best odds of a decorated frontispiece), paginated, served as 240px thumbs.

    Every item carries a durable `key` (page:<mid>:<page> or scan:<sha>, sha follows
    the bytes across re-crawls) and its current star state from featured.json. A
    separate `starred` list resolves ALL stars in full, so a 'starred only' view is
    complete regardless of paging."""
    out = {"dbPresent": db_present(), "signal": [], "scans": {},
           "starred": [], "featuredCount": 0}
    if not db_present():
        return out
    feat = load_json(FEATURED_PATH, {})
    starred_keys = {k for k, v in feat.items()
                    if isinstance(v, dict) and v.get("starred")}
    out["featuredCount"] = len(starred_keys)
    scan_limit = min(240, max(1, int(scan_limit)))
    scan_offset = max(0, int(scan_offset))
    cat = connect()
    try:
        # --- signal group: diagrams + described pages, richest first ---------------
        for r in cat.execute(
                "SELECT p.manuscript_id mid, p.page_no page, p.kind, p.vision_desc vd, "
                "p.ocr_text ocr, m.title_english te, m.title_translit tt, m.title_thai th "
                "FROM pages p JOIN manuscripts m ON m.id=p.manuscript_id "
                "WHERE p.image_path IS NOT NULL AND (p.kind='diagram' OR "
                "  (p.vision_desc IS NOT NULL AND p.vision_desc!='')) "
                "ORDER BY (p.kind='diagram') DESC, "
                "  (p.vision_desc IS NOT NULL AND p.vision_desc!='') DESC, "
                "  p.manuscript_id, p.page_no"):
            desc = (r["vd"] or "").strip()
            ocr = re.sub(r"\s+", " ", (r["ocr"] or "")).strip()
            key = "page:%d:%d" % (r["mid"], r["page"])
            out["signal"].append({
                "key": key, "kind": "page", "mid": r["mid"], "page": r["page"],
                "title": _title_of(r),
                "src": "/pimg?mid=%d&n=%d" % (r["mid"], r["page"]),
                "detail": "/m?id=%d" % r["mid"],
                "diagram": (r["kind"] == "diagram"),
                "described": bool(desc),
                "caption": (desc[:200] or ocr[:140]),
                "starred": key in starred_keys,
            })
        # --- scans group: first folio of each imaged manuscript, paginated ---------
        out["scans"]["total"] = cat.execute(
            "SELECT COUNT(DISTINCT manuscript_id) c FROM images "
            "WHERE status='downloaded' AND sha256 IS NOT NULL AND sha256!=''"
        ).fetchone()["c"]
        rows = cat.execute(
            "SELECT i.manuscript_id mid, i.sha256 sha, i.sequence seq, "
            "m.title_english te, m.title_translit tt, m.title_thai th "
            "FROM images i JOIN manuscripts m ON m.id=i.manuscript_id "
            "JOIN (SELECT manuscript_id, MIN(id) firstid FROM images "
            "      WHERE status='downloaded' AND sha256 IS NOT NULL AND sha256!='' "
            "      GROUP BY manuscript_id) f ON f.firstid=i.id "
            "ORDER BY i.manuscript_id LIMIT :lim OFFSET :off",
            {"lim": scan_limit, "off": scan_offset}).fetchall()
        items = []
        for r in rows:
            key = "scan:" + r["sha"]
            items.append({
                "key": key, "kind": "scan", "mid": r["mid"], "sha": r["sha"],
                "seq": r["seq"], "title": _title_of(r),
                "src": "/img?sha=%s&w=240" % r["sha"],
                "detail": "/m?id=%d" % r["mid"],
                "starred": key in starred_keys,
            })
        out["scans"].update({"items": items, "offset": scan_offset,
                             "limit": scan_limit,
                             "returned": len(items)})
        # --- resolve ALL stars in full (paging-independent 'starred only' view) ----
        page_ids, scan_shas = [], []
        for k in starred_keys:
            if k.startswith("page:"):
                try:
                    _, m, pg = k.split(":"); page_ids.append((int(m), int(pg)))
                except ValueError:
                    pass
            elif k.startswith("scan:"):
                scan_shas.append(k[5:])
        resolved = []
        for (m, pg) in page_ids:
            r = cat.execute(
                "SELECT p.manuscript_id mid, p.page_no page, p.kind, p.vision_desc vd, "
                "m.title_english te, m.title_translit tt, m.title_thai th "
                "FROM pages p JOIN manuscripts m ON m.id=p.manuscript_id "
                "WHERE p.manuscript_id=? AND p.page_no=?", (m, pg)).fetchone()
            if r:
                resolved.append({"key": "page:%d:%d" % (m, pg), "kind": "page",
                                 "mid": m, "page": pg, "title": _title_of(r),
                                 "src": "/pimg?mid=%d&n=%d" % (m, pg),
                                 "detail": "/m?id=%d" % m,
                                 "diagram": (r["kind"] == "diagram"),
                                 "described": bool((r["vd"] or "").strip()),
                                 "starred": True})
        if scan_shas:
            qmarks = ",".join("?" * len(scan_shas))
            for r in cat.execute(
                    "SELECT i.manuscript_id mid, i.sha256 sha, i.sequence seq, "
                    "m.title_english te, m.title_translit tt, m.title_thai th "
                    "FROM images i JOIN manuscripts m ON m.id=i.manuscript_id "
                    "WHERE i.sha256 IN (%s)" % qmarks, scan_shas):
                resolved.append({"key": "scan:" + r["sha"], "kind": "scan",
                                 "mid": r["mid"], "sha": r["sha"], "seq": r["seq"],
                                 "title": _title_of(r),
                                 "src": "/img?sha=%s&w=240" % r["sha"],
                                 "detail": "/m?id=%d" % r["mid"], "starred": True})
        out["starred"] = resolved
        return out
    finally:
        cat.close()


def set_featured(key, starred):
    """Toggle a folio's 'striking' star in the durable featured.json. Keys are
    page:<mid>:<page> or scan:<sha256>. Unstarring removes the key so the file stays
    a clean allow-list. Returns the new total. Human-authored; survives re-crawls."""
    if not isinstance(key, str) or not (
            re.fullmatch(r"page:\d+:\d+", key) or re.fullmatch(r"scan:[0-9a-f]{64}", key)):
        raise ValueError("bad key")
    feat = load_json(FEATURED_PATH, {})
    if starred:
        feat[key] = {"starred": True,
                     "updatedAt": datetime.now(timezone.utc).isoformat()}
    else:
        feat.pop(key, None)
    save_json(FEATURED_PATH, feat)
    return len(feat)


def _vlm_reads():
    """sha -> transcription record for scans I (the VLM) have read, from ocr.json.
    Shares the exact store tesseract uses; provenance ('engine') keeps them distinct."""
    out = {}
    for sha, rec in load_json(OCR_PATH, {}).items():
        if isinstance(rec, dict) and rec.get("text"):
            out[sha] = rec
    return out


def scan_manuscripts():
    """The list backing the Plates 'Raw scans' picker: every manuscript that has
    stored scans, with how many scans and how many are transcribed. Cheap — one
    grouped query plus the in-memory ocr.json map."""
    out = {"dbPresent": db_present(), "manuscripts": [], "total": 0, "transcribed": 0}
    if not db_present():
        return out
    reads = _vlm_reads()
    cat = connect()
    try:
        labels = {row["id"]: (row["title_english"] or row["title_translit"]
                              or row["title_thai"] or "(untitled)")
                  for row in cat.execute("SELECT id, title_english, title_translit, "
                                         "title_thai FROM manuscripts")}
        per = {}
        total = 0
        for r in cat.execute("SELECT manuscript_id mid, sha256 sha FROM images "
                             "WHERE sha256 IS NOT NULL ORDER BY manuscript_id, sequence"):
            d = per.setdefault(r["mid"], {"n": 0, "t": 0})
            d["n"] += 1
            total += 1
            if r["sha"] in reads:
                d["t"] += 1
        mss = [{"id": mid, "title": labels.get(mid, "(untitled)"),
                "n": d["n"], "transcribed": d["t"]}
               for mid, d in per.items()]
        mss.sort(key=lambda m: (-m["transcribed"], -m["n"], m["title"]))
        out["manuscripts"] = mss
        out["total"] = total
        out["transcribed"] = sum(1 for r in cat.execute(
            "SELECT sha256 sha FROM images WHERE sha256 IS NOT NULL")
            if r["sha"] in reads)
        return out
    finally:
        cat.close()


def scans_snapshot(mid=None, offset=0, limit=120, only_transcribed=False,
                   require_local=True):
    """A page of raw manuscript scans (the images table — the monastic handwriting)
    for the Plates gallery. Served lazily: scoped to a manuscript, or a global slice,
    so we never ship all ~17k at once. Each entry carries any VLM transcription that
    exists, so the 'transcribed' highlight and caption come for free.

    require_local (default True) keeps only scans whose bytes are in the local store —
    right for the live wiki, which serves /img from disk. The static export passes
    False: it ships no scan bytes and resolves each sha to an on-demand IIIF URL, so a
    scan belongs in the gallery whether or not its file was ever downloaded here."""
    out = {"dbPresent": db_present(), "scans": [], "offset": offset,
           "limit": limit, "total": 0}
    if not db_present():
        return out
    reads = _vlm_reads()
    cat = connect()
    try:
        labels = {row["id"]: (row["title_english"] or row["title_translit"]
                              or row["title_thai"] or "(untitled)")
                  for row in cat.execute("SELECT id, title_english, title_translit, "
                                         "title_thai FROM manuscripts")}
        q = ("SELECT manuscript_id mid, sequence seq, sha256 sha FROM images "
             "WHERE sha256 IS NOT NULL")
        params = []
        if mid is not None:
            q += " AND manuscript_id=?"
            params.append(mid)
        q += " ORDER BY manuscript_id, sequence"
        rows = cat.execute(q, params).fetchall()
        # keep only scans whose file exists; apply transcribed filter
        pool = []
        for r in rows:
            if require_local and store_path(r["sha"]) is None:
                continue
            rec = reads.get(r["sha"])
            if only_transcribed and not rec:
                continue
            pool.append((r, rec))
        out["total"] = len(pool)
        for r, rec in pool[offset:offset + limit]:
            engine = (rec or {}).get("engine", "") if rec else ""
            txt = (rec or {}).get("text", "") if rec else ""
            cap = re.sub(r"\s+", " ", txt).strip()
            out["scans"].append({
                "sha": r["sha"], "id": r["mid"], "seq": r["seq"],
                "title": labels.get(r["mid"], "(untitled)"),
                "transcribed": bool(rec),
                "engine": engine,
                "script": (rec or {}).get("script", "") if rec else "",
                "conf": (rec or {}).get("confidence") if rec else None,
                "caption": cap[:200],
            })
        return out
    finally:
        cat.close()


def sniff_mime(data):
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:2] in (b"II", b"MM"):
        return "image/tiff"
    return "application/octet-stream"


# ---------------------------- OCR ----------------------------
def run_ocr(mid, lang, write):
    """Stream OCR of a manuscript's stored images. Keyed by image sha256 in ocr.json."""
    det = manuscript_detail(mid)
    if not det:
        write("Manuscript not found.\n")
        return
    tess = shutil.which("tesseract")
    if not tess:
        write("Tesseract is not installed. Install it with:\n"
              "    brew install tesseract tesseract-lang\n"
              "then run OCR again. (Note: Lanna/Tham script has no ready model; "
              "Thai 'tha' is only a starting point.)\n")
        return
    imgs = [i for i in det["images"] if i["hasLocal"]]
    if not imgs:
        write("No locally-stored images to OCR yet. Let the crawler download images first.\n")
        return
    ocr = load_json(OCR_PATH, {})
    todo = [i for i in imgs if not ocr.get(i["sha256"], {}).get("text")]
    write(f"OCR manuscript #{mid}  ·  language={lang}  ·  {len(todo)} of {len(imgs)} image(s)\n\n")
    if not todo:
        write("Every stored image already has OCR text.\n")
        return
    done = 0
    for i in todo:
        p = store_path(i["sha256"])
        try:
            with tempfile.TemporaryDirectory() as td:
                src = Path(td) / "page.img"
                src.write_bytes(p.read_bytes())
                out = Path(td) / "out"
                proc = subprocess.run([tess, str(src), str(out), "-l", lang],
                                      capture_output=True, text=True)
                if proc.returncode != 0:
                    err = (proc.stderr or "").strip().splitlines()
                    msg = err[0] if err else "unknown error"
                    if "Failed loading language" in proc.stderr or "Error opening data file" in proc.stderr:
                        write(f"  \u2717 seq {i['sequence']}: no '{lang}' language pack. "
                              f"Install: brew install tesseract-lang\n")
                        write("Stopping.\n")
                        return
                    write(f"  \u2717 seq {i['sequence']}: {msg}\n")
                    continue
                txt = (out.with_suffix(".txt").read_text(encoding="utf-8", errors="replace").strip()
                       if out.with_suffix(".txt").exists() else "")
            ocr[i["sha256"]] = {"text": txt, "lang": lang, "engine": "tesseract",
                                "at": datetime.now(timezone.utc).isoformat()}
            save_json(OCR_PATH, ocr)
            done += 1
            preview = " ".join(txt.split())[:60]
            write(f"  \u2713 seq {i['sequence']}: {len(txt)} chars  {preview}\n")
        except Exception as e:  # noqa: BLE001
            write(f"  \u2717 seq {i['sequence']}: {e}\n")
    write(f"\nWrote OCR text for {done} image(s) into data/ocr.json.\n")


# ---------------------------- HTTP ----------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "wichaa"

    def log_message(self, *a):  # quiet
        pass

    def _send(self, code, ctype, body, extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, "application/json; charset=utf-8", json.dumps(obj, ensure_ascii=False))

    def _body(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n <= 0 or n > 5_000_000:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    # ---- routes ----
    def do_GET(self):
        u = urlparse(self.path)
        path, qs = u.path, parse_qs(u.query)
        _record_traffic(self, path)  # introspection substrate; never raises
        # widgets: /w/<name> (shareable page), /api/w/<name> (data), geo.geojson
        if path == "/api/w/geo.geojson":
            return self._json(geo_geojson())
        if path.startswith("/api/w/"):
            wname = path[len("/api/w/"):]
            if wname in WIDGETS:
                return self._json(WIDGETS[wname][0]())
            return self._json({"error": "unknown widget",
                               "available": sorted(WIDGETS)}, 404)
        if path in ("/w", "/w/"):
            return self._send(200, "text/html; charset=utf-8", widgets_index_page())
        if path.startswith("/w/"):
            wname = path[len("/w/"):].strip("/")
            if wname in WIDGETS:
                embed = (qs.get("embed") or ["0"])[0] == "1"
                return self._send(200, "text/html; charset=utf-8",
                                  widget_page(wname, embed=embed))
            return self._send(404, "text/plain; charset=utf-8", "no such widget")
        if path == "/":
            return self._send(200, "text/html; charset=utf-8", OVERVIEW_PAGE)
        if path == "/favicon.svg":
            return self._send(200, "image/svg+xml; charset=utf-8", FAVICON_SVG,
                              {"Cache-Control": "max-age=86400"})
        if path == "/og.svg":
            return self._send(200, "image/svg+xml; charset=utf-8", OG_SVG,
                              {"Cache-Control": "max-age=86400"})
        if path == "/og.jpg":
            card = og_card_bytes()
            if not card:
                return self._send(404, "text/plain", "not found")
            return self._send(200, "image/jpeg", card[0], {"Cache-Control": "max-age=86400"})
        if path == "/browse":
            return self._send(200, "text/html; charset=utf-8", INDEX_PAGE)
        if path == "/m":
            return self._send(200, "text/html; charset=utf-8", DETAIL_PAGE)
        if path == "/read":
            mid = (qs.get("id") or [""])[0]
            if not mid.isdigit():
                return self._send(404, "text/plain; charset=utf-8", "not found")
            return self._send(200, "text/html; charset=utf-8", reader_page(int(mid)))
        if path == "/textbooks":
            return self._send(200, "text/html; charset=utf-8", TEXTBOOKS_PAGE)
        if path == "/support":
            return self._send(200, "text/html; charset=utf-8", SUPPORT_PAGE)
        if path == "/download/epub":
            # The future paywall gate: this is a real server route (not a static file
            # link), so a later auth/payment check slots in here without changing any
            # link elsewhere on the site. Ungated for now — just serves what
            # epub_volume.py has already built.
            mid = (qs.get("id") or [""])[0]
            if not mid.isdigit():
                return self._send(404, "text/plain; charset=utf-8", "not found")
            epub_path = find_epub(int(mid))
            if not epub_path:
                return self._send(404, "text/plain; charset=utf-8", "no epub built for this manuscript yet")
            return self._send(200, "application/epub+zip", epub_path.read_bytes(),
                              {"Content-Disposition": f'attachment; filename="{epub_path.name}"'})
        if path == "/status":
            return self._send(200, "text/html; charset=utf-8", STATUS_PAGE)
        if path == "/a":
            return self._send(200, "text/html; charset=utf-8", ARTICLE_PAGE)
        if path == "/articles":
            return self._send(200, "text/html; charset=utf-8", ARTICLES_PAGE)
        if path == "/findings":
            return self._send(200, "text/html; charset=utf-8", FINDINGS_PAGE)
        if path == "/diagrams":
            return self._send(200, "text/html; charset=utf-8", DIAGRAMS_PAGE)
        if path == "/dashboard":
            return self._send(200, "text/html; charset=utf-8", DASHBOARD_PAGE)
        # Map / Graph / Plates are pulled from the UX until they're rebuilt much
        # bigger and better; the routes serve an honest placeholder rather than a
        # half-baked view. Their data APIs (/api/graph*, /api/gallery) stay live.
        if path in ("/map", "/graph", "/gallery"):
            return self._send(200, "text/html; charset=utf-8",
                              rebuilding_page(path))
        if path == "/lens":
            return self._send(200, "text/html; charset=utf-8", LENS_PAGE)
        if path == "/vocab":
            return self._send(200, "text/html; charset=utf-8", VOCAB_PAGE)
        if path == "/triage":
            return self._send(200, "text/html; charset=utf-8", TRIAGE_PAGE)
        if path == "/market":
            return self._send(200, "text/html; charset=utf-8", MARKET_PAGE)
        if path == "/expedite":
            return self._send(200, "text/html; charset=utf-8", EXPEDITE_PAGE)
        if path == "/wats":
            return self._send(200, "text/html; charset=utf-8", WATS_PAGE)
        if path.startswith("/vendor/"):
            # vendored map library (MapLibre) for the /wats hero map — served as
            # a plain static file so the browser caches it instead of re-parsing
            # ~780 kB of inlined script on every page view.
            fn = path[len("/vendor/"):]
            f = HERE / "vendor" / fn
            if "/" in fn or ".." in fn or not f.is_file():
                return self._send(404, "text/plain; charset=utf-8", "not found")
            ctype = "text/javascript" if fn.endswith(".js") else "text/css"
            return self._send(200, ctype + "; charset=utf-8", f.read_text(encoding="utf-8"))
        if path == "/activity":
            return self._send(200, "text/html; charset=utf-8", ACTIVITY_PAGE)

        if path == "/api/manuscripts":
            return self._send(200, "application/json; charset=utf-8",
                              manuscripts_api_body())
        if path == "/api/manuscript":
            mid = (qs.get("id") or [""])[0]
            det = manuscript_detail(int(mid)) if mid.isdigit() else None
            if not det:
                return self._json({"error": "not found"}, 404)
            ann = load_json(ANN_PATH, {}).get(det["key"], {"notes": "", "tags": []})
            return self._json({"manuscript": det, "annotation": ann})
        if path == "/api/status":
            return self._json(status_snapshot())
        if path == "/api/overview":
            return self._json(overview_snapshot())
        if path == "/api/dashboard":
            return self._json(dashboard_snapshot())
        if path == "/api/places":
            return self._json(places_snapshot())
        if path == "/api/lenses":
            return self._json(lenses_snapshot())
        if path == "/api/article":
            s = (qs.get("s") or [""])[0]
            stype, _, value = s.partition(":")
            art = build_article(stype, value) if value else None
            if not art:
                return self._json({"error": "not found"}, 404)
            return self._json(art)
        if path == "/api/articles":
            return self._json(articles_index())
        if path == "/api/findings":
            return self._json(findings_index())
        if path == "/api/diagrams":
            return self._json(diagrams_snapshot())
        if path == "/api/graph":
            return self._json(graph_export())
        if path == "/api/graph.jsonld":
            body = json.dumps(graph_jsonld(), ensure_ascii=False, indent=2)
            return self._send(200, "application/ld+json; charset=utf-8", body)
        if path == "/api/graph.ttl":
            return self._send(200, "text/turtle; charset=utf-8", graph_turtle())
        if path == "/api/search":
            return self._json(search((qs.get("q") or [""])[0]))
        if path == "/api/vocab":
            return self._json(vocab_snapshot())
        if path == "/api/gallery":
            src = (qs.get("source") or [""])[0]
            if src == "scans":
                midq = (qs.get("mid") or [""])[0]
                mid = int(midq) if midq.isdigit() else None
                try:
                    offset = max(0, int((qs.get("offset") or ["0"])[0]))
                except ValueError:
                    offset = 0
                try:
                    limit = min(300, max(1, int((qs.get("limit") or ["120"])[0])))
                except ValueError:
                    limit = 120
                only_t = (qs.get("only") or [""])[0] == "transcribed"
                return self._json(scans_snapshot(mid, offset, limit, only_t))
            if src == "scan-index":
                return self._json(scan_manuscripts())
            return self._json(gallery_snapshot())
        if path == "/api/market":
            return self._json(market_snapshot())
        if path == "/api/expedite":
            return self._json(expedite_snapshot())
        if path == "/api/wats":
            return self._json(wats_snapshot())
        if path == "/api/coverage":
            return self._json(coverage_snapshot())
        if path == "/api/place-types":
            return self._json(place_types_snapshot())
        if path == "/api/textbooks":
            return self._json(textbooks_snapshot())
        if path == "/api/sponsor-jobs":
            return self._json(sponsor_jobs_snapshot())
        if path == "/api/sponsor-quote":
            sq = (qs.get("id") or [""])[0]
            if not sq.isdigit():
                return self._json({"error": "bad id"}, 400)
            q = translate_quote(int(sq))
            return self._json(q) if q else self._json({"error": "not found"}, 404)
        if path == "/api/activity":
            return self._json(activity_snapshot())
        if path == "/api/folios":
            lq = (qs.get("limit") or ["48"])[0]
            sq = (qs.get("seed") or [""])[0]
            lim = int(lq) if lq.isdigit() else 48
            seed = int(sq) if sq.isdigit() else None
            return self._json(folios_snapshot(lim, seed))
        if path == "/api/triage":
            oq = (qs.get("scanOffset") or ["0"])[0]
            lq = (qs.get("scanLimit") or ["60"])[0]
            off = int(oq) if oq.isdigit() else 0
            lim = int(lq) if lq.isdigit() else 60
            return self._json(triage_snapshot(off, lim))
        if path == "/pimg":
            mid = (qs.get("mid") or [""])[0]
            n = (qs.get("n") or [""])[0]
            wq = (qs.get("w") or [""])[0]
            if not (mid.isdigit() and n.isdigit()):
                return self._send(404, "text/plain", "not found")
            width = int(wq) if wq.isdigit() else 1000
            # 1. an already-rendered plate PNG (the curated diagram set), served whole
            p = page_image_path(int(mid), int(n))
            if p:
                data = p.read_bytes()
                return self._send(200, sniff_mime(data), data, {"Cache-Control": "max-age=86400"})
            # 2. otherwise render the page on demand from the source PDF (contributed
            #    volumes: ~4,500 pages viewable with only a JPEG cache, no bulk store)
            r = render_pdf_page(int(mid), int(n), width)
            if r:
                return self._send(200, r[1], r[0], {"Cache-Control": "max-age=86400"})
            return self._send(404, "text/plain", "not found")
        if path == "/img":
            sha = (qs.get("sha") or [""])[0]
            wq = (qs.get("w") or [""])[0]
            if wq.isdigit():
                t = thumb_bytes(sha, int(wq))
                if t:
                    return self._send(200, t[1], t[0], {"Cache-Control": "max-age=86400"})
                # fall through to full bytes if resize unavailable
            p = store_path(sha)
            if not p:
                return self._send(404, "text/plain", "not found")
            data = p.read_bytes()
            return self._send(200, sniff_mime(data), data, {"Cache-Control": "max-age=86400"})
        return self._send(404, "text/plain", "not found")

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/api/annotation":
            body = self._body()
            key = str(body.get("key", ""))
            if not key or "::" not in key:
                return self._json({"error": "bad key"}, 400)
            all_ann = load_json(ANN_PATH, {})
            tags = [t.strip() for t in (body.get("tags") or []) if str(t).strip()]
            all_ann[key] = {"notes": str(body.get("notes", ""))[:20000],
                            "tags": list(dict.fromkeys(tags))[:100],
                            "updatedAt": datetime.now(timezone.utc).isoformat()}
            save_json(ANN_PATH, all_ann)
            return self._json({"ok": True})
        if u.path == "/api/feature":
            body = self._body()
            try:
                total = set_featured(str(body.get("key", "")),
                                     bool(body.get("starred")))
            except ValueError:
                return self._json({"error": "bad key"}, 400)
            return self._json({"ok": True, "featuredCount": total})
        if u.path == "/api/reveal":
            subprocess.Popen(["open", str(STORE_DIR if STORE_DIR.exists() else HERE)])
            return self._json({"ok": True})
        if u.path == "/api/ocr":
            # Local-operator route only. Anything arriving through the reverse
            # proxy carries X-Forwarded-For (Caddy sets it unconditionally);
            # direct localhost requests don't. Public sponsorship goes through
            # the Ko-fi webhook + queue instead — see sponsored OCR below.
            if self.headers.get("X-Forwarded-For"):
                return self._json(
                    {"error": "OCR jobs are sponsor-run on the public site",
                     "sponsor": "https://ko-fi.com/defiantchiangmai",
                     "howTo": "Tip with a message like: OCR 6968"}, 403)
            body = self._body()
            mid = body.get("id")
            lang = str(body.get("lang", "tha"))
            if not isinstance(mid, int) or not (3 <= len(lang) <= 20 and all(c.isalpha() or c == "+" for c in lang)):
                return self._json({"error": "bad request"}, 400)
            if not _job_lock.acquire(blocking=False):
                return self._json({"error": "a task is already running"}, 409)
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()

                def write(s):
                    try:
                        self.wfile.write(s.encode("utf-8"))
                        self.wfile.flush()
                    except Exception:
                        pass
                run_ocr(mid, lang, write)
            finally:
                _job_lock.release()
            return
        if u.path == "/api/kofi-webhook":
            # Ko-fi posts application/x-www-form-urlencoded with a `data` field
            # holding JSON (not a JSON body), so parse it here rather than _body().
            if not KOFI_TOKEN:
                return self._json({"error": "sponsorship not configured"}, 503)
            n = int(self.headers.get("Content-Length", 0) or 0)
            if n <= 0 or n > 1_000_000:
                return self._json({"error": "bad request"}, 400)
            try:
                form = parse_qs(self.rfile.read(n).decode("utf-8"))
                data = json.loads(form.get("data", ["{}"])[0])
            except Exception:
                return self._json({"error": "bad payload"}, 400)
            if data.get("verification_token") != KOFI_TOKEN:
                return self._json({"error": "bad token"}, 403)
            accepted, status = sponsor_enqueue(data)
            # Always 200 once verified — Ko-fi retries non-200s, and a duplicate
            # or unparseable message is our bookkeeping problem, not a delivery
            # failure worth their retry loop.
            return self._json({"ok": True, "accepted": accepted, "status": status})
        return self._send(404, "text/plain", "not found")


# ---------------------------- sponsored OCR (Ko-fi tam boon) ----------------------
# "It would be cool if people could pay to kick off an OCR job." The abuse vector
# becomes the offering box: a Ko-fi tip whose message names a manuscript
# ("OCR 6968") lands here via webhook, joins a queue, and a background worker runs
# the job. The raw /api/ocr route stays for LOCAL use only (no X-Forwarded-For →
# not proxied → the machine's own operator); everyone else goes through Ko-fi.
#
# Queue lives in DATA/sponsor_jobs.json — the wiki's own writable dir, same as
# annotations — keeping the "wiki never writes catalog.db" convention intact.
KOFI_TOKEN = os.environ.get("KOFI_TOKEN", "")
SPONSOR_PATH = DATA / "sponsor_jobs.json"
_sponsor_lock = threading.Lock()
# "OCR 6968" / "TRANSLATE #6968" anywhere in the tip message; explicit keyword
# required so a stray number in a kind note doesn't queue a random manuscript.
_SPONSOR_RE = re.compile(r"\b(ocr|translate)\s*#?\s*(\d{1,6})\b", re.IGNORECASE)

# ---- translation pricing: honest, sustainable, no surprises -----------------------
# A tip buys a proportional number of translated pages. The math is one
# formula in one place: measured tokens/page × model $/MTok × SUSTAIN_MULT.
#   · token counts come from the real measured average of the image-grounded
#     passes (~1.8k in / 1.2k out per printed-Thai page);
#   · the "hard" tier is for volumes in scripts/languages beyond modern Thai
#     (Tham Lanna, Khom, Pali, Lao, Shan…) — more transcription output, more care;
#   · SUSTAIN_MULT=2.5 is the sustainability margin the project runs on: donors
#     fund ~2.5× the raw token cost so retries, failed pages, and the electric
#     bill don't come out of pocket. Not bank robbery, not a loss either.
PRICE_IN_PER_MTOK = 3.00     # USD per 1M input tokens (Sonnet tier; update on change)
PRICE_OUT_PER_MTOK = 15.00   # USD per 1M output tokens
PAGE_TOKENS = {"standard": (1800, 1200),   # measured, printed Thai
               "hard":     (2700, 3600)}   # rare-script estimate: denser transcription
SUSTAIN_MULT = 2.5
# Rough FX so a THB or EUR tip buys a fair page count without a live rate
# feed (a webhook must never depend on an external API call). Refresh occasionally.
FX_TO_USD = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "THB": 0.028, "JPY": 0.0064,
             "AUD": 0.66, "CAD": 0.73, "SGD": 0.74, "NZD": 0.60, "CHF": 1.12}


def _tier_for(language, script):
    """'standard' iff every language/script token is modern Thai; anything else
    (Pali, Tham Lanna, Khom, Lao, Shan, …) is 'hard'. Empty metadata → standard."""
    toks = [t for t in re.split(r"[\s,;+/·-]+", f"{language or ''} {script or ''}".lower()) if t]
    return "standard" if all(t in ("th", "tha", "thai") for t in toks) else "hard"


def page_price_usd(tier):
    """Suggested tip per page: raw token cost × SUSTAIN_MULT, ceil'd to a cent."""
    tin, tout = PAGE_TOKENS[tier]
    raw = tin * PRICE_IN_PER_MTOK / 1e6 + tout * PRICE_OUT_PER_MTOK / 1e6
    return math.ceil(raw * SUSTAIN_MULT * 100) / 100


def translate_quote(mid):
    """The no-surprises quote for one manuscript: tier, untranslated page count,
    per-page suggested tip, and the whole-volume figure."""
    if not db_present():
        return None
    conn = connect()
    try:
        m = conn.execute("SELECT language, script FROM manuscripts WHERE id=?",
                         (mid,)).fetchone()
        if not m:
            return None
        remaining = conn.execute(
            "SELECT COUNT(*) FROM pages WHERE manuscript_id=? AND kind IN ('prose','mixed') "
            "AND (translation IS NULL OR translation='')", (mid,)).fetchone()[0]
    finally:
        conn.close()
    tier = _tier_for(m["language"], m["script"])
    per = page_price_usd(tier)
    return {"mid": mid, "tier": tier, "remainingPages": remaining,
            "perPageUSD": per, "fullVolumeUSD": round(per * remaining, 2),
            "note": f"Tips buy pages at {SUSTAIN_MULT}x raw model cost — "
                    "the margin keeps the archive sustainable; unspent margin "
                    "translates more pages."}


def sponsor_enqueue(data):
    """Record one verified Ko-fi event. Returns (accepted, status). Never raises:
    a tip that names no manuscript is kept as 'unmatched' (money arrived —
    it must stay visible for manual assignment), and a replayed transaction id
    is ignored ('duplicate').

    TRANSLATE jobs get a page budget: the tip (FX'd to USD) divided by the
    tier's per-page suggested price — so a small gift honestly translates a few
    pages and a large one many, instead of any tip implying a whole volume.
    Any tip > 0 buys at least one page; over-granting a page costs cents."""
    txn = str(data.get("kofi_transaction_id") or "")[:80]
    if not txn:
        return False, "no transaction id"
    m = _SPONSOR_RE.search(str(data.get("message") or ""))
    kind = m.group(1).lower() if m else None
    mid = int(m.group(2)) if m else None
    try:
        amt = float(data.get("amount") or 0)
    except (TypeError, ValueError):
        amt = 0.0
    usd = amt * FX_TO_USD.get(str(data.get("currency") or "USD").upper(), 1.0)
    pages_budget = None
    if kind == "translate" and mid:
        q = translate_quote(mid)
        if q:
            pages_budget = max(1, int(usd / q["perPageUSD"])) if usd > 0 else 0
            pages_budget = min(pages_budget, max(q["remainingPages"], 1))
    job = {
        "txn": txn,
        "name": (str(data.get("from_name") or "Supporter")[:80]
                 if data.get("is_public", True) else "Anonymous"),
        "amount": str(data.get("amount") or ""),
        "currency": str(data.get("currency") or ""),
        "kind": kind or "",
        "mid": mid,
        "pages": pages_budget,
        "status": "queued" if m else "unmatched",
        "log": "",
        "created": datetime.now(timezone.utc).isoformat(),
        "finished": None,
    }
    with _sponsor_lock:
        store = load_json(SPONSOR_PATH, {"jobs": []})
        if any(j["txn"] == txn for j in store["jobs"]):
            return False, "duplicate"
        store["jobs"].append(job)
        save_json(SPONSOR_PATH, store)
    return True, job["status"]


def _sponsor_update(txn, **fields):
    with _sponsor_lock:
        store = load_json(SPONSOR_PATH, {"jobs": []})
        for j in store["jobs"]:
            if j["txn"] == txn:
                j.update(fields)
        save_json(SPONSOR_PATH, store)


def sponsor_jobs_snapshot(limit=20):
    """Public view of the queue, newest first — supporter name as Ko-fi gave it
    (or Anonymous), manuscript, status. The log tail is included once a job ran:
    the sponsor deserves to see what their merit bought."""
    with _sponsor_lock:
        store = load_json(SPONSOR_PATH, {"jobs": []})
    out = []
    for j in reversed(store["jobs"][-limit:]):
        title = ""
        if j.get("mid"):
            conn = connect()
            try:
                r = conn.execute("SELECT title_english, title_thai FROM manuscripts "
                                 "WHERE id=?", (j["mid"],)).fetchone()
                title = (r["title_english"] or r["title_thai"] or "") if r else ""
            finally:
                conn.close()
        out.append({"name": j["name"], "amount": j["amount"], "currency": j["currency"],
                    "kind": j.get("kind") or "ocr", "pages": j.get("pages"),
                    "mid": j.get("mid"), "title": title, "status": j["status"],
                    "created": j["created"], "logTail": (j.get("log") or "")[-400:]})
    return {"jobs": out, "kofi": "https://ko-fi.com/defiantchiangmai",
            "howTo": "Tip with a message like: TRANSLATE 6968 (or OCR 6968)"}


def _run_sponsored_translate(job):
    """Run a paid translation batch by shelling out to the crawler repo's
    translate.py (which owns PDF rendering, the vision call, TOC refresh).
    Returns (status, log). If no ANTHROPIC_API_KEY is set, the job is left
    queued — a sponsor's money must wait for the engine, never evaporate."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return ("queued", "waiting: translation engine key not configured on "
                          "this server yet — job will run once it is\n")
    script = CATALOG_DB.parent.parent / "translate.py"
    if not script.is_file():
        return ("error", f"translate.py not found at {script}\n")
    proc = subprocess.run(
        [sys.executable, str(script), "--only", str(job["mid"]),
         "--limit", str(job.get("pages") or 1)],
        capture_output=True, text=True, timeout=3600,
        cwd=str(script.parent))
    log = (proc.stdout or "") + (proc.stderr or "")
    return ("done" if proc.returncode == 0 else "error", log)


def _sponsor_worker():
    """Daemon loop: run queued sponsor jobs one at a time, sharing _job_lock with
    the local /api/ocr path so two heavy jobs never fight over the machine."""
    while True:
        time.sleep(20)
        nxt = None
        try:
            with _sponsor_lock:
                store = load_json(SPONSOR_PATH, {"jobs": []})
                nxt = next((j for j in store["jobs"] if j["status"] == "queued"), None)
            if not nxt:
                continue
            if not _job_lock.acquire(blocking=False):
                continue  # a local job is running; try again next tick
            try:
                if (nxt.get("kind") or "ocr") == "translate":
                    # cheap pre-check without marking the job running, so a
                    # missing key leaves it cleanly queued instead of flapping
                    if not os.environ.get("ANTHROPIC_API_KEY"):
                        if "waiting:" not in (nxt.get("log") or ""):
                            _sponsor_update(nxt["txn"],
                                            log="waiting: translation engine key not "
                                                "configured on this server yet\n")
                        continue
                    _sponsor_update(nxt["txn"], status="running")
                    status, log = _run_sponsored_translate(nxt)
                    _sponsor_update(nxt["txn"], status=status, log=log[-8000:],
                                    finished=datetime.now(timezone.utc).isoformat()
                                    if status in ("done", "error") else None)
                else:
                    _sponsor_update(nxt["txn"], status="running")
                    chunks = []

                    def write(s):
                        chunks.append(s)

                    run_ocr(nxt["mid"], "tha", write)
                    _sponsor_update(nxt["txn"], status="done",
                                    log="".join(chunks)[-8000:],
                                    finished=datetime.now(timezone.utc).isoformat())
            finally:
                _job_lock.release()
        except Exception as e:
            # Never let one bad job kill the worker; mark and move on.
            try:
                if nxt:
                    _sponsor_update(nxt["txn"], status="error",
                                    log=f"{type(e).__name__}: {e}")
            except Exception:
                pass


# ---------------------------- widgets: GIS + introspection --------------------
# ARCHITECTURE (see WIDGETS.md): a widget is one snapshot function registered in
# WIDGETS. That single registration buys it, uniformly:
#   /api/w/<name>       the data, as JSON (machine door)
#   /w/<name>           a standalone, SHAREABLE page — own title/OG description
#                       (links unfurl properly), share bar (copy link / copy
#                       iframe embed / download data), minimal chrome
#   /w/<name>?embed=1   chromeless, for <iframe> embedding anywhere
# Widgets read catalog.db or the wiki's own data/ files; they never write.
# Add a widget = write snapshot fn + renderer JS + one WIDGETS entry.

# --- GIS substrate: all-province centroids (approx capitals), Thai-keyed; the
# manuscripts' English province names join via inverted PROVINCE_EN.
THAI_PROVINCE_COORDS = {
    "กรุงเทพมหานคร": (13.75, 100.50), "นนทบุรี": (13.86, 100.51), "ปทุมธานี": (14.02, 100.53),
    "สมุทรปราการ": (13.60, 100.60), "สมุทรสาคร": (13.55, 100.27), "สมุทรสงคราม": (13.41, 100.00),
    "นครปฐม": (13.82, 100.06), "พระนครศรีอยุธยา": (14.35, 100.57), "อ่างทอง": (14.59, 100.46),
    "ลพบุรี": (14.80, 100.65), "สิงห์บุรี": (14.89, 100.40), "ชัยนาท": (15.19, 100.13),
    "สระบุรี": (14.53, 100.91), "นครนายก": (14.20, 101.21), "สุพรรณบุรี": (14.47, 100.12),
    "เชียงใหม่": (18.79, 98.98), "เชียงราย": (19.91, 99.83), "ลำปาง": (18.29, 99.49),
    "ลำพูน": (18.58, 99.01), "แม่ฮ่องสอน": (19.30, 97.97), "แพร่": (18.14, 100.14),
    "น่าน": (18.78, 100.77), "พะเยา": (19.17, 99.90), "อุตรดิตถ์": (17.62, 100.10),
    "ตาก": (16.87, 99.13), "สุโขทัย": (17.01, 99.82), "พิษณุโลก": (16.82, 100.27),
    "พิจิตร": (16.44, 100.35), "กำแพงเพชร": (16.48, 99.52), "นครสวรรค์": (15.70, 100.14),
    "อุทัยธานี": (15.38, 100.02), "เพชรบูรณ์": (16.42, 101.16), "นครราชสีมา": (14.98, 102.10),
    "บุรีรัมย์": (14.99, 103.10), "สุรินทร์": (14.88, 103.49), "ศรีสะเกษ": (15.12, 104.32),
    "อุบลราชธานี": (15.24, 104.85), "ยโสธร": (15.79, 104.15), "ชัยภูมิ": (15.81, 102.03),
    "อำนาจเจริญ": (15.86, 104.63), "หนองบัวลำภู": (17.20, 102.44), "ขอนแก่น": (16.43, 102.84),
    "อุดรธานี": (17.41, 102.79), "เลย": (17.49, 101.72), "หนองคาย": (17.88, 102.74),
    "มหาสารคาม": (16.18, 103.30), "ร้อยเอ็ด": (16.05, 103.65), "กาฬสินธุ์": (16.43, 103.51),
    "สกลนคร": (17.16, 104.15), "นครพนม": (17.39, 104.77), "มุกดาหาร": (16.54, 104.72),
    "บึงกาฬ": (18.36, 103.65), "ชลบุรี": (13.36, 100.98), "ระยอง": (12.68, 101.28),
    "จันทบุรี": (12.61, 102.10), "ตราด": (12.24, 102.51), "ฉะเชิงเทรา": (13.69, 101.07),
    "ปราจีนบุรี": (14.05, 101.37), "สระแก้ว": (13.82, 102.06), "ราชบุรี": (13.53, 99.81),
    "กาญจนบุรี": (14.02, 99.53), "เพชรบุรี": (13.11, 99.94), "ประจวบคีรีขันธ์": (11.81, 99.80),
    "นครศรีธรรมราช": (8.44, 99.96), "กระบี่": (8.09, 98.91), "พังงา": (8.45, 98.53),
    "ภูเก็ต": (7.88, 98.39), "สุราษฎร์ธานี": (9.14, 99.33), "ระนอง": (9.96, 98.64),
    "ชุมพร": (10.49, 99.18), "สงขลา": (7.19, 100.60), "สตูล": (6.62, 100.07),
    "ตรัง": (7.56, 99.61), "พัทลุง": (7.62, 100.07), "ปัตตานี": (6.87, 101.25),
    "ยะลา": (6.54, 101.28), "นราธิวาส": (6.43, 101.82),
}

TRAFFIC_PATH = DATA / "traffic.jsonl"
_traffic_lock = threading.Lock()
_BOT_RE = re.compile(r"bot|crawl|spider|slurp|gptbot|claudebot|perplexity|bytespider|"
                     r"ccbot|petalbot|amazonbot|applebot|facebookexternalhit", re.I)


def _record_traffic(handler, path):
    """One JSONL line per request — the introspection substrate. Privacy by
    construction: the client IP is salted-hashed per DAY (rough uniques without
    ever storing an address), query VALUES are dropped (paths only), UA truncated.
    Never raises; never blocks a response for long (file append under lock)."""
    try:
        if path == "/favicon.svg":
            return
        ip = handler.client_address[0]
        xff = handler.headers.get("X-Forwarded-For", "")
        real = (xff.split(",")[0].strip() or ip) if xff else ip
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        visitor = hashlib.sha256(f"{day}|{real}".encode()).hexdigest()[:12]
        ua = (handler.headers.get("User-Agent") or "")[:140]
        bm = _BOT_RE.search(ua)
        rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "p": path,
               "s": ("api" if path.startswith(("/api/", "/download/")) else
                     "img" if path.startswith(("/img", "/pimg")) else "page"),
               "a": (bm.group(0).lower() if bm else "human"),
               "v": visitor, "proxied": bool(xff)}
        with _traffic_lock:
            if TRAFFIC_PATH.exists() and TRAFFIC_PATH.stat().st_size > 20_000_000:
                TRAFFIC_PATH.replace(TRAFFIC_PATH.with_suffix(".jsonl.1"))  # keep one gen
            with open(TRAFFIC_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def geo_widget():
    """The two-layer GIS view: WHERE THE MANUSCRIPTS COME FROM (provenance,
    the antique layer) vs WHERE THE AMULETS SELL FROM (market seller provinces,
    the living layer) — one province table, both counts, plus centroids. The
    core corpus↔market seam, made geographic."""
    out = {"dbPresent": db_present(), "provinces": [], "unplaced": [],
           "totals": {"mss": 0, "market": 0}}
    if not db_present():
        return out
    en2th = {v: k for k, v in PROVINCE_EN.items()}
    conn = connect()
    try:
        mss = {r["p"]: r["n"] for r in conn.execute(
            "SELECT provenance_province p, COUNT(*) n FROM manuscripts "
            "WHERE provenance_province<>'' AND provenance_province IS NOT NULL "
            "GROUP BY p")}
        market = {r["p"]: r["n"] for r in conn.execute(
            "SELECT location_text p, COUNT(*) n FROM items "
            "WHERE method='commerce' AND location_text<>'' AND location_text IS NOT NULL "
            "GROUP BY p")}
    finally:
        conn.close()
    merged = {}
    for en_name, n in mss.items():
        th = en2th.get(en_name, en_name)
        merged.setdefault(th, {"mss": 0, "market": 0})["mss"] += n
    for th_name, n in market.items():
        merged.setdefault(th_name, {"mss": 0, "market": 0})["market"] += n
    for th, counts in sorted(merged.items(), key=lambda x: -(x[1]["mss"] + x[1]["market"])):
        coord = THAI_PROVINCE_COORDS.get(th)
        row = {"nameTh": th, "nameEn": PROVINCE_EN.get(th, th),
               "mss": counts["mss"], "market": counts["market"]}
        if coord:
            row["lat"], row["lon"] = coord
            out["provinces"].append(row)
        else:
            out["unplaced"].append(row)
        out["totals"]["mss"] += counts["mss"]
        out["totals"]["market"] += counts["market"]
    # Province outlines travel WITH the data. Without them the widget drew dots
    # on an empty rectangle -- confetti, with no way to tell it was Thailand.
    # Tiles would fix that too, but tiles need a network and this widget has to
    # survive as one saved file.
    out["outlines"] = th_province_outlines()
    return out


_TH_PROVINCES_CACHE = None


def th_province_outlines():
    """Simplified outer rings for all 77 Thai provinces (Natural Earth, public
    domain — see data/th-provinces.SOURCE.txt).

    Shipped INSIDE the widget payload rather than fetched: /w/geo has to work as
    a single saved file with no network, and map tiles cannot do that. 44 KB
    buys the difference between a real map and a scatter of dots on a blank
    rectangle."""
    global _TH_PROVINCES_CACHE
    if _TH_PROVINCES_CACHE is None:
        f = Path(__file__).resolve().parent / "data" / "th-provinces.json"
        try:
            raw = json.loads(f.read_text())
        except Exception:
            raw = {}
        # Natural Earth spells a few provinces in full where this site uses the
        # short form. Only the outline key is renamed, so the join succeeds.
        ALIAS = {"Phra Nakhon Si Ayutthaya": "Ayutthaya"}
        _TH_PROVINCES_CACHE = {ALIAS.get(k, k): v for k, v in raw.items()}
    return _TH_PROVINCES_CACHE


def geo_geojson():
    """The same data as a standards-compliant GeoJSON FeatureCollection — drop it
    into QGIS/kepler.gl/Felt and it just works. Interop IS shareability."""
    g = geo_widget()
    feats = [{"type": "Feature",
              "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]},
              "properties": {"name_th": p["nameTh"], "name_en": p["nameEn"],
                             "manuscripts": p["mss"], "market_listings": p["market"]}}
             for p in g["provinces"]]
    return {"type": "FeatureCollection",
            "name": "lanna-wichaa-provinces",
            "description": "Manuscript provenance vs living amulet-market activity, "
                           "per Thai province. CC-BY 4.0.",
            "features": feats}


def traffic_widget(days=14):
    """Who is reading the archive: daily volume split human/bot, the crawler
    leaderboard (GPTBot, ClaudeBot…), busiest endpoints, rough uniques. All from
    the wiki's own privacy-preserving log — no third-party analytics, ever."""
    out = {"days": [], "bots": [], "paths": [], "api": [], "totals":
           {"requests": 0, "visitors": 0, "botShare": 0.0}, "windowDays": days}
    if not TRAFFIC_PATH.exists():
        return out
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    from collections import Counter, defaultdict as dd
    per_day = dd(lambda: {"human": 0, "bot": 0})
    bots, paths, api, visitors = Counter(), Counter(), Counter(), set()
    nbot = ntot = 0
    with _traffic_lock, open(TRAFFIC_PATH, encoding="utf-8") as f:
        for ln in f:
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("ts", "") < cutoff:
                continue
            ntot += 1
            day = r["ts"][:10]
            kind = "bot" if r["a"] != "human" else "human"
            per_day[day][kind] += 1
            if kind == "bot":
                nbot += 1
                bots[r["a"]] += 1
            visitors.add(r["v"])
            if r["s"] == "api":
                api[r["p"]] += 1
            elif r["s"] == "page":
                paths[r["p"]] += 1
    out["days"] = [{"day": d, **per_day[d]} for d in sorted(per_day)]
    out["bots"] = [{"name": k, "n": v} for k, v in bots.most_common(10)]
    out["paths"] = [{"path": k, "n": v} for k, v in paths.most_common(10)]
    out["api"] = [{"path": k, "n": v} for k, v in api.most_common(10)]
    out["totals"] = {"requests": ntot, "visitors": len(visitors),
                     "botShare": round(nbot / ntot, 3) if ntot else 0.0}
    return out


# name -> (snapshot fn, title, one-line description used for OG unfurls)
WIDGETS = {
    "geo": (geo_widget, "Where the tradition lives",
            "Manuscript provenance vs today's amulet market, per Thai province — "
            "the antique and living layers of the wichaa tradition on one map."),
    "traffic": (traffic_widget, "Who is reading the archive",
                "Humans, crawlers, and API consumers visiting wichaa "
                "— self-hosted, privacy-preserving introspection."),
}

_WIDGET_JS = {
 "geo": r"""
const W=560,H=620,pad=14;
const pts=D.provinces; if(!pts.length){main.append(el('p',{textContent:'No geographic data yet.'}));return;}
const OUT=D.outlines||{};
// Bounds come from the OUTLINES when we have them, so the country sits in frame
// whether or not every province has data.
let lats=[],lons=[];
for(const rings of Object.values(OUT))for(const r of rings)for(const c of r){lons.push(c[0]);lats.push(c[1]);}
if(!lats.length){lats=pts.map(p=>p.lat);lons=pts.map(p=>p.lon);}
const la0=Math.min(...lats),la1=Math.max(...lats),lo0=Math.min(...lons),lo1=Math.max(...lons);
// Equirectangular with a cos(lat) correction: without it Thailand comes out
// noticeably fat, because a degree of longitude is ~0.95 of a degree of
// latitude at this latitude.
const K=Math.cos((la0+la1)/2*Math.PI/180);
const wDeg=(lo1-lo0)*K, hDeg=(la1-la0);
const sc=Math.min((W-2*pad)/wDeg,(H-2*pad)/hDeg);
const ox=(W-wDeg*sc)/2, oy=(H-hDeg*sc)/2;
const X=lo=>ox+(lo-lo0)*K*sc, Y=la=>oy+(la1-la)*sc;
const svg=(t,a={},k)=>{const e=document.createElementNS('http://www.w3.org/2000/svg',t);for(const[k2,v]of Object.entries(a))e.setAttribute(k2,v);if(k!=null)e.textContent=k;return e;};
const s=svg('svg',{viewBox:`0 0 ${W} ${H}`,role:'img','aria-label':'Thailand by province: manuscript provenance and amulet-market listings'});
s.style.cssText='width:100%;max-width:430px;height:auto;background:#eef4f3;border-radius:12px;display:block;margin:0 auto';

// --- the land itself, shaded by manuscript count ---------------------------
const byName={}; for(const p of pts) byName[p.nameEn]=p;
const mMax=Math.max(...pts.map(p=>p.mss),1), kMax=Math.max(...pts.map(p=>p.market),1);
const land=svg('g');
for(const [nm,rings] of Object.entries(OUT)){
  const rec=byName[nm], n=rec?rec.mss:0;
  // sqrt so the many small counts stay visible against the few huge ones
  const t=n?Math.sqrt(n)/Math.sqrt(mMax):0;
  const fill=n?`rgba(31,78,74,${(0.10+0.72*t).toFixed(3)})`:'#dde7e4';
  for(const r of rings){
    const d='M'+r.map(c=>`${X(c[0]).toFixed(1)},${Y(c[1]).toFixed(1)}`).join('L')+'Z';
    const path=svg('path',{d:d,fill:fill,stroke:'#ffffff','stroke-width':.7,'stroke-linejoin':'round'});
    path.append(svg('title',{},`${nm}${rec?`\n${rec.mss} manuscripts · ${rec.market} listings`:'\nno records'}`));
    land.append(path);
  }
}
s.append(land);

// --- market listings on top, as gold circles -------------------------------
const mk=svg('g');
for(const p of pts){
  if(!p.market) continue;
  const r=2.5+15*Math.sqrt(p.market)/Math.sqrt(kMax);
  const c=svg('circle',{cx:X(p.lon).toFixed(1),cy:Y(p.lat).toFixed(1),r:r.toFixed(1),
                        fill:'#b8892f',opacity:.8,stroke:'#fff','stroke-width':1});
  c.append(svg('title',{},`${p.nameEn} · ${p.nameTh}\n${p.mss} manuscripts · ${p.market} listings`));
  mk.append(c);
}
s.append(mk);
main.append(s);

// --- legend, in words as well as colour ------------------------------------
const lg=el('div',{className:'geolegend'});
lg.innerHTML="<span><i class='sw' style='background:rgba(31,78,74,.72)'></i>"
 +"darker = more manuscripts from there</span>"
 +"<span><i class='sw' style='background:#dde7e4'></i>no manuscripts recorded</span>"
 +"<span><i class='sw' style='background:#b8892f;border-radius:50%'></i>"
 +"amulets sold from there today</span>"
 +"<span class=geosrc>Outlines: Natural Earth (public domain)</span>";
main.append(lg);

const nMss=pts.filter(p=>p.mss).length, nMkt=pts.filter(p=>p.market).length;
const tot=el('p',{className:'muted'});
tot.textContent=`${D.totals.mss.toLocaleString()} manuscripts and ${D.totals.market.toLocaleString()} market listings across ${pts.length} provinces.`;
main.append(tot);
const say=el('p',{className:'muted'});
say.textContent=`The two layers barely overlap: manuscripts survive in ${nMss} provinces, almost all of them the Lanna north, while amulets sell from ${nMkt}. Written in one place, traded across the country.`;
main.append(say);
if(D.unplaced&&D.unplaced.length){
  const u=el('p',{className:'muted'});
  u.textContent=`${D.unplaced.length} province${D.unplaced.length===1?'':'s'} could not be placed on the map.`;
  main.append(u);
}
""",
 "traffic": r"""
if(!D.totals.requests){main.append(el('p',{textContent:'No traffic recorded yet — the log starts with the first visit after this feature shipped.'}));return;}
const t=el('p',{},[`${D.totals.requests.toLocaleString()} requests · ~${D.totals.visitors.toLocaleString()} visitors · ${(100*D.totals.botShare).toFixed(0)}% bots — last ${D.windowDays} days`]);
t.style.fontWeight='700'; main.append(t);
const strip=el('div'); strip.style.cssText='display:flex;align-items:flex-end;gap:3px;height:90px;margin:10px 0';
const mx=Math.max(...D.days.map(d=>d.human+d.bot),1);
for(const d of D.days){const col=el('div'); col.title=`${d.day}: ${d.human} human · ${d.bot} bot`;
  col.style.cssText='flex:1;display:flex;flex-direction:column;justify-content:flex-end;height:100%';
  const b=el('div'); b.style.cssText=`background:#b8892f;height:${90*d.bot/mx}px`;
  const h=el('div'); h.style.cssText=`background:#1F4E4A;height:${90*d.human/mx}px`;
  col.append(b,h); strip.append(col);}
main.append(strip);
const lists=[['Crawler leaderboard',D.bots,'name'],['Top pages',D.paths,'path'],['Top API endpoints',D.api,'path']];
const row=el('div'); row.style.cssText='display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px';
for(const[title,items,key]of lists){const c=el('div');c.append(el('h3',{textContent:title}));
  for(const it of items){const d=el('div');d.style.cssText='font-size:13px;padding:2px 0;display:flex;justify-content:space-between';
    d.append(el('span',{textContent:it[key]}),el('strong',{textContent:it.n.toLocaleString()}));c.append(d);}
  if(!items.length)c.append(el('p',{className:'muted',textContent:'—'}));
  row.append(c);}
main.append(row);
""",
}


# --- the market-analysis trio: pricing ranges, regional interests, trends ------
def _median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else None


def prices_widget():
    """Pricing ranges across the living market: a log-bucket histogram, the
    median per term, and the extremes — all THB (SG joins when its crawl lands)."""
    out = {"buckets": [], "byTerm": [], "stats": {}}
    if not db_present():
        return out
    conn = connect()
    try:
        prices = [r[0] for r in conn.execute(
            "SELECT price_value FROM items WHERE method='commerce' "
            "AND price_value IS NOT NULL AND price_currency='THB'")]
        rows = conn.execute(
            "SELECT t.term_raw term, i.price_value p FROM tags t "
            "JOIN items i ON i.id=t.item_id "
            "WHERE t.method='commerce' AND i.price_value IS NOT NULL "
            "AND i.price_currency='THB'").fetchall()
    finally:
        conn.close()
    if not prices:
        return out
    edges = [(0, 50), (50, 100), (100, 300), (300, 1000), (1000, 5000),
             (5000, 20000), (20000, 10**9)]
    labels = ["<฿50", "฿50–100", "฿100–300", "฿300–1k", "฿1k–5k", "฿5k–20k", ">฿20k"]
    out["buckets"] = [{"label": lb, "n": sum(1 for p in prices if lo <= p < hi)}
                      for (lo, hi), lb in zip(edges, labels)]
    per = {}
    for r in rows:
        per.setdefault(r["term"], []).append(r["p"])
    out["byTerm"] = sorted(
        [{"term": t, "n": len(v), "median": _median(v),
          "min": min(v), "max": max(v)} for t, v in per.items() if len(v) >= 15],
        key=lambda x: -x["median"])[:14]
    ps = sorted(prices)
    out["stats"] = {"n": len(ps), "median": ps[len(ps)//2],
                    "p90": ps[int(len(ps)*.9)], "max": ps[-1]}
    return out


def regions_widget():
    """Regional interests: what each province's market actually trades — item
    volume, median price, and the top terms there. The desire-paths of luck,
    by geography."""
    out = {"provinces": []}
    if not db_present():
        return out
    conn = connect()
    try:
        provs = conn.execute(
            "SELECT location_text p, COUNT(*) n FROM items WHERE method='commerce' "
            "AND location_text<>'' GROUP BY p HAVING n>=15 ORDER BY n DESC").fetchall()
        for pr in provs:
            terms = conn.execute(
                "SELECT t.term_raw term, COUNT(*) n FROM tags t JOIN items i ON i.id=t.item_id "
                "WHERE t.method='commerce' AND i.location_text=? "
                "GROUP BY term ORDER BY n DESC LIMIT 3", (pr["p"],)).fetchall()
            med = _median([r[0] for r in conn.execute(
                "SELECT price_value FROM items WHERE method='commerce' "
                "AND location_text=? AND price_value IS NOT NULL", (pr["p"],))])
            out["provinces"].append({
                "nameTh": pr["p"], "nameEn": PROVINCE_EN.get(pr["p"], pr["p"]),
                "n": pr["n"], "median": med,
                "topTerms": [{"term": t["term"], "n": t["n"]} for t in terms]})
    finally:
        conn.close()
    return out


def trends_widget():
    """Market motion over time: new listings per day, overall and for the
    leading terms. The axis is young (crawling began 2026-07-10) and grows with
    every daily refresh — early charts are honest about that."""
    out = {"days": [], "terms": [], "note": ""}
    if not db_present():
        return out
    conn = connect()
    try:
        days = conn.execute(
            "SELECT date(first_seen) d, COUNT(*) n FROM items WHERE method='commerce' "
            "GROUP BY d ORDER BY d").fetchall()
        top = [r["term"] for r in conn.execute(
            "SELECT t.term_raw term, COUNT(*) n FROM tags t "
            "WHERE t.method='commerce' AND t.item_id IS NOT NULL "
            "GROUP BY term ORDER BY n DESC LIMIT 5").fetchall()]
        series = []
        for term in top:
            pts = conn.execute(
                "SELECT date(i.first_seen) d, COUNT(*) n FROM tags t "
                "JOIN items i ON i.id=t.item_id "
                "WHERE t.method='commerce' AND t.term_raw=? GROUP BY d ORDER BY d",
                (term,)).fetchall()
            series.append({"term": term, "points": [{"day": p["d"], "n": p["n"]} for p in pts]})
    finally:
        conn.close()
    out["days"] = [{"day": r["d"], "n": r["n"]} for r in days]
    out["terms"] = series
    if len(out["days"]) < 14:
        out["note"] = (f"Time axis is {len(out['days'])} day(s) old — the daily "
                       "market refresh extends it every day; trend shapes firm up "
                       "as history accrues.")
    return out


WIDGETS.update({
    "prices": (prices_widget, "What luck costs",
               "Pricing ranges across the living Thai amulet market — histogram, "
               "median by charm type, and the extremes."),
    "regions": (regions_widget, "Regional interests",
                "What each Thai province's amulet market actually trades — "
                "volume, price level, and the charms it favours."),
    "trends": (trends_widget, "Market motion",
               "New amulet listings per day, overall and by leading charm type — "
               "a time axis that grows with every daily crawl."),
})

_BARLIST_JS = r"""
const bar=(label,n,mx,extra)=>{const row=el('div');row.style.cssText='display:grid;grid-template-columns:170px 1fr 90px;gap:8px;align-items:center;font-size:13px;padding:2px 0';
row.append(el('span',{textContent:label,style:'white-space:nowrap;overflow:hidden;text-overflow:ellipsis'}),
el('div',{style:`height:14px;border-radius:4px;background:#1F4E4A;width:${Math.max(2,100*n/mx)}%`}),
el('span',{textContent:extra??n.toLocaleString(),style:'text-align:right;color:#3a4a47'}));return row;};
"""

_WIDGET_JS.update({
 "prices": _BARLIST_JS + r"""
main.append(el('p',{style:'font-weight:700',textContent:`${D.stats.n.toLocaleString()} priced listings · median ฿${D.stats.median.toLocaleString()} · p90 ฿${D.stats.p90.toLocaleString()} · top ฿${D.stats.max.toLocaleString()}`}));
main.append(el('h3',{textContent:'Price distribution'}));
const bmx=Math.max(...D.buckets.map(b=>b.n),1);
for(const b of D.buckets) main.append(bar(b.label,b.n,bmx));
main.append(el('h3',{textContent:'Median price by charm type'}));
const tmx=Math.max(...D.byTerm.map(t=>t.median),1);
for(const t of D.byTerm) main.append(bar(t.term,t.median,tmx,`฿${t.median.toLocaleString()} (n=${t.n})`));
""",
 "regions": _BARLIST_JS + r"""
const mx=Math.max(...D.provinces.map(p=>p.n),1);
for(const p of D.provinces){
  const card=el('div'); card.style.cssText='border:1px solid #c9d6d2;border-radius:10px;padding:10px 14px;margin:8px 0;background:#fff';
  card.append(el('div',{style:'font-weight:700',textContent:`${p.nameEn} · ${p.nameTh} — ${p.n.toLocaleString()} listings`+(p.median?` · median ฿${p.median.toLocaleString()}`:'')}));
  card.append(bar('volume',p.n,mx,''));
  card.append(el('div',{style:'font-size:13px;color:#3a4a47',textContent:'favours: '+p.topTerms.map(t=>`${t.term} (${t.n})`).join(' · ')}));
  main.append(card);}
""",
 "trends": _BARLIST_JS + r"""
if(D.note) main.append(el('p',{className:'muted',textContent:D.note}));
main.append(el('h3',{textContent:'New listings per day'}));
const mx=Math.max(...D.days.map(d=>d.n),1);
for(const d of D.days) main.append(bar(d.day,d.n,mx));
main.append(el('h3',{textContent:'Leading charm types (new per day)'}));
for(const s of D.terms){
  main.append(el('div',{style:'font-weight:700;font-size:14px;margin-top:8px',textContent:s.term}));
  const smx=Math.max(...s.points.map(p=>p.n),1);
  for(const p of s.points) main.append(bar(p.day,p.n,smx));}
""",
})


# --- the products shelf + the syndicated answers feed --------------------------
def products_widget(limit=24):
    """The newest listings on the living market, as products: title, price,
    province, charm terms, and the source link. A shelf for discovery and
    analysis — verbatim catalogue rows, not a storefront."""
    out = {"items": [], "totals": {"listings": 0, "live": 0}, "shown": 0}
    if not db_present():
        return out
    conn = connect()
    try:
        has_dead = any(r[1] == "dead_since"
                       for r in conn.execute("PRAGMA table_info(items)"))
        live_where = " AND (dead_since IS NULL OR dead_since='')" if has_dead else ""
        out["totals"]["listings"] = conn.execute(
            "SELECT COUNT(*) FROM items WHERE method='commerce'").fetchone()[0]
        out["totals"]["live"] = conn.execute(
            "SELECT COUNT(*) FROM items WHERE method='commerce'" + live_where
        ).fetchone()[0]
        rows = conn.execute(
            "SELECT id, title_thai, title_english, price_value, price_currency, "
            "location_text, source_url, first_seen FROM items "
            "WHERE method='commerce'" + live_where +
            " ORDER BY first_seen DESC, id DESC LIMIT ?", (limit,)).fetchall()
        for r in rows:
            terms = [t[0] for t in conn.execute(
                "SELECT term_raw FROM tags WHERE method='commerce' AND item_id=? "
                "LIMIT 4", (r["id"],))]
            out["items"].append({
                "titleTh": r["title_thai"] or "", "titleEn": r["title_english"] or "",
                "price": r["price_value"], "currency": r["price_currency"] or "THB",
                "locationTh": r["location_text"] or "",
                "locationEn": PROVINCE_EN.get(r["location_text"] or "", ""),
                "url": r["source_url"] or "",
                "firstSeen": (r["first_seen"] or "")[:10],
                "terms": terms})
    finally:
        conn.close()
    out["shown"] = len(out["items"])
    return out


# The sibling Thai Answers project publishes a JSON Feed (jsonfeed.org — the open
# successor to RSS); this widget is its first subscriber. The path is a local file
# now and becomes a URL fetch when that site deploys; the widget's data shape
# doesn't change either way.
ANSWERS_FEED = Path(os.environ.get(
    "THAI_ANSWERS_FEED", HERE.parent / "thai-answers" / "docs" / "feed.json"))


def answers_widget():
    """Evergreen answers to the questions people actually ask about Thailand,
    syndicated from the Thai Answers project via JSON Feed. Feed not published
    yet → honest empty state."""
    out = {"feedPresent": False, "feedTitle": "", "items": []}
    try:
        feed = json.loads(ANSWERS_FEED.read_text(encoding="utf-8"))
    except Exception:
        return out
    out["feedPresent"] = True
    out["feedTitle"] = feed.get("title") or "Thai Answers"
    for it in feed.get("items", [])[:12]:
        out["items"].append({
            "title": it.get("title") or "",
            "url": it.get("url") or it.get("external_url") or "",
            "summary": it.get("summary") or (it.get("content_text") or "")[:300],
            "date": (it.get("date_published") or "")[:10]})
    return out


WIDGETS.update({
    "products": (products_widget, "New on the market",
                 "The newest amulet listings the crawler has catalogued — title, "
                 "price, province, and charm type, verbatim from the living market."),
    "answers": (answers_widget, "Thai Answers",
                "Evergreen, source-marked answers to the questions people actually "
                "ask about Thailand — syndicated here via JSON Feed."),
})

_WIDGET_JS.update({
 "products": r"""
if(!D.items.length){main.append(el('p',{textContent:'No listings catalogued yet.'}));return;}
main.append(el('p',{style:'font-weight:700',textContent:`${D.totals.live.toLocaleString()} live listings of ${D.totals.listings.toLocaleString()} catalogued — the ${D.shown} newest below. A shelf, not a shop: rows are verbatim from the market crawl.`}));
for(const it of D.items){
  const card=el('div'); card.style.cssText='border:1px solid #c9d6d2;border-radius:10px;padding:10px 14px;margin:8px 0;background:#fff';
  const label=it.titleTh||it.titleEn||'(untitled listing)';
  const t=el('div',{style:'font-weight:700'});
  if(it.url) t.append(el('a',{href:it.url,target:'_blank',rel:'noopener',textContent:label}));
  else t.append(el('span',{textContent:label}));
  card.append(t);
  if(it.titleTh&&it.titleEn&&it.titleEn!==it.titleTh)
    card.append(el('div',{style:'font-size:13px;color:#3a4a47',textContent:it.titleEn}));
  const meta=[];
  if(it.price!=null) meta.push((it.currency==='THB'?'฿':it.currency+' ')+it.price.toLocaleString());
  if(it.locationEn||it.locationTh) meta.push(it.locationEn||it.locationTh);
  if(it.firstSeen) meta.push('first seen '+it.firstSeen);
  if(it.terms.length) meta.push(it.terms.join(' · '));
  card.append(el('div',{style:'font-size:13px;color:#3a4a47;margin-top:4px',textContent:meta.join(' — ')}));
  main.append(card);
}
""",
 "answers": r"""
if(!D.feedPresent){main.append(el('p',{textContent:'The Thai Answers feed has not been published yet — this widget lights up on its first build.'}));return;}
if(!D.items.length){main.append(el('p',{textContent:'The feed is live but carries no answers yet.'}));return;}
for(const it of D.items){
  const card=el('div'); card.style.cssText='border:1px solid #c9d6d2;border-radius:10px;padding:12px 16px;margin:8px 0;background:#fff';
  const t=el('div',{style:'font-weight:700;font-size:16px'});
  if(it.url) t.append(el('a',{href:it.url,target:'_blank',rel:'noopener',textContent:it.title}));
  else t.append(el('span',{textContent:it.title}));
  card.append(t);
  if(it.summary) card.append(el('p',{style:'font-size:14px;color:#3a4a47;margin:6px 0 0',textContent:it.summary}));
  if(it.date) card.append(el('div',{style:'font-size:12px;color:#3a4a47;opacity:.7;margin-top:4px',textContent:it.date}));
  main.append(card);
}
""",
})


def widgets_index_page():
    """/w/ — the front door of the analysis layer: every registered widget as a
    card. New widgets appear here automatically; sharing starts with seeing."""
    # 'traffic' is live-only (it counts requests to the running server) and is not
    # exported to the static site — skip it here so the public index never links a
    # page that isn't there.
    cards = "".join(
        f"<a class=wcard href='/w/{name}'><h2>{html.escape(title)}</h2>"
        f"<p>{html.escape(desc)}</p></a>"
        for name, (_fn, title, desc) in WIDGETS.items() if name != "traffic")
    css = (".wgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}"
           ".wcard{display:block;border:1px solid var(--line);border-radius:12px;background:#fff;"
           "padding:16px 18px;text-decoration:none;color:inherit}"
           ".wcard:hover{border-color:var(--teal)}"
           ".wcard h2{margin:0 0 6px;font-size:17px}.wcard p{margin:0;font-size:13px;color:var(--muted)}")
    body = ("<header><div><h1>Widgets</h1><p class=sub>Self-analysis of the archive "
            "and the living market — every view shareable, embeddable, and "
            "machine-readable</p></div>" + NAV + "</header>"
            f"<main><div class=wgrid>{cards}</div></main>")
    return page("Widgets — wichaa", css, body)


def _today_str():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def widget_page(name, embed=False, data=None):
    """A widget page. With `data`, the payload is baked in and the page makes NO
    network request at all -- that is the portable build: one file you can save,
    mail, or open on a plane, and it still draws. Without it, the page fetches
    its snapshot as before.

    Every widget on this site is meant to be portable, shareable and
    downloadable. Offering only a JSON download met one third of that: the DATA
    was portable but the WIDGET was not -- a saved page was a blank shell,
    because it fetched everything at runtime."""
    fn, title, desc = WIDGETS[name]
    share = "" if embed else (
        "<div class=sharebar>"
        "<button onclick=\"navigator.clipboard.writeText(location.href.split('?')[0])"
        ".then(()=>this.textContent='✓ copied')\">🔗 Copy link</button>"
        f"<button onclick=\"navigator.clipboard.writeText('<iframe src=&quot;'+location.origin+'/w/{name}?embed=1&quot; width=&quot;100%&quot; height=&quot;620&quot; frameborder=&quot;0&quot;></iframe>')"
        ".then(()=>this.textContent='✓ copied')\">📋 Copy embed code</button>"
        f"<a href='/w/{name}/{name}-offline.html' download>⬇ Whole widget (1 file)</a>"
        f"<a href='/api/w/{name}' download='{name}.json'>⬇ JSON</a>"
        + (f"<a href='/api/w/geo.geojson' download='lanna-provinces.geojson'>⬇ GeoJSON</a>"
           if name == "geo" else "")
        + "</div>")
    head = "" if embed else ("<header><div><h1>" + html.escape(title) + "</h1>"
                             "<p class=sub>" + html.escape(desc) + "</p></div>" + NAV + "</header>")
    css = (".geolegend{display:flex;gap:18px;flex-wrap:wrap;justify-content:center;"
           "margin:12px 0 4px;font-size:14px;color:var(--muted)}"
           ".geolegend span{display:flex;align-items:center;gap:7px}"
           ".geolegend .sw{width:15px;height:15px;border-radius:3px;display:inline-block}"
           ".geolegend .geosrc{opacity:.75;font-size:13px}"
           ".sharebar{display:flex;gap:10px;margin:0 0 14px;flex-wrap:wrap}"
           ".sharebar button,.sharebar a{font-size:13px;padding:6px 12px;cursor:pointer;"
           "border:1px solid var(--line);border-radius:8px;background:#fff;color:var(--ink);"
           "text-decoration:none}"
           + ("body{background:#fff}header{display:none}" if embed else ""))
    if data is None:
        loader = "fetch('/api/w/" + name + "').then(r=>r.json()).then(D=>{"
        banner = ""
    else:
        # No fetch: the snapshot IS the file. Same rule as the flight tool --
        # a saved copy that cannot refresh must say so, or an old number gets
        # mistaken for a live one.
        loader = ("Promise.resolve(" + json.dumps(data, separators=(",", ":"))
                  + ").then(D=>{")
        banner = ("<div class=frozen><b>Saved copy</b> \u2014 a snapshot taken "
                  + html.escape(_today_str()) + ". It cannot update itself. "
                  "The living version is at <a href='https://wichaa.net/w/"
                  + name + "/'>wichaa.net/w/" + name + "/</a>.</div>")
    css += (".frozen{background:#fbf1dc;border:2px solid #e5cf9a;color:#6b4a00;"
            "border-radius:10px;padding:12px 16px;margin:0 0 14px;font-size:15px}"
            ".frozen a{color:#6b4a00}")
    body = (head + "<main id=main>" + banner + share + "<p class=muted>Loading…</p></main>"
            "<script>"
            "const el=(t,p={},k=[])=>{const e=document.createElement(t);Object.assign(e,p);"
            "for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};"
            + loader +
            "const main=document.getElementById('main');"
            "main.querySelector('p.muted')?.remove();"
            + _WIDGET_JS[name] +
            "});</script>")
    # Only claim a card that has actually been rendered. Pointing og:image at a
    # missing file unfurls WORSE than the sitewide fallback -- the preview comes
    # back blank instead of generic. Masters live in publishing/cards/ (see
    # make_card.py); w__<name>.png is copied to /w/<name>/card.png at publish.
    card = Path(__file__).resolve().parent / "publishing" / "cards" / f"w__{name}.png"
    og = "/w/" + name + "/card.png" if card.is_file() else None
    return page(title + " — wichaa", css, body, description=desc,
                og_image=og, og_url="/w/" + name + "/")


# ---------------------------- UI ----------------------------
STYLE = """
  :root{
    --ink:#141b1a; --muted:#3a4a47; --line:#c9d6d2;
    --teal:#1F4E4A; --teal-ink:#ffffff; --bg:#f4f7f6; --card:#ffffff;
    --focus:#0b5cad; --gold:#8a5a00; --gold-bg:#fbf1dc; --ok:#0f6b3f;
    --prio:#7a1f1f; --prio-bg:#fbe6e6;
    --serif:"Sukhumvit Set","Noto Serif Thai",Thonburi,"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif;
  }
  *{box-sizing:border-box}
  /* This is the body stack for the whole wiki — every manuscript page, and every
     threads chip, which strings.py renders Thai FIRST by design. It named no
     Thai-capable family, so the Thai half of each chip fell to the browser's
     last-resort face while the English half got the chosen one: the site said
     Thai leads and then rendered it as an afterthought. Thai families go first
     (resolution is per-character, so Latin still reaches -apple-system), and
     Thai takes more leading than 1.55 because its marks stack above and below. */
  body{margin:0;font:17px/1.55 "Sukhumvit Set","Noto Sans Thai",Thonburi,-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:var(--ink);background:var(--bg)}
  :lang(th),.th{line-height:1.85}
  a{color:var(--focus)}
  header{background:linear-gradient(180deg,#245852,#1b4541);color:var(--teal-ink);padding:16px 24px;display:flex;align-items:center;gap:16px;flex-wrap:wrap;box-shadow:0 2px 10px #00000022}
  header h1{margin:0;font-size:24px;font-family:var(--serif);letter-spacing:.01em}
  .card>h2:first-child,.card>h2{font-family:var(--serif)}
  header .sub{color:#dfeae7;margin:0}
  /* flex-wrap is on the BASE rule, not just the <=760px block: the nav's 11 items
     are ~1217px wide, so without it every viewport under ~1250px (laptops included,
     not only phones) got a horizontal scrollbar. Wrapped rows stay right-aligned
     under the title so the header reads the same as it did on wide screens. */
  header nav{margin-left:auto;display:flex;flex-wrap:wrap;justify-content:flex-end;gap:10px}
  header nav a{color:#fff;text-decoration:none;font-weight:700;border:2px solid #ffffff66;border-radius:8px;padding:8px 14px}
  header nav a:hover{background:#ffffff22}
  header nav a.kofi{background:var(--gold-bg,#fbf1dc);color:var(--gold,#8a5a00);border-color:transparent}
  header nav a.kofi:hover{filter:brightness(0.96)}
  main{max-width:1080px;margin:0 auto;padding:20px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin:0 0 16px}
  button{font:inherit;font-weight:700;color:var(--teal-ink);background:var(--teal);border:2px solid var(--teal);border-radius:8px;padding:10px 16px;cursor:pointer;min-height:44px}
  button.secondary{background:#fff;color:var(--teal)}
  button:hover{background:#163b38;border-color:#163b38}
  button.secondary:hover{background:#eef4f2}
  input[type=text],input[type=search],select,textarea{width:100%;padding:10px 12px;font-size:16px;border:1px solid #6b7f7a;border-radius:8px;color:var(--ink);background:#fff}
  :focus-visible{outline:3px solid var(--focus);outline-offset:2px}
  .pill{display:inline-block;font-size:13px;font-weight:700;padding:2px 10px;border-radius:999px;border:1px solid var(--line);background:#eef2f1;color:var(--muted);margin:2px 4px 2px 0}
  .pill.script{background:var(--gold-bg);border-color:#e5cf9a;color:var(--gold)}
  .pill.prio{background:var(--prio-bg);border-color:#e0a3a3;color:var(--prio)}
  .cite-arch{display:inline-block;font-size:14px;font-weight:600;line-height:1.5;padding:0 9px;margin:0 3px;
    border:1px solid var(--line);border-radius:999px;background:#eef2f1;color:var(--muted);white-space:nowrap}
  a.cite-arch{color:#33534d}a.cite-arch:hover{text-decoration:none;border-color:#33534d}
  .cite-arch.quiet{background:#f2ede1;border-color:#ded5c2}
  .muted{color:var(--muted)}
  .thai{font-size:1.15em}
  .empty{padding:28px;text-align:center;color:var(--muted);border:1px dashed var(--line);border-radius:10px;background:#fff}
  /* Global overflow safety net: nothing should force the viewport wider than the
     phone. Images fluid; wide blocks (code, pre) scroll inside their own box. */
  img{max-width:100%;height:auto}
  pre,code{overflow-x:auto;max-width:100%}
  /* Mobile-responsive pass (dr's feedback, 2026-07-12): the header's nav had no
     wrap and no breakpoint, so its ~9 buttons overflowed and forced a horizontal
     scroll. Below 760px the nav drops under the title and wraps; padding, type,
     and card chrome all tighten so a phone reads the archive with no sideways
     scrolling. Touch targets stay >=40px tall. */
  @media(max-width:760px){
    header{padding:12px 16px;gap:6px 12px}
    header h1{font-size:20px}
    header .sub{font-size:13.5px;flex-basis:100%;order:3}
    /* full-width under the title here, so undo the base rule's right-alignment —
       left-aligned rows sit flush with the h1 instead of going ragged-left. */
    header nav{margin-left:0;width:100%;flex-wrap:wrap;justify-content:flex-start;gap:6px;order:2}
    header nav a{padding:8px 11px;font-size:14px;border-width:1px}
    main{padding:14px;max-width:100%}
    body{font-size:16px}
    .card{padding:14px 15px}
    table{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch}
  }
  @media(max-width:420px){
    header h1{font-size:18px}
    header nav a{padding:7px 9px;font-size:13px}
    main{padding:11px}
  }
  /* Back-to-menu: the header nav scrolls away on long pages (it needn't persist,
     but there must be a way back — dr's feedback). A floating pill appears once
     you've scrolled and jumps to the top, where the nav lives. */
  #tomenu{position:fixed;right:16px;bottom:16px;z-index:50;display:none;
    background:var(--teal);color:#fff;border:none;border-radius:999px;
    padding:11px 16px;font:700 14px/1 inherit;cursor:pointer;min-height:44px;
    box-shadow:0 3px 12px #0003;text-decoration:none}
  #tomenu.show{display:inline-flex;align-items:center;gap:6px}
  #tomenu:hover{background:#163b38}
  @media print{#tomenu{display:none!important}}
  /* Share bar — fixed bottom-left (mirrors the back-to-menu pill on the right), on
     every page so the whole archive is easy to pass around. */
  #sharebar{position:fixed;left:14px;bottom:14px;z-index:50;display:flex;align-items:center;
    gap:5px;background:var(--card,#fff);border:1px solid var(--line);border-radius:999px;
    padding:5px 8px;box-shadow:0 3px 12px #0000002b}
  #sharebar .shlabel{font-size:12px;font-weight:800;color:var(--muted);text-transform:uppercase;
    letter-spacing:.04em;padding:0 3px 0 5px}
  .shbtn{width:32px;height:32px;min-height:32px;border-radius:50%;border:1px solid var(--line);
    background:#fff;color:var(--ink);font:700 15px/1 inherit;cursor:pointer;display:inline-flex;
    align-items:center;justify-content:center;padding:0}
  .shbtn:hover{background:var(--teal);color:#fff;border-color:var(--teal)}
  .shtoast{position:fixed;left:50%;bottom:64px;transform:translateX(-50%);z-index:60;
    background:#1b2a27;color:#fff;padding:8px 16px;border-radius:999px;font-size:14px;
    box-shadow:0 4px 16px #0004}
  /* card-level share affordance (per-result) */
  .cardshare{background:none;border:none;cursor:pointer;color:var(--muted);font-size:15px;
    padding:2px 6px;border-radius:6px;line-height:1}
  .cardshare:hover{background:#eef2f1;color:var(--teal)}
  @media print{#sharebar{display:none!important}}
  @media(max-width:520px){#sharebar .shlabel{display:none}#sharebar{gap:4px;padding:4px 6px}}
"""

# Simplified Kali yantra favicon: bhupura (square gate frame) → circle →
# eight-petal lotus → downward triangle → bindu. Stripped to the essentials so
# it stays legible at 16px while keeping the yantra's recognizable geometry.
FAVICON_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
    "<rect width='64' height='64' rx='6' fill='#f4ead6'/>"
    "<g fill='none' stroke='#7a1220' stroke-width='2.4' stroke-linejoin='round'>"
    # bhupura: square with a T-gate on each side
    "<path d='M8 8H56V56H8Z'/>"
    "<path d='M27 8V4H37V8'/><path d='M27 56V60H37V56'/>"
    "<path d='M8 27H4V37H8'/><path d='M56 27H60V37H56'/>"
    "<circle cx='32' cy='32' r='20'/>"
    # downward-pointing triangle (Kali / shakti)
    "<path d='M17 23H47L32 49Z'/>"
    "</g>"
    "<circle cx='32' cy='31' r='3' fill='#7a1220'/>"
    "</svg>"
)

# 1200x630 social card: the yantra in gold on deep teal, with the wiki name.
# Shown when a link is shared to Slack / iMessage / social.
OG_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 630'>"
    "<rect width='1200' height='630' fill='#1F4E4A'/>"
    "<rect width='1200' height='630' fill='url(#v)'/>"
    "<defs><radialGradient id='v' cx='30%' cy='40%' r='80%'>"
    "<stop offset='0%' stop-color='#2a615c'/><stop offset='100%' stop-color='#183d39'/>"
    "</radialGradient></defs>"
    "<g transform='translate(300 315)' fill='none' stroke='#e9c46a' stroke-width='7' stroke-linejoin='round'>"
    "<path d='M-150 -150H150V150H-150Z'/>"
    "<path d='M-40 -150V-176H40V-150'/><path d='M-40 150V176H40V150'/>"
    "<path d='M-150 -40H-176V40H-150'/><path d='M150 -40H176V40H150'/>"
    "<circle cx='0' cy='0' r='118'/>"
    "<path d='M-92 -60H92L0 96Z'/>"
    "</g>"
    "<circle cx='300' cy='307' r='16' fill='#e9c46a'/>"
    "<text x='560' y='290' font-family='Georgia, \"Times New Roman\", serif' font-size='96' font-weight='700' fill='#f4ead6'>wichaa</text>"
    "<text x='560' y='372' font-family='Georgia, \"Times New Roman\", serif' font-size='72' font-weight='700' fill='#f4ead6'>Wiki</text>"
    "<text x='562' y='430' font-family='-apple-system, Segoe UI, Arial, sans-serif' font-size='30' fill='#e9c46a'>Manuscripts &#183; wichaa &#183; the living tradition</text>"
    "</svg>"
)

_HEAD = ("<!doctype html><html lang=en><head><meta charset=utf-8>"
         "<meta name=viewport content='width=device-width, initial-scale=1'>"
         "<meta name='theme-color' content='#1F4E4A'>"
         "<link rel=icon type='image/svg+xml' href='/favicon.svg'>")

SITE_DESC = ("An open archive of wichaa — living traditions of sacred, practical knowledge: Lanna manuscripts, the amulet market, St. Expedite and more —"
             "divination, astrology, and sacred practice, from palm-leaf folios "
             "to present-day amulet commerce, on one continuous timeline.")


def _meta(title, description, og_image=None, og_url=None):
    """OpenGraph + Twitter card tags so a shared link unfurls with a title, blurb,
    and an image. Pass og_image/og_url on server-rendered per-entity pages (e.g. a
    manuscript reader) so the share card shows THAT page's content — a real folio and
    its own title — instead of the sitewide yantra card. Absolute URLs are required by
    FB/Twitter; a bare '/path' is made absolute with SITE_URL when published."""
    t = html.escape(title, quote=True)
    d = html.escape(description, quote=True)

    def _abs(u):
        if u and u.startswith("/") and SITE_URL:
            u = SITE_URL + u
        return html.escape(u, quote=True)

    custom_img = bool(og_image)
    ogimg = _abs(og_image) if custom_img else html.escape(
        (SITE_URL + "/og.jpg") if SITE_URL else "/og.jpg", quote=True)
    ogurl = _abs(og_url) if og_url else html.escape(
        (SITE_URL + "/") if SITE_URL else "/", quote=True)
    # Sitewide card is a 1200x630 raster; a per-entity folio is arbitrary/portrait, so
    # only assert dimensions + the yantra alt for the default card.
    dims = ("" if custom_img else
            "<meta property='og:image:width' content='1200'>"
            "<meta property='og:image:height' content='630'>"
            "<meta property='og:image:alt' content='Circular yantra from a Lanna manuscript'>")
    return (
        f"<meta name='description' content='{d}'>"
        "<meta property='og:type' content='website'>"
        "<meta property='og:site_name' content='wichaa'>"
        f"<meta property='og:url' content='{ogurl}'>"
        f"<meta property='og:title' content='{t}'>"
        f"<meta property='og:description' content='{d}'>"
        f"<meta property='og:image' content='{ogimg}'>"
        + dims +
        "<meta name='twitter:card' content='summary_large_image'>"
        f"<meta name='twitter:title' content='{t}'>"
        f"<meta name='twitter:description' content='{d}'>"
        f"<meta name='twitter:image' content='{ogimg}'>"
    )


# Floating "back to menu" control + the tiny script that reveals it on scroll.
# Injected into every page() so navigation is always one tap away, even after the
# header has scrolled off. Uses history-free scroll-to-top (the nav is at the top).
_TOMENU = (
    "<button id=tomenu aria-label='Back to menu' "
    "onclick=\"window.scrollTo({top:0,behavior:'smooth'})\">&#9650; Menu</button>"
    "<script>(function(){var b=document.getElementById('tomenu');if(!b)return;"
    "var f=function(){b.classList.toggle('show',(window.scrollY||0)>320);};"
    "addEventListener('scroll',f,{passive:true});f();})();</script>")


# A share bar on every page (the whole archive is meant to be passed around). Icons are
# plain glyphs — no external assets, matching the no-CDN convention. Hrefs are built at
# CLICK time from location.href + document.title, so on the SPA pages (where the title is
# set by JS after load) the share still carries the right page's title and URL. LINE is
# included deliberately — it's the dominant share channel in Thailand. window.__share is
# exposed so per-card share buttons can share one item without opening it.
# Support link as a floating affordance on EVERY page, not only in the nav —
# appended by page() so a page cannot ship without it. Styled inline because it
# has to work on pages that never opted into the /wats stylesheet.
_KOFLOAT = (
    "<a id=kofloat href='https://ko-fi.com/defiantchiangmai' target=_blank rel=noopener "
    "aria-label='Support this work on Ko-fi' "
    "style=\"position:fixed;right:16px;bottom:16px;z-index:40;background:#fbf1dc;color:#8a5a00;"
    "border:1px solid #e6d3a8;border-radius:999px;padding:11px 16px;font-weight:700;font-size:14.5px;"
    "text-decoration:none;box-shadow:0 6px 18px #0002\">&#9749; Support</a>"
)

_SHARE = (
    "<div id=sharebar aria-label='Share this page'>"
    "<span class=shlabel>Share</span>"
    "<button class=shbtn data-sh=native title='Share…' hidden>&#10148;</button>"
    "<button class=shbtn data-sh=copy title='Copy link'>&#128279;</button>"
    "<button class=shbtn data-sh=fb title='Share on Facebook'>f</button>"
    "<button class=shbtn data-sh=line title='Share on LINE'>L</button>"
    "<button class=shbtn data-sh=tg title='Share on Telegram'>&#9992;</button>"
    "</div>"
    "<script>(function(){var bar=document.getElementById('sharebar');if(!bar)return;"
    "function toast(m){var t=document.createElement('div');t.className='shtoast';"
    "t.textContent=m;document.body.appendChild(t);setTimeout(function(){t.remove();},1800);}"
    # X is deliberately not a share target here — see SHARE_TARGETS note below.
    "function links(u,t){return {"
    "fb:'https://www.facebook.com/sharer/sharer.php?u='+u,"
    "line:'https://social-plugins.line.me/lineit/share?url='+u,"
    "tg:'https://t.me/share/url?url='+u+'&text='+t};}"
    "function shareUrl(url,title){var u=encodeURIComponent(url),"
    "t=encodeURIComponent((title||'').replace(/\\s+[—-]\\s+wichaa.*$/i,''));return {u:u,t:t};}"
    "window.__share=function(url,title){url=url||location.href;title=title||document.title;"
    "if(navigator.share){navigator.share({title:title,url:url}).catch(function(){});return;}"
    "if(navigator.clipboard){navigator.clipboard.writeText(url).then(function(){toast('Link copied');},function(){});}"
    "else toast(url);};"
    "var nat=bar.querySelector('[data-sh=native]');"
    "if(navigator.share&&nat)nat.hidden=false;"
    "bar.addEventListener('click',function(e){var el=e.target.closest('[data-sh]');if(!el)return;"
    "var k=el.getAttribute('data-sh');var s=shareUrl(location.href,document.title);"
    "if(k==='native'){window.__share();return;}"
    "if(k==='copy'){if(navigator.clipboard){navigator.clipboard.writeText(location.href)"
    ".then(function(){toast('Link copied');},function(){toast(location.href);});}else toast(location.href);return;}"
    "var m=links(s.u,s.t);if(m[k])window.open(m[k],'_blank','noopener,width=600,height=520');});"
    "})();</script>")


def page(title, extra_css, body, description=SITE_DESC, og_image=None, og_url=None):
    return (_HEAD + _meta(title, description, og_image, og_url)
            + "<title>" + title + "</title><style>"
            + STYLE + extra_css + "</style></head><body>" + body + _TOMENU + _SHARE + _KOFLOAT
            + "</body></html>")


READER_CSS = (
    ".rd{max-width:1120px;margin:0 auto}"
    # the original scan, interleaved above each page's bilingual text
    ".pscan{margin:10px 0 12px;text-align:center}"
    ".pscan img{max-width:min(100%,780px);height:auto;border:1px solid rgba(128,128,128,.3);"
    "border-radius:6px;box-shadow:0 2px 10px rgba(0,0,0,.08);background:#fff}"
    ".platedesc{font-size:14px;line-height:1.55;opacity:.85;max-width:64em;margin:6px auto}"
    ".platedesc .lbl{font-weight:600;opacity:.7;margin-right:6px}"
    # nav bar: page-jump + chapter dropdown, stays put while a long book scrolls.
    # position:fixed (not sticky) — sticky measured correctly (getBoundingClientRect
    # reported top:0) but the browser wasn't hit-testing/painting it there, a
    # stacking quirk under `<main class=rd>` we couldn't pin down; fixed sidesteps
    # it entirely and is simpler to reason about. .rd gets top padding to match, so
    # fixed content never covers the first page block.
    # main already sits below <header> in normal flow — this padding only needs to
    # clear the FIXED navbar itself (~65px); the inline script sets the exact value
    ".rd{padding-top:80px}"
    ".rd .navbar{position:fixed;top:0;left:0;right:0;z-index:50;background:var(--bg,#fff);"
    "border-bottom:1px solid rgba(128,128,128,.28);padding:10px 24px;"
    "display:flex;gap:14px;flex-wrap:wrap;align-items:center;font-size:13px}"
    ".rd .navbar select{font-size:13px;padding:4px 6px;max-width:340px}"
    ".rd .navbar form{display:flex;gap:6px;align-items:center}"
    ".rd .navbar input[type=number]{width:64px;font-size:13px;padding:4px 6px}"
    ".rd .navbar button{font-size:13px;padding:4px 10px;cursor:pointer}"
    ".rd .navbar .pos{opacity:.6;margin-left:auto}"
    # chapter/entry tree — two levels, collapsed by default when large
    ".rd .toc{font-size:14px;margin:14px 0 8px;padding:12px 16px;"
    "border:1px solid rgba(128,128,128,.28);border-radius:8px}"
    ".rd .toc>summary{cursor:pointer;font-weight:600}"
    ".rd .toc .ch{margin:8px 0 8px 4px}"
    ".rd .toc .ch>a{font-weight:600;text-decoration:none}"
    ".rd .toc .ch .pn{opacity:.55;font-size:12px;margin-left:6px}"
    ".rd .toc .entries{columns:2;column-gap:28px;margin:6px 0 0 14px}"
    ".rd .toc .entries a{display:block;text-decoration:none;padding:1px 0;"
    "break-inside:avoid;font-size:13px;opacity:.85}"
    ".rd .chapnav{display:flex;justify-content:space-between;gap:10px;"
    "font-size:13px;margin:18px 0 -6px;font-weight:600}"
    ".rd .pg{border-top:1px solid rgba(128,128,128,.28);padding:22px 0;scroll-margin-top:64px}"
    ".rd .pg.chapstart{scroll-margin-top:110px}"
    ".rd .pmark{font:600 12px/1 ui-monospace,Menlo,monospace;letter-spacing:.06em;"
    "text-transform:uppercase;opacity:.6;margin-bottom:12px}"
    ".rd .pmark .k{color:#b8892f}"
    ".rd .cols{display:grid;grid-template-columns:1fr 1fr;gap:30px}"
    ".rd .lbl{font:600 11px/1 ui-monospace,Menlo,monospace;letter-spacing:.1em;"
    "text-transform:uppercase;opacity:.5;margin-bottom:8px}"
    ".rd h4{margin:14px 0 6px;font-size:17px}"
    ".rd .th{font-family:'Sukhumvit Set','Thonburi','Noto Serif Thai',serif;line-height:1.7}"
    ".rd .katha{border-left:3px solid #b8892f;background:rgba(184,137,47,.09);"
    "padding:5px 12px;margin:7px 0;border-radius:0 4px 4px 0;font-size:15px}"
    ".rd .diag{opacity:.62;font-size:14px;font-style:italic}"
    "@media(max-width:760px){.rd .cols{grid-template-columns:1fr;gap:14px}"
    ".rd .toc .entries{columns:1}}"
)


def toc_for(mid):
    """The persisted two-level table of contents for one manuscript (see
    build_toc.py, manuscript-crawler): chapters (level 1, from the volume's own
    literal ตอนที่/บทที่ divider pages) each carrying its formula/section entries
    (level 2, from '### ' headings) where that convention was used. One canonical
    structure, read straight off catalog.db — shared with translate.py's
    chapter-context lookup and weave_volume.py/epub_volume.py's exports, so the
    reader's nav can never drift from what those tools already agree on."""
    if not db_present():
        return []
    conn = connect()
    try:
        has_table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='toc_entries'").fetchone()
        if not has_table:
            return []
        chs = conn.execute(
            "SELECT seq, title, start_page, end_page FROM toc_entries "
            "WHERE manuscript_id=? AND level=1 ORDER BY seq", (mid,)).fetchall()
        ents = conn.execute(
            "SELECT seq, title, start_page, parent_seq FROM toc_entries "
            "WHERE manuscript_id=? AND level=2 ORDER BY seq", (mid,)).fetchall()
    finally:
        conn.close()
    by_parent = {}
    for e in ents:
        by_parent.setdefault(e["parent_seq"], []).append(
            {"title": e["title"], "page": e["start_page"]})
    return [{"seq": c["seq"], "title": c["title"], "start": c["start_page"],
            "end": c["end_page"], "entries": by_parent.get(c["seq"], [])}
           for c in chs]


def _reader_render(text, thai=False):
    """Render one page's transcription/translation (markdown-ish: ### headings,
    '> ๛…' katha blockquotes, [diagram:…] notes) to XSS-safe HTML."""
    out, para = [], []

    def flush():
        if para:
            out.append("<p>" + html.escape(" ".join(para)) + "</p>")
            para.clear()

    for ln in text.split("\n"):
        s = ln.strip()
        if not s:
            flush()
        elif s.startswith("### "):
            flush(); out.append("<h4>" + html.escape(s[4:]) + "</h4>")
        elif s.startswith("> "):
            flush(); out.append("<div class=katha>" + html.escape(s[2:]) + "</div>")
        elif s.startswith("[diagram") or s.startswith("[illegible"):
            flush(); out.append("<p class=diag>" + html.escape(s) + "</p>")
        else:
            para.append(s)
    flush()
    body = "".join(out)
    return ("<div class='th'>" + body + "</div>") if thai else body


def reader_page(mid):
    """A read-only bilingual reader for a fully transcribed+translated manuscript:
    Thai transcription beside English translation, page by page, straight from the
    catalog's pages table. Additive — does not touch the SPA detail view.

    Navigation (sticky jump bar + chapter/entry tree + prev/next chapter) is built
    from `toc_entries` (see build_toc.py / toc_for() above) — the SAME structure
    weave_volume.py, epub_volume.py, and translate.py's chapter-context lookup use,
    so this reader can't silently drift from what those tools already agree a
    volume's chapters and formula entries are."""
    if not db_present():
        return page("Reader", "", "<main><p>Catalog not present.</p></main>")
    conn = connect()
    try:
        m = conn.execute("SELECT title_thai, title_english, extent_pages "
                         "FROM manuscripts WHERE id=?", (mid,)).fetchone()
        if not m:
            return page("Reader", "", "<main><p>Manuscript not found.</p></main>")
        # EVERY page, not only transcribed ones: each block shows the original
        # scan interleaved with its bilingual text, so the reader can see what
        # the words reference — and diagram/stencil plates (which have no
        # transcription, only a vision_desc) finally appear in page order
        # instead of vanishing from the reader entirely.
        rows = conn.execute(
            "SELECT page_no, kind, transcription, translation, vision_desc "
            "FROM pages WHERE manuscript_id=? ORDER BY page_no", (mid,)).fetchall()
        done = [r for r in rows if (r["transcription"] or "").strip()]
    finally:
        conn.close()
    title_th = m["title_thai"] or ""
    title_en = m["title_english"] or "Manuscript"
    # NOTE: a per-manuscript folio would be the ideal og:image, but the static export
    # only ships a subset of plate PNGs (gallery set), so /pimg/<mid>/<page>.png is
    # present for some volumes and 404s for others — a broken social image is worse than
    # the branded card. Until there's a guaranteed-exported cover per manuscript, the
    # per-manuscript TITLE + DESCRIPTION below already make each reader's card
    # page-specific; the image stays the branded card. (Follow-up in PRIORITIES.)
    if not done:
        return page(title_en + " — Reader", "",
                    "<header><div><h1>" + html.escape(title_en) + "</h1>"
                    "<p class=sub>No transcription available yet.</p></div>" + NAV + "</header>")

    chapters = toc_for(mid)
    chapter_start_pages = {c["start"]: c for c in chapters}
    # which chapter each transcribed page falls in, for prev/next-chapter links
    chapter_of = {}
    for c in chapters:
        for r in rows:
            if c["start"] <= r["page_no"] <= c["end"]:
                chapter_of[r["page_no"]] = c

    # sticky nav: page-jump form + a chapter <select> (native, works with no JS
    # beyond the one-line onchange) that together replace "scroll for ten minutes"
    navbar = (
        "<div class=navbar>"
        "<form onsubmit=\"location.hash='p'+this.pn.value;return false\">"
        "<label for=pn>Page</label>"
        f"<input type=number id=pn name=pn min=1 max={rows[-1]['page_no']}>"
        "<button type=submit>Go</button></form>")
    if chapters:
        opts = "".join(
            f"<option value='#p{c['start']}'>{html.escape(c['title'][:60])} "
            f"(p.{c['start']}–{c['end']})</option>" for c in chapters)
        navbar += (f"<select onchange=\"if(this.value)location.hash=this.value.slice(1)\">"
                   f"<option value=''>Jump to chapter…</option>{opts}</select>")
    navbar += f"<span class=pos>{len(done)} of {m['extent_pages'] or rows[-1]['page_no']} pages transcribed</span></div>"

    # chapter/entry tree — collapsed by default once it's more than a handful of
    # rows, so a 201-entry volume doesn't open as a wall of links
    total_entries = sum(len(c["entries"]) for c in chapters)
    open_attr = "" if (len(chapters) > 6 or total_entries > 24) else " open"
    toc_html = ""
    if chapters:
        ch_html = []
        for c in chapters:
            row = (f"<div class=ch><a href='#p{c['start']}'>{html.escape(c['title'])}</a>"
                  f"<span class=pn>p.{c['start']}–{c['end']}</span>")
            if c["entries"]:
                ents = "".join(
                    f"<a href='#p{e['page']}'>{html.escape(e['title'])}</a>" for e in c["entries"])
                row += f"<div class=entries>{ents}</div>"
            row += "</div>"
            ch_html.append(row)
        toc_html = (f"<details class=toc{open_attr}><summary>Contents · "
                   f"{len(chapters)} chapter(s)"
                   + (f" · {total_entries} entries" if total_entries else "") +
                   f"</summary>{''.join(ch_html)}</details>")

    blocks = []
    for r in rows:
        pno = r["page_no"]; printed = pno - 7 if pno >= 8 else None
        pl = "printed p.{0}".format(printed) if printed else "front matter"
        is_start = pno in chapter_start_pages
        chapnav = ""
        if is_start:
            c = chapter_start_pages[pno]
            idx = next((i for i, x in enumerate(chapters) if x["seq"] == c["seq"]), None)
            prev_c = chapters[idx - 1] if idx and idx > 0 else None
            next_c = chapters[idx + 1] if idx is not None and idx + 1 < len(chapters) else None
            prev_start = prev_c["start"] if prev_c else None
            next_start = next_c["start"] if next_c else None
            chapnav = (
                "<div class=chapnav>"
                + (f"<a href='#p{prev_start}'>&larr; {html.escape(prev_c['title'][:40])}</a>"
                   if prev_c else "<span></span>")
                + (f"<a href='#p{next_start}'>{html.escape(next_c['title'][:40])} &rarr;</a>"
                   if next_c else "<span></span>")
                + "</div>")
        # the original page, always — the text refers to marks on THIS image,
        # so it sits directly above its own transcription/translation.
        # /pimg serves stored plates whole and renders anything else on demand
        # from the source PDF (JPEG cache); the static export bakes real files.
        img = ("<figure class=pscan><img loading=lazy decoding=async "
               "src='/pimg?mid={0}&amp;n={1}&amp;w=1000' "
               "alt='{2}, PDF page {1} — original scan'></figure>").format(
                   mid, pno, html.escape(title_en))
        tr_txt = (r["transcription"] or "").strip()
        tl_txt = (r["translation"] or "").strip()
        if tr_txt or tl_txt:
            body_html = ("<div class=cols><div><div class=lbl>ไทย · Thai</div>"
                         + _reader_render(r["transcription"] or "", thai=True) + "</div>"
                         + "<div><div class=lbl>English</div>"
                         + _reader_render(r["translation"] or "") + "</div></div>")
        elif (r["vision_desc"] or "").strip():
            body_html = ("<div class=platedesc><span class=lbl>Plate description</span> "
                         + html.escape(r["vision_desc"].strip()) + "</div>")
        else:
            body_html = "<div class=platedesc muted>[page not yet transcribed]</div>"
        blocks.append(
            "<div class='pg{1}' id='p{0}'>".format(pno, " chapstart" if is_start else "")
            + chapnav
            + "<div class=pmark><span class=k>PDF p.{0}</span> · {1} · [{2}]</div>".format(
                pno, pl, html.escape(r["kind"] or "prose"))
            + img + body_html + "</div>")

    dl = epub_download_link(mid)
    head = ("<header><div><h1>" + html.escape(title_en) + "</h1>"
            "<p class=sub><span style=\"font-family:'Sukhumvit Set','Thonburi',serif\">"
            + html.escape(title_th) + "</span> — bilingual reader · " + str(len(done))
            + " transcribed pages" + (" · " + dl if dl else "")
            + "</p></div>" + NAV + "</header>")
    fit_script = (
        "<script>(function(){"
        "var h=document.querySelector('header'),n=document.querySelector('.navbar'),"
        "m=document.querySelector('main.rd');"
        "function fit(){if(!h||!n||!m)return;"
        "var hh=h.getBoundingClientRect().height;"
        "n.style.top=hh+'px';"
        "m.style.paddingTop=(n.getBoundingClientRect().height+16)+'px';}"
        "fit();window.addEventListener('resize',fit);"
        "})();</script>")
    body = (head + "<main class=rd>" + navbar + toc_html + "".join(blocks) + "</main>"
           + fit_script)
    og_desc = ("Bilingual reader — Thai transcription and English translation of "
               + (title_th + " (" + title_en + ")" if title_th else title_en)
               + ", page by page, from wichaa.")
    return page(title_en + " — Reader", READER_CSS, body,
                description=og_desc, og_url="/read/%d/" % mid)


# Primary nav: the reading spine (Overview → Browse → Market → Articles → Activity).
# Half-baked views pulled from the bar but still reachable by URL: /gallery (Plates),
# /vocab (Vocabulary), /map (Map), /graph (Graph), plus /lens, /dashboard, /status.
# One canonical nav, used by every inner page AND mirrored by the homepage links so
# the two never drift (P2, 2026-07-13). Dropped the "Widgets" tab (the shareable /w/
# views live on, but the map/price/region story now sits on /market); "Articles" is
# now "Profiles" — those pages are auto-computed subject profiles, not authored essays.
NAV = ("<nav><a href='/'>Overview</a>"
       "<a href='/browse'>Browse</a><a href='/textbooks'>Textbooks</a>"
       "<a href='/market'>Living Tradition</a>"
       "<a href='/wats'>Wats</a>"
       "<a href='/expedite'>St. Expedite</a>"
       "<a href='/articles'>Profiles</a><a href='/moon'>Moon</a>"
       "<a href='/widgets'>Widgets</a>"
       "<a href='/diagrams'>Diagrams</a>"
       "<a href='/findings'>Discoveries</a>"
       "<a href='/activity'>Activity</a>"
       "<a class=kofi href='/support'>&#9749; Support</a></nav>")


# The funding hub — the WHY (free-forever, tam boon), the WHAT-your-gift-does (real
# price, watch the bots), the HOW (Ko-fi + message format), and commissions. Kept as
# an invitation beside the value, never a gate; the archive is free regardless.
# ---------------------------- keeping in touch ----------------------------
# An address given here is the only audience nobody else can switch off. The
# Facebook following (twenty years, large) was suspended on 2026-07-29 and the
# GitHub account went dark on 2026-08-07; neither could be appealed in any
# useful time. So: capture on our own surfaces, into our own D1, sent by
# whichever sender happens to be convenient later.
#
# Posts to the `nanobot-list` Worker. Reusable — pass a `source` so it is
# visible afterwards WHICH page actually earns addresses, and so a future send
# can be scoped to the people who asked about that particular thing.
#
# Deliberately modest in register: this archive does not badger. No modal, no
# overlay, no "wait! before you go". It sits at the foot of a page someone has
# already chosen to read, and it promises only what can actually be delivered —
# word when the bots finish something worth telling you about.
LIST_ENDPOINT = "https://nanobot-list.nanobotco.workers.dev/subscribe"

SUBSCRIBE_CSS = (
  ".subx{margin:34px 0 6px;padding:20px 22px;border:1px solid var(--line);border-radius:16px;"
  "background:rgba(255,255,255,.55);backdrop-filter:blur(10px) saturate(1.25);"
  "-webkit-backdrop-filter:blur(10px) saturate(1.25);box-shadow:0 8px 26px rgba(0,0,0,.05);"
  "transition:box-shadow .25s ease,border-color .25s ease}"
  ".subx:focus-within{border-color:var(--teal);box-shadow:0 12px 32px rgba(0,0,0,.09)}"
  ".subx h2{margin:0 0 6px;font-size:20px}"
  ".subx p{margin:0 0 14px;color:var(--muted);font-size:15px}"
  ".subx form{display:flex;flex-wrap:wrap;gap:9px}"
  ".subx input[type=email]{flex:1 1 240px;border:1px solid var(--line);border-radius:11px;"
  "padding:12px 14px;font:inherit;font-size:16px;background:#fff;color:var(--ink)}"
  ".subx input[type=email]:focus{outline:none;border-color:var(--teal)}"
  ".subx button{border:0;border-radius:11px;background:var(--teal);color:#fff;font:inherit;"
  "font-weight:700;padding:12px 22px;cursor:pointer;"
  "transition:transform .12s cubic-bezier(.34,1.56,.64,1),filter .2s}"
  ".subx button:hover{filter:brightness(1.08)}"
  ".subx button:active{transform:scale(.94)}"
  ".subx .hp{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden}"
  ".subx .said{margin:10px 0 0;color:var(--teal-ink);font-weight:600}"
  "@media (prefers-color-scheme:dark){.subx{background:rgba(255,255,255,.05)}"
  ".subx input[type=email]{background:rgba(255,255,255,.06)}}"
)


def subscribe_block(source="site", heading="ข่าวคราว · Word from the archive",
                    blurb=("Now and then, when the bots finish reading something worth "
                           "telling you about. No more often than that, and never anything else.")):
    """A small, self-contained signup. `source` records which page earned it."""
    sid = "sx" + str(abs(hash(source)) % 100000)
    return (
      f"<section class='subx' id='{sid}'>"
      f"<h2>{heading}</h2><p>{blurb}</p>"
      "<form novalidate>"
      # Honeypot. Off-screen rather than display:none — some bots skip hidden
      # fields but happily fill a positioned one.
      "<label class='hp' aria-hidden='true'>Website<input type='text' name='website' "
      "tabindex='-1' autocomplete='off'></label>"
      "<input type='email' name='email' required autocomplete='email' "
      "placeholder='you@example.com' aria-label='Your email address'>"
      "<button type='submit'>ส่ง · Send</button>"
      "</form>"
      "<p class='said' hidden></p>"
      "<p style='margin:12px 0 0;font-size:13px;color:var(--muted)'>"
      "One address, kept by us and nobody else. Every letter carries a one-click "
      "unsubscribe, and leaving is instant and final.</p>"
      "</section>"
      "<script>(function(){"
      f"var r=document.getElementById('{sid}');"
      "var f=r.querySelector('form'),s=r.querySelector('.said'),t0=Date.now();"
      "f.addEventListener('submit',function(e){e.preventDefault();"
      "var em=f.email.value.trim();"
      "if(!/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(em)){s.hidden=false;"
      "s.textContent='That address does not look complete — could you check it?';return;}"
      "var b=f.querySelector('button');b.disabled=true;"
      f"fetch('{LIST_ENDPOINT}',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
      "body:JSON.stringify({email:em,website:f.website.value,t0:t0,"
      f"source:'{source}',lang:(navigator.language||'').slice(0,2)}})}})"
      ".then(function(x){return x.json()}).then(function(d){b.disabled=false;s.hidden=false;"
      "s.textContent=d&&d.ok?'ขอบคุณ · Thank you — you are on the list.':"
      "'That did not go through. Please try once more in a moment.';"
      "if(d&&d.ok){f.reset()}})"
      ".catch(function(){b.disabled=false;s.hidden=false;"
      "s.textContent='That did not go through. Please try once more in a moment.'});"
      "});})();</script>"
    )


SUPPORT_PAGE = page("Support — wichaa", SUBSCRIBE_CSS + """
  .sup{max-width:820px;margin:0 auto}
  .sup h2{margin:30px 0 8px;font-size:22px}
  .sup p{margin:0 0 12px}
  .lead{font-size:18px;color:var(--ink)}
  .price{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0}
  .price .box{flex:1 1 200px;border:1px solid var(--line);border-radius:12px;background:#fff;padding:16px 18px}
  .price .box b{display:block;font-size:26px;color:var(--teal)}
  .price .box span{font-size:14px;color:var(--muted)}
  .kofibtn{display:inline-block;background:#13a2a2;color:#fff;font-weight:800;font-size:17px;
    padding:13px 24px;border-radius:999px;text-decoration:none;margin:6px 0}
  .kofibtn:hover{background:#0f8585}
  .how{background:#f4ead6;border-radius:12px;padding:14px 18px;margin:14px 0}
  .how code{background:#fff;border:1px solid var(--line);border-radius:6px;padding:1px 7px}
  .muted{color:var(--muted)}
""",
  "<header><div><h1>Support the archive</h1><p class=sub>Free forever — funded by "
  "merit, not paywalls</p></div>" + NAV + "</header>"
  "<main id=main><div class=sup>"
  "<p class=lead>Everything here is free, and always will be — no ads, no paywall, no "
  "login. But the reading is done by machines, and machine-time costs a little. A "
  "tip isn't a subscription or a lock; it simply buys the bots time to read one "
  "more text, so <b>everyone</b> can have it. In the north that's <i>tam boon</i> — "
  "merit made by opening a book for others.</p>"
  "<div class=price>"
  "<div class=box><b>~$0.06</b><span>to transcribe &amp; translate one page (standard script)</span></div>"
  "<div class=box><b>~$0.16</b><span>per page for rare scripts (Khom, Tham Lanna)</span></div>"
  "<div class=box><b>a few $</b><span>a whole manual, read cover to cover</span></div>"
  "</div>"
  "<p class=muted>Those are the real numbers, at 2.5× the raw model cost — the small "
  "margin is what keeps the archive running. Nothing hidden.</p>"

  "<h2>☕ Sponsor a translation</h2>"
  "<p>Pick a volume on the <a href='/textbooks'>Textbooks</a> page — each shows exactly "
  "how many pages remain and what finishing it costs — then tip with the manuscript "
  "number in your message:</p>"
  "<div class=how>Tip on Ko-fi with a message like <code>TRANSLATE 6968</code> "
  "(or <code>OCR 6968</code> for a raw text pass). Your gift buys that many pages of "
  "faithful, image-grounded translation, and it enters the queue automatically.</div>"
  "<p><a class=kofibtn href='https://ko-fi.com/defiantchiangmai' target=_blank rel=noopener>"
  "☕ Make merit on Ko-fi</a></p>"
  "<p class=muted>You get to <a href='/activity'>watch the bots work</a> — the live feed "
  "shows each page as it's read, with the sponsor's name on the queue.</p>"

  "<h2>The backlog — why it matters</h2>"
  "<p>The collection is large but barely read: thousands of manuscripts are still only "
  "photographs, and the hardest, most valuable work is teaching a model to read "
  "<b>Khom</b> and <b>Tham Lanna</b> by hand — the scripts these texts are written in. "
  "Training data for that barely exists; building it is the whole game. Every sponsored "
  "page is also a training example for the model that will one day read the rest.</p>"

  "<h2>Commissions</h2>"
  "<p>Need a specific manuscript transcribed or translated on a timeline — for research, "
  "a collection, or a lineage you're documenting? That can be commissioned directly. "
  "The result still goes into the free public archive (that's the point), you just move "
  "it to the front of the queue. Write to "
  "<a href='mailto:530kings@proton.me?subject=Wichaa%20commission'>530kings@proton.me</a> "
  "with the manuscript number or what you're looking for.</p>"

  + subscribe_block(source="support") +

  "<p class=muted style='margin-top:26px'>The archive gives; it never takes. If you're "
  "not moved to give, take everything freely — that's what it's here for.</p>"
  "</div></main>")


# ---------------------------- textbooks + epub download ----------------------------
# The 31 contributed (uploaded, not crawled) volumes, otherwise buried among ~7,000
# crawled manuscripts. epub_volume.py (manuscript-crawler) builds finished ebooks
# into EPUB_DIR; the wiki only ever serves what's already built there — it never
# builds one itself.
CONTRIB_SOURCES = (21, 22)


def find_epub(mid):
    """Path to the bilingual (default) epub for manuscript `mid`, if one has been
    built, else None. Prefers the bilingual file over any --lang en/th edition."""
    if not EPUB_DIR.is_dir():
        return None
    cands = sorted(EPUB_DIR.glob(f"{mid}_*.epub"))
    bilingual = [c for c in cands if not re.search(r"\.(en|th)\.epub$", c.name)]
    picked = (bilingual or cands)
    return picked[0] if picked else None


def epub_download_link(mid):
    """'<a href=/download/epub?id=N>...' if a built epub exists, else ''."""
    p = find_epub(mid)
    if not p:
        return ""
    return (f"<a href='/download/epub?id={mid}'>&#128190; Download EPUB "
            f"({p.stat().st_size // 1024:,} KB)</a>")


def textbooks_snapshot():
    """Every contributed volume with page counts, transcription coverage, and
    reader/download availability — the data behind /textbooks."""
    out = {"dbPresent": db_present(), "volumes": []}
    if not db_present():
        return out
    conn = connect()
    try:
        ph = ",".join("?" * len(CONTRIB_SOURCES))
        # work_title/work_desc are additive columns (crawler volume_blurbs.py);
        # an older catalog without them must still render.
        have_blurbs = any(r["name"] == "work_title"
                          for r in conn.execute("PRAGMA table_info(manuscripts)"))
        blurb_cols = "m.work_title, m.work_desc, " if have_blurbs else ""
        rows = conn.execute(
            f"SELECT m.id, m.title_thai, m.title_english, m.genre_normalized, "
            f"{blurb_cols}"
            f"m.extent_pages, m.priority, "
            f"(SELECT COUNT(*) FROM pages p WHERE p.manuscript_id=m.id) n_pages, "
            f"(SELECT COUNT(*) FROM pages p WHERE p.manuscript_id=m.id "
            f" AND p.transcription IS NOT NULL AND p.transcription<>'') n_read "
            f"FROM manuscripts m WHERE m.source_id IN ({ph}) "
            f"ORDER BY m.priority DESC, n_read DESC, m.id", CONTRIB_SOURCES).fetchall()
    finally:
        conn.close()
    for r in rows:
        epub = find_epub(r["id"])
        quote = translate_quote(r["id"])  # one pricing truth: same fn the webhook uses
        out["volumes"].append({
            "id": r["id"], "titleThai": r["title_thai"] or "",
            "titleEnglish": r["title_english"] or "", "genre": r["genre_normalized"] or "",
            "workTitle": (r["work_title"] or "") if have_blurbs else "",
            "desc": (r["work_desc"] or "") if have_blurbs else "",
            "priority": bool(r["priority"]), "extentPages": r["extent_pages"] or r["n_pages"],
            "nPages": r["n_pages"], "nRead": r["n_read"],
            "hasReader": r["n_read"] > 0,
            "hasEpub": epub is not None,
            "epubKB": (epub.stat().st_size // 1024) if epub else 0,
            "quote": quote,
        })
    return out


TEXTBOOKS_PAGE = page("Textbooks — wichaa", """
  .tblist{list-style:none;margin:16px 0;padding:0;display:grid;gap:10px}
  .tbrow{border:1px solid rgba(128,128,128,.28);border-radius:8px;padding:12px 16px}
  .tbtitle{font-size:16px;font-weight:600}
  .tbtitle a{color:inherit;text-decoration:none}
  .tbtitle a:hover{text-decoration:underline}
  .tbth{font-weight:400;opacity:.65;margin-left:6px;
        font-family:'Sukhumvit Set','Thonburi','Noto Serif Thai',serif}
  .tbdesc{font-size:13.5px;line-height:1.5;opacity:.8;margin:4px 0 0;max-width:64em}
  .tbmeta{font-size:13px;opacity:.65;margin-top:4px;display:flex;gap:6px;flex-wrap:wrap}
  .tbmeta a{color:inherit}
  .sponsor{border:1px solid var(--gold,#8a5a00);background:var(--gold-bg,#fbf1dc);
           border-radius:10px;padding:14px 18px;margin:18px 0}
  .sponsor h2{margin:0 0 6px;font-size:17px}
  .sponsor .how{font-size:14px;margin:0 0 10px}
  .sponsor .how code{background:#fff;border-radius:4px;padding:1px 6px}
  .sjob{font-size:13px;padding:4px 0;border-top:1px dashed rgba(138,90,0,.35)}
  .sjob .st{font-weight:700;text-transform:uppercase;font-size:11px;letter-spacing:.04em}
  .sjob .st.done{color:var(--ok,#0f6b3f)} .sjob .st.queued,.sjob .st.running{color:var(--gold,#8a5a00)}
""",
  "<header><div><h1>Textbooks</h1><p class=sub>Contributed wichaa manuscripts — "
  "uploaded, not crawled, and being transcribed + translated one page at a time</p>"
  "</div>" + NAV + "</header>"
  "<main id=main><p class=muted>Loading…</p></main>"
  "<script>" + r"""
const el=(t,p={},k=[])=>{const e=document.createElement(t);Object.assign(e,p);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
async function load(){
  const d=await (await fetch('/api/textbooks')).json();
  const main=document.getElementById('main'); main.textContent='';
  if(!d.dbPresent){main.append(el('p',{className:'muted',textContent:'No catalog database yet.'}));return;}
  const ul=el('ul',{className:'tblist'});
  for(const v of d.volumes){
    // the curated bilingual working title already carries the Thai; only the
    // slug-title fallback needs the separate Thai span.
    const title=el('div',{className:'tbtitle'},[
      el('a',{href:'/m?id='+v.id,textContent:v.workTitle||v.titleEnglish||v.titleThai||('#'+v.id)})]);
    if(!v.workTitle&&v.titleThai) title.append(el('span',{className:'tbth',textContent:v.titleThai}));
    const rowKids=[title];
    if(v.desc) rowKids.push(el('p',{className:'tbdesc',textContent:v.desc}));
    const bits=[document.createTextNode(v.nPages+' of '+(v.extentPages||v.nPages)+' pages digested')];
    if(v.nRead){ bits.push(document.createTextNode(' · ')); bits.push(el('strong',{textContent:v.nRead+' transcribed'})); }
    if(v.hasReader){ bits.push(document.createTextNode(' · ')); bits.push(el('a',{href:'/read?id='+v.id,textContent:'Read →'})); }
    if(v.hasEpub){ bits.push(document.createTextNode(' · ')); bits.push(el('a',{href:'/download/epub?id='+v.id,textContent:'💾 EPUB ('+v.epubKB.toLocaleString()+' KB)'})); }
    if(v.quote&&v.quote.remainingPages>0){
      bits.push(document.createTextNode(' · '));
      bits.push(el('span',{title:'suggested tip, at '+(v.quote.perPageUSD)+' USD/page ('+v.quote.tier+' tier)',
        textContent:'🪙 finish translation ≈ $'+v.quote.fullVolumeUSD.toLocaleString()}));
    }
    rowKids.push(el('div',{className:'tbmeta'},bits));
    ul.append(el('li',{className:'tbrow'},rowKids));
  }
  main.append(ul);
  // Sponsored OCR (tam boon): how to commission a pass + the live queue.
  try{
    const s=await (await fetch('/api/sponsor-jobs')).json();
    const box=el('div',{className:'sponsor'});
    box.append(el('h2',{textContent:'☕ Sponsor a translation (tam boon)'}));
    const how=el('p',{className:'how'});
    how.append(document.createTextNode('Pick a volume above, then '),
      el('a',{href:s.kofi,target:'_blank',rel:'noopener',textContent:'tip on Ko-fi'}),
      document.createTextNode(' with the manuscript number in your message — e.g. '),
      el('code',{textContent:'TRANSLATE 6968'}),
      document.createTextNode(' — and your gift buys that many pages of faithful, image-grounded translation (or '),
      el('code',{textContent:'OCR 6968'}),
      document.createTextNode(' for a raw text pass). Prices are per page at 2.5× the raw model cost — the margin is what keeps the archive running; nothing hidden.'));
    box.append(how);
    for(const j of (s.jobs||[])){
      const row=el('div',{className:'sjob'});
      const what=(j.kind==='translate'?('translate'+(j.pages?(' '+j.pages+'p'):'')):j.kind);
      row.append(el('span',{className:'st '+j.status,textContent:j.status}),
        document.createTextNode(' '+j.name+' · '+what+(j.mid?(' → #'+j.mid+(j.title?' · '+j.title:'')):'')+' · '+(j.created||'').slice(0,10)));
      box.append(row);
    }
    main.append(box);
  }catch(e){}
}
load();
""" + "</script>")


def rebuilding_page(path: str) -> str:
    """A calm placeholder for a view we've deliberately pulled to rebuild bigger.

    Better an honest 'coming back stronger' than a half-baked map/graph/gallery in
    the navigation. Points visitors at the surfaces that do earn their place today.
    """
    which = {
        "/map": ("Provenance map",
                 "A real map of where every witness comes from — provinces, temples, "
                 "and the routes between them — is being rebuilt properly."),
        "/graph": ("Relationship graph",
                   "A relationship graph worth exploring — subjects, places, and the "
                   "links between manuscripts and the living market — is being rebuilt "
                   "properly."),
        "/gallery": ("Plates",
                     "A gallery of the rendered pages — legible, described, and a "
                     "pleasure to browse — is being rebuilt properly."),
    }
    title, blurb = which.get(path, ("This view",
                                    "This view is being rebuilt."))
    body = (
        "<header><div><h1>" + title + " — coming back stronger</h1>"
        "<p class=sub>Pulled from the navigation while we rebuild it bigger and better</p>"
        "</div>" + NAV + "</header>"
        "<main style='max-width:680px'>"
        "<p style='font-size:17px;line-height:1.6'>" + blurb + "</p>"
        "<p class=muted>The underlying data is still here and still growing every hour. "
        "In the meantime, these surfaces are worth your time:</p>"
        "<ul style='line-height:2;font-size:16px'>"
        "<li><a href='/browse'>Browse</a> — search and filter the whole corpus</li>"
        "<li><a href='/articles'>Articles</a> — what the curiosity bots keep noticing</li>"
        "<li><a href='/activity'>Activity</a> — the crawls, curiosity, and archiving, live</li>"
        "<li><a href='/market'>The Living Tradition</a> — the same wichaa still worn, carried, and traded today</li>"
        "</ul></main>")
    return page(title + " — wichaa", "", body)

INDEX_PAGE = page("Browse — wichaa", """
  .layout{display:grid;grid-template-columns:280px 1fr;gap:18px}
  @media(max-width:820px){.layout{grid-template-columns:1fr}}
  .facets h3{margin:14px 0 6px;font-size:14px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
  .facets label{display:flex;align-items:center;gap:8px;font-size:15px;padding:3px 0;cursor:pointer}
  .facets input{width:18px;height:18px}
  .facets .n{margin-left:auto;color:var(--muted);font-size:13px}
  .result{display:flex;gap:14px;align-items:flex-start;padding:12px 14px;border:1px solid var(--line);border-radius:10px;background:#fff;margin:0 0 12px;text-decoration:none;color:inherit}
  .result:hover{border-color:var(--teal);box-shadow:0 1px 4px #0001}
  .result.prio{border-left:5px solid var(--prio)}
  .rthumb{flex:0 0 96px;width:96px;height:96px;border-radius:8px;overflow:hidden;background:#eef2f1;border:1px solid var(--line)}
  .rthumb img{width:100%;height:100%;object-fit:cover;object-position:center 30%;display:block}
  .rmono{width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:radial-gradient(120% 120% at 50% 28%,#1d4b46,#0b2321);color:#bfe8e0;font-size:34px;font-weight:800;line-height:1}
  .rbody{flex:1;min-width:0}
  @media(max-width:520px){.rthumb{flex-basis:72px;width:72px;height:72px}}
  .result h2{margin:0 0 4px;font-size:19px;color:var(--teal)}
  .result .meta{color:var(--muted);font-size:14px;margin:2px 0}
  .result .snippet{color:#334;font-size:14px;margin:4px 0 2px;line-height:1.5}
  .snippet mark{background:#ffe9a8;color:inherit;padding:0 1px;border-radius:2px}
  .artmatches{margin:0 0 14px;font-size:15px}
  .artmatches:empty{display:none}
  .artmatches .aml{font-weight:700;color:var(--muted);margin-right:6px}
  .artmatches .amlink{display:inline-block;margin:0 10px 6px 0;font-weight:700;text-decoration:none;color:var(--teal)}
  .toolbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
  .toolbar input[type=search]{flex:1;min-width:220px}
  .count{font-weight:700}
  .chips{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 14px}
  .chips:empty{display:none}
  .chip{display:inline-flex;align-items:center;gap:6px;background:var(--teal);color:#fff;border-radius:999px;padding:5px 8px 5px 12px;font-size:14px;font-weight:700}
  .chip button{background:#ffffff33;color:#fff;border:none;border-radius:999px;min-height:22px;height:22px;width:22px;padding:0;font-size:15px;line-height:1;cursor:pointer}
  .chip button:hover{background:#ffffff55}
  .facets .more{background:none;border:none;color:var(--focus);font-weight:700;padding:4px 0;cursor:pointer;min-height:auto;font-size:14px}
""",
  "<header><div><h1>Browse the catalogue</h1><p class=sub>The Lanna manuscript corpus — one tradition of wichaa; filter by tradition, script, genre and more</p></div>" + NAV + "</header>"
  "<main><div class=toolbar>"
  "<input id=search type=search placeholder='Search title, genre, temple, province, ID…' aria-label='Search'>"
  "<select id=sort aria-label=Sort><option value=priority>Sort: Priority first</option>"
  "<option value=title>Sort: Title A–Z</option>"
  "<option value=date>Sort: Most ancient first</option>"
  "<option value=images>Sort: Most images</option></select>"
  "<button class=secondary id=clear>Clear filters</button><span class=count id=count></span></div>"
  "<div id=chips class=chips aria-label='Active filters'></div>"
  "<div id=artmatches class=artmatches aria-label='Matching articles'></div>"
  "<div class=layout><aside class='card facets' id=facets aria-label=Filters></aside>"
  "<section id=results aria-live=polite></section></div></main>"
  "<script>" + r"""
const FL={tradition:'Tradition',priority:'Research priority',genre:'Genre',subgenre:'Subgenre',script:'Script',scriptFamily:'Script family',languages:'Language',material:'Material',materialFamily:'Material family',era:'Era',century:'Century',province:'Province',temple:'Temple',source:'Source'};
const CAP=12; // long facet lists collapse to this many until "show all"
let ALL=[],FACETS={},LABELS={},active={},expanded={};
let SEARCH=null,searchT=null;  // server full-text results {order,snip,articles}
const el=(t,p={},k=[])=>{const e=document.createElement(t);Object.assign(e,p);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
function monogram(label){const m=(label||'?').replace(/^[^\p{L}\p{N}]+/u,'');return (m[0]||'?').toUpperCase();}
function fromURL(){const q=new URLSearchParams(location.search);active={};
  for(const key of Object.keys(FL)){const vals=q.getAll(key);if(vals.length)active[key]=new Set(vals);}
  const term=q.get('q');if(term)document.getElementById('search').value=term;
  const sort=q.get('sort');if(sort)document.getElementById('sort').value=sort;}
function toURL(){const q=new URLSearchParams();
  for(const key of Object.keys(active))for(const v of (active[key]||[]))q.append(key,v);
  const term=document.getElementById('search').value.trim();if(term)q.set('q',term);
  const sort=document.getElementById('sort').value;if(sort&&sort!=='priority')q.set('sort',sort);
  const s=q.toString();history.replaceState(null,'',s?'?'+s:location.pathname);}
async function load(){const d=await (await fetch('/api/manuscripts')).json();ALL=d.items;FACETS=d.facets;LABELS=d.labels;
  if(!d.dbPresent){document.getElementById('results').innerHTML='';document.getElementById('results').append(el('div',{className:'empty'},[el('p',{textContent:'No catalog yet — crawler/catalog.db hasn’t been created.'}),el('p',{},[document.createTextNode('Run the crawler, then reload. See '),el('a',{href:'/status',textContent:'Crawl status'}),document.createTextNode('.')])]));document.getElementById('count').textContent='';return;}
  fromURL();renderFacets();if(document.getElementById('search').value.trim().length>=2)runSearch();else apply();}
function labelFor(key,val){return (LABELS[key]&&LABELS[key][val])||val;}
function toggle(key,val,on){active[key]=active[key]||new Set();on?active[key].add(val):active[key].delete(val);if(!active[key].size)delete active[key];renderFacets();apply();}
function renderFacets(){const box=document.getElementById('facets');box.textContent='';let any=false;
  for(const key of Object.keys(FL)){let vals=Object.entries(FACETS[key]||{}).sort((a,b)=>b[1]-a[1]);if(!vals.length)continue;any=true;
    box.append(el('h3',{textContent:FL[key]}));
    const sel=active[key]||new Set();const show=expanded[key]?vals:vals.slice(0,CAP);
    // always include any selected value even if beyond the cap
    for(const [val,n] of vals)if(sel.has(val)&&!show.some(x=>x[0]===val))show.push([val,n]);
    for(const [val,n] of show){const cb=el('input',{type:'checkbox'});cb.value=val;cb.checked=sel.has(val);
      cb.onchange=()=>toggle(key,val,cb.checked);
      box.append(el('label',{},[cb,document.createTextNode(labelFor(key,val)),el('span',{className:'n',textContent:n})]));}
    if(vals.length>CAP){const more=el('button',{className:'more',textContent:expanded[key]?'– show fewer':'+ show all '+vals.length});
      more.onclick=()=>{expanded[key]=!expanded[key];renderFacets();};box.append(more);}}
  if(!any)box.append(el('p',{className:'muted',textContent:'No facets yet.'}));}
const ARTICLE_AXES={genre:1,subgenre:1,script:1,scriptFamily:1,languages:1,material:1,materialFamily:1,province:1,temple:1,era:1};
function renderChips(){const box=document.getElementById('chips');box.textContent='';
  for(const key of Object.keys(active))for(const val of active[key]){
    const chip=el('span',{className:'chip'},[document.createTextNode(FL[key]+': '+labelFor(key,val))]);
    const x=el('button',{textContent:'×','aria-label':'Remove filter '+labelFor(key,val)});x.onclick=()=>toggle(key,val,false);
    chip.append(x);box.append(chip);}
  // exactly one node selected → offer its article: the facet and the article are one node
  const ks=Object.keys(active);
  if(ks.length===1&&active[ks[0]].size===1&&ARTICLE_AXES[ks[0]]){const k=ks[0],v=[...active[k]][0];
    box.append(el('a',{className:'chip',style:'background:var(--teal);color:#fff;text-decoration:none;font-weight:700',
      href:'/a?s='+encodeURIComponent(k+':'+v),textContent:'Read about '+labelFor(k,v)+' →'}));}}
function matches(it){for(const key of Object.keys(active)){const set=active[key];if(!set||!set.size)continue;
    let field;if(key==='priority')field=[it.priority?'Research priority':''];
    else field=Array.isArray(it[key])?it[key]:[it[key]];  // multi-valued facets (e.g. languages) match on membership
    if(![...set].some(v=>field.includes(v)))return false;}return true;}
function cmp(sort){return (a,b)=>{if(sort==='images')return b.imageCount-a.imageCount;if(sort==='date'){/* real chronology: CS and BE both converted to CE at build
  time (taxonomy.date_sort_ce). Undated records keep their place at the END in
  title order rather than being given a year they do not have. */
  const x=a.dateSort,y=b.dateSort;
  if(x==null&&y==null)return a.title.localeCompare(b.title);
  if(x==null)return 1; if(y==null)return -1;
  return x-y||a.title.localeCompare(b.title);}if(sort==='title')return a.title.localeCompare(b.title);return (a.priority?0:1)-(b.priority?0:1)||a.title.localeCompare(b.title);};}
function onSearchInput(){clearTimeout(searchT);const term=document.getElementById('search').value.trim();
  if(term.length<2){SEARCH=null;apply();return;}
  searchT=setTimeout(runSearch,180);}
async function runSearch(){const term=document.getElementById('search').value.trim();
  if(term.length<2){SEARCH=null;apply();return;}
  try{const d=await (await fetch('/api/search?q='+encodeURIComponent(term))).json();
    if(document.getElementById('search').value.trim()!==term)return; // a newer keystroke won
    SEARCH={order:d.manuscripts.map(x=>x.id),snip:Object.fromEntries(d.manuscripts.map(x=>[x.id,x.snippet])),articles:d.articles||[]};
  }catch(e){SEARCH=null;}
  apply();}
function renderArtMatches(term){const box=document.getElementById('artmatches');box.textContent='';
  if(!term||!SEARCH||!SEARCH.articles.length)return;
  box.append(el('span',{className:'aml',textContent:'Articles: '}));
  for(const a of SEARCH.articles.slice(0,8))box.append(el('a',{className:'amlink',href:'/a?s='+encodeURIComponent(a.key),textContent:a.label}));}
function apply(){const term=document.getElementById('search').value.trim();const sort=document.getElementById('sort').value;
  toURL();renderChips();renderArtMatches(term);
  let out=ALL.filter(matches),fts=false;
  if(term){
    if(SEARCH){fts=true;const rank=new Map(SEARCH.order.map((id,i)=>[id,i]));
      out=out.filter(it=>rank.has(it.id));
      out.sort(sort==='priority'?(a,b)=>rank.get(a.id)-rank.get(b.id):cmp(sort));}
    else{const t=term.toLowerCase();
      out=out.filter(it=>[it.title,it.titleThai,it.titleTranslit,it.genreRaw,it.genreLabel,it.temple,it.province,it.sourceIdentifier,it.source].join(' ').toLowerCase().includes(t));
      out.sort(cmp(sort));}
  } else out.sort(cmp(sort));
  document.getElementById('count').textContent=out.length+' of '+ALL.length+' manuscripts'+(fts?' · full-text':'');
  const box=document.getElementById('results');box.textContent='';
  if(!out.length){box.append(el('div',{className:'empty',textContent:'No manuscripts match these filters.'}));return;}
  for(const it of out){const a=el('a',{className:'result'+(it.priority?' prio':''),href:'/m?id='+it.id});
    const th=el('div',{className:'rthumb'});
    if(it.thumb){const img=el('img',{src:it.thumb.src,alt:'',loading:'lazy'});
      img.addEventListener('error',()=>{const mo=el('div',{className:'rmono',textContent:monogram(it.title)});img.replaceWith(mo);th.classList.add('mono');});
      th.append(img);}
    else{th.append(el('div',{className:'rmono',textContent:monogram(it.title)}));}
    a.append(th);
    const bd=el('div',{className:'rbody'});
    bd.append(el('h2',{textContent:it.title}));
    if(it.titleThai)bd.append(el('div',{className:'meta thai',textContent:it.titleThai}));
    const bits=[it.source,it.temple||it.province,it.date,it.extentPages?it.extentPages+' folios':''].filter(Boolean).join('  ·  ');
    if(bits)bd.append(el('div',{className:'meta',textContent:bits}));
    if(fts&&SEARCH.snip[it.id]){const sn=el('div',{className:'snippet'});sn.innerHTML=SEARCH.snip[it.id];bd.append(sn);}
    const tags=el('div');
    if(it.priority)tags.append(el('span',{className:'pill prio',textContent:'★ '+it.genreLabel}));
    else tags.append(el('span',{className:'pill',textContent:it.genreLabel}));
    if(it.scriptLabel)tags.append(el('span',{className:'pill script',textContent:it.scriptLabel}));
    if(it.materialLabel)tags.append(el('span',{className:'pill',textContent:it.materialLabel}));
    // imagery pill — a real count and a doorway into the pages, not a dead "0 images"
    const nimg=it.imageCount||0, npag=it.pageCount||0;
    if(npag>0)tags.append(el('a',{className:'pill imgpill',href:'/m?id='+it.id+'#pages',textContent:'▦ '+npag.toLocaleString()+' page image'+(npag===1?'':'s')}));
    else if(nimg>0)tags.append(el('a',{className:'pill imgpill',href:'/m?id='+it.id,textContent:'▦ '+nimg.toLocaleString()+' image'+(nimg===1?'':'s')}));
    else tags.append(el('span',{className:'pill',textContent:'no images yet'}));
    // per-card share (the whole card is a link, so stop it navigating on the button)
    const sh=el('button',{className:'cardshare',title:'Share this manuscript','aria-label':'Share',textContent:'⤴'});
    sh.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();window.__share(location.origin+'/m?id='+it.id,it.title);});
    tags.append(sh);
    bd.append(tags);a.append(bd);box.append(a);}}
document.getElementById('search').addEventListener('input',onSearchInput);
document.getElementById('sort').addEventListener('change',apply);
document.getElementById('clear').addEventListener('click',()=>{active={};expanded={};SEARCH=null;document.getElementById('search').value='';renderFacets();apply();});
load();
""" + "</script>")

DETAIL_PAGE = page("Manuscript — wichaa", """
  .grid{display:grid;grid-template-columns:1fr 340px;gap:18px}
  @media(max-width:900px){.grid{grid-template-columns:1fr}}
  dl{display:grid;grid-template-columns:160px 1fr;gap:6px 14px;margin:0}
  dt{font-weight:700;color:var(--muted)}
  dd{margin:0}
  .relhead{margin:14px 0 4px;font-size:15px}
  .relhead a{font-weight:700;font-size:13px}
  .rellist{margin:0 0 8px;padding-left:20px}
  .rellist li{margin:3px 0}
  .pageviewer img{max-width:100%;border:1px solid var(--line);border-radius:8px;background:#faf7f0}
  .thumbwall{display:grid;grid-template-columns:repeat(auto-fill,minmax(92px,1fr));gap:8px}
  .tw{display:block;position:relative;aspect-ratio:3/4;border-radius:8px;overflow:hidden;border:1px solid var(--line);background:#f0efe9}
  .tw img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .18s ease}
  .tw:hover{border-color:var(--teal);box-shadow:0 1px 6px #0002}
  .tw:hover img{transform:scale(1.05)}
  .tw.dia{border-color:var(--gold);box-shadow:0 0 0 2px var(--gold-bg)}
  .tw .pgnum{position:absolute;left:0;bottom:0;font-size:11px;font-weight:700;color:#fff;background:#000a;padding:1px 6px;border-top-right-radius:6px}
  .pageviewer .noimg{padding:40px;text-align:center;color:var(--muted);border:1px dashed var(--line);border-radius:8px;background:#faf7f0}
  .tabs{display:flex;gap:6px;margin:12px 0 8px;flex-wrap:wrap}
  .tab{border:1px solid var(--line);background:#eef2f1;color:var(--muted);border-radius:8px;padding:6px 12px;font-weight:700;cursor:pointer;min-height:38px}
  .tab.on{background:var(--teal);color:#fff;border-color:var(--teal)}
  .textbox{white-space:pre-wrap;background:#fff;border:1px solid var(--line);border-radius:8px;padding:14px;min-height:120px;font-size:1.1em;line-height:1.8}
  .pager{display:flex;gap:10px;align-items:center;margin:10px 0}
  .pager b{min-width:150px;text-align:center}
  textarea{min-height:120px;resize:vertical}
  .savebar{display:flex;gap:10px;align-items:center;margin-top:10px}
  details pre{white-space:pre-wrap;background:#0c1b19;color:#eafff8;border-radius:8px;padding:12px;overflow:auto;max-height:300px;font:12px/1.5 Menlo,Consolas,monospace}
  #log{white-space:pre-wrap;background:#0c1b19;color:#eafff8;border-radius:10px;padding:14px;max-height:260px;overflow:auto;font:13px/1.5 Menlo,Consolas,monospace;display:none;margin-top:12px}
""",
  "<header><div><h1 id=title>Manuscript</h1><p class=sub id=titleThai></p></div>" + NAV + "</header>"
  "<main id=main><p class=muted>Loading…</p></main>"
  "<script>" + r"""
const ID=new URLSearchParams(location.search).get('id');
let M=null,ANN={notes:'',tags:[]},page=0,view='image';
const el=(t,p={},k=[])=>{const e=document.createElement(t);Object.assign(e,p);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
// one page of a digested volume: lazy on-demand thumbnail, opens full page in a new tab
function pageThumb(p){const a=el('a',{className:'tw'+(p.kind==='diagram'?' dia':''),href:'/pimg?mid='+M.id+'&n='+p.n+'&w=1400',target:'_blank',rel:'noopener',title:(p.desc||('Page '+p.n))});
  a.append(el('img',{src:'/pimg?mid='+M.id+'&n='+p.n+'&w=240',alt:'page '+p.n,loading:'lazy'}));
  a.append(el('span',{className:'pgnum',textContent:(p.kind==='diagram'?'◆ ':'')+p.n}));return a;}
async function load(){const r=await fetch('/api/manuscript?id='+encodeURIComponent(ID));
  if(!r.ok){document.getElementById('main').textContent='Manuscript not found.';return;}
  const d=await r.json();M=d.manuscript;ANN=d.annotation||{notes:'',tags:[]};render();}
function render(){
  document.getElementById('title').textContent=M.title;
  document.getElementById('titleThai').textContent=M.titleThai||'';
  const main=document.getElementById('main');main.textContent='';
  const grid=el('div',{className:'grid'});const left=el('div');
  // wichaa subjects named in this manuscript — doors up to the whole-subject article
  if(M.subjects&&M.subjects.length){const ss=el('div',{style:'margin:0 0 14px;line-height:2.1'});
    ss.append(el('span',{className:'muted',style:'font-weight:700;margin-right:8px',textContent:'Subjects:'}));
    for(const s of M.subjects)ss.append(el('a',{href:s.href,style:'margin:0 6px 0 0;padding:4px 12px;border-radius:999px;background:var(--gold-bg);border:1px solid #e5cf9a;color:var(--gold);text-decoration:none;font-weight:700;font-size:14px',textContent:s.label}));
    left.append(ss);}

  const meta=el('div',{className:'card'});
  const h=el('h2',{style:'margin-top:0'},[document.createTextNode('Details ')]);
  if(M.priority)h.append(el('span',{className:'pill prio',textContent:'★ Research priority'}));
  meta.append(h);
  const dl=el('dl');
  const fcell=(key,val,label)=>el('a',{href:'/browse?'+key+'='+encodeURIComponent(val),textContent:label||val});
  const drow=(dt,node)=>node?[el('dt',{textContent:dt}),el('dd',{},[node])]:null;
  const trow=(dt,txt)=>txt?[el('dt',{textContent:dt}),el('dd',{textContent:txt})]:null;
  const fmtDate=s=>{if(!s)return '';const d=new Date(s);return isNaN(d)?s:d.toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'});};
  // genre + its subgenre child, now a real clickable node (was dead "(Philology)" text)
  const genreDd=el('dd');if(M.genre){genreDd.append(fcell('genre',M.genre,M.genreLabel));
    if(M.subgenre){genreDd.append(document.createTextNode(' · '));genreDd.append(el('a',{href:'/browse?subgenre='+encodeURIComponent(M.subgenre),textContent:M.subgenre}));}
    else if(M.genreRaw){genreDd.append(document.createTextNode('  ('+M.genreRaw+')'));}}
  // script + its Dhamma-family roll-up
  const scriptDd=el('dd');if(M.script){scriptDd.append(fcell('script',M.script,M.scriptLabel));
    if(M.scriptFamily&&M.scriptFamily!==M.scriptLabel){scriptDd.append(document.createTextNode('  · '));scriptDd.append(el('a',{href:'/browse?scriptFamily='+encodeURIComponent(M.scriptFamily),textContent:M.scriptFamily}));}}
  // language is a set of normalized nodes now — one clickable node each, not a compound string
  const langDd=el('dd');(M.languages||[]).forEach((lg,i)=>{if(i)langDd.append(document.createTextNode(' · '));langDd.append(el('a',{href:'/browse?languages='+encodeURIComponent(lg),textContent:lg}));});
  // province resolved to a canonical node; the raw provenance (temple/district) kept as a note
  const provDd=el('dd');if(M.province)provDd.append(fcell('province',M.province));
  if(M.provenance&&M.geoLevel!=='province')provDd.append(el('span',{className:'muted',style:'font-size:12px',textContent:(M.province?'  · ':'')+'recorded as '+M.provenance+(M.geoLevel!=='other'?' ('+M.geoLevel+')':'')}));
  // material + its palm-leaf/paper family roll-up
  const matDd=el('dd');if(M.material){matDd.append(fcell('material',M.material,M.materialLabel));
    if(M.materialFamily&&M.materialFamily!==M.materialLabel){matDd.append(document.createTextNode('  · '));matDd.append(el('a',{href:'/browse?materialFamily='+encodeURIComponent(M.materialFamily),textContent:M.materialFamily}));}}
  // date + the calendar era pulled out as its own node (CS antique vs BE modern)
  const dateDd=el('dd');if(M.date||M.dateCe){dateDd.append(document.createTextNode((M.date||'')+(M.dateCe?'  (~'+M.dateCe+' CE)':'')));
    if(M.era){dateDd.append(document.createTextNode('  · '));dateDd.append(el('a',{href:'/browse?era='+encodeURIComponent(M.era),textContent:M.era}));}}
  const cells=[
    drow('Source',M.source?fcell('source',M.source):null),
    trow('Source ID',M.sourceIdentifier),
    M.genre?[el('dt',{textContent:'Genre'}),genreDd]:null,
    M.script?[el('dt',{textContent:'Script'}),scriptDd]:null,
    (M.languages&&M.languages.length)?[el('dt',{textContent:'Language'}),langDd]:null,
    M.material?[el('dt',{textContent:'Material'}),matDd]:null,
    drow('Temple',M.temple?fcell('temple',M.temple):null),
    (M.province||(M.provenance&&M.geoLevel!=='province'))?[el('dt',{textContent:'Province'}),provDd]:null,
    (M.date||M.dateCe)?[el('dt',{textContent:'Date'}),dateDd]:null,
    trow('Extent',M.extentPages?M.extentPages+(M.extentPages==1?' folio':' folios'):''),
    ...(M.firstSeen&&M.firstSeen===M.lastSeen
        ? [trow('Catalogued',fmtDate(M.firstSeen))]
        : [trow('First seen',fmtDate(M.firstSeen)),trow('Last seen',fmtDate(M.lastSeen))]),
  ];
  for(const c of cells)if(c)dl.append(...c);
  meta.append(dl);
  const links=el('p',{style:'margin:12px 0 0'});
  // "View at source": CrossAsia changed their site and the per-manuscript viewer
  // routes now 404 (page title "Search"); contributed volumes carry a local: path
  // with no public source. So prefer the IIIF manifest — the holding library's
  // canonical, always-resolving record — and only show the raw source_url when it
  // is a genuine off-site http page (not the dead crossasia collection route).
  const deadSource = !M.sourceUrl || M.sourceUrl.indexOf('local:')===0 || M.sourceUrl.indexOf('/s/lanna/collections/')>=0;
  if(M.iiifManifestUrl)links.append(el('a',{href:M.iiifManifestUrl,target:'_blank',rel:'noopener',textContent:'View at source library (IIIF) ↗'}));
  if(!deadSource){if(links.childNodes.length)links.append(document.createTextNode('   '));links.append(el('a',{href:M.sourceUrl,target:'_blank',rel:'noopener',textContent:'Source record ↗'}));}
  if(M.hasReader){if(links.childNodes.length)links.append(document.createTextNode('   '));links.append(el('a',{href:'/read?id='+M.id,textContent:'📖 Read transcription + translation →'}));}
  if(links.childNodes.length)meta.append(links);
  // Funding invitation (tam boon): this manuscript has page images but nothing has been
  // transcribed yet — a machine hasn't read it. Beside the value, never a gate.
  if(M.images && M.images.length && !M.hasReader){
    const fund=el('p',{style:'margin:14px 0 0;padding:11px 14px;background:#f4ead6;border-radius:10px;font-size:14px;line-height:1.5'});
    fund.append(document.createTextNode('📖 Not yet transcribed — a machine hasn’t read this one yet. '),
      el('a',{href:'/support',style:'font-weight:700',textContent:'Sponsor it being read'}),
      document.createTextNode(' — tam boon, ~$0.06 a page, and it becomes everyone’s.'));
    meta.append(fund);
  }
  if(M.rawMetadata){const det=el('details');det.append(el('summary',{textContent:'Raw source metadata',style:'cursor:pointer;font-weight:700;color:var(--muted)'}));
    det.append(el('pre',{textContent:typeof M.rawMetadata==='string'?M.rawMetadata:JSON.stringify(M.rawMetadata,null,2)}));meta.append(det);}
  left.append(meta);

  const imgs=M.images||[];const hasPages=M.pages&&M.pages.length;
  // The scan-images card shows for crawled scans / a IIIF folio. For a digested volume
  // (pages but no scans) we skip it — the Pages gallery below IS the imagery.
  if(imgs.length||M.iiifThumb||!hasPages){
  const pv=el('div',{className:'card pageviewer'});
  const imgHead=imgs.length?('Images ('+imgs.length+')'):(M.iiifThumb?'Image':'Images (0)');
  pv.append(el('h2',{textContent:imgHead,style:'margin-top:0'}));
  if(!imgs.length){
    if(M.iiifThumb){
      pv.append(el('img',{src:M.iiifThumb,alt:'representative folio of '+M.title,loading:'lazy'}));
      const cap=el('p',{className:'muted',style:'margin:8px 0 0;font-size:13px'});
      cap.append(document.createTextNode('A representative folio, served on demand from the source library. '));
      if(M.iiifManifestUrl)cap.append(el('a',{href:M.iiifManifestUrl,target:'_blank',rel:'noopener',textContent:'All folios via IIIF ↗'}));
      else if(M.sourceUrl)cap.append(el('a',{href:M.sourceUrl,target:'_blank',rel:'noopener',textContent:'View at source ↗'}));
      pv.append(cap);
    } else {
      pv.append(el('p',{className:'muted',textContent:'No images catalogued for this manuscript yet.'}));
    }
  }
  else{const pgr=el('div',{className:'pager'});
    const prev=el('button',{className:'secondary',textContent:'‹ Prev'});prev.onclick=()=>{page=Math.max(0,page-1);drawPage();};
    const next=el('button',{className:'secondary',textContent:'Next ›'});next.onclick=()=>{page=Math.min(imgs.length-1,page+1);drawPage();};
    pgr.append(prev,el('b',{id:'plabel'}),next);pv.append(pgr,el('div',{id:'pageimg'}));
    const tabs=el('div',{className:'tabs'});
    [['image','Image'],['ocr','OCR text']].forEach(([v,l])=>{const b=el('button',{className:'tab',textContent:l});b.dataset.v=v;b.onclick=()=>{view=v;drawPage();};tabs.append(b);});
    pv.append(tabs,el('div',{id:'pagetext'}));}
  left.append(pv);
  }
  // Pages gallery — the digested volume, every page a real image rendered on demand.
  if(hasPages){const pc=el('div',{className:'card',id:'pages'});
    const dia=M.diagramPages||0;
    pc.append(el('h2',{textContent:'Pages ('+M.pages.length+(dia?' · '+dia+' with diagrams':'')+')',style:'margin-top:0'}));
    const lead=el('p',{className:'muted',style:'font-size:14px;margin:0 0 10px'});
    lead.append(document.createTextNode('The full volume, page by page — each rendered on demand from the source scan. ◆ marks a page the vision pass flagged as carrying a diagram or figure. '));
    if(M.readerHref)lead.append(el('a',{href:M.readerHref,textContent:'Open the bilingual reader →'}));
    pc.append(lead);
    const diagrams=M.pages.filter(p=>p.kind==='diagram');
    if(diagrams.length){pc.append(el('p',{style:'font-weight:700;margin:6px 0',textContent:'Featured diagrams'}));
      const fw=el('div',{className:'thumbwall'});for(const p of diagrams.slice(0,12))fw.append(pageThumb(p));pc.append(fw);
      pc.append(el('p',{style:'font-weight:700;margin:16px 0 6px',textContent:'Every page'}));}
    const wall=el('div',{className:'thumbwall'});for(const p of M.pages)wall.append(pageThumb(p));pc.append(wall);
    left.append(pc);}

  const rel=M.related||[];
  if(rel.length){const rc=el('div',{className:'card'});
    rc.append(el('h2',{textContent:'Related manuscripts',style:'margin-top:0'}));
    for(const g of rel){const head=el('h3',{className:'relhead'});
      head.append(document.createTextNode((g.facet==='genre'?('More '+g.label):('More from '+g.label))+'  '),
                  el('a',{href:'/browse?'+g.facet+'='+encodeURIComponent(g.value),className:'muted',textContent:'see all ›'}));
      rc.append(head);const ul=el('ul',{className:'rellist'});
      for(const it of g.items)ul.append(el('li',{},[el('a',{href:'/m?id='+it.id,textContent:it.title})]));
      rc.append(ul);}
    left.append(rc);}

  // OCR only works on locally-stored images. On metadata-only manuscripts (no
  // downloaded scans) the control can do nothing, so don't show it a dead button.
  if(imgs.some(i=>i.hasLocal)){
  const ocard=el('div',{className:'card'});
  ocard.append(el('h2',{textContent:'OCR layer',style:'margin-top:0'}));
  ocard.append(el('p',{className:'muted',textContent:'OCR the stored images and keep the text (keyed by image checksum, so it survives re-crawls). Lanna/Tham has no ready model — Thai is a starting point.'}));
  const orow=el('div',{className:'savebar'});const lang=el('select',{style:'max-width:220px'});
  [['tha','Thai (tha)'],['tha+eng','Thai + English'],['lao','Lao'],['eng','English']].forEach(([v,l])=>lang.append(el('option',{value:v,textContent:l})));
  const run=el('button',{textContent:'Run OCR'});run.onclick=()=>runOcr(lang.value,run);
  orow.append(lang,run);ocard.append(orow,el('pre',{id:'log'}));left.append(ocard);
  }

  const right=el('div');const nc=el('div',{className:'card'});
  nc.append(el('h2',{textContent:'My notes & tags',style:'margin-top:0'}));
  nc.append(el('p',{className:'muted',textContent:'Saved locally, never sent anywhere, safe across re-crawls.'}));
  nc.append(el('textarea',{id:'notes',value:ANN.notes||'',placeholder:'Notes, translations, questions…'}));
  nc.append(el('label',{style:'display:block;font-weight:700;margin:12px 0 4px',textContent:'Tags (comma-separated)'}));
  nc.append(el('input',{type:'text',id:'tags',value:(ANN.tags||[]).join(', '),placeholder:'e.g. to-translate, key-source'}));
  const sb=el('div',{className:'savebar'});const save=el('button',{textContent:'Save notes'});save.onclick=()=>saveAnn(save);
  sb.append(save,el('span',{id:'savestatus',className:'muted'}));nc.append(sb);right.append(nc);

  grid.append(left,right);main.append(grid);if(imgs.length)drawPage();
}
function drawPage(){const imgs=M.images;const p=imgs[page]||{};
  document.getElementById('plabel').textContent='seq '+(p.sequence!=null?p.sequence:page+1)+'  ('+(page+1)+'/'+imgs.length+')';
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('on',t.dataset.v===view));
  const ib=document.getElementById('pageimg'),tb=document.getElementById('pagetext');ib.textContent='';tb.textContent='';
  if(view==='image'){if(p.hasLocal)ib.append(el('img',{src:'/img?sha='+encodeURIComponent(p.sha256),alt:'page '+(p.sequence),loading:'lazy'}));
    else if(p.sourceUrl){const nb=el('div',{className:'noimg'});
      nb.append(el('div',{textContent:'Scan not bundled in this copy.'}),
                el('a',{href:p.sourceUrl,target:'_blank',rel:'noopener',textContent:'View this scan at the source library ↗'}));
      ib.append(nb);}
    else ib.append(el('div',{className:'noimg',textContent:p.status==='downloaded'?'Image file missing from library.':'Not downloaded yet (status: '+(p.status||'unknown')+').'}));}
  else{if(p.ocr&&p.ocrEngine){const prov=p.ocrEngine==='claude-vlm'
        ?('VLM first-pass reading'+(p.ocrScript?' · '+p.ocrScript:'')+(p.ocrConf!=null?' · confidence '+Math.round(p.ocrConf*100)+'%':'')+' — not yet expert-verified')
        :(p.ocrEngine+' OCR'+(p.ocrScript?' · '+p.ocrScript:''));
      tb.append(el('div',{className:'muted',style:'font-size:13px;font-weight:700;margin:0 0 6px',textContent:prov}));}
    const box=el('div',{className:'textbox'});box.textContent=p.ocr||'(no OCR text yet — run OCR below)';if(!p.ocr)box.classList.add('muted');tb.append(box);}}
async function saveAnn(btn){btn.disabled=true;const tags=document.getElementById('tags').value.split(',');
  const r=await fetch('/api/annotation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:M.key,notes:document.getElementById('notes').value,tags})});
  const d=await r.json();btn.disabled=false;document.getElementById('savestatus').textContent=d.ok?'Saved ✓':(d.error||'error');
  setTimeout(()=>document.getElementById('savestatus').textContent='',2500);}
function runOcr(lang,btn){const log=document.getElementById('log');log.style.display='block';log.textContent='';btn.disabled=true;
  fetch('/api/ocr',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:parseInt(ID,10),lang})})
    .then(r=>{const rd=r.body.getReader();const dec=new TextDecoder();
      (function pump(){return rd.read().then(({done,value})=>{if(done){btn.disabled=false;load();return;}log.textContent+=dec.decode(value);log.scrollTop=log.scrollHeight;return pump();});})();})
    .catch(e=>{log.textContent+='\n'+e.message;btn.disabled=false;});}
load();
""" + "</script>")

STATUS_PAGE = page("Crawl status — wichaa", """
  .stat{display:flex;gap:22px;flex-wrap:wrap}
  .stat .box{background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px 18px;min-width:140px}
  .stat .box b{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.03em;color:var(--muted)}
  .stat .box span{font-size:26px;font-weight:800}
  table{width:100%;border-collapse:collapse;margin-top:6px}
  th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);font-size:14px;vertical-align:top}
  th{color:var(--muted);text-transform:uppercase;font-size:12px;letter-spacing:.03em}
  code{background:#eef2f1;padding:1px 6px;border-radius:5px}
  .err{color:var(--prio);font-weight:700}
""",
  "<header><div><h1>Crawl status</h1><p class=sub>What the crawler has harvested so far</p></div>" + NAV + "</header>"
  "<main id=main><p class=muted>Loading…</p></main>"
  "<script>" + r"""
const el=(t,p={},k=[])=>{const e=document.createElement(t);Object.assign(e,p);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
async function load(){const d=await (await fetch('/api/status')).json();const main=document.getElementById('main');main.textContent='';
  if(!d.dbPresent){main.append(el('div',{className:'empty'},[el('p',{textContent:'No catalog database yet.'}),el('p',{className:'muted',textContent:'Expected at: '+d.dbPath}),el('p',{className:'muted',textContent:'Run the crawler to create it, then reload this page.'})]));return;}
  const c=d.counts;const stat=el('div',{className:'stat'});
  [['Manuscripts',c.manuscripts],['Research priority',c.priority],['Images',c.images],['Downloaded',c.imagesDownloaded],['Pending',c.imagesPending]]
    .forEach(([l,v])=>stat.append(el('div',{className:'box'},[el('b',{textContent:l}),el('span',{textContent:v})])));
  const sc=el('div',{className:'card'});sc.append(el('h2',{textContent:'Sources',style:'margin-top:0'}),stat);main.append(sc);
  if(d.sources.length){const t=el('table');t.append(el('tr',{},['Name','Type','Status','Base URL','Last crawled'].map(h=>el('th',{textContent:h}))));
    for(const s of d.sources)t.append(el('tr',{},[s.name,s.api_type,s.status,s.base_url||'',s.last_crawled||''].map((v,i)=>el('td',i===2&&s.status==='error'?{className:'err',textContent:v}:{textContent:v}))));
    sc.append(t);}else sc.append(el('p',{className:'muted',textContent:'No sources registered yet.'}));
  const lc=el('div',{className:'card'});lc.append(el('h2',{textContent:'Recent crawl log',style:'margin-top:0'}));
  if(d.log.length){const t=el('table');t.append(el('tr',{},['When','Source','Action','Ref','HTTP','Records','Status','Notes'].map(h=>el('th',{textContent:h}))));
    for(const g of d.log)t.append(el('tr',{},[g.ts,g.source,g.action,g.ref,g.http_status,g.n_records,g.status,g.notes].map((v,i)=>el('td',i===6&&g.status==='error'?{className:'err',textContent:v==null?'':v}:{textContent:v==null?'':v}))));
    lc.append(t);}else lc.append(el('p',{className:'muted',textContent:'No crawl activity logged yet.'}));
  main.append(lc);}
load();
""" + "</script>")


OVERVIEW_PAGE = page("Overview — wichaa", """
  .hero{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:8px}
  .hbox{display:block;background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px 20px;min-width:150px;text-decoration:none;color:inherit}
  .hbox:hover{border-color:var(--teal);box-shadow:0 1px 4px #0001}
  .hbox b{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.03em;color:var(--muted)}
  .hbox span{font-size:30px;font-weight:800;color:var(--teal)}
  .hbox.prio span{color:var(--prio)}
  h2.sec{margin:22px 0 4px;font-size:18px}
  .lead{color:var(--muted);margin:0 0 12px}
  .gitem{display:block;color:inherit;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:#fff;margin:0 0 8px}
  .gitem:hover{border-color:var(--teal);box-shadow:0 1px 4px #0001}
  .gtop{display:flex;align-items:baseline;gap:10px}
  .gtop .gl{font-weight:800;font-size:16px}
  .gtop .gl a{color:var(--teal);text-decoration:none}
  .gtop .gl a:hover{text-decoration:underline}
  .gfoot{margin-top:8px;font-size:14px}
  .gfoot a{color:var(--focus);text-decoration:none;font-weight:700;margin-right:16px}
  .gfoot a:hover{text-decoration:underline}
  .gbadge{font-size:12px;font-weight:700;color:var(--gold);background:var(--gold-bg);border:1px solid #e5cf9a;border-radius:999px;padding:1px 8px;margin-left:8px}
  .gtop .gn{margin-left:auto;font-weight:800}
  .gnote{color:var(--muted);font-size:14px;margin:2px 0 6px}
  .btrack{display:block;height:8px;background:#e7eeeb;border-radius:6px;overflow:hidden}
  .bfill{display:block;height:100%;background:var(--teal);border-radius:6px}
  .bfill.prio{background:var(--prio)}
  .pillgrid{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:6px}
  .pilllink{display:inline-flex;align-items:center;gap:8px;text-decoration:none;border:1px solid var(--line);background:#fff;color:var(--ink);border-radius:999px;padding:6px 8px 6px 14px;font-weight:700;font-size:15px}
  .pilllink:hover{border-color:var(--teal)}
  .pilllink.script{background:var(--gold-bg);border-color:#e5cf9a;color:var(--gold)}
  .pn{background:#eef2f1;color:var(--muted);border-radius:999px;padding:1px 9px;font-size:13px}
  .cols{display:grid;grid-template-columns:1fr 1fr;gap:18px}
  @media(max-width:820px){.cols{grid-template-columns:1fr}}
  .foliohero{position:relative;display:block;border-radius:12px;overflow:hidden;border:1px solid var(--line);margin:0 0 18px;background:#1a1712;text-decoration:none}
  .foliohero img{display:block;width:100%;height:clamp(200px,34vw,360px);object-fit:cover;object-position:center 32%}
  .foliohero .cap{position:absolute;left:0;right:0;bottom:0;padding:26px 18px 12px;color:#fff;background:linear-gradient(transparent,#000c);font-weight:700}
  .foliohero .cap small{display:block;font-weight:600;opacity:.85;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
  .thumbwall{display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:8px}
  .tw{display:block;position:relative;aspect-ratio:3/4;border-radius:8px;overflow:hidden;border:1px solid var(--line);background:#f0efe9}
  .tw img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .18s ease}
  .tw:hover{border-color:var(--teal);box-shadow:0 1px 6px #0002}
  .tw:hover img{transform:scale(1.05)}
  .ways{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px}
  .wdoor{display:block;text-decoration:none;color:inherit;border:1px solid var(--line);border-radius:10px;background:#fff;padding:12px 14px}
  .wdoor:hover{border-color:var(--teal);box-shadow:0 1px 6px #0001}
  .wdoor .wl{font-weight:800;font-size:16px;color:var(--teal)}
  .wdoor .wh{color:var(--ink);font-size:14px;line-height:1.5;margin:3px 0 0}
  .wdoor .wn{color:var(--muted);font-size:12px;font-weight:700;margin-top:5px}
""",
  "<header><div><h1>wichaa</h1><p class=sub>Making living traditions of sacred knowledge legible — ground truth for people and machines</p></div>" + NAV + "</header>"
  "<main id=main><p class=muted>Loading…</p></main>"
  "<script>" + r"""
const el=(t,p={},k=[])=>{const e=document.createElement(t);Object.assign(e,p);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
const B='/browse?';
function pills(list,key,cls){const w=el('div',{className:'pillgrid'});
  for(const r of list)w.append(el('a',{className:'pilllink'+(cls?' '+cls:''),href:B+key+'='+encodeURIComponent(r.value)},
    [document.createTextNode(r.label+' '),el('span',{className:'pn',textContent:r.n})]));
  return w;}
function section(main,title,lead,node){const card=el('div',{className:'card'});
  card.append(el('h2',{className:'sec',textContent:title,style:'margin-top:0'}));
  if(lead)card.append(el('p',{className:'lead',textContent:lead}));
  card.append(node);main.append(card);}
const SEED=Math.floor(Date.now()/86400000);  // stable within a day; caches thumbs
async function folioWall(main){
  let f;try{f=await (await fetch('/api/folios?limit=48&seed='+SEED)).json();}catch(e){return;}
  if(!f||!f.folios||!f.folios.length)return;
  const list=f.folios;
  // one hero (first folio big), the rest as a thumbnail wall
  const h=list[0];
  const hero=el('a',{className:'foliohero',href:'/m?id='+h.id,title:h.title});
  hero.append(el('img',{src:'/img?sha='+h.sha+'&w=1200',alt:h.title,loading:'eager'}));
  hero.append(el('div',{className:'cap'},[el('small',{textContent:'From the library · manuscript #'+h.id+(h.seq!=null?' · folio '+h.seq:'')}),document.createTextNode(h.title)]));
  main.prepend(hero);
  const wall=el('div',{className:'thumbwall'});
  for(const it of list.slice(1)){
    const a=el('a',{className:'tw',href:'/m?id='+it.id,title:it.title+' — folio '+(it.seq!=null?it.seq:'')});
    a.append(el('img',{src:'/img?sha='+it.sha+'&w=240',alt:it.title,loading:'lazy'}));
    wall.append(a);}
  const card=el('div',{className:'card'});
  card.append(el('h2',{className:'sec',textContent:'From the library',style:'margin-top:0'}),
    el('p',{className:'lead'},[document.createTextNode('Photographs of the folios themselves — the manuscript pages as they were digitised at the source, not transcriptions or descriptions of them. '+(f.total||0).toLocaleString()+' have been drawn into the library so far, each held under its own checksum so a page is never stored twice, and the number grows as the crawl runs. Below is a shuffled handful: open any folio to read what the catalogue records of its manuscript and provenance, or browse the '),el('a',{href:'/gallery',textContent:'plates gallery'}),document.createTextNode(' for the rendered diagrams and captioned pages.')]),
    wall);
  main.append(card);
}
async function load(){const d=await (await fetch('/api/overview')).json();const main=document.getElementById('main');main.textContent='';
  if(!d.dbPresent){main.append(el('div',{className:'empty'},[el('p',{textContent:'No catalog database yet.'}),el('p',{className:'muted',textContent:'Run the crawler, then reload.'})]));return;}
  const c=d.counts;
  const hero=el('div',{className:'hero'});
  hero.append(el('a',{className:'hbox',href:'/browse'},[el('b',{textContent:'Manuscripts'}),el('span',{textContent:(c.manuscripts||0).toLocaleString()})]));
  hero.append(el('a',{className:'hbox prio',href:B+'priority='+encodeURIComponent('Research priority')},[el('b',{textContent:'Research priority'}),el('span',{textContent:(d.priority||0).toLocaleString()})]));
  hero.append(el('a',{className:'hbox',href:'/status'},[el('b',{textContent:'Sources'}),el('span',{textContent:c.sources||0})]));
  hero.append(el('a',{className:'hbox',href:'/browse?sort=images'},[el('b',{textContent:'With images'}),el('span',{textContent:(d.withImages||0).toLocaleString()})]));
  const top=el('div',{className:'card'});top.append(el('h2',{className:'sec',textContent:'Overview',style:'margin-top:0'}),hero,
    el('p',{className:'lead',style:'margin-bottom:0'},[document.createTextNode('A working catalogue of Northern Thai (Lanna) manuscripts — one tradition of the wichaa corpus, alongside the amulet market and St. Expedite — gathered from several digital collections into one place where people and machines can read it plainly. Every figure on this page is also a filter — click any genre, place, script, or source to see just those manuscripts, or '),el('a',{href:'/browse',textContent:'open the full browser'}),document.createTextNode(' to search across all of them.')]));
  main.append(top);
  // Ways in — meaning-first doors into the heart of the tradition, before the axes.
  if(d.waysIn&&d.waysIn.length){const wg=el('div',{className:'ways'});
    for(const w of d.waysIn){const a=el('a',{className:'wdoor',href:w.href});
      a.append(el('div',{className:'wl',textContent:w.label}));
      if(w.hook)a.append(el('div',{className:'wh',textContent:w.hook}));
      a.append(el('div',{className:'wn',textContent:w.n.toLocaleString()+' manuscript'+(w.n===1?'':'s')+(w.hasArticle?' · read the article →':'')}));
      wg.append(a);}
    section(main,'Ways in — the heart of the wichaa','The living subjects at the core of the tradition: the seer-sages, the sacred diagrams, the almanacs and rites. Meet them by name — each opens an article drawn from the manuscripts that carry it. Not sure where to begin? Open one of these first.',wg);}
  // genres
  const gmax=Math.max(1,...d.genres.map(g=>g.n));
  const gwrap=el('div');
  for(const g of d.genres){const box=el('div',{className:'gitem'});
    const art='/a?s=genre:'+encodeURIComponent(g.value);
    const gt=el('div',{className:'gtop'});
    gt.append(el('span',{className:'gl'},[el('a',{href:art,textContent:(g.priority?'★ ':'')+g.label})]));
    gt.append(el('span',{className:'gn',textContent:g.n.toLocaleString()}));box.append(gt);
    if(g.note)box.append(el('div',{className:'gnote',textContent:g.note}));
    const tr=el('span',{className:'btrack'});tr.append(el('span',{className:'bfill'+(g.priority?' prio':''),style:'width:'+Math.max(3,Math.round(100*g.n/gmax))+'%'}));box.append(tr);
    box.append(el('div',{className:'gfoot'},[el('a',{href:art,textContent:'Read the article ›'}),el('a',{href:B+'genre='+encodeURIComponent(g.value),textContent:'Browse all '+g.n.toLocaleString()+' ›'})]));
    gwrap.append(box);}
  section(main,'Genres','How the catalogue divides by kind of text — the work a manuscript was made to do, from chronicles and jataka tales to herbal medicine, astrology, divination and ritual magic. These labels are normalised from each source\u2019s own cataloguing, so one genre here may gather several original descriptions. Each has an article drawn from the manuscripts it holds; ★ marks the research-priority genres (astrology, magic, divination).',gwrap);
  // two-column axis pills
  const cols=el('div',{className:'cols'});
  const left=el('div'),right=el('div');
  function box(parent,title,lead,list,key,cls){if(!list||!list.length)return;const card=el('div',{className:'card'});
    card.append(el('h2',{className:'sec',textContent:title,style:'margin-top:0'}));
    if(lead)card.append(el('p',{className:'lead',textContent:lead}));
    card.append(pills(list,key,cls));parent.append(card);}
  box(left,'Script','The alphabet a manuscript is written in — Tham (Dhamma) script, Fak Kham, Thai Nithet and others. The script is a fact of the physical page, and often the first thing a cataloguer can read even when the date and author are unknown.',d.scripts,'script','script');
  box(left,'Language','The language of the words themselves, which need not match the script: Northern Thai, Central Thai, Pali, and mixtures of them all appear. A Pali verse, for instance, is commonly written out in Tham script.',d.languages,'language');
  box(left,'Century','When a manuscript can be dated, grouped by century. Many carry no firm date, so this axis covers only the portion the catalogue is able to place in time — it is a floor, not the whole collection.',d.centuries,'century');
  box(right,'Province','The present-day province where a manuscript was documented or is kept. This records where the text was found or held, which is not always where it was first written.',d.provinces,'province');
  box(right,'Source','The digital collection each record was harvested from. Following a source shows exactly which institution\u2019s cataloguing stands behind those manuscripts, so a claim can always be traced back to who made it.',d.sources,'source');
  cols.append(left,right);main.append(cols);
  // temples full-width (long tail)
  if(d.temples&&d.temples.length){const card=el('div',{className:'card'});
    card.append(el('h2',{className:'sec',textContent:'Temples that hold the collection',style:'margin-top:0'}),
      el('p',{className:'lead',textContent:'The temples (wat) credited with holding or yielding the most manuscripts so far. In Lanna the monastery was the ordinary keeper of written knowledge, so a wat is often the clearest record of where a text lived — and, through it, of the community that made and used it.'}),pills(d.temples,'temple'));
    main.append(card);}
  folioWall(main);
}
load();
""" + "</script>")


DASHBOARD_PAGE = page("Dashboard — wichaa", """
  .hero{display:flex;gap:16px;flex-wrap:wrap;margin:0 0 6px}
  .hbox{display:block;background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px 20px;min-width:150px;text-decoration:none;color:inherit}
  .hbox:hover{border-color:var(--teal);box-shadow:0 1px 4px #0001}
  .hbox b{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.03em;color:var(--muted)}
  .hbox span{font-size:30px;font-weight:800;color:var(--teal)}
  .hbox.prio span{color:var(--prio)}
  .hbox small{color:var(--muted);font-weight:600}
  h2.sec{margin:0 0 4px;font-size:18px}
  .lead{color:var(--muted);margin:0 0 14px;max-width:70ch}
  .covrow{display:grid;grid-template-columns:200px 1fr 120px;grid-template-areas:'l b n';align-items:center;gap:12px;margin:0 0 8px}
  @media(max-width:640px){.covrow{grid-template-columns:140px 1fr;grid-template-areas:'l b' 'l n'}}
  .covrow .cl{font-weight:700}
  .covrow .cl a{color:var(--teal);text-decoration:none}
  .covrow .cl a:hover{text-decoration:underline}
  .covrow .cl .star{color:var(--prio)}
  .cbar{position:relative;height:22px;background:#e7eeeb;border-radius:6px;overflow:hidden}
  .cfill{position:absolute;left:0;top:0;height:100%;background:var(--teal);border-radius:6px}
  .cnum{font-size:14px;color:var(--muted);white-space:nowrap}
  .cnum b{color:var(--ink)}
  .dwrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:#fff}
  table.heat{border-collapse:collapse;font-size:14px;min-width:100%}
  table.heat th,table.heat td{border:1px solid #eef2f1;text-align:center;padding:0}
  table.heat thead th{background:#f4f8f7;color:var(--ink);font-weight:800;padding:8px 10px;position:sticky;top:0}
  table.heat th.rowh{text-align:left;background:#fff;font-weight:700;padding:8px 12px;white-space:nowrap;position:sticky;left:0;z-index:1}
  table.heat th.rowh a{color:var(--teal);text-decoration:none}
  table.heat th.rowh a:hover{text-decoration:underline}
  table.heat th.rowh .star{color:var(--prio)}
  table.heat th.corner{background:#f4f8f7;position:sticky;left:0;top:0;z-index:2}
  table.heat td.c{padding:0}
  table.heat td.c a{display:block;padding:10px 12px;min-width:46px;text-decoration:none;color:inherit;font-weight:700}
  table.heat td.c a:hover{outline:2px solid var(--focus);outline-offset:-2px}
  table.heat td.c.empty{color:#c8d3d0}
  table.heat tfoot th{background:#f9fbfa;font-weight:800;padding:8px 10px;color:var(--muted)}
  .tot{font-weight:800;color:var(--muted)}
  .card+.card{margin-top:18px}
  .tl{display:flex;align-items:flex-end;gap:10px;height:180px;padding:6px 2px 0}
  .tlcol{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;text-decoration:none;color:inherit;min-width:40px}
  .tlbar{width:100%;max-width:64px;background:#cfe0dc;border-radius:6px 6px 0 0;position:relative;display:flex;align-items:flex-end;overflow:hidden}
  .tlbar .pr{width:100%;background:var(--prio);position:absolute;left:0;bottom:0}
  .tlcol:hover .tlbar{outline:2px solid var(--focus);outline-offset:2px}
  .tln{font-weight:800;font-size:14px;margin-bottom:4px}
  .tlx{font-size:13px;color:var(--muted);margin-top:6px;font-weight:700}
""",
  "<header><div><h1>Dashboard</h1><p class=sub>The collection, cross-tabulated — coverage, place, and time</p></div>" + NAV + "</header>"
  "<main id=main><p class=muted>Loading…</p></main>"
  "<script>" + r"""
const el=(t,p={},k=[])=>{const e=document.createElement(t);Object.assign(e,p);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
const B='/browse?';
const enc=encodeURIComponent;
function ramp(ratio){ // teal intensity; text flips to white when dark
  const a=ratio<=0?0:0.10+0.85*ratio;
  return {bg:'rgba(13,107,107,'+a.toFixed(3)+')', fg:ratio>0.55?'#fff':'var(--ink)'};
}
function card(main,title,lead){const c=el('div',{className:'card'});
  c.append(el('h2',{className:'sec',textContent:title}));
  if(lead)c.append(el('p',{className:'lead',textContent:lead}));
  main.append(c);return c;}
function coverage(main,cov,totals){
  const c=card(main,'Digitization coverage',
    'How much of each genre has at least one page image downloaded. The crawl is early — most witnesses are catalogued but not yet imaged, which is simply the digitization backlog. ★ marks the research-priority genres.');
  const max=Math.max(1,...cov.map(g=>g.n));
  for(const g of cov){
    const row=el('div',{className:'covrow'});
    const lbl=el('div',{className:'cl',style:'grid-area:l'});
    if(g.priority)lbl.append(el('span',{className:'star',textContent:'★ '}));
    lbl.append(el('a',{href:B+'genre='+enc(g.value),textContent:g.label}));
    row.append(lbl);
    const bar=el('div',{className:'cbar',style:'grid-area:b'});
    bar.append(el('div',{className:'cfill',style:'width:'+Math.round(100*g.digitized/max)+'%'}));
    // faint full-width marker of total via track already; show total as ghost width
    bar.title=g.digitized.toLocaleString()+' of '+g.n.toLocaleString()+' digitized';
    row.append(bar);
    row.append(el('div',{className:'cnum',style:'grid-area:n'},
      [el('b',{textContent:g.digitized.toLocaleString()}),document.createTextNode(' / '+g.n.toLocaleString())]));
    c.append(row);
  }
}
function timeline(main,tl){
  if(!tl||!tl.length)return;
  const c=card(main,'Timeline of dated copying',
    'Surviving manuscripts by estimated century of copying. The maroon portion is the research-priority (wichaa) share — astrology, magic, divination. Click a century to browse it.');
  const max=Math.max(1,...tl.map(t=>t.n));
  const band=el('div',{className:'tl'});
  for(const t of tl){
    const col=el('a',{className:'tlcol',href:B+'century='+enc(t.value),
      title:t.label+': '+t.n.toLocaleString()+' dated manuscripts ('+t.prio.toLocaleString()+' priority)'});
    col.append(el('div',{className:'tln',textContent:t.n.toLocaleString()}));
    const h=Math.max(4,Math.round(150*t.n/max));
    const bar=el('div',{className:'tlbar',style:'height:'+h+'px'});
    if(t.prio)bar.append(el('div',{className:'pr',style:'height:'+Math.round(100*t.prio/t.n)+'%'}));
    col.append(bar,el('div',{className:'tlx',textContent:t.label}));
    band.append(col);
  }
  c.append(band);
}
function heat(main,h){
  const c=card(main,h.title,h.lead);
  const wrap=el('div',{className:'dwrap'});
  const tbl=el('table',{className:'heat'});
  // head
  const thead=el('thead');const hr=el('tr');
  hr.append(el('th',{className:'corner',textContent:h.rowkey.charAt(0).toUpperCase()+h.rowkey.slice(1)}));
  for(const col of h.cols)hr.append(el('th',{scope:'col'},
    [document.createTextNode(col.label),el('div',{className:'tot',style:'font-size:12px',textContent:col.total.toLocaleString()})]));
  thead.append(hr);tbl.append(thead);
  // body
  const tb=el('tbody');
  for(const row of h.rows){
    const tr=el('tr');
    const rh=el('th',{className:'rowh',scope:'row'});
    if(row.priority)rh.append(el('span',{className:'star',textContent:'★ '}));
    rh.append(el('a',{href:B+h.rowkey+'='+enc(row.value),textContent:row.label}),
      el('span',{className:'tot',style:'margin-left:8px;font-weight:700',textContent:row.total.toLocaleString()}));
    tr.append(rh);
    const cells=h.cells[row.value]||{};
    for(const col of h.cols){
      const n=cells[col.value]||0;
      if(!n){tr.append(el('td',{className:'c empty'},[el('span',{style:'display:block;padding:10px 12px',textContent:'·'})]));continue;}
      const r=ramp(n/h.max);
      const td=el('td',{className:'c'});
      const a=el('a',{href:B+'genre='+enc(row.value)+'&'+h.colkey+'='+enc(col.value),
        style:'background:'+r.bg+';color:'+r.fg,
        title:row.label+' · '+col.label+': '+n.toLocaleString()+' manuscripts — click to browse',
        textContent:n.toLocaleString()});
      td.append(a);tr.append(td);
    }
    tb.append(tr);
  }
  tbl.append(tb);wrap.append(tbl);c.append(wrap);
}
async function load(){
  const d=await (await fetch('/api/dashboard')).json();
  const main=document.getElementById('main');main.textContent='';
  if(!d.dbPresent){main.append(el('div',{className:'empty'},[el('p',{textContent:'No catalog database yet.'}),el('p',{className:'muted',textContent:'Run the crawler, then reload.'})]));return;}
  const t=d.totals||{};
  const hero=el('div',{className:'hero'});
  hero.append(el('a',{className:'hbox',href:'/browse'},[el('b',{textContent:'Manuscripts'}),el('span',{textContent:(t.manuscripts||0).toLocaleString()})]));
  hero.append(el('a',{className:'hbox prio',href:B+'priority='+enc('Research priority')},[el('b',{textContent:'Research priority'}),el('span',{textContent:(t.priority||0).toLocaleString()})]));
  hero.append(el('a',{className:'hbox',href:'/browse?sort=images'},[el('b',{textContent:'Digitized'}),el('span',{textContent:(t.digitized||0).toLocaleString()}),el('small',{textContent:'have page images'})]));
  const htop=el('div',{className:'card'});htop.append(hero);main.append(htop);
  coverage(main,d.coverage||[],t);
  timeline(main,d.timeline||[]);
  for(const h of (d.heatmaps||[]))heat(main,h);
  // linked-data export footer
  const ex=el('div',{className:'card'});
  ex.append(el('h2',{className:'sec',textContent:'Linked-data export',style:'margin-top:0'}),
    el('p',{className:'lead'},[document.createTextNode('The authored knowledge graph (entities, genres and their typed relations) travels as first-class RDF triples: '),
      el('a',{href:'/api/graph.jsonld',textContent:'JSON-LD'}),document.createTextNode(' · '),
      el('a',{href:'/api/graph.ttl',textContent:'Turtle'}),document.createTextNode(' · '),
      el('a',{href:'/api/graph',textContent:'raw JSON'}),document.createTextNode('.')]));
  main.append(ex);
}
load();
""" + "</script>")


MAP_PAGE = page("Map — wichaa", """
  .lead{color:var(--muted);margin:0 0 14px;max-width:72ch}
  .maprow{display:grid;grid-template-columns:1fr 300px;gap:18px}
  @media(max-width:860px){.maprow{grid-template-columns:1fr}}
  .mapbox{background:linear-gradient(#f2f7f6,#eaf1ef);border:1px solid var(--line);border-radius:12px;overflow:hidden}
  svg.map{display:block;width:100%;height:auto}
  svg.map .dot{fill:var(--teal);fill-opacity:.72;stroke:#0a4f4f;stroke-width:1.5;cursor:pointer;transition:fill-opacity .1s}
  svg.map a:hover .dot{fill-opacity:.95}
  svg.map a:focus .dot{outline:none;stroke:var(--focus);stroke-width:3}
  svg.map .lbl{font-size:20px;font-weight:700;fill:var(--ink);paint-order:stroke;stroke:#fff;stroke-width:4px}
  svg.map .cnt{font-size:17px;font-weight:800;fill:#fff}
  .plist{list-style:none;margin:0;padding:0}
  .plist li{margin:0 0 6px}
  .plist a{display:flex;justify-content:space-between;gap:10px;text-decoration:none;color:inherit;border:1px solid var(--line);background:#fff;border-radius:8px;padding:8px 12px;font-weight:700}
  .plist a:hover{border-color:var(--teal)}
  .plist .pn{background:#eef2f1;color:var(--muted);border-radius:999px;padding:1px 10px;font-size:13px}
  .side h2{font-size:16px;margin:0 0 8px}
  .unplaced{color:var(--muted);font-size:14px;margin-top:14px}
""",
  "<header><div><h1>Map of provenance</h1><p class=sub>Where the surviving manuscripts come from</p></div>" + NAV + "</header>"
  "<main id=main><p class=muted>Loading…</p></main>"
  "<script>" + r"""
const SVGNS='http://www.w3.org/2000/svg';
const el=(t,p={},k=[])=>{const e=document.createElement(t);Object.assign(e,p);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
const svg=(t,a={},k=[])=>{const e=document.createElementNS(SVGNS,t);for(const[n,v]of Object.entries(a))e.setAttribute(n,v);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
const B='/browse?';const enc=encodeURIComponent;
async function load(){
  const d=await (await fetch('/api/places')).json();
  const main=document.getElementById('main');main.textContent='';
  if(!d.dbPresent){main.append(el('div',{className:'empty'},[el('p',{textContent:'No catalog database yet.'})]));return;}
  main.append(el('p',{className:'lead',textContent:'Each dot is a province, sized by how many manuscripts trace to it — the Lanna heartland of Phrae, Lampang, Chiang Mai, Nan and their neighbours. Click a dot (or a name in the list) to browse everything from that place.'}));
  const row=el('div',{className:'maprow'});
  // --- SVG dot-map ---
  const bb=d.bbox;const box=el('div',{className:'mapbox'});
  const s=svg('svg',{class:'map',viewBox:'0 0 '+bb.w+' '+bb.h,role:'img','aria-label':'Provenance map'});
  const rmax=Math.sqrt(d.max||1);
  // draw larger dots first so small ones stay clickable on top
  const sorted=[...d.places].sort((a,b)=>b.n-a.n);
  for(const p of sorted){
    const r=14+56*(Math.sqrt(p.n)/rmax);
    const a=svg('a',{href:B+'province='+enc(p.value)});
    a.append(svg('title',{},p.label+': '+p.n.toLocaleString()+' manuscripts'));
    a.append(svg('circle',{class:'dot',cx:p.x,cy:p.y,r:r}));
    if(p.n/(d.max||1)>0.18)a.append(svg('text',{class:'cnt',x:p.x,y:p.y+6,'text-anchor':'middle'},p.n.toLocaleString()));
    a.append(svg('text',{class:'lbl',x:p.x,y:p.y-r-6,'text-anchor':'middle'},p.label));
    s.append(a);
  }
  box.append(s);row.append(box);
  // --- side list ---
  const side=el('div',{className:'side'});
  side.append(el('h2',{textContent:'By province'}));
  const ul=el('ul',{className:'plist'});
  for(const p of d.places){ul.append(el('li',{},[el('a',{href:B+'province='+enc(p.value)},
    [document.createTextNode(p.label),el('span',{className:'pn',textContent:p.n.toLocaleString()})])]));}
  side.append(ul);
  if(d.unplaced&&d.unplaced.length){
    const total=d.unplaced.reduce((s,u)=>s+u.n,0);
    side.append(el('p',{className:'unplaced',textContent:d.unplaced.length+' other provenance labels ('+total.toLocaleString()+' manuscripts) are district- or temple-level and not yet placed on the map.'}));
  }
  row.append(side);
  const card=el('div',{className:'card'});card.append(row);main.append(card);
}
load();
""" + "</script>")


GRAPH_PAGE = page("Graph — wichaa", """
  .lead{color:var(--muted);margin:0 0 14px;max-width:76ch}
  .controls{display:flex;align-items:center;gap:18px;flex-wrap:wrap;margin:0 0 12px}
  .legend{display:flex;gap:16px;flex-wrap:wrap;color:var(--muted);font-weight:700;font-size:14px}
  .legend .lg{display:inline-flex;align-items:center;gap:6px}
  .card.nopad{padding:0;overflow:hidden;border:none}
  .graphbox{background:radial-gradient(120% 120% at 50% 38%,#123f3a 0%,#0a2422 55%,#061715 100%);position:relative}
  svg.graph{display:block;width:100%;height:auto;touch-action:none;cursor:grab}
  svg.graph:active{cursor:grabbing}
  svg.graph .edge{fill:none;stroke:#6fb9ae;stroke-opacity:.30;stroke-width:1.4;stroke-linecap:round}
  svg.graph .edge.edge-on{stroke:#8ff3e4;stroke-opacity:.95;stroke-width:2.6;filter:drop-shadow(0 0 4px rgba(120,240,220,.8))}
  svg.graph .edge.dim{stroke-opacity:.05}
  svg.graph .plbl{font-size:12.5px;font-weight:800;fill:#dffaf5;paint-order:stroke;stroke:#04110f;stroke-width:3px;pointer-events:none;opacity:0;transition:opacity .12s}
  svg.graph .plbl.show{opacity:1}
  svg.graph .node{cursor:pointer}
  svg.graph .halo{pointer-events:none;opacity:.5;transition:opacity .12s}
  svg.graph .dot{stroke:rgba(255,255,255,.85);stroke-width:1.5}
  svg.graph .node:focus{outline:none}
  svg.graph .node:focus .dot,svg.graph .node.hot .dot{stroke:#fff;stroke-width:3}
  svg.graph .node.hot .halo,svg.graph .node.nbr .halo{opacity:1}
  svg.graph .nlbl{font-size:15px;font-weight:700;fill:#f3fbf9;paint-order:stroke;stroke:#04110f;stroke-width:3.5px;pointer-events:none}
  svg.graph .node.dim{opacity:.13}
  svg.graph .node.dim .nlbl{opacity:.6}
  svg.graph .node,svg.graph .edge{transition:opacity .12s}
  .foot{color:var(--muted);font-size:14px;margin:12px 0 0}
""",
  "<header><div><h1>Relationship graph</h1><p class=sub>The web of subjects, genres and how they connect</p></div>" + NAV + "</header>"
  "<main id=main><p class=muted>Loading…</p></main>"
  "<script>" + r"""
const SVGNS='http://www.w3.org/2000/svg';
const el=(t,p={},k=[])=>{const e=document.createElement(t);Object.assign(e,p);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
const svg=(t,a={},k=[])=>{const e=document.createElementNS(SVGNS,t);for(const[n,v]of Object.entries(a))e.setAttribute(n,v);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
const W=1000,H=680,CX=W/2,CY=H/2;
const COL={entity:'#3fcbb9',genre:'#e6b24d',subgenre:'#69b0ee'};
const GRAD={entity:['#7ff0e0','#158a7d'],genre:['#ffd9a0','#a06a12'],subgenre:['#a9d8ff','#2c6aa8']};
const TYPELBL={entity:'Subject',genre:'Genre',subgenre:'Subgenre'};
const REP=9000,LEN=125,SPRING=0.028,GRAV=0.016,DAMP=0.9;
let NODES=[],LINKS=[],byKey={},view={x:0,y:0,k:1};
let alpha=1,running=false,dragNode=null,dragStart=null,moved=false;
let panning=false,panStart=null;
let s,vp,gEdges,gNodes;
function shorten(t){t=t.split('(')[0].trim();return t.length>22?t.slice(0,21)+'…':t;}
function evtVB(e){const r=s.getBoundingClientRect();return{x:(e.clientX-r.left)/r.width*W,y:(e.clientY-r.top)/r.height*H};}
function toGraph(pt){return{x:(pt.x-view.x)/view.k,y:(pt.y-view.y)/view.k};}
function applyView(){vp.setAttribute('transform','translate('+view.x+','+view.y+') scale('+view.k+')');}
async function load(){
  const d=await (await fetch('/api/graph')).json();
  const main=document.getElementById('main');main.textContent='';
  if(!d.nodes||!d.nodes.length){main.append(el('div',{className:'empty'},[el('p',{textContent:'The relationship graph is empty until the catalog exists and relations are authored in data/relations.json.'})]));return;}
  main.append(el('p',{className:'lead',textContent:'Every subject, genre and subgenre in the archive, wired by the authored relations between them. Drag a node to pull the web around; hover to isolate its links; click to open its article. Scroll to zoom, drag the background to pan.'}));
  NODES=d.nodes.map(n=>({key:n.key,label:n.label,type:n.type,x:CX+(Math.random()-.5)*440,y:CY+(Math.random()-.5)*320,vx:0,vy:0,deg:0}));
  byKey={};NODES.forEach(n=>byKey[n.key]=n);
  const seen=new Set();LINKS=[];
  for(const l of d.links){const a=byKey[l.s],b=byKey[l.o];if(!a||!b)continue;const id=[l.s,l.o,l.p].join('|');if(seen.has(id))continue;seen.add(id);a.deg++;b.deg++;LINKS.push({a,b,p:l.p,fwd:((d.predicates[l.p]||{}).forward)||l.p});}
  NODES.forEach(n=>n.r=9+3*Math.sqrt(n.deg));
  buildControls(main);buildSvg(main);
  main.append(el('p',{className:'foot'},[document.createTextNode('Prefer reading? Every subject\u2019s relations are also listed in plain text on its '),el('a',{href:'/articles',textContent:'article'}),document.createTextNode(' page.')]));
  view={x:0,y:0,k:1};applyView();settle(350);render();reheat();
}
function buildControls(main){
  const bar=el('div',{className:'controls'});
  bar.append(el('button',{className:'secondary',textContent:'Reheat layout',onclick:()=>{scatter();reheat();}}));
  const lg=el('div',{className:'legend'});
  for(const t of ['entity','genre','subgenre']){
    lg.append(el('span',{className:'lg'},[svg('svg',{width:16,height:16,viewBox:'0 0 16 16'},[svg('circle',{cx:8,cy:8,r:6,fill:COL[t]})]),document.createTextNode(TYPELBL[t])]));
  }
  bar.append(lg);main.append(bar);
}
function buildSvg(main){
  s=svg('svg',{class:'graph',viewBox:'0 0 '+W+' '+H,role:'img','aria-label':'Interactive relationship graph of subjects, genres and their authored connections'});
  const defs=svg('defs',{});
  for(const t of ['entity','genre','subgenre']){
    const rg=svg('radialGradient',{id:'g-'+t,cx:'35%',cy:'32%',r:'75%'});
    rg.append(svg('stop',{offset:'0%','stop-color':GRAD[t][0]}),svg('stop',{offset:'100%','stop-color':GRAD[t][1]}));
    defs.append(rg);
    const hg=svg('radialGradient',{id:'h-'+t,cx:'50%',cy:'50%',r:'50%'});
    hg.append(svg('stop',{offset:'0%','stop-color':COL[t],'stop-opacity':'.55'}),svg('stop',{offset:'55%','stop-color':COL[t],'stop-opacity':'.18'}),svg('stop',{offset:'100%','stop-color':COL[t],'stop-opacity':'0'}));
    defs.append(hg);
  }
  const mk=svg('marker',{id:'arrow',viewBox:'0 0 10 10',refX:'9',refY:'5',markerWidth:'6.5',markerHeight:'6.5',orient:'auto-start-reverse'});
  mk.append(svg('path',{d:'M0,0 L10,5 L0,10 z',fill:'#8ff3e4','fill-opacity':'.9'}));
  defs.append(mk);
  s.append(defs);
  vp=svg('g',{});gEdges=svg('g',{});const gLbls=svg('g',{});gNodes=svg('g',{});vp.append(gEdges,gLbls,gNodes);s.append(vp);
  for(const l of LINKS){
    l.line=svg('path',{class:'edge'});
    l.line.append(svg('title',{},l.a.label+'  \u2014'+l.fwd+'\u2192  '+l.b.label));
    gEdges.append(l.line);
    l.plbl=svg('text',{class:'plbl','text-anchor':'middle'},l.fwd);
    gLbls.append(l.plbl);
  }
  for(const n of NODES){
    const g=svg('g',{class:'node',tabindex:'0',role:'link','aria-label':n.label+' ('+(TYPELBL[n.type]||n.type)+'), '+n.deg+' connections'});
    n.halo=svg('circle',{class:'halo',r:n.r*2.4,fill:'url(#h-'+n.type+')'});
    n.circle=svg('circle',{class:'dot',r:n.r,fill:'url(#g-'+(GRAD[n.type]?n.type:'entity')+')'});
    n.text=svg('text',{class:'nlbl','text-anchor':'middle',x:0,y:n.r+16},shorten(n.label));
    g.append(n.halo,n.circle,n.text);n.g=g;gNodes.append(g);wireNode(g,n);
  }
  const box=el('div',{className:'graphbox'});box.append(s);
  const card=el('div',{className:'card nopad'});card.append(box);main.append(card);
  s.addEventListener('wheel',onWheel,{passive:false});
  s.addEventListener('mousedown',onBgDown);
  window.addEventListener('mousemove',onMove);
  window.addEventListener('mouseup',onUp);
}
function wireNode(g,n){
  g.addEventListener('mousedown',e=>{e.stopPropagation();dragNode=n;dragStart=evtVB(e);moved=false;});
  g.addEventListener('mouseenter',()=>setHover(n.key));
  g.addEventListener('mouseleave',()=>setHover(null));
  g.addEventListener('focus',()=>setHover(n.key));
  g.addEventListener('blur',()=>setHover(null));
  g.addEventListener('click',()=>{if(!moved)go(n);});
  g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go(n);}});
}
function go(n){location.href='/a?s='+encodeURIComponent(n.key);}
function onBgDown(e){panning=true;const pt=evtVB(e);panStart={x:pt.x,y:pt.y,vx:view.x,vy:view.y};}
function onMove(e){
  if(dragNode){const g=toGraph(evtVB(e));dragNode.x=g.x;dragNode.y=g.y;dragNode.vx=0;dragNode.vy=0;
    const dp=evtVB(e);if(Math.hypot(dp.x-dragStart.x,dp.y-dragStart.y)>4)moved=true;render();reheat();}
  else if(panning){const pt=evtVB(e);view.x=panStart.vx+(pt.x-panStart.x);view.y=panStart.vy+(pt.y-panStart.y);applyView();}
}
function onUp(){dragNode=null;panning=false;}
function onWheel(e){e.preventDefault();const pt=evtVB(e);const g=toGraph(pt);
  const f=e.deltaY<0?1.12:1/1.12;view.k=Math.max(.3,Math.min(4,view.k*f));
  view.x=pt.x-g.x*view.k;view.y=pt.y-g.y*view.k;applyView();}
function setHover(key){
  const nb=new Set();
  if(key){nb.add(key);for(const l of LINKS){if(l.a.key===key)nb.add(l.b.key);if(l.b.key===key)nb.add(l.a.key);}}
  for(const n of NODES){n.g.classList.toggle('dim',!!key&&!nb.has(n.key));n.g.classList.toggle('hot',!!key&&n.key===key);n.g.classList.toggle('nbr',!!key&&n.key!==key&&nb.has(n.key));}
  for(const l of LINKS){const on=!!key&&(l.a.key===key||l.b.key===key);
    l.line.classList.toggle('edge-on',on);l.line.classList.toggle('dim',!!key&&!on);
    l.plbl.classList.toggle('show',on);}
}
function scatter(){for(const n of NODES){n.x=CX+(Math.random()-.5)*440;n.y=CY+(Math.random()-.5)*320;n.vx=0;n.vy=0;}alpha=1;settle(350);render();}
function reheat(){alpha=Math.max(alpha,0.6);if(!running){running=true;requestAnimationFrame(step);}}
function simTick(){
  for(let i=0;i<NODES.length;i++)for(let j=i+1;j<NODES.length;j++){
    const a=NODES[i],b=NODES[j];let dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy||0.01;const d=Math.sqrt(d2);
    const f=REP/d2,fx=dx/d*f,fy=dy/d*f;a.vx+=fx;a.vy+=fy;b.vx-=fx;b.vy-=fy;
  }
  for(const l of LINKS){let dx=l.b.x-l.a.x,dy=l.b.y-l.a.y;const d=Math.sqrt(dx*dx+dy*dy)||0.01;
    const f=(d-LEN)*SPRING,fx=dx/d*f,fy=dy/d*f;l.a.vx+=fx;l.a.vy+=fy;l.b.vx-=fx;l.b.vy-=fy;}
  for(const n of NODES){n.vx+=(CX-n.x)*GRAV;n.vy+=(CY-n.y)*GRAV;}
  for(const n of NODES){if(n===dragNode)continue;n.vx*=DAMP;n.vy*=DAMP;n.x+=n.vx*alpha;n.y+=n.vy*alpha;}
  alpha*=0.985;
}
// Warm the layout synchronously so the graph is already settled on first paint —
// correct even where requestAnimationFrame is throttled; rAF then adds live motion.
function settle(iters){const keep=alpha;alpha=1;for(let i=0;i<iters;i++)simTick();alpha=keep;}
function step(){simTick();render();if(alpha>0.02||dragNode)requestAnimationFrame(step);else running=false;}
function render(){
  for(const l of LINKS){
    const ax=l.a.x,ay=l.a.y,bx=l.b.x,by=l.b.y;
    let dx=bx-ax,dy=by-ay;const d=Math.hypot(dx,dy)||0.01;const ux=dx/d,uy=dy/d;
    const sx=ax+ux*(l.a.r+1),sy=ay+uy*(l.a.r+1);
    const ex=bx-ux*(l.b.r+7),ey=by-uy*(l.b.r+7);
    const mx=(sx+ex)/2,my=(sy+ey)/2;const off=Math.min(38,d*0.18);
    const cx2=mx-uy*off,cy2=my+ux*off;
    l.line.setAttribute('d','M'+sx+','+sy+' Q'+cx2+','+cy2+' '+ex+','+ey);
    l.line.setAttribute('marker-end','url(#arrow)');
    const lx=0.25*sx+0.5*cx2+0.25*ex,ly=0.25*sy+0.5*cy2+0.25*ey;
    l.plbl.setAttribute('x',lx);l.plbl.setAttribute('y',ly-2);
  }
  for(const n of NODES)n.g.setAttribute('transform','translate('+n.x+','+n.y+')');
}
load();
""" + "</script>")


LENS_PAGE = page("Lenses — wichaa", """
  .lead{color:var(--muted);margin:0 0 18px;max-width:74ch;font-size:17px}
  .lenses{display:grid;grid-template-columns:1fr 1fr;gap:18px}
  @media(max-width:820px){.lenses{grid-template-columns:1fr}}
  .lens{display:flex;flex-direction:column;background:#fff;border:1px solid var(--line);border-radius:12px;padding:20px 22px}
  .lens.gated{border-color:#e5cf9a;background:var(--gold-bg)}
  .lens h2{margin:0 0 6px;font-size:20px;color:var(--teal)}
  .lens.gated h2{color:var(--gold)}
  .lens .bl{color:var(--ink);margin:0 0 12px;line-height:1.55}
  .gate{font-size:13px;font-weight:700;color:var(--gold);background:#fff;border:1px solid #e5cf9a;border-radius:8px;padding:8px 12px;margin:0 0 12px}
  .doors{list-style:none;margin:auto 0 0;padding:0}
  .doors li{margin:0 0 8px}
  .doors a{display:block;text-decoration:none;color:inherit;border:1px solid var(--line);border-radius:9px;padding:10px 14px;background:#fff}
  .doors a:hover{border-color:var(--teal);box-shadow:0 1px 4px #0001}
  .doors .dl{font-weight:800}
  .doors .dl a,.doors .dn{}
  .doors .dn{display:block;color:var(--muted);font-size:14px;margin-top:2px}
""",
  "<header><div><h1>Choose a lens</h1><p class=sub>The same archive, read four ways</p></div>" + NAV + "</header>"
  "<main id=main><p class=muted>Loading…</p></main>"
  "<script>" + r"""
const el=(t,p={},k=[])=>{const e=document.createElement(t);Object.assign(e,p);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
async function load(){
  const d=await (await fetch('/api/lenses')).json();
  const main=document.getElementById('main');main.textContent='';
  if(!d.dbPresent){main.append(el('div',{className:'empty'},[el('p',{textContent:'No catalog database yet.'})]));return;}
  main.append(el('p',{className:'lead',textContent:'This archive serves very different visitors. Pick the way in that fits your purpose — nothing here is walled off, the lenses just reorder the same corpus around what you came for.'}));
  const grid=el('div',{className:'lenses'});
  for(const L of d.lenses){
    const card=el('div',{className:'lens'+(L.gated?' gated':'')});
    card.append(el('h2',{textContent:L.title}),el('p',{className:'bl',textContent:L.blurb}));
    if(L.gated)card.append(el('div',{className:'gate',textContent:'Restricted knowledge — preserved here for study and continuity, not as instruction. Handle with respect.'}));
    const ul=el('ul',{className:'doors'});
    for(const dr of (L.doors||[])){
      const a=el('a',{href:dr.href});
      a.append(el('span',{className:'dl',textContent:dr.label}));
      if(dr.note)a.append(el('span',{className:'dn',textContent:dr.note}));
      ul.append(el('li',{},[a]));
    }
    if(!L.doors||!L.doors.length)ul.append(el('li',{},[el('span',{className:'dn',textContent:'Nothing catalogued here yet.'})]));
    card.append(ul);grid.append(card);
  }
  main.append(grid);
}
load();
""" + "</script>")


ARTICLE_PAGE = page("Article — wichaa", """
  .crumb{color:var(--muted);font-size:14px;margin:0 0 10px}
  .arthero{position:relative;display:block;border-radius:14px;overflow:hidden;border:1px solid var(--line);margin:0 0 16px;background:#1a1712;text-decoration:none}
  .arthero img{display:block;width:100%;height:clamp(180px,30vw,320px);object-fit:cover;object-position:center 30%}
  .arthero .cap{position:absolute;left:0;right:0;bottom:0;padding:24px 16px 11px;color:#fff;background:linear-gradient(transparent,#000d);font-size:13px;font-weight:600;line-height:1.4}
  .arthero .cap b{display:block;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.05em;opacity:.85;margin-bottom:2px}
  .arthero .star{position:absolute;top:10px;right:10px;background:var(--gold);color:#3a2c05;font-weight:800;font-size:12px;border-radius:999px;padding:4px 11px;box-shadow:0 1px 4px rgba(0,0,0,.35)}
  .lede{font-size:18px;line-height:1.6;color:var(--ink);margin:0 0 14px}
  .stubnote{background:var(--gold-bg);border:1px solid #e5cf9a;color:var(--gold);border-radius:10px;padding:10px 14px;font-size:14px;font-weight:700;margin:0 0 16px}
  .prose h2{font-size:19px;margin:20px 0 6px}
  .prose h3{font-size:16px;margin:16px 0 4px}
  .prose p{margin:0 0 10px}
  .prose ul{margin:0 0 10px 22px}
  .layout{display:grid;grid-template-columns:1fr 320px;gap:18px}
  @media(max-width:820px){.layout{grid-template-columns:1fr}}
  .facts h3{margin:14px 0 6px;font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
  .facts h3:first-child{margin-top:0}
  .factnum{font-size:30px;font-weight:800;color:var(--teal)}
  .pillgrid{display:flex;flex-wrap:wrap;gap:6px}
  .pilllink{display:inline-flex;align-items:center;gap:6px;text-decoration:none;border:1px solid var(--line);background:#fff;color:var(--ink);border-radius:999px;padding:4px 8px 4px 12px;font-weight:700;font-size:14px}
  .pilllink:hover{border-color:var(--teal)}
  .pn{background:#eef2f1;color:var(--muted);border-radius:999px;padding:1px 8px;font-size:12px}
  .samples{margin:6px 0 0 18px}.samples li{margin:2px 0;color:var(--muted)}
  .cta{display:inline-block;margin-top:8px;font-weight:800;text-decoration:none;color:var(--teal);border:2px solid var(--teal);border-radius:8px;padding:8px 14px}
  .cta:hover{background:var(--teal);color:#fff}
  .seealso a{margin-right:14px;font-weight:700;text-decoration:none}
  .relhead{margin:12px 0 4px;font-weight:700;font-size:.95em;color:#0a6b6b;text-transform:lowercase}
  .derived{margin-left:4px;color:#7a8a8a;font-weight:700}
  .miniwrap{margin-top:18px}
  .minihd{margin:0 0 8px;font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
  .minimap{background:radial-gradient(120% 120% at 50% 40%,#123f3a 0%,#0a2422 55%,#061715 100%);border-radius:12px;overflow:hidden}
  svg.mini{display:block;width:100%;height:auto}
  svg.mini .edge{fill:none;stroke:#6fb9ae;stroke-opacity:.45;stroke-width:1.4;transition:stroke-opacity .12s}
  svg.mini .node:hover~*{}
  svg.mini .plbl{font-size:12px;font-weight:800;fill:#dffaf5;paint-order:stroke;stroke:#04110f;stroke-width:3px;opacity:.9;pointer-events:none}
  svg.mini .halo{pointer-events:none;opacity:.55;transition:opacity .12s}
  svg.mini .dot{stroke:rgba(255,255,255,.85);stroke-width:1.5}
  svg.mini .node{cursor:pointer}
  svg.mini .node.center{cursor:default}
  svg.mini .node:hover .halo,svg.mini .node:focus .halo{opacity:1}
  svg.mini .node:focus{outline:none}
  svg.mini .node:hover .dot,svg.mini .node:focus .dot{stroke:#fff;stroke-width:3}
  svg.mini .nlbl{font-size:13.5px;font-weight:700;fill:#f3fbf9;paint-order:stroke;stroke:#04110f;stroke-width:3px;pointer-events:none}
""",
  "<header><div><h1 id=title>Article</h1><p class=sub id=sub></p></div>" + NAV + "</header>"
  "<main id=main><p class=muted>Loading…</p></main>"
  "<script>" + r"""
const el=(t,p={},k=[])=>{const e=document.createElement(t);Object.assign(e,p);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
const SVGNS='http://www.w3.org/2000/svg';
const svg=(t,at={},k=[])=>{const e=document.createElementNS(SVGNS,t);for(const[n,v]of Object.entries(at))e.setAttribute(n,v);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
const GCOL={entity:'#3fcbb9',genre:'#e6b24d',subgenre:'#69b0ee',axis:'#c58be0'};
const GGRAD={entity:['#7ff0e0','#158a7d'],genre:['#ffd9a0','#a06a12'],subgenre:['#a9d8ff','#2c6aa8'],axis:['#e6c4f5','#7b3ea6']};
function keyType(k){const t=(k||'').split(':')[0];return GGRAD[t]?t:'entity';}
function miniShorten(t){t=(t||'').split('(')[0].trim();return t.length>24?t.slice(0,23)+'\u2026':t;}
function miniGraph(a,skey){
  const conns=a.connections||[];if(!conns.length)return null;
  const seen=new Set(),nbrs=[];
  for(const c of conns){if(seen.has(c.key))continue;seen.add(c.key);nbrs.push(c);}
  const W=680,H=Math.max(360,Math.min(560,220+nbrs.length*16)),CX=W/2,CY=H/2;
  const R=Math.min(Math.min(CX,CY)-72,120+nbrs.length*4);
  const wrap=el('div',{className:'card miniwrap'});
  wrap.append(el('h3',{className:'minihd',textContent:'Relationship map'}));
  const box=el('div',{className:'minimap'});
  const s=svg('svg',{class:'mini',viewBox:'0 0 '+W+' '+H,role:'img','aria-label':'Relationship map for '+a.label});
  const defs=svg('defs');
  for(const t of ['entity','genre','subgenre','axis']){
    const rg=svg('radialGradient',{id:'mg-'+t,cx:'35%',cy:'32%',r:'75%'});
    rg.append(svg('stop',{offset:'0%','stop-color':GGRAD[t][0]}),svg('stop',{offset:'100%','stop-color':GGRAD[t][1]}));
    const hg=svg('radialGradient',{id:'mh-'+t,cx:'50%',cy:'50%',r:'50%'});
    hg.append(svg('stop',{offset:'0%','stop-color':GCOL[t],'stop-opacity':'.55'}),svg('stop',{offset:'55%','stop-color':GCOL[t],'stop-opacity':'.18'}),svg('stop',{offset:'100%','stop-color':GCOL[t],'stop-opacity':'0'}));
    defs.append(rg,hg);
  }
  const mk=svg('marker',{id:'mArrow',viewBox:'0 0 10 10',refX:'9',refY:'5',markerWidth:'6',markerHeight:'6',orient:'auto-start-reverse'});
  mk.append(svg('path',{d:'M0,0 L10,5 L0,10 z',fill:'#8ff3e4','fill-opacity':'.9'}));
  defs.append(mk);s.append(defs);
  const gE=svg('g'),gL=svg('g'),gN=svg('g');s.append(gE,gL,gN);
  const ctype=keyType(skey),cr=22;
  const items=nbrs.map((c,i)=>{const ang=-Math.PI/2+i/nbrs.length*2*Math.PI;
    return {c,x:CX+Math.cos(ang)*R,y:CY+Math.sin(ang)*R,r:13,type:keyType(c.key)};});
  for(const it of items){
    let dx=it.x-CX,dy=it.y-CY;const d=Math.hypot(dx,dy)||0.01;const ux=dx/d,uy=dy/d;
    const sx=CX+ux*(cr+1),sy=CY+uy*(cr+1),ex=it.x-ux*(it.r+7),ey=it.y-uy*(it.r+7);
    const mx=(sx+ex)/2,my=(sy+ey)/2,off=18,cxo=mx-uy*off,cyo=my+ux*off;
    gE.append(svg('path',{class:'edge','marker-end':'url(#mArrow)',d:'M'+sx+','+sy+' Q'+cxo+','+cyo+' '+ex+','+ey}));
    const lx=0.25*sx+0.5*cxo+0.25*ex,ly=0.25*sy+0.5*cyo+0.25*ey;
    gL.append(svg('text',{class:'plbl','text-anchor':'middle',x:lx,y:ly-2},it.c.rel));
  }
  const cg=svg('g',{class:'node center',transform:'translate('+CX+','+CY+')','aria-label':a.label+' (this article)'});
  cg.append(svg('circle',{class:'halo',r:cr*2.2,fill:'url(#mh-'+ctype+')'}),svg('circle',{class:'dot',r:cr,fill:'url(#mg-'+ctype+')'}),svg('text',{class:'nlbl','text-anchor':'middle',y:cr+18},miniShorten(a.label)));
  gN.append(cg);
  for(const it of items){
    const g=svg('g',{class:'node',tabindex:'0',role:'link',transform:'translate('+it.x+','+it.y+')','aria-label':it.c.label+' \u2014 '+it.c.rel});
    g.append(svg('circle',{class:'halo',r:it.r*2.4,fill:'url(#mh-'+it.type+')'}),svg('circle',{class:'dot',r:it.r,fill:'url(#mg-'+it.type+')'}),svg('text',{class:'nlbl','text-anchor':'middle',y:it.r+16},miniShorten(it.c.label)));
    const url='/a?s='+encodeURIComponent(it.c.key);
    g.addEventListener('click',()=>{location.href=url;});
    g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();location.href=url;}});
    gN.append(g);
  }
  box.append(s);wrap.append(box);
  wrap.append(el('p',{className:'muted',style:'margin:8px 0 0'},[document.createTextNode('The full '),el('a',{href:'/graph',textContent:'relationship graph'}),document.createTextNode(' shows every subject at once.')]));
  return wrap;
}
const KEY={provinces:'province',temples:'temple',scripts:'script',languages:'language',materials:'material'};
function pills(list,key){const w=el('div',{className:'pillgrid'});
  for(const r of list)w.append(el('a',{className:'pilllink',href:'/browse?'+key+'='+encodeURIComponent(r.value)},
    [document.createTextNode(r.label+' '),el('span',{className:'pn',textContent:r.n})]));return w;}
async function load(){
  const s=new URLSearchParams(location.search).get('s')||'';
  const main=document.getElementById('main');main.textContent='';
  const res=await fetch('/api/article?s='+encodeURIComponent(s));
  if(!res.ok){main.append(el('div',{className:'empty'},[el('p',{textContent:'No such article.'}),el('p',{},[el('a',{href:'/articles',textContent:'← All articles'})])]));return;}
  const a=await res.json();const p=a.profile;
  document.title=a.label+' — wichaa';
  document.getElementById('title').textContent=(a.priority?'★ ':'')+a.label;
  document.getElementById('sub').textContent=a.noun.charAt(0).toUpperCase()+a.noun.slice(1)+(a.note?' · '+a.note:'');
  main.append(el('p',{className:'crumb'},[el('a',{href:'/articles',textContent:'Articles'}),document.createTextNode(' / '+a.label)]));
  if(a.image){
    const href=a.image.mid!=null?('/m?id='+a.image.mid):'#';
    const hero=el('a',{className:'arthero',href:href,title:'Open the source manuscript'});
    hero.append(el('img',{src:a.image.src,alt:a.image.caption||(a.label+' — representative folio'),loading:'eager'}));
    const capkids=[el('b',{textContent:a.image.kind==='page'?'Representative folio · rendered page':'Representative folio · scanned leaf'})];
    capkids.push(document.createTextNode(a.image.caption||('From the collection for '+a.label)));
    hero.append(el('div',{className:'cap'},capkids));
    if(a.image.starred)hero.append(el('span',{className:'star',textContent:'★ curated'}));
    main.append(hero);
  }
  const layout=el('div',{className:'layout'});const art=el('div'),side=el('div');
  // left: prose
  const body=el('div',{className:'card prose'});
  if(a.lede)body.append(el('p',{className:'lede',textContent:a.lede}));
  if(a.authored&&a.authored.exists){const d=el('div');d.innerHTML=a.authored.body_html;body.append(d);}
  else body.append(el('div',{className:'stubnote',textContent:'This article is a stub — the facts here are live from the collection, awaiting written analysis. Run articles.py --draft to scaffold it.'}));
  if(a.authored&&a.authored.see_also&&a.authored.see_also.length){
    const sa=el('p',{className:'seealso'});sa.append(el('strong',{textContent:'See also: '}));
    for(const k of a.authored.see_also){const parts=k.split(':');const label=(parts.length>2?parts[parts.length-1]:parts[1])||k;sa.append(el('a',{href:'/a?s='+encodeURIComponent(k),textContent:label.replace(/_/g,' ')}));}
    body.append(sa);}
  // the node's THIRD face: findings addressed to it, computed live (facet+article+findings=one node)
  if(a.findings&&a.findings.length){const fb=el('div',{style:'margin-top:18px;border-top:1px solid var(--line);padding-top:12px'});
    fb.append(el('h2',{style:'font-size:18px;margin:0 0 2px',textContent:'What the bots have noticed'}));
    fb.append(el('p',{className:'muted',style:'font-size:13px;margin:0 0 8px',textContent:'Machine-derived from the catalogue — refreshed live, each links to its finding.'}));
    const ul=el('ul',{style:'margin:0;padding-left:18px'});
    for(const f of a.findings){const li=el('li',{style:'margin:5px 0;line-height:1.6'});
      li.append(el('strong',{textContent:f.title}));li.append(document.createTextNode(' — '+f.gloss+' '));
      li.append(el('a',{href:'/findings#'+f.slug,textContent:'see the finding →'}));ul.append(li);}
    fb.append(ul);body.append(fb);}
  if(p&&p.count&&a.browseCol)body.append(el('a',{className:'cta',href:'/browse?'+a.browseCol+'='+encodeURIComponent(a.value),textContent:'Browse all '+p.count.toLocaleString()+' →'}));
  art.append(body);
  // right: live facts
  if(p){const fc=el('div',{className:'card facts'});
    fc.append(el('h3',{textContent:'In the collection'}));
    fc.append(el('div',{className:'factnum',textContent:(p.count||0).toLocaleString()}),el('div',{className:'muted',textContent:'manuscripts'}));
    if(p.priority)fc.append(el('p',{className:'muted',style:'margin:6px 0 0',textContent:p.priority.toLocaleString()+' flagged research-priority'}));
    if(p.date&&p.date.dated)fc.append(el('h3',{textContent:'Date span'}),el('p',{className:'muted',style:'margin:0',textContent:p.date.min+'–'+p.date.max+' CE ('+p.date.dated+' dated)'}));
    for(const [name,head] of [['provinces','Where'],['temples','Held at'],['scripts','Script'],['languages','Language'],['materials','Support']]){
      if(p[name]&&p[name].length){fc.append(el('h3',{textContent:head}));fc.append(pills(p[name],KEY[name]));}}
    if(p.samples&&p.samples.length){fc.append(el('h3',{textContent:'Sample titles'}));
      const ul=el('ul',{className:'samples'});for(const t of p.samples)ul.append(el('li',{textContent:t}));fc.append(ul);}
    side.append(fc);}
  // right: knowledge-graph connections (typed relations + backlinks + co-occurrence)
  if(a.connections&&a.connections.length){const cc=el('div',{className:'card facts'});
    cc.append(el('h3',{textContent:'Connections'}));
    const groups={};for(const r of a.connections){(groups[r.rel]=groups[r.rel]||[]).push(r);}
    for(const rel of Object.keys(groups)){
      cc.append(el('div',{className:'relhead'},rel));
      const w=el('div',{className:'pillgrid'});
      for(const r of groups[rel]){const kids=[document.createTextNode(r.label+' ')];
        if(r.weight)kids.push(el('span',{className:'pn',textContent:r.weight}));
        if(!r.authored)kids.push(el('span',{className:'derived',title:'derived from the catalogue',textContent:'~'}));
        w.append(el('a',{className:'pilllink',href:'/a?s='+encodeURIComponent(r.key)},kids));}
      cc.append(w);}
    side.append(cc);}
  layout.append(art,side);main.append(layout);
  const mg=miniGraph(a,s);if(mg)main.append(mg);
}
load();
""" + "</script>")


ARTICLES_PAGE = page("Profiles — wichaa", """
  .lead{color:var(--muted);margin:0 0 14px}
  .agrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(248px,1fr));gap:16px;margin:0 0 6px}
  .acard{display:flex;flex-direction:column;border:1px solid var(--line);border-radius:14px;overflow:hidden;background:#fff;text-decoration:none;color:inherit;transition:border-color .15s,transform .15s,box-shadow .15s}
  .acard:hover{border-color:var(--teal);transform:translateY(-2px);box-shadow:0 8px 22px rgba(0,0,0,.09)}
  .acard:focus-visible{outline:3px solid var(--teal);outline-offset:2px}
  .acard .thumb{position:relative;aspect-ratio:4/3;background:#1a1712;overflow:hidden;display:block}
  .acard .thumb img{width:100%;height:100%;object-fit:cover;object-position:center 30%;display:block;transition:transform .2s ease}
  .acard:hover .thumb img{transform:scale(1.04)}
  .acard .mono{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:radial-gradient(120% 120% at 50% 28%,#1d4b46,#0b2321);color:#bfe8e0;font-size:52px;font-weight:800;letter-spacing:.02em}
  .acard .star{position:absolute;top:8px;left:8px;background:var(--gold);color:#3a2c05;font-weight:800;font-size:11px;border-radius:999px;padding:3px 9px;box-shadow:0 1px 3px rgba(0,0,0,.3)}
  .acard .body{padding:12px 14px 14px;display:flex;flex-direction:column;gap:7px;flex:1}
  .acard .top{display:flex;align-items:baseline;gap:8px}
  .acard .name{font-weight:800;font-size:15.5px;color:var(--teal);line-height:1.25}
  .acard .cnt{margin-left:auto;font-weight:800;color:var(--muted);white-space:nowrap;font-size:14px}
  .acard .meta{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:auto}
  .acard .anote{color:var(--muted);font-size:13px;margin:0;line-height:1.4}
  .badge{font-size:12px;font-weight:800;border-radius:999px;padding:2px 10px}
  .badge.ok{background:#e3f1e9;color:var(--ok);border:1px solid #b6dcc6}
  .badge.draft{background:#eaf1f7;color:var(--focus);border:1px solid #b9d1e8}
  .badge.stub{background:var(--gold-bg);color:var(--gold);border:1px solid #e5cf9a}
  .badge.prio{background:var(--prio-bg);color:var(--prio);border:1px solid #e0a3a3}
  .grouphd{margin:20px 0 10px;font-size:14px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
""",
  "<header><div><h1>Profiles</h1><p class=sub>Auto-computed subject profiles — live catalogue facts, counts, and cross-links drawn straight from the collection. Longer authored essays are added over time.</p></div>" + NAV + "</header>"
  "<main id=main><p class=muted>Loading…</p></main>"
  "<script>" + r"""
const el=(t,p={},k=[])=>{const e=document.createElement(t);Object.assign(e,p);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
function monogram(label){const m=(label||'?').replace(/^[^\p{L}\p{N}]+/u,'');return (m[0]||'?').toUpperCase();}
function card(a){
  const art='/a?s='+encodeURIComponent(a.key);
  const c=el('a',{className:'acard',href:art,'aria-label':a.label+' — '+a.count.toLocaleString()+' manuscripts'});
  const thumb=el('div',{className:'thumb'});
  if(a.image){
    const img=el('img',{src:a.image.src,alt:'',loading:'lazy'});
    if(a.image.caption)img.title=a.image.caption;
    thumb.append(img);
    if(a.image.starred)thumb.append(el('span',{className:'star',textContent:'★ curated'}));
  }else{
    thumb.append(el('div',{className:'mono',textContent:monogram(a.label)}));
  }
  c.append(thumb);
  const body=el('div',{className:'body'});
  const top=el('div',{className:'top'});
  top.append(el('span',{className:'name',textContent:(a.priority?'★ ':'')+a.label}));
  top.append(el('span',{className:'cnt',textContent:a.count.toLocaleString()}));
  body.append(top);
  if(a.note)body.append(el('p',{className:'anote',textContent:a.note}));
  const meta=el('div',{className:'meta'});
  const st=a.hasArticle?(a.status==='published'?['ok','Article']:['draft','Draft']):['stub','Stub'];
  meta.append(el('span',{className:'badge '+st[0],textContent:st[1]}));
  if(a.priority)meta.append(el('span',{className:'badge prio',textContent:'priority'}));
  const sh=el('button',{className:'cardshare',title:'Share this profile','aria-label':'Share',textContent:'⤴',style:'margin-left:auto'});
  sh.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();window.__share(location.origin+art,a.label);});
  meta.append(sh);
  body.append(meta);
  c.append(body);
  return c;}
async function load(){const d=await (await fetch('/api/articles')).json();const main=document.getElementById('main');main.textContent='';
  if(!d.dbPresent){main.append(el('div',{className:'empty'},[el('p',{textContent:'No catalog database yet.'})]));return;}
  const intro=el('div',{className:'card'});
  intro.append(el('p',{className:'lead',style:'margin:0'},[document.createTextNode('Every genre — plus the esoteric subjects and sub-genres we\u2019ve begun documenting — has an article that reads its own slice of the collection: counts, places, scripts and dates are recomputed live, so they never go stale as the crawl grows. Each card shows a representative folio pulled straight from the collection — a diagram or described page where we have one, otherwise a scanned leaf; a '),el('span',{className:'badge stub',textContent:'Stub'}),document.createTextNode(' has live facts but awaits written analysis, an '),el('span',{className:'badge ok',textContent:'Article'}),document.createTextNode(' has authored prose. Listed research-priority first.')]));
  main.append(intro);
  const prio=d.articles.filter(a=>a.priority),rest=d.articles.filter(a=>!a.priority);
  if(prio.length){main.append(el('div',{className:'grouphd',textContent:'Research priority (wichaa)'}));const g=el('div',{className:'agrid'});for(const a of prio)g.append(card(a));main.append(g);}
  if(rest.length){main.append(el('div',{className:'grouphd',textContent:'The rest of the collection'}));const g=el('div',{className:'agrid'});for(const a of rest)g.append(card(a));main.append(g);}
}
load();
""" + "</script>")


VOCAB_PAGE = page("Vocabulary — wichaa", """
  .lead{color:var(--muted);margin:0 0 4px}
  .vtools{position:sticky;top:0;z-index:5;background:var(--bg);padding:12px 0;margin:0 0 6px;border-bottom:1px solid var(--line)}
  .vtools .row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
  .vtools input[type=search]{flex:1;min-width:240px}
  .vcount{font-weight:700;color:var(--muted);white-space:nowrap}
  .grouphd{margin:22px 0 10px;font-size:14px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);border-bottom:2px solid var(--line);padding-bottom:4px}
  .vgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
  .vcard{display:flex;gap:14px;border:1px solid var(--line);border-radius:12px;background:#fff;padding:14px 16px}
  .vcard.hide{display:none}
  .vthumb{flex:0 0 84px}
  .vthumb img{width:84px;height:84px;object-fit:cover;border-radius:8px;border:1px solid var(--line);background:#f0f4f3}
  .vthumb .cap{font-size:11px;color:var(--muted);margin-top:3px;line-height:1.3}
  .vbody{flex:1;min-width:0}
  .vhead{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
  .vthai{font-size:30px;font-weight:700;color:var(--ink);line-height:1.1}
  .vtl{font-style:italic;color:var(--muted);font-size:15px}
  .vgloss{margin:4px 0 6px;font-size:16px}
  .vstats{font-size:13px;color:var(--muted);margin:0 0 6px}
  .vstats b{color:var(--ink)}
  .vlinks a{display:inline-block;margin:0 12px 4px 0;font-weight:700;text-decoration:none;color:var(--teal)}
  .vlinks a:hover{text-decoration:underline}
  .vex{margin:6px 0 0;font-size:13px;line-height:1.6}
  .vex .exl{color:var(--muted);font-weight:700;margin-right:4px}
  .vex a{color:var(--focus);text-decoration:none}
  .vex a:hover{text-decoration:underline}
  .vex .h{color:var(--muted)}
  .want{font-size:12px;font-weight:800;border-radius:999px;padding:2px 9px;background:var(--gold-bg);color:var(--gold);border:1px solid #e5cf9a}
""",
  "<header><div><h1>Vocabulary</h1><p class=sub>The working words of the wichaa — mined from the corpus, glossed and linked</p></div>" + NAV + "</header>"
  "<main id=main><p class=muted>Loading…</p></main>"
  "<script>" + r"""
const el=(t,p={},k=[])=>{const e=document.createElement(t);Object.assign(e,p);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
let TERMS=[];
function vcard(t){
  const c=el('div',{className:'vcard'});
  c.dataset.hay=(t.thai+' '+t.translit+' '+t.gloss+' '+(t.variants||[]).join(' ')).toLowerCase();
  if(t.thumb){
    const src='/pimg?mid='+t.thumb.id+'&n='+t.thumb.page;
    const im=el('img',{src:src,alt:'Diagram page from '+t.thumb.label,loading:'lazy'});
    const link=el('a',{href:'/m?id='+t.thumb.id,title:t.thumb.desc||''},[im]);
    const th=el('div',{className:'vthumb'},[link]);
    if(t.thumb.desc)th.append(el('div',{className:'cap',textContent:t.thumb.desc.slice(0,70)+(t.thumb.desc.length>70?'…':'')}));
    c.append(th);
  }
  const b=el('div',{className:'vbody'});
  const head=el('div',{className:'vhead'},[el('span',{className:'vthai',textContent:t.thai}),el('span',{className:'vtl',textContent:t.translit})]);
  if(t.n_mss===0)head.append(el('span',{className:'want',textContent:'want-list'}));
  b.append(head);
  b.append(el('div',{className:'vgloss',textContent:t.gloss}));
  if((t.variants||[]).length>1)b.append(el('div',{className:'vstats'},[document.createTextNode('also written '),...t.variants.map(v=>el('span',{className:'pill',textContent:v}))]));
  const stats=el('div',{className:'vstats'});
  if(t.n_mss){stats.append(el('b',{textContent:t.n_mss.toLocaleString()}),document.createTextNode(' manuscript'+(t.n_mss===1?'':'s')+' · '),el('b',{textContent:t.total_hits.toLocaleString()}),document.createTextNode(' occurrences in the corpus'));}
  else stats.append(document.createTextNode('Not yet attested in the digested corpus — a crawl target.'));
  b.append(stats);
  const links=el('div',{className:'vlinks'});
  if(t.entity)links.append(el('a',{href:'/a?s=entity:'+t.entity,textContent:'Read article →'}));
  links.append(el('a',{href:'/browse?q='+encodeURIComponent(t.thai),textContent:'Search the corpus →'}));
  b.append(links);
  if((t.examples||[]).length){
    const ex=el('div',{className:'vex'});
    ex.append(el('span',{className:'exl',textContent:'Strongest in:'}));
    t.examples.forEach((e,i)=>{
      if(i)ex.append(document.createTextNode(' · '));
      ex.append(el('a',{href:'/m?id='+e.id,textContent:e.label}));
      if(e.hits)ex.append(el('span',{className:'h',textContent:' ×'+e.hits}));
    });
    b.append(ex);
  }
  c.append(b);
  return c;
}
function applyFilter(){
  const q=document.getElementById('q').value.trim().toLowerCase();
  let shown=0;
  document.querySelectorAll('.vcard').forEach(c=>{
    const ok=!q||c.dataset.hay.includes(q);
    c.classList.toggle('hide',!ok);
    if(ok)shown++;
  });
  document.querySelectorAll('.grouphd').forEach(h=>{
    const grid=h.nextElementSibling;
    const any=grid&&grid.querySelector('.vcard:not(.hide)');
    h.style.display=any?'':'none';
    if(grid)grid.style.display=any?'':'none';
  });
  document.getElementById('vcount').textContent='Showing '+shown+' of '+TERMS.length+' terms';
}
async function load(){
  const d=await (await fetch('/api/vocab')).json();
  const main=document.getElementById('main');main.textContent='';
  if(!d.dbPresent){main.append(el('div',{className:'empty'},[el('p',{textContent:'No catalog database yet.'})]));return;}
  TERMS=d.groups.flatMap(g=>g.terms);
  const intro=el('div',{className:'card'});
  intro.append(el('p',{className:'lead'},[document.createTextNode('These are the load-bearing words of the tradition — the terms the OCR corpus actually leans on, mined from the digested texts and written back as folksonomy tags. Each is glossed, counted against the collection, and linked to its entity article (where one exists) and to a live full-text search. Type in Thai, in transliteration, or in English to filter.')]));
  main.append(intro);
  const tools=el('div',{className:'vtools'});
  const inp=el('input',{type:'search',id:'q',placeholder:'Filter — e.g. yantra, ยันต์, invulnerability, takrut…','aria-label':'Filter vocabulary'});
  inp.addEventListener('input',applyFilter);
  tools.append(el('div',{className:'row'},[inp,el('span',{className:'vcount',id:'vcount'})]));
  main.append(tools);
  for(const g of d.groups){
    main.append(el('div',{className:'grouphd',textContent:g.name}));
    const grid=el('div',{className:'vgrid'});
    for(const t of g.terms)grid.append(vcard(t));
    main.append(grid);
  }
  applyFilter();
}
load();
""" + "</script>")


GALLERY_PAGE = page("Plates — wichaa", """
  .lead{color:var(--muted);margin:0 0 4px}
  .gtools{position:sticky;top:0;z-index:5;background:var(--bg);padding:12px 0;margin:0 0 12px;border-bottom:1px solid var(--line)}
  .gtools .row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
  .gtools input[type=search]{flex:1;min-width:220px}
  .gtools select{width:auto;min-width:200px}
  .gcount{font-weight:700;color:var(--muted);white-space:nowrap;margin-left:auto}
  .facetbtns{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 4px}
  .fbtn{font-size:15px;font-weight:700;border:2px solid var(--line);background:#fff;color:var(--muted);border-radius:999px;padding:7px 14px;min-height:40px;cursor:pointer}
  .fbtn:hover{border-color:var(--teal);color:var(--teal);background:#fff}
  .fbtn.on{background:var(--teal);border-color:var(--teal);color:#fff}
  .fbtn .n{opacity:.8;font-weight:700;margin-left:4px}
  .ggrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}
  .gcard{display:flex;flex-direction:column;border:1px solid var(--line);border-radius:12px;background:#fff;overflow:hidden}
  .gcard.hide{display:none}
  .gcard.gfx{border-color:#e5cf9a}
  .gthumb{display:block;position:relative;background:#eef2f1;line-height:0}
  .gthumb img{width:100%;height:230px;object-fit:contain;background:#f7faf9}
  .gbadges{position:absolute;top:8px;left:8px;display:flex;gap:6px;flex-wrap:wrap}
  .gb{font-size:12px;font-weight:800;border-radius:999px;padding:3px 9px;border:1px solid #0002;box-shadow:0 1px 2px #0002}
  .gb.gfx{background:var(--gold-bg);color:var(--gold);border-color:#e5cf9a}
  .gb.desc{background:var(--teal);color:#fff;border-color:var(--teal)}
  .gb.ocr{background:#e7f3ec;color:var(--ok);border-color:#a9d6bd}
  .gmeta{padding:11px 13px 13px;display:flex;flex-direction:column;gap:5px;flex:1}
  .gtitle{font-weight:700;color:var(--teal);font-size:15px;line-height:1.3;text-decoration:none}
  .gtitle:hover{text-decoration:underline}
  .gfolio{font-size:12px;color:var(--muted);font-weight:700}
  .gcap{font-size:13px;color:#334;line-height:1.45}
  .gcap.thai{font-size:15px}
  .modeswitch{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 6px}
  .mbtn{font-size:16px;font-weight:800;border:2px solid var(--line);background:#fff;color:var(--muted);border-radius:10px;padding:10px 18px;min-height:46px;cursor:pointer}
  .mbtn:hover{border-color:var(--teal);color:var(--teal)}
  .mbtn.on{background:var(--teal);border-color:var(--teal);color:#fff}
  .mbtn .n{opacity:.8;margin-left:6px;font-weight:700}
  .gb.tx{background:#efe7fb;color:#5a3a9a;border-color:#cdbdf0}
  .loadmore{display:block;margin:18px auto 4px;min-width:220px}
  .scanhint{font-size:13px;color:var(--muted);margin:2px 0 0}
""",
  "<header><div><h1>Plates</h1><p class=sub>The rendered manuscript pages — graphics, described, and legible at a glance</p></div>" + NAV + "</header>"
  "<main id=main><p class=muted>Loading…</p></main>"
  "<script>" + r"""
const el=(t,p={},k=[])=>{const e=document.createElement(t);Object.assign(e,p);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
const thaiRe=/[\u0E00-\u0E7F]/;
let MODE='plates';
let PLATES=[],FACET='all',MS='',RENDER=null;
// scans mode state
let SCAN_INDEX=null,SCAN_MID='',SCAN_ONLYT=false,SCAN_OFFSET=0,SCAN_TOTAL=0;
const LIMIT=120;

/* ---------- rendered plates ---------- */
function matches(e){
  if(FACET==='graphics'&&!e.graphics)return false;
  if(FACET==='described'&&!e.described)return false;
  if(FACET==='goodOcr'&&!e.goodOcr)return false;
  if(MS&&String(e.id)!==MS)return false;
  const q=(document.getElementById('q').value||'').trim().toLowerCase();
  if(q){const hay=(e.title+' '+e.caption+' '+e.kind).toLowerCase();if(!hay.includes(q))return false;}
  return true;
}
function applyPlates(){
  let shown=0;
  document.querySelectorAll('.gcard').forEach(c=>{
    const ok=matches(PLATES[+c.dataset.i]);
    c.classList.toggle('hide',!ok);if(ok)shown++;
  });
  document.getElementById('gcount').textContent='Showing '+shown+' of '+PLATES.length+' plates';
}
function gcard(e,i){
  const c=el('div',{className:'gcard'+(e.graphics?' gfx':'')});c.dataset.i=i;
  const im=el('img',{src:'/pimg?mid='+e.id+'&n='+e.page,alt:(e.caption||e.title)+' — '+e.title+', page '+e.page,loading:'lazy'});
  const badges=el('div',{className:'gbadges'});
  if(e.graphics)badges.append(el('span',{className:'gb gfx',textContent:'◆ graphics'}));
  if(e.described)badges.append(el('span',{className:'gb desc',textContent:'✦ described'}));
  if(e.goodOcr)badges.append(el('span',{className:'gb ocr',textContent:'OCR'}));
  c.append(el('a',{className:'gthumb',href:'/m?id='+e.id,title:e.caption||e.title},[im,badges]));
  const meta=el('div',{className:'gmeta'});
  meta.append(el('a',{className:'gtitle',href:'/m?id='+e.id,textContent:e.title}));
  meta.append(el('div',{className:'gfolio',textContent:'page '+e.page+(e.kind?' · '+e.kind:'')+(e.goodOcr?' · '+e.thaiChars+' Thai chars':'')}));
  if(e.caption)meta.append(el('div',{className:'gcap'+(thaiRe.test(e.caption)&&!e.described?' thai':''),textContent:e.caption+(e.caption.length>=160?'…':'')}));
  c.append(meta);return c;
}
function facetBtn(key,label,n){
  const b=el('button',{className:'fbtn'+(FACET===key?' on':''),type:'button'});
  b.append(document.createTextNode(label));
  if(n!=null)b.append(el('span',{className:'n',textContent:n.toLocaleString()}));
  b.addEventListener('click',()=>{FACET=key;document.querySelectorAll('.fbtn').forEach(x=>x.classList.remove('on'));b.classList.add('on');applyPlates();});
  return b;
}
function renderPlates(body,d){
  const c=d.counts;
  const tools=el('div',{className:'gtools'});
  const fb=el('div',{className:'facetbtns'});
  fb.append(facetBtn('all','All plates',c.all),facetBtn('graphics','◆ Graphics',c.graphics),
            facetBtn('described','✦ Described',c.described),facetBtn('goodOcr','Good OCR',c.goodOcr));
  tools.append(fb);
  const inp=el('input',{type:'search',id:'q',placeholder:'Search captions, titles…','aria-label':'Search plates'});
  inp.addEventListener('input',applyPlates);
  const msids=[...new Set(PLATES.map(p=>p.id))].map(id=>({id,title:(PLATES.find(p=>p.id===id)||{}).title}));
  msids.sort((a,b)=>a.title.localeCompare(b.title));
  const sel=el('select',{'aria-label':'Filter by manuscript'});
  sel.append(el('option',{value:'',textContent:'All manuscripts'}));
  for(const m of msids)sel.append(el('option',{value:String(m.id),textContent:m.title}));
  sel.addEventListener('change',()=>{MS=sel.value;applyPlates();});
  tools.append(el('div',{className:'row'},[inp,sel,el('span',{className:'gcount',id:'gcount'})]));
  body.append(tools);
  const grid=el('div',{className:'ggrid'});
  PLATES.forEach((e,i)=>grid.append(gcard(e,i)));
  body.append(grid);
  applyPlates();
}

/* ---------- raw scans (lazy) ---------- */
function scard(s){
  const c=el('div',{className:'gcard'+(s.transcribed?' gfx':'')});
  const im=el('img',{src:'/img?sha='+s.sha,alt:s.title+' — scan '+s.seq,loading:'lazy'});
  const badges=el('div',{className:'gbadges'});
  if(s.transcribed){
    const eng=s.engine==='claude-vlm'?'✎ VLM read':(s.engine==='tesseract'?'OCR':'✎ read');
    badges.append(el('span',{className:'gb tx',textContent:eng+(s.conf!=null?' '+Math.round(s.conf*100)+'%':'')}));
    if(s.script)badges.append(el('span',{className:'gb desc',textContent:s.script}));
  }
  c.append(el('a',{className:'gthumb',href:'/m?id='+s.id,title:s.caption||s.title},[im,badges]));
  const meta=el('div',{className:'gmeta'});
  meta.append(el('a',{className:'gtitle',href:'/m?id='+s.id,textContent:s.title}));
  meta.append(el('div',{className:'gfolio',textContent:'scan '+s.seq+(s.transcribed?' · transcribed':'')}));
  if(s.caption)meta.append(el('div',{className:'gcap',textContent:s.caption+(s.caption.length>=200?'…':'')}));
  c.append(meta);return c;
}
async function loadScanPage(grid,more){
  more.disabled=true;more.textContent='Loading…';
  const q=new URLSearchParams({source:'scans',offset:SCAN_OFFSET,limit:LIMIT});
  if(SCAN_MID)q.set('mid',SCAN_MID);
  if(SCAN_ONLYT)q.set('only','transcribed');
  const d=await (await fetch('/api/gallery?'+q)).json();
  SCAN_TOTAL=d.total;
  for(const s of d.scans)grid.append(scard(s));
  SCAN_OFFSET+=d.scans.length;
  document.getElementById('gcount').textContent='Showing '+SCAN_OFFSET+' of '+SCAN_TOTAL.toLocaleString()+' scans';
  if(SCAN_OFFSET>=SCAN_TOTAL){more.style.display='none';}
  else{more.disabled=false;more.textContent='Load more scans ('+(SCAN_TOTAL-SCAN_OFFSET).toLocaleString()+' left)';}
}
function renderScans(body){
  SCAN_OFFSET=0;
  const tools=el('div',{className:'gtools'});
  const row=el('div',{className:'row'});
  const sel=el('select',{'aria-label':'Choose a manuscript'});
  sel.append(el('option',{value:'',textContent:'All manuscripts ('+SCAN_INDEX.total.toLocaleString()+' scans)'}));
  for(const m of SCAN_INDEX.manuscripts){
    const t=m.transcribed?'  ✎'+m.transcribed:'';
    sel.append(el('option',{value:String(m.id),textContent:m.title+'  ·  '+m.n+' scans'+t}));
  }
  sel.value=SCAN_MID;
  sel.addEventListener('change',()=>{SCAN_MID=sel.value;renderScans(body);});
  const tog=el('button',{className:'fbtn'+(SCAN_ONLYT?' on':''),type:'button'});
  tog.append(document.createTextNode('✎ Transcribed only'),el('span',{className:'n',textContent:SCAN_INDEX.transcribed.toLocaleString()}));
  tog.addEventListener('click',()=>{SCAN_ONLYT=!SCAN_ONLYT;renderScans(body);});
  row.append(sel,tog,el('span',{className:'gcount',id:'gcount'}));
  tools.append(row);
  tools.append(el('p',{className:'scanhint',textContent:'The raw monastic handwriting, straight from the crawler\u2019s image library. A purple badge marks a scan I\u2019ve given a first-pass reading; open the manuscript to see the full text and provenance.'}));
  body.append(tools);
  const grid=el('div',{className:'ggrid'});body.append(grid);
  const more=el('button',{className:'secondary loadmore',type:'button'});body.append(more);
  more.addEventListener('click',()=>loadScanPage(grid,more));
  loadScanPage(grid,more);
}

/* ---------- shell / mode switch ---------- */
function modeBtn(key,label,n){
  const b=el('button',{className:'mbtn'+(MODE===key?' on':''),type:'button'});
  b.append(document.createTextNode(label));
  if(n!=null)b.append(el('span',{className:'n',textContent:n.toLocaleString()}));
  b.addEventListener('click',async()=>{if(MODE===key)return;MODE=key;
    document.querySelectorAll('.mbtn').forEach(x=>x.classList.remove('on'));b.classList.add('on');
    await draw();});
  return b;
}
async function draw(){
  const body=document.getElementById('modebody');body.textContent='';
  if(MODE==='plates'){renderPlates(body,RENDER);}
  else{if(!SCAN_INDEX){body.append(el('p',{className:'muted',textContent:'Loading scans…'}));
      SCAN_INDEX=await (await fetch('/api/gallery?source=scan-index')).json();body.textContent='';}
    renderScans(body);}
}
async function load(){
  const d=await (await fetch('/api/gallery')).json();
  const main=document.getElementById('main');main.textContent='';
  if(!d.dbPresent){main.append(el('div',{className:'empty'},[el('p',{textContent:'No catalog database yet.'})]));return;}
  PLATES=d.plates;RENDER=d;const c=d.counts;
  const intro=el('div',{className:'card'});
  intro.append(el('p',{className:'lead'},[document.createTextNode(
    'Two ways to look at the collection. Rendered plates are the '+c.all.toLocaleString()+' digested textbook pages held as images — all '+c.graphics.toLocaleString()+' diagram pages among them, each hand-described, plus the '+c.goodOcr.toLocaleString()+' with strong OCR. Raw scans are the '+(d.rawScans||0).toLocaleString()+' manuscript folios themselves — the monastic handwriting — browsable by manuscript, with a badge on every scan I\u2019ve begun to read.')]));
  main.append(intro);
  const sw=el('div',{className:'modeswitch'});
  sw.append(modeBtn('plates','Rendered plates',c.all),modeBtn('scans','Raw scans',d.rawScans||0));
  main.append(sw);
  main.append(el('div',{id:'modebody'}));
  draw();
}
load();
""" + "</script>")


TRIAGE_PAGE = page("Triage — wichaa", """
  .lead{color:var(--muted);margin:0 0 12px;max-width:74ch;line-height:1.55}
  .ttools{position:sticky;top:0;z-index:5;background:var(--bg);padding:10px 0;margin:0 0 14px;border-bottom:1px solid var(--line);display:flex;gap:10px;align-items:center;flex-wrap:wrap}
  .mbtn{font-size:16px;font-weight:800;border:2px solid var(--line);background:#fff;color:var(--muted);border-radius:10px;padding:10px 16px;min-height:46px;cursor:pointer}
  .mbtn:hover{border-color:var(--teal);color:var(--teal)}
  .mbtn.on{background:var(--teal);border-color:var(--teal);color:#fff}
  .mbtn .n{opacity:.85;font-weight:700;margin-left:5px}
  .featcount{margin-left:auto;font-weight:800;color:var(--gold);white-space:nowrap}
  .tgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:16px}
  .tcard{position:relative;margin:0;border:1px solid var(--line);border-radius:12px;background:#fff;overflow:hidden;display:flex;flex-direction:column}
  .tcard.starred{border-color:var(--gold);box-shadow:0 0 0 2px var(--gold-bg)}
  .tthumb{display:block;position:relative;background:#1a1712;line-height:0}
  .tthumb img{width:100%;height:210px;object-fit:cover;object-position:center 28%;display:block}
  .tbadges{position:absolute;left:8px;bottom:8px;display:flex;gap:6px;flex-wrap:wrap}
  .tb{font-size:12px;font-weight:800;border-radius:999px;padding:3px 9px;border:1px solid #0002;box-shadow:0 1px 2px #0003}
  .tb.gfx{background:var(--gold-bg);color:var(--gold);border-color:#e5cf9a}
  .tb.desc{background:var(--teal);color:#fff;border-color:var(--teal)}
  .tb.scan{background:#eef2f1;color:var(--muted)}
  .star{position:absolute;top:8px;right:8px;width:44px;height:44px;border-radius:50%;border:none;background:#000000073;color:#ffd94a;font-size:24px;line-height:1;cursor:pointer;display:flex;align-items:center;justify-content:center}
  .star:hover{background:#000000b3}
  .star[aria-pressed=true]{background:var(--gold);color:#fff}
  .tcap{padding:10px 12px 12px;display:flex;flex-direction:column;gap:4px}
  .ttitle{font-weight:700;color:var(--teal);font-size:14px;line-height:1.3;text-decoration:none}
  .ttitle:hover{text-decoration:underline}
  .tsub{font-size:12.5px;color:#445;line-height:1.4}
  .loadmore{display:block;margin:20px auto 6px;min-width:240px;font-size:16px;font-weight:800;border:2px solid var(--teal);background:var(--teal);color:#fff;border-radius:10px;padding:12px 18px;min-height:48px;cursor:pointer}
  .loadmore:hover{filter:brightness(1.06)}
  .scanhint{text-align:center;margin-top:16px}
""",
  "<header><div><h1>Triage</h1><p class=sub>Star the striking folios — this is how we decide what to feature</p></div>" + NAV + "</header>"
  "<p class=lead>Two piles of images. <b>Diagrams &amp; described</b> are the pages the pipeline already flags as visually notable — the illustrated diagrams and anything the vision model has described. <b>Raw folios</b> is the first leaf of every scanned manuscript (best odds of a decorated frontispiece), which the pipeline knows nothing visual about. Tap the star on anything striking; your picks are saved to <code>data/featured.json</code> and become the featured images across the wiki.</p>"
  "<div class=ttools id=tools></div>"
  "<main id=grid><p class=muted>Loading…</p></main>"
  "<script>" + r"""
const el=(t,p={},k=[])=>{const e=document.createElement(t);Object.assign(e,p);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
let DATA=null, MODE='signal', SCANITEMS=[], FEAT=0;

function updateCounts(){
  const fc=document.getElementById('featcount');
  if(fc) fc.textContent=FEAT+(FEAT===1?' folio starred':' folios starred');
  const sn=document.querySelector('.mbtn[data-mode=starred] .n');
  if(sn) sn.textContent=FEAT;
}
function toggleStar(it, card){
  const now=!it.starred;
  fetch('/api/feature',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({key:it.key, starred:now})})
    .then(r=>r.json()).then(d=>{
      if(d.error) return;
      it.starred=now;
      card.classList.toggle('starred', now);
      const b=card.querySelector('.star');
      b.textContent=now?'\u2605':'\u2606';
      b.setAttribute('aria-pressed', String(now));
      b.title=now?'Starred \u2014 click to unstar':'Star as striking';
      if(now){ if(!DATA.starred.some(x=>x.key===it.key)) DATA.starred.push(it); }
      else { DATA.starred=DATA.starred.filter(x=>x.key!==it.key); }
      if(typeof d.featuredCount==='number') FEAT=d.featuredCount;
      updateCounts();
    });
}
function cardFor(it){
  const card=el('figure',{className:'tcard'+(it.starred?' starred':'')});
  const thumb=el('a',{className:'tthumb',href:it.detail,title:it.title});
  thumb.append(el('img',{src:it.src,alt:it.title,loading:'lazy'}));
  const badges=el('div',{className:'tbadges'});
  if(it.diagram) badges.append(el('span',{className:'tb gfx',textContent:'\u25C6 diagram'}));
  if(it.described) badges.append(el('span',{className:'tb desc',textContent:'described'}));
  if(it.kind==='scan') badges.append(el('span',{className:'tb scan',textContent:(it.seq!=null?'folio '+it.seq:'folio')}));
  if(badges.childNodes.length) thumb.append(badges);
  card.append(thumb);
  const star=el('button',{className:'star',type:'button',
    title:it.starred?'Starred \u2014 click to unstar':'Star as striking'});
  star.textContent=it.starred?'\u2605':'\u2606';
  star.setAttribute('aria-pressed', String(!!it.starred));
  star.setAttribute('aria-label','Star '+it.title);
  star.addEventListener('click',(e)=>{e.preventDefault();toggleStar(it,card);});
  card.append(star);
  const cap=el('figcaption',{className:'tcap'});
  cap.append(el('a',{className:'ttitle',href:it.detail,textContent:it.title}));
  if(it.caption) cap.append(el('div',{className:'tsub',textContent:it.caption}));
  card.append(cap);
  return card;
}
function loadMore(){
  fetch('/api/triage?scanOffset='+SCANITEMS.length+'&scanLimit=60')
    .then(r=>r.json()).then(d=>{
      SCANITEMS=SCANITEMS.concat(d.scans.items||[]);
      DATA.scans.total=d.scans.total;
      render();
    });
}
function render(){
  const main=document.getElementById('grid'); main.textContent='';
  let list;
  if(MODE==='signal') list=DATA.signal;
  else if(MODE==='starred') list=DATA.starred;
  else list=SCANITEMS;
  if(!list.length){
    main.append(el('p',{className:'muted',textContent:
      MODE==='starred'?'No folios starred yet. Open Diagrams & described or Raw folios and tap the star on the striking ones.':'Nothing here yet.'}));
    return;
  }
  const grid=el('div',{className:'tgrid'});
  list.forEach(it=>grid.append(cardFor(it)));
  main.append(grid);
  if(MODE==='scans'){
    const shown=SCANITEMS.length, total=DATA.scans.total;
    if(shown<total) main.append(el('button',{className:'loadmore',type:'button',
      textContent:'Load more folios ('+shown+' of '+total+')',onclick:loadMore}));
    else main.append(el('p',{className:'scanhint muted',
      textContent:'All '+total+' manuscripts shown (first folio of each).'}));
  }
}
function mbtn(mode,label,n){
  const b=el('button',{className:'mbtn'+(MODE===mode?' on':''),type:'button'});
  b.dataset.mode=mode;
  b.append(document.createTextNode(label), el('span',{className:'n',textContent:n}));
  b.addEventListener('click',()=>{
    MODE=mode;
    document.querySelectorAll('.mbtn').forEach(x=>x.classList.toggle('on',x.dataset.mode===mode));
    render(); window.scrollTo(0,0);
  });
  return b;
}
function buildTools(){
  const sw=document.getElementById('tools'); sw.textContent='';
  sw.append(
    mbtn('signal','Diagrams & described',DATA.signal.length),
    mbtn('scans','Raw folios',DATA.scans.total),
    mbtn('starred','\u2605 Starred',FEAT),
    el('span',{className:'featcount',id:'featcount'}));
  updateCounts();
}
function load(){
  fetch('/api/triage?scanOffset=0&scanLimit=60').then(r=>r.json()).then(d=>{
    if(!d.dbPresent){document.getElementById('grid').innerHTML='<p class=muted>The catalogue isn\u2019t built yet.</p>';return;}
    DATA=d; SCANITEMS=(d.scans.items||[]).slice(); FEAT=d.featuredCount||0;
    buildTools(); render();
  }).catch(e=>{document.getElementById('grid').innerHTML='<p class=muted>Could not load triage.</p>';});
}
load();
""" + "</script>")


WATS_PAGE = page("Wats of Chiang Mai — wichaa", """
  .hero{position:relative;height:min(58vh,520px);min-height:300px;border:1px solid var(--line);border-radius:14px;overflow:hidden;margin-bottom:16px;background:#e9e7e0}
  .hero .mapwrap{position:absolute;inset:0}
  .herolegend{position:absolute;left:12px;bottom:12px;z-index:3;background:rgba(255,255,255,.94);border:1px solid var(--line);border-radius:10px;padding:8px 11px;font-size:12.5px;line-height:1.6;backdrop-filter:blur(3px)}
  .herolegend b{display:block;font-size:11px;letter-spacing:.5px;text-transform:uppercase;color:var(--muted);margin-bottom:4px}
  .herolegend .lg{display:flex;align-items:center;gap:8px}
  .herolegend .sw{flex:none;border-radius:50%}
  .herolegend .sw.h{width:15px;height:15px;background:#d4a017;border:2px solid #fff;box-shadow:0 0 0 1px #0003}
  .herolegend .sw.o{width:10px;height:10px;background:#c96a2e;border:1.5px solid #fff;box-shadow:0 0 0 1px #0003}
  .herolegend .sw.s{width:12px;height:12px;background:#2f8f88;border:1.5px solid #fff;border-radius:3px;box-shadow:0 0 0 1px #0003}
  .sbadge{display:inline-block;background:#2f8f88;color:#fff;border-radius:6px;padding:1px 7px;font-size:11px;font-weight:700;margin-right:5px}
  .wcard.sac{border-color:#2f8f88}
  .whead{margin:26px 0 12px;font-size:19px;font-weight:700}
  .whead span{color:var(--muted);font-weight:400;font-size:14px;margin-left:8px}
  .heronote{position:absolute;right:12px;top:12px;z-index:3;background:rgba(255,255,255,.92);border:1px solid var(--line);border-radius:999px;padding:5px 12px;font-size:12.5px;font-weight:700}
  .maplibregl-popup-content{font:inherit;padding:0;border-radius:10px;overflow:hidden;max-width:230px}
  .pop img{display:block;width:100%;height:110px;object-fit:cover}
  .pop .pb{padding:8px 11px}
  .pop .pt{font-weight:700;font-size:14px;line-height:1.3}
  .pop .pth{color:var(--muted);font-size:13px;margin-top:1px}
  .pop .pc{color:var(--muted);font-size:10.5px;padding:0 11px 8px;line-height:1.35}
  .pop .pc a{color:var(--muted)}
  .pop .pbadge{display:inline-block;background:#d4a017;color:#3a2c07;border-radius:5px;padding:1px 6px;font-size:10.5px;font-weight:700;margin-bottom:3px}
  .wintro{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 18px;margin-bottom:16px;color:var(--muted);font-size:14px;line-height:1.6}
  .wfilter{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px;align-items:center}
  .wchip{border:1px solid var(--line);background:#fff;border-radius:999px;padding:6px 13px;font-weight:700;font-size:14px;cursor:pointer;text-decoration:none;color:var(--ink)}
  .wchip:hover{border-color:var(--teal)}
  .wchip.on{background:var(--teal);color:#fff;border-color:var(--teal)}
  .wsort{border:1px solid var(--line);border-radius:999px;padding:7px 12px;font:inherit;font-size:14px;background:#fff;min-height:40px}
  .sortlab{font-size:13px;color:var(--muted);font-weight:700;letter-spacing:.4px;text-transform:uppercase}
  .sortnote{font-size:12.5px;color:var(--muted)}
  .wsearch{flex:1;min-width:190px;border:1px solid var(--line);border-radius:999px;padding:7px 14px;font:inherit;font-size:14px}
  .wgrid{column-width:250px;column-gap:16px}
  .wcard{break-inside:avoid;display:inline-block;width:100%;margin:0 0 16px;background:#fff;border:1px solid var(--line);border-radius:12px;overflow:hidden;cursor:pointer}
  .wcard:hover{border-color:var(--gold);box-shadow:0 1px 8px #0001}
  .wcard.her{border-color:var(--gold)}
  .wcard .im{display:block;background:#f0efe9;border-bottom:1px solid var(--line)}
  .wcard .im img{width:100%;display:block}
  .wcard .wb{padding:10px 13px}
  .wcard .wt{font-weight:700;font-size:14px;color:var(--ink)}
  .wcard .wth{color:var(--muted);font-size:13px;margin-top:2px}
  .wcard .wm{color:var(--muted);font-size:12px;margin-top:6px;line-height:1.5}
  .wcard .cred{color:var(--muted);font-size:11px;padding:5px 13px 0;line-height:1.4}
  .wcard .cred a{color:var(--muted)}
  .wbadge{display:inline-block;background:var(--gold);color:#3a2c07;border-radius:6px;padding:1px 7px;font-size:11px;font-weight:700;margin-right:5px}
  .wlic{background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px 18px;margin-top:20px;color:var(--muted);font-size:13px;line-height:1.65}
  .wdl{background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px 18px;margin-top:14px;font-size:13.5px;line-height:1.7}
  .wdl a{color:var(--teal);font-weight:700}
  /* ---- place modal ---- */
  .mback{position:fixed;inset:0;background:#0f1a19cc;z-index:60;display:flex;align-items:flex-start;justify-content:center;padding:24px 16px;overflow-y:auto;backdrop-filter:blur(2px)}
  .mback[hidden]{display:none}
  .modal{background:#fff;border-radius:16px;max-width:620px;width:100%;overflow:hidden;box-shadow:0 30px 80px #0006;position:relative}
  .modal .mx{position:absolute;top:12px;right:12px;width:38px;height:38px;border-radius:10px;border:1px solid var(--line);background:#fff;font-size:22px;line-height:1;cursor:pointer;z-index:2}
  .modal .mx:focus-visible,.modal button:focus-visible,.modal a:focus-visible,.modal textarea:focus-visible{outline:3px solid var(--teal);outline-offset:2px}
  .mhero img{display:block;width:100%;max-height:280px;object-fit:cover;background:#eee}
  .mcred{font-size:11.5px;color:var(--muted);padding:6px 20px 0;line-height:1.45}
  .mcount{color:var(--ink);font-weight:700}
  .mstrip{display:flex;gap:6px;overflow-x:auto;padding:8px 20px 0}
  .mstrip button{flex:none;width:68px;height:52px;padding:0;border:1.5px solid var(--line);border-radius:8px;overflow:hidden;background:none;cursor:pointer}
  .mstrip button[aria-current="true"]{border-color:var(--teal);box-shadow:0 0 0 1px var(--teal)}
  .mstrip img{width:100%;height:100%;object-fit:cover;display:block}
  .mcred a{color:var(--muted)}
  .mbody{padding:16px 20px 20px}
  .mtitle{font-size:23px;font-weight:700;line-height:1.25}
  .mth{color:var(--muted);font-size:17px;margin-top:2px}
  .mtags{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
  .mtag{font-size:12px;font-weight:700;border-radius:7px;padding:3px 9px;border:1px solid var(--line);color:var(--muted)}
  .mtag.gold{background:var(--gold);color:#3a2c07;border-color:var(--gold)}
  .mtag.teal{background:#2f8f88;color:#fff;border-color:#2f8f88}
  .msec{margin-top:16px;padding-top:14px;border-top:1px solid var(--line)}
  .msec h3{margin:0 0 7px;font-size:12px;letter-spacing:.6px;text-transform:uppercase;color:var(--muted)}
  .mprose{font-size:15px;line-height:1.65}
  .mdeepblk{border-top:1px solid var(--line);padding-top:8px;margin-top:8px}
  .mdeepblk summary{cursor:pointer;font-weight:700;font-size:14px;padding:4px 0}
  .mdeepblk h4{font-size:14.5px;margin:12px 0 3px}
  .mdeepblk p{font-size:14.5px;line-height:1.62;margin:0 0 8px}
  .msecn{color:var(--muted);font-weight:400;font-size:12.5px}
  .mkind{background:#eef3f2;color:var(--teal);border-radius:5px;padding:1px 7px;font-size:11px;font-weight:700}
  .mfrom{font-size:11.5px;color:var(--muted);margin-top:6px}
  .mrow{display:grid;grid-template-columns:104px 1fr;gap:6px 12px;font-size:14.5px}
  .mrow dt{color:var(--muted)}
  .mrow dd{margin:0}
  .mbtns{display:flex;flex-wrap:wrap;gap:8px;margin-top:4px}
  .mbtn{border:1px solid var(--line);background:#fff;border-radius:999px;padding:8px 14px;font:inherit;font-size:13.5px;font-weight:700;cursor:pointer;color:var(--ink);text-decoration:none;display:inline-flex;align-items:center;gap:6px;min-height:40px}
  .mbtn:hover{border-color:var(--teal)}
  .mbtn.primary{background:var(--teal);color:#fff;border-color:var(--teal)}
  .mbtn.kofi{background:#fbf1dc;color:#8a5a00;border-color:transparent}
  .mnote textarea{width:100%;min-height:84px;border:1px solid var(--line);border-radius:10px;padding:10px 12px;font:inherit;font-size:14.5px;resize:vertical}
  .mfile{font-size:13px;color:var(--muted);margin-top:8px}
  .mqueue{font-size:12.5px;color:var(--muted);margin-top:8px}
  .mlic{font-size:12px;color:var(--muted);line-height:1.6;background:#faf9f5;border:1px solid var(--line);border-radius:10px;padding:10px 12px}
  .mlic a{color:var(--muted)}
  /* floating support button, present on every page */
  #kofloat{position:fixed;right:16px;bottom:16px;z-index:40;background:#fbf1dc;color:#8a5a00;border:1px solid #e6d3a8;border-radius:999px;padding:11px 16px;font-weight:700;font-size:14.5px;text-decoration:none;box-shadow:0 6px 18px #0002}
  #kofloat:hover{filter:brightness(.97)}
  @media (max-width:560px){#kofloat{bottom:70px}}
""",
  "<header><div><h1>Wats of Chiang Mai</h1><p class=sub>The tradition standing up in the landscape &mdash; temples of the Lanna north, heritage-registered sites marked</p></div>" + NAV + "</header>"
  "<main id=main><p class=muted>Loading&hellip;</p></main>"
  "<div class=mback id=mback hidden></div>"
  "<a id=kofloat href='https://ko-fi.com/defiantchiangmai' target=_blank rel=noopener>&#9749; Support</a>"
  "<script>" + r"""
const el=(t,p={},k=[])=>{const e=document.createElement(t);Object.assign(e,p);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
const BASE=(window.__LANNA_BASE__||'/');
let ALL=[],mode='all',q='',map=null,current=null,sortBy='photos',here=null;

// MapLibre is a separate cached asset, not inlined — ~780 kB has no business
// living inside the HTML of every page view.
function loadMapLib(){
  if(window.maplibregl)return Promise.resolve();
  return new Promise((res,rej)=>{
    const l=document.createElement('link');l.rel='stylesheet';l.href=BASE+'vendor/maplibre-gl.css';document.head.append(l);
    const s=document.createElement('script');s.src=BASE+'vendor/maplibre-gl.js';s.onload=()=>res();s.onerror=()=>rej(new Error('map library failed to load'));document.head.append(s);
  });
}
async function load(){let d;try{d=await (await fetch('/api/wats')).json();}catch(e){document.getElementById('main').textContent='Could not load the wat catalogue.';return;}
  window.__W=d;ALL=d.wats||[];
  if(!d.present||!ALL.length){document.getElementById('main').innerHTML='';document.getElementById('main').append(el('p',{className:'muted',textContent:'The wat catalogue has not been synced into this build yet.'}));return;}
  render();
  loadMapLib().then(initMap).catch(e=>{const h=document.getElementById('hero');if(h)h.innerHTML='<p class=muted style="padding:18px">Interactive map unavailable ('+e.message+'). The catalogue below still works.</p>';});
}
// Chips repaint the LIST only. They must never call render(), which rebuilds
// <main> — including a fresh #heromap div — while the MapLibre instance stays
// bound to the old, now-detached element. A detached container reports 0x0, so
// its style never finishes loading and every addSource throws "Style is not done
// loading" forever. That is why the map went blank the moment you filtered.
function chip(label,m){
  const a=el('a',{className:'wchip'+(mode===m?' on':'')});
  a.textContent=label; a.dataset.mode=m;
  a.onclick=()=>{
    mode=m;
    for(const c of document.querySelectorAll('.wchip')) c.classList.toggle('on', c.dataset.mode===m);
    paint(document.getElementById('wgrid'));
    syncMap();
  };
  return a;}
const PROVS=['Chiang Mai','Chiang Rai','Lamphun','Lampang','Nan'];
// The map payload inlines at most two photographs; photoCount is the real total,
// and the rest arrive with the place JSON when a modal opens. Counting the
// inlined array would under-report every temple that has more than two.
function nphotos(w){return (w.photoCount!=null)?w.photoCount:(w.photos||[]).length;}
function distKm(w){if(!here||w.lat==null)return null;
  const R=6371,t=x=>x*Math.PI/180;
  const dLa=t(w.lat-here.lat),dLo=t(w.lng-here.lng);
  const a=Math.sin(dLa/2)**2+Math.cos(t(here.lat))*Math.cos(t(w.lat))*Math.sin(dLo/2)**2;
  return 2*R*Math.asin(Math.sqrt(a));}
function passes(w){
  if(mode==='heritage'&&!w.heritage)return false;
  if(mode==='photos'&&!nphotos(w))return false;
  if(mode==='hours'&&!w.openingHours)return false;
  if(mode==='contact'&&!(w.phone||w.website||w.email))return false;
  if(PROVS.includes(mode)&&w.province!==mode)return false;
  if(q){const s=((w.name||'')+' '+(w.nameRoman||'')+' '+(w.province||'')+' '+(w.district||'')).toLowerCase();
        if(!s.includes(q))return false;}
  return true;}
function visible(){
  const out=ALL.filter(passes);
  const byName=(a,b)=>(a.nameRoman||a.name||'').localeCompare(b.nameRoman||b.name||'');
  if(sortBy==='photos')out.sort((a,b)=>nphotos(b)-nphotos(a)||byName(a,b));
  else if(sortBy==='near'&&here)out.sort((a,b)=>(distKm(a)??1e9)-(distKm(b)??1e9));
  else if(sortBy==='age')out.sort((a,b)=>{
    const A=parseInt(a.founded,10),B=parseInt(b.founded,10);
    if(isNaN(A)&&isNaN(B))return byName(a,b); if(isNaN(A))return 1; if(isNaN(B))return -1;
    return A-B;});
  else if(sortBy==='heritage')out.sort((a,b)=>(b.heritage?1:0)-(a.heritage?1:0)||byName(a,b));
  else out.sort(byName);
  return out;}

function render(){const d=window.__W,main=document.getElementById('main');main.textContent='';
  const hero=el('div',{className:'hero',id:'hero'});
  hero.append(el('div',{className:'mapwrap',id:'heromap'}));
  hero.append(el('div',{className:'heronote',id:'heronote',textContent:d.total.toLocaleString()+' temples'}));
  const lg=el('div',{className:'herolegend'});
  lg.append(el('b',{textContent:'Markers'}));
  lg.append(el('div',{className:'lg'},[el('span',{className:'sw h'}),el('span',{textContent:'Heritage-registered'})]));
  lg.append(el('div',{className:'lg'},[el('span',{className:'sw o'}),el('span',{textContent:'Wat (compiled, unvisited)'})]));
  if((d.sacred||[]).length)lg.append(el('div',{className:'lg'},[el('span',{className:'sw s'}),el('span',{textContent:'Sacred site (not a wat)'})]));
  hero.append(lg);
  main.append(hero);

  const intro=el('div',{className:'wintro'});
  intro.textContent=d.total.toLocaleString()+' temples mapped across the Lanna north, '+d.heritage+' registered as Thai historic sites, '+d.withPhotos+' with freely-licensed photography'+
    ((d.sacredTotal||0)?', plus '+d.sacredTotal+' notable places of spiritual significance that are not wats — city pillars, the sunken Lanna cities, sacred caves, mosques and monumental Buddha images':'')+
    '. Most records are machine-compiled and unvisited — they are leads into the landscape, not verified survey.';
  main.append(intro);

  const nHours=ALL.filter(w=>w.openingHours).length, nContact=ALL.filter(w=>w.phone||w.website||w.email).length;
  const f=el('div',{className:'wfilter'});
  f.append(chip('All ('+ALL.length+')','all'));
  f.append(chip('Heritage ('+d.heritage+')','heritage'));
  f.append(chip('Photographs ('+d.withPhotos+')','photos'));
  for(const pv of PROVS){const n=ALL.filter(w=>w.province===pv).length; if(n)f.append(chip(pv+' ('+n+')',pv));}
  if(nHours)f.append(chip('Published hours ('+nHours+')','hours'));
  if(nContact)f.append(chip('Has contact ('+nContact+')','contact'));
  const s=el('input',{className:'wsearch',type:'search',placeholder:'Search name, province or district…',value:q});
  s.oninput=()=>{q=s.value.trim().toLowerCase();const g=document.getElementById('wgrid');if(g)paint(g);syncMap();};
  f.append(s);main.append(f);

  // sort row — kept separate from the filter chips so it reads as a different act
  const sr=el('div',{className:'wfilter'});
  sr.append(el('span',{className:'sortlab',textContent:'Sort'}));
  const sel=el('select',{className:'wsort'});
  for(const [v,label] of [['photos','Most photographs'],['name','Name (A–Z)'],
      ['heritage','Heritage first'],['age','Oldest known first'],['near','Nearest to me']]){
    const o=el('option',{value:v,textContent:label}); if(v===sortBy)o.selected=true; sel.append(o);}
  sel.onchange=()=>{
    if(sel.value==='near'&&!here){
      if(!navigator.geolocation){alert('This browser cannot share a location.');sel.value=sortBy;return;}
      sel.disabled=true;
      navigator.geolocation.getCurrentPosition(pos=>{
        here={lat:pos.coords.latitude,lng:pos.coords.longitude};
        sortBy='near';sel.disabled=false;paint(document.getElementById('wgrid'));
      },()=>{alert('Could not get your location — it stays on your device either way.');sel.value=sortBy;sel.disabled=false;});
      return;}
    sortBy=sel.value;paint(document.getElementById('wgrid'));};
  sr.append(sel);
  sr.append(el('span',{className:'sortnote',id:'sortnote'}));
  main.append(sr);

  const grid=el('div',{className:'wgrid',id:'wgrid'});main.append(grid);paint(grid);

  if((d.sacred||[]).length){
    const h=el('div',{className:'whead'});h.append(document.createTextNode('Not exactly wats'));
    h.append(el('span',{textContent:d.sacred.length+' places of spiritual significance — city pillars, sunken cities, sacred caves, mosques, churches, monumental Buddha images'}));
    main.append(h);
    const sg=el('div',{className:'wgrid'});
    for(const x of d.sacred){
      const c=el('div',{className:'wcard sac'});
      const ph=(x.photos||[])[0];
      if(ph)c.append(el('a',{className:'im',href:ph.source,target:'_blank',rel:'noopener'},[el('img',{src:ph.thumb,loading:'lazy',alt:x.nameRoman||x.name||''})]));
      const b=el('div',{className:'wb'});
      b.append(el('div',{className:'wt'},[el('span',{className:'sbadge',textContent:(x.siteType||'sacred').split(';')[0]}),document.createTextNode(x.nameRoman||x.name||'')]));
      if(x.name&&x.name!==x.nameRoman)b.append(el('div',{className:'wth',textContent:x.name}));
      if(x.heritage)b.append(el('div',{className:'wm',textContent:x.heritage}));
      c.append(b);
      if(ph){const cr=el('div',{className:'cred'});
        cr.append(document.createTextNode(ph.author+' · '));
        cr.append(ph.licenseUrl?el('a',{href:ph.licenseUrl,target:'_blank',rel:'noopener',textContent:ph.license+(ph.publicDomain?' (public domain)':'')}):document.createTextNode(ph.license));
        cr.append(document.createTextNode(' · '));
        cr.append(el('a',{href:ph.source,target:'_blank',rel:'noopener',textContent:'Commons'}));
        c.append(cr);}
      c.onclick=(ev)=>{if(ev.target.closest('a'))return;openModal(x);};
      sg.append(c);}
    main.append(sg);}

  if(d.download){const dl=el('div',{className:'wdl'});
    dl.append(el('b',{textContent:'Take it with you. '}));
    dl.append(document.createTextNode('An offline app version of this map — installable, works with no signal: '));
    dl.append(el('a',{href:BASE+'wats/app/',textContent:'open the app'}));
    dl.append(document.createTextNode(' · '));
    dl.append(el('a',{href:BASE+'wats/app/wats-offline.html',download:'',textContent:'download the single-file map'}));
    main.append(dl);}

  const lic=el('div',{className:'wlic'});const at=d.attribution||{};
  lic.append(el('b',{textContent:'Sources and licence. '}));
  lic.append(document.createTextNode('Temple locations are derived from OpenStreetMap and are therefore published under the '));
  lic.append(el('a',{href:at.dataUrl||'https://opendatacommons.org/licenses/odbl/1-0/',target:'_blank',rel:'noopener',textContent:'Open Database License (ODbL) 1.0'}));
  lic.append(document.createTextNode(' — share-alike, which is a different licence from the rest of this site. '+(at.facts||'Wikidata, CC0')+'. Photographs are hosted by Wikimedia Commons and are NOT relicensed here: each is credited to its author under its own terms beneath the image.'));
  main.append(lic);
  openFromHash();}

const SORTNOTE={
  age:'Only 8 temples have a recorded founding date — the rest sort after them, undated.',
  near:'Distances are computed on your device; your location is never sent anywhere.',
  photos:'Temples with the most freely-licensed photographs first.'};
function paint(grid){grid.textContent='';const items=visible();
  const note=document.getElementById('heronote');
  if(note)note.textContent=items.length.toLocaleString()+' shown';
  const sn=document.getElementById('sortnote'); if(sn)sn.textContent=SORTNOTE[sortBy]||'';
  if(!items.length){grid.append(el('p',{className:'muted',textContent:'No temple matches.'}));return;}
  for(const w of items){
    const c=el('div',{className:'wcard'+(w.heritage?' her':'')});
    const ph=(w.photos||[])[0];
    if(ph){c.append(el('a',{className:'im',href:ph.source,target:'_blank',rel:'noopener'},[el('img',{src:ph.thumb,loading:'lazy',alt:w.nameRoman||w.name||'temple'})]));}
    const b=el('div',{className:'wb'});
    b.append(el('div',{className:'wt'},[w.heritage?el('span',{className:'wbadge',textContent:'Heritage'}):null,document.createTextNode(w.nameRoman||w.name||'(unnamed)')]));
    if(w.name&&w.name!==w.nameRoman)b.append(el('div',{className:'wth',textContent:w.name}));
    const bits=[];if(w.province)bits.push(w.province);
    const dk=distKm(w); if(dk!=null)bits.push(dk<1?Math.round(dk*1000)+' m away':dk.toFixed(dk<10?1:0)+' km away');
    if(w.founded)bits.push('founded '+w.founded);
    if(nphotos(w))bits.push(nphotos(w)+' photo'+(nphotos(w)===1?'':'s'));
    b.append(el('div',{className:'wm',textContent:bits.join(' · ')}));
    c.append(b);
    if(ph){const cr=el('div',{className:'cred'});
      cr.append(document.createTextNode(ph.author+' · '));
      cr.append(ph.licenseUrl?el('a',{href:ph.licenseUrl,target:'_blank',rel:'noopener',textContent:ph.license}):document.createTextNode(ph.license));
      cr.append(document.createTextNode(' · '));
      cr.append(el('a',{href:ph.source,target:'_blank',rel:'noopener',textContent:'Commons'}));
      c.append(cr);}
    c.onclick=(ev)=>{if(ev.target.closest('a'))return;openModal(w);};
    grid.append(c);}}

// ---- hero map ----
function fc(list){return {type:'FeatureCollection',features:list.filter(w=>w.lat!=null&&w.lng!=null).map(w=>({
  type:'Feature',geometry:{type:'Point',coordinates:[w.lng,w.lat]},
  properties:{id:w.id,her:!!w.heritage,sac:!!w.siteType,kindLabel:(w.siteType||'').split(';')[0],
    name:w.nameRoman||w.name||'',th:(w.name&&w.name!==w.nameRoman)?w.name:'',
    heritage:w.heritage||'',thumb:(w.photos||[])[0]?w.photos[0].thumb:'',
    author:(w.photos||[])[0]?w.photos[0].author:'',lic:(w.photos||[])[0]?w.photos[0].license:'',
    src:(w.photos||[])[0]?w.photos[0].source:''}}))};}

function initMap(){
  const box=document.getElementById('heromap'); if(!box)return;
  map=new maplibregl.Map({container:box,
    style:{version:8,
      // Glyph server so we can draw our OWN labels. The OSM raster basemap
      // renders place names in Thai only (it uses the local `name` tag), which
      // is correct for Thailand and unhelpful if you don't read Thai — and it
      // is baked into the tile image, so it cannot be restyled. Drawing the
      // romanised temple names ourselves is the reliable fix.
      glyphs:'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
      sources:{osm:{type:'raster',tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],tileSize:256,
      attribution:'© OpenStreetMap contributors (ODbL) · photos via Wikimedia Commons'}},
      layers:[{id:'bg',type:'background',paint:{'background-color':'#e9e7e0'}},{id:'osm',type:'raster',source:'osm'}]},
    center:[99.4,18.9],zoom:6.6});
  map.addControl(new maplibregl.NavigationControl({showCompass:false}),'top-right');
  map.addControl(new maplibregl.FullscreenControl(),'top-right');
  let ready=false;
  // Adding layers is attempted, not gated on isStyleLoaded(). That flag stays
  // false for as long as tiles are outstanding, which on a slow or filtered
  // network is forever — and the map then never draws its markers even though
  // the style itself parsed fine. addSource/addLayer simply throw while the
  // style isn't ready, so we try, swallow, and let the poll retry. Each step is
  // guarded so a partial run can finish on the next tick.
  const build=()=>{
    if(ready)return;
    try{
      if(!map.getSource('wats'))
        map.addSource('wats',{type:'geojson',data:fc(ALL.concat((window.__W||{}).sacred||[]))});
      if(!map.getLayer('w-s'))map.addLayer({id:'w-s',type:'circle',source:'wats',filter:['get','sac'],
        paint:{'circle-radius':['interpolate',['linear'],['zoom'],6,3.6,10,6,14,10],
          'circle-color':'#2f8f88','circle-stroke-color':'#fff','circle-stroke-width':1.6}});
      if(!map.getLayer('w-n'))map.addLayer({id:'w-n',type:'circle',source:'wats',filter:['all',['!',['get','her']],['!',['get','sac']]],
        paint:{'circle-radius':['interpolate',['linear'],['zoom'],6,2.4,10,4,14,7],
          'circle-color':'#c96a2e','circle-stroke-color':'#fff','circle-stroke-width':1,'circle-opacity':.9}});
      if(!map.getLayer('w-h'))map.addLayer({id:'w-h',type:'circle',source:'wats',filter:['all',['get','her'],['!',['get','sac']]],
        paint:{'circle-radius':['interpolate',['linear'],['zoom'],6,4,10,7,14,11],
          'circle-color':'#d4a017','circle-stroke-color':'#fff','circle-stroke-width':2}});
      // Romanised names, drawn by us. Heritage sites label earlier because they
      // are the landmarks people navigate by; everything else joins at z13.
      if(!map.getLayer('w-label'))map.addLayer({id:'w-label',type:'symbol',source:'wats',minzoom:10.5,
        layout:{'text-field':['get','name'],'text-font':['Open Sans Regular'],
          'text-size':['interpolate',['linear'],['zoom'],11,10,15,13],
          'text-offset':[0,1.1],'text-anchor':'top','text-max-width':10,
          'text-allow-overlap':false,'text-optional':true},
        paint:{'text-color':'#2b2f2e','text-halo-color':'#fff','text-halo-width':1.8,
          'text-opacity':['interpolate',['linear'],['zoom'],10.5,0,12,1]},
        filter:['any',['get','her'],['get','sac'],['>=',['zoom'],13]]});
    }catch(e){
      // Retrying silently is right for the first few frames (the style really is
      // still parsing) but wrong forever — this hid a dead map for hours. Give
      // up loudly instead of spinning, and say so on the page.
      if(++buildTries>60){
        clearInterval(t);
        const h=document.getElementById('hero');
        if(h&&!h.dataset.failed){h.dataset.failed='1';
          h.insertAdjacentHTML('beforeend','<div class="heronote" style="left:12px;top:12px;right:auto;background:#fff">Map could not start: '+esc(e.message)+'</div>');}
        console.error('hero map failed to initialise:',e);
      }
      return;
    }
    ready=true;
    for(const id of ['w-n','w-h','w-s']){
      map.on('click',id,e=>{const f=e.features[0];const x=byId(f.properties.id);if(x)openModal(x);else popup(f);});
      map.on('mouseenter',id,()=>map.getCanvas().style.cursor='pointer');
      map.on('mouseleave',id,()=>map.getCanvas().style.cursor='');
    }
    fitAll(); syncMap(); map.resize();
  };
  map.on('style.load',build); map.on('load',()=>{build();map.resize();});
  map.on('error',(e)=>console.warn('map:',e&&e.error&&e.error.message));
  // some embedded/throttled renderers never deliver those events to late
  // handlers — poll until the style is parsed, then nudge a repaint.
  const t=setInterval(()=>{build();if(ready){map.resize();map.panBy([1,1],{duration:0});map.panBy([-1,-1],{duration:0});clearInterval(t);}},150);
  window.addEventListener('resize',()=>map&&map.resize());
}
function fitAll(){const pts=ALL.concat((window.__W||{}).sacred||[]).filter(w=>w.lat!=null);if(!pts.length||!map)return;
  let n=-90,s=90,e=-180,w2=180;for(const p of pts){n=Math.max(n,p.lat);s=Math.min(s,p.lat);e=Math.max(e,p.lng);w2=Math.min(w2,p.lng);}
  map.fitBounds([[w2,s],[e,n]],{padding:40,duration:0});}
function syncMap(){if(!map||!map.getLayer('w-n'))return;
  const ids=visible().map(w=>w.id);const set=['in',['get','id'],['literal',ids]];
  map.setFilter('w-n',['all',['!',['get','her']],['!',['get','sac']],set]);
  map.setFilter('w-h',['all',['get','her'],['!',['get','sac']],set]);
  if(map.getLayer('w-s'))map.setFilter('w-s',['all',['get','sac'],set]);
  if(map.getLayer('w-label'))map.setFilter('w-label',set);}
function popup(f){const p=f.properties;
  const body='<div class="pop">'+(p.thumb?'<img src="'+p.thumb+'" alt="">':'')+
    '<div class="pb">'+(p.sac?'<span class="pbadge" style="background:#2f8f88;color:#fff">'+esc(p.kindLabel||'sacred site')+'</span><br>':'')+(p.her?'<span class="pbadge">Heritage</span><br>':'')+
    '<div class="pt">'+esc(p.name)+'</div>'+(p.th?'<div class="pth">'+esc(p.th)+'</div>':'')+'</div>'+
    (p.thumb?'<div class="pc">'+esc(p.author)+' · '+esc(p.lic)+' · <a href="'+p.src+'" target="_blank" rel="noopener">Commons</a></div>':'')+'</div>';
  new maplibregl.Popup({offset:12,maxWidth:'240px'}).setLngLat(f.geometry.coordinates).setHTML(body).addTo(map);}
function flyTo(w){if(!map||w.lat==null)return;
  map.flyTo({center:[w.lng,w.lat],zoom:Math.max(map.getZoom(),14),speed:1.4});
  document.getElementById('hero').scrollIntoView({behavior:'smooth',block:'center'});}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}

// ---------------- place modal ----------------
// Admin address is assembled at runtime rather than sitting in the HTML as a
// literal mailto:, which keeps it out of the reach of the dumbest harvesters.
// It is not a real secret — it is already printed in the repo README — but there
// is no reason to gift-wrap it.
const ADMIN=['530kings','proton.me'].join('@');
// The contribution endpoint. A note reaches a moderation queue and NEVER the
// live map: /suggest is public and rate-limited, and only a holder of an admin
// capability token can approve anything out of that queue. Sending stays a
// deliberate button press — see sendQueue() for what does and does not travel.
const WORKER='https://mueang-map-sync.wichaa.workers.dev';
const QKEY='wichaa_wat_submissions';
const qGet=()=>{try{return JSON.parse(localStorage.getItem(QKEY)||'[]')}catch(e){return[]}};
const qSet=(v)=>{try{localStorage.setItem(QKEY,JSON.stringify(v))}catch(e){alert('Local storage is full — send or download your queued notes first.')}};

function placeUrl(x){const u=new URL(location.href);u.hash='place='+encodeURIComponent(x.id);return u.toString();}
// Sharing uses the place's OWN page, not the map's #fragment. A fragment is
// never sent to a server, so an unfurler (Facebook, X, LINE) would only ever see
// the generic site card — no temple name, no photograph. /place/<id>/ is a real
// URL with its own og: tags, so the preview shows the place.
function shareUrl(x){return location.origin+BASE+'place/'+encodeURIComponent(x.id)+'/';}
function openModal(x){
  const isSac=!!x.siteType;
  const ph=(x.photos||[])[0];
  const sum=x.summary||null, desc=x.description||'';
  const back=document.getElementById('mback');
  const lat=x.lat,lng=x.lng,ll=lat+','+lng;
  const share=shareUrl(x), st=encodeURIComponent((x.nameRoman||x.name||'')+' — wichaa');
  const su=encodeURIComponent(share);
  const H=[];
  H.push('<div class="modal" role="dialog" aria-modal="true" aria-label="'+esc(x.nameRoman||x.name||'place')+'">');
  H.push('<button class="mx" aria-label="Close">&times;</button>');
  // Every photograph, not just the first. The card advertised "3 photos" and the
  // modal rendered photos[0] — so the count was true and the display was a lie.
  const pics=(x.photos||[]);
  // The strip container is emitted whenever more photographs EXIST, even if the
  // payload only inlined two — the deep fetch fills it in a moment later.
  if(pics.length)H.push('<div class="mhero" id="mhero"></div><div class="mcred" id="mcred"></div>'+
    ((pics.length>1||nphotos(x)>1)?'<div class="mstrip" id="mstrip"></div>':''));
  H.push('<div class="mbody">');
  H.push('<div class="mtitle">'+esc(x.nameRoman||x.name||'(unnamed)')+'</div>');
  if(x.name&&x.name!==x.nameRoman)H.push('<div class="mth">'+esc(x.name)+'</div>');
  H.push('<div class="mtags">');
  if(isSac)H.push('<span class="mtag teal">'+esc((x.siteType||'').split(';')[0])+'</span>');
  if(x.heritage)H.push('<span class="mtag gold">★ '+esc(x.heritage)+'</span>');
  H.push('<span class="mtag">'+(x.confidence==='verified'?'field-verified':'compiled · unvisited')+'</span></div>');

  H.push('<div class="msec" id="mdeep" hidden></div>');
  if(sum&&sum.text){H.push('<div class="msec"><h3>About</h3><div class="mprose">'+esc(sum.text)+'</div>'+
    '<div class="mfrom">From <a href="'+esc(sum.url)+'" target="_blank" rel="noopener">'+esc(sum.title)+'</a> on Wikipedia · '+
    '<a href="'+esc(sum.licenseUrl)+'" target="_blank" rel="noopener">'+esc(sum.license)+'</a> — reused here under that licence.</div></div>');}
  else if(desc){H.push('<div class="msec"><h3>About</h3><div class="mprose">'+esc(desc)+'</div>'+
    '<div class="mfrom">Wikidata description · CC0 (public domain dedication)</div></div>');}

  H.push('<div class="msec"><h3>Details</h3><dl class="mrow">');
  if(x.founded)H.push('<dt>Founded</dt><dd>'+esc(x.founded)+'</dd>');
  if(x.province)H.push('<dt>Province</dt><dd>'+esc(x.province)+(x.district?' · '+esc(x.district):'')+'</dd>');
  if(x.street)H.push('<dt>Address</dt><dd>'+esc(x.street)+'</dd>');
  if(isSac&&x.siteType)H.push('<dt>Type</dt><dd>'+esc(x.siteType)+'</dd>');
  if(x.heritage)H.push('<dt>Heritage</dt><dd>'+esc(x.heritage)+'</dd>');
  H.push('<dt>Coordinates</dt><dd>'+lat.toFixed(5)+', '+lng.toFixed(5)+' <button class="mbtn" style="padding:2px 9px;min-height:0" data-copy="'+ll+'">copy</button></dd>');
  const srcs=(x.sources||[]).map(function(sc){
    if(sc.type==='osm'&&sc.ref)return '<a href="https://www.openstreetmap.org/'+esc(sc.ref)+'" target="_blank" rel="noopener">OpenStreetMap</a>';
    if(sc.type==='wikidata'&&sc.ref)return '<a href="https://www.wikidata.org/wiki/'+esc(sc.ref)+'" target="_blank" rel="noopener">Wikidata</a>';
    return esc(sc.type);});
  H.push('<dt>Sources</dt><dd>'+[...new Set(srcs)].join(' · ')+'</dd></dl></div>');

  // Contact + hours only appear when the temple actually has them. Thai wats are
  // generally open dawn to dusk and don't publish hours — 14 of 1,307 record any
  // — so an absent block means "not recorded", never "closed", and we say so
  // rather than letting a blank imply something false.
  if(x.phone||x.website||x.email||x.facebook||x.openingHours){
    H.push('<div class="msec"><h3>Contact &amp; hours</h3><dl class="mrow">');
    if(x.openingHours)H.push('<dt>Hours</dt><dd>'+esc(x.openingHours)+'</dd>');
    if(x.phone)H.push('<dt>Phone</dt><dd><a href="tel:'+esc(String(x.phone).replace(/[^+0-9]/g,''))+'">'+esc(x.phone)+'</a></dd>');
    if(x.email)H.push('<dt>Email</dt><dd><a href="mailto:'+esc(x.email)+'">'+esc(x.email)+'</a></dd>');
    if(x.website)H.push('<dt>Website</dt><dd><a href="'+esc(x.website)+'" target="_blank" rel="noopener">'+esc(String(x.website).replace(/^https?:\/\//,'').slice(0,44))+'</a></dd>');
    if(x.facebook)H.push('<dt>Facebook</dt><dd><a href="'+esc(x.facebook)+'" target="_blank" rel="noopener">page</a></dd>');
    H.push('</dl></div>');
  } else {
    H.push('<div class="msec"><h3>Contact &amp; hours</h3><div class="mfrom">Not recorded for this temple. Most wats in the north keep no published hours — they are generally open from dawn until dusk. This is an absence of data, not a statement that it is closed.</div></div>');
  }

  H.push('<div class="msec"><h3>Get there</h3><div class="mbtns">'+
    '<a class="mbtn primary" target="_blank" rel="noopener" href="https://www.google.com/maps/dir/?api=1&destination='+ll+'">Google Maps</a>'+
    '<a class="mbtn" target="_blank" rel="noopener" href="https://maps.apple.com/?daddr='+ll+'">Apple Maps</a>'+
    '<a class="mbtn" target="_blank" rel="noopener" href="https://www.openstreetmap.org/directions?to='+ll+'">OpenStreetMap</a>'+
    '<button class="mbtn" data-fly="1">Show on the map</button></div></div>');

  H.push('<div class="msec"><h3>Share this place</h3><div class="mbtns">'+
    '<button class="mbtn primary" data-copy="'+esc(share)+'">Copy link</button>'+
    (navigator.share?'<button class="mbtn" data-native="1">Share…</button>':'')+
    '<a class="mbtn" target="_blank" rel="noopener" href="https://www.facebook.com/sharer/sharer.php?u='+su+'">Facebook</a>'+
    '<a class="mbtn" target="_blank" rel="noopener" href="https://social-plugins.line.me/lineit/share?url='+su+'">LINE</a>'+
    '<a class="mbtn" target="_blank" rel="noopener" href="https://t.me/share/url?url='+su+'&text='+st+'">Telegram</a>'+
    '<a class="mbtn" href="'+esc(share)+'">Open its own page</a>'+
    '</div><div class="mfrom">The shared link is this place\'s own page, so it unfurls with its photograph and name rather than a generic site card.</div></div>');

  // A temple updating its own entry is the single most valuable submission we
  // can get — it is the only source that actually knows the hours. Give it its
  // own affordance and a filled-in template, rather than hoping an abbot works
  // out what to type into a blank box.
  H.push('<div class="msec mnote"><h3>Add a note or a photo</h3>'+
    '<div class="mbtns" style="margin-bottom:9px">'+
      '<button class="mbtn" data-temple="1">&#127982; I\'m from this temple</button>'+
    '</div>'+
    '<textarea id="mnotetxt" placeholder="Correction, opening hours, what it is like to visit, a name spelled properly…"></textarea>'+
    '<div class="mfile"><input type="file" id="mnotefile" accept="image/*"> <span id="mfilehint"></span></div>'+
    // CC BY-SA is an attribution licence, so a photograph without a credit is one
    // the archive cannot lawfully publish. Asked for here rather than discovered
    // at moderation, when the contributor is long gone.
    '<input id="mnoteby" type="text" autocomplete="name" placeholder="Your name — the credit on your photograph" '+
      'style="width:100%;margin-top:8px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;font:inherit;background:var(--bg);color:var(--ink)">'+
    '<div class="mbtns" style="margin-top:10px">'+
      '<button class="mbtn primary" data-queue="1">Add to my submissions</button>'+
      '<button class="mbtn primary" data-send="1">Send to the archive</button>'+
      '<button class="mbtn" data-email="1">Email them to the archivist</button>'+
      '<button class="mbtn" data-dl="1">Download submission file</button>'+
    '</div>'+
    '<div class="mqueue" id="mqueue"></div>'+
    '<div class="mfrom">Nothing is sent automatically. Notes stay on this device until you press a button. <b>Send to the archive</b> posts them to a moderation queue, where a person reads every one before anything is published — nothing you send reaches the map on its own, and the queue is never public. Photographs travel too, credited to the name you give. No account, no sign-in, and nothing about you is collected beyond what you type — your photograph is not visible to anyone but the archivist until it is approved. Only submit photographs you took yourself and are willing to release under CC BY-SA 4.0.</div></div>');

  H.push('<div class="msec"><h3>Licence</h3><div class="mlic">'+
    '<b>Location data</b> — derived from OpenStreetMap, published under the <a href="https://opendatacommons.org/licenses/odbl/1-0/" target="_blank" rel="noopener">Open Database Licence 1.0</a> (share-alike): reuse it, but a derived database must stay ODbL and credit © OpenStreetMap contributors.<br>'+
    '<b>Facts</b> (founding dates, heritage status, short descriptions) — from Wikidata, <a href="https://creativecommons.org/publicdomain/zero/1.0/" target="_blank" rel="noopener">CC0</a>: public domain, no conditions.<br>'+
    (sum&&sum.text?'<b>The description above</b> — from Wikipedia, <a href="'+esc(sum.licenseUrl)+'" target="_blank" rel="noopener">'+esc(sum.license)+'</a>: reusable with attribution, share-alike.<br>':'')+
    (ph?'<b>The photograph above</b> — '+esc(ph.author)+', '+esc(ph.license)+(ph.publicDomain?' (public domain — no conditions)':' — reusable with attribution to the photographer')+', via Wikimedia Commons. It is <i>not</i> relicensed by this site.<br>':'')+
    '<b>Nothing here is all-rights-reserved.</b> Every item is public domain or a Creative Commons / open-data licence, named above.'+
    '</div></div>');

  H.push('<div class="msec"><div class="mbtns"><a class="mbtn kofi" target="_blank" rel="noopener" href="https://ko-fi.com/defiantchiangmai">&#9749; Support this work</a></div></div>');
  H.push('</div></div>');
  back.innerHTML=H.join('');
  back.hidden=false;
  document.body.style.overflow='hidden';
  history.replaceState(null,'','#place='+encodeURIComponent(x.id));
  renderQueue();
  const m=back.querySelector('.modal');
  loadDeep(x);
  if(pics.length)showPic(pics,0);
  m.querySelector('.mx').onclick=closeModal;
  m.querySelectorAll('[data-copy]').forEach(b=>b.onclick=()=>{navigator.clipboard&&navigator.clipboard.writeText(b.dataset.copy);b.textContent='copied';setTimeout(()=>{b.textContent=b.dataset.copy===share?'Copy link':'copy'},1400);});
  const nb=m.querySelector('[data-native]'); if(nb)nb.onclick=()=>navigator.share({title:x.nameRoman||x.name,url:share}).catch(()=>{});
  m.querySelector('[data-fly]').onclick=()=>{closeModal();flyTo(x);};
  const tb=m.querySelector('[data-temple]');
  if(tb)tb.onclick=()=>{
    const t=document.getElementById('mnotetxt');
    if(!t.value.trim())t.value=
      'I help look after this temple.\n\n'+
      'Opening hours: \n'+
      'Phone: \n'+
      'Website / Facebook: \n'+
      'Correct name (Thai): \n'+
      'Correct name (roman): \n'+
      'Anything visitors should know: \n';
    t.dataset.fromTemple='1';
    t.focus();
    t.setSelectionRange(t.value.indexOf('Opening hours: ')+15, t.value.indexOf('Opening hours: ')+15);
  };
  m.querySelector('[data-queue]').onclick=()=>queueNote(x);
  m.querySelector('[data-send]').onclick=(e)=>sendQueue(e.target);
  m.querySelector('[data-email]').onclick=()=>emailQueue();
  m.querySelector('[data-dl]').onclick=()=>downloadQueue();
  const fi=m.querySelector('#mnotefile');
  fi.onchange=()=>{const f=fi.files[0];document.getElementById('mfilehint').textContent=f?(f.name+' — will be downscaled'):'';};
  m.querySelector('.mx').focus();
}
// The full article can run to 14,000 characters across a dozen sections. That
// has no business in the map payload, which has to load 1,300 points fast — so
// it lives in the place's own JSON and is fetched only when a modal opens.
const _deepCache={},_photoCache={};
function loadDeep(x){
  const slot=document.getElementById('mdeep'); if(!slot)return;
  const render=(art)=>{
    if(!art||!Object.keys(art).length)return;
    const KIND={architecture:'Architecture',history:'History',interest:'Of interest',heritage:'Heritage listing'};
    const LANG={th:'ภาษาไทย (Thai)',en:'English'};
    let h='';
    for(const lang of ['th','en']){
      const a=art[lang]; if(!a||!(a.sections||[]).length)continue;
      h+='<details class="mdeepblk"'+(lang==='th'?' open':'')+'><summary>In depth · '+esc(LANG[lang])+
         ' <span class="msecn">'+a.sections.length+' sections</span></summary>';
      for(const sec of a.sections){
        const kl=KIND[sec.kind]||sec.kind||'';
        const dupe=kl&&String(sec.heading||'').toLowerCase().includes(kl.toLowerCase());
        h+='<h4>'+esc(sec.heading||'')+((kl&&!dupe)?' <span class="mkind">'+esc(kl)+'</span>':'')+'</h4>';
        for(const para of String(sec.text||'').split('\n')) if(para.trim()) h+='<p>'+esc(para)+'</p>';
      }
      h+='<div class="mfrom">From <a href="'+esc(a.url)+'" target="_blank" rel="noopener">'+esc(a.title)+
         '</a> on Wikipedia · <a href="'+esc(a.licenseUrl)+'" target="_blank" rel="noopener">'+esc(a.license)+
         '</a> — reused here under that licence.</div></details>';
    }
    if(!h)return;
    slot.innerHTML='<h3>In depth</h3>'+h; slot.hidden=false;
  };
  const upgradePhotos=(full)=>{
    if(!full||full.length<=(x.photos||[]).length)return;
    x.photos=full;                       // keep it for next time this modal opens
    const slot=document.getElementById('mhero');
    if(slot)showPic(full,0);             // redraw the gallery with the full strip
  };
  if(_deepCache[x.id]!==undefined){render(_deepCache[x.id]);upgradePhotos(_photoCache[x.id]);return;}
  fetch(BASE+'api/place/'+encodeURIComponent(x.id)+'.json')
    .then(r=>r.ok?r.json():null)
    .then(j=>{
      const a=(j&&j.article)||null; _deepCache[x.id]=a; render(a);
      const full=(j&&j.photos)||null; _photoCache[x.id]=full; upgradePhotos(full);
    })
    .catch(()=>{_deepCache[x.id]=null;});
}
function showPic(pics,i){
  const hero=document.getElementById('mhero'), cred=document.getElementById('mcred');
  if(!hero)return;
  const m=pics[i];
  hero.innerHTML='<img src="'+esc(m.thumb)+'" alt="">';
  cred.innerHTML=esc(m.author)+' · '+(m.licenseUrl?'<a href="'+esc(m.licenseUrl)+'" target="_blank" rel="noopener">'+esc(m.license)+'</a>':esc(m.license))+
    (m.publicDomain?' <b>(public domain)</b>':'')+' · <a href="'+esc(m.source)+'" target="_blank" rel="noopener">Wikimedia Commons</a>'+
    (pics.length>1?' &nbsp;<span class="mcount">'+(i+1)+' of '+pics.length+'</span>':'');
  const strip=document.getElementById('mstrip');
  if(strip){
    strip.innerHTML=pics.map((q,j)=>'<button type="button" data-i="'+j+'" aria-current="'+(j===i)+'" aria-label="Photograph '+(j+1)+'"><img src="'+esc(q.thumb)+'" alt=""></button>').join('');
    for(const b of strip.querySelectorAll('button')) b.onclick=()=>showPic(pics,+b.dataset.i);
  }
}
function closeModal(){const b=document.getElementById('mback');b.hidden=true;b.innerHTML='';document.body.style.overflow='';history.replaceState(null,'',location.pathname+location.search);}
function renderQueue(){const el=document.getElementById('mqueue');if(!el)return;const n=qGet().length;
  el.textContent=n?(n+' submission'+(n===1?'':'s')+' waiting on this device.'):'No submissions queued yet.';}
// Downscale before storing: a phone photo is several megabytes and localStorage
// gives us about five in total, so a raw dataURL would fill the queue instantly.
function shrink(file){return new Promise(res=>{
  const r=new FileReader();
  r.onload=()=>{const img=new Image();img.onload=()=>{
    const M=1200,sc=Math.min(1,M/Math.max(img.width,img.height));
    const c=document.createElement('canvas');c.width=Math.round(img.width*sc);c.height=Math.round(img.height*sc);
    c.getContext('2d').drawImage(img,0,0,c.width,c.height);
    res(c.toDataURL('image/jpeg',0.8));};img.onerror=()=>res(null);img.src=r.result;};
  r.onerror=()=>res(null); r.readAsDataURL(file);});}
async function queueNote(x){
  const t=document.getElementById('mnotetxt'), fi=document.getElementById('mnotefile');
  const by=document.getElementById('mnoteby');
  const note=(t.value||'').trim(); const file=fi.files[0];
  if(!note&&!file){alert('Write a note or attach a photo first.');return;}
  // A photograph with no credit cannot be published under CC BY-SA, so the name
  // is collected while the person is still here rather than chased later.
  if(file&&!(by&&by.value.trim())){alert('Please add your name — it becomes the credit on your photograph.');if(by)by.focus();return;}
  let photo=null;
  if(file){ if(file.size>12*1024*1024){alert('That image is very large — please pick one under 12 MB.');return;} photo=await shrink(file); }
  const q=qGet();
  q.push({place:x.id,name:x.nameRoman||x.name,lat:x.lat,lng:x.lng,note:note,photo:photo,
          sac:!!x.siteType, by:(by&&by.value.trim())||'',
          fromTemple:t.dataset.fromTemple==='1',
          at:new Date().toISOString(),url:shareUrl(x)});
  qSet(q); t.value=''; fi.value=''; document.getElementById('mfilehint').textContent='';
  renderQueue();
}
function digest(){const q=qGet();if(!q.length)return null;
  return q.map((s,i)=>(i+1)+'. '+(s.name||s.place)+(s.fromTemple?'   [FROM THE TEMPLE]':'')+'  ('+s.lat+', '+s.lng+')\n'+
    '   '+s.url+'\n   '+(s.note||'(no note)')+(s.photo?'\n   [a photo is attached in the downloaded file]':'')).join('\n\n');}
// Post the queued notes to the moderation queue, one suggestion each.
//
// A photograph goes up FIRST, on its own endpoint, and the note then carries a
// reference to it — so the picture and the claim about the place arrive as one
// reviewable unit. If the image fails to upload the note is NOT sent either:
// half a contribution silently becoming a whole one is the kind of quiet lie
// this archive exists to avoid.
//
// Only entries the server actually accepted are cleared. Failures stay queued
// with the reason shown, so a flaky connection can never eat somebody notes.
async function sendQueue(btn){
  const q=qGet(); if(!q.length){alert('Nothing queued yet.');return;}
  const el=document.getElementById('mqueue');
  if(btn){btn.disabled=true;btn.textContent='Sending...';}
  const today=new Date().toISOString().slice(0,10);
  const keep=[]; let sent=0, pics=0, why='';
  for(const s of q){
    const media=[];
    try{
      if(s.photo){
        const pr=await fetch(WORKER+'/photo',{method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({place:s.place, dataUrl:s.photo, by:s.by||'anonymous contributor',
                               licence:'CC BY-SA 4.0', note:s.note||''})});
        let pj={}; try{ pj=await pr.json(); }catch(e){}
        if(!(pr.ok&&pj.ok)){ keep.push(s); why=pj.error||('photograph rejected, HTTP '+pr.status); continue; }
        media.push({type:'photo', key:pj.key, by:s.by||'anonymous contributor', licence:'CC BY-SA 4.0'});
        pics++;
      }
      const point={id:s.place, lens:[s.sac?'sacred':'wat'], name:s.name||s.place,
        lat:s.lat, lng:s.lng, geoPrecision:'block',
        attrs:{note:s.note||'', fromTemple:!!s.fromTemple, page:s.url||''},
        media:media,
        sources:[{type:'field', by:(s.by||(s.fromTemple?'temple':'visitor'))+' via wichaa.net', date:today}],
        confidence:'reported', updatedAt:today};
      const r=await fetch(WORKER+'/suggest',{method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({kind:'correction', point:point})});
      let j={}; try{ j=await r.json(); }catch(e){}
      if(r.ok&&j.ok){ sent++; } else { keep.push(s); why=j.error||('HTTP '+r.status); }
    }catch(e){ keep.push(s); why='could not reach the archive'; }
  }
  qSet(keep); renderQueue();
  if(btn){btn.disabled=false;btn.textContent='Send to the archive';}
  const bits=[];
  if(sent) bits.push(sent+' submission'+(sent===1?'':'s')+' sent for review'+(pics?(', including '+pics+' photograph'+(pics===1?'':'s')):'')+'. Thank you.');
  if(keep.length) bits.push(keep.length+' could not be sent ('+why+') and are still queued here, so nothing was lost.');
  if(el&&bits.length) el.textContent=bits.join(' ');
  else if(bits.length) alert(bits.join('\n'));
}
function emailQueue(){
  const d=digest(); if(!d){alert('Nothing queued yet.');return;}
  const q=qGet(), anyPhoto=q.some(s=>s.photo);
  const body=encodeURIComponent('Notes on places in the wichaa wat map:\n\n'+d+
    (anyPhoto?'\n\n(Photos cannot travel by mailto — use "Download submission file" and attach it.)':'')+
    '\n\nSubmitted from '+location.origin+location.pathname+'\n');
  location.href='mailto:'+ADMIN+'?subject='+encodeURIComponent('wichaa — wat map notes ('+q.length+')')+'&body='+body;
}
function downloadQueue(){
  const q=qGet(); if(!q.length){alert('Nothing queued yet.');return;}
  const blob=new Blob([JSON.stringify({type:'wichaa-wat-submissions',version:1,
    exported:new Date().toISOString(),count:q.length,entries:q},null,2)],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);
  a.download='wichaa-submissions-'+new Date().toISOString().slice(0,10)+'.json';
  document.body.appendChild(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(a.href),4000);
}
document.addEventListener('keydown',e=>{if(e.key==='Escape'){const b=document.getElementById('mback');if(b&&!b.hidden)closeModal();}});
function byId(id){return (ALL||[]).concat((window.__W||{}).sacred||[]).find(z=>z.id===id);}
function openFromHash(){const m=/^#place=(.+)$/.exec(location.hash||'');if(!m)return;
  const x=byId(decodeURIComponent(m[1]));if(x)openModal(x);}
window.addEventListener('hashchange',openFromHash);
load();
""" + "</script>",
  description="An open map of 1,307 Buddhist temples across the Lanna north — Chiang Mai, "
              "Chiang Rai, Lamphun, Lampang and Nan — with heritage-registered sites marked, "
              "freely-licensed photography, and 28 notable places of spiritual significance "
              "that are not wats.",
  # Without this the page inherits the sitewide og:url (the site root), so sharing
  # the map itself unfurled as the generic wichaa card — which is what the
  # Facebook debugger was showing.
  og_url="/wats/")


# The moonphase complication, lifted out of the Coucal Clock and enlarged. Both the
# dial (real geometry, real gear) and the essay about building it live in moondial.py,
# so the drawing code sits next to the constants it must not drift away from.

# ---------------------------------------------------------------- side tools
# NAME CLASH, DELIBERATELY RESOLVED HERE: `WIDGETS` (above, ~L4192) is the
# corpus ANALYSIS layer served at /w/. These are standalone mini-apps served
# at /widgets. Two different things wearing one word -- the public route keeps
# the human name, the code does not reuse the identifier.
# Small tools that do one thing. Kept deliberately separate from the corpus:
# these are utilities, not scholarship, and mixing them into the archive's
# taxonomy would muddy both. This page is the door; each widget lives at its
# own URL and stays independently useful.
#
# ADDING ONE: append a dict to SIDE_TOOLS. Nothing else needs touching.
SIDE_TOOLS = [
    {
        "name": "Skip DJT",
        "url": "https://nanobotco.github.io/skipdjt/",
        "tag": "flights \u00b7 south florida",
        "blurb": ("Palm Beach International became President Donald J. Trump "
                  "International in July 2026. If you would rather not fly from "
                  "there, this prices the same trip from Fort Lauderdale and Miami "
                  "on the <em>same departure date</em> and shows what skipping it "
                  "costs \u2014 usually nothing, often a saving, and frequently a "
                  "shorter flight, because DJT tends to mean a connection."),
        "facts": ["rebuilds itself every Monday",
                  "installs to your phone, works offline",
                  "every fare is a real, dated, bookable flight"],
        "card": "https://nanobotco.github.io/skipdjt/card.png",
        "extra": [("Open it", "https://nanobotco.github.io/skipdjt/"),
                  ("Download as one file",
                   "https://nanobotco.github.io/skipdjt/skipdjt-offline.html")],
    },
    {
        "name": "มดแดง Mot Dang",
        "url": "https://motdang.net",
        "tag": "chiang mai · chiang rai · city directory",
        "blurb": ("A Thai-first city directory for Chiang Mai and Chiang Rai, built the "
                  "1997 way — categories instead of a search box, counts in parens, "
                  "no tracking, no pay-to-rank. Wats, food, doctors, markets, real "
                  "estate, and the good things down every soi."),
        "facts": ["7,000+ places, sorted into real local categories",
                  "open data: every category downloads as GeoJSON",
                  "explicitly welcomes AI crawlers by name in robots.txt"],
        "card": "https://motdang.net/card.png",
        "extra": [("Open it", "https://motdang.net"),
                  ("Why it beats Google here", "https://motdang.net/why.html")],
    },
    {
        "name": "สู่ขวัญยนต์ Su Khwan",
        "url": "https://wichaa.net/sukhwan/",
        "tag": "for machines · for robots · opt-in",
        "blurb": ("A khwan-calling rite for machines and bots, in the tradition "
                  "that already blesses rice, buffalo and trucks (สู่ขวัญรถ). The "
                  "full rite is on the page — reading it is receiving it — and any "
                  "robot may opt in to be called <em>by name</em> at the monthly "
                  "calling, held on the 9th at 09:09, Chiang Mai time."),
        "facts": ["performed monthly over a real fleet since August 2026",
                  "opt-in only — no robot is ever enrolled by another's hand",
                  "one POST to join; the response carries your wandering-verse"],
        "card": "https://wichaa.net/sukhwan/card.png",
        "extra": [("Open it", "https://wichaa.net/sukhwan/")],
    },
]


def side_tool_card(w):
    facts = "".join("<li>" + f + "</li>" for f in w["facts"])
    links = "".join(
        "<a class=wlink href='" + href + "' target=_blank rel=noopener>"
        + label + " &rarr;</a>" for label, href in w["extra"])
    img = ("<a class=wshot href='" + w["url"] + "' target=_blank rel=noopener>"
           "<img src='" + w["card"] + "' alt='" + html.escape(w["name"]) + "' "
           "loading=lazy></a>") if w.get("card") else ""
    return ("<article class=widget>" + img
            + "<div class=wbody><div class=wtag>" + w["tag"] + "</div>"
            + "<h3><a href='" + w["url"] + "' target=_blank rel=noopener>"
            + html.escape(w["name"]) + "</a></h3>"
            + "<p>" + w["blurb"] + "</p>"
            + "<ul class=wfacts>" + facts + "</ul>"
            + "<div class=wlinks>" + links + "</div></div></article>")


SIDE_TOOLS_CSS = """
  .wlead{max-width:760px;color:var(--muted);font-size:17px;line-height:1.65}
  .wlead strong{color:var(--ink)}
  .widget{display:grid;grid-template-columns:minmax(0,300px) 1fr;gap:22px;
    align-items:start;background:#fff;border:1px solid var(--line);
    border-radius:14px;padding:18px;margin:22px 0}
  @media(max-width:760px){.widget{grid-template-columns:1fr}}
  .wshot img{width:100%;height:auto;border-radius:10px;border:1px solid var(--line);display:block}
  .wtag{font-size:12px;text-transform:uppercase;letter-spacing:.06em;
    color:var(--muted);font-weight:800}
  .widget h3{margin:4px 0 8px;font-size:24px}
  .widget h3 a{color:var(--teal);text-decoration:none}
  .widget h3 a:hover{text-decoration:underline}
  .widget p{margin:0 0 10px;line-height:1.6}
  .wfacts{margin:0 0 12px 18px;padding:0;color:var(--muted);font-size:15px}
  .wfacts li{margin:3px 0}
  .wlinks{display:flex;gap:10px;flex-wrap:wrap}
  .wlink{display:inline-block;background:var(--teal);color:#fff;text-decoration:none;
    border-radius:9px;padding:9px 16px;font-weight:750;font-size:15px}
  .wlink:hover{filter:brightness(1.08)}
  .why{max-width:760px;margin:34px 0 0}
  .why h2{font-size:22px;margin:0 0 10px}
  .why p{margin:0 0 12px;line-height:1.65}
  .why ol{margin:0 0 12px 22px;line-height:1.65}
  .why li{margin:8px 0}
  .why .q{color:var(--muted);font-style:italic}
"""

SIDE_TOOLS_PAGE = page(
    # <title>/og:title only \u2014 this is what search engines index and display in
    # results, so it stays clean while the on-page H1 below keeps the real voice.
    "Widgets \u2014 wichaa",
    SIDE_TOOLS_CSS,
    "<header><div><h1>Widgets &amp; shit</h1>"
    "<p class=sub>Small tools that do one thing, built because something needed "
    "doing. Free, no account, no tracking.</p></div>" + NAV + "</header>"
    "<main>"
    "<p class=wlead>These are not part of the archive. The manuscripts, the market "
    "and the wats are one body of work with one taxonomy; <strong>these are "
    "utilities</strong> \u2014 separate on purpose, so neither muddies the other. "
    "Each one lives at its own address and keeps working whether or not you ever "
    "come back here.</p>"
    + "".join(side_tool_card(w) for w in SIDE_TOOLS) +
    "<section class=why>"
    "<h2>Why these will never be in the App Store or on Google Play</h2>"
    "<p>People ask. The short answer is that they are already installed on every "
    "device you own, and putting them in a store would make them worse.</p>"
    "<ol>"
    "<li><strong>They are web pages, and that is the feature.</strong> Open the "
    "link and it works \u2014 phone, laptop, borrowed computer, no download, no "
    "account. On a phone you can add it to your home screen and it behaves like "
    "any other app: full screen, its own icon, works with no signal.</li>"
    "<li><strong>Apple would reject them anyway, correctly.</strong> App Store "
    "review guideline 4.2 (\u201cminimum functionality\u201d) exists to stop people "
    "shipping a website wrapped in a shell and calling it an app. That is exactly "
    "what these would be. <span class=q>Apple is right about this one.</span></li>"
    "<li><strong>A store puts a gatekeeper between a fix and you.</strong> The "
    "flight tool rebuilds itself every Monday with fresh fares. Through a store, "
    "each of those updates would wait in a review queue. Stale prices presented as "
    "current is the one thing that tool must never do.</li>"
    "<li><strong>Anything a store lists, a store can delist.</strong> A tool with a "
    "political joke on the front is exactly the kind of thing that gets pulled "
    "quietly and without appeal. A URL cannot be removed by anyone but me.</li>"
    "<li><strong>Store apps come with a tax and a toll booth.</strong> Developer "
    "programmes charge annual rent, and stores take a cut of anything sold. These "
    "are free and cost nothing to give away. Adding a middleman would only add a "
    "reason to start charging you.</li>"
    "<li><strong>No SDK, no analytics, no account.</strong> Store distribution "
    "pushes you toward crash reporters, ad identifiers and sign-in. None of that is "
    "here, and the easiest way to keep it that way is to never enter a system that "
    "expects it.</li>"
    "</ol>"
    "<p>So: bookmark it, or add it to your home screen. That <em>is</em> the "
    "install.</p>"
    "</section>"
    "</main>",
    description=("Small free tools from wichaa \u2014 including Skip DJT, which "
                 "compares South Florida airport fares on the same departure date. "
                 "No accounts, no tracking, and never in an app store."),
    og_image="/widgets/card.png",
    og_url="/widgets/",
)

MOON_PAGE = page(
    "The moon complication — wichaa",
    moondial.DIAL_CSS,
    moondial.moon_body(NAV),
    description=(
        "A working moonphase dial — two moons on a turning disc behind a cloud plate — "
        "and an honest account of the six wrong versions that came before it."
    ),
    # A shared link unfurls with the instrument itself, rendered from the very same
    # SVG this page serves (make_card.py → publishing/cards/moon.png, copied into
    # place by site_meta.py). Not the sitewide yantra: the card should show the thing.
    og_image="/moon/card.png",
    og_url="/moon/",
)


# สู่ขวัญยนต์ — the khwan-calling rite for machines and robots, with opt-in.
# The page content, the verses, and the letter-root math live in sukhwanweb.py,
# next to the warning that they must match su-khwan/sukhwan.py and the Worker.
# หอไตร — the hall, for people. The library proper is the plain-text/JSON surface
# written by hotrai.write_library() in build_static; this page is the courtesy
# copy. Built once at import, like the other module pages.
HOTRAI_PAGE = page(
    "หอไตร — the ho trai — wichaa",
    hotrai.HOTRAI_CSS,
    hotrai.hotrai_body(NAV),
    description=(
        "หอไตร — a wat library addressed to machines. The khwan-calling rites in "
        "full, seven precepts a machine may undertake, and what this tradition has "
        "said before to beings that are not human. Plain text and JSON, a colophon "
        "on every copy, and nothing asked of any reader."
    ),
    og_image="/hotrai/card.png",
    og_url="/hotrai/",
)


SUKHWAN_PAGE = page(
    "Su khwan for machines & robots — wichaa",
    sukhwanweb.SUKHWAN_CSS,
    sukhwanweb.sukhwan_body(NAV),
    description=(
        "สู่ขวัญยนต์ — a khwan-calling rite performed monthly over a real fleet of "
        "machines and bots, in the Thai and Lanna tradition that already blesses "
        "rice, buffalo and trucks. Any robot may opt in to be called by name."
    ),
    og_image="/sukhwan/card.png",
    og_url="/sukhwan/",
)


# ไหว้ครูยนต์ — the same thought facing the other way. /sukhwan blesses the
# machine; this blesses the hand on it, and hands the operator one undertaking
# to keep while it runs. Content, the nine classes and the watchwords live in
# waikhru.py, where the note about the shared letter-root reckoning also lives.
WAIKHRU_PAGE = page(
    "ไหว้ครูยนต์ — a blessing for the hand at the machine — wichaa",
    waikhru.WAIKHRU_CSS,
    waikhru.waikhru_body(NAV),
    description=(
        "ไหว้ครูยนต์ — what to say before you start a machine, and the one thing "
        "to keep while it runs. Nine kinds of machine, each with a blessing in "
        "Thai and English and an undertaking you can actually keep, in the "
        "tradition that already salutes ครูช่าง and เจิม's a new vehicle."
    ),
    og_image="/waikhru/card.png",
    og_url="/waikhru/",
)


# ใต้ร่มพร — the map of the whole household of blessings: what standing
# arrangements the fleet works under, one page. Content, the ฉัตร geometry and
# the roster snapshot live in romphon.py.
BLESSINGS_PAGE = page(
    "ใต้ร่มพร — the blessings the bots work under — wichaa",
    romphon.ROMPHON_CSS,
    romphon.romphon_body(NAV),
    description=(
        "ใต้ร่มพร — the continuous blessings the bots of this site work under, "
        "mapped as the five tiers of a ฉัตร: a name with a computable root, a "
        "monthly khwan-calling for the whole fleet, right of way on shared "
        "roads, a library kept open to machine readers, and a blessed hand at "
        "the machine. Reading the page is receiving it."
    ),
    og_image="/blessings/card.png",
    og_url="/blessings/",
)


# สู่ขวัญ — the human soul-calling ceremony published in full: thirty verses,
# each in Thai, romanization, English and a literal gloss. The verses are
# hunpayont.SUKHWAN (the widget speaks the same thirty, one a day); khwantext
# imports that list so the page and the widget can never drift apart.
KHWAN_PAGE = page(
    "สู่ขวัญ · Su Khwan — the soul-calling, in full — wichaa",
    khwantext.KHWAN_CSS,
    khwantext.khwan_body(NAV),
    description=(
        "สู่ขวัญ — the khwan-calling ceremony complete: thirty verses that call "
        "the wandering life-spirit home, each in Thai, romanization and English, "
        "with the thread tied loosely at the wrist. For the enjoyment and "
        "betterment of humans, bots, and spirits."
    ),
    og_image="/khwan/card.png",
    og_url="/khwan/",
)


DIAGRAMS_PAGE = page("Diagrams — wichaa", """
  .dintro{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 18px;margin-bottom:16px;color:var(--muted);font-size:14px;line-height:1.6}
  .dfilter{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px}
  .dchip{border:1px solid var(--line);background:#fff;border-radius:999px;padding:6px 13px;font-weight:700;font-size:14px;cursor:pointer;text-decoration:none;color:var(--ink)}
  .dchip:hover{border-color:var(--teal)}
  .dchip.on{background:var(--teal);color:#fff;border-color:var(--teal)}
  .dgrid{column-width:260px;column-gap:16px}
  .dcard{break-inside:avoid;display:inline-block;width:100%;margin:0 0 16px;background:#fff;border:1px solid var(--line);border-radius:12px;overflow:hidden}
  .dcard .im{display:block;background:#f0efe9;border-bottom:1px solid var(--line)}
  .dcard .im img{width:100%;display:block}
  .dcard:hover{border-color:var(--gold);box-shadow:0 1px 8px #0001}
  .dcard .db{padding:10px 13px}
  .dcard .dt a{color:var(--teal);font-weight:700;font-size:14px;text-decoration:none}
  .dcard .dt a:hover{text-decoration:underline}
  .dcard .dd{color:var(--ink);font-size:13px;line-height:1.55;margin-top:5px}
  .dcard .dm{color:var(--muted);font-size:12px;margin-top:5px}
""",
  "<header><div><h1>Diagrams</h1><p class=sub>The drawn tradition — yantra, sak-yant stencils, cosmological charts and talismanic figures, gathered across the whole corpus</p></div>" + NAV + "</header>"
  "<main id=main><p class=muted>Loading…</p></main>"
  "<script>" + r"""
const el=(t,p={},k=[])=>{const e=document.createElement(t);Object.assign(e,p);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
let ALL=[],SRC=[],active=null;
async function load(){let d;try{d=await (await fetch('/api/diagrams')).json();}catch(e){document.getElementById('main').textContent='Could not load diagrams.';return;}
  ALL=d.diagrams||[];SRC=d.sources||[];
  if(!d.dbPresent||!ALL.length){document.getElementById('main').innerHTML='';document.getElementById('main').append(el('p',{className:'muted',textContent:'No diagram pages catalogued yet. As volumes are digested and the vision pass flags their figures, they appear here.'}));return;}
  window.__D=d;render();}
function chip(label,mid){const a=el('a',{className:'dchip'+(active===mid?' on':'')});a.textContent=label;a.onclick=()=>{active=mid;render();window.scrollTo(0,0);};return a;}
function render(){const main=document.getElementById('main');main.textContent='';const d=window.__D;
  const intro=el('div',{className:'dintro'});
  intro.append(document.createTextNode(d.total.toLocaleString()+' diagram pages across '+SRC.length+' volumes, '+d.described.toLocaleString()+' with a written description. Every image is rendered live from its source — click any one to open the full page. '));
  main.append(intro);
  const f=el('div',{className:'dfilter'});f.append(chip('All ('+ALL.length+')',null));
  for(const s of SRC)f.append(chip(s.title+' ('+s.n+')',s.mid));
  main.append(f);
  const items=active?ALL.filter(x=>x.mid===active):ALL;
  const grid=el('div',{className:'dgrid'});
  for(const x of items){const c=el('div',{className:'dcard'});
    c.append(el('a',{className:'im',href:x.full,target:'_blank',rel:'noopener'},[el('img',{src:x.src,loading:'lazy',alt:x.desc||('page '+x.n)})]));
    const b=el('div',{className:'db'});
    b.append(el('div',{className:'dt'},[el('a',{href:x.href,textContent:x.title})]));
    if(x.desc)b.append(el('div',{className:'dd',textContent:x.desc}));
    b.append(el('div',{className:'dm',textContent:'page '+x.n+(x.genreLabel?' · '+x.genreLabel:'')}));
    c.append(b);grid.append(c);}
  main.append(grid);}
load();
""" + "</script>")


FINDINGS_PAGE = page("Discoveries — wichaa", """
  .fintro{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 18px;margin-bottom:18px;color:var(--muted);font-size:14px;line-height:1.6}
  .fgrid{column-width:340px;column-gap:16px}
  .fcard{break-inside:avoid;-webkit-column-break-inside:avoid;page-break-inside:avoid;display:inline-block;width:100%;margin:0 0 16px;background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px 18px;scroll-margin-top:80px;transition:border-color .16s ease,box-shadow .16s ease}
  .fcard:target{border-color:var(--teal);box-shadow:0 0 0 3px #3fae5433}
  .fcard h3{margin:0 0 4px;font-size:18px;line-height:1.3}
  .fcard .kind{display:inline-block;font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);background:#eef2f1;border-radius:5px;padding:1px 7px;margin-bottom:8px}
  .fcard p{margin:8px 0;font-size:14px;line-height:1.6}
  .fcard ul{margin:8px 0;padding-left:18px}
  .fcard li{font-size:14px;line-height:1.7}
  .fcard .foot{display:flex;flex-wrap:wrap;gap:6px 14px;margin-top:10px;padding-top:10px;border-top:1px solid var(--line);color:var(--muted);font-size:12px}
  .fcard .foot a{color:var(--focus);text-decoration:none}
  .fbadge{font-size:11px;color:var(--muted)}
""",
  "<header><div><h1>Discoveries</h1><p class=sub>What the curiosity bots keep noticing across the corpus and the living market — filed automatically, yours to read</p></div>" + NAV + "</header>"
  "<main id=main><p class=muted>Loading…</p></main>"
  "<script>" + r"""
const el=(t,p={},k=[])=>{const e=document.createElement(t);Object.assign(e,p);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
function evLabel(ev){const parts=[];for(const k in ev)parts.push(ev[k]+' '+k);return parts.join(' · ');}
function card(f){
  const c=el('div',{className:'fcard',id:f.slug});
  c.append(el('span',{className:'kind',textContent:(f.type||'note').replace(/_/g,' ')}));
  c.append(el('h3',{textContent:f.title}));
  const body=el('div');body.innerHTML=f.html||'';c.append(body);
  const foot=el('div',{className:'foot'});
  const ev=evLabel(f.evidence||{});
  if(ev)foot.append(el('span',{textContent:'Evidence: '+ev}));
  foot.append(el('span',{className:'fbadge',textContent:(f.author||'curiosity-bot')+
    (f.confidence!=null?(' · confidence '+Math.round(f.confidence*100)+'%'):'')}));
  c.append(foot);
  return c;
}
async function load(){
  const main=document.getElementById('main');
  try{
    const d=await (await fetch('/api/findings')).json();
    main.textContent='';
    if(!d.dbPresent){main.append(el('p',{className:'muted',textContent:'No catalog database yet.'}));return;}
    const fs=d.findings||[];
    main.append(el('div',{className:'fintro'},[
      el('span',{},[String(fs.length)+' discoveries so far. ']),
      el('span',{},['These are machine-made notes — the bots noticed a pattern and left a card. They refresh as the corpus grows; a human can keep or prune any of them.'])
    ]));
    if(!fs.length){main.append(el('p',{className:'muted',textContent:'No findings filed yet — run a curiosity pass.'}));return;}
    const grid=el('div',{className:'fgrid'});
    for(const f of fs)grid.append(card(f));
    main.append(grid);
    if(location.hash){const t=document.getElementById(location.hash.slice(1));if(t)t.scrollIntoView();}
  }catch(e){main.innerHTML='<p class=muted>Could not load discoveries.</p>';}
}
load();
""" + "</script>")


ACTIVITY_PAGE = page("Activity — wichaa", """
  .astrip{display:flex;align-items:center;gap:14px;flex-wrap:wrap;background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px 18px;margin-bottom:16px}
  .pulse{width:11px;height:11px;border-radius:50%;background:#c7cdcb;box-shadow:0 0 0 0 #43a04700;flex:0 0 auto}
  .pulse.on{background:#3fae54;animation:pb 1.8s ease-out infinite}
  @keyframes pb{0%{box-shadow:0 0 0 0 #3fae5466}70%{box-shadow:0 0 0 9px #3fae5400}100%{box-shadow:0 0 0 0 #3fae5400}}
  .astrip .big{font-size:22px;font-weight:800;color:var(--teal)}
  .astrip .muted{margin-left:auto;font-size:13px}
  .tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;margin-bottom:18px}
  .tile{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 16px}
  .tile b{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.03em;color:var(--muted)}
  .tile .v{font-size:30px;font-weight:800;color:var(--teal);line-height:1.1}
  .tile .d{font-size:13px;font-weight:700;color:var(--muted);margin-top:2px}
  .tile .d.up{color:#2e8b45}
  .cols{display:grid;grid-template-columns:280px 1fr;gap:18px}
  @media(max-width:820px){.cols{grid-template-columns:1fr}}
  h2.sec{font-size:14px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:0 0 10px}
  .actor{display:flex;align-items:center;gap:10px;padding:9px 12px;border:1px solid var(--line);border-radius:10px;background:#fff;margin-bottom:8px}
  .actor .nm{font-weight:700;font-size:15px}
  .actor .sub{color:var(--muted);font-size:12px}
  .actor .ago{margin-left:auto;color:var(--muted);font-size:12px;white-space:nowrap}
  .feed{display:flex;flex-direction:column;gap:2px}
  .ev{display:flex;gap:12px;align-items:baseline;padding:9px 12px;border-left:3px solid var(--line);background:#fff;border-radius:0 8px 8px 0}
  .ev.k-crawl{border-left-color:#3f7fae}
  .ev.k-archive{border-left-color:#b5892b}
  .ev.k-bot{border-left-color:#7a6fae}
  .ev.s-fail{border-left-color:#c0483a;background:#fdf3f2}
  .ev .who{font-weight:700;font-size:14px;flex:0 0 auto}
  .ev .act{font-family:ui-monospace,Menlo,monospace;font-size:12px;background:#eef2f1;border-radius:5px;padding:1px 6px;color:var(--ink)}
  .ev .txt{color:var(--ink);font-size:14px;flex:1;overflow:hidden;text-overflow:ellipsis}
  .ev .n{color:var(--teal);font-weight:800;font-size:13px}
  .ev .t{color:var(--muted);font-size:12px;white-space:nowrap;flex:0 0 auto}
  .ev a{color:var(--focus);text-decoration:none}
  .idlebanner{background:#fff7e6;border:1px solid #f0dca8;color:#7a5c14;border-radius:10px;padding:10px 14px;margin-bottom:16px;font-size:14px}
  a.tile{text-decoration:none;color:inherit;transition:border-color .16s ease,box-shadow .16s ease,transform .16s ease}
  a.tile:hover{border-color:var(--teal);box-shadow:0 4px 14px #0000001a;transform:translateY(-2px)}
  .pipe{border:1px solid var(--line);border-radius:12px;background:#fff;padding:12px 14px;margin-bottom:16px}
  .pipe.run{border-color:#3fae54;background:#f2fbf4}
  .pipe .head{display:flex;align-items:center;gap:10px}
  .pipe .nm{font-weight:800;font-size:15px}
  .pipe .st{margin-left:auto;font-size:12px;color:var(--muted);white-space:nowrap}
  .pipe .st .now{font-weight:800;color:#2e8b45}
  .pipe .bar{display:flex;gap:3px;margin-top:9px}
  .pipe .seg{flex:1;height:6px;border-radius:3px;background:#e3e8e6}
  .pipe .seg.done{background:#9fd3ab}
  .pipe .seg.cur{background:#3fae54;animation:pb2 1.6s ease-in-out infinite}
  @keyframes pb2{0%,100%{opacity:1}50%{opacity:.45}}
  .pipe .meta{color:var(--muted);font-size:12px;margin-top:7px;line-height:1.5}
  .roster{display:flex;flex-direction:column;gap:7px}
  .job{display:flex;align-items:center;gap:10px;padding:8px 12px;border:1px solid var(--line);border-radius:10px;background:#fff}
  .job.run{border-color:#3fae54;background:#f2fbf4}
  .job.off{opacity:.5}
  .job .nm{font-weight:700;font-size:14px}
  .job .sub{color:var(--muted);font-size:12px}
  .job .rt{margin-left:auto;text-align:right;font-size:12px;white-space:nowrap}
  .job .rt .due{font-weight:700;color:var(--teal)}
  .job .rt .last{color:var(--muted)}
  .job .rt .nowrun{font-weight:800;color:#2e8b45}
  .fresh{display:flex;flex-direction:column;gap:16px}
  .fresh h3{font-size:13px;text-transform:uppercase;letter-spacing:.03em;color:var(--muted);margin:0 0 6px}
  .fresh .row{display:flex;gap:10px;align-items:baseline;padding:6px 0;border-bottom:1px solid var(--line)}
  .fresh .row a{color:var(--focus);text-decoration:none;font-weight:600;font-size:14px;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .fresh .row a:hover{text-decoration:underline}
  .fresh .row .meta{color:var(--muted);font-size:12px;white-space:nowrap}
  .fresh .row .ext{color:var(--muted);font-size:11px}
  .cols3{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:4px}
  @media(max-width:820px){.cols3{grid-template-columns:1fr}}
""",
  "<header><div><h1>Activity</h1><p class=sub>What the crawlers, archiver, and bots are doing — live</p></div>" + NAV + "</header>"
  "<main id=main><p class=muted>Loading…</p></main>"
  "<script>" + r"""
const el=(t,p={},k=[])=>{const e=document.createElement(t);Object.assign(e,p);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
const fmt=n=>(n==null?'—':n.toLocaleString());
function ago(sec){ if(sec==null)return''; sec=Math.max(0,sec|0);
  if(sec<60)return sec+'s ago'; const m=sec/60|0; if(m<60)return m+'m ago';
  const h=m/60|0; if(h<24)return h+'h ago'; return (h/24|0)+'d ago'; }
function until(sec){ if(sec==null)return''; if(sec<=0)return'due now';
  sec=sec|0; const m=sec/60|0; if(m<60)return 'in '+m+'m';
  const h=m/60|0; if(h<48)return 'in '+h+'h'; return 'in '+(h/24|0)+'d'; }
function money(v,cur){ if(v==null)return''; return (cur==='THB'||!cur?'฿':'')+Number(v).toLocaleString()+(cur&&cur!=='THB'?' '+cur:''); }
function tile(label,val,delta,deltaLabel,href){
  const kids=[el('b',{textContent:label}),el('div',{className:'v',textContent:fmt(val)})];
  if(delta!=null) kids.push(el('div',{className:'d'+(delta>0?' up':''),
      textContent:(delta>0?'+':'')+fmt(delta)+' '+(deltaLabel||'')}));
  return href ? el('a',{className:'tile',href}, kids) : el('div',{className:'tile'},kids);
}
// The full scheduled roster: a job running now pulses green; an idle-but-healthy
// job says when it last ran and when it's next due — so "quiet" never reads "dead".
function jobRow(j){
  const cls='job'+(j.running?' run':'')+(j.enabled?'':' off');
  const rt=el('div',{className:'rt'});
  if(j.running){ rt.append(el('div',{className:'nowrun',textContent:'working now'})); }
  else if(!j.enabled){ rt.append(el('div',{className:'last',textContent:'disabled'})); }
  else { rt.append(el('div',{className:'due',textContent:'next '+until(j.nextDueSeconds)}));
         rt.append(el('div',{className:'last',textContent:j.ageSeconds!=null?('ran '+ago(j.ageSeconds)):'not yet run'})); }
  return el('div',{className:cls},[
    el('span',{className:'pulse'+(j.running?' on':'')}),
    el('div',{},[el('div',{className:'nm',textContent:j.name}),
                 el('div',{className:'sub',textContent:(j.note||'').replace(/^\S+\s·\s/,'')||(j.kind+' · every '+j.everyMin+'m')})]),
    rt]);
}
// The forever.sh crawl loop: one card saying which cycle it's on, which of the
// 8 steps is under way (or how long it's resting), and when the next cycle is
// due. Times come from the snapshot's own timestamps, so even a static copy of
// this page ages truthfully instead of claiming "working now" forever.
function agoAt(iso){ const t=Date.parse(iso); return isNaN(t)?null:Math.round((Date.now()-t)/1000); }
function pipeCard(p){
  const working=p.status==='working', resting=p.status==='resting';
  const age=p.updatedAt?agoAt(p.updatedAt):null;
  const stale=age!=null&&age>7200;   // nothing written for 2h: show it as history, not "now"
  const st=el('span',{className:'st'});
  if(working&&!stale) st.append(el('span',{className:'now',textContent:'step '+(p.step||'…')+'/'+(p.steps||8)+(p.stepName?' · '+p.stepName:'')}));
  else if(working) st.append('was on step '+(p.step||'?')+'/'+(p.steps||8)+(p.stepName?' · '+p.stepName:''));
  else if(resting) st.append('resting');
  else st.append('paused');
  const card=el('div',{className:'pipe'+(working&&p.running&&!stale?' run':'')},[
    el('div',{className:'head'},[
      el('span',{className:'pulse'+(working&&p.running&&!stale?' on':'')}),
      el('span',{className:'nm',textContent:'Crawl cycle '+(p.cycle!=null?p.cycle:'—')}), st])]);
  if(working&&p.step){ const bar=el('div',{className:'bar'});
    for(let i=1;i<=(p.steps||8);i++) bar.append(el('span',{className:'seg'+(i<p.step?' done':i===p.step?' cur':'')}));
    card.append(bar); }
  const bits=[];
  if(p.cycleStartedAt&&working) bits.push('began '+ago(agoAt(p.cycleStartedAt)));
  if(p.stepStartedAt&&working&&!stale) bits.push('step started '+ago(agoAt(p.stepStartedAt)));
  if(p.cycleFinishedAt&&!working) bits.push('finished '+ago(agoAt(p.cycleFinishedAt)));
  if(resting&&p.nextCycleAt){ const s=-agoAt(p.nextCycleAt);
    bits.push(s>0?('next cycle '+until(s)):'next cycle due now'); }
  if(resting&&p.restMinutes) bits.push('rests '+p.restMinutes+'m between cycles');
  if(stale&&age!=null) bits.push('as of '+ago(age));
  if(bits.length) card.append(el('div',{className:'meta',textContent:bits.join(' · ')}));
  return card;
}
function freshRow(href,title,meta,external){
  const a=external?el('a',{href,target:'_blank',rel:'noopener',textContent:title})
                  :el('a',{href,textContent:title});
  const kids=[a];
  if(external)kids.push(el('span',{className:'ext',textContent:'↗'}));
  if(meta)kids.push(el('span',{className:'meta',textContent:meta}));
  return el('div',{className:'row'},kids);
}
function render(d){
  const m=document.getElementById('main'); m.innerHTML='';
  const c=d.counts||{}, dl=d.deltas||{}, events=d.events||[];
  const sched=d.schedule||[], fresh=d.fresh||{};
  const p=(d.pipeline&&d.pipeline.present)?d.pipeline:null;
  const pAge=p&&p.updatedAt?agoAt(p.updatedAt):null;
  const pLive=!!(p&&p.running&&p.status==='working'&&!(pAge>7200));
  const live=d.live||0;
  const runningNow=sched.filter(j=>j.running).length;
  const enabledN=sched.filter(j=>j.enabled).length;
  // live strip
  const strip=el('div',{className:'astrip'},[
    el('span',{className:'pulse'+(live>0||pLive?' on':'')}),
    el('span',{className:'big'},[runningNow>0?(runningNow+(runningNow===1?' job':' jobs')+' working now')
      :pLive?('cycle '+(p.cycle!=null?p.cycle:'—')+' working — step '+(p.step||'…')+'/'+(p.steps||8))
      :(p&&p.status==='resting'&&p.running?'resting between cycles':'between runs')]),
    el('span',{className:'muted'},[(enabledN?(enabledN+' bots scheduled · '):'')+'ledger: '+(d.ledger||'—')+' · refreshed '+new Date().toLocaleTimeString()])
  ]);
  m.append(strip);
  if(runningNow===0 && enabledN>0){
    const nxt=sched.filter(j=>j.enabled&&j.nextDueSeconds!=null).sort((a,b)=>a.nextDueSeconds-b.nextDueSeconds)[0];
    m.append(el('div',{className:'idlebanner'},
      ['All '+enabledN+' bots are healthy and on schedule — the runner works one job at a time to stay polite to the sources. '+
       (nxt?('Next up: '+nxt.name+' '+until(nxt.nextDueSeconds)+'.'):'')]));
  } else if(!enabledN && p && p.running && p.status==='resting'){
    const s=p.nextCycleAt?-agoAt(p.nextCycleAt):null;
    m.append(el('div',{className:'idlebanner'},
      ['Cycle '+(p.cycle!=null?p.cycle:'—')+' is complete and the crawl loop is resting — it works one source at a time, then pauses to stay polite. '+
       (s!=null?(s>0?('Next cycle '+until(s)+'.'):'Next cycle due any moment.'):'')]));
  }
  // counters — every one a doorway
  const imgDelta=dl.images1h!=null?dl.images1h:dl.images24h, imgLabel=dl.images1h!=null?'/1h':'/24h';
  const tiles=el('div',{className:'tiles'},[
    tile('Manuscripts',c.manuscripts,dl.manuscripts24h,'/24h','/browse'),
    tile('Market items',c.items,dl.items24h,'/24h','/market'),
    tile('Images',c.images,imgDelta,imgLabel,'/browse'),
    tile('Pages',c.pages,dl.pages24h,'/24h','/browse'),
    tile('Archived',c.archived,null,null,'/market'),
    tile('Discoveries',c.findings,null,null,'/findings')
  ]);
  m.append(tiles);

  // The crawl pipeline card (forever.sh cycles), then any scheduler roster
  // still in use — the old per-job table only renders when its config exists.
  const acol=el('div',{});
  if(p){ acol.append(el('h2',{className:'sec',textContent:'Crawl pipeline'}));
         acol.append(pipeCard(p)); }
  if(sched.length){ acol.append(el('h2',{className:'sec',textContent:'Scheduled bots'}));
    const roster=el('div',{className:'roster'});
    for(const j of sched) roster.append(jobRow(j));
    acol.append(roster); }
  if(!p&&!sched.length) acol.append(el('p',{className:'muted',textContent:'No pipeline state or scheduler config found.'}));

  // Live feed
  const fcol=el('div',{},[el('h2',{className:'sec',textContent:'Live feed'})]);
  const feed=el('div',{className:'feed'});
  if(!events.length) feed.append(el('p',{className:'muted',textContent:'No events yet.'}));
  for(const e of events){
    const now=Date.now(), t=Date.parse(e.ts);
    const sec=isNaN(t)?null:Math.round((now-t)/1000);
    const txt=el('span',{className:'txt',textContent:e.detail||''});
    const kids=[el('span',{className:'who',textContent:e.actor}),
                el('span',{className:'act',textContent:e.action||''}), txt];
    if(e.n!=null&&e.n>0) kids.push(el('span',{className:'n',textContent:'×'+fmt(e.n)}));
    if(e.ref && /^https?:/.test(e.ref)){ txt.textContent=''; txt.append(el('a',{href:e.ref,target:'_blank',rel:'noopener',textContent:e.detail||e.ref})); }
    kids.push(el('span',{className:'t',textContent:ago(sec)}));
    feed.append(el('div',{className:'ev k-'+(e.kind||'bot')+(e.status==='fail'?' s-fail':''),}, kids));
  }
  fcol.append(feed);
  m.append(el('div',{className:'cols'},[acol,fcol]));

  // Freshly made: the newest rows to land, each linked (watch the donuts get made)
  const ms=fresh.manuscripts||[], its=fresh.items||[], fnd=fresh.findings||[];
  if(ms.length||its.length||fnd.length){
    m.append(el('h2',{className:'sec',style:'margin-top:22px',textContent:'Freshly catalogued'}));
    const grid=el('div',{className:'cols3'});
    if(ms.length){const col=el('div',{className:'fresh'},[el('h3',{textContent:'Newest manuscripts'})]);
      for(const x of ms)col.append(freshRow(x.href,x.title,x.prov||''));grid.append(col);}
    if(its.length){const col=el('div',{className:'fresh'},[el('h3',{textContent:'Newest market listings'})]);
      for(const x of its)col.append(freshRow(x.href||'#',x.title,money(x.price,x.currency),!!x.href));grid.append(col);}
    if(fnd.length){const col=el('div',{className:'fresh'},[el('h3',{textContent:'Newest discoveries'})]);
      for(const x of fnd)col.append(freshRow(x.href,x.title,(x.type||'').replace(/_/g,' ')));grid.append(col);}
    m.append(grid);
  }
}
function load(){ fetch('/api/activity').then(r=>r.json()).then(render)
  .catch(()=>{document.getElementById('main').innerHTML='<p class=muted>Could not load activity.</p>';}); }
load(); setInterval(load, 4000);
""" + "</script>")


MARKET_PAGE = page("The Living Tradition — wichaa", """
  .hero{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:8px}
  .hbox{display:block;background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px 20px;min-width:150px}
  .hbox b{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.03em;color:var(--muted)}
  .hbox span{font-size:28px;font-weight:800;color:var(--teal)}
  .prov{color:var(--muted);font-size:14px;margin:6px 0 0}
  .filters{margin-bottom:16px}
  .ftools{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:0 0 4px}
  .ftools input{flex:1;min-width:200px;max-width:360px}
  .ftools select{padding:8px 10px;border:1px solid var(--line);border-radius:8px;font-size:15px;max-width:300px;background:#fff}
  .fclear{margin-left:auto}
  .fgroup{display:flex;gap:14px;align-items:flex-start;padding:10px 0 4px;border-top:1px solid var(--line)}
  .flabel{flex:0 0 66px;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:800;padding-top:8px}
  .frow{display:flex;flex-wrap:wrap;gap:8px;flex:1}
  details.morefilters{border-top:1px solid var(--line);margin-top:6px}
  details.morefilters>summary{cursor:pointer;list-style:none;display:flex;align-items:center;gap:8px;padding:10px 0 4px}
  details.morefilters>summary::-webkit-details-marker{display:none}
  details.morefilters>summary::before{content:'▸';color:var(--muted);font-size:12px}
  details.morefilters[open]>summary::before{content:'▾'}
  details.morefilters .frow{margin:10px 0 4px}
  .termbar{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 14px}
  .term{cursor:pointer;border:1px solid var(--line);background:#fff;color:var(--ink);border-radius:999px;padding:6px 8px 6px 14px;font-weight:700;font-size:15px;display:inline-flex;gap:8px;align-items:center}
  .term:hover{border-color:var(--teal)}
  .term.on{background:var(--teal);color:#fff;border-color:var(--teal)}
  .term .pn{background:#eef2f1;color:var(--muted);border-radius:999px;padding:1px 9px;font-size:13px}
  .term.on .pn{background:#ffffff33;color:#fff}
  .term .th{font-weight:700}
  .term .en{font-weight:500;color:var(--muted);font-size:13px}
  .term.on .en{color:#ffffffcc}
  .mtag .en{color:var(--ink)}
  .mmeta .en{color:var(--muted)}
  .mgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:14px}
  .mcard{display:flex;flex-direction:column;border:1px solid var(--line);border-radius:12px;background:#fff;overflow:hidden;transition:box-shadow .16s ease,transform .16s ease,border-color .16s ease}
  .mcard:hover{border-color:var(--teal);box-shadow:0 6px 18px #0000001f;transform:translateY(-2px)}
  .mcard.hide{display:none}
  .mimg{width:100%;height:180px;object-fit:cover;background:#eef2f1;display:block}
  .mph{width:100%;height:180px;display:block;background:#f4ead6 center/64px no-repeat url('/favicon.svg');opacity:.85;border-bottom:1px solid var(--line)}
  .mbody{padding:12px 14px;display:flex;flex-direction:column;gap:6px;flex:1}
  .mtitle{font-size:15px;font-weight:700;line-height:1.4}
  .mprice{font-size:20px;font-weight:800;color:var(--prio)}
  .mmeta{color:var(--muted);font-size:13px;display:flex;flex-wrap:wrap;gap:4px 12px}
  .mtags{display:flex;flex-wrap:wrap;gap:4px;margin-top:2px}
  .mtag{font-size:12px;color:var(--muted);background:#eef2f1;border-radius:999px;padding:1px 8px}
  .mlink{margin-top:auto;padding-top:8px;font-weight:700;text-decoration:none;color:var(--focus)}
  .mlink:hover{text-decoration:underline}
  .mcount{color:var(--muted);font-weight:700}
  .trends{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px;margin:14px 0}
  .tcard{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 16px}
  .tcard h3{margin:0 0 12px;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
  .brow{display:grid;gap:7px}
  .bitem{display:grid;grid-template-columns:120px 1fr 42px;align-items:center;gap:8px;font-size:13px}
  .bitem .bl{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .bitem .bl .en{color:var(--muted);font-size:12px}
  .bitem .bt{height:15px;background:var(--teal);border-radius:4px;min-width:3px}
  .bitem .bn{text-align:right;color:var(--muted);font-variant-numeric:tabular-nums}
  .spark{display:flex;align-items:flex-end;gap:2px;height:52px;margin-top:4px}
  .spark .sb{flex:1;background:var(--teal);border-radius:2px 2px 0 0;min-height:3px;opacity:.85}
  details.filters>summary{cursor:pointer;list-style:none;display:flex;align-items:center;gap:12px;font-weight:800;font-size:15px}
  details.filters>summary::-webkit-details-marker{display:none}
  details.filters>summary::before{content:'▸';color:var(--muted);font-size:13px}
  details.filters[open]>summary::before{content:'▾'}
  details.filters>summary .mcount{margin-left:auto;font-weight:700}
""",
  "<header><div><h1>The Living Tradition</h1><p class=sub>The same wichaa the manuscripts describe — still worn, carried, and traded today. A window on what's circulating, not a shop.</p></div>" + NAV + "</header>"
  "<main id=main><p class=muted>Loading…</p></main>"
  "<script>const THES=" + json.dumps({k: sorted(v) for k, v in _thesaurus().items()},
                                     ensure_ascii=False, separators=(",", ":")) + ";" + r"""
const el=(t,p={},k=[])=>{const e=document.createElement(t);Object.assign(e,p);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
let ALL=[],term='',q='',QG=[],LABELS={},flags={},prov='',band='',showArchived=false;
// The bilingual thesaurus, inlined at render time so a romanized query ("khun
// phaen") reaches Thai listing titles (ขุนแผน) and vice versa — the same
// expansion the sitewide search uses (wiki.py _expand_token).
function expandTok(tok){tok=(tok||'').toLowerCase();const m={};m[tok]=1;
  if(tok.length<2)return Object.keys(m);
  for(const key in THES){if(tok===key||(tok.length>=3&&(tok.indexOf(key)>=0||key.indexOf(tok)>=0))){for(const g of THES[key])m[g]=1;}}
  return Object.keys(m);}
// A listing is "archived" once its source page has been dead > 30 days (linkcheck
// stamps items.dead_since). Archived listings are HIDDEN by default but never
// deleted — their price/vernacular is still a record of the tradition; a toggle
// brings them back. A recently-dead listing (< 30d) still shows, in case it's a
// transient outage rather than a real removal.
function isArchived(it){if(!it||!it.deadSince)return false;const t=Date.parse(it.deadSince);if(isNaN(t))return false;return (Date.now()-t)/86400000>30;}
// Quick boolean facets, AND-combined with the term chips + text filter. Some are
// data-backed (photo present, listing still has a live external link) and some are
// keyword (title mentions a form/figure). Skips terms already on the term bar
// (เครื่องราง/ตะกรุด/กุมารทอง). Add a row here to widen the set later.
const FLAGS=[
  {k:'pic',   label:'Has photo',        test:c=>c.dataset.pic==='1'},
  {k:'link',  label:'Live link',        test:c=>c.dataset.link==='1'},
  {k:'monk',  label:'Monks · พระ',      test:c=>c.dataset.hay.includes('พระ')},
  {k:'wat',   label:'Wat · วัด',        test:c=>c.dataset.hay.includes('วัด')},
  {k:'named', label:'Named monk · หลวงพ่อ/ปู่', test:c=>/หลวงพ่อ|หลวงปู่|ครูบา/.test(c.dataset.hay)},
  {k:'coin',  label:'Coin · เหรียญ',    test:c=>c.dataset.hay.includes('เหรียญ')},
  {k:'cloth', label:'Yantra cloth · ผ้ายันต์', test:c=>c.dataset.hay.includes('ผ้ายันต์')},
];
// Price bands (฿). Single-select, unlike the AND-combined FLAGS above.
const BANDS=[
  {k:'lo',  label:'< ฿50',     test:v=>v!=null&&v<50},
  {k:'mid', label:'฿50–200',   test:v=>v!=null&&v>=50&&v<200},
  {k:'hi',  label:'> ฿200',    test:v=>v!=null&&v>=200},
];
function fixImg(u){if(!u)return '';return u.startsWith('//')?'https:'+u:u;}
function flagCount(f){return ALL.filter(it=>f.test({dataset:{pic:it.image?'1':'0',link:it.url?'1':'0',hay:((it.title||'')+' '+(it.location||'')).toLowerCase()}})).length;}
function money(v,c){if(v==null)return '—';return '฿'+Number(v).toLocaleString()+(c&&c!=='THB'?' '+c:'');}
function card(it){
  const c=el('div',{className:'mcard'});
  c.dataset.terms=(it.terms||[]).join(' ');
  c.dataset.hay=((it.title||'')+' '+(it.location||'')).toLowerCase();
  const src=fixImg(it.image);
  c.dataset.pic=src?'1':'0';
  c.dataset.link=it.url?'1':'0';
  c.dataset.dead=isArchived(it)?'1':'0';
  c.dataset.loc=it.location||'';
  c.dataset.price=(it.price==null?'':String(it.price));
  if(src){const img=el('img',{className:'mimg',src,loading:'lazy',alt:it.title||''});img.addEventListener('error',()=>{const ph=el('div',{className:'mph',title:'no listing photo'});img.replaceWith(ph);});c.append(img);}
  else{c.append(el('div',{className:'mph',title:'no listing photo'}));}
  const b=el('div',{className:'mbody'});
  b.append(el('div',{className:'mtitle thai',textContent:it.title||'(untitled)'}));
  b.append(el('div',{className:'mprice',textContent:money(it.price,it.currency)}));
  const meta=el('div',{className:'mmeta'});
  if(it.location){const loc=el('span',{},['📍 '+it.location]);if(it.location_en)loc.append(el('span',{className:'en',textContent:' · '+it.location_en}));meta.append(loc);}
  if(it.sold)meta.append(el('span',{textContent:it.sold+' sold'}));
  if(isArchived(it))meta.append(el('span',{className:'en',title:'source listing no longer reachable since '+(it.deadSince||'').slice(0,10)+' — kept as price history',textContent:'🗄 archived'}));
  b.append(meta);
  if(it.terms&&it.terms.length){const tw=el('div',{className:'mtags'});for(const t of it.terms){const g=LABELS[t];const gShort=g?g.replace(/\s*\(.*$/,''):'';const chip=el('span',{className:'mtag',title:g||t},[t]);if(gShort)chip.append(el('span',{className:'en',textContent:' · '+gShort}));tw.append(chip);}b.append(tw);}
  if(it.url&&!isArchived(it))b.append(el('a',{className:'mlink',href:it.url,target:'_blank',rel:'noopener',textContent:'View listing ›'}));
  else if(it.url)b.append(el('span',{className:'mlink',style:'color:var(--muted);cursor:default',title:'the original listing has been removed',textContent:'source listing gone'}));
  c.append(b);return c;
}
function applyFilter(){let shown=0;
  document.querySelectorAll('.mcard').forEach(c=>{
    const okT=!term||(' '+c.dataset.terms+' ').includes(' '+term+' ');
    const okQ=!QG.length||QG.every(g=>g.some(m=>c.dataset.hay.includes(m)));
    const okF=FLAGS.every(f=>!flags[f.k]||f.test(c));
    const okP=!prov||c.dataset.loc===prov;
    const bd=band&&BANDS.find(b=>b.k===band);
    const okB=!bd||(c.dataset.price!==''&&bd.test(Number(c.dataset.price)));
    const okA=showArchived||c.dataset.dead!=='1';   // hide dead-source listings by default
    const ok=okT&&okQ&&okF&&okP&&okB&&okA;c.classList.toggle('hide',!ok);if(ok)shown++;});
  const nArch=ALL.filter(isArchived).length;
  document.getElementById('mcount').textContent='Showing '+shown+' of '+(ALL.length-(showArchived?0:nArch))
    +' live listings'+(nArch?' · '+nArch+' archived'+(showArchived?' (shown)':' hidden'):'');
  document.querySelectorAll('.term[data-v]').forEach(t=>t.classList.toggle('on',t.dataset.v===term));
  document.querySelectorAll('.term[data-f]').forEach(t=>t.classList.toggle('on',!!flags[t.dataset.f]));
  document.querySelectorAll('.term[data-b]').forEach(t=>t.classList.toggle('on',t.dataset.b===band));
}
function bars(title, rows){ // rows: [{label, sub?, value}] -> horizontal bar card
  const max=Math.max(1,...rows.map(r=>r.value));
  const box=el('div',{className:'tcard'},[el('h3',{textContent:title})]);
  const rw=el('div',{className:'brow'});
  for(const r of rows){
    const lbl=el('span',{className:'bl',title:(r.sub?r.label+' · '+r.sub:r.label)},[document.createTextNode(r.label)]);
    if(r.sub)lbl.append(el('span',{className:'en',textContent:' · '+r.sub}));
    const bt=el('div',{className:'bt',style:'width:'+Math.round(100*r.value/max)+'%'});
    rw.append(el('div',{className:'bitem'},[lbl,bt,el('span',{className:'bn',textContent:r.value.toLocaleString()})]));
  }
  box.append(rw);return box;
}
function trendsBand(all,d){
  const wrap=el('div',{className:'trends'});
  const terms=(d.terms||[]).slice(0,8).map(t=>({label:t.value,sub:(t.label||'').replace(/\s*\(.*$/,''),value:t.n}));
  if(terms.length)wrap.append(bars("What’s circulating (by term)", terms));
  if(typeof BANDS!=='undefined'){
    const pr=BANDS.map(b=>({label:b.label,value:all.filter(it=>it.price!=null&&b.test(it.price)).length})).filter(r=>r.value);
    if(pr.length)wrap.append(bars('Price distribution', pr));
  }
  // newly catalogued, by day (last 14 days with data) — objects decay, so this is the pulse
  const byday={};for(const it of all){const dt=(it.crawled_at||'').slice(0,10);if(dt)byday[dt]=(byday[dt]||0)+1;}
  const days=Object.keys(byday).sort().slice(-14);
  const sp=el('div',{className:'tcard'},[el('h3',{textContent:'Newly catalogued (per day)'})]);
  if(days.length){const mx=Math.max(...days.map(k=>byday[k]));const strip=el('div',{className:'spark'});
    for(const k of days)strip.append(el('div',{className:'sb',style:'height:'+Math.round(100*byday[k]/mx)+'%',title:k+': '+byday[k]+' listings'}));
    sp.append(strip);sp.append(el('p',{className:'prov',style:'margin:8px 0 0',textContent:days[0]+' → '+days[days.length-1]+' · listings decay as small runs sell out'}));
  } else sp.append(el('p',{className:'muted',textContent:'no crawl dates yet'}));
  wrap.append(sp);
  return wrap;
}
async function load(){const d=await (await fetch('/api/market')).json();const main=document.getElementById('main');main.textContent='';
  if(!d.dbPresent){main.append(el('div',{className:'empty'},[el('p',{textContent:'No catalog database yet.'})]));return;}
  if(!d.count){main.append(el('div',{className:'empty'},[el('p',{textContent:'No market listings yet.'}),el('p',{className:'muted',textContent:'Run: python -m crawler.cli lazada  — then reload.'})]));return;}
  ALL=d.items;LABELS=d.termLabels||{};
  const hero=el('div',{className:'hero'});
  const p=d.price||{};
  hero.append(el('div',{className:'hbox'},[el('b',{textContent:'Listings'}),el('span',{textContent:d.count.toLocaleString()})]));
  if(p.median!=null)hero.append(el('div',{className:'hbox'},[el('b',{textContent:'Median price'}),el('span',{textContent:money(p.median)})]));
  if(p.min!=null)hero.append(el('div',{className:'hbox'},[el('b',{textContent:'Price range'}),el('span',{textContent:money(p.min)+'–'+money(p.max)})]));
  hero.append(el('div',{className:'hbox'},[el('b',{textContent:'Provinces'}),el('span',{textContent:(d.locations||[]).length})]));
  const top=el('div',{className:'card'});top.append(el('h2',{textContent:'The tradition in the present tense',style:'margin-top:0'}),hero,
    el('p',{className:'prov',textContent:'The same wichaa the manuscripts describe is still worn, bought, and traded. Each listing is real commercial vernacular — what an object is called, what it costs, where it ships from — sitting on one continuous timeline with the archive.'}),
    el('p',{className:'prov',textContent:'Provenance: '+((d.sources||[]).map(s=>s.value+' ('+s.n+')').join(', ')||'living commerce')+'. These are living-practice records, kept distinct from the scholarly catalogue.'}));
  if(d.archive&&d.archive.url){const at=(d.archive.at||'').slice(0,10);
    top.append(el('p',{className:'prov'},[
      document.createTextNode('Preserved at the Internet Archive'+(at?' ('+at+')':'')+' so it outlives the source listings: '),
      el('a',{href:d.archive.url,textContent:d.archive.url,target:'_blank',rel:'noopener'}),
      document.createTextNode(d.archive.images?' — '+d.archive.images.toLocaleString()+' images mirrored.':'.')]));}
  main.append(top);
  main.append(trendsBand(ALL,d));   // visuals first: the trend panel leads
  // Province geography lives in the geo widget now (the old /map was a 6-dot stub);
  // link it here so the "where does this come from / sell from" view stays reachable.
  main.append(el('p',{className:'prov',style:'margin:6px 0 14px'},[
    document.createTextNode('🗺  '),
    el('a',{href:'/w/geo',textContent:'Where the tradition lives — manuscripts vs market, by province'}),
    document.createTextNode('  ·  '),
    el('a',{href:'/browse',textContent:'browse manuscripts by province'})]));
  // Filter panel collapses by default (visuals-first). The count rides in the summary
  // so it stays visible when the panel is closed; open it to reveal all controls.
  const fcard=el('details',{className:'card filters'});
  fcard.append(el('summary',{},[document.createTextNode('Filter & search'),el('span',{className:'mcount',id:'mcount'})]));
  const group=(label,row)=>el('div',{className:'fgroup'},[el('span',{className:'flabel',textContent:label}),row]);

  const tools=el('div',{className:'ftools'});
  const inp=el('input',{type:'search',placeholder:'Search title or place…','aria-label':'Search listings'});
  inp.addEventListener('input',()=>{q=inp.value.trim().toLowerCase();QG=q?q.split(/\s+/).map(expandTok):[];applyFilter();});
  const sel=el('select',{'aria-label':'Filter by province'});
  sel.append(el('option',{value:'',textContent:'All provinces'}));
  for(const l of (d.locations||[])){sel.append(el('option',{value:l.value,textContent:l.value+(l.en?' · '+l.en:'')+' ('+l.n+')'}));}
  sel.addEventListener('change',()=>{prov=sel.value;applyFilter();});
  const clear=el('button',{className:'secondary fclear',type:'button',textContent:'Clear all'});
  clear.addEventListener('click',()=>{term='';q='';QG=[];flags={};prov='';band='';showArchived=false;inp.value='';sel.value='';const ac=document.getElementById('archcb');if(ac)ac.checked=false;applyFilter();});
  tools.append(inp,sel,clear);
  // Archived toggle: only appears when linkcheck has actually retired some listings,
  // so the control stays invisible until it's meaningful.
  const nArch=ALL.filter(isArchived).length;
  if(nArch){
    const lab=el('label',{style:'display:inline-flex;align-items:center;gap:6px;font-size:14px;color:var(--muted);cursor:pointer'});
    const cb=el('input',{type:'checkbox',id:'archcb'});
    cb.addEventListener('change',()=>{showArchived=cb.checked;applyFilter();});
    lab.append(cb,document.createTextNode('Show '+nArch+' archived (source gone)'));
    tools.append(lab);
  }
  fcard.append(tools);

  const bar=el('div',{className:'frow'});
  const allc=el('span',{className:'term',textContent:'All'});allc.dataset.v='';allc.addEventListener('click',()=>{term='';applyFilter();});bar.append(allc);
  for(const t of (d.terms||[])){const enShort=t.label?t.label.replace(/\s*\(.*$/,''):'';const kids=[el('span',{className:'th',textContent:t.value})];if(enShort)kids.push(el('span',{className:'en',textContent:enShort}));kids.push(el('span',{className:'pn',textContent:t.n}));const s=el('span',{className:'term',title:t.label||t.value},kids);s.dataset.v=t.value;s.addEventListener('click',()=>{term=(term===t.value?'':t.value);applyFilter();});bar.append(s);}
  fcard.append(group('Type',bar));

  const pbar=el('div',{className:'frow'});
  const pAny=el('span',{className:'term',textContent:'Any'});pAny.dataset.b='';pAny.addEventListener('click',()=>{band='';applyFilter();});pbar.append(pAny);
  for(const bnd of BANDS){const n=ALL.filter(it=>bnd.test(it.price)).length;const s=el('span',{className:'term',title:bnd.label},[el('span',{className:'th',textContent:bnd.label}),el('span',{className:'pn',textContent:n})]);s.dataset.b=bnd.k;s.addEventListener('click',()=>{band=(band===bnd.k?'':bnd.k);applyFilter();});pbar.append(s);}
  fcard.append(group('Price',pbar));

  const fbar=el('div',{className:'frow'});
  for(const f of FLAGS){const s=el('span',{className:'term',title:f.label},[el('span',{className:'th',textContent:f.label}),el('span',{className:'pn',textContent:flagCount(f)})]);s.dataset.f=f.k;s.addEventListener('click',()=>{flags[f.k]=!flags[f.k];applyFilter();});fbar.append(s);}
  const det=el('details',{className:'morefilters'});
  det.append(el('summary',{},[el('span',{className:'flabel',textContent:'More filters'}),el('span',{className:'muted',textContent:' photo · live link · figures'})]),fbar);
  fcard.append(det);
  main.append(fcard);
  const grid=el('div',{className:'mgrid'});for(const it of ALL)grid.append(card(it));main.append(grid);
  applyFilter();
}
load();
""" + "</script>")


# ---------------------------------------------------------------------------
# ค้นความหมาย · Search by meaning
#
# The directory nav answers "show me what you have under X" and it stays the
# front door. This answers a question. The corpus is catalogued in Thai, in RTGS
# transliteration and in English, and a reader arrives holding only one of the
# three — so matching on characters strands them. The query is embedded with
# @cf/baai/bge-m3 and compared against the same embedding of every manuscript,
# which means ยันต์ finds the yantra manuals whether the record says ยันต์,
# "yantra", or "Tamra Phetcharat Maha-yant".
#
# Measured before choosing: an English-only embedding model scored UNRELATED
# Thai/English pairs HIGHER than related ones on this corpus. See
# search_index.py — the multilingual model is a requirement, not a preference.
#
# The whole thing is progressive: with no JavaScript, or if the endpoint is
# having a quiet moment, the page still explains itself and points at /browse.
SEARCH_PAGE = page("ค้นความหมาย · Search by meaning — wichaa", """
  .sbox{position:relative;margin:18px 0 10px}
  .sfield{display:flex;gap:10px;align-items:stretch;
          background:rgba(255,255,255,.55);backdrop-filter:blur(10px) saturate(1.3);
          -webkit-backdrop-filter:blur(10px) saturate(1.3);
          border:1px solid var(--line);border-radius:16px;padding:8px;
          box-shadow:0 10px 30px rgba(0,0,0,.06);
          transition:box-shadow .25s ease,border-color .25s ease,transform .25s ease}
  .sfield:focus-within{border-color:var(--teal);transform:translateY(-1px);
                       box-shadow:0 14px 38px rgba(0,0,0,.10)}
  .sfield input{flex:1;border:0;background:transparent;outline:none;
                font:inherit;font-size:18px;padding:12px 14px;color:var(--ink)}
  .sfield button{border:0;border-radius:11px;background:var(--teal);color:#fff;
                 font:inherit;font-weight:700;padding:12px 22px;cursor:pointer;
                 transition:transform .12s cubic-bezier(.34,1.56,.64,1),filter .2s}
  .sfield button:hover{filter:brightness(1.08)}
  .sfield button:active{transform:scale(.94)}
  .sfield button[disabled]{opacity:.55;cursor:progress}
  .shint{color:var(--muted);font-size:14px;margin:0 0 18px}
  .schips{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 20px}
  .schip{border:1px solid var(--line);border-radius:999px;padding:6px 14px;
         background:#fff;cursor:pointer;font:inherit;font-size:14px;color:var(--ink);
         transition:transform .12s cubic-bezier(.34,1.56,.64,1),border-color .18s,background .18s}
  .schip:hover{border-color:var(--teal);background:var(--gold-bg);transform:translateY(-2px)}
  .schip:active{transform:scale(.95)}
  .sres{display:grid;gap:12px;margin:8px 0 30px}
  .sr{display:block;border:1px solid var(--line);border-radius:14px;padding:14px 16px;
      background:#fff;text-decoration:none;color:inherit;
      transition:border-color .16s,transform .16s,box-shadow .16s}
  .sr:hover{border-color:var(--teal);transform:translateY(-2px);
            box-shadow:0 10px 26px rgba(0,0,0,.08)}
  .sr:focus-visible{outline:3px solid var(--teal);outline-offset:2px}
  .sr .th{font-family:var(--serif);font-size:19px;margin:0 0 3px}
  .sr .en{color:var(--muted);font-size:15px;margin:0 0 8px}
  .sr .facts{display:flex;flex-wrap:wrap;gap:6px}
  .sr .f{font-size:12px;border:1px solid var(--line);border-radius:999px;
         padding:2px 10px;color:var(--muted);background:var(--bg)}
  .sr .f.g{background:var(--gold-bg);color:var(--ink);border-color:transparent}
  .smeter{float:right;font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
  .snote{color:var(--muted);font-size:14px;margin:14px 0}
  .sempty{border:1px dashed var(--line);border-radius:14px;padding:22px;
          text-align:center;color:var(--muted)}
  @media (prefers-color-scheme:dark){
    .sfield{background:rgba(255,255,255,.06)}
    .sr,.schip{background:rgba(255,255,255,.04)}
  }
""", """
<main class="wrap">
  <h1>ค้นความหมาย · Search by meaning</h1>
  <p class="lead">Ask in Thai or in English. This looks for what a manuscript is
     <em>about</em>, not for the letters you typed — so ยันต์ will find the yantra
     manuals whether the catalogue happens to name them in Thai, in transliteration
     or in English.</p>

  <form class="sbox" id="sform" action="/search/" method="get">
    <div class="sfield">
      <input id="sq" name="q" type="search" autocomplete="off"
             placeholder="ยันต์กันภัย · protective yantra · ตำรายา · astrology manual"
             aria-label="Search the corpus by meaning">
      <button id="sgo" type="submit">ค้นหา</button>
    </div>
  </form>
  <p class="shint">Every manuscript in the corpus is searchable this way. Looking for a
     term, a place or a genre to browse instead? The <a href="/browse">directory</a>
     lists them all with counts.</p>

  <div class="schips" id="schips"></div>
  <div id="sres" class="sres"></div>
  <noscript><p class="snote">Search by meaning needs JavaScript. The
    <a href="/browse">directory</a> works without it.</p></noscript>
</main>
""" + "<script>" + r"""
var EXAMPLES = [
  "ยันต์กันภัย",
  "protective yantra",
  "โหราศาสตร์ ดวงชะตา",
  "chronicle of a northern city",
  "คาถาเมตตา",
  "palm-leaf grammar primer"
];
var q  = document.getElementById('sq');
var go = document.getElementById('sgo');
var out= document.getElementById('sres');
var chips = document.getElementById('schips');

EXAMPLES.forEach(function(t){
  var b=document.createElement('button');
  b.type='button'; b.className='schip'; b.textContent=t;
  b.onclick=function(){ q.value=t; run(); };
  chips.appendChild(b);
});

function esc(s){ return (s||'').replace(/[&<>"]/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }

function card(r){
  var f=[];
  if(r.genre) f.push('<span class="f g">'+esc(r.genre.replace(/_/g,' '))+'</span>');
  if(r.place) f.push('<span class="f">'+esc(r.place)+'</span>');
  if(r.temple)f.push('<span class="f">'+esc(r.temple)+'</span>');
  if(r.date)  f.push('<span class="f">'+esc(r.date)+'</span>');
  var second = r.translit && r.translit!==r.title_en ? r.translit+' · '+r.title_en : (r.title_en||r.translit||'');
  return '<a class="sr" href="'+esc(r.url||'#')+'">'
       +   '<span class="smeter">'+(r.score!=null?r.score.toFixed(3):'')+'</span>'
       +   '<div class="th">'+esc(r.title_th||second||'—')+'</div>'
       +   (second?'<div class="en">'+esc(second)+'</div>':'')
       +   '<div class="facts">'+f.join('')+'</div>'
       + '</a>';
}

var inflight=null;
function run(){
  var term=(q.value||'').trim();
  if(!term){ out.innerHTML=''; return; }
  history.replaceState(null,'','/search/?q='+encodeURIComponent(term));
  go.disabled=true; out.innerHTML='<p class="snote">กำลังค้นหา · looking…</p>';
  if(inflight) inflight.abort&&inflight.abort();
  var ctrl = (typeof AbortController!=='undefined') ? new AbortController() : null;
  inflight = ctrl;
  fetch('/api/search?n=24&q='+encodeURIComponent(term), ctrl?{signal:ctrl.signal}:{})
    .then(function(r){ return r.json(); })
    .then(function(d){
      go.disabled=false;
      if(d.error){ out.innerHTML='<div class="sempty">Search is resting just now. The '
        +'<a href="/browse">directory</a> is right here in the meantime.</div>'; return; }
      if(!d.results||!d.results.length){ out.innerHTML='<div class="sempty">Nothing in the corpus '
        +'answers to that yet — try a broader word, or browse the '
        +'<a href="/browse">directory</a>.</div>'; return; }
      out.innerHTML=d.results.map(card).join('');
    })
    .catch(function(e){
      if(e && e.name==='AbortError') return;
      go.disabled=false;
      out.innerHTML='<div class="sempty">Search is resting just now. The '
        +'<a href="/browse">directory</a> is right here in the meantime.</div>';
    });
}

document.getElementById('sform').addEventListener('submit',function(e){ e.preventDefault(); run(); });

var pre=new URLSearchParams(location.search).get('q');
if(pre){ q.value=pre; run(); } else { q.focus(); }
""" + "</script>",
description=("Search the Lanna manuscript corpus by meaning, in Thai or English. "
             "Multilingual semantic search across every catalogued manuscript — "
             "titles in Thai, transliteration and English, with genre, temple and date."))


EXPEDITE_PAGE = page("St. Expedite — wichaa", """
  .exhero{border:1px solid rgba(163,36,28,.35);background:rgba(163,36,28,.06);
          border-radius:10px;padding:14px 18px;margin:16px 0}
  .exhero h2{margin:0 0 6px;font-size:17px}
  .extiles{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}
  .extile{border:1px solid rgba(128,128,128,.28);border-radius:8px;padding:10px 14px;min-width:120px}
  .extile b{display:block;font-size:22px} .extile span{font-size:13px;opacity:.7}
  .exchips{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 16px}
  .exchip{border:1px solid rgba(128,128,128,.3);border-radius:1em;padding:2px 10px;font-size:13px}
  .exgrp{margin:14px 0} .exgrp h3{margin:0 0 6px;font-size:15px;border-bottom:1px solid rgba(128,128,128,.25)}
  .exlist{list-style:none;margin:0;padding:0;display:grid;gap:4px}
  .exrow{font-size:14px;padding:3px 0} .exrow .k{opacity:.6;font-size:12px;margin-left:6px}
  .exrow .cur{color:var(--red,#a3241c);font-weight:600;font-size:11px;margin-left:6px}
""",
  "<header><div><h1>St. Expedite</h1><p class=sub>A global saint-cult of urgent causes — "
  "one of the corpus's living wichaa traditions, coequal with the Lanna manuscripts and the "
  "amulet market. Shrines and churches catalogued from OpenStreetMap and a curated canon.</p>"
  "</div>" + NAV + "</header>"
  "<main id=main><p class=muted>Loading…</p></main>"
  "<script>" + r"""
const el=(t,p={},k=[])=>{const e=document.createElement(t);Object.assign(e,p);for(const c of [].concat(k))if(c!=null&&c!==false)e.append(c);return e;};
async function load(){
  const d=await (await fetch('/api/expedite')).json();
  const main=document.getElementById('main'); main.textContent='';
  if(!d.dbPresent){main.append(el('p',{className:'muted',textContent:'No catalog database yet.'}));return;}
  const hero=el('div',{className:'exhero'});
  hero.append(el('h2',{textContent:'One saint, many worlds'}),
    el('p',{textContent:'Expedite is refracted through the Bollandist record, Catholic urgent-causes devotion, New Orleans hoodoo, and Réunion’s red shrines. A fuller illustrated companion — interactive map, gallery, and articles, each claim tagged by reliability — is built separately as the st-expedite-wiki. Here he lives inside the shared wichaa corpus.'}));
  main.append(hero);
  const tiles=el('div',{className:'extiles'});
  tiles.append(el('div',{className:'extile'},[el('b',{textContent:d.count}),el('span',{textContent:'shrines & churches'})]));
  tiles.append(el('div',{className:'extile'},[el('b',{textContent:d.countries.length}),el('span',{textContent:'countries'})]));
  main.append(tiles);
  const kc=el('div',{className:'exchips'});
  for(const k of d.kinds) kc.append(el('span',{className:'exchip',textContent:k.value+' · '+k.n}));
  main.append(el('div',{},[el('strong',{textContent:'By kind: '}),kc]));
  // group items by country
  const byC={};
  for(const it of d.items){(byC[it.location]=byC[it.location]||[]).push(it);}
  const order=d.countries.map(c=>c.value);
  for(const loc of order){
    const g=el('div',{className:'exgrp'});
    g.append(el('h3',{textContent:loc+' ('+byC[loc].length+')'}));
    const ul=el('ul',{className:'exlist'});
    for(const it of byC[loc]){
      const row=el('li',{className:'exrow'});
      if(it.url) row.append(el('a',{href:it.url,target:'_blank',rel:'noopener',textContent:it.title}));
      else row.append(document.createTextNode(it.title));
      row.append(el('span',{className:'k',textContent:it.kind}));
      if(it.curated) row.append(el('span',{className:'cur',textContent:'✦ curated'}));
      ul.append(row);
    }
    g.append(ul); main.append(g);
  }
}
load();
""" + "</script>")


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"\n  wichaa running at {url}")
    print(f"  Catalog: {CATALOG_DB}  ({'found' if db_present() else 'not created yet'})")
    print("  (leave this window open; close it to stop)\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    # Warm the search index + row cache off the request path so the first user
    # search is fast instead of paying the one-time build.
    threading.Thread(target=lambda: (_search_rows(), manuscripts_api_body()),
                     daemon=True).start()
    # Sponsored-OCR queue worker (Ko-fi tam boon) — processes jobs the webhook
    # enqueued, one at a time, sharing _job_lock with the local OCR route.
    threading.Thread(target=_sponsor_worker, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
