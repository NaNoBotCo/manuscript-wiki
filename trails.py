#!/usr/bin/env python3
"""trails — wandering, made a thing you can hold (Phase D of WAYFINDING_PLAN.md).

A TRAIL is an ordered walk through the knowledge graph with one line of
narration per step. It is the answer to "where do I even start" that a facet
list can never give: somebody (or something) that already knows the corpus
takes you by the hand and says *look at this, now this, now see what they have
to do with each other*.

Two provenances, both visible:
  · hand   — written into data/trails.json by a person, checked against the data
  · bots   — assembled here from a curiosity finding and the records it cites,
             published immediately (decision 3) wearing a label that says so
             and linking the evidence. Extract-don't-author: a bot trail states
             counts and quotes the finding, and invents no relationship.

STEPS ARE NODE IDS, NOT URLS. `ms:727`, `place:wat-chiang-man`, `term:เมตตา` —
resolved through cartography.href_for/labels at build time. That is deliberate:
a trail then breaks LOUDLY (validate() refuses it) if the corpus loses the thing
it points at, instead of quietly publishing a dead link. A published trail is a
promise, and this project's rule is that permalinks are promises.

    python3 trails.py            # validate every trail, print the walk
"""
from __future__ import annotations

import html
import json
from pathlib import Path

import cartography
import strings

HERE = Path(__file__).resolve().parent
TRAILS_JSON = HERE / "data" / "trails.json"
KOFI = "https://ko-fi.com/defiantchiangmai"

# A bot trail needs enough cited records to be a walk rather than a shrug.
MIN_BOT_CITES = 4
MAX_BOT_TRAILS = 8
BOT_STEPS = 5


def _esc(s):
    return html.escape(str(s or ""), quote=True)


