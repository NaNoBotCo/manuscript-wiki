#!/usr/bin/env python3
"""article_pages — one real, crawlable page per subject article (genre/entity/
sub-genre), mirroring manuscript_pages.py's "two doors, one subject" fix.

WHY THIS EXISTS
/a?id=<key> is one client-rendered SPA shell (ARTICLE_PAGE, wiki.py) that reads
identically for all ~33+ subjects — genres, curated esoteric entities, authored
sub-genres. A search engine or a shared link sees the same generic template no
matter which subject it names. This writes the real thing: a self-contained,
server-rendered page per subject, at /a/<slug>/, with the actual authored prose
where it exists and an honest data-only lede where it doesn't — never a blank or
invented page. /a?id=<key> stays the interactive door (connections graph, live
findings) — reached from here by an explicit link, same as manuscripts.

Reuses manuscript_pages._CSS (generic page chrome, not manuscript-specific) rather
than duplicating it.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

import cartography
from manuscript_pages import _CSS, _esc

# Per-article share-card masters (publishing/cards/a__<slug>.png). site_meta.py
# copies each master to /a/<slug>/card.png post-build, so the master's existence
# at build time is the only signal page_html can key og:image off — the copy
# itself hasn't happened yet when this module renders.
_CARD_MASTERS = Path(__file__).resolve().parent / "publishing" / "cards"


def _hero(prof, site):
    """(img_url, caption) from prof['image']['src'] — already bundled to a static,
    base-relative path by build_static.py's bundle_article_image() before this is
    called, so no image-resolution logic belongs here (matches build_place_pages.py's
    precedent: the caller resolves images, the page renderer just points at them).
    Absolutized against `site` (the origin) — unfurlers won't resolve a relative
    og:image, same rule as manuscript_pages.py's og_image handling."""
    img = prof.get("image") or {}
    src = img.get("src")
    if not src:
        return None
    url = src if src.startswith("http") else f"{site}{src}" if site else src
    return url, img.get("caption") or ""


def _jsonld(prof, url, img_url, authored):
    label = prof.get("label") or prof["value"]
    if authored.get("exists"):
        ld = {"@context": "https://schema.org", "@type": "Article",
              "headline": authored.get("title") or label, "name": label, "url": url,
              "articleBody_available": True,
              "isPartOf": {"@type": "Collection", "name": "wichaa"}}
    else:
        # No authored prose — this is a data-driven subject overview, not an
        # "Article" in the schema.org sense; CollectionPage is the honest type.
        ld = {"@context": "https://schema.org", "@type": "CollectionPage",
              "name": label, "url": url,
              "isPartOf": {"@type": "Collection", "name": "wichaa"}}
    profc = prof.get("profile") or {}
    if profc.get("count"):
        ld["about"] = {"@type": "Thing", "name": label}
    if img_url:
        ld["image"] = img_url
    return json.dumps(ld, ensure_ascii=False)


