#!/usr/bin/env python3
"""file_chai — ใจ's compounds, filed by hand.

WHY BY HAND
Measured against sourced filings, gloss similarity picks a head's core sense 91%
of the time where the source says 9%. It cannot do this. ใจ has 134 open
compounds and is the most productive head in the lexicon, so it is done by
reading, and the reading follows one rule stated in advance rather than 134
separate judgements:

  1  ใจ as the FACULTY — the seat itself. Standing dispositions (ใจดี, ใจร้อน)
     and anything done to or with it (ตั้งใจ, ไว้ใจ, ตัดใจ, เข้าใจ).
  4  ใจ as the FEELINGS — a state that befalls you (ดีใจ, เสียใจ, ตกใจ, ช้ำใจ).
  3  ใจ as BREATH — สิ้นใจ, ขาดใจ, ถอนใจ, and บัดใจ, a moment being one breath.
  2  ใจ as the ORGAN, and the beloved spoken of as the heart — ดวงใจ, ขวัญใจ.
  5  ใจ as the CRUCIAL POINT — ใจความ the gist, ใจกลาง the centre.

The 1/4 line is the one that carries the weight and it is the same asymmetry
lexicon_frames.py found: ใจ-first is a property of the person, so the faculty;
ใจ-second is something that happened to them, so the feeling. Where a compound
could be read either way the frame decides it.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ENTRY = Path(__file__).resolve().parent.parent / "data" / "lexicon" / "entries" / "chai.json"

F = {
 # 1 — the faculty: dispositions, and acts on or with it
 1: """ใจบุญ จิตใจ กลับใจ ใจลอย หลายใจ ถอดใจ ใจร้าย เป็นใจ จริงใจ สำรวมใจ ดลใจ ใจดำ
    ข่มขืนใจ ใจแคบ ลองใจ กาวใจ สุจริตใจ ใจคอ ใจหมา ตกลงใจ เปลี่ยนใจ ใจเร็ว วางใจ
    กำลังใจ จงใจ รู้ใจ เห็นใจ ตัดสินใจ นอกใจ ตัดใจ ใส่ใจ ใจหิน คู่ใจ ใจแข็ง ตั้งใจ
    ใจแตก ดูใจ ใจกว้าง เชื่อใจ ใจพระ แน่ใจ ทันใจ ใจร้อน ใจเดียว ใจน้อย ใจเพชร ปลงใจ
    เกรงใจ เต็มใจ ตามใจ สนใจ สมัครใจ ซื้อใจ เข้าใจ แข็งใจ มั่นใจ ชั่งใจ จูงใจ ใจง่าย
    ใจกล้า ใจเบา ตายใจ ใจดี ไว้ใจ ขอบใจ ใจสัตว์ ใจเสาะ ใจเย็น เอาใจ ปลุกใจ อำเภอใจ
    ขืนใจ นอนใจ""",
 # 4 — the feelings: a state that befalls
 4: """เสียวใจ เฉลียวใจ พอใจ น้อยใจ ฉุกใจ คาใจ จับใจ หลากใจ สะใจ ตกใจ ภอใจ ขวยใจ
    แหนงใจ ถึงใจ ดีใจ ไข้ใจ ช้ำใจ หนักใจ หมางใจ ชื่นใจ เจ็บใจ จุใจ เบาใจ ถูกใจ หนำใจ
    สะเทือนใจ แปลกใจ เสมอใจ ข้องใจ ค้างคาใจ กริ่งใจ อิ่มใจ ประทับใจ ใจหาย ฝังใจ
    สบายใจ เสียใจ แคลงใจ สมใจ ได้ใจ ขัดใจ ภูมิใจ ชอบใจ สลดใจ เข็ญใจ สาใจ พิมพ์ใจ
    ผิดใจ ต้องใจ โล่งใจ กินใจ""",
 # 3 — breath
 3: "สิ้นใจ ขาดใจ ถอนใจ บัดใจ",
 # 2 — the organ, and the beloved as heart
 2: "ดวงใจ ขวัญใจ กลอยใจ สายใจ",
 # 5 — the crucial point
 5: "ใจความ ใจกลาง",
}
WHY = {
 1: "ใจ as the faculty — a standing disposition, or something done to or with it",
 2: "ใจ as the organ, and the beloved spoken of as the heart",
 3: "ใจ as breath",
 4: "ใจ as the feelings themselves — a state that befalls",
 5: "ใจ as the crucial point of a thing",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    want = {w: n for n, block in F.items() for w in block.split()}
    d = json.loads(ENTRY.read_text("utf-8"))
    by_n = {s["n"]: s for s in d["senses"]}
    keep, moved = [], Counter()
    for c in d.get("compounds_unassigned", []):
        n = want.get(c["th"])
        if n is None or n not in by_n:
            keep.append(c)
            continue
        c = dict(c)
        c["conf"] = "standard"
        c["src"] = sorted(set((c.get("src") or []) + ["CUR"]))
        c["note"] = ((c.get("note", "") + " · ") if c.get("note") else "") + \
                    f"filed under sense {n} by hand: {WHY[n]}"
        by_n[n].setdefault("compounds", []).append(c)
        moved[n] += 1
    unmatched = [w for w in want if w not in
                 {c["th"] for s in d["senses"] for c in s.get("compounds", [])}]
    if keep:
        d["compounds_unassigned"] = keep
    else:
        d.pop("compounds_unassigned", None)
    print("filed by hand:", {f"sense {k}": v for k, v in sorted(moved.items())},
          "total", sum(moved.values()))
    print(f"left open: {len(keep)}")
    if unmatched:
        print(f"named but not found among the open set ({len(unmatched)}): "
              f"{' '.join(unmatched[:12])}")
    if a.write:
        ENTRY.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", "utf-8")
        print("written")
    else:
        print("(dry run — pass --write)")


if __name__ == "__main__":
    main()
