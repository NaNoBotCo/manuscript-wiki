#!/usr/bin/env python3
"""siteindex — the authored index of wichaa (WAYFINDING_PLAN.md, the nav rebuild).

"Never index your own book." — Cat's Cradle. An index is a portrait: the shape of
how knowledge is organised reveals, and creates, what the thing IS. routes.py can
guarantee that every page exists and is reachable, but it cannot give the site a
SHAPE — an auto-generated list has no point of view. This module is the point of
view: a hand-authored ordering of what wichaa contains and how its parts relate.

It is the single source of the site's self-description, projected many ways:
  · the grouped "More" menu on every page          (menu_html)
  · the root/landing orientation                    (render, reused there)
  · the /everything index page                      (render)
  · the machine-readable structure in llms.txt      (as_text)

THE DISCIPLINE (this is what stops the day-one decay):
Every non-hidden section/door route MUST appear in exactly one group. coverage()
cross-examines this index against routes.py and returns any route that is placed
NOWHERE (it would silently vanish from the description) or placed TWICE. The build
surfaces the unplaced ones as an "Unfiled" shelf and a warning — so adding a page
forces a one-line "where does this belong", and forgetting is loud, not silent.

Items are (route_or_href, label, gloss). A leading "/" is an on-site route; label
and gloss are authored HERE (not pulled from routes.py) because the DESCRIPTION is
the authored act — the same page reads differently depending on which shelf it sits
on and what sentence introduces it.

Stdlib only; imports routes for the coverage check.
"""
from __future__ import annotations

import routes

# The header carries only these — the MODES of reading, the constant "ways in".
# They never grow: everything else is described in the groups below and reached
# through the index, so a page added tomorrow never touches the header.
WAYS_IN = ["/browse", "/atlas", "/trails", "/search", "/wander"]

# Two "ways in" are not pages but behaviours already living in the chrome:
#   /search  — the box on /browse and the overview (a header affordance)
#   /wander  — the เดินเล่น pill
# They appear in the header as actions; coverage() knows not to demand a route.
_NON_ROUTE_WAYS = {"/search", "/wander"}

TAGLINE = ("practical, efficacious sacred knowledge — where no line is drawn "
           "between science, magic, medicine, and nature.")

# ---- the authored index --------------------------------------------------------
# (group_key, group_title_th_en, group_gloss, [ (route/href, label, gloss) ... ])
GROUPS = [
    ("ways", "ทางเข้า · Ways in",
     "How to read the whole — the modes, not the material.",
     [
         ("/browse", "Browse", "the whole corpus, by place, script, genre and date"),
         ("/atlas", "The Atlas", "everything as one map — every concept, joined by what it shares"),
         ("/trails", "Trails", "guided walks: a few records in an order, and why each comes next"),
         ("/search", "Search", "go straight to a word — ยันต์, Pali, Phrae…"),
         ("/wander", "Wander · เดินเล่น", "one tap, somewhere unexpected"),
     ]),

    ("traditions", "สาย · The traditions",
     "Where this knowledge lives. Coequal — none of them the trunk; the seam "
     "between them is provenance, not structure.",
     [
         ("/browse?tradition=Lanna+manuscripts", "Lanna manuscripts",
          "the palm-leaf archive — nearly 7,000 volumes, the antique heart"),
         ("/market", "The living market",
          "the same wichaa, still worn and traded today"),
         ("/expedite", "St. Expedite",
          "a global saint-cult of urgent causes — wichaa is not one culture's"),
         ("/wats", "The temples of the north",
          "1,466 mapped wats of the Lanna north — where the manuscripts were kept and the rites are still done"),
         ("/browse?tradition=Museum+heritage", "Museum heritage",
          "CC0 objects from Cleveland, the Met, the Smithsonian — the comparanda"),
     ]),

    ("practices", "วิชา · The practices",
     "What the knowledge does. The subjects a manuscript is FOR, and the people "
     "who keep them.",
     [
         ("/a?s=genre:astrology", "Astrology & the almanac",
          "horā, the holasat, the phrommachat — reading time, fate, the lucky day"),
         ("/a?s=entity:yantra", "Yantra & katha",
          "the drawn magic and the spoken — diagrams inked, formulae chanted"),
         ("/a?s=entity:su_khwan", "The rites",
          "soul-calling, life-extension, protection over house and dead"),
         ("/a?s=entity:lersi", "The lersi",
          "the ascetic seer-sages who keep the wichaa and teach it"),
         ("/articles", "All the subjects →",
          "every explainer the tradition is written up under"),
     ]),

    ("instruments", "เครื่อง · The instruments",
     "Things the maker built — working models that compute the sacred and the "
     "natural in one mechanism, and so make the no-line claim you can hold.",
     [
         ("/moon", "The moon complication", "a working dial — two moons on one turning disc"),
         ("/jovilabe", "The Jovilabe", "Jupiter's four moons, geared — eclipses, transits, the wheelwork"),
         ("/redspot", "The Red Spot dial", "the same four moons, seen from a Jovian horizon"),
         ("/hun", "Hun Payont", "an effigy you forge and carry — it reads the day and goes to market for you"),
     ]),

    ("reference", "ชั้นอ้างอิง · The reference shelf",
     "The apparatus that holds the rest up.",
     [
         ("/glossary/", "Glossary", "the tradition's words, in Thai · English · 中文"),
         ("/na/", "The 108 Na", "the sacred glyphs, each paired with the page it was drawn on"),
         ("/diagrams", "Diagrams", "yantra plates and sak-yant stencils across the corpus"),
         ("/textbooks", "Textbooks", "the digitised manuals, page by page"),
         ("/findings", "Discoveries", "what the curiosity bots have noticed across the whole corpus"),
     ]),

    ("making", "เบื้องหลัง · The making of",
     "The project itself — honest about its own state.",
     [
         ("/support", "Tam boon", "free forever, funded by merit not paywalls — sponsor a page"),
         ("/activity", "The bots at work", "what the automation has been doing, and what it costs to go on"),
         ("/widgets", "Tools & shit", "small free tools that do one thing — no accounts, no app store"),
         ("/api/index.json", "For machines", "the API, the graph, llms.txt — even the bots can learn"),
     ]),
]


