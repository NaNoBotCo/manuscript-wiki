# Work orders — the same decisions, applied to wichaa.net (gemba of 2026-08-17)

> These orders mirror `mot-dang/WORKORDERS-GEMBA-2026-08.md` — one set of
> decisions, two properties. Read that file's standing contracts; they all apply
> here, plus this stack's own gates: `routes.py` drift fails the build,
> `verify_build.py` runs after the FULL pipeline, the privacy grep must stay
> silent, and **the catalogue is opened read-only**
> (`sqlite3 "file:…/catalog.db?mode=ro&immutable=1"`). Bots build and test;
> Nan publishes (`publishing/publish_site.sh`).
>
> Demure and mindful: this is the manuscript stack. Nothing here needs a crawl;
> every order below runs on data already on disk.

## What the gemba found here

- The wat registry stamp is on **6,203 manuscripts** (113 รหัสวัด codes, columns
  `wat_code, wat_sect, wat_rank, wat_founded_ce, …` on the `manuscripts` table) —
  and **zero pages render any of it**. The only consumer in this repo is one
  `wat_name_th` string folded into the embedding text (`search_index.py:121,132`).
- Two wat universes, no join: registry codes (authority, 43,858 rows, **no
  coords**) vs vault place ids (1,459 wats, 100% coords, photos, articles, **no
  codes**). `wats_north.json` reports `withCoordinates: 98`.
- `/place/<id>/` pages **don't mention manuscripts** — while `held_at` × 6,549
  edges already sit in the shipped graph.
- Node articles exist for 3 of 11 axes (38 pages). Province, temple (158), script,
  language, material, era have counts, predicates (`wiki.py:1259-1264`), and no
  page. `content/temple-wat_sung_men.md` is written prose with no route.
- `/browse`'s "Date" sort compares `date_text` **lexicographically** — 3,772 CS
  records cannot be ordered as time, though `taxonomy.era_of()` already decodes
  the era and 4,349 records carry `date_ce_estimate`.
- English natural phrases die in search: "love charm" returns nothing while
  เมตตา manuals fill a genre. The thesaurus (`wiki.py:2251-2276`) doesn't know the
  amulet-function vocabulary that `data/functions.json` already holds bilingually.
- The graph has 126,852 edges but `authored` = 104 and `adjudicated` = 0 — the
  vault-wikilink socket (`cartography.py:469-509`) and the entity-resolver table
  (one entry) are built and empty.
- `/wats` draws on **third-party OSM raster tiles** while mot-dang's self-hosted
  vector basemap covers the same bbox from R2, already paid for.
- `check_articles.py` — the only thing that catches silently-deleted markdown
  links — is **not in the publish pipeline**.

Sequence: **WW-1 → WW-2 → WW-3 first** (render what exists), WW-4 second,
WW-5/WW-6/WW-7 third.

---

## WW-1 — Render the wat registry; bridge the two wat universes

**Why.** The largest enrichment in the stack is already joined and invisible.

**Read first.** `manuscripts` stamp columns (schema in the gemba report),
`wat-registry/README.md` + `match.py` (match discipline, `name_key`),
`build_place_pages.py` (`facets_of()` at `:39-63`), `manuscript_pages.py`,
`cartography.py` (`held_at` layer), `wichaa-vault/scripts/validate.py --strict`
(the vault gate you must keep green).

**Steps.**
1. **Manuscript pages** render the stamp where present: "held at วัดสูงเม่น · Wat
   Sung Men — รหัสวัด 03540401002 · มหานิกาย · วัดราษฎร์ · founded 1840 CE", with
   the ONAB register (BE 2567) provenance line, in the existing facts block. The
   match route (`wat_match_how`) is auditable — carry it in a tooltip/title, not
   body text.
2. **Bridge table.** `scripts/bridge_wat_registry.py`: match vault place ids ↔
   registry codes via `name_key` + province (+ amphoe where the vault note has
   it). Fails closed; ambiguity → review file. Write
   `data/wat_bridge.json`: `{place_id, wat_code, matched_how}`. Expect ~600–900
   of 1,459 — the register is temples only, the vault also holds shrines and
   sacred sites, and a miss is a fact, not a failure.
