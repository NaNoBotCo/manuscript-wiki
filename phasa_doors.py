#!/usr/bin/env python3
"""phasa_doors — mark Thai text with portal doors, at build time.

WHY SERVER-SIDE
portal.js can find doors in the browser, but only with a vocabulary big enough to
know where words end, and that vocabulary is 32,494 entries. Shipping it to each
of 13,973 manuscript pages to linkify one title is absurd. The build already
knows the title, so the doors are marked into the HTML and the script only has to
handle the click. Works with scripting off, too.

THE FOUR GUARDS, AND WHY EACH EXISTS
Manuscript titles are mostly Pali, and every naive approach shreds them. Measured
on 4,000 real titles:

  no guards          3,950 doors, nearly all wrong — อาฏานาติยสูตฺต cut into
                     อา + นา + ติ, which is Āṭānāṭiya Sutta turned into gibberish
  1 script tell      ฺ ฏ ฐ ฑ ฒ ฬ mark Pali conjuncts and the retroflex series and
                     appear in almost nothing else: 1,113 runs refused
  2 full coverage    segment with the BIG dictionary and take the run only if
                     every character is covered — an unknown span is the
                     signature of a foreign word being cut up
  3 a Pali word in   if any segment is itself a dictionary word whose etymology
    the run          says it was borrowed from Pali, Sanskrit or Khmer, the whole
                     run is a Pali title: 4,652 such words known
  4 no short door    a door of two characters inside a run of four or more
    in a long run    segments is a syllable pulled out of a word nobody knows

That leaves ~500 doors per 4,000 titles, and they are right: สองเข้าติดหม้อ opens
เข้า and ติด, สองผ้าน้ำฝน opens ผ้า and น้ำ.

This is the fourth place in this project that has needed the same rule — do not
cut a borrowed word with Thai morphology. It was ตาย under ตา, then ราหู under หู,
then เมตตา as a compound, now Āṭānāṭiya. Worth writing down as the standing law.
"""
from __future__ import annotations

import html
import json
import re
from functools import lru_cache
from pathlib import Path
from lexicon_tags import is_compound

HERE = Path(__file__).resolve().parent
DUMPS = (HERE.parent / "thairoots" /
         "_downloads drop 2026-08-17 (builds + dictionary dumps)")
SEGDICT = HERE.parent / "search-core" / "data" / "wichaa.segdict.txt"

THAI_RUN = re.compile(r"[฀-๿]+")
INDIC_SCRIPT = re.compile(r"[ฺฏฐฑฒฬ]")  # ฺ ฏ ฐ ฑ ฒ ฬ
BORROWED = re.compile(r"^\s*(ยืมมาจาก|จาก(บาลี|สันสกฤต|เขมร))")
MAXLEN = 16


@lru_cache(maxsize=1)
def _tables():
    full = json.loads((DUMPS / "thai-full.json").read_text("utf-8"))
    vocab = {w for w in full if len(w) >= 2}
    if SEGDICT.exists():
        vocab |= {w.strip() for w in SEGDICT.read_text("utf-8").splitlines()
                  if len(w.strip()) >= 2}
    indic = {w for w, v in full.items()
             if v.get("ety") and BORROWED.match(" ".join(v["ety"]))}
    return vocab, indic


@lru_cache(maxsize=1)
def _linkable(_ignored=""):
    """What is worth opening — read from the lexicon SOURCE, not from the built site.

    Reading docs/api/phasa/lookup.json looked natural and was a build-order trap:
    build_static wipes docs/ and then writes the 13,973 manuscript pages, so the
    lookup it would consult is the one that was just deleted, and every title would
    come out doorless on a clean run. The source of truth is data/lexicon/entries,
    which no build step removes.
    """
    words = set()
    for f in (HERE / "data" / "lexicon" / "entries").glob("*.json"):
        try:
            d = json.loads(f.read_text("utf-8"))
        except Exception:
            continue
        words.add(d["th"])
        for c in [x for s2 in d["senses"] for x in s2.get("compounds", [])] + \
                 d.get("compounds_unassigned", []):
            if is_compound(c):
                words.add(c["th"])
    return words


def _segment(run, vocab):
    out, i = [], 0
    while i < len(run):
        hit = None
        for L in range(min(MAXLEN, len(run) - i), 1, -1):
            s = run[i:i + L]
            if s in vocab:
                hit = s
                break
        if not hit:
            return None                      # guard 2: full coverage or nothing
        out.append(hit)
        i += len(hit)
    return out


def mark(text, docs=None, cls="pt-door"):
    """Return `text` HTML-escaped, with recognised words wrapped as doors."""
    vocab, indic = _tables()
    link = _linkable()
    if not link:
        return html.escape(text or "")
    out, last = [], 0
    for m in THAI_RUN.finditer(text or ""):
        run = m.group(0)
        if len(run) < 2 or INDIC_SCRIPT.search(run):     # guard 1
            continue
        seg = _segment(run, vocab)
        if not seg:
            continue
        if any(w in indic for w in seg):                 # guard 3
            continue
        long_run = len(seg) >= 4
        doors = [w for w in seg
                 if w in link and not (long_run and len(w) <= 2)]   # guard 4
        if not doors:
            continue
        out.append(html.escape(text[last:m.start()]))
        for w in seg:
            e = html.escape(w)
            out.append(f'<span class="{cls}" data-w="{e}">{e}</span>'
                       if w in doors else e)
        last = m.end()
    out.append(html.escape(text[last:]))
    return "".join(out)


if __name__ == "__main__":
    import sys
    d = sys.argv[1] if len(sys.argv) > 1 else \
        str(HERE.parent / "nanobotco-lanna" / "docs")
    for t in ["คำเรียกขวัญลูกแก้ว", "สองเข้าติดหม้อ", "อาฏานาติยสูตฺต",
              "ปัญจนิบาตวันนะนา", "ตำรายาแผนโบราณ", "สองผ้าน้ำฝน"]:
        print(f"  {t:<22} {mark(t, d)}")
