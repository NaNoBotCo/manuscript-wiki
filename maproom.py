#!/usr/bin/env python3
"""maproom — the landing page's strata (Phase C of WAYFINDING_PLAN.md).

The landing was a hero, six counters and the doors: "built like it's a small
site." This module adds the strata that make it a map room — a place you can
stand in and see the whole archive breathing:

    today       the site knows what day it is (wan phra · the great days) and
                offers a date-seeded stroll everyone in the world gets alike
    bots        what the machines have read, and the honest ask (decision 2)
    gaps        coverage-as-object: the archive knows what it doesn't know
    constellation  a small ego-graph — a window into the Atlas (Phase G)

WHERE THIS RUNS, AND WHY
Post-build, from the ALREADY-BUILT api/ files — the same reasoning as
site_meta._geo_map_svg: the landing should paint in one pass, and everything it
states is a fact the build already computed. Nothing here opens the database.

WHAT IS CLIENT-SIDE, AND WHY
The day. A static page is published once and read for hours or days, so a
"today" baked at build time is wrong by breakfast. The published wan-phra table
travels INTO the page and the reading happens in the reader's own browser —
which is also why it needs no server, no clock sync and no tracking.

Numbers are never hand-typed here (the landing's own principle: a site whose
stated rule is that every fact is recomputed cannot carry authored numbers).
"""
from __future__ import annotations

import json
from pathlib import Path

import strings

HERE = Path(__file__).resolve().parent
KOFI = "https://ko-fi.com/defiantchiangmai"


def _load(p, fallback):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _n(x):
    try:
        return f"{int(x):,}"
    except Exception:
        return "0"


# ---------------------------------------------------------------- the day block
def day_block() -> str:
    """The published Thai calendar, travelling into the page so the READER's
    browser can say what day it is.

    The table and the reasoning are hunpayont.py's: the Thai lunar calendar is
    arithmetic, not astronomy — deriving it from the moon scored 17/49 and 37/49
    against the published days, so the holy days are a TABLE, and 2569 carries a
    doubled eighth month no lunation model can know about. We reuse that table
    rather than keeping a second copy.

    Northern (Lanna) festival names come from the coucal-clock project's
    almanac (src/coucal/almanac/lanna.py, _FULL_MOON_FESTIVALS), which anchors
    them to the same published Thai table — cited, not asserted from memory.
    """
    import hunpayont

    # Northern names for the days the Lanna north keeps under its own name.
    # Transcribed from coucal-clock's almanac table; anything not attested there
    # simply keeps its central-Thai name rather than being glossed by guesswork.
    NORTHERN = {"2026-11-24": "ยี่เป็ง · Yi Peng — the lantern festival"}

    great = dict(hunpayont.GREAT_DAYS)
    table = {
        "phra": hunpayont.WAN_PHRA,
        "great": great,
        "northern": NORTHERN,
        # w15 = fifteenth waxing (full), n15/n14 = the dark moon, w8/n8 = quarters
        "kinds": {
            "w15": ["ขึ้น ๑๕ ค่ำ · full moon", "the full moon — the great wan phra"],
            "w14": ["ขึ้น ๑๔ ค่ำ · waxing", "a holy day"],
            "w8": ["ขึ้น ๘ ค่ำ · half moon", "a holy day — the waxing quarter"],
            "n15": ["แรม ๑๕ ค่ำ · dark moon", "the dark moon — a holy day"],
            "n14": ["แรม ๑๔ ค่ำ · dark moon", "the dark moon — a holy day"],
            "n8": ["แรม ๘ ค่ำ · half moon", "a holy day — the waning quarter"],
        },
    }
    return ("<script>window.__WICHAA_DAYS__="
            + json.dumps(table, ensure_ascii=False, separators=(",", ":"))
            + ";</script>")


