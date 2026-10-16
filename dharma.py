#!/usr/bin/env python3
"""dharma — /dharma: the word dharma for readers of any language or faith.

The word in eighteen languages (bells), what it does for Hindus, Buddhists, Jains
and Sikhs (cards), the eight-spoked wheel, a day at a wat, sand chedi at Songkran,
siam si fortune sticks carrying Dhammapada verses, the tham script that writes this
corpus, and neighbouring words from other traditions.

Self-contained like kesa.py and expedite.py: reads catalog.db for the manuscript
counts, data/dharma/ for photographs, credits and the page text (i18n/<lang>.json,
English is the source), and writes docs/dharma/. The English text is rendered into
the HTML; the other languages load when a reader picks one.

    python3 dharma.py --docs <site>/docs [--site-url https://wichaa.net]
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
DATA = HERE / "data" / "dharma"

LANGS = [("en", "English"), ("th", "ไทย"), ("zh", "中文"), ("ja", "日本語"), ("ko", "한국어"),
         ("hi", "हिन्दी"), ("my", "မြန်မာ"), ("es", "Español"), ("fr", "Français"),
         ("de", "Deutsch"), ("ru", "Русский"), ("he", "עברית")]

# key, word as written, romanised, c = carried from Sanskrit/Pali, t = another word chosen
BELLS = [
    ("sa", "धर्म", "dharma", "c"), ("pi", "dhamma", "dhamma", "c"), ("hi", "धर्म", "dharm", "c"),
    ("pa", "ਧਰਮ", "dharam", "c"), ("th", "ธรรม", "tham", "c"), ("tt", "ᨵᨾ᩠ᨾ", "tham", "c"),
    ("lo", "ທຳ", "tham", "c"), ("km", "ធម៌", "thoa", "c"), ("my", "ဓမ္မ", "dhamma", "c"),
    ("si", "ධර්මය", "dharmaya", "c"), ("id", "derma", "derma", "c"), ("bo", "ཆོས", "chö", "t"),
    ("mn", "ном", "nom", "t"), ("zh", "法", "fǎ", "t"), ("ja", "法", "hō", "t"),
    ("ko", "법", "beop", "t"), ("vi", "pháp", "pháp", "t"), ("ta", "அறம்", "aram", "t"),
]
BELL_LANG = {"sa": "Sanskrit", "pi": "Pali", "hi": "Hindi", "pa": "Punjabi", "th": "Thai",
             "tt": "Lanna", "lo": "Lao", "km": "Khmer", "my": "Burmese", "si": "Sinhala",
             "id": "Malay", "bo": "Tibetan", "mn": "Mongolian", "zh": "Chinese",
             "ja": "Japanese", "ko": "Korean", "vi": "Vietnamese", "ta": "Tamil"}
HERO_WORDS = ["Dharma", "धर्म", "ธรรม", "ᨵᨾ᩠ᨾ", "ဓမ္မ", "法", "ཆོས", "ਧਰਮ", "ធម៌", "ທຳ",
              "ධර්ම", "법", "அறம்", "Ном", "Dhamma", "Pháp"]

GALLERY = [("hiranyawat-tung-avenue", "cap_avenue"), ("chiangman-glass-mosaic", "cap_mosaic"),
           ("phumin-mural-whisper", "cap_whisper"), ("saengkaew-naga-stair-bells", "cap_bells"),
           ("temple-dog", "cap_dog"), ("songkran-family", "cap_songkran"),
           ("sand-hands", "cap_sand"), ("langar-family", "cap_langar_family")]

LINKS = [("/browse/", "Browse manuscripts"), ("/kesa/", "ยันต์เกศาผิด · the kesa yant"),
         ("/wats/", "Wats of the Lanna north"), ("/expedite/", "St. Expedite"),
         ("/khwan/", "Su Khwan"), ("/hotrai/", "หอไตร · the ho trai")]


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def counts() -> dict:
    db = os.environ.get("CATALOG_DB") or str(
        HERE.parent / "manuscript-crawler" / "crawler" / "catalog.db")
    uri = f"file:{db}?mode=ro" + ("&immutable=1" if os.environ.get("CATALOG_IMMUTABLE") else "")
    con = sqlite3.connect(uri, uri=True)
    q = lambda s: con.execute(s).fetchone()[0]
    out = {
        "total": q("SELECT COUNT(*) FROM manuscripts"),
        "tham": q("SELECT COUNT(*) FROM manuscripts WHERE script LIKE 'tham%'"),
        "wats": q("SELECT COUNT(DISTINCT provenance_temple) FROM manuscripts "
                  "WHERE script LIKE 'tham%' AND COALESCE(provenance_temple,'')<>''"),
        "ves": q("SELECT COUNT(*) FROM manuscripts WHERE title_thai LIKE '%เวสสัน%' "
                 "OR title_thai LIKE '%มหาชาติ%' "
                 "OR LOWER(COALESCE(title_translit,'')||' '||COALESCE(title_english,'')) LIKE '%wetsan%' "
                 "OR LOWER(COALESCE(title_translit,'')||' '||COALESCE(title_english,'')) LIKE '%vessantar%'"),
    }
    con.close()
    return out


class Text:
    """English text for the static HTML, tagged with its path so the page can swap it."""

    def __init__(self, en: dict):
        self.en = en

    def get(self, path: str):
        v = self.en
        for k in path.split("."):
            v = v[int(k)] if isinstance(v, list) else v[k]
        return v

    def __call__(self, path: str, tag: str = "span", cls: str = "", vars: dict | None = None,
                 extra: str = "") -> str:
        s = self.get(path)
        dv = ""
        if vars:
            s = s.format(**vars)
            dv = f" data-v='{esc(json.dumps(vars))}'"
        c = f' class="{cls}"' if cls else ""
        return f'<{tag}{c} data-i="{path}"{dv}{extra}>{esc(s)}</{tag}>'


def pic(cred: dict, pid: str, cls: str = "", eager: bool = False) -> str:
    c = cred[pid]
    load = 'fetchpriority="high"' if eager else 'loading="lazy"'
    return (f'<img class="{cls}" src="img/{pid}-800.jpg" srcset="img/{pid}-800.jpg 800w, '
            f'img/{pid}.jpg 1600w" sizes="100vw" alt="" {load} decoding="async">')


def credit_line(cred: dict, pid: str) -> str:
    c = cred[pid]
    return (f'<a href="{esc(c["page"])}" rel="noopener">{esc(c["by"])}</a> · '
            f'{esc(c["licence"])}')


def band(cred, pid, inner, cls="", eager=False) -> str:
    return (f'<section class="band {cls}"><div class="ph">{pic(cred, pid, eager=eager)}</div>'
            f'<div class="in">{inner}</div><p class="cred">{credit_line(cred, pid)}</p></section>')


def render(en: dict, n: dict, cred: dict, site: str, have: list) -> str:
    T = Text(en)
    url = f"{site}/dharma/"

    bells = "".join(
        f'<button class="bell k{i % 6}" data-b="{k}" data-n="{i}" aria-label="{esc(BELL_LANG[k])}: {esc(rom)}">'
        f'<svg viewBox="0 0 60 70" aria-hidden="true"><path class="bd" d="M30 6c-3 0-5 2-5 5v2C14 16 10 26 10 38c0 8-3 13-6 16h52c-3-3-6-8-6-16 0-12-4-22-15-25v-2c0-3-2-5-5-5z"/>'
        f'<circle class="cl" cx="30" cy="60" r="6"/></svg>'
        f'<b class="bw" lang="{k if k not in ("tt", "pi", "sa") else "und"}">{esc(word)}</b>'
        f'<small>{esc(rom)}</small><i class="mark {kind}"></i></button>'
        for i, (k, word, rom, kind) in enumerate(BELLS))

    rooms = []
    for i, r in enumerate(en["rooms"]):
        extra = ""
        if r["id"] == "jain":
            extra = (f'<div class="pond" aria-hidden="true"><span class="fish">🐟</span></div>'
                     f'<button class="toy jtoggle" type="button" aria-pressed="true">'
                     f'{T(f"rooms.{i}.toy_on")}</button>')
        if r["id"] == "thai":
            tiles = "".join(
                f'<li><b lang="th">{esc(w["th"]).replace("ธรรม", "<em>ธรรม</em>")}</b>'
                f'<small>{esc(w["rom"])}</small>{T(f"thai_words.{j}.en")}</li>'
                for j, w in enumerate(en["thai_words"]))
            extra = f'<ul class="tw">{tiles}</ul>'
        rooms.append(
            f'<article class="room r-{r["id"]}"><div class="face front">'
            f'<h3>{T(f"rooms.{i}.name")}</h3><p class="rw">{esc(r["word"])}</p>'
            f'{T(f"rooms.{i}.front", "p")}<button class="turn" type="button">{T("rooms_turn")} ↻</button></div>'
            f'<div class="face back"><h3>{T(f"rooms.{i}.name")}</h3>{T(f"rooms.{i}.back", "p")}{extra}'
            f'<button class="turn" type="button">↺</button></div></article>')

    spokes = "".join(f'<li data-s="{i}"><b>{i + 1}</b> {T(f"spokes.{i}.en")}</li>'
                     for i in range(len(en["spokes"])))
    day_list = "".join(f'<li><b>{esc(d["t"])}</b> {T(f"day.{i}.what")}</li>'
                       for i, d in enumerate(en["day"]))
    gallery = "".join(
        f'<figure>{pic(cred, pid)}<figcaption>{T(key)}<small>{credit_line(cred, pid)}</small></figcaption></figure>'
        for pid, key in GALLERY)
    nbs = "".join(
        f'<button class="nb" type="button"><b>{esc(x["w"])}</b>{T(f"neighbours.{i}.from", "small")}'
        f'{T(f"neighbours.{i}.say", "span", "say")}</button>'
        for i, x in enumerate(en["neighbours"]))
    links = "".join(f'<li><a href="{esc(h)}">{esc(t)}</a></li>' for h, t in LINKS)
    creds = "".join(
        f'<li>{esc(c.get("place") or c["id"])}: {credit_line(cred, c["id"])}</li>' for c in cred.values())
    langs = "".join(f'<li><button type="button" data-lang="{k}" lang="{k}">{esc(nm)}</button></li>'
                    for k, nm in LANGS if k in have)

    data = {
        "en": en, "bells": [{"k": k, "w": w, "r": r, "kind": kd} for k, w, r, kd in BELLS],
        "hero": HERO_WORDS, "n": n, "langs": have,
    }
    jsonld = json.dumps(byline.webpage(url, "Dharma · ธรรม", "/dharma", about={
        "@type": "Thing", "name": "Dharma",
        "sameAs": "https://www.wikidata.org/wiki/Q131113"}), ensure_ascii=False)
    sub = "".join(sorted(set("".join(HERO_WORDS + [b[1] for b in BELLS]))))

    tv = {"total": f'{n["total"]:,}'}
    body = f"""
