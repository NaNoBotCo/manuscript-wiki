#!/usr/bin/env python3
"""cartography — Phase A of the wayfinding overhaul: the corpus-scale edge store.

WHY THIS EXISTS (WAYFINDING_PLAN.md, ADR-002, accepted 2026-07-22)
The site's graph machinery was boutique: relations.json (22 authored triples) +
per-article see_also, covering ~33 subject nodes while the corpus holds ~22,000
addressable things. Navigation, breadcrumbs, related-strips, trails and the Atlas
are all planned as PROJECTIONS of one knowledge graph — this module builds that
graph, at build time, from data that already exists. It writes nothing visible;
it gives the bots (and later phases) something to traverse.

THE MODEL
  Node  {id, cls, label, …small attrs}
    ms:<id>           manuscripts                (catalog.db manuscripts)
    item:<id>         market/museum/shrine items (catalog.db items)
    place:<slug>      wats & sacred places       (data/wats.geojson, vault-compiled)
    term:<term_raw>   tagged vocabulary          (catalog.db tags)
    finding:<slug>    curiosity-bot findings     (catalog.db articles, published)
    page:<path>       site pages                 (routes.py registry)
    tradition:<name>  the top axis               (taxonomy.tradition_of)
    entity:/genre:/subgenre:/language:/script:/province:/temple:/material:/era:<v>
                      subject & axis nodes — SAME keys wiki.py already uses, so
                      relations.json and article see_also plug in unchanged.

  Edge  {src, dst, type, prov, w, ev}
    prov — the seam extended to relationships (project_seamless_corpus):
      authored     a human wrote it   (relations.json, see_also, vault wikilinks,
                                       vault walk_cluster)
      adjudicated  a resolver ruled   (taxonomy entity resolvers — phra_rahu rule,
                                       fail-closed; never substring)
      computed     structure says so  (catalogue columns via taxonomy normalizers,
                                       tags, geo proximity, title-alias matches)
      derived      a bot noticed it   (propose_edges co-occurrence counts,
                                       curiosity findings)
    w  — raw count where one exists (shared records, metres), else 1.
    ev — short human-readable receipt ("7 shared manuscripts", "title contains
         'ruesi'", "312 m apart"). Verbatim data and counts only — extract,
         don't author. NEVER a path, NEVER an LLM-prior claim.

  Scale strategy: entities connect to VALUE NODES (ms→genre:astrology), never
  pairwise to each other (that's O(n²)); sparse entity↔entity edges exist only
  where a natural key makes them (geo proximity top-K, co-occurrence over
  thresholds, authored links). Per-item "threads" ranking is Phase B's job.

  Determinism: nodes sorted by id, edges by (src, type, dst), no timestamps in
  the jsonl — so an unchanged catalogue rebuilds byte-identical files and the
  nightly publish (publish_site.sh) sees no phantom churn.

OUTPUTS (written by build_static.py into docs/api/graph/)
  nodes.jsonl   one node per line
  edges.jsonl   one edge per line
  summary.json  counts by class and by type×provenance — the acceptance artifact
  audit.json    orphans, dead-ends, isolates, components  (+ /graph-audit page)

    python3 cartography.py                    # build + print the summary
    python3 cartography.py --out /tmp/graph   # also write the four files
    python3 cartography.py --audit-docs DIR   # + link-walk a built site

Stdlib only. Read-only against every source. Fail-soft: a missing sibling
(vault, propose_edges) degrades to fewer edges, never to a crash.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent

# Resolve the catalogue exactly the way build_static.py does, BEFORE importing
# wiki (wiki reads the environment at import time). Harmless when build_static
# already did it (setdefault), necessary when run standalone.
_default_db = HERE.parent / "manuscript-crawler" / "crawler" / "catalog.db"
if not _default_db.exists():
    _alt = HERE.parent / "crawler" / "catalog.db"
    if _alt.exists():
        _default_db = _alt
os.environ.setdefault("CATALOG_DB", str(_default_db))
os.environ.setdefault("STORE_DIR", str(Path(os.environ["CATALOG_DB"]).parent / "store"))

import routes    # noqa: E402
import taxonomy  # noqa: E402
import wiki      # noqa: E402  (env must be set first)

VAULT_DIR = Path(os.environ.get("WICHAA_VAULT",
                                HERE.parent / "wichaa-vault"))
WATS_GEOJSON = HERE / "data" / "wats.geojson"

# Display strings for the NEW edge types, same shape as wiki.RELATIONS
# (forward reading, reverse reading). Authored predicates from relations.json
# keep their wiki.RELATIONS displays; the union is exported in summary.json so
# Phase B chrome can name every relation it renders.
TYPES = {
    "in_tradition":      ("in the tradition of", "tradition of"),
    "in_genre":          ("in the genre",        "genre of"),
    "in_subgenre":       ("in the sub-genre",    "sub-genre of"),
    "in_language":       ("written in",          "language of"),
    "in_script":         ("written in script",   "script of"),
    "from_province":     ("from",                "provenance of"),
    "held_at":           ("held at",             "holds"),
    "on_material":       ("written on",          "material of"),
    "in_era":            ("dated in era",        "era of"),
    "about":             ("about",               "appears in"),
    "carries_term":      ("carries the term",    "carried by"),
    "near":              ("near",                "near"),
    "of_type":           ("of type",             "type of"),
    "same_walk_cluster": ("same walking cluster", "same walking cluster"),
    "concerns":          ("concerns",            "noticed in a finding"),
    "cites":             ("cites",               "cited by a finding"),
}

# Structural-membership types: a node whose ONLY edges are these is a dead-end
# in the wandering sense (it belongs to shelves, but connects to nothing).
AXIS_TYPES = {"in_tradition", "in_genre", "in_subgenre", "in_language",
              "in_script", "from_province", "held_at", "on_material",
              "in_era", "of_type"}

_MAX_LABEL = 140


def _label(*candidates, fallback=""):
    for c in candidates:
        if c and str(c).strip():
            s = " ".join(str(c).split())
            return s[:_MAX_LABEL]
    return fallback


class Graph:
    """Accumulator with dedup: one node per id, one edge per (src, dst, type) —
    the strongest provenance wins a collision (authored > adjudicated >
    computed > derived is NOT a strength order for facts, but for display
    priority; we keep the first-seen prov and the max weight)."""

    def __init__(self):
        self.nodes = {}                 # id -> dict
        self.edges = {}                 # (src, dst, type) -> dict

    def node(self, nid, cls, label, **attrs):
        n = self.nodes.get(nid)
        if n is None:
            n = {"id": nid, "cls": cls, "label": label}
            self.nodes[nid] = n
        for k, v in attrs.items():
            if v not in (None, "", 0, False):
                n[k] = v
        return n

    def edge(self, src, dst, type_, prov, w=1, ev=""):
        if src == dst:
            return
        key = (src, dst, type_)
        e = self.edges.get(key)
        if e is None:
            e = {"src": src, "dst": dst, "type": type_, "prov": prov, "w": w}
            if ev:
                e["ev"] = ev
            self.edges[key] = e
        else:
            if w > e.get("w", 1):
                e["w"] = w
                if ev:
                    e["ev"] = ev

    def degree(self):
        d = defaultdict(int)
        for (s, t, _t2) in self.edges:
            d[s] += 1
            d[t] += 1
        return d

    def by_src(self):
        """{src: [edge, …]}, built once and cached. threads_for() is called per
        node across the whole corpus, and a linear scan of ~119k edges each time
        would make the build quadratic — this keeps it linear overall. Invalidate
        by deleting _by_src if edges are added after the first call."""
        idx = getattr(self, "_by_src", None)
        if idx is None:
            idx = defaultdict(list)
            for e in self.edges.values():
                idx[e["src"]].append(e)
            self._by_src = idx
        return idx


# ---------------------------------------------------------------- subject layer
def subject_layer(g, conn):
    """The existing boutique graph, absorbed whole: relations.json triples and
    every article's see_also — the authored tier. Subject/axis node labels come
    from wiki.node_label so they match the live site everywhere."""
    n_rel = 0
    for s, p, o in wiki.authored_edges(conn):
        for k in (s, o):
            cls = k.partition(":")[0]
            g.node(k, cls, _label(wiki.node_label(k), fallback=k))
        g.edge(s, o, p, "authored")
        n_rel += 1
    return n_rel


# ------------------------------------------------------------- manuscript layer
def manuscript_layer(g, conn):
    """One pass over all manuscripts: node + axis edges via the taxonomy
    normalizers (computed), entity title-alias matches (computed, with the
    matched alias as the receipt), and adjudicated entity resolution
    (phra_rahu — the rule, never the substring)."""
    ent_variants = [(e[0], e[3]) for e in wiki.ENTITIES]
    rows = conn.execute(
        "SELECT id, source_id, title_thai, title_translit, title_english, "
        "language, script, genre_raw, genre_normalized, material, "
        "provenance_temple, provenance_province, date_text, date_ce_estimate "
        "FROM manuscripts").fetchall()
    for r in rows:
        mid = f"ms:{r['id']}"
        g.node(mid, "ms",
               _label(r["title_english"], r["title_translit"], r["title_thai"],
                      fallback=f"manuscript #{r['id']}"),
               date=r["date_ce_estimate"] or None)

        trad = taxonomy.tradition_of(r["source_id"])
        g.node(f"tradition:{trad}", "tradition",
               taxonomy.TRADITION_LABELS.get(trad, trad))
        g.edge(mid, f"tradition:{trad}", "in_tradition", "computed")

        if r["genre_normalized"]:
            k = f"genre:{r['genre_normalized']}"
            g.node(k, "genre", _label(wiki.node_label(k)))
            g.edge(mid, k, "in_genre", "computed")
        sub = taxonomy.subgenre(r["genre_raw"])
        if sub and r["genre_normalized"]:
            k = f"subgenre:{r['genre_normalized']}:{r['genre_raw']}"
            g.node(k, "subgenre", _label(wiki.node_label(k)))
            g.edge(mid, k, "in_subgenre", "computed")
        for lang in taxonomy.language_components(r["language"]):
            k = f"language:{lang}"
            g.node(k, "language", taxonomy.LANGUAGE_LABELS.get(lang, lang))
            g.edge(mid, k, "in_language", "computed")
        if r["script"]:
            k = f"script:{r['script']}"
            g.node(k, "script", _label(wiki.node_label(k)))
            g.edge(mid, k, "in_script", "computed")
        prov = taxonomy.resolve_province(r["provenance_province"])
        if prov:
            k = f"province:{prov}"
            g.node(k, "province", prov)
            g.edge(mid, k, "from_province", "computed")
        if r["provenance_temple"]:
            k = f"temple:{r['provenance_temple']}"
            g.node(k, "temple", r["provenance_temple"])
            g.edge(mid, k, "held_at", "computed")
        if r["material"]:
            k = f"material:{r['material']}"
            g.node(k, "material", _label(wiki.node_label(k)))
            g.edge(mid, k, "on_material", "computed")
        era = taxonomy.era_of(r["date_text"])
        if era:
            k = f"era:{era}"
            g.node(k, "era", taxonomy.ERA_LABELS.get(era, era))
            g.edge(mid, k, "in_era", "computed")

        # entity matches: alias substring over the coalesced title (computed,
        # receipt = the alias that hit) — mirrors wiki's _ENTITY_TITLE heuristic
        title = " ".join(filter(None, (r["title_english"], r["title_translit"],
                                       r["title_thai"]))).lower()
        if title:
            for key, variants in ent_variants:
                for v in variants:
                    if v in title:
                        g.edge(mid, f"entity:{key}", "about", "computed",
                               ev=f"title contains ‘{v}’")
                        break
        # adjudicated: the Rahu rule (fails closed when the rule module is away)
        for ekey in taxonomy.entity_keys(r):
            k = f"entity:{ekey}"
            g.node(k, "entity", _label(wiki.node_label(k)))
            g.edge(mid, k, "about", "adjudicated", ev="entity resolver rule")
    return len(rows)


# ------------------------------------------------------------------- item layer
def item_layer(g, conn):
    rows = conn.execute(
        "SELECT id, source_id, kind, method, title_thai, title_translit, "
        "title_english, dead_since FROM items").fetchall()
    for r in rows:
        iid = f"item:{r['id']}"
        g.node(iid, "item",
               _label(r["title_english"], r["title_thai"], r["title_translit"],
                      fallback=f"item #{r['id']}"),
               dead=1 if r["dead_since"] else 0)
        trad = taxonomy.tradition_of(r["source_id"], r["method"] or "")
        g.node(f"tradition:{trad}", "tradition",
               taxonomy.TRADITION_LABELS.get(trad, trad))
        g.edge(iid, f"tradition:{trad}", "in_tradition", "computed")
        if r["kind"]:
            k = f"kind:{r['kind']}"
            g.node(k, "kind", r["kind"].replace("-", " ").replace("_", " "))
            g.edge(iid, k, "of_type", "computed")
    return len(rows)


# -------------------------------------------------------------------- tag layer
def tag_layer(g, conn):
    n = 0
    for r in conn.execute(
            "SELECT manuscript_id, item_id, term_raw, topic FROM tags "
            "WHERE term_raw IS NOT NULL AND term_raw<>''").fetchall():
        t = f"term:{r['term_raw']}"
        g.node(t, "term", r["term_raw"], topic=r["topic"] or None)
        src = None
        if r["manuscript_id"] is not None:
            src = f"ms:{r['manuscript_id']}"
        elif r["item_id"] is not None:
            src = f"item:{r['item_id']}"
        if src and src in g.nodes:
            g.edge(src, t, "carries_term", "computed",
                   ev=(r["topic"] or ""))
            n += 1
    return n


# ------------------------------------------------------------------ place layer
def _haversine_m(lat1, lng1, lat2, lng2):
    rl1, rl2 = math.radians(lat1), math.radians(lat2)
    dlat = rl2 - rl1
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(rl1) * math.cos(rl2) * math.sin(dlng / 2) ** 2)
    return 2 * 6371000 * math.asin(math.sqrt(a))


def place_layer(g, near_m=1200, near_k=3):
    """Places from the vault-compiled wats.geojson: nodes + province/type
    membership + geo-proximity edges (top-K neighbours within near_m metres,
    receipt = the distance). Proximity is a fact of coordinates — computed."""
    data = wiki.load_json(WATS_GEOJSON, None)
    if not isinstance(data, dict):
        return 0
    places = list(data.get("wats") or []) + list(data.get("sacred") or [])
    sacred_ids = {p.get("id") for p in (data.get("sacred") or [])}
    pts = []
    for p in places:
        pid = p.get("id")
        if not pid:
            continue
        nid = f"place:{pid}"
        g.node(nid, "place", _label(p.get("name"), p.get("nameRoman"),
                                    fallback=pid),
               sacred=1 if pid in sacred_ids else 0,
               heritage=1 if p.get("heritage") else 0)
        if p.get("province"):
            k = f"province:{p['province']}"
            g.node(k, "province", p["province"])
            g.edge(nid, k, "from_province", "computed")
        ptype = p.get("type") or ""
        if ptype:
            k = f"ptype:{ptype}"
            g.node(k, "ptype", _label(p.get("typeEn"), ptype))
            g.edge(nid, k, "of_type", "computed")
        lat, lng = p.get("lat"), p.get("lng")
        if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
            pts.append((nid, lat, lng))

    # proximity: grid-bucket (~1.1 km cells) then exact haversine, top-K per
    # place; pair emitted once (a<b) so `near` reads the same from both ends
    grid = defaultdict(list)
    for nid, lat, lng in pts:
        grid[(int(lat * 100), int(lng * 100))].append((nid, lat, lng))
    pairs = {}
    for nid, lat, lng in pts:
        cx, cy = int(lat * 100), int(lng * 100)
        cand = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cand.extend(grid.get((cx + dx, cy + dy), ()))
        near = []
        for oid, olat, olng in cand:
            if oid == nid:
                continue
            d = _haversine_m(lat, lng, olat, olng)
            if d <= near_m:
                near.append((d, oid))
        near.sort()
        for d, oid in near[:near_k]:
            a, b = sorted((nid, oid))
            prev = pairs.get((a, b))
            if prev is None or d < prev:
                pairs[(a, b)] = d
    for (a, b), d in pairs.items():
        g.edge(a, b, "near", "computed", w=int(d), ev=f"{int(d)} m apart")
    return len(places)


def place_threads(near_m=1200, near_k=3):
    """Per-place lateral threads for the place-page builder (Phase B):
    {slug: [{'to', 'label', 'rel', 'note'}]} — walk-cluster siblings first
    (authored, when the vault says so), then geo-proximity, and for a place
    with no neighbour inside near_m, the single NEAREST place regardless of
    distance — so no place page is ever a dead end. Distances are receipts."""
    g = Graph()
    place_layer(g, near_m=near_m, near_k=near_k)
    vault_layer(g)
    out = defaultdict(list)
    for e in g.edges.values():
        rel = {"near": "near", "same_walk_cluster": "same_walk"}.get(e["type"])
        if not rel:
            continue
        note = (f"{e['w']} m" if rel == "near" else
                e.get("ev", "").replace("walk cluster ", ""))
        for a, b in ((e["src"], e["dst"]), (e["dst"], e["src"])):
            out[a.split(":", 1)[1]].append(
                {"to": b.split(":", 1)[1], "label": g.nodes[b]["label"],
                 "rel": rel, "note": note,
                 "_w": 0 if rel == "same_walk" else e["w"]})
    # nearest-fallback for isolated places
    data = wiki.load_json(WATS_GEOJSON, {}) or {}
    pts = [(p["id"], p["lat"], p["lng"], p.get("name") or p.get("nameRoman") or p["id"])
           for p in list(data.get("wats") or []) + list(data.get("sacred") or [])
           if p.get("id") and isinstance(p.get("lat"), (int, float))
           and isinstance(p.get("lng"), (int, float))]
    have = set(out)
    for pid, lat, lng, _name in pts:
        if pid in have:
            continue
        best = None
        for oid, olat, olng, oname in pts:
            if oid == pid:
                continue
            d = _haversine_m(lat, lng, olat, olng)
            if best is None or d < best[0]:
                best = (d, oid, oname)
        if best:
            km = best[0] / 1000
            out[pid].append({"to": best[1], "label": best[2], "rel": "nearest",
                             "note": f"{km:.1f} km", "_w": int(best[0])})
    for pid in out:
        out[pid].sort(key=lambda t: t["_w"])
        for t in out[pid]:
            t.pop("_w", None)
    return dict(out)


# ------------------------------------------------------------------ vault layer
_FM_LINE = re.compile(r"^([a-z_]+):\s*(.*)$")
_WIKILINK = re.compile(r"\[\[([^\]|#]+)")


def _frontmatter_scalars(text):
    """The scalar frontmatter keys of one vault note — a deliberate subset
    parser (id, walk_cluster, story_hook), not YAML. The vault schema keeps
    these as plain quoted-or-bare strings on one line."""
    out = {}
    if not text.startswith("---"):
        return out
    for line in text.split("\n---", 1)[0].splitlines()[1:]:
        m = _FM_LINE.match(line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return out


def vault_layer(g):
    """Authored place knowledge, straight from the Obsidian vault: walk_cluster
    groups become same_walk_cluster cliques, body [[wikilinks]] become
    related_to edges (targets resolved by exact place id only), story_hook
    presence is marked on the node. All of this is empty today — the layer is
    the SOCKET the vault plugs into the moment a human writes there
    (WAYFINDING_PLAN.md, the Obsidian round-trip)."""
    places_dir = VAULT_DIR / "places"
    if not places_dir.is_dir():
        return {"notes": 0, "clusters": 0, "wikilinks": 0}
    clusters = defaultdict(list)
    n_links = 0
    notes = sorted(places_dir.glob("*.md"))
    for f in notes:
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        fm = _frontmatter_scalars(text)
        pid = fm.get("id") or f.stem
        nid = f"place:{pid}"
        if nid not in g.nodes:
            continue
        if fm.get("walk_cluster"):
            clusters[fm["walk_cluster"]].append(nid)
        if fm.get("story_hook"):
            g.nodes[nid]["story"] = 1
        body = text.split("\n---", 1)[-1]
        for target in _WIKILINK.findall(body):
            tid = f"place:{target.strip()}"
            if tid in g.nodes and tid != nid:
                g.edge(nid, tid, "related_to", "authored", ev="vault wikilink")
                n_links += 1
    for cname, members in clusters.items():
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                x, y = sorted((a, b))
                g.edge(x, y, "same_walk_cluster", "authored",
                       ev=f"walk cluster ‘{cname}’")
    return {"notes": len(notes), "clusters": len(clusters),
            "wikilinks": n_links}


# --------------------------------------------------------------- finding layer
def finding_layer(g, conn):
    """Published curiosity findings become nodes; each links to the subject it
    concerns (derived — a bot noticed it, receipt = its confidence) and cites
    the records in its evidence lists where those are recognisable ids."""
    try:
        rows = conn.execute(
            "SELECT slug, finding_type, finding_key, title, confidence, "
            "evidence_json FROM articles WHERE status='published'").fetchall()
    except Exception:
        return 0
    for r in rows:
        fid = f"finding:{r['slug']}"
        g.node(fid, "finding", _label(r["title"], fallback=r["slug"]),
               ftype=r["finding_type"] or None,
               confidence=r["confidence"] or None)
        key = r["finding_key"] or ""
        target = None
        if ":" in key:
            target = key
        elif key and f"term:{key}" in g.nodes:
            target = f"term:{key}"
        if target:
            if target not in g.nodes:
                cls = target.partition(":")[0]
                g.node(target, cls, _label(wiki.node_label(target),
                                           fallback=target))
            g.edge(fid, target, "concerns", "derived",
                   ev=f"confidence {r['confidence']}" if r["confidence"] else "")
        try:
            ev = json.loads(r["evidence_json"] or "{}")
        except Exception:
            ev = {}
        for lname, lst in ev.items():
            if not isinstance(lst, list):
                continue
            pref = ("ms" if "manuscript" in lname
                    else "item" if ("item" in lname or "listing" in lname)
                    else None)
            if not pref:
                continue
            for v in lst[:24]:
                if isinstance(v, int) or (isinstance(v, str) and v.isdigit()):
                    rid = f"{pref}:{int(v)}"
                    if rid in g.nodes:
                        g.edge(fid, rid, "cites", "derived", ev=lname)
    return len(rows)


# --------------------------------------------------------------- proposed layer
def _load_propose_edges():
    """The crawler's propose_edges module, file-loaded off its path (never via
    sys.path — the crawler's http.py would shadow stdlib http; same technique
    and reasoning as taxonomy._load_rahu_rule). None when the sibling is away."""
    candidates = [HERE.parent / "manuscript-crawler" / "propose_edges.py"]
    env_db = os.environ.get("CATALOG_DB")
    if env_db:
        candidates.append(Path(env_db).resolve().parent.parent / "propose_edges.py")
    for path in candidates:
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("_wichaa_propose_edges", path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules["_wichaa_propose_edges"] = mod
            spec.loader.exec_module(mod)
            return mod
        except Exception:
            sys.modules.pop("_wichaa_propose_edges", None)
            return None
    return None


def proposed_layer(g, min_ms=2, min_market=6):
    """Term↔term co-occurrence, computed by the T4b bot's own code so the two
    can never drift: every weight is a shared-record COUNT, never an inferred
    relationship (extract-don't-author, verbatim from propose_edges.py). The
    corpus↔market echo terms get their per-side counts stamped on the node —
    the living thread, measured."""
    mod = _load_propose_edges()
    if mod is None:
        return None
    try:
        data = mod.build(Path(str(wiki.CATALOG_DB)), min_ms, min_market)
    except Exception:
        return None
    for e in data.get("co_occurs_with_manuscripts", []):
        a, b = f"term:{e['a']}", f"term:{e['b']}"
        if a in g.nodes and b in g.nodes:
            x, y = sorted((a, b))
            g.edge(x, y, "co_occurs_with", "derived", w=e["shared"],
                   ev=f"{e['shared']} shared manuscripts")
    for e in data.get("co_occurs_with_market", []):
        a, b = f"term:{e['a']}", f"term:{e['b']}"
        if a in g.nodes and b in g.nodes:
            x, y = sorted((a, b))
            g.edge(x, y, "co_occurs_with", "derived", w=e["shared"],
                   ev=f"{e['shared']} shared listings")
    for t in data.get("corpus_market_echo", []):
        nid = f"term:{t['term']}"
        if nid in g.nodes:
            g.nodes[nid]["echo_ms"] = t["manuscripts"]
            g.nodes[nid]["echo_mk"] = t["listings"]
    return data.get("counts", {})


# ------------------------------------------------- node → site address & threads
# ONE rule for "where does this node live on the site" and "how does an edge read
# as a thread". Both the manuscript-detail threads (build_static) and the landing
# constellation (maproom) go through here — two copies of this mapping is how the
# drift starts, and this project has been bitten by exactly that before.
_AXIS_FACET = {"genre": "genre", "language": "languages", "script": "script",
               "province": "province", "temple": "temple", "material": "material",
               "tradition": "tradition", "era": "era"}


def art_slug(key):
    """Filesystem/URL-safe slug for a subject article key ('genre:foo' →
    'genre_foo') — MUST match build_static.art(), which independently defines the
    same regex for /api/article/<slug>.json filenames (and its client-side JS
    mirror). Kept as a small, tolerated duplication rather than a cross-module
    import, same rationale as manuscript_pages.py's own dead-source-link mirror."""
    import re
    return re.sub(r"[^A-Za-z0-9]+", "_", "" if key is None else str(key))


def href_for(nid):
    """The on-site URL for a node id, or '' when the node has no page of its own
    (market items live only on the aggregate; kinds and ptypes are pure axes)."""
    cls, _, val = str(nid).partition(":")
    if cls == "ms":
        # The real, crawlable page (manuscript_pages.py, Phase F) — every
        # graph-driven link (threads, trails, wander) leads here, the
        # "discovery" door. /m?id=<id> (the interactive OCR/annotate tool)
        # stays reachable FROM this page, but is no longer what the graph
        # itself points at.
        return f"/m/{val}/"
    if cls == "place":
        return f"/place/{val}/"
    if cls == "term":
        return "/browse?q=" + quote(val)
    if cls == "finding":
        return f"/findings#{val}"
    if cls == "page":
        return val
    if cls == "item":
        return "/market"
    if cls in ("entity", "genre", "subgenre"):
        # The real, crawlable page (article_pages.py) — same "ms" precedent above.
        # /a?id=<key> (the interactive connections/findings view) stays reachable
        # FROM this page, but is no longer what the graph itself points at.
        return f"/a/{art_slug(nid)}/"
    if cls in _AXIS_FACET:
        return f"/browse?{_AXIS_FACET[cls]}=" + quote(val)
    return ""


# edge type → (strings.py relation key, which endpoint reads it this way)
_THREAD_REL = {
    "about": "about", "carries_term": "term", "held_at": "held_at",
    "near": "near", "same_walk_cluster": "same_walk", "co_occurs_with": "paired",
    "concerns": "about", "cites": "see_also", "related_to": "see_also",
    "paired_with": "paired", "part_of": "includes", "same_as": "see_also",
}


def threads_for(g, nid, limit=10, echo=True):
    """A node's lateral threads: [{rel, href, label, note}] — named relations
    with their receipts, ready to render. Structural membership edges (in_genre,
    in_language…) are NOT threads: they are shelves, and the facets already
    carry them. `echo` adds the corpus↔market thread when a term the node
    carries is also live in today's market."""
    out, seen = [], {}
    for e in sorted(g.by_src().get(nid, ()),
                    key=lambda e: (e["type"], -e.get("w", 1))):
        rel = _THREAD_REL.get(e["type"])
        if not rel:
            continue
        dst = e["dst"]
        href = href_for(dst)
        if not href:
            continue
        node = g.nodes.get(dst, {})
        # One thread per destination. A generic "see also" is redundant once a
        # stronger typed relation (part of, paired with…) already links the same
        # two nodes — the same de-noising rule wiki.connections() applies to the
        # article panel, kept here so every surface reads alike.
        prev = seen.get(dst)
        if prev is not None:
            if out[prev]["rel"] == "see_also" and rel != "see_also":
                out[prev] = {"rel": rel, "href": href,
                             "label": node.get("label") or dst.split(":", 1)[1],
                             "note": e.get("ev", "")}
            continue
        seen[dst] = len(out)
        out.append({"rel": rel, "href": href,
                    "label": node.get("label") or dst.split(":", 1)[1],
                    "note": e.get("ev", "")})
        if echo and e["type"] == "carries_term" and node.get("echo_mk"):
            out.append({"rel": "in_market", "href": "/market",
                        "label": node.get("label", ""),
                        "note": f"{node['echo_mk']} listings"})
    return out[:limit]


# ------------------------------------------------------------------ the atlas
# The graph's shape is carried by 22,000 records, but a picture of 22,000 dots
# shows nothing. Fold the bipartite graph onto its CONCEPT layer instead: two
# concepts are joined when records belong to both, and the weight is how many.
# That is a measurement, not a model — the same extract-don't-author rule as
# everywhere else — and it makes the real structure visible at a glance: which
# script travels with which language, which genre with which material, which
# word with which province.
_CONCEPT_CLASSES = {
    "tradition", "genre", "subgenre", "language", "script", "province",
    "material", "era", "entity", "term", "kind", "ptype", "temple",
}
# Which edge types carry a record INTO a concept (its memberships).
_MEMBERSHIP = AXIS_TYPES | {"about", "carries_term"}


def concept_projection(g, min_shared=12, max_concepts_per_record=14, top=420):
    """({node_id: node}, [(a, b, shared)]) — the concept co-membership graph.

    `min_shared` keeps it legible: a link means "at least this many records sit
    in both", not "these two once touched". Records with an implausible number
    of memberships are capped rather than allowed to dominate the pair counts.
    """
    by_record = defaultdict(list)
    for e in g.edges.values():
        if e["type"] in _MEMBERSHIP and e["dst"] in g.nodes:
            if g.nodes[e["dst"]]["cls"] in _CONCEPT_CLASSES:
                by_record[e["src"]].append(e["dst"])
    pair = defaultdict(int)
    weight = defaultdict(int)
    for rec, concepts in by_record.items():
        cs = sorted(set(concepts))[:max_concepts_per_record]
        for c in cs:
            weight[c] += 1
        for i, a in enumerate(cs):
            for b in cs[i + 1:]:
                pair[(a, b)] += 1
    keep = {c for c, _ in sorted(weight.items(), key=lambda kv: -kv[1])[:top]}
    edges = [(a, b, n) for (a, b), n in pair.items()
             if n >= min_shared and a in keep and b in keep]
    edges.sort(key=lambda e: -e[2])
    used = {x for a, b, _ in edges for x in (a, b)}
    nodes = {nid: g.nodes[nid] for nid in used}
    return nodes, edges, weight


def atlas_payload(g, **kw):
    """The whole atlas, as small as it can honestly be: one records-count per
    node, one weight per edge, indices instead of ids in the edge list."""
    nodes, edges, weight = concept_projection(g, **kw)
    order = sorted(nodes, key=lambda nid: (nodes[nid]["cls"], -weight[nid], nid))
    idx = {nid: i for i, nid in enumerate(order)}
    return {
        "note": ("Concepts joined when records belong to both; the weight is how "
                 "many records they share. Folded from api/graph/edges.jsonl."),
        "nodes": [{"id": nid, "l": nodes[nid]["label"], "c": nodes[nid]["cls"],
                   "n": weight[nid], "h": href_for(nid)} for nid in order],
        "edges": [[idx[a], idx[b], n] for a, b, n in edges],
    }


# ------------------------------------------------------------------- page layer
def page_layer(g):
    for r in routes.ROUTES:
        g.node(f"page:{r.path}", "page", r.title, kind=r.kind,
               nav=1 if r.nav else 0, door=1 if r.door else 0,
               hidden=1 if r.hidden_reason else 0)
    return len(routes.ROUTES)


# ------------------------------------------------------------------------ build
def build(conn=None):
    """The whole graph. Returns (Graph, meta) where meta records which soft
    sources were present — an absent vault or crawler is a smaller graph, not
    an error, but the summary must say so (no silent caps)."""
    own = conn is None
    if own:
        conn = wiki.connect()
    g = Graph()
    meta = {}
    try:
        meta["authored_triples"] = subject_layer(g, conn)
        meta["manuscripts"] = manuscript_layer(g, conn)
        meta["items"] = item_layer(g, conn)
        meta["tag_edges"] = tag_layer(g, conn)
        meta["places"] = place_layer(g)
        meta["vault"] = vault_layer(g)
        meta["findings"] = finding_layer(g, conn)
        co = proposed_layer(g)
        meta["proposed"] = co if co is not None else "unavailable (crawler sibling not found)"
        meta["pages"] = page_layer(g)
    finally:
        if own:
            conn.close()
    return g, meta


def summarize(g, meta):
    by_cls = defaultdict(int)
    for n in g.nodes.values():
        by_cls[n["cls"]] += 1
    by_type_prov = defaultdict(int)
    for e in g.edges.values():
        by_type_prov[f"{e['type']}·{e['prov']}"] += 1
    by_prov = defaultdict(int)
    for e in g.edges.values():
        by_prov[e["prov"]] += 1
    displays = {}
    for k, (fwd, rev) in TYPES.items():
        displays[k] = {"forward": fwd, "reverse": rev}
    for k, v in wiki.RELATIONS.items():
        displays[k] = {"inverse": v[0], "forward": v[1], "reverse": v[2]}
    return {
        "schema": "wichaa-graph/1",
        # Self-describing, because an agent that finds edges.jsonl before it
        # finds llms.txt should still know what it is holding.
        "howto": {
            "node_id": "class:value — e.g. ms:6962, place:wat-chiang-man, term:เมตตา",
            "edge": "{src, dst, type, prov, w, ev}",
            "w": "a real count, or a distance in metres; never an invented score",
            "ev": "the receipt, in words — '7 shared manuscripts', '312 m apart'",
            "provenance": {
                "authored": "a human asserted it",
                "adjudicated": "a written rule decided it, and fails closed when it cannot",
                "computed": "it follows from the catalogue's columns or coordinates",
                "derived": "a bot noticed a pattern and cited the records it counted",
            },
            "note": ("Nothing here is inferred from a language model's priors. "
                     "Resolved relations also ride inside api/manuscript/{id}.json, "
                     "api/place/{id}.json and api/article/{slug}.json as `threads`."),
        },
        "nodes": {"total": len(g.nodes), "by_class": dict(sorted(by_cls.items()))},
        "edges": {"total": len(g.edges),
                  "by_provenance": dict(sorted(by_prov.items())),
                  "by_type_provenance": dict(sorted(by_type_prov.items()))},
        "types": displays,
        "sources": meta,
    }


# ------------------------------------------------------------------------ audit
def _components(g, provs=("authored", "derived")):
    """Connected components over the authored+derived layer only — the layer a
    human or bot deliberately wove. (Through axis nodes everything is one blob;
    that would measure nothing.)"""
    adj = defaultdict(set)
    for e in g.edges.values():
        if e["prov"] in provs:
            adj[e["src"]].add(e["dst"])
            adj[e["dst"]].add(e["src"])
    seen, comps = set(), []
    for start in adj:
        if start in seen:
            continue
        comp, stack = [], [start]
        seen.add(start)
        while stack:
            n = stack.pop()
            comp.append(n)
            for m in adj[n]:
                if m not in seen:
                    seen.add(m)
                    stack.append(m)
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    return comps


_HREF = re.compile(r"""href=["']([^"'#?]+)""")


def _link_walk(docs_dir):
    """Static reachability, measured two ways — and the second one matters:
      · inbound counts   (a page nothing links to = a direct orphan)
      · BFS from "/"     (a page only orphans link to is STILL unreachable —
                          /w/prices is "linked" from /w, but /w hangs in space)
    Bulk namespaces (place/, read/) are judged at namespace level — their
    members are client-rendered destinations (data-driven), which is exactly
    the wayfinding gap Phase B exists to close, so it is REPORTED, not failed."""
    docs = Path(docs_dir)
    inbound = defaultdict(set)          # target route -> set of source pages
    outgoing = defaultdict(set)         # source page  -> set of target routes
    for f in docs.rglob("*.html"):
        src = "/" + f.relative_to(docs).as_posix()
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for href in _HREF.findall(text):
            if not href.startswith("/") or href.startswith("//"):
                continue
            t = href.rstrip("/") or "/"
            inbound[t].add(src)
            outgoing[src].add(t)
    # judge every depth<=2 index.html target that exists on disk
    targets = set()
    for f in docs.glob("*/index.html"):
        targets.add("/" + f.parent.name)
    for f in docs.glob("*/*/index.html"):
        targets.add("/" + f.parent.parent.name + "/" + f.parent.name)
    bulk_prefixes = routes.BULK_NAMESPACES
    hidden = {r.path.rstrip("/") or "/": r.hidden_reason
              for r in routes.ROUTES if r.hidden_reason}
    # Template routes (/m, /a) are query-param destinations reached via
    # /m?id=… and /a?s=… from CLIENT-RENDERED pages (browse, gallery, search) —
    # links the static link-walk cannot see — plus the per-entity pages'
    # "open the interactive viewer" links, which the self-link rule below
    # discounts. They are reachable in every real sense; being a bare-path
    # "orphan" is expected, exactly like a hidden route. Exempt them by reason.
    for r in routes.ROUTES:
        if r.kind == "template":
            hidden.setdefault(r.path.rstrip("/") or "/",
                              "query-param template — reached via ?id=/?s= from "
                              "client-rendered pages the static walk can't trace")

    # transitive reachability: BFS over routes, starting at the landing page
    def _files_of(route):
        rel = route.strip("/")
        return ([docs / "index.html"] if route == "/" else
                [docs / rel / "index.html"])
    reached, queue = {"/"}, ["/"]
    while queue:
        cur = queue.pop(0)
        for f in _files_of(cur):
            if not f.is_file():
                continue
            src = "/" + f.relative_to(docs).as_posix()
            for t in outgoing.get(src, ()):
                if t in targets and t not in reached:
                    reached.add(t)
                    queue.append(t)

    report = []
    for t in sorted(targets):
        if t.startswith(bulk_prefixes):
            continue
        n_in = len({s for s in inbound.get(t, ())
                    if not s.startswith(t + "/")})   # self-links don't count
        entry = {"route": t, "inbound": n_in}
        if t in hidden:
            entry["hidden_reason"] = hidden[t]
        else:
            if n_in == 0:
                entry["orphan"] = True
            if t not in reached:
                entry["unreachable"] = True
        report.append(entry)
    orphans = [r["route"] for r in report if r.get("orphan")]
    unreachable = [r["route"] for r in report if r.get("unreachable")]
    bulk = {}
    for pref in bulk_prefixes:
        members = sum(1 for f in docs.glob(pref.strip("/") + "/*/index.html"))
        static_in = len(inbound.get(pref.rstrip("/"), set()))
        bulk[pref] = {"members": members,
                      "static_inbound_to_root": static_in,
                      "note": "members are client-rendered destinations "
                              "(reached via data, not static hrefs) — the "
                              "Phase B lateral-link gap, reported not failed"}
    return {"routes": report, "orphans": orphans, "unreachable": unreachable,
            "bulk_namespaces": bulk}


def audit(g, meta, docs_dir=None):
    deg = g.degree()
    by_cls_iso = defaultdict(int)
    by_cls_total = defaultdict(int)
    for nid, n in g.nodes.items():
        by_cls_total[n["cls"]] += 1
        if deg.get(nid, 0) == 0:
            by_cls_iso[n["cls"]] += 1
    # dead-ends in the wandering sense: entity-class nodes whose every edge is
    # structural membership (nothing a wanderer can follow sideways)
    nonaxis = defaultdict(int)
    for e in g.edges.values():
        if e["type"] not in AXIS_TYPES:
            nonaxis[e["src"]] += 1
            nonaxis[e["dst"]] += 1
    deadend = {}
    for cls in ("ms", "item", "place"):
        total = by_cls_total.get(cls, 0)
        if not total:
            continue
        with_lateral = sum(1 for nid, n in g.nodes.items()
                           if n["cls"] == cls and nonaxis.get(nid, 0) > 0)
        deadend[cls] = {"total": total, "with_lateral_edges": with_lateral,
                        "dead_end_share": round(1 - with_lateral / total, 4)}
    comps = _components(g)
    hubs = sorted(((deg[nid], nid) for nid in g.nodes), reverse=True)[:15]
    out = {
        "isolates_by_class": {k: v for k, v in sorted(by_cls_iso.items()) if v},
        "dead_ends": deadend,
        "woven_layer_components": {
            "count": len(comps),
            "largest": [{"size": len(c), "sample": sorted(c)[:5]}
                        for c in comps[:5]],
        },
        "hubs": [{"id": nid, "label": g.nodes[nid]["label"], "degree": d}
                 for d, nid in hubs],
    }
    if docs_dir:
        out["reachability"] = _link_walk(docs_dir)
    return out


# ---------------------------------------------------------------- audit page
def audit_page(summary, audit_data):
    """The /graph-audit page — maintainer diagnostics, data baked in (no fetch,
    no shim dependency), standard chrome via wiki.page()."""
    def esc(s):
        return (str(s).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;"))

    def table(rows, headers):
        h = "".join(f"<th>{esc(x)}</th>" for x in headers)
        b = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>"
                    for row in rows)
        return f"<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>"

    nodes = summary["nodes"]
    edges = summary["edges"]
    parts = [
        "<p class=sub>Phase A cartography (ADR-002): the corpus-scale knowledge "
        "graph, measured. Machine copies: <a href='/api/graph/nodes.jsonl'>"
        "nodes.jsonl</a> · <a href='/api/graph/edges.jsonl'>edges.jsonl</a> · "
        "<a href='/api/graph/summary.json'>summary.json</a> · "
        "<a href='/api/graph/audit.json'>audit.json</a></p>",
        f"<h2>Nodes — {nodes['total']:,}</h2>",
        table(sorted(nodes["by_class"].items()), ("class", "count")),
        f"<h2>Edges — {edges['total']:,}</h2>",
        "<h3>by provenance</h3>",
        table(sorted(edges["by_provenance"].items()), ("provenance", "count")),
        "<h3>by type · provenance</h3>",
        table(sorted(edges["by_type_provenance"].items()), ("type·prov", "count")),
    ]
    de = audit_data.get("dead_ends", {})
    if de:
        parts += ["<h2>Dead-ends (no lateral edges — the Phase B work-list)</h2>",
                  table([(k, v["total"], v["with_lateral_edges"],
                          f"{v['dead_end_share']:.0%}") for k, v in de.items()],
                        ("class", "total", "with lateral", "dead-end share"))]
    reach = audit_data.get("reachability")
    if reach:
        orphans = reach.get("orphans", [])
        unreach = reach.get("unreachable", [])
        parts.append(f"<h2>Static reachability — {len(orphans)} orphan(s), "
                     f"{len(unreach)} unreachable from the landing</h2>")
        items = []
        for o in orphans:
            items.append(f"<li><code>{esc(o)}</code> — published, linked "
                         f"from nothing</li>")
        for o in unreach:
            if o not in orphans:
                items.append(f"<li><code>{esc(o)}</code> — linked only from "
                             f"pages that are themselves unreachable</li>")
        if items:
            parts.append("<ul>" + "".join(items) + "</ul>")
        else:
            parts.append("<p>Every published route is reachable from the "
                         "landing page or carries a declared hidden_reason.</p>")
        bulk = reach.get("bulk_namespaces", {})
        if bulk:
            parts.append(table(
                [(k, v["members"], v["static_inbound_to_root"]) for k, v in
                 sorted(bulk.items())],
                ("namespace", "members", "static inbound to root")))
    comps = audit_data.get("woven_layer_components", {})
    if comps:
        parts.append(f"<h2>Woven layer (authored + derived) — "
                     f"{comps.get('count', 0)} component(s)</h2>")
        parts.append(table([(c["size"], ", ".join(c["sample"])) for c in
                            comps.get("largest", [])], ("size", "sample")))
    hubs = audit_data.get("hubs", [])
    if hubs:
        parts += ["<h2>Best-connected nodes</h2>",
                  table([(h["degree"], h["id"], h["label"]) for h in hubs],
                        ("degree", "id", "label"))]
    css = ("table{border-collapse:collapse;margin:10px 0 22px;font-size:14px}"
           "td,th{border:1px solid rgba(128,128,128,.3);padding:5px 10px;"
           "text-align:left}th{opacity:.7}h2{margin-top:26px}"
           "code{font-size:13px}")
    body = ("<header><div><h1>Graph audit</h1><p class=sub>the edge store, "
            "counted and cross-examined</p></div>" + wiki.NAV + "</header>"
            "<main>" + "".join(parts) + "</main>")
    return wiki.page("Graph audit — wichaa", css, body)


# ---------------------------------------------------------------------- output
def write_outputs(out_dir, g, summary, audit_data=None):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "nodes.jsonl").open("w", encoding="utf-8") as f:
        for nid in sorted(g.nodes):
            f.write(json.dumps(g.nodes[nid], ensure_ascii=False) + "\n")
    with (out / "edges.jsonl").open("w", encoding="utf-8") as f:
        for key in sorted(g.edges):
            f.write(json.dumps(g.edges[key], ensure_ascii=False) + "\n")
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    if audit_data is not None:
        (out / "audit.json").write_text(
            json.dumps(audit_data, ensure_ascii=False, indent=1),
            encoding="utf-8")