# ------------------------------------------------------- what the bots have read
def bots_block(docs: Path) -> str:
    """The automation's work, told as the sponsorship story it actually is.

    dr, reviewing the site: "167 of 167 pages digested" reads as pipeline
    metadata leaking into the UX — nobody cares how many pages were *digested*.
    The answer isn't to delete the number, it's to say what it MEANS: every page
    the archive holds has been read by the vision pass, and only a small share
    has been transcribed and translated into something a human can actually
    read. That gap is the ask. (PRIORITIES.md, dr feedback items 2 and 3.)
    """
    bi = _load(docs / "api" / "build-info.json", {}) or {}
    c = bi.get("counts", {}) or {}
    act = _load(docs / "api" / "activity.json", {}) or {}
    ac = act.get("counts", {}) or {}
    pages = c.get("pages") or ac.get("pages") or 0
    read = c.get("pagesTranscribed", 0)
    done = c.get("pagesTranslated", 0)
    findings = ac.get("findings", 0)
    if not pages:
        return ""
    pct = (read / pages * 100) if pages else 0
    left = max(pages - read, 0)
    # $0.06/pg is the price already published on /support; the estimate is
    # arithmetic on it, and rounds DOWN to a plain figure rather than a promise.
    cost = int(left * 0.06)
    bar = (f'<div class="meter" role="img" aria-label="'
           f'{_n(read)} of {_n(pages)} pages transcribed">'
           f'<span style="width:{max(pct, 0.6):.2f}%"></span></div>')
    return f"""
    <div class="eyebrow">Today's work</div>
    <h2>What the bots have read</h2>
    <p class="botlede">Every page the archive holds — <b>{_n(pages)}</b> of them — has been
      read by the machines and described. Turning that into something a person can
      actually <i>read</i> is slower: <b>{_n(read)}</b> pages are transcribed and
      translated so far, {pct:.1f}% of the whole.</p>
    {bar}
    <p class="botmeta"><b>{_n(left)}</b> pages still waiting · about
      <b>${_n(cost)}</b> to finish at the going rate of $0.06 a page ·
      <b>{_n(findings)}</b> discoveries noticed by the curiosity bots so far</p>
    <div class="tamboon-cta">
      <a class="btn primary" href="{KOFI}" target="_blank" rel="noopener">&#9749; Tam boon — sponsor a page</a>
      <a class="btn ghost" href="/support">How sponsorship works</a>
      <a class="btn ghost" href="/activity">Watch the bots work &rarr;</a>
    </div>"""


# ------------------------------------------------------------------- the gaps
def gap_block(docs: Path) -> str:
    """The archive's own account of what it does not have.

    Coverage is an object here, not a silence: `api/coverage.json` already
    records what was looked for, where, by what method, and what is out of
    scope. This makes it navigable and gives each gap a way to be closed —
    which is the contribution quest list, on the front door.

    Every number is measured at build time from the built API files. A gap that
    closes disappears from this list by itself.
    """
    bi = _load(docs / "api" / "build-info.json", {}) or {}
    c = bi.get("counts", {}) or {}
    cov = _load(docs / "api" / "coverage.json", {}) or {}
    arts = _load(docs / "api" / "articles.json", {}) or {}
    gsum = _load(docs / "api" / "graph" / "summary.json", {}) or {}
    nodes = (gsum.get("nodes") or {}).get("by_class", {})

    pages = c.get("pages", 0)
    read = c.get("pagesTranscribed", 0)
    ms = c.get("manuscripts", 0)
    n_art = len(arts.get("articles", []) or [])
    n_nodes = (gsum.get("nodes") or {}).get("total", 0)

    gaps = []
    if pages and read < pages:
        gaps.append(("อ่านไม่ครบ · Unread pages", f"{_n(pages - read)} of {_n(pages)}",
                     "Transcribed and translated, page by page. The bots have "
                     "described every page; turning that into readable text is "
                     "the backlog a sponsor shortens.",
                     "/support", "Sponsor a page"))
    # Local preservation vs. a link to someone else's server — the "for
    # posterity" gap named in PRIORITIES.md (≈20% of manuscripts have a local image).
    plates = c.get("plates", 0)
    if ms:
        gaps.append(("เก็บภาพเอง · Images not held here", f"{_n(ms)} manuscripts",
                     "Most manuscripts are metadata plus a live link to the "
                     "library's own image server. They display, but nothing is "
                     "preserved here — and a link is not a copy."
                     + (" No plates were bundled in this build."
                        if not plates else ""),
                     "/status", "See the crawl status"))
    if n_nodes and n_art < n_nodes:
        gaps.append(("ยังไม่มีคำอธิบาย · Subjects with no prose",
                     f"{_n(n_art)} written",
                     f"The graph holds {_n(n_nodes)} things worth explaining. "
                     "Articles are written by hand, and most subjects are still "
                     "waiting for their first paragraph.",
                     "/articles", "Read what exists"))
    for s in (cov.get("scopes") or []):
        if s.get("status") == "known-limit":
            gaps.append((s.get("what", "A known limit"), "known limit",
                         s.get("note") or s.get("method") or "",
                         "/api/coverage.json", "The coverage record"))
    if not gaps:
        return ""
    cards = "".join(
        f'<div class="gap"><div class="gaptop"><b>{_esc(t)}</b>'
        f'<span class="gapn">{_esc(n)}</span></div>'
        f'<p>{_esc(d)}</p><a href="{_esc(href)}">{_esc(cta)} &rarr;</a></div>'
        for t, n, d, href, cta in gaps[:6])
    return f"""
    <div class="eyebrow">Coverage</div>
    <h2>What the archive knows it doesn't know</h2>
    <p style="max-width:44rem;opacity:.85">An absence you can read is worth more than a
      silence. Every gap here is measured at build time, names how it could be closed,
      and vanishes from this list when it is.</p>
    <div class="gaps">{cards}</div>"""


