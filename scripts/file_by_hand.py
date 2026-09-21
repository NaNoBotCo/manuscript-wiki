#!/usr/bin/env python3
"""file_by_hand — compounds filed under senses by reading, one head at a time.

Gloss similarity picks a head's core sense 91% of the time where the source says
9%, so this cannot be automated and is done by reading. Each head gets a RULE
stated before the list, so the filing can be argued with as a whole rather than
compound by compound, and so a wrong call is a wrong rule and not 84 mistakes.

    python3 scripts/file_by_hand.py --head tua --write
    python3 scripts/file_by_hand.py --all --write
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

LEX = Path(__file__).resolve().parent.parent / "data" / "lexicon" / "entries"

TABLE = {
 "tua": {
   "_rule": "ตัว splits four ways. The SELF (5) takes everything reflexive — what a "
            "person does to or about themselves. The REFERRING word (3) takes people "
            "named by a role. The FORM (1) takes letters, notes and the thing-itself. "
            "The BODY (2) takes only what is literally corporeal.",
   1: """ตัวอักษร ตัวสะกด ตัวย่อ ตัวขาว ตัวดำ ตัวแปล ตัวเมือง ตัวอย่าง ตายตัว ขาดตัว
        ลงตัว ตัวกลม""",
   2: "ลำตัว ห่อตัว แข็งตัว ตัวอ่อน ไหวตัว ถีบตัว",
   3: """ตัวแทน ตัวการ ตัวสำคัญ ตัวเอก ตัวร้าย ตัวประกอบ ตัวตลก ตัวยุ่ง ตัวเอ้ ตัวประกัน
        ตัวตึง คุณตัว อีตัว ตัวสำรอง ตัวกระตุ้น ตัวนำ ตัวเมีย ตัวผู้""",
   5: """ตัวเอง คืนตัว คุมตัว ติดตัว คงตัว ตั้งตัว เสนอตัว ชื่อตัว เฉพาะตัว กักตัว ฝากตัว
        รู้ตัว เปิดตัว ตื่นตัว หายตัว ขายตัว เตรียมตัว รายงานตัว ก่อตัว สลายตัว ถ่อมตัว
        เล่นตัว วางตัว ส่วนตัว ปลีกตัว ถือตัว เจ้าตัว ถวายตัว หวงตัว แก่ตัว ลืมตัว ไว้ตัว
        ทำตัว เสียตัว อวดตัว ร้อนตัว ลดตัว ทะนงตัว แยกตัว ถอนตัว เลี้ยงตัว เก็บตัว มอบตัว
        แก้ตัว เกินตัว เสมอตัว""",
   7: "ตัวแปร ตัวตั้ง",
 },
 "na": {
   "_rule": "หน้า's nineteen senses collapse to four working groups. The FACE (1) "
            "takes the literal countenance. DIGNITY (15) takes the whole face-losing "
            "and face-saving vocabulary, which is the largest group and the reason "
            "the word matters. The FACING SIDE (3) takes spatial relations to a "
            "person. AHEAD (17) takes what is in front in time or motion.",
   1: """หน้าหยก เบ้าหน้า หน้าเน่า หน้าตาย หน้าเป็น สีหน้า หน้าชา หน้าตา ตีหน้า ก้มหน้า
        หน้ามืด เหม็นหน้า เบื่อหน้า หนังหน้า หน้ากาก วางหน้า หน้าม้า""",
   2: "หน้าอก หน้าตัก",
   3: """ต่อหน้า ซึ่งหน้า เข้าหน้า หนีหน้า หลบหน้า สู้หน้า รับหน้า ออกหน้า เสมอหน้า
        เกินหน้า ปาดหน้า ไหมหน้า""",
   4: "ฉาบหน้า หน้าหม้อ",
   5: "หน้ากระฉีก หน้าตั้ง",
   6: "ย่อหน้า เปิดหน้า",
   9: "ไม้หน้า หน้าไม้ กรอบหน้า",
   12: "หน้าที่",
   13: "หน้าแล้ง",
   14: "นายหน้า หัวหน้า กองหน้า ฝ่ายหน้า",
   15: """เสียหน้า ได้หน้า ไว้หน้า ขายหน้า รักษาหน้า แก้หน้า งามหน้า ฉีกหน้า หน้าแหก
        เอาหน้า หน้าด้าน หน้าทน หน้าหนา เสนอหน้า แบกหน้า หมายหน้า ตอกหน้า ตราหน้า
        หน้าแตก น้ำหน้า""",
   17: "ล่วงหน้า ก้าวหน้า ตั้งหน้า ไฟหน้า หน้าต่าง หน้าจั่ว หน้าเงิน",
 },
 "luk": {
   "_rule": "ลูก is offspring (1) and round-thing (7), and almost nothing else. Sense 1 "
            "carries its own figurative reach — the RID's own gloss says โดยปริยาย "
            "ถือว่ามีฐานะเสมือนลูก — so anyone who BELONGS to a household, a crew, a "
            "trade or a patron files there: ลูกน้อง, ลูกค้า, ลูกจ้าง, ลูกเรือ.",
   1: """ลูกสะใภ้ ลูกครึ่ง ลูกชาย ลูกหญิง ลูกสาว ลูกเขย ลูกเลี้ยง ลูกหัวปี ลูกอ่อน ลูกหลาน
        ลูกผู้ชาย ลูกผู้หญิง ลูกลก ลูกอก ลูกขวัญ ลูกแก้ว ลูกประสม ลูกผสม ออกลูก ตกลูก
        รีดลูก มดลูก ลูกเถื่อน ลูกหลง ลูกบ้าน ลูกเรือ ลูกน้อง ลูกพี่ ลูกจ้าง ลูกค้า ลูกหนี้
        ลูกขุน ลูกมือ ลูกทัวร์ ลูกทัพฟ้า ลูกเสือ""",
   4: "ลูกเจี๊ยบ ลูกกระจอก",
   5: "ลูกหวาย",
   7: """ลูกคิด ลูกกวาด ลูกปัด ลูกบาศก์ ลูกนิมิต ลูกชะเนาะ ลูกคลื่น ลูกระเบิด ลูกสูบ ลูกเอ็น
        ลูกดอก ลูกบิด ลูกอม ลูกกรง ลูกกะโล่ ลูกโซ่ ลูกเห็บ ลูกโลก ลูกประคำ ลูกน้ำ ลูกโป่ง
        ลูกชิ้น ลูกปืน ลูกหนัง ลูกเล่น ลูกคำ ล้วงลูก""",
 },
 "ta": {
   "_rule": "ตา is two words and the compounds sort cleanly between them. The EYE (4) "
            "takes nearly everything. The GRANDFATHER (1) takes the kin terms. The "
            "APERTURE (6) takes what is a hole in a mesh or a face on an instrument. "
            "เมตตา, อัตตา, ชะตา and มาตา are Pali and Sanskrit and are not here at all.",
   1: "พ่อตา หลานตา ขรัวตา",
   4: """แว่นตา กวาดตา เข้าตา น้ำตา ขวัญตา หลบตา ตาโต แยงตา จับตา เปลือกตา กลีบตา ขี้ตา
        ตาพอง ลับตา ตาหวาน ตบตา ตาเจ้าชู้ ถูกตา ขนตา ตาลาย นัยน์ตา ตาดำ จกตา หน้าตา
        ตาบอด กระจกตา สายตา ตาขาว ตาทิพย์ หนังตา แก้วตา ดวงตา ลวงตา ขัดตา ตาลุก ต้องตา
        กินน้ำตา ตากุ้ง ตาน้ำข้าว""",
   5: "ตาปู ตาขอ",
   6: "ตาข่าย ตาไก่ ตาชั่ง ตาเหลว ตาน้ำ",
   8: "ตาสับปะรด",
 },
 "nam": {
   "_rule": "น้ำ is nearly all sense 1 (water) or 2 (a liquid LIKE water). The line is "
            "whether the thing IS water — น้ำแข็ง, น้ำทะเล, ห้องน้ำ — or is merely "
            "liquid and named for it: น้ำนม, น้ำตาล, น้ำมูก, น้ำเชื่อม. Sense 3, the "
            "essence of a thing, takes only น้ำเสียง and น้ำหน้า.",
   1: """น้ำดื่ม ห้องน้ำ กดน้ำ ตลาดน้ำ หม้อน้ำ กินน้ำ สรงน้ำ สีน้ำ ตาน้ำ กระแสน้ำ น้ำค้าง
        สายน้ำ น้ำแข็ง น้ำทะเล น้ำมนต์ น้ำประปา ห้วงน้ำ น้ำท่า น้ำสุก ต้นน้ำ ร่องน้ำ ลายน้ำ
        พืชน้ำ น้ำดิบ น้ำพุ น้ำกระด้าง น้ำอ่อน น้ำขึ้น น้ำใต้ดิน ตำหนักน้ำ น้ำแร่ อาบน้ำ
        น้ำกลั่น น้ำเค็ม น้ำฟ้า กรวดน้ำ น่านน้ำ ตะไคร่น้ำ แม่น้ำ น้ำท่วม ฟองน้ำ น้ำตก
        น้ำซึม อวบน้ำ ค่าน้ำ ลูกน้ำ น้ำเปล่า น้ำดี ปากน้ำ สัตว์น้ำ น้ำป่า ประตูน้ำ ช้างน้ำ
        ตะพาบน้ำ น้ำเงิน""",
   2: """น้ำปรุง น้ำหอม น้ำนม น้ำตาล น้ำเกลือ น้ำเต้าหู้ น้ำเหลือง น้ำรัก น้ำเคย น้ำเดิน
        น้ำข้าว น้ำมูก น้ำเชื่อม น้ำอัดลม น้ำจัณฑ์ น้ำกาม น้ำขาว น้ำยา น้ำว่าว ไข่น้ำ
        น้ำลำไย น้ำกรด น้ำย่อย น้ำกะทิ น้ำแตก น้ำลาย น้ำนางเอก""",
   3: "น้ำเสียง น้ำหน้า",
 },
}


def file_head(slug, spec, write):
    f = LEX / f"{slug}.json"
    d = json.loads(f.read_text("utf-8"))
    want = {w: n for n, block in spec.items() if isinstance(n, int)
            for w in block.split()}
    by_n = {s["n"]: s for s in d["senses"]}
    keep, moved, unknown = [], Counter(), []
    for c in d.get("compounds_unassigned", []):
        n = want.get(c["th"])
        if n is None or n not in by_n:
            if not c.get("use"):
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
    print(f"{d['th']:<6} filed {sum(moved.values()):3} "
          f"{dict(sorted(moved.items()))}  left open {len(keep)}"
          + (f"  NOT NAMED: {' '.join(unknown)}" if unknown else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--head")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    heads = list(TABLE) if a.all else [a.head]
    for h in heads:
        file_head(h, TABLE[h], a.write)
    if not a.write:
        print("(dry run — pass --write)")


if __name__ == "__main__":
    main()
