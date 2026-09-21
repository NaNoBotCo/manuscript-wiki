#!/usr/bin/env python3
"""lexicon_page — the entry page, and the /roots index.

The sense map is the point of the page, so it is built from ordered HTML —
headings, lists, a definition table — and never from a canvas. atlas.py already
settled the rule for this project: a canvas is invisible to a screen reader and
useless at 400% zoom, so the structure has to carry the meaning on its own. The
EXTENDS chain is rendered as a sentence attached to each sense ("grew out of
sense 3, by metaphor: …") rather than as arrows, because that sentence is the
thing a reader actually takes away.

Confidence is shown, not hidden. Every asserted claim carries its `conf` as a
visible chip, and the open questions from `needs_check` are printed at the foot
of the entry under their own heading. A dictionary that hides what it has not
checked is harder to correct.
"""
from __future__ import annotations

import html
import json

PALETTE = """
 :root{--bg:#f4efe3;--panel:#fdfbf5;--ink:#26302a;--muted:#6d6455;--gold:#a8791e;
  --gold-soft:#c9a24a;--crimson:#8c3b2e;--line:#e5dcc7;
  --serif:"Sukhumvit Set","Noto Serif Thai",Thonburi,"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
  --sans:"Sukhumvit Set","Noto Sans Thai",Thonburi,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
  font-family:var(--sans);font-size:18px;line-height:1.65}
 a{color:var(--crimson);text-decoration:none}a:hover{text-decoration:underline}
 .wrap{max-width:900px;margin:0 auto;padding:0 24px 72px}
 header{text-align:center;padding:48px 24px 12px}
 .mark{font-family:var(--serif);letter-spacing:.4em;color:var(--gold);font-size:13px}
 h1{font-family:var(--serif);font-size:clamp(34px,7vw,58px);margin:10px 0 4px}
 .rom{color:var(--muted);font-size:19px;letter-spacing:.02em}
 .core{font-family:var(--serif);font-style:italic;font-size:clamp(19px,3vw,25px);
   color:#3c463f;max-width:620px;margin:18px auto 0}
 .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;
   padding:20px 22px;margin:18px 0}
 h2{font-family:var(--serif);font-size:23px;margin:34px 0 10px;color:var(--gold)}
 .sense{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--gold-soft);
   border-radius:12px;padding:18px 22px;margin:16px 0}
 .sense h3{font-family:var(--serif);font-size:22px;margin:0 0 6px;display:flex;
   flex-wrap:wrap;gap:10px;align-items:baseline}
 .n{color:var(--gold);font-size:15px;font-weight:700;min-width:1.6em}
 .glth{color:var(--muted);font-size:16.5px;margin:2px 0 8px}
 .chip{display:inline-block;font-size:12.5px;padding:2px 9px;border-radius:999px;
   border:1px solid var(--line);background:#fff;color:var(--muted);margin:0 4px 4px 0}
 .chip.c-verified{border-color:#7fb3a8;color:#3f6f66}
 .chip.c-standard{border-color:var(--gold-soft);color:#8a6a1c}
 .chip.c-probable,.chip.c-traditional{border-color:#c98b5e;color:#8f5a33}
 .chip.c-disputed,.chip.c-unverified{border-color:var(--crimson);color:var(--crimson)}
 .via{border-left:3px solid var(--line);padding:2px 0 2px 14px;margin:10px 0;
   color:#4a5450;font-size:16.5px}
 .via b{color:var(--gold)}
 table{border-collapse:collapse;width:100%;margin:12px 0;font-size:16.5px}
 th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
 th{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:600}
 td.th{font-size:19px;white-space:nowrap}
 .lit{color:var(--muted);font-style:italic;font-size:15.5px}
 .note{color:#4a5450;font-size:15.5px;margin-top:4px}
 .cult{background:#f7f2e4;border-radius:10px;padding:12px 15px;margin:12px 0;font-size:16.5px}
 ul.plain{list-style:none;padding-left:0}ul.plain li{margin:8px 0}
 .open li{margin:9px 0;color:#4a5450;font-size:16.5px}
 footer{border-top:1px solid var(--line);margin-top:44px;padding-top:18px;
   color:var(--muted);font-size:14.5px}
 @media(max-width:620px){body{font-size:17px}.wrap{padding:0 16px 56px}
   td.th{white-space:normal}}
"""

