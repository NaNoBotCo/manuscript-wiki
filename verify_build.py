#!/usr/bin/env python3
"""verify_build — refuse to publish an incomplete site.

WHY THIS EXISTS
On 2026-07-22 a publish committed and pushed a build that was missing fifteen
directories — /moon, /hun, /support, /articles, /expedite and more. The build
printed "20 pages", reported ERRORS: 0, exited 0, and the commit removed 19,216
lines across 6,162 files. wichaa.net served a gutted site until the next run.

Nothing caught it because publish_site.sh commits whatever is sitting in docs/.
The build's own success message only means it reached the end, not that the
output is whole.

routes.py already declares every page this site is supposed to have. This walks
that list against what is actually on disk and exits non-zero if anything is
missing, so the publish stops BEFORE the commit rather than after the push.

    python3 verify_build.py --docs ../nanobotco-lanna/docs

RUN IT AFTER THE WHOLE PIPELINE, NOT AFTER build_static ALONE.
Several pages arrive in later stages — /glossary from glossary.py, /na from
na_gallery.py, /explore plus llms.txt, robots.txt, sitemap.xml and api/index.json
from site_meta.py. Checked straight after build_static those are legitimately
absent and this will cry wolf. publish_site.sh calls it in the right place:
immediately before `git add`, once everything has run.

Exit 0 = safe to commit. Exit 1 = do not publish, and it says what is absent.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import routes

# Written by other producers in the pipeline, not by PAGE_SPECS, but still
# expected in a finished build.
EXTRA_EXPECTED = (
    "api/index.json",
    "llms.txt",
    "robots.txt",
    "sitemap.xml",
    "index.html",
    # Phase A cartography (WAYFINDING_PLAN.md): the edge store the later phases
    # project from — a build without it is incomplete.
    "api/graph/nodes.jsonl",
    "api/graph/edges.jsonl",
    "api/graph/summary.json",
    "api/graph/audit.json",
    # Phase D: the trails index and its data (individual trail pages are a bulk
    # namespace — see routes.BULK_NAMESPACES — and are counted, not enumerated).
    "api/trails.json",
)

# A whole build is big. A build that collapses to a handful of files is the
# failure this script exists to catch, so treat a suspiciously small tree as
# an error even if every named route happens to be present.
MIN_HTML_PAGES = 25


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--docs", required=True, help="the built site directory")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    docs = Path(args.docs).resolve()
    if not docs.is_dir():
        print(f"verify: {docs} is not a directory", file=sys.stderr)
        return 1

    missing: list[str] = []

    for r in routes.ROUTES:
        if not (docs / r.file).is_file():
            missing.append(f"{r.path:<14} expected {r.file}"
                           + (f"  (built by {r.built_by})" if r.built_by != "specs" else ""))

    for extra in EXTRA_EXPECTED:
        if not (docs / extra).is_file():
            missing.append(f"{'(site file)':<14} expected {extra}")

    html_count = sum(1 for _ in docs.rglob("index.html"))

    if missing or html_count < MIN_HTML_PAGES:
        print("\nBUILD IS INCOMPLETE — refusing to publish.", file=sys.stderr)
        if missing:
            print(f"\n  {len(missing)} expected file(s) absent:", file=sys.stderr)
            for m in missing:
                print(f"    - {m}", file=sys.stderr)
        if html_count < MIN_HTML_PAGES:
            print(f"\n  only {html_count} index.html files found "
                  f"(expected at least {MIN_HTML_PAGES}) — the build looks truncated",
                  file=sys.stderr)
        print("\nNothing was committed. Two things to check, in order:", file=sys.stderr)
        print("  1. Did you run this after the FULL pipeline? /glossary, /na, /explore "
              "and\n     the site files land in later stages, not in build_static.",
              file=sys.stderr)
        print("  2. Was a second build running at the same time? build_static.py wipes "
              "docs/\n     at the start, so two concurrent runs destroy each other.",
              file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"verify: {len(routes.ROUTES)} declared routes present, "
              f"{html_count} pages — safe to publish")
    return 0


if __name__ == "__main__":
    sys.exit(main())
