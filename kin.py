#!/usr/bin/env python3
"""kin — what the three dials have to do with each other.

A list of links tells a reader that other pages exist. It does not tell them why
they should care, and on a site whose whole argument is that the material is
*connected*, that is the interesting half left out.

So each dial says, in its own words, what the other two are **to it**. The moon
complication is the ancestor; the jovilabe is the same question asked of another
planet; the Red Spot dial is that question turned inside out and asked from the far
end. The wording changes depending on where you are standing, because the
relationship does.

The numbers in here are not decoration and they are not retyped. They come from the
instruments themselves:

  * Io seen from the Great Red Spot is 0.60 degrees across. Our own Moon is 0.52.
    Of everything in that sky, the one thing that would look familiar is the size of
    the nearest moon — which is the sentence that ties the newest dial back to the
    oldest one.
  * A lunation here is 29.53 days. From the Red Spot, Io comes round again in
    12.96 hours, and the slowest of the four takes 10.18. The idea generalises; the
    timescale does not survive the trip.
"""
from __future__ import annotations

KOFI = "https://ko-fi.com/defiantchiangmai"

# path -> (title, what it is in one line)
DIALS = {
    "/moon": ("The moon complication",
              "our own moon, on a disc that carries two of them"),
    "/jovilabe": ("The Jovilabe",
                  "Jupiter&#8217;s four moons, seen from here"),
    "/redspot": ("The Red Spot dial",
                 "the same four moons, seen from <em>there</em>"),
}

# How each page describes the other two. Keyed (standing_on, pointing_at).
SAID = {
    ("/moon", "/jovilabe"): (
        "This dial does for Jupiter what the one above does for the Earth &#8212; "
        "except that Jupiter has four moons to keep track of, so instead of one "
        "turning disc it needs a gear train, and instead of a phase it reports "
        "eclipses, transits and occultations."),
    ("/moon", "/redspot"): (
        "And this one asks the question from the other side: what the sky looks like "
        "to somebody standing on Jupiter. The lunation you are reading here takes "
        "29&#189; days. There, the nearest moon comes round again in under thirteen "
        "hours &#8212; and it is almost exactly the size of the moon on this page."),
    ("/jovilabe", "/moon"): (
        "The one this grew out of, and the simpler machine by far: a single disc "
        "carrying two moons behind a cloud plate, half a turn a month. Everything "
        "here &#8212; drawing the mechanism rather than a picture of it, publishing "
        "the error instead of the claim &#8212; was worked out on that dial first."),
    ("/jovilabe", "/redspot"): (
        "The same four moons and the same tables, pointed the other way: the sky over "
        "the Great Red Spot, where the moons rise and set. Two things this instrument "
        "labours over vanish there. There is no light equation to apply &#8212; you "
        "are standing next to them &#8212; and eclipses stop being something you "
        "compute and become something that happens overhead."),
    ("/redspot", "/moon"): (
        "The ancestor of this dial, and still the plainest of the three: our own moon, "
        "one disc, two moons, half a turn a lunation. The link is closer than it "
        "looks. Io in this sky is 0.60&deg; across; the moon on that page is 0.52&deg;. "
        "In all that strangeness, the size of the nearest moon is the one thing that "
        "would feel like home."),
    ("/redspot", "/jovilabe"): (
        "The same arithmetic, read from the Earth instead: where these four stand as "
        "seen through a telescope, what the gearing to drive them would have to be, "
        "and why their eclipses were once the only clock the whole world could read "
        "at once."),
}


def block(here: str) -> str:
    """The kin block for the page at ``here``."""
    others = [p for p in DIALS if p != here]
    cards = []
    for path in others:
        title, _what = DIALS[path]
        cards.append(
            f"<a class=kin-card href='{path}'>"
            f"<b>{title}</b>"
            f"<span>{SAID[(here, path)]}</span>"
            f"<i>{path} &#8594;</i></a>")
    return (
        "<section class=kin>"
        "<h2>Its kin</h2>"
        "<p class=kin-lead>Three instruments, one method: draw the mechanism rather "
        "than a picture of it, compute everything in the page, and publish the error "
        "rather than the claim. They are more interesting together than apart.</p>"
        "<div class=kin-cards>" + "".join(cards) + "</div>"
        "</section>"
        + support_block()
    )


def support_block() -> str:
    return (
        "<section class=kofi-cta>"
        "<div>"
        "<b>&#9749; These are free.</b>"
        "<p>No accounts, no app store, nothing to buy. If one of them was "
        "worth your evening, you can buy me a coffee &#8212; it pays for the "
        "domain and the hosting and nothing else.</p>"
        "</div>"
        f"<a class=kofi-btn href='{KOFI}' target=_blank rel=noopener>"
        "Support on Ko-fi</a>"
        "</section>"
    )