CONF_TH = {"verified": "ตรวจแล้ว", "standard": "ทั่วไป", "probable": "น่าจะใช่",
           "traditional": "ตามประเพณี", "disputed": "ยังถกเถียง", "unverified": "ยังไม่ตรวจ"}
VIA_TH = {"metaphor": "อุปมา", "metonymy": "นามนัย", "specialisation": "แคบลง",
          "generalisation": "กว้างขึ้น", "euphemism": "คำเลี่ยง", "calque": "แปลตรง"}


def rom_of(d):
    """What to SHOW: the real romanisation, never the URL slug — the slug may
    carry a -2 disambiguator that is not part of how the word is written."""
    return d.get("rtgs") or d.get("translit_auto") or ""


def handle(d):
    """URL handle from the id — `rtgs` collides across homographs. See lexicon.handle."""
    if d.get("id", "").startswith("w:"):
        return d["id"][2:]
    return d.get("rtgs") or d.get("translit_auto") or "x"


def e(s):
    return html.escape(str(s or ""), quote=True)


def chip(txt, cls=""):
    return f'<span class="chip {cls}">{e(txt)}</span>'


def conf_chip(c):
    return chip(f"{c} · {CONF_TH.get(c, '')}".strip(" ·"), f"c-{c}") if c else ""