# ----------------------------------------------------------- the constellation
def constellation_block(docs: Path) -> str:
    """One ego-graph, drawn as inline SVG — the graph made visible without
    shipping a 22,000-node hairball at the front door. The set is built into
    api/constellation.json; the client picks one by today's date (same for
    everyone), so the front page quietly turns over.

    Deliberately NOT the primary navigation: the chrome (threads, breadcrumbs,
    wander) carries that. This is a window, and Phase G is the room.
    """
    data = _load(docs / "api" / "constellation.json", {}) or {}
    cons = data.get("constellations") or []
    if not cons:
        return ""
    return f"""
    <div class="eyebrow">The graph</div>
    <h2>Everything is tied to something</h2>
    <p style="max-width:44rem;opacity:.85">{_n(len(cons))} neighbourhoods of the archive's
      knowledge graph, one shown each day. Every line is a relation the data can
      account for — a shared word, a named subject, a wat down the road.</p>
    <figure class="constel"><div id="constel-svg"></div>
      <figcaption id="constel-cap"></figcaption></figure>"""


# ------------------------------------------------------------- today's stroll
def stroll_block() -> str:
    """Eight doors, chosen by the date — the same eight for everyone, all day.

    A deterministic seed rather than randomness: "today at wichaa" has to be a
    thing two people can talk about, and a thing you can share. The pool is
    api/wander.json, the same one the เดินเล่น button uses.
    """
    return f"""
    <div class="eyebrow">{_esc(strings.pair('wander'))}</div>
    <h2>Today at wichaa</h2>
    <p id="daysay" class="daysay"></p>
    <div class="stroll" id="stroll"></div>
    <p class="strollnote">Eight doors, chosen by today's date — the same eight for
      everyone, until midnight. <button id="reroll" class="linkish" type="button">Or
      roll the dice &#127922;</button></p>"""


