#!/usr/bin/env python3
"""Rasterise a page's social share card into publishing/cards/<name>.png.

Every page on wichaa.net should unfurl with a picture of ITS OWN subject when one
exists, not the sitewide yantra. For pages whose subject is a drawing we generate
(the moon dial, and anything like it later), the card is that drawing, rendered
from the very same SVG the page serves — so the two cannot drift.

WHY THIS IS NOT PART OF publish_site.sh
    Rasterising needs a browser engine. Publishing must not: it runs nightly on a
    timer and has to work whether or not Chrome is installed. So the PNG is a
    MASTER, committed under publishing/cards/, and site_meta.py copies it into
    docs/<name>/card.png on every build. Run this by hand when the artwork
    changes — which is rare, and is exactly when a human should look at it.

WHY CHROME AND NOT ImageMagick
    Measured, not assumed: `magick` here has no rsvg delegate, so it falls back to
    its own SVG renderer, which dropped every gradient (all fills went black), got
    the clip-paths wrong and lost all the text. Chrome is the engine that renders
    the page, so what it produces is what a reader actually sees.

Usage:  python3 make_card.py moon
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CARDS = HERE / "publishing" / "cards"

CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
)

# name -> zero-argument callable returning a standalone 1200x630 SVG string.
def _sources():
    import moondial

    return {"moon": moondial.og_card_svg, "widgets": _widgets_card_svg,
            "w__geo": _geo_card_svg, "w__prices": _prices_card_svg,
            "w__regions": _regions_card_svg, "w__trends": _trends_card_svg,
            "w__products": _products_card_svg, "w__answers": _answers_card_svg}



# --- shared card furniture ---------------------------------------------------
# One visual family: teal rule, WICHAA eyebrow, serif headline, then the data
# itself. Each card draws ITS OWN subject from the same payload the widget
# draws, so a card cannot drift away from the page it advertises.
_CARD_FONT = ("system-ui,-apple-system,'Helvetica Neue','Noto Sans Thai',"
              "Thonburi,sans-serif")


def _card_shell(title_lines, subtitle, route, body_svg, foot=""):
    ttl = "".join(
        f'<text x="66" y="{206 + i * 64}" font-family="Georgia,serif" font-size="56" '
        f'font-weight="700" fill="#141b1a">{t}</text>'
        for i, t in enumerate(title_lines))
    sub_y = 206 + len(title_lines) * 64 + 14
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
<rect width="1200" height="630" fill="#f4f7f6"/>
<rect x="0" y="0" width="1200" height="16" fill="#1F4E4A"/>
<text x="66" y="124" font-family="Georgia,serif" font-size="28" fill="#1F4E4A" letter-spacing="6">WICHAA</text>
{ttl}
<text x="66" y="{sub_y}" font-family="{_CARD_FONT}" font-size="25" fill="#3a4a47">{subtitle}</text>
{body_svg}
<text x="66" y="580" font-family="{_CARD_FONT}" font-size="20" fill="#3a4a47">{route}</text>
{foot}
</svg>"""


def _esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _prices_card_svg() -> str:
    """The price distribution itself — where the market actually sits."""
    import wiki

    d = wiki.WIDGETS["prices"][0]()
    b = d["buckets"]; st = d["stats"]
    if not b:
        return _widgets_card_svg()
    BX, BY, BW, BH = 660, 150, 470, 300
    mx = max(x["n"] for x in b) or 1
    bw = BW / len(b)
    bars = []
    for i, x in enumerate(b):
        h = (x["n"] / mx) * BH
        bars.append(f'<rect x="{BX + i * bw + 4:.1f}" y="{BY + BH - h:.1f}" '
                    f'width="{bw - 8:.1f}" height="{h:.1f}" rx="4" fill="#1F4E4A" opacity=".85"/>')
        bars.append(f'<text x="{BX + i * bw + bw / 2:.1f}" y="{BY + BH + 22:.0f}" '
                    f'font-family="{_CARD_FONT}" font-size="15" fill="#3a4a47" '
                    f'text-anchor="middle">{_esc(x["label"])}</text>')
    return _card_shell(["What luck costs"],
                       "the price of every amulet on the market, in one shape",
                       "wichaa.net/w/prices", "".join(bars),
                       foot=f'<text x="66" y="410" font-family="{_CARD_FONT}" font-size="30" '
                            f'font-weight="700" fill="#141b1a">median &#3647;{st["median"]:,.0f}</text>'
                            f'<text x="66" y="452" font-family="{_CARD_FONT}" font-size="23" '
                            f'fill="#3a4a47">across {st["n"]:,} listings &#183; '
                            f'9 in 10 under &#3647;{st["p90"]:,.0f}</text>')


