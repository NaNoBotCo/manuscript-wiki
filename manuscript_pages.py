#!/usr/bin/env python3
"""manuscript_pages — one real, crawlable page per manuscript (Phase F, decision 6).

WHY THIS EXISTS
Every manuscript already has a rich JSON record (api/manuscript/<id>.json) and an
interactive detail view (/m?id=<id>, a client-rendered SPA). Neither is a page a
search engine indexes as distinct content: the JSON isn't HTML, and the SPA is one
template shell that reads identically no matter which id the query names. Measured:
searching this project's own subject — "Lanna manuscript archive", "Tai Tham yantra
katha" — returns EFEO, CrossAsia, thaimanuscripts.de, never wichaa, though wichaa's
corpus is larger. The site was built almost entirely for the visitor who already
knows to come here; it had almost nothing for the one who would find it by searching.

THE FIX MATCHES THE PROJECT'S OWN PRINCIPLE: two doors, one manuscript.
  · /m/<id>/    — THIS module. A real, server-rendered, indexable page: title,
    metadata, a real hero image where one exists, schema.org structured data, and
    the manuscript's actual graph THREADS (named relations, receipted). This is
    what Google indexes, what a shared link unfurls as, and where a HUMAN wandering
    the graph lands.
  · /m?id=<id>  — unchanged. The interactive tool: OCR, page thumbnails, annotation,
    the facsimile viewer. Reached from this page by an explicit "Open the interactive
    viewer" link — never removed as a destination, just no longer the only door.

WHY THIS IS A SELF-CONTAINED LIGHT PAGE, NOT wiki.page()
The interactive pages inline a ~17 kB SPA shim (fetch interception, image rewriting)
plus the full site stylesheet into EVERY page. A static content page needs none of
that, and at 6,990 pages the duplication is ~180 MB of pure repeat. So this follows
the /place/<id>/ precedent (build_place_pages.py): a small self-contained document,
its own ~2 kB of CSS, no shim — ~9 kB a page instead of ~35 kB. The wayfinding value
(threads, breadcrumb, a light header, share) is kept; the machinery is dropped.

Extract-don't-author: every fact rendered is a catalogue column or a graph edge with
its receipt. Nothing here is synthesised prose.
"""
from __future__ import annotations

import html
import json

import cartography
import imagemeta
import strings
import taxonomy

KOFI = "https://ko-fi.com/defiantchiangmai"

