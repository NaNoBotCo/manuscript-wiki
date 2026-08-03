#!/usr/bin/env python3
"""atlas — the graph, drawn (Phase G of WAYFINDING_PLAN.md).

"I want to graph this thing out in the pimpest way possible. the graph itself is
sexy and does the work." — the owner, deciding this phase.

WHAT IS DRAWN, AND WHY IT IS NOT 22,000 DOTS
A picture of every record is a picture of nothing. What carries the shape of this
corpus is its CONCEPT layer — scripts, languages, genres, materials, provinces,
words, the traditions themselves — and the honest way to see that shape is to
fold the records onto it: two concepts are joined when records belong to both,
and the line's weight is HOW MANY. Nothing is modelled, inferred or scored; every
line is a count you could go and verify (cartography.concept_projection).

The result is legible at a glance and true: Pali, Tham Lanna and palm-leaf sit in
one dense knot at the middle of the Lanna manuscript world, while `amulet` and
the market hang off their own side of the sky.

HOW IT IS DRAWN
Canvas, and a DETERMINISTIC layout — no physics, no random seeds. Classes take
sectors of a circle; inside a sector a concept's distance from the centre is set
by how many records it holds, so the heavy things sink to the middle. The same
build always draws the same map, which means a link to a spot on it keeps
meaning that spot tomorrow.

ACCESSIBILITY IS NOT OPTIONAL HERE
A canvas is invisible to a screen reader and useless at 400% zoom, so the same
data is ALSO rendered as a plain linked list underneath, always present, never
hidden behind the picture. Low vision is a first-class case in this project, not
a fallback.
"""
from __future__ import annotations

import strings

# One colour per class, from the site's own palette (teal ground, gold accents).
CLASS_COLOURS = {
    "tradition": "#e9c46a", "genre": "#7fb3a8", "subgenre": "#5f9a8e",
    "language": "#c98b5e", "script": "#b5726a", "province": "#8aa9c9",
    "material": "#9d8ec2", "era": "#c2a15a", "entity": "#e0a458",
    "term": "#6fa287", "kind": "#a8a29a", "ptype": "#8fa39b", "temple": "#6b8f89",
}
CLASS_LABEL = {
    "tradition": "สาย · tradition", "genre": "หมวด · genre",
    "subgenre": "หมวดย่อย · sub-genre", "language": "ภาษา · language",
    "script": "อักษร · script", "province": "จังหวัด · province",
    "material": "วัสดุ · material", "era": "ยุค · era", "entity": "เรื่อง · subject",
    "term": "คำ · word", "kind": "ชนิด · kind", "ptype": "ประเภท · place type",
    "temple": "วัด · temple",
}

