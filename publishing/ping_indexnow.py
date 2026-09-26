#!/usr/bin/env python3
"""Tell IndexNow which wichaa pages changed. Run AFTER the deploy lands.

IndexNow is one POST to one endpoint that shares it with Bing, Yandex, Seznam,
Naver and everything that reads Bing's index. It wants the URLs that changed,
not the whole site every night, so this reads the sitemap the build just wrote
and sends the rows whose lastmod is newer than the last successful ping.

The first run has no record of a last ping and sends every URL once. After
that, a night on which nothing changed sends nothing.

    python3 publishing/ping_indexnow.py --docs ../nanobotco-lanna/docs
    python3 publishing/ping_indexnow.py --docs … --all       # everything, once more
    python3 publishing/ping_indexnow.py --docs … --dry-run   # count, send nothing

Exit status is 0 even when the endpoint refuses: by the time this runs the site
is already live, and a failed notice is not worth a failed publish. It says so
in the log instead.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
HOST = "wichaa.net"
ENDPOINT = "https://api.indexnow.org/IndexNow"
BATCH = 10_000                     # the protocol's per-request ceiling
STAMP = HERE / "data" / "indexnow_last.txt"
KEY = re.search(r'^INDEXNOW_KEY = "([0-9a-f]+)"',
                (HERE / "site_meta.py").read_text(encoding="utf-8"), re.M).group(1)


def rows(docs: Path) -> list[tuple[str, str]]:
    """(url, lastmod) for every page in the sitemap plus the sub-site sitemaps
    the index names, so /amulets/ and /handpoke/ are announced too."""
    out: list[tuple[str, str]] = []
    files = [docs / "sitemap-pages.xml"]
    idx = docs / "sitemap.xml"
    if idx.is_file():
        for loc in re.findall(r"<loc>https://wichaa\.net/([^<]+)</loc>",
                              idx.read_text(encoding="utf-8")):
            f = docs / loc
            if f.is_file() and f not in files:
                files.append(f)
    for f in files:
        if not f.is_file():
            continue
        text = f.read_text(encoding="utf-8")
        for block in re.findall(r"<url>(.*?)</url>", text, re.S):
            loc = re.search(r"<loc>([^<]+)</loc>", block)
            mod = re.search(r"<lastmod>([^<]+)</lastmod>", block)
            if loc and loc.group(1).startswith(f"https://{HOST}/"):
                out.append((loc.group(1), (mod.group(1)[:10] if mod else "")))
    return out


def send(urls: list[str]) -> int:
    body = json.dumps({"host": HOST, "key": KEY,
                       "keyLocation": f"https://{HOST}/{KEY}.txt",
                       "urlList": urls}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:  # network down, DNS, timeout
        print(f"indexnow: could not reach the endpoint — {e}")
        return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--docs", required=True)
    ap.add_argument("--all", action="store_true", help="send every URL, not only changed ones")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    docs = Path(a.docs).expanduser().resolve()

    live = urllib.request.Request(f"https://{HOST}/{KEY}.txt", method="GET")
    try:
        with urllib.request.urlopen(live, timeout=30) as r:
            served = r.read().decode().strip()
    except Exception:
        served = ""
    if served != KEY and not a.dry_run:
        print(f"indexnow: https://{HOST}/{KEY}.txt is not serving the key yet — "
              "nothing sent. It goes live with the next deploy.")
        return 0

    last = "" if a.all or not STAMP.is_file() else STAMP.read_text().strip()
    every = rows(docs)
    urls = [u for u, m in every if not last or (m and m > last)]
    why = "all" if not last else f"changed since {last}"
    print(f"indexnow: {len(urls):,} of {len(every):,} URLs ({why})")
    if a.dry_run or not urls:
        return 0

    ok = True
    for i in range(0, len(urls), BATCH):
        chunk = urls[i:i + BATCH]
        status = send(chunk)
        # 200 = taken, 202 = taken and key check pending. Anything else is a refusal.
        print(f"indexnow: batch {i // BATCH + 1}: {len(chunk):,} URLs → HTTP {status}")
        ok = ok and status in (200, 202)
    if ok:
        STAMP.parent.mkdir(parents=True, exist_ok=True)
        STAMP.write_text(date.today().isoformat() + "\n")
    else:
        print("indexnow: at least one batch was refused — the stamp is not advanced, "
              "so tomorrow's run sends these again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
