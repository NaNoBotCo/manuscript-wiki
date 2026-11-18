#!/usr/bin/env python3
"""Writes hotrai/texts/patimokkha.md, the bhikkhu Pātimokkha, from two fetched files.

    python3 -I hotrai/patimokkha_build.py <pm.json> <navakovada.json>

pm.json         https://suttacentral.net/api/bilarasuttas/pli-tv-bu-pm/brahmali?lang=en
navakovada.json https://th.wikisource.org/w/api.php?action=parse&prop=wikitext&format=json
                &page=นวโกวาท/วินัยบัญญัติ

Pali and English come segment by segment from SuttaCentral. After each rule goes the
same rule from นวโกวาท, matched by class and position; the counts must come out
4 · 13 · 2 · 30 · 92 · 4 · 75 · 7 or the script stops.
"""

import json
import re
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent / "texts" / "patimokkha.md"
TH_DIGITS = str.maketrans("0123456789", "๐๑๒๓๔๕๖๗๘๙")

# SuttaCentral heading prefix → (Navakovāda section heads, in order; Thai class name)
CLASSES = {
    "Pārājika": (["ปาราชิก ๔"], "ปาราชิก", 4),
    "Saṅghādisesa": (["สังฆาทิเสส ๑๓"], "สังฆาทิเสส", 13),
    "Aniyata": (["อนิยต ๒"], "อนิยต", 2),
    "Nissaggiya Pācittiya": (["จีวรวรรค", "โกสิยวรรค", "ปัตตวรรค"], "นิสสัคคิยปาจิตตีย์", 30),
    "Pācittiya": (["มุสาวาทวรรค", "ภูตคามวรรค", "โอวาทวรรค", "โภชนวรรค", "อเจลกวรรค",
                   "สุราปานวรรค", "สัปปวณวรรค", "สหธรรมิกวรรค", "รตนวรรค"], "ปาจิตตีย์", 92),
    "Pāṭidesanīya": (["ปาฏิเทสนียะ ๔"], "ปาฏิเทสนียะ", 4),
    "Sekhiya": (["สารูป", "โภชนปฏิสังยุต", "ธัมมเทสนาปฏิสังยุต", "ปกิณณกะ"], "เสขิยวัตร", 75),
    "Adhikaraṇasamatha": (["อธิกรณสมถะมี ๗"], "อธิกรณสมถะ", 7),
}
RULE = re.compile(r"^(Nissaggiya Pācittiya|Pārājika|Saṅghādisesa|Aniyata|Pācittiya|"
                  r"Pāṭidesanīya|Sekhiya|Adhikaraṇasamatha)\s+(\d+)\b")
# Thai name of each recitation section, keyed by its Pali heading
SECTION_TH = {
    "Nidānuddeso": "นิทานุทเทส",
    "Pārājikuddeso": "ปาราชิก ๔",
    "Saṅghādisesuddeso": "สังฆาทิเสส ๑๓",
    "Aniyatuddeso": "อนิยต ๒",
    "Nissaggiyapācittiyā": "นิสสัคคิยปาจิตตีย์ ๓๐",
    "Suddhapācittiyā": "ปาจิตตีย์ ๙๒",
    "Pāṭidesanīya": "ปาฏิเทสนียะ ๔",
    "Sekhiya": "เสขิยวัตร ๗๕",
    "Adhikaraṇasamathā": "อธิกรณสมถะ ๗",
}


def clean_th(s):
    s = re.sub(r"<sup>\[([๐-๙]+)\]</sup>", r" [\1]", s)
    s = re.sub(r"</?small>", "", s)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)
    s = s.replace("'''", "").replace("''", "")
    return re.sub(r"\s+", " ", s).strip()