# A compact self-contained stylesheet — the site's palette, responsive, ~2 kB.
_CSS = """
:root{--bg:#f4efe3;--panel:#fdfbf5;--ink:#26302a;--muted:#6d6455;--gold:#a8791e;
--crimson:#8c3b2e;--line:#e5dcc7;--teal:#1f4e4a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.6 -apple-system,
BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
-webkit-font-smoothing:antialiased}
a{color:var(--crimson);text-decoration:none}a:hover{text-decoration:underline}
h1,h2,h3{font-family:"Iowan Old Style",Palatino,Georgia,serif;line-height:1.2}
.top{background:var(--teal);color:#f4efe3;padding:12px 20px;display:flex;flex-wrap:wrap;
gap:6px 16px;align-items:baseline}
.top a{color:#f4efe3}.top .mark{font-weight:700;letter-spacing:.04em;margin-right:auto}
.top nav a{font-size:14.5px;opacity:.92;padding:4px 2px;display:inline-block;min-height:32px}
.wrap{max-width:800px;margin:0 auto;padding:22px 20px 60px}
.crumb{font-size:14px;color:var(--muted);margin:0 0 16px}
.crumb a{color:var(--muted)}
h1{font-size:clamp(24px,4.5vw,33px);margin:0 0 4px}
.th{font-family:"Iowan Old Style",serif;font-size:19px;color:#43403a;margin:0 0 18px}
.subj{margin:0 0 18px}
.subj a{display:inline-block;margin:0 6px 6px 0;padding:5px 13px;border-radius:999px;
background:#fdf3dd;border:1px solid #e5cf9a;color:#8a5a00;font-weight:600;font-size:14px}
.hero{width:100%;border-radius:12px;display:block;margin:0 0 6px;background:#eef2f1}
.cred{font-size:12.5px;color:var(--muted);margin:0 0 20px}
.noimg{font-size:15px;color:#43473f;background:#efe9db;border-radius:10px;
padding:14px 16px;margin:0 0 20px}
dl.meta{display:grid;grid-template-columns:140px 1fr;gap:8px 16px;margin:0 0 22px}
dl.meta dt{color:var(--muted);font-weight:600;font-size:14.5px}
dl.meta dd{margin:0}
.read{background:rgba(168,121,30,.1);border:1px solid rgba(168,121,30,.32);
border-radius:12px;padding:15px 17px;margin:0 0 22px}
.read a{font-weight:700}
.icono{margin:26px 0 0;padding-top:16px;border-top:1px solid var(--line)}
.icono h2{font-size:19px;margin:0 0 4px}
.iconolede{font-size:14.5px;color:var(--muted);margin:0 0 12px;max-width:44rem}
.icono ul{list-style:none;margin:0;padding:0}
.icono li{margin:0 0 14px;font-size:16px;line-height:1.6;padding-left:14px;
border-left:3px solid rgba(168,121,30,.4)}
.icono li b{font-family:"Iowan Old Style",serif}
.icono li a{font-size:14px;white-space:nowrap}
.tool{margin:22px 0 0;padding:15px 17px;border:1px solid var(--line);border-radius:12px;
background:var(--panel)}
.tool a{font-weight:700}.tool p{margin:5px 0 0;color:var(--muted);font-size:14px}
.pages{margin:22px 0 0}
.pages h2{font-size:19px;margin:0 0 4px}
.thumbwall{display:grid;grid-template-columns:repeat(auto-fill,minmax(92px,1fr));gap:8px;margin-top:10px}
.tw{display:block;position:relative;aspect-ratio:3/4;border-radius:8px;overflow:hidden;
border:1px solid var(--line);background:#f0efe9}
.tw img{width:100%;height:100%;object-fit:cover;display:block}
.tw.dia{border-color:var(--gold)}
.tw .pgnum{position:absolute;left:4px;bottom:4px;background:rgba(38,48,42,.72);color:#fdfbf5;
font-size:11px;padding:1px 5px;border-radius:5px}
.peers{margin:26px 0 0;padding-top:16px;border-top:1px solid var(--line)}
.peers h3{font-size:15px;margin:0 0 8px}.peers ul{list-style:none;margin:0 0 16px;padding:0}
.peers li{margin:4px 0;font-size:15px}
.share{margin:26px 0 0;padding-top:16px;border-top:1px solid var(--line);font-size:14px;color:var(--muted)}
.share a{display:inline-block;min-height:40px;padding:8px 14px;margin:0 6px 6px 0;
border:1px solid var(--line);border-radius:999px;color:var(--ink);font-weight:600}
foot,.foot{display:block;margin:30px 0 0;padding-top:16px;border-top:1px solid var(--line);
font-size:14px;color:var(--muted)}
.cite-arch{display:inline-block;font-size:14px;font-weight:600;line-height:1.5;padding:0 9px;
margin:0 3px;border:1px solid var(--line);border-radius:999px;background:#efe9db;
color:var(--muted);white-space:nowrap}
a.cite-arch{color:var(--teal)}a.cite-arch:hover{text-decoration:none;border-color:var(--teal)}
.cite-arch.quiet{background:#f2ede1}
@media(max-width:520px){dl.meta{grid-template-columns:1fr;gap:2px 0}
dl.meta dt{margin-top:9px}.wrap{padding:16px 15px 48px}}
"""


def _esc(s):
    return html.escape(str(s or ""), quote=True)


# The dead-source rule is DETAIL_PAGE's own (wiki.py): CrossAsia's collections
# route and 'local:' contributed paths both 404 now. Mirrored so a server-rendered
# page never links a dead "view at source".
def _source_link(det):
    manifest = det.get("iiifManifestUrl")
    if manifest:
        return manifest, "View at source library (IIIF) ↗"
    src = det.get("sourceUrl") or ""
    if src and not (src.startswith("local:") or "/s/lanna/collections/" in src):
        return src, "View at source ↗"
    return None, None


