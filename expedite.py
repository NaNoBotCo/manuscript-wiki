#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""expedite — /expedite, St. Expedite, the saint of today.

A Roman soldier holds up a cross lettered HODIE (today) and stamps on a crow
whose ribbon reads CRAS (tomorrow). The page opens on that pun, then turns the
catalogue's shrine records into lights on a globe, charts his name in five
languages' books cresting together around 1905, walks the cult from a doubled
martyrology entry to 70,000 people in Buenos Aires, and sets the devotion's
contract (ask, promise, thank in public) as two things a reader can do.

Every claim carries the reliability tag the st-expedite-wiki research gave it.
Refuted claims from that research (the XII Fulminata legion, Réunion red from
the cloak) stay out; see st-expedite-wiki/CONTENT_INVENTORY.md.

Self-contained, like kesa.py and handpoke.py: reads catalog.db for the shrine
records (items.method = 'devotion'), reads its own committed data under
data/expedite/, writes its own HTML. Declared in routes.py with
built_by="expedite.py".

    python3 expedite.py --docs ../nanobotco-lanna/docs --site-url https://wichaa.net

Writes  docs/expedite/index.html, land.json, img/*, card.png
"""
from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

import byline

HERE = Path(__file__).resolve().parent
DB = Path(os.environ.get("CATALOG_DB") or
          (HERE.parent / "manuscript-crawler" / "crawler" / "catalog.db"))
DATA = HERE / "data" / "expedite"
CARD = HERE / "publishing" / "cards" / "expedite.png"

# Images: Wikimedia Commons harvests from st-expedite-wiki/images (see its
# ATTRIBUTION.md), resized to webp masters in data/expedite/img.
# file → (English caption, Thai caption, credit, licence, source page)
IMAGES = {
    "077-holycard-devotieprent-3.webp": (
        "Sanctus Expeditus, a Dutch devotional print", "การ์ดภาพนักบุญ พิมพ์ในเนเธอร์แลนด์",
        "printer unknown", "CC0",
        "https://commons.wikimedia.org/wiki/File:Devotieprent_van_de_heilige_Expeditus_van_Melitene,_asset_r2VKThUmddtdL5VyXDgOi1ae.tif"),
    "074-holycard-1897-milan-chromolithograph.webp": (
        "Sant'Espedito Martire, from a Milan chromolithograph of 1897", "การ์ดพิมพ์สี มิลาน ค.ศ. ๑๘๙๗",
        "unknown", "Public domain",
        "https://commons.wikimedia.org/wiki/File:Sant%27Espedito_Martire.jpg"),
    "076-holycard-devotieprent-2.webp": (
        "Saint Expédit, “aujourd'hui et non demain”, Boumard et Fils", "“วันนี้ ไม่ใช่พรุ่งนี้” การ์ดฝรั่งเศส",
        "Boumard et Fils", "CC0",
        "https://commons.wikimedia.org/wiki/File:Devotieprent_van_de_heilige_Expeditus_van_Melitene,_asset_NegYf"),
    "081-print-wurzer-engraving.webp": (
        "Engraving by J.P. Wurzer: clock, crow and cross together", "ภาพแกะของ J.P. Wurzer มีทั้งนาฬิกา กา และกางเขน",
        "J.P. Wurzer · Wellcome Collection", "CC BY 4.0",
        "https://commons.wikimedia.org/wiki/File:Saint_Expiditus._Engraving_by_J.P._Wurzer._Wellcome_V0033295.jpg"),
    "068-austria-graz-jungwierth-engraving-1790.webp": (
        "Franz Xaver Jungwierth, engraving, before 1790, Graz", "ภาพแกะ กราซ ก่อน ค.ศ. ๑๗๙๐",
        "Franz Xaver Jungwierth", "Public domain",
        "https://commons.wikimedia.org/wiki/File:ContentServer-2.jpg"),
    "067-austria-graz-oil-painting-18c.webp": (
        "Oil painting, late 18th century, Diözesanmuseum Graz", "ภาพสีน้ำมัน ปลายศตวรรษที่ ๑๘ กราซ",
        "unknown", "Public domain",
        "https://commons.wikimedia.org/wiki/File:S._Expeditus.jpg"),
    "060-italy-acireale-painting-1781.webp": (
        "San Expedito, c. 1781, Gesù e Maria, Acireale", "ภาพในโบสถ์ Gesù e Maria เมืองอาชีเรอาเล ราว ค.ศ. ๑๗๘๑",
        "unknown", "Public domain",
        "https://commons.wikimedia.org/wiki/File:San_Expedito_circa_1781.jpg"),
    "061-italy-palermo-painting-ten-scenes.webp": (
        "His life in ten scenes, a Palermo painter, 19th century", "ชีวิตของท่านสิบฉาก จิตรกรปาแลร์โม ศตวรรษที่ ๑๙",
        "Wellcome Collection", "CC BY 4.0",
        "https://commons.wikimedia.org/wiki/File:Saint_Expeditus._Oil_painting_by_a_painter_of_Palermo_Wellcome_L0076176.jpg"),
    "019-reunion-petit-serre-altar-2.webp": (
        "Statues of Saint Expédit inside a red altar, Petit Serré, Réunion", "รูปปั้นในศาลแดง เปอตีแซเร เกาะเรอูนียง",
        "David Monniaux", "CC BY-SA 3.0",
        "https://commons.wikimedia.org/wiki/File:Saint_Exp%C3%A9dit_Petit_Serr%C3%A9_dsc03555.jpg"),
    "020-reunion-route-des-plaines-altar.webp": (
        "A roadside altar on the route des Plaines, Réunion", "ศาลริมถนน route des Plaines เกาะเรอูนียง",
        "David Monniaux", "CC BY-SA 3.0",
        "https://commons.wikimedia.org/wiki/File:Saint_Exp%C3%A9dit_route_des_plaines_dsc02353.jpg"),
    "018-reunion-petit-serre-altar-1.webp": (
        "An altar to Saint Expédit on the Petit Serré, Réunion", "ศาลนักบุญ เปอตีแซเร เกาะเรอูนียง",
        "David Monniaux", "CC BY-SA 3.0",
        "https://commons.wikimedia.org/wiki/File:Saint_Exp%C3%A9dit_Petit_Serr%C3%A9_dsc03553.jpg"),
    "022-new-orleans-guadalupe-chapel-statue.webp": (
        "By the door of Our Lady of Guadalupe, Rampart Street, New Orleans", "ข้างประตูโบสถ์พระแม่กวาดาลูเป นิวออร์ลีนส์",
        "Infrogmation of New Orleans", "CC BY 3.0",
        "https://commons.wikimedia.org/wiki/File:GuadalupeNOLAExpedite.jpg"),
    "023-argentina-dia-san-expedito-ba-1.webp": (
        "19 April at Balvanera parish, Buenos Aires", "๑๙ เมษายน ที่วัดบัลบาเนรา บัวโนสไอเรส",
        "Frodar", "CC BY-SA 4.0",
        "https://commons.wikimedia.org/wiki/File:D%C3%ADa_de_San_Expedito_-_Buenos_Aires_-_01.jpg"),
    "029-argentina-estatua-bermejo.webp": (
        "His statue at the Bermejo sanctuary, San Juan, Argentina, papered in thanks", "รูปปั้นที่เบร์เมโฮ อาร์เจนตินา ท่ามกลางใบขอบคุณ",
        "Daniel eduardo rosal", "CC BY 3.0",
        "https://commons.wikimedia.org/wiki/File:Estatua_de_San_Expedito_en_su_santuario_de_Bermejo,_San_Juan.jpg"),
    "079-medal-st-expedit-1.webp": (
        "Medal, “St. Expédit priez pour nous”, 1850–1949", "เหรียญ “นักบุญเอ็กซ์เปดิต โปรดภาวนาเพื่อเรา”",
        "unknown", "CC0",
        "https://commons.wikimedia.org/wiki/File:Medaille_met_H._Expeditus_en_opschrift_%27St._Exp%C3%A9dit_priez_pour_nous%27,_asset_o2fPRTMaRQcoTRGagTkqRp96.tif"),
}
IMG_SIZE = {
    "018-reunion-petit-serre-altar-1.webp": (1100, 825),
    "019-reunion-petit-serre-altar-2.webp": (825, 1100),
    "020-reunion-route-des-plaines-altar.webp": (1100, 825),
    "022-new-orleans-guadalupe-chapel-statue.webp": (534, 1100),
    "023-argentina-dia-san-expedito-ba-1.webp": (1100, 825),
    "029-argentina-estatua-bermejo.webp": (916, 769),
    "060-italy-acireale-painting-1781.webp": (630, 809),
    "061-italy-palermo-painting-ten-scenes.webp": (784, 1100),
    "067-austria-graz-oil-painting-18c.webp": (619, 1088),
    "068-austria-graz-jungwierth-engraving-1790.webp": (630, 931),
    "074-holycard-1897-milan-chromolithograph.webp": (462, 726),
    "076-holycard-devotieprent-2.webp": (500, 787),
    "077-holycard-devotieprent-3.webp": (631, 1100),
    "079-medal-st-expedit-1.webp": (926, 1100),
    "081-print-wurzer-engraving.webp": (675, 1100),
}

# Fly-to points on the globe: (label, Thai, lon, lat)
PLACES = [
    ("Buenos Aires", "บัวโนสไอเรส", -58.40, -34.61),
    ("São Paulo", "เซาเปาลู", -46.63, -23.55),
    ("New Orleans", "นิวออร์ลีนส์", -90.07, 29.96),
    ("Réunion", "เรอูนียง", 55.50, -21.12),
    ("Sicily", "ซิซิลี", 15.10, 37.60),
    ("Graz", "กราซ", 15.44, 47.07),
]

# c. 303 → today. (year, place, tag, English, Thai)
TIMELINE = [
    ("c. 303", "Melitene · Malatya, Turkey", "legend",
     "A Roman soldier, the story goes, martyred under Diocletian. His feast, 19 April, is the one fact nobody disputes.",
     "ทหารโรมันผู้ถูกประหารในยุคจักรพรรดิดิโอคลีเชียน ตามที่เล่าสืบกันมา วันฉลอง ๑๙ เมษายน เป็นข้อเดียวที่ไม่มีใครเถียง"),
    ("5th c.", "The Hieronymian Martyrology", "scholarship",
     "His name stands twice in the old list of martyrs, at Rome on 18 April and at Melitene on 19 April. Herbert Thurston called it a copyist's blunder; Hippolyte Delehaye read Expeditus as a slip for Elpidius.",
     "ชื่อของท่านอยู่ในบัญชีมรณสักขีโบราณสองแห่ง ที่โรม ๑๘ เมษายน และที่เมลิทีนี ๑๙ เมษายน นักวิชาการเห็นว่าผู้คัดลอกเขียนซ้ำ บ้างว่าชื่อเดิมคือ เอลปิดิอุส"),
    ("1600s", "Messina, then Acireale · Sicily", "documented",
     "The first church images of him that can be traced.",
     "รูปเคารพของท่านในโบสถ์ที่เก่าที่สุดเท่าที่สืบได้"),
    ("1781", "Acireale · and a Paris convent", "documented",
     "On 18 April 1781 Acireale makes him its second patron, for merchants and sailors. Same year, the legend: a crate stamped spedito, “dispatched”, reaches Paris nuns, who take the shipping word for the saint's name. The Sicilian churches are older than every version of the crate.",
     "๑๘ เมษายน ๑๗๘๑ เมืองอาชีเรอาเลยกท่านเป็นผู้อุปถัมภ์ของพ่อค้าและชาวเรือ ปีเดียวกันนั้นมีตำนานว่า ลังไม้ประทับคำว่า spedito แปลว่า “ส่งแล้ว” ไปถึงคอนแวนต์ในปารีส แม่ชีเข้าใจว่าเป็นชื่อนักบุญ แต่โบสถ์ในซิซิลีมีมาก่อนตำนานลังไม้ทุกฉบับ"),
    ("1870s–1920s", "Vienna · Graz", "documented",
     "Der eilige Heilige, “the saint in a hurry”: among the best-loved folk saints of German-speaking lands. Early German prints show him pointing at a clock.",
     "ชาวเยอรมันเรียกท่านว่า “นักบุญผู้รีบเร่ง” เป็นนักบุญที่ชาวบ้านรักมากที่สุดองค์หนึ่ง ภาพพิมพ์ยุคแรกให้ท่านชี้ไปที่นาฬิกา"),
    ("c. 1905", "Rome · Pius X", "contested",
     "Rome moves against unauthorised images and devotions. No primary decree has been found; the martyrology keeps his entry; the devotion keeps growing.",
     "วาติกันสมัยสมเด็จพระสันตะปาปาปิอุสที่ ๑๐ จัดการกับรูปเคารพที่ไม่ได้รับอนุญาต ยังไม่พบเอกสารต้นฉบับ ชื่อท่านยังอยู่ในบัญชีมรณสักขี และศรัทธาก็ยังโตต่อไป"),
    ("1918–1931", "Marseille → Réunion", "documented",
     "Fanny Fleurié, stranded in Marseille by the 1918 influenza, vows him a statue if she gets home. A bishop blesses it in Saint-Denis on 3 May 1931.",
     "ฟานี เฟลอรีเย ติดอยู่ที่มาร์เซย์ช่วงไข้หวัดใหญ่ ๑๙๑๘ บนไว้ว่าถ้าได้กลับบ้านจะถวายรูปปั้น บิชอปเสกรูปปั้นนั้นที่แซ็งเดอนี ๓ พฤษภาคม ๑๙๓๑"),
    ("1935–39", "New Orleans", "scholarship",
     "Harry Middleton Hyatt records a devotee who owes the saint flowers, and warns what happens to a house that withholds them. The pound cake comes later.",
     "แฮร์รี่ มิดเดิลตัน ไฮแอตต์ บันทึกคำของผู้ศรัทธาที่ต้องถวายดอกไม้แก่ท่าน และเล่าว่าบ้านที่ไม่ถวายจะเกิดอะไรขึ้น เค้กปอนด์มาทีหลัง"),
    ("1940s", "Santo Expedito · São Paulo state", "documented",
     "A family chapel grows into a town that carries his name.",
     "โบสถ์น้อยของครอบครัวหนึ่งเติบโตจนเป็นเมืองที่ใช้ชื่อท่าน"),
    ("19 April", "Balvanera parish · Buenos Aires", "documented",
     "About 70,000 people, queues up to twenty blocks long, waiting hours to touch his image.",
     "ผู้คนราว ๗๐,๐๐๐ คน ต่อแถวยาวถึงยี่สิบช่วงถนน รอหลายชั่วโมงเพื่อได้แตะรูปของท่าน"),
]

TAGS = {
    "documented": ("Documented", "มีบันทึก"),
    "scholarship": ("Scholarship", "งานวิชาการ"),
    "contested": ("Contested", "ยังถกเถียง"),
    "legend": ("Tradition", "ตำนาน"),
    "practitioner": ("Practitioner", "ผู้ปฏิบัติ"),
}

SOURCES = [
    ("Expeditus — Wikipedia", "https://en.wikipedia.org/wiki/Expeditus"),
    ("Kuefler, “The Convertible Saint,” Journal of Religious History 42.1 (2018)",
     "https://onlinelibrary.wiley.com/journal/14679809"),
    ("Le culte de Saint-Expédit à la Réunion — Presses universitaires de Rennes",
     "https://books.openedition.org/pur/4689?lang=fr"),
    ("Les oratoires de Saint-Expédit", "https://www.les-oratoires.asso.fr/sesc.html"),
    ("St. Expedito in South Louisiana — Louisiana Folklife Program",
     "https://www.louisianafolklife.org/lt/articles_essays/lfmexpedito.html"),
    ("Saint Expedite — readersandrootworkers.org", "https://readersandrootworkers.org/wiki/Saint_Expedite"),
    ("Santo Expedito, o santo das causas urgentes — O Município",
     "https://www.omunicipio.jor.br/wordpress/2024/04/17/expedito-o-santo-das-causas-urgentes/"),
    ("Google Books Ngram Viewer, 2019 corpora, smoothing 3", "https://books.google.com/ngrams"),
    ("Shrine and church locations — OpenStreetMap contributors (ODbL)", "https://www.openstreetmap.org/copyright"),
]


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def country(loc: str) -> str:
    c = (loc or "—").split(",")[-1].strip()
    if "Réunion" in c:
        return "Réunion"
    if c.startswith("Portugal"):
        return "Portugal"
    return c


COUNTRY_TH = {
    "Brazil": "บราซิล", "Argentina": "อาร์เจนตินา", "Réunion": "เรอูนียง", "Chile": "ชิลี",
    "Italy": "อิตาลี", "France": "ฝรั่งเศส", "United States": "สหรัฐอเมริกา", "Spain": "สเปน",
    "Portugal": "โปรตุเกส", "Nicaragua": "นิการากัว", "Bolivia": "โบลิเวีย", "Austria": "ออสเตรีย",
}


def shrines() -> list[dict]:
    if not DB.exists():
        return []
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT i.title_english, i.kind, i.location_text, i.source_url, i.raw_metadata "
            "FROM items i WHERE i.method = 'devotion' "
            "ORDER BY i.location_text, i.title_english").fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        try:
            raw = json.loads(r["raw_metadata"]) if r["raw_metadata"] else {}
        except Exception:
            raw = {}
        out.append({
            "t": r["title_english"] or "(unnamed shrine)",
            "k": r["kind"] or "shrine",
            "loc": r["location_text"] or "—",
            "c": country(r["location_text"]),
            "u": r["source_url"] or "",
            "lat": raw.get("lat"), "lon": raw.get("lon"),
            "cur": bool(raw.get("curated")),
        })
    return out


def thai_digits(s) -> str:
    return str(s).translate(str.maketrans("0123456789", "๐๑๒๓๔๕๖๗๘๙"))


def ngram_svg(ng: dict) -> str:
    """Static SVG, one row per spelling: each scaled to its own highest year,
    1860–2019, with that year marked. The 1904–1911 band runs through all rows."""
    series = ng["series"]
    y0 = 1860
    n = len(series[0]["v"])
    y1 = y0 + n - 1
    W, L, R, ROW, T = 900, 150, 70, 50, 30
    H = T + ROW * len(series) + 30
    X = lambda y: L + (y - y0) / (y1 - y0) * (W - L - R)
    cols = ["#e8b44a", "#e0533d", "#d98ab0", "#5fb3a8", "#efe6d0", "#8fa3c9"]
    p = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="ngt ngd" class="ngsvg">',
         '<title id="ngt">Printed mentions of St. Expedite by language, 1860–2019</title>',
         '<desc id="ngd">One row per spelling, each scaled to its own highest year. French peaks '
         'in 1905, Italian 1906, Spanish 1904, German 1911, English St. Expeditus 1909; the modern '
         'English spelling Saint Expedite peaks in 2011.</desc>',
         f'<rect x="{X(1904):.1f}" y="{T-6}" width="{X(1911)-X(1904):.1f}" height="{ROW*len(series)+6}" class="ngband"/>']
    for yr in range(1880, 2020, 20):
        p.append(f'<line x1="{X(yr):.1f}" x2="{X(yr):.1f}" y1="{T-6}" y2="{T+ROW*len(series)}" class="ngg"/>'
                 f'<text x="{X(yr):.1f}" y="{H-8}" class="ngx">{yr}</text>')
    for i, s in enumerate(series):
        base = T + ROW * (i + 1) - 6
        amp = ROW - 14
        pts = [(X(y0 + j), base - v * amp) for j, v in enumerate(s["v"])]
        line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        area = f"M{pts[0][0]:.1f},{base} L" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + f" L{pts[-1][0]:.1f},{base} Z"
        px = X(s["peak"])
        c = cols[i]
        p.append(f'<g class="ngrow" style="--d:{i*0.25:.2f}s">'
                 f'<path d="{area}" fill="{c}" opacity=".13"/>'
                 f'<polyline points="{line}" fill="none" stroke="{c}" stroke-width="1.6" pathLength="1" class="ngl"/>'
                 f'<line x1="{L}" x2="{W-R}" y1="{base}" y2="{base}" class="ngbase"/>'
                 f'<circle cx="{px:.1f}" cy="{base-amp:.1f}" r="4.5" fill="{c}" class="ngpk"/>'
                 f'<text x="{L-12}" y="{base-10}" class="ngn" text-anchor="end">{esc(s["native"])}</text>'
                 f'<text x="{L-12}" y="{base+3}" class="ngs" text-anchor="end">{esc(s["ngram"])}</text>'
                 f'<text x="{W-R+10}" y="{base-amp+5}" class="ngy" fill="{c}">{s["peak"]}</text></g>')
    p.append(f'<text x="{X(1907.5):.1f}" y="{T-9}" class="ng05t" text-anchor="middle">1904–1911</text>')
    p.append("</svg>")
    return "".join(p)


def figure(name: str, cls: str = "", eager: bool = False) -> str:
    en, th, who, lic, src = IMAGES[name]
    w, h = IMG_SIZE[name]
    load = "eager" if eager else "lazy"
    return (f'<figure class="{cls}"><button class="lb" data-full="img/{name}" '
            f'data-cap="{esc(en)} — {esc(who)}, {esc(lic)}" aria-label="Enlarge: {esc(en)}">'
            f'<img src="img/{name}" width="{w}" height="{h}" alt="{esc(en)}" loading="{load}" decoding="async"></button>'
            f'<figcaption><span class="thc">{esc(th)}</span>{esc(en)}'
            f' <a href="{esc(src)}" rel="noopener">{esc(who)} · {esc(lic)}</a></figcaption></figure>')


def tag(key: str) -> str:
    en, th = TAGS[key]
    return f'<span class="tag t-{key}">{en} · {th}</span>'


def render(items: list[dict], ng: dict, site: str) -> str:
    total = len(items)
    counts: dict[str, int] = {}
    for it in items:
        counts[it["c"]] = counts.get(it["c"], 0) + 1
    order = sorted(counts, key=lambda c: -counts[c])
    placed = [it for it in items if it["lat"] is not None and it["lon"] is not None]

    tl = "".join(
        f'<li class="tl-i"><div class="tl-y">{esc(y)}</div><div class="tl-b">'
        f'<div class="tl-p">{esc(p)} {tag(t)}</div><p>{esc(en)}</p><p class="th">{esc(th)}</p>'
        f'</div></li>' for y, p, t, en, th in TIMELINE)

    places = "".join(
        f'<button class="fly" data-lon="{lo}" data-lat="{la}">{esc(en)} <span>{esc(th)}</span></button>'
        for en, th, lo, la in PLACES)

    tally = "".join(
        f'<span class="ct"><b>{counts[c]}</b> {esc(c)} <i>{esc(COUNTRY_TH.get(c, ""))}</i></span>'
        for c in order)

    lists = []
    for c in order:
        rows = []
        for it in (x for x in items if x["c"] == c):
            name = (f'<a href="{esc(it["u"])}" rel="noopener">{esc(it["t"])}</a>'
                    if it["u"] else esc(it["t"]))
            cur = ' <span class="cur">✦ curated</span>' if it["cur"] else ""
            where = f' <span class="k">{esc(it["loc"])}</span>' if it["loc"] != c else ""
            rows.append(f'<li>{name}<span class="k">{esc(it["k"])}</span>{where}{cur}</li>')
        lists.append(f'<details><summary>{esc(c)} <i>{esc(COUNTRY_TH.get(c, ""))}</i> '
                     f'<b>{counts[c]}</b></summary><ul>{"".join(rows)}</ul></details>')

    gallery_names = ["074-holycard-1897-milan-chromolithograph.webp",
                     "076-holycard-devotieprent-2.webp",
                     "061-italy-palermo-painting-ten-scenes.webp",
                     "067-austria-graz-oil-painting-18c.webp",
                     "060-italy-acireale-painting-1781.webp",
                     "029-argentina-estatua-bermejo.webp",
                     "018-reunion-petit-serre-altar-1.webp",
                     "079-medal-st-expedit-1.webp"]
    gallery = "".join(figure(n) for n in gallery_names)

    src = "".join(f'<li><a href="{esc(u)}" rel="noopener">{esc(t)}</a></li>' for t, u in SOURCES)
    credits = "".join(
        f'<li>{esc(en)} — <a href="{esc(s)}" rel="noopener">{esc(who)}</a>, {esc(lic)}</li>'
        for n, (en, th, who, lic, s) in IMAGES.items())

    data = json.dumps({
        "s": [[round(it["lon"], 3), round(it["lat"], 3), it["t"], it["k"], it["loc"],
               it["u"], 1 if it["cur"] else 0] for it in placed],
    }, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    jsonld = json.dumps(byline.sign({
        "@context": "https://schema.org", "@type": "Article",
        "name": "St. Expedite — the saint of today",
        "url": f"{site}/expedite/",
        "description": ("St. Expedite, patron of urgent causes: the HODIE and CRAS pun, "
                        f"{total} shrines and churches on a globe, his name in five languages "
                        "cresting around 1905, and the cult from Melitene to Buenos Aires."),
        "inLanguage": ["en", "th"],
        "about": {"@type": "Person", "name": "Saint Expeditus",
                  "alternateName": ["St. Expedite", "Saint-Expédit", "Sant'Espedito",
                                    "San Expedito", "Santo Expedito", "นักบุญเอ็กซ์เปดิต"]},
        "image": f"{site}/expedite/card.png",
        "isPartOf": {"@type": "Dataset", "name": "wichaa", "url": f"{site}/"},
        "license": "https://creativecommons.org/licenses/by/4.0/",
    }, "expedite/"), ensure_ascii=False).replace("</", "<\\/")

    hero = IMAGES["077-holycard-devotieprent-3.webp"]
    rep = {
        "{{SITE}}": site, "{{JSONLD}}": jsonld, "{{DATA}}": data,
        "{{TOTAL}}": str(total), "{{TOTAL_TH}}": thai_digits(total),
        "{{PLACED}}": str(len(placed)),
        "{{NCOUNTRY}}": str(len(order)), "{{NCOUNTRY_TH}}": thai_digits(len(order)),
        "{{TALLY}}": tally, "{{LISTS}}": "".join(lists), "{{TIMELINE}}": tl,
        "{{PLACES}}": places, "{{NGRAM}}": ngram_svg(ng), "{{NGNOTE}}": esc(ng["note"]),
        "{{GALLERY}}": gallery, "{{SOURCES}}": src, "{{CREDITS}}": credits,
        "{{HERO_CREDIT}}": f'{esc(hero[2])} · {esc(hero[3])}', "{{HERO_SRC}}": esc(hero[4]),
        "{{F_WURZER}}": figure("081-print-wurzer-engraving.webp", "evo"),
        "{{F_GRAZ}}": figure("068-austria-graz-jungwierth-engraving-1790.webp", "evo"),
        "{{F_MILAN}}": figure("076-holycard-devotieprent-2.webp", "evo"),
        "{{F_REUNION}}": figure("019-reunion-petit-serre-altar-2.webp", "w-img"),
        "{{F_REUNION2}}": figure("020-reunion-route-des-plaines-altar.webp", "w-img"),
        "{{F_NOLA}}": figure("022-new-orleans-guadalupe-chapel-statue.webp", "w-img"),
        "{{F_BA}}": figure("023-argentina-dia-san-expedito-ba-1.webp", "w-img"),
        "{{T_DOC}}": tag("documented"), "{{T_SCH}}": tag("scholarship"),
        "{{T_CON}}": tag("contested"), "{{T_LEG}}": tag("legend"), "{{T_PRA}}": tag("practitioner"),
    }
    out = PAGE
    for k, v in rep.items():
        out = out.replace(k, v)
    return out


PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>St. Expedite · นักบุญเอ็กซ์เปดิต · wichaa</title>
<meta name="description" content="St. Expedite, patron of urgent causes: a cross lettered HODIE, a crow crying CRAS. {{TOTAL}} shrines and churches on a turning globe, his name in five languages cresting around 1905, and the cult from Melitene to Buenos Aires.">
<link rel="canonical" href="{{SITE}}/expedite/">
<meta property="og:type" content="article">
<meta property="og:site_name" content="wichaa">
<meta property="og:title" content="St. Expedite · the saint of today">
<meta property="og:description" content="HODIE over CRAS — today over tomorrow. A Roman soldier, a crow, and {{TOTAL}} lights around the world.">
<meta property="og:url" content="{{SITE}}/expedite/">
<meta property="og:image" content="{{SITE}}/expedite/card.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0b0607">
<script type="application/ld+json">{{JSONLD}}</script>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700;900&family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500&family=Noto+Serif+Thai:wght@400;600&display=swap" rel="stylesheet">
<style>
:root{--night:#0b0607;--night2:#150b0b;--ink:#f1e7d3;--muted:#b9a88e;--gold:#e3b04b;--gold2:#f6d98a;
 --red:#d0331f;--blood:#8e1409;--line:rgba(227,176,75,.22);--panel:rgba(255,236,200,.045);
 --cap:"Cinzel","Trajan Pro",Georgia,serif;
 --serif:"Cormorant Garamond","Iowan Old Style",Palatino,Georgia,serif;
 --thai:"Noto Serif Thai","Sukhumvit Set",Thonburi,serif;
 --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans Thai",sans-serif}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--night);color:var(--ink);font-family:var(--serif);font-size:20px;line-height:1.6;
 overflow-x:hidden}
a{color:var(--gold2)}
.th{font-family:var(--thai);font-size:.86em;line-height:1.9;color:#e6d7bb}
.wrap{max-width:980px;margin-left:auto;margin-right:auto;padding-left:20px;padding-right:20px}
.skip{position:absolute;left:-999px}.skip:focus{left:12px;top:12px;z-index:9;background:#000;padding:8px}
.bar{position:absolute;top:0;left:0;right:0;z-index:5;display:flex;justify-content:space-between;
 padding:14px 20px;font-family:var(--cap);font-size:13px;letter-spacing:.3em}
.bar a{color:var(--muted);text-decoration:none}.bar a:hover{color:var(--gold2)}

/* ---------- hero ---------- */
.hero{position:relative;min-height:100vh;min-height:100svh;display:flex;flex-direction:column;align-items:center;
 justify-content:center;text-align:center;padding:70px 16px 40px;overflow:hidden;
 background:radial-gradient(ellipse 70% 55% at 50% 55%,#3a0d08 0%,#1a0807 45%,var(--night) 75%)}
#embers{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.hodie{position:relative;font-family:var(--cap);font-weight:900;letter-spacing:.14em;margin:0;
 font-size:clamp(56px,min(17vw,19vh),200px);line-height:1;color:transparent;
 -webkit-text-stroke:1px rgba(227,176,75,.35);transition:color .2s}
.hodie .fill{position:absolute;inset:0;color:transparent;background:linear-gradient(180deg,#fff4cf 0%,#f6d98a 30%,#e3b04b 60%,#a4721c 100%);
 -webkit-background-clip:text;background-clip:text;opacity:0;filter:drop-shadow(0 0 22px rgba(246,190,80,.55));
 transition:opacity .35s ease-out}
.lit .hodie .fill{opacity:1}
.gloss{font-family:var(--cap);letter-spacing:.5em;font-size:13px;color:var(--muted);margin:10px 0 0;min-height:1.4em}
.stage{position:relative;margin:14px auto 0;width:clamp(150px,min(62vw,calc((100vh - 430px) * .56)),300px)}
.tk{font-family:var(--thai);letter-spacing:0;font-weight:600}
.arch{position:relative;border-radius:999px 999px 14px 14px;padding:8px;
 background:linear-gradient(180deg,#f6d98a,#a4721c 60%,#5a3a0c);box-shadow:0 0 60px rgba(208,51,31,.35),0 0 140px rgba(227,176,75,.18)}
.arch img{display:block;width:100%;height:auto;border-radius:999px 999px 8px 8px;aspect-ratio:631/1100;object-fit:cover}
.halo{position:absolute;left:50%;top:14%;width:150%;aspect-ratio:1;transform:translate(-50%,-50%);border-radius:50%;
 background:radial-gradient(circle,rgba(246,217,138,.28),rgba(246,217,138,0) 60%);animation:breathe 5s ease-in-out infinite;pointer-events:none}
@keyframes breathe{50%{opacity:.55;transform:translate(-50%,-50%) scale(1.08)}}
.crowrow{position:relative;height:120px;margin-top:-34px;display:flex;justify-content:center}
#crow{width:230px;height:120px;overflow:visible;transform-origin:50% 100%}
#crow .cras{font-family:var(--cap);font-weight:700;font-size:26px;letter-spacing:.2em;fill:#1b0a08}
#crow .ribbon{fill:#efe2c4}
#crow .ribbon-edge{fill:#bfae8a}
#crow .bird{fill:#0a0a0c}
#crow .sheen{fill:#2b3350;opacity:.55}
#crow .eye{fill:#e3b04b}
.cawing #crow .beak-top{animation:caw .5s ease-in-out 3}
@keyframes caw{50%{transform:rotate(-9deg)}}
#crow .beak-top{transform-origin:62px 58px;transform-box:view-box}
.stamped #crow{animation:squash .5s cubic-bezier(.3,1.6,.5,1) forwards}
@keyframes squash{0%{transform:scaleY(1)}35%{transform:scale(1.25,.28)}100%{transform:scale(1.18,.34);opacity:.55}}
.shake .arch{animation:stomp .45s cubic-bezier(.2,.9,.3,1)}
@keyframes stomp{30%{transform:translateY(16px)}60%{transform:translateY(-4px)}}
.letter{position:absolute;font-family:var(--cap);font-weight:700;font-size:26px;color:#efe2c4;pointer-events:none;
 text-shadow:0 0 8px rgba(0,0,0,.8)}
.ring{position:absolute;left:50%;top:50%;width:40px;height:40px;margin:-20px;border-radius:50%;border:2px solid var(--gold2);
 pointer-events:none;animation:ring 1.1s ease-out forwards}
@keyframes ring{to{transform:scale(22);opacity:0;border-width:.5px}}
.stampbtn{margin-top:14px;font-family:var(--cap);font-weight:700;font-size:15px;letter-spacing:.22em;color:#1a0806;
 background:linear-gradient(180deg,#f6d98a,#e3b04b);border:0;border-radius:999px;padding:14px 26px;cursor:pointer;
 box-shadow:0 0 0 1px rgba(255,240,200,.4) inset,0 8px 30px rgba(227,176,75,.35)}
.stampbtn:hover{filter:brightness(1.08)}.stampbtn span{font-family:var(--thai);letter-spacing:0;font-weight:600;margin-left:8px}
.stampbtn[disabled]{opacity:0;pointer-events:none;transition:opacity .4s}
.after{max-width:640px;margin:18px auto 0;opacity:0;transform:translateY(10px);transition:opacity 1s .5s,transform 1s .5s}
.lit .after{opacity:1;transform:none}
.after h1{font-family:var(--cap);font-weight:700;font-size:clamp(26px,4.4vw,40px);letter-spacing:.08em;margin:0;color:var(--ink)}
.after h1 small{display:block;font-family:var(--thai);font-weight:600;letter-spacing:0;font-size:.62em;color:var(--gold2);margin-top:6px}
.after p{margin:12px 0 0;color:#e7dac2}
.hint{font-family:var(--cap);font-size:12px;letter-spacing:.35em;color:var(--muted);margin-top:26px;opacity:.7}
.hero .credit{position:absolute;right:12px;bottom:8px;font-size:12px;color:#7d6d57;font-family:var(--sans)}
.hero .credit a{color:#8d7c63}

/* ---------- day ribbon ---------- */
.ribbon-day{border-block:1px solid var(--line);background:linear-gradient(90deg,rgba(142,20,9,.25),rgba(142,20,9,.08),rgba(142,20,9,.25));
 padding:18px 0;text-align:center}
.ribbon-day .big{font-family:var(--cap);font-size:clamp(20px,3vw,28px);letter-spacing:.06em;color:var(--gold2)}
.ribbon-day .big .th{display:block;font-size:.66em;letter-spacing:0;color:#ecd9b4}
.ribbon-day .small{font-size:16px;color:var(--muted);margin-top:6px}
.ribbon-day.feast{background:radial-gradient(ellipse at center,rgba(208,51,31,.55),rgba(142,20,9,.2))}

/* ---------- sections ---------- */
section{padding:84px 0 20px}
.kicker{font-family:var(--cap);letter-spacing:.4em;font-size:12px;color:var(--gold);margin:0 0 10px}
h2{font-family:var(--cap);font-weight:700;font-size:clamp(28px,4.6vw,46px);letter-spacing:.04em;line-height:1.15;margin:0 0 6px}
h2 .th{display:block;font-size:.5em;font-weight:600;letter-spacing:0;color:var(--gold2);margin-top:6px}
h3{font-family:var(--cap);font-size:22px;letter-spacing:.05em;margin:0 0 6px}
h3 .th{font-size:.7em;color:var(--gold2);margin-left:8px;letter-spacing:0}
.lede{font-size:22px;max-width:760px}
p.th,div.th{border-left:2px solid rgba(227,176,75,.35);padding-left:14px;max-width:760px}
.tag{display:inline-block;font-family:var(--sans);font-size:11.5px;letter-spacing:.04em;padding:2px 9px;border-radius:999px;
 vertical-align:middle;margin-left:4px;border:1px solid;white-space:nowrap}
.t-documented{color:#9fd6b0;border-color:rgba(159,214,176,.45)}
.t-scholarship{color:#a9c1ec;border-color:rgba(169,193,236,.45)}
.t-contested{color:#f0b37e;border-color:rgba(240,179,126,.5)}
.t-legend{color:#d8a7e0;border-color:rgba(216,167,224,.45)}
.t-practitioner{color:#f3d27a;border-color:rgba(243,210,122,.45)}
.tagkey{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0 0}

/* pun */
.pun{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:28px 0}
.word{border:1px solid var(--line);border-radius:18px;padding:22px;background:var(--panel);text-align:center}
.word b{display:block;font-family:var(--cap);font-weight:900;font-size:clamp(40px,8vw,72px);letter-spacing:.12em;line-height:1}
.word.h b{color:var(--gold2);text-shadow:0 0 24px rgba(246,190,80,.4)}
.word.c b{color:#6f6a66;text-decoration:line-through;text-decoration-color:var(--red);text-decoration-thickness:4px}
.word span{display:block;margin-top:8px;color:var(--muted);font-size:17px}
.evolution{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin:26px 0 0}
.evolution .step{font-family:var(--cap);font-size:13px;letter-spacing:.2em;color:var(--gold);margin:0 0 8px}

/* figures */
figure{margin:0}
figure .lb{display:block;padding:0;border:0;background:#000;cursor:zoom-in;border-radius:12px;overflow:hidden;width:100%;
 box-shadow:0 10px 40px rgba(0,0,0,.5)}
figure img{display:block;width:100%;height:auto;transition:transform .6s}
figure .lb:hover img{transform:scale(1.03)}
figcaption{font-size:14px;color:var(--muted);margin-top:8px;line-height:1.45;font-family:var(--sans)}
figcaption .thc{display:block;font-family:var(--thai);font-size:14px;color:#e6d7bb}
figcaption a{color:#8d7c63}
.evo .lb{aspect-ratio:3/4.3}.evo img{height:100%;object-fit:cover}

/* globe */
.globe-wrap{position:relative;display:grid;grid-template-columns:minmax(0,1fr);justify-items:center;margin-top:18px}
#globe{width:min(640px,94vw);aspect-ratio:1;touch-action:none;cursor:grab;display:block}
#globe:active{cursor:grabbing}
.gnote{min-height:3.4em;text-align:center;font-size:17px;margin-top:6px}
.gnote b{color:var(--gold2);font-weight:600}.gnote .k{color:var(--muted);font-size:15px}
.flies{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:10px}
.fly{font:inherit;font-size:15px;color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:999px;
 padding:6px 14px;cursor:pointer}
.fly span{font-family:var(--thai);font-size:13px;color:var(--gold2);margin-left:4px}
.fly:hover,.fly:focus-visible{border-color:var(--gold)}
.tally{display:flex;flex-wrap:wrap;gap:8px 16px;justify-content:center;margin:22px 0 0;font-size:16px;color:var(--muted)}
.tally b{color:var(--gold2);font-family:var(--cap);font-size:20px;margin-right:2px}
.tally i{font-family:var(--thai);font-style:normal;font-size:13px}
.aside{margin:24px auto 0;max-width:760px;border:1px solid rgba(208,51,31,.45);border-radius:14px;padding:14px 18px;
 background:rgba(142,20,9,.14);font-size:17px}

/* ngram */
.ngbox{border:1px solid var(--line);border-radius:18px;background:var(--panel);padding:16px 14px 12px;margin-top:22px}
.ngbox{overflow-x:auto}
.ngsvg{width:100%;min-width:640px;height:auto;display:block}
.ngg{stroke:rgba(241,231,211,.07)}.ngx{fill:#8d7c63;font:12px var(--sans);text-anchor:middle}
.ngband{fill:rgba(208,51,31,.2)}.ngbase{stroke:rgba(241,231,211,.12)}
.ng05t{fill:#f0b37e;font:12px var(--sans)}
.ngn{fill:var(--ink);font:600 14px var(--sans)}.ngs{fill:#8d7c63;font:italic 11.5px var(--sans)}
.ngy{font:700 14px var(--sans)}
.ngpk{filter:drop-shadow(0 0 6px currentColor)}
.ngl{stroke-dasharray:1;stroke-dashoffset:1}
.inview .ngl{animation:draw 2.6s ease-out forwards;animation-delay:var(--d)}
@keyframes draw{to{stroke-dashoffset:0}}

/* timeline */
.tl{list-style:none;padding:0;margin:30px 0 0;position:relative}
.tl::before{content:"";position:absolute;left:118px;top:6px;bottom:6px;width:2px;
 background:linear-gradient(180deg,rgba(227,176,75,0),var(--gold) 8%,var(--red) 92%,rgba(208,51,31,0))}
.tl-i{display:grid;grid-template-columns:100px 1fr;gap:36px;padding:0 0 30px;position:relative;
 opacity:0;transform:translateY(16px);transition:opacity .8s,transform .8s}
.tl-i.inview{opacity:1;transform:none}
.tl-i::before{content:"";position:absolute;left:112px;top:10px;width:14px;height:14px;border-radius:50%;
 background:var(--gold2);box-shadow:0 0 14px var(--gold),0 0 30px rgba(208,51,31,.6)}
.tl-y{font-family:var(--cap);font-weight:700;color:var(--gold2);text-align:right;font-size:18px;padding-top:2px}
.tl-p{font-family:var(--cap);font-size:15px;letter-spacing:.08em;color:var(--ink)}
.tl-b p{margin:6px 0 0}.tl-b p.th{margin-top:8px}

/* worlds */
.worlds{display:grid;gap:40px;margin-top:30px}
.world{display:grid;grid-template-columns:minmax(0,5fr) minmax(0,6fr);gap:28px;align-items:start}
.world:nth-child(even){grid-template-columns:minmax(0,6fr) minmax(0,5fr)}
.world:nth-child(even) .w-img{order:2}
.w-img img{max-height:520px;object-fit:cover}
.world.reunion h3{color:#ff5a3c}

/* contract */
.beats{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:28px 0}
.beat{border:1px solid var(--line);border-radius:18px;padding:20px;background:var(--panel)}
.beat b{display:block;font-family:var(--cap);font-size:40px;color:var(--gold);line-height:1}
.beat h4{font-family:var(--cap);letter-spacing:.08em;margin:8px 0 4px;font-size:18px}
.beat h4 span{font-family:var(--thai);font-size:14px;color:var(--gold2);margin-left:6px;letter-spacing:0}
.beat p{margin:0;font-size:17px;color:#e3d6bd}
.tools{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:26px;margin-top:20px}
.tool{border:1px solid var(--line);border-radius:18px;padding:20px;background:rgba(0,0,0,.25)}
.tool label{display:block;font:14px var(--sans);color:var(--muted);margin:10px 0 4px}
.tool input{width:100%;font:17px var(--sans);color:var(--ink);background:rgba(255,255,255,.05);border:1px solid var(--line);
 border-radius:10px;padding:10px 12px}
.tool input:focus{outline:2px solid var(--gold);outline-offset:1px}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:999px;overflow:hidden;margin-top:6px}
.seg button{font:14px var(--sans);color:var(--muted);background:none;border:0;padding:6px 14px;cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--gold);color:#1a0806}
#notice{width:100%;height:auto;display:block;border-radius:6px;margin-top:14px;box-shadow:0 10px 40px rgba(0,0,0,.6)}
.btn{font:600 15px var(--sans);color:#1a0806;background:var(--gold);border:0;border-radius:999px;padding:10px 18px;cursor:pointer;margin-top:12px}
.btn.ghost{background:none;color:var(--gold2);border:1px solid var(--line)}
.candles{display:grid;grid-template-columns:repeat(9,1fr);gap:6px;margin:18px 0 8px;align-items:end}
.candle{position:relative;height:120px;display:flex;flex-direction:column;align-items:center;justify-content:flex-end}
.candle .wax{width:62%;max-width:26px;height:64px;border-radius:4px 4px 2px 2px;background:linear-gradient(90deg,#8e1409,#d0331f 45%,#8e1409)}
.candle .flame{position:absolute;bottom:66px;width:14px;height:26px;border-radius:50% 50% 50% 50%/60% 60% 40% 40%;
 background:radial-gradient(ellipse at 50% 70%,#fff8d8,#f6d98a 35%,#e37b1f 70%,rgba(227,123,31,0));opacity:0;transform-origin:50% 90%}
.candle.on .flame{opacity:1;animation:flick 1.6s ease-in-out infinite alternate}
.candle.on::after{content:"";position:absolute;bottom:52px;width:70px;height:70px;border-radius:50%;
 background:radial-gradient(circle,rgba(246,190,80,.35),rgba(246,190,80,0) 70%);pointer-events:none}
.candle.today .wax{box-shadow:0 0 0 2px var(--gold2)}
.candle small{font:12px var(--sans);color:var(--muted);margin-top:6px}
@keyframes flick{0%{transform:scale(1,1) rotate(-2deg)}40%{transform:scale(.92,1.08) rotate(2deg)}100%{transform:scale(1.05,.95) rotate(-1deg)}}
.nstat{font-size:17px;min-height:2.6em}

/* offerings */
.offer{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-top:26px}
.off{text-align:center;border:1px solid var(--line);border-radius:18px;padding:18px 10px;background:var(--panel)}
.off .ic{font-size:34px;line-height:1;display:block;margin-bottom:8px;filter:saturate(1.2)}
.off b{display:block;font-family:var(--cap);font-size:15px;letter-spacing:.05em}
.off span{display:block;font-family:var(--thai);font-size:14px;color:var(--gold2)}
.off p{font-size:14.5px;color:var(--muted);margin:8px 0 0;font-family:var(--sans);line-height:1.45}

/* gallery */
.gallery{columns:4 220px;column-gap:16px;margin-top:26px}
.gallery figure{break-inside:avoid;margin:0 0 18px}

/* lists */
details{border-bottom:1px solid var(--line);padding:10px 0}
summary{cursor:pointer;font-family:var(--cap);letter-spacing:.06em;font-size:18px}
summary i{font-family:var(--thai);font-style:normal;font-size:14px;color:var(--gold2);margin-left:6px}
summary b{color:var(--gold);margin-left:8px}
details ul{list-style:none;padding:0;margin:10px 0 4px;columns:2 300px;column-gap:28px;font:15px/1.5 var(--sans)}
details li{break-inside:avoid;padding:3px 0}
details .k{color:#8d7c63;font-size:12.5px;margin-left:6px}
details .cur{color:#ff7a5c;font-size:12px;margin-left:6px}
.srcs{font:15px/1.6 var(--sans);color:var(--muted);padding-left:20px}
.srcs a{color:#d6c29a}
footer{text-align:center;padding:60px 20px 80px;color:var(--muted);font-size:16px}
footer .seal{font-family:var(--cap);font-size:28px;letter-spacing:.3em;color:var(--gold)}

/* lightbox */
#lbx{position:fixed;inset:0;z-index:20;background:rgba(5,2,2,.92);display:none;align-items:center;justify-content:center;
 flex-direction:column;padding:20px}
#lbx.open{display:flex}
#lbx img{max-width:94vw;max-height:82vh;border-radius:8px;box-shadow:0 0 80px rgba(227,176,75,.2)}
#lbx p{font:14px var(--sans);color:var(--muted);margin:12px 0 0;text-align:center;max-width:720px}
#lbx button{position:absolute;top:14px;right:16px;font:28px var(--sans);color:var(--ink);background:none;border:0;cursor:pointer}

@media (max-width:760px){
 body{font-size:18px}
 .pun,.tools{grid-template-columns:1fr}
 .evolution{grid-template-columns:repeat(3,1fr);gap:8px}
 .evolution figcaption{font-size:11.5px}
 .world,.world:nth-child(even){grid-template-columns:1fr}
 .world:nth-child(even) .w-img{order:0}
 .beats{grid-template-columns:1fr}
 .offer{grid-template-columns:repeat(2,1fr)}
 .tl::before{left:8px}
 .tl-i{grid-template-columns:1fr;gap:4px;padding-left:34px}
 .tl-i::before{left:2px}
 .tl-y{text-align:left}
 .candle{height:96px}.candle .wax{height:48px}.candle .flame{bottom:50px}.candle.on::after{bottom:36px}
}
@media (prefers-reduced-motion:reduce){
 *{animation:none!important;transition:none!important}
 .ngl{stroke-dashoffset:0}.tl-i{opacity:1;transform:none}
}
</style>
</head><body>
<a class="skip" href="#main">Skip to content</a>
<nav class="bar"><a href="/">WICHAA · <span class="tk">วิชา</span></a><a href="#shrines">SHRINES</a></nav>

<header class="hero" id="hero">
 <canvas id="embers" aria-hidden="true"></canvas>
 <p class="hodie" aria-label="HODIE — today"><span aria-hidden="true">HODIE</span><span class="fill" aria-hidden="true">HODIE</span></p>
 <p class="gloss" id="gloss">CRAS · CRAS · CRAS</p>
 <div class="stage" id="stage">
  <div class="halo"></div>
  <div class="arch"><img src="img/077-holycard-devotieprent-3.webp" width="631" height="1100" alt="St. Expedite as a Roman soldier, holding up a cross in a burst of light, a palm in his other hand" fetchpriority="high"></div>
  <div class="crowrow">
   <svg id="crow" viewBox="0 0 230 120" aria-hidden="true">
    <g class="banner">
     <path class="ribbon-edge" d="M60 60 C 95 40, 120 70, 150 52 L 214 40 L 204 56 L 220 70 L 152 78 C 122 94, 98 64, 66 72 Z"/>
     <path class="ribbon" d="M62 58 C 96 38, 120 66, 150 50 L 210 42 L 200 56 L 214 67 L 152 74 C 122 90, 98 62, 66 70 Z"/>
     <text class="cras" x="118" y="70" transform="rotate(-6 150 60)">CRAS</text>
    </g>
    <g class="bird">
     <path d="M8 96 L 44 80 L 40 92 Z"/>
     <ellipse cx="48" cy="84" rx="30" ry="18"/>
     <circle cx="62" cy="64" r="13"/>
     <path class="beak-top" d="M72 58 L 90 60 L 72 64 Z"/>
     <path d="M72 64 L 86 66 L 71 68 Z"/>
     <path d="M30 76 C 44 60, 66 70, 70 84 C 58 82, 44 84, 30 90 Z" class="sheen"/>
     <path d="M44 100 L 42 112 M 54 100 L 56 112" stroke="#0a0a0c" stroke-width="3" fill="none"/>
     <circle class="eye" cx="65" cy="61" r="2.2"/>
    </g>
   </svg>
  </div>
 </div>
 <button class="stampbtn" id="stamp">STAMP THE CROW <span>เหยียบกา</span></button>
 <div class="after">
  <h1>St. Expedite<small>นักบุญเอ็กซ์เปดิต · ผู้อุปถัมภ์เรื่องด่วน</small></h1>
  <p>The crow cries <i>cras</i>, tomorrow. The soldier holds up <i>hodie</i>, today.
  Patron of urgent causes, from a doubled line in an ancient list of martyrs to {{TOTAL}} lights around the world.</p>
  <p class="th">การ้องว่า <i>คราส</i> แปลว่าพรุ่งนี้ ทหารชูคำว่า <i>โฮดิเอ</i> แปลว่าวันนี้
  นักบุญผู้อุปถัมภ์เรื่องด่วน จากชื่อที่เขียนซ้ำในบัญชีมรณสักขีโบราณ สู่แสงเทียน {{TOTAL_TH}} ดวงทั่วโลก</p>
  <p class="hint">↓</p>
 </div>
 <p class="credit">Holy card: <a href="{{HERO_SRC}}" rel="noopener">{{HERO_CREDIT}}</a></p>
</header>

<div class="ribbon-day" id="day" aria-live="polite">
 <div class="big" id="dayBig">19 April · ๑๙ เมษายน</div>
 <div class="small" id="daySmall">His feast day. The 19th of every month is his day across Latin America.</div>
</div>

<main id="main">
<section class="wrap" id="pun">
 <p class="kicker">THE IMAGE · <span class="tk">รูปเคารพ</span></p>
 <h2>Today, not tomorrow<span class="th">วันนี้ ไม่ใช่พรุ่งนี้</span></h2>
 <p class="lede">His image explains itself. A young Roman soldier holds up a cross lettered
 HODIE. Under his foot lies a crow, and from its beak a ribbon reads CRAS, which is Latin for
 tomorrow and also the sound a crow makes. {{T_DOC}}</p>
 <p>Devotees tell why: the devil came as a crow to talk a new convert into putting off his
 baptism, <i>cras, cras</i>. He stamped on the bird and said <i>hodie</i>. {{T_LEG}}</p>
 <p class="th">รูปของท่านอธิบายตัวเองได้ ทหารโรมันหนุ่มชูไม้กางเขนที่เขียนว่า HODIE ใต้เท้ามีกา
 ปากกาคาบแถบผ้าเขียนว่า CRAS ภาษาละตินแปลว่า “พรุ่งนี้” และยังเป็นเสียงร้องของกาด้วย
 ผู้ศรัทธาเล่าว่าปีศาจแปลงเป็นกามากล่อมให้ท่านเลื่อนการรับศีลล้างบาปออกไป ท่านจึงเหยียบกาแล้วประกาศว่า วันนี้</p>
 <div class="pun">
  <div class="word h"><b>HODIE</b><span>today · วันนี้</span></div>
  <div class="word c"><b>CRAS</b><span>tomorrow · พรุ่งนี้</span></div>
 </div>
 <h3>The picture grew<span class="th">รูปค่อย ๆ เติบโต</span></h3>
 <p>Eighteenth-century German prints show him pointing at a clock or sundial, with no crow. Then
 clock and crow appear together. The HODIE cross over the CRAS crow settles in the late
 nineteenth century and travels the world on cheap colour-printed holy cards. {{T_DOC}}</p>
 <p class="th">ภาพพิมพ์เยอรมันศตวรรษที่ ๑๘ ให้ท่านชี้ไปที่นาฬิกาหรือนาฬิกาแดด ยังไม่มีกา ต่อมามีทั้งนาฬิกาและกา
 จนปลายศตวรรษที่ ๑๙ จึงลงตัวเป็นกางเขน HODIE เหนือกา CRAS แล้วแพร่ไปทั่วโลกผ่านการ์ดภาพนักบุญพิมพ์สีราคาถูก</p>
 <div class="evolution">
  <div><p class="step">I · HASTE</p>{{F_GRAZ}}</div>
  <div><p class="step">II · CLOCK + CROW</p>{{F_WURZER}}</div>
  <div><p class="step">III · HODIE</p>{{F_MILAN}}</div>
 </div>
</section>

<section class="wrap" id="lights">
 <p class="kicker">THE LIGHTS · <span class="tk">แสงเทียน</span></p>
 <h2>{{TOTAL}} lights<span class="th">แสงเทียน {{TOTAL_TH}} ดวง ใน {{NCOUNTRY_TH}} ดินแดน</span></h2>
 <p class="lede">The shrines and churches to him in this catalogue, from OpenStreetMap and a
 hand-picked list, one candle each. Drag to turn the world; tap a light for its name.</p>
 <p class="th">โบสถ์และศาลของท่านในคลังนี้ จาก OpenStreetMap และรายชื่อที่คัดมาเอง แห่งละหนึ่งดวง
 ลากเพื่อหมุนโลก แตะแสงเทียนเพื่อดูชื่อ</p>
 <div class="globe-wrap">
  <canvas id="globe" role="img" aria-label="A turning globe with {{PLACED}} candle lights, one for each mapped shrine or church of St. Expedite. Most are in Brazil and Argentina."></canvas>
  <div class="gnote" id="gnote" aria-live="polite"></div>
  <div class="flies">{{PLACES}}</div>
 </div>
 <div class="tally">{{TALLY}}</div>
 <div class="aside"><b>Réunion</b> holds about 340 blood-red roadside oratories (338 in the
 1998 census, plus 31 chapels). OpenStreetMap names only a handful, so only a handful glow
 here. {{T_DOC}}
 <div class="th">เกาะเรอูนียงมีศาลริมทางสีแดงราว ๓๔๐ แห่ง (สำรวจปี ๑๙๙๘ นับได้ ๓๓๘ กับโบสถ์น้อยอีก ๓๑)
 แต่ OpenStreetMap ระบุชื่อไว้ไม่กี่แห่ง แผนที่นี้จึงสว่างแค่ไม่กี่ดวง</div></div>
</section>

<section class="wrap" id="print">
 <p class="kicker">THE PRINTED RECORD · <span class="tk">ในหน้าหนังสือ</span></p>
 <h2>Five languages, one crest<span class="th">ห้าภาษา ขึ้นสูงสุดพร้อมกัน</span></h2>
 <p class="lede">His name in French, Italian, Spanish, German and English books crests between
 1904 and 1911, the same years Rome, under Pius X, moved against unauthorised images of him.
 The modern English spelling, <i>Saint Expedite</i>, climbs to its own peak in 2011. {{T_CON}}</p>
 <p class="th">ชื่อของท่านในหนังสือภาษาฝรั่งเศส อิตาลี สเปน เยอรมัน และอังกฤษ ขึ้นสูงสุดพร้อมกันระหว่างปี ๑๙๐๔–๑๙๑๑
 ตรงกับช่วงที่วาติกันสมัยสมเด็จพระสันตะปาปาปิอุสที่ ๑๐ ออกมาจัดการรูปเคารพของท่านที่ไม่ได้รับอนุญาต
 ส่วนตัวสะกดอังกฤษสมัยใหม่ Saint Expedite ขึ้นสูงสุดอีกรอบปี ๒๐๑๑</p>
 <div class="ngbox" id="ngbox">{{NGRAM}}</div>
 <p style="font:14px var(--sans);color:var(--muted)">Each row scaled to its own highest year. {{NGNOTE}}
 <span class="th" style="display:block;border:0;padding:0">Google Books ไม่มีคลังภาษาโปรตุเกส บราซิลซึ่งมีผู้ศรัทธามากที่สุดจึงไม่ปรากฏในกราฟนี้</span></p>
</section>

<section class="wrap" id="journey">
 <p class="kicker">THE JOURNEY · <span class="tk">เส้นทาง</span></p>
 <h2>From a name to a world<span class="th">จากชื่อหนึ่งชื่อ สู่ทั้งโลก</span></h2>
 <p>Each step carries where its authority comes from.
 <span class="tagkey">{{T_DOC}}{{T_SCH}}{{T_CON}}{{T_LEG}}{{T_PRA}}</span></p>
 <ol class="tl">{{TIMELINE}}</ol>
</section>

<section class="wrap" id="worlds">
 <p class="kicker">THREE WORLDS · <span class="tk">สามโลก</span></p>
 <h2>One saint, many altars<span class="th">นักบุญองค์เดียว หลายแท่นบูชา</span></h2>
 <div class="worlds">
  <div class="world reunion">
   {{F_REUNION}}
   <div><h3>Réunion<span class="th">ศาลแดงแห่งเรอูนียง</span></h3>
   <p>Red oratories stand at crossroads and dangerous bends across the island, where the dead
   of road accidents are said to wander. The red comes from Tamil practice and the goddess
   Kali. Devotees call him <i>un malbar-catholique</i>, a Tamil-Catholic; Catholics, Hindus
   and Malagasy all come, each without ceasing to be themselves. He is asked for a job, a cure,
   an exam passed, and feared when a vow goes unpaid. {{T_SCH}}</p>
   <p class="th">ศาลสีแดงตั้งอยู่ตามทางแยกและโค้งอันตรายทั่วเกาะ ที่ซึ่งว่ากันว่าวิญญาณผู้ตายจากอุบัติเหตุยังเร่ร่อน
   สีแดงมาจากประเพณีทมิฬและเจ้าแม่กาลี ชาวเกาะเรียกท่านว่า “มาลบาร์-คาทอลิก” คือคาทอลิกเชื้อสายทมิฬ
   ทั้งคาทอลิก ฮินดู และชาวมาลากาซีต่างมากราบไหว้ ขอทั้งงาน ขอหายป่วย ขอสอบผ่าน และเกรงท่านนักหากบนแล้วไม่แก้บน</p></div>
  </div>
  <div class="world">
   {{F_NOLA}}
   <div><h3>New Orleans<span class="th">ถวายเค้กให้ท่าน</span></h3>
   <p>His statue stands by the door of Our Lady of Guadalupe on Rampart Street, built in 1827
   as the yellow-fever mortuary chapel. {{T_DOC}} Practitioners read that doorway as the rule for
   a home altar: he belongs at the threshold. They pay him, most famously with a pound cake,
   and make their thanks public. {{T_PRA}}</p>
   <p class="th">รูปปั้นของท่านยืนอยู่ข้างประตูโบสถ์พระแม่กวาดาลูเป ถนนแรมพาร์ต ซึ่งสร้างปี ๑๘๒๗ เป็นโบสถ์สำหรับศพผู้ป่วยไข้เหลือง
   ผู้ปฏิบัติถือว่าท่านควรอยู่ที่ธรณีประตูบ้าน เมื่อได้ตามขอก็แก้บน ที่รู้จักกันดีคือเค้กปอนด์ แล้วประกาศคำขอบคุณให้คนรู้</p></div>
  </div>
  <div class="world">
   {{F_BA}}
   <div><h3>Buenos Aires &amp; Brazil<span class="th">ฝูงชนที่ใหญ่ที่สุด</span></h3>
   <p>About 70,000 people come to Balvanera parish on 19 April. {{T_DOC}} Chile's Reñaca parish
   reports 15,000 to 20,000 every 19th of the month. In Brazil a favour granted is repaid with
   the <i>promessa do milheiro</i>: a thousand small prayer cards, printed and handed out. {{T_PRA}}</p>
   <p class="th">วันที่ ๑๙ เมษายน ผู้คนราว ๗๐,๐๐๐ คนมาที่วัดบัลบาเนรา ที่ชิลี วัดเรญากามีคน ๑๕,๐๐๐–๒๐,๐๐๐ คนทุกวันที่ ๑๙ ของเดือน
   ส่วนที่บราซิล เมื่อได้ตามขอ ผู้ศรัทธาจะแก้บนด้วยการพิมพ์การ์ดภาพนักบุญหนึ่งพันใบแจกจ่ายออกไป</p></div>
  </div>
 </div>
</section>

<section class="wrap" id="contract">
 <p class="kicker">THE CONTRACT · <span class="tk">สัญญา</span></p>
 <h2>Ask. Promise. Thank in public.<span class="th">ขอ · บน · ขอบคุณให้คนรู้</span></h2>
 <p class="lede">Parish Catholic or hoodoo rootworker, devotion to him runs as a bargain in three beats. {{T_PRA}}</p>
 <div class="beats">
  <div class="beat"><b>I</b><h4>Ask<span>ขอ</span></h4><p>State the need plainly and fast. He is the saint of speed.</p><p class="th">บอกสิ่งที่ต้องการให้ชัดและเร็ว ท่านคือนักบุญแห่งความรวดเร็ว</p></div>
  <div class="beat"><b>II</b><h4>Promise<span>บน</span></h4><p>Name what you will give in return, and when.</p><p class="th">บอกว่าจะถวายอะไรตอบแทน และเมื่อไร</p></div>
  <div class="beat"><b>III</b><h4>Thank in public<span>ประกาศ</span></h4><p>When it comes, pay and say so where others can read it.</p><p class="th">เมื่อได้ตามขอ ให้แก้บนและประกาศให้คนอื่นได้อ่าน</p></div>
 </div>
 <div class="tools">
  <div class="tool">
   <h3>Set your thanks in type<span class="th">เรียงพิมพ์คำขอบคุณ</span></h3>
   <p style="font-size:16px;color:var(--muted);margin:0">New Orleans devotees once paid him in the newspaper personal columns.
   Set a notice in that style and keep it as a picture.</p>
   <div class="seg" role="group" aria-label="Language"><button type="button" data-l="en" aria-pressed="true">English</button><button type="button" data-l="th" aria-pressed="false">ไทย</button></div>
   <label for="nfor">Thanks for (optional) · ขอบคุณสำหรับ</label>
   <input id="nfor" maxlength="80" placeholder="favor granted" autocomplete="off">
   <label for="nsig">Signed · ลงชื่อ</label>
   <input id="nsig" maxlength="24" placeholder="N.P." autocomplete="off">
   <canvas id="notice" width="900" height="560" role="img" aria-label="Your notice, set as a newspaper personal column"></canvas>
   <button class="btn" id="nsave" type="button">Save the notice · บันทึกเป็นรูป</button>
  </div>
  <div class="tool">
   <h3>Nine candles<span class="th">โนวีนา เก้าวัน</span></h3>
   <p style="font-size:16px;color:var(--muted);margin:0">A novena is nine days of prayer, one a day, often timed to end on a 19th.
   Light one candle each day.</p>
   <p class="th" style="font-size:14px">โนวีนาคือการสวดภาวนาเก้าวัน วันละครั้ง มักนับให้ครบในวันที่ ๑๙ จุดเทียนวันละเล่ม</p>
   <div class="candles" id="candles"></div>
   <div class="nstat" id="nstat"></div>
   <button class="btn" id="nlight" type="button">Light today's candle · จุดเทียนวันนี้</button>
   <button class="btn ghost" id="nreset" type="button">Begin again</button>
  </div>
 </div>
</section>

<section class="wrap" id="offerings">
 <p class="kicker">OFFERINGS · <span class="tk">ของถวาย</span></p>
 <h2>What people leave him<span class="th">สิ่งที่ผู้คนถวายท่าน</span></h2>
 <div class="offer">
  <div class="off"><span class="ic">🌹</span><b>Red flowers</b><span>ดอกไม้สีแดง</span><p>The oldest New Orleans offering on record, Hyatt, 1935–39.</p></div>
  <div class="off"><span class="ic">🍰</span><b>Pound cake</b><span>เค้กปอนด์</span><p>“Feed the saint.” New Orleans.</p></div>
  <div class="off"><span class="ic">🪙</span><b>Coins &amp; water</b><span>เหรียญและน้ำ</span><p>On home altars.</p></div>
  <div class="off"><span class="ic">🃏</span><b>A thousand cards</b><span>การ์ดพันใบ</span><p>Brazil's <i>milheiro</i>.</p></div>
  <div class="off"><span class="ic">📰</span><b>Public thanks</b><span>คำขอบคุณ</span><p>Once the newspaper, now online.</p></div>
 </div>
</section>

<section class="wrap" id="gallery">
 <p class="kicker">GALLERY · <span class="tk">ภาพ</span></p>
 <h2>Cards, canvases, altars<span class="th">การ์ด ภาพวาด แท่นบูชา</span></h2>
 <div class="gallery">{{GALLERY}}</div>
</section>

<section class="wrap" id="shrines">
 <p class="kicker">SHRINES · <span class="tk">โบสถ์และศาล</span></p>
 <h2>{{TOTAL}} shrines &amp; churches<span class="th">โบสถ์และศาล {{TOTAL_TH}} แห่ง</span></h2>
 <p style="font:15px var(--sans);color:var(--muted)">From OpenStreetMap and a curated canon (✦). Also as data: <a href="/api/expedite.json">/api/expedite.json</a></p>
 {{LISTS}}
</section>

<section class="wrap" id="sources">
 <p class="kicker">SOURCES · <span class="tk">แหล่งอ้างอิง</span></p>
 <ul class="srcs">{{SOURCES}}</ul>
 <p class="kicker" style="margin-top:26px">IMAGES · <span class="tk">ภาพ</span></p>
 <ul class="srcs">{{CREDITS}}</ul>
</section>
</main>

<footer><div class="seal">HODIE</div><p>St. Expedite on <a href="/">wichaa</a> · text CC BY 4.0</p></footer>

<div id="lbx" role="dialog" aria-modal="true" aria-label="Image"><button type="button" aria-label="Close">×</button><img alt=""><p></p></div>

<script>
const DATA={{DATA}};
const RM=matchMedia('(prefers-reduced-motion: reduce)').matches;
const TD=s=>String(s).replace(/\d/g,d=>'๐๑๒๓๔๕๖๗๘๙'[d]);
const MTH=['มกราคม','กุมภาพันธ์','มีนาคม','เมษายน','พฤษภาคม','มิถุนายน','กรกฎาคม','สิงหาคม','กันยายน','ตุลาคม','พฤศจิกายน','ธันวาคม'];
const store={get(k){try{return JSON.parse(localStorage.getItem(k))}catch(e){return null}},
 set(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}}};

/* ---------- embers ---------- */
(()=>{const c=document.getElementById('embers'),x=c.getContext('2d');let W,H,P=[],run=true;
 const size=()=>{const r=devicePixelRatio||1;W=c.clientWidth;H=c.clientHeight;c.width=W*r;c.height=H*r;x.setTransform(r,0,0,r,0,0)};
 size();addEventListener('resize',size);
 const spawn=(burst,cx,cy)=>({x:cx??Math.random()*W,y:cy??H+10,vx:(Math.random()-.5)*(burst?5:.4),vy:-(burst?2+Math.random()*5:.3+Math.random()*.9),
  r:.6+Math.random()*(burst?2.6:1.8),life:0,max:burst?80+Math.random()*60:260+Math.random()*260,h:Math.random()<.7?30+Math.random()*20:8});
 for(let i=0;i<70;i++){const p=spawn();p.y=Math.random()*H;P.push(p)}
 window.emberBurst=(cx,cy)=>{for(let i=0;i<90;i++)P.push(spawn(true,cx,cy))};
 new IntersectionObserver(e=>{run=e[0].isIntersecting;if(run)requestAnimationFrame(tick)}).observe(c);
 function tick(){if(!run)return;x.clearRect(0,0,W,H);x.globalCompositeOperation='lighter';
  for(let i=P.length-1;i>=0;i--){const p=P[i];p.life++;p.x+=p.vx+Math.sin((p.life+i)*.03)*.25;p.y+=p.vy;p.vy*=.999;
   const a=Math.max(0,1-p.life/p.max);if(a<=0||p.y<-20){P.splice(i,1);if(P.length<70)P.push(spawn());continue}
   const g=x.createRadialGradient(p.x,p.y,0,p.x,p.y,p.r*4);g.addColorStop(0,`hsla(${p.h},95%,70%,${a})`);g.addColorStop(1,`hsla(${p.h},95%,50%,0)`);
   x.fillStyle=g;x.beginPath();x.arc(p.x,p.y,p.r*4,0,7);x.fill()}
  x.globalCompositeOperation='source-over';if(!RM)requestAnimationFrame(tick)}
 tick()})();

/* ---------- the stamp ---------- */
(()=>{const hero=document.getElementById('hero'),btn=document.getElementById('stamp'),gl=document.getElementById('gloss'),
 crow=document.getElementById('crow'),stage=document.getElementById('stage');
 let cawT=setInterval(()=>{if(hero.classList.contains('lit'))return clearInterval(cawT);hero.classList.add('cawing');
  setTimeout(()=>hero.classList.remove('cawing'),1600)},4200);
 function stamp(){if(hero.classList.contains('lit'))return;btn.disabled=true;
  const hr=hero.getBoundingClientRect(),cr=crow.getBoundingClientRect();
  const cx=cr.left-hr.left+cr.width*.6,cy=cr.top-hr.top+cr.height*.5;
  if(!RM){[...'CRAS'].forEach((ch,i)=>{const s=document.createElement('span');s.className='letter';s.textContent=ch;
    s.style.left=(cx+i*24-20)+'px';s.style.top=(cy-10)+'px';hero.appendChild(s);
    s.animate([{transform:'translate(0,0) rotate(0)',opacity:1},{transform:`translate(${(i-1.5)*70}px,${140+Math.random()*80}px) rotate(${(i-1.5)*90}deg)`,opacity:0}],
     {duration:1400,easing:'cubic-bezier(.3,.1,.6,1)',fill:'forwards'})});
   const r=document.createElement('div');r.className='ring';r.style.left=cx+'px';r.style.top=cy+'px';hero.appendChild(r);
   window.emberBurst&&emberBurst(cx,cy)}
  stage.parentNode.classList.add('shake');hero.classList.add('stamped');crow.querySelector('.banner').style.opacity=0;
  setTimeout(()=>{hero.classList.add('lit');gl.innerHTML='TODAY · <span class="tk">วันนี้</span>'},RM?0:260);
  store.set('expedite-stamped',1)}
 btn.addEventListener('click',stamp);crow.addEventListener('click',stamp);crow.style.cursor='pointer';
 if(store.get('expedite-stamped')&&location.hash){stamp()}})();

/* ---------- the day ---------- */
(()=>{const n=new Date(),d=n.getDate(),m=n.getMonth(),y=n.getFullYear(),dow=n.getDay();
 const big=document.getElementById('dayBig'),sm=document.getElementById('daySmall'),box=document.getElementById('day');
 const day0=new Date(y,m,d);const diff=t=>Math.round((t-day0)/864e5);
 let next19=new Date(y,m,19);if(d>19)next19=new Date(y,m+1,19);
 let feast=new Date(y,3,19);if(diff(feast)<0)feast=new Date(y+1,3,19);
 const nd=diff(next19),fd=diff(feast);
 const fmt=t=>t.toLocaleDateString('en-GB',{weekday:'short',day:'numeric',month:'short'});
 const fmtTh=t=>TD(t.getDate())+' '+MTH[t.getMonth()];
 let lines=[];
 if(m===3&&d===19){box.classList.add('feast');big.innerHTML='Today is his feast · 19 April<span class="th">วันนี้วันฉลองนักบุญเอ็กซ์เปดิต ๑๙ เมษายน</span>'}
 else if(d===19){box.classList.add('feast');big.innerHTML='Today is the 19th, his day of the month<span class="th">วันนี้วันที่ ๑๙ วันของท่านประจำเดือน</span>'}
 else big.innerHTML=`The 19th, his day, in ${nd} day${nd>1?'s':''}<span class="th">อีก ${TD(nd)} วันถึงวันที่ ๑๙ วันของท่าน</span>`;
 if(!(m===3&&d===19))lines.push(`Feast, 19 April: ${fd} days · วันฉลอง อีก ${TD(fd)} วัน`);
 const end=new Date(y,m,d+8);lines.push(`A novena begun today ends ${fmt(end)} · เริ่มโนวีนาวันนี้ ครบ ${fmtTh(end)}`);
 if(dow===3)lines.push('Wednesday: hoodoo workers keep it as his day, Mercury\'s day · วันพุธ หมอฮูดูถือเป็นวันของท่าน');
 sm.textContent=lines.join('  ·  ')})();

/* ---------- reveal on scroll ---------- */
(()=>{const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('inview');io.unobserve(e.target)}}),{threshold:.2});
 document.querySelectorAll('.tl-i,#ngbox').forEach(el=>io.observe(el))})();

/* ---------- globe ---------- */
(()=>{const cv=document.getElementById('globe'),x=cv.getContext('2d'),note=document.getElementById('gnote');
 let land=null,W=0,R=0,lam=48,phi=-18,vis=false,drag=null,idle=0,target=null,sel=null,t0=performance.now();
 const S=DATA.s.map((s,i)=>({lon:s[0],lat:s[1],t:s[2],k:s[3],loc:s[4],u:s[5],cur:s[6],ph:Math.random()*6.3,sp:.8+Math.random()*1.4}));
 const rad=Math.PI/180;
 function size(){const r=devicePixelRatio||1;W=cv.clientWidth;cv.width=W*r;cv.height=W*r;x.setTransform(r,0,0,r,0,0);R=W*.46}
 size();addEventListener('resize',()=>{size();draw()});
 function proj(lon,lat){const l=(lon+lam)*rad,p=lat*rad,p0=phi*rad;
  const cc=Math.sin(p0)*Math.sin(p)+Math.cos(p0)*Math.cos(p)*Math.cos(l);
  return [W/2+R*Math.cos(p)*Math.sin(l),W/2-R*(Math.cos(p0)*Math.sin(p)-Math.sin(p0)*Math.cos(p)*Math.cos(l)),cc]}
 function ring(pts){let started=false;for(const [lo,la] of pts){let [px,py,c]=proj(lo,la);
   if(c<0){const dx=px-W/2,dy=py-W/2,m=Math.hypot(dx,dy)||1;px=W/2+dx/m*R;py=W/2+dy/m*R}
   if(!started){x.moveTo(px,py);started=true}else x.lineTo(px,py)}x.closePath()}
 function draw(now=performance.now()){if(!W)return;x.clearRect(0,0,W,W);
  const g=x.createRadialGradient(W/2,W/2,R*.2,W/2,W/2,R*1.12);g.addColorStop(0,'#1a0f14');g.addColorStop(.86,'#0d0709');g.addColorStop(.9,'rgba(227,176,75,.28)');g.addColorStop(1,'rgba(227,176,75,0)');
  x.fillStyle=g;x.beginPath();x.arc(W/2,W/2,R*1.12,0,7);x.fill();
  x.fillStyle='#0f080b';x.beginPath();x.arc(W/2,W/2,R,0,7);x.fill();
  x.save();x.beginPath();x.arc(W/2,W/2,R,0,7);x.clip();
  x.strokeStyle='rgba(227,176,75,.07)';x.lineWidth=1;
  for(let lo=-180;lo<180;lo+=30){x.beginPath();let st=false;for(let la=-90;la<=90;la+=5){const [px,py,c]=proj(lo,la);if(c<0){st=false;continue}st?x.lineTo(px,py):x.moveTo(px,py);st=true}x.stroke()}
  for(let la=-60;la<=60;la+=30){x.beginPath();let st=false;for(let lo=-180;lo<=180;lo+=5){const [px,py,c]=proj(lo,la);if(c<0){st=false;continue}st?x.lineTo(px,py):x.moveTo(px,py);st=true}x.stroke()}
  if(land){x.fillStyle='#3a1a14';x.strokeStyle='rgba(227,176,75,.35)';x.lineWidth=.6;
   for(const r of land){let any=false;for(let i=0;i<r.length;i+=Math.max(1,r.length>>3)){if(proj(r[i][0],r[i][1])[2]>0){any=true;break}}
    if(!any)continue;x.beginPath();ring(r);x.fill();x.stroke()}}
  const sh=x.createRadialGradient(W/2-R*.35,W/2-R*.4,R*.1,W/2,W/2,R);sh.addColorStop(0,'rgba(255,220,160,.06)');sh.addColorStop(1,'rgba(0,0,0,.35)');
  x.fillStyle=sh;x.fillRect(0,0,W,W);
  x.globalCompositeOperation='lighter';const tt=now/1000;
  for(const s of S){const [px,py,c]=proj(s.lon,s.lat);s.px=px;s.py=py;s.v=c>0.02;if(!s.v)continue;
   const f=RM?1:.75+.25*Math.sin(tt*s.sp*3+s.ph)+.08*Math.sin(tt*11+s.ph*3);const rr=(s.cur?9:6)*f*Math.min(1,c*1.6+.3)*(W/640+.4);
   const gg=x.createRadialGradient(px,py,0,px,py,rr*2.4);gg.addColorStop(0,'rgba(255,248,220,.95)');gg.addColorStop(.25,'rgba(246,200,100,.75)');gg.addColorStop(.6,'rgba(220,90,30,.25)');gg.addColorStop(1,'rgba(200,40,20,0)');
   x.fillStyle=gg;x.beginPath();x.arc(px,py,rr*2.4,0,7);x.fill()}
  x.globalCompositeOperation='source-over';
  if(sel&&sel.v){x.strokeStyle='#f6d98a';x.lineWidth=1.5;x.beginPath();x.arc(sel.px,sel.py,12,0,7);x.stroke()}
  x.restore()}
 function loop(now){if(!vis)return;const dt=Math.min(50,now-t0);t0=now;
  if(target){lam+=(target[0]-lam)*.08;phi+=(target[1]-phi)*.08;if(Math.abs(target[0]-lam)<.1&&Math.abs(target[1]-phi)<.1)target=null}
  else if(!drag&&!RM&&now-idle>2500)lam-=dt*.004;
  draw(now);requestAnimationFrame(loop)}
 new IntersectionObserver(async e=>{vis=e[0].isIntersecting;if(vis){if(!land){try{land=await (await fetch('land.json')).json()}catch(err){land=[]}}
  t0=performance.now();requestAnimationFrame(loop);if(RM)draw()}},{rootMargin:'200px'}).observe(cv);
 const pt=e=>{const r=cv.getBoundingClientRect();return [e.clientX-r.left,e.clientY-r.top]};
 cv.addEventListener('pointerdown',e=>{drag={p:pt(e),l:lam,f:phi,moved:false};cv.setPointerCapture(e.pointerId);target=null});
 cv.addEventListener('pointermove',e=>{if(!drag)return;const [a,b]=pt(e),k=90/R;const dx=a-drag.p[0],dy=b-drag.p[1];
  if(Math.hypot(dx,dy)>4)drag.moved=true;lam=drag.l+dx*k;phi=Math.max(-80,Math.min(80,drag.f+dy*k));if(RM)draw()});
 cv.addEventListener('pointerup',e=>{const d=drag;drag=null;idle=performance.now();if(d&&!d.moved)pick(pt(e))});
 function show(s){sel=s;if(!s){note.textContent='';return}
  note.innerHTML='';const b=document.createElement(s.u?'a':'b');b.textContent=s.t;if(s.u){b.href=s.u;b.rel='noopener';b.style.color='var(--gold2)';b.style.fontWeight='600'}
  const k=document.createElement('div');k.className='k';k.textContent=s.k+' · '+s.loc+(s.cur?' · ✦ curated':'');note.append(b,k);if(RM)draw()}
 function pick([a,b]){let best=null,bd=22;for(const s of S){if(!s.v)continue;const d=Math.hypot(s.px-a,s.py-b);if(d<bd){bd=d;best=s}}show(best)}
 document.querySelectorAll('.fly').forEach(bt=>bt.addEventListener('click',()=>{const lo=+bt.dataset.lon,la=+bt.dataset.lat;
  let tl=-lo;while(tl-lam>180)tl-=360;while(tl-lam<-180)tl+=360;target=[tl,la];idle=performance.now()+4000;
  let best=null,bd=1e9;for(const s of S){const d=Math.hypot(s.lon-lo,s.lat-la);if(d<bd){bd=d;best=s}}if(best&&bd<3)show(best);
  if(RM){lam=target[0];phi=target[1];target=null;draw()}}));
})();

/* ---------- the notice ---------- */
(()=>{const cv=document.getElementById('notice'),x=cv.getContext('2d'),f=document.getElementById('nfor'),s=document.getElementById('nsig');
 let lang='en';
 document.querySelectorAll('.seg button').forEach(b=>b.addEventListener('click',()=>{lang=b.dataset.l;
  document.querySelectorAll('.seg button').forEach(o=>o.setAttribute('aria-pressed',o===b));draw()}));
 const noise=(()=>{const c=document.createElement('canvas');c.width=c.height=180;const g=c.getContext('2d'),d=g.createImageData(180,180);
  for(let i=0;i<d.data.length;i+=4){const v=Math.random()*40;d.data[i]=d.data[i+1]=d.data[i+2]=v;d.data[i+3]=Math.random()*22}g.putImageData(d,0,0);return c})();
 function wrap(t,maxW){const out=[];let line='';const toks=lang==='th'?[...(Intl.Segmenter?[...new Intl.Segmenter('th',{granularity:'word'}).segment(t)].map(z=>z.segment):t.split(''))]:t.split(/(\s+)/);
  for(const w of toks){const test=line+w;if(x.measureText(test).width>maxW&&line.trim()){out.push(line.trim());line=w.trimStart()}else line=test}if(line.trim())out.push(line.trim());return out}
 function draw(){const W=cv.width,H=cv.height;x.fillStyle='#ece2cb';x.fillRect(0,0,W,H);x.fillStyle=x.createPattern(noise,'repeat');x.fillRect(0,0,W,H);
  const vg=x.createRadialGradient(W/2,H/2,H*.3,W/2,H/2,W*.75);vg.addColorStop(0,'rgba(120,90,40,0)');vg.addColorStop(1,'rgba(120,90,40,.28)');x.fillStyle=vg;x.fillRect(0,0,W,H);
  x.fillStyle='#1d1712';x.strokeStyle='#1d1712';x.textAlign='center';
  const hd=lang==='th'?'"Noto Serif Thai",serif':'"Cinzel",Georgia,serif',bd=lang==='th'?'"Noto Serif Thai",serif':'"Cormorant Garamond",Georgia,serif';
  x.font=`700 30px ${hd}`;x.fillText(lang==='th'?'ประกาศขอบคุณ':'PERSONAL',W/2,70);
  x.lineWidth=2;x.beginPath();x.moveTo(60,90);x.lineTo(W-60,90);x.stroke();x.lineWidth=.8;x.beginPath();x.moveTo(60,96);x.lineTo(W-60,96);x.stroke();
  const what=f.value.trim(),who=s.value.trim()||'N.P.';
  const body=lang==='th'?`ขอบพระคุณนักบุญเอ็กซ์เปดิต ${what?'สำหรับ'+what:'ที่โปรดประทานตามคำขอ'} ได้สัญญาไว้ว่าจะประกาศให้ทราบทั่วกัน`
   :`THANKS to St. Expedite for ${what||'favor granted'}. Publication promised.`;
  x.textAlign='left';x.font=`600 ${lang==='th'?34:40}px ${bd}`;const lines=wrap(body,W-150);const lh=lang==='th'?64:54;
  let yy=Math.max(150,(H-lines.length*lh)/2+10);
  lines.forEach((l,i)=>{if(i===0&&lang==='en'){x.font=`700 40px ${hd}`;const w0='THANKS';x.fillText(w0,75,yy);const off=x.measureText(w0).width;x.font=`600 40px ${bd}`;x.fillText(l.slice(6),75+off,yy)}else x.fillText(l,75,yy);yy+=lh});
  x.textAlign='right';x.font=`italic 600 34px ${bd}`;x.fillText('— '+who,W-75,yy+20);
  x.lineWidth=.8;x.beginPath();x.moveTo(60,H-60);x.lineTo(W-60,H-60);x.stroke();
  x.textAlign='center';x.font=`500 16px ${hd}`;x.fillStyle='rgba(29,23,18,.6)';x.fillText('HODIE · wichaa.net/expedite',W/2,H-32)}
 f.addEventListener('input',draw);s.addEventListener('input',draw);
 (document.fonts?document.fonts.ready:Promise.resolve()).then(draw);draw();
 document.getElementById('nsave').addEventListener('click',()=>{const a=document.createElement('a');a.download='thanks-st-expedite.png';a.href=cv.toDataURL('image/png');a.click()})})();

/* ---------- nine candles ---------- */
(()=>{const box=document.getElementById('candles'),st=document.getElementById('nstat'),K='expedite-novena';
 const iso=d=>d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
 const today=new Date();today.setHours(0,0,0,0);
 let nv=store.get(K);
 const dayN=()=>nv?Math.round((today-new Date(nv.start+'T00:00'))/864e5):-1;
 if(nv&&dayN()>8+1)nv=null;
 function render(){box.innerHTML='';const n=dayN();
  for(let i=0;i<9;i++){const c=document.createElement('div');c.className='candle';
   const lit=nv&&nv.lit.includes(i);if(lit)c.classList.add('on');if(nv?i===n:i===0)c.classList.add('today');
   c.innerHTML='<div class="flame"></div><div class="wax"></div><small>'+(i+1)+'</small>';box.appendChild(c)}
  const start=nv?new Date(nv.start+'T00:00'):today,end=new Date(start);end.setDate(start.getDate()+8);
  const s11=new Date(today.getFullYear(),today.getMonth()+(today.getDate()>11?1:0),11);
  if(!nv)st.innerHTML=`Begin today and the ninth candle falls on ${end.toLocaleDateString('en-GB',{day:'numeric',month:'long'})}. Begin on the 11th to finish on the 19th (next: ${s11.toLocaleDateString('en-GB',{day:'numeric',month:'short'})}).<br><span class="th">เริ่มวันนี้ ครบวันที่ ${TD(end.getDate())} ${MTH[end.getMonth()]} ถ้าเริ่มวันที่ ๑๑ จะครบวันที่ ๑๙ พอดี</span>`;
  else if(n>8)st.innerHTML='Nine days are done. <span class="th">ครบเก้าวันแล้ว</span>';
  else st.innerHTML=`Day ${n+1} of 9 · ${nv.lit.length} lit · ends ${end.toLocaleDateString('en-GB',{weekday:'short',day:'numeric',month:'short'})}<br><span class="th">วันที่ ${TD(n+1)} จาก ๙ · จุดแล้ว ${TD(nv.lit.length)} เล่ม</span>`;
  document.getElementById('nlight').disabled=!!(nv&&(n>8||nv.lit.includes(n)))}
 document.getElementById('nlight').addEventListener('click',()=>{if(!nv)nv={start:iso(today),lit:[]};const n=dayN();
  if(n>=0&&n<9&&!nv.lit.includes(n))nv.lit.push(n);store.set(K,nv);render()});
 document.getElementById('nreset').addEventListener('click',()=>{nv=null;store.set(K,null);render()});
 render()})();

/* ---------- lightbox ---------- */
(()=>{const lb=document.getElementById('lbx'),im=lb.querySelector('img'),cp=lb.querySelector('p');let back=null;
 document.querySelectorAll('.lb').forEach(b=>b.addEventListener('click',()=>{back=b;im.src=b.dataset.full;im.alt=b.querySelector('img').alt;cp.textContent=b.dataset.cap;lb.classList.add('open');lb.querySelector('button').focus()}));
 const close=()=>{lb.classList.remove('open');back&&back.focus()};
 lb.addEventListener('click',e=>{if(e.target!==im)close()});addEventListener('keydown',e=>{if(e.key==='Escape'&&lb.classList.contains('open'))close()})})();
</script>
</body></html>
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", required=True)
    ap.add_argument("--site-url", default="https://wichaa.net")
    a = ap.parse_args(argv)
    docs = Path(a.docs)
    if not docs.is_dir():
        raise SystemExit(f"expedite: docs directory not found: {docs}")
    items = shrines()
    if not items:
        print("expedite: no shrine records in catalog.db (method='devotion') — page not written",
              file=sys.stderr)
        return 1
    missing = [n for n in IMAGES if not (DATA / "img" / n).exists()]
    if missing or not (DATA / "land.json").exists() or not (DATA / "ngrams.json").exists():
        print(f"expedite: data/expedite incomplete ({len(missing)} images missing) — page not written",
              file=sys.stderr)
        return 1
    ng = json.loads((DATA / "ngrams.json").read_text(encoding="utf-8"))
    site = a.site_url.rstrip("/")
    out = docs / "expedite"
    (out / "img").mkdir(parents=True, exist_ok=True)
    for n in IMAGES:
        shutil.copyfile(DATA / "img" / n, out / "img" / n)
    shutil.copyfile(DATA / "land.json", out / "land.json")
    if CARD.exists():
        shutil.copyfile(CARD, out / "card.png")
    (out / "index.html").write_text(render(items, ng, site), encoding="utf-8")
    placed = sum(1 for it in items if it["lat"] is not None)
    print(f"expedite: /expedite written — {len(items)} shrines, {placed} on the globe, "
          f"{len(IMAGES)} images")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
