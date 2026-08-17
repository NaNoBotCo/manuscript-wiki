# Slugs & metadata — a concrete proposal

Survey basis: `routes.py`, `build_static.py`, `wiki.py`, `site_meta.py`, `imagemeta.py`,
`make_card.py`, `cards.py`, `manuscript_pages.py`, `article_pages.py`, `trails.py`,
plus a sample of `../nanobotco-lanna/docs/`. Counts below are measured from the built
tree (2026-08-06), not estimated.

## 1. Inventory — every current URL pattern

| Route family | Pattern today | Count | Slug quality | Metadata today |
|---|---|---|---|---|
| Sections (`/browse`, `/market`, `/wats`, `/moon`, …) | English word, `routes.py`-declared | 32 | Already good (hand-picked) | Mixed: root + `/wats`, `/widgets`, `/moon`, `/jovilabe`, `/hotrai`, `/sukhwan`, `/khwan` have custom `og_image` cards (`wiki.py` ~8130–8370) and Dataset/Website JSON-LD (root only, via `site_meta.py`); most others fall back to the sitewide `og.jpg` and `SITE_DESC`, no page-specific JSON-LD |
| Manuscript detail `/m/<id>/` | **raw DB integer** | 6,990 | Poor — no human signal | Good: real `<title>`, `og:*` (incl. image), `Manuscript`+`BreadcrumbList` JSON-LD, all baked in `manuscript_pages.py` at build time |
| Bilingual reader `/read/<id>/` | **raw DB integer** | 7 (only fully-transcribed volumes) | Poor | Partial: title + description + `og:url`, but **no custom `og:image`** (falls back to site default) and JSON-LD (`CreativeWork`) is patched on **after the fact** by `site_meta.py`, not baked at render time — no `BreadcrumbList` |
| Article `/a/<slug>/` | `entity_su_khwan`, `genre_astrology` (type-prefixed, regex-slugified key) | 33 | Functional but ugly (underscore, type prefix leaks into the URL) | Good: title, `og:*`, `Article`/`CollectionPage` + `BreadcrumbList` JSON-LD |
| Place/wat `/place/<slug>/` | `wat-chiang-man`, `al-israq-mosque` — kebab-case, human-readable, **inherited from the OSM/Wikidata id upstream in `data/`** | 1,494 | **Already the model to copy** | Good: per-place `og:*`, `Place` JSON-LD (`wiki.py` comment at ~7813) |
| Trail `/trail/<slug>/` | hand-authored trails: clean (`old-city-walk`, `wat-chiang-man`); bot-authored trails: **concatenation bug** — `"bot-" + node_id` with no separator before the title half (`bot-chronologydeep-roots`, should read `bot-chronology-deep-roots`) | 13 | Good design, one bug | Good: `og_image`/`og_url` set (`trails.py:247`) |
| Widget `/w/<name>/` | `geo`, `prices`, `regions`, … — plain words | 6 (+6 offline variants) | Already good | Good: per-widget `og:image` card via `make_card.py`/`cards.py` |
| Textbook volumes | **Not a distinct route** — 31 contributed volumes are manuscripts, so they live at `/m/<id>/` like any other; `work_title`/`work_desc` (bilingual, curated) exist as DB columns but only render as link text on `/textbooks`, never as a slug | 31 (subset of the 6,990) | Poor (same numeric-id problem as manuscripts) | Same as `/m/<id>/` |
| Glossary, Na, Diagrams | Single index page each, no per-entry URL (in-page anchors/gallery only) | 1 page each | N/A — not yet addressable per-entity | Page-level only |

Everything under `BULK_NAMESPACES` in `routes.py` (`/place/`, `/read/`, `/trail/`,
`/m/`) is already the registry's own concept of "one-page-per-record built by a
generator" — the right seam to hang slug logic on.

## 2. Slug design

**Constraints taken as given** (repeated back so the plan is checked against them):
GH Pages has no server-side redirects; old URLs are indexed and Wayback-archived so
they must resolve *forever*; slugs must be minted once and frozen, never re-derived
from a mutable title; `routes.py` is the nav registry and the build fails on drift.