def navakovada(path):
    """{section head: [(item, [notes])]} plus the opening paragraphs."""
    w = json.loads(Path(path).read_text(encoding="utf-8"))["parse"]["wikitext"]["*"]
    parts = re.split(r"^(==+[^=]+==+)\s*$", w, flags=re.M)
    sections, opening, head = {}, [], None
    for part in parts:
        if part.startswith("=="):
            head = clean_th(part.strip("= "))
            sections[head] = []
            continue
        for line in (x.strip() for x in part.split("\n")):
            if not line or line.startswith(("{{", "|", "}}", "[[หมวดหมู่", "----")):
                continue
            if head and head.startswith("อนุศาสน์"):
                opening.append(clean_th(line))
            elif re.match(r"^[๐-๙]+\.?\s", line):
                sections[head].append([clean_th(line), []])
            elif line.startswith("<small>") and sections.get(head):
                # the chapter's footnotes, each placed under the rule that cites it
                for n, note in re.findall(r"([๐-๙]+)\.\s*([^๐-๙<]+)", line):
                    for item in sections[head]:
                        if f"[{n}]" in item[0]:
                            item[1].append(f"[{n}] {clean_th(note)}")
    return sections, opening


def thai_rules(sections):
    """{class: [(label, text, notes)]} in recitation order, numbered across the class."""
    out = {}
    for cls, (heads, th_name, count) in CLASSES.items():
        rows = []
        for h in heads:
            key = next((k for k in sections if k.startswith(h)), None)
            if key is None:
                sys.exit(f"นวโกวาท: no section starting {h!r}")
            sub = ""
            if len(heads) > 1:
                sub = re.sub(r"\s*มี\s.*$", "", key).replace("วรรคที ", "วรรคที่ ")
            for text, notes in sections[key]:
                if not sub:
                    text = re.sub(r"^[๐-๙]+\.?\s+", "", text)
                rows.append((sub, text, notes))
        if len(rows) != count:
            sys.exit(f"นวโกวาท {th_name}: {len(rows)} rules, expected {count}")
        out[cls] = [(f"{th_name} {str(n).translate(TH_DIGITS)}" + (f" · {sub}" if sub else ""),
                     text, notes) for n, (sub, text, notes) in enumerate(rows, 1)]
    return out


def build(pm_path, nk_path):
    d = json.loads(Path(pm_path).read_text(encoding="utf-8"))
    keys, root, en, html = d["keys_order"], d["root_text"], d["translation_text"], d["html_text"]
    sections, opening = navakovada(nk_path)
    th = thai_rules(sections)
    used = {cls: 0 for cls in CLASSES}

    start = next(i for i, p in enumerate(opening) if p.startswith("โทษที่เกิด"))
    lines = [
        "# ภิกขุปาติโมกข์ · The Monks' Rules — Bhikkhu Pātimokkha",
        "",
        "The Pātimokkha (ปาติโมกข์) is the code of training rules of a bhikkhu (ภิกษุ, a fully ordained Theravāda monk). Monks recite it together every fortnight, on the observance day (uposatha, วันอุโบสถ). This is the whole of it, in the order it is recited: 4 rules on expulsion, 13 on suspension, 2 undetermined, 30 on relinquishment and confession, 92 on confession, 4 on acknowledgement, 75 of training, and 7 for settling legal issues — 227.",
        "",
        "Pali first, then the English of the same segment. After each rule, the same rule in Thai from นวโกวาท (Navakovāda, \"instruction for the newly ordained\"), the handbook of monastic discipline written by สมเด็จพระมหาสมณเจ้า กรมพระยาวชิรญาณวโรรส, Supreme Patriarch of Thailand, who died in 1921.",
        "",
        "## นวโกวาท · วินัยบัญญัติ",
        "",
    ]
    lines += [f"    {p}\n" for p in opening[start:]]

    pending = None

    def flush():
        nonlocal pending
        if pending:
            label, text, notes = pending
            lines.append(f"    นวโกวาท {label} — {text}")
            lines.extend(f"    {n}" for n in notes)
            lines.append("")
        pending = None

    for k in keys:
        r, e, h = root.get(k, "").strip(), en.get(k, "").strip(), html.get(k, "")
        if not r and not e:
            continue
        if "<h1" in h or k.endswith(":0.1"):
            continue
        if "<hr" in h:
            flush()
        m = re.search(r"<h([2-4])", h)
        if m:
            flush()
            level = "##" if m.group(1) == "2" else "###"
            title = f"{r} · {e}" if e else r
            if level == "##" and r in SECTION_TH:
                title += f" · {SECTION_TH[r]}"
            lines += [f"{level} {title}", ""]
            rm = RULE.match(r)
            if rm:
                cls = rm.group(1)
                n = int(rm.group(2))
                if n != used[cls] + 1:
                    sys.exit(f"{k}: {cls} {n} out of order")
                used[cls] = n
                pending = th[cls][n - 1]
            continue
        lines += [f"    {r}", f"    {e}", ""]
    flush()

    for cls, (_, th_name, count) in CLASSES.items():
        if used[cls] != count:
            sys.exit(f"SuttaCentral {cls}: {used[cls]} rules, expected {count}")
    return "\n".join(lines).rstrip() + "\n"


