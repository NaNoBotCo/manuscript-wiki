#!/usr/bin/env python3
"""cards — a generic Pillow text card for entities with no photograph of their own.

Follows the one precedent already proven in this codebase, wiki.py's
og_card_bytes() (the homepage's featured-plate card): a 1200x630 image matted on
the site's dark teal ground, drawn with Pillow at build time, no headless-browser
dependency. That function is image+text (a manuscript plate beside a title); this
is the text-only sibling for entities that have no image to put beside — a wat with
no Wikimedia photo, a subject article, a glossary domain. Degrades to None (never
raises) if Pillow or a usable font is unavailable, exactly like og_card_bytes().

Cached by simple existence check at `cache_path` — unlike og_card_bytes()'s
content-hash cache (which exists because the homepage's featured plate rotates),
these cards are keyed to facts (a place's name, a term's headword) that don't
change build to build, so "already on disk" is cache-valid.
"""
from __future__ import annotations

import io
from pathlib import Path

W, H = 1200, 630
BG = (18, 45, 42)                    # deep teal, matches the site header
CREAM, GOLD, MUTED = (244, 234, 214), (233, 196, 106), (150, 180, 172)


def _has_thai(s: str) -> bool:
    return any(0x0E00 <= ord(c) <= 0x0E7F for c in s)


def _font(size, serif=True, thai=False):
    from PIL import ImageFont
    if thai:
        # Georgia/Arial have no Thai glyphs at all (silent tofu boxes, not an
        # exception PIL would raise) — a title/subtitle carrying Thai script (no
        # romanization on file) needs a Thai-capable face instead.
        candidates = ("/System/Library/Fonts/Supplemental/Ayuthaya.ttf",
                     "/System/Library/Fonts/Supplemental/SukhumvitSet.ttc",
                     "/System/Library/Fonts/ThonburiUI.ttc")
    else:
        candidates = (
            ("/System/Library/Fonts/Supplemental/Georgia.ttf",
             "/Library/Fonts/Georgia.ttf",
             "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
             "/System/Library/Fonts/Georgia.ttf") if serif else
            ("/System/Library/Fonts/Supplemental/Arial.ttf",
             "/Library/Fonts/Arial.ttf")
        )
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return None


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def text_card_bytes(title: str, subtitle: str = "",
                    tagline: str = "wichaa — living traditions of sacred knowledge",
                    cache_path: Path | None = None) -> bytes | None:
    """A 1200x630 JPEG: title (large, cream) + subtitle (gold) + brand tagline
    (small, bottom-left), centered on the dark ground. None if Pillow/fonts are
    unavailable or `title` is empty — never a broken or blank card."""
    if not title:
        return None
    if cache_path and cache_path.is_file():
        return cache_path.read_bytes()
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None
    try:
        canvas = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(canvas)
        pad, tw = 90, W - 180
        tf = _font(64, thai=_has_thai(title))
        sf = _font(30, thai=_has_thai(subtitle)) if subtitle else _font(30)
        cf = _font(22, serif=False)
        if not (tf and sf and cf):
            return None
        title_lines = _wrap(draw, title, tf, tw)[:3]
        sub_lines = _wrap(draw, subtitle, sf, tw)[:2] if subtitle else []
        block_h = len(title_lines) * 76 + (16 + len(sub_lines) * 40 if sub_lines else 0)
        y = (H - block_h) // 2
        for ln in title_lines:
            draw.text((pad, y), ln, font=tf, fill=CREAM); y += 76
        if sub_lines:
            y += 16
            for ln in sub_lines:
                draw.text((pad, y), ln, font=sf, fill=GOLD); y += 40
        draw.text((pad, H - 64), tagline, font=cf, fill=MUTED)
        buf = io.BytesIO()
        canvas.save(buf, "JPEG", quality=88, optimize=True)
        data = buf.getvalue()
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache_path.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(cache_path)
        return data
    except Exception:
        return None
