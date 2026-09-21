#!/usr/bin/env python3
"""lexicon_frames — what a compound predicates, which order decides and sense cannot.

THE FACT THIS EXISTS FOR
Thai builds psycho-collocations out of a body-or-mind part and a modifier, and
the ORDER carries the meaning:

    ใจดี   kind-hearted      a standing property of a person
    ดีใจ   glad              a state that befalls them
    ใจแข็ง unyielding        a property again
    แข็งใจ to steel oneself  now an act performed on the heart
    ใจหาย  startled          the heart goes missing — a fright
    หายใจ  TO BREATHE        the same two morphemes, and the plainest act of living

Both orders use the SAME SENSE of ใจ. Sense-filing therefore cannot tell ใจดี
from ดีใจ — no amount of gloss similarity will, because the distinction is not in
the sense at all. It is in the frame, and the frame is readable off the order.

    part + ADJ   -> trait    a property of the person who has the part
    ADJ + part   -> state    a condition the part is in
    VERB + part  -> act      something done to or with the part
    N + N        -> entity   the ordinary compound noun (ตาข่าย)

PARTS THAT TAKE FRAMES
Only where the head is a body or mind part, because that is where the asymmetry
lives. ตาข่าย is a net, not a state of the eye, and forcing a frame onto every
N+N would make the field mean nothing.

`FLIPS_WITH` records the minimal pairs directly — 103 of them, the same two
morphemes in both orders — which is the cheapest proof the distinction is real
and the best thing to show a learner.

    python3 lexicon_frames.py --write
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

LEX = Path(__file__).resolve().parent / "data" / "lexicon"

# The parts whose compounds carry a frame. Thai's psycho-collocations are built
# on the body and its seats of feeling; this is that inventory, not a guess at
# which words are common.
BODY_MIND = {"ใจ", "ตา", "หน้า", "หัว", "มือ", "ปาก", "อก", "ท้อง", "คอ", "หู",
             "ตีน", "เท้า", "ตัว", "ขวัญ", "เนื้อ", "เลือด", "กาย", "จิต"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    files = sorted((LEX / "entries").glob("*.json"))
    docs = {}
    for f in files:
        docs[f] = json.loads(f.read_text("utf-8"))

    # index every compound by (head, other) so both orders can find each other
    seen = defaultdict(dict)
    for f, d in docs.items():
        for c in [x for s in d["senses"] for x in s.get("compounds", [])] + \
                 d.get("compounds_unassigned", []):
            p = c.get("parts") or []
            if len(p) != 2 or d["th"] not in p:
                continue
            other = p[1] if p[0] == d["th"] else p[0]
            seen[(d["th"], other)]["H+X" if p[0] == d["th"] else "X+H"] = c

    frames = Counter()
    flips = 0
    for f, d in docs.items():
        th = d["th"]
        touched = False
        for c in [x for s in d["senses"] for x in s.get("compounds", [])] + \
                 d.get("compounds_unassigned", []):
            p = c.get("parts") or []
            if len(p) != 2 or th not in p:
                continue
            other = p[1] if p[0] == th else p[0]
            first = p[0] == th
            pat = c.get("pattern") or ""
            fr = None
            if th in BODY_MIND:
                head_pos, mod_pos = (pat.split("+") + ["?", "?"])[:2] if "+" in pat else ("?", "?")
                xpos = mod_pos if first else head_pos
                g = (c["gloss"].get("th") or "").strip()
                # The RID writes causatives with ทำ…ให้ — "to make the heart —".
                # แข็งใจ is glossed ทำใจให้กล้า and is something a person DOES;
                # ดีใจ is not, and is something that happens to them. POS alone
                # cannot separate them, and the definition's own syntax can.
                causative = g.startswith(("ทำ", "บังคับ", "ห้าม", "ตั้ง"))
                # ONLY property-words and verbs take a frame. A noun beside a body
                # part just names a thing — หน้าผาก is a forehead, หัวถนน is the top
                # of the road, หูฟัง is a headphone. The first pass called those
                # traits and states, which made the field mean nothing. The
                # asymmetry ใจดี/ดีใจ lives in the ADJECTIVES and VERBS, so that is
                # where the frame is claimed and nowhere else.
                if xpos == "N":
                    fr = "entity"
                elif first:
                    # part first, part is the subject: an adjective is a standing
                    # property (ใจดี); a verb is the part doing something, an event
                    # rather than a character (ใจหาย).
                    fr = "trait" if xpos in ("ADJ", "ADV") else "state"
                elif causative or xpos == "V":
                    fr = "act"
                elif xpos in ("ADJ", "ADV"):
                    fr = "state"
            elif pat == "N+N":
                fr = "entity"
            elif pat.endswith("+ADJ") or pat.startswith("ADJ+"):
                fr = "quality"
            # WHERE THE CLAIM IS ALLOWED TO STAND.
            # Applied broadly, the frame is roughly half wrong: หูฟัง came out a
            # "state" (it is a headphone) and หน้าร้อน a "trait" (it is the hot
            # season). thai-full gives one coarse POS per word and Thai's noun /
            # verb / adjective boundaries are soft, so the rule cannot carry the
            # weight everywhere. It is kept only where the asymmetry can be shown:
            # on ใจ, where all five minimal pairs were checked by hand, and on any
            # compound that HAS a twin in the opposite order — there the flip is
            # itself the evidence. Everywhere else the field stays empty, which is
            # the honest state of it.
            demonstrable = th == "ใจ" or c.get("flips_with") or \
                (th, other) in seen and len(seen[(th, other)]) == 2
            if fr in ("trait", "state", "act") and not demonstrable:
                fr = None
            if fr and not c.get("frame"):
                c["frame"] = fr
                frames[fr] += 1
                touched = True
            pair = seen.get((th, other), {})
            if len(pair) == 2 and not c.get("flips_with"):
                twin = pair["X+H"] if first else pair["H+X"]
                c["flips_with"] = twin["th"]
                flips += 1
                touched = True
        if touched and a.write:
            f.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", "utf-8")

    print("frames assigned:", dict(frames.most_common()))
    print(f"minimal pairs linked with flips_with: {flips}")
    print("\nthe ใจ asymmetry, as the data has it:")
    for (h, o), pr in seen.items():
        if h == "ใจ" and len(pr) == 2:
            A, B = pr["H+X"], pr["X+H"]
            print(f"  {A['th']:<9} [{A.get('frame','?'):<6}] {(A['gloss'].get('th') or '')[:30]:<32}"
                  f"| {B['th']:<9} [{B.get('frame','?'):<6}] {(B['gloss'].get('th') or '')[:30]}")
    if not a.write:
        print("\n(dry run — pass --write)")


if __name__ == "__main__":
    main()
