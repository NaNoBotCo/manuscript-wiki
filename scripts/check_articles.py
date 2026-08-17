#!/usr/bin/env python3
"""check_articles — validate the authored prose in content/ before it ships.

WHY THIS EXISTS
Articles are hand-written markdown rendered by wiki.md_to_html(), a deliberately
tiny subset. Two failure modes are silent and were both found in the wild:

  · a link whose first path segment is not a real route is DELETED — the anchor
    text survives, so "the [prices widget](/w/prices)" ships as plain words and
    nothing anywhere says the link is gone. (/w, /glossary, /na, /need … were all
    in this state until the allowlist was derived from routes.py.)
  · a "> " blockquote renders as a literal ">" character mid-sentence, because
    md_to_html has no blockquote rule.

Neither breaks the build, so neither was ever noticed at build time. This walks
every article and reports them, plus the things a writer can get wrong that only
a query can catch: a /m/ or /place/ link to a page that does not exist, an
entity/genre key that is not registered, a manuscript id cited in prose that is
not in the catalogue.

It is a REPORTER, not a gate: prose problems should not stop a publish. Exit code
is 1 only when a link target is provably missing, so CI can choose to care.

Usage:
    python3 scripts/check_articles.py
    python3 scripts/check_articles.py --docs ../nanobotco-lanna/docs
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import wiki  # noqa: E402

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
# "1. " / "12) " at line start — markdown ordered list, which md_to_html does not
# implement. Deliberately anchored and space-terminated so prose like "2026." or a
# citation "(1)" does not trip it.
_ORDERED_LI_RE = re.compile(r"^\d{1,2}[.)] +\S")
# "ms 6964", "manuscript 6964", "id 6964" — a claim a reader could check
MSID_RE = re.compile(r"\b(?:ms|manuscript|id)\.?\s+(\d{3,4})\b", re.I)


def load_articles():
    for p in sorted((HERE / "content").glob("*.md")):
        if p.name.startswith("_"):
            continue
        yield p, p.read_text(encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default=str(HERE.parent / "nanobotco-lanna" / "docs"),
                    help="built site, for verifying /m/ and /place/ targets exist")
    args = ap.parse_args()
    docs = Path(args.docs)

    roots = wiki._link_roots()
    entities = {e[0] for e in wiki.ENTITIES}
    conn = wiki.connect() if wiki.db_present() else None
    genres, msids = set(), set()
    if conn is not None:
        genres = {r["v"] for r in conn.execute(
            "SELECT DISTINCT genre_normalized v FROM manuscripts WHERE genre_normalized<>''")}
        msids = {r["id"] for r in conn.execute("SELECT id FROM manuscripts")}

    have_m = {p.name for p in (docs / "m").iterdir()} if (docs / "m").is_dir() else set()
    have_place = {p.name for p in (docs / "place").iterdir()} if (docs / "place").is_dir() else set()

    # Temple names repeat across provinces — there is a Wat Sung Men in Lampang
    # AND the famous manuscript library of the same name in Phrae, and only one
    # of them has a page. A slug that merely EXISTS is therefore not evidence the
    # link is right, so report which province each linked page actually names and
    # let a human match it against the manuscript being cited. (This caught a real
    # error: an article citing Phrae witnesses linked the Lampang temple.)
    PROVINCES = ("Chiang Mai", "Chiang Rai", "Lamphun", "Lampang", "Phrae",
                 "Nan", "Phayao", "Mae Hong Son")

    def place_province(slug):
        """The page's OWN declared region (schema.org addressRegion), not the first
        province name that happens to appear in the markup — a naive scan reads
        whatever a nearby-temples list mentions first and is wrong more often than
        it is right. Note the declared region is not itself trustworthy everywhere:
        the place layer currently files all 57 Phrae temples under Lampang, so a
        Phrae mismatch here means the DATA is wrong, not necessarily the link."""
        f = docs / "place" / slug / "index.html"
        if not f.is_file():
            return None
        txt = f.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'"addressRegion"\s*:\s*"([^"]*)"', txt)
        if m:
            reg = m.group(1)
            # จังหวัดX in the Thai description is the temple's own statement of
            # where it is, and beats the metadata when the two disagree.
            m2 = re.search(r"จังหวัด(\S{2,12}?)[\s\"<.,]", txt)
            if m2 and m2.group(1) not in reg:
                return f"{reg} (desc says จังหวัด{m2.group(1)})"
            return reg
        for p in PROVINCES:
            if p in txt:
                return p
        return "?"

    place_links = []

    problems, stats = [], []
    for path, raw in load_articles():
        name = path.name
        add = lambda kind, detail: problems.append((kind, name, detail))  # noqa: E731

        body = raw.split("\n---", 1)[-1] if raw.startswith("---") else raw
        if not raw.startswith("---") or "title:" not in raw.split("\n---")[0]:
            add("frontmatter", "missing or malformed --- title: --- block")

        prev_blank = True
        for ln in body.splitlines():
            stripped = ln.lstrip()
            if stripped.startswith(">"):
                add("blockquote", f"renders as a literal '>': {ln.strip()[:70]}")
            # Same silent class as the blockquote: md_to_html has no table rule and
            # no ordered-list rule, so a pipe table and a "1. " list both collapse
            # into one run-on paragraph with the markup showing. Found in the wild
            # authoring entity-ma.md — a 12-row zodiac table shipped as one line of
            # pipes. Use "- " bullets with the number bolded inline instead.
            if stripped.startswith("|") or set(stripped) <= set("|-: ") and "|" in stripped:
                add("table", f"no table rule — renders as literal pipes: {ln.strip()[:70]}")
            # Only at the top of a block: mid-paragraph a wrapped line can begin
            # with a number and a period ("…and Chiang Mai\n64. **89 of…"), which is
            # prose, not a list. Requiring a preceding blank line separates them.
            if prev_blank and _ORDERED_LI_RE.match(stripped):
                add("ordered-list", f"no <ol> rule — collapses into a paragraph: {ln.strip()[:70]}")
            prev_blank = not stripped

        links = LINK_RE.findall(body)
        for text, href in links:
            if href.startswith(("http://", "https://")):
                continue
            if not href.startswith("/"):
                add("dropped-link", f"[{text[:30]}]({href}) — not absolute, will be deleted")
                continue
            seg = href.lstrip("/").split("?")[0].split("#")[0].split("/")[0]
            if seg not in roots:
                add("dropped-link", f"[{text[:30]}]({href}) — /{seg} is not a route, will be deleted")
                continue
            parts = href.strip("/").split("/")
            if seg == "m" and len(parts) > 1 and have_m and parts[1] not in have_m:
                add("missing-target", f"{href} — no such manuscript page")
            if seg == "place" and len(parts) > 1 and have_place:
                if parts[1] not in have_place:
                    add("missing-target", f"{href} — no such place page")
                else:
                    place_links.append((name, parts[1], place_province(parts[1])))
            if href.startswith("/a?s=entity:"):
                k = href.split("entity:", 1)[1].split("&")[0]
                if k not in entities:
                    add("missing-target", f"{href} — '{k}' is not in wiki.ENTITIES")
            if href.startswith("/a?s=genre:"):
                k = href.split("genre:", 1)[1].split("&")[0]
                if genres and k not in genres:
                    add("missing-target", f"{href} — '{k}' is not a genre in the catalogue")

        for mid in MSID_RE.findall(body):
            if msids and int(mid) not in msids:
                add("bad-ms-id", f"cites manuscript {mid}, which is not in the catalogue")

        stats.append((name, len(raw), len(links)))

    if conn is not None:
        conn.close()

    print(f"{len(stats)} articles · "
          f"{sum(s[1] for s in stats)/1024:.0f} KB prose · "
          f"{sum(s[2] for s in stats)} internal links\n")
    for name, size, nlinks in sorted(stats, key=lambda s: -s[2]):
        print(f"  {name:<50} {size/1024:5.1f} KB  {nlinks:3d} links")

    if place_links:
        print("\nplace links — check each province against the manuscript cited:")
        for name, slug, prov in sorted(set(place_links)):
            print(f"  {name:<44} /place/{slug}/  → {prov}")

    if not problems:
        print("\n✓ no problems found")
        return 0
    print(f"\n{len(problems)} problem(s):")
    for kind, name, detail in sorted(problems):
        print(f"  [{kind}] {name}: {detail}")
    fatal = {"missing-target", "bad-ms-id"}
    return 1 if any(k in fatal for k, _, _ in problems) else 0


if __name__ == "__main__":
    sys.exit(main())
