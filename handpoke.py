#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""handpoke — /handpoke, the Lanna leg tattoo and what the corpus says about it.

/yant indexes the named designs. This asks a different question, and it is one the
corpus can answer with a number: how often does the corpus mention สักขาลาย — the
waist-to-ankle tattoo that a Lanna man was expected to carry — at all?

The answer is once. That page (ms6968 p.20) is quoted here in Thai and in English,
because it is the only emic account of the custom on the disk, and because every other
source for the same custom was written by a British administrator.

Self-contained, like glossary.py, na_gallery.py and yant_index.py: reads catalog.db,
counts, renders its own HTML. Declared in routes.py with built_by="handpoke.py".

    python3 handpoke.py --docs ../nanobotco-lanna/docs --site-url https://wichaa.net

Writes  docs/handpoke/corpus/index.html  +  docs/api/handpoke.json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = Path(os.environ.get("CATALOG_DB") or (HERE.parent / "manuscript-crawler" / "crawler" / "catalog.db"))
# The full site moved to wichaa on Nan's call, 2026-09-21; the GitHub copy is
# redirect stubs now. This page is the corpus count beside it, at /handpoke/corpus.
SITE = "https://wichaa.net/handpoke/"

# the word, the transliteration, and what it means — the words a page could use
TERMS = [
    ("สัก", "sak", "to prick — and the everyday word for “about”, so this is an upper bound"),
    ("สักยันต์", "sak yant", "to tattoo a yantra"),
    ("การสัก", "kan sak", "tattooing, as a noun"),
    ("สักขาลาย", "sak kha lai", "to tattoo the legs in patterns — the Lanna leg tattoo"),
    ("ขาลาย", "kha lai", "patterned legs"),
    ("พุงดำ", "phung dam", "black belly — the outsider’s name for the tattooed northerner"),
    ("รอยสัก", "roi sak", "a tattoo, as a mark"),
    ("ช่างสัก", "chang sak", "a tattooist"),
    ("เหล็กจาร", "lek chan", "the iron stylus — the palm-leaf pen"),
    ("ขันตั้ง", "khan tang", "the teacher’s fee, in the Lanna word"),
    ("ชาด", "chat", "vermilion"),
    ("เขม่า", "khamao", "soot"),
]

PASSAGE_TH = (
    "ปรากฏภาพจิตรกรรมฝาผนังในวัดสำคัญต่างๆ มากมาย แสดงให้เห็นว่าชายชาวล้านนานั้นนิยมที่จะสักยันต์ลงบนร่างกาย"
    "จนดูเหมือนนุ่งกางเกงสีดำหรือเสื้อผ้าทั้งตัว ผู้เฒ่าผู้แก่บางคนเล่าว่า ในสมัยโบราณสักขาลายตั้งแต่บั้นเอวเรื่อยลงมา"
    "จนถึงข้อเท้า สักตามลำตัวทั้งด้านหน้าและด้านหลัง สักตามแขนหรือแม้แต่นิ้วมือ ทั้งนี้บางคนสักไปจนถึงคอและส่วนบนหัว "
    "ซึ่งความนิยมการสักเช่นนี้พบมากในกลุ่มชาวพม่าและชาวไทยใหญ่ ซึ่งก็มีการสักยันต์ลงบนร่างกายไม่น้อยไปกว่าชาวล้านนา"
)
PASSAGE_EN = (
    "Many murals in important temples show that Lanna men favoured tattooing yantras over "
    "their bodies until it looked as if they wore black trousers or a full suit of clothes. "
    "Some elders relate that in old times they tattooed the legs in patterns from the waist "
    "down to the ankles, the torso front and back, the arms, even the fingers; some tattooed "
    "up to the neck and the crown of the head. This fashion was widespread among the Burmese "
    "and the Tai Yai, who tattoo yantras no less than the Lanna."
)
SHAME_TH = (
    "ด้วยเหตุว่าชายใดไม่สักขาและลำตัวก็จะถูกนินทาว่าเป็นผู้หญิงที่ไม่มีน้ำอดน้ำทน… "
    "ถ้าไม่มีรอยสักเลยก็ให้ไปนุ่งผ้าซิ่นเหมือนดังผู้หญิงเสีย"
)
SHAME_EN = (
    "Any man who did not tattoo his legs and torso would be gossiped about as being like a "
    "woman, lacking the endurance… if he had no tattoos, he might as well wear a sarong."
)