def _hero(det, wiki, base="/"):
    """(img_url, alt, credit, page) for the best real image, or None. `page` is the
    described-plate dict when the hero is a contributed volume's illustrated page
    (so the caller can use its vision reading as alt/description), else None — same
    tier order as site_meta.manuscript_images() for IIIF folios so this page's hero
    and the sitemap agree, then a rendered plate we already bundle."""
    for im in det.get("images") or []:
        if im.get("hasLocal") and im.get("sourceUrl"):
            return (wiki.iiif_resize(im["sourceUrl"], 1200),
                    f"Folio {im.get('sequence', '')} of {det.get('title', 'this manuscript')}",
                    "Image via IIIF from the holding library", None)
    if det.get("iiifThumb"):
        return (wiki.iiif_resize(det["iiifThumb"], 1200), det.get("title", ""),
                "Thumbnail via IIIF from the source catalogue", None)
    # No IIIF image — but a contributed volume whose illustrated pages a vision pass
    # has read carries real, bundled plate images (docs/pimg/<mid>/<n>.png, copied by
    # build_static from gallery_snapshot). Use the first described page as the
    # manuscript's face, so the page, its share-unfurl, and its ImageObject show the
    # actual illustration and its reading instead of a bare 'no image' note.
    described = imagemeta.described_pages(det, limit=1)
    if described:
        n = described[0]["n"]
        page = {"n": n, "descFull": described[0]["text"]}
        return (f"{base}pimg/{det['id']}/{n}.png",
                imagemeta.hero_alt(det, page),
                imagemeta.credit_line(det), page)
    return None


def _meta_rows(det):
    rows = []
    if det.get("source"):
        rows.append(("Source", _esc(det["source"])))
    if det.get("genreLabel"):
        rows.append(("Genre", f'<a href="{_esc(cartography.href_for("genre:" + det["genre"]))}">{_esc(det["genreLabel"])}</a>'))
    if det.get("scriptLabel"):
        rows.append(("Script", f'<a href="{_esc(cartography.href_for("script:" + det["script"]))}">{_esc(det["scriptLabel"])}</a>'))
    if det.get("languages"):
        links = " · ".join(f'<a href="{_esc(cartography.href_for("language:" + l))}">{_esc(l)}</a>' for l in det["languages"])
        rows.append(("Language", links))
    if det.get("materialLabel"):
        rows.append(("Material", f'<a href="{_esc(cartography.href_for("material:" + det["material"]))}">{_esc(det["materialLabel"])}</a>'))
    if det.get("province") or det.get("temple"):
        bits = []
        if det.get("temple"):
            bits.append(_esc(det["temple"]))
        if det.get("province"):
            bits.append(f'<a href="{_esc(cartography.href_for("province:" + det["province"]))}">{_esc(det["province"])}</a>')
        elif det.get("provenance"):
            bits.append(_esc(det["provenance"]))
        rows.append(("Held at", " · ".join(bits)))
    # What the holding temple is on paper. The register is the National Office
    # of Buddhism's own, and the match route is recorded so a doubtful one can
    # be found again — hence the title attribute rather than more body text.
    if det.get("watCode"):
        bits = []
        if det.get("watNameTh"):
            bits.append(_esc(det["watNameTh"]))
        if det.get("watFoundedCe"):
            bits.append(f'founded {det["watFoundedCe"]}')
        for key in ("watSect", "watRank"):
            if det.get(key):
                bits.append(_esc(det[key]))
        how = _esc(det.get("watMatchHow") or "")
        code = (f'<span class="watcode" title="matched: {how}">'
                f'รหัสวัด {_esc(det["watCode"])}</span>')
        rows.append(("Temple register", " · ".join(bits + [code])
                     + '<br><span class="tinynote">ทะเบียนวัด สำนักงาน'
                       'พระพุทธศาสนาแห่งชาติ · National Office of Buddhism '
                       'temple register</span>'))
    if det.get("date"):
        era = det.get("era")
        era_label = taxonomy.ERA_LABELS.get(era, era) if era else ""
        era_bit = f' <span style="color:#6d6455">({_esc(era_label)})</span>' if era_label else ""
        rows.append(("Date", _esc(det["date"]) + era_bit))
    if det.get("extentPages"):
        rows.append(("Extent", f"{det['extentPages']:,} pages"))
    return rows


