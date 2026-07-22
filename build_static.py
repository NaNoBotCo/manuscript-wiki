#!/usr/bin/env python3
"""build_static.py — export the live Lanna Manuscript Wiki as a *static* site that
GitHub Pages can host (Pages runs no Python, so the dynamic wiki.py server can't run
there). The trick: we keep wiki.py's exact HTML/JS unchanged and make the dynamic
fetches resolve against pre-dumped files.

How it works
  • Every page's HTML gets one small inline shim injected right after <body>. The
    shim (a) intercepts window.fetch and maps  /api/…?params  to a static .json file,
    and (b) rewrites <img> src from  /pimg?mid=&n=  to a bundled PNG, and from
    /img?sha=  (the 15 GB of raw scans we deliberately DON'T ship) to a small
    "scan at source" placeholder. Writes (POST) are swallowed read-only.
  • EXCEPTION: each article's single representative image IS bundled (a curated
    ~one-folio-per-article set — tens of files, a few MB — NOT the whole store) so the
    Articles index and article heroes stay visual. Those images' srcs are rewritten in
    the dumped JSON to point straight at the bundled file, so the shim never sees them.
  • We dump every no-arg API to  docs/api/<name>.json , every manuscript detail to
    docs/api/manuscript/<id>.json , every article to  docs/api/article/<slug>.json ,
    a full scan list (sliced client-side) and a search-doc list (searched client-side).
  • We copy the ~258 rendered plates to  docs/pimg/<mid>/<n>.png .

The result in  docs/  is a plain folder of HTML + JSON + PNG. Point GitHub Pages at
it (root site  nanobotco.github.io ) and the whole viewer works, read-only, offline.

    python3 build_static.py            # writes ./docs
    python3 build_static.py --out /tmp/site

Nothing is uploaded. Publishing is a separate, deliberate step (see refresh_site.sh).
"""
import argparse
import html
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Bump when the export shape changes, so a downstream reader can tell which schema
# a given docs/ snapshot was built against (surfaced in api/build-info.json).
GENERATOR_VERSION = "1.1.0"

# Resolve the catalogue + image store the SAME way the launcher does, BEFORE importing
# wiki (wiki reads these from the environment at import time).
_default_db = HERE.parent / "manuscript-crawler" / "crawler" / "catalog.db"
if not _default_db.exists():
    alt = HERE.parent / "crawler" / "catalog.db"
    if alt.exists():
        _default_db = alt
os.environ.setdefault("CATALOG_DB", str(_default_db))
os.environ.setdefault("STORE_DIR", str(Path(os.environ["CATALOG_DB"]).parent / "store"))

import wiki  # noqa: E402  (env must be set first)