def _regions_card_svg() -> str:
    """Which provinces the market actually posts from."""
    import wiki

    d = wiki.WIDGETS["regions"][0]()
    ps = d["provinces"][:7]
    if not ps:
        return _widgets_card_svg()
    mx = max(p["n"] for p in ps) or 1
    rows = []
    for i, p in enumerate(ps):
        y = 158 + i * 44
        w = (p["n"] / mx) * 300
        rows.append(f'<text x="660" y="{y + 15}" font-family="{_CARD_FONT}" font-size="20" '
                    f'fill="#141b1a" text-anchor="end">{_esc(p["nameEn"])}</text>')
        rows.append(f'<rect x="672" y="{y}" width="{w:.1f}" height="21" rx="4" '
                    f'fill="#b8892f" opacity=".85"/>')
        rows.append(f'<text x="{682 + w:.1f}" y="{y + 16}" font-family="{_CARD_FONT}" '
                    f'font-size="17" fill="#3a4a47">{p["n"]}</text>')
    return _card_shell(["Regional", "interests"],
                       "where today&#8217;s amulet sellers post from",
                       "wichaa.net/w/regions", "".join(rows))


def _trends_card_svg() -> str:
    """New listings per day — the market's pulse."""
    import wiki

    d = wiki.WIDGETS["trends"][0]()
    days = d["days"]
    if len(days) < 2:
        return _widgets_card_svg()
    BX, BY, BW, BH = 640, 170, 490, 270
    mx = max(x["n"] for x in days) or 1
    step = BW / (len(days) - 1)
    pts = [(BX + i * step, BY + BH - (x["n"] / mx) * BH) for i, x in enumerate(days)]
    line = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = line + f"L{pts[-1][0]:.1f},{BY + BH}L{pts[0][0]:.1f},{BY + BH}Z"
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#1F4E4A"/>'
                   for x, y in pts)
    tot = sum(x["n"] for x in days)
    return _card_shell(["Market motion"],
                       "new amulet listings, day by day",
                       "wichaa.net/w/trends",
                       f'<path d="{area}" fill="#1F4E4A" opacity=".14"/>'
                       f'<path d="{line}" fill="none" stroke="#1F4E4A" stroke-width="3.5" '
                       f'stroke-linejoin="round"/>{dots}'
                       f'<text x="{BX}" y="{BY + BH + 26}" font-family="{_CARD_FONT}" '
                       f'font-size="16" fill="#3a4a47">{_esc(days[0]["day"])}</text>'
                       f'<text x="{BX + BW}" y="{BY + BH + 26}" font-family="{_CARD_FONT}" '
                       f'font-size="16" fill="#3a4a47" text-anchor="end">{_esc(days[-1]["day"])}</text>',
                       foot=f'<text x="66" y="410" font-family="{_CARD_FONT}" font-size="30" '
                            f'font-weight="700" fill="#141b1a">{tot:,} listings</text>'
                            f'<text x="66" y="450" font-family="{_CARD_FONT}" font-size="23" '
                            f'fill="#3a4a47">catalogued over {len(days)} days</text>')


def _products_card_svg() -> str:
    """The freshest listings, priced — proof the market is live right now."""
    import wiki

    d = wiki.WIDGETS["products"][0]()
    items = d.get("items", [])[:5]
    if not items:
        return _widgets_card_svg()
    rows = []
    for i, it in enumerate(items):
        y = 158 + i * 56
        raw = (it.get("titleEn") or it.get("titleTh") or "")
        # Thai has no spaces, so a hard cut is unavoidable -- but say it was cut.
        t = raw if len(raw) <= 34 else raw[:33].rstrip() + "\u2026"
        pr = it.get("price")
        rows.append(f'<rect x="640" y="{y}" width="490" height="46" rx="9" fill="#fff" '
                    f'stroke="#dde7e4"/>')
        rows.append(f'<text x="658" y="{y + 29}" font-family="{_CARD_FONT}" font-size="19" '
                    f'fill="#141b1a">{_esc(t)}</text>')
        if pr:
            rows.append(f'<text x="1112" y="{y + 29}" font-family="{_CARD_FONT}" font-size="19" '
                        f'font-weight="700" fill="#b8892f" text-anchor="end">'
                        f'&#3647;{pr:,.0f}</text>')
    tot = d.get("totals", {}).get("listings", 0)
    return _card_shell(["New on the", "market"],
                       "what the crawler catalogued most recently",
                       "wichaa.net/w/products", "".join(rows),
                       foot=f'<text x="66" y="430" font-family="{_CARD_FONT}" font-size="30" '
                            f'font-weight="700" fill="#141b1a">{tot:,} listings</text>'
                            f'<text x="66" y="470" font-family="{_CARD_FONT}" font-size="23" '
                            f'fill="#3a4a47">tracked and still arriving</text>')