def _compounds(cs):
    if not cs:
        return ""
    rows = []
    for c in cs:
        en = [x for x in c["gloss"]["en"] if not x.startswith("[")]
        g = "; ".join(en)
        lit = f'<div class="lit">lit. {e(c["lit"])}</div>' if c.get("lit") else ""
        if c.get("lit_th"):
            lit += f'<div class="lit">{e(c["lit_th"])}</div>'
        if c.get("pattern"):
            lit += chip(c["pattern"])
        if c.get("cross_listed"):
            lit += ('<div class="note">also filed under '
                    + ", ".join(e(x) for x in c["cross_listed"]) + "</div>")
        note = f'<div class="note">{e(c.get("note"))}</div>' if c.get("note") else ""
        used = chip(c["use"]) if c.get("use") else ""
        if c.get("frame"):
            used += chip(c["frame"], "ok")
        if c.get("flips_with"):
            used += ('<div class="note">flips with <b>' + e(c["flips_with"])
                     + "</b> — the same two morphemes the other way round, "
                     "and a different kind of thing</div>")
        flags = used + "".join(chip(x) for x in (
            ["phrase"] if c.get("is_phrase") else []) + (
            ["name"] if c.get("is_name") else []) + (
            ["classifier"] if c.get("is_classifier_use") else []))
        th_gloss = (c["gloss"].get("th") or "").strip()
        if not g and th_gloss:
            body = f'<span class="glth">{e(th_gloss)}</span>'
        elif g and th_gloss:
            body = f'{e(g)}<div class="lit">{e(th_gloss)}</div>'
        else:
            body = e(g) or '<span class="lit">ยังไม่มีคำแปล · no gloss yet</span>'
        rows.append(
            f'<tr><td class="th">{e(c["th"])}<div class="lit">{e(rom_of(c))}</div></td>'
            f'<td>{body}{lit}{note}{flags}{conf_chip(c.get("conf"))}</td></tr>')
    return ('<table><thead><tr><th class="pt-skip">คำประกอบ · compound</th>'
            '<th>meaning, and why</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table>")


def _sense(s, senses_by_n):
    en = [x for x in s["gloss"]["en"] if not x.startswith("[")]
    g = "; ".join(en) or (s["gloss"].get("th") or "").strip()[:90]
    out = [f'<section class="sense" id="s{s["n"]}">',
           f'<h3><span class="n">{s["n"]}</span><span>{e(g)}</span></h3>']
    if s["gloss"].get("th"):
        out.append(f'<div class="glth">{e(s["gloss"]["th"])}</div>')
    out.append("".join(chip(r.split(":", 1)[-1]) for r in s.get("register", []))
               + "".join(chip(d.split(":", 1)[-1]) for d in s.get("domains", []))
               + conf_chip(s.get("conf")))
    if s.get("def"):
        out.append(f"<p>{e(s['def'])}</p>")
    if s.get("extends"):
        parent = senses_by_n.get(s["extends"], {})
        pg = "; ".join(parent.get("gloss", {}).get("en", []))
        via = s.get("via", "")
        out.append(
            f'<div class="via">grew out of <b>sense {s["extends"]}</b> ({e(pg)}) '
            f'— by <b>{e(via)}</b> · {e(VIA_TH.get(via, ""))}'
            + (f': {e(s["via_note"])}' if s.get("via_note") else "")
            + " " + conf_chip(s.get("via_conf")) + "</div>")
    if s.get("cultural"):
        out.append(f'<div class="cult">{e(s["cultural"])}</div>')
    if s.get("usage"):
        out.append(f'<div class="cult">{e(s["usage"])}</div>')
    if s.get("classifier"):
        out.append("<p class=\"note\">ลักษณนาม · classifier: "
                   + ", ".join(e(c) for c in s["classifier"]) + "</p>")
    out.append(_compounds(s.get("compounds")))
    for x in s.get("examples", []):
        out.append(f'<div class="via">{e(x["th"])}'
                   + (f' <span class="lit">{e(x.get("rtgs"))}</span>' if x.get("rtgs") else "")
                   + f'<br>{e(x["en"])}'
                   + (f'<div class="note">{e(x.get("note"))}</div>' if x.get("note") else "")
                   + "</div>")
    for ed in s.get("edges", []):
        out.append(f'<p class="note"><b>{e(ed["rel"].replace("_", " ").lower())}</b> '
                   f'{e(ed.get("label") or ed["to"])}'
                   + (f' — {e(ed.get("distinction") or ed.get("note"))}'
                      if ed.get("distinction") or ed.get("note") else "")
                   + " " + conf_chip(ed.get("conf")) + "</p>")
    for n in s.get("needs_check", []):
        out.append(f'<p class="note">⚑ open question: {e(n)}</p>')
    out.append("</section>")
    return "".join(out)


STATUS_BANNER = {
 "listed": ("ยังไม่จัดลำดับ · listed, not yet mapped",
   "The senses below are the RID's, in the RID's order — an editorial order, not "
   "an argument about how the meaning moved. No sense here has been said to grow "
   "out of another, and the attested compounds are still filed at the foot of the "
   "page rather than under the sense that motivates them. That ordering and that "
   "filing are the editorial work, and they have not been done for this word yet."),
 "mapped": ("จัดลำดับแล้ว · mapped",
   "The senses are ordered core-first as an argument about how the meaning moved, "
   "and every compound sits under the sense that motivates it."),
}


def _unassigned(cs):
    if not cs:
        return ""
    rows = "".join(
        f'<tr><td class="th">{e(c["th"])}'
        f'<div class="lit">{e(c.get("translit_auto") or c.get("rtgs") or "")}</div></td>'
        f'<td>{e("; ".join(x for x in c["gloss"]["en"] if not x.startswith("[")))}'
        + (f'<div class="lit">{e(c["gloss"].get("th",""))[:150]}</div>' if c["gloss"].get("th") else "")
        + (f'<div class="lit">{e(c["lit"])}</div>' if c.get("lit") else "")
        + (f'<div class="lit">{e(c["lit_th"])}</div>' if c.get("lit_th") else "")
        + (chip(c["frame"], "ok") if c.get("frame") else "")
        + (chip(c["pattern"]) if c.get("pattern") else "")
        + (f'<div class="note">flips with <b>{e(c["flips_with"])}</b> — the same two '
           f'morphemes the other way round, and a different kind of thing</div>'
           if c.get("flips_with") else "")
        + "</td></tr>" for c in cs)
    return (f'<h2>คำประกอบที่ยังไม่จัดเข้าความหมาย · compounds awaiting a sense '
            f'<span class="chip warn">{len(cs)}</span></h2>'
            '<p class="note">Every one is dictionary-attested: the word exists, and '
            'both of its parts are headwords. What has not been decided is which '
            'sense above each belongs to.</p>'
            '<div class="tscroll"><table><thead><tr><th class="pt-skip">คำ · word</th>'
            '<th>meaning</th></tr></thead><tbody>' + rows + "</tbody></table></div>")


def _wlist(ws, n=40):
    return " ".join(f'<span class="chip">{e(w)}</span>' for w in (ws or [])[:n])


def _hood(d, h):
    """The neighbourhood: where this word lives, rather than what it means.

    `found inside` is every word built on it. `the other way round` is the flip,
    where one exists — ใจดี and ดีใจ. `sounds identical` is the RTGS collision,
    which the site's own search collapses and which the reader must be warned of.
    `shares a half with` is the modifier family, and it exists in no source: the
    compounds that take the same other half. ดี gives ใจดี, หัวดี, คนดี, ของดี,
    ขวัญดี, น้ำดี, นาดี, ได้ดี — a heart, a head, a person, a thing, a soul, a
    bile, a field and a fortune, all good in the same grammatical way.
    """
    if not h:
        return ""
    out = ['<h2>ละแวกคำ · the neighbourhood</h2>']
    if h.get("inside"):
        out.append(f'<div class="card"><b class="pt-skip">พบใน · found inside</b> '
                   f'<span class="chip">{len(h["inside"])}</span>'
                   f'<div class="chips">{_wlist(h["inside"], 60)}</div></div>')
    if h.get("flips"):
        out.append('<div class="card"><b class="pt-skip">กลับกัน · the other way round</b>'
                   '<p class="note">The same two morphemes reversed, and a different '
                   'kind of thing — a property of a person against something that '
                   'befalls them.</p>'
                   f'<div class="chips">{_wlist(h["flips"])}</div></div>')
    if h.get("sounds_like"):
        out.append('<div class="card"><b class="pt-skip">เสียงพ้อง · sounds identical, is not this word</b>'
                   '<p class="note">RTGS drops tone, so these read the same and are not '
                   'the same. The site\'s own search collapses them.</p>'
                   f'<div class="chips">{_wlist(h["sounds_like"])}</div></div>')
    fam = h.get("family") or {}
    if fam:
        rows = "".join(
            f'<div style="margin:7px 0"><b>{e(m)}</b> &nbsp;{_wlist(ws, 12)}</div>'
            for m, ws in list(fam.items())[:8])
        out.append('<div class="card"><b class="pt-skip">ร่วมครึ่งคำ · shares a half with</b>'
                   '<p class="note">Compounds built on the same other half. This '
                   'grouping is in no dictionary; it falls out of the parts.</p>'
                   + rows + "</div>")
    return "".join(out)


def entry_page(d, site, hood=None):
    by_n = {s["n"]: s for s in d["senses"]}
    hood = hood or {}
    st = d.get("status", "listed")
    stitle, sbody = STATUS_BANNER.get(st, STATUS_BANNER["listed"])
    ety = d.get("etymology") or {}
    lan = d.get("lanna") or {}
    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "DefinedTerm",
        "name": d["th"], "alternateName": d.get("rtgs"),
        "description": d.get("core_image", ""),
        "inDefinedTermSet": f"{site}/roots/",
        "url": f"{site}/kham/{handle(d)}/",
    }, ensure_ascii=False)
    senses = "".join(_sense(s, by_n) for s in d["senses"])
    conf_edges = "".join(
        f'<li><b>{e(ed.get("label") or ed["to"])}</b> — {e(ed.get("note") or "")} '
        f'{chip(ed.get("why") or "")}{conf_chip(ed.get("conf"))}</li>'
        for ed in d.get("edges", []) if ed["rel"] == "CONFUSABLE_WITH")
    opens = "".join(f"<li>⚑ {e(n)}</li>" for n in d.get("needs_check", []))
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(d['th'])} · {e(handle(d))} — wichaa</title>
<meta name="description" content="{e(d['th'])} ({e(handle(d))}) — {e(d.get('core_image',''))}. {len(d['senses'])} senses, with the compounds each one carries and how the meaning moved between them.">
<link rel="canonical" href="{site}/kham/{e(handle(d))}/">
<meta property="og:type" content="article">
<meta property="og:title" content="{e(d['th'])} · {e(handle(d))} — {len(d['senses'])} senses">
<meta property="og:description" content="{e(d.get('core_image',''))}">
<meta property="og:image" content="{site}/og.jpg">
<script type="application/ld+json">{jsonld}</script>
<style>{PALETTE}</style>
<script src="/phasa/portal.js" defer></script></head><body>
<header>
 <div class="mark">พจนานุกรมราก</div>
 <h1>{e(d['th'])}</h1>
 <div class="rom">{" · ".join(x for x in [e(rom_of(d)), e(d.get("paiboon")), e(d.get("ipa")), e(d.get("tones"))] if x)}</div>
 {'<div class="rom">' + e(d.get('syllable_respelling')) + '</div>' if d.get('syllable_respelling') else ''}
 {'<div class="rom" style="color:var(--crimson)">romanisation below is a character walk, not RTGS</div>' if not d.get('rtgs') else ''}
 <div class="core">{e(d.get('core_image'))}</div>
 <div class="rom">{e(d.get('core_image_th'))}</div>
