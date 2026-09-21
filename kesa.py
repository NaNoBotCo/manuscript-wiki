#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kesa — /kesa, the yant that writes the thirty-two parts of the body.

A Thai yant manual page describes an edition of ยันต์เกศาผิด laid in by the
knight's move, closing so that it can be re-entered without end. The letters
are the FIRST letters of the thirty-two parts — a mnemonic the post calls
อาทิสังเกต.

This page asks where that method came from, and answers it out of this corpus:
the same thirty-two parts are the laying-in liturgy for any yant drawn as a
figure, they are recited while an effigy is bound, and the knight's move is
already an attested laying-in order for a letter series. Then it asks whether
the loop is possible, and computes the answer.

Self-contained, like glossary.py, na_gallery.py, yant_index.py and handpoke.py:
reads catalog.db, counts, solves, renders its own HTML. Declared in routes.py
with built_by="kesa.py".

    python3 kesa.py --docs ../nanobotco-lanna/docs --site-url https://wichaa.net

Writes  docs/kesa/index.html  +  docs/api/kesa.json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = Path(os.environ.get("CATALOG_DB") or
          (HERE.parent / "manuscript-crawler" / "crawler" / "catalog.db"))

# ---------------------------------------------------------------- the knight

MOVES = [(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)]
# The hardest board here (a 6x6 with its four corners empty) needs 25.3M nodes
# to settle. The cap is a guard against a silent half-search, not a budget:
# if a board hits it, main() refuses to write the page rather than publish a
# claim of exhaustiveness the search did not earn.
NODE_CAP = int(os.environ.get("KESA_NODE_CAP") or 60_000_000)


def _adj(cells):
    cs = set(cells)
    return {c: [d for d in ((c[0] + dx, c[1] + dy) for dx, dy in MOVES) if d in cs]
            for c in cs}


def tour(cells, closed: bool):
    """Exhaustive search. Returns (path|None, nodes, exhausted)."""
    cells = sorted(cells)
    adj = _adj(cells)
    need = 2 if closed else 1
    if any(len(adj[c]) < need for c in cells):
        return None, 0, True
    nodes = [0]
    capped = [False]

    def reachable(rem, cur):
        seeds = [d for d in adj[cur] if d in rem]
        if not seeds:
            return not rem
        seen = {seeds[0]}
        stack = [seeds[0]]
        while stack:
            c = stack.pop()
            for d in adj[c]:
                if d in rem and d not in seen:
                    seen.add(d)
                    stack.append(d)
        return len(seen) == len(rem)

    starts = [cells[0]] if closed else cells   # a cycle can be cut anywhere
    for s in starts:
        path = [s]
        rem = set(cells)
        rem.discard(s)

        def dfs():
            nodes[0] += 1
            if nodes[0] > NODE_CAP:
                capped[0] = True
                return False
            if not rem:
                return (not closed) or (path[0] in adj[path[-1]])
            cur = path[-1]
            cand = [c for c in adj[cur] if c in rem]
            if not cand or not reachable(rem, cur):
                return False
            ends = 0
            start = path[0]
            for c in rem:
                deg = sum(1 for e in adj[c] if e in rem)
                # A cell still to be visited takes its edges from other
                # unvisited cells, from the cell we are standing on, and — for a
                # closed tour only — from the START cell, which is where the
                # cycle comes back. Leaving that last term out prunes every
                # closed tour one move before it completes: the final cell has
                # no unvisited neighbours left, so it looks like a dead end when
                # in fact it is the cell that closes the loop. That error is why
                # this page first published "no closed tour" for a board that
                # has one.
                avail = deg + (1 if c in cand else 0) + \
                        (1 if (closed and start in adj[c]) else 0)
                if avail < need:
                    return False
                if avail == 1 and not closed:
                    ends += 1
            if not closed and ends > 1:
                return False
            cand.sort(key=lambda c: sum(1 for e in adj[c] if e in rem))
            for c in cand:
                path.append(c)
                rem.discard(c)
                if dfs():
                    return True
                if capped[0]:
                    return False
                path.pop()
                rem.add(c)
            return False

        if dfs():
            return list(path), nodes[0], True
        if capped[0]:
            return None, nodes[0], False
    return None, nodes[0], True


def is_tour(path, cells, closed: bool) -> bool:
    if not path or sorted(path) != sorted(set(cells)) or len(path) != len(cells):
        return False
    ok = lambda a, b: (abs(a[0] - b[0]), abs(a[1] - b[1])) in {(1, 2), (2, 1)}
    if not all(ok(path[i], path[i + 1]) for i in range(len(path) - 1)):
        return False
    return ok(path[-1], path[0]) if closed else True


def rect(w, h):
    return [(x, y) for x in range(w) for y in range(h)]


# ------------------------------------------------------------- the thirty-two
# Pali, the initial the yant lays in (อาทิสังเกต), Thai reading, gloss.
# As given in the yant post; the readings and glosses are its own.
PARTS = [
    ("เกสา", "เก", "เกสา", "hair of the head"),
    ("โลมา", "โล", "โลมา", "body hair"),
    ("นขา", "น", "นะขา", "nails"),
    ("ทนฺตา", "ท", "ทันตา", "teeth"),
    ("ตโจ", "ต", "ตะโจ", "skin"),
    ("มํสํ", "มํ", "มังสัง", "flesh"),
    ("นฺหารู", "น", "นะหารู", "sinew"),
    ("อฏฺฐิ", "อ", "อัฏฐิ", "bone"),
    ("อฏฺฐิมิญฺชํ", "อ", "อัฏฐิมิญชัง", "marrow"),
    ("วกฺกํ", "ว", "วักกัง", "spleen"),
    ("หทยํ", "ห", "หะทะยัง", "heart"),
    ("ยกนํ", "ย", "ยะกะนัง", "liver"),
    ("กิโลมกํ", "กิ", "กิโลมะกัง", "fascia"),
    ("ปิหกํ", "ปิ", "ปิหะกัง", "kidney"),
    ("ปปฺผาสํ", "ป", "ปัปผาสัง", "lungs"),
    ("อนฺตํ", "อ", "อันตัง", "large intestine"),
    ("อนฺตคุณํ", "อ", "อันตะคุณัง", "small intestine"),
    ("อุทริยํ", "อุ", "อุทะริยัง", "food newly eaten"),
    ("กรีสํ", "ก", "กะรีสัง", "food digested"),
    ("ปิตฺตํ", "ปิ", "ปิตตัง", "bile"),
    ("เสมฺหํ", "เส", "เสมหัง", "phlegm"),
    ("ปุพฺโพ", "ปุ", "ปุพโพ", "pus"),
    ("โลหิตํ", "โล", "โลหิตัง", "blood"),
    ("เสโท", "เส", "เสโท", "sweat"),
    ("เมโท", "เม", "เมโท", "fat"),
    ("อสฺสุ", "อ", "อัสสุ", "tears"),
    ("วสา", "ว", "วะสา", "grease"),
    ("เขโฬ", "เข", "เขโฬ", "saliva"),
    ("สึฆานิกา", "สึ", "สิงฆานิกา", "mucus"),
    ("ลสิกา", "ล", "ละสิกา", "synovial fluid"),
    ("มุตฺตํ", "มุ", "มุตตัง", "urine"),
    ("มตฺถเก มตฺถลุงฺคํ", "ม", "มัตถะเก มัตถะลุงคัง", "brain"),
]