def write_audit_into(docs_dir, base="/"):
    """Audit a BUILT site tree and write api/graph/audit.json plus the
    /graph-audit page into it. ONE code path for both callers, so they can
    never drift: build_static.py at its own end (preliminary — later
    generators haven't run yet) and publish_site.sh after site_meta (the
    complete picture; this overwrite is what actually publishes)."""
    g, meta = build()
    summary = summarize(g, meta)
    a = audit(g, meta, docs_dir=docs_dir)
    out = Path(docs_dir)
    gdir = out / "api" / "graph"
    gdir.mkdir(parents=True, exist_ok=True)
    (gdir / "audit.json").write_text(
        json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    import build_static  # lazy: build_static imports THIS module at its top
    (out / "graph-audit").mkdir(parents=True, exist_ok=True)
    (out / "graph-audit" / "index.html").write_text(
        build_static.inject(audit_page(summary, a), base), encoding="utf-8")
    return a


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Build the corpus-scale knowledge graph (Phase A cartography)")
    ap.add_argument("--out", help="directory to write nodes/edges/summary[/audit]")
    ap.add_argument("--audit-docs", help="built-site dir to link-walk for the audit")
    ap.add_argument("--write-audit-into", metavar="DOCS",
                    help="audit a built site tree and write audit.json + the "
                         "/graph-audit page into it (publish pipeline step)")
    ap.add_argument("--base", default="/",
                    help="URL prefix for --write-audit-into page injection")
    a = ap.parse_args(argv)

    if a.write_audit_into:
        if not wiki.db_present():
            print(f"cartography: catalogue not found at {wiki.CATALOG_DB}",
                  file=sys.stderr)
            return 1
        aud = write_audit_into(a.write_audit_into, a.base)
        reach = aud.get("reachability", {})
        print(f"cartography: audit written into {a.write_audit_into} — "
              f"{len(reach.get('orphans', []))} orphan(s), "
              f"{len(reach.get('unreachable', []))} unreachable")
        return 0

    if not wiki.db_present():
        print(f"cartography: catalogue not found at {wiki.CATALOG_DB}",
              file=sys.stderr)
        return 1
    g, meta = build()
    summary = summarize(g, meta)
    audit_data = audit(g, meta, docs_dir=a.audit_docs)

    print(f"nodes: {summary['nodes']['total']:,}")
    for cls, n in summary["nodes"]["by_class"].items():
        print(f"  {cls:<10} {n:,}")
    print(f"edges: {summary['edges']['total']:,}")
    for prov, n in summary["edges"]["by_provenance"].items():
        print(f"  {prov:<12} {n:,}")
    for tp, n in summary["edges"]["by_type_provenance"].items():
        print(f"    {tp:<32} {n:,}")
    de = audit_data.get("dead_ends", {})
    for cls, d in de.items():
        print(f"dead-end share {cls}: {d['dead_end_share']:.0%} "
              f"({d['with_lateral_edges']:,}/{d['total']:,} have lateral edges)")
    if a.audit_docs:
        reach = audit_data.get("reachability", {})
        orphans = reach.get("orphans", [])
        unreach = reach.get("unreachable", [])
        print(f"orphan routes: {len(orphans)} {orphans}")
        print(f"unreachable from landing: {len(unreach)} {unreach}")
    if a.out:
        write_outputs(a.out, g, summary, audit_data)
        print(f"wrote {a.out}/nodes.jsonl, edges.jsonl, summary.json, audit.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
