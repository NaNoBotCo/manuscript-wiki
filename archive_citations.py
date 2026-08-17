#!/usr/bin/env python3
"""archive_citations.py — give every outbound article citation a Wayback anchor.

The authored articles (content/*.md) and the published curiosity findings (the
articles table in the catalog) cite the open web, and the open web rots. This
tool walks every outbound http(s) link in that prose, asks the Wayback Machine
Availability API for the closest snapshot, probes whether the original still
answers, and writes the result to data/citation_archive.json — which wiki.py
reads at render time to set a quiet "archived <date>" badge beside each
citation (see wiki._external_link). A citation that is offline AND unarchived
is named and dated on the page but never hyperlinked — the same discipline the
mot-dang directory uses for its dead listings.

AVAILABILITY ONLY, by design: this never asks the Wayback Machine to capture
anything (Save-Page-Now lives in ../manuscript-crawler/spn.py, with its own
ledger and etiquette). It only asks what already exists.

Gentle and resumable:
  · one request in flight at a time; ≥1.1 s between archive.org calls and
    ≥1.5 s between liveness probes
  · snapshot-first cache: once a URL has a snapshot recorded, reruns never
    re-ask — a Wayback snapshot URL is permanent. Unarchived URLs are re-asked
    only after --recheck-days (default 7)
  · data/citation_archive.json is rewritten after every URL, so an interrupted
    run resumes exactly where it stopped

Liveness follows linkcheck.py's lesson from the market tier: mark offline ONLY
on strong signals (HTTP 404/410). A 403/429/timeout is inconclusive — the link
stays a normal link and is re-tried next run — because a bot-wall must never
read as a dead source.

Scope today is the article prose (content/*.md + published findings). The wats
pages carry their own Wikipedia/Commons attribution links, which must stay
linked as attribution regardless of archive state, so they are deliberately
not swept; widening later means adding a collector beside gather_urls().

Usage:
    python3 archive_citations.py               # fetch what is missing, then report
    python3 archive_citations.py --report      # coverage report only, no network
    python3 archive_citations.py --refresh     # ignore the recheck window
    python3 archive_citations.py --limit 10    # bound a run
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTENT = HERE / "content"
DATA = HERE / "data"
OUT = DATA / "citation_archive.json"

AVAILABILITY_API = "https://archive.org/wayback/available"
UA = "LannaWikiCitations/1.0 (+wichaa.net article citation preservation; contact 530kings@proton.me)"
# For liveness probes only: a bot UA gets walled instantly and every citation
# would look offline — same reasoning, same string, as linkcheck.py.
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

WAYBACK_GAP_S = 1.1     # min seconds between Availability API calls
PROBE_GAP_S = 1.5       # min seconds between liveness probes
TIMEOUT_S = 30

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BARE_URL_RE = re.compile(r"https?://[^\s)\"'<>\]]+")
TRAIL_PUNCT = ".,;:!?·…'\")"

_last_call = {"wayback": 0.0, "probe": 0.0}


def now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _pace(kind, gap):
    wait = _last_call[kind] + gap - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_call[kind] = time.monotonic()


def _clean_url(u):
    return u.rstrip(TRAIL_PUNCT)


def extract_urls(text):
    """Outbound http(s) URLs in one article body: markdown-link hrefs first
    (taken exactly as written — that exact string is the render-time cache key),
    then bare URLs in the remaining prose."""
    urls = []
    for m in LINK_RE.finditer(text):
        href = m.group(2).strip()
        if href.startswith(("http://", "https://")):
            urls.append(href)
    rest = LINK_RE.sub(" ", text)
    for m in BARE_URL_RE.finditer(rest):
        urls.append(_clean_url(m.group(0)))
    return urls


def gather_urls():
    """url -> sorted list of the article files / finding slugs that cite it."""
    cites = {}

    def add(url, where):
        cites.setdefault(url, set()).add(where)

    for p in sorted(CONTENT.glob("*.md")):
        if p.name.startswith("_"):
            continue
        for url in extract_urls(p.read_text(encoding="utf-8")):
            add(url, p.name)

    # Published curiosity findings render through the same md_to_html, so their
    # citations get the same protection. The catalog is the crawler's file and
    # may be busy — read-only, and a locked DB just narrows this run's scope.
    db = Path(HERE.parent / "manuscript-crawler" / "crawler" / "catalog.db")
    if db.is_file():
        try:
            conn = sqlite3.connect("file:" + str(db) + "?mode=ro", uri=True, timeout=5)
            try:
                rows = conn.execute(
                    "SELECT slug, body_md FROM articles "
                    "WHERE status='published'").fetchall()
            finally:
                conn.close()
            for slug, body in rows:
                for url in extract_urls(body or ""):
                    add(url, "finding:" + (slug or "?"))
        except sqlite3.OperationalError as e:
            print(f"  note: findings skipped this run (catalog busy: {e}); content/*.md swept in full")
    return {u: sorted(w) for u, w in cites.items()}


def wayback_lookup(url):
    """Ask the Availability API for the closest snapshot. Returns
    (archived, snapshot_url, snapshot_ts) — never raises."""
    _pace("wayback", WAYBACK_GAP_S)
    q = AVAILABILITY_API + "?" + urllib.parse.urlencode({"url": url})
    req = urllib.request.Request(q, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            payload = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        print(f"    availability query failed ({e}) — left unarchived for next run")
        return False, "", ""
    closest = (payload.get("archived_snapshots") or {}).get("closest") or {}
    if closest.get("available") and closest.get("url"):
        snap = closest["url"]
        if snap.startswith("http://"):
            snap = "https://" + snap[len("http://"):]
        return True, snap, str(closest.get("timestamp") or "")
    return False, "", ""


def probe_live(url):
    """(live, status): True only on a real answer, False only on strong signals
    (404/410), None when inconclusive — bot walls and hiccups stay linked."""
    _pace("probe", PROBE_GAP_S)
    req = urllib.request.Request(url, method="HEAD",
                                 headers={"User-Agent": BROWSER_UA,
                                          "Accept-Language": "en,th;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return True, r.status
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return False, e.code
        if e.code in (405, 501):            # HEAD refused; try a real GET once
            try:
                req2 = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
                with urllib.request.urlopen(req2, timeout=TIMEOUT_S) as r2:
                    return True, r2.status
            except urllib.error.HTTPError as e2:
                if e2.code in (404, 410):
                    return False, e2.code
                return None, e2.code
            except Exception:
                return None, 0
        return None, e.code
    except Exception:
        return None, 0


def ts_to_date(ts):
    ts = str(ts or "")
    if len(ts) >= 8:
        return ts[0:4] + "-" + ts[4:6] + "-" + ts[6:8]
    return ts


def load_store():
    if OUT.is_file():
        try:
            return json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"_meta": {}, "urls": {}}


def save_store(store):
    store["_meta"] = {
        "tool": "archive_citations.py",
        "api": AVAILABILITY_API,
        "src": "wayback_availability_api",
        "license_note": "snapshot URLs point into the Internet Archive Wayback Machine",
        "updated": now_iso(),
    }
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(store, ensure_ascii=False, indent=2, sort_keys=True),
                   encoding="utf-8")
    tmp.replace(OUT)


def is_due(entry, recheck_days, refresh):
    if not entry:
        return True
    if entry.get("archived") and entry.get("snapshot_url") and not refresh:
        return False                        # a snapshot is permanent — never re-ask
    if refresh:
        return True
    checked = entry.get("checked_at") or ""
    try:
        age = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(checked)
        return age.days >= recheck_days
    except Exception:
        return True


def report(store, cites):
    urls = store.get("urls", {})
    n = len(cites)
    archived = sum(1 for u in cites if urls.get(u, {}).get("archived"))
    offline_unarchived = [u for u in cites
                          if urls.get(u, {}).get("live") is False
                          and not urls.get(u, {}).get("archived")]
    unchecked = [u for u in cites if u not in urls]
    print(f"\ncitation archive coverage — {n} outbound URLs cited by articles")
    print(f"  archived on Wayback : {archived}")
    print(f"  offline, unarchived : {len(offline_unarchived)}  (rendered named + dated, not linked)")
    print(f"  not yet checked     : {len(unchecked)}")
    for u in offline_unarchived:
        e = urls.get(u, {})
        print(f"    offline: {u}  (checked {str(e.get('live_checked_at') or '')[:10]}; "
              f"cited by {', '.join(e.get('articles') or [])})")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report", action="store_true", help="coverage report only; no network")
    ap.add_argument("--refresh", action="store_true", help="re-ask even inside the recheck window")
    ap.add_argument("--recheck-days", type=int, default=7,
                    help="days before an unarchived URL is asked about again (default 7)")
    ap.add_argument("--limit", type=int, default=0, help="check at most N URLs this run")
    args = ap.parse_args()

    cites = gather_urls()
    store = load_store()
    urls = store.setdefault("urls", {})

    # Keep the citing-articles provenance current even for cached entries.
    for u, arts in cites.items():
        if u in urls:
            urls[u]["articles"] = arts

    if args.report:
        save_store(store)
        return report(store, cites)

    due = [u for u in cites if is_due(urls.get(u), args.recheck_days, args.refresh)]
    if args.limit:
        due = due[:args.limit]
    print(f"{len(cites)} outbound citation URLs; {len(due)} to check this run")

    for i, u in enumerate(due, 1):
        print(f"  [{i}/{len(due)}] {u}")
        entry = urls.get(u, {})
        archived, snap, ts = wayback_lookup(u)
        if archived:
            entry.update(archived=True, snapshot_url=snap,
                         snapshot_ts=ts, snapshot_date=ts_to_date(ts))
            print(f"    archived {entry['snapshot_date']}")
        else:
            entry.setdefault("archived", False)
            entry.setdefault("snapshot_url", "")
            entry.setdefault("snapshot_date", "")
            print("    no snapshot on record")
        live, status = probe_live(u)
        if live is not None:
            entry.update(live=live, live_status=status, live_checked_at=now_iso())
            print(f"    original {'answers' if live else 'offline'} (HTTP {status})")
        else:
            entry.setdefault("live", None)
            print(f"    liveness inconclusive (HTTP {status}) — stays a normal link")
        entry.update(checked_at=now_iso(), articles=cites[u],
                     src="wayback_availability_api")
        urls[u] = entry
        save_store(store)                   # resumable: every URL lands on disk

    return report(store, cites)


if __name__ == "__main__":
    sys.exit(main())