ATLAS_CSS = """
.atwrap{position:relative;margin:0 -8px}
#atlas{width:100%;height:min(74vh,760px);display:block;border-radius:14px;
  background:radial-gradient(circle at 50% 45%,#14322e 0%,#0e2523 70%,#0b1e1c 100%);
  cursor:grab;touch-action:none}
#atlas.drag{cursor:grabbing}
/* On a phone touch-action:none would trap the page: a vertical swipe on the tall
   canvas pans the graph instead of scrolling, stranding the accessible list below.
   Let vertical swipes scroll the page (pan-y) — pinch-zoom and horizontal drag
   still work — and shorten the canvas so a scroll gutter always exists. */
@media(max-width:760px){#atlas{height:min(56vh,460px);touch-action:pan-y}
  .atwrap{padding-bottom:8px}}
.atbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:12px 0}
.atbar input{flex:1 1 240px;min-width:180px;padding:10px 14px;font-size:16px;
  border:1px solid rgba(128,128,128,.4);border-radius:999px}
/* the site's global rule paints button text white for its teal buttons, so any
   pale-backed button here must say its own colour or it disappears */
.atbar button{font:inherit;padding:9px 14px;border-radius:999px;cursor:pointer;
  border:1px solid rgba(128,128,128,.4);background:var(--card,#fff);color:var(--ink,#26302a)}
.atbar button:hover{background:#efe7d5;border-color:var(--gold,#a8791e)}
.legend{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 4px}
.legend button{display:flex;align-items:center;gap:7px;font:inherit;font-size:13.5px;
  font-weight:500;padding:6px 12px;border-radius:999px;border:1px solid rgba(128,128,128,.32);
  background:var(--card,#fff);color:var(--ink,#26302a);cursor:pointer}
.legend button:hover{background:#efe7d5;border-color:var(--gold,#a8791e)}
.legend button[aria-pressed=false]{opacity:.38}
.legend i{width:12px;height:12px;border-radius:3px;display:inline-block}
#atinfo{position:absolute;left:12px;top:12px;max-width:min(330px,62%);
  background:rgba(253,251,245,.96);border-radius:12px;padding:12px 14px;
  font-size:14.5px;line-height:1.5;pointer-events:none;opacity:0;transition:opacity .12s;
  box-shadow:0 4px 16px rgba(0,0,0,.22)}
#atinfo.show{opacity:1}
#atinfo b{font-size:16px;display:block}
#atinfo .cls{font-size:12.5px;opacity:.7}
#atinfo ul{margin:6px 0 0;padding-left:18px}#atinfo li{margin:2px 0}
.athint{font-size:14px;opacity:.72;margin:6px 0 0}
.atlist{margin:26px 0 0}
.atlist summary{cursor:pointer;font-size:16px;font-weight:600;padding:8px 0}
.atlist ul{columns:2;column-gap:26px;list-style:none;padding:0;margin:10px 0}
@media(max-width:720px){.atlist ul{columns:1}}
.atlist li{break-inside:avoid;margin:5px 0;font-size:15px}
.atlist .n{opacity:.62;font-size:13px}
"""


def atlas_page(wiki):
    legend = "".join(
        f'<button data-cls="{c}" aria-pressed="true">'
        f'<i style="background:{CLASS_COLOURS[c]}"></i>{CLASS_LABEL.get(c, c)}</button>'
        for c in CLASS_COLOURS)
    body = (
        "<header><div><h1>The Atlas</h1><p class=sub>"
        "แผนที่ความรู้ · the whole archive, as one picture</p></div>"
        + wiki.NAV + "</header>"
        "<main>"
        "<p style='max-width:46rem'>Every dot is a concept the archive actually uses — a "
        "script, a language, a genre, a province, a word people search for. Two are joined "
        "when records belong to both, and the line is heavier the more records they share. "
        "Nothing here is modelled or guessed: each line is a count you can go and check.</p>"
        "<div class=atbar>"
        "<input id=atq type=search placeholder='Find a concept — ยันต์, Pali, Phrae…' "
        "aria-label='Find a concept'>"
        "<button id=atreset>Reset view</button></div>"
        "<div class=legend id=atlegend>" + legend + "</div>"
        "<div class=atwrap><canvas id=atlas></canvas><div id=atinfo></div></div>"
        "<p class=athint>Drag to move · scroll or pinch to zoom · hover a dot to see what "
        "it is tied to · click to open it. The picture is drawn the same way every time, "
        "so a place on it stays that place.</p>"
        "<details class=atlist id=atlist><summary>Read the atlas as a list "
        "(every concept, with its record count)</summary><div id=atlistbody>"
        "<p class=muted>Loading…</p></div></details>"
        "</main>"
        "<script>" + ATLAS_JS + "</script>")
    return wiki.page("The Atlas — wichaa", ATLAS_CSS, body,
                     description="The whole archive as one picture: every concept it uses, "
                                 "joined by how many records they share.",
                     og_image="/atlas/card.png", og_url="/atlas")


