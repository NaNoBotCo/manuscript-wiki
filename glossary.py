#!/usr/bin/env python3
"""glossary — a multilingual glossary of the discovered wichaa terms.

The crawlers surface a folksonomy: the words the tradition actually uses, tagged on
manuscripts and on market listings. This turns the meaningful ones into a real
glossary — each term in Thai, romanised, and glossed in English and 中文 (Chinese),
with the *verified* count of how many manuscripts and how many listings carry it.

Multilingual by design (Singapore is a core audience): every entry is a dict of
language → gloss, so Malay (ms) and Tamil (ta) slot in later without a rewrite; the
page shows whatever languages are present. The glosses are editorial — careful, but
refinements from readers who know the tradition better are welcome. The counts are
not editorial: they are read straight from the catalogue.

    python3 glossary.py --docs ../nanobotco-lanna/docs --site-url https://wichaa.net
Writes  docs/api/glossary.json  +  docs/glossary/index.html .
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_db = HERE.parent / "manuscript-crawler" / "crawler" / "catalog.db"

# term (Thai) → {roman, domain, glosses:{lang:text}}. English is authoritative;
# Chinese is a careful editorial gloss. Domains group the glossary into desire paths.
GLOSS = {
 "ยันต์": {"roman":"yan · yantra","domain":"yantra","en":"A sacred diagram of letters, syllables and lines — drawn, inscribed or tattooed to protect, empower, or attract. The north's core visual magic.","zh":"符 · 護身法陣 — 由聖字、音節與線條構成的幾何圖，用以護身、加持或招引。"},
 "ผ้ายันต์": {"roman":"pha yant","domain":"yantra","en":"A yantra inked onto cloth — a protective banner or wearing-cloth carrying the diagram.","zh":"符布 — 繪有法陣的護身布或旗。"},
 "คาถา": {"roman":"katha","domain":"katha","en":"A Pali incantation — verses of power, recited to activate a charm, ward danger, or draw fortune.","zh":"咒語 — 巴利語的靈驗偈頌，誦唸以啟動法物、驅邪或招福。"},
 "นะ": {"roman":"na","domain":"katha","en":"The sacred syllable นะ — a seed-letter at the heart of countless katha and yantra; the tradition counts 108 of its forms.","zh":"「那」聖音字 — 眾多咒與符的種子字，傳有一百零八變化。"},
 "ตะกรุด": {"roman":"takrut","domain":"amulet","en":"A spell inscribed on a thin metal scroll, rolled tight and empowered — worn for protection, invulnerability, or love.","zh":"符管 — 刻於薄金屬並捲緊加持的經文護符，用於護身、刀槍不入或招情。"},
 "เครื่องราง": {"roman":"khrueang rang","domain":"amulet","en":"Talisman or charm, in the broad sense — any empowered object worn or carried for its power.","zh":"護身符（廣義）— 一切經加持、隨身佩帶以求靈力的物件。"},
 "พระเครื่อง": {"roman":"phra khrueang","domain":"amulet","en":"A Buddhist amulet, usually a small moulded image of a Buddha or revered monk.","zh":"佛牌 — 多為佛陀或高僧的小型模製聖像護符。"},
 "วัตถุมงคล": {"roman":"watthu mongkhon","domain":"amulet","en":"Auspicious sacred objects — the umbrella category for amulets, charms and consecrated items.","zh":"聖物 · 吉祥物 — 佛牌、護符與開光物件的總稱。"},
 "พระสมเด็จ": {"roman":"phra somdet","domain":"amulet","en":"The Somdej amulet — among the most revered Thai amulet types, the 'king of amulets.'","zh":"崇迪佛牌 — 最受尊崇的泰國佛牌之一，有『佛牌之王』之稱。"},
 "จตุคาม": {"roman":"jatukham","domain":"amulet","en":"Jatukham Ramathep — a guardian-deity amulet cult that swept Thailand in the 2000s.","zh":"加都堪拉瑪贴 — 二〇〇〇年代風靡泰國的護法神護符。"},
 "เมตตา": {"roman":"metta","domain":"attraction","en":"Loving-kindness — as a magical quality, the power to draw goodwill and warmth from all who meet you.","zh":"慈心 — 作為法門的特質，能招來眾人的善意與愛戴。"},
 "เมตตามหานิยม": {"roman":"metta mahaniyom","domain":"attraction","en":"Loving-kindness + 'great popularity' — charm that makes one widely liked and favoured.","zh":"慈心廣受愛戴 — 使人緣廣結、備受喜愛的法門。"},
 "เสน่ห์": {"roman":"saneh","domain":"attraction","en":"Love-drawing allure — charms and rites to kindle desire and attraction.","zh":"魅惑 · 招情 — 引動愛慕與情緣的法術。"},
 "สีผึ้งเสน่ห์": {"roman":"si phueng saneh","domain":"attraction","en":"Enchanted lip-wax — a balm consecrated to lend the wearer allure.","zh":"招情蜂蠟 — 開光的唇蠟，增添佩者魅力。"},
 "คงกระพัน": {"roman":"kongkraphan","domain":"power","en":"Invulnerability — the classic martial protection, skin that blades cannot cut.","zh":"刀槍不入 — 經典的護體法門，刀刃不能傷。"},
 "ฤๅษี": {"roman":"lersi · ruesi","domain":"teachers","en":"The ascetic hermit-seers — the teacher-figures at the root of the tradition, patrons of yantra, katha and healing.","zh":"修行隱士 · 仙人 — 傳統根源的祖師，符、咒與醫術的守護者。"},
 "หลวงปู่ทวด": {"roman":"luang pu thuat","domain":"teachers","en":"A revered southern monk (16th–17th c.), whose amulets are believed to protect from harm and misfortune.","zh":"龍菩托祖師 — 受尊崇的南方高僧，其佛牌被信能護身避險。"},
 "ราหู": {"roman":"rahu","domain":"astrology","en":"The eclipse-deity — the shadow-planet that swallows sun and moon; propitiated to turn misfortune to fortune.","zh":"羅睺 — 食日月的影曜之神，供奉以轉厄為福。"},
 "โหราศาสตร์": {"roman":"horasat · hora","domain":"astrology","en":"Astrology — the reckoning of time, star and fate; the diviner's science of auspicious days and birth-charts.","zh":"占星術 — 推算時辰、星曜與命運，擇吉日、排命盤之學。"},
 "ยา": {"roman":"ya","domain":"medicine","en":"Medicine — herbal remedy and the medical manuals; healing sits inside wichaa, not apart from it.","zh":"藥 · 草藥 — 醫方與醫書；療癒本屬 wichaa 之內，不與其分。"},
 "กุมารทอง": {"roman":"kuman thong","domain":"spirits","en":"The 'golden boy' — a child-spirit effigy kept and fed for luck, wealth and protection.","zh":"金童 — 供養以求財、護佑的靈童造像。"},
 "นางกวัก": {"roman":"nang kwak","domain":"spirits","en":"The beckoning lady — her raised hand calls in customers and wealth; the merchant's charm.","zh":"招財女神 — 舉手招客招財，商家的守護。"},
 "ไอ้ไข่": {"roman":"ai khai","domain":"spirits","en":"Ai Khai — the boy-spirit of Wat Chedi, famed for granting luck and answered wishes.","zh":"艾蓋童子 — 柴迪寺的靈童，以賜運、有求必應聞名。"},
 "ท้าวเวสสุวรรณ": {"roman":"thao wessuwan","domain":"deities","en":"Vaishravana — guardian king of the north, giant lord of yakṣas, who wards off ghosts and evil.","zh":"多聞天王（毗沙門）— 北方護法天王，夜叉之主，驅鬼辟邪。"},
 "ปลัดขิก": {"roman":"palad khik","domain":"material","en":"A phallic amulet — carved for protection, virility and warding of harm.","zh":"陽形護符 — 雕製以護身、旺陽、避害。"},
 "เขี้ยวเสือ": {"roman":"khiao suea","domain":"material","en":"Tiger fang — worn for authority, command over others and protection.","zh":"虎牙 — 佩以增威權、懾眾、護身。"},
 "พญาเต่าเรือน": {"roman":"phaya tao ruean","domain":"material","en":"The turtle amulet — for longevity and steady, sheltering wealth.","zh":"龜將軍 — 象徵長壽與穩固招財。"},
 "เบี้ยแก้": {"roman":"bia kae","domain":"material","en":"A cowrie-shell remedy charm — the classic guard against black magic and curse.","zh":"解厄寶螺 — 對治邪術與詛咒的傳統寶貝護符。"},
 "มีดหมอ": {"roman":"mit mo","domain":"ritual","en":"The ritual master's knife — for exorcism, cutting malign influence, and consecrating charms.","zh":"法師刀 — 用於驅邪、斬煞與開光法物。"},
 "น้ำมันมนต์": {"roman":"nam man mon","domain":"ritual","en":"Enchanted oil — consecrated for love, luck or persuasion, anointed on skin or object.","zh":"法油 · 咒油 — 為招情、招運或說服而開光，塗於身或物。"},
 "ผงพุทธคุณ": {"roman":"phong phutthakhun","domain":"ritual","en":"Sacred powder of Buddha-virtue — ground from consecrated materials and pressed into amulets.","zh":"佛粉（聖粉）— 由開光材料研磨，壓入佛牌之中。"},
 "ชานหมาก": {"roman":"chan mak","domain":"ritual","en":"Chewed betel-quid — spat and worked into folk blessing, healing and love magic.","zh":"檳榔渣 — 用於民間祝福、療癒與情術。"},
 "กะลาตาเดียว": {"roman":"kala ta diao","domain":"material","en":"A rare one-eyed coconut shell — a single natural sprout-hole makes it a powerful protective charm.","zh":"獨眼椰殼 — 天然僅一芽孔的稀有椰殼，為強力護符。"},
}

DOMAIN_LABEL = {
 "yantra":"Yantra — sacred diagrams","katha":"Katha — spells & sacred sound",
 "amulet":"Amulets","attraction":"Love & attraction","power":"Powers of the body",
 "teachers":"Teachers & lineage","astrology":"Astrology & fate","medicine":"Medicine",
 "spirits":"Spirits & effigies","deities":"Deities & guardians","material":"Materials & bodies",
 "ritual":"Ritual craft",
}
LANGS = [("en","English"),("zh","中文"),("th","ไทย")]


def counts(conn):
    out = {}
    for r in conn.execute(
        "SELECT term_raw, COUNT(DISTINCT manuscript_id) ms, COUNT(DISTINCT item_id) mkt "
        "FROM tags GROUP BY term_raw"):
        out[r["term_raw"]] = (r["ms"] or 0, r["mkt"] or 0)
    return out


def build_data(db: Path):
    conn = sqlite3.connect(str(db)); conn.row_factory = sqlite3.Row
    try:
        c = counts(conn)
    finally:
        conn.close()
    entries = []
    for th, g in GLOSS.items():
        ms, mkt = c.get(th, (0, 0))
        gl = {"en": g["en"]}
        if g.get("zh"): gl["zh"] = g["zh"]
        gl["th"] = ""  # the headword itself is the Thai; per-lang gloss optional
        entries.append({
            "term": th, "roman": g["roman"], "domain": g["domain"],
            "domainLabel": DOMAIN_LABEL.get(g["domain"], g["domain"]),
            "glosses": gl, "manuscripts": ms, "listings": mkt,
        })
    entries.sort(key=lambda e: (e["domain"], -(e["manuscripts"] + e["listings"])))
    return {"kind": "glossary", "note": "Glosses are editorial (English authoritative, "
            "中文 careful); manuscript & listing counts are read from the catalogue.",
            "languages": [l[0] for l in LANGS], "count": len(entries), "entries": entries}


def render_page(data, site):
    entries_json = json.dumps(data["entries"], ensure_ascii=False)
    langs_json = json.dumps(LANGS, ensure_ascii=False)
    return PAGE.replace("{{SITE}}", site).replace("{{COUNT}}", str(data["count"]))\
        .replace("{{ENTRIES}}", entries_json).replace("{{LANGS}}", langs_json)


PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Glossary · wichaa</title>
<meta name="description" content="A multilingual glossary of Northern Thai wichaa — the terms of the tradition, in Thai, English and 中文, each with how many manuscripts and market listings carry it.">
<meta name="keywords" content="wichaa glossary, Thai amulet terms, Thai magic glossary, yantra, katha, takrut, kuman thong, metta, sak yant, Northern Thai, 泰国佛牌, 泰国法术, Chinese, multilingual">
<link rel="canonical" href="{{SITE}}/glossary/">
<meta property="og:type" content="website">
<meta property="og:title" content="Glossary — the words of wichaa · Thai · English · 中文">
<meta property="og:description" content="The tradition's own vocabulary — takrut, kuman thong, metta, rahu — glossed in Thai, English and Chinese, each with the manuscripts and market listings that carry it.">
<meta property="og:url" content="{{SITE}}/glossary/">
<meta property="og:image" content="{{SITE}}/og.jpg">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{{SITE}}/og.jpg">
<style>
 :root{--bg:#f4efe3;--panel:#fdfbf5;--ink:#26302a;--muted:#6d6455;--gold:#a8791e;
  --gold-soft:#c9a24a;--crimson:#8c3b2e;--line:#e5dcc7;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
  font-family:var(--sans);font-size:18px;line-height:1.6}
 a{color:var(--crimson);text-decoration:none}a:hover{text-decoration:underline}
 .wrap{max-width:1000px;margin:0 auto;padding:0 24px}
 header{text-align:center;padding:52px 24px 20px}
 .mark{font-family:var(--serif);letter-spacing:.4em;color:var(--gold);font-size:13px}
 h1{font-family:var(--serif);font-size:clamp(30px,5vw,46px);margin:14px 0 8px}
 .sub{color:#3c463f;font-family:var(--serif);font-style:italic;font-size:20px;max-width:640px;margin:0 auto}
 .controls{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);
  padding:16px 0;z-index:5;margin-top:22px}
 .controls .wrap{display:flex;gap:14px;flex-wrap:wrap;align-items:center;justify-content:center}
 #q{flex:1 1 260px;max-width:420px;padding:11px 16px;border:1.5px solid var(--line);
  border-radius:999px;font-size:16px;background:var(--panel);color:var(--ink)}
 .lang{display:flex;gap:6px}
 .lang button{padding:8px 15px;border:1.5px solid var(--gold);background:transparent;
  color:var(--ink);border-radius:999px;font-size:15px;font-weight:600;cursor:pointer}
 .lang button.on{background:var(--ink);color:#f6f1e4;border-color:var(--ink)}
 h2.dom{font-family:var(--serif);font-size:23px;color:var(--gold);
  border-bottom:1px solid var(--line);padding-bottom:8px;margin:38px 0 4px}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;margin-top:16px}
 .card{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:18px 20px}
 .card .th{font-family:var(--serif);font-size:26px;color:var(--ink);line-height:1.2}
 .card .rm{color:var(--gold);font-size:15px;font-style:italic;margin-bottom:8px}
 .card .gl{font-size:16px;color:#3c473f;line-height:1.55}
 .card .cnt{margin-top:12px;font-size:13.5px;color:var(--muted);display:flex;gap:14px;flex-wrap:wrap}
 .card .cnt a{color:var(--muted)}.card .cnt b{color:var(--ink)}
 footer{border-top:1px solid var(--line);margin-top:50px;padding:30px 0 60px;text-align:center;
  color:var(--muted);font-size:15px}
 .empty{text-align:center;color:var(--muted);padding:40px}
</style></head><body>
<header><div class="mark">wichaa · วิชา</div>
 <h1>Glossary</h1>
 <p class="sub">The words the tradition actually uses — in Thai, English and 中文 — each
   with how many manuscripts and how many market listings carry it.</p>
 <p style="margin-top:14px"><a href="/">← wichaa.net</a></p></header>
<div class="controls"><div class="wrap">
  <input id="q" type="search" placeholder="Search a term, meaning, or sound…">
  <div class="lang" id="lang"></div>
</div></div>
<main class="wrap" id="main"></main>
<footer><div class="wrap">
  Glosses are editorial — English authoritative, 中文 a careful reading; refinements welcome.
  Counts come straight from the catalogue. Malay &amp; Tamil to follow.<br>
  Open under <a href="/LICENSE">CC-BY 4.0</a> · <a href="/api/glossary.json">glossary.json</a>
</div></footer>
<script>
var ENTRIES={{ENTRIES}}, LANGS={{LANGS}}, SITE="{{SITE}}", lang="en";
function esc(s){var d=document.createElement('div');d.textContent=s||'';return d.innerHTML;}
function gloss(e){return e.glosses[lang]||e.glosses.en||'';}
function draw(){
 var q=(document.getElementById('q').value||'').toLowerCase().trim();
 var list=ENTRIES.filter(function(e){
   if(!q)return true;
   return (e.term+' '+e.roman+' '+e.glosses.en+' '+(e.glosses.zh||'')).toLowerCase().indexOf(q)>=0;
 });
 var main=document.getElementById('main');
 if(!list.length){main.innerHTML='<p class="empty">No term matches that.</p>';return;}
 var html='', dom=null;
 list.forEach(function(e){
   if(e.domain!==dom){
     if(dom!==null)html+='</div>';   // close the PREVIOUS domain's grid before opening the next
     dom=e.domain;html+='<h2 class="dom">'+esc(e.domainLabel)+'</h2><div class="grid">';
   }
   var links=[];
   if(e.manuscripts)links.push('<a href="/browse">▦ <b>'+e.manuscripts+'</b> manuscripts</a>');
   if(e.listings)links.push('<a href="/market">◈ <b>'+e.listings+'</b> listings</a>');
   html+='<div class="card"><div class="th">'+esc(e.term)+'</div>'+
     '<div class="rm">'+esc(e.roman)+'</div>'+
     '<div class="gl">'+esc(gloss(e))+'</div>'+
     '<div class="cnt">'+(links.join('')||'<span>—</span>')+'</div></div>';
 });
 // close the final domain's grid
 main.innerHTML=html+(list.length?'</div>':'');
}
var lc=document.getElementById('lang');
LANGS.forEach(function(l){var b=document.createElement('button');b.textContent=l[1];
 if(l[0]===lang)b.className='on';b.onclick=function(){lang=l[0];
 [].forEach.call(lc.children,function(c){c.className='';});b.className='on';draw();};
 lc.appendChild(b);});
document.getElementById('q').addEventListener('input',draw);
draw();
</script></body></html>"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the multilingual wichaa glossary")
    ap.add_argument("--db", default=str(_db))
    ap.add_argument("--docs", default=str(HERE.parent / "nanobotco-lanna" / "docs"))
    ap.add_argument("--site-url", default="https://wichaa.net")
    a = ap.parse_args(argv)
    db = Path(a.db); docs = Path(a.docs)
    if not db.is_file():
        print(f"glossary: catalog.db not found at {db}", file=sys.stderr); return 1
    if not (docs / "api").is_dir():
        print(f"glossary: no built site at {docs} (run build_static.py first)", file=sys.stderr); return 1
    data = build_data(db)
    (docs / "api" / "glossary.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    gdir = docs / "glossary"; gdir.mkdir(exist_ok=True)
    (gdir / "index.html").write_text(render_page(data, a.site_url.rstrip("/")), encoding="utf-8")
    withzh = sum(1 for e in data["entries"] if e["glosses"].get("zh"))
    print(f"glossary: {data['count']} terms ({withzh} with 中文) → "
          f"api/glossary.json + glossary/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
