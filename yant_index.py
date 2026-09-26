#!/usr/bin/env python3
"""yant_index — /yant, the named yant designs, indexed by what they are FOR.

/diagrams already gathers every drawn page in the corpus, but as one
undifferentiated wall: described-first, newest volume wherever it lands. A reader
who wants "the paired-sarika" or "the ones worked for metta" has no way in. That
is the gap this fills, and it is the same move /need and /nuea make — enter by
the tradition's own category, not by a shelf number.

The data is CURATED, not scraped. data/yant_designs.json was read out of the
plates' own vision descriptions volume by volume; a regex over them yields
mostly noise (นะโม is a katha opening, ยันต์นี้ลงข้างหน้า is an instruction).
Every entry cites the manuscript and page it came from, and carries
`captioned: false` when the plate bears no caption and the reading is from the
figure alone — so a reader can always tell curation from source.

Self-contained, like glossary.py and na_gallery.py: reads the JSON, renders each
cited plate straight from its PDF (pdftoppm, on demand) into
docs/pimg/<mid>/<n>.png, then writes its own HTML. Doesn't touch wiki.py or
build_static.py; declared in routes.py with built_by="yant_index.py".

    python3 yant_index.py --docs ../nanobotco-lanna/docs --site-url https://wichaa.net

Writes  docs/yant/index.html  +  docs/api/yant-designs.json  +  docs/pimg/<mid>/<n>.png
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CRAWLER = HERE.parent / "manuscript-crawler"
DB = CRAWLER / "crawler" / "catalog.db"
CONTRIB = CRAWLER / "contributed" / "thai_wichaa_texts"
DESIGNS_JSON = HERE / "data" / "yant_designs.json"


def pdftoppm_bin() -> str:
    """Absolute path to pdftoppm, or a clear SystemExit.

    Same guard as na_gallery.py (kept local — these renderers are deliberately
    self-contained): launchd's default PATH has no Homebrew dir, and a bare
    "pdftoppm" from there is a FileNotFoundError traceback that takes the whole
    publish down. Look it up, try the two Homebrew locations, then say so.
    """
    found = shutil.which("pdftoppm")
    if found:
        return found
    for p in ("/opt/homebrew/bin/pdftoppm", "/usr/local/bin/pdftoppm"):
        if Path(p).is_file():
            return p
    raise SystemExit("yant_index: pdftoppm not found (brew install poppler), "
                     "and launchd PATH has no Homebrew dir — cannot render plates")


# ---------------------------------------------------------------- source PDFs

def pdf_for(mid: int, conn) -> Path | None:
    """Map a manuscript id to its contributed PDF via the slug the crawler stored
    in source_identifier, matched against the contributed manifest. Doing it
    through the manifest rather than hardcoding filenames means a re-download
    under a different name still resolves."""
    row = conn.execute("SELECT source_identifier FROM manuscripts WHERE id=?",
                       (mid,)).fetchone()
    if not row or not row[0]:
        return None
    slug = row[0]
    manifest = CONTRIB / "manifest.json"
    if not manifest.is_file():
        return None
    for m in json.loads(manifest.read_text(encoding="utf-8")):
        if m.get("slug") and m["slug"] in slug:
            p = CONTRIB / m["new"]
            return p if p.is_file() else None
    return None


def cited_pages(data: dict) -> dict[int, set[int]]:
    """Every (manuscript, page) the index points at — headline plates, variants,
    and the ornament run — so each is bundled exactly once."""
    want: dict[int, set[int]] = {}
    for d in data["designs"]:
        want.setdefault(d["ms"], set()).add(d["page"])
        for v in d.get("variants", []):
            want.setdefault(v["ms"], set()).add(v["page"])
    orn = data.get("ornament") or {}
    for p in orn.get("pages", []):
        want.setdefault(6985, set()).add(p)
    return want


def bundle(docs: Path, want: dict[int, set[int]], conn) -> int:
    """Render each cited page to docs/pimg/<mid>/<n>.png at 150dpi. Skips whatever
    is already bundled, so a re-run costs nothing and other tools' renders stand."""
    n = 0
    pdftoppm = pdftoppm_bin()
    for mid, pages in sorted(want.items()):
        pdf = pdf_for(mid, conn)
        if not pdf:
            print(f"yant_index: no source PDF for ms{mid}, skipping its plates",
                  file=sys.stderr)
            continue
        dest_dir = docs / "pimg" / str(mid)
        dest_dir.mkdir(parents=True, exist_ok=True)
        for p in sorted(pages):
            dest = dest_dir / f"{p}.png"
            if dest.is_file():
                continue
            tmp = dest_dir / f"_tmp{p}"
            r = subprocess.run([pdftoppm, "-f", str(p), "-l", str(p), "-png",
                                "-r", "150", str(pdf), str(tmp)], capture_output=True)
            if r.returncode != 0:
                continue
            got = list(dest_dir.glob(f"_tmp{p}-*.png"))
            if got:
                got[0].replace(dest)
                n += 1
    return n