</header>
<div class="wrap">
 <p><a href="/roots/">← พจนานุกรมราก · the lexicon</a></p>
 <div class="card">
  <b class="pt-skip">ที่มา · etymology</b> {conf_chip(ety.get('conf'))}
  <p>{e(ety.get('summary'))}</p>
  <p class="glth">{e(ety.get('summary_th'))}</p>
  {'<p class="note"><b class="pt-skip">คำเมือง · Northern:</b> ' + e(lan.get('th')) + ' ' + e(lan.get('tham')) + ' — ' + e(lan.get('note')) + ' ' + conf_chip(lan.get('conf')) + '</p>' if lan else ''}
  {'<p class="note"><b class="pt-skip">สะกด · spelling:</b> ' + e(d.get('spelling_note')) + '</p>' if d.get('spelling_note') else ''}
 </div>
 <div class="card"><b>{e(stitle)}</b><p class="note">{e(sbody)}</p></div>
 <h2>ความหมาย · the senses</h2>
 <p class="note">Ordered core first, then what grew out of it. The order is an
 argument about how the meaning moved, not an alphabet.</p>
 {senses}
 {_unassigned(d.get("compounds_unassigned"))}
 {_hood(d, hood)}
 {'<h2>คำที่สับสนกันได้ · easily confused</h2><ul class="plain">' + conf_edges + '</ul>' if conf_edges else ''}
 {'<h2>ยังต้องตรวจ · open questions</h2><ul class="open">' + opens + '</ul>' if opens else ''}
 <footer>
  <b class="pt-skip">ที่มาข้อมูล · sources:</b> {e(', '.join(d.get('src', [])))} ·
  confidence is marked on every claim · corrections welcome.
  <br>RID = พจนานุกรมฉบับราชบัณฑิตยสถาน · WIKT = Wiktionary · CUR = editorial ·
  catalog.db, wat-registry and wichaa.segdict are this project's own counted data.
 </footer>