<a class="skip" href="#main">{T("skip")}</a>
<nav class="bar"><a class="home" href="/">wichaa · <span lang="th">วิชา</span></a>
 <div class="lang"><button type="button" id="langbtn" aria-haspopup="true" aria-expanded="false">🌐 <span id="langnow">English</span></button>
 <ul id="langs" hidden>{langs}</ul></div></nav>

<header class="band hero">{'<div class="ph">' + pic(cred, "lokmoli-chedi-tung", eager=True) + '</div>'}
 <div class="in">
  {T("hero_kicker", "p", "kicker")}
  <h1><button type="button" id="heroword" aria-describedby="herotap">Dharma</button></h1>
  {T("hero_tap", "p", "tap", extra=' id="herotap"')}
  {T("hero_lede", "p", "lede")}
  <a class="go" href="#word">{T("hero_go")} ↓</a>
 </div>
 <p class="cred">{T("credit")}: {credit_line(cred, "lokmoli-chedi-tung")}</p>
</header>

<main id="main">
<section id="word" class="sec cream">
 <div class="wrap">
  {T("word_kicker", "p", "kicker")}
  {T("word_title", "h2")}
  {T("word_body", "p", "lead")}
  {T("word_hint", "p", "hint")}
  <div class="bells">{bells}</div>
  <div class="bellsay" id="bellsay" aria-live="polite"></div>
  <p class="legend"><i class="mark c"></i> {T("word_cognate")} &nbsp; <i class="mark t"></i> {T("word_translated")}</p>
  <button class="toy" id="ringall" type="button">🔔 {T("word_all")}</button>
 </div>
</section>

<section id="rooms" class="sec saffron">
 <div class="wrap">
  {T("rooms_kicker", "p", "kicker")}
  {T("rooms_title", "h2")}
  {T("rooms_body", "p", "lead")}
  <div class="rooms">{"".join(rooms)}</div>
 </div>
</section>

{band(cred, "langar", T("band_langar", "p", "big"), "short")}

<section id="wheel" class="sec red">
 <div class="wrap two">
  <div>
   {T("wheel_kicker", "p", "kicker")}
   {T("wheel_title", "h2")}
   {T("wheel_body", "p", "lead")}
   {T("wheel_hint", "p", "hint")}
   <ol class="spokes" id="spokes">{spokes}</ol>
  </div>
  <div class="wheelbox">
   <div class="pointer" aria-hidden="true">▼</div>
   <svg id="wheelsvg" viewBox="-110 -110 220 220" role="img" aria-label="dharma wheel"><g id="wh"></g></svg>
   <button class="toy" id="spin" type="button">☸ {T("wheel_spin")}</button>
   <div class="spokesay" id="spokesay" aria-live="polite"></div>
  </div>
 </div>
</section>

{band(cred, "sand-stupas", T("wat_kicker", "p", "kicker") + T("wat_title", "h2"), "tall")}

<section id="wat" class="sec cream">
 <div class="wrap">
  {T("wat_body", "p", "lead")}
  <div class="day">
   {T("day_title", "h3")}
   <div class="sky" id="sky"><span class="orb" id="orb"></span><b class="clock" id="clock">06:00</b>
    <p class="now" id="daynow" aria-live="polite"></p></div>
   <input type="range" id="dayr" min="270" max="1260" step="5" value="360" dir="ltr" aria-label="time of day">
   {T("day_hint", "p", "hint")}
   <p class="moon" id="moon"></p>
   {T("moon_note", "p", "small")}
   <noscript><ul>{day_list}</ul></noscript>
  </div>
 </div>
</section>

<section class="gallery" aria-label="photographs">{T("photos_title", "h3", "gt")}<div class="strip">{gallery}</div></section>

<section id="sand" class="sec tung">
 <div class="wrap two">
  <div>
   {T("sand_title", "h2")}
   {T("sand_body", "p", "lead")}
   <p class="count" id="sandcount" data-i="sand_count" data-v='{{"n":0}}'>0</p>
   <div class="row"><button class="toy" id="carry" type="button">🪣 {T("sand_carry")}</button>
   <button class="toy ghost" id="sandreset" type="button">{T("sand_reset")}</button></div>
  </div>
  <svg id="sandsvg" viewBox="0 0 320 230" role="img" aria-label="sand chedi">
   <rect x="0" y="200" width="320" height="30" class="ground"/>
   <g id="flags"></g><path id="pile" d=""/><g id="grains"></g></svg>
 </div>