**Scheme, per entity type:**

- **Manuscripts (`/m/`) and textbook volumes** (the same table): `/m/<slug>-<id>/`,
  e.g. `/m/tamra-maleng-pouy-sut-6980/`. The trailing `-<id>` is not decoration — it
  guarantees uniqueness even when two titles collide, and it means the OLD path
  `/m/6980/` and the new path share a component, which matters for the migration
  (below). Slug text: prefer `work_title` (curated bilingual working title) where
  present — that is exactly what those 31 textbook rows have and what makes them
  worth a real title in the first place — else `title_english`, else a
  transliteration of `title_thai`. Ascii-fold, lowercase, strip stopwords a reader
  doesn't need in a URL (`a`, `the`, `of`), cap at ~60 chars before the id suffix.

- **Reader pages (`/read/`)**: reuse the manuscript's slug — a reader page and its
  manuscript page are the same work, two views. `/read/<slug>-<id>/`. This is a
  straight lookup (reader ids ⊂ manuscript ids), no separate minting needed.

- **Articles (`/a/`)**: keep the *shape* (already a real slug), fix the *style*.
  Strip the `entity_`/`genre_`/… type prefix from the URL (keep it as an internal
  key, not user-facing text) and swap underscores for hyphens:
  `entity_su_khwan` → `/a/su-khwan/`. Lower priority than manuscripts/readers since
  the current form is at least stable and unique — do this in the same pass as the
  trail-slug fix, not before it.

- **Wats/places (`/place/`)**: no change. This is the reference implementation —
  human, kebab-case, minted once upstream and carried through untouched. Worth
  copying the *mechanism* (slug lives in the source data record, build never
  recomputes it), not just the *look*.

- **Trails (`/trail/`)**: fix the missing-hyphen bug in the bot-slug formula
  (`trails.py` ~line 106: `"bot-" + node["id"].split(":", 1)[1]` needs a separator
  inserted between the category half and the title half). Mechanical, one line,
  but changes 6+ live URLs — needs the same stub treatment as the manuscript
  migration, not a silent rename.

- **Sections and widgets**: no change. Already human, stable, hand-chosen.

**Where slugs are stored — the actual decision:**
A **flat registry file**, not a `catalog.db` schema migration:
`data/slugs_manuscripts.json`, `{ "<id>": "<slug>" }`, checked into git next to the
other `data/*.json` files this repo already treats as build inputs. Reasons over an
`ALTER TABLE`:
1. `catalog.db` is written by the crawler (a separate, actively-running pipeline —
   see `project_lanna_crawler.md`) and read by a dozen modules here; adding a column
   safely needs coordinating a migration across both codebases. A registry file
   needs coordinating nothing — it is purely additive, read-only to everything
   except its own minting script.
2. It is directly diffable and reviewable in a PR — 6,990 lines of `id → slug`,
   one line per manuscript, is a legible artifact; a DB column is not.
3. "Never re-derive from a mutable title" is enforced *by construction*: once a row
   exists in the file, the minting script must skip it, not overwrite it, even if
   `work_title` later changes upstream.

**Which code path mints them:** one new standalone script,
`scripts/mint_manuscript_slugs.py` (mechanical, no model). It reads
`catalog.db` + the existing registry, mints a slug for any id missing one
(collision-checked against everything already minted, `-2`/`-3` suffix on a
literal collision — belt-and-braces on top of the id suffix already making
collisions unlikely), and appends only the new rows. It is run by hand or by a
pre-build hook, **never** by `build_static.py` itself — `build_static.py` and
`manuscript_pages.py` only *read* the registry (`slug = registry.get(str(mid), str(mid))`,
so a manuscript with no minted slug yet degrades to today's numeric path instead of
failing the build). This keeps slug-minting off the hot, frequently-edited,
concurrently-owned build path entirely.