def _peers(det):
    """The facet-based 'more like this' (_related, wiki.py), pointing at the peers'
    own real pages so browsing between manuscripts stays inside indexable HTML."""
    out = []
    for group in det.get("related") or []:
        items = "".join(f'<li><a href="/m/{it["id"]}/">{_esc(it["title"])}</a></li>'
                        for it in group.get("items", []))
        if items:
            out.append(f'<h3>More {_esc(group["label"])}</h3><ul>{items}</ul>')
    return "".join(out)


def _jsonld(det, url, og_image, page=None, crumb_items=None):
    """schema.org structured data — a Manuscript is a CreativeWork; giving Google
    typed fields (name, language, material, dateCreated, holdingLocation) is a real
    rich-result / discovery lever the SPA never offered."""
    ld = {"@context": "https://schema.org", "@type": ["Manuscript", "CreativeWork"],
          "name": det.get("title"), "url": url,
          "isPartOf": {"@type": "Collection", "name": "wichaa — an archive of Lanna manuscripts and living wichaa"}}
    if det.get("titleThai"):
        ld["alternateName"] = det["titleThai"]
    if det.get("languages"):
        ld["inLanguage"] = det["languages"]
    if det.get("materialLabel"):
        ld["material"] = det["materialLabel"]
    if det.get("date"):
        ld["dateCreated"] = det["date"]
    if det.get("temple") or det.get("province"):
        ld["holdingLocation"] = {"@type": "Place",
                                 "name": det.get("temple") or det.get("province")}
    if og_image:
        # a full ImageObject (caption, description, credit, copyright), not a bare
        # URL — so image search and rich results get the conscientious metadata too.
        # `page` (a described plate) makes the ImageObject carry that page's reading.
        ld["image"] = imagemeta.image_object(det, og_image, page)
    if det.get("genreLabel"):
        ld["genre"] = det["genreLabel"]
    out = [json.dumps(ld, ensure_ascii=False)]
    if crumb_items:
        # Same trail as the visible breadcrumb (wichaa › tradition › genre › this),
        # as a real BreadcrumbList — a rich-result lever the visible nav alone isn't.
        bc = {"@context": "https://schema.org", "@type": "BreadcrumbList",
              "itemListElement": [
                  {"@type": "ListItem", "position": i + 1, "name": name, "item": href}
                  for i, (name, href) in enumerate(crumb_items)]}
        out.append(json.dumps(bc, ensure_ascii=False))
    return "".join(f'<script type="application/ld+json">{s}</script>' for s in out)


def _pages_gallery(det):
    """Every digested page's original scan, for a contributed volume that has NOT
    been transcribed yet — the gap where a visitor previously found nothing at all
    (a fully-transcribed volume gets the bilingual /read/ page instead, which
    already interleaves every scan with the text, so this would just duplicate it).
    Emits the SAME '/pimg?mid=&n=&w=' query-string src reader_page() uses, so
    build_static's existing image-baking regex (_bake_reader_images) resolves these
    to real files with no new baking logic — one convention, two callers."""
    if det.get("hasReader"):
        return ""
    pages = det.get("pages") or []
    if not pages:
        return ""
    mid = det["id"]
    dia = det.get("diagramPages") or 0
    cells = []
    for p in pages:
        n = p["n"]
        is_dia = p.get("kind") == "diagram"
        title = _esc(p.get("desc") or f"Page {n}")
        cells.append(
            f'<a class="tw{" dia" if is_dia else ""}" '
            f'href="/pimg?mid={mid}&amp;n={n}&amp;w=1000" target="_blank" rel="noopener" '
            f'title="{title}">'
            f'<img src="/pimg?mid={mid}&amp;n={n}&amp;w=1000" alt="page {n}" loading="lazy">'
            f'<span class="pgnum">{"&#9670; " if is_dia else ""}{n}</span></a>')
    lead = "The full volume, page by page — every scan, rendered from the source PDF."
    if dia:
        lead += f" &#9670; marks a page the vision pass flagged as carrying a diagram or figure."
    return (f'<div class=pages><h2>Pages ({len(pages)}'
            + (f' &middot; {dia} with diagrams' if dia else '') + ')</h2>'
            f'<p class=iconolede>{lead}</p>'
            f'<div class=thumbwall>{"".join(cells)}</div></div>')