# ---------------------------------------------------------------- assembly

def build_payload(data: dict, conn) -> dict:
    """The JSON the page renders from: designs with their plate paths resolved and
    their virtue labels denormalised, plus the facet counts the directory-style
    nav needs. Virtue families attested in the treatises but carrying no plate are
    kept with a zero count rather than dropped — an empty shelf that says WHY is
    information; one that silently vanishes is not."""
    virtues = data["_virtues"]
    sources = data["_sources"]
    out = []
    for d in data["designs"]:
        plates = [{"ms": d["ms"], "page": d["page"]}] + [
            {"ms": v["ms"], "page": v["page"]} for v in d.get("variants", [])]
        out.append({
            "slug": d["slug"], "th": d["th"], "translit": d["translit"], "en": d["en"],
            "roots": d.get("roots", ""), "desc": d["desc"], "note": d.get("note", ""),
            "living": d.get("living", ""),
            "captioned": d["captioned"], "script": d.get("script", "none"),
            "figure": d.get("figure", []), "virtues": d["virtues"],
            "placement": d.get("placement", ""),
            "seeAlso": d.get("see_also", ""),
            "ms": d["ms"], "page": d["page"],
            "source": sources.get(str(d["ms"]), ""),
            "plates": [{"ms": p["ms"], "page": p["page"],
                        "img": f"/pimg/{p['ms']}/{p['page']}.png"} for p in plates],
        })

    vcount = {k: 0 for k in virtues}
    fcount: dict[str, int] = {}
    for d in out:
        for v in d["virtues"]:
            vcount[v] = vcount.get(v, 0) + 1
        for f in d["figure"]:
            fcount[f] = fcount.get(f, 0) + 1

    # How often each virtue is NAMED in the treatises' own text, counted across
    # every digested page. This is the honest companion to the plate count: a
    # family can be heavily written about and never drawn (แคล้วคลาด is named on
    # ~100 pages and captioned on no plate at all), and a page that showed only
    # "(0)" would misreport that as absence rather than as a difference between
    # what the manuals SAY and what they DRAW.
    vpages = {k: None for k in virtues}
    if conn is not None:
        for k, v in virtues.items():
            term = v.get("th_search")
            if not term:
                continue
            try:
                vpages[k] = conn.execute(
                    "SELECT count(*) FROM pages WHERE transcription LIKE ? "
                    "OR translation LIKE ?", (f"%{term}%", f"%{term}%")).fetchone()[0]
            except sqlite3.Error:
                vpages[k] = None

    return {
        "designs": out,
        "virtues": [{"key": k, **v, "n": vcount.get(k, 0),
                     "corpusPages": vpages.get(k)} for k, v in virtues.items()],
        "figures": [{"key": k, "n": n} for k, n in
                    sorted(fcount.items(), key=lambda x: (-x[1], x[0]))],
        "sources": [{"ms": int(k), "title": v} for k, v in sorted(sources.items())],
        "ornament": data.get("ornament", {}),
        "living": data.get("living", {}),
        "key": data.get("key", {}),
        "count": len(out),
        "plateCount": len({(p["ms"], p["page"]) for d in out for p in d["plates"]}),
    }


