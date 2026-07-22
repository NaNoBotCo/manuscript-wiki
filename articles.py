#!/usr/bin/env python3
"""articles.py — keep the wiki's articles honest and growing.

The wiki (wiki.py) serves an article for every genre: the FACTS (counts, places,
scripts, dates) are recomputed live from the catalog, and the PROSE lives in
content/*.md. This is the automation around that — it reads the collection and
tells you what's covered and what to write next, wichaa-priority first, then
scaffolds stubs pre-filled with the live data-lede so a human (or a later LLM
pass) only has to expand them.

  python3 articles.py                     coverage report (priority-ordered)
  python3 articles.py --draft genre:astrology   scaffold ONE stub  (dry-run)
  python3 articles.py --draft-missing            scaffold every genre lacking prose
  python3 articles.py --apply  --draft-missing   actually write the .md files
  python3 articles.py --score                    rank subjects at every level:
                                                 ready-to-write vs. crawl "wanted"
  python3 articles.py --score --level L3          filter to one level/axis
  python3 articles.py --score --json              machine-readable candidates

Safe by default: with no --apply nothing is written, and an existing content file
is NEVER overwritten. Read-only against the catalog.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# The wiki lives beside the crawler; point at its catalog unless told otherwise.
_default_db = HERE.parent / "manuscript-crawler" / "crawler" / "catalog.db"
os.environ.setdefault("CATALOG_DB", str(_default_db))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import wiki  # shares the profile, lede, slug and content helpers


def _places_sentence(prof):
    provs = prof.get("provinces") or []
    temples = prof.get("temples") or []
    parts = []
    if provs:
        parts.append("mostly from " + ", ".join(p["label"] for p in provs[:3]))
    if temples:
        parts.append("with the largest holdings at " + ", ".join(t["label"] for t in temples[:3]))
    return ("It is " + "; ".join(parts) + ".") if parts else ""


def draft_markdown(art):
    """A stub pre-filled with the live lede + a skeleton to expand."""
    prof = art["profile"] or {"count": 0}
    label, noun = art["label"], art["noun"]
    lede = art["lede"] or f"{label} — {prof['count']} manuscripts in the collection."
    places = _places_sentence(prof)
    return (
        f"---\n"
        f"title: {label}\n"
        f"status: draft\n"
        f"see_also:\n"
        f"---\n"
        f"## Overview\n\n"
        f"{lede}\n\n"
        f"_Expand this: what this {noun} is, why it matters to the Lanna / wichaa "
        f"tradition, and what a reader should know before browsing it._\n\n"
        f"## In the collection\n\n"
        f"The catalogue holds {prof['count']} manuscripts under this {noun}. {places}\n\n"
        f"## Notes\n\n"
        f"- \n"
    )


# ---------------------------- multi-level scorer ----------------------------
# New crawl data should deepen the wiki at many levels of the descriptive
# taxonomy, not just the genre tier. This enumerates candidate SUBJECTS across
# levels — L1 genre · L2 sub-genre · L3 named entity — plus the cross-axes
# (place, script), then scores each by  importance × availability:
#   importance   = curated thematic weight (the wichaa core is boosted)
#   availability = live data density (log-scaled volume × metadata richness)
# The two are linked — priority subjects get collected more — so the payload is
# the *divergence*: important-and-rich subjects are "ready to write"; important-
# but-thin ones are the next crawl's "wanted" targets. Read-only against the DB.

GENRE_WEIGHT = {
    "astrology": 3.0, "magic_ritual": 3.0, "divination_omen": 3.0,
    "liturgy_chanting": 2.0, "tamnan_chronicle": 1.5, "law_customary": 1.3,
    "grammar_lexicography": 1.2,
}
# L3 named entities live in wiki.py as the single source of truth (the renderer
# needs the same alias table to build entity articles). Matching is a heuristic
# LIKE over the title, so entity counts are indicative, not exact.
ENTITIES = wiki.ENTITIES
_TITLE = wiki._ENTITY_TITLE
MIN_READY = 12      # records a subject needs before it can carry its own article
RICH_READY = 0.35   # …and the metadata richness it needs alongside the volume
IMPORTANT = 1.5     # importance at/above which a *thin* subject becomes a crawl target


def genre_weight(g):
    return GENRE_WEIGHT.get(g, 1.0)


def _density(conn, where, params):
    """count + metadata richness for an arbitrary slice. Richness = the mean
    non-null fraction across the fields an article leans on (date, place, script,
    image manifest) — a slice can be large but too thin to write from."""
    r = conn.execute(
        f"SELECT COUNT(*) n, COUNT(date_ce_estimate) dated, "
        f"SUM(CASE WHEN TRIM(COALESCE(provenance_province,''))<>'' THEN 1 END) prov, "
        f"SUM(CASE WHEN TRIM(COALESCE(provenance_temple,''))<>'' THEN 1 END) temple, "
        f"SUM(CASE WHEN TRIM(COALESCE(script,''))<>'' THEN 1 END) scr, "
        f"SUM(CASE WHEN TRIM(COALESCE(iiif_manifest_url,''))<>'' THEN 1 END) img "
        f"FROM manuscripts WHERE {where}", params).fetchone()
    n = r["n"] or 0
    if not n:
        return {"count": 0, "richness": 0.0}
    fr = [(r[k] or 0) / n for k in ("dated", "prov", "temple", "scr", "img")]
    return {"count": n, "richness": sum(fr) / len(fr)}


def _availability(dens):
    """Log-scaled volume modulated by richness. Volume alone over-rewards big
    thin buckets; richness alone ignores scale — the product tracks 'how much
    can I actually write about this today'."""
    return round(math.log10(dens["count"] + 1) * (0.4 + 0.6 * dens["richness"]), 3)