SOURCES = [
    ("Upper Burma", "1882", "Shway Yoe (Sir James George Scott), The Burman: His Life and Notions",
     "Nearly all Bamar men were tattooed at boyhood, from the waist to the knees — the effect "
     "“not so much of a marking of the cuticle as of a skin-tight pair of caleçons”.",
     "https://archive.org/details/burmanhislifenot00scot"),
    ("The Shan States", "1910", "Leslie Milne, Shans at Home",
     "“A Shan boy is considered to have reached manhood when he has been tattooed… the rule "
     "is to tattoo both legs from waist to knee.”",
     "https://archive.org/details/shansathomewitht00miln"),
    ("Lanna", "—", "A contributed volume in this corpus, item 6968, page 20",
     "“…until it looked as if they wore black trousers… from the waist down to the ankles.”",
     ""),
    ("Siam", "1910", "Leslie Milne, Shans at Home",
     "“The Siamese, who are so closely related to them, tattoo themselves very slightly, or "
     "not at all.”",
     "https://archive.org/details/shansathomewitht00miln"),
]


def counts() -> dict:
    if not DB.exists():
        return {}
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    text = "ifnull(p.transcription,'')||ifnull(p.translation,'')"
    out = {"pages": db.execute("select count(*) from pages where ifnull(transcription,'')<>''").fetchone()[0],
           "manuscripts": db.execute("select count(*) from manuscripts").fetchone()[0], "terms": []}
    for th, rtgs, gloss in TERMS:
        n = db.execute(f"select count(*) from pages p where {text} like ?", (f"%{th}%",)).fetchone()[0]
        m = db.execute(f"select count(distinct p.manuscript_id) from pages p where {text} like ?",
                       (f"%{th}%",)).fetchone()[0]
        out["terms"].append({"th": th, "rtgs": rtgs, "gloss": gloss, "pages": n, "manuscripts": m})
    return out


def render(c: dict, site: str) -> str:
    mx = max([t["pages"] for t in c["terms"]] or [1]) or 1
    rows = "".join(
        f'<tr><td class="w">{t["th"]}</td><td class="r">{t["rtgs"]}</td>'
        f'<td class="g">{t["gloss"]}</td>'
        f'<td class="b"><span style="width:{max(1.5, 100 * t["pages"] / mx):.1f}%"></span></td>'
        f'<td class="n">{t["pages"]}</td><td class="n muted">{t["manuscripts"]}</td></tr>'
        for t in c["terms"])
    src_rows = []
    for w, y, s, q, u in SOURCES:
        cite = f'<a href="{u}" rel="noopener">{s}</a>' if u else s
        src_rows.append(f'<tr><th>{w}</th><td class="n">{y}</td><td>{q}</td>'
                        f'<td class="g">{cite}</td></tr>')
    src = "".join(src_rows)
    kha = next((t["pages"] for t in c["terms"] if t["th"] == "สักขาลาย"), 0)
    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "ScholarlyArticle",
        "name": "สักขาลาย — the Lanna leg tattoo, counted in the corpus",
        "url": f"{site}/handpoke/corpus/",
        "description": f"The waist-to-ankle tattoo a Lanna man was expected to carry, and how "
                       f"often it appears in {c['pages']:,} transcribed manuscript pages: {kha}.",
        "isBasedOn": SITE,
    }, ensure_ascii=False)
    return PAGE.replace("{{SITE}}", site).replace("{{JSONLD}}", jsonld) \
        .replace("{{ROWS}}", rows).replace("{{SRC}}", src) \
        .replace("{{PAGES}}", f"{c['pages']:,}").replace("{{MSS}}", f"{c['manuscripts']:,}") \
        .replace("{{KHA}}", str(kha)).replace("{{HP}}", SITE) \
        .replace("{{PASSAGE_TH}}", PASSAGE_TH).replace("{{PASSAGE_EN}}", PASSAGE_EN) \
        .replace("{{SHAME_TH}}", SHAME_TH).replace("{{SHAME_EN}}", SHAME_EN)


PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>สักขาลาย · the leg tattoo, counted · wichaa</title>
<meta name="description" content="The waist-to-ankle tattoo a Lanna man was expected to carry — quoted from the one page of this corpus that describes it, and counted against {{PAGES}} transcribed pages.">
<link rel="canonical" href="{{SITE}}/handpoke/corpus/">
<meta property="og:type" content="article">
<meta property="og:site_name" content="wichaa">
<meta property="og:title" content="สักขาลาย · the leg tattoo, counted">
<meta property="og:description" content="Lanna men tattooed from the waist to the ankles, until the murals painted it as trousers. It appears on {{KHA}} page of {{PAGES}}.">
<meta property="og:url" content="{{SITE}}/handpoke/corpus/">
<meta property="og:image" content="{{SITE}}/og.jpg">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{{JSONLD}}</script>
<style>
 :root{--bg:#f4efe3;--panel:#fdfbf5;--ink:#26302a;--muted:#6d6455;--gold:#a8791e;
  --gold-soft:#c9a24a;--crimson:#8c3b2e;--line:#e5dcc7;
  --serif:"Sukhumvit Set","Noto Serif Thai",Thonburi,"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
  --sans:"Sukhumvit Set","Noto Sans Thai",Thonburi,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
  font-family:var(--sans);font-size:18px;line-height:1.65}
 a{color:var(--crimson)}
 .wrap{max-width:900px;margin:0 auto;padding:0 24px}
 header{text-align:center;padding:52px 24px 12px}
 .mark{font-family:var(--serif);letter-spacing:.4em;color:var(--gold);font-size:13px}
 h1{font-family:var(--serif);font-size:clamp(30px,5vw,46px);margin:14px 0 6px;line-height:1.15}
 h1 small{display:block;font-size:.5em;color:var(--muted);font-style:italic;margin-top:8px}
 .sub{color:#3c463f;font-family:var(--serif);font-style:italic;font-size:19px;max-width:680px;margin:10px auto 0}
 h2{font-family:var(--serif);font-size:26px;margin:44px 0 10px}
 .big{display:flex;gap:18px;flex-wrap:wrap;margin:26px 0 8px;justify-content:center}
 .big div{background:var(--panel);border:1px solid var(--line);border-radius:14px;
  padding:16px 22px;min-width:150px;text-align:center}
 .big b{display:block;font-family:var(--serif);font-size:34px;color:var(--gold);line-height:1.1}
 .big span{font-size:13px;color:var(--muted)}
 table{width:100%;border-collapse:collapse;margin:16px 0;font-size:15.5px;background:var(--panel)}
 th,td{border-bottom:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
 th{font-weight:600;color:var(--muted);font-size:13.5px}
 td.w{font-family:var(--serif);font-size:19px;white-space:nowrap}
 td.r{font-style:italic;color:var(--muted);white-space:nowrap}
 td.g{font-size:14px;color:var(--muted)}
 td.n{font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
 td.b{width:34%;min-width:110px}
 td.b span{display:block;height:11px;background:var(--gold-soft);border-radius:2px}
 blockquote{margin:18px 0;padding:18px 22px;background:var(--panel);
  border-left:4px solid var(--gold);border-radius:0 12px 12px 0}
 blockquote .th{font-family:var(--serif);font-size:20px;line-height:1.85}
 blockquote .en{margin-top:12px;color:#3c473f}
 blockquote cite{display:block;margin-top:12px;font-size:13.5px;color:var(--muted);font-style:normal}
 .note{font-size:15px;color:var(--muted);border-top:1px solid var(--line);padding-top:14px;margin-top:34px}
 .go{display:inline-block;margin:6px 8px 6px 0;padding:11px 18px;background:var(--crimson);
  color:#fdfbf5;border-radius:999px;text-decoration:none;font-size:15px}
 .go.alt{background:transparent;color:var(--crimson);border:1.5px solid var(--crimson)}
 footer{padding:40px 0 60px;text-align:center;color:var(--muted);font-size:14px}
 @media (max-width:640px){td.g{display:none}}
</style>
</head><body>
<header><div class="wrap">
 <div class="mark">WICHAA</div>
 <h1>สักขาลาย<small>the leg tattoo, and how often this corpus says so</small></h1>
 <p class="sub">A Lanna man was expected to carry a tattoo from the waist to the ankles.
 The murals paint it as trousers. In {{PAGES}} transcribed pages of manuscript here, the
 word for it appears on {{KHA}}.</p>
</div></header>
<div class="wrap">

 <div class="big">
  <div><b>{{PAGES}}</b><span>transcribed pages searched</span></div>
  <div><b>{{MSS}}</b><span>manuscripts in the corpus</span></div>
  <div><b>{{KHA}}</b><span>pages naming สักขาลาย</span></div>
 </div>

 <h2>The page that does describe it</h2>
 <blockquote>
  <div class="th">{{PASSAGE_TH}}</div>
  <div class="en">{{PASSAGE_EN}}</div>
  <cite>Item 6968, page 20 — a contributed volume in this corpus. Translation this project’s.</cite>
 </blockquote>
 <blockquote>
  <div class="th">{{SHAME_TH}}</div>
  <div class="en">{{SHAME_EN}}</div>
  <cite>Same page. The enforcement was talk, and the fee had a Lanna name of its own — ขันตั้ง.</cite>
 </blockquote>

 <h2>Counted, word by word</h2>
 <table>
  <thead><tr><th>word</th><th>said</th><th>what it means</th><th></th><th>pages</th><th>mss</th></tr></thead>
  <tbody>{{ROWS}}</tbody>
 </table>
 <p class="note">Thai is written without spaces, so a short word matches inside longer ones
 and every count here is an upper bound — สัก is also the everyday word for “about”. The
 silence is not evidence that the custom was rare: it is a fact about what manuscripts are
 for. This corpus is katha, yantra, horoscopes and recipes. A tattoo every man in the
 kingdom wore needed no instructions written down.</p>

 <h2>Four sources, side by side</h2>
 <table>
  <thead><tr><th>where</th><th>when</th><th>what it says</th><th>source</th></tr></thead>
  <tbody>{{SRC}}</tbody>
 </table>
 <p class="note">The fourth line is usually read as a fact about Thailand. It is a fact about
 <b>central</b> Thailand: Milne was comparing the Shan to Bangkok, and Lanna — a tributary
 kingdom, not a province, until 1899 — is on the other side of her comparison. The leg
 tattoo’s territory is the Tai-Buddhist upland, and its edge runs through the middle of the
 modern country.</p>

 <h2>What this is not</h2>
 <p>สักขาลาย is not สักยันต์. The same needle, a different job: the leg work covered a man,
 the yant marks him with a formula. The named yant designs of this corpus are indexed
 separately.</p>
 <p>
  <a class="go" href="{{HP}}">The whole subject, worldwide →</a>
  <a class="go alt" href="{{SITE}}/yant/">The yant designs →</a>
  <a class="go alt" href="{{SITE}}/diagrams/">The plates →</a>
 </p>
</div>
<footer>wichaa.net · <a href="{{SITE}}/">home</a> · <a href="{{SITE}}/api/handpoke.json">this page as JSON</a></footer>
</body></html>
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", required=True)
    ap.add_argument("--site-url", default="https://wichaa.net")
    a = ap.parse_args(argv)
    docs = Path(a.docs)
    if not docs.is_dir():
        raise SystemExit(f"handpoke: docs directory not found: {docs}")
    c = counts()
    if not c:
        print(f"handpoke: catalog.db not at {DB} — cannot count, page not written",
              file=sys.stderr)
        return 1
    site = a.site_url.rstrip("/")
    (docs / "handpoke" / "corpus").mkdir(parents=True, exist_ok=True)
    (docs / "handpoke" / "corpus" / "index.html").write_text(
        render(c, site), encoding="utf-8")
    (docs / "api").mkdir(parents=True, exist_ok=True)
    (docs / "api" / "handpoke.json").write_text(
        json.dumps({"corpus": {"pages_transcribed": c["pages"], "manuscripts": c["manuscripts"]},
                    "terms": c["terms"], "companion": SITE}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    kha = next((t["pages"] for t in c["terms"] if t["th"] == "สักขาลาย"), 0)
    print(f"handpoke: /handpoke/corpus written — {c['pages']:,} pages searched, สักขาลาย on {kha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