# ---- the client shim, injected into every page -----------------------------------
# Must match art() below for /api/article filenames.
SHIM = r"""<script>
(function(){
  "use strict";
  // ---- Lanna Wiki static shim: run the dynamic viewer on a static host ----------
  // BASE lets the same build work at the domain root ('/') or under a project path
  // ('/Lanna/'). All static targets are resolved through S() so they land correctly.
  var BASE = (window.__LANNA_BASE__ || '/');
  if (BASE.charAt(BASE.length-1) !== '/') BASE += '/';
  function S(p){ return BASE + String(p).replace(/^\//,''); }
  var PLACE = 'data:image/svg+xml;utf8,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="260" height="150">'+
    '<rect width="100%" height="100%" fill="#eef2f1"/>'+
    '<text x="50%" y="50%" fill="#3a4a47" font-family="sans-serif" font-size="13" '+
    'text-anchor="middle" dominant-baseline="middle">raw scan — view at source</text></svg>');
  function art(s){ return String(s==null?'':s).replace(/[^A-Za-z0-9]+/g,'_'); }
  function jresp(o){ return new Response(JSON.stringify(o),
    {status:200, headers:{'Content-Type':'application/json; charset=utf-8'}}); }
  var NOARG = {
    '/api/overview':'/api/overview.json','/api/dashboard':'/api/dashboard.json',
    '/api/places':'/api/places.json','/api/lenses':'/api/lenses.json',
    '/api/vocab':'/api/vocab.json','/api/market':'/api/market.json',
    '/api/graph':'/api/graph.json','/api/articles':'/api/articles.json',
    '/api/status':'/api/status.json','/api/manuscripts':'/api/manuscripts.json',
    '/api/graph.jsonld':'/api/graph.jsonld','/api/graph.ttl':'/api/graph.ttl',
    '/api/diagrams':'/api/diagrams.json','/api/findings':'/api/findings.json',
    '/api/activity':'/api/activity.json',
    '/api/expedite':'/api/expedite.json','/api/wats':'/api/wats.json',
    '/api/coverage':'/api/coverage.json','/api/place-types':'/api/place-types.json'
  };
  var _fetch = window.fetch ? window.fetch.bind(window) : function(u){return fetch(u);};

  var _docs=null;
  function loadDocs(){ if(_docs) return Promise.resolve(_docs);
    return _fetch(S('/api/searchdocs.json')).then(function(r){return r.json();})
      .then(function(d){_docs=d;return d;}).catch(function(){_docs=[];return [];}); }
  var _thes=null;
  function loadThes(){ if(_thes) return Promise.resolve(_thes);
    return _fetch(S('/api/thesaurus.json')).then(function(r){return r.json();})
      .then(function(t){_thes=t;return t;}).catch(function(){_thes={};return {};}); }
  // mirrors wiki.py _expand_token: query token -> OR-set of cross-language equivalents
  function expand(tok, thes){
    tok=(tok||'').toLowerCase();
    var members={}; members[tok]=1;
    if(tok.length<2) return Object.keys(members);
    for(var key in thes){
      if(tok===key || (tok.length>=3 && (tok.indexOf(key)>=0 || key.indexOf(tok)>=0))){
        var grp=thes[key]; for(var i=0;i<grp.length;i++) members[grp[i]]=1;
      }
    }
    return Object.keys(members);
  }
  function staticSearch(q){
    q=(q||'').trim(); var out={manuscripts:[],articles:[],query:q};
    if(!q) return Promise.resolve(jresp(out));
    return Promise.all([loadDocs(), loadThes()]).then(function(res){
      var docs=res[0], thes=res[1];
      var groups=q.toLowerCase().split(/\s+/).filter(Boolean)
                  .map(function(t){return expand(t, thes);}).filter(function(g){return g.length;});
      if(!groups.length) return jresp(out);
      var scored=[];
      for(var i=0;i<docs.length;i++){
        var d=docs[i], title=(d.ntitle||'').toLowerCase(), body=(d.nbody||'').toLowerCase();
        var ok=true, score=0, pos=null;
        for(var j=0;j<groups.length;j++){
          var g=groups[j], ghit=0;
          for(var m=0;m<g.length;m++){
            var tk=g[m]; if(!tk) continue;
            if(title.indexOf(tk)>=0) ghit+=12;
            var idx=body.indexOf(tk);
            if(idx>=0){ ghit+=Math.min(body.split(tk).length-1,6); if(pos===null||idx<pos)pos=idx; }
          }
          if(ghit===0){ok=false;break;} score+=ghit;
        }
        if(ok) scored.push([score,d,pos]);
      }
      scored.sort(function(a,b){return b[0]-a[0];});
      for(var k=0;k<scored.length;k++){
        var d2=scored[k][1], pos2=scored[k][2]==null?0:scored[k][2];
        var text=d2.nbody||d2.ntitle||'';
        var snip=text.substr(Math.max(0,pos2-60),200).replace(/\s+/g,' ').trim();
        if(d2.kind==='m'){ if(out.manuscripts.length<60)
          out.manuscripts.push({id:parseInt(d2.ref,10),label:d2.label,snippet:snip}); }
        else { if(out.articles.length<60)
          out.articles.push({key:d2.ref,label:d2.label,snippet:snip}); }
      }
      return jresp(out);
    });
  }

  var _scans=null;
  function loadScans(){ if(_scans) return Promise.resolve(_scans);
    return _fetch(S('/api/scans.all.json')).then(function(r){return r.json();})
      .then(function(d){_scans=d.scans||[];return _scans;}).catch(function(){_scans=[];return [];}); }

  // ---- IIIF on-demand images: /img?sha=&w= -> sized library IIIF URL ------------
  // We ship no scan bytes; a {sha -> IIIF url} map lets every page image load from
  // the originating library, resized via the IIIF size parameter. The <img> src
  // setter is synchronous, so images requested before the map arrives get the
  // placeholder and are re-resolved once it loads (IIIF_Q flush).
  var IIIF=null, IIIF_Q=[], IIIF_LOADING=false;
  function iiifSized(u,w){ w=w||1024;
    return String(u).replace('/full/full/0/default.jpg','/full/'+w+',/0/default.jpg'); }
  function flushIIIF(){ var q=IIIF_Q; IIIF_Q=[];
    for(var i=0;i<q.length;i++){ var it=q[i], u=IIIF[it.sha];
      if(u){ try{ desc.set.call(it.el, iiifSized(u,it.w)); }catch(e){} } } }
  // LAZY: the {sha -> IIIF url} map is ~2.6 MB and only pages that actually render
  // scan images (browse, gallery, manuscript detail) need it. Fetch it on the FIRST
  // /img?sha= request instead of on every page load, so image-free pages (home,
  // articles, findings, market, textbooks) pay zero bytes for it.
  function loadIIIF(){ if(IIIF) return Promise.resolve(IIIF);
    if(IIIF_LOADING) return Promise.resolve(null); IIIF_LOADING=true;
    return _fetch(S('/api/img-iiif.json')).then(function(r){return r.json();})
      .then(function(m){ IIIF=m||{}; flushIIIF(); return IIIF; })
      .catch(function(){ IIIF={}; flushIIIF(); return IIIF; }); }
  function scansSlice(sp){
    var midp=sp.get('mid'); var mid = midp?parseInt(midp,10):null;
    var offset=parseInt(sp.get('offset')||'0',10)||0;
    var limit=parseInt(sp.get('limit')||'120',10)||120;
    var onlyT=(sp.get('only')==='transcribed');
    return loadScans().then(function(all){
      var pool=all.filter(function(s){
        if(mid!==null && s.id!==mid) return false;
        if(onlyT && !s.transcribed) return false;
        return true;
      });
      return jresp({dbPresent:true, scans:pool.slice(offset,offset+limit),
                    offset:offset, limit:limit, total:pool.length});
    });
  }

  window.fetch = function(input, init){
    init = init || {};
    var url;
    try { url = new URL((typeof input==='string')?input:input.url, location.origin); }
    catch(e){ return _fetch(input, init); }
    if(url.origin !== location.origin) return _fetch(input, init);
    var method = (init.method || (typeof input!=='string' && input.method) || 'GET').toUpperCase();
    var p = url.pathname, sp = url.searchParams;
    if(method !== 'GET') return Promise.resolve(jresp({ok:false, readonly:true}));
    if(p==='/api/search') return staticSearch(sp.get('q'));
    if(p==='/api/gallery' && sp.get('source')==='scans') return scansSlice(sp);
    // analysis widgets: /api/w/<name> -> the dumped snapshot; geo.geojson is a real
    // file already, everything else gains a .json extension on disk.
    if(p.indexOf('/api/w/')===0){
      if(p.slice(-8)==='.geojson') return _fetch(S(p), {});
      return _fetch(S(p+'.json'), {});
    }
    if(NOARG[p]) return _fetch(S(NOARG[p]), {});
    if(p==='/api/manuscript') return _fetch(S('/api/manuscript/'+encodeURIComponent(sp.get('id'))+'.json'), {});
    if(p==='/api/article')    return _fetch(S('/api/article/'+art(sp.get('s'))+'.json'), {});
    if(p==='/api/gallery'){
      var src=sp.get('source');
      if(src==='scan-index') return _fetch(S('/api/gallery.scan-index.json'), {});
      return _fetch(S('/api/gallery.json'), {});
    }
    if(p==='/pimg') return _fetch(S('/pimg/'+sp.get('mid')+'/'+sp.get('n')+'.png'), {});
    return _fetch(input, init);
  };

  // internal navigation: app links are baked as root-absolute ('/browse', '/m?id=…').
  // Under a project subpath they must be re-rooted at BASE. A capture-phase click
  // handler does this for every link, however it was created.
  document.addEventListener('click', function(ev){
    if(ev.defaultPrevented || ev.button!==0 || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
    var a = ev.target && ev.target.closest ? ev.target.closest('a[href]') : null;
    if(!a) return;
    if(a.target==='_blank') return;
    var href=a.getAttribute('href');
    if(!href || href.charAt(0)!=='/' || href.charAt(1)==='/') return;  // only root-absolute, not protocol-relative
    if(BASE!=='/' && href.indexOf(BASE)===0) return;                   // already re-rooted
    // '/read?id=N' is a query-string route the live wiki serves dynamically; a
    // static host can't route query strings, so the export ships it as a real
    // path instead (read/N/index.html) — rewrite the click to match.
    var rm = href.match(/^\/read\?id=(\d+)/);
    if(rm){ ev.preventDefault(); location.href = S('read/'+rm[1]+'/'); return; }
    // widget JSON download links point at '/api/w/<name>' (no extension); on disk
    // that snapshot is '<name>.json' — map the download to the real file.
    var wm = href.match(/^\/api\/w\/([a-z]+)$/);
    if(wm){ ev.preventDefault(); location.href = S('api/w/'+wm[1]+'.json'); return; }
    ev.preventDefault();
    location.href = S(href);
  }, true);

  // rewrite <img> src (Object.assign in el() sets the .src property, so this catches it)
  try {
    var proto=HTMLImageElement.prototype;
    var desc=Object.getOwnPropertyDescriptor(proto,'src');
    Object.defineProperty(proto,'src',{configurable:true,enumerable:true,
      get:function(){return desc.get.call(this);},
      set:function(v){
        try{
          var u=new URL(v, location.origin);
          if(u.origin===location.origin){
            if(u.pathname==='/pimg'){
              v=S('/pimg/'+u.searchParams.get('mid')+'/'+u.searchParams.get('n')+'.png');
            } else if(u.pathname==='/img'){
              var sha=u.searchParams.get('sha');
              var w=parseInt(u.searchParams.get('w')||'0',10)||0;
              if(sha && IIIF && IIIF[sha]){ v=iiifSized(IIIF[sha], w); }
              else if(sha && IIIF===null){ IIIF_Q.push({el:this, sha:sha, w:w}); v=PLACE; loadIIIF(); }
              else { v=PLACE; }
            }
          }
        }catch(e){}
        desc.set.call(this,v);
      }});
  } catch(e){}
})();
</script>"""