def page_html(det, wiki, base="/", path=None):
    """The manuscript's real page — self-contained, light, no SPA shim. `det` is
    manuscript_detail(mid) with `threads` already attached by build_static. `base`
    is the site URL prefix, so a bundled plate hero resolves under any prefix.
    `path` is the canonical site-relative location of THIS page (e.g.
    "m/supreme-maha-mantra-katha-6968/") — canonical/og:url must state the slug
    URL, not the numeric legacy one; defaults to the numeric path."""
    mid = det["id"]
    site = (wiki.SITE_URL or "").rstrip("/")
    path = (path or f"m/{mid}/").lstrip("/")
    url = f"{site}/{path}" if site else f"/{path}"
    title = det.get("title") or f"Manuscript #{mid}"
    title_thai = det.get("titleThai") or ""

    genre_lbl = det.get("genreLabel") or ""
    trad_lbl = taxonomy.TRADITION_LABELS.get(det.get("tradition"), det.get("tradition") or "")

    # --- breadcrumb (wichaa › tradition › genre › this) ---
    # Built as (label, href) pairs once, so the visible nav and the BreadcrumbList
    # JSON-LD (_jsonld, below) say exactly the same trail.
    crumb_items = [("wichaa", "/")]
    if det.get("tradition"):
        crumb_items.append((trad_lbl, cartography.href_for("tradition:" + det["tradition"])))
    if genre_lbl:
        crumb_items.append((genre_lbl, cartography.href_for("genre:" + det["genre"])))
    crumb_items.append((title[:60], url))
    crumb = [f'<a href="{_esc(h)}">{_esc(n)}</a>' for n, h in crumb_items[:-1]]
    crumb.append(f'<b>{_esc(crumb_items[-1][0])}</b>')
    crumb_html = f'<p class=crumb>{" &rsaquo; ".join(crumb)}</p>'
    # BreadcrumbList needs absolute URLs; site-relative hrefs get the origin prefixed.
    crumb_ld = [(n, h if h.startswith("http") else f"{site}{h}") for n, h in crumb_items]

    # --- subjects (entities named in the title) ---
    subjects = det.get("subjects") or []
    subj_html = ""
    if subjects:
        subj_html = "<div class=subj>" + "".join(
            f'<a href="{_esc(s["href"])}">{_esc(s["label"])}</a>' for s in subjects) + "</div>"

    # --- hero image / honest no-image note ---
    hero = _hero(det, wiki, base)
    if hero:
        img_url, _alt0, _credit0, hero_page = hero
        # conscientious, descriptive: a faithful alt sentence — a vision reading of
        # the actual plate where the hero IS a described page, else composed from
        # facts — and an honest credit, all from imagemeta so the page, the sitemap,
        # and the JSON-LD say the same true thing.
        alt = imagemeta.hero_alt(det, hero_page)
        credit = imagemeta.credit_line(det)
        hero_html = (f'<img class=hero src="{_esc(img_url)}" alt="{_esc(alt)}" loading="lazy">'
                     f'<p class=cred>{_esc(credit)}</p>')
        og_image = img_url
    else:
        hero_page = None
        src_url, src_label = _source_link(det)
        note = ("No image is catalogued here yet — this record is metadata only."
                + (f' <a href="{_esc(src_url)}" target=_blank rel=noopener>{_esc(src_label)}</a> holds the images.'
                   if src_url else ""))
        hero_html = f'<div class=noimg>{note}</div>'
        og_image = None

    meta_html = "<dl class=meta>" + "".join(
        f"<dt>{_esc(k)}</dt><dd>{v}</dd>" for k, v in _meta_rows(det)) + "</dl>"

    # --- read / sponsor ---
    if det.get("hasReader"):
        read_html = ('<div class=read>This volume is transcribed and translated. '
                     f'<a href="/read/{mid}/">Read the bilingual text →</a></div>')
    elif det.get("extentPages") or det.get("pageCount"):
        pages = det.get("extentPages") or det.get("pageCount") or 0
        # Small volumes cost under a dollar — int() showed "About $0", which
        # reads as either broken or a lie. Under $5, say the cents.
        cost = pages * 0.06
        cost_txt = f"${cost:,.2f}" if cost < 5 else f"${int(cost):,}"
        read_html = (f'<div class=read>{pages:,} pages, not yet transcribed. '
                     f'About {cost_txt} would have the bots read the whole '
                     f'volume, at $0.06 a page. '
                     f'<a href="{KOFI}" target=_blank rel=noopener>☕ Sponsor it being read →</a></div>')
    else:
        read_html = ""

    # The rare, rich vision readings surfaced as content — the iconography of the
    # illustrated pages, in the tradition's own terms (yant, unalome, Khom…),
    # with the caption transcribed. Empty for the vast majority of manuscripts.
    described = imagemeta.described_pages(det)
    if described:
        rows = "".join(
            f'<li><b>Folio {_esc(p["n"])}'
            + (f' · {_esc(p["kind"])}' if p.get("kind") else "")
            + f'</b> — {_esc(p["text"])} '
            f'<a href="/m?id={mid}#pages">see the page →</a></li>'
            for p in described)
        icon_html = ('<div class=icono><h2>What is drawn on these pages</h2>'
                     '<p class=iconolede>Readings of the illustrated pages, in the '
                     "tradition's own vocabulary. Described by a vision pass; the "
                     'quoted captions are transcribed from the page itself.</p>'
                     f'<ul>{rows}</ul></div>')
    else:
        icon_html = ""

    pages_html = _pages_gallery(det)
    threads_html = strings.threads_section(det.get("threads") or [])

    tool_html = (f'<div class=tool><a href="/m?id={mid}">Open the interactive viewer →</a>'
                 '<p>Page images, OCR, and your own notes on this manuscript.</p></div>')

    peers = _peers(det)
    peers_html = f'<div class=peers>{peers}</div>' if peers else ""

    su = _esc(url)
    share_html = (
        '<div class=share>Share this manuscript &nbsp;'
        f'<a target=_blank rel=noopener href="https://social-plugins.line.me/lineit/share?url={su}">LINE</a>'
        f'<a target=_blank rel=noopener href="https://www.facebook.com/sharer/sharer.php?u={su}">Facebook</a>'
        f'<a target=_blank rel=noopener href="https://t.me/share/url?url={su}">Telegram</a>'
        '</div>')

    foot_html = ('<div class=foot><a href="/browse">← All manuscripts</a> &nbsp;·&nbsp; '
                 '<a href="/atlas">The Atlas</a> &nbsp;·&nbsp; '
                 '<a href="/">wichaa — an open archive of Lanna manuscripts and living wichaa</a></div>')

    # --- description for meta + unfurl ---
    desc_bits = [b for b in (title, genre_lbl, det.get("province"), det.get("date")) if b]
    description = " — ".join(desc_bits) or f"Manuscript #{mid} in the wichaa archive."
    description = description[:300]

    # og:image must be ABSOLUTE for unfurlers (FB/LINE won't resolve a relative one).
    # IIIF heroes are already absolute (https://…); a bundled plate hero is a
    # site-relative path (/pimg/…) that needs the origin prefixed.
    if og_image and og_image.startswith("/") and site:
        ogimg = f"{site}{og_image}"
    else:
        ogimg = og_image or (f"{site}/og.jpg" if site else "/og.jpg")

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
        + _jsonld(det, url, og_image, hero_page, crumb_ld)
        + f"<style>{_CSS}</style></head>")

    top = ('<div class=top><a class=mark href="/">วิชา · wichaa</a>'
           '<nav><a href="/browse">Browse</a> <a href="/atlas">Atlas</a> '
           '<a href="/trails">Trails</a> <a href="/support">☕ Support</a></nav></div>')

    body = (
        "<body>" + top + '<div class=wrap>'
        + crumb_html
        + f"<h1>{_esc(title[:90])}</h1>"
        + (f'<p class=th>{_esc(title_thai)}</p>' if title_thai else "")
        + subj_html + hero_html + meta_html + read_html
        + icon_html + pages_html + threads_html + tool_html + peers_html + share_html + foot_html
        + "</div></body></html>")

    return head + body
