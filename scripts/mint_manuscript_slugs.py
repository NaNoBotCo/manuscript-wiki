#!/usr/bin/env python3
"""mint_manuscript_slugs — one frozen, human-readable slug per manuscript.

The registry (data/slugs_manuscripts.json, {"<id>": "<slug>"}) is the single
source of URL truth for /m/ and /read/ pages. Rules, per
SLUGS_METADATA_PROPOSAL.md §2:

- Minted ONCE. An id already in the registry is never touched, even if its
  title later improves — a published URL is a promise. (--dry-run to preview.)
- Slug text: the ascii half of work_title (curated bilingual, "thai — English"),
  else title_english, else title_translit, else the genre; ascii-folded,
  lowercased, kebab-case, reader-useless stopwords dropped, capped ~60 chars at
  a word boundary. The final path component is always "<slug>-<id>" (uniqueness
  by construction; the bare "<slug>" stored here carries no id).
- Purely additive: this script appends new rows; build code only READS the
  registry and falls back to the numeric id when a row is absent, so a fresh
  crawl never breaks the build.

    python3 scripts/mint_manuscript_slugs.py            # mint missing rows
    python3 scripts/mint_manuscript_slugs.py --dry-run  # show, write nothing
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REGISTRY = HERE / "data" / "slugs_manuscripts.json"
DB = Path(
    __import__("os").environ.get(
        "CATALOG_DB",
        HERE.parent / "manuscript-crawler" / "crawler" / "catalog.db"))

STOP = {"a", "an", "the", "of", "and", "for", "with", "on", "in", "to",
        "untitled"}


def _ascii_half(work_title):
    """The English side of a 'ไทย — English' bilingual working title."""
    if not work_title:
        return ""
    for sep in (" — ", " – ", " - "):
        if sep in work_title:
            tail = work_title.split(sep, 1)[1]
            if re.search(r"[A-Za-z]", tail):
                return tail
    return work_title if re.search(r"[A-Za-z]", work_title) else ""


def slugify(text, max_len=60):
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    # single alpha letters are orphans of possessives/initials ("narai's" →
    # "narai","s"); digits stay — "vol 1" must survive as vol-1
    words = [w for w in re.split(r"[^a-z0-9]+", text)
             if w and w not in STOP and not (len(w) == 1 and w.isalpha())]
    out = ""
    for w in words:
        cand = (out + "-" + w) if out else w
        if len(cand) > max_len:
            break
        out = cand
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    registry = {}
    if REGISTRY.exists():
        registry = json.loads(REGISTRY.read_text())

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cols = {r[1] for r in conn.execute("PRAGMA table_info(manuscripts)")}
    wt = "work_title, " if "work_title" in cols else "'' AS work_title, "
    rows = conn.execute(
        f"SELECT id, {wt} title_english, title_translit, title_thai, "
        f"genre_normalized FROM manuscripts ORDER BY id").fetchall()

    taken = set(registry.values())
    minted, empty = 0, 0
    for r in rows:
        rid = str(r["id"])
        if rid in registry:
            continue
        base = (slugify(_ascii_half(r["work_title"]))
                or slugify(r["title_english"])
                or slugify(r["title_translit"])
                or slugify(r["genre_normalized"]))
        if not base:
            empty += 1        # stays numeric-only: "<id>" is still a fine path
            continue
        # the id suffix on the PATH already guarantees uniqueness; keeping the
        # stored slugs distinct too is belt-and-braces for anything that ever
        # uses the bare slug as a key
        slug, n = base, 2
        while slug in taken:
            slug, n = f"{base}-{n}", n + 1
        registry[rid] = slug
        taken.add(slug)
        minted += 1
        if a.dry_run and minted <= 40:
            print(f"  {rid} -> {slug}-{rid}")

    print(f"mint_manuscript_slugs: {minted} new, {len(registry)} total, "
          f"{empty} with no usable latin text (stay numeric)")
    if not a.dry_run:
        REGISTRY.parent.mkdir(exist_ok=True)
        REGISTRY.write_text(json.dumps(registry, indent=0, sort_keys=True) + "\n",
                            encoding="utf-8")
        print(f"  wrote {REGISTRY}")


if __name__ == "__main__":
    main()