def art(s):
    """Filesystem-safe slug for an article key — MUST match art() in the shim."""
    return re.sub(r"[^A-Za-z0-9]+", "_", "" if s is None else str(s))


def bundle_article_image(img, out, base, seen):
    """Ship the ONE representative image an article card/hero points at, and rewrite
    its `src` to the bundled static file. This is the deliberate exception to 'we
    don't ship raw scans': it's a curated ~one-folio-per-article set (tens of files,
    a few MB), not the 16 GB store. Two cases:
      · page  → copy the rendered PNG to  pimg/<mid>/<n>.png
      · scan  → write a 480px JPEG thumbnail to  imgthumb/<sha>_480.jpg
    The rewritten src is baked BASE-absolute (e.g. '/Lanna/pimg/6980/18.png') so the
    client's <img> shim leaves it untouched and it resolves under any URL prefix.
    Returns the mutated img, or None if the asset can't be produced (missing page or
    the store drive isn't mounted) — the caller then falls back to a monogram.
    `seen` dedupes assets shared across articles."""
    if not img:
        return None
    kind = img.get("kind")
    if kind == "page":
        mid, n = img.get("mid"), img.get("page")
        if mid is None or n is None:
            return None
        key = ("p", mid, n)
        if key not in seen:
            src = wiki.page_image_path(mid, n)
            if not src or not Path(src).is_file():
                return None
            dst = out / "pimg" / str(mid) / f"{n}.png"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            seen.add(key)
        img["src"] = f"{base}pimg/{mid}/{n}.png"
        return img
    if kind == "scan":
        sha = img.get("sha")
        if not sha:
            return None
        key = ("s", sha)
        if key not in seen:
            tb = wiki.thumb_bytes(sha, 480)  # needs the store drive mounted
            if not tb:
                return None
            dst = out / "imgthumb" / f"{sha}_480.jpg"
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(tb[0])
            seen.add(key)
        img["src"] = f"{base}imgthumb/{sha}_480.jpg"
        return img
    return None