**Migration mechanics (the GH-Pages-has-no-redirects constraint, made concrete):**
`build_static.py` starts writing the new path (`/m/<slug>-<id>/`) as the real page,
and additionally writes a **tiny stub** at the old path (`/m/<id>/index.html`):
`<!doctype html><meta charset=utf-8><title>…</title><link rel=canonical href="…new…">
<meta http-equiv=refresh content="0; url=…new…"><meta name=robots content="noindex,follow">
<p>Moved to <a href="…new…">…</a>.</p>`. This is exactly the "meta-refresh stub"
option named in the brief — it is the standard static-host answer, and it does two
things at once: a human's old bookmark or a Wayback capture lands somewhere real
in zero seconds, and `rel=canonical` tells search engines to consolidate ranking
signal onto the new URL rather than treating it as duplicate content. `sitemap.xml`
should list only the new canonical URLs going forward (`site_meta.py`'s
`build_sitemap`); the old stub paths stay resolvable but stop being *advertised*.

## 3. Metadata design

Per type, what should exist vs. what is missing today:

- **Manuscripts `/m/`** — already close to "spectacular": title, `og:*` incl.
  image, `Manuscript`+`BreadcrumbList` JSON-LD, faithful `imagemeta.py` alt/caption/
  credit. The one gap: the hero image, when present, is the right asset, but there
  is no **per-manuscript share card** distinct from the hero photo for volumes with
  no photograph at all (many crawled records have no IIIF hero) — those currently
  ship the honest "not yet described" note but no `og:image` of their own, falling
  back to the sitewide default. `cards.py`'s `text_card_bytes()` already exists for
  exactly this case (a generic Pillow text card for entities with no photo) but
  is not wired to manuscripts — wire it: `og_image` = hero photo if present, else
  a generated `cards.text_card_bytes(title, genre_label)`.

- **Textbook volumes** — same as manuscripts, but the share card should prefer
  `work_title`/`work_desc` (the curated bilingual blurb) over the raw catalogue
  title/genre when present — that field exists specifically because the raw
  catalogue title is often a bare description, not a real title.

- **Readers `/read/`** — bring JSON-LD in-house (bake it in `wiki.reader_page()`
  the same way `manuscript_pages.py` does, instead of `site_meta.py` patching it
  on after the fact) and add `og_image` — reuse the manuscript's own hero/card via
  the shared slug, so a reader link unfurls with the actual folio, not the sitewide
  yantra. Add `BreadcrumbList` to match `/m/`.

- **Articles `/a/`** — already has everything (title, `og:*`, `Article`+
  `BreadcrumbList`). No metadata work needed, only the slug-style cleanup in §2.

- **Places `/place/`** — already has everything. Reference implementation.

- **Trails `/trail/`** — already has `og_image`/`og_url`; confirm each trail's card
  is actually rendered (`make_card.py`'s convention: PNG committed under
  `publishing/cards/`, copied into `docs/<name>/card.png` at build) rather than
  silently 404ing — worth a `verify_build.py` gate (see §5) since this is exactly
  the kind of "page present but hollow" failure mode `verify_build.py` was written
  to catch for other routes.

- **Sections** — the 20-odd sections with no custom card fall back to the sitewide
  `og.jpg`, which is honest but generic. Each already has a one-line `desc` in
  `routes.py` (used for `<meta name=description>` and crawler text) — extending
  that same registry with an optional `card` field (defaulting to none →
  `og.jpg`) would let a handful of high-traffic sections (`/browse`, `/market`,
  `/wats`, `/expedite`) get a real card cheaply, using the exact `make_card.py`/
  `cards.py` machinery already proven on `/widgets`, `/moon`, `/hotrai`.

- **Per-entity share cards at build time** — the existing convention
  (`make_card.py` renders a master PNG via headless Chrome, committed under
  `publishing/cards/`, copied by `site_meta.py`/`build_static.py` into
  `docs/<name>/card.png`) is deliberately NOT run during `build_static.py` itself
  (`make_card.py`'s own docstring: rasterising needs a browser engine; publishing
  must work without one). For **6,990 manuscripts** that pattern does not scale —
  you cannot commit 6,990 hand-rendered masters. This is exactly the case
  `cards.py`'s Pillow-based `text_card_bytes()` was built for: no browser
  dependency, cache-keyed by a fact that does not change build to build (already
  the documented cache rule), safe to generate inline for every manuscript that
  lacks a real photo, at build time, in Python. Recommend: manuscripts/textbooks
  use `cards.py` (stdlib-safe, scales to thousands); the handful of hand-designed
  section/widget cards keep using `make_card.py` (curated, low count, worth the
  Chrome dependency for the visual quality).

