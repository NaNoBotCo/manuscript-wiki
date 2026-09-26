#!/usr/bin/env python3
"""phasa_portal — the doors, and what is behind them.

"Every surface of meaning should be a portal to the semantic network."

phasa_graph.py built the network and a resolver, and nothing consumed either. A
contract with no client is not a portal. This emits what a page actually needs to
turn Thai text into doors, and — the part that matters — what a reader finds when
they walk through one.

WHAT IS BEHIND A DOOR
Not a definition. A neighbourhood. Arriving at ใจ should show its senses, the
compounds filed under each, what it is built from, every word it is found INSIDE,
the word it flips with, the words that sound identical and are not it, and the
family of compounds that share its modifier. Nine relations, because a word's
meaning in Thai is mostly its company.

THE RELATION NOBODY FILED
`family` is computed here and exists nowhere else: compounds grouped by their
MODIFIER rather than their head. ดี gives ใจดี, หัวดี, คนดี, ของดี, ขวัญดี, น้ำดี,
นาดี, ได้ดี — a heart, a head, a person, a thing, a soul, a bile, a field and a
fortune, all being good in the same grammatical way. 489 such families. Nothing
in any source lists them; they fall out of the parts, and they are the best
reason to wander.

    python3 phasa_portal.py --docs ../nanobotco-lanna/docs
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from lexicon_tags import is_compound

HERE = Path(__file__).resolve().parent
LEX = HERE / "data" / "lexicon" / "entries"


def slug(s):
    return re.sub(r"[^a-z0-9-]+", "-", (s or "x").lower()).strip("-") or "x"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", required=True)
    a = ap.parse_args()
    docs = Path(a.docs)
    api = docs / "api" / "phasa"

    entries = [json.loads(f.read_text("utf-8")) for f in sorted(LEX.glob("*.json"))]
    net = json.loads((api / "graph.json").read_text("utf-8"))
    NODES = {n["id"]: n for n in net["nodes"]}

    def all_comps(e):
        return [(c, s["n"]) for s in e["senses"] for c in s.get("compounds", [])] + \
               [(c, None) for c in e.get("compounds_unassigned", [])]

    # ---- indexes -------------------------------------------------------
    head_of = {e["th"]: e for e in entries}
    inside = defaultdict(list)       # part -> compounds containing it
    bymod = defaultdict(list)        # modifier -> compounds
    byrtgs = defaultdict(set)        # rtgs -> heads that read the same
    card = {}                        # thai -> the door's face

    for e in entries:
        if e.get("rtgs"):
            byrtgs[e["rtgs"]].add(e["th"])
        card[e["th"]] = {"id": e["id"], "c": "word", "th": e["th"],
                         "r": e.get("rtgs") or e.get("translit_auto"),
                         "g": e.get("core_image") or "",
                         "h": f"/kham/{e['id'][2:]}/"}
        for c, sn in all_comps(e):
            if not is_compound(c):
                continue
            p = c.get("parts") or []
            for part in p:
                inside[part].append((c["th"], e["th"]))
            if len(p) == 2 and e["th"] in p:
                bymod[p[1] if p[0] == e["th"] else p[0]].append((c["th"], e["th"]))
            en = [x for x in c["gloss"]["en"] if not x.startswith("[")]
            card.setdefault(c["th"], {
                "id": "c:" + slug(c.get("rtgs") or c.get("translit_auto") or c["th"]),
                "c": "compound", "th": c["th"],
                "r": c.get("rtgs") or c.get("translit_auto"),
                "g": "; ".join(en) or (c["gloss"].get("th") or "")[:70],
                "lit": c.get("lit"), "frame": c.get("frame"),
                "h": f"/kham/{head_of[e['th']]['id'][2:]}/#s{sn}" if sn else
                     f"/kham/{head_of[e['th']]['id'][2:]}/"})

    # loanwords and glossary terms are doors too
    for n in net["nodes"]:
        if n["c"] in ("loanword", "term") and n["l"] not in card:
            card[n["l"]] = {"id": n["id"], "c": n["c"], "th": n["l"],
                            "r": n.get("roman"), "g": n.get("en") or "",
                            "h": n.get("h") or "/phasa/"}

    # ---- the neighbourhood ---------------------------------------------
    hood = {}
    for e in entries:
        th, wid = e["th"], e["id"]
        senses = []
        for s in e["senses"]:
            en = [x for x in s["gloss"]["en"] if not x.startswith("[")]
            senses.append({
                "n": s["n"], "en": en, "th": (s["gloss"].get("th") or "")[:110],
                "extends": s.get("extends"), "via": s.get("via"),
                "why": s.get("via_note"),
                "compounds": [c["th"] for c in s.get("compounds", [])
                              if is_compound(c)],
            })
        flips = [c["flips_with"] for c, _ in all_comps(e) if c.get("flips_with")]
        fam = {}
        for c, _ in all_comps(e):
            p = c.get("parts") or []
            if len(p) == 2 and th in p and is_compound(c):
                mod = p[1] if p[0] == th else p[0]
                sibs = [w for w, h in bymod.get(mod, []) if h != th]
                if len(sibs) >= 2:
                    fam.setdefault(mod, sorted(set(sibs))[:10])
        hood[wid] = {
            "th": th, "rtgs": e.get("rtgs"), "ipa": e.get("ipa"),
            "core": e.get("core_image"), "senses": senses,
            "inside": sorted({w for w, _ in inside.get(th, [])})[:60],
            "flips": sorted(set(flips)),
            "sounds_like": sorted(byrtgs.get(e.get("rtgs") or "", set()) - {th}),
            "family": fam,
            "open": [c["th"] for c, sn in all_comps(e)
                     if sn is None and not c.get("use")],
        }

    api.mkdir(parents=True, exist_ok=True)
    # longest first: the client matches greedily and must not take ตา out of ตาข่าย
    (api / "lookup.json").write_text(json.dumps(
        {"order": sorted(card, key=lambda w: -len(w)), "card": card},
        ensure_ascii=False) + "\n", "utf-8")
    (api / "neighbours.json").write_text(
        json.dumps(hood, ensure_ascii=False) + "\n", "utf-8")

    fams = sum(len(v["family"]) for v in hood.values())
    print(f"doors (addressable Thai strings): {len(card)}")
    print(f"  words {sum(1 for c in card.values() if c['c']=='word')} · "
          f"compounds {sum(1 for c in card.values() if c['c']=='compound')} · "
          f"loanwords {sum(1 for c in card.values() if c['c']=='loanword')} · "
          f"glossary terms {sum(1 for c in card.values() if c['c']=='term')}")
    print(f"neighbourhoods: {len(hood)}")
    print(f"  found-inside lists {sum(1 for v in hood.values() if v['inside'])} · "
          f"flip pairs {sum(len(v['flips']) for v in hood.values())} · "
          f"sound-alike sets {sum(1 for v in hood.values() if v['sounds_like'])} · "
          f"modifier families {fams}")
    print(f"wrote {api}/lookup.json + neighbours.json")


if __name__ == "__main__":
    main()