# Where the recension on this disk reads differently from the post's list.
# Left: the post. Right: ประมวลคาถาตำราโบราณ p.39, as transcribed here.
VARIANTS = [
    (16, "อนฺตํ", "ไส้ใหญ่", "ไส้น้อย",
     "the two intestines change places between the two lists"),
    (17, "อนฺตคุณํ", "ไส้น้อย", "ไส้ใหญ่",
     "and so this one does too — the pair is swapped, not mistranslated once"),
    (28, "เขโฬ", "เขโฬ", "เขโพ",
     "ฬ for พ — and the plate writes เขโพ too, so this is a reading, not a slip"),
    (26, "อสฺสุ", "อัสสุ", "อัฐสุ", "a written variant in the same transcription"),
]

# The two the Thai liturgy reads against the Pali commentaries, in both lists.
AGAINST_PALI = [
    (10, "วกฺกํ", "ม้าม · spleen", "kidney"),
    (14, "ปิหกํ", "ไต · kidney", "spleen"),
]

# -------------------------------------------------------------- the genealogy
# Each step: what it is, the manuscript, printed/page reference, the words.
CHAIN = [
    ("The list is canonical, and its work is disgust",
     "ทวัตติงสาการ · dvattiṃsākāra",
     "Khuddakapāṭha 3, and the paṭikūlamanasikāra of the commentaries",
     "Recited to see the body as unlovely and be done wanting it. The thirty-two "
     "are a meditation before they are ever a yant. Four of the meditation "
     "manuals in this corpus use them that way and nothing else.",
     ""),
    ("The yant tradition turns the same list into armour",
     "ประมวลคาถาตำราโบราณ",
     "page 39 — โองการเอิกเกริกน้อย",
     "Every one of the thirty-two is named and answered with เพ็ชชะคง — "
     "diamond-hard. The list that was recited to loosen a man's grip on his body "
     "is recited here to make that body impossible to cut.",
     "th"),
    ("The thirty-two become the laying-in liturgy for a figure yant",
     "สูตรการลงยันต์แบบขอมผสมไทย",
     "page 43 — ยันต์รูปภาพ",
     "For any yant drawn as a figure — a deva, a lion, a bird, a fish — the "
     "manual gives the full thirty-two as the words you say while you draw it. "
     "Not a footnote: the formula for that whole class of yant.",
     "th2"),
    ("A yant drawn as a person gets them twice",
     "สูตรการลงยันต์แบบขอมผสมไทย",
     "page 44",
     "A figure written with a name — the kind buried with a candle — is laid in "
     "with the ปถมังโลกีย์ formula and then consecrated with the thirty-two on "
     "top of it.",
     ""),
    ("Each letter laid in is a birth, and has to be pinned or it leaves",
     "สูตรการลงยันต์แบบขอมผสมไทย",
     "page 45",
     "Every letter carries its own line — X กาโรโหติสัมภะโว, the letter X comes "
     "into being — and the manual warns that a letter not pinned (กรึง) "
     "afterwards can escape and fade. A sequence that closes on itself is a "
     "sequence with nowhere to leave from.",
     ""),
    ("The knight's move is already a laying-in order",
     "ตำรามหายันต์",
     "page 27, yant ๒๔",
     "การลงตัวอักขระต้องลงอย่างตามคำม้าหมากรุก ตามลำดับตัวอักขระ — the letters "
     "must be laid in by the knight's move, in the order of the letters. Here it "
     "carries the five Pali consonant groups rather than the thirty-two parts.",
     "th3"),
    ("And the thirty-two are recited while a body is bound",
     "ตำราสร้างเครื่องรางของขลัง",
     "printed page ๗๘ — หุ่นพยนต์ แบบที่ ๒",
     "Thirty-two strands of rice straw, one per part, bound while you recite the "
     "thirty-two until it is finished. The same list, carried by straw instead of "
     "letters.",
     "th4"),
]

Q = {
 "th": ("อิติปิโส ภะคะวา โอม เกสา ผมอยู่ในทั่วสารพางค์ตัวกู โอมเพ็ชชะคง คง ตรีเพ็ชชะคง "
        "อิติปิโส ภะคะวา โอม โลมา ขนอยู่ในทั่วสารพางค์ตัวกู โอมเพ็ชชะคง คง ตรีเพ็ชชะคง "
        "อิติปิโส ภะคะวา โอม นักขา เล็บอยู่ในทั่วสารพางค์ตัวกู โอมเพ็ชชะคง คง ตรีเพ็ชชะคง …",
        "Itipiso Bhagava. Om, kesā — the hair is throughout my whole frame. Om, "
        "diamond-fast, fast, thrice diamond-fast. Itipiso Bhagava. Om, lomā — the "
        "body hair is throughout my whole frame… and so through all thirty-two."),
 "th2": ("ยันต์รูปภาพ บรรดารูปภาพต่างๆ ที่ใช้ลงเป็นยันต์นั้นเมื่อเวลาลงภาพนั้น ให้ลงด้วยอาการ ๓๒ คือ "
         "เกษา โลมา นักขา ทันตา ตะโจ มังสัง นะหารู อัฏฐิ …",
         "Figure yant: for all the various figures used as a yant, when you lay in "
         "the figure, lay it in with the thirty-two parts, thus — kesā, lomā, "
         "nakhā, dantā, taco, maṃsaṃ, nhārū, aṭṭhi…"),
 "th3": ("ยันต์นี้ใช้ลงเป็นผ้าประเจียด ใช้ได้สารพัดทุกประการ ตามแต่จะปรารถนาเถิด "
         "การลงตัวอักขระต้องลงอย่างตามคำม้าหมากรุก ตามลำดับตัวอักขระ แล้วจึงเสกด้วยพระคาถานี้",
         "This yant is laid onto a prajiat cloth and serves for anything you wish. "
         "The letters must be laid in by the knight's move, in the order of the "
         "letters, and then consecrated with this katha."),
 "th4": ("ถ้าจะผูกหุ่นพยนต์ ท่านให้ผูกขึ้นด้วยซังข้าว ๓๒ เส้น … "
         "เมื่อผูกหุ่นนั้นให้ภาวนาด้วยอาการ ๓๒ กว่าจะแล้วเสร็จ",
         "To bind a hun payont, bind it up from thirty-two strands of rice straw… "
         "and while you bind it, recite the thirty-two parts until it is done."),
}

TERMS = [
    ("อาการ ๓๒", "akan sam-sip-song", "the thirty-two parts, in the Thai name"),
    ("เกสา", "kesā", "hair of the head — the first part, and this yant's name"),
    ("ทวัตติงสา", "dvattiṃsā", "the Pali name of the set"),
    ("หมากรุก", "mak ruk", "chess — the knight's move is คำม้าหมากรุก"),
    ("ปถมัง", "pathamang", "the foundational laying-in system"),
    ("กรึง", "kruెng", "to pin a letter so it cannot leave"),
    ("เพ็ชชะคง", "phetcha khong", "diamond-fast — the invulnerability formula"),
    ("อาทิสังเกต", "ādi-saṅketa", "marking by the initial — this yant's mnemonic"),
]
TERMS[5] = ("กรึง", "krueng", "to pin a letter so it cannot leave")