# --------------------------------------------------------------------- loading
def load_authored():
    try:
        data = json.loads(TRAILS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for t in data.get("trails", []):
        if t.get("slug") and t.get("steps"):
            t.setdefault("author", "hand")
            out.append(t)
    return out


def propose_from_findings(g, limit=MAX_BOT_TRAILS):
    """Bot-assembled trails: one per curiosity finding that cites enough real
    records. The bot chooses nothing about MEANING — the finding already said
    what it noticed, and the records are the ones it counted. What the bot adds
    is the ORDER (finding first, then its evidence) and a sentence that states,
    verbatim, how many records it counted and how sure it said it was."""
    out = []
    for node in sorted(g.nodes.values(), key=lambda n: n["id"]):
        if node["cls"] != "finding":
            continue
        cites = [e for e in g.by_src().get(node["id"], ())
                 if e["type"] == "cites" and e["dst"] in g.nodes]
        if len(cites) < MIN_BOT_CITES:
            continue
        conf = node.get("confidence")
        steps = [{
            "node": node["id"],
            "say": ("A curiosity bot noticed this across the whole corpus"
                    + (f", and rated its own confidence {conf}" if conf else "")
                    + f". It counted {len(cites)} records; the walk below is "
                      f"those records, in the order it cited them."),
        }]
        # One step per DESTINATION, not per citation. Market listings have no
        # page of their own — they all resolve to /market — so an undeduped
        # market finding produced five steps that were the same click five
        # times. A trail whose steps do not move is not a trail.
        used = {cartography.href_for(node["id"])}
        for e in cites:
            href = cartography.href_for(e["dst"])
            if href in used:
                continue
            used.add(href)
            n2 = g.nodes[e["dst"]]
            what = _CLS_LABEL.get(n2.get("cls", ""), "a record").split("·")[-1].strip()
            steps.append({
                "node": e["dst"],
                "say": f"One of the {len(cites)} it counted — {what}"
                       + (f", from its {e['ev']} evidence." if e.get("ev") else "."),
            })
            if len(steps) > BOT_STEPS:
                break
        if len(steps) < 3:
            continue      # nowhere to walk; the finding page alone says it better
        out.append({
            "slug": "bot-" + node["id"].split(":", 1)[1],
            "title_th": "ทางที่บอทเดิน",
            "title_en": node["label"],
            "blurb": node["label"],
            "author": "bots",
            "evidence_count": len(cites),
            "evidence_href": cartography.href_for(node["id"]),
            "steps": steps,
        })
        if len(out) >= limit:
            break
    return out


def validate(g, trail):
    """[] if every step resolves, else the reasons it must not be published."""
    problems = []
    for i, s in enumerate(trail.get("steps", []), 1):
        nid = s.get("node")
        if nid not in g.nodes:
            problems.append(f"{trail['slug']} step {i}: no such node {nid!r}")
        elif not cartography.href_for(nid):
            problems.append(f"{trail['slug']} step {i}: {nid} has no page")
        if not (s.get("say") or "").strip():
            problems.append(f"{trail['slug']} step {i}: no narration")
    if len(trail.get("steps", [])) < 2:
        problems.append(f"{trail['slug']}: a trail needs at least two steps")
    return problems


def resolved(g, trail):
    """The trail with each step's label and href filled in from the graph."""
    out = dict(trail)
    out["steps"] = []
    for s in trail["steps"]:
        n = g.nodes.get(s["node"], {})
        out["steps"].append({
            "node": s["node"],
            "cls": n.get("cls", ""),
            "label": n.get("label", s["node"]),
            "href": cartography.href_for(s["node"]),
            "say": s["say"],
        })
    return out


def all_trails(g):
    """Authored first (a person's walk outranks a machine's), then bot-assembled.
    Anything that fails validation is DROPPED with its reason returned, never
    published half-broken."""
    good, problems = [], []
    for t in load_authored() + propose_from_findings(g):
        errs = validate(g, t)
        if errs:
            problems.extend(errs)
            continue
        good.append(resolved(g, t))
    return good, problems


# --------------------------------------------------------------------- rendering
_TRAIL_CSS = """
.tr{max-width:760px;margin:0 auto}
.trlede{font-size:19px;line-height:1.65;margin:0 0 6px}
.trmeta{font-size:14px;opacity:.72;margin:0 0 22px}
.botmark{display:inline-block;background:var(--gold-bg,#fdf3dd);border:1px solid #e5cf9a;
  color:#8a5a00;border-radius:999px;padding:4px 12px;font-size:13px;font-weight:600}
ol.steps{list-style:none;counter-reset:s;margin:0;padding:0}
ol.steps li{counter-increment:s;position:relative;padding:0 0 26px 46px;
  border-left:2px solid rgba(128,128,128,.28);margin-left:14px}
ol.steps li:last-child{border-left-color:transparent}
ol.steps li::before{content:counter(s);position:absolute;left:-17px;top:0;
  width:32px;height:32px;border-radius:50%;background:var(--gold,#a8791e);color:#fff;
  display:flex;align-items:center;justify-content:center;font-weight:700;font-size:15px}
.steplab{font-size:19px;font-weight:600;display:inline-flex;align-items:center;min-height:44px;padding:2px 2px;margin:0 0 2px}
.stepcls{font-size:12.5px;opacity:.66;margin-left:8px;font-weight:400}
.stepsay{margin:0;font-size:16.5px;line-height:1.6;opacity:.92}
.trend{margin:26px 0 0;padding:20px;border:1px solid rgba(128,128,128,.3);border-radius:14px}
.trend p{margin:0 0 12px;font-size:16.5px}
.trbtns{display:flex;flex-wrap:wrap;gap:10px}
.trbtn{display:inline-block;padding:10px 16px;border-radius:999px;border:1px solid var(--gold,#a8791e);
  text-decoration:none;font-weight:600;font-size:15px}
.trbtn.kofi{background:#fbf1dc;color:#8a5a00;border-color:transparent}
.trcard{display:block;border:1px solid rgba(128,128,128,.3);border-radius:14px;padding:18px 20px;
  text-decoration:none;margin:0 0 14px}
.trcard:hover{border-color:var(--gold,#a8791e)}
.trcard b{font-size:19px;display:block}
.trcard .th{font-size:16px;opacity:.75}
.trcard span.bl{display:block;font-size:15.5px;opacity:.82;margin-top:6px;line-height:1.5}
"""

# The class of a step, said plainly — so a reader knows whether they are about to
# open a manuscript, a temple, a word, or the machine's own note.
_CLS_LABEL = {
    "ms": "ใบลาน · manuscript", "item": "ตลาด · a listing", "place": "สถานที่ · a place",
    "term": "คำ · a word", "finding": "ข้อสังเกต · a finding", "entity": "เรื่อง · a subject",
    "genre": "หมวด · a genre", "subgenre": "หมวดย่อย · a sub-genre",
    "language": "ภาษา · a language", "script": "อักษร · a script",
    "material": "วัสดุ · a material", "province": "จังหวัด · a province",
    "temple": "วัด · a temple", "tradition": "สาย · a tradition", "page": "หน้า · a page",
}


def trail_page(t, wiki):
    """One trail, rendered. Uses wiki.page so it inherits the whole chrome —
    nav, share bar, the เดินเล่น pill, the back-to-menu pill."""
    steps = []
    for s in t["steps"]:
        cls = _CLS_LABEL.get(s["cls"], s["cls"])
        steps.append(
            f'<li><a class=steplab href="{_esc(s["href"])}">{_esc(s["label"])}</a>'
            f'<span class=stepcls>{_esc(cls)}</span>'
            f'<p class=stepsay>{_esc(s["say"])}</p></li>')
    if t.get("author") == "bots":
        mark = (f'<p><span class=botmark>&#129302; assembled by the bots from '
                f'{t.get("evidence_count", 0)} cited records</span> '
                f'<a href="{_esc(t.get("evidence_href", "/findings"))}">see the evidence</a></p>')
    else:
        mark = ""
    end = (
        '<div class=trend>'
        '<p><b>That was a trail.</b> Every step is a real record in the archive, and '
        'every link on it goes somewhere you can keep pulling.</p>'
        '<div class=trbtns>'
        '<a class=trbtn href="/trails">More trails</a>'
        '<a class=trbtn href="/browse">Wander off on your own</a>'
        f'<a class="trbtn kofi" href="{KOFI}" target=_blank rel=noopener>'
        '&#9749; Tam boon — sponsor a page</a>'
        '</div></div>')
    body = (
        "<header><div><h1>" + _esc(t["title_en"]) + "</h1>"
        "<p class=sub>" + _esc(t.get("title_th", "")) + "</p></div>"
        + wiki.NAV + "</header>"
        "<main><div class=tr>"
        + f'<p class=trlede>{_esc(t.get("blurb", ""))}</p>'
        + f'<p class=trmeta>{len(t["steps"])} steps</p>'
        + mark
        + "<ol class=steps>" + "".join(steps) + "</ol>"
        + end + "</div></main>")
    return wiki.page(f"{t['title_en']} — a trail — wichaa", _TRAIL_CSS, body,
                     description=t.get("blurb", ""),
                     og_image=f"/trail/{t['slug']}/card.png",
                     og_url=f"/trail/{t['slug']}/")


def index_page(trails, wiki):
    hand = [t for t in trails if t.get("author") != "bots"]
    bots = [t for t in trails if t.get("author") == "bots"]

    def card(t):
        return (f'<a class=trcard href="/trail/{_esc(t["slug"])}/">'
                f'<b>{_esc(t["title_en"])}</b>'
                f'<span class=th>{_esc(t.get("title_th", ""))}</span>'
                f'<span class=bl>{_esc(t.get("blurb", ""))}</span>'
                f'<span class=bl style="opacity:.6">{len(t["steps"])} steps</span></a>')

    body = (
        "<header><div><h1>Trails</h1><p class=sub>"
        + _esc(strings.pair("trails")) + "</p></div>" + wiki.NAV + "</header>"
        "<main><div class=tr>"
        "<p class=trlede>A trail is somebody walking you through the archive on "
        "purpose — a few records in an order, with a line about why each one is "
        "next. Follow one end to end, or step off it at any point and keep going "
        "on your own.</p>"
        + "".join(card(t) for t in hand)
        + ("<h2 style='margin-top:32px'>Assembled by the bots</h2>"
           "<p class=trmeta>The curiosity bots notice patterns across the whole "
           "corpus and cite the records they counted. These trails are those "
           "findings, walked. Nothing here is an opinion — every step is a record "
           "the bot pointed at.</p>" + "".join(card(t) for t in bots) if bots else "")
        + "</div></main>")
    return wiki.page("Trails — wichaa", _TRAIL_CSS, body,
                     description="Walks through the archive — a few records in an "
                                 "order, with a line about why each one is next.",
                     og_image="/trails/card.png", og_url="/trails")


# ------------------------------------------------------------------- share cards
def card_bytes(t, width=1200, height=630):
    """A per-trail social card, drawn with Pillow at build time.

    Every page gets an og:image picturing the thing
    itself, and the masters for hand-designed cards live in publishing/cards/
    because make_card.py needs a browser. A trail cannot work that way — there
    is one per finding and more arrive whenever the bots notice something — so
    this follows the OTHER established precedent in this codebase: og_card_bytes(),
    which draws with Pillow inside the build and degrades to None when Pillow
    isn't there. Same palette as the site header.
    """
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None
    try:
        import wiki as _w
        BG, CREAM, GOLD, MUTED = (18, 45, 42), (244, 234, 214), (233, 196, 106), (150, 180, 172)
        img = Image.new("RGB", (width, height), BG)
        d = ImageDraw.Draw(img)
        tf, sf, cf = _w._og_font(58), _w._og_font(30), _w._og_font(24)
        if not (tf and sf and cf):
            return None
        x, y, tw = 80, 96, width - 160
        d.text((x, y), "A TRAIL · ทาง", font=cf, fill=GOLD)
        y += 56
        for ln in _w._wrap(d, t["title_en"], tf, tw)[:3]:
            d.text((x, y), ln, font=tf, fill=CREAM)
            y += 68
        y += 10
        for ln in _w._wrap(d, t.get("blurb", ""), sf, tw)[:3]:
            d.text((x, y), ln, font=sf, fill=MUTED)
            y += 40
        # the walk itself, as a row of dots — the shape of a trail, at a glance
        n = len(t["steps"])
        dy = height - 120
        for i in range(n):
            cx = x + i * min(90, (tw - 40) // max(n - 1, 1))
            d.ellipse([cx - 11, dy - 11, cx + 11, dy + 11], fill=GOLD)
            if i < n - 1:
                nx = x + (i + 1) * min(90, (tw - 40) // max(n - 1, 1))
                d.line([cx + 13, dy, nx - 13, dy], fill=(90, 120, 112), width=3)
        foot = (f"{n} steps · assembled by the bots"
                if t.get("author") == "bots" else f"{n} steps")
        d.text((x, height - 66), foot + "  ·  wichaa.net", font=cf, fill=MUTED)
        import io
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True)
        return buf.getvalue()
    except Exception:
        return None


if __name__ == "__main__":
    g, _meta = cartography.build()
    ts, probs = all_trails(g)
    for t in ts:
        mark = " [bots]" if t.get("author") == "bots" else ""
        print(f"\n{t['title_en']}{mark}  ({len(t['steps'])} steps) /trail/{t['slug']}/")
        for i, s in enumerate(t["steps"], 1):
            print(f"  {i}. {s['label'][:46]:48} {s['href']}")
    print(f"\n{len(ts)} trails valid")
    if probs:
        print(f"{len(probs)} problem(s):")
        for p in probs:
            print("  -", p)
