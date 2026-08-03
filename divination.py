"""/divination — the divination hub.

A growing room of working divination tools. The first tenant is the Taoist
Oracle (I Ching, Plum Blossom, Wen Wang Gua), a self-contained offline app built
in its own repo (../taoist-oracle) and exported here by its export_wichaa.py.
build_static.py writes that app to /divination/app.html; this module builds the
chrome page around it and frames it in an iframe, so the tool stays one artifact
and is never re-authored.

Deliberately NOT folded into the corpus taxonomy: these are working tools, not
catalogue records. The page is honest about what is here and what is coming.
"""
from __future__ import annotations

HUB_CSS = """
  .lead{max-width:760px;color:var(--muted);font-size:17px;line-height:1.65;margin:0 0 6px}
  .lead strong{color:var(--ink)}
  .tool{margin:30px 0}
  .tool h2{font-size:26px;margin:0 0 4px}
  .tool .zh{color:var(--muted);font-weight:600}
  .tool .desc{max-width:760px;line-height:1.65;margin:8px 0 4px}
  .grounded{max-width:760px;border-left:3px solid var(--teal);
    background:rgba(31,111,106,.08);padding:10px 16px;border-radius:0 6px 6px 0;
    margin:14px 0;font-size:15px;line-height:1.6}
  .oracleframe{width:100%;height:860px;border:1px solid var(--line);border-radius:14px;
    background:#fffdf8;display:block;margin:16px 0}
  @media(max-width:760px){.oracleframe{height:780px}}
  .toolact{display:flex;gap:10px;flex-wrap:wrap;margin:2px 0 4px}
  .toolact a{display:inline-block;background:var(--teal);color:#fff;text-decoration:none;
    border-radius:9px;padding:9px 16px;font-weight:750;font-size:15px}
  .toolact a.ghost{background:transparent;color:var(--teal);border:1px solid var(--teal)}
  .toolact a:hover{filter:brightness(1.08)}
  .roadmap{max-width:760px;margin:34px 0 0}
  .roadmap h2{font-size:22px;margin:0 0 10px}
  .roadmap ul{margin:0 0 12px 20px;line-height:1.7}
  .roadmap li{margin:6px 0}
  .roadmap .soon{color:var(--muted)}
  .relbar{max-width:760px;margin:24px 0 0;color:var(--muted);font-size:15px}
  .relbar a{color:var(--teal)}
"""


def hub_body(nav: str) -> str:
    return (
        "<header><div><h1>Divination</h1>"
        "<p class=sub>Working tools for reading a question — grounded in the "
        "tradition, not invented. Free, offline, no account.</p></div>"
        + nav + "</header>"
        "<main>"
        "<p class=lead>A growing room of divination instruments. Each one does the "
        "real method — the actual casting, the actual reckoning — and shows its "
        "workings rather than hiding them behind a fortune. <strong>The words of a "
        "reading come from the received texts</strong>, marked as such; the "
        "mechanics are exact and checkable.</p>"

        "<section class=tool>"
        "<h2>The Taoist Oracle <span class=zh>易經 · 梅花易數 · 文王卦</span></h2>"
        "<p class=desc>Three Chinese cast-oracle methods on one engine: the "
        "<b>I Ching</b> (cast by three coins or by the traditional 49 yarrow "
        "stalks, with its ritual shown line by line), <b>Plum Blossom</b> "
        "numerology (read a number or the moment itself), and <b>Wen Wang Gua / "
        "Liu Yao</b> (the full six-line overlay — najia, palaces, six relatives, "
        "the day's void). Hold a question, cast, and read all six lines with the "
        "moving ones marked.</p>"
        "<div class=grounded>The Judgment (卦辭) and every line statement (爻辭) "
        "shown are the verbatim canonical Zhou Yi text — public domain — each "
        "with a concise English translation of my own, clearly labelled. The "
        "位/中/正/應 line-position notes are traditional line theory. Nothing is "
        "invented.</div>"
        "<div class=toolact>"
        "<a href='app.html' target=_blank rel=noopener>Open full screen</a>"
        "<a class=ghost href='app.html' download='taoist-oracle.html'>Download as one file</a>"
        "</div>"
        "<iframe class=oracleframe src='app.html' title='The Taoist Oracle' loading=lazy></iframe>"
        "</section>"

        "<section class=roadmap>"
        "<h2>What is here, and what is coming</h2>"
        "<ul>"
        "<li><b>Here now —</b> the Chinese cast oracles above.</li>"
        "<li class=soon><b>Coming —</b> the deterministic Chinese layers on the "
        "same engine: Bazi / Four Pillars, Zi Wei Dou Shu, and feng-shui reckoning "
        "(Flying Star, Eight Mansions).</li>"
        "<li class=soon><b>Later —</b> the Thai and Lanna methods this archive is "
        "built for.</li>"
        "</ul>"
        "</section>"

        "<p class=relbar>Related in the archive: "
        "<a href='/articles'>the tradition, subject by subject</a> · "
        "<a href='/glossary/'>its words in Thai · English · 中文</a>.</p>"
        "</main>"
    )


def card_svg() -> str:
    """1200x630 social share card. Rasterised by make_card.py -> publishing/cards/
    divination.png, copied to /divination/card.png at build."""
    return """<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <rect width="1200" height="630" fill="#122d2a"/>
  <text x="90" y="200" font-family="Iowan Old Style, Palatino, Georgia, serif" font-size="150" fill="#e9c46a">☯</text>
  <text x="300" y="180" font-family="Iowan Old Style, Palatino, Georgia, serif" font-size="90" font-weight="700" fill="#f4ead6">Divination</text>
  <text x="302" y="250" font-family="Iowan Old Style, Palatino, Georgia, serif" font-size="40" fill="#8fc7c1">易經 · 梅花易數 · 文王卦</text>
  <text x="92" y="380" font-family="Iowan Old Style, Palatino, Georgia, serif" font-size="38" fill="#f4ead6">I Ching · Plum Blossom · Wen Wang Gua</text>
  <text x="92" y="440" font-family="Iowan Old Style, Palatino, Georgia, serif" font-size="32" fill="#cfe3e0">The real methods, grounded in the canonical texts.</text>
  <text x="92" y="560" font-family="Iowan Old Style, Palatino, Georgia, serif" font-size="26" fill="#8fc7c1">wichaa.net/divination — free, offline, no account</text>
</svg>"""