</div></body></html>"""


def index_page(entries, site):
    rows = "".join(
        f'<li><a href="/kham/{e(handle(d))}/"><span style="font-size:24px">{e(d["th"])}</span></a> '
        f'<span class="rom">{e(rom_of(d))}</span> — <i>{e(d.get("core_image") or "")}</i> '
        f'{chip(str(len(d["senses"])) + " senses")}</li>' for d in entries)
    n_sense = sum(len(d["senses"]) for d in entries)
    n_comp = sum(len(s.get("compounds", [])) for d in entries for s in d["senses"])
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>พจนานุกรมราก · the lexicon — wichaa</title>
<meta name="description" content="A sense-first dictionary of Thai: each word's meanings ordered core to figurative, every compound filed under the sense that motivates it, and every claim carrying its confidence.">
<link rel="canonical" href="{site}/roots/">
<meta property="og:type" content="website">
<meta property="og:title" content="พจนานุกรมราก · the lexicon">
<meta property="og:image" content="{site}/og.jpg">
<style>{PALETTE}</style></head><body>
<header>
 <div class="mark">พจนานุกรมราก</div>
 <h1>the lexicon</h1>
 <div class="core">Not what the word means — why it means that.</div>
</header>
<div class="wrap">
 <div class="card">
  <p>Each entry runs core sense first, then the senses that grew out of it, each
  one saying how it grew — by metaphor, by metonymy, by narrowing. Compounds are
  filed under the sense that motivates them rather than in one list, so the family
  visibly forks. Every claim carries its confidence, and what has not been checked
  is printed as an open question rather than left to look settled.</p>
  <p class="note">{len(entries)} entr{'y' if len(entries) == 1 else 'ies'} ·
  {n_sense} senses · {n_comp} compounds. Distinct from
  <a href="/glossary/">the glossary</a>, which is the tradition's discovered
  vocabulary with counts; this asks where the words come from.</p>
 </div>
 <h2>คำ · words</h2>
 <ul class="plain">{rows}</ul>
</div></body></html>"""