def _verdict(imp, dens, has_article):
    if has_article:
        return "written"
    if dens["count"] >= MIN_READY and dens["richness"] >= RICH_READY:
        return "ready"
    if imp >= IMPORTANT and (dens["count"] < MIN_READY or dens["richness"] < 0.30):
        return "wanted"
    return "thin"


def _cand(conn, level, stype, value, label, importance, where, params, keep_empty=False):
    dens = _density(conn, where, params)
    if not dens["count"] and not keep_empty:
        return None
    has = wiki.content_path(stype, value).exists()
    avail = _availability(dens)
    return {
        "level": level, "stype": stype, "value": value, "label": label,
        "count": dens["count"], "richness": round(dens["richness"], 2),
        "importance": round(importance, 2), "availability": avail,
        "score": round(importance * avail, 3), "hasArticle": has,
        "verdict": _verdict(importance, dens, has),
    }


def enumerate_subjects(conn):
    """Every candidate subject across levels and axes, each scored. Read-only."""
    cands = []
    # L1 — genre
    for r in conn.execute("SELECT genre_normalized v, COUNT(*) n FROM manuscripts "
                          "WHERE COALESCE(genre_normalized,'')<>'' GROUP BY v"):
        g = r["v"]
        cands.append(_cand(conn, "L1", "genre", g, wiki.prettify(g, wiki.GENRE_LABELS),
                           genre_weight(g), "genre_normalized=?", (g,)))
    # L2 — sub-genre (genre × raw label), only for genres that actually branch
    multi = {r["g"] for r in conn.execute(
        "SELECT genre_normalized g FROM manuscripts WHERE COALESCE(genre_normalized,'')<>'' "
        "AND COALESCE(genre_raw,'')<>'' GROUP BY g HAVING COUNT(DISTINCT genre_raw)>1")}
    for r in conn.execute("SELECT genre_normalized g, genre_raw raw, COUNT(*) n FROM manuscripts "
                          "WHERE COALESCE(genre_normalized,'')<>'' AND COALESCE(genre_raw,'')<>'' "
                          "GROUP BY g, raw HAVING n>=5"):
        g, raw = r["g"], r["raw"]
        if g not in multi:
            continue
        cands.append(_cand(conn, "L2", "subgenre", f"{g}:{raw}",
                           f"{wiki.prettify(g, wiki.GENRE_LABELS)} \u203a {raw}",
                           genre_weight(g), "genre_normalized=? AND genre_raw=?", (g, raw)))
    # L3 — named entities (heuristic title match against the alias table).
    # These are a *curated wishlist*: an entity with zero matches isn't noise, it's
    # a known part of the tradition we simply haven't collected — the strongest
    # possible crawl target — so keep it even at count 0.
    for key, label, w, variants in ENTITIES:
        where = "(" + " OR ".join([f"{_TITLE} LIKE ?"] * len(variants)) + ")"
        cands.append(_cand(conn, "L3", "entity", key, label, w, where,
                           tuple(f"%{v}%" for v in variants), keep_empty=True))
    # cross-axes — place and script (the orthographic axis), long tail trimmed
    for stype, col, w, floor in (("province", "provenance_province", 1.0, 25),
                                 ("temple", "provenance_temple", 1.0, 25),
                                 ("script", "script", 1.3, 10)):
        labels = wiki.SUBJECT[stype]["labels"]
        for r in conn.execute(f"SELECT {col} v, COUNT(*) n FROM manuscripts "
                              f"WHERE TRIM(COALESCE({col},''))<>'' GROUP BY v HAVING n>=? "
                              f"ORDER BY n DESC", (floor,)):
            v = r["v"]
            cands.append(_cand(conn, "axis", stype, v,
                               wiki.prettify(v, labels) if labels else v,
                               w, f"{col}=?", (v,)))
    return [c for c in cands if c]


