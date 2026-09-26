#!/usr/bin/env python3
"""lexicon_compounds — the literal reading, the shape, and the cross-listings.

WHY THE LITERAL READING IS THE POINT
A compound entry that says only "ตาข่าย = net" teaches nothing. What teaches is
"eye + net" — the moment a reader sees that Thai calls the holes in a net its
eyes, every other ตา- compound gets easier and the sense map earns its keep. That
field was filled on 23 of 8,104 compounds, all of them hand-written for แก้ว.

It can be composed, because every compound here is two words that are BOTH
dictionary headwords — that was the selection test — so each part can be glossed
from one of three sources, in this order of quality:

    the 300 heads of this lexicon   full sense map, so the core sense is known
    the Wiktionary English bridge   a word-level gloss
    the RID's own Thai definition   always present; Thai side only

A composed reading is not the compound's meaning and must never be printed as
one: ร้อยแก้ว reads "string + gem" and means prose. So `lit` carries conf
"probable" and the page labels it lit., the way a dictionary does.

WHAT ELSE FALLS OUT
  · `pattern`  the POS shape (N+N, N+V …), counted across the whole set
  · `head`     which part this entry heads — head-initial is the Thai norm, and
               the exceptions are worth being able to list
  · `cross_listed`  1,363 compounds file under more than one head (น้ำตา under
               both น้ำ and ตา). Recording it stops the same word reading as two
               unrelated ones.

    python3 lexicon_compounds.py --write
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEX = HERE / "data" / "lexicon"
DUMPS = (HERE.parent / "thairoots" /
         "_downloads drop 2026-08-17 (builds + dictionary dumps)")

POS_SHORT = {"คำนาม": "N", "คำกริยา": "V", "คำคุณศัพท์": "ADJ", "คำวิเศษณ์": "ADV",
             "คำลักษณนาม": "CLF", "คำสรรพนาม": "PRON", "คำบุพบท": "PREP",
             "คำสันธาน": "CONJ", "คำอุทาน": "INTJ", "คำวิสามานยนาม": "PROP"}


def trim(s, n=40):
    s = re.split(r"[,;(]", (s or "").strip())[0].strip()
    return s[:n].strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    full = json.loads((DUMPS / "thai-full.json").read_text("utf-8"))
    inv = json.loads((DUMPS / "wikt-en-bridge.json").read_text("utf-8"))["inv"]
    files = sorted((LEX / "entries").glob("*.json"))
    entries = {}
    for f in files:
        d = json.loads(f.read_text("utf-8"))
        entries[d["th"]] = (f, d)

    # part -> short English / short Thai, best source first
    def _en_from_sense(s):
        g = [x for x in s["gloss"]["en"] if not x.startswith("[")]
        return trim(g[0]) if g else None

    def en_of(w, sense=None):
        """Best English gloss, falling THROUGH each source rather than stopping at
        the first that exists.

        `sense` matters more than it looks. 108 of these entries hold several words
        under one spelling, and the first rootless sense is not always the right
        one: ตา is both 'maternal grandfather' and 'eye', and ตาข่าย composes with
        the eye. Where a compound has been filed under a sense, that sense supplies
        the gloss; otherwise the first sense that has English does, which is a
        guess and is why lit carries conf 'probable'.
        """
        ent = entries.get(w)
        if ent:
            if sense is not None:
                for s in ent[1]["senses"]:
                    if s["n"] == sense:
                        g = _en_from_sense(s)
                        if g:
                            return g
                        break
            # bridge_en BEFORE any-other-sense: once the copied glosses were
            # stripped, the only sense left with English on some heads was the
            # place-name one, and ตาน้อย started composing as "ta as an element in
            # place names + noi as an element in place names". A word-level gloss
            # is the right object for a literal reading; a name-use sense never is.
            b = ent[1].get("bridge_en")
            if b:
                return trim(b[0])
            for s in ent[1]["senses"]:
                if (s["gloss"].get("th") or "").strip() == "ใช้ประกอบชื่อสถานที่":
                    continue
                g = _en_from_sense(s)
                if g:
                    return g
        v = inv.get(w)
        if v:
            return trim(v[0])
        return None

    def th_of(w, sense=None):
        ent = entries.get(w)
        if ent:
            if sense is not None:
                for s in ent[1]["senses"]:
                    if s["n"] == sense and s["gloss"].get("th"):
                        return trim(s["gloss"]["th"], 34)
            for s in ent[1]["senses"]:
                if s["gloss"].get("th"):
                    return trim(s["gloss"]["th"], 34)
        g = full.get(w, {}).get("g")
        return trim(g[0], 34) if g else None

    def pos_of(w):
        p = full.get(w, {}).get("pos") or []
        return POS_SHORT.get(p[0], "?") if p else "?"

    # first pass: where does each compound word appear?
    where = defaultdict(set)
    for th, (f, d) in entries.items():
        for c in [x for s in d["senses"] for x in s.get("compounds", [])] + \
                 d.get("compounds_unassigned", []):
            where[c["th"]].add(th)

    stats = Counter()
    pats = Counter()
    for th, (f, d) in entries.items():
        touched = False
        filed = [(x, s["n"]) for s in d["senses"] for x in s.get("compounds", [])]
        filed += [(x, None) for x in d.get("compounds_unassigned", [])]
        for c, under in filed:
            parts = c.get("parts") or []
            if len(parts) == 2:
                pa, pb = parts
                sa = under if pa == th else None
                sb = under if pb == th else None
                ea, eb = en_of(pa, sa), en_of(pb, sb)
                ta, tb = th_of(pa, sa), th_of(pb, sb)
                # The reading is composed at the sense the compound is FILED
                # under, so it has to be recomposed when the filing changes.
                # Writing it once left 1,061 readings frozen at sense 1, where
                # they landed while the compound was still unassigned: ตะวันออก
                # read "sun + noble title prefix" because ออก's first sense is
                # the ออกญา honorific. A stored reading is only ever replaced
                # when it is the machine's own "a + b" shape — a hand-written
                # lit (แก้ว's "glass screen") has no " + " and is never touched,
                # and the model entry is held back entirely.
                model = th == "แก้ว"

                def _put(key, new):
                    old = c.get(key)
                    if not new:
                        return False
                    if old is None:
                        c[key] = new
                        stats[key] += 1
                        return True
                    if old != new and " + " in old and not model:
                        c[key] = new
                        stats[key + " recomposed"] += 1
                        return True
                    return False

                if _put("lit", f"{ea} + {eb}" if ea and eb else None):
                    touched = True
                elif not c.get("lit"):
                    stats["lit not composable in English"] += 1
                if _put("lit_th", f"{ta} + {tb}" if ta and tb else None):
                    touched = True
                pat = f"{pos_of(pa)}+{pos_of(pb)}"
                if "?" not in pat and not c.get("pattern"):
                    c["pattern"] = pat
                    pats[pat] += 1
                    stats["pattern"] += 1
                    touched = True
                if th in parts and c.get("head") is None:
                    c["head"] = parts.index(th)
                    stats["head recorded"] += 1
                    touched = True
            others = sorted(where[c["th"]] - {th})
            if others and not c.get("cross_listed"):
                c["cross_listed"] = others
                stats["cross-listed"] += 1
                touched = True
        if touched and a.write:
            f.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", "utf-8")

    for k, v in stats.most_common():
        print(f"  {v:6}  {k}")
    print("\ncompound POS shapes, most common first:")
    tot = sum(pats.values())
    for p, n in pats.most_common(10):
        print(f"  {n:6}  {p:10} {n/tot:5.1%}")
    if not a.write:
        print("\n(dry run — pass --write)")


if __name__ == "__main__":
    main()
