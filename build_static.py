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
import atexit
import html
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
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
import hotrai  # noqa: E402  — หอไตร: writes the machine-facing library files
import cartography  # noqa: E402
import manuscript_pages  # noqa: E402
import article_pages  # noqa: E402


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
    // baked pimg files are EITHER .png (stored plate) or .jpg (on-demand render) —
    // the shim has no way to know which without a filesystem stat, so try .png
    // first and fall back to .jpg on a miss.
    if(p==='/pimg'){
      var pmid=sp.get('mid'), pn=sp.get('n');
      return _fetch(S('/pimg/'+pmid+'/'+pn+'.png'), {}).then(function(r){
        return r.ok ? r : _fetch(S('/pimg/'+pmid+'/'+pn+'.jpg'), {});
      });
    }
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
              // same png-vs-jpg ambiguity as the fetch shim above; try .png and
              // fall back to .jpg on load error (onerror fires at most once).
              var pmid=u.searchParams.get('mid'), pn=u.searchParams.get('n');
              var jpgFallback=S('/pimg/'+pmid+'/'+pn+'.jpg');
              var imgEl=this;
              imgEl.onerror=function(){ imgEl.onerror=null; imgEl.src=jpgFallback; };
              v=S('/pimg/'+pmid+'/'+pn+'.png');
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


# ---------------------------------------------------------------------------
# PUBLISH LOCK — one build at a time, no matter who starts it.
#
# main() WIPES --out before repopulating it, so two overlapping builds destroy
# each other's work. publish_site.sh has guarded itself with an atomic-mkdir
# lock for a while — but the guard lived in the SHELL, so running this file
# directly (`python3 build_static.py --out …/nanobotco-lanna/docs --base /`,
# an entirely normal thing to do by hand or from another session) took no lock
# at all. On 2026-08-09 exactly that happened: a direct build wiped docs/ out
# from under a publish that was mid-run, which then died in the privacy scan
# at the end of main() with
#     FileNotFoundError: [Errno 2] … /nanobotco-lanna/docs/divination
# The guard belongs HERE, next to the wipe, where every caller passes.
#
# Same lock directory and the same semantics as publish_site.sh (atomic mkdir,
# PID file inside, stale-lock reclaim when the recorded holder is gone) so the
# shell and the Python interoperate rather than deadlock. `${TMPDIR:-/tmp}` and
# the Path below resolve to the same directory — TMPDIR's trailing slash just
# collapses.
LOCK_DIR = Path(os.environ.get("TMPDIR") or "/tmp") / "lanna-publish.lock"

# publish_site.sh ALREADY holds the lock when it invokes this script, so we must
# not block on our own ancestor's lock — that would wedge every publish forever.
# Two independent ways out, either of which makes acquisition re-entrant:
#   1. the holder exports LANNA_PUBLISH_LOCK_HELD=<its pid> (publish_site.sh does),
#   2. the recorded holder PID turns out to be one of our forebears.
# (2) is the safety net: an old or hand-restored publish_site.sh that never
# learned to export anything still works, it just takes the ancestor path.
LOCK_HELD_ENV = "LANNA_PUBLISH_LOCK_HELD"


class PublishLockBusy(RuntimeError):
    """Another build/publish holds the lock and we were told not to wait."""


def _lock_holder():
    """PID recorded inside the lock, or None if absent/unreadable."""
    try:
        return int((LOCK_DIR / "pid").read_text().strip())
    except Exception:
        return None


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True          # alive, just owned by another user
    except Exception:
        return True          # unsure → assume alive; never reclaim on a guess
    return True


def _is_ancestor(pid, max_depth=40):
    """True if `pid` is this process or one of the processes we run under."""
    cur = os.getpid()
    for _ in range(max_depth):
        if cur == pid:
            return True
        if cur <= 1:
            return False
        try:
            r = subprocess.run(["ps", "-o", "ppid=", "-p", str(cur)],
                               capture_output=True, text=True, timeout=5)
            cur = int(r.stdout.strip())
        except Exception:
            return False
    return False