def render_page(payload: dict, site: str) -> str:
    first = payload["designs"][0]["plates"][0] if payload["designs"] else None
    ogimg = f"{site}{first['img']}" if first else f"{site}/og.jpg"
    desc = (f"{payload['count']} named yant designs from the Lanna corpus — by Thai "
            f"name, by figure, and by what each one is worked for — each paired with "
            f"the plate it was drawn on.")
    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": "The yant designs", "url": f"{site}/yant",
        "description": desc,
        "mainEntity": {"@type": "ItemList", "numberOfItems": payload["count"]},
    }, ensure_ascii=False)
    return PAGE.replace("{{SITE}}", site) \
        .replace("{{DESC}}", desc) \
        .replace("{{COUNT}}", str(payload["count"])) \
        .replace("{{PLATES}}", str(payload["plateCount"])) \
        .replace("{{OGIMG}}", ogimg).replace("{{JSONLD}}", jsonld) \
        .replace("{{DATA}}", json.dumps(payload, ensure_ascii=False))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", required=True, help="the published docs/ directory")
    ap.add_argument("--site-url", default="https://wichaa.net")
    ap.add_argument("--no-bundle", action="store_true",
                    help="skip page rendering (HTML only)")
    a = ap.parse_args(argv)

    docs = Path(a.docs).expanduser().resolve()
    if not docs.is_dir():
        raise SystemExit(f"yant_index: docs directory not found: {docs}")
    if not DESIGNS_JSON.is_file():
        raise SystemExit(f"yant_index: {DESIGNS_JSON} not found")
    data = json.loads(DESIGNS_JSON.read_text(encoding="utf-8"))

    conn = sqlite3.connect(DB) if DB.is_file() else None
    if conn is None:
        print(f"yant_index: catalog.db not at {DB} — plates cannot be bundled",
              file=sys.stderr)

    bundled = 0
    if conn is not None and not a.no_bundle:
        bundled = bundle(docs, cited_pages(data), conn)

    payload = build_payload(data, conn)
    if conn is not None:
        conn.close()

    (docs / "api").mkdir(parents=True, exist_ok=True)
    (docs / "api" / "yant-designs.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out = docs / "yant"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(render_page(payload, a.site_url.rstrip("/")),
                                    encoding="utf-8")

    print(f"yant_index: {payload['count']} designs across {payload['plateCount']} "
          f"plates; {bundled} page image(s) newly rendered")
    print(f"            -> {out / 'index.html'}")
    return 0


PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ยันต์ · The yant designs · wichaa</title>
<meta name="description" content="{{DESC}}">
<link rel="canonical" href="{{SITE}}/yant">
<meta property="og:type" content="website">
<meta property="og:site_name" content="wichaa">
<meta property="og:title" content="ยันต์ · The yant designs · wichaa">
<meta property="og:description" content="{{DESC}}">
<meta property="og:url" content="{{SITE}}/yant">
<meta property="og:image" content="{{OGIMG}}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="ยันต์ · The yant designs · wichaa">
<meta name="twitter:image" content="{{OGIMG}}">
<script type="application/ld+json">{{JSONLD}}</script>
<style>
 :root{--bg:#f4efe3;--panel:#fdfbf5;--ink:#26302a;--muted:#6d6455;--gold:#a8791e;
  --gold-soft:#c9a24a;--crimson:#8c3b2e;--line:#e5dcc7;
  --serif:"Sukhumvit Set","Noto Serif Thai",Thonburi,"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
  --sans:"Sukhumvit Set","Noto Sans Thai",Thonburi,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
  font-family:var(--sans);font-size:18px;line-height:1.6}
 a{color:var(--crimson);text-decoration:none}a:hover{text-decoration:underline}
 .wrap{max-width:1180px;margin:0 auto;padding:0 24px}
 header{text-align:center;padding:48px 24px 10px}
 .mark{font-family:var(--serif);letter-spacing:.4em;color:var(--gold);font-size:13px}
 h1{font-family:var(--serif);font-size:clamp(30px,5vw,46px);margin:14px 0 6px}
 .sub{color:#3c463f;font-family:var(--serif);font-style:italic;font-size:19px;
  max-width:720px;margin:0 auto}
 .src{margin-top:12px;font-size:14.5px;color:var(--muted)}

 /* the directory — Term (count), the way in */
 .dir{margin:26px 0 6px;padding:20px 22px;border:1px solid var(--line);border-radius:16px;
  background:linear-gradient(160deg,#fdfbf5f0,#f7f1e2cc);backdrop-filter:blur(6px);
  box-shadow:0 1px 0 #fff inset,0 6px 22px -18px #6d645599}
 .dir h2{font-family:var(--serif);font-size:15px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--gold);margin:0 0 4px}
 .dir p.hint{margin:0 0 12px;font-size:14.5px;color:var(--muted)}
 .terms{display:flex;flex-wrap:wrap;gap:8px 14px;margin:0 0 4px;padding:0;list-style:none}
 .terms li{margin:0}
 .term{display:inline-block;padding:5px 13px;border-radius:999px;font-size:15px;
  border:1.5px solid transparent;background:#f0e8d4;color:var(--crimson);
  transition:transform .13s cubic-bezier(.34,1.56,.64,1),background .15s,border-color .15s,box-shadow .15s;
  cursor:pointer}
 .term:hover{transform:translateY(-2px) scale(1.035);background:#eadfc2;
  box-shadow:0 6px 14px -8px #8c3b2e88}
 .term:active{transform:translateY(0) scale(.97)}
 .term.on{background:var(--crimson);color:#fdfbf5;border-color:var(--crimson);
  box-shadow:0 6px 16px -8px #8c3b2ecc}
 .term .n{opacity:.62;font-size:13px}
 .term.zero{opacity:.5;cursor:default}
 .term.zero:hover{transform:none;box-shadow:none;background:#f0e8d4}
 .th-term{font-family:var(--serif);font-size:16.5px}

 .controls{position:sticky;top:0;background:#f4efe3ee;backdrop-filter:blur(8px);
  border-bottom:1px solid var(--line);padding:12px 0;z-index:5;margin-top:18px}
 .controls .wrap{display:flex;gap:14px;flex-wrap:wrap;align-items:center;justify-content:center}
 #q{flex:1 1 260px;max-width:420px;padding:10px 16px;border:1.5px solid var(--line);
  border-radius:999px;font-size:15.5px;background:var(--panel);color:var(--ink);
  transition:border-color .15s,box-shadow .15s}
 #q:focus{outline:none;border-color:var(--gold-soft);box-shadow:0 0 0 4px #c9a24a2e}
 #cnt{font-size:14.5px;color:var(--muted)}
 #clear{font-size:14px;color:var(--crimson);cursor:pointer;border:0;background:none;
  text-decoration:underline;padding:0}

 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:20px;
  margin:24px 0 40px}
 .card{background:var(--panel);border:1px solid var(--line);border-radius:16px;
  overflow:hidden;scroll-margin-top:84px;display:flex;flex-direction:column;
  transition:transform .18s cubic-bezier(.34,1.4,.64,1),border-color .18s,box-shadow .18s}
 .card:hover{transform:translateY(-3px);border-color:var(--gold-soft);
  box-shadow:0 16px 30px -22px #26302abb}
 .card:target{border-color:var(--gold);box-shadow:0 0 0 3px #a8791e33}
 .shots{display:flex;gap:2px;background:var(--line)}
 .shots a{flex:1 1 0;min-width:0;display:block}
 /* contain, not cover: these are whole manuscript leaves and the design often sits
    low on the page — cropping to the top served a blank margin and hid the yant. */
 .shots img{width:100%;height:270px;object-fit:contain;object-position:center;
  display:block;background:#fffdf7;transition:opacity .2s}
 .shots a:hover img{opacity:.88}
 .body{padding:16px 18px 18px;flex:1 1 auto;display:flex;flex-direction:column}
 .th{font-family:var(--serif);font-size:25px;line-height:1.2}
 .tr{color:var(--gold);font-size:14.5px;font-style:italic;margin-top:3px}
 .en{font-size:15px;margin-top:4px;color:#3c473f}
 .tags{display:flex;flex-wrap:wrap;gap:6px;margin:11px 0 0}
 .tag{font-size:12.5px;padding:3px 10px;border-radius:999px;background:#efe6d0;
  color:#6b4a2e;white-space:nowrap}
 .tag.v{background:#e7ecdf;color:#3f5b3a}
 .tag.uncap{background:#f2e3e0;color:#8c3b2e}
 .txt{font-size:14.5px;line-height:1.62;color:#3c473f;margin:12px 0 0}
 .living{margin:11px 0 0;padding:10px 12px;border-left:3px solid var(--gold-soft);
  background:#f7f1e2;font-size:14px;color:#4a4335;border-radius:0 8px 8px 0}
 .living b{color:var(--gold);font-weight:600}
 .meta{margin-top:auto;padding-top:13px;font-size:12.5px;color:var(--muted);
  border-top:1px dotted var(--line)}
 .meta a{color:var(--muted);text-decoration:underline}
 .roots{font-size:13px;color:var(--muted);margin-top:7px;font-style:italic}
 .empty{text-align:center;color:var(--muted);padding:46px 0;font-style:italic}

 /* the interpretive key — the tradition's own rule, before the catalogue */
 .keybox{margin:26px 0 0;padding:22px 24px;border:1px solid var(--line);border-radius:16px;
  background:linear-gradient(150deg,#fdfbf5,#f6efdf)}
 .keybox h2{font-family:var(--serif);font-size:22px;margin:0 0 4px}
 .keylead{margin:0 0 14px;font-size:15px;color:var(--muted)}
 .geom{list-style:none;padding:0;margin:0 0 16px;display:grid;gap:10px;
  grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
 .geom li{background:#fffdf7;border:1px solid var(--line);border-radius:12px;padding:12px 14px}
 .geom .g-th{font-family:var(--serif);font-size:20px}
 .geom .g-tr{color:var(--gold);font-style:italic;font-size:14px}
 .geom .g-mean{font-size:14.5px;margin-top:5px;color:#3c473f}
 .keybox blockquote{margin:0;padding:14px 18px;border-left:3px solid var(--gold-soft);
  background:#fffdf7;border-radius:0 10px 10px 0;font-size:15.5px;line-height:1.62;color:#3c473f}
 .figgloss{margin:12px 0 0;font-family:var(--serif);font-style:italic;font-size:16.5px}

 /* the living layer — our own photographs */
 .living-sec{margin:26px 0 0;padding:22px 24px;border:1px solid var(--line);border-radius:16px;
  background:#fdfbf5}
 .living-sec h2{font-family:var(--serif);font-size:22px;margin:0 0 4px}
 .lgrid{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}
 .lfig{margin:0;background:#fffdf7;border:1px solid var(--line);border-radius:14px;overflow:hidden;
  transition:transform .18s cubic-bezier(.34,1.4,.64,1),box-shadow .18s}
 .lfig:hover{transform:translateY(-3px);box-shadow:0 16px 30px -22px #26302abb}
 .lfig.hero{grid-column:1/-1}
 .lfig img{width:100%;display:block;background:#efe7d5}
 .lfig.hero img{max-height:520px;object-fit:cover;object-position:center 40%}
 .lfig figcaption{padding:13px 16px;font-size:14.5px;line-height:1.6;color:#3c473f}
 .lcredit{margin:16px 0 0;font-size:13.5px;color:var(--muted);border-top:1px dotted var(--line);
  padding-top:12px}
 .lajarn{margin:10px 0 0;font-size:14.5px;color:#3c473f}
 .lajarn b{font-family:var(--serif);font-size:16px}
 .orn{margin:10px 0 60px;padding:20px 22px;border:1px dashed var(--line);
  border-radius:16px;background:#faf6ea}
 .orn h2{font-family:var(--serif);font-size:21px;margin:0 0 6px}
 .orn p{margin:0;font-size:14.5px;color:#3c473f}
 footer{border-top:1px solid var(--line);padding:26px 0 60px;text-align:center;
  font-size:14px;color:var(--muted)}
 @media (max-width:640px){.shots img{height:200px}}
</style>
</head><body>

<header>
  <div class="mark">WICHAA</div>
  <h1>ยันต์ · The yant designs</h1>
  <p class="sub">The named designs, gathered out of the treatises' own plates — each one
     entered the way the tradition enters it: by what it is <em>for</em>.</p>
  <p class="src">{{COUNT}} designs · {{PLATES}} plates · read from four volumes of the corpus</p>
</header>

<div class="wrap">
  <section id="key" class="keybox">
    <h2>How to read one</h2>
    <p class="keylead">Before the designs, the rule the treatises give for reading them. The shapes
       are not ornament and the creatures are not chosen for looks.</p>
    <p class="keylead">The treatises also give the <em>order</em> the letters go in, which the
       finished plate does not show. One of them lays them by the knight's move —
       <a href="/kesa/">ยันต์เกศาผิด writes the thirty-two parts of the body that way</a>.</p>
    <ul id="geom" class="geom"></ul>
    <blockquote id="figrule"></blockquote>
    <p id="figgloss" class="figgloss"></p>
  </section>

  <section id="living" class="living-sec" hidden>
    <h2>Worked today</h2>
    <p class="keylead" id="livinglead"></p>
    <div class="lgrid" id="lgrid"></div>
    <p class="lcredit" id="lcredit"></p>
  </section>

  <div class="dir">
    <h2>By virtue — what the design is worked for</h2>
    <p class="hint">The tradition's own families, in its own words. A design often carries
       more than one. Where a family is named in the treatises but appears on no plate,
       the count says so — the manuals write about more than they draw.</p>
    <ul class="terms" id="vterms"></ul>
  </div>
  <div class="dir" style="margin-top:14px">
    <h2>By figure — what is drawn</h2>
    <p class="hint">Birds, beasts, teachers, grids and numbers.</p>
    <ul class="terms" id="fterms"></ul>
  </div>
</div>

<div class="controls"><div class="wrap">
  <input id="q" type="search" placeholder="ค้นหา · search name, figure, or meaning" autocomplete="off">
  <span id="cnt"></span>
  <button id="clear" hidden>clear all</button>
</div></div>

<div class="wrap">
  <div class="grid" id="grid"></div>
  <div class="orn" id="orn" hidden>
    <h2>And the flash that carries no spell</h2>
    <p id="ornTxt"></p>
  </div>
</div>

<footer><div class="wrap">
  Every entry cites the manuscript and page it was read from. Where a plate carries no
  caption, the card says so — the reading is from the figure alone.
  · <a href="/diagrams">every drawn page</a>
  · <a href="/na/">the 108 na</a>
  · <a href="/kesa/">the thirty-two parts</a>
  · <a href="/a?s=entity:yantra">the yantra article</a>
</div></footer>

<script>
const D = {{DATA}};
const grid = document.getElementById('grid');
const q = document.getElementById('q');
const cnt = document.getElementById('cnt');
const clearBtn = document.getElementById('clear');
const selV = new Set(), selF = new Set();

const FIGLABEL = {
  na_square:'na-square', script_column:'script column', money_bag:'money bag',
  number_grid:'number grid', bearer_figure:'bearer figure', lotus_pedestal:'lotus pedestal',
  face_crown:'face-crown', gourd_form:'gourd form', prasat_crown:'prasat crown',
  diamond_grid:'diamond grid', knot_corners:'knot corners', na_syllables:'na syllables',
  square_grid:'square grid'
};
const fig = k => FIGLABEL[k] || k.replace(/_/g,' ');

function termLi(html, on, zero, onclick){
  const li = document.createElement('li');
  const b = document.createElement('span');
  b.className = 'term' + (on?' on':'') + (zero?' zero':'');
  b.innerHTML = html;
  if(!zero) b.onclick = onclick;
  li.append(b); return li;
}

function drawTerms(){
  const vt = document.getElementById('vterms'); vt.textContent='';
  for(const v of D.virtues){
    const zero = v.n === 0;
    // A family with no plate still gets its page-count shown, so "not drawn"
    // never reads as "not in the tradition".
    const tail = zero && v.corpusPages
      ? `<span class="n">(named on ${v.corpusPages} pages, drawn on none)</span>`
      : `<span class="n">(${v.n})</span>`;
    vt.append(termLi(
      `<span class="th-term">${v.th}</span> ${v.translit} ${tail}`,
      selV.has(v.key), zero,
      () => { selV.has(v.key) ? selV.delete(v.key) : selV.add(v.key); render(); }));
  }
  const ft = document.getElementById('fterms'); ft.textContent='';
  for(const f of D.figures){
    ft.append(termLi(`${fig(f.key)} <span class="n">(${f.n})</span>`,
      selF.has(f.key), false,
      () => { selF.has(f.key) ? selF.delete(f.key) : selF.add(f.key); render(); }));
  }
}

function matches(d){
  if(selV.size && !d.virtues.some(v => selV.has(v))) return false;
  if(selF.size && !d.figure.some(f => selF.has(f))) return false;
  const t = q.value.trim().toLowerCase();
  if(!t) return true;
  return [d.th, d.translit, d.en, d.desc, d.roots, d.placement, d.living,
          ...d.figure.map(fig)].join(' ').toLowerCase().includes(t);
}

function vLabel(key){
  const v = D.virtues.find(x => x.key === key);
  return v ? `${v.th} ${v.translit}` : key;
}

function card(d){
  const el = document.createElement('article');
  el.className = 'card'; el.id = 'y-' + d.slug;

  const shots = document.createElement('div'); shots.className='shots';
  for(const p of d.plates.slice(0,3)){
    const a = document.createElement('a');
    a.href = p.img; a.target='_blank'; a.rel='noopener';
    a.title = `ms${p.ms} p.${p.page} — open the full plate`;
    const img = document.createElement('img');
    img.src = p.img; img.loading='lazy';
    img.alt = `${d.translit} — plate from manuscript ${p.ms}, page ${p.page}`;
    a.append(img); shots.append(a);
  }
  el.append(shots);

  const b = document.createElement('div'); b.className='body';
  b.insertAdjacentHTML('beforeend',
    `<div class="th">${d.th}</div><div class="tr">${d.translit}</div>` +
    `<div class="en">${d.en}</div>` +
    (d.roots ? `<div class="roots">${d.roots}</div>` : ''));

  const tags = document.createElement('div'); tags.className='tags';
  for(const v of d.virtues){
    const s=document.createElement('span'); s.className='tag v';
    s.textContent = vLabel(v); tags.append(s);
  }
  for(const f of d.figure.slice(0,4)){
    const s=document.createElement('span'); s.className='tag';
    s.textContent = fig(f); tags.append(s);
  }
  if(!d.captioned){
    const s=document.createElement('span'); s.className='tag uncap';
    s.textContent='plate uncaptioned'; tags.append(s);
  }
  b.append(tags);

  b.insertAdjacentHTML('beforeend', `<p class="txt">${d.desc}</p>`);
  if(d.note) b.insertAdjacentHTML('beforeend', `<p class="txt">${d.note}</p>`);
  if(d.living) b.insertAdjacentHTML('beforeend',
    `<p class="living"><b>Still worked today —</b> ${d.living}</p>`);

  const plates = d.plates.map(p => `p.${p.page}`).join(', ');
  b.insertAdjacentHTML('beforeend',
    `<div class="meta">${d.placement ? 'Placed: ' + d.placement + ' · ' : ''}` +
    `${d.source} · <a href="/m?id=${d.ms}#pages">ms${d.ms}</a> ${plates}` +
    (d.seeAlso ? ` · <a href="/a?s=${d.seeAlso}">${d.seeAlso.split(':')[1]}</a>` : '') +
    `</div>`);
  el.append(b);
  return el;
}

function render(){
  drawTerms();
  const hits = D.designs.filter(matches);
  grid.textContent = '';
  if(!hits.length){
    grid.insertAdjacentHTML('beforeend',
      '<p class="empty">Nothing under that combination yet — try one term at a time.</p>');
  } else {
    for(const d of hits) grid.append(card(d));
  }
  const filtered = selV.size || selF.size || q.value.trim();
  cnt.textContent = filtered ? `${hits.length} of ${D.count}` : `${D.count} designs`;
  clearBtn.hidden = !filtered;

  const orn = document.getElementById('orn');
  if(D.ornament && D.ornament.desc && !filtered){
    document.getElementById('ornTxt').textContent = D.ornament.desc;
    orn.hidden = false;
  } else orn.hidden = true;
}

// --- the interpretive key -------------------------------------------------
(function drawKey(){
  const K = D.key || {};
  const g = document.getElementById('geom');
  for(const e of (K.geometry || [])){
    const li = document.createElement('li');
    li.innerHTML = `<div class="g-th">${e.th}</div><div class="g-tr">${e.translit} · ${e.en}</div>` +
                   `<div class="g-mean">${e.means}</div>`;
    g.append(li);
  }
  if(K.figure_rule_en){
    document.getElementById('figrule').innerHTML =
      `<div style="font-family:var(--serif);font-size:16px;margin-bottom:8px">${K.figure_rule_th || ''}</div>` +
      `<div>${K.figure_rule_en}</div>`;
  }
  if(K.gloss) document.getElementById('figgloss').textContent = K.gloss;
  if(!(K.geometry || []).length && !K.figure_rule_en) document.getElementById('key').hidden = true;
})();

// --- the living layer -----------------------------------------------------
(function drawLiving(){
  const L = D.living || {};
  const photos = L.photos || [];
  if(!photos.length) return;
  const sec = document.getElementById('living');
  document.getElementById('livinglead').textContent =
    'The same designs, off the page. Photographs from a single session in Chiang Mai.';
  const grid = document.getElementById('lgrid');
  for(const p of photos){
    const fig = document.createElement('figure');
    fig.className = 'lfig' + (p.hero ? ' hero' : '');
    const img = document.createElement('img');
    img.src = p.img; img.alt = p.alt || ''; img.loading = 'lazy';
    const cap = document.createElement('figcaption');
    cap.innerHTML = p.caption || '';
    fig.append(img, cap); grid.append(fig);
  }
  let credit = L.credit || '';
  for(const a of (L.ajarns || [])){
    credit += `<div class="lajarn"><b>${a.name}</b> — ${a.detail}</div>`;
  }
  if(L.link) credit += `<div class="lajarn"><a href="${L.link.href}" rel="noopener">${L.link.label}</a></div>`;
  document.getElementById('lcredit').innerHTML = credit;
  sec.hidden = false;
})();

q.addEventListener('input', render);
clearBtn.onclick = () => { selV.clear(); selF.clear(); q.value=''; render(); };
render();
if(location.hash){ const t=document.querySelector(location.hash); if(t) t.scrollIntoView(); }
</script>
</body></html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