def page_html(prof, slug, wiki):
    """`prof` is wiki.build_article(stype, value) with prof['image'] already
    rewritten to a base-prefixed bundled static path by build_static.py's
    bundle_article_image(). `slug` is the filesystem/URL-safe id
    (build_static.art(key)) — computed by the caller so this module doesn't need
    to duplicate that regex."""
    site = (wiki.SITE_URL or "").rstrip("/")
    url = f"{site}/a/{slug}/" if site else f"/a/{slug}/"
    label = prof.get("label") or prof["value"]
    authored = prof.get("authored") or {}
    has_article = bool(authored.get("exists"))
    title = (authored.get("title") if has_article else "") or label
    lede = prof.get("lede") or ""
    profc = prof.get("profile") or {}
    count = profc.get("count") or 0
    browse_col = prof.get("browseCol") or ""

    crumb_items = [("wichaa", "/"), ("Subjects", "/articles"), (title[:60], url)]
    crumb = [f'<a href="{_esc(h)}">{_esc(n)}</a>' for n, h in crumb_items[:-1]]
    crumb.append(f'<b>{_esc(crumb_items[-1][0])}</b>')
    crumb_html = f'<p class=crumb>{" &rsaquo; ".join(crumb)}</p>'
    crumb_ld = [(n, h if h.startswith("http") else f"{site}{h}") for n, h in crumb_items]

    hero = _hero(prof, site)
    if hero:
        img_url, caption = hero
        hero_html = (f'<img class=hero src="{_esc(img_url)}" alt="{_esc(caption or title)}" loading="lazy">'
                     + (f'<p class=cred>{_esc(caption)}</p>' if caption else ''))
    else:
        img_url = None
        hero_html = ('<div class=noimg>No representative image is catalogued for this '
                     'subject yet.</div>')

    if count:
        meta_html = (f'<dl class=meta><dt>Manuscripts</dt><dd>{count:,}</dd></dl>')
    else:
        meta_html = ""

    body_html = authored.get("body_html") if has_article else ""
    lede_html = f'<p class=th>{_esc(lede)}</p>' if lede and not has_article else ""

    if browse_col and count:
        cta_html = (f'<div class=read><a href="/browse?{_esc(browse_col)}='
                   f'{_esc(prof["value"])}">Browse all {count:,} →</a></div>')
    else:
        cta_html = ""

    conns = wiki.connections(prof["type"], prof["value"]) or []
    peers_html = ""
    if conns:
        rows = "".join(
            f'<li><a href="{_esc(cartography.href_for(c["key"]))}">{_esc(c["label"])}</a> '
            f'<span style="color:var(--muted);font-size:13px">({_esc(c["rel"])})</span></li>'
            for c in conns[:12] if cartography.href_for(c["key"]))
        peers_html = f'<div class=peers><h3>Connections</h3><ul>{rows}</ul></div>'

    tool_html = (f'<div class=tool><a href="/a?id={html.escape(prof["key"], quote=True)}">'
                 'Open the interactive view →</a>'
                 '<p>The live connections graph and any current curiosity-bot findings.</p></div>')

    su = _esc(url)
    share_html = (
        '<div class=share>Share this subject &nbsp;'
        f'<a target=_blank rel=noopener href="https://social-plugins.line.me/lineit/share?url={su}">LINE</a>'
        f'<a target=_blank rel=noopener href="https://www.facebook.com/sharer/sharer.php?u={su}">Facebook</a>'
        f'<a target=_blank rel=noopener href="https://t.me/share/url?url={su}">Telegram</a>'
        '</div>')

    foot_html = ('<div class=foot><a href="/articles">← All subjects</a> &nbsp;·&nbsp; '
                 '<a href="/">wichaa — an open archive of Lanna manuscripts and living wichaa</a></div>')

    description = (lede or f"{label} in the wichaa archive.")[:300]
    # A real folio beats a drawn card; a drawn card beats the sitewide yantra.
    if img_url:
        ogimg = img_url
    elif (_CARD_MASTERS / f"a__{slug}.png").is_file():
        ogimg = f"{site}/a/{slug}/card.png"
    else:
        ogimg = f"{site}/og.jpg" if site else "/og.jpg"

    head = (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        f"<title>{_esc(title[:70])} — wichaa</title>"
        f'<meta name=description content="{_esc(description)}">'
        f'<link rel=canonical href="{su}">'
        '<link rel=icon href="/favicon.svg">'
        '<meta property="og:type" content="article">'
        '<meta property="og:site_name" content="wichaa">'
        f'<meta property="og:title" content="{_esc(title[:90])}">'
        f'<meta property="og:description" content="{_esc(description)}">'
        f'<meta property="og:url" content="{su}">'
        f'<meta property="og:image" content="{_esc(ogimg)}">'
        '<meta name="twitter:card" content="summary_large_image">'
        f'<meta name="twitter:title" content="{_esc(title[:90])}">'
        f'<meta name="twitter:image" content="{_esc(ogimg)}">'
        f'<script type="application/ld+json">{_jsonld(prof, url, img_url, authored)}</script>'
        f'<script type="application/ld+json">{json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": h} for i, (n, h) in enumerate(crumb_ld)]}, ensure_ascii=False)}</script>'
        f"<style>{_CSS}</style></head>")

    top = ('<div class=top><a class=mark href="/">วิชา · wichaa</a>'
           '<nav><a href="/browse">Browse</a> <a href="/articles">Subjects</a> '
           '<a href="/atlas">Atlas</a> <a href="/support">☕ Support</a></nav></div>')

    body = (
        "<body>" + top + '<div class=wrap>'
        + crumb_html
        + f"<h1>{_esc(title[:90])}</h1>"
        + lede_html + hero_html + meta_html + cta_html
        + (f'<div class=icono>{body_html}</div>' if body_html else "")
        + tool_html + peers_html + share_html + foot_html
        + "</div></body></html>")

    return head + body
