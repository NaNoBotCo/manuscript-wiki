#!/usr/bin/env python3
"""make_snapshot.py — package a shareable, self-contained copy of the Lanna
Manuscript Wiki "as it is right now", for other scholars to open on their own Mac.

What goes in the bundle:
  • wiki.py + articles.py           — the viewer itself (plain Python, no installs)
  • crawler/catalog.db              — a consistent read-only copy of the catalogue
  • store_pages/                    — the rendered plates (diagrams, described pages)
  • content/ , data/ocr.json …      — the articles and your transcriptions/notes
  • "View Lanna Wiki.command"       — double-click to open it in a browser
  • "READ ME FIRST.txt"             — one short page for the recipient

What is deliberately LEFT OUT:
  • the 15 GB of raw manuscript scans (they live on your external drive and are
    too big to hand around). In the snapshot those images fall back to a
    "view at source" link to the originating library, so nothing looks broken.

The bundle is a normal folder plus a .zip beside it. Nothing is uploaded or
published — you decide who to send it to.

Usage:
    python3 make_snapshot.py                 # writes to ~/Desktop
    python3 make_snapshot.py --out /some/dir
    python3 make_snapshot.py --no-zip
"""
import argparse
import os
import shutil
import sqlite3
import zipfile
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CATALOG_DB = Path(os.environ.get("CATALOG_DB", ROOT / "manuscript-crawler" / "crawler" / "catalog.db"))
if not CATALOG_DB.exists():
    CATALOG_DB = ROOT / "crawler" / "catalog.db"
PAGES_BASE = CATALOG_DB.resolve().parent.parent  # holds store_pages/
STORE_PAGES = PAGES_BASE / "store_pages"

VIEW_LAUNCHER = """#!/bin/bash
# ============================================================================
#  Lanna Manuscript Wiki  —  a shared snapshot.  Double-click to open it.
#  Needs nothing but the Python that comes with macOS. Leave this window open
#  while you read; close it when you're done.
# ============================================================================
DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=4200
URL="http://127.0.0.1:${PORT}/"
export CATALOG_DB="$DIR/crawler/catalog.db"
export STORE_DIR="$DIR/crawler/store"
export PORT
cd "$DIR" || exit 1
PY=$(command -v python3 || command -v python)
if [ -z "$PY" ]; then
  echo "This snapshot needs Python 3. On a Mac, open Terminal and run: xcode-select --install"
  sleep 20; exit 1
fi
if curl -s -o /dev/null --max-time 2 "$URL"; then open "$URL"; exit 0; fi
echo "Opening the Lanna Manuscript Wiki snapshot…"
nohup "$PY" wiki.py >/tmp/lanna-wiki-snapshot.log 2>&1 &
disown 2>/dev/null
for i in $(seq 1 25); do curl -s -o /dev/null "$URL" && break; sleep 0.3; done
open "$URL"
echo "It should now be open in your browser at $URL"
echo "You can close this window."
sleep 3
"""

READ_ME = """LANNA MANUSCRIPT WIKI — shared snapshot ({dated})
==================================================================

This is a self-contained copy of a working research catalogue of Lanna
(Northern Thai) manuscripts and the living tradition around them — divination,
astrology, protective magic, sak-yant, herbal and ritual texts — digitised and
made legible for both people and AI.

TO OPEN IT
  • Double-click  "View Lanna Wiki.command".
  • Your web browser opens to the wiki. That's it.
  • (The first time, macOS may ask you to confirm opening a downloaded file:
     right-click the file → Open → Open.)

WHAT YOU'RE LOOKING AT
  • Overview / Browse — the full catalogue, filterable by script, genre, temple,
    province, date and more.
  • Plates — a gallery of the digitised pages. "Rendered plates" are the
    diagrams and described pages; "Raw scans" are the manuscript folios
    themselves (shown here as links to the source library).
  • Articles / Vocabulary — the interpretive layer: named figures, the working
    words of the tradition, each claim marked by how it's known.
  • Map / Graph — where the manuscripts come from, and how they connect.

A NOTE ON THE IMAGES
  The high-resolution manuscript scans are held at their originating libraries;
  this snapshot links out to them rather than copying them. Everything else —
  the catalogue, the plates, the articles — is fully included and works offline.

QUESTIONS OR CONCERNS
  This is a preservation project, shared openly. If you are a rights-holder or
  community member with a concern about anything here, contact: 530kings@proton.me
"""


def copy_db(src: Path, dst: Path):
    """Consistent read-only copy even while the crawler may be writing (WAL)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    src_conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    dst_conn = sqlite3.connect(str(dst))
    with dst_conn:
        src_conn.backup(dst_conn)
    src_conn.close()
    dst_conn.close()


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def dir_size(p: Path):
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(Path.home() / "Desktop"),
                    help="where to write the snapshot (default: Desktop)")
    ap.add_argument("--no-zip", action="store_true", help="skip making the .zip")
    args = ap.parse_args()

    dated = date.today().isoformat()
    name = f"Lanna-Wiki-snapshot-{dated}"
    out = Path(args.out).expanduser() / name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    print(f"Building snapshot → {out}")

    # 1. the viewer
    for f in ("wiki.py", "articles.py"):
        if (HERE / f).exists():
            shutil.copy2(HERE / f, out / f)
    if (HERE / "README.md").exists():
        shutil.copy2(HERE / "README.md", out / "wiki-README.md")

    # 2. the catalogue (consistent copy), placed so wiki.py's path logic just works
    print("  · copying catalogue (consistent snapshot)…")
    copy_db(CATALOG_DB, out / "crawler" / "catalog.db")

    # 3. the rendered plates
    if STORE_PAGES.exists():
        print(f"  · copying rendered plates ({human(dir_size(STORE_PAGES))})…")
        shutil.copytree(STORE_PAGES, out / "store_pages")

    # 4. articles + the interpretive/annotation layer (skip the rebuildable search index)
    if (HERE / "content").exists():
        shutil.copytree(HERE / "content", out / "content")
    data_out = out / "data"
    data_out.mkdir(exist_ok=True)
    for f in ("ocr.json", "annotations.json", "relations.json"):
        if (HERE / "data" / f).exists():
            shutil.copy2(HERE / "data" / f, data_out / f)

    # 5. launcher + read-me
    launcher = out / "View Lanna Wiki.command"
    launcher.write_text(VIEW_LAUNCHER, encoding="utf-8")
    launcher.chmod(0o755)
    (out / "READ ME FIRST.txt").write_text(READ_ME.format(dated=dated), encoding="utf-8")

    total = dir_size(out)
    print(f"  · folder assembled: {human(total)}")

    # 6. zip
    if not args.no_zip:
        zpath = out.with_suffix(".zip")
        print(f"  · zipping → {zpath.name} …")
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for f in out.rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(out.parent))
        print(f"  · zip: {human(zpath.stat().st_size)}")

    print("\nDone. To share: send the .zip (or the folder on a USB drive).")
    print("The recipient just double-clicks \"View Lanna Wiki.command\" inside it.")


if __name__ == "__main__":
    main()