SOURCES = [
    ("The post", "2026",
     "A Thai yant page, #ว่าด้วยยันต์เกศาผิด — the edition that closes and can be "
     "re-entered, and the อาทิสังเกต table of initials. Text as shared, September 2026.",
     ""),
    ("ประมวลคาถาตำราโบราณ", "—",
     "p.39, โองการเอิกเกริกน้อย — the thirty-two answered one by one with เพ็ชชะคง.",
     ""),
    ("สูตรการลงยันต์แบบขอมผสมไทย", "—",
     "pp.43–45 — the thirty-two as the laying-in formula for a figure yant; "
     "pathamang for a named figure; a letter is born, and must be pinned.",
     ""),
    ("ตำรามหายันต์", "—",
     "p.27 (yant ๒๔), the knight's move as a laying-in order; p.107, the "
     "thirty-two recited while a figure is bound.",
     ""),
    ("ตำราสร้างเครื่องรางของขลัง", "—",
     "printed pp.๗๗–๗๘ — thirty-two straws, bound to the thirty-two parts.",
     ""),
    ("Khuddakapāṭha 3 · Paṭikūlamanasikāra", "—",
     "The canonical set. The paṭikūlamanasikāra list runs to thirty-one; "
     "mattake matthaluṅgaṃ, the brain, is not in the earlier canonical sources.",
     "https://en.wikipedia.org/wiki/Patikulamanasikara"),
    ("A. J. Schwenk", "1991",
     "Which rectangular chessboards have a knight's tour? — no m×n board with "
     "m = 4 has a closed tour, whatever n is.",
     "https://doi.org/10.1080/0025570X.1991.11977625"),
]


# ---------------------------------------------------------------- the plate
# The yant itself, as published. Six drawings of one design: the laying-in
# order, then the thirty-two initials and the thirty-two full words, each in
# Khom and in Thai. Not ours — see PLATE_CREDIT.
PLATES = [
    ("plate-order.jpeg", "แสดงลำดับการลงยันต์ของอาการ ๓๒",
     "the order — an arrow per move, ๑ near the middle and ๓๒ below left"),
    ("plate-thai-initials.jpeg", "แสดงอักษรไทยแบบอาทิสังเกตของอาการ ๓๒",
     "the thirty-two initials, in Thai letters"),
    ("plate-khom-initials.jpeg", "แสดงอักษรขอมแบบอาทิสังเกตของอาการ ๓๒",
     "the same initials in Khom — the script a yant is written in"),
    ("plate-thai-full.jpeg", "แสดงคำอ่านไทยแบบเต็มคำของอาการ ๓๒",
     "the full words, Thai reading — what settles which cell is which"),
    ("plate-pali-thai-full.jpeg", "แสดงคำอ่านไทย-บาลีแบบเต็มคำของอาการ ๓๒",
     "the full words, Thai-Pali"),
    ("plate-khom-full.jpeg", "แสดงอักษรขอมแบบเต็มคำของอาการ ๓๒",
     "the full words in Khom"),
]

# The grid transcribed off the plate: a 6x6 with its four corners absent, row 0
# at the top, each cell holding the initial it carries. This is the datum; the
# order below is DERIVED from it and re-derived on every build.
PLATE_GRID = {
    (0, 1): "ล",  (0, 2): "เส", (0, 3): "โล", (0, 4): "อ",
    (1, 0): "ปิ", (1, 1): "ป",  (1, 2): "อ",  (1, 3): "สึ", (1, 4): "ปุ", (1, 5): "น",
    (2, 0): "มุ", (2, 1): "เข", (2, 2): "เก", (2, 3): "ย",  (2, 4): "น",  (2, 5): "ว",
    (3, 0): "ปิ", (3, 1): "ก",  (3, 2): "อ",  (3, 3): "เม", (3, 4): "ท",  (3, 5): "โล",
    (4, 0): "ว",  (4, 1): "ม",  (4, 2): "กิ", (4, 3): "อุ", (4, 4): "ห",  (4, 5): "มํ",
    (5, 1): "อ",  (5, 2): "อ",  (5, 3): "ต",  (5, 4): "เส",
}

# The full words, read off the two full-word plates, cell by cell. These are not
# needed to derive the order — they are the independent check on it.
PLATE_WORDS = {
    (0, 1): "ละสิกา", (0, 2): "เสมหัง", (0, 3): "โลมา", (0, 4): "อัฏฐิมิญชัง",
    (1, 0): "ปิตตัง", (1, 1): "ปัปผาสัง", (1, 2): "อัฏฐิ", (1, 3): "สิงฆานิกา",
    (1, 4): "ปุพโพ", (1, 5): "นะขา",
    (2, 0): "มุตตัง", (2, 1): "เขโพ", (2, 2): "เกสา", (2, 3): "ยะกะนัง",
    (2, 4): "นะหารู", (2, 5): "วักกัง",
    (3, 0): "ปิหะกัง", (3, 1): "กะรีสัง", (3, 2): "อันตัง", (3, 3): "เมโท",
    (3, 4): "ทันตา", (3, 5): "โลหิตัง",
    (4, 0): "วะสา", (4, 1): "มัตถะเก มัตถะลุงคัง", (4, 2): "กิโลมะกัง",
    (4, 3): "อุทะริยัง", (4, 4): "หะทะยัง", (4, 5): "มังสัง",
    (5, 1): "อันตะคุณัง", (5, 2): "อัสสุ", (5, 3): "ตะโจ", (5, 4): "เสโท",
}

PLATE_CELLS = sorted(PLATE_GRID)


def solve_order():
    """Recover the laying-in order from the letters alone.

    Each of the thirty-two positions in the list has a known initial, and each
    cell of the plate carries one. Seventeen of the initials occur once, so
    those cells are fixed outright; the other fifteen repeat. Require every
    consecutive pair to be a knight's move and see how many arrangements
    survive. Returns (orders, fixed) — every solution found, and how many
    positions were pinned by their letter before any searching.
    """
    seq = [k for _, k, _, _ in PARTS]
    cand = {i: [c for c, l in PLATE_GRID.items() if l == seq[i]]
            for i in range(len(seq))}
    fixed = sum(1 for i in cand if len(cand[i]) == 1)
    kn = lambda a, b: (abs(a[0] - b[0]), abs(a[1] - b[1])) in {(1, 2), (2, 1)}
    out, path, used = [], [], set()

    def walk(i):
        if i == len(seq):
            out.append(list(path))
            return
        for c in cand[i]:
            if c in used or (i and not kn(path[-1], c)):
                continue
            used.add(c); path.append(c)
            walk(i + 1)
            path.pop(); used.remove(c)

    walk(0)
    return out, fixed


def counts() -> dict:
    if not DB.exists():
        return {}
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    text = "ifnull(p.transcription,'')||ifnull(p.ocr_text,'')||ifnull(p.vision_desc,'')"
    out = {"pages": db.execute(
               "select count(*) from pages where ifnull(transcription,'')<>''").fetchone()[0],
           "manuscripts": db.execute("select count(*) from manuscripts").fetchone()[0],
           "terms": []}
    for th, rtgs, gloss in TERMS:
        n = db.execute(f"select count(*) from pages p where {text} like ?",
                       (f"%{th}%",)).fetchone()[0]
        m = db.execute(f"select count(distinct p.manuscript_id) from pages p "
                       f"where {text} like ?", (f"%{th}%",)).fetchone()[0]
        out["terms"].append({"th": th, "rtgs": rtgs, "gloss": gloss,
                             "pages": n, "manuscripts": m})
    db.close()
    return out


def minus(cells, holes):
    h = set(holes)
    return [c for c in cells if c not in h]


def symmetric_36_boards():
    """The nine ways to leave four cells empty in a 6x6 grid so that the empty
    cells are carried onto each other by a quarter turn. A yant plate is
    symmetric; this is the family of 32-cell boards that keeps it so."""
    N = 6
    seen, out = set(), []
    for x in range(N):
        for y in range(N):
            o, a, b = set(), x, y
            for _ in range(4):
                o.add((a, b)); a, b = b, N - 1 - a
            fo = frozenset(o)
            if len(fo) == 4 and fo not in seen:
                seen.add(fo)
                out.append(sorted(fo))
    return sorted(out)


