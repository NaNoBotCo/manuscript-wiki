#!/usr/bin/env python3
"""build_place_pages.py — one real HTML page per place, so a shared link unfurls.

    python3 build_place_pages.py --docs ../nanobotco-lanna/docs --site-url https://wichaa.net

WHY THIS EXISTS
The map shares links like /wats/#place=wat-chedi-luang. A URL fragment is never
sent to the server, so Facebook, X, LINE and every other unfurler sees only the
generic site card — no temple name, no photograph. The only fix is a real URL per
place carrying its own Open Graph tags. That is what this writes.

URL SHAPE
    /place/<id>/            — kind-neutral on purpose.
Not /wats/<id>/: sacred sites are not wats, and hard-coding a parent category
into the URL would make any later re-grouping a breaking change. A place is a
place; what KIND it is stays data (see `facets` below), which is also what lets a
future taxonomy re-derive groupings without rewriting URLs or breaking links.

MACHINE LEGIBILITY
Each page also gets api/place/<id>.json with the same record plus an explicit
`facets` block, and every page is appended to api/pages.json so the sitemap picks
it up without anyone maintaining a list.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)


def clip(s, n):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"


def facets_of(p, kind, article=None):
    """Explicit, multi-valued facets — the shape a later taxonomy can consume
    directly instead of re-parsing prose. Values are omitted when unknown rather
    than filled with a guess."""
    f = {"kind": [kind]}
    if p.get("province"):
        f["province"] = [p["province"]]
    if p.get("district"):
        f["district"] = [p["district"]]
    if p.get("heritage"):
        f["designation"] = [p["heritage"]]
    if p.get("siteType"):
        f["siteType"] = [t.strip() for t in str(p["siteType"]).split(";") if t.strip()]
    if p.get("founded"):
        f["founded"] = [str(p["founded"])]
    f["hasPhotograph"] = [bool(p.get("photos"))]
    kinds = sorted({sec.get("kind") for lang in (article or {}).values()
                    for sec in (lang.get("sections") or []) if sec.get("kind")}) if article else []
    if kinds:
        f["describes"] = kinds          # architecture / history / interest / heritage
    if article:
        f["articleLanguages"] = sorted(article.keys())
    f["confidence"] = [p.get("confidence") or "crawled"]
    return f


def page_html(p, kind, site, back, article=None):
    name = p.get("nameRoman") or p.get("name") or p.get("id")
    thai = p.get("name") if p.get("name") and p.get("name") != p.get("nameRoman") else None
    ph = (p.get("photos") or [{}])[0] or {}
    sm = p.get("summary") or None
    lat, lng = p.get("lat"), p.get("lng")
    ll = f"{lat},{lng}"
    url = f"{site}/place/{p['id']}/"

    # The unfurl description: real prose when we have it, otherwise the facts we
    # do have — never an invented sentence.
    if sm and sm.get("text"):
        desc = clip(sm["text"], 300)
    elif p.get("description"):
        desc = clip(p["description"], 300)
    else:
        bits = [b for b in [p.get("heritage") and "Registered Thai historic site",
                            p.get("province") and f"{p['province']} province", "Thailand"] if b]
        desc = clip((thai + " — " if thai else "") + ", ".join(bits), 300)

    og_img = ph.get("thumb") or ""
    jsonld = {
        "@context": "https://schema.org", "@type": "Place", "name": name,
        "url": url, "description": desc,
        "geo": {"@type": "GeoCoordinates", "latitude": lat, "longitude": lng},
    }
    if thai:
        jsonld["alternateName"] = thai
    if og_img:
        jsonld["image"] = og_img
    if p.get("province"):
        jsonld["address"] = {"@type": "PostalAddress", "addressRegion": p["province"],
                             "addressCountry": "TH"}
    if p.get("phone"):
        jsonld["telephone"] = p["phone"]
    if p.get("website"):
        jsonld["sameAs"] = [p["website"]]
    if p.get("openingHours"):
        jsonld["openingHours"] = p["openingHours"]

    h = []
    h.append("<!doctype html><html lang=en><head><meta charset=utf-8>")
    h.append('<meta name=viewport content="width=device-width,initial-scale=1">')
    h.append(f"<title>{E(name)} — wichaa</title>")
    h.append(f'<meta name=description content="{E(desc)}">')
    h.append('<meta property="og:type" content="place">')
    h.append(f'<meta property="og:title" content="{E(name)}">')
    h.append(f'<meta property="og:description" content="{E(desc)}">')
    h.append(f'<meta property="og:url" content="{E(url)}">')
    h.append('<meta property="og:site_name" content="wichaa">')
    if og_img:
        h.append(f'<meta property="og:image" content="{E(og_img)}">')
        h.append(f'<meta property="og:image:alt" content="{E(name)}">')
        h.append('<meta name="twitter:card" content="summary_large_image">')
    else:
        h.append('<meta name="twitter:card" content="summary">')
    h.append(f'<meta name="twitter:title" content="{E(name)}">')
    h.append(f'<meta name="twitter:description" content="{E(desc)}">')
    if lat is not None:
        h.append(f'<meta name="geo.position" content="{lat};{lng}"><meta name="ICBM" content="{lat}, {lng}">')
    h.append(f'<link rel=canonical href="{E(url)}">')
    h.append('<script type="application/ld+json">' + json.dumps(jsonld, ensure_ascii=False) + "</script>")
    h.append("""<style>