def _answers_card_svg() -> str:
    """The questions themselves. With one answer so far, say one."""
    import wiki, textwrap

    d = wiki.WIDGETS["answers"][0]()
    items = d.get("items", [])
    if not items:
        return _widgets_card_svg()
    q = items[0].get("title", "")
    lines = textwrap.wrap(q, 30)[:4]
    body = "".join(
        f'<text x="660" y="{200 + i * 46}" font-family="{_CARD_FONT}" font-size="27" '
        f'fill="#141b1a">{_esc(l)}</text>' for i, l in enumerate(lines))
    n = len(items)
    return _card_shell(["Thai Answers"],
                       "real questions, answered from the catalogue",
                       "wichaa.net/w/answers",
                       f'<text x="660" y="160" font-family="Georgia,serif" font-size="62" '
                       f'fill="#b8892f">&#8220;</text>{body}',
                       foot=f'<text x="66" y="410" font-family="{_CARD_FONT}" font-size="30" '
                            f'font-weight="700" fill="#141b1a">{n} answer{"" if n == 1 else "s"}</text>'
                            f'<text x="66" y="450" font-family="{_CARD_FONT}" font-size="23" '
                            f'fill="#3a4a47">each one sourced, not guessed</text>')


def _geo_card_svg() -> str:
    """Card for /w/geo: the real map, same shapes and same shading the widget
    draws. House rule is that a card shows the thing -- before the outlines
    existed this was a scatter of dots on a blank rectangle, which showed
    nothing at all."""
    import math

    import wiki

    d = wiki.WIDGETS["geo"][0]()
    pts = [p for p in d.get("provinces", []) if p.get("lat") and p.get("lon")]
    out = d.get("outlines") or {}
    if not pts or not out:
        return _widgets_card_svg()

    las = [c[1] for rs in out.values() for r in rs for c in r]
    los = [c[0] for rs in out.values() for r in rs for c in r]
    la0, la1, lo0, lo1 = min(las), max(las), min(los), max(los)
    K = math.cos((la0 + la1) / 2 * math.pi / 180)
    BW, BH, OX, OY = 430, 560, 700, 35          # map box on the 1200x630 card
    sc = min(BW / ((lo1 - lo0) * K), BH / (la1 - la0))
    ox = OX + (BW - (lo1 - lo0) * K * sc) / 2
    oy = OY + (BH - (la1 - la0) * sc) / 2
    X = lambda lo: ox + (lo - lo0) * K * sc
    Y = lambda la: oy + (la1 - la) * sc

    by = {p["nameEn"]: p for p in pts}
    mmax = max([p["mss"] for p in pts] + [1]) ** .5
    kmax = max([p["market"] for p in pts] + [1]) ** .5
    land = []
    for nm, rings in out.items():
        n = by.get(nm, {}).get("mss", 0)
        fill = (f"rgba(31,78,74,{0.10 + 0.72 * (n ** .5) / mmax:.3f})"
                if n else "#dde7e4")
        for r in rings:
            dpath = "M" + "L".join(f"{X(c[0]):.1f},{Y(c[1]):.1f}" for c in r) + "Z"
            land.append(f'<path d="{dpath}" fill="{fill}" stroke="#fff" stroke-width=".6"/>')
    dots = [f'<circle cx="{X(p["lon"]):.1f}" cy="{Y(p["lat"]):.1f}" '
            f'r="{2 + 13 * (p["market"] ** .5) / kmax:.1f}" fill="#b8892f" '
            f'opacity=".8" stroke="#fff" stroke-width=".8"/>'
            for p in pts if p.get("market")]

    n_mss = sum(1 for p in pts if p.get("mss"))
    n_mkt = sum(1 for p in pts if p.get("market"))
    tot_m = d["totals"]["mss"]
    tot_k = d["totals"]["market"]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
