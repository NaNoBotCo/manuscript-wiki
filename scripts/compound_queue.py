#!/usr/bin/env python3
"""compound_queue — the work queue for filing compounds under senses.

WHY A QUEUE AND NOT A CLASSIFIER
This job cannot be automated and the measurement is on the record: where a SOURCE
says which sense a compound belongs to, it is the head's core sense 9% of the time
(18% counting only Wiktionary's own examples). Gloss similarity picks the core
sense 91% of the time. It is not weakly right, it is anti-correlated — one-line RID
glosses do not say which sense a compound uses, and a bag of trigrams lands on
whichever sense carries the most text. So the filing is done by READING, and this
tool exists to make the reading cheap: it hands over one head at a time with its
senses and its unfiled compounds, and takes back a table.

    python3 scripts/compound_queue.py --next            one head, ready to read
    python3 scripts/compound_queue.py --status          what is left, and where
    python3 scripts/compound_queue.py --apply <slug>    file from data/lexicon/filing/

A head's filing lives in data/lexicon/filing/<slug>.json as a RULE and a map of
sense number to words. The rule is written first and the words sorted under it, so
a wrong call is a wrong rule that can be argued with, rather than eighty-four
separate mistakes that cannot.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
ENTRIES = HERE / "data" / "lexicon" / "entries"
FILING = HERE / "data" / "lexicon" / "filing"
LEDGER = HERE / "data" / "lexicon" / "FILING_LOG.md"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lexicon_tags import NOT_A_COMPOUND  # noqa: E402


def load():
    out = []
    for f in sorted(ENTRIES.glob("*.json")):
        d = json.loads(f.read_text("utf-8"))
        opens = [c for c in d.get("compounds_unassigned", [])
                 if c.get("use") not in NOT_A_COMPOUND]
        out.append((f, d, opens))
    return out


def show(d, opens):
    print(f"HEAD  {d['th']}  ({d.get('rtgs')})   file: "
          f"data/lexicon/filing/{d['id'][2:]}.json")
    print(f"\nSENSES ({len(d['senses'])}) — file under these numbers:")
    for s in d["senses"]:
        en = [x for x in s["gloss"]["en"] if not x.startswith("[")]
        note = " ← CORE" if not s.get("extends") else \
               f"  (from {s['extends']}, {s.get('via','')})"
        print(f"  {s['n']:2}. {(en[0] if en else '')[:24]:<26}"
              f"{(s['gloss'].get('th') or '')[:44]}{note}")
    print(f"\nUNFILED ({len(opens)}):")
    for c in opens:
        lit = f"  [{c['lit']}]" if c.get("lit") else ""
        print(f"  {c['th']:<14}{(c['gloss'].get('th') or '')[:52]}{lit}")
    print("\nWrite the RULE first, then sort every word above under a sense number.")
    print("Anything that is NOT a compound of this head (a borrowing whose spelling")
    print("happens to start with it) gets use:\"false-split\" instead of a sense.")


def apply(slug, write):
    doc = json.loads((FILING / f"{slug}.json").read_text("utf-8"))
    f = ENTRIES / f"{slug}.json"
    d = json.loads(f.read_text("utf-8"))
    want = {w: int(n) for n, ws in doc["senses"].items() for w in ws}
    by_n = {s["n"]: s for s in d["senses"]}
    keep, moved, unknown = [], Counter(), []
    for c in d.get("compounds_unassigned", []):
        n = want.get(c["th"])
        if n is None or n not in by_n:
            if c.get("use") not in NOT_A_COMPOUND:
                unknown.append(c["th"])
            keep.append(c)
            continue
        c = dict(c)
        c["conf"] = "standard"
        c["src"] = sorted(set((c.get("src") or []) + ["CUR"]))
        c["note"] = ((c.get("note", "") + " · ") if c.get("note") else "") + \
                    f"filed under sense {n} by hand"
        by_n[n].setdefault("compounds", []).append(c)
        moved[n] += 1
    if keep:
        d["compounds_unassigned"] = keep
    else:
        d.pop("compounds_unassigned", None)
    if write:
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", "utf-8")
    print(f"{d['th']:<6} filed {sum(moved.values()):3} {dict(sorted(moved.items()))}"
          f"  left {len(keep)}"
          + (f"  NOT NAMED: {' '.join(unknown)}" if unknown else ""))
    return sum(moved.values()), unknown


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--next", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--apply")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    if a.apply:
        apply(a.apply, a.write)
        if not a.write:
            print("(dry run — pass --write)")
        return

    rows = load()
    todo = sorted(((len(o), d, f) for f, d, o in rows if o), reverse=True,
                  key=lambda r: r[0])
    if a.status:
        done = sum(len(s.get("compounds", [])) for _, d, _ in rows for s in d["senses"])
        left = sum(n for n, _, _ in todo)
        print(f"filed {done} · unfiled {left} across {len(todo)} heads")
        print(f"filing tables written: {len(list(FILING.glob('*.json')))}")
        print("\nnext ten:")
        for n, d, _ in todo[:10]:
            print(f"  {n:4}  {d['th']:<8} {d.get('rtgs','')}")
        return

    if not todo:
        print("queue empty — every compound is filed.")
        return
    n, d, f = todo[0]
    opens = [c for c in d.get("compounds_unassigned", [])
             if c.get("use") not in NOT_A_COMPOUND]
    show(d, opens)


if __name__ == "__main__":
    main()
