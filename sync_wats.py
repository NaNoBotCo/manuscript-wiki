#!/usr/bin/env python3
"""sync_wats.py — pull the Chiang Mai wat catalogue into the wiki's data folder.

The wats are compiled in a separate project (mueang-map): OSM + Wikidata point
data, enriched with heritage flags and freely-licensed Wikimedia Commons photos.
This copies a TRIMMED snapshot into data/wats.geojson, which wiki.py reads.

Trimming matters: the source carries up to 6 photos per temple with full EXIF-ish
metadata, which would push the published /api/wats.json past a megabyte for no
reader benefit. We keep at most 3 photos and only the fields the page renders —
but never drop author/licence/source, because those are the attribution and are
not optional.

    python3 sync_wats.py

Licensing carried through to the page: point data is OSM-derived and therefore
ODbL 1.0 SHARE-ALIKE (not the site's CC-BY), Wikidata facts are CC0, and each
photograph keeps its own Commons licence.
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(os.environ.get(
    "WATS_GEOJSON",
    HERE.parent / "mueang-map" / "dist" / "data" / "wat.geojson"))
# Notable spiritual places that are NOT wats — city pillars, the sunken Lanna
# cities, sacred and prehistoric caves, mosques, churches, monumental Buddha
# images. Kept as a SEPARATE list so they can never inflate the temple count.
SACRED = Path(os.environ.get(
    "SACRED_GEOJSON",
    HERE.parent / "mueang-map" / "dist" / "data" / "sacred.geojson"))
DEST = HERE / "data" / "wats.geojson"
# Full sectioned Wikipedia articles live in their OWN file. Inlining them
# would push the map payload from ~1.4 MB to several megabytes, and almost
# nobody needs 14 k characters about a temple until they open it — the place
# page and the modal fetch this on demand.
DETAIL = HERE / "data" / "wats-detail.json"   # full photos + full articles, per id
# Photographs are split like the articles: the map payload carries a couple so a
# card has something to show, and the rest arrive with the per-place JSON when a
# modal actually opens. Six photos × 1,307 temples is most of a megabyte spent
# before anyone has clicked anything.
MAP_PHOTOS = 2      # inlined in wats.geojson (the map payload)
MAX_PHOTOS = 6      # kept in full in wats-detail.json / api/place/<id>.json

SUMMARY_KEYS = ("text", "title", "url", "lang", "license", "licenseUrl")


def _slim(summary):
    """Lead paragraph + attribution only — never the full section list."""
    if not summary:
        return None
    return {k: summary.get(k) for k in SUMMARY_KEYS if summary.get(k)}


def main():
    if not SRC.exists():
        print(f"ERROR: no wat catalogue at {SRC}\n"
              f"Build it first:  cd ../mueang-map && node build.mjs", file=sys.stderr)
        return 1
    geo = json.loads(SRC.read_text(encoding="utf-8"))
    feats = geo.get("features", [])
    out, n_photos, n_heritage = [], 0, 0

    for f in feats:
        p = f.get("properties", {}) or {}
        a = p.get("attrs", {}) or {}
        lng, lat = f["geometry"]["coordinates"][:2]
        photos = []
        for m in (p.get("media") or []):
            if m.get("type") != "image" or not m.get("thumb"):
                continue
            photos.append({
                "thumb": m["thumb"],
                "author": m.get("author") or "Unknown",
                "license": m.get("license") or "",
                "licenseUrl": m.get("licenseUrl") or "",
                "source": m.get("source") or "",
            })
            if len(photos) >= MAX_PHOTOS:
                break
        heritage = a.get("heritage") or ""
        if heritage:
            n_heritage += 1
        n_photos += len(photos)
        out.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "nameRoman": p.get("nameRoman"),
            "lat": round(float(lat), 6), "lng": round(float(lng), 6),
            "heritage": heritage,
            "status": a.get("status") or "",
            "founded": a.get("founded") or "",
            # one-line Wikidata gloss (CC0) and the Wikipedia intro (CC BY-SA);
            # the summary object carries its own title/url/licence so the page can
            # attribute the specific paragraph, which share-alike requires.
            "description": a.get("description") or "",
            # Only the LEAD and its attribution ride in the map payload. The
            # harvester now attaches full `sections` to this object too, and
            # copying those here silently doubled /api/wats.json (1.4 → 2.6 MB)
            # for text nobody reads until they open a modal.
            "summary": _slim(a.get("summary")),
            "province": a.get("province") or "", "district": a.get("district") or "",
            "street": a.get("street") or "",
            "phone": a.get("phone") or "", "website": a.get("website") or "",
            "email": a.get("email") or "", "facebook": a.get("facebook") or "",
            "openingHours": a.get("openingHours") or "",
            "confidence": p.get("confidence") or "crawled",
            "photos": photos,
            # provenance, so a reader can trace any single record back
            "sources": [{"type": s.get("type"), "ref": s.get("ref")}
                        for s in (p.get("sources") or [])],
        })

    # heritage first, then alphabetical — the same ordering the map uses
    out.sort(key=lambda w: (0 if w["heritage"] else 1, (w["nameRoman"] or w["name"] or "")))

    # split the deep text out of the map payload
    detail, n_sec, n_arch = {}, 0, 0
    for f in json.loads(SRC.read_text(encoding="utf-8")).get("features", []):
        pr = f.get("properties", {}) or {}
        art = (pr.get("attrs") or {}).get("article")
        if not art or not pr.get("id"):
            continue
        keep = {}
        for lang in ("th", "en"):
            a = art.get(lang)
            if not a or not (a.get("sections") or a.get("text")):
                continue
            keep[lang] = a
            n_sec += len(a.get("sections") or [])
            if any(x.get("kind") == "architecture" for x in (a.get("sections") or [])):
                n_arch += 1
        if keep:
            detail.setdefault(pr["id"], {})["article"] = keep


    sacred, s_photos = [], 0
    if SACRED.exists():
        for f in json.loads(SACRED.read_text(encoding="utf-8")).get("features", []):
            p = f.get("properties", {}) or {}
            a = p.get("attrs", {}) or {}
            lng, lat = f["geometry"]["coordinates"][:2]
            photos = []
            for m in (p.get("media") or []):
                if m.get("type") != "image" or not m.get("thumb"):
                    continue
                photos.append({"thumb": m["thumb"], "author": m.get("author") or "Unknown",
                               "license": m.get("license") or "", "licenseUrl": m.get("licenseUrl") or "",
                               "source": m.get("source") or "",
                               "publicDomain": bool(m.get("publicDomain"))})
                if len(photos) >= MAX_PHOTOS:
                    break
            s_photos += len(photos)
            sacred.append({
                "id": p.get("id"), "name": p.get("name"), "nameRoman": p.get("nameRoman"),
                "lat": round(float(lat), 6), "lng": round(float(lng), 6),
                "siteType": a.get("siteType") or "", "heritage": a.get("heritage") or "",
                "description": a.get("description") or "", "summary": _slim(a.get("summary")),
                "confidence": p.get("confidence") or "crawled", "photos": photos,
                "sources": [{"type": s.get("type"), "ref": s.get("ref")} for s in (p.get("sources") or [])],
            })
        # photographed first — a sacred site you can actually see reads better
        sacred.sort(key=lambda x: (0 if x["photos"] else 1, x["nameRoman"] or x["name"] or ""))
    DEST.parent.mkdir(parents=True, exist_ok=True)
    # full photo lists (the map payload keeps only the first MAP_PHOTOS)
    # The detail file holds the COMPLETE photo list, not just the overflow past
    # MAP_PHOTOS. Storing only the remainder made detail a diff against the map
    # payload, so anything with two photos or fewer existed *only* in the payload
    # — and a compiler regenerating that payload from the vault could not see
    # them at all (53 records, 68 photographs). Detail is the whole record; the
    # map payload is a trimmed view of it.
    for rec in list(out) + list(sacred):
        if rec["photos"]:
            detail.setdefault(rec["id"], {})["photos"] = rec["photos"]
        rec["photoCount"] = len(rec["photos"])
        rec["photos"] = rec["photos"][:MAP_PHOTOS]

    DEST.write_text(json.dumps({
        "wats": out,
        "sacred": sacred,
        "sacredTotal": len(sacred),
        "sacredPhotos": s_photos,
        "total": len(out),
        "heritage": n_heritage,
        "photos": n_photos,
        "withPhotos": sum(1 for w in out if w["photos"]),
        # tells the page to render the offline-app block (built by build_wats_app.py)
        "download": True,
        "attribution": {
            "data": "© OpenStreetMap contributors, ODbL 1.0 (share-alike)",
            "dataUrl": "https://opendatacommons.org/licenses/odbl/1-0/",
            "facts": "Wikidata, CC0",
            "photos": "Wikimedia Commons — each image credited to its author under its own licence",
        },
    }, ensure_ascii=False), encoding="utf-8")
    DETAIL.write_text(json.dumps(detail, ensure_ascii=False), encoding="utf-8")
    akb = DETAIL.stat().st_size / 1024
    n_extra = sum(1 for v in detail.values() if v.get("photos"))
    print(f"→ {DETAIL.relative_to(HERE)}  {len(detail)} records "
          f"({n_sec} sections, {n_arch} with architecture; {n_extra} with extra photos) · {akb:.0f} KB")
    kb = DEST.stat().st_size / 1024
    print(f"→ {DEST.relative_to(HERE)}  {len(out)} wats + {len(sacred)} sacred sites "
          f"({n_heritage} heritage, {n_photos + s_photos} photos) · {kb:.0f} KB")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