</section>

<section id="sticks" class="sec gold">
 <div class="wrap two">
  <div>
   {T("sticks_kicker", "p", "kicker")}
   {T("sticks_title", "h2")}
   {T("sticks_body", "p", "lead")}
   {T("sticks_motion", "p", "hint motionhint", extra=" hidden")}
  </div>
  <div class="cupbox">
   <svg id="cup" viewBox="0 -90 160 310" aria-hidden="true"><g id="stickset"></g>
    <path class="cupb" d="M30 100h100l-12 112H42z"/><path class="cupr" d="M26 96h108v10H26z"/>
    <g id="out" class="outstick"><rect x="68" y="10" width="24" height="150" rx="7"/><rect x="68" y="10" width="24" height="12" rx="5" class="tip"/><text x="80" y="48" id="outn">1</text></g></svg>
   <button class="toy" id="shake" type="button">🎋 {T("sticks_shake")}</button>
  </div>
 </div>
 <div class="wrap"><blockquote class="verse" id="verse" aria-live="polite" hidden></blockquote></div>
</section>

<section id="tham" class="band tall glass"><div class="ph">{pic(cred, "chiangman-glass-mosaic")}</div>
 <div class="in">
  {T("tham_kicker", "p", "kicker")}
  {T("tham_title", "h2")}
  {T("tham_body", "p")}
  <div class="stats">
   <div><b>{n["tham"]:,}</b>{T("tham_stat_tham", vars=tv)}</div>
   <div><b>{n["wats"]:,}</b>{T("tham_stat_wats")}</div>
   <div><b>{n["ves"]:,}</b>{T("tham_stat_ves")}</div>
  </div>
  <p class="row"><a class="go" href="/browse/">{T("tham_go")} →</a> <a class="go" href="/kesa/">{T("tham_kesa")} →</a></p>
 </div>
 <p class="cred">{credit_line(cred, "chiangman-glass-mosaic")}</p>
</section>

<section id="neighbours" class="sec blue">
 <div class="wrap">
  {T("nb_kicker", "p", "kicker")}
  {T("nb_title", "h2")}
  {T("nb_body", "p", "lead")}
  <div class="nbs">{nbs}</div>
 </div>
</section>

{band(cred, "suthep-naga-stair", T("end_title", "h2") + T("end_body", "p"), "tall", )}

<section class="sec cream foot">
 <div class="wrap two">
  <div>{T("more", "h3")}<ul class="links">{links}</ul></div>
  <div>{T("src_title", "h3")}{T("src_body", "p", "small")}
   <ul class="creds">{creds}</ul>{T("made", "p", "small")}</div>
 </div>
</section>
</main>
"""
    return (PAGE.replace("{{SITE}}", site).replace("{{URL}}", url)
            .replace("{{TITLE}}", esc(en["meta_title"])).replace("{{DESC}}", esc(en["meta_desc"]))
            .replace("{{JSONLD}}", jsonld.replace("</", "<\\/"))
            .replace("{{SUB}}", sub.replace(" ", "")).replace("{{BODY}}", body)
            .replace("{{DATA}}", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")))


PAGE = r"""<!doctype html>
<html lang="en" dir="ltr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{TITLE}}</title>
<meta name="description" content="{{DESC}}">
<link rel="canonical" href="{{URL}}">
<meta property="og:type" content="article"><meta property="og:site_name" content="wichaa">
<meta property="og:title" content="Dharma · ธรรม">
<meta property="og:description" content="{{DESC}}">
<meta property="og:url" content="{{URL}}">
<meta property="og:image" content="{{URL}}card.jpg">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Sand chedi planted with bright flags in a temple courtyard at Songkran">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#c8102e">
<script type="application/ld+json">{{JSONLD}}</script>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;700;800&family=Noto+Sans:wght@400;600&family=Noto+Sans+Thai:wght@400;600&display=swap" rel="stylesheet">
<link id="fsub" href="https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari:wght@700&family=Noto+Sans+Gurmukhi:wght@700&family=Noto+Sans+Tai+Tham:wght@700&family=Noto+Sans+Lao:wght@700&family=Noto+Sans+Khmer:wght@700&family=Noto+Sans+Myanmar:wght@700&family=Noto+Sans+Sinhala:wght@700&family=Noto+Serif+Tibetan:wght@700&family=Noto+Sans+Tamil:wght@700&family=Noto+Sans+SC:wght@700&family=Noto+Sans+KR:wght@700&display=swap&text={{SUB}}" rel="stylesheet">
<style>
:root{--cream:#fff6e6;--ink:#2a140e;--muted:#6d4b3a;--red:#c8102e;--red2:#8e0b20;--gold:#f2b134;
 --saffron:#f28c28;--green:#16936a;--blue:#2350b8;--pink:#e8478b;--teal:#0f8b8d;
 --disp:"Baloo 2","Rubik","Mali","Noto Sans Thai","Noto Sans Devanagari",system-ui,sans-serif;
 --body:"Noto Sans","Noto Sans Thai",system-ui,-apple-system,"Segoe UI",sans-serif;
 --scripts:"Noto Sans Devanagari","Noto Sans Gurmukhi","Noto Sans Tai Tham","Noto Sans Lao","Noto Sans Khmer","Noto Sans Myanmar","Noto Sans Sinhala","Noto Serif Tibetan","Noto Sans Tamil","Noto Sans Thai","Noto Sans SC","Noto Sans KR","Baloo 2",sans-serif}
