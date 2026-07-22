#!/usr/bin/env python3
"""build_wats_app.py — publish the wat map as an installable offline app.

Emits docs/wats/app/ :
    index.html          the app (self-contained map) + PWA wiring
    wats-offline.html   the same map with no service worker — a single file you
                        can download, email, or keep on a USB stick forever
    manifest.webmanifest
    sw.js               caches the shell AND map tiles as you browse them
    icon.svg

Source is mueang-map's `wats.html`, which already inlines MapLibre, the whole
catalogue and every photo credit into one file. That property is what makes an
offline app possible at all, so we reuse it rather than rebuild it: one artifact
serves both the installable app and the download.

Run it AFTER the mueang-map visual is current:
    cd ../mueang-map && node build.mjs && node scripts/build-wats-visual.mjs
    python3 build_wats_app.py --docs ../nanobotco-lanna/docs

Offline honesty: the catalogue and the interface work with no signal. Map TILES
are fetched from OpenStreetMap, so a region you have never viewed will be blank
until you visit it online once — the service worker keeps every tile you load.
"""
import argparse
import os
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SRC = HERE.parent / "mueang-map" / "wats.html"

ICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
<rect width="512" height="512" rx="96" fill="#12151a"/>
<path d="M256 96l26 54 60 9-43 42 10 59-53-28-53 28 10-59-43-42 60-9z" fill="#eab945"/>
<path d="M150 300h212v24H150zm-24 40h260v26H126zm-26 42h312v34H100z" fill="#e08a4a"/>
</svg>"""

SW = r"""// sw.js — offline cache for the wat map.
// Shell: cache-first (the app is one self-contained file, so this is the app).
// Tiles: cache-first with network fill — every tile you view is kept, so a
// region browsed once stays available with no signal. Tiles are capped so the
// cache cannot grow without bound on a phone.
const SHELL = 'wats-shell-v__VER__';
const TILES = 'wats-tiles-v1';
const MAX_TILES = 1200;
const ASSETS = ['./', './index.html', './manifest.webmanifest', './icon.svg'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks =>
    Promise.all(ks.filter(k => k !== SHELL && k !== TILES).map(k => caches.delete(k)))
  ).then(() => self.clients.claim()));
});

async function trimTiles() {
  const c = await caches.open(TILES);
  const keys = await c.keys();
  if (keys.length > MAX_TILES) for (const k of keys.slice(0, keys.length - MAX_TILES)) await c.delete(k);
}

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  const isTile = /tile\.openstreetmap\.org|\.png($|\?)/.test(url.href);
  const isPhoto = /upload\.wikimedia\.org/.test(url.hostname);
  if (isTile || isPhoto) {
    e.respondWith(caches.open(TILES).then(async c => {
      const hit = await c.match(e.request);
      if (hit) return hit;
      try {
        const res = await fetch(e.request);
        if (res && (res.ok || res.type === 'opaque')) { c.put(e.request, res.clone()); trimTiles(); }
        return res;
      } catch (err) {
        return hit || Response.error();
      }
    }));
    return;
  }
  e.respondWith(caches.match(e.request).then(hit => hit || fetch(e.request).catch(() => caches.match('./index.html'))));
});
"""

PWA_HEAD = """<link rel="manifest" href="./manifest.webmanifest">
<meta name="theme-color" content="#12151a">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="apple-touch-icon" href="./icon.svg">
"""

PWA_TAIL = """<script>
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('./sw.js').catch(() => {}));
}
// Install affordance: browsers fire beforeinstallprompt only when the app
// qualifies, so this button appears exactly when installing is actually possible.
let _ip = null;
window.addEventListener('beforeinstallprompt', e => {
  e.preventDefault(); _ip = e;
  const b = document.createElement('button');
  b.textContent = 'Install app';
  b.style.cssText = 'position:fixed;right:14px;bottom:14px;z-index:99;padding:11px 16px;border-radius:999px;border:0;background:#eab945;color:#3a2c07;font:inherit;font-weight:700;font-size:15px;cursor:pointer;box-shadow:0 6px 20px #0007';
  b.onclick = async () => { b.remove(); _ip.prompt(); await _ip.userChoice; _ip = null; };
  document.body.appendChild(b);
});
</script>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--docs", required=True, help="published docs/ folder")
    ap.add_argument("--src", default=str(DEFAULT_SRC), help="self-contained wats.html to wrap")
    ap.add_argument("--site-url", default="https://wichaa.net")
    args = ap.parse_args()

    src = Path(args.src).expanduser().resolve()
    if not src.exists():
        print(f"ERROR: {src} not found.\n"
              f"Build it first:  cd ../mueang-map && node build.mjs && node scripts/build-wats-visual.mjs",
              file=sys.stderr)
        return 1
    html = src.read_text(encoding="utf-8")
    # cache version tracks the payload, so a rebuilt map invalidates the shell
    ver = str(abs(hash(html)) % 10**10)

    out = Path(args.docs).expanduser().resolve() / "wats" / "app"
    out.mkdir(parents=True, exist_ok=True)

    # 1. the plain single-file download — no service worker, nothing external
    #    but tiles and photos. Keep it byte-identical to the source build.
    (out / "wats-offline.html").write_text(html, encoding="utf-8")

    # 2. the installable app: same file + manifest/SW wiring
    if "</head>" not in html:
        print("ERROR: source has no </head>; cannot inject PWA wiring", file=sys.stderr)
        return 1
    app = html.replace("</head>", PWA_HEAD + "</head>", 1)
    app = app.replace("</body>", PWA_TAIL + "</body>", 1) if "</body>" in app else app + PWA_TAIL
    (out / "index.html").write_text(app, encoding="utf-8")

    (out / "icon.svg").write_text(ICON, encoding="utf-8")
    (out / "sw.js").write_text(SW.replace("__VER__", ver), encoding="utf-8")
    (out / "manifest.webmanifest").write_text(
        '{\n'
        '  "name": "Wats of the Lanna North",\n'
        '  "short_name": "Wats",\n'
        '  "description": "An offline map of Buddhist temples across northern Thailand, with heritage-registered sites marked.",\n'
        '  "start_url": "./",\n'
        '  "scope": "./",\n'
        '  "display": "standalone",\n'
        '  "orientation": "any",\n'
        '  "background_color": "#12151a",\n'
        '  "theme_color": "#12151a",\n'
        '  "icons": [\n'
        '    {"src": "./icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"}\n'
        '  ]\n'
        '}\n', encoding="utf-8")

    kb = len(html.encode()) / 1024
    print(f"wats app → {out.relative_to(Path(args.docs).resolve().parent)}  "
          f"({kb:.0f} KB payload, cache v{ver})")
    print("  · index.html (installable) · wats-offline.html (download) · sw.js · manifest · icon")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