## 4. Sonnet-bot work plan

| Work item | Type | Est. units |
|---|---|---|
| `mint_manuscript_slugs.py` (registry writer) | Mechanical script | 1 |
| Wire slug registry into `manuscript_pages.py` + `build_static.py` read paths, stub-page writer | Main session (shared files: `build_static.py`, `manuscript_pages.py`) | 1 |
| Trail-slug hyphen bug fix + stub for renamed trail URLs | Mechanical, tiny | 1 |
| Article slug cleanup (`entity_x` → `x`) + stubs | Mechanical + main-session wiring | 1–2 |
| Wire `cards.py` text-card fallback into `/m/` og:image | Main session (`manuscript_pages.py`) | 1 |
| Bake JSON-LD + og:image into `wiki.reader_page()` directly, retire the `site_meta.py` patch | Main session (`wiki.py`, `site_meta.py`) | 1 |
| Per-entity **descriptions** grounded in catalogue facts for the ~6,700 manuscripts whose only text is a bare title (no genre-derived sentence yet) | **Cheap parallel model workers** — this is exactly "write a faithful sentence from structured fields," the same job `imagemeta.object_phrase()`/`hero_alt()` already do mechanically; a model pass is only needed where those heuristics produce something thin (undated, no genre, no province) and a human-quality gap sentence is wanted for the `<meta description>`. Batch in ~500-record chunks, each worker given only that record's catalogue fields (extract-don't-author — same rule `imagemeta.py`'s docstring states) | ~14 batches of 500 |
| `routes.py` `card` field + a couple of section cards via `make_card.py` | Main session (`routes.py` is the nav registry, drift-checked) | 1 |
| `verify_build.py` gate: card PNGs present for every route that declares one | Mechanical | 1 |

Rule of thumb used above: anything touching `routes.py`, `build_static.py`,
`wiki.py`, or `manuscript_pages.py` is main-session work, because those are the
files `routes.py`'s own docstring identifies as the drift-checked, shared spine —
parallel workers editing the same file concurrently is exactly the failure mode
`routes.py` was written to stop happening again at the *declaration* level; it is
just as real at the *file-edit* level.

## 5. Risks

- **URL breakage** — the whole point of the stub-page design in §2 is to make this
  close to zero: nothing is deleted, old paths keep resolving, `rel=canonical`
  hands ranking signal forward cleanly. Real residual risk: any *external* system
  that parses the URL rather than following it (an API consumer hard-coding
  `/m/6980/`, not a browser) sees no redirect, since a meta-refresh only fires for
  a browser/crawler that executes it. Worth explicitly deciding to accept this
  (the JSON API at `/api/manuscript/<id>.json` is unaffected either way — it stays
  id-keyed).

- **Repo weight** — 6,990 new stub HTML files (tiny, ~300 bytes each, ~2 MB total)
  plus one slug per manuscript in a JSON registry (~150 KB) is negligible next to
  the existing tree. If per-manuscript Pillow cards are generated for the ~6,700
  photo-less records, that's the real weight to watch: even a modest ~15 KB JPEG
  each is ~100 MB added to `docs/` — confirm whether cards for the numerous public-domain,
  every text sub-cards on-demand-only.

- **Coordination with the concurrent session** — `build_static.py`, `wiki.py`,
  `routes.py`, and `manuscript_pages.py` are all live, frequently-touched files
  (per the `mtimes` seen during this survey, several were edited today). The slug
  registry file and the mint script are designed to be **additive and
  out-of-band** specifically to avoid touching those files until a single,
  reviewed change lands — do not start editing `build_static.py`'s per-manuscript
  loop (~line 630–656) piecemeal while another session may also be mid-edit there;
  land the registry + mint script first (zero collision risk, touches no shared
  file), then do the `build_static.py`/`manuscript_pages.py` wiring as one
  self-contained diff once the shared files are quiet.