3. **Vault enrichment (via the vault's own pipeline).** Feed bridged codes +
   `sect/rank/founded_ce` into `wichaa-vault` frontmatter through
   `migrate.py --write` with per-field provenance, so `compile.py` carries them
   into `wats.geojson` → `/wats` and `/place/` pages. Never hand-edit compiled
   files.
4. **Place pages learn their holdings.** In `build_place_pages.py`, for a bridged
   place: count manuscripts by `wat_code`, render "คลังใบลานที่นี่ · The library
   here: 1,805 manuscripts — top genres …" with a deep link into `/browse`
   filtered to that temple, and founded/sect/rank facts. The `held_at` edges
   already exist; this is rendering, not new inference.
5. **Graph**: temple nodes gain `wat_code`; bridge edges ship as
   `same_as` with `prov:"adjudicated"` and the match rule as `ev` — the first
   non-zero adjudicated count.

**Writes.** `manuscript_pages.py` facts block · `scripts/bridge_wat_registry.py` ·
`data/wat_bridge.json` · vault frontmatter via migrate · `build_place_pages.py`.

**Landed 2026-08-17.** Manuscript pages render the stamp (holding temple's
founding year, nikaya, rank, รหัสวัด, with the match route in a title
attribute). `scripts/bridge_wat_registry.py` joins register codes to vault place
ids and `build_place_pages.py` renders the holdings band:
`/place/wat-sung-men/` now reads **"1,805 manuscripts — canonical 1,032 ·
jātaka 358 · grammar 154 · chronicle 147"**, with a working deep link into
`/browse?temple=Wat%20Sung%20Men`.

**The ≥600 target in this order was wrong.** It assumed the bridge should cover
the vault's 1,459 places. It should not: only temples the corpus actually
**cites** are worth bridging, which is the 113 distinct `wat_code` values on the
manuscripts. **58 of those 113 matched, covering 4,259 manuscripts** — that is
the number that matters, and 54 are in `cache/wat_bridge_review.txt`.

Two things found on the way, both worth acting on:
- **The vault holds 8 temples twice** — one curated note and one OSM-derived
  record for the same ground (วัดลี: `wat-li-chiang-rai` and `wat-li-phayao`,
  both province Phayao, 44 m apart; วัดพันอ้น: `wat-phun-ohn` and
  `osm-way-695790006`). The bridge folds them, keeps the curated slug, and logs
  every pair to `cache/wat_vault_duplicates.txt`. **Folding them at source
  would tidy `/wats`, the place pages and the graph at once.** Note also that
  `wat-li-chiang-rai` is a misnamed slug for a Phayao temple.
- **The link had to use the catalogue's own temple string**, not the register's
  Thai name — `/browse` filters on `provenance_temple` ("Wat Sung Men"), so
  linking with "สูงเม่น" would have landed every reader on an empty shelf.

**Still open on this order:** the vault-frontmatter enrichment (step 3) and the
graph's `same_as` adjudicated edges (step 5) are not done. The bridge file they
both need is now on disk.

---

## WW-2/WW-3 — landed 2026-08-17

**WW-2.** `articles_index()` now enumerates the axes it always resolved but
never listed: **38 article doors → 194** (135 temples, 13 genres, 10 provinces,
8 scripts, 6 subgenres, 19 entities, 3 materials).
`content/temple-wat_sung_men.md` has a page for the first time. Two vocabulary
traps were refused rather than shipped, and both should stay refused:
- `provenance_temple` carries districts ("Mueang District", "Sung Men
  District"), bare provinces ("Phrae") and institutional holders (Siam Society,
  Nan Provincial Museum). They are real holders and **not temples**; a
  `Wat|วัด` gate keeps them out of the temple directory.
- **Language is deliberately absent.** `SUBJECT` resolves it by exact match on
  the raw column, which would publish "Monolingual Pali" and "Pali and Lan Na"
  as nodes while `/browse` counts the eleven canonical languages
  `taxonomy.language_components()` splits them into. Two vocabularies for one
  axis is worse than one door fewer. It wants `node_predicate`, which is its
  own piece of work — **the next thing to do on this order.**

**WW-3.** `taxonomy.date_sort_ce()` converts CS (+638) and BE (−543) to a common
era, and `/browse`'s date sort uses it instead of comparing date strings as
text. **4,350 of 6,990 are datable**; CS 833 → 1471 CE, so the Wat Lai Hin Luang
scripture now sorts first, as the front page has always claimed. The 2,640
undated records keep their place at the end in title order and are never given a
year. The control reads **"Most ancient first"**.

**Not done from WW-3:** step 4, the Vectorize metadata (era, century, province,
`wat_code`) and the Worker-side filters. That is a re-index and belongs in its
own run.

---

## WW-2 — Node articles for every axis (the directory grows)

**Why.** The Yahoo-directory nav is the house style, and 8 of 11 axes have no
door. The machinery (`NODE_BROWSE_KEY`, `node_predicate()`,
`wiki._reverse_index()`) already resolves them — `articles_index()`
(`wiki.py:2740-2795`) just doesn't enumerate them.

**Steps.**
1. Extend `articles_index()` to emit province (10), temple (158 — seeded from the
   registry stamp: founded, sect, rank in the header facts), script (8), language
   (9), material (3), era (3). Computed facts + facet counts + graph threads +
   deep links into `/browse`; prose renders where a `content/*.md` file exists
   (`temple-wat_sung_men.md` finally gets its page) and is absent otherwise —
   never generated filler.
2. Directory listings render Term (count) style per the house nav rule, with the
   quiet delights intact.
3. Raise `verify_build.py` expectations to cover the new namespace count.
4. Run `scripts/check_articles.py`; fix what it catches; then **WW-7 step 3 wires
   it into the pipeline** so it stays fixed.

**Writes.** `wiki.py` (`articles_index()`, article template plumbing) ·
`verify_build.py` counts.

**Acceptance.** `/a/` count 38 → ~226; every axis page's counts equal `/browse`
facet counts for the same key; `check_articles.py` exit 0; no page ships
model-written prose.

---

## WW-3 — Ancientness as a real axis (time sorts as time)

**Why.** The CS/BE seam is "the seam the whole project is built around"
(`taxonomy.py:193-215`) — and the date sort is lexicographic.

**Steps.**
1. Build-time `date_sort_key` per manuscript: prefer `date_ce_estimate` (4,349);
   else decode `date_text` era — CS year + 638 (Eade, *Calendrical Systems of
   Mainland South-East Asia*, the conversion the astro work already cites), BE −
   543 — with a `date_sort_source` marker; undated → absent, never invented.
2. `/browse` "Date" sort uses the key: `โบราณก่อน · Most ancient first`, dated
   records first in true order, undated below in title order, count of undated
   stated plainly ("2,599 await a date").
3. Era/century chips already exist in facets — link the browse header year-range
   readout to them so the axis is visible, not buried.
4. **Vectorize metadata**: add `era`, `century`, `province`, `wat_code` to stored
   metadata in `search_index.py` (stay inside the metadata size cap — drop
   nothing that's there today), and accept them as filters in
   `cloudflare-mirror/src/index.js` `serveSearch()` so "protection yantra, CS
   era, Phrae" is one query. Re-run the index build incrementally (`--since`).
5. `/browse` and `/search` share chip vocabulary — same labels, same counts.

**Writes.** `wiki.py` sort + browse JS · `search_index.py` metadata ·
`cloudflare-mirror/src/index.js` filter params.

**Acceptance.** Date sort is chronological (spot-check: 1471 Wat Lai Hin Luang
scripture first); undated count stated; filtered semantic query returns only
matching-era records; existing search regression (ยันต์กันภัย → yantra manuals,
not ภัยยะราด) still holds.

---

## WW-4 — One thesaurus, both searches, doors on empty

**Why.** "love charm" fails while `functions.json` holds เมตตามหานิยม/โชคลาภ
bilingually with counts. The lexical and semantic paths each have half the fix.

**Steps.**
1. Grow `_thesaurus()` groups from the three vocab files: every
   `functions/classes/materials.json` entry contributes its Thai name, English
   gloss, and transliteration as one group (love charm / เมตตา / metta /
   maha niyom; luck / โชคลาภ / chok lap; …). Keep groups curated in one data
   file consumed by `_thesaurus()` — not scattered literals.
2. The Worker's lexical re-rank (`index.js:173-196`) expands query terms through
   the same thesaurus (inline the JSON at deploy or fetch `api/thesaurus.json`
   with a long cache) — so the +0.25 title bonus fires on เมตตา when the reader
   typed "love charm".
3. Empty state on `/search`: keep the directory door, add function/genre chips
   with counts ("เมตตา · love & favour (566 in the market, 9 manuals)") sourced
   from the vocab files — doors, never a dead end.
4. Example chips on `/search` get one natural-English phrase ("love charm") so
   the pattern is taught by example.

**Writes.** thesaurus data file + `wiki.py:2251-2276` · `index.js` re-rank ·
search page chips.

**Acceptance.** "love charm" returns เมตตา manuals through **both** paths (client
lexical and `/api/search`); ยันต์กันภัย regression holds; empty states show
counted doors.

---

## WW-5 — The amulet lattice: วัด × รุ่น × พิมพ์ × เนื้อ, phased

**Why.** The four-axis browse is the stated shape of the market corpus and none of
it is crossable today. Three axes have data (`cls:` 1,587+ / `fn:` 575+ /
`mat:` 418 in `tags.topic`); two (รุ่น, พิมพ์) have none anywhere.

**Steps.**
1. **Phase 1 (now):** `/market` gains facet chips for class / function / material
   from `tags.topic`, AND across axes, OR within, counts stated with the gap
   plain: "1,587 classed · 11,433 not yet classed". Untagged is silence, not "no".
2. **Phase 2:** two detectors in the crawler's vocab pipeline (pattern:
   `vocab_candidates`) mining listing titles for `รุ่น <token>` and `พิมพ์
   <token>`; reviewed candidates land as `run:` / `pim:` topics. Review file, not
   auto-tag — market Thai is noisy.
3. **Phase 3:** the วัด axis — match listing `location_text` against registry
   `name_key` (adjudicated, fails closed, review file). Where it lands, an amulet
   joins its temple node — and its temple's manuscripts — in the graph: the
   antique↔current seam, crossed at last.
4. Keep the no-prai / no-tiger / no-ivory exclusions of the clearinghouse work in
   force on any new browse surface.

**Writes.** market page facets · two crawler detectors · match script + review
files.

**Acceptance.** P1: chips filter 13,020 items client-side with stated coverage;
P2: ≥50 reviewed รุ่น/พิมพ์ values before any UI; P3: zero guessed temple
matches; graph gains `item → temple` edges only through the adjudicated route.

---

## WW-6 — Maps: one basemap for the family; places get locators

**Why.** `/wats` fetches OSM raster tiles from a third party; mot-dang serves a
vector basemap of the exact same provinces from its own R2 bucket. And 1,494
place pages have coordinates and no map.

**Read first.** `wiki.py:7660` (`WATS_PAGE`), `:7961-8035` (`initMap()`),
`mot-dang/data/basemap.json` (the pmtiles URL + verified Range/CORS),
`mot-dang/data/basemap_style.json` (14 layers), `mot-dang/map_shell.py` (the
drawn-SVG-first mount — the pattern, not an import), `build_place_pages.py`.

**Steps.**
1. **Basemap switch on `/wats`.** Style JSON porting mot-dang's 14 layers, source
   = the shared pmtiles URL (`pmtiles://` protocol, `vendor/pmtiles.js` copied
   the way maplibre already is), glyphs as mot-dang configures them. Keep the
   four data layers (`w-s/w-n/w-h/w-label`) untouched on top. Keep the
   150 ms-retry robustness. The OSM tile host leaves the page entirely;
   attribution updates to Protomaps/OSM-data lines.
2. **Degrade state.** `basemap url == ""` (or unreachable) → the grid and list
   remain the page; the map panel says so plainly. Low vision is a first-class
   case: the linked list under the map stays, always.
3. **Place locators.** `build_place_pages.py` gains a drawn-SVG locator per
   place (port the mot-dang `place_map()` pattern: neighbour dots **as links**
   from the graph's `near` edges (1,236), leader-line label placement, drawn
   first, live tiles mounted under). `imagemeta.py` composes the alt text — it
   is currently unused by place pages; that ends here.
4. **Cross-site chip.** On bridged places (WW-1), render "ในสารบัญเมือง มดแดง ·
   in the Mot Dang city directory →" using mot-dang's `data/wichaa_links.json`
   pairs (copy the file into this repo's `data/` at build; mot-dang already
   links back). Two sites, one graph, visible seams.

**Writes.** `wiki.py` wats map block · style JSON in `data/` · `build_place_pages.py`
locators · vendored `pmtiles.js`.

**Acceptance.** `/wats` makes zero requests to `tile.openstreetmap.org`; place
pages show locators with clickable neighbours and composed alt text; scripting
off, the drawn SVG and the list still say everything; bridged places link to
mot-dang and back.

---

## WW-7 — Fill the empty sockets; wire the missing gate

**Why.** The graph's human tiers are built and empty (`authored` 104,
`adjudicated` 0 before WW-1), and the one checker that catches silent link
deletion is manual.

