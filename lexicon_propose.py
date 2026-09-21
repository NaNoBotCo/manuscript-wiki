#!/usr/bin/env python3
"""lexicon_propose — file compounds under senses, in tiers, by how well sourced.

THE NEGATIVE FINDING THAT SHAPES THIS
No dictionary here files compounds under senses. Measured over all 8,078 attested
compounds of the 300 heads:

    sense gloss literally names the compound (RID)      1.6%
    compound appears as a sense EXAMPLE (Wiktionary)    2.8%
    ------------------------------------------------------
    filed by a source, combined                        ~4%

So ~96% of the filing is unsourced editorial judgment. Rather than hide that
behind a similarity score, this tool separates what a source says from what a
machine guesses, and refuses to guess when the guess is not decisive:

    tier 1  sourced   the dictionary put the compound under that sense
    tier 2  proposed  gloss similarity, and only where one sense wins clearly
    tier 3  open      left in compounds_unassigned, queued for a human

Tier 1 is written with conf "verified" and its real src. Tier 2 is written with
conf "probable", `proposed_by` naming the method and its margin, and the entry
drops to status "proposed" — never "mapped", which stays reserved for a human.
Tier 3 is the honest remainder and is reported, never silently absorbed.

    python3 lexicon_propose.py            # measure only
    python3 lexicon_propose.py --write
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEX = HERE / "data" / "lexicon"
MARGIN = 0.08          # a win this small is not a win
FLOOR = 0.10           # and it must clear a floor of actual overlap


def grams(s, n=3):
    s = re.sub(r"[\s,.;:()\[\]\"'“”‘’]+", "", s or "")
    return Counter(s[i:i + n] for i in range(max(0, len(s) - n + 1)))


def dice(a, b):
    if not a or not b:
        return 0.0
    inter = sum((a & b).values())
    return 2 * inter / (sum(a.values()) + sum(b.values()))


# RID definitions are formulaic, and the FORM of a definition is itself evidence
# about what the compound does. "ชื่อตำบลหนึ่งในอำเภอ…" is not a sense of the head
# that needs arguing about — it is the head used to name a place. Classifying on
# the definition's opening is sourced (it is the dictionary's own wording), and it
# reaches a fifth of the backlog that similarity could never touch.
USE_RULES = [
    ("toponym",       re.compile(r"^ชื่อ(ตำบล|อำเภอ|จังหวัด|เขต|แขวง|หมู่บ้าน|บ้าน|เมือง|แม่น้ำ|ภูเขา|เกาะ|คลอง)")),
    ("biological",    re.compile(r"^ชื่อ(ไม้|ต้นไม้|พรรณไม้|สัตว์|นก|ปลา|แมลง|งู|เห็ด|หญ้า|ผัก|ผลไม้)")),
    ("calendrical",   re.compile(r"^ชื่อ(เดือน|ปี|วัน|ฤดู)")),
    ("personal-name", re.compile(r"^ชื่อ(จริง|เล่น|บุคคล)")),
    ("nominalisation", re.compile(r"^คำอาการนามของ")),
    ("synonym-pointer", re.compile(r"^(คำพ้องความของ|ดู\s)")),
]


def classify_use(gloss):
    for name, rx in USE_RULES:
        if rx.match((gloss or "").strip()):
            return name
    return None


def sense_text(s, filed):
    """What a sense looks like, in words, for comparison.

    The sense's own gloss is thin — one RID line — so the compounds ALREADY filed
    under it are folded in as exemplars. A sense that has collected ตาข่าย and
    ตาตาราง describes itself better through them than through its definition, and
    2,649 compounds were filed by sourced evidence in the earlier pass, which is
    what makes them safe to learn from.
    """
    parts = [s["gloss"].get("th", ""), " ".join(s["gloss"].get("en", []))]
    for c in filed:
        parts.append(c["gloss"].get("th", ""))
        parts.append(" ".join(x for x in c["gloss"].get("en", []) if not x.startswith("[")))
    return " ".join(parts)


def compound_text(c):
    """And the compound, likewise — its gloss plus the literal reading, which
    carries both parts' glosses and is often the only text that discriminates."""
    return " ".join([c["gloss"].get("th", ""),
                     " ".join(x for x in c["gloss"].get("en", []) if not x.startswith("[")),
                     c.get("lit_th", ""), c.get("lit", "")])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--margin", type=float, default=MARGIN)
    ap.add_argument("--similarity", action="store_true",
                    help="enable the gloss-similarity tier. Measured anti-correlated "
                         "with sourced filings (91%% core vs the source's 9%%); off "
                         "by default and kept only so the result can be re-checked.")
    a = ap.parse_args()

    wsenses = json.loads((LEX / "senses.json").read_text("utf-8"))
    files = sorted((LEX / "entries").glob("*.json"))
    tier = Counter()
    changed = 0
    review = []

    for f in files:
        d = json.loads(f.read_text("utf-8"))
        # Sense ORDERING and compound FILING are different axes. `mapped` means
        # the senses were ordered, which is now true of 284 entries and would skip
        # nearly the whole corpus if read as "finished". Only the hand-written
        # entry is protected here.
        if d["th"] == "แก้ว":
            tier["skipped (hand-written)"] += 1
            continue
        unassigned = d.get("compounds_unassigned") or []
        if not unassigned:
            continue
        senses = d["senses"]
        sg = [grams(s["gloss"].get("th", "") + " " + " ".join(s["gloss"].get("en", [])))
              for s in senses]

        # tier 1a: the wiktextract sense that lists this compound as an example
        exmap = {}
        for i, row in enumerate(wsenses.get(d["th"], [])):
            for x in row.get("examples", []):
                exmap.setdefault(x.strip(), row["gloss"])
        # map a wiktextract gloss back onto our sense list by exact gloss text
        gloss_to_n = {}
        for s in senses:
            gloss_to_n.setdefault((s["gloss"].get("th") or "").strip(), s["n"])

        keep = []
        for c in unassigned:
            target, why, conf, src, label = None, None, None, None, None
            wg = exmap.get(c["th"])
            if wg and wg.strip() in gloss_to_n:
                target = gloss_to_n[wg.strip()]
                why, conf, src = "wiktionary lists it as an example of this sense", "verified", ["WIKT"]
                label = "1a wiktionary example"
            use = classify_use(c["gloss"].get("th"))
            if use in ("synonym-pointer", "nominalisation"):
                # Not a compound of this head in any useful sense: one points at a
                # synonym, the other is a grammatical nominalisation. Recorded as
                # what it is instead of being filed under a meaning.
                c = dict(c); c["note"] = ((c.get("note", "") + " · ") if c.get("note") else "") + \
                    f"definition form: {use} — not a semantic compound of this head"
                c["use"] = use
                tier[f"1c {use}"] += 1
                keep.append(c)
                continue
            if use and target is None:              # tier 1c: definition form
                for s2 in senses:
                    g2 = (s2["gloss"].get("th") or "").strip()
                    if g2.startswith("ชื่อ") or g2 == "ใช้ประกอบชื่อสถานที่":
                        target = s2["n"]
                        why = f"definition form is a {use}; filed under the head's name-use sense"
                        conf, src = "verified", ["RID"]
                        break
                if target is None:
                    c = dict(c); c["use"] = use
                    c["note"] = ((c.get("note", "") + " · ") if c.get("note") else "") + \
                        (f"definition form: {use}. This head has no name-use sense to file "
                         f"it under — add one, then this files itself.")
                    tier[f"1c {use} (no sense to file under)"] += 1
                    keep.append(c)
                    continue
                label = f"1c {use}"
            if target is None:                      # tier 1b: the gloss names it
                for s in senses:
                    if c["th"] in (s["gloss"].get("th") or ""):
                        target, why, conf, src = s["n"], "the sense gloss names this compound", "verified", ["RID"]
                        label = "1b gloss names it"
                        break
            if target is None and len(senses) == 1:   # tier 0: nothing to choose
                target = senses[0]["n"]
                why = "the head has one sense, so this is forced rather than chosen"
                conf, src, label = "verified", ["CUR"], "0 forced (single sense)"

            # TIER 2 IS OFF BY DEFAULT AND SHOULD STAY OFF. Measured against the
            # 2,649 compounds filed by sourced evidence on multi-sense heads, the
            # source puts a compound on the head's CORE sense only 9% of the time
            # — 18% counting only Wiktionary's own examples, which is the cleanest
            # evidence here. Gloss similarity picks the core sense 91% of the time,
            # with or without IDF weighting. It is not weakly right, it is
            # anti-correlated with the answer: one-line RID glosses do not say
            # which sense a compound uses, and a bag of trigrams simply lands on
            # whichever sense carries the most text. Filing 1,589 compounds this
            # way would be worse than leaving them open, because they would then
            # be exemplars and the error would compound.
            if target is None and a.similarity:       # tier 2: similarity, if decisive
                cg = grams(compound_text(c))
                scores = sorted(
                    ((dice(cg, grams(sense_text(s2, s2.get("compounds", [])))), s2["n"])
                     for s2 in senses), reverse=True)
                if scores and scores[0][0] >= FLOOR and (
                        len(scores) == 1 or scores[0][0] - scores[1][0] >= a.margin):
                    target = scores[0][1]
                    why = (f"gloss and filed-exemplar similarity {scores[0][0]:.2f}"
                           + (f", next best {scores[1][0]:.2f}" if len(scores) > 1 else ""))
                    conf, src = "probable", ["CUR"]
                    label = "2 proposed (gloss + exemplars)"
                else:
                    tier["3 open"] += 1
                    if scores and len(scores) > 1:
                        review.append((scores[0][0] - scores[1][0], d["th"], c["th"]))
                    keep.append(c)
                    continue

            if target is None:      # every tier declined — it stays open
                tier["3 open"] += 1
                keep.append(c)
                continue

            tier[label or "1 sourced"] += 1

            c = dict(c)
            c["conf"] = conf
            c["src"] = sorted(set((c.get("src") or []) + src))
            c["note"] = ((c.get("note", "") + " · ") if c.get("note") else "") + \
                        f"filed under sense {target}: {why}"
            for s in senses:
                if s["n"] == target:
                    s.setdefault("compounds", []).append(c)
                    break

        if keep != unassigned:
            changed += 1
            if keep:
                d["compounds_unassigned"] = keep
            else:
                d.pop("compounds_unassigned", None)
            if d.get("status") == "listed":
                d["status"] = "proposed"
            d.setdefault("needs_check", []).append(
                "Compound filing is tiered: entries marked 'verified' were filed by a "
                "source, 'probable' by gloss similarity. Neither orders the senses, so "
                "this entry is 'proposed', not 'mapped'.")
            if a.write:
                f.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", "utf-8")

    tot = sum(v for k, v in tier.items() if k[0].isdigit())
    print(f"compounds considered: {tot}")
    for k in sorted(tier):
        if k[0].isdigit():
            print(f"  tier {k:<42} {tier[k]:5}  {tier[k]/tot:5.1%}")
    print(f"entries touched: {changed}")
    review.sort()
    print(f"\nreview queue — closest calls first ({len(review)} left open):")
    for m, head, comp in review[:12]:
        print(f"  margin {m:.3f}  {head} → {comp}")
    if not a.write:
        print("\n(dry run — pass --write)")


if __name__ == "__main__":
    main()