:root{--ink:#1b1f1e;--muted:#5d6b68;--line:#e2e0d8;--teal:#2f6f68;--gold:#d4a017}
*{box-sizing:border-box}body{margin:0;background:#f7f6f1;color:var(--ink);
font:17px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans Thai",sans-serif}
.wrap{max-width:680px;margin:0 auto;padding:22px 18px 80px}
a{color:var(--teal)}
.card{background:#fff;border:1px solid var(--line);border-radius:16px;overflow:hidden}
.card img.hero{display:block;width:100%;max-height:340px;object-fit:cover;background:#eee}
.cred{font-size:11.5px;color:var(--muted);padding:7px 18px 0;line-height:1.45}
.bd{padding:16px 18px 20px}
h1{font-size:26px;margin:0;line-height:1.22}.th{color:var(--muted);font-size:18px;margin-top:3px}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:11px}
.tag{font-size:12px;font-weight:700;border:1px solid var(--line);border-radius:7px;padding:3px 9px;color:var(--muted)}
.tag.gold{background:var(--gold);color:#3a2c07;border-color:var(--gold)}
.tag.teal{background:var(--teal);color:#fff;border-color:var(--teal)}
.sec{margin-top:16px;padding-top:14px;border-top:1px solid var(--line)}
.sec h2{font-size:12px;letter-spacing:.6px;text-transform:uppercase;color:var(--muted);margin:0 0 7px}
dl{display:grid;grid-template-columns:110px 1fr;gap:6px 12px;margin:0;font-size:15px}
dt{color:var(--muted)}dd{margin:0}
.btns{display:flex;flex-wrap:wrap;gap:8px}
.btn{display:inline-flex;align-items:center;min-height:40px;padding:8px 14px;border:1px solid var(--line);
background:#fff;border-radius:999px;font-size:13.5px;font-weight:700;text-decoration:none;color:var(--ink)}
.btn.primary{background:var(--teal);color:#fff;border-color:var(--teal)}
.btn.kofi{background:#fbf1dc;color:#8a5a00;border-color:transparent}
.lic{font-size:12px;color:var(--muted);line-height:1.6;background:#faf9f5;border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.from{font-size:11.5px;color:var(--muted);margin-top:6px}
.home{font-size:13.5px;margin-bottom:14px}
</style></head><body><div class=wrap>""")
    h.append(f'<div class=home><a href="{E(back)}">← the whole map</a></div>')
    h.append("<div class=card>")
    if og_img:
        h.append(f'<img class=hero src="{E(og_img)}" alt="{E(name)}">')
        lic = (f'<a href="{E(ph.get("licenseUrl"))}" target=_blank rel=noopener>{E(ph.get("license"))}</a>'
               if ph.get("licenseUrl") else E(ph.get("license")))
        pd = " <b>(public domain)</b>" if ph.get("publicDomain") else ""
        h.append(f'<div class=cred>{E(ph.get("author"))} · {lic}{pd} · '
                 f'<a href="{E(ph.get("source"))}" target=_blank rel=noopener>Wikimedia Commons</a></div>')
    h.append("<div class=bd>")
    h.append(f"<h1>{E(name)}</h1>")
    if thai:
        h.append(f'<div class=th>{E(thai)}</div>')
    h.append("<div class=tags>")
    if p.get("siteType"):
        h.append(f'<span class="tag teal">{E(str(p["siteType"]).split(";")[0])}</span>')
    if p.get("heritage"):
        h.append(f'<span class="tag gold">★ {E(p["heritage"])}</span>')
    h.append(f'<span class=tag>{"field-verified" if p.get("confidence")=="verified" else "compiled · unvisited"}</span></div>')

    if sm and sm.get("text"):
        h.append(f'<div class=sec><h2>About</h2><div>{E(sm["text"])}</div>'
                 f'<div class=from>From <a href="{E(sm["url"])}" target=_blank rel=noopener>{E(sm["title"])}</a>'
                 f' on Wikipedia · <a href="{E(sm["licenseUrl"])}" target=_blank rel=noopener>{E(sm["license"])}</a>'
                 f' — reused here under that licence.</div></div>')
    elif p.get("description"):
        h.append(f'<div class=sec><h2>About</h2><div>{E(p["description"])}</div>'
                 f'<div class=from>Wikidata description · CC0 (public domain dedication)</div></div>')

    h.append("<div class=sec><h2>Details</h2><dl>")
    if p.get("founded"):
        h.append(f"<dt>Founded</dt><dd>{E(p['founded'])}</dd>")
    if p.get("province"):
        d = f" · {E(p['district'])}" if p.get("district") else ""
        h.append(f"<dt>Province</dt><dd>{E(p['province'])}{d}</dd>")
    if p.get("openingHours"):
        h.append(f"<dt>Hours</dt><dd>{E(p['openingHours'])}</dd>")
    if p.get("phone"):
        h.append(f"<dt>Phone</dt><dd>{E(p['phone'])}</dd>")
    if p.get("website"):
        h.append(f'<dt>Website</dt><dd><a href="{E(p["website"])}" target=_blank rel=noopener>{E(clip(re.sub(r"^https?://","",p["website"]),44))}</a></dd>')
    h.append(f"<dt>Coordinates</dt><dd>{lat:.5f}, {lng:.5f}</dd>")
    srcs = []
    for sc in p.get("sources") or []:
        if sc.get("type") == "osm" and sc.get("ref"):
            srcs.append(f'<a href="https://www.openstreetmap.org/{E(sc["ref"])}" target=_blank rel=noopener>OpenStreetMap</a>')
        elif sc.get("type") == "wikidata" and sc.get("ref"):
            srcs.append(f'<a href="https://www.wikidata.org/wiki/{E(sc["ref"])}" target=_blank rel=noopener>Wikidata</a>')
    if srcs:
        h.append("<dt>Sources</dt><dd>" + " · ".join(dict.fromkeys(srcs)) + "</dd>")
    h.append("</dl></div>")

    # Full article, both languages. Thai first when present — this is a Thai
    # subject and the Thai articles are consistently the fuller ones. Each
    # language block carries its own attribution because CC BY-SA attaches to
    # that text, not to the page.
    LANGNAME = {"th": "ภาษาไทย (Thai)", "en": "English"}
    KIND = {"architecture": "Architecture", "history": "History",
            "interest": "Of interest", "heritage": "Heritage listing"}
    for lang in ("th", "en"):
        a = (article or {}).get(lang)
        if not a or not a.get("sections"):
            continue
        h.append(f'<div class=sec><h2>In depth · {E(LANGNAME[lang])}</h2>')
        budget = 7000
        for sec in a["sections"]:
            if budget <= 0:
                break
            body = sec.get("text") or ""
            if len(body) > budget:
                body = body[:budget].rsplit(" ", 1)[0] + "…"
            budget -= len(body)
            k = KIND.get(sec.get("kind"))
            head = sec.get("heading") or ""
            label = E(head)
            # Only tag when the classification adds something the heading doesn't
            # already say — otherwise you get "History History".
            show_tag = k and k.lower() not in head.lower()
            tag = f' <span class=tag style="font-weight:700">{E(k)}</span>' if show_tag else ""
            h.append(f'<h3 style="font-size:15px;margin:14px 0 4px">{label}{tag}</h3>')
            for para in [x for x in body.split("\n") if x.strip()]:
                h.append(f'<p style="margin:0 0 8px">{E(para)}</p>')
        h.append(f'<div class=from>From <a href="{E(a["url"])}" target=_blank rel=noopener>{E(a["title"])}</a>'
                 f' on Wikipedia · <a href="{E(a["licenseUrl"])}" target=_blank rel=noopener>{E(a["license"])}</a>'
                 f' — reused here under that licence.</div></div>')

    rest = (p.get("photos") or [])[1:]
    if rest:
        h.append(f'<div class=sec><h2>More photographs ({len(rest)+1})</h2>')
        for m in rest:
            lic2 = (f'<a href="{E(m.get("licenseUrl"))}" target=_blank rel=noopener>{E(m.get("license"))}</a>'
                    if m.get("licenseUrl") else E(m.get("license")))
            pd2 = " <b>(public domain)</b>" if m.get("publicDomain") else ""
            h.append(f'<img src="{E(m.get("thumb"))}" alt="{E(name)}" '
                     f'style="width:100%;border-radius:10px;margin-top:10px;display:block">'
                     f'<div class=cred style="padding:5px 0 0">{E(m.get("author"))} · {lic2}{pd2} · '
                     f'<a href="{E(m.get("source"))}" target=_blank rel=noopener>Wikimedia Commons</a></div>')
        h.append('</div>')

    h.append('<div class=sec><h2>Get there</h2><div class=btns>'
             f'<a class="btn primary" target=_blank rel=noopener href="https://www.google.com/maps/dir/?api=1&destination={ll}">Google Maps</a>'
             f'<a class=btn target=_blank rel=noopener href="https://maps.apple.com/?daddr={ll}">Apple Maps</a>'
             f'<a class=btn target=_blank rel=noopener href="https://www.openstreetmap.org/directions?to={ll}">OpenStreetMap</a>'
             f'<a class=btn href="{E(back)}">Show on the map</a></div></div>')

    su = E(url)
    h.append('<div class=sec><h2>Share</h2><div class=btns>'
             f'<a class=btn target=_blank rel=noopener href="https://www.facebook.com/sharer/sharer.php?u={su}">Facebook</a>'
             f'<a class=btn target=_blank rel=noopener href="https://social-plugins.line.me/lineit/share?url={su}">LINE</a>'
             f'<a class=btn target=_blank rel=noopener href="https://t.me/share/url?url={su}">Telegram</a>'
             '</div></div>')

    parts = ['<b>Location data</b> — from OpenStreetMap, <a href="https://opendatacommons.org/licenses/odbl/1-0/" target=_blank rel=noopener>ODbL 1.0</a> (share-alike).',
             '<b>Facts</b> — Wikidata, <a href="https://creativecommons.org/publicdomain/zero/1.0/" target=_blank rel=noopener>CC0</a>.']
    if sm and sm.get("text"):
        parts.append(f'<b>Description</b> — Wikipedia, {E(sm["license"])}, attributed above.')
    if og_img:
        parts.append(f'<b>Photograph</b> — {E(ph.get("author"))}, {E(ph.get("license"))}, via Wikimedia Commons; not relicensed here.')
    h.append('<div class=sec><h2>Licence</h2><div class=lic>' + "<br>".join(parts) +
             "<br>Everything here is public domain or an open/Creative Commons licence, named above.</div></div>")

    h.append('<div class=sec><div class=btns><a class="btn kofi" target=_blank rel=noopener '
             'href="https://ko-fi.com/defiantchiangmai">&#9749; Support this work</a></div></div>')
    h.append("</div></div></div></body></html>")
    return "".join(h)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--docs", required=True)
    ap.add_argument("--site-url", default="https://wichaa.net")
    ap.add_argument("--data", default=str(HERE / "data" / "wats.geojson"))
    ap.add_argument("--detail", default=str(HERE / "data" / "wats-detail.json"))
    args = ap.parse_args()

    src = Path(args.data)
    if not src.exists():
        print(f"ERROR: {src} not found — run sync_wats.py first", file=sys.stderr)
        return 1
    d = json.loads(src.read_text(encoding="utf-8"))
    dpath = Path(args.detail)
    detail = json.loads(dpath.read_text(encoding="utf-8")) if dpath.exists() else {}
    site = args.site_url.rstrip("/")
    docs = Path(args.docs).resolve()
    out = docs / "place"
    out.mkdir(parents=True, exist_ok=True)
    api = docs / "api" / "place"
    api.mkdir(parents=True, exist_ok=True)

    records = [(w, "wat") for w in d.get("wats", [])] + [(x, "sacred") for x in d.get("sacred", [])]
    manifest, n_img = [], 0
    for p, kind in records:
        pid = p.get("id")
        if not pid or p.get("lat") is None:
            continue
        back = f"{site}/wats/#place={pid}"
        (out / pid).mkdir(parents=True, exist_ok=True)
        det = detail.get(pid) or {}
        art = det.get("article") or {}
        # the map payload was trimmed to two photographs; restore the full set here
        if det.get("photos"):
            p = dict(p)
            p["photos"] = det["photos"]
        (out / pid / "index.html").write_text(page_html(p, kind, site, back, art), encoding="utf-8")
        rec = dict(p)
        if art:
            rec["article"] = art
        rec["kind"] = kind
        rec["facets"] = facets_of(p, kind, art)
        rec["url"] = f"{site}/place/{pid}/"
        (api / f"{pid}.json").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        if (p.get("photos") or []):
            n_img += 1
        manifest.append({"route": f"place/{pid}/", "label": p.get("nameRoman") or p.get("name") or pid,
                         "kind": "entity"})

    # append to the shared page manifest so the sitemap finds these without
    # anyone maintaining a second list
    pj = docs / "api" / "pages.json"
    try:
        cur = json.loads(pj.read_text(encoding="utf-8"))
    except Exception:
        cur = {"pages": []}
    keep = [e for e in cur.get("pages", []) if not str(e.get("route", "")).startswith("place/")]
    pj.write_text(json.dumps({"pages": keep + manifest}, ensure_ascii=False), encoding="utf-8")

    print(f"place pages: {len(manifest)} written to place/ ({n_img} with an og:image) "
          f"· api/place/*.json · registered in api/pages.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
