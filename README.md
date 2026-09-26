# Lanna Manuscript Wiki

A small, zero-dependency (Python stdlib only) local wiki that browses the
products of the Lanna manuscript crawler in `../crawler/`. Double-click
**`Wiki.command`** (or run `python3 wiki.py`) and it opens at
<http://127.0.0.1:4190>.

It is a **read-only view** over the crawler's outputs — it never writes to the
catalog:

- **`../crawler/catalog.db`** — the SQLite catalog (`sources`, `manuscripts`,
  `images`, `crawl_log`) that the crawler upserts into.
- **`../crawler/store/`** — the content-addressed image store
  (`store/<sha256[:2]>/<sha256>`); the wiki serves page images from here by
  checksum.

Your own additions live in side files under `wiki/data/`, keyed so they survive
re-crawls and DB rebuilds:

- `data/annotations.json` — your notes & tags, keyed by `source::identifier`.
- `data/ocr.json` — OCR text, keyed by **image sha256** (so OCR follows the
  image bytes, not a row id).

## What you can do

- **Browse & search** every catalogued manuscript. Facets come straight from the
  crawler's normalized tokens (`crawler/genre.py`): genre, script, material,
  language, province, source, century, and a **Research priority** filter
  (`divination_omen`, `astrology`, `magic_ritual`). Priority manuscripts are
  sorted first and flagged.
- **Read a manuscript** — every catalog column, the untouched `raw_metadata`
  blob (collapsible), and an image viewer paging through the stored page images
  with an **Image / OCR text** toggle. Links out to `source_url` and the IIIF
  manifest when present.
- **OCR layer** — OCR the stored images from the manuscript page; text is saved
  in `data/ocr.json` by image checksum.
- **Notes & tags** — per-manuscript, saved locally.
- **Crawl status** (`/status`) — counts, the `sources` table, and the recent
  `crawl_log`, so you can see harvest progress. Renders gracefully before the
  DB even exists.

## Config

Environment overrides (all optional):

- `CATALOG_DB` — path to the catalog (default `../crawler/catalog.db`).
- `STORE_DIR` — path to the image store (default `../crawler/store`).
- `PORT` — default `4190`.

## OCR

From a manuscript page, pick a language and press **Run OCR**. It shells out to
the **Tesseract** CLI (`brew install tesseract tesseract-lang`) over each stored
image and writes the text into `data/ocr.json`.

**Lanna (Tham) script has no off-the-shelf OCR model.** Thai (`tha`) is only a
starting point for Thai-script portions — swap in a better engine in
`run_ocr()`/`run_engine` when you have one. If Tesseract or a language pack is
missing, the run reports exactly what to install and changes nothing.

## Files

| File | Purpose |
|------|---------|
| `wiki.py` | The whole server + UI (Python stdlib, no deps). |
| `Wiki.command` | Double-click launcher. |
| `data/annotations.json` | Your notes & tags. |
| `data/ocr.json` | OCR text by image checksum. |

The catalog and image store are produced by the crawler in `../crawler/`; this
wiki only reads them.


## Licence

Records, prose, pages and the compilation: **CC BY 4.0**, attributed to wichaa.
Code: **MIT**. Attribution is the only condition — name the work and link back,
and the rest is yours: copy it, adapt it, sell it, index it, train on it.

Manuscript images and their thumbnails are not covered by that: rights remain
with each holding library, and the record's source link names it. Wikipedia text
carried into the articles stays CC BY-SA 4.0, Wikidata is CC0, OpenStreetMap
data is ODbL. Each layer, with its attribution, is in [NOTICE.txt](NOTICE.txt);
the verbatim licence text is in [LICENSE](LICENSE).

---

Contact: Nan · nan@motdang.net · Sponsor: [Ko-fi](https://ko-fi.com/defiantchiangmai) · [Patreon](https://www.patreon.com/nanobotco)