# --------------------------------------------------------------- the page script
# One script for all four strata. No dependencies, no build step, no analytics.
LANDING_JS = r"""
(function(){
  "use strict";
  var D=window.__WICHAA_DAYS__||{phra:{},great:{},northern:{},kinds:{}};
  function iso(d){return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');}
  var today=new Date(), key=iso(today);
  // ---- the day -------------------------------------------------------------
  // The table is the authority; when the day is not in it we say nothing rather
  // than guess (the table covers 2026 and reports its own reach by running out).
  var say=document.getElementById('daysay');
  if(say){
    var bits=[], kind=D.phra[key];
    if(D.great[key])bits.push('<b>'+D.great[key]+'</b>');
    if(D.northern[key])bits.push('<b>'+D.northern[key]+'</b>');
    if(kind&&D.kinds[kind])bits.push('วันพระ · a holy day — '+D.kinds[kind][0]);
    if(!bits.length){
      // when is the next one? a reason to come back
      var ks=Object.keys(D.phra).sort(), nxt=null;
      for(var i=0;i<ks.length;i++){if(ks[i]>key){nxt=ks[i];break;}}
      if(nxt){
        var days=Math.round((Date.parse(nxt)-Date.parse(key))/86400000);
        var nm=D.great[nxt]?(' — '+D.great[nxt]):'';
        bits.push('The next วันพระ (holy day) is in '+days+' day'+(days===1?'':'s')+nm+'.');
      }
    }
    if(bits.length)say.innerHTML=bits.join(' &middot; ');
    else say.remove();
  }
  // ---- deterministic pick --------------------------------------------------
  function seedFrom(s){var h=2166136261;for(var i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619);}return h>>>0;}
  function rng(seed){return function(){seed|=0;seed=seed+0x6D2B79F5|0;var t=Math.imul(seed^seed>>>15,1|seed);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}
  function pick(pool,n,seed){var r=rng(seed),a=pool.slice(),out=[];
    while(a.length&&out.length<n){out.push(a.splice(Math.floor(r()*a.length),1)[0]);}return out;}
  // ---- today's stroll ------------------------------------------------------
  var box=document.getElementById('stroll');
  if(box){
    fetch('/api/wander.json').then(function(r){return r.json();}).then(function(d){
      var pool=(d&&d.pool)||[]; if(!pool.length){box.remove();return;}
      // Round-robin across CLASSES so a stroll is a cross-section of the
      // archive, not eight temple names — places outnumber articles 45:1, and
      // a flat draw shows you the majority every single day.
      var by={},order=[];
      pool.forEach(function(e){var k=e[2]||'other';
        if(!by[k]){by[k]=[];order.push(k);} by[k].push(e);});
      order.sort();
      function strollPick(s,n){
        var out=[],pools=order.map(function(k){return pick(by[k],by[k].length,s+k.length);}),i=0;
        while(out.length<n&&pools.some(function(p){return p.length;})){
          var p=pools[i%pools.length]; if(p.length)out.push(p.shift()); i++;}
        return out;}
      var seed=seedFrom(key);
      function draw(s){box.textContent='';
        strollPick(s,8).forEach(function(e){
          var a=document.createElement('a');a.className='door';a.href=e[0];a.textContent=e[1]||e[0];box.appendChild(a);});}
      draw(seed);
      var rr=document.getElementById('reroll');
      if(rr)rr.addEventListener('click',function(){draw(seedFrom(key+Math.random()));});
    }).catch(function(){box.remove();});
  }
  // ---- the constellation ---------------------------------------------------
  // Two layouts, because one does not fit both: a radial fan on a wide screen,
  // a plain vertical spine on a phone (where a fan collapses into overlapping
  // 8px text). Labels anchor by which side of the hub they sit on, and every
  // label carries a halo so a line passing behind it never muddies the words.
  var svgBox=document.getElementById('constel-svg');
  if(svgBox){
    fetch('/api/constellation.json').then(function(r){return r.json();}).then(function(d){
      var cs=(d&&d.constellations)||[]; if(!cs.length){throw 0;}
      var c=pick(cs,1,seedFrom(key+'c'))[0], sp=c.spokes.slice(0,7);
      var ns='http://www.w3.org/2000/svg', narrow=(window.innerWidth||1024)<620;
      function clip(s,n){return s.length>n?s.slice(0,n-1)+'…':s;}
      function text(x,y,label,cls,anchor){
        var t=document.createElementNS(ns,'text');
        t.setAttribute('x',x);t.setAttribute('y',y);
        t.setAttribute('text-anchor',anchor||'middle');t.setAttribute('class',cls);
        t.textContent=label;return t;}
      function link(href,el){
        var a=document.createElementNS(ns,'a');a.setAttribute('href',href||'#');
        a.appendChild(el);return a;}
      function line(x1,y1,x2,y2){
        var l=document.createElementNS(ns,'line');
        l.setAttribute('x1',x1);l.setAttribute('y1',y1);
        l.setAttribute('x2',x2);l.setAttribute('y2',y2);
        l.setAttribute('class','egoline');return l;}
      function relOf(s){return (window.__WICHAA_REL__&&window.__WICHAA_REL__[s.rel])||s.rel;}
      var svg=document.createElementNS(ns,'svg');
      svg.setAttribute('class','egograph');svg.setAttribute('role','img');
      svg.setAttribute('aria-label','Graph neighbourhood of '+c.hub.label);
      if(narrow){
        var W=340,rowH=64,H=86+sp.length*rowH,cx=44;
        svg.setAttribute('viewBox','0 0 '+W+' '+H);
        svg.appendChild(link(c.hub.href,text(16,30,clip(c.hub.label,30),'hubt','start')));
        svg.appendChild(line(cx,42,cx,H-30));
        sp.forEach(function(s,i){
          var y=82+i*rowH;
          svg.appendChild(line(cx,y-6,cx+26,y-6));
          svg.appendChild(text(cx+34,y-14,clip(relOf(s),34),'relt','start'));
          svg.appendChild(link(s.href,text(cx+34,y+6,clip(s.label,26),'spoket','start')));});
      }else{
        var W2=860,H2=340,mx=W2/2,my=H2/2,fit=[];
        svg.setAttribute('viewBox','0 0 '+W2+' '+H2);
        sp.forEach(function(s,i){
          var a=(-Math.PI/2)+(i+0.5)*(2*Math.PI/sp.length);
          var x=mx+Math.cos(a)*220, y=my+Math.sin(a)*128;
          var anchor=Math.cos(a)>0.15?'start':(Math.cos(a)<-0.15?'end':'middle');
          svg.appendChild(line(mx,my,x,y));
          var rx=mx+(x-mx)*0.62, ry=my+(y-my)*0.62;
          var rt=text(rx,ry-7,clip(relOf(s),30),'relt',anchor);
          var lt=text(x,y+5,clip(s.label,26),'spoket',anchor);
          svg.appendChild(rt);svg.appendChild(link(s.href,lt));
          // how much room this label actually has before the edge
          var room=anchor==='start'?(W2-x-8):(anchor==='end'?(x-8):Math.min(x,W2-x)*2-8);
          fit.push([rt,room],[lt,room]);});
        svg.appendChild(link(c.hub.href,text(mx,my+6,clip(c.hub.label,28),'hubt','middle')));
        fit.push([svg.querySelector('.hubt'),W2-24]);
        svgBox.appendChild(svg);
        // MEASURE, don't guess. A character budget is wrong for Thai (wider
        // glyphs, no spaces to break on) and wrong again for a long Latin name,
        // so trim each label against its real rendered width until it fits.
        fit.forEach(function(p){
          var t=p[0],room=p[1],guard=40;
          while(t.getComputedTextLength()>room&&t.textContent.length>6&&guard--){
            t.textContent=t.textContent.replace(/…$/,'').slice(0,-1)+'…';}});
      }
      if(!svg.parentNode)svgBox.appendChild(svg);
      var cap=document.getElementById('constel-cap');
      if(cap)cap.innerHTML='<a href="'+c.hub.href+'">'+c.hub.label+'</a> and what it is tied to — one of '+cs.length+', changing daily.';
    }).catch(function(){var f=document.querySelector('.constel');if(f)f.remove();});
  }
})();
"""


