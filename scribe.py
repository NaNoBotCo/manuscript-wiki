#!/usr/bin/env python3
"""scribe — propagate derived knowledge INTO the articles.

The curiosity bots notice patterns and file them as *findings* (the Discoveries
page). Until now that knowledge dead-ended there: the hand-authored articles in
content/*.md never received it. scribe closes the loop. For every subject that
already has an article, it gathers the findings that pertain to that subject and
writes them into the article as a clearly-labelled, machine-maintained block —

    <!-- derived:begin -->  …auto-written…  <!-- derived:end -->

The human prose OUTSIDE that block is never touched: scribe only ever rewrites
between the two markers (appending the block at the end of the body the first
time). So "the article already exists" becomes a reason to *enrich* it, not skip
it. Idempotent: re-running refreshes the block from the current findings.

    python3 scribe.py --dry-run             # show what every article would gain
    python3 scribe.py --only genre:astrology --dry-run
    python3 scribe.py                        # write the blocks (existing articles only)

Org chart: scribe is the SCRIBE tier — downstream of the NOTICERS (curiosity
bots). It reads findings, it writes articles. It does not crawl and it does not
invent: every line traces to a filed finding. See ../manuscript-crawler/BOTS.md.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Resolve the catalogue the same way build_static.py does, before importing wiki.
_db = HERE.parent / "manuscript-crawler" / "crawler" / "catalog.db"
if not _db.exists():
    _alt = HERE.parent / "crawler" / "catalog.db"
    if _alt.exists():
        _db = _alt
os.environ.setdefault("CATALOG_DB", str(_db))
os.environ.setdefault("STORE_DIR", str(Path(os.environ["CATALOG_DB"]).parent / "store"))

import wiki  # noqa: E402

BEGIN = "<!-- derived:begin -->"
END = "<!-- derived:end -->"
# The whole managed region, including the markers, matched non-greedily.
BLOCK_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)


def _load_findings() -> list[dict]:
    """Published curiosity findings as raw rows (title + markdown body), straight
    from the catalogue — findings_index() renders body to HTML, but the scribe wants
    the raw markdown for both matching and the one-line gloss."""
    if not wiki.db_present():
        return []
    conn = wiki.connect()
    try:
        rows = conn.execute(
            "SELECT slug, finding_type, finding_key, title, body_md, confidence "
            "FROM articles WHERE status='published' AND finding_key IS NOT NULL "
            "AND finding_key<>'' ORDER BY confidence DESC").fetchall()
    finally:
        conn.close()
    return [{"slug": r["slug"], "type": r["finding_type"], "key": r["finding_key"],
             "title": r["title"], "body_md": r["body_md"] or "",
             "confidence": r["confidence"] or 0} for r in rows]


def _first_sentence(md: str) -> str:
    """A one-line gloss from a finding body: first sentence, markdown/ής stripped."""
    text = re.sub(r"\s+", " ", md or "").strip()
    text = re.sub(r"[*_`#>]+", "", text)          # drop md emphasis/heading marks
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # [label](url) -> label
    m = re.search(r"(.+?[.!?])(\s|$)", text)
    out = (m.group(1) if m else text).strip()
    return out[:240]


def _name_candidates(subject: dict) -> list[str]:
    """The strings whose presence in a finding means the finding is *about* this
    subject. The subject value ('magic_ritual'), a spaced form ('magic ritual'),
    and the leading chunk of the display label ('Magic & ritual') before any
    '(', '·' or '›' qualifier."""
    cands = set()
    val = (subject.get("value") or "").strip()
    if val:
        cands.add(val)
        cands.add(val.replace("_", " "))
    label = (subject.get("label") or "").strip()
    if label:
        head = re.split(r"[(·›|/]", label)[0].strip()
        if head:
            cands.add(head)
    # keep only reasonably specific candidates to avoid spurious substring hits
    return [c.lower() for c in cands if len(c) >= 4]


# A finding that (loosely) mentions more subjects than this is treated as a
# corpus-wide observation: it attaches to a subject only when that subject is named
# in the finding's TITLE, not merely somewhere in the body. Keeps specific findings
# broad in reach while stopping a single "about the whole corpus" note from landing
# on a dozen articles on a stray body word.
BROAD_SUBJECT_THRESHOLD = 6


def _hit(subject: dict, f: dict) -> str | None:
    """'title' if a candidate name for the subject appears in the finding title,
    'body' if only in the body, else None."""
    cands = _name_candidates(subject)
    if not cands:
        return None
    title = (f.get("title") or "").lower()
    if any(c in title for c in cands):
        return "title"
    if any(c in (f.get("body_md") or "").lower() for c in cands):
        return "body"
    return None


def _match_map(subjects: list[dict], findings: list[dict]) -> dict:
    """{subject_key: [findings]} with the corpus-wide dampener applied."""
    grid = {}                              # (subject_key, finding_slug) -> 'title'|'body'
    per_finding = {}                       # finding_slug -> set(subject_key)
    for s in subjects:
        for f in findings:
            where = _hit(s, f)
            if where:
                grid[(s["key"], f["slug"])] = where
                per_finding.setdefault(f["slug"], set()).add(s["key"])
    out = {}
    for s in subjects:
        keep = []
        for f in findings:
            where = grid.get((s["key"], f["slug"]))
            if not where:
                continue
            broad = len(per_finding.get(f["slug"], ())) > BROAD_SUBJECT_THRESHOLD
            if broad and where != "title":
                continue                   # corpus-wide + only-body match -> drop
            keep.append(f)
        keep.sort(key=lambda f: (-(f.get("confidence") or 0), f.get("title") or ""))
        out[s["key"]] = keep
    return out


def _render_block(matched: list[dict]) -> str:
    """The managed markdown region. Empty match -> empty string (block removed)."""
    if not matched:
        return ""
    lines = [BEGIN,
             "## What the bots have noticed",
             "",
             "*Auto-derived from the catalogue and the curiosity bots — refreshed "
             "automatically, not hand-written. Each note links to its finding.*",
             ""]
    for f in matched:
        slug = f.get("slug") or ""
        title = (f.get("title") or "").strip()
        gloss = _first_sentence(f.get("body_md") or "")
        link = f"[see the finding →](/findings#{slug})" if slug else ""
        lines.append(f"- **{title}** — {gloss} {link}".rstrip())
    lines.append(END)
    return "\n".join(lines)


def _splice(md: str, block: str) -> str:
    """Replace the existing managed region, or append the block at the end. When
    block is empty, strip any existing region. Human prose is preserved verbatim."""
    if BLOCK_RE.search(md):
        if block:
            return BLOCK_RE.sub(lambda _: block, md).rstrip() + "\n"
        # remove stale block + the blank line(s) that preceded it
        return re.sub(r"\n*" + BLOCK_RE.pattern + r"\n*", "\n", md, flags=re.DOTALL).rstrip() + "\n"
    if not block:
        return md
    return md.rstrip() + "\n\n" + block + "\n"


def run(only: str | None, dry_run: bool) -> int:
    findings = _load_findings()
    subjects = wiki.articles_index().get("articles", [])
    if only:
        subjects = [s for s in subjects if s.get("key") == only]
        if not subjects:
            print(f"scribe: no subject with key {only!r}", file=sys.stderr)
            return 1

    match_map = _match_map(subjects, findings)
    changed = enriched = skipped = 0
    for s in subjects:
        stype, _, value = (s.get("key") or "").partition(":")
        path = wiki.content_path(stype, value)
        if not path.is_file():
            skipped += 1            # existing-articles-only: never create files here
            continue
        matched = match_map.get(s["key"], [])
        old = path.read_text(encoding="utf-8")
        block = _render_block(matched)
        new = _splice(old, block)
        if new == old:
            continue
        changed += 1
        if matched:
            enriched += 1
        label = s.get("label") or s.get("key")
        if dry_run:
            print(f"\n=== {label}  ({s['key']})  — {len(matched)} finding(s) ===")
            print(block or "(derived block would be removed — no matching findings)")
        else:
            path.write_text(new, encoding="utf-8")
            print(f"· {label}: {len(matched)} finding(s) propagated")

    verb = "would change" if dry_run else "changed"
    print(f"\nscribe: {verb} {changed} article(s) "
          f"({enriched} with findings), {skipped} subjects have no article file.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Propagate derived findings into articles")
    ap.add_argument("--only", default=None, help="a single subject key, e.g. genre:astrology")
    ap.add_argument("--dry-run", action="store_true", help="show changes, write nothing")
    a = ap.parse_args()
    return run(a.only, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