def board_set():
    """Every 32-cell board this page tests, with the name it is shown under."""
    bs = [("4x8", "a 4x8 block", rect(4, 8), None),
          ("2x16", "a 2x16 strip", rect(2, 16), None)]
    for holes in symmetric_36_boards():
        tag = "".join(f"{x}{y}" for x, y in holes)
        where = " ".join(f"({x},{y})" for x, y in holes)
        bs.append((f"6x6-{tag}", f"6x6, four cells empty at {where}",
                   minus(rect(6, 6), holes), holes))
    return bs


def colour_split(cells):
    light = sum(1 for x, y in cells if (x + y) % 2 == 0)
    return light, len(cells) - light


CACHE = HERE / "data" / "kesa_boards.json"

# The plate itself. Not ours: a photograph of one page's diagram, shown small,
# credited, on a non-commercial research page. Drop the cropped image in as
# content/kesa/plate.png (or .jpg) and the figure below appears; with no file
# there the page simply does not carry it.
PLATE_DIR = HERE / "content" / "kesa"
PLATE_CREDIT = ("ตำราอักขระเลขยันต์ ส.สุวรรณ พ.พัฒนศักดิ์", "Facebook, September 2026")


def plate_files() -> list[tuple[str, bytes]]:
    """The plate drawings, if they are on disk. Empty list = the page carries
    no images and says nothing about them."""
    out = []
    for name, _, _ in PLATES:
        f = PLATE_DIR / name
        if f.is_file() and f.stat().st_size > 1024:
            out.append((name, f.read_bytes()))
    return out


def boards(recompute: bool = False) -> dict:
    """Solve every board, open and closed. Exhaustive; the slowest board costs
    minutes, so results are cached beside this script and each cached entry is
    re-checked here — an open tour is re-verified move by move, and a cached
    'no closed tour' is used only if its own search ran to exhaustion."""
    cache = {}
    if CACHE.exists() and not recompute:
        try:
            cache = json.loads(CACHE.read_text(encoding="utf-8")).get("boards", {})
        except (ValueError, OSError):
            cache = {}
    out, dirty = {}, False
    for key, label, cells, holes in board_set():
        got = cache.get(key)
        ok = False
        if got:
            ok = got.get("cells") == len(cells)
            for kind, shut in (("open", False), ("closed", True)):
                leg = got.get(kind, {})
                if leg.get("exhausted") is not True:
                    ok = False
                if leg.get("exists") and not is_tour(
                        [tuple(c) for c in (leg.get("path") or [])], cells, shut):
                    ok = False
        if not ok:
            t0 = time.time()
            op_p, op_n, op_done = tour(cells, False)
            cl_p, cl_n, cl_done = tour(cells, True)
            got = {"label": label, "cells": len(cells), "holes": holes,
                   "colours": colour_split(cells),
                   "open": {"exists": bool(op_p), "nodes": op_n,
                            "exhausted": op_done,
                            "path": [list(c) for c in op_p] if op_p else None},
                   "closed": {"exists": bool(cl_p), "nodes": cl_n,
                              "exhausted": cl_done,
                              "path": [list(c) for c in cl_p] if cl_p else None},
                   "seconds": round(time.time() - t0, 2),
                   "solved": time.strftime("%Y-%m-%d")}
            dirty = True
        got["label"] = label
        got["holes"] = holes
        got["colours"] = got.get("colours") or colour_split(cells)
        out[key] = got
    if dirty:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps({"boards": out}, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    return out


def render(c: dict, bs: dict, site: str, orders, fixed: int, have_plates: bool) -> str:
    b = bs["4x8"]
    order = orders[0]
    closes = (abs(order[-1][0] - order[0][0]), abs(order[-1][1] - order[0][1])) in {(1, 2), (2, 1)}

    gallery = ""
    if have_plates:
        who, when = PLATE_CREDIT
        figs = "".join(
            f'<figure><img src="{f}" alt="{alt}" loading="lazy">'
            f'<figcaption><span class="th">{cap}</span>{alt}</figcaption></figure>'
            for f, cap, alt in PLATES)
        gallery = (f'<div class="gallery">{figs}</div>'
                   f'<p class="note">Six drawings of one design, published by '
                   f'<b>{who}</b> ({when}) and shown here for study — the plates are '
                   f'that page\u2019s work, not this one\u2019s. Everything below is '
                   f'read off them.</p>')

    pos_cell = {i: order[i] for i in range(len(order))}
    part_rows = "".join(
        f'<tr><td class="n muted">{i + 1}</td><td class="w">{p}</td>'
        f'<td class="k">{k}</td><td class="r">{r}</td><td class="g">{g}</td>'
        f'<td class="c">{PLATE_WORDS.get(pos_cell[i], "")}</td>'
        f'<td class="n muted">r{pos_cell[i][0] + 1}&#8202;c{pos_cell[i][1] + 1}</td></tr>'
        for i, (p, k, r, g) in enumerate(PARTS))

    var_rows = "".join(
        f'<tr><td class="n muted">{i}</td><td class="w">{p}</td>'
        f'<td class="w">{a}</td><td class="w">{bb}</td><td class="g">{why}</td></tr>'
        for i, p, a, bb, why in sorted(VARIANTS))

    pali_rows = "".join(
        f'<tr><td class="n muted">{i}</td><td class="w">{p}</td>'
        f'<td class="w">{thai}</td><td class="g">Pali commentaries: {pali}</td></tr>'
        for i, p, thai, pali in AGAINST_PALI)

    chain = []
    for n, (head, ms, ref, body, qk) in enumerate(CHAIN, 1):
        quote = ""
        if qk and qk in Q:
            th, en = Q[qk]
            quote = (f'<blockquote><div class="th">{th}</div>'
                     f'<div class="en">{en}</div>'
                     f'<cite>{ms} · {ref}. Translation this project’s.</cite></blockquote>')
        cite = f'<div class="ms">{ms} · {ref}</div>' if not quote else ""
        chain.append(f'<li><h3>{head}</h3>{cite}<p>{body}</p>{quote}</li>')
    chain_html = "".join(chain)

    src = "".join(
        f'<tr><th>{w}</th><td class="n">{y}</td><td>{s}</td>'
        f'<td class="g">{"<a href=" + chr(34) + u + chr(34) + " rel=" + chr(34) + "noopener" + chr(34) + ">link</a>" if u else ""}</td></tr>'
        for w, y, s, u in SOURCES)

    term_rows = ""
    if c.get("terms"):
        mx = max([t["pages"] for t in c["terms"]] or [1]) or 1
        term_rows = "".join(
            f'<tr><td class="w">{t["th"]}</td><td class="r">{t["rtgs"]}</td>'
            f'<td class="g">{t["gloss"]}</td>'
            f'<td class="b"><span style="width:{max(1.5, 100 * t["pages"] / mx):.1f}%"></span></td>'
            f'<td class="n">{t["pages"]}</td><td class="n muted">{t["manuscripts"]}</td></tr>'
            for t in c["terms"])

    tested = len(bs)
    closed_found = sum(1 for v in bs.values() if v["closed"]["exists"])
    open_found = sum(1 for v in bs.values() if v["open"]["exists"])
    board_rows = "".join(
        f'<tr><td class="w">{v["label"]}</td>'
        f'<td class="y">{"yes" if v["open"]["exists"] else "no"}</td>'
        f'<td class="y">{"yes" if v["closed"]["exists"] else "no"}</td>'
        f'<td class="n muted">{v["closed"]["nodes"]:,}</td>'
        f'<td class="n muted">{v["colours"][0]}&#8202;/&#8202;{v["colours"][1]}</td></tr>'
        for v in bs.values())
    data = json.dumps({
        "parts": [{"pali": p, "key": k, "read": r, "gloss": g,
                   "word": PLATE_WORDS.get(order[i], "")}
                  for i, (p, k, r, g) in enumerate(PARTS)],
        "path": [list(c) for c in order],
        "cells": [list(c) for c in PLATE_CELLS],
        "closes": closes, "n": 6}, ensure_ascii=False)

    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "ScholarlyArticle",
        "name": "ยันต์เกศาผิด — the yant that writes the thirty-two parts",
        "url": f"{site}/kesa/",
        "description": "Where the kesa yant's method comes from, traced through the "
                       "manuals in this corpus, and whether its closing loop is possible.",
        "license": "https://creativecommons.org/licenses/by/4.0/",
    }, ensure_ascii=False)

    closed_line = ("no closed tour exists" if not b["closed"]["exists"]
                   else "a closed tour exists")
    return PAGE.replace("{{SITE}}", site).replace("{{JSONLD}}", jsonld) \
        .replace("{{PARTS}}", part_rows).replace("{{VARS}}", var_rows) \
        .replace("{{PALI}}", pali_rows).replace("{{CHAIN}}", chain_html) \
        .replace("{{SRC}}", src).replace("{{TERMS}}", term_rows) \
        .replace("{{DATA}}", data) \
        .replace("{{PAGES}}", f"{c.get('pages', 0):,}") \
        .replace("{{MSS}}", f"{c.get('manuscripts', 0):,}") \
        .replace("{{CLOSEDNODES}}", f"{b['closed']['nodes']:,}") \
        .replace("{{CLOSEDLINE}}", closed_line) \
        .replace("{{PLATE}}", gallery) \
        .replace("{{FIXED}}", str(fixed)) \
        .replace("{{AMBIG}}", str(len(PARTS) - fixed)) \
        .replace("{{SOLUTIONS}}", str(len(orders))) \
        .replace("{{CLOSES}}", "closes" if closes else "does not close") \
        .replace("{{FIRSTCELL}}", f"r{order[0][0] + 1} c{order[0][1] + 1}") \
        .replace("{{LASTCELL}}", f"r{order[-1][0] + 1} c{order[-1][1] + 1}") \
        .replace("{{BOARDROWS}}", board_rows) \
        .replace("{{TESTED}}", str(tested)) \
        .replace("{{OPENFOUND}}", str(open_found)) \
        .replace("{{CLOSEDFOUND}}", str(closed_found)) \
        .replace("{{NODETOTAL}}", f"{sum(v['closed']['nodes'] + v['open']['nodes'] for v in bs.values()):,}")


PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ยันต์เกศาผิด · the thirty-two parts, laid by the knight's move · wichaa</title>
<meta name="description" content="The kesa yant writes the first letter of each of the thirty-two parts of the body, laid in by the knight's move. Where that method comes from, traced through the manuals in this corpus — and whether the loop closes.">
<link rel="canonical" href="{{SITE}}/kesa/">
<meta property="og:type" content="article">
<meta property="og:site_name" content="wichaa">
<meta property="og:title" content="ยันต์เกศาผิด · the thirty-two parts, laid by the knight's move">
<meta property="og:description" content="A list recited to make the body repellent, turned into a formula for making it uncuttable — and put on a chessboard.">
<meta property="og:url" content="{{SITE}}/kesa/">
<meta property="og:image" content="{{SITE}}/og.jpg">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{{JSONLD}}</script>
<style>
 :root{--bg:#f4efe3;--panel:#fdfbf5;--ink:#26302a;--muted:#6d6455;--gold:#a8791e;
  --gold-soft:#c9a24a;--crimson:#8c3b2e;--line:#e5dcc7;--ok:#2f6b4f;
  --serif:"Sukhumvit Set","Noto Serif Thai",Thonburi,"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
  --sans:"Sukhumvit Set","Noto Sans Thai",Thonburi,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
  font-family:var(--sans);font-size:18px;line-height:1.65}
 a{color:var(--crimson)}
 .wrap{max-width:900px;margin:0 auto;padding:0 24px}
 header{text-align:center;padding:52px 24px 12px}
 .mark{font-family:var(--serif);letter-spacing:.4em;color:var(--gold);font-size:13px}
 h1{font-family:var(--serif);font-size:clamp(28px,5vw,44px);margin:14px 0 6px;line-height:1.15}
 h1 small{display:block;font-size:.46em;color:var(--muted);font-style:italic;margin-top:10px}
 .sub{color:#3c463f;font-family:var(--serif);font-style:italic;font-size:19px;max-width:700px;margin:10px auto 0}
 h2{font-family:var(--serif);font-size:26px;margin:46px 0 10px}
 h3{font-family:var(--serif);font-size:20px;margin:0 0 4px}
 .big{display:flex;gap:18px;flex-wrap:wrap;margin:26px 0 8px;justify-content:center}
 .big div{background:var(--panel);border:1px solid var(--line);border-radius:14px;
  padding:16px 22px;min-width:150px;text-align:center}
 .big b{display:block;font-family:var(--serif);font-size:34px;color:var(--gold);line-height:1.1}
 .big span{font-size:13px;color:var(--muted)}
 table{width:100%;border-collapse:collapse;margin:16px 0;font-size:15.5px;background:var(--panel)}
 th,td{border-bottom:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
 th{font-weight:600;color:var(--muted);font-size:13.5px}
 td.w{font-family:var(--serif);font-size:18px}
 td.k{font-family:var(--serif);font-size:20px;color:var(--crimson);white-space:nowrap}
 td.r{font-style:italic;color:var(--muted)}
 td.g{font-size:14px;color:var(--muted)}
 td.n{font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
 td.muted{color:var(--muted)}
 td.y{font-family:var(--serif);font-size:16px}
 td.b{width:26%;min-width:90px}
 td.b span{display:block;height:11px;background:var(--gold-soft);border-radius:2px}
 blockquote{margin:16px 0;padding:18px 22px;background:var(--panel);
  border-left:4px solid var(--gold);border-radius:0 12px 12px 0}
 blockquote .th{font-family:var(--serif);font-size:19px;line-height:1.9}
 blockquote .en{margin-top:12px;color:#3c473f}
 blockquote cite{display:block;margin-top:12px;font-size:13.5px;color:var(--muted);font-style:normal}
 ol.chain{list-style:none;counter-reset:s;padding:0;margin:18px 0}
 ol.chain li{counter-increment:s;position:relative;padding:0 0 26px 52px;
  border-left:2px solid var(--line);margin-left:14px}
 ol.chain li:last-child{border-left-color:transparent}
 ol.chain li::before{content:counter(s);position:absolute;left:-17px;top:0;width:32px;height:32px;
  border-radius:50%;background:var(--gold);color:#fdfbf5;font-family:var(--serif);
  display:grid;place-items:center;font-size:16px}
 ol.chain .ms{font-family:var(--serif);font-size:15px;color:var(--gold);margin-bottom:6px}
 ol.chain p{margin:6px 0 0}
 .boardwrap{background:var(--panel);border:1px solid var(--line);border-radius:16px;
  padding:20px;margin:18px 0}
 .boardwrap svg{width:100%;height:auto;display:block;max-width:560px;margin:0 auto}
 .cell{fill:#fdfbf5;stroke:var(--line)}
 .cell.dark{fill:#efe7d4}
 .cell.on{fill:#f3e2bc}
 .lay{font-family:var(--serif);font-size:13px;fill:var(--ink)}
 .num{font-family:var(--sans);font-size:6px;fill:var(--muted)}
 .trail{fill:none;stroke:var(--crimson);stroke-width:1.2;stroke-linecap:round;opacity:.75}
 .shut{fill:none;stroke:var(--crimson);stroke-width:1.4;stroke-dasharray:4 3;opacity:.6}
 .ctl{display:flex;gap:10px;flex-wrap:wrap;align-items:center;justify-content:center;margin-top:14px}
 .ctl button{font:inherit;font-size:15px;padding:9px 16px;border-radius:999px;
  border:1.5px solid var(--crimson);background:transparent;color:var(--crimson);cursor:pointer}
 .ctl button.p{background:var(--crimson);color:#fdfbf5}
 .read{text-align:center;font-family:var(--serif);margin-top:12px;min-height:3.2em}
 .read b{font-size:24px;color:var(--crimson)}
 .read i{display:block;font-size:15px;color:var(--muted);font-style:normal}
 .gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));
  gap:18px;margin:26px 0 10px}
 .gallery figure{margin:0}
 .gallery img{width:100%;height:auto;display:block;background:#000;
  border:1px solid var(--line);border-radius:10px}
 .gallery figcaption{font-size:13px;color:var(--muted);margin-top:8px;line-height:1.5}
 .gallery figcaption .th{display:block;font-family:var(--serif);font-size:15px;
  color:var(--ink)}
 .fr{fill:none;stroke:var(--line);stroke-width:1.4}
 .trail.shut{stroke-dasharray:none;stroke-width:1.8;opacity:1}
 td.c{font-family:var(--serif);font-size:15px;color:var(--gold)}
 .fix{background:#fdf6e8;border:1px solid var(--gold-soft);border-radius:14px;
  padding:4px 22px 14px;margin:24px 0}
 .fix h3{color:var(--crimson)}
 table.wide{font-size:14.5px}
 @media (max-width:760px){table.wide td.c,table.wide th:nth-child(6){display:none}}
 .thai{background:var(--panel);border:1px solid var(--line);border-radius:16px;
  padding:6px 24px 14px;margin:26px 0 8px;font-family:var(--serif);font-size:17.5px;line-height:1.95}
 .thai b{color:var(--gold);font-weight:600}
 .note{font-size:15px;color:var(--muted);border-top:1px solid var(--line);padding-top:14px;margin-top:34px}
 .go{display:inline-block;margin:6px 8px 6px 0;padding:11px 18px;background:var(--crimson);
  color:#fdfbf5;border-radius:999px;text-decoration:none;font-size:15px}
 .go.alt{background:transparent;color:var(--crimson);border:1.5px solid var(--crimson)}
 footer{padding:40px 0 60px;text-align:center;color:var(--muted);font-size:14px}
 @media (max-width:640px){td.g{display:none}td.r{display:none}}
</style>
</head><body>
<header><div class="wrap">
 <div class="mark">WICHAA</div>
 <h1>ยันต์เกศาผิด<small>a body written as thirty-two letters, laid in by the knight’s move</small></h1>
 <p class="sub">The yant carries the first letter of each of the thirty-two parts of the
 body, walked across the plate like a knight. The route closes, so it can be entered
 again without end — and the letters alone are enough to recover it.</p>
</div></header>
<div class="wrap">

 <div class="big">
  <div><b>32</b><span>parts, one letter each</span></div>
  <div><b>{{FIXED}}</b><span>letters that occur once</span></div>
  <div><b>{{SOLUTIONS}}</b><span>orders the plate can hold</span></div>
  <div><b>{{PAGES}}</b><span>transcribed pages searched</span></div>
 </div>

 <div class="thai">
  <p>ยันต์เกศาผิด คือยันต์ที่ลงอักษรตัวแรกของศัพท์ในอาการ ๓๒ ทีละตัว เดินตาม้าหมากรุกไปบนผัง
  ฉบับที่ว่ากันในโพสต์นั้นเดินวนกลับมาตั้งต้นใหม่ได้ ไม่มีที่สิ้นสุด</p>
  <p>หน้านี้ตามหาว่าวิธีลงแบบนี้มาจากไหน แล้วหาเจอในตำราที่อยู่ในคลังนี้เอง — อาการ ๓๒
  เป็นสูตรสำหรับลงยันต์รูปภาพอยู่ก่อนแล้ว (<b>สูตรการลงยันต์แบบขอมผสมไทย</b> น.๔๓)
  ใช้ภาวนาตอนผูกหุ่นพยนต์ด้วยซังข้าว ๓๒ เส้น (<b>ตำราสร้างเครื่องรางของขลัง</b> น.๗๘)
  และการลงอักขระ “ตามคำม้าหมากรุก” ก็มีบอกไว้แล้วในยันต์อีกตัวหนึ่ง
  (<b>ตำรามหายันต์</b> น.๒๗ ยันต์ที่ ๒๔) สิ่งที่ใหม่คือการเอาสามอย่างนี้มารวมกัน</p>
  <p>ส่วนคำถามว่าเดินวนครบ ๓๒ แล้วกลับมาตั้งต้นที่เดิมได้จริงหรือไม่ อันนี้คิดเลขได้
  และคำตอบคือ<b>ได้จริง</b> — ผังเป็นตาราง ๖×๖ ตัดสี่มุมออก เหลือ ๓๒ ช่องพอดี
  ตัวที่ ๓๒ กับตัวที่ ๑ ห่างกันเท่าตาม้าหมากรุก</p>
  <p>ที่น่าสนใจกว่านั้น: อักษรตัวแรก ๑๗ ตัวในผังไม่ซ้ำกับใคร เมื่อบวกกับเงื่อนไขว่าต้องเดินตาม้า
  ลำดับทั้ง ๓๒ ก็เหลือทางเดียว คืออ่านลำดับกลับออกมาจากตัวอักษรได้ ไม่ต้องดูลูกศร
  และตรงกับผังแบบเต็มคำทุกช่อง</p>
 </div>

 {{PLATE}}

 <h2>Watch it laid in</h2>
 <div class="boardwrap">
  <svg id="bd" viewBox="0 0 400 400" role="img" aria-label="The plate: a six by six grid with its four corners absent, thirty-two cells, each taking one letter in knight's-move order."></svg>
  <div class="ctl">
   <button class="p" id="play">Lay it in</button>
   <button id="step">One move</button>
   <button id="reset">Clear</button>
   <button id="shut">Close the loop</button>
  </div>
  <div class="read" id="read"><i>Thirty-two cells, thirty-two parts. Each move is a knight’s move.</i></div>
 </div>
 <p class="note">The grid, the empty corners and the order are the plate’s own, transcribed
 from the drawings above. The route is checked move by move when this page is built.</p>

 <h2>The thirty-two, and the letter each one gives</h2>
 <p>The method the post names is <b>อาทิสังเกต</b> — marking by the initial. Take the first
 letter of each word and lay that letter in, instead of the word. The plate does this twice
 over, once in Khom and once in Thai, and then gives the full words on two more plates.</p>
 <table class="wide">
  <thead><tr><th></th><th>Pali</th><th>laid in</th><th>read as</th><th>what it is</th>
   <th>the plate’s full word</th><th>cell</th></tr></thead>
  <tbody>{{PARTS}}</tbody>
 </table>

 <h2>How it came to be</h2>
 <p>Nothing about the kesa yant is invented at the yant. Every part of the method is
 already in the manuals — the list, the use of the list as words-while-you-draw, the
 knight’s move as an order, and the worry that makes a closed route worth having. What is
 new is putting them together.</p>
 <ol class="chain">{{CHAIN}}</ol>

 <h2>Recited to be repelled, recited to be uncuttable</h2>
 <p>That second step is the turn worth sitting with. In the meditation the thirty-two are
 gone through so that the body stops looking like a possession worth keeping. In the yant
 manual the same thirty-two are gone through so that the body cannot be cut. Same list,
 same order, opposite errand — and the manuals on this disk carry both without comment.</p>

 <h2>Where the lists disagree</h2>
 <p>The post’s table and the recension transcribed in this corpus are not identical. Set
 side by side, they part company in four places.</p>
 <table>
  <thead><tr><th></th><th>Pali</th><th>the post</th><th>ประมวลคาถาตำราโบราณ p.39</th><th></th></tr></thead>
  <tbody>{{VARS}}</tbody>
 </table>
 <p>And in two places both Thai lists read against the Pali commentaries, in the same
 direction — so this is the Thai liturgical convention rather than a slip in either.</p>
 <table>
  <thead><tr><th></th><th>Pali</th><th>both Thai lists</th><th></th></tr></thead>
  <tbody>{{PALI}}</tbody>
 </table>
 <p class="note">Item 32 is the tell that the set grew. <b>มตฺถเก มตฺถลุงฺคํ</b> — “the brain
 in the head” — is two words and a locative where every other entry is a single noun, and
 it is absent from the earlier canonical list, which runs to thirty-one. The yant needs
 thirty-two cells because a late addition made the count even.</p>

 <h2>Counted in this corpus</h2>
 <table>
  <thead><tr><th>word</th><th>said</th><th>what it means</th><th></th><th>pages</th><th>mss</th></tr></thead>
  <tbody>{{TERMS}}</tbody>
 </table>
 <p class="note">Thai is written without spaces, so a short word matches inside longer ones
 and each count is an upper bound. These are counts over the pages transcribed so far, which
 are a slice of the catalogue, not the whole of it — a nil here means not on this disk.</p>

 <h2>Does the route close?</h2>
 <p>The post’s claim is a geometric one: the letters can be laid start to finish and then
 begun again by the same method, round without end. In chess terms the open route is a
 knight’s tour and the looping one is a <i>closed</i> tour — one whose last cell is a
 knight’s move from its first.</p>
 <p><b>It closes.</b> The plate’s board is a 6×6 grid with its four corner cells absent,
 which leaves exactly thirty-two — and the route drawn on it runs {{FIRSTCELL}} to
 {{LASTCELL}}, a knight’s move apart. Every one of the thirty-two steps is checked when
 this page is built, and so is the closing one.</p>

 <div class="fix">
  <h3>A correction</h3>
  <p>This page said the opposite when it first went up on 19 September 2026: that no
  thirty-two-cell board it tested could close, this one included. That was a bug in the
  search here, not a fact about the yant. A cell still to be visited can take its second
  edge from the cell the route started at — that is what closing a loop means — and the
  search was not counting it, so it threw away every closed tour one move before
  completion. The plate is what caught it.</p>
 </div>

 <h2>The letters are enough to recover the order</h2>
 <p>The interesting consequence is what อาทิสังเกต costs and what it does not. Cutting
 thirty-two words down to their initials looks lossy — five cells read อ, and โล, น, ว, ปิ
 and เส each appear twice. But <b>{{FIXED}} of the thirty-two letters occur only once on
 the plate</b>, which pins those cells outright, and the knight’s move constrains what can
 follow what. Put those two together and the remaining {{AMBIG}} cells have
 <b>{{SOLUTIONS}}</b> arrangement: the order is recoverable from the letters alone, with
 the arrows removed.</p>
 <p>That is not an argument this page makes about the plate — it is what the plate does.
 The order derived that way was then checked against the two full-word drawings, cell by
 cell, and agrees on all thirty-two. The design is self-checking: lay the letters wrong and
 no knight’s route will thread them.</p>

 <h2>Why a rectangle cannot do it</h2>
 <p>Thirty-two cells do not have to sit in that shape, and most shapes will not take the
 route. Eleven arrangements are searched here exhaustively, open and closed — the two
 rectangles that hold thirty-two cells, and every way of leaving four cells empty in a 6×6
 so that a quarter turn carries the empty cells onto each other, which is the family that
 keeps a plate symmetric. The plate’s own board is the last of those.</p>
 <table>
  <thead><tr><th>thirty-two cells as</th><th>open route</th><th>closes</th>
   <th>nodes searched</th><th>light&#8202;/&#8202;dark</th></tr></thead>
  <tbody>{{BOARDROWS}}</tbody>
 </table>
 <p><b>{{OPENFOUND}} of {{TESTED}} take the open route; {{CLOSEDFOUND}} close</b>, the
 plate’s board among them. {{NODETOTAL}} positions were examined. A 4×8 block takes the
 open route and cannot close, and there the result is general rather than particular: no
 rectangle four cells deep has a closed tour, whatever its length. What the rectangle has
 and the plate does not is corners — a cell in the corner of a rectangle is one a knight
 can enter only two ways, and a closed route has to use both. The plate cuts those four
 cells out of the grid entirely, which is also what brings the count to thirty-two.</p>
 <p>Nor does any of this turn on the easy check: a knight always moves between a light cell
 and a dark one, so a closed route needs sixteen of each, and every board in the table has
 sixteen of each. Shape decides it, not the count.</p>

 <h2>ผิด, พิด, พิศ</h2>
 <p>The post is careful about the name and this page will be too. Some manuals write
 <b>ผิด</b> — wrong, out of place. Some write <b>พิด</b>, which reads as poison. Some write
 <b>พิศ</b>, to gaze at, to consider closely. Only the third has an obvious bearing on a
 list of body parts used for contemplation, and the post’s own hashtag uses the first. Who
 first tied this yant, and which he meant, the post says nobody knows.</p>

 <h2>Sources</h2>
 <table>
  <thead><tr><th>what</th><th>when</th><th>the part used here</th><th></th></tr></thead>
  <tbody>{{SRC}}</tbody>
 </table>

 <p>
  <a class="go" href="{{SITE}}/yant/">The yant designs of this corpus →</a>
  <a class="go alt" href="{{SITE}}/hun/">หุ่นพยนต์ · the effigy →</a>
  <a class="go alt" href="{{SITE}}/handpoke/">สักขาลาย · the leg tattoo →</a>
 </p>
 <p class="note">Text and tables on this page: CC BY 4.0, attribution to wichaa.net.
 Translations from the Thai are this project’s. The manuscript pages quoted are contributed
 volumes in this corpus, cited by their transcribed page.</p>
</div>
<footer>wichaa.net · <a href="{{SITE}}/">home</a> ·
 <a href="{{SITE}}/api/kesa.json">this page as JSON</a></footer>
<script>
(function(){
 var D = {{DATA}};
 var svg=document.getElementById('bd'), read=document.getElementById('read');
 var N=D.n, S=58, PAD=(400-N*S)/2, i=0, timer=null;
 var live={}; D.cells.forEach(function(c){live[c[0]+'_'+c[1]]=true});
 function cx(c){return PAD + c[1]*S + S/2}
 function cy(c){return PAD + c[0]*S + S/2}
 function el(n,a){var e=document.createElementNS('http://www.w3.org/2000/svg',n);
  for(var k in a) e.setAttribute(k,a[k]); return e}
 function frame(){
  svg.innerHTML='';
  // the plate's own outline: two overlapping squares, corners curled
  var a=PAD+S, b=PAD+(N-1)*S;
  svg.appendChild(el('rect',{x:a,y:PAD,width:(N-2)*S,height:N*S,rx:10,'class':'fr'}));
  svg.appendChild(el('rect',{x:PAD,y:a,width:N*S,height:(N-2)*S,rx:10,'class':'fr'}));
  D.cells.forEach(function(c){
   svg.appendChild(el('rect',{x:PAD+c[1]*S,y:PAD+c[0]*S,width:S,height:S,
     'class':'cell'+(((c[0]+c[1])%2)?' dark':''),id:'c'+c[0]+'_'+c[1]}));
  });
  svg.appendChild(el('g',{id:'trail'}));
  svg.appendChild(el('g',{id:'marks'}));
 }
 function draw(){
  var marks=document.getElementById('marks'), trail=document.getElementById('trail');
  marks.innerHTML=''; trail.innerHTML='';
  D.cells.forEach(function(c){
   document.getElementById('c'+c[0]+'_'+c[1])
     .setAttribute('class','cell'+(((c[0]+c[1])%2)?' dark':''));
  });
  for(var n=0;n<i;n++){
   var c=D.path[n], p=D.parts[n];
   document.getElementById('c'+c[0]+'_'+c[1]).setAttribute('class','cell on');
   var t=el('text',{x:cx(c),y:cy(c)+6,'class':'lay','text-anchor':'middle'});
   t.textContent=p.key; marks.appendChild(t);
   var u=el('text',{x:PAD+c[1]*S+5,y:PAD+c[0]*S+12,'class':'num'});
   u.textContent=(n+1); marks.appendChild(u);
   if(n>0){var a=D.path[n-1];
    trail.appendChild(el('line',{x1:cx(a),y1:cy(a),x2:cx(c),y2:cy(c),'class':'trail'}));}
  }
  if(i>0){var p=D.parts[i-1];
   read.innerHTML='<b>'+p.key+'</b> · '+p.pali+
     ' <i>'+p.word+' — '+p.gloss+'</i>';}
  else read.innerHTML='<i>Thirty-two cells, thirty-two parts. Each move is a knight\u2019s move.</i>';
 }
 function step(){ if(i<D.path.length){i++; draw(); if(i===D.path.length) shut(true);} else stop(); }
 function stop(){ if(timer){clearInterval(timer); timer=null;
   document.getElementById('play').textContent='Lay it in';} }
 function shut(auto){
  if(i<D.path.length){ i=D.path.length; draw(); }
  var a=D.path[D.path.length-1], b=D.path[0];
  document.getElementById('trail').appendChild(
    el('line',{x1:cx(a),y1:cy(a),x2:cx(b),y2:cy(b),
               'class':D.closes?'trail shut':'shut'}));
  read.innerHTML='<b>ม \u2192 เก</b><i>' + (D.closes
    ? 'Thirty-two back to one is a knight\u2019s move, so the route closes and can be entered again.'
    : 'That last link is not a knight\u2019s move.') + '</i>';
  if(auto) stop();
 }
 document.getElementById('step').onclick=function(){stop(); step()};
 document.getElementById('reset').onclick=function(){stop(); i=0; draw()};
 document.getElementById('shut').onclick=function(){stop(); shut(false)};
 document.getElementById('play').onclick=function(){
  if(timer){stop(); return}
  if(i>=D.path.length) i=0;
  this.textContent='Stop';
  timer=setInterval(step,330);
 };
 frame(); draw();
})();
</script>
</body></html>
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", required=True)
    ap.add_argument("--site-url", default="https://wichaa.net")
    ap.add_argument("--recompute", action="store_true",
                    help="re-solve every board instead of using the cache")
    a = ap.parse_args(argv)
    docs = Path(a.docs)
    if not docs.is_dir():
        raise SystemExit(f"kesa: docs directory not found: {docs}")
    c = counts()
    if not c:
        print(f"kesa: catalog.db not at {DB} — cannot count, page not written",
              file=sys.stderr)
        return 1
    bs = boards(recompute=a.recompute)
    bad = [k for k, v in bs.items()
           if not (v["open"]["exhausted"] and v["closed"]["exhausted"])]
    if bad:
        print("kesa: search hit its node cap on " + ", ".join(bad) +
              "; the page would claim an exhaustive result it does not have — "
              "not written", file=sys.stderr)
        return 1
    four = bs["4x8"]
    if not four["open"]["exists"] or not is_tour(
            [tuple(x) for x in four["open"]["path"]], rect(4, 8), False):
        print("kesa: no verified open tour on the 4x8 board — page not written",
              file=sys.stderr)
        return 1
    site = a.site_url.rstrip("/")
    (docs / "kesa").mkdir(parents=True, exist_ok=True)
    orders, fixed = solve_order()
    if not orders:
        print("kesa: the plate transcription admits no knight's-move order at all — "
              "the grid has been mistyped; page not written", file=sys.stderr)
        return 1
    order = orders[0]
    if not is_tour(order, PLATE_CELLS, True):
        print("kesa: the order recovered from the plate is not a closed tour of its "
              "thirty-two cells; page not written", file=sys.stderr)
        return 1
    # the two full-word drawings are the independent check on the order
    missing = [c for c in PLATE_CELLS if c not in PLATE_WORDS]
    if missing:
        print(f"kesa: {len(missing)} cells have no full word transcribed; "
              f"page not written", file=sys.stderr)
        return 1

    pls = plate_files()
    for name, raw in pls:
        (docs / "kesa" / name).write_bytes(raw)
    if pls and len(pls) != len(PLATES):
        print(f"kesa: only {len(pls)} of {len(PLATES)} plate drawings are on disk",
              file=sys.stderr)
    (docs / "kesa" / "index.html").write_text(
        render(c, bs, site, orders, fixed, len(pls) == len(PLATES)), encoding="utf-8")
    (docs / "api").mkdir(parents=True, exist_ok=True)
    (docs / "api" / "kesa.json").write_text(json.dumps({
        "parts": [{"pali": p, "laid_in": k, "thai_reading": r, "gloss": g}
                  for p, k, r, g in PARTS],
        "corpus": {"pages_transcribed": c["pages"], "manuscripts": c["manuscripts"],
                   "terms": c["terms"]},
        "boards": bs,
        "plate": {"cells": [list(c) for c in PLATE_CELLS],
                  "grid": {f"r{r+1}c{cc+1}": l for (r, cc), l in sorted(PLATE_GRID.items())},
                  "words": {f"r{r+1}c{cc+1}": w for (r, cc), w in sorted(PLATE_WORDS.items())},
                  "order": [list(c) for c in order],
                  "letters_occurring_once": fixed,
                  "orders_consistent_with_the_letters": len(orders),
                  "closed": True,
                  "credit": {"by": PLATE_CREDIT[0], "when": PLATE_CREDIT[1]}},
        "licence": "CC BY 4.0",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    shut = sum(1 for v in bs.values() if v["closed"]["exists"])
    print(f"kesa: /kesa written — the plate's order recovered from its letters "
          f"({fixed} of 32 pinned by letter, {len(orders)} arrangement), closed tour "
          f"verified; {len(bs)} boards solved, {shut} close; {len(pls)} plates published; "
          f"{c['pages']:,} pages searched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
