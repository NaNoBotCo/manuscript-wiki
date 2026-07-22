#!/usr/bin/env python3
"""obsidian_export — make content/ a first-class Obsidian vault.

The authored articles ARE markdown files (content/*.md), so Obsidian can open that
folder as a vault directly — no sync layer, no copies: what you edit there is what
the wiki publishes. This exporter adds the two things a vault wants that the wiki
doesn't need:

  · content/_INDEX.md              a Map-of-Content: every article, grouped by type,
                                   wiki-linked, with status at a glance
  · content/Knowledge Graph.canvas the curated knowledge graph as an Obsidian canvas —
                                   nodes that HAVE an article are file-cards (click one
                                   and the article opens beside the canvas); nodes that
                                   don't yet are text-cards; edges carry their predicate

Both are regenerated whole each run (they carry a "generated" banner; hand-edits to
THESE TWO files don't survive — the articles themselves are never touched). Extract,
don't author: the canvas draws only the authored graph, the index only real files.

    python3 obsidian_export.py            # write both into content/
Then in Obsidian:  Open folder as vault →  manuscript-wiki/content
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_db = HERE.parent / "manuscript-crawler" / "crawler" / "catalog.db"
if _db.exists():
    os.environ.setdefault("CATALOG_DB", str(_db))
    os.environ.setdefault("STORE_DIR", str(_db.parent / "store"))

import wiki  # noqa: E402

CONTENT = HERE / "content"
BANNER = ("> [!info] Generated file\n"
          "> Built by `obsidian_export.py` from the catalogue + authored graph — "
          "re-running replaces it. Edit the *articles*, not this file.\n")

TYPE_LABELS = {"genre": "Genres", "entity": "Esoteric subjects (entities)",
               "subgenre": "Sub-genres", "temple": "Temples", "province": "Provinces"}


def frontmatter(p: Path) -> dict:
    meta = {}
    try:
        raw = p.read_text(encoding="utf-8")
    except Exception:
        return meta
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            for line in raw[3:end].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip()
    return meta


def key_to_file(key: str) -> Path | None:
    stype, _, value = key.partition(":")
    if not stype or not value:
        return None
    p = wiki.content_path(stype, value)
    return p if p.is_file() else None


def build_index() -> str:
    groups: dict[str, list[tuple[str, str, str]]] = {}
    for p in sorted(CONTENT.glob("*.md")):
        if p.name == "_INDEX.md":
            continue
        stype = p.stem.split("-", 1)[0]
        meta = frontmatter(p)
        title = meta.get("title", p.stem)
        status = meta.get("status", "published")
        groups.setdefault(stype, []).append((p.stem, title, status))
    lines = ["# Lanna Wiki — article vault", "", BANNER,
             "This folder is the *source of truth* for the wiki's authored prose. "
             "Blocks between `<!-- derived:begin -->` and `<!-- derived:end -->` are "
             "machine-maintained (the scribe refreshes them) — write above or below "
             "them, never inside.", "",
             "The knowledge graph lives beside this note as "
             "[[Knowledge Graph.canvas|Knowledge Graph]].", ""]
    for stype in ("entity", "genre", "subgenre", "temple", "province"):
        if stype not in groups:
            continue
        lines.append(f"## {TYPE_LABELS.get(stype, stype.title())}")
        lines.append("")
        for stem, title, status in groups[stype]:
            badge = "" if status == "published" else f"  ·  *{status}*"
            lines.append(f"- [[{stem}|{title}]]{badge}")
        lines.append("")
    return "\n".join(lines)


def build_canvas() -> dict:
    g = wiki.graph_export()
    nodes_in = g.get("nodes", [])
    links_in = g.get("links", [])
    n = max(len(nodes_in), 1)
    # One ring per node type, so the layout reads as taxonomy, not spaghetti:
    # entities inner, genres middle, everything else outer.
    ring = {"entity": 520, "genre": 900}
    default_r = 1240
    by_type: dict[str, list[dict]] = {}
    for nd in nodes_in:
        by_type.setdefault(nd.get("type", "?"), []).append(nd)
    nodes_out, pos = [], {}
    for t, members in by_type.items():
        r = ring.get(t, default_r)
        for i, nd in enumerate(members):
            ang = 2 * math.pi * i / len(members)
            x, y = int(r * math.cos(ang)), int(r * math.sin(ang))
            f = key_to_file(nd["key"])
            cid = nd["key"].replace(":", "_")
            pos[nd["key"]] = cid
            if f:
                nodes_out.append({"id": cid, "type": "file", "file": f.name,
                                  "x": x - 190, "y": y - 130, "width": 380, "height": 260})
            else:
                nodes_out.append({"id": cid, "type": "text",
                                  "text": f"**{nd.get('label', nd['key'])}**\n`{nd['key']}` — no article yet",
                                  "x": x - 150, "y": y - 50, "width": 300, "height": 100})
    edges_out = []
    for i, ln in enumerate(links_in):
        s, o = pos.get(ln.get("s")), pos.get(ln.get("o"))
        if not s or not o:
            continue
        edges_out.append({"id": f"e{i}", "fromNode": s, "toNode": o,
                          "fromSide": "bottom", "toSide": "top",
                          "label": ln.get("p", "").replace("_", " ")})
    return {"nodes": nodes_out, "edges": edges_out}


def main() -> int:
    if not CONTENT.is_dir():
        print(f"obsidian_export: no content/ at {CONTENT}", file=sys.stderr)
        return 1
    (CONTENT / "_INDEX.md").write_text(build_index(), encoding="utf-8")
    canvas = build_canvas()
    (CONTENT / "Knowledge Graph.canvas").write_text(
        json.dumps(canvas, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"obsidian_export: _INDEX.md + Knowledge Graph.canvas "
          f"({len(canvas['nodes'])} nodes, {len(canvas['edges'])} edges) → {CONTENT}")
    print("Open in Obsidian:  Open folder as vault →  manuscript-wiki/content")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
