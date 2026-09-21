#!/usr/bin/env python3
"""lexicon — the sense-first dictionary, and its graph.

WHY THIS EXISTS SEPARATELY FROM glossary.py
/glossary is the discovered folksonomy: the words the crawlers found on
manuscripts and listings, each with a verified count. It answers "what does
this term mean". This answers a different question — "why does this word mean
that" — and needs a different shape to do it, because the unit here is the
SENSE, not the word.

WHAT WENT WRONG LAST TIME
The predecessor (ThaiRoots, 257 heads / 974 words) filed words under a shared
root the way Hans Wehr does, but kept no slot for a sense. Measured in its own
data: 77 of 257 heads packed several meanings into one gloss string with a
semicolon; only 34.7% of its `ext` neighbours even contained their root
verbatim, so `ตาย` (die) and `เตา` (stove) sat under `ตา` (eye); and `แก้ว`,
the richest family in the language, was absent entirely because it is not a
root. See data/lexicon/SCHEMA.md for the full post-mortem.

THE GRAPH, AND AN HONEST DISTINCTION
atlas.py states its own rule plainly: "nothing is modelled, inferred or scored;
every line is a count you could go and verify." A lexicon edge is the opposite
kind of claim — EXTENDS says one meaning grew out of another, and no count
establishes that. So edges are emitted in two families:

    structural   HAS_SENSE, COMPOUND_OF, IN_DOMAIN, HAS_REGISTER,
                 FROM_ETYMON, SOUND_KEY        -- mechanical, safe to project
    asserted     EXTENDS, HEADS, CALQUES, NEAR_SYNONYM, CONFUSABLE_WITH,
                 ATTESTED_IN, ...              -- each carries conf + src

`--atlas` exports the structural family only. The asserted family ships with
its confidence attached and is drawn on the entry page, where a reader can see
who says so. Mixing them would quietly make the atlas dishonest.

DANGLING EDGES ARE WORK, NOT ERRORS
An edge may point at a word not yet written. That is the normal state of a
growing dictionary and is reported as a queue, not a failure — it is, in fact,
the most useful thing the tool produces: the ranked list of what to write next.

    python3 lexicon.py --report
    python3 lexicon.py --docs ../nanobotco-lanna/docs
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

import lexicon_page
from lexicon_tags import is_compound

HERE = Path(__file__).resolve().parent
LEX = HERE / "data" / "lexicon"
ENTRIES = LEX / "entries"
REGISTRY = LEX / "registry.json"

STRUCTURAL = {"HAS_SENSE", "COMPOUND_OF", "IN_DOMAIN", "HAS_REGISTER",
              "FROM_ETYMON", "SOUND_KEY"}


# --- a small JSON Schema checker -------------------------------------------
# Only the keywords this schema actually uses. A dependency would buy little
# and this project runs on the standard library everywhere else.
def _resolve(node, root):
    while "$ref" in node:
        ref = node["$ref"]
        if not ref.startswith("#/"):
            raise ValueError(f"external $ref unsupported: {ref}")
        cur = root
        for part in ref[2:].split("/"):
            cur = cur[part]
        node = cur
    return node


def check(inst, schema, root, path="", errs=None):
    errs = [] if errs is None else errs
    schema = _resolve(schema, root)
    t = schema.get("type")
    if t == "object":
        if not isinstance(inst, dict):
            errs.append(f"{path or '/'}: expected object, got {type(inst).__name__}")
            return errs
        for r in schema.get("required", []):
            if r not in inst:
                errs.append(f"{path}/{r}: required field missing")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for k in inst:
                if k not in props:
                    errs.append(f"{path}/{k}: field not in schema")
        for k, v in inst.items():
            if k in props:
                check(v, props[k], root, f"{path}/{k}", errs)
    elif t == "array":
        if not isinstance(inst, list):
            errs.append(f"{path}: expected array, got {type(inst).__name__}")
            return errs
        if len(inst) < schema.get("minItems", 0):
            errs.append(f"{path}: needs at least {schema['minItems']} item(s)")
        if "items" in schema:
            for i, v in enumerate(inst):
                check(v, schema["items"], root, f"{path}[{i}]", errs)
    elif t == "string":
        if not isinstance(inst, str):
            errs.append(f"{path}: expected string, got {type(inst).__name__}")
            return errs
        if "enum" in schema and inst not in schema["enum"]:
            errs.append(f"{path}: {inst!r} not one of {schema['enum']}")
        if "pattern" in schema and not re.match(schema["pattern"], inst):
            errs.append(f"{path}: {inst!r} fails pattern {schema['pattern']}")
    elif t == "integer":
        if not isinstance(inst, int) or isinstance(inst, bool):
            errs.append(f"{path}: expected integer")
            return errs
        if "minimum" in schema and inst < schema["minimum"]:
            errs.append(f"{path}: below minimum {schema['minimum']}")
    elif t == "boolean":
        if not isinstance(inst, bool):
            errs.append(f"{path}: expected boolean")
    return errs


# --- ids --------------------------------------------------------------------
def handle(d):
    """The URL handle.

    Taken from the id where there is one, because `rtgs` collides by design:
    ส่ง and ทรง are both "song", and two entries cannot share a URL. The id was
    allocated once with a disambiguating suffix and is frozen, so it is the only
    safe thing to build a link out of. `rtgs` stays display data.
    """
    if d.get("id", "").startswith("w:"):
        return d["id"][2:]
    return d.get("rtgs") or d.get("translit_auto") or "x"


def slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "x"


class Registry:
    """Ids are allocated once and frozen, so a link keeps meaning its target."""

    def __init__(self, path: Path):
        self.path = path
        self.map = json.loads(path.read_text("utf-8")) if path.exists() else {}
        self.dirty = False

    def word_id(self, rtgs: str, th: str) -> str:
        for wid, rec in self.map.items():
            if rec.get("th") == th and rec.get("rtgs") == rtgs:
                return wid
        base = f"w:{slug(rtgs)}"
        wid, n = base, 1
        while wid in self.map:
            n += 1
            wid = f"{base}-{n}"
        self.map[wid] = {"th": th, "rtgs": rtgs}
        self.dirty = True
        return wid

    def save(self):
        if self.dirty:
            self.path.write_text(
                json.dumps(OrderedDict(sorted(self.map.items())),
                           ensure_ascii=False, indent=2) + "\n", "utf-8")


# --- graph ------------------------------------------------------------------
def build_graph(entries, reg: Registry):
    nodes, edges = OrderedDict(), []

    def node(nid, cls, label, **kw):
        if nid not in nodes:
            nodes[nid] = {"id": nid, "c": cls, "l": label, **kw}
        return nodes[nid]

    def edge(rel, a, b, **kw):
        e = {"rel": rel, "from": a, "to": b,
             "kind": "structural" if rel in STRUCTURAL else "asserted"}
        e.update({k: v for k, v in kw.items() if v is not None})
        edges.append(e)

    def explicit(owner, lst):
        for ed in lst or []:
            edge(ed["rel"], owner, ed["to"], label=ed.get("label"),
                 via=ed.get("via"), why=ed.get("why"),
                 distinction=ed.get("distinction"), note=ed.get("note"),
                 conf=ed.get("conf"), src=ed.get("src"))

    for e in entries:
        wid = e["id"]
        node(wid, "word", e["th"], rtgs=e.get("rtgs"), ipa=e.get("ipa"),
             stratum=e.get("stratum"), core=e.get("core_image"),
             h=f"/kham/{slug(handle(e))}/")
        for et in (e.get("etymology") or {}).get("chain", []):
            node(et, "etymon", et.split(":", 2)[-1])
            edge("FROM_ETYMON", wid, et)
        if (e.get("etymology") or {}).get("root"):
            r = e["etymology"]["root"]
            node(r, "root", r.split(":", 1)[-1])
            edge("FROM_ETYMON", wid, r)
        explicit(wid, e.get("edges"))

        # Attested compounds not yet filed under a sense. They are real words and
        # belong in the graph, but they get COMPOUND_OF only — never HEADS, which
        # would assert a sense assignment nobody has made.
        for c in e.get("compounds_unassigned", []):
            cid = reg.word_id(handle(c), c["th"])
            node(cid, "word", c["th"], rtgs=handle(c), unassigned=True,
                 h=f"/kham/{slug(handle(c))}/")
            for part in c.get("parts", []):
                pid = next((k for k, v in reg.map.items() if v.get("th") == part), None)
                if pid is None:
                    pid = f"w:?{part}"
                    node(pid, "word", part, pending=True)
                edge("COMPOUND_OF", cid, pid)

        for s in e["senses"]:
            sid = f"{wid}#{s['n']}"
            node(sid, "sense", "; ".join(s["gloss"]["en"]),
                 word=wid, n=s["n"], conf=s.get("conf"))
            edge("HAS_SENSE", wid, sid)
            for r in s.get("register", []):
                node(r, "register", r.split(":", 1)[-1]); edge("HAS_REGISTER", sid, r)
            for d in s.get("domains", []):
                node(d, "domain", d.split(":", 1)[-1]); edge("IN_DOMAIN", sid, d)
            if s.get("extends"):
                edge("EXTENDS", sid, f"{wid}#{s['extends']}", via=s.get("via"),
                     note=s.get("via_note"), conf=s.get("via_conf"))
            explicit(sid, s.get("edges"))

            for c in s.get("compounds", []):
                cid = reg.word_id(handle(c), c["th"])
                node(cid, "word", c["th"], rtgs=c.get("rtgs"),
                     lit=c.get("lit"), frame=c.get("frame"),
                     h=f"/kham/{slug(handle(c))}/")
                if c.get("flips_with"):
                    edge("FLIPS_WITH", cid, f"w:?{c['flips_with']}",
                         label=c["flips_with"],
                         note="the same two morphemes in the opposite order; "
                              "order carries the meaning, not sense",
                         conf="verified", src=["CUR"])
                edge("HEADS", sid, cid, note=c.get("lit"),
                     conf=c.get("conf"), src=c.get("src"))
                for part in c.get("parts", []):
                    pid = next((k for k, v in reg.map.items() if v.get("th") == part), None)
                    if pid is None:
                        pid = f"w:?{part}"
                        node(pid, "word", part, pending=True)
                    edge("COMPOUND_OF", cid, pid)
                for r in c.get("register", []):
                    node(r, "register", r.split(":", 1)[-1]); edge("HAS_REGISTER", cid, r)
                for d in c.get("domains", []):
                    node(d, "domain", d.split(":", 1)[-1]); edge("IN_DOMAIN", cid, d)
                explicit(cid, c.get("edges"))
    return nodes, edges


def main():
    ap = argparse.ArgumentParser(description="lexicon — validate, graph, report")
    ap.add_argument("--docs", help="site docs dir; writes api/lexicon/*.json")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--atlas", action="store_true", help="print structural projection only")
    ap.add_argument("--site", "--site-url", dest="site",
                    default="https://wichaa.net", help="canonical site url")
    a = ap.parse_args()

    schema = json.loads((LEX / "schema.json").read_text("utf-8"))
    files = sorted(ENTRIES.glob("*.json"))
    if not files:
        sys.exit("no entries in data/lexicon/entries/")

    entries, bad = [], 0
    for f in files:
        d = json.loads(f.read_text("utf-8"))
        errs = check(d, schema, schema)
        if errs:
            bad += 1
            print(f"✗ {f.name}")
            for e in errs[:20]:
                print("   ", e)
        else:
            print(f"✓ {f.name}")
            entries.append(d)
    if bad:
        sys.exit(f"\n{bad} entry/entries failed validation")

    reg = Registry(REGISTRY)
    for e in entries:                     # seed heads before compounds resolve parts
        reg.map.setdefault(e["id"], {"th": e["th"], "rtgs": handle(e)})
        reg.dirty = True
    nodes, edges = build_graph(entries, reg)
    reg.save()

    known = set(nodes)
    dangling = Counter(e["to"] for e in edges if e["to"] not in known)
    struct = [e for e in edges if e["kind"] == "structural"]

    if a.report or not a.docs:
        print(f"\nentries {len(entries)} · nodes {len(nodes)} · edges {len(edges)}"
              f" ({len(struct)} structural, {len(edges)-len(struct)} asserted)")
        print("node classes :", dict(Counter(n['c'] for n in nodes.values())))
        print("relations    :", dict(Counter(e['rel'] for e in edges)))
        print("confidence   :", dict(Counter(
            e.get("conf", "—") for e in edges if e["kind"] == "asserted")))
        nc = [(e["id"], n) for e in entries for n in e.get("needs_check", [])]
        nc += [(e["id"], n) for e in entries for s in e["senses"]
               for n in s.get("needs_check", [])]
        nc += [(e["id"], n) for e in entries for s in e["senses"]
               for c in s.get("compounds", []) for n in c.get("needs_check", [])]
        unassigned = sum(len(e.get("compounds_unassigned", [])) for e in entries)
        st = Counter(e.get("status", "listed") for e in entries)
        filed = sum(len(s.get("compounds", [])) for e in entries for s in e["senses"])
        print("status       : " + " · ".join(f"{n} {k}" for k, n in st.most_common())
              + f" · {filed} compounds filed, {unassigned} still open")
        print(f"\nneeds_check  : {len(nc)} open")
        for wid, n in nc:
            print(f"   · {n[:104]}")
        print(f"\nwrite-next queue (dangling targets, most-linked first): {len(dangling)}")
        for t, n in dangling.most_common(12):
            lbl = next((e.get("label", "") for e in edges if e["to"] == t and e.get("label")), "")
            print(f"   {n}×  {t}  {lbl}")

    if a.atlas:
        print(json.dumps({"nodes": list(nodes.values()), "edges": struct},
                         ensure_ascii=False, indent=1)[:2000])

    if a.docs:
        out = Path(a.docs) / "api" / "lexicon"
        out.mkdir(parents=True, exist_ok=True)
        (out / "graph.json").write_text(json.dumps(
            {"nodes": list(nodes.values()), "edges": edges},
            ensure_ascii=False, indent=1) + "\n", "utf-8")
        (out / "atlas.json").write_text(json.dumps(
            {"nodes": list(nodes.values()), "edges": struct},
            ensure_ascii=False) + "\n", "utf-8")
        for e in entries:
            (out / f"{slug(handle(e))}.json").write_text(
                json.dumps(e, ensure_ascii=False, indent=1) + "\n", "utf-8")
        (out / "index.json").write_text(json.dumps(
            [{"id": e["id"], "th": e["th"], "rtgs": handle(e),
              "core": e.get("core_image"), "senses": len(e["senses"])} for e in entries],
            ensure_ascii=False, indent=1) + "\n", "utf-8")

        # The neighbourhood, computed once and rendered into every entry page.
        # portal.js shows the same relations in a card; these are the static half,
        # so they work with scripting off and can be crawled.
        from collections import defaultdict as _dd
        inside, bymod, byrtgs = _dd(list), _dd(list), _dd(set)
        for e in entries:
            if e.get("rtgs"):
                byrtgs[e["rtgs"]].add(e["th"])
            for c in [x for s2 in e["senses"] for x in s2.get("compounds", [])] + \
                     e.get("compounds_unassigned", []):
                if not is_compound(c):
                    continue
                p2 = c.get("parts") or []
                for part in p2:
                    inside[part].append(c["th"])
                if len(p2) == 2 and e["th"] in p2:
                    bymod[p2[1] if p2[0] == e["th"] else p2[0]].append((c["th"], e["th"]))
        hood = {}
        for e in entries:
            th = e["th"]
            fam = {}
            for c in [x for s2 in e["senses"] for x in s2.get("compounds", [])] + \
                     e.get("compounds_unassigned", []):
                p2 = c.get("parts") or []
                if len(p2) == 2 and th in p2 and is_compound(c):
                    mod = p2[1] if p2[0] == th else p2[0]
                    sibs = sorted({w for w, h2 in bymod.get(mod, []) if h2 != th})
                    if len(sibs) >= 2:
                        fam.setdefault(mod, sibs[:12])
            hood[th] = {
                "inside": sorted(set(inside.get(th, []))),
                "flips": sorted({c["flips_with"] for s2 in e["senses"]
                                 for c in s2.get("compounds", []) if c.get("flips_with")}
                                | {c["flips_with"] for c in e.get("compounds_unassigned", [])
                                   if c.get("flips_with")}),
                "sounds_like": sorted(byrtgs.get(e.get("rtgs") or "", set()) - {th}),
                "family": fam,
            }

        site = a.site.rstrip("/")
        docs = Path(a.docs)
        roots = docs / "roots"
        roots.mkdir(parents=True, exist_ok=True)
        (roots / "index.html").write_text(
            lexicon_page.index_page(entries, site), "utf-8")
        kham = docs / "kham"
        kham.mkdir(parents=True, exist_ok=True)
        (kham / "index.html").write_text(
            lexicon_page.namespace_page(entries, site), "utf-8")
        for e in entries:
            wd = docs / "kham" / slug(handle(e))
            wd.mkdir(parents=True, exist_ok=True)
            (wd / "index.html").write_text(
                lexicon_page.entry_page(e, site, hood.get(e["th"])), "utf-8")
        print(f"\nwrote {out}")
        print(f"wrote {roots}/index.html + {len(entries)} entry page(s) under {docs}/kham/")


if __name__ == "__main__":
    main()