ATLAS_JS = r"""
(function(){
  "use strict";
  var BASE=(window.__LANNA_BASE__||'/');
  var COL=%%COLOURS%%, CLS=%%CLSLABEL%%;
  var cv=document.getElementById('atlas'), info=document.getElementById('atinfo');
  if(!cv) return;
  var ctx=cv.getContext('2d'), DATA=null, LAY=[], off={x:0,y:0}, scale=1, hot=-1;
  var cx0=0, cy0=0;   // the layout's own centre, in layout coords
  var hidden={}, dpr=Math.max(1,Math.min(2,window.devicePixelRatio||1));

  function size(){
    var r=cv.getBoundingClientRect();
    cv.width=r.width*dpr; cv.height=r.height*dpr;
    return r;
  }
  // ---- deterministic layout: sectors by class, depth by weight --------------
  // No physics and no randomness — the same data must always draw the same map,
  // otherwise "the thing at the top left" stops meaning anything between builds.
  function layout(){
    var r=size(), W=r.width, H=r.height, cx=W/2, cy=H/2;
    var R=Math.min(W,H)*0.46, Rin=R*0.16;
    var byCls={}, order=[];
    DATA.nodes.forEach(function(n,i){ if(!byCls[n.c]){byCls[n.c]=[];order.push(n.c);} byCls[n.c].push(i); });
    order.sort();
    var tot=order.reduce(function(s,c){return s+Math.sqrt(byCls[c].length);},0), a0=-Math.PI/2;
    var maxN=Math.max.apply(null,DATA.nodes.map(function(n){return n.n;}))||1;
    LAY=new Array(DATA.nodes.length);
    order.forEach(function(c){
      var idxs=byCls[c].slice().sort(function(a,b){return DATA.nodes[b].n-DATA.nodes[a].n;});
      var span=Math.PI*2*Math.sqrt(idxs.length)/tot;
      idxs.forEach(function(ni,k){
        var n=DATA.nodes[ni];
        var frac=idxs.length>1?(k+0.5)/idxs.length:0.5;
        var ang=a0+span*frac;
        // heavy concepts sink toward the middle; log so one giant doesn't flatten the rest
        var depth=Math.log(1+n.n)/Math.log(1+maxN);
        var rad=Rin+(R-Rin)*(1-depth);
        LAY[ni]={x:cx+Math.cos(ang)*rad, y:cy+Math.sin(ang)*rad,
                 r:3+7*Math.pow(depth,1.3), a:ang};
        cx0=cx; cy0=cy;
      });
      a0+=span;
    });
  }
  function T(p){ return {x:(p.x+off.x)*scale+ (1-scale)*cv.width/(2*dpr),
                         y:(p.y+off.y)*scale+ (1-scale)*cv.height/(2*dpr)}; }
  function vis(i){ return !hidden[DATA.nodes[i].c]; }

  function draw(){
    if(!DATA) return;
    var W=cv.width/dpr, H=cv.height/dpr;
    ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.clearRect(0,0,W,H);
    var maxW=DATA.edges.length?DATA.edges[0][2]:1;
    // edges first, bowed toward the centre so the bundle reads as a weave
    for(var e=0;e<DATA.edges.length;e++){
      var a=DATA.edges[e][0], b=DATA.edges[e][1], w=DATA.edges[e][2];
      if(!vis(a)||!vis(b)) continue;
      var lit=(hot===a||hot===b);
      if(hot>=0 && !lit) continue;
      var p=T(LAY[a]), q=T(LAY[b]);
      var t=Math.log(1+w)/Math.log(1+maxW);
      ctx.strokeStyle=lit?'rgba(233,196,106,.85)':'rgba(150,200,190,'+(0.05+0.30*t)+')';
      ctx.lineWidth=(lit?1.6:0.4+2.2*t)*Math.min(scale,2);
      // bundle each chord toward the centre of the VIEW (not a fixed offset —
      // that skewed the whole weave off to one side)
      var mx2=(p.x+q.x)/2, my2=(p.y+q.y)/2, C=T({x:cx0,y:cy0});
      ctx.beginPath(); ctx.moveTo(p.x,p.y);
      ctx.quadraticCurveTo(mx2+(C.x-mx2)*0.45, my2+(C.y-my2)*0.45, q.x, q.y);
      ctx.stroke();
    }
    // nodes, then labels for the heavy ones (or everything, once zoomed in)
    for(var i=0;i<DATA.nodes.length;i++){
      if(!vis(i)) continue;
      var n=DATA.nodes[i], P=T(LAY[i]), rad=LAY[i].r*Math.min(scale,2.2);
      ctx.beginPath(); ctx.arc(P.x,P.y,rad,0,Math.PI*2);
      ctx.fillStyle=COL[n.c]||'#9aa'; ctx.globalAlpha=(hot<0||hot===i)?1:0.35;
      ctx.fill(); ctx.globalAlpha=1;
      if(hot===i){ ctx.strokeStyle='#fff'; ctx.lineWidth=2; ctx.stroke(); }
    }
    // Labels, heaviest first, and NEVER on top of each other: the middle of this
    // map is where the corpus is densest, which is exactly where overlapping
    // text turns a legible picture into a smear. A claimed-box test drops the
    // ones that would collide; zooming in gives them room and they return.
    ctx.font='13px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif';
    ctx.textAlign='center'; ctx.textBaseline='middle';
    var taken=[], ORDER=DATA.__order||(DATA.__order=DATA.nodes
      .map(function(n,i){return i;})
      .sort(function(a,b){return DATA.nodes[b].n-DATA.nodes[a].n;}));
    for(var oi=0;oi<ORDER.length;oi++){
      var j=ORDER[oi];
      if(!vis(j)) continue;
      var nn=DATA.nodes[j];
      var show=(hot===j)||(scale>1.7)||(LAY[j].r>7.2);
      if(!show) continue;
      var PP=T(LAY[j]);
      if(PP.x<-40||PP.y<-20||PP.x>W+40||PP.y>H+20) continue;
      var tx=nn.l.length>26?nn.l.slice(0,25)+'…':nn.l;
      var w=ctx.measureText(tx).width, ly=PP.y-LAY[j].r*Math.min(scale,2.2)-9;
      var box=[PP.x-w/2-3,ly-9,PP.x+w/2+3,ly+9], clash=false;
      if(hot!==j){
        for(var b2=0;b2<taken.length;b2++){var t2=taken[b2];
          if(box[0]<t2[2]&&t2[0]<box[2]&&box[1]<t2[3]&&t2[1]<box[3]){clash=true;break;}}
      }
      if(clash) continue;
      taken.push(box);
      ctx.lineWidth=3.5; ctx.strokeStyle='rgba(11,30,28,.92)';
      ctx.strokeText(tx,PP.x,ly);
      ctx.fillStyle=(hot===j)?'#fff':'rgba(238,244,240,.92)';
      ctx.fillText(tx,PP.x,ly);
    }
  }
  function nearest(mx,my){
    var best=-1,bd=22*22;
    for(var i=0;i<DATA.nodes.length;i++){
      if(!vis(i)) continue;
      var P=T(LAY[i]), dx=P.x-mx, dy=P.y-my, d=dx*dx+dy*dy;
      if(d<bd){bd=d;best=i;}
    }
    return best;
  }
  function neighbours(i){
    var out=[];
    for(var e=0;e<DATA.edges.length;e++){
      var E=DATA.edges[e];
      if(E[0]===i&&vis(E[1]))out.push([E[1],E[2]]);
      else if(E[1]===i&&vis(E[0]))out.push([E[0],E[2]]);
    }
    out.sort(function(a,b){return b[1]-a[1];});
    return out.slice(0,6);
  }
  function esc(s){return String(s).replace(/[<>&]/g,function(c){return {'<':'&lt;','>':'&gt;','&':'&amp;'}[c];});}
  function showInfo(i){
    if(i<0){info.classList.remove('show');return;}
    var n=DATA.nodes[i], nb=neighbours(i);
    info.innerHTML='<b>'+esc(n.l)+'</b><span class=cls>'+esc(CLS[n.c]||n.c)+' · '+
      n.n.toLocaleString()+' records</span>'+
      (nb.length?'<ul>'+nb.map(function(p){
        return '<li>'+esc(DATA.nodes[p[0]].l)+' <span style="opacity:.65">'+
          p[1].toLocaleString()+' shared</span></li>';}).join('')+'</ul>':'')+
      (n.h?'<div style="margin-top:6px;opacity:.75">click to open</div>':'');
    info.classList.add('show');
  }
  // ---- interaction ---------------------------------------------------------
  var drag=null;
  cv.addEventListener('pointerdown',function(ev){
    drag={x:ev.clientX,y:ev.clientY,ox:off.x,oy:off.y,moved:false};
    cv.classList.add('drag'); cv.setPointerCapture(ev.pointerId);});
  cv.addEventListener('pointermove',function(ev){
    var r=cv.getBoundingClientRect(), mx=ev.clientX-r.left, my=ev.clientY-r.top;
    if(drag){
      var dx=ev.clientX-drag.x, dy=ev.clientY-drag.y;
      if(Math.abs(dx)+Math.abs(dy)>3)drag.moved=true;
      off.x=drag.ox+dx/scale; off.y=drag.oy+dy/scale; draw(); return;
    }
    var h=nearest(mx,my);
    if(h!==hot){hot=h; showInfo(h); draw(); cv.style.cursor=h>=0?'pointer':'grab';}
  });
  function endDrag(ev){ if(drag){cv.classList.remove('drag'); if(!drag.moved){
      var r=cv.getBoundingClientRect(), h=nearest(ev.clientX-r.left,ev.clientY-r.top);
      if(h>=0&&DATA.nodes[h].h) location.href=BASE+DATA.nodes[h].h.replace(/^\//,'');
    } drag=null;} }
  cv.addEventListener('pointerup',endDrag);
  cv.addEventListener('pointercancel',function(){drag=null;cv.classList.remove('drag');});
  cv.addEventListener('wheel',function(ev){
    ev.preventDefault();
    var f=Math.exp(-ev.deltaY*0.0016);
    scale=Math.max(0.55,Math.min(6,scale*f)); draw();
  },{passive:false});
  document.getElementById('atreset').addEventListener('click',function(){
    scale=1; off={x:0,y:0}; hot=-1; showInfo(-1); draw();});
  document.getElementById('atlegend').addEventListener('click',function(ev){
    var b=ev.target.closest('button[data-cls]'); if(!b)return;
    var c=b.getAttribute('data-cls'); hidden[c]=!hidden[c];
    b.setAttribute('aria-pressed',hidden[c]?'false':'true'); draw();});
  document.getElementById('atq').addEventListener('input',function(ev){
    var q=ev.target.value.trim().toLowerCase();
    if(!q){hot=-1;showInfo(-1);draw();return;}
    for(var i=0;i<DATA.nodes.length;i++){
      if(DATA.nodes[i].l.toLowerCase().indexOf(q)>=0&&vis(i)){
        hot=i; showInfo(i);
        // centre it, so finding a thing also takes you to it
        off.x=cv.width/(2*dpr)-LAY[i].x; off.y=cv.height/(2*dpr)-LAY[i].y;
        draw(); return;}
    }
    hot=-1; showInfo(-1); draw();});
  addEventListener('resize',function(){ if(DATA){layout();draw();} });

  // ---- the same data, as a list — always present, never a fallback ---------
  function list(){
    var by={};
    DATA.nodes.forEach(function(n){ (by[n.c]=by[n.c]||[]).push(n); });
    var html='';
    Object.keys(by).sort().forEach(function(c){
      html+='<h3 style="margin:16px 0 4px;font-size:15px">'+esc(CLS[c]||c)+'</h3><ul>';
      by[c].sort(function(a,b){return b.n-a.n;}).forEach(function(n){
        html+='<li>'+(n.h?'<a href="'+esc(n.h)+'">'+esc(n.l)+'</a>':esc(n.l))+
          ' <span class=n>'+n.n.toLocaleString()+'</span></li>';});
      html+='</ul>';
    });
    document.getElementById('atlistbody').innerHTML=html;
  }
  fetch(BASE+'api/atlas.json').then(function(r){return r.json();}).then(function(d){
    DATA=d; layout(); draw(); list();
  }).catch(function(){
    document.querySelector('.atwrap').innerHTML=
      '<p class=muted>The atlas data could not be loaded.</p>';
  });
})();
"""

