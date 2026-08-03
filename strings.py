#!/usr/bin/env python3
"""strings — the ONE bilingual string registry (WAYFINDING_PLAN.md decision 1).

"Very Thai friendly from the start… It's true sitewide. The internet has a big
blind spot in thailand, and it cannot be fixed without thai participation and
visitors." — the owner, 2026-07-22.

The sysop-safe shape: every chrome label is a (Thai, English) PAIR in this one
module; renderers show both, Thai first. No parallel page trees, no locale
toggle, no translation backlog — there is nothing to fall out of sync because
there is only one source. URLs stay neutral English, so a later sourced-Lanna
naming pass (the open polish item) changes display strings only.

Thai here is deliberately STANDARD, everyday vocabulary (ดูเพิ่ม, ใกล้กัน,
เดินเล่น) — dictionary words, not coined terms and not Lanna. Anything more
poetic waits for the sourced naming session the ADR reserves.

Stdlib only, imports nothing, importable from anywhere (wiki.py, cartography,
build scripts) without cycles.
"""

PAIRS = {
    # chrome
    "threads":      ("สายใย", "Threads"),
    "wander":       ("เดินเล่น", "Wander"),
    "trails":       ("เส้นทาง", "Trails"),
    "your_trail":   ("ทางที่คุณเดิน", "Where you've been"),
    "places":       ("สถานที่", "Places"),
    "manuscripts":  ("ใบลาน", "Manuscripts"),
    # relations (rendered on every thread chip — the NAMED relation is the
    # whole difference between navigation and discovery)
    "near":         ("ใกล้กัน", "near"),
    "nearest":      ("ใกล้ที่สุด", "nearest"),
    "same_walk":    ("เดินถึงกันได้", "same walking cluster"),
    "same_temple":  ("เก็บที่วัดเดียวกัน", "held at the same wat"),
    "held_at":      ("เก็บรักษาที่", "held at"),
    "about":        ("ว่าด้วย", "about"),
    "term":         ("มีคำว่า", "carries the term"),
    "in_market":    ("คำเดียวกันในตลาดวันนี้", "the same word in today's market"),
    "paired":       ("คู่กัน", "paired with"),
    "includes":     ("รวมถึง", "includes"),
    "see_also":     ("ดูเพิ่ม", "see also"),
    "install_app":  ("ติดตั้งแอปออฟไลน์", "install the offline app"),
}


def th(key):
    return PAIRS[key][0]


def en(key):
    return PAIRS[key][1]


def pair(key, sep=" · "):
    t, e = PAIRS[key]
    return f"{t}{sep}{e}"


def js_pairs(keys=None):
    """A compact JS object literal of {key: [th, en]} for client-side renderers
    (manuscript detail, market drawer) — generated from this registry so the
    client can never drift from it."""
    import json
    ks = keys or PAIRS.keys()
    return json.dumps({k: list(PAIRS[k]) for k in ks}, ensure_ascii=False,
                      separators=(",", ":"))


# ---- the Threads section (server-side renderer) -----------------------------------
# One shared HTML shape for every statically-rendered threads strip (place pages,
# mechanism pages, tools). Client-rendered pages (manuscript detail, market)
# rebuild the same shape in JS from js_pairs(). Chips are deliberately large
# (accessibility: big targets, high contrast) and each names its relation.
_THREADS_CSS = (
    "<style>.threads{margin:26px 0 10px;padding:14px 0;border-top:1px solid "
    "rgba(128,128,128,.25)}.threads h2{font-size:17px;margin:0 0 10px}"
    ".threads ul{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;"
    "gap:10px}.threads a{display:inline-block;padding:10px 14px;border:1px solid "
    "rgba(128,128,128,.35);border-radius:10px;text-decoration:none;line-height:1.45}"
    ".threads a:hover{border-color:currentColor}"
    ".trel{display:block;font-size:12.5px;opacity:.72}"
    ".tlabel{font-weight:600}.tnote{font-size:12.5px;opacity:.72;margin-left:6px}"
    "</style>")


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def threads_section(entries, heading_key="threads"):
    """<section class=threads> from [{'href','label','rel','note'?}] — rel is a
    PAIRS key, rendered Thai-first; empty entries → empty string (honest-empty,
    no furniture)."""
    items = []
    for t in entries:
        if not t.get("href") or not t.get("label"):
            continue
        rel = t.get("rel") or "see_also"
        note = f" <span class=tnote>{_esc(t['note'])}</span>" if t.get("note") else ""
        items.append(
            f"<li><a href=\"{_esc(t['href'])}\">"
            f"<span class=trel>{_esc(pair(rel))}</span>"
            f"<span class=tlabel>{_esc(t['label'])}</span>{note}</a></li>")
    if not items:
        return ""
    return (_THREADS_CSS + "<section class=threads aria-label=\""
            + _esc(pair(heading_key)) + "\"><h2>" + _esc(pair(heading_key))
            + "</h2><ul>" + "".join(items) + "</ul></section>")