def namespace_page(entries, site):
    """/kham/ — the plain word list.

    Deliberately not a second copy of /roots. /roots is the door: it says what
    the dictionary is for and why the senses are ordered the way they are.
    This is the index a reader who already knows that wants — every word, in
    Thai alphabetical order, and nothing else. Each canonical to itself, so the
    two are not competing for the same query.
    """
    rows = "".join(
        f'<li><a href="/kham/{e(handle(d))}/">'
        f'<span style="font-size:23px">{e(d["th"])}</span></a> '
        f'<span class="rom">{e(rom_of(d))}</span> '
        f'{chip(str(len(d["senses"])) + " senses")}'
        f'<div class="lit">{e(d.get("core_image"))}</div></li>'
        for d in sorted(entries, key=lambda x: x["th"]))
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>คำทั้งหมด · all words — wichaa</title>
<meta name="description" content="Every word in the wichaa lexicon, in Thai alphabetical order, with its core image and how many senses it carries.">
<link rel="canonical" href="{site}/kham/">
<meta property="og:type" content="website">
<meta property="og:title" content="คำทั้งหมด · all words">
<meta property="og:image" content="{site}/og.jpg">
<style>{PALETTE}</style></head><body>
<header>
 <div class="mark">พจนานุกรมราก</div>
 <h1>คำทั้งหมด</h1>
 <div class="core">all words, in Thai alphabetical order</div>
</header>
<div class="wrap">
 <p><a href="/roots/">← พจนานุกรมราก · what this dictionary is for</a></p>
 <ul class="plain">{rows}</ul>
 <footer>{len(entries)} entr{'y' if len(entries) == 1 else 'ies'}.
 Every claim in an entry carries its confidence; unchecked claims are printed
 as open questions rather than left to look settled.</footer>
</div></body></html>"""