ATLAS_JS = (ATLAS_JS
            .replace("%%COLOURS%%", __import__("json").dumps(CLASS_COLOURS))
            .replace("%%CLSLABEL%%", __import__("json").dumps(CLASS_LABEL,
                                                              ensure_ascii=False)))


def card_bytes(payload):
    """The atlas's own share card: the real layout, drawn small. Pillow, in-build
    (same precedent as og_card_bytes and the trail cards)."""
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None
    try:
        import math
        import wiki as _w
        W, H = 1200, 630
        img = Image.new("RGB", (W, H), (14, 37, 35))
        d = ImageDraw.Draw(img)
        nodes, edges = payload["nodes"], payload["edges"]
        cx, cy, R, Rin = W * 0.62, H / 2, H * 0.42, H * 0.07
        by_cls = {}
        for i, n in enumerate(nodes):
            by_cls.setdefault(n["c"], []).append(i)
        maxn = max((n["n"] for n in nodes), default=1)
        pos = {}
        a0, tot = -math.pi / 2, sum(math.sqrt(len(v)) for v in by_cls.values()) or 1
        for c in sorted(by_cls):
            idxs = sorted(by_cls[c], key=lambda i: -nodes[i]["n"])
            span = 2 * math.pi * math.sqrt(len(idxs)) / tot
            for k, ni in enumerate(idxs):
                frac = (k + 0.5) / len(idxs) if len(idxs) > 1 else 0.5
                ang = a0 + span * frac
                depth = math.log(1 + nodes[ni]["n"]) / math.log(1 + maxn)
                rad = Rin + (R - Rin) * (1 - depth)
                pos[ni] = (cx + math.cos(ang) * rad, cy + math.sin(ang) * rad,
                           2 + 6 * depth ** 1.3)
            a0 += span
        maxw = edges[0][2] if edges else 1
        for a, b, w in edges:
            if a not in pos or b not in pos:
                continue
            t = math.log(1 + w) / math.log(1 + maxw)
            g = int(70 + 90 * t)
            d.line([pos[a][0], pos[a][1], pos[b][0], pos[b][1]],
                   fill=(40 + g // 3, g, g - 10), width=1)
        for i, (x, y, r) in pos.items():
            col = CLASS_COLOURS.get(nodes[i]["c"], "#9aa").lstrip("#")
            rgb = tuple(int(col[j:j + 2], 16) for j in (0, 2, 4))
            d.ellipse([x - r, y - r, x + r, y + r], fill=rgb)
        tf, sf = _w._og_font(62), _w._og_font(27)
        if tf and sf:
            d.text((70, 214), "The Atlas", font=tf, fill=(244, 234, 214))
            y = 300
            for ln in _w._wrap(d, "Every concept the archive uses, joined by how "
                                 "many records they share.", sf, 360)[:4]:
                d.text((70, y), ln, font=sf, fill=(150, 180, 172))
                y += 36
            d.text((70, H - 70), "wichaa.net/atlas", font=sf, fill=(233, 196, 106))
        import io
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True)
        return buf.getvalue()
    except Exception:
        return None
