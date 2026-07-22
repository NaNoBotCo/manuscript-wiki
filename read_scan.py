#!/usr/bin/env python3
"""read_scan.py — land a VLM transcription of a raw manuscript scan into the wiki's
shared per-image text store (data/ocr.json), the SAME channel tesseract writes to.

Claude IS the vision model here: `pick` surfaces un-read scans (sha, path, title) to
look at; `set` takes the transcription on stdin and stores it keyed by the image's
sha256, tagged with its provenance (engine='claude-vlm', script, confidence). Because
the store is keyed by checksum, the reading survives re-crawls; because it carries an
engine tag, a machine read and a monk's hand-copy are told apart by provenance, not by
living in different tables. The wiki's detail viewer, the Plates gallery and the search
index all read this file, so a transcription written here shows up everywhere at once.

  python read_scan.py pick  [--mid N] [--limit K] [--only-untranscribed]
  python read_scan.py stats [--mid N]
  echo "<transcription>" | python read_scan.py set <sha> [--script ID] [--conf 0.82] [--lang tha]

Read-only against catalog.db; the only file it writes is data/ocr.json.
"""
import argparse
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CATALOG_DB = Path(os.environ.get("CATALOG_DB", ROOT / "manuscript-crawler" / "crawler" / "catalog.db"))
if not CATALOG_DB.exists():  # fall back to the sibling layout the wiki uses
    CATALOG_DB = Path(os.environ.get("CATALOG_DB", ROOT / "crawler" / "catalog.db"))
STORE_DIR = Path(os.environ.get("STORE_DIR", CATALOG_DB.parent / "store"))
OCR_PATH = HERE / "data" / "ocr.json"


def connect():
    conn = sqlite3.connect(f"file:{CATALOG_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def store_path(sha):
    if not sha or len(sha) < 3 or not all(c in "0123456789abcdef" for c in sha.lower()):
        return None
    p = STORE_DIR / sha[:2] / sha
    return p if p.is_file() else None


def load_ocr():
    try:
        return json.loads(OCR_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_ocr(obj):
    OCR_PATH.parent.mkdir(parents=True, exist_ok=True)
    # atomic write so the running wiki never reads a half-written file
    fd, tmp = tempfile.mkstemp(dir=str(OCR_PATH.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, OCR_PATH)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _label(row):
    return (row["title_english"] or row["title_translit"] or row["title_thai"]
            or "(untitled)")


def cmd_pick(args):
    ocr = load_ocr()
    cat = connect()
    q = ("SELECT i.sha256 sha, i.sequence seq, i.manuscript_id mid, "
         "m.title_english te, m.title_translit tt, m.title_thai th, "
         "m.genre_normalized genre, m.priority prio "
         "FROM images i JOIN manuscripts m ON m.id=i.manuscript_id "
         "WHERE i.sha256 IS NOT NULL")
    params = []
    if args.mid:
        q += " AND i.manuscript_id=?"
        params.append(args.mid)
    q += " ORDER BY (m.priority IS NULL), m.priority DESC, i.manuscript_id, i.sequence"
    n = 0
    for r in cat.execute(q, params):
        if store_path(r["sha"]) is None:
            continue
        rec = ocr.get(r["sha"])
        done = bool(rec and (rec.get("text") if isinstance(rec, dict) else rec))
        if args.only_untranscribed and done:
            continue
        title = (r["te"] or r["tt"] or r["th"] or "(untitled)")
        flag = "·done" if done else "·NEW "
        print(f"{flag} sha={r['sha']} mid={r['mid']} seq={r['seq']} "
              f"[{r['genre'] or '—'}] {title[:48]}")
        print(f"       file={store_path(r['sha'])}")
        n += 1
        if n >= args.limit:
            break
    cat.close()
    if n == 0:
        print("(no matching scans on disk)")


def cmd_stats(args):
    ocr = load_ocr()
    vlm = {sha for sha, rec in ocr.items()
           if isinstance(rec, dict) and rec.get("engine") == "claude-vlm" and rec.get("text")}
    tess = {sha for sha, rec in ocr.items()
            if isinstance(rec, dict) and rec.get("engine") == "tesseract" and rec.get("text")}
    cat = connect()
    total = cat.execute("SELECT count(*) c FROM images WHERE sha256 IS NOT NULL").fetchone()["c"]
    cat.close()
    print(f"scans with sha : {total}")
    print(f"VLM-transcribed: {len(vlm)}")
    print(f"tesseract-OCR  : {len(tess)}")


def cmd_set(args):
    text = sys.stdin.read().strip()
    if not text:
        print("refusing to store an empty transcription", file=sys.stderr)
        return 1
    if store_path(args.sha) is None:
        print(f"no scan on disk for sha={args.sha}", file=sys.stderr)
        return 1
    ocr = load_ocr()
    ocr[args.sha] = {
        "text": text,
        "lang": args.lang or (args.script or "und"),
        "engine": "claude-vlm",
        "script": args.script or "",
        "confidence": args.conf,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    save_ocr(ocr)
    print(f"stored {len(text)} chars for sha={args.sha[:12]}… "
          f"(script={args.script or '?'}, conf={args.conf})")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pick", help="list scans to read")
    p.add_argument("--mid", type=int)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--only-untranscribed", action="store_true")
    p.set_defaults(func=cmd_pick)
    s = sub.add_parser("stats", help="counts of transcribed scans")
    s.add_argument("--mid", type=int)
    s.set_defaults(func=cmd_stats)
    st = sub.add_parser("set", help="store a transcription from stdin")
    st.add_argument("sha")
    st.add_argument("--script", default="")
    st.add_argument("--conf", type=float, default=None)
    st.add_argument("--lang", default="")
    st.set_defaults(func=cmd_set)
    args = ap.parse_args()
    sys.exit(args.func(args) or 0)


if __name__ == "__main__":
    main()