def score_report(level_filter=None, as_json=False):
    if not wiki.db_present():
        print("  no catalog at", wiki.CATALOG_DB)
        return 1
    conn = wiki.connect()
    try:
        cands = enumerate_subjects(conn)
    finally:
        conn.close()
    if level_filter:
        cands = [c for c in cands if level_filter in (c["level"], c["stype"])]
    if as_json:
        print(json.dumps(cands, ensure_ascii=False, indent=2))
        return 0
    ready = sorted((c for c in cands if c["verdict"] == "ready"), key=lambda c: -c["score"])
    wanted = sorted((c for c in cands if c["verdict"] == "wanted"),
                    key=lambda c: -(c["importance"] / (c["availability"] + 0.1)))
    written = [c for c in cands if c["verdict"] == "written"]
    print(f"\n  SUBJECT SCORER  ·  {len(cands)} candidates  ·  "
          f"{len(written)} written · {len(ready)} ready · {len(wanted)} wanted\n")

    def show(c):
        star = "\u2605" if c["importance"] >= 2.0 else " "
        print(f"   {star} [{c['level']:<4}] imp {c['importance']:>4} \u00d7 avail "
              f"{c['availability']:>5} = {c['score']:>6}   n={c['count']:>4} "
              f"rich={c['richness']:<4}  {c['label']}")

    print("  READY TO WRITE  ·  by importance \u00d7 availability, high \u2192 low")
    for c in ready[:20]:
        show(c)
    if not ready:
        print("     (none)")
    print("\n  WANTED  ·  next crawl's targets — important but data-thin")
    for c in wanted[:20]:
        show(c)
    if not wanted:
        print("     (none)")
    print("\n  importance = curated thematic weight · availability = log-volume \u00d7 "
          "metadata richness.\n  L3 entity counts are heuristic title matches. "
          "Filter with --level (L1/L2/L3/province/temple/script).\n")
    return 0


def report():
    idx = wiki.articles_index()
    if not idx["dbPresent"]:
        print("  no catalog found at", os.environ["CATALOG_DB"])
        return 1
    arts = idx["articles"]
    authored = [a for a in arts if a["hasArticle"] and a["status"] == "published"]
    drafts = [a for a in arts if a["hasArticle"] and a["status"] != "published"]
    stubs = [a for a in arts if not a["hasArticle"]]
    print(f"\n  ARTICLE COVERAGE  ·  {len(authored)} written · {len(drafts)} draft · "
          f"{len(stubs)} stub  (of {len(arts)} genres)\n")
    sym = {"published": "✓ article", "draft": "~ draft  "}
    for a in arts:
        mark = sym.get(a["status"], "· stub   ") if a["hasArticle"] else "· stub   "
        star = "★" if a["priority"] else " "
        print(f"   {star} {mark}  {a['count']:>5}  {a['key']}")
        if not a["hasArticle"] and a["note"]:
            print(f"                        {a['note']}")
    if stubs:
        nxt = stubs[0]["key"]
        print(f"\n  next up (priority): {nxt}"
              f"\n  scaffold it with:   python3 articles.py --apply --draft {nxt}")
    print()
    return 0


def do_draft(keys, apply):
    wrote = skipped = 0
    for key in keys:
        stype, _, value = key.partition(":")
        art = wiki.build_article(stype, value) if value else None
        if not art:
            print(f"  ? unknown subject: {key}")
            continue
        path = wiki.content_path(stype, value)
        if path.exists():
            print(f"  · skip (exists)   {path.name}")
            skipped += 1
            continue
        text = draft_markdown(art)
        if apply:
            wiki.CONTENT.mkdir(exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(f"  + wrote          {path.name}  ({art['label']})")
            wrote += 1
        else:
            print(f"  would write      {path.name}  ({art['label']})")
            for line in text.splitlines()[:8]:
                print(f"        | {line}")
            print("        | …")
    if not apply:
        print("\n  (dry-run — nothing written. Add --apply to create the files.)")
    else:
        print(f"\n  done: {wrote} written, {skipped} skipped (already had prose).")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Report and scaffold wiki articles")
    ap.add_argument("--draft", metavar="TYPE:VALUE", action="append", default=[],
                    help="scaffold a stub for one subject, e.g. genre:astrology")
    ap.add_argument("--draft-missing", action="store_true",
                    help="scaffold every genre that has no prose yet")
    ap.add_argument("--apply", action="store_true", help="actually write files (else dry-run)")
    ap.add_argument("--score", action="store_true",
                    help="rank subjects at every level by importance \u00d7 availability")
    ap.add_argument("--json", action="store_true",
                    help="with --score: emit the ranked candidates as JSON")
    ap.add_argument("--level", help="with --score: filter to one level/axis "
                    "(L1, L2, L3, province, temple, script)")
    ap.add_argument("--db", help="path to catalog.db (overrides CATALOG_DB)")
    a = ap.parse_args(argv)

    if a.db:
        os.environ["CATALOG_DB"] = a.db
        wiki.CATALOG_DB = Path(a.db)

    if not wiki.db_present():
        print("  no catalog at", wiki.CATALOG_DB)
        return 1

    if a.score:
        return score_report(a.level, a.json)

    keys = list(a.draft)
    if a.draft_missing:
        idx = wiki.articles_index()
        keys += [x["key"] for x in idx["articles"] if not x["hasArticle"]]
    if keys:
        # de-dupe, keep order
        seen, ordered = set(), []
        for k in keys:
            if k not in seen:
                seen.add(k); ordered.append(k)
        return do_draft(ordered, a.apply)
    return report()


if __name__ == "__main__":
    raise SystemExit(main())