# ---- coverage: the anti-decay check --------------------------------------------
def _indexed_routes():
    """Which routes this index gives a HOME to. Only a bare "/path" is a home;
    a "/browse?tradition=…" is a deep link INTO a page, a view, not the page's
    own shelf — so it neither files nor duplicates the bare route."""
    seen = {}
    for gkey, _t, _g, items in GROUPS:
        for href, label, _gl in items:
            if "?" in href or href.startswith("/api"):
                continue
            if href.startswith("/"):
                seen.setdefault(href, []).append(gkey)
    return seen


def coverage(route_list=None):
    """Cross-examine the index against routes.py. Returns {unfiled, duplicated}:
    routes a visitor can reach that the INDEX describes nowhere (they'd vanish
    from the site's self-description), and routes placed on two shelves. Every
    page a person is meant to land on should have exactly one home here."""
    rs = route_list or routes.ROUTES
    indexed = _indexed_routes()
    # the pages the index is responsible for describing: real destinations, not
    # templates, not deliberately-hidden utilities.
    describable = {r.path for r in rs
                   if r.kind == "section" and not r.hidden_reason}
    describable.add("/")  # the root/overview is describable too (via Ways in → Browse etc.)
    unfiled = sorted(p for p in describable
                     if p not in indexed and p not in _NON_ROUTE_WAYS and p != "/")
    duplicated = {p: g for p, g in indexed.items() if len(g) > 1}
    # index entries that point at a route which no longer exists (rot the other way)
    known = {r.path for r in rs} | _NON_ROUTE_WAYS
    dangling = sorted(p for p in indexed if p not in known)
    return {"unfiled": unfiled, "duplicated": duplicated, "dangling": dangling}


# ---- projections ---------------------------------------------------------------
def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def render(wiki, unfiled=()):
    """The /everything index page — the site described, in full. Also the body the
    root page reuses. `unfiled` (from coverage) is shown as a flagged shelf so a
    forgotten page is visible here rather than silently absent."""
    secs = []
    for _k, title, gloss, items in GROUPS:
        rows = "".join(
            f'<li><a href="{_esc(href)}"><b>{_esc(label)}</b>'
            f'<span>{_esc(gloss)}</span></a></li>' for href, label, gloss in items)
        secs.append(f'<section class=ixg><h2>{_esc(title)}</h2>'
                    f'<p class=ixgloss>{_esc(gloss)}</p><ul class=ixlist>{rows}</ul></section>')
    if unfiled:
        rows = "".join(f'<li><a href="{_esc(p)}"><b>{_esc(p)}</b>'
                       f'<span>not yet placed on a shelf — give it a home in siteindex.py</span>'
                       f'</a></li>' for p in unfiled)
        secs.append('<section class=ixg ixunfiled><h2>Unfiled</h2>'
                    '<p class=ixgloss>Pages the index has not yet placed. They are '
                    'reachable, but the site does not yet describe them.</p>'
                    f'<ul class=ixlist>{rows}</ul></section>')
    css = (
        ".ixlede{font-size:20px;max-width:44rem;margin:0 0 8px}"
        ".ixg{margin:30px 0 0;padding-top:18px;border-top:1px solid rgba(128,128,128,.2)}"
        ".ixg h2{font-size:21px;margin:0 0 4px}"
        ".ixgloss{opacity:.72;margin:0 0 14px;max-width:44rem;font-size:15.5px}"
        ".ixlist{list-style:none;margin:0;padding:0;display:grid;"
        "grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}"
        ".ixlist a{display:block;padding:14px 16px;border:1px solid rgba(128,128,128,.28);"
        "border-radius:12px;text-decoration:none;height:100%}"
        ".ixlist a:hover{border-color:var(--gold,#a8791e)}"
        ".ixlist b{font-size:16.5px;display:block}"
        ".ixlist span{font-size:14.5px;opacity:.8;display:block;margin-top:3px;line-height:1.5}"
        ".ixunfiled h2{color:#8c3b2e}"
        "@media(max-width:520px){.ixlist{grid-template-columns:1fr}}")
    body = (
        "<header><div><h1>Everything</h1><p class=sub>"
        "สารบัญ · the whole of wichaa, indexed</p></div>" + wiki.NAV + "</header>"
        "<main><p class=ixlede><b>wichaa</b> — " + _esc(TAGLINE) + "</p>"
        "<p class=ixgloss>Not a menu of pages but an index of the thing itself: what "
        "it holds, and how the parts stand to one another.</p>"
        + "".join(secs) + "</main>")
    return wiki.page("Everything — wichaa", css, body,
                     description="The whole of wichaa, indexed: the traditions, the "
                                 "practices, the instruments, and the reference shelf.")


if __name__ == "__main__":
    import json
    cov = coverage()
    print("INDEX COVERAGE CHECK")
    print("  unfiled (reachable but undescribed):", cov["unfiled"] or "none")
    print("  duplicated (on two shelves):", cov["duplicated"] or "none")
    print("  dangling (index points at a dead route):", cov["dangling"] or "none")
    print(f"\n{len(GROUPS)} groups, "
          f"{sum(len(g[3]) for g in GROUPS)} entries")