def landing_scripts(docs: Path) -> str:
    """Everything the strata need, in one <script> — plus the relation labels
    generated from the ONE bilingual registry (strings.py), so the landing can
    never drift from the rest of the chrome."""
    rel = {k: strings.pair(k) for k in strings.PAIRS}
    return ("<script>window.__WICHAA_REL__="
            + json.dumps(rel, ensure_ascii=False, separators=(",", ":"))
            + ";</script><script>" + LANDING_JS + "</script>")


def wander_pill() -> str:
    """The เดินเล่น pill, as the landing's own copy.

    wiki.page() puts this on every generated page, but the landing is a
    hand-authored file that never passes through it — and it also never gets
    the static shim, so it must fetch the REAL file path (/api/wander.json)
    rather than the shim-mapped /api/wander that interior pages use.
    """
    return (
        "<button id=wander title='" + _esc(strings.pair("wander"))
        + " — somewhere unexpected'>&#127922; " + _esc(strings.th("wander"))
        + "</button>"
        "<script>(function(){var b=document.getElementById('wander');if(!b)return;"
        "var P=null;b.addEventListener('click',function(){"
        "(P?Promise.resolve(P):fetch('/api/wander.json').then(function(r){"
        "if(!r.ok)throw 0;return r.json();}).then(function(d){P=d;return d;}))"
        ".then(function(d){var pool=(d&&d.pool)||[];"
        "if(!pool.length){b.style.display='none';return;}"
        "var by={};for(var j=0;j<pool.length;j++){var k=pool[j][2]||'other';"
        "(by[k]=by[k]||[]).push(pool[j]);}var ks=Object.keys(by);"
        "for(var i=0;i<9;i++){var g=by[ks[Math.floor(Math.random()*ks.length)]];"
        "var e=g[Math.floor(Math.random()*g.length)];"
        "if(e&&e[0]&&e[0]!=='/'){location.href=e[0];return;}}})"
        ".catch(function(){b.style.display='none';});});})();</script>")
