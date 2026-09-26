#!/usr/bin/env python3
"""add_nameuse_senses — give place-name formatives the sense they were missing.

WHY A SENSE CAN BE ADDED THAT THE SOURCE DOES NOT LIST
The RID's entry for หนอง defines a marsh. It does not list "used to name places",
and yet eighty of หนอง's dictionary-attested compounds are definitions of the form
ชื่อตำบลหนึ่งในอำเภอ… — the dictionary documents the usage exhaustively while never
naming it as a sense. The compounds ARE the evidence, and they are countable, so
this is not an assertion dropped on the entry: it is a sense justified by a number
anyone can re-derive.

Threshold is three. A head with eighty place names demonstrably works as a name
formative; a head with one has a coincidence, and 39 such heads are deliberately
left alone rather than given a sense to tidy up a queue.

WHAT THE NORTHERN COUNT CAN AND CANNOT SAY
Cross-counting against the northern wat registry separates formatives that build
names up here — แม่, นา, หนอง, บ้าน, ป่า, ศรี — from ones the dictionary is full of
and the north has almost none of: บาง, คลอง, โนน. That absence is worth recording
on a Lanna site. Where those names ARE built is a different claim and this data
cannot make it: the registry is northern only, so "absent from the north" is the
finding, and "central" or "Isan" would be a guess wearing a number's clothes.

    python3 scripts/add_nameuse_senses.py --write
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
LEX = HERE / "data" / "lexicon"
WATS = HERE.parent / "wat-registry" / "wats_north.json"
SEG = HERE.parent / "search-core" / "data" / "wichaa.segdict.txt"
MARKER = "ใช้ประกอบชื่อสถานที่"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=3)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    wats = json.loads(WATS.read_text("utf-8"))
    wats = wats if isinstance(wats, list) else wats.get("wats", wats)
    names = [str(w.get("nameTh", "")) for w in wats]
    seg = SEG.read_text("utf-8").split("\n") if SEG.exists() else []

    added = skipped = below = 0
    rows = []
    for f in sorted((LEX / "entries").glob("*.json")):
        d = json.loads(f.read_text("utf-8"))
        topo = [c for c in d.get("compounds_unassigned", []) if c.get("use") == "toponym"]
        if not topo:
            continue
        if any((s["gloss"].get("th") or "").strip().startswith("ชื่อ")
               or (s["gloss"].get("th") or "").strip() == MARKER for s in d["senses"]):
            skipped += 1
            continue
        if len(topo) < a.min:
            below += 1
            continue

        th = d["th"]
        nw = sum(1 for n in names if th in n)
        ns = sum(1 for x in seg if th in x)
        region = ""
        if len(topo) >= 20 and nw <= 5:
            region = (f" Heavy in the dictionary ({len(topo)} place names) but nearly "
                      f"absent from the northern wat registry ({nw} of {len(wats)}), so "
                      f"it builds names somewhere other than the Lanna north. WHERE is "
                      f"not measurable from this project's data, which is northern only.")
        elif nw >= 50:
            region = (f" Strongly northern: {nw} of the {len(wats)} wats in the northern "
                      f"registry carry it, and {ns} entries of the segmentation dictionary.")

        n = max(s["n"] for s in d["senses"]) + 1
        sense = {
            "n": n,
            "gloss": {"en": [f"{d.get('rtgs') or th} as an element in place names"],
                      "th": MARKER, "conf": "standard", "src": ["RID", "CUR"]},
            "def": (f"Used to build place names. Not listed as a sense by the RID, but "
                    f"{len(topo)} of this head's dictionary-attested compounds are place-name "
                    f"definitions (ชื่อตำบล / ชื่ออำเภอ / ชื่อเขต).{region}"),
            "def_th": f"ใช้ประกอบชื่อสถานที่ — พบในคำที่พจนานุกรมนิยามว่าเป็นชื่อสถานที่ {len(topo)} คำ",
            "pos": "proper noun", "pos_th": "วิสามานยนาม",
            "domains": ["d:toponym", "d:place"],
            "order_conf": "unverified",
            "conf": "standard",
            "src": ["RID", "CUR"] + (["wat-registry"] if nw else []),
            "needs_check": [
                "This sense is NOT in the RID's own sense list. It is added on counted "
                f"evidence — {len(topo)} place-name compounds — and which literal sense "
                "it grew out of has not been argued, so it carries no EXTENDS edge yet.",
            ],
        }
        if nw:
            sense["edges"] = [{
                "rel": "ATTESTED_IN", "to": "corpus:wat-registry",
                "label": f"{nw} of {len(wats)} northern wats",
                "note": "A counted edge, re-derivable from wats_north.json.",
                "conf": "verified", "src": ["wat-registry"]}]
        d["senses"].append(sense)
        added += 1
        rows.append((len(topo), th, nw, ns, bool(region)))
        if a.write:
            f.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", "utf-8")

    rows.sort(reverse=True)
    print(f"name-use senses added: {added} "
          f"(skipped {skipped} that already had one; {below} below the --min {a.min} threshold)")
    print(f"toponym compounds unblocked: {sum(r[0] for r in rows)}")
    print("\n  dict  wats  seg   head")
    for t, th, nw, ns, reg in rows[:14]:
        print(f"  {t:4}  {nw:4}  {ns:3}   {th}{'   ← absent from the north' if reg and nw <= 5 else ''}")
    if not a.write:
        print("\n(dry run — pass --write)")


if __name__ == "__main__":
    main()
