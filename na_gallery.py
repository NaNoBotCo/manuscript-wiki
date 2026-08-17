#!/usr/bin/env python3
"""na_gallery — a visual, one-by-one card gallery for the na compendium.

crawler/na_compendium.py slices manuscript #6964 into 142 individual na entries
(name, formula, translation, attribution) but that's still just structured text.
This is the point of the whole exercise: pair EVERY entry with the actual page
image it was drawn on, so reading a na's meaning and SEEING its glyph happen
together, not as a wall of text with no visual reference.

Self-contained, like glossary.py: reads crawler/na_compendium.json, renders each
distinct source page straight from the PDF (pdftoppm — the same on-demand approach
used everywhere else in this project) and bundles it into docs/pimg/<mid>/<n>.png,
then writes its own HTML + API JSON. Doesn't touch wiki.py or build_static.py.

    python3 na_gallery.py --docs ../nanobotco-lanna/docs --site-url https://wichaa.net
Writes  docs/api/na-compendium.json  +  docs/na/index.html  + docs/pimg/6964/<n>.png
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CRAWLER = HERE.parent / "manuscript-crawler"
COMPENDIUM_JSON = CRAWLER / "na_compendium.json"
PDF = (CRAWLER / "contributed" / "thai_wichaa_texts" /
       "katha_scripture-of-108-magical-na_คัมภีร์108นะวิเศษ.pdf")
MANUSCRIPT_ID = 6964


def ensure_compendium() -> dict:
    """Regenerate na_compendium.json fresh from the current catalogue (cheap, pure
    SQL + text parsing, no LLM calls) so the gallery never serves stale data."""
    script = CRAWLER / "na_compendium.py"
    if script.is_file():
        subprocess.run([sys.executable, str(script)], cwd=str(CRAWLER), check=False)
    if not COMPENDIUM_JSON.is_file():
        raise SystemExit(f"na_gallery: {COMPENDIUM_JSON} not found and could not be built")
    return json.loads(COMPENDIUM_JSON.read_text(encoding="utf-8"))


def bundle_pages(docs: Path, pages: set[int]) -> int:
    """Render each distinct source page to docs/pimg/6964/<n>.png via pdftoppm —
    the same live-PDF-render approach used elsewhere for this contributed volume
    (its prose-page PNGs aren't kept on disk long-term; only re-rendered on demand).
    Skips a page that's already bundled (e.g. by another tool)."""
    if not PDF.is_file():
        print(f"na_gallery: source PDF not found at {PDF}", file=sys.stderr)
        return 0
    dest_dir = docs / "pimg" / str(MANUSCRIPT_ID)
    dest_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in sorted(pages):
        dest = dest_dir / f"{p}.png"
        if dest.is_file():
            continue
        with_tmp = dest_dir / f"_tmp{p}"
        r = subprocess.run(["pdftoppm", "-f", str(p), "-l", str(p), "-png", "-r", "150",
                            str(PDF), str(with_tmp)], capture_output=True)
        if r.returncode != 0:
            continue
        rendered = list(dest_dir.glob(f"_tmp{p}-*.png"))
        if rendered:
            rendered[0].replace(dest)
            n += 1
    return n


NA_GENRE_MARK = "na"  # tags the diagram cards we inject, so re-runs replace not duplicate


def na_diagram_card(e: dict) -> dict:
    """One na entry → a diagram card in the exact shape /diagrams' page renders
    (title/desc/src/full/href/n/genreLabel). The image is the page the glyph was
    drawn on (we have no per-glyph bounding box, so the page IS the honest image);
    the glyph's own `[diagram: …]` description is the caption; the title links to
    the na's full compendium card; the source monk/temple rides the metadata line."""
    page = e["page_start"]
    desc = (e["diagrams"][0] if e.get("diagrams") else e.get("name_en", "")).strip()
    name_en = (e.get("name_en") or "").strip()
    title = e["name_th"] + (" · " + name_en if name_en else "")
    return {
        "mid": MANUSCRIPT_ID, "n": page, "title": title,
        "genre": NA_GENRE_MARK,
        "genreLabel": ", ".join(e.get("source_notes") or []),
        "desc": desc[:400],
        "src": f"/pimg?mid={MANUSCRIPT_ID}&n={page}&w=400",
        "full": f"/pimg?mid={MANUSCRIPT_ID}&n={page}&w=1400",
        "href": f"/na/#na-{e['id']}",
    }


def merge_into_diagrams(docs: Path, data: dict) -> int:
    """Merge the na entries into the already-built docs/api/diagrams.json as their
    own cards, so they show on the corpus-wide /diagrams page too. Idempotent: drops
    any na cards a previous run injected before re-adding, so it never duplicates
    (build_static.py rewrites diagrams.json fresh each publish anyway; this makes a
    bare re-run of na_gallery safe as well). No wiki.py change — this patches the
    generated JSON the existing DIAGRAMS_PAGE already renders."""
    dpath = docs / "api" / "diagrams.json"
    if not dpath.is_file():
        return 0
    dj = json.loads(dpath.read_text(encoding="utf-8"))
    dj["diagrams"] = [x for x in dj.get("diagrams", []) if x.get("genre") != NA_GENRE_MARK]
    dj["sources"] = [s for s in dj.get("sources", []) if not s.get("na")]
    cards = [na_diagram_card(e) for e in data["entries"]]
    dj["diagrams"] += cards
    dj["described"] = sum(1 for x in dj["diagrams"] if (x.get("desc") or "").strip())
    dj["total"] = len(dj["diagrams"])
    dj["sources"].append({"mid": MANUSCRIPT_ID,
                          "title": data.get("titleEnglish") or "Scripture of 108 Magical Na",
                          "n": len(cards), "na": True})
    dj["sources"].sort(key=lambda x: -x["n"])
    dpath.write_text(json.dumps(dj, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(cards)


def render_page(data: dict, site: str) -> str:
    entries_json = json.dumps(data["entries"], ensure_ascii=False)
    # A representative na page image, so a shared /na/ link unfurls with an actual
    # glyph instead of nothing — the first entry's first page, same "pick one real
    # thing" approach as the site's other og:image fallbacks.
    entries = data.get("entries") or []
    first_page = entries[0]["pages"][0] if entries and entries[0].get("pages") else None
    ogimg = f"{site}/pimg/{MANUSCRIPT_ID}/{first_page}.png" if first_page else f"{site}/og.jpg"
    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": "The 108 Na", "url": f"{site}/na/",
        "description": f"Every na (sacred syllable-glyph) from the Scripture of 108 Magical "
                       f"Na, paired one by one with the actual page it was drawn on — "
                       f"{data['count']} entries.",
        "isPartOf": {"@type": "Manuscript", "name": data.get("titleEnglish", ""),
                     "url": f"{site}/m/{MANUSCRIPT_ID}/"},
        "mainEntity": {"@type": "ItemList", "numberOfItems": data["count"]},
    }, ensure_ascii=False)
    return PAGE.replace("{{SITE}}", site).replace("{{MID}}", str(MANUSCRIPT_ID)) \
        .replace("{{COUNT}}", str(data["count"])) \
        .replace("{{OGIMG}}", ogimg).replace("{{JSONLD}}", jsonld) \
        .replace("{{TITLE_EN}}", data.get("titleEnglish", "")) \
        .replace("{{ENTRIES}}", entries_json)


PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>The 108 Na · wichaa</title>
<meta name="description" content="Every na (sacred syllable-glyph) from the Scripture of 108 Magical Na, paired one by one with the actual page it was drawn on — {{COUNT}} entries.">
<link rel="canonical" href="{{SITE}}/na/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="wichaa">
<meta property="og:title" content="The 108 Na · wichaa">
<meta property="og:description" content="Every na (sacred syllable-glyph) from the Scripture of 108 Magical Na, paired one by one with the actual page it was drawn on — {{COUNT}} entries.">
<meta property="og:url" content="{{SITE}}/na/">
<meta property="og:image" content="{{OGIMG}}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="The 108 Na · wichaa">
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
 .wrap{max-width:1100px;margin:0 auto;padding:0 24px}
 header{text-align:center;padding:48px 24px 18px}
 .mark{font-family:var(--serif);letter-spacing:.4em;color:var(--gold);font-size:13px}
 h1{font-family:var(--serif);font-size:clamp(30px,5vw,46px);margin:14px 0 6px}
 .sub{color:#3c463f;font-family:var(--serif);font-style:italic;font-size:19px;max-width:680px;margin:0 auto}
 .src{margin-top:12px;font-size:14.5px;color:var(--muted)}
 .controls{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);
  padding:14px 0;z-index:5;margin-top:20px}
 .controls .wrap{display:flex;gap:14px;flex-wrap:wrap;align-items:center;justify-content:center}
 #q{flex:1 1 260px;max-width:420px;padding:10px 16px;border:1.5px solid var(--line);
  border-radius:999px;font-size:15.5px;background:var(--panel);color:var(--ink)}
 #cnt{font-size:14.5px;color:var(--muted)}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:18px;
  margin:22px 0 50px}
 .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;
  overflow:hidden;scroll-margin-top:80px;transition:border-color .16s,box-shadow .16s}
 .card:target{border-color:var(--gold);box-shadow:0 0 0 3px #a8791e33}
 .shots{display:flex;gap:2px;background:var(--line)}
 .shots img{flex:1 1 0;min-width:0;width:100%;height:230px;object-fit:cover;
  object-position:top;display:block;background:#e9dfc4}
 .body{padding:16px 18px}
 .th{font-family:var(--serif);font-size:23px;line-height:1.25}
 .en{color:var(--gold);font-size:14.5px;font-style:italic;margin-top:2px}
 .pg{font-size:12.5px;color:var(--muted);margin-top:6px}
 details{margin-top:12px}
 summary{cursor:pointer;font-size:13.5px;color:var(--crimson);font-weight:600;
  list-style:none}
 summary::-webkit-details-marker{display:none}
 summary:before{content:"▸ ";}
 details[open] summary:before{content:"▾ ";}
 .txt{font-size:14.5px;line-height:1.6;color:#3c473f;white-space:pre-wrap;
  margin-top:10px;max-height:260px;overflow-y:auto;padding-right:4px}
 .txt b.hd{color:var(--gold);display:block;margin:8px 0 2px;font-size:12.5px;
  text-transform:uppercase;letter-spacing:.06em}
 .badges{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
 .badge{font-size:12px;background:#eef2f1;color:#3a4a47;border-radius:999px;
  padding:3px 10px}
 .rel{margin-top:10px;font-size:12.5px;color:var(--muted)}
 .rel a{color:var(--muted);text-decoration:underline}
 footer{border-top:1px solid var(--line);padding:30px 0 60px;text-align:center;
  color:var(--muted);font-size:15px}
 .empty{text-align:center;color:var(--muted);padding:60px 20px}
</style></head><body>
<header><div class="mark">wichaa · วิชา</div>
 <h1>The 108 Na</h1>
 <p class="sub">Every na — sacred syllable-glyph — from the {{TITLE_EN}}, paired one
   by one with the actual page it was drawn on. {{COUNT}} entries.</p>
 <p class="src"><a href="/read/{{MID}}/">Read the whole book →</a> ·
   <a href="/">← wichaa.net</a></p></header>
<div class="controls"><div class="wrap">
  <input id="q" type="search" placeholder="Search a na name, formula, or attribution…">
  <span id="cnt"></span>
</div></div>
<main class="wrap"><div class="grid" id="grid"></div></main>
<footer><div class="wrap">
  Extracted from the completed transcription/translation — every field is either a
  heading, transcribed body text, or a <code>[diagram: …]</code> note someone wrote
  while looking at the page. Nothing here is inferred beyond what was read off it.<br>
  Open under <a href="/LICENSE">CC-BY 4.0</a> · <a href="/api/na-compendium.json">na-compendium.json</a>
</div></footer>
<script>
var ENTRIES={{ENTRIES}}, SITE="{{SITE}}", MID="{{MID}}";
function esc(s){var d=document.createElement('div');d.textContent=s||'';return d.innerHTML;}
function byId(id){var m=ENTRIES.filter(function(e){return e.id===id});return m[0];}
function pageImgs(e){
  return e.pages.map(function(p){
    return '<img src="/pimg/'+MID+'/'+p+'.png" alt="'+esc(e.name_th)+' — page '+p+'" loading="lazy">';
  }).join('');
}
function relLinks(ids){
  return ids.slice(0,6).map(function(id){var o=byId(id);
    return o?'<a href="#na-'+o.id+'">'+esc(o.name_th||o.name_en)+'</a>':'';
  }).filter(Boolean).join(', ');
}
function card(e){
  var pageLabel = e.page_start===e.page_end ? ('p.'+e.page_start) : ('p.'+e.page_start+'–'+e.page_end);
  var badges = (e.source_notes||[]).map(function(n){return '<span class="badge">'+esc(n)+'</span>';}).join('');
  var rel = '';
  if(e.related && (e.related.same_source||[]).length){
    rel += '<div class="rel">Same source: '+relLinks(e.related.same_source)+'</div>';
  }
  return '<div class="card" id="na-'+e.id+'">'+
    '<div class="shots">'+pageImgs(e)+'</div>'+
    '<div class="body">'+
      '<div class="th">'+esc(e.name_th)+'</div>'+
      '<div class="en">'+esc(e.name_en)+'</div>'+
      '<div class="pg">'+pageLabel+' · <a href="/read/'+MID+'/#p'+e.page_start+'">read in context →</a></div>'+
      (badges?'<div class="badges">'+badges+'</div>':'')+
      '<details><summary>Formula & translation</summary><div class="txt">'+
        '<b class="hd">Thai</b>'+esc(e.transcription)+
        '<b class="hd">English</b>'+esc(e.translation)+
      '</div></details>'+
      rel+
    '</div></div>';
}
function draw(){
  var q=(document.getElementById('q').value||'').toLowerCase().trim();
  var list=ENTRIES.filter(function(e){
    if(!q) return true;
    return (e.name_th+' '+e.name_en+' '+e.transcription+' '+e.translation+' '+
            (e.source_notes||[]).join(' ')).toLowerCase().indexOf(q)>=0;
  });
  document.getElementById('cnt').textContent=list.length+' of '+ENTRIES.length;
  var grid=document.getElementById('grid');
  grid.innerHTML = list.length ? list.map(card).join('') :
    '<p class="empty">No na matches that.</p>';
}
document.getElementById('q').addEventListener('input',draw);
draw();
if(location.hash) setTimeout(function(){
  var el=document.querySelector(location.hash);
  if(el) el.scrollIntoView({block:'center'});
},80);
</script></body></html>"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the visual na-compendium gallery")
    ap.add_argument("--docs", default=str(HERE.parent / "nanobotco-lanna" / "docs"))
    ap.add_argument("--site-url", default="https://wichaa.net")
    a = ap.parse_args(argv)
    docs = Path(a.docs)
    if not (docs / "api").is_dir():
        print(f"na_gallery: no built site at {docs} (run build_static.py first)", file=sys.stderr)
        return 1

    data = ensure_compendium()
    pages = {p for e in data["entries"] for p in e["pages"]}
    n_bundled = bundle_pages(docs, pages)

    (docs / "api" / "na-compendium.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    gdir = docs / "na"; gdir.mkdir(exist_ok=True)
    (gdir / "index.html").write_text(render_page(data, a.site_url.rstrip("/")), encoding="utf-8")

    n_merged = merge_into_diagrams(docs, data)

    print(f"na_gallery: {data['count']} entries · {len(pages)} page images "
          f"({n_bundled} newly rendered) → na/index.html + api/na-compendium.json "
          f"· merged {n_merged} na cards into /diagrams")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