**Steps.**
1. **Wikilink proposals, human-approved.** `scripts/propose_wikilinks.py`: from
   computed evidence only (near < 300 m, shared `walk_cluster` candidates, same
   festival, shared holdings), write suggestions to a review file *in vault
   inbox style* — Nan (or a reviewing human) pastes accepted ones into the
   notes. Bots never write `[[links]]` into vault notes directly; `authored`
   stays human, per the cartography contract.
2. **More adjudicated resolvers.** The tested-alias audit trail in
   `wiki.py:1157-1204` (assa / ma sang / phrommachat rejections) already
   documents the hard cases — promote 3–5 entities to written resolver rules in
   the crawler (the `rahu_seed.py` pattern: cite the rule, fail closed, name the
   false-positive ids the rule excludes).
3. **Pipeline wiring.** `publish_site.sh`: run `scripts/check_articles.py`
   between build and `verify_build.py`; its exit-1 (provably-missing link
   targets) halts publish. Its warnings print; they don't halt.
4. **Route hygiene note** (no action this order): the eleven build-path-less
   routes (`/hun`, `/jovilabe`, …) stay on the `UNMANAGED` preserve list; any
   future order touching them starts by reading `build_hun.py`'s docstring and
   the 2026-07-28 incident it records.

**Writes.** proposal script + review files · resolver rules in crawler ·
`publish_site.sh` one line.

**Acceptance.** A proposals file exists with ≥50 evidenced suggestions and zero
auto-applied; adjudicated resolver count ≥4 with named exclusions; a build with a
deleted content link fails at the new gate; `/hun` and friends still stand after
a full pipeline run.