def _reentrant_holder(holder):
    """Why the existing lock is really ours (a string), or None if it is not."""
    if holder is None:
        return None
    declared = (os.environ.get(LOCK_HELD_ENV) or "").strip()
    if declared.isdigit() and int(declared) == holder:
        return f"our caller (pid {holder}, {LOCK_HELD_ENV})"
    if _is_ancestor(holder):
        return f"an ancestor process (pid {holder})"
    if declared:
        # Set to something that is not the holder's PID — a deliberate override
        # by some wrapper. Honour it, but say so: a stale export left in a shell
        # would otherwise silently disable the guard.
        print(f"  ! {LOCK_HELD_ENV}={declared!r} is not the lock holder's pid "
              f"({holder}) — trusting it anyway and building without the lock",
              file=sys.stderr)
        return f"{LOCK_HELD_ENV}={declared}"
    return None


def _install_lock_signal_handlers():
    """Make SIGTERM/SIGHUP unwind so the atexit release actually runs — the
    Python equivalent of publish_site.sh's `trap _release EXIT`."""
    def _bail(signum, _frame):
        raise SystemExit(128 + signum)
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        try:
            signal.signal(sig, _bail)
        except (ValueError, OSError):
            pass             # not the main thread, or platform says no


def release_publish_lock():
    """Drop the lock, but only if it is still ours."""
    if _lock_holder() == os.getpid():
        shutil.rmtree(LOCK_DIR, ignore_errors=True)


def acquire_publish_lock(wait=0.0):
    """Take the publish lock.

    Returns True when we now own it (release is wired to process exit), or
    False when a process we are running under already holds it — nothing to
    acquire and, crucially, nothing for us to release.

    Raises PublishLockBusy if someone else holds it and `wait` seconds elapse.
    """
    deadline = time.monotonic() + max(0.0, wait)
    empty_since = None
    announced = False
    while True:
        try:
            LOCK_DIR.mkdir(parents=True)
        except FileExistsError:
            pass
        else:
            (LOCK_DIR / "pid").write_text(f"{os.getpid()}\n")
            atexit.register(release_publish_lock)
            _install_lock_signal_handlers()
            return True

        holder = _lock_holder()
        mine = _reentrant_holder(holder)
        if mine:
            print(f"  publish lock already held by {mine} — continuing (re-entrant)")
            return False

        if holder is None:
            # Either a crash between mkdir and the pid write, or a competitor
            # that is a few milliseconds from writing its pid. Give it a grace
            # period rather than snatching a lock that is being claimed.
            now = time.monotonic()
            if empty_since is None:
                empty_since = now
            if now - empty_since < 5.0:
                time.sleep(0.2)
                continue
            print("  [lock] reclaiming lock with no pid file (never claimed)",
                  file=sys.stderr)
            _reclaim_stale()
            empty_since = None
            continue
        empty_since = None

        if not _pid_alive(holder):
            print(f"  [lock] reclaiming stale lock (holder pid {holder} is gone)",
                  file=sys.stderr)
            _reclaim_stale()
            continue

        if time.monotonic() >= deadline:
            raise PublishLockBusy(
                f"another build or publish (pid {holder}) is running and holds "
                f"{LOCK_DIR}.\n"
                f"  Refusing to start: this build would wipe the output directory "
                f"out from under it.\n"
                f"  Wait for it to finish, or re-run with --lock-wait 900 to queue "
                f"behind it.\n"
                f"  For a throwaway build to a scratch folder, --no-lock skips the "
                f"guard entirely.")

        if not announced:
            print(f"  [lock] another build/publish (pid {holder}) is running — "
                  f"waiting up to {wait:.0f}s…", file=sys.stderr)
            announced = True
        time.sleep(2)