<rect width="1200" height="630" fill="#f4f7f6"/>
<rect x="0" y="0" width="1200" height="16" fill="#1F4E4A"/>
<text x="66" y="132" font-family="Georgia,serif" font-size="28" fill="#1F4E4A" letter-spacing="6">WICHAA</text>
<text x="66" y="214" font-family="Georgia,serif" font-size="58" font-weight="700" fill="#141b1a">Where the tradition</text>
<text x="66" y="278" font-family="Georgia,serif" font-size="58" font-weight="700" fill="#141b1a">lives</text>
<text x="66" y="336" font-family="system-ui,sans-serif" font-size="25" fill="#3a4a47">Written in the north. Traded everywhere.</text>
<rect x="66" y="392" width="20" height="20" rx="4" fill="rgba(31,78,74,.72)"/>
<text x="98" y="409" font-family="system-ui,sans-serif" font-size="23" fill="#141b1a">{tot_m:,} manuscripts, from {n_mss} provinces</text>
<circle cx="76" cy="452" r="10" fill="#b8892f" opacity=".85"/>
<text x="98" y="460" font-family="system-ui,sans-serif" font-size="23" fill="#141b1a">{tot_k:,} amulets on sale, from {n_mkt}</text>
<text x="66" y="546" font-family="system-ui,sans-serif" font-size="20" fill="#3a4a47">wichaa.net/w/geo</text>
{"".join(land)}
{"".join(dots)}
</svg>"""


def _widgets_card_svg() -> str:
    """Card for /widgets. The subject is a toolbox, not one artefact, so it says
    what the page is and names what is in it -- generated from wiki.SIDE_TOOLS so it
    cannot drift out of date as tools are added."""
    import wiki

    names = [w["name"] for w in wiki.SIDE_TOOLS]
    listing = " \u00b7 ".join(names) if names else "coming soon"
    n = len(names)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
<rect width="1200" height="630" fill="#f7f4ee"/>
<rect x="0" y="0" width="1200" height="16" fill="#0d8a8a"/>
<text x="600" y="150" font-family="Georgia,serif" font-size="34" fill="#0d8a8a"
      text-anchor="middle" letter-spacing="6">WICHAA</text>
<text x="600" y="278" font-family="Georgia,serif" font-size="96" font-weight="700"
      fill="#22201c" text-anchor="middle">Widgets &amp; shit</text>
<text x="600" y="350" font-family="system-ui,sans-serif" font-size="34"
      fill="#5d5750" text-anchor="middle">small free tools that do one thing</text>
<rect x="270" y="410" width="660" height="88" rx="20" fill="#fff" stroke="#0d8a8a" stroke-width="3"/>
<text x="600" y="466" font-family="system-ui,sans-serif" font-size="32" font-weight="700"
      fill="#22201c" text-anchor="middle">{listing}</text>
<text x="600" y="562" font-family="system-ui,sans-serif" font-size="27"
      fill="#5d5750" text-anchor="middle">{n} tool{"" if n == 1 else "s"} \u00b7 no accounts \u00b7 no tracking \u00b7 never in an app store</text>
</svg>"""


def find_browser() -> str | None:
    for path in CHROME_CANDIDATES:
        if Path(path).is_file():
            return path
    return shutil.which("chromium") or shutil.which("google-chrome")


def render(svg: str, out: Path, width: int = 1200, height: int = 630) -> None:
    browser = find_browser()
    if not browser:
        raise SystemExit(
            "No Chrome/Chromium found. The card is a committed master, so an existing\n"
            f"{out} stays valid — install Chrome only when the artwork changes."
        )
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "card.html"
        # margin:0 so the SVG sits flush in the viewport; the screenshot is the
        # viewport, and any body margin would shift the artwork inside the frame.
        page.write_text(
            "<!doctype html><meta charset=utf-8>"
            "<style>html,body{margin:0;padding:0;background:#132420}"
            "svg{display:block}</style>" + svg,
            encoding="utf-8",
        )
        # --headless (not =new): measured on Chrome 150, the new mode writes the PNG
        # and then never exits, so a plain subprocess.run() hangs until timeout. The
        # old mode is also what actually produces a 1200x630 file — exactly the
        # OpenGraph size, no rescaling needed.
        cmd = [
            browser, "--headless", "--disable-gpu", "--hide-scrollbars",
            "--no-sandbox", "--no-first-run", "--no-default-browser-check",
            "--disable-extensions", "--virtual-time-budget=3000",
            f"--window-size={width},{height}",
            f"--screenshot={out}", "--user-data-dir=" + tmp + "/profile",
            page.as_uri(),
        ]
        if out.exists():
            out.unlink()  # so "file appeared" is a real success signal, not a stale one
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            # Poll for the artefact rather than for the process: Chrome is prone to
            # lingering after the screenshot, and the file is what we actually want.
            for _ in range(600):
                if out.is_file() and out.stat().st_size > 0:
                    time.sleep(0.4)  # let the write finish before we read the size
                    break
                if proc.poll() is not None:
                    break
                time.sleep(0.1)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
        if not out.is_file() or out.stat().st_size == 0:
            err = (proc.stderr.read() or b"").decode(errors="replace")
            raise SystemExit(f"Chrome produced no image.\n{err[-1500:]}")


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(HERE))
    sources = _sources()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", choices=sorted(sources), help="which card to build")
    args = ap.parse_args(argv)

    CARDS.mkdir(parents=True, exist_ok=True)
    out = CARDS / f"{args.name}.png"
    render(sources[args.name](), out)
    kb = out.stat().st_size / 1024
    print(f"{args.name} card → {out}  ({kb:.0f} KB)")
    print("Now run publishing/publish_site.sh to ship it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
