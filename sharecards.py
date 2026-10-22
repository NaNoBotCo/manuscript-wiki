#!/usr/bin/env python3
"""sharecards — link-card tags for pages whose generators do not write them.

    python3 sharecards.py apply  --docs DIR [--site-url URL]     after every generator, before the gates
    python3 sharecards.py render [slug ...]                      draw data/sharecards/<slug>.jpg

data/sharecards/spec.json lists each page (path under docs/) and what it gets:
  keep    the page's own card stays; the alt text and size tags are written beside it
  image   a card already in docs/ (site-relative path) becomes the page's card
  render  a 1200x630 card in data/sharecards/<slug>.jpg, copied to docs/og/<slug>.jpg

`apply` rewrites og:image, og:image:width/height/type/alt and twitter:card/image/alt in the head
and leaves og:title and og:description as the page has them. It runs on a fresh build every
time, so the tags survive build_static.py wiping docs/. A page it cannot find, or a card file
it cannot find, is skipped with a warning and left as built.

`render` draws the cards with ../share-cards/render.mjs (Chromium through playwright).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "sharecards"
SPEC = DATA / "spec.json"
SHARE_CARDS = Path(os.environ.get("SHARECARDS_DIR") or Path.home() / "Developer" / "claude code projects" / "share-cards")

KEYS = r"og:image(?::(?:width|height|alt|type|secure_url|url))?|twitter:image(?::alt)?|twitter:card"
OLD = re.compile(r'[ \t]*<meta\s+[^>]*(?:property|name)\s*=\s*["\'](?:' + KEYS + r')["\'][^>]*>[ \t]*\n?', re.I)
OG_IMAGE = re.compile(r'<meta\s+[^>]*property\s*=\s*["\']og:image["\'][^>]*>', re.I)
CONTENT = re.compile(r'content\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', re.I)


def tags(image: str, alt: str, w: int = 1200, h: int = 630) -> str:
    a, i = html.escape(alt, quote=True), html.escape(image, quote=True)
    t = "image/png" if image.lower().endswith(".png") else "image/jpeg"
    return (f'<meta property="og:image" content="{i}">'
            f'<meta property="og:image:width" content="{w}"><meta property="og:image:height" content="{h}">'
            f'<meta property="og:image:type" content="{t}"><meta property="og:image:alt" content="{a}">'
            f'<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{i}">'
            f'<meta name="twitter:image:alt" content="{a}">')


def stamp(text: str, image: str, alt: str) -> str:
    end = re.search(r"</head\s*>", text, re.I)
    if not end:
        raise ValueError("no </head>")
    head, rest = text[:end.start()], text[end.start():]
    head = OLD.sub("", head)
    block = tags(image, alt)
    m = (re.search(r'<meta\s+[^>]*property\s*=\s*["\']og:description["\'][^>]*>', head, re.I)
         or re.search(r'<meta\s+[^>]*property\s*=\s*["\']og:title["\'][^>]*>', head, re.I))
    head = head[:m.end()] + "\n" + block + head[m.end():] if m else head.rstrip() + "\n" + block + "\n"
    return head + rest


def current_image(text: str, site: str) -> str | None:
    end = re.search(r"</head\s*>", text, re.I)
    head = text[:end.end()] if end else text
    m = OG_IMAGE.search(head)
    if not m:
        return None
    c = CONTENT.search(m.group(0))
    url = html.unescape((c.group(1) or c.group(2) or "").strip()) if c else ""
    if not url:
        return None
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return site + url
    return url


def load_spec() -> dict:
    return json.loads(SPEC.read_text(encoding="utf-8"))


def apply(docs: Path, site: str) -> int:
    spec = load_spec()
    site = (site or spec["site"]).rstrip("/")
    done = skipped = 0
    for rel, v in spec["pages"].items():
        page = docs / rel
        if not page.is_file():
            print(f"  sharecards: {rel} not in docs, skipped", file=sys.stderr)
            skipped += 1
            continue
        text = page.read_text(encoding="utf-8")
        if v.get("keep"):
            image = current_image(text, site)
            if not image:
                print(f"  sharecards: {rel} has no og:image to keep, skipped", file=sys.stderr)
                skipped += 1
                continue
        elif v.get("image"):
            if not (docs / v["image"].lstrip("/")).is_file():
                print(f"  sharecards: {v['image']} not in docs, {rel} skipped", file=sys.stderr)
                skipped += 1
                continue
            image = site + "/" + v["image"].lstrip("/")
        else:
            src = DATA / f"{v['slug']}.jpg"
            if not src.is_file():
                print(f"  sharecards: {src.name} not drawn, {rel} skipped", file=sys.stderr)
                skipped += 1
                continue
            dst = docs / "og" / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            image = f"{site}/og/{src.name}"
        new = stamp(text, image, v["alt"])
        if new != text:
            page.write_text(new, encoding="utf-8")
        done += 1
    print(f"  sharecards: {done} pages tagged, {skipped} skipped")
    return 0


def render(slugs: list[str]) -> int:
    spec = load_spec()
    jobs = []
    for v in spec["pages"].values():
        r = v.get("render")
        if not r or (slugs and v["slug"] not in slugs):
            continue
        img = r.get("image", "")
        if img and not re.match(r"^(https?|data|file):", img) and not os.path.isabs(img):
            r = {**r, "image": str(DATA / img)}  # a picture kept in data/sharecards/
        jobs.append({**spec["common"], **r, "out": str(DATA / f"{v['slug']}.jpg"),
                     "url": f"{spec['site'].split('//')[-1]}/{v['slug']}"})
    if not jobs:
        print("nothing to draw")
        return 0
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False)
    return subprocess.call(["node", str(SHARE_CARDS / "render.mjs"), f.name], cwd=SHARE_CARDS)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("apply")
    a.add_argument("--docs", required=True)
    a.add_argument("--site-url", default=os.environ.get("SITE_URL", ""))
    r = sub.add_parser("render")
    r.add_argument("slugs", nargs="*")
    args = ap.parse_args()
    if args.cmd == "apply":
        return apply(Path(args.docs), args.site_url)
    return render(args.slugs)


if __name__ == "__main__":
    sys.exit(main())
