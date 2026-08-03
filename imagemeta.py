#!/usr/bin/env python3
"""imagemeta — conscientious, descriptive metadata for every image.

We hold far more about each image than we say: the manuscript's title (in Thai,
transliteration, and English), its genre in emic terms, the script it is written
in, its language, its material, the temple that kept it, its date and calendar
era, the wichaa subjects it names — and, for the pages a vision pass has read, a
careful iconographic description in the tradition's own vocabulary (yant,
unalome, Khom, the transcribed caption). This module composes that into the
metadata a person and a search engine actually see: alt text, captions, credit,
and schema.org — from ONE place, so every surface says the same true thing.

TWO PRINCIPLES, both load-bearing:
  1. Faithful, never invented (extract-don't-author). When a vision description
     exists, THAT is the description — it is a reading of the actual page. When
     none does, we describe only what the catalogue KNOWS (a palm-leaf folio of
     such-and-such manuscript, in such-and-such script), never what the image
     might contain. We say "not yet described" rather than guess.
  2. Credit and rights, always. Most folio images are served from the holding
     library via IIIF and are NOT ours; every image states where it comes from
     and under what terms. This is the "images stay with the libraries" ethic
     written into the metadata itself.

Stdlib only. Works from a manuscript_detail() dict (`det`), so the composed
strings match the site and the JSON without a second query.
"""
from __future__ import annotations


def _clean(s) -> str:
    return " ".join(str(s or "").split())


def _short(label: str) -> str:
    """The English/plain head of a bilingual '<Thai> · <English>' label."""
    if not label:
        return ""
    # our labels put the emic term first, English after '·' — for a running
    # sentence we want the readable head, but keep the whole where it's short.
    return _clean(label)


def _material_word(det) -> str:
    m = (det.get("materialFamily") or det.get("materialLabel") or "").lower()
    if "palm" in m:
        return "palm-leaf"
    if "paper" in m or "khoi" in m or "mulberry" in m:
        return "paper"
    return ""


def object_phrase(det) -> str:
    """A faithful noun phrase for the manuscript AS a physical object, built only
    from catalogue facts: 'a palm-leaf Buddhist-canonical manuscript in Tham
    Lanna script'. Empty parts drop out cleanly."""
    mat = _material_word(det)
    # our labels are 'English · Thai'; a running English sentence reads best with
    # the English head, but the emic Thai term is worth keeping in parentheses.
    gl = [x.strip() for x in _short(det.get("genreLabel") or "").split("·")]
    if len(gl) >= 2 and gl[0] and gl[1]:
        genre_head = f"{gl[0]} ({gl[1]})"
    else:
        genre_head = gl[0] if gl else ""
    base = "manuscript"
    lead = f"a {mat} {base}".strip() if mat else f"a {base}"
    if genre_head and genre_head.split(" ")[0].lower() not in ("other", "undetermined", ""):
        lead = f"a {mat + ' ' if mat else ''}{genre_head} {base}"
    script_head = _short(det.get("scriptLabel") or "").split("·")[0].strip()
    if script_head and script_head.lower() != "none":
        lead += f" in {script_head} script"
    return lead


def _provenance_clause(det) -> str:
    temple = _clean(det.get("temple"))
    prov = _clean(det.get("province"))
    if temple and prov:
        return f"held at {temple}, {prov}"
    if temple:
        return f"held at {temple}"
    if prov:
        return f"from {prov}"
    return ""


def _date_clause(det) -> str:
    # the catalogue's date string already carries its calendar era —
    # e.g. "1168 (Cunlasakkalat (CS))" — so don't append it again.
    date = _clean(det.get("date"))
    if not date or date in ("?", "Undated"):
        return ""
    return f"dated {date}"


def hero_alt(det, page=None) -> str:
    """Alt text for a manuscript's representative image — concise but true, for a
    screen reader and for search. A vision description, where present, IS the
    alt (it reads the actual page). Otherwise a faithful sentence from facts."""
    vd = _clean((page or {}).get("descFull") or (page or {}).get("desc"))
    if vd:
        return vd[:500]
    title = _clean(det.get("title") or f"manuscript #{det.get('id')}")
    obj = object_phrase(det)
    tail = "; ".join(c for c in (_provenance_clause(det), _date_clause(det)) if c)
    seq = (page or {}).get("n")
    leaf = f"Folio {seq}: " if seq else ""
    s = f"{leaf}a page of {title}, {obj}"
    if tail:
        s += f", {tail}"
    return _clean(s)


def caption(det, page=None) -> str:
    """The visible caption under an image. Prefers the vision reading (the rich
    content), else names the folio and its manuscript plainly."""
    vd = _clean((page or {}).get("descFull") or (page or {}).get("desc"))
    if vd:
        return vd
    seq = (page or {}).get("n")
    title = _clean(det.get("title"))
    return f"Folio {seq} of {title}" if seq else f"A folio of {title}"


def credit_line(det, image=None) -> str:
    """Where the image comes from and under what terms — stated on every image.
    Folio scans are served from the holding library and their rights remain
    there; this is the ethic made explicit, not decoration."""
    src = _clean(det.get("source"))
    manifest = det.get("iiifManifestUrl")
    if manifest:
        who = src or "the holding library"
        return (f"Digitised by {who}; served via the IIIF Image API. "
                f"Image rights remain with the holding library.")
    if src:
        return f"From {src}. Metadata CC BY 4.0; image rights remain with the source."
    return "Image rights remain with the source library."


def image_object(det, url, page=None) -> dict:
    """schema.org ImageObject for the hero — so Google Images and rich results
    get a real caption, description, credit, and licence, not a bare URL."""
    obj = {
        "@type": "ImageObject",
        "contentUrl": url,
        "name": _clean(det.get("title")),
        "caption": hero_alt(det, page),
    }
    vd = _clean((page or {}).get("descFull") or (page or {}).get("desc"))
    if vd:
        obj["description"] = vd
    src = _clean(det.get("source"))
    if src:
        obj["creditText"] = src
        obj["provider"] = {"@type": "Organization", "name": src}
    # the image itself is the library's; the record/metadata is CC-BY. State the
    # copyright honestly rather than asserting a licence we don't hold.
    obj["copyrightNotice"] = ("Image rights remain with the holding library; "
                              "catalogue metadata is CC BY 4.0.")
    return obj


def sitemap_caption(det, page=None) -> str:
    """A richer caption for the image sitemap entry — a real sentence, so an
    image-search result reads as the cultural object it is."""
    vd = _clean((page or {}).get("descFull") or (page or {}).get("desc"))
    title = _clean(det.get("title") or f"Manuscript #{det.get('id')}")
    if vd:
        return f"{title} — {vd[:180]}"
    obj = object_phrase(det)
    tail = "; ".join(c for c in (_provenance_clause(det), _date_clause(det)) if c)
    s = f"{title}: {obj}"
    if tail:
        s += f", {tail}"
    return _clean(s)


def described_pages(det, limit=12) -> list[dict]:
    """The manuscript's pages that carry a vision reading — the rare, rich
    iconographic descriptions worth surfacing as content. Each: {n, kind,
    text, thumbHref}. Empty for the vast majority (only a vision pass produces
    these)."""
    out = []
    for p in det.get("pages") or []:
        text = _clean(p.get("descFull") or p.get("desc"))
        if not text:
            continue
        out.append({"n": p.get("n"), "kind": p.get("kind") or "",
                    "text": text, "thumbHref": f"/pimg?mid={det['id']}&n={p['n']}&w=1000"})
        if len(out) >= limit:
            break
    return out