:root:lang(zh){--body:"Noto Sans SC","Noto Sans",system-ui,sans-serif;--disp:"Noto Sans SC",system-ui,sans-serif}
:root:lang(ja){--body:"Noto Sans JP","Noto Sans",system-ui,sans-serif;--disp:"Noto Sans JP",system-ui,sans-serif}
:root:lang(ko){--body:"Noto Sans KR","Noto Sans",system-ui,sans-serif;--disp:"Noto Sans KR",system-ui,sans-serif}
:root:lang(hi){--body:"Noto Sans Devanagari","Noto Sans",system-ui,sans-serif}
:root:lang(my){--body:"Noto Sans Myanmar","Noto Sans",system-ui,sans-serif;--disp:"Noto Sans Myanmar",system-ui,sans-serif}
:root:lang(he){--body:"Noto Sans Hebrew","Noto Sans",system-ui,sans-serif;--disp:"Rubik","Noto Sans Hebrew",system-ui,sans-serif}
:root:lang(ru){--disp:"Rubik","Noto Sans",system-ui,sans-serif}
:root:lang(th){--disp:"Mali","Noto Sans Thai",system-ui,sans-serif}
:lang(th) .kicker,:lang(my) .kicker,:lang(hi) .kicker,:lang(zh) .kicker,:lang(ja) .kicker,:lang(ko) .kicker,:lang(he) .kicker{letter-spacing:.04em}
*{box-sizing:border-box}
html{scroll-behavior:smooth;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--cream);color:var(--ink);font-family:var(--body);font-size:18px;line-height:1.65;overflow-x:hidden}
:lang(my) body,:root:lang(my) body{line-height:1.9}
a{color:var(--red2)}
img{display:block;max-width:100%}
button{font:inherit;color:inherit}
.skip{position:absolute;top:0;inset-inline-start:0;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}.skip:focus{width:auto;height:auto;clip-path:none;top:60px;inset-inline-start:12px;z-index:20;background:#000;color:#fff;padding:8px}
.wrap{max-width:1040px;margin:0 auto;padding:0 16px}
.two{display:grid;gap:28px;align-items:center}
@media(min-width:820px){.two{grid-template-columns:1.1fr .9fr}}
h1,h2,h3{font-family:var(--disp);line-height:1.08;margin:.2em 0 .35em}
h2{font-size:clamp(2rem,6.5vw,3.4rem);font-weight:800}
:lang(my) h1,:lang(my) h2,:lang(my) h3,:lang(my) .big{line-height:1.55}
:lang(th) h2,:lang(th) h3,:lang(hi) h2,:lang(hi) h3,:lang(th) .big,:lang(hi) .big{line-height:1.35}
h3{font-size:1.45rem;font-weight:700}
.kicker{font-family:var(--disp);font-weight:700;letter-spacing:.18em;text-transform:uppercase;font-size:.85rem;margin:0;opacity:.85}
.lead{font-size:1.12rem;max-width:62ch}
.hint{font-size:.95rem;opacity:.8;font-style:italic}
.small{font-size:.9rem;opacity:.85}
.sec{padding:64px 0;position:relative}
.cream{background:var(--cream)}
.saffron{background:linear-gradient(160deg,#ffb347,#f28c28 60%,#e8653a);color:#2a0f05}
.red{background:radial-gradient(120% 90% at 80% 20%,#e0243f,#8e0b20);color:#fff3e0}
.red a{color:#ffd88a}
.tung{background:repeating-linear-gradient(90deg,#fde9f1 0 46px,#fff3d6 46px 92px,#e3f3ff 92px 138px);}
.gold{background:linear-gradient(170deg,#ffd76a,#f2b134 70%,#e39a1b)}
.blue{background:linear-gradient(170deg,#2350b8,#16367f);color:#eef3ff}
.foot{padding:48px 0 80px}

/* top bar */
.bar{position:fixed;top:0;left:0;right:0;z-index:15;display:flex;justify-content:space-between;align-items:center;
 padding:8px 12px;background:rgba(42,20,14,.55);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)}
.bar .home{color:#fff;text-decoration:none;font-family:var(--disp);font-weight:700;letter-spacing:.06em}
.lang{position:relative}
#langbtn{background:#fff;border:0;border-radius:99px;padding:6px 14px;font-weight:600;cursor:pointer;min-height:40px}
#langs{position:absolute;inset-inline-end:0;top:46px;margin:0;padding:6px;list-style:none;background:#fff;border-radius:14px;
 box-shadow:0 10px 30px rgba(0,0,0,.3);display:grid;grid-template-columns:1fr 1fr;gap:2px;width:260px}
#langs[hidden]{display:none}
#langs button{width:100%;text-align:start;background:none;border:0;border-radius:8px;padding:8px 10px;cursor:pointer;font-size:1rem}
#langs button:hover,#langs button[aria-current]{background:#ffe6c4}

/* bands: the photograph stays put while the page slides over it */
.band{position:relative;clip-path:inset(0);min-height:clamp(300px,60vh,560px);display:grid;align-items:center;color:#fff;isolation:isolate}
.band .ph{position:fixed;inset:0;z-index:-2}
.band .ph img{width:100%;height:100%;object-fit:cover}
.band::before{content:"";position:absolute;inset:0;z-index:-1;background:linear-gradient(180deg,rgba(20,6,4,.62),rgba(20,6,4,.22) 40%,rgba(20,6,4,.35) 65%,rgba(20,6,4,.8))}
.band .in{max-width:1040px;width:100%;margin:0 auto;padding:72px 16px}
.band h2,.band .big{text-shadow:0 2px 24px rgba(0,0,0,.6)}
.band .big{font-family:var(--disp);font-size:clamp(1.6rem,5vw,2.6rem);font-weight:700;line-height:1.15;max-width:24ch}
.band p{max-width:60ch;text-shadow:0 1px 12px rgba(0,0,0,.7)}
.band.tall{min-height:clamp(380px,82vh,760px)}
.band.short{min-height:clamp(260px,46vh,420px)}
.band .cred{position:absolute;inset-inline-end:0;bottom:0;margin:0;font-size:.68rem;background:rgba(0,0,0,.6);padding:3px 8px;max-width:80%;text-shadow:none}
.band .cred a{color:#fde6c8}
.hero{min-height:100svh;text-align:center}
.hero .in{display:flex;flex-direction:column;align-items:center;padding-top:90px}
.hero h1{margin:.05em 0}
#heroword{background:none;border:0;cursor:pointer;color:#fff;font-family:var(--scripts);font-weight:800;
 font-size:clamp(4rem,19vw,10rem);line-height:1.1;text-shadow:0 4px 40px rgba(0,0,0,.6),0 0 2px #000;min-height:1.2em;transition:transform .25s}
#heroword:active{transform:scale(.94)}
.hero .tap{font-size:.95rem;opacity:.9;margin:0}
.hero .lede{font-size:clamp(1.05rem,2.6vw,1.3rem);max-width:40ch;margin:18px auto}
.go{display:inline-block;background:var(--gold);color:#2a140e;font-family:var(--disp);font-weight:800;text-decoration:none;
 border-radius:99px;padding:10px 22px;margin:6px 4px;box-shadow:0 4px 0 #a86d00}
.go:active{transform:translateY(2px);box-shadow:0 2px 0 #a86d00}

/* toys share a chunky button */
.toy{background:var(--red);color:#fff;border:0;border-radius:99px;padding:11px 22px;font-family:var(--disp);font-weight:800;font-size:1.1rem;
 cursor:pointer;box-shadow:0 4px 0 var(--red2);min-height:46px}
.toy:active{transform:translateY(2px);box-shadow:0 2px 0 var(--red2)}
.toy.ghost{background:transparent;color:inherit;box-shadow:inset 0 0 0 2px currentColor}
.red .toy{background:var(--gold);color:#2a140e;box-shadow:0 4px 0 #a86d00}
.row{display:flex;flex-wrap:wrap;gap:10px;align-items:center}

/* bells */
.bells{display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:10px;margin:18px 0}
.bell{position:relative;border:0;border-radius:18px;padding:8px 4px 10px;cursor:pointer;display:flex;flex-direction:column;align-items:center;
 background:#fff;box-shadow:0 3px 0 rgba(0,0,0,.12)}
.bell svg{width:46px;height:54px;transform-origin:50% 8%}
.bell .bd{fill:var(--c)}.bell .cl{fill:#7a4a10}
.bell.ring svg{animation:swing .9s ease-out}
@keyframes swing{0%{transform:rotate(0)}15%{transform:rotate(22deg)}35%{transform:rotate(-16deg)}55%{transform:rotate(10deg)}75%{transform:rotate(-5deg)}100%{transform:rotate(0)}}
.bell .bw{font-family:var(--scripts);font-size:1.45rem;line-height:1.5;color:var(--ink)}
.bell small{font-size:.8rem;color:var(--muted)}
.k0{--c:#f2b134}.k1{--c:#e8478b}.k2{--c:#16936a}.k3{--c:#2350b8}.k4{--c:#c8102e}.k5{--c:#f28c28}
.mark{position:absolute;top:8px;inset-inline-end:8px;width:10px;height:10px;border-radius:50%;display:inline-block}
.mark.c{background:var(--saffron)}.mark.t{background:var(--teal)}
.legend .mark{position:static;vertical-align:middle;margin:0 4px}
.legend{font-size:.9rem}
.bellsay{min-height:5.5em;background:#fff;border-radius:18px;padding:14px 18px;border-inline-start:6px solid var(--gold);margin:6px 0 16px}
.bellsay:empty{display:none}
.bellsay b{font-family:var(--scripts);font-size:2rem;margin-inline-end:10px}

/* rooms */
.rooms{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));margin-top:20px}
.room{display:grid;perspective:1200px}
.face{grid-area:1/1;display:flex;flex-direction:column;border-radius:22px;padding:22px 20px 18px;backface-visibility:hidden;-webkit-backface-visibility:hidden;
 transition:transform .7s cubic-bezier(.3,1.3,.5,1);background:#fff;color:var(--ink);box-shadow:0 6px 0 rgba(0,0,0,.15)}
.face.back{transform:rotateY(180deg);font-size:.97rem}
.room.flipped .front{transform:rotateY(-180deg)}.room.flipped .back{transform:rotateY(0)}
.room .rw{font-family:var(--scripts);font-size:2.2rem;font-weight:800;margin:0;line-height:1.2}
.r-hindu .front{background:#ffe7c2}.r-buddhist .front{background:#ffd3a1}.r-jain .front{background:#e3f4e9}
.r-sikh .front{background:#e2e9ff}.r-thai .front{background:#ffe0ec}
.turn{margin-top:auto;align-self:flex-start;background:var(--ink);color:#fff;border:0;border-radius:99px;padding:6px 16px;cursor:pointer;min-height:40px}
.face p{margin:.4em 0 1em}
.pond{height:44px;border-radius:12px;background:linear-gradient(180deg,#9ee3f0,#3aa7c9);position:relative;overflow:hidden;margin:10px 0}
.fish{position:absolute;top:6px;font-size:26px;inset-inline-start:6px;transform:scaleX(-1)}
.room.flipped .pond.on .fish{animation:swim 4s linear infinite}
@keyframes swim{0%{inset-inline-start:-10%}100%{inset-inline-start:100%}}
.jtoggle{font-size:.85rem;padding:6px 14px;min-height:40px}
.tw{list-style:none;padding:0;margin:8px 0 0;display:grid;gap:6px}
.tw li{background:#fff4f8;border-radius:10px;padding:6px 10px;font-size:.85rem;line-height:1.35}
.tw b{font-size:1.3rem;font-family:"Noto Sans Thai",sans-serif;display:block}
.tw em{font-style:normal;color:var(--red);background:#ffe27a;border-radius:4px;padding:0 2px}
.tw small{color:var(--muted);margin-inline-end:6px}

/* wheel */
.wheelbox{text-align:center;position:relative}
.pointer{color:var(--gold);font-size:2rem;line-height:1;margin-bottom:-8px;position:relative;z-index:1}
#wheelsvg{width:min(86vw,360px);height:auto;touch-action:none;cursor:grab;filter:drop-shadow(0 8px 18px rgba(0,0,0,.35))}
#wheelsvg .rim{fill:none;stroke:#f2b134;stroke-width:12}
#wheelsvg .rim2{fill:none;stroke:#ffd76a;stroke-width:3}
#wheelsvg .spk{stroke:#f2b134;stroke-width:7;stroke-linecap:round}
#wheelsvg .hub{fill:#f2b134;stroke:#ffd76a;stroke-width:3}
#wheelsvg .num{fill:#8e0b20;font:800 15px var(--disp);text-anchor:middle;dominant-baseline:central}
#wheelsvg .knob{fill:#ffd76a}
#wheelsvg .badge{fill:#ffd76a;stroke:#8e0b20;stroke-width:2}
.spokes{columns:2;column-gap:20px;padding-inline-start:0;list-style:none;font-size:.95rem}
.spokes li{break-inside:avoid;padding:3px 8px;border-radius:8px;display:grid;grid-template-columns:1.5em 1fr;cursor:pointer}
.spokes li b{color:var(--gold)}
.spokes li.on{background:var(--gold);color:#2a140e}
.spokes li.on b{color:#8e0b20}
.spokesay{min-height:6em;margin-top:12px;background:rgba(0,0,0,.25);border-radius:16px;padding:12px 16px;text-align:start}
.spokesay:empty{visibility:hidden}
.spokesay b{font-family:var(--disp);font-size:1.4rem;display:block}
.spokesay i{opacity:.8}

/* day */
.day{background:#fff;border-radius:24px;padding:20px;margin-top:22px;box-shadow:0 6px 0 rgba(0,0,0,.08)}
.sky{position:relative;height:230px;border-radius:18px;overflow:hidden;transition:background 1s;padding:16px;color:#fff}
.orb{position:absolute;width:46px;height:46px;border-radius:50%;background:#ffe27a;box-shadow:0 0 40px 10px rgba(255,226,122,.7);transition:background .6s}
.clock{font-family:var(--disp);font-size:2.4rem;position:relative;text-shadow:0 2px 8px rgba(0,0,0,.4)}
.now{position:absolute;inset-inline:16px;bottom:12px;margin:0;font-size:1.02rem;line-height:1.45;text-shadow:0 1px 6px rgba(0,0,0,.7)}
#dayr{width:100%;margin:16px 0 4px;accent-color:var(--red);height:32px}
.moon{font-weight:600;margin:.6em 0 0}

/* gallery */
.gallery{background:#2a140e;color:#fff;padding:36px 0 30px}
.gallery .gt{max-width:1040px;margin:0 auto 12px;padding:0 16px}
.strip{display:flex;gap:12px;overflow-x:auto;scroll-snap-type:x mandatory;padding:0 16px 12px}
.strip figure{flex:0 0 min(78vw,420px);margin:0;scroll-snap-align:start}
.strip img{width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:14px}
.strip figcaption{font-size:.9rem;padding:6px 2px;line-height:1.4}
.strip figcaption small{display:block;opacity:.7;font-size:.72rem}
.strip figcaption a{color:#ffd88a}

/* sand */
#sandsvg{width:100%;max-width:440px;margin:0 auto;display:block;cursor:pointer;touch-action:manipulation}
#sandsvg .ground{fill:#d9b77c}
#pile{fill:#e8c98a;stroke:#c9a35e;stroke-width:2}
.grain{fill:#c9a35e}
.count{font-family:var(--disp);font-size:1.5rem;font-weight:800;color:var(--red2)}

/* sticks */
.cupbox{text-align:center}
#cup{width:210px;height:auto;display:block;margin:0 auto 10px}
#cup .cupb{fill:#b5651d;stroke:#7a3f0c;stroke-width:3}
#cup .cupr{fill:#7a3f0c}
#cup .stk{fill:#f3d9a4;stroke:#b98a3c;stroke-width:1.5}
#cup .stkt{fill:#c8102e}
#cup.shaking{animation:shake .12s linear 9;transform-origin:50% 90%}
@keyframes shake{0%{transform:rotate(-8deg)}50%{transform:rotate(8deg)}100%{transform:rotate(-8deg)}}
.outstick{opacity:0;transition:transform .8s cubic-bezier(.3,1.4,.5,1),opacity .3s}
.outstick rect{fill:#fff1cf;stroke:#b98a3c;stroke-width:2}
.outstick text{fill:#c8102e;font:800 19px var(--disp);text-anchor:middle}
.outstick .tip{fill:#c8102e;stroke:none}
.outstick.up{opacity:1;transform:translate(14px,-84px) rotate(9deg)}
.verse{background:#fffaf0;border-radius:20px;margin:26px 0 0;padding:22px 24px;border-inline-start:8px solid var(--red);font-size:1.15rem;box-shadow:0 6px 0 rgba(0,0,0,.1)}
.verse .vn{font-family:var(--disp);font-weight:800;color:var(--red);display:block;font-size:1.3rem}
.verse cite{display:block;font-size:.85rem;opacity:.75;margin-top:10px;font-style:normal}

/* tham */
.glass .stats{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));margin:24px 0}
.glass .stats div{background:rgba(0,0,0,.5);border-radius:18px;padding:14px 16px;backdrop-filter:blur(3px)}
.glass .stats b{display:block;font-family:var(--disp);font-size:2.6rem;color:#ffd76a;line-height:1.1}

/* neighbours */
.nbs{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));margin-top:18px}
.nb{background:#fff;color:var(--ink);border:0;border-radius:18px;padding:16px;text-align:start;cursor:pointer;box-shadow:0 5px 0 rgba(0,0,0,.25);min-height:110px}
.nb b{display:block;font-family:"Noto Sans","Noto Sans Hebrew","Noto Sans Arabic","Noto Sans SC",serif;font-size:1.4rem}
.nb small{color:var(--muted)}
.nb .say{display:none;margin-top:8px;font-size:.96rem;line-height:1.5}
.nb.open{background:#ffe7a8}.nb.open .say{display:block}

.links{padding-inline-start:20px}
.creds{font-size:.8rem;padding-inline-start:18px;opacity:.85}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}html{scroll-behavior:auto}}
</style>
</head><body>
{{BODY}}
<script id="dd" type="application/json">{{DATA}}</script>
<script>
(()=>{'use strict';
const D=JSON.parse(document.getElementById('dd').textContent),EN=D.en;let T=EN,LANG='en';
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const store={get(k){try{return localStorage.getItem(k)}catch(e){return null}},set(k,v){try{localStorage.setItem(k,v)}catch(e){}}};
const get=(o,p)=>p.split('.').reduce((a,k)=>a==null?a:a[k],o);
const fill=(s,v)=>s.replace(/\{(\w+)\}/g,(m,k)=>v&&k in v?v[k]:m);
const t=(p,v)=>{let s=get(T,p);if(s==null||s==='')s=get(EN,p);return s==null?'':(v?fill(s,v):s)};
const fmt=n=>n.toLocaleString(LANG==='en'?'en-US':LANG);

/* ---------- sound: synthesised, made on the first tap ---------- */
let AC=null;const ac=()=>{if(!AC){try{AC=new (window.AudioContext||window.webkitAudioContext)()}catch(e){}}if(AC&&AC.state==='suspended')AC.resume();return AC};
function bell(f,vol=.32,len=3.2){const a=ac();if(!a)return;const t0=a.currentTime,g=a.createGain();g.connect(a.destination);
 g.gain.setValueAtTime(0,t0);g.gain.linearRampToValueAtTime(vol,t0+.01);g.gain.exponentialRampToValueAtTime(.0008,t0+len);
 [[1,1],[2.01,.45],[2.76,.32],[5.4,.16],[8.93,.08]].forEach(([r,amp])=>{const o=a.createOscillator(),og=a.createGain();o.frequency.value=f*r;og.gain.value=amp;
  og.gain.setValueAtTime(amp,t0);og.gain.exponentialRampToValueAtTime(.0005,t0+len/(r*.6+.4));o.connect(og).connect(g);o.start(t0);o.stop(t0+len)})}
function drum(){const a=ac();if(!a)return;const t0=a.currentTime;for(let i=0;i<3;i++){const o=a.createOscillator(),g=a.createGain();const s=t0+i*.55;
 o.frequency.setValueAtTime(120,s);o.frequency.exponentialRampToValueAtTime(48,s+.4);g.gain.setValueAtTime(.7,s);g.gain.exponentialRampToValueAtTime(.001,s+.6);o.connect(g).connect(a.destination);o.start(s);o.stop(s+.7)}}
function tick(){const a=ac();if(!a)return;const o=a.createOscillator(),g=a.createGain(),t0=a.currentTime;o.type='triangle';o.frequency.value=1800;
 g.gain.setValueAtTime(.08,t0);g.gain.exponentialRampToValueAtTime(.001,t0+.05);o.connect(g).connect(a.destination);o.start(t0);o.stop(t0+.06)}
function pour(){const a=ac();if(!a)return;const t0=a.currentTime,n=a.sampleRate*.5,b=a.createBuffer(1,n,a.sampleRate),d=b.getChannelData(0);
 for(let i=0;i<n;i++)d[i]=(Math.random()*2-1)*(1-i/n);const s=a.createBufferSource(),f=a.createBiquadFilter(),g=a.createGain();s.buffer=b;f.type='bandpass';f.frequency.value=2400;g.gain.value=.25;s.connect(f).connect(g).connect(a.destination);s.start(t0)}
function rattle(){const a=ac();if(!a)return;for(let i=0;i<10;i++){const o=a.createOscillator(),g=a.createGain(),s=a.currentTime+i*.11;o.type='square';o.frequency.value=600+Math.random()*500;
 g.gain.setValueAtTime(.05,s);g.gain.exponentialRampToValueAtTime(.001,s+.05);o.connect(g).connect(a.destination);o.start(s);o.stop(s+.06)}}
const SCALE=[0,2,4,7,9];const pitch=i=>392*Math.pow(2,(SCALE[i%5]+12*Math.floor(i/5))/12)/1.5;

/* ---------- hero word ---------- */
let hi=0;const hw=$('#heroword');hw.addEventListener('click',()=>{hi=(hi+1)%D.hero.length;hw.textContent=D.hero[hi];bell(pitch(hi%10),.2,2.2)});
setInterval(()=>{if(document.hidden||matchMedia('(prefers-reduced-motion: reduce)').matches)return;if(window.scrollY>innerHeight)return;hi=(hi+1)%D.hero.length;hw.textContent=D.hero[hi]},2600);

/* ---------- bells ---------- */
const say=$('#bellsay');
function ringBell(btn,quiet){const i=+btn.dataset.n,b=D.bells[i];btn.classList.remove('ring');void btn.offsetWidth;btn.classList.add('ring');bell(pitch(i));
 if(!quiet){say.innerHTML='';const w=document.createElement('b');w.textContent=b.w;const r=document.createElement('i');r.textContent=b.r+' — ';
  const p=document.createElement('span');p.textContent=t('bells.'+b.k);say.append(w,r,p);say.dataset.k=b.k}}
$$('.bell').forEach(b=>b.addEventListener('click',()=>ringBell(b)));
$('#ringall').addEventListener('click',()=>{$$('.bell').forEach((b,i)=>setTimeout(()=>ringBell(b,true),i*170))});

/* ---------- rooms ---------- */
$$('.room').forEach(r=>r.querySelectorAll('.turn').forEach(b=>b.addEventListener('click',()=>{r.classList.toggle('flipped');tick()})));
const jt=$('.jtoggle'),pond=$('.pond');let jon=true;if(pond)pond.classList.add('on');
const jtext=()=>{const i=EN.rooms.findIndex(r=>r.id==='jain');jt.textContent=t('rooms.'+i+(jon?'.toy_on':'.toy_off'))};
if(jt)jt.addEventListener('click',()=>{jon=!jon;pond.classList.toggle('on',jon);jt.setAttribute('aria-pressed',jon);jtext()});

/* ---------- wheel ---------- */
const NS='http://www.w3.org/2000/svg',wh=$('#wh'),svg=$('#wheelsvg');
const mk=(n,a)=>{const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);return e};
wh.append(mk('circle',{r:96,class:'rim'}),mk('circle',{r:86,class:'rim2'}));
for(let i=0;i<8;i++){const a=(i*45-90)*Math.PI/180,x=Math.cos(a),y=Math.sin(a);
 wh.append(mk('line',{x1:x*18,y1:y*18,x2:x*90,y2:y*90,class:'spk'}),mk('circle',{cx:x*103,cy:y*103,r:7,class:'knob'}));
 wh.append(mk('circle',{cx:x*62,cy:y*62,r:13,class:'badge'}));const tx=mk('text',{x:x*62,y:y*62,class:'num'});tx.textContent=i+1;wh.append(tx)}
wh.append(mk('circle',{r:20,class:'hub'}),mk('circle',{r:7,fill:'#8e0b20'}));
let ang=0,vel=0,raf=0,lastIdx=0,drag=null;
const idx=()=>((Math.round(-ang/45)%8)+8)%8;
function draw(){wh.setAttribute('transform','rotate('+ang+')');const i=idx();if(i!==lastIdx){lastIdx=i;tick()}}
function show(){const i=idx();$$('#spokes li').forEach(l=>l.classList.toggle('on',+l.dataset.s===i));
 const s=$('#spokesay');s.innerHTML='';const b=document.createElement('b');b.textContent=(i+1)+'. '+t('spokes.'+i+'.en');
 const p=document.createElement('i');p.textContent=EN.spokes[i].pali;const q=document.createElement('p');q.style.margin='.3em 0 0';q.textContent=t('spokes.'+i+'.say');s.append(b,p,q);s.dataset.i=i}
function run(){vel*=.978;ang+=vel;draw();if(Math.abs(vel)>.04){raf=requestAnimationFrame(run)}else{const target=-idx()*45;const d=((target-ang)%360+540)%360-180;
 const st=ang;let k=0;const snap=()=>{k+=.12;ang=st+d*Math.min(1,k);draw();if(k<1)requestAnimationFrame(snap);else show()};snap()}}
$('#spin').addEventListener('click',()=>{ac();cancelAnimationFrame(raf);vel=14+Math.random()*12;run()});
const pa=e=>{const r=svg.getBoundingClientRect();return Math.atan2(e.clientY-r.top-r.height/2,e.clientX-r.left-r.width/2)*180/Math.PI};
svg.addEventListener('pointerdown',e=>{ac();cancelAnimationFrame(raf);drag={a:pa(e),t:performance.now()};vel=0;svg.setPointerCapture(e.pointerId)});
svg.addEventListener('pointermove',e=>{if(!drag)return;const a=pa(e);let d=a-drag.a;if(d>180)d-=360;if(d<-180)d+=360;const now=performance.now();
 ang+=d;vel=d/Math.max(1,(now-drag.t))*16;drag={a,t:now};draw()});
const up=()=>{if(!drag)return;drag=null;run()};svg.addEventListener('pointerup',up);svg.addEventListener('pointercancel',up);
$$('#spokes li').forEach(l=>l.addEventListener('click',()=>{ang=-(+l.dataset.s)*45;draw();show()}));
draw();

/* ---------- a day at the wat ---------- */
const dr=$('#dayr'),sky=$('#sky'),orb=$('#orb'),clk=$('#clock'),dn=$('#daynow');let slot=-1,heard=false;
const mins=s=>{const[h,m]=s.split(':');return +h*60+ +m};
const SK=[[270,'#1b1b4a','#3b2a6b'],[360,'#f7a35c','#ffd9a0'],[480,'#59b7f0','#bfe8ff'],[720,'#2f9be8','#a9dcff'],[960,'#f0a04b','#ffd27a'],[1080,'#d9475a','#5b2a6e'],[1200,'#141a3d','#28205a'],[1260,'#0d1030','#1d1846']];
const mix=(a,b,f)=>{const p=h=>[1,3,5].map(i=>parseInt(h.substr(i,2),16));const x=p(a),y=p(b);return'rgb('+x.map((v,i)=>Math.round(v+(y[i]-v)*f)).join(',')+')'};
function day(){const v=+dr.value;let i=0;while(i<SK.length-2&&v>SK[i+1][0])i++;const f=Math.min(1,Math.max(0,(v-SK[i][0])/(SK[i+1][0]-SK[i][0])));
 sky.style.background='linear-gradient(180deg,'+mix(SK[i][1],SK[i+1][1],f)+','+mix(SK[i][2],SK[i+1][2],f)+')';
 const sun=v>=360&&v<=1110,u=sun?(v-360)/750:((v<360?v+1440:v)-1110)/690;
 orb.style.left=(6+u*80)+'%';orb.style.top=(70-Math.sin(u*Math.PI)*58)+'%';orb.style.background=sun?'#ffe27a':'#f4f1de';orb.style.boxShadow=sun?'':'0 0 24px 4px rgba(255,255,255,.4)';
 clk.textContent=String(Math.floor(v/60)).padStart(2,'0')+':'+String(v%60).padStart(2,'0');
 let s=0;EN.day.forEach((d,j)=>{if(v>=mins(d.t))s=j});dn.textContent=t('day.'+s+'.what');
 if(s!==slot){const was=slot;slot=s;if(heard&&was!==-1){const tt=EN.day[s].t;if(tt==='04:30'||tt==='18:00')bell(196,.35,4);else if(tt==='11:00')drum();}}}
dr.addEventListener('input',()=>{heard=true;day()});dr.addEventListener('pointerdown',()=>ac());
{const d=new Date(),m=d.getHours()*60+d.getMinutes();dr.value=Math.min(1260,Math.max(270,m))}day();
function moon(){const age=((Date.now()/864e5-10962.76)%29.530588853+29.530588853)%29.530588853,wax=age<14.765;
 const d=Math.min(15,Math.floor(wax?age:age-14.765)+1);let s=t('moon_now',{phase:t(wax?'moon_waxing':'moon_waning'),d:fmt(d)});
 if(d===8||d>=14)s+=' '+t('moon_near');$('#moon').textContent='🌙 '+s}moon();

/* ---------- sand chedi ---------- */
const pile=$('#pile'),grains=$('#grains'),flags=$('#flags'),sc=$('#sandcount');let bk=0;const MAX=12,cx=160;
const W=()=>50+bk*13,H=()=>bk*12.5;
const surf=x=>{const w=W()/2,h=H();const u=Math.abs(x-cx)/w;return 200-h*Math.pow(Math.max(0,1-u),1.25)};
function drawPile(){if(!bk){pile.setAttribute('d','');return}const w=W()/2,pts=[];for(let k=0;k<=40;k++){const x=cx-w+k*(2*w/40);pts.push(x.toFixed(1)+','+surf(x).toFixed(1))}
 pile.setAttribute('d','M'+pts.join(' L')+' Z');sc.dataset.v=JSON.stringify({n:fmt(bk)});sc.textContent=bk>=MAX?t('sand_done'):t('sand_count',{n:fmt(bk)})}
function plant(x){const y=surf(x),c=['#c8102e','#2350b8','#16936a','#f2b134','#e8478b','#f28c28','#7b3fc4'][Math.floor(Math.random()*7)];
 const g=mk('g',{});g.append(mk('line',{x1:x,y1:y,x2:x,y2:y-34,stroke:'#6b4a1f','stroke-width':2}),mk('path',{d:`M${x} ${y-34} l18 6 l-18 6z`,fill:c}));flags.append(g);tick()}
$('#carry').addEventListener('click',()=>{if(bk>=MAX){plant(cx+(Math.random()-.5)*W()*.8);return}pour();
 for(let k=0;k<14;k++){const c=mk('circle',{cx:cx+(Math.random()-.5)*20,cy:0,r:2.2,class:'grain'});grains.append(c);
  const tgt=surf(cx)-2,dl=k*25;c.animate([{transform:'translateY(0)'},{transform:`translateY(${tgt}px)`}],{duration:520,delay:dl,easing:'ease-in',fill:'forwards'}).onfinish=()=>c.remove()}
 setTimeout(()=>{bk++;drawPile();if(bk===MAX){bell(523,.25);plant(cx)}},560)});
$('#sandsvg').addEventListener('click',e=>{if(bk<MAX)return;const r=e.currentTarget.getBoundingClientRect(),x=(e.clientX-r.left)/r.width*320;
 if(Math.abs(x-cx)<W()/2*.9)plant(x)});
$('#sandreset').addEventListener('click',()=>{bk=0;flags.innerHTML='';drawPile();sc.textContent=t('sand_count',{n:fmt(0)})});
drawPile();sc.textContent=t('sand_count',{n:fmt(0)});

/* ---------- siam si ---------- */
const VK=Object.keys(EN.verses).sort((a,b)=>a-b),stk=$('#stickset');
for(let i=0;i<13;i++){const x=40+i*6.5,h=70+((i*37)%22);stk.append(mk('rect',{x,y:100-h,width:5,height:h+40,rx:2,class:'stk',transform:`rotate(${(i-6)*2.4} ${x} 200)`}),mk('rect',{x,y:100-h,width:5,height:8,class:'stkt',transform:`rotate(${(i-6)*2.4} ${x} 200)`}))}
const cup=$('#cup'),out=$('#out'),vb=$('#verse');let busy=false,last=-1,cur=-1;
function verseShow(){if(cur<0)return;const k=VK[cur];vb.hidden=false;vb.innerHTML='';const n=document.createElement('span');n.className='vn';n.textContent=t('sticks_num',{n:fmt(cur+1)});
 const p=document.createElement('p');p.style.margin='.2em 0';p.textContent=t('verses.'+k);const c=document.createElement('cite');
 c.textContent=t('sticks_src',{v:k})+(LANG!=='en'?' '+t('sticks_tr'):'')+(k==='354'?' '+t('verse354_note'):'');vb.append(n,p,c)}
function shake(){if(busy)return;busy=true;out.classList.remove('up');cup.classList.add('shaking');rattle();
 setTimeout(()=>{cup.classList.remove('shaking');do{cur=Math.floor(Math.random()*VK.length)}while(cur===last);last=cur;$('#outn').textContent=cur+1;out.classList.add('up');tick();verseShow();
  $('#shake').lastChild.textContent=t('sticks_again');$('#shake').lastChild.dataset.i='sticks_again';busy=false},1150)}
$('#shake').addEventListener('click',()=>{ac();shake();askMotion()});
let motionAsked=false;function askMotion(){if(motionAsked||typeof DeviceMotionEvent==='undefined')return;motionAsked=true;
 const go=()=>{let lastS=0;addEventListener('devicemotion',e=>{const a=e.accelerationIncludingGravity;if(!a)return;const m=Math.hypot(a.x||0,a.y||0,a.z||0);
  const r=$('#sticks').getBoundingClientRect();if(m>24&&Date.now()-lastS>2500&&r.top<innerHeight&&r.bottom>0){lastS=Date.now();shake()}})};
 if(typeof DeviceMotionEvent.requestPermission==='function')DeviceMotionEvent.requestPermission().then(s=>{if(s==='granted')go()}).catch(()=>{});else go()}
if(matchMedia('(pointer:coarse)').matches&&typeof DeviceMotionEvent!=='undefined')$('.motionhint').hidden=false;

/* ---------- neighbours ---------- */
$$('.nb').forEach(b=>b.addEventListener('click',()=>{b.classList.toggle('open');b.setAttribute('aria-expanded',b.classList.contains('open'))}));

/* ---------- language ---------- */
const NAMES={};$$('#langs button').forEach(b=>NAMES[b.dataset.lang]=b.textContent);
const FONTS={zh:'Noto+Sans+SC:wght@400;700',ja:'Noto+Sans+JP:wght@400;700',ko:'Noto+Sans+KR:wght@400;700',hi:'Noto+Sans+Devanagari:wght@400;700',
 my:'Noto+Sans+Myanmar:wght@400;700',he:'Noto+Sans+Hebrew:wght@400;700&family=Rubik:wght@500;800',ru:'Rubik:wght@500;800',th:'Mali:wght@600;700'};
const loaded={en:EN};
function font(l){if(!FONTS[l]||document.getElementById('f-'+l))return;const k=document.createElement('link');k.rel='stylesheet';k.id='f-'+l;
 k.href='https://fonts.googleapis.com/css2?family='+FONTS[l]+'&display=swap';document.head.append(k)}
function apply(){document.documentElement.lang=LANG;document.documentElement.dir=LANG==='he'?'rtl':'ltr';
 $$('[data-i]').forEach(el=>{let s=t(el.dataset.i);if(!s)return;if(el.dataset.v){try{s=fill(s,JSON.parse(el.dataset.v))}catch(e){}}el.textContent=s});
 document.title=t('meta_title');$('#langnow').textContent=NAMES[LANG]||LANG;
 $$('#langs button').forEach(b=>b.toggleAttribute('aria-current',b.dataset.lang===LANG));
 if(say.dataset.k){say.lastChild.textContent=t('bells.'+say.dataset.k)}
 if($('#spokesay').dataset.i!=null)show();day();moon();verseShow();if(jt)jtext();
 sc.textContent=bk>=MAX?t('sand_done'):t('sand_count',{n:fmt(bk)})}
async function setLang(l){if(!D.langs.includes(l))l='en';font(l);
 if(!loaded[l]){try{const r=await fetch('i18n/'+l+'.json');if(!r.ok)throw 0;loaded[l]=await r.json()}catch(e){l='en'}}
 LANG=l;T=loaded[l];store.set('dharma-lang',l);apply();
 const u=new URL(location);if(l==='en')u.searchParams.delete('lang');else u.searchParams.set('lang',l);history.replaceState(null,'',u)}
const lb=$('#langbtn'),ll=$('#langs');lb.addEventListener('click',()=>{ll.hidden=!ll.hidden;lb.setAttribute('aria-expanded',!ll.hidden)});
ll.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;ll.hidden=true;lb.setAttribute('aria-expanded','false');setLang(b.dataset.lang)});
document.addEventListener('click',e=>{if(!e.target.closest('.lang'))ll.hidden=true});
const want=new URLSearchParams(location.search).get('lang')||store.get('dharma-lang')||(navigator.languages||[navigator.language||'en']).map(x=>x.slice(0,2).toLowerCase()).find(x=>D.langs.includes(x))||'en';
if(want!=='en')setLang(want);
})();
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
        raise SystemExit(f"dharma: docs directory not found: {docs}")
    en = json.loads((DATA / "i18n" / "en.json").read_text(encoding="utf-8"))
    cred = {c["id"]: c for c in json.loads((DATA / "credits.json").read_text(encoding="utf-8"))}
    n = counts()
    site = a.site_url.rstrip("/")
    out = docs / "dharma"
    (out / "img").mkdir(parents=True, exist_ok=True)
    (out / "i18n").mkdir(exist_ok=True)
    for p in (DATA / "img").glob("*.jpg"):
        shutil.copyfile(p, out / "img" / p.name)
    langs = []
    for k, _ in LANGS:
        src = DATA / "i18n" / f"{k}.json"
        if src.exists():
            shutil.copyfile(src, out / "i18n" / src.name)
            langs.append(k)
    shutil.copyfile(DATA / "card.jpg", out / "card.jpg")
    (out / "index.html").write_text(render(en, n, cred, site, langs), encoding="utf-8")
    print(f"dharma: /dharma written — {n['tham']:,} of {n['total']:,} in tham, "
          f"{len(langs)} languages, {len(list((out / 'img').glob('*.jpg')))} images")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