def inject(html_str, base):
    """Insert the shim immediately after <body> so it patches fetch/img before the
    page's own inline scripts run. `base` is baked in so links/fetches resolve under
    the site's URL prefix (root '/' or a project path like '/Lanna/')."""
    marker = "</head><body>"
    if marker not in html_str:
        raise RuntimeError("page template changed; could not find <body> insertion point")
    # The favicon <link> href is root-absolute ('/favicon.svg') in the live wiki.
    # Under a project subpath (e.g. '/Lanna/') that 404s, so rebase it here — the
    # SHIM rewrites <img>/<a> at runtime but not <link rel=icon>.
    html_str = html_str.replace("href='/favicon.svg'", f"href='{base}favicon.svg'")
    html_str = html_str.replace("url('/favicon.svg')", f"url('{base}favicon.svg')")
    base_js = f'<script>window.__LANNA_BASE__={json.dumps(base)};</script>'
    return html_str.replace(marker, marker + base_js + SHIM, 1)


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path, obj):
    write_text(path, json.dumps(obj, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(HERE / "docs"),
                    help="output folder (default: ./docs)")
    ap.add_argument("--base", default="/",
                    help="URL path the site is served under. Root site: '/'. "
                         "GitHub project repo (e.g. NaNoBotCo/Lanna): '/Lanna/'.")
    args = ap.parse_args()
    base = "/" + args.base.strip("/") + "/"
    if base == "//":
        base = "/"

    if not wiki.db_present():
        print(f"ERROR: catalogue not found at {wiki.CATALOG_DB}", file=sys.stderr)
        return 1

    out = Path(args.out).expanduser().resolve()
    if (out / ".git").exists():
        print(f"ERROR: refusing to wipe {out} — it is a git working tree.\n"
              f"Point --out at a 'docs' subfolder of the repo, not the repo root.",
              file=sys.stderr)
        return 1
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    print(f"Building static site → {out}")
    print(f"  catalogue: {wiki.CATALOG_DB}")
    print(f"  base path: {base}")

    # 1. HTML pages -------------------------------------------------------------
    # route → (page constant, human label, kind). This is the SINGLE source of
    # truth about what pages exist: it is written here, where the pages are
    # actually created, and exported as api/pages.json so downstream tools
    # (sitemap, JSON-LD, anything later) read it instead of keeping their own
    # copy. A hand-maintained second list always drifts — site_meta's did, and
    # ended up advertising /map/ and /dashboard/ to crawlers years after both
    # were removed, while /wats and /expedite stayed invisible.
    #
    # kind:  section  — a real page a reader (or crawler) should land on
    #        template — needs query params to mean anything (/m?id=…), so it is
    #                   emitted but never advertised as a destination
    PAGE_SPECS = {
        "index.html":            (wiki.OVERVIEW_PAGE, "Overview", "section"),
        "browse/index.html":     (wiki.INDEX_PAGE, "Browse manuscripts", "section"),
        "m/index.html":          (wiki.DETAIL_PAGE, "Manuscript detail", "template"),
        "status/index.html":     (wiki.STATUS_PAGE, "Status", "section"),
        "a/index.html":          (wiki.ARTICLE_PAGE, "Article", "template"),
        "articles/index.html":   (wiki.ARTICLES_PAGE, "Subject articles", "section"),
        # P2 prune (2026-07-13): /dashboard folded into /status; /map removed —
        # province is a facet on /browse now, and a 6-dot SVG wasn't a real map.
        "graph/index.html":      (wiki.GRAPH_PAGE, "Knowledge graph", "section"),
        "lens/index.html":       (wiki.LENS_PAGE, "Lenses", "section"),
        "vocab/index.html":      (wiki.VOCAB_PAGE, "Vocabulary", "section"),
        "gallery/index.html":    (wiki.GALLERY_PAGE, "Gallery", "section"),
        "market/index.html":     (wiki.MARKET_PAGE, "Living market", "section"),
        "support/index.html":    (wiki.SUPPORT_PAGE, "Support", "section"),
        "diagrams/index.html":   (wiki.DIAGRAMS_PAGE, "Diagrams", "section"),
        "moon/index.html":       (wiki.MOON_PAGE, "The moon complication", "section"),
        # /widgets — small standalone tools. Deliberately NOT part of the corpus
        # taxonomy: they are utilities, and folding them into the archive's facets
        # would muddy both. Add one by appending to wiki.WIDGETS.
        "widgets/index.html":    (wiki.SIDE_TOOLS_PAGE, "Widgets & shit", "section"),
        "findings/index.html":   (wiki.FINDINGS_PAGE, "Discoveries", "section"),
        # activity/ is a STATIC SNAPSHOT (as-of-build state), not a live dashboard —
        # matches this whole export's "consistent, not live" design (see the docstring
        # of publish_site.sh); a truly live feed on a static host is a separate,
        # bigger feature (tracked in PRIORITIES.md), not something to fake here.
        "activity/index.html":   (wiki.ACTIVITY_PAGE, "Activity", "section"),
        # /expedite is served by the live wiki and linked from the landing page, but
        # was missing from this export — so the published door 404'd. Exported now.
        "expedite/index.html":   (wiki.EXPEDITE_PAGE, "St. Expedite", "section"),
        # /wats — temple catalogue of the Lanna north (OSM+Wikidata via sync_wats.py).
        "wats/index.html":       (wiki.WATS_PAGE, "Wats of the Lanna north", "section"),
    }
    manifest = []
    for rel, (htmlstr, label, kind) in PAGE_SPECS.items():
        write_text(out / rel, inject(htmlstr, base))
        manifest.append({"route": rel[:-len("index.html")], "label": label, "kind": kind})
    print(f"  · {len(PAGE_SPECS)} pages")

    # 2. no-arg API dumps --------------------------------------------------------
    api = out / "api"
    api.mkdir(exist_ok=True)
    write_json(api / "overview.json",  wiki.overview_snapshot())
    write_json(api / "dashboard.json", wiki.dashboard_snapshot())
    write_json(api / "places.json",    wiki.places_snapshot())
    write_json(api / "lenses.json",    wiki.lenses_snapshot())
    write_json(api / "vocab.json",     wiki.vocab_snapshot())
    write_json(api / "market.json",    wiki.market_snapshot())
    write_json(api / "graph.json",     wiki.graph_export())
    write_json(api / "graph.jsonld",   wiki.graph_jsonld())
    write_text(api / "graph.ttl",      wiki.graph_turtle())
    # articles.json — bundle each card's representative image (curated, ~1/article)
    img_seen = set()
    _idx = wiki.articles_index()
    _n_card_img = 0
    for _a in _idx.get("articles", []):
        _a["image"] = bundle_article_image(_a.get("image"), out, base, img_seen)
        if _a["image"]:
            _n_card_img += 1
    write_json(api / "articles.json",  _idx)
    print(f"  · {_n_card_img} article thumbnails bundled")
    write_json(api / "status.json",    wiki.status_snapshot())
    write_json(api / "diagrams.json",  wiki.diagrams_snapshot())
    write_json(api / "expedite.json", wiki.expedite_snapshot())
    write_json(api / "wats.json",     wiki.wats_snapshot())
    write_json(api / "coverage.json", wiki.coverage_snapshot())
    write_json(api / "place-types.json", wiki.place_types_snapshot())
    write_json(api / "findings.json",  wiki.findings_index())
    write_json(api / "activity.json",  wiki.activity_snapshot())
    _mbody = wiki.manuscripts_api_body()  # already serialized (str or bytes)
    if isinstance(_mbody, bytes):
        _mbody = _mbody.decode("utf-8")
    write_text(api / "manuscripts.json", _mbody)
    write_json(api / "gallery.json",   wiki.gallery_snapshot())
    write_json(api / "gallery.scan-index.json", wiki.scan_manuscripts())
    # IIIF on-demand: ship a {sha → IIIF image URL} map so page images load straight
    # from the originating library (sized via the IIIF size param in the shim) with
    # zero scan bytes in the repo. This is what lets the corpus scale past a handful
    # of manuscripts without the export ballooning.
    iiif_map = wiki.iiif_image_map()
    write_json(api / "img-iiif.json", iiif_map)
    print(f"  · core APIs  (+{len(iiif_map)} IIIF image URLs)")

    # 2b. Analysis widgets (/w/ index + /w/<name> pages + /api/w/<name> data) ------
    # The live wiki serves these dynamically; the static export never wrote them, so
    # the "Widgets" nav item and every shareable /w/<name> link 404'd on wichaa.net.
    # Export each data widget as a standalone page + a JSON snapshot the shim resolves.
    # `traffic` is intentionally live-only (it counts requests to the running server) —
    # it still gets a page so the index link resolves, but with an empty snapshot so it
    # renders its honest "no traffic recorded" state instead of a frozen, stale number.
    wdir = api / "w"
    wdir.mkdir(exist_ok=True)
    write_text(out / "w" / "index.html", inject(wiki.widgets_index_page(), base))
    STATIC_WIDGETS = ("geo", "prices", "regions", "trends", "products", "answers")
    for wname in STATIC_WIDGETS:
        wdata = wiki.WIDGETS[wname][0]()
        write_json(wdir / f"{wname}.json", wdata)
        write_text(out / "w" / wname / "index.html",
                   inject(wiki.widget_page(wname), base))
        # Portable build: the same widget with its snapshot baked in, so the
        # saved file still draws with no network. Every widget here is supposed
        # to be portable, shareable and downloadable -- a JSON link alone only
        # made the DATA portable, not the widget.
        write_text(out / "w" / wname / f"{wname}-offline.html",
                   inject(wiki.widget_page(wname, data=wdata), base))
    write_json(wdir / "geo.geojson", wiki.geo_geojson())
    # traffic widget dropped (P2, 2026-07-13): it counts requests to the live server,
    # which a static mirror can't have — it only ever rendered an all-zeros "no traffic"
    # panel. The remaining widgets are shareable data views; the Widgets nav tab itself
    # is gone (see NAV in wiki.py), the map/prices/regions story now lives on /market.
    print(f"  · widgets  ({len(STATIC_WIDGETS)} pages under /w/)")

    # 3. per-manuscript detail (raw scans not bundled → hasLocal forced False) ----
    ms_ids = [r["id"] for r in wiki.all_manuscripts()]
    reader_ids = []  # manuscripts with ≥1 transcribed page — get a static /read export
    for mid in ms_ids:
        det = wiki.manuscript_detail(mid)
        if not det:
            continue
        for im in det.get("images", []):
            # We ship no scan bytes. An image is viewable iff we have a IIIF URL for
            # its sha — then hasLocal=True so the viewer renders an <img> the shim
            # resolves to the sized IIIF endpoint. No IIIF → keep the source link.
            im["hasLocal"] = bool(im.get("sha256") and im["sha256"] in iiif_map)
        if det.get("hasReader"):
            reader_ids.append(mid)
        write_json(api / "manuscript" / f"{mid}.json",
                   {"manuscript": det, "annotation": {"notes": "", "tags": []}})
    print(f"  · {len(ms_ids)} manuscript details")

    # 3b. bilingual reader pages (/read?id=N) — fully server-rendered (no client-side
    # fetch: the Thai/English text is baked straight into the HTML), so exporting it
    # statically is just calling the same render function and writing the result.
    # Live only lets you reach these via a query string, which static hosts can't
    # route — so we ALSO patch the shim's click handler (below) to translate
    # /read?id=N clicks into this path.
    for mid in reader_ids:
        write_text(out / "read" / str(mid) / "index.html",
                   inject(wiki.reader_page(mid), base))
    print(f"  · {len(reader_ids)} reader pages (/read)")

    # 3c. Textbooks index — the 31 contributed (uploaded, not crawled) volumes are
    # otherwise buried among ~7,000 crawled manuscripts. One page making them
    # browsable as BOOKS: page count, how much is transcribed, a link to read.
    _tb_rows = wiki.connect().execute(
        "SELECT m.id, m.title_thai, m.title_english, m.genre_normalized, "
        "m.extent_pages, m.priority, "
        "(SELECT COUNT(*) FROM pages p WHERE p.manuscript_id=m.id) n_pages, "
        "(SELECT COUNT(*) FROM pages p WHERE p.manuscript_id=m.id "
        " AND p.transcription IS NOT NULL AND p.transcription<>'') n_read "
        "FROM manuscripts m WHERE m.source_id IN (21,22) "
        "ORDER BY m.priority DESC, n_read DESC, m.id").fetchall()
    _tb_items = "".join(
        "<li class='tbrow'><div class='tbtitle'>"
        + f"<a href='{base}m/?id={r['id']}'>{html.escape(r['title_english'] or r['title_thai'] or ('#' + str(r['id'])))}</a>"
        + (f" <span class='tbth'>{html.escape(r['title_thai'])}</span>" if r['title_thai'] else "")
        + "</div><div class='tbmeta'>"
        + f"{r['n_pages']} of {r['extent_pages'] or r['n_pages']} pages digested"
        + (f" &middot; <strong>{r['n_read']}</strong> transcribed" if r['n_read'] else "")
        + (f" &middot; <a href='{base}read/{r['id']}/'>Read &rarr;</a>" if r['n_read'] else "")
        + "</div></li>"
        for r in _tb_rows)
    _tb_css = (".tblist{list-style:none;margin:16px 0;padding:0;display:grid;gap:10px}"
              ".tbrow{border:1px solid rgba(128,128,128,.28);border-radius:8px;padding:12px 16px}"
              ".tbtitle{font-size:16px;font-weight:600}"
              ".tbth{font-weight:400;opacity:.65;margin-left:6px;"
              "font-family:'Sukhumvit Set','Thonburi','Noto Serif Thai',serif}"
              ".tbmeta{font-size:13px;opacity:.65;margin-top:4px}")
    _tb_body = ("<header><div><h1>Textbooks</h1><p class=sub>"
               f"{len(_tb_rows)} contributed wichaa manuscripts — uploaded, not crawled, "
               "and being transcribed + translated one page at a time</p></div>"
               + wiki.NAV + "</header>"
               f"<main><ul class='tblist'>{_tb_items}</ul></main>")
    write_text(out / "textbooks" / "index.html",
              inject(wiki.page("Textbooks — Lanna Manuscript Wiki", _tb_css, _tb_body), base))
    print(f"  · textbooks index ({len(_tb_rows)} volumes)")

    # 4. per-article -------------------------------------------------------------
    seen = {}
    n_art = 0
    for a in wiki.articles_index().get("articles", []):
        key = a["key"]
        stype, _, value = key.partition(":")
        prof = wiki.build_article(stype, value)
        if not prof:
            continue
        prof["image"] = bundle_article_image(prof.get("image"), out, base, img_seen)
        slug = art(key)
        if slug in seen and seen[slug] != key:
            print(f"    ! slug collision: {key} vs {seen[slug]} → {slug}", file=sys.stderr)
        seen[slug] = key
        write_json(api / "article" / f"{slug}.json", prof)
        n_art += 1
    print(f"  · {n_art} articles")

    # 5. full scan list (sliced client-side) + search docs -----------------------
    # require_local=False: ship every scan the catalogue knows, not just ones whose
    # bytes happen to be on this machine — the client resolves each sha to an on-demand
    # IIIF image, so local presence is irrelevant to what belongs in the gallery.
    scans = wiki.scans_snapshot(None, 0, 10 ** 9, False, require_local=False)
    write_json(api / "scans.all.json", scans)
    print(f"  · {scans.get('total', 0)} raw-scan entries (thumbs link to source)")

    rows = wiki._search_rows() or []
    # Cap each doc body so the client-side search index stays a reasonable download.
    # Titles + the lead of every body are kept; only the long tail of folded OCR on a
    # handful of heavily-transcribed manuscripts is truncated.
    BODY_CAP = 2000
    docs = [{"ref": r["ref"], "kind": r["kind"], "label": r["label"],
             "ntitle": r["ntitle"] or "", "nbody": (r["nbody"] or "")[:BODY_CAP]}
            for r in rows]
    write_json(api / "searchdocs.json", docs)
    # the bilingual thesaurus, so the client can expand query tokens exactly as the
    # live search does (typing 'astrology' / 'hora' / 'โหร' all reach the same group)
    write_json(api / "thesaurus.json",
               {k: sorted(v) for k, v in wiki._thesaurus().items()})
    print(f"  · {len(docs)} search docs + thesaurus")

    # 6. rendered plates ---------------------------------------------------------
    n_img = 0
    for pl in wiki.gallery_snapshot().get("plates", []):
        src = wiki.page_image_path(pl["id"], pl["page"])
        if not src or not Path(src).is_file():
            continue
        dst = out / "pimg" / str(pl["id"]) / f"{pl['page']}.png"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        n_img += 1
    print(f"  · {n_img} plate images")

    # 6b. social-preview card (raster og:image FB/Twitter can unfurl) ------------
    # _meta() already points og:image at SITE_URL + '/og.jpg'; write the file here so
    # the absolute URL resolves. Falls back silently if Pillow/fonts are unavailable.
    card = wiki.og_card_bytes()
    if card:
        (out / "og.jpg").write_bytes(card[0])
        print("  · og.jpg social card")
    else:
        print("  · og.jpg skipped (Pillow unavailable)", file=sys.stderr)

    # 6c. favicon ---------------------------------------------------------------
    # The live wiki serves /favicon.svg from a route; the static export has no
    # server, so write the file. inject() rebases the <link>/CSS href to `base`.
    (out / "favicon.svg").write_text(wiki.FAVICON_SVG, encoding="utf-8")
    print("  · favicon.svg")

    # 6d. vendored map library ---------------------------------------------------
    # /wats renders an interactive hero map. MapLibre ships as a SEPARATE cached
    # asset rather than inlined into the page: ~780 kB inlined into every /wats
    # load would be absurd, whereas a static file is fetched once and cached.
    vend_src = HERE / "vendor"
    if vend_src.is_dir():
        vend_out = out / "vendor"
        vend_out.mkdir(exist_ok=True)
        n_v = 0
        for f in vend_src.iterdir():
            if f.is_file() and f.suffix in (".js", ".css"):
                shutil.copy2(f, vend_out / f.name)
                n_v += 1
        print(f"  · vendor assets ({n_v} files)")

    # 6e. page manifest ----------------------------------------------------------
    # Exported so downstream tools stop keeping their own copy of "what pages
    # exist". Later generators (glossary.py, na_gallery.py, wat place pages)
    # append their own entries; site_meta unions this with a filesystem walk, so
    # an unregistered page is still found and a removed page cannot linger.
    write_json(api / "pages.json", {"pages": manifest})
    print(f"  · page manifest ({len(manifest)} routes)")

    # 7. housekeeping ------------------------------------------------------------
    (out / ".nojekyll").write_text("", encoding="utf-8")  # serve _-prefixed paths verbatim
    (out / "README.md").write_text(
        "# Lanna Manuscript Wiki — static snapshot\n\n"
        "A read-only, self-contained export of a working research catalogue of Lanna "
        "(Northern Thai) manuscripts and the living tradition around them.\n\n"
        "This `docs/` folder is served by GitHub Pages. It is generated by "
        "`build_static.py` from the live wiki; edit the wiki, not these files.\n\n"
        "High-resolution manuscript scans stay at their originating libraries; this "
        "snapshot links out to them. Concerns: 530kings@proton.me\n",
        encoding="utf-8")

    # 8. build manifest — a single machine-checkable staleness stamp. One file (not a
    # per-file _meta block) so a rebuild churns one path, not all ~7k. A reader compares
    # catalog_mtime against the live DB to know if this snapshot has fallen behind.
    try:
        db_path = Path(wiki.CATALOG_DB)
        db_mtime = datetime.fromtimestamp(
            db_path.stat().st_mtime, tz=timezone.utc).isoformat() if db_path.exists() else None
    except Exception:
        db_mtime = None
    ov = wiki.overview_snapshot()
    counts = ov.get("counts", ov) if isinstance(ov, dict) else {}
    write_json(api / "build-info.json", {
        "generator": "build_static.py",
        "generator_version": GENERATOR_VERSION,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "base": base,
        # basename only — this file is public; an absolute path leaks the operator's
        # username + local directory layout (see status_snapshot in wiki.py).
        "catalog_db": Path(str(wiki.CATALOG_DB)).name,
        "catalog_mtime": db_mtime,
        "counts": {
            "manuscripts": len(ms_ids),
            "articles": n_art,
            "scans": scans.get("total", 0),
            "search_docs": len(docs),
            "market_items": len(wiki.market_snapshot().get("items", [])),
            "plates": n_img,
        },
    })
    print(f"  · build-info.json (v{GENERATOR_VERSION})")

    # Privacy gate: this whole tree is about to go PUBLIC. A build machine's absolute
    # path leaks the operator's username + local directory layout (this actually
    # happened — build-info.json/status.json shipped a full /Users/<name>/… path).
    # Fail the build loudly rather than publish another leak; scan text files only.
    leaks = []
    home = str(Path.home())
    for f in out.rglob("*"):
        if not f.is_file() or f.suffix.lower() in {
                ".jpg", ".jpeg", ".png", ".gif", ".webp", ".ico", ".woff", ".woff2",
                ".ttf", ".pdf", ".epub", ".zip"}:
            continue
        try:
            txt = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "/Users/" in txt or "/home/" in txt or home in txt:
            leaks.append(str(f.relative_to(out)))
    if leaks:
        print("\nERROR: absolute host paths found in build output (privacy leak) — "
              "NOT publishing. Offending files:", file=sys.stderr)
        for rel in leaks[:40]:
            print(f"  · {rel}", file=sys.stderr)
        return 2

    total = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"\nDone. {total/1024/1024:.1f} MB in {out}")
    print("Preview locally:  (cd docs && python3 -m http.server 8000) then open http://127.0.0.1:8000/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
