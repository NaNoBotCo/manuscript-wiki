#!/usr/bin/env python3
"""phasa_graph — one semantic network for every surface of meaning on the site.

THE PROBLEM THIS SOLVES
The linguistics content arrived in pieces and each piece grew its own shape: a
sense-mapped lexicon of 300 heads, a ทับศัพท์ catalogue of borrowings, a
romanizer, a 65-term glossary of wichaa vocabulary, twelve sound-change cards, a
gallery of sacred syllables. Six answers to one subject, none of them joined, so
a reader who met พระเครื่อง in the glossary could not walk from it to พระ in the
lexicon even though it is the same word standing in front of them.

phasa.py already named the organising idea, and it is Thai's own — the ศัพท์
family, รากศัพท์ (where a word came from) · ทับศัพท์ (a word laid over from
another language) · ถ่ายเสียง (the sound carried across scripts). This module
does the mechanical half of that idea: it reads every source, emits them into ONE
node and edge vocabulary, and joins them where they are talking about the same
Thai string.

THE JOIN IS THE WHOLE POINT
`SAME_AS` is what makes this a network rather than five lists side by side. When
พระเครื่อง appears as a glossary term and as a compound under พระ, one edge says
so, and both surfaces become doors onto the same node. Everything else here is
bookkeeping; that edge is the product.

EVERY SURFACE A PORTAL
`resolve.json` maps a Thai string to the nodes that describe it. Any page holding
Thai text — a manuscript title, a market listing, an article, a place name — can
look a term up and make it a door, without knowing which subsystem owns it.

WHAT IS ASSERTED AND WHAT IS COUNTED
The distinction the lexicon runs on holds here too and is carried on every edge.
`SAME_AS` on an exact string match is mechanical. A borrowing's source word is a
claim someone made, and carries its method (`hand`, `aligned`, `signal`). Nothing
is upgraded by being copied into this graph.

    python3 phasa_graph.py --docs ../nanobotco-lanna/docs
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEX = HERE / "data" / "lexicon"
PROJ = HERE.parent
THAPSAP = Path(os.environ.get("THAPSAP_DATA") or
               PROJ / "thapsap" / "exports" / "thapsap.json")
THAIROOTS = PROJ / "thairoots" / "index.html"

STRUCTURAL = {"HAS_SENSE", "COMPOUND_OF", "IN_DOMAIN", "HAS_REGISTER",
              "FROM_ETYMON", "SOUND_KEY", "SAME_AS", "IN_SOURCE", "CONTAINS_HEAD"}


def load_json(p, default=None):
    try:
        return json.loads(Path(p).read_text("utf-8"))
    except Exception:
        return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", required=True)
    a = ap.parse_args()
    docs = Path(a.docs)

    nodes, edges = OrderedDict(), []
    by_thai = defaultdict(set)
    src_count = Counter()

    def node(nid, cls, label, source, **kw):
        if nid not in nodes:
            nodes[nid] = {"id": nid, "c": cls, "l": label, "src": source,
                          **{k: v for k, v in kw.items() if v is not None}}
            src_count[source] += 1
        return nodes[nid]

    def edge(rel, a_, b_, **kw):
        edges.append({"rel": rel, "from": a_, "to": b_,
                      "kind": "structural" if rel in STRUCTURAL else "asserted",
                      **{k: v for k, v in kw.items() if v is not None}})

    def index(th, nid):
        if th:
            by_thai[th].add(nid)

    # --- รากศัพท์ · the lexicon ------------------------------------------
    for f in sorted((LEX / "entries").glob("*.json")):
        d = json.loads(f.read_text("utf-8"))
        wid = d["id"]
        node(wid, "word", d["th"], "lexicon", rtgs=d.get("rtgs"),
             ipa=d.get("ipa"), core=d.get("core_image"),
             h=f"/kham/{wid[2:]}/", status=d.get("status"))
        index(d["th"], wid)
        for s in d["senses"]:
            sid = f"{wid}#{s['n']}"
            en = [x for x in s["gloss"]["en"] if not x.startswith("[")]
            node(sid, "sense", "; ".join(en) or (s["gloss"].get("th") or "")[:60],
                 "lexicon", word=wid, n=s["n"], h=f"/kham/{wid[2:]}/#s{s['n']}")
            edge("HAS_SENSE", wid, sid)
            if s.get("extends"):
                edge("EXTENDS", sid, f"{wid}#{s['extends']}", via=s.get("via"),
                     note=s.get("via_note"), conf=s.get("via_conf"))
            for dm in s.get("domains", []):
                node(dm, "domain", dm.split(":", 1)[-1], "lexicon")
                edge("IN_DOMAIN", sid, dm)
            for c in s.get("compounds", []):
                cid = f"w:{re.sub('[^a-z0-9-]', '-', (c.get('rtgs') or c.get('translit_auto') or 'x').lower())}"
                node(cid, "compound", c["th"], "lexicon", lit=c.get("lit"),
                     pattern=c.get("pattern"))
                index(c["th"], cid)
                edge("HEADS", sid, cid, note=c.get("lit"), conf=c.get("conf"))
                for p in c.get("parts", []):
                    edge("COMPOUND_OF", cid, next(iter(by_thai.get(p, [f"w:?{p}"]))))
        for c in d.get("compounds_unassigned", []):
            cid = f"w:{re.sub('[^a-z0-9-]', '-', (c.get('rtgs') or c.get('translit_auto') or 'x').lower())}"
            node(cid, "compound", c["th"], "lexicon", lit=c.get("lit"),
                 pattern=c.get("pattern"), unfiled=True)
            index(c["th"], cid)
            edge("COMPOUND_OF", cid, wid)

    # --- ทับศัพท์ · borrowings -------------------------------------------
    tp = load_json(THAPSAP)
    if tp:
        for e in tp.get("entries", []):
            lid = "l:" + re.sub(r"[^a-z0-9]+", "-", (e.get("reads") or e["th"])).strip("-")
            node(lid, "loanword", e["th"], "thapsap", en=e.get("en"),
                 seen=e.get("seen"), h="/phasa/")
            index(e["th"], lid)
            if e.get("en"):
                sid = "src:en:" + re.sub(r"[^a-z0-9]+", "-", e["en"].lower())
                node(sid, "etymon", e["en"], "thapsap", lang="English")
                edge("BORROWED_FROM", lid, sid, conf=(
                    "verified" if e.get("how") == "hand" else "probable"),
                    note=f"method: {e.get('how')}")
            if e.get("misread"):
                # the romanizer's reading of a borrowing is wrong BY CONSTRUCTION —
                # RTGS transcribes Thai letters, and these letters are spelling
                # English. Recording it is what lets a page warn instead of mislead.
                edge("MISREAD_AS", lid, "read:" + e["misread"],
                     note="RTGS reads the Thai letters; the word is English underneath",
                     conf="verified")
                node("read:" + e["misread"], "reading", e["misread"], "thapsap")

    # --- the wichaa glossary ---------------------------------------------
    for g in (load_json(docs / "api" / "glossary.json") or {}).get("entries", []):
        tid = "t:" + re.sub(r"[^a-z0-9]+", "-", (g.get("roman") or g["term"])).strip("-")
        node(tid, "term", g["term"], "glossary", roman=g.get("roman"),
             en=(g.get("glosses") or {}).get("en"), h="/glossary/")
        index(g["term"], tid)
        if g.get("domain"):
            node("d:" + g["domain"], "domain", g.get("domainLabel") or g["domain"], "glossary")
            edge("IN_DOMAIN", tid, "d:" + g["domain"])

    # --- ถ่ายเสียง · the sound-change cards ------------------------------
    if THAIROOTS.exists():
        html = THAIROOTS.read_text("utf-8", errors="ignore")
        for m in re.finditer(r'\{"id":"(K\d+)","name":"([^"]{2,120})"', html):
            node("k:" + m.group(1), "soundkey", m.group(2), "thairoots")

    # --- THE JOIN --------------------------------------------------------
    # Exact string equality joins almost nothing: the glossary's พระเครื่อง is not
    # spelled the same as the lexicon's พระ. The join that matters is
    # morphological — a term on any surface is a door to the heads inside it —
    # and it uses the same test the lexicon was built on: a split counts only when
    # the REMAINDER is itself a dictionary word, so พระ+เครื่อง passes and a
    # coincidental substring does not.
    full = load_json(PROJ / "thairoots" /
                     "_downloads drop 2026-08-17 (builds + dictionary dumps)" /
                     "thai-full.json", {})
    W = set(full)
    heads = {nodes[i]["l"]: i for i in nodes if nodes[i]["c"] == "word"}

    # A BORROWED WORD MUST NOT BE CUT WITH THAI MORPHOLOGY. The remainder test
    # alone passes on nonsense the moment the input is a loan: ราหู is Sanskrit
    # rāhu and split as หู 'ear' + รา; เมตตา is Pali mettā and split as ตา 'eye';
    # เพลส is the English "Place" and split as พล + เส. This is the ตาย-under-ตา
    # failure the whole lexicon was built to avoid, resurfacing one layer up,
    # and the fix is the same in spirit: require the word to be Thai-formed
    # before believing a Thai-formed analysis of it.
    LOAN = re.compile(r"บาลี|สันสกฤต|ยืมมาจาก|เขมร|อังกฤษ|จีน|มลายู|โปรตุเกส")

    def borrowed(th):
        ety = " ".join(full.get(th, {}).get("ety") or [])
        return bool(ety and LOAN.search(ety))

    contains = skipped = 0
    for th, ids in list(by_thai.items()):
        for nid in ids:
            if nodes[nid]["src"] == "lexicon" and nodes[nid]["c"] == "word":
                continue
            if nodes[nid]["c"] == "loanword" or borrowed(th):
                skipped += 1
                continue
            # Longest head first: น้ำมันมนต์ is น้ำมัน + มนต์, not มัน + น้ำมนต์,
            # and taking the first match found rather than the longest picks the
            # shorter, wronger analysis.
            best = None
            for h, hid in heads.items():
                if h == th or h not in th or len(h) < 2:
                    continue
                rest = th.replace(h, "", 1)
                if len(rest) >= 2 and (rest in W or rest.strip() in W):
                    if best is None or len(h) > len(best[0]):
                        best = (h, hid, rest)
            if best:
                h, hid, rest = best
                edge("CONTAINS_HEAD", nid, hid, note=f"{th} = {h} + {rest}",
                     conf="verified")
                contains += 1

    joins = 0
    for th, ids in by_thai.items():
        if len(ids) < 2:
            continue
        ids = sorted(ids)
        for i, x in enumerate(ids):
            for y in ids[i + 1:]:
                if nodes[x]["src"] != nodes[y]["src"]:
                    edge("SAME_AS", x, y,
                         note=f"the same Thai string in {nodes[x]['src']} and {nodes[y]['src']}",
                         conf="verified")
                    joins += 1

    out = docs / "api" / "phasa"
    out.mkdir(parents=True, exist_ok=True)
    (out / "graph.json").write_text(json.dumps(
        {"nodes": list(nodes.values()), "edges": edges}, ensure_ascii=False) + "\n", "utf-8")
    (out / "resolve.json").write_text(json.dumps(
        {k: sorted(v) for k, v in sorted(by_thai.items())}, ensure_ascii=False) + "\n", "utf-8")

    print(f"nodes {len(nodes)} · edges {len(edges)}")
    print("by source :", dict(src_count))
    print("classes   :", dict(Counter(n["c"] for n in nodes.values())))
    print("relations :", dict(Counter(e["rel"] for e in edges).most_common(10)))
    print(f"cross-source SAME_AS joins: {joins}")
    print(f"CONTAINS_HEAD joins (a term is a door to the head inside it): {contains}")
    print(f"  refused on {skipped} borrowed words — a loan is not built from Thai parts")
    print(f"resolver: {len(by_thai)} Thai strings addressable")
    print(f"wrote {out}/graph.json + resolve.json")


if __name__ == "__main__":
    main()
