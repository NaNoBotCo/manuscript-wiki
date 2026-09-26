#!/usr/bin/env python3
"""add_core_english — English for the core sense of every head that lacked it.

WHY THIS IS COMPOUND WORK, NOT GLOSS WORK
A compound's literal reading is composed from its parts, and 4,940 compounds
could not get one in English because a part had no English gloss. The blockers
were not obscure words: they were this lexicon's own heads. ใจ alone blocked 258
compounds, ตัว 164, พระ 71. One good gloss on each head's core sense unblocks
them all at once, which is why these were written by hand rather than left to
the queue.

They are editorial renderings of the RID's Thai, so they carry conf "standard"
with src RID + CUR — not "verified", which would claim a source said it in
English, and none did.

    python3 scripts/add_core_english.py --write
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

LEX = Path(__file__).resolve().parent.parent / "data" / "lexicon"

# th -> (sense number, English glosses nearest-first)
G = {
 "กก": (1, ["the -k final spelling class (แม่กก)"]), "กล": (1, ["trick", "deception", "stratagem"]),
 "กา": (1, ["crow"]), "กาม": (1, ["desire", "sensual desire"]), "กาย": (1, ["body"]),
 "การระ": (1, ["nominalisation of ระ"]), "การลง": (1, ["nominalisation of ลง"]),
 "กำ": (1, ["to close the hand", "to make a fist"]), "กิจ": (1, ["business", "affair", "duty"]),
 "กุด": (1, ["to cut short", "to lop"]), "ขวัญ": (3, ["khwan", "the life-essence", "soul-stuff"]),
 "ขัน": (1, ["bowl", "water bowl", "dipper"]), "คลอง": (1, ["canal", "waterway"]),
 "คา": (1, ["cangue", "wooden neck-yoke"]), "จร": (3, ["to go", "to wander", "to travel"]),
 "ชะ": (1, ["to rinse", "to wash off"]), "ชัย": (1, ["victory"]), "ชาติ": (1, ["birth"]),
 "ชีพ": (1, ["life"]), "ดง": (1, ["deep forest", "jungle"]), "ตรา": (1, ["seal", "emblem", "stamp"]),
 "ตรี": (1, ["fish"]), "ตัว": (1, ["form", "body", "physical shape"]), "ตีน": (1, ["foot"]),
 "ต้น": (1, ["trunk", "plant", "stem"]), "ทรง": (1, ["form", "shape"]), "ทอง": (1, ["gold"]),
 "ทับ": (1, ["hut", "temporary shelter"]), "ทัพ": (1, ["army", "troops"]),
 "ที": (1, ["time", "occasion", "turn"]), "ทุกข์": (1, ["suffering", "hardship", "dukkha"]),
 "ทุ่ง": (1, ["open field", "plain"]), "ท่า": (1, ["landing", "riverside landing", "pier"]),
 "นอก": (1, ["outside", "outer"]), "นะ": (1, ["the sentence particle na"]), "นาม": (1, ["name"]),
 "บัง": (1, ["to screen", "to shield", "to hide"]), "บัว": (1, ["lotus"]),
 "บาล": (2, ["to guard", "to protect", "to keep"]), "บุญ": (3, ["merit", "goodness"]),
 "บุรี": (1, ["town", "city"]), "บ่อ": (1, ["well", "pit", "pond"]), "ผี": (1, ["spirit", "ghost"]),
 "พระ": (8, ["the honorific prefix phra", "sacred", "venerable"]),
 "พล": (1, ["strength", "force"]), "พิษ": (1, ["harm", "toxicity"]),
 "พุทธ": (1, ["the awakened one", "buddha"]), "ฟ้า": (1, ["sky"]),
 "ภัณฑ์": (1, ["goods", "articles", "wares"]), "ภู": (1, ["earth", "land"]),
 "ภูมิ": (1, ["land", "ground"]), "มั่น": (2, ["firm", "fixed", "immovable"]),
 "มูล": (1, ["base", "root", "foot"]), "ม่วง": (1, ["purple"]), "ยก": (1, ["to lift", "to raise"]),
 "รม": (1, ["to smoke", "to fumigate"]), "รา": (1, ["joist", "supporting timber"]),
 "ราช": (1, ["king"]), "รี": (1, ["oval", "tapering"]),
 "ละ": (1, ["to leave", "to let go", "to quit"]), "ลับ": (1, ["to whet", "to sharpen"]),
 "ลาน": (1, ["open ground", "yard", "court"]), "ลี": (1, ["to go"]),
 "วน": (1, ["to circle", "to go round"]), "วา": (2, ["to spread the arms"]),
 "วาร": (1, ["day", "day of the week"]), "วิทยา": (1, ["knowledge", "science"]),
 "วี": (1, ["to fan", "to wave"]), "ว่า": (1, ["to say", "to tell"]), "ศก": (1, ["hair"]),
 "ศรี": (1, ["splendour", "auspiciousness", "glory"]), "สถาน": (1, ["place", "site"]),
 "สัก": (1, ["teak"]), "สัน": (1, ["ridge", "crest"]),
 "สำ": (1, ["jumbled", "tangled", "out of order"]), "สิทธิ์": (1, ["right", "rightful power"]),
 "สิน": (1, ["wealth", "money", "property"]),
 "สิ้น": (1, ["to be exhausted", "to end", "to run out"]),
 "สุข": (1, ["happiness", "ease", "wellbeing"]),
 "หมอ": (1, ["one who knows", "expert", "adept"]), "หมาก": (1, ["areca palm", "betel nut"]),
 "หลวง": (1, ["royal", "of the crown"]), "ห้วย": (1, ["stream pool", "mountain stream"]),
 "อก": (1, ["chest", "breast"]), "อง": (1, ["the Vietnamese royal prefix ong"]),
 "อด": (1, ["to restrain", "to hold back"]),
 "อา": (1, ["father's younger sibling", "uncle", "aunt"]),
 "เก": (1, ["out of line", "crooked", "askew"]), "เกิน": (1, ["to exceed", "beyond", "over"]),
 "เชิง": (1, ["foot", "base", "footing"]), "เรือน": (1, ["house", "dwelling"]),
 "เส": (1, ["to swerve", "to veer"]), "เห": (1, ["to swerve", "to turn aside"]),
 "เอก": (1, ["one", "first"]), "แก": (1, ["house crow"]),
 "แกง": (1, ["curry", "a soup-like dish"]),
 "แก้": (1, ["cowrie shell used to burnish cloth"]), "แดง": (1, ["red"]),
 "แนว": (1, ["row", "line", "range"]), "โค": (1, ["cow", "ox"]),
 "โคก": (1, ["mound", "low rise"]), "โท": (1, ["two", "second"]),
 "โทษ": (1, ["badness", "fault"]), "โนน": (1, ["mound", "rise"]),
 "โป่ง": (1, ["swollen", "puffed with air"]), "โพธิ์": (1, ["enlightenment", "bodhi"]),
 "โรง": (1, ["shed", "hall", "roofed building"]), "โอ": (1, ["pomelo"]),
 "ใจ": (2, ["heart", "the physical heart"]), "ใบ": (1, ["leaf"]),
 "ไข": (1, ["fat", "wax", "tallow"]), "ไผ่": (1, ["bamboo"]),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    n = miss = 0
    seen = set()
    for f in sorted((LEX / "entries").glob("*.json")):
        d = json.loads(f.read_text("utf-8"))
        spec = G.get(d["th"])
        if not spec:
            continue
        seen.add(d["th"])
        sn, en = spec
        for s in d["senses"]:
            if s["n"] != sn:
                continue
            s["gloss"]["en"] = en
            s["gloss"]["conf"] = "standard"
            s["gloss"]["src"] = sorted(set((s["gloss"].get("src") or []) + ["RID", "CUR"]))
            n += 1
            if a.write:
                f.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", "utf-8")
            break
        else:
            miss += 1
            print(f"  ! {d['th']}: no sense {sn}")
    print(f"core English glosses written: {n}"
          + (f" ({miss} sense-number mismatches)" if miss else ""))
    absent = set(G) - seen
    if absent:
        print(f"  ! not found as entries: {sorted(absent)}")
    if not a.write:
        print("(dry run — pass --write)")


if __name__ == "__main__":
    main()