def share_block(path: str, title: str) -> str:
    """A visible share row — the floating bar is easy to miss on a long page."""
    return (
        "<section class=shareme>"
        "<b>Share this dial</b>"
        f"<div class=shareme-row data-path='{path}' data-title=\"{title}\">"
        "<button class=sm data-k=copy>&#128279; Copy link</button>"
        "<button class=sm data-k=fb>Facebook</button>"
        "<button class=sm data-k=line>LINE</button>"
        "<button class=sm data-k=tg>Telegram</button>"
        "<button class=sm data-k=x>X</button>"
        "<button class=sm data-k=native hidden>&#10148; Share&#8230;</button>"
        "</div><span class=shareme-said></span></section>"
        + SHARE_JS
    )


SHARE_JS = """<script>(function(){
  var row=document.querySelector('.shareme-row'); if(!row) return;
  var said=document.querySelector('.shareme-said');
  var url=location.origin+row.dataset.path, title=row.dataset.title;
  if(navigator.share) row.querySelector('[data-k=native]').hidden=false;
  var go={
    fb:'https://www.facebook.com/sharer/sharer.php?u='+encodeURIComponent(url),
    line:'https://social-plugins.line.me/lineit/share?url='+encodeURIComponent(url),
    tg:'https://t.me/share/url?url='+encodeURIComponent(url)+'&text='+encodeURIComponent(title),
    x:'https://twitter.com/intent/tweet?url='+encodeURIComponent(url)+'&text='+encodeURIComponent(title)
  };
  row.addEventListener('click',function(e){
    var b=e.target.closest('button[data-k]'); if(!b) return;
    var k=b.dataset.k;
    if(k==='copy'){
      navigator.clipboard.writeText(url).then(function(){said.textContent='Link copied.';},
        function(){said.textContent=url;});
      return;
    }
    if(k==='native'){navigator.share({title:title,url:url}).catch(function(){}); return;}
    window.open(go[k],'_blank','noopener,width=640,height=560');
  });
})();</script>"""


CSS = """
/* The tail sits outside each dial's own wrapper, so it needs its own measure —
   otherwise it runs edge-to-edge while the prose above it is inset. */
.dialtail{max-width:1040px;margin:34px auto 0;padding:0 18px}
.kin{margin:34px 0 0;border-top:2px solid var(--line);padding-top:6px}
.kin h2{font-size:20px;margin:.9em 0 .3em}
.kin-lead{color:var(--muted);font-size:15.5px;max-width:70ch;margin:0 0 16px}
.kin-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
.kin-card{display:block;text-decoration:none;color:inherit;background:var(--card);
  border:1px solid var(--line);border-left:5px solid var(--gold);border-radius:10px;
  padding:14px 16px;transition:transform .12s ease,box-shadow .12s ease}
.kin-card:hover{transform:translateY(-2px);box-shadow:0 6px 18px #0001}
.kin-card b{display:block;font-family:var(--serif);font-size:18.5px;margin-bottom:6px}
.kin-card span{display:block;font-size:15px;line-height:1.55;color:var(--ink)}
.kin-card i{display:block;margin-top:10px;font-style:normal;font-size:14px;
  letter-spacing:.06em;color:var(--gold)}
.kofi-cta{display:flex;flex-wrap:wrap;gap:16px;align-items:center;justify-content:space-between;
  background:var(--gold-bg);border:1px solid #e6d3a8;border-radius:12px;
  padding:16px 20px;margin:22px 0 0}
.kofi-cta b{font-size:17px;display:block;margin-bottom:4px}
.kofi-cta p{margin:0;font-size:15px;color:#5f4b1c;max-width:62ch}
.kofi-btn{flex:0 0 auto;background:#8a5a00;color:#fff;text-decoration:none;font-weight:700;
  padding:13px 22px;border-radius:999px;font-size:16px;white-space:nowrap}
.kofi-btn:hover{filter:brightness(1.12)}
.shareme{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:20px 0 0;
  padding:14px 16px;border:1px dashed var(--line);border-radius:10px}
.shareme b{font-size:15.5px}
.shareme-row{display:flex;flex-wrap:wrap;gap:8px}
.shareme .sm{font:inherit;font-size:14.5px;padding:8px 13px;border-radius:8px;cursor:pointer;
  border:1px solid var(--line);background:var(--card);color:var(--ink)}
.shareme .sm:hover{background:#fff;border-color:var(--gold)}
.shareme-said{font-size:14px;color:var(--ok)}
@media (max-width:640px){.kofi-cta{justify-content:flex-start}}
"""
