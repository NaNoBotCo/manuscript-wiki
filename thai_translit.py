#!/usr/bin/env python3
"""thai_translit — a deterministic Thai→Latin transliteration, for SLUGS ONLY.

THIS IS NOT RTGS AND MUST NOT BE LABELLED AS SUCH. Real RTGS needs syllable
segmentation, initial-cluster rules, silent-letter (การันต์) handling and vowel
length — none of which a character walk can do. What this gives is a stable,
readable, collision-resistant ASCII handle so an entry can have a URL before a
human has written its romanisation.

Entries carry it as `translit_auto`; the `rtgs` field stays absent until someone
fills it in, and every generated entry says so in needs_check. Leading vowels
(เ แ โ ใ ไ) are written before their consonant and pronounced after, so they are
buffered and emitted in spoken order — the one piece of real Thai the walk knows.
"""
from __future__ import annotations

INIT = {"ก": "k", "ข": "kh", "ฃ": "kh", "ค": "kh", "ฅ": "kh", "ฆ": "kh", "ง": "ng",
        "จ": "ch", "ฉ": "ch", "ช": "ch", "ซ": "s", "ฌ": "ch", "ญ": "y",
        "ฎ": "d", "ฏ": "t", "ฐ": "th", "ฑ": "th", "ฒ": "th", "ณ": "n",
        "ด": "d", "ต": "t", "ถ": "th", "ท": "th", "ธ": "th", "น": "n",
        "บ": "b", "ป": "p", "ผ": "ph", "ฝ": "f", "พ": "ph", "ฟ": "f", "ภ": "ph",
        "ม": "m", "ย": "y", "ร": "r", "ล": "l", "ว": "w", "ศ": "s", "ษ": "s",
        "ส": "s", "ห": "h", "ฬ": "l", "อ": "", "ฮ": "h"}
FINAL = {"ก": "k", "ข": "k", "ค": "k", "ฆ": "k", "ง": "ng", "จ": "t", "ช": "t",
         "ซ": "t", "ฌ": "t", "ฎ": "t", "ฏ": "t", "ฐ": "t", "ฑ": "t", "ฒ": "t",
         "ด": "t", "ต": "t", "ถ": "t", "ท": "t", "ธ": "t", "ศ": "t", "ษ": "t",
         "ส": "t", "ญ": "n", "ณ": "n", "น": "n", "ร": "n", "ล": "n", "ฬ": "n",
         "บ": "p", "ป": "p", "พ": "p", "ฟ": "p", "ภ": "p", "ม": "m",
         "ย": "i", "ว": "o"}
VOWEL = {"ะ": "a", "ั": "a", "า": "a", "ิ": "i", "ี": "i", "ึ": "ue", "ื": "ue",
         "ุ": "u", "ู": "u", "ๅ": "a", "ำ": "am", "ๆ": ""}
LEAD = {"เ": "e", "แ": "ae", "โ": "o", "ใ": "ai", "ไ": "ai"}
DROP = set("่้๊๋์็ฺ๎")


def translit(th: str) -> str:
    out, lead, prev_cons = [], None, False
    chars = list(th)
    for i, c in enumerate(chars):
        if c in DROP:
            continue
        if c in LEAD:
            lead = LEAD[c]
            continue
        if c in VOWEL:
            out.append(VOWEL[c])
            prev_cons = False
            continue
        if c == "อ" and out and i + 1 < len(chars) and chars[i + 1] in INIT:
            out.append("o")          # อ as the written vowel in e.g. ทอง thong
            prev_cons = False
            continue
        if c in INIT:
            is_last = all(x in DROP or x == "" for x in chars[i + 1:])
            if prev_cons and is_last and c in FINAL:
                out.append(FINAL[c])
            else:
                out.append(INIT[c])
                if lead:
                    out.append(lead)
                    lead = None
            prev_cons = True
            continue
        if c.isalnum():
            out.append(c.lower())
    s = "".join(out)
    return "".join(ch for ch in s if ch.isalnum()) or "x"


if __name__ == "__main__":
    for w in ["แก้ว", "ใจ", "น้ำ", "ขวัญ", "ตา", "หัว", "เมือง", "ข้าว", "ทอง", "ไฟ"]:
        print(f"  {w:<8} {translit(w)}")