def _reclaim_stale():
    """Rename the dead lock aside, then delete it.

    Rename is atomic, so if two builds decide to reclaim at the same instant
    only one of them moves the directory and the other simply loops — whereas
    two plain rm -rf's can delete the fresh lock the winner just created.
    (A holder that dies in the microsecond between our liveness check and this
    rename can still be raced; that window is the same one publish_site.sh has
    always had, and it needs a crash to open at all.)
    """
    aside = LOCK_DIR.with_name(LOCK_DIR.name + f".stale.{os.getpid()}")
    try:
        os.rename(LOCK_DIR, aside)
    except OSError:
        return               # someone else got there first — just loop
    shutil.rmtree(aside, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(HERE / "docs"),
                    help="output folder (default: ./docs)")
    ap.add_argument("--base", default="/",
                    help="URL path the site is served under. Root site: '/'. "
                         "GitHub project repo (e.g. NaNoBotCo/Lanna): '/Lanna/'.")
    ap.add_argument("--lock-wait", type=float, default=0.0, metavar="SECONDS",
                    help="if another build/publish holds the lock, wait this long "
                         "for it instead of failing straight away (default: 0)")
    ap.add_argument("--no-lock", action="store_true",
                    help="build without taking the publish lock. Only for a "
                         "throwaway --out that no publish touches.")
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

    # Everything below this line mutates `out`, starting with a wipe. Take the
    # publish lock first, so a second build refuses to start rather than pulling
    # the tree out from under one already in flight (see LOCK_DIR above).
    if args.no_lock:
        print("  ! --no-lock: building without the publish lock")
    else:
        try:
            acquire_publish_lock(wait=args.lock_wait)
        except PublishLockBusy as exc:
            print(f"\nERROR: {exc}", file=sys.stderr)
            return 4          # same code publish_site.sh uses for lock contention

    # THE WIPE MUST SPARE WHAT NO GENERATOR OWNS.
    #
    # PAGE_SPECS below is hand-maintained and builds 22 pages; routes.py declares
    # 33. The other eleven — /hun, /jovilabe, /redspot, /divination, /atlas, /need,
    # /nuea, /trails, /trail/*, /graph-audit — come from modules (hunpayont.py,
    # jovilabe.py, redspot.py, atlas.py, maproom.py) that are LIBRARIES with no
    # main() and no CLI, so publish_site.sh cannot invoke them. Their output was
    # written once and has lived in docs/ ever since.
    #
    # An unconditional rmtree therefore deletes eleven live routes on every run and
    # nothing puts them back. That is what happened on 2026-07-28 03:06: 7,049 files
    # removed, wichaa.net/hun, /jovilabe and /need serving 404 until restored by hand.
    #
    # Until those modules grow real entry points and join the pipeline, the honest
    # thing is to leave their output alone rather than destroy pages we cannot
    # rebuild. Everything build_static owns is still wiped and rebuilt from scratch.
    UNMANAGED = (
        "hun", "jovilabe", "redspot", "divination", "atlas",
        "need", "nuea", "trails", "trail", "graph-audit",
        "api/graph", "api/trails.json",
    )
    if out.exists():
        # Move-aside/move-back rather than a filtered walk: it handles the nested
        # api/… entries for free and never leaves a half-deleted tree behind.
        keep = Path(tempfile.mkdtemp(prefix="lanna-keep-", dir=out.parent))
        for rel in UNMANAGED:
            src = out / rel
            if src.exists():
                (keep / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(keep / rel))
        shutil.rmtree(out)
        out.mkdir(parents=True)
        for rel in UNMANAGED:
            src = keep / rel
            if src.exists():
                (out / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(out / rel))
        shutil.rmtree(keep, ignore_errors=True)
        print(f"  preserved {len(UNMANAGED)} unmanaged route(s) across the wipe")
    else:
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
        "search/index.html":     (wiki.SEARCH_PAGE, "Search by meaning", "section"),
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
        "khwan/index.html":      (wiki.KHWAN_PAGE, "Su Khwan — the calling", "section"),
        # /widgets — small standalone tools. Deliberately NOT part of the corpus
        # taxonomy: they are utilities, and folding them into the archive's facets
        # would muddy both. Add one by appending to wiki.WIDGETS.
        "widgets/index.html":    (wiki.SIDE_TOOLS_PAGE, "Widgets & shit", "section"),
        # /sukhwan — สู่ขวัญยนต์, the khwan-calling rite for machines and robots.
        # A /widgets side tool (see its SIDE_TOOLS entry); robot opt-in goes
        # through the su-khwan Worker, the page itself is fully static.
        "sukhwan/index.html":    (wiki.SUKHWAN_PAGE, "Su khwan for machines & robots", "utility"),
        # /hotrai — หอไตร, the wat library addressed to machines. This entry writes
        # only the human courtesy page; the library proper (entry.txt, all.txt,
        # t/*.txt, t/*.json, api/hotrai.json) is written by hotrai.write_library()
        # further down, and verify_build guards both halves.
        "hotrai/index.html":     (wiki.HOTRAI_PAGE, "หอไตร — the ho trai", "section"),
        # /waikhru — ไหว้ครูยนต์, the blessing for the hand at the machine. The
        # human-facing twin of /sukhwan; fully static, nothing typed on it ever
        # leaves the reader's device.
        "waikhru/index.html":    (wiki.WAIKHRU_PAGE, "ไหว้ครูยนต์ — a blessing at the machine", "section"),
        # /blessings — ใต้ร่มพร, the map of the household: the standing blessings
        # the fleet works under, one page, fully static, reading is receiving.
        "blessings/index.html":  (wiki.BLESSINGS_PAGE, "ใต้ร่มพร — the blessings the bots work under", "section"),
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

    # หอไตร — the library itself. The /hotrai HTML page above is the courtesy copy
    # for humans; these are the files a machine reads. Same writers as everything
    # else here, so the manifest and encoding stay consistent.
    _ht = hotrai.write_library(out, write_text=write_text, write_json=write_json)
    _sweep = _ht["sweep"]
    print(f"  · ho trai  ({_ht['texts']} texts, {_sweep['verified']}/"
          f"{_sweep['texts']} verified"
          + (f", FAULTS: {', '.join(_sweep['faults'])}" if _sweep["faults"] else "")
          + ")")

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

    # Both the reader (/read/<id>/) and the manuscript detail page (/m/<id>/, for a
    # digested-but-untranscribed volume's page gallery) interleave original scans as
    # <img src='/pimg?mid=&n=&w='>. A static host can't run that on-demand route, so
    # bake each referenced image to a real file: an already-stored plate PNG is
    # copied whole; any other page is rendered from the source PDF via
    # wiki.render_pdf_page's JPEG cache (grayscale, ~60–120KB/page). One factory, two
    # independent stats counters — reader_page() emits single-quoted attrs,
    # manuscript_pages.py emits double-quoted, so the regex accepts either.
    def _make_image_baker():
        stats = {"copied": 0, "rendered": 0, "missing": 0}
        pimg_ref = re.compile(r"src=(['\"])/pimg\?mid=(\d+)&amp;n=(\d+)(?:&amp;w=(\d+))?\1")

        def bake(html_text):
            def repl(mm):
                q = mm.group(1)
                mid_, n_ = int(mm.group(2)), int(mm.group(3))
                w_ = int(mm.group(4) or 1000)
                plate = wiki.page_image_path(mid_, n_)
                if plate:
                    dst = out / "pimg" / str(mid_) / f"{n_}.png"
                    if not dst.exists():
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(plate, dst)
                    stats["copied"] += 1
                    return f"src={q}{base}pimg/{mid_}/{n_}.png{q}"
                r = wiki.render_pdf_page(mid_, n_, w_)
                if r:
                    dst = out / "pimg" / str(mid_) / f"{n_}.jpg"
                    if not dst.exists():
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        dst.write_bytes(r[0])
                    stats["rendered"] += 1
                    return f"src={q}{base}pimg/{mid_}/{n_}.jpg{q}"
                stats["missing"] += 1
                return mm.group(0)   # leave the live URL; better a 404 than a lie
            return pimg_ref.sub(repl, html_text)

        return bake, stats

    _bake_gallery_images, _gallery_stats = _make_image_baker()
    _bake_reader_images, _reader_stats = _make_image_baker()

    # 3. per-manuscript detail (raw scans not bundled → hasLocal forced False) ----
    # ---- slug registry (data/slugs_manuscripts.json, minted once by
    # scripts/mint_manuscript_slugs.py, frozen thereafter). The canonical page
    # for a manuscript/reader lives at <slug>-<id>/; the numeric legacy path
    # gets a meta-refresh stub so every old bookmark/Wayback capture still
    # lands. A missing registry (or row) degrades to the numeric path.
    _slug_reg = {}
    _slug_file = HERE / "data" / "slugs_manuscripts.json"
    if _slug_file.exists():
        _slug_reg = json.loads(_slug_file.read_text())

    def mpath(mid):
        s = _slug_reg.get(str(mid))
        return f"{s}-{mid}" if s else str(mid)

    _STUB = ("<!doctype html><meta charset=utf-8><title>{t}</title>"
             '<link rel=canonical href="{u}">'
             '<meta http-equiv=refresh content="0; url={u}">'
             '<meta name=robots content="noindex,follow">'
             '<p>Moved to <a href="{u}">{t}</a>.</p>')

    def write_stub(old_dir, new_url, label):
        # canonical should be ABSOLUTE when the site origin is known — a
        # path-relative canonical is legal but weaker for crawlers
        _site = (wiki.SITE_URL or "").rstrip("/")
        if _site and new_url.startswith("/"):
            new_url = _site + new_url
        write_text(old_dir / "index.html",
                   _STUB.format(t=html.escape(label or ""), u=new_url))

    ms_ids = [r["id"] for r in wiki.all_manuscripts()]
    reader_ids = []  # manuscripts with ≥1 transcribed page — get a static /read export
    # Knowledge graph, built once — feeds each manuscript's "threads" (named lateral
    # relations with receipts), the one field manuscript_pages.page_html() renders
    # that manuscript_detail() doesn't already carry. See cartography.threads_for().
    g, _cart_meta = cartography.build()
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

        # 3a. /m/<id>/ — a real, server-rendered, indexable page per manuscript (Phase
        # F, decision 6 in manuscript_pages.py). /m?id=<id> stays the interactive SPA;
        # this is the door search engines and share-unfurlers actually see. A digested
        # (but not yet transcribed) contributed volume's page_html() includes a page
        # gallery — bake those scans too, the same way the reader's are baked below.
        det["threads"] = cartography.threads_for(g, f"ms:{mid}")
        mdir = mpath(mid)
        write_text(out / "m" / mdir / "index.html",
                   _bake_gallery_images(inject(
                       manuscript_pages.page_html(det, wiki, base, path=f"m/{mdir}/"),
                       base)))
        if mdir != str(mid):
            # legacy numeric path: instant meta-refresh stub, canonical forward
            write_stub(out / "m" / str(mid), f"{base}m/{mdir}/",
                       det.get("title") or f"Manuscript {mid}")
        manifest.append({"route": f"m/{mdir}/",
                          "label": det.get("title") or f"Manuscript {mid}", "kind": "entity"})
    print(f"  · {len(ms_ids)} manuscript details — page-gallery scans: "
          f"{_gallery_stats['copied']} plates copied, {_gallery_stats['rendered']} rendered"
          + (f", {_gallery_stats['missing']} MISSING" if _gallery_stats["missing"] else ""))

    # 3b. bilingual reader pages (/read?id=N) — fully server-rendered (no client-side
    # fetch: the Thai/English text is baked straight into the HTML), so exporting it
    # statically is just calling the same render function and writing the result.
    # Live only lets you reach these via a query string, which static hosts can't
    # route — so we ALSO patch the shim's click handler (below) to translate
    # /read?id=N clicks into this path.
    for mid in reader_ids:
        rdir = mpath(mid)   # a reader and its manuscript are one work, one slug
        write_text(out / "read" / rdir / "index.html",
                   _bake_reader_images(inject(wiki.reader_page(mid), base)))
        if rdir != str(mid):
            write_stub(out / "read" / str(mid), f"{base}read/{rdir}/",
                       f"Reader — manuscript {mid}")
    print(f"  · {len(reader_ids)} reader pages (/read) — scans: "
          f"{_reader_stats['copied']} plates copied, {_reader_stats['rendered']} rendered"
          + (f", {_reader_stats['missing']} MISSING" if _reader_stats["missing"] else ""))

    # 3c. Textbooks index — the 31 contributed (uploaded, not crawled) volumes are
    # otherwise buried among ~7,000 crawled manuscripts. One page making them
    # browsable as BOOKS: page count, how much is transcribed, a link to read.
    _tb_conn = wiki.connect()
    # work_title/work_desc are additive columns (crawler volume_blurbs.py) —
    # curated bilingual working titles + a catalog note of what each book holds.
    _tb_have_blurbs = any(r["name"] == "work_title" for r in
                          _tb_conn.execute("PRAGMA table_info(manuscripts)"))
    _tb_rows = _tb_conn.execute(
        "SELECT m.id, m.title_thai, m.title_english, m.genre_normalized, "
        + ("m.work_title, m.work_desc, " if _tb_have_blurbs else "")
        + "m.extent_pages, m.priority, "
        "(SELECT COUNT(*) FROM pages p WHERE p.manuscript_id=m.id) n_pages, "
        "(SELECT COUNT(*) FROM pages p WHERE p.manuscript_id=m.id "
        " AND p.transcription IS NOT NULL AND p.transcription<>'') n_read "
        "FROM manuscripts m WHERE m.source_id IN (21,22) "
        "ORDER BY m.priority DESC, n_read DESC, m.id").fetchall()

    def _tb_title(r):
        # /m/<id>/ (manuscript_pages.py), not the /m?id= SPA: the SPA's page-gallery
        # thumbnails fetch live /pimg URLs the static shim can't resolve correctly
        # (it always assumes .png; baked scans are .png OR .jpg), so it 404s on a
        # static host. /m/<id>/ is the real page with the baked gallery that works.
        wt = (r["work_title"] or "") if _tb_have_blurbs else ""
        if wt:
            return f"<a href='{base}m/{mpath(r['id'])}/'>{html.escape(wt)}</a>"
        return (f"<a href='{base}m/{mpath(r['id'])}/'>{html.escape(r['title_english'] or r['title_thai'] or ('#' + str(r['id'])))}</a>"
                + (f" <span class='tbth'>{html.escape(r['title_thai'])}</span>" if r['title_thai'] else ""))

    def _tb_desc(r):
        wd = (r["work_desc"] or "") if _tb_have_blurbs else ""
        return f"<p class='tbdesc'>{html.escape(wd)}</p>" if wd else ""

    _tb_items = "".join(
        "<li class='tbrow'><div class='tbtitle'>"
        + _tb_title(r)
        + "</div>"
        + _tb_desc(r)
        + "<div class='tbmeta'>"
        + f"{r['n_pages']} of {r['extent_pages'] or r['n_pages']} pages digested"
        + (f" &middot; <strong>{r['n_read']}</strong> transcribed" if r['n_read'] else "")
        + (f" &middot; <a href='{base}read/{mpath(r['id'])}/'>Read &rarr;</a>" if r['n_read'] else "")
        + "</div></li>"
        for r in _tb_rows)
    _tb_css = (".tblist{list-style:none;margin:16px 0;padding:0;display:grid;gap:10px}"
              ".tbrow{border:1px solid rgba(128,128,128,.28);border-radius:8px;padding:12px 16px}"
              ".tbtitle{font-size:16px;font-weight:600}"
              ".tbth{font-weight:400;opacity:.65;margin-left:6px;"
              "font-family:'Sukhumvit Set','Thonburi','Noto Serif Thai',serif}"
              ".tbdesc{font-size:13.5px;line-height:1.5;opacity:.8;margin:4px 0 0;max-width:64em}"
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
        # /a/<slug>/ — a real, server-rendered, indexable page per subject (same
        # "two doors" fix as /m/<id>/). /a?id=<key> stays the interactive view.
        write_text(out / "a" / slug / "index.html",
                   inject(article_pages.page_html(prof, slug, wiki), base))
        manifest.append({"route": f"a/{slug}/", "label": prof.get("label") or value,
                          "kind": "entity"})
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
    # handful of heavily-transcribed manuscripts is truncated. The contributed
    # TEXTBOOKS get a much larger cap: their English translations are the only way
    # an English query can find textbook content, and 2000 chars hid all but the
    # first page or two (caught 2026-08-05). ~60KB × 30 volumes worst case ≈ 1.8MB
    # raw / ~400KB gzipped once everything is translated — revisit (per-page docs
    # or a split index) if that ever feels slow.
    BODY_CAP = 2000
    CONTRIB_BODY_CAP = 60000
    contrib_refs = {str(r["id"]) for r in wiki.connect().execute(
        "SELECT id FROM manuscripts WHERE source_id IN (21,22)")}
    docs = [{"ref": r["ref"], "kind": r["kind"], "label": r["label"],
             "ntitle": r["ntitle"] or "",
             "nbody": (r["nbody"] or "")[:CONTRIB_BODY_CAP if r["ref"] in contrib_refs
                                         else BODY_CAP]}
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

    # Dead article links. An article naming a page that does not exist used to
    # render as bare text with no signal anywhere — the link just evaporated.
    # A warning, not a failure: the page is still correct prose, and a typo in
    # one article should not stop a publish.
    dead = wiki.link_report()
    if dead:
        print(f"\n! {len(dead)} article link(s) point at nothing and were rendered "
              f"as plain text — fix the article or add the route:", file=sys.stderr)
        for href, where in dead[:30]:
            print(f"  · {where}: {href}", file=sys.stderr)

    total = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"\nDone. {total/1024/1024:.1f} MB in {out}")
    print("Preview locally:  (cd docs && python3 -m http.server 8000) then open http://127.0.0.1:8000/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