FRONT = """---
slug: patimokkha
title_th: ภิกขุปาติโมกข์
title_en: The Monks' Rules — Bhikkhu Pātimokkha
translit: phikkhu patimok
cabinet: traipidok
marking: tradition
licence: English translation: CC0 1.0 Universal (public domain dedication) — SuttaCentral bilara-data LICENSE.md. Thai, นวโกวาท: marked PD-Thailand on Thai Wikisource. Pali root text: see the note at the foot of this text.
source: SuttaCentral pli-tv-bu-pm — https://suttacentral.net/pli-tv-bu-pm/en/brahmali · Thai Wikisource — https://th.wikisource.org/wiki/นวโกวาท/วินัยบัญญัติ
by: Pali — Mahāsaṅgīti Tipiṭaka Buddhavasse 2500; English — Bhikkhu Brahmali; Thai — สมเด็จพระมหาสมณเจ้า กรมพระยาวชิรญาณวโรรส, นวโกวาท
summary: >
  The 227 training rules a Theravāda monk recites every fortnight, whole. Pali and English segment by segment, and each rule in Thai as นวโกวาท gives it.
---

"""

PROVENANCE = """
---

## Provenance

Fetched once from SuttaCentral (pli-tv-bu-pm), segment-aligned at the source, so each Pali line and the English beneath it are the same passage.

**English — Bhikkhu Brahmali. CC0 1.0**, a public domain dedication: the bilara-data repository's `LICENSE.md` states that all translations created in Bilara and supported by SuttaCentral are dedicated to the public domain under CC0.

**Pali — the Mahāsaṅgīti Tipiṭaka Buddhavasse 2500 edition**, prepared by the M.L. Maniratana Bunnag Dhamma Society Fund from the Vipassana Research Institute's Chaṭṭha Saṅgāyana Tipiṭaka (tipitaka.org) and published by SuttaCentral. SuttaCentral's `LICENSE.md` speaks of translations; a root text is not a translation, so it does not plainly cover the Pali. https://suttacentral.net/licensing

**Thai — นวโกวาท, ภาคที่ ๑ วินัยบัญญัติ**, by สมเด็จพระมหาสมณเจ้า กรมพระยาวชิรญาณวโรรส (1860–1921), as transcribed on Thai Wikisource from the 2513 (1970) printing, where it carries the PD-Thailand mark. นวโกวาท gives each rule in short Thai, not word for word, and numbers the rules within each วรรค (chapter); the number after the class name here counts across the class, as the Pali does. The two notes marked [๑] and [๒] are นวโกวาท's own footnotes.

The Thai recitation follows the Thai edition of the Pali (ฉบับสยามรัฐ), which differs from the Pali above in some spellings.
"""


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    body = build(sys.argv[1], sys.argv[2])
    tmp = OUT.with_suffix(".md.tmp")
    tmp.write_text(FRONT + body + PROVENANCE, encoding="utf-8")
    tmp.replace(OUT)
    print(f"wrote {OUT} — {OUT.stat().st_size:,} bytes")
