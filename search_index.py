#!/usr/bin/env python3
"""search_index.py — build the semantic search index for wichaa in Vectorize.

What this is for
----------------
wichaa's navigation is a directory: terms, counts, facets. That is the right
front door and it stays. What it cannot do is answer a question — "manuscripts
about protective tattoos from Lamphun", "ตำรายา on palm leaf" — because a
directory can only match the words someone already knows to type.

This embeds every manuscript as a single multilingual document and stores the
vector in Vectorize, so the corpus can be searched by MEANING, in Thai or in
English, regardless of which language the record happens to be written in.

Why bge-m3
----------
Measured, not assumed. Embedding a Thai term and its English gloss with three
candidate models and comparing cosine separation against an unrelated pair:

    @cf/baai/bge-m3               separation +0.164   (1024 dims)
    @cf/qwen/qwen3-embedding-0.6b separation +0.126   (1024 dims)
    @cf/baai/bge-base-en-v1.5     separation -0.006   (768 dims)

The English-only model scored UNRELATED Thai/English pairs slightly higher than
related ones — it is not merely weaker on this corpus, it is anti-correlated.
Any English-first embedding choice here is wrong.

Document shape
--------------
One vector per manuscript, built from the trilingual title (Thai, RTGS
transliteration, English), genre, material, script, provenance temple and
province, date, and mined tags. Records are ~100% covered on titles and 94% on
provenance, so nearly every document carries place and genre — which is what
makes "from Lamphun" work as a query rather than a keyword match.

Resumable
---------
Vector ids are stable (`ms:<id>`), so re-running upserts rather than
duplicates, and `--since` limits work to recently-changed records. Workers AI
has a daily free allowance; on quota exhaustion this stops cleanly and reports
how far it got, so the next run continues instead of starting over.

Usage:
  python3 search_index.py --dry-run          # show documents, embed nothing
  python3 search_index.py --limit 200        # a first slice
  python3 search_index.py                    # everything
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sqlite3
import sys
import time
import urllib.error
import urllib.request

ACCOUNT_ID = "fe332688b1b25b543f8429d7f08292a3"
INDEX = "wichaa-search"
MODEL = "@cf/baai/bge-m3"
DIMS = 1024
API = "https://api.cloudflare.com/client/v4"

# bge-m3 takes 8192 tokens, far more than any of these documents need, but the
# REST endpoint has its own request-size ceiling — keep batches modest.
BATCH = 50

CRAWLER = pathlib.Path.home() / "Developer" / "claude code projects" / "manuscript-crawler"
DB_PATH = pathlib.Path(os.environ.get("CATALOG_DB", CRAWLER / "crawler" / "catalog.db"))


def token(force_refresh: bool = False) -> str:
    sys.path.insert(0, str(CRAWLER))
    from crawler import cfauth
    return cfauth.token(force_refresh=force_refresh)


def _clean(*parts: object) -> str:
    seen, out = set(), []
    for p in parts:
        s = ("" if p is None else str(p)).strip()
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return " · ".join(out)


def documents(db: sqlite3.Connection, limit: int | None) -> list[dict]:
    """One embeddable document per manuscript, plus its display metadata.

    Metadata is kept small on purpose: Vectorize caps metadata per vector, and
    everything here is only what the results list needs to render without a
    second lookup. The full record still lives in catalog.db.
    """
    # The mined vernacular tags (เลขยันต์, ตะกรุด, …) are the emic vocabulary
    # this corpus exists to preserve, and they are the terms a Thai reader will
    # actually type. Indexing without them would work and would quietly be a
    # much poorer search, so a schema mismatch SHOUTS rather than degrading —
    # an earlier version caught OperationalError and passed, and silently
    # dropped all 27,195 of them because the column is `term_raw`, not `term`.
    tags: dict[int, list[str]] = {}
    try:
        for mid, term_raw, topic in db.execute(
            "select manuscript_id, term_raw, topic from tags "
            "where manuscript_id is not null and term_raw is not null"
        ):
            bucket = tags.setdefault(mid, [])
            bucket.append(term_raw)
            if topic and topic not in bucket:
                bucket.append(topic)
    except sqlite3.OperationalError as e:
        sys.exit(f"tags table not in the expected shape ({e}).\n"
                 f"  Refusing to build a silently impoverished index — fix the query first.")
    print(f"tags: {sum(len(v) for v in tags.values())} across {len(tags)} manuscripts")

    rows = db.execute(f"""
        select id, title_thai, title_translit, title_english, genre_raw,
               genre_normalized, material, script, language, provenance_temple,
               provenance_province, date_text, work_title, work_desc, wat_name_th
        from manuscripts order by id {"limit " + str(limit) if limit else ""}
    """).fetchall()

    docs = []
    for r in rows:
        t = tags.get(r["id"], [])[:12]
        text = "\n".join(filter(None, [
            _clean(r["title_thai"], r["title_translit"], r["title_english"]),
            _clean(r["genre_normalized"], r["genre_raw"]),
            _clean(r["material"], r["script"], r["language"]),
            _clean(r["provenance_temple"], r["wat_name_th"], r["provenance_province"]),
            _clean(r["date_text"]),
            _clean(r["work_title"], r["work_desc"]),
            (" · ".join(t) if t else ""),
        ]))
        docs.append({
            "id": f"ms:{r['id']}",
            "text": text,
            "meta": {
                "kind": "manuscript",
                "mid": r["id"],
                # Titles are truncated so a long record cannot blow the metadata
                # budget and fail the whole upsert batch.
                "th": (r["title_thai"] or "")[:180],
                "en": (r["title_english"] or "")[:180],
                "translit": (r["title_translit"] or "")[:180],
                "genre": (r["genre_normalized"] or "")[:60],
                "place": (r["provenance_province"] or "")[:60],
                "temple": (r["provenance_temple"] or "")[:100],
                "date": (r["date_text"] or "")[:60],
            },
        })
    return docs


def embed(texts: list[str], tok: str) -> list[list[float]]:
    url = f"{API}/accounts/{ACCOUNT_ID}/ai/run/{MODEL}"
    body = json.dumps({"text": texts}).encode()
    for attempt in range(5):
        try:
            req = urllib.request.Request(
                url, data=body, method="POST",
                headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                d = json.load(r)
            if not d.get("success"):
                raise RuntimeError(f"AI error: {d.get('errors')}")
            return d["result"]["data"]
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            if e.code in (401, 403) and "quota" not in detail.lower():
                tok = token(force_refresh=True)
                continue
            # 429 = the daily neuron allowance. Not retryable within this run.
            if e.code == 429 or "quota" in detail.lower() or "limit" in detail.lower():
                raise QuotaExhausted(detail) from e
            if attempt == 4:
                raise RuntimeError(f"HTTP {e.code}: {detail}") from e
            time.sleep(2 ** attempt)
        except (urllib.error.URLError, TimeoutError):
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


class QuotaExhausted(RuntimeError):
    """Daily Workers AI allowance is spent. Stop cleanly; resume tomorrow."""


def upsert(vectors: list[dict], tok: str) -> int:
    """Vectorize's REST insert takes NDJSON, one vector object per line."""
    url = f"{API}/accounts/{ACCOUNT_ID}/vectorize/v2/indexes/{INDEX}/upsert"
    body = "\n".join(json.dumps(v) for v in vectors).encode()
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url, data=body, method="POST",
                headers={"Authorization": f"Bearer {tok}",
                         "Content-Type": "application/x-ndjson"})
            with urllib.request.urlopen(req, timeout=180) as r:
                d = json.load(r)
            if not d.get("success"):
                raise RuntimeError(f"upsert failed: {d.get('errors')}")
            return len(vectors)
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            if e.code in (401, 403):
                tok = token(force_refresh=True)
                continue
            if attempt == 3:
                raise RuntimeError(f"upsert HTTP {e.code}: {detail}") from e
            time.sleep(2 ** attempt)
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--batch", type=int, default=BATCH)
    args = ap.parse_args()

    if not DB_PATH.exists():
        sys.exit(f"no catalogue at {DB_PATH}")
    db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row

    docs = documents(db, args.limit)
    print(f"documents: {len(docs)}")
    avg = sum(len(d["text"]) for d in docs) / max(len(docs), 1)
    print(f"avg length: {avg:.0f} chars")

    if args.dry_run:
        for d in docs[:3]:
            print(f"\n--- {d['id']} ---\n{d['text']}")
        print("\ndry run — nothing embedded.")
        return

    tok = token()
    done = failed = 0
    started = time.time()
    for i in range(0, len(docs), args.batch):
        chunk = docs[i:i + args.batch]
        try:
            vecs = embed([c["text"] for c in chunk], tok)
        except QuotaExhausted as e:
            print(f"\nWorkers AI daily allowance reached after {done} documents.")
            print(f"  {e}")
            print("  Re-run tomorrow (or on Workers Paid) — ids are stable, so it resumes.")
            break
        except Exception as e:  # noqa: BLE001
            print(f"  ! embed batch {i}: {e}")
            failed += len(chunk)
            continue
        payload = [{"id": c["id"], "values": v, "metadata": c["meta"]}
                   for c, v in zip(chunk, vecs)]
        try:
            done += upsert(payload, tok)
        except Exception as e:  # noqa: BLE001
            print(f"  ! upsert batch {i}: {e}")
            failed += len(chunk)
        if (i // args.batch) % 10 == 0:
            el = time.time() - started
            print(f"  {done}/{len(docs)}  {el/60:.1f} min", flush=True)

    print(f"\nindexed {done}, failed {failed}, in {(time.time()-started)/60:.1f} min")


if __name__ == "__main__":
    main()
