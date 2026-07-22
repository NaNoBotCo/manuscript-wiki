# Priorities — future work

A durable list of known deficiencies and directions, so nothing raised in passing
gets lost between sessions. Add to this; don't let it go stale — strike items when
done, with the date and what shipped.

---

## Open

### Privacy gate runs too early in the publish pipeline (noticed 2026-07-13)
`build_static.py`'s privacy gate (scans build output for `/Users/`/`/home/` paths,
aborts if found — added after the 2026-07-13 leak, see project memory
`project_wichaa_privacy_incident`) runs at the END of `build_static.py` itself. But
`glossary.py` and `na_gallery.py` (and any future post-build generator) run AFTER
that, writing more files into `docs/` that the gate never re-scans. Today's publish
was checked by hand (na_gallery/na_compendium output confirmed clean, no absolute
paths), but that's a manual check, not a guarantee for next time. Fix: move the
privacy scan into `site_meta.py` (or a final step in `publish_site.sh`) so it runs
LAST, after every generator has written its files — catches a leak from ANY script
in the pipeline, not just build_static.py's own output. Not started.

### The map is deficient (flagged by NaN, 2026-07-12)
`/map` is a plain SVG dot-map, and it's underselling the corpus:

- **Only 10 provinces are plotted.** `places_snapshot()` in wiki.py sizes dots from
  `PROVINCE_COORDS`, a small hand-coded lat/lon table. Everything else falls to
  "unplaced" — currently **43 distinct provenance labels, 160 manuscripts**, mostly
  district- and temple-level strings (`Sung Men District`, `Wat Lai Hin Luang`, `Wat
  Chiang Man`…) that never make it onto the map at all, just a footnote count.
- No real basemap, no zoom, no pan — just proportional circles on a flat SVG canvas.
- No temple-level pins even though `provenance_temple` is a real, populated field —
  the map only operates at the province level, so "where exactly did this come
  from" isn't answerable without leaving the page.
- Clicking a dot jumps to `/browse?province=`, losing the visual context — no
  hover preview, no in-place manuscript peek.

**Worth doing, roughly in order of leverage:**
1. Expand `PROVINCE_COORDS` (or replace with a geocoded lookup) so far fewer than
   43 labels fall to "unplaced" — most are resolvable Northern Thai districts.
2. A real basemap (even a simple static Thailand outline) instead of a bare
   coordinate projection, so the geography reads at a glance.
3. Temple-level pins where `provenance_temple` is known, nested under their province.
4. Hover/click preview of a place's manuscripts in-page, not just a browse-filter jump.

Not started — flagged for a future session with the budget to do it properly rather
than a rushed pass.

### Research question: which wats (esp. northern) are known for charming gambling amulets? (asked by NaN, 2026-07-12)

**Not answerable from the corpus as it stands** — the two datasets that look relevant
don't actually cover this:

- `provenance_temple` (158 distinct values on manuscripts) records where an *old
  manuscript was held*, not which temples have a *living reputation* for consecrating
  gambling luck today. Different question, easy to conflate.
- Market crawl vocabulary already has `เรียกทรัพย์` (wealth-calling) and `โชคลาภ`
  (fortune) tagged from listings, but nothing gambling-specific — no `หวย` (lottery),
  `พนัน` (gambling), `เลขเด็ด` (winning numbers), `ไฮโล` (dice) — and no detector
  linking a temple/monk name to that vocabulary even where it exists.

**Extract-don't-author matters especially here**: reputational claims about specific
temples are exactly the kind of thing a bot must never assert from an LLM's training
priors — it's the fabricated-ajarn failure mode by another name. A named wat's
reputation has to come from what real listings/sources actually say, not be generated.

**Concretely, to make this answerable:**
1. Add gambling-luck terms to `crawler/sources/lazada.py` `DEFAULT_QUERIES` (currently
   just 4 broad terms) — `เลขเด็ด`, `หวย`, `พนัน`, `ปลุกเสกหวย`, `เบอร์มงคล` — and re-run
   `fresh_market_crawl.py` so listings naming a monk/wat for gambling luck actually
   enter `items`.
2. Add a `curiosity.py` detector (pattern like `market_royalty`/`antique_modern_echoes`)
   that looks for temple/monk names co-occurring with the gambling-luck term set in
   listing titles — surfaced only where the *data* shows the pattern, confidence tied
   to how many independent listings name the same wat.
3. Separately, this may need a real web-research pass (news, Thai amulet forums,
   travel/temple-guide sources) rather than pure Lazada-listing mining — reputation
   like this often lives in text that never appears as a product listing. If done,
   cite sources explicitly; don't let a bot's synthesis read as established fact.

**A few leads worth checking, not asserted as fact** — offered as starting points for
whoever picks this up, explicitly *not* verified: San Chao Pho Suea (Bangkok) has a
well-known general reputation among gamblers/traders; Wat Ban Rai's Luang Phu Khoon
amulets are bought heavily before lottery draws nationwide. I do not have confident,
specific knowledge of a Northern-Thai temple with an equivalent reputation — that gap
is itself the reason this is worth a real research pass rather than a guess.

Not started.

### Archival growth is stalled — gemba findings (NaN, 2026-07-12: "we're behind on amassing our archival collection")

Investigated with live test-crawls (not guesswork) before concluding anything. Three
separate findings, not one problem:

1. **DLNTM (CrossAsia) and EFEO are metadata-EXHAUSTED, not throttled.** Both show
   `status='crawled'`. Live-tested by running crossasia with `--max-pages 280` (vs
   the scheduled 3) and efeo with `--max-pages 50` — **0 new manuscripts** either way.
   6,582 + 377 = 6,959 manuscripts already IS the whole available metadata from these
   two sources as of today. Nothing more to gain here by crawling harder — this is
   not where "behind" comes from.

2. **The real image-archival gap: only 1,382 of 6,959 manuscripts (≈20%) have a
   locally-downloaded image; 5,200 have only an IIIF pointer.** IIIF-on-demand means
   they still *display* fine on the site, but nothing is actually preserved/owned —
   pure metadata + a live link to someone else's server. For a "for posterity"
   project this is the real shortfall, and:

3. **It's currently blocked at the infrastructure level: the external store drive
   died today (2026-07-12).** `crawler/store` (was a symlink to `/Volumes/Passport5TB`,
   see [[project_image_store_hd]]) is now a plain empty local directory — the drive
   isn't mounted. `download-A`/`download-B` (the jobs that would grow local image
   coverage) are still `enabled: true` in the scheduler and have a job note someone
   already wrote acknowledging this ("drive died 2026-07-12; auto-stops at 5 GB
   free, resumes when space appears") — so they're running but almost certainly
   writing nowhere useful, or failing/no-op'ing, until the drive is reconnected or
   replaced. **This should be the first thing fixed** — everything else here is
   secondary until storage exists again.

4. **The real opportunity for NEW archival material: 18 candidate sources already
   identified, zero crawled.** `crawler/sources/landscape.py` (built earlier, from
   a recon of thaimanuscripts.de + SEALG) seeded the `sources` table with 18 known
   Thai/Lao/SE-Asian manuscript digital collections at `status='discovered'` or
   `'not_crawled'` — a real shopping list, not a cold start. Two were actually
   live-tested this session (not just named); findings below are verified, not guessed.

   **EAP691 "Buddhist Archive of Luang Prabang" (Endangered Archives Programme,
   British Library) — CONFIRMED real, on-topic content, discovery mechanism blocked.**
   - Verified via a real record (`EAP691/2/1`): genuinely tagged
     `script: Tai Tham (Lanna)` + Lao, 1,684 TIFF images, dated 17th–20th c., rich
     provenance (temple: Vat Suvanna Khili, coordinates, subjects).
   - IIIF Presentation API v3 manifests are confirmed openly fetchable per-item
     (`https://eap.bl.uk/archive-file/{id}/manifest` → real JSON, no wall) — same
     shape as CrossAsia.
   - **Licensing is stricter than CrossAsia**: manifest `requiredStatement` says
     material "may not be copied or distributed further"; the companion BL Archives
     Catalogue record says "Access is for research purposes only," `legal_status:
     Not Public Record(s)`. → any integration MUST be metadata + on-demand-IIIF-link
     only (same pattern already used for CrossAsia's 5,200 un-downloaded manuscripts)
     — never feed into `download-A`/`download-B`.
   - **The wall: enumeration.** eap.bl.uk's own search/browse HTML is behind an AWS
     WAF challenge (scripted requests blocked; only the per-item `/manifest` JSON is
     open, which needs known IDs first). The companion BL Archives Catalogue
     (`searcharchives.bl.uk`, Blacklight-based) has a genuinely open per-record JSON
     API (`/catalog/{id}.json` — confirmed working, rich ISAD(G) hierarchy fields
     including `project_collections_ssim`, `ancestor_ssim`, `direct_child_title_ssm`)
     — but every attempt to actually *filter/search* it (facet params `f[field][]=`,
     several encodings tried) returned the same unfiltered ~2.4M-record firehose, not
     respecting the query. No OAI-PMH endpoint found at guessed paths either.
   - **What it would take:** either careful reverse-engineering of the real Blacklight
     query format (inspect actual browser network calls against searcharchives.bl.uk
     to find the correct param shape — the API clearly exists and works, I just
     didn't find the right incantation), or a Playwright-based crawler driving
     eap.bl.uk's search UI directly (same technique as `lazada.py`) and using the
     confirmed-open manifest endpoint for the actual data once IDs are known.

   **CMU Digital Heritage Collection (Chiang Mai University) — promising, license
   matches CrossAsia, also blocked by discovery.**
   - 1,214 "Heritage Manuscripts" per public description, explicitly Northern-Thai
     heritage, **CC BY-NC 4.0** — same license posture as CrossAsia, cleaner than EAP.
   - Best topical/institutional fit — the actual Chiang Mai University library.
   - **The wall:** `cmudc.library.cmu.ac.th` is a client-side JS SPA — the fetched
     search-results HTML ships literal unrendered template syntax
     (`{{value.author_id}}`) instead of real data, meaning manuscript listings load
     via an AJAX call to an endpoint not found by inspecting the page source alone
     (likely defined in an external JS bundle). Home page confirmed reachable (200,
     real content shell); no anti-bot wall detected, just genuinely dynamic rendering.
   - **What it would take:** either dig through the site's JS bundles for the real
     API endpoint, or a Playwright-based crawler (same as EAP option above) — likely
     the *easier* of the two once someone's willing to open dev tools against the
     live site, since there's no WAF fighting back, just a SPA.
   - Precise Lanna/Tai-Tham content depth within the 1,214 items is NOT yet confirmed
     (only the collection-level description is known) — worth checking before
     committing to a full crawler build.

   Remaining un-investigated: British Library Digital Library of Thai Manuscripts,
   Digital Library of Lao Manuscripts, NIU SEA Digital Library, SAC (Bangkok),
   Chester Beatty (Dublin), Bodleian Senmai (checked — turns out to be a
   *finding-aid/index only*, not an actual digital library; low priority as a direct
   image source, though useful as a discovery layer pointing at other collections),
   PNTMP (own docstring flags a broken/mismatched TLS cert — technical red flag),
   SEALG (a mailing list/directory, not a collection — skip).
   No crawler module exists yet for any of these — only `crossasia.py`/`efeo.py`
   (+ non-manuscript comparanda `cma.py`/`met.py`/`smithsonian.py`/`lazada.py`).

**The pattern worth remembering:** CrossAsia's clean open-JSON-API shape is the
*exception*, not the rule. Every other candidate checked so far (EAP, CMU) needs
either real API reverse-engineering or a Playwright/headless-browser crawler —
budget for that, not a CrossAsia-style quick build, when picking this up.

**Recommendation, in order:** (a) get the external drive reconnected or replaced —
until then, downloaded-image growth is capped near zero regardless of anything else;
(b) commit real time (a session, not a quick add) to EITHER EAP691 (confirmed
on-topic, stricter license) OR CMU (license matches CrossAsia, topical fit
unconfirmed) — both need Playwright-class effort now that discovery is understood
to be the hard part; (c) the rest of the 18 as time allows, source-by-source.

Not started — needs a session with dedicated build time; this session did real
reconnaissance (live-tested, not guessed) but the user chose to stop before building.

### Feedback from dr in #skynets-basilisk (read 2026-07-12 evening, first outside review of wichaa.net)

Overall reception: *"Oooh. I like this."* Then three concrete items:

1. **Mobile responsiveness — the header doesn't compact.** "I have to scroll
   horizontally." (Two screenshots attached in the thread; one shows the
   relationship-graph page.) The wiki's `header` is a flex row that never
   collapses; on a phone the nav pushes the viewport wide. Needs a real
   responsive pass over `STYLE` in wiki.py: collapsing/wrapping nav, fluid
   type, no fixed-width elements. dr's process suggestion: "write a spec first,
   then make the changes" — a UX spec before touching CSS would suit this.
2. **"167 of 167 pages digested" reads as pipeline metadata leaking into the
   UX.** dr: nobody cares how many pages were *digested*; they care how many
   pages there *are*. NaN's answer in-thread: it's deliberate — digestion
   progress is the donation story — **"i should probably be more explicit"**
   and **"i'll add something about it next session."** So the fix is a
   REFRAME, not a removal: make progress bars explicitly a sponsorship story
   ("X of Y pages read by the bots — sponsor the rest"), linked to Ko-fi,
   instead of bare pipeline counts. Ties into the sponsored-TRANSLATE quotes
   that already exist per-volume.
3. **The donation pitch NaN made in the thread, verbatim commitments worth
   shipping:** raw collection is done but only minimally processed (2 textbooks
   deep-processed); ~30k major files have no digitization beyond flat images;
   there's an opportunity to train a Khom/Tham-Lanna handwriting+translation
   model (sources exceedingly hard to find); and **"you get to watch the bots
   work if someone donates"** — the live activity feed as the donor's reward.
   The site should say all of this somewhere a visitor actually reads it.

Status: **item 1 DONE** (2026-07-12, see Done log); items 2–3 not started.

---

## Done (log, don't delete)
- 2026-07-13 — **Social sharing.** (1) **Share bar on every page** (`_SHARE` in the
  page() template, bottom-left, mirrors the back-to-menu pill): Copy-link, X, Facebook,
  **LINE** (Thailand's dominant channel), Telegram, + native share on mobile. Hrefs are
  built at CLICK time from `location.href` + `document.title`, so on the SPA pages (title
  set by JS) the share still carries the right page. Exposes `window.__share(url,title)`.
  (2) **Per-card share icons** — a share button on every browse manuscript card (6,990)
  and every profile card, sharing that item without opening it (stops the card-link
  navigating). Market cards skipped (external listings, no own on-site page — the page
  bar covers /market). (3) **Per-page share CARDS**: extended `_meta`/`page()` with
  `og_image`/`og_url`; reader pages now emit per-manuscript og:title + og:description +
  correct og:url, so a shared reader link unfurls with THAT manuscript's title and blurb
  instead of the generic card. Verified on the live wiki (share bar renders + functions,
  6,990 card buttons capture the right url/title without navigating, reader OG per-ms).
  KNOWN GAPS / follow-ups: (a) **manuscript DETAIL (/m) share cards stay generic** — it's
  one SPA shell for all ~7,000 mss and crawlers don't run JS; per-manuscript detail cards
  need per-id pre-rendered HTML (like /read/N) + changing ~20 `/m?id=` link sites — a
  bounded but invasive follow-up. (b) **Per-manuscript folio as og:image** — the static
  export ships only a subset of plate PNGs, so /pimg/<mid>/<page>.png 404s for some
  volumes; needs a guaranteed-exported per-ms cover before it's safe to use.
- 2026-07-13 — **P5 performance (dr work-brief).** searchdocs.json (19 MB) was ALREADY
  lazy — verified a cold browse load fetches only img-iiif + manuscripts, never
  searchdocs (shim loadDocs is memoized; browse searches on input ≥2 chars). The real
  per-page bloat was **img-iiif.json (2.6 MB) loaded eagerly on EVERY page** by the
  shim's top-level `loadIIIF()`. Made it lazy: fetch on the FIRST `/img?sha=` image, with
  a loading guard. Verified in a served build — /support & homepage (image-free) fetch
  ZERO img-iiif; /browse (6,612 images) fetches it on first render. Graph page renders no
  scan images, so it too now loads nothing heavy. Deferred: sharding the 19 MB index
  (gzip already helps; 0-bytes-until-used met) and per-file cache-versioning (GH Pages
  has a 10-min TTL). 
- 2026-07-13 — **P4 funding surface (dr work-brief).** The highest-traffic page (home)
  had no funding CTA. Added, tastefully (tam-boon, beside-the-value not a gate):
  **homepage** — a "☕ Tam boon" hero button, a tam-boon section after the maker's note
  (real price $0.06/pg, "watch the bots", Make-merit Ko-fi button styled for the dark
  section), and a footer Ko-fi. **New /support page** (in nav, replacing the raw Ko-fi
  nav link): the WHY (free-forever, tam boon), price boxes, "sponsor a translation" with
  the `TRANSLATE <id>` Ko-fi message format, the backlog/HTR story, and **commissions**
  (mailto — result still enters the free archive). **Per-manuscript CTA** on /m: images
  but no transcription → "Sponsor it being read ~$0.06/pg → /support". **llms.txt** gained
  a Support section + dropped the dead /map link + Articles→Profiles. **Public repo**: added
  README.md (with the tam-boon pitch) + .github/FUNDING.yml (Ko-fi sponsor button) —
  committed & pushed. All verified in a served build. Overlaps/supersedes the earlier
  paused funding-surfaces plan (that plan's approved copy was reused here).
- 2026-07-13 — **P2 prune & reorganize (dr work-brief).** Reduced nav sprawl / dead
  pages. Cuts: **/w/traffic** dropped (all-zeros live-only widget); **/map** removed
  (6-dot SVG; province is a facet on /browse, and the geo widget is the real map now —
  linked from /market + homepage "Map" repointed to /w/geo); **/dashboard** unexported
  (duplicated /status). **One canonical nav**: dropped the "Widgets" tab, relabelled
  "Articles"→**"Profiles"** (they're auto-computed subject profiles, not authored
  essays — page copy updated too), and replaced the two stale inline navs (manuscript
  detail + crawl status still linked the deleted /dashboard,/lens) with the shared NAV
  constant. **api/index.json** already exists (site_meta machine-readable API index) —
  P2.8 intent met via that + single-source NAV. **Privacy gate hardened** (P2.9): added
  a FINAL scan in publish_site.sh that runs AFTER every generator (glossary/na_gallery/
  site_meta) and refuses to publish if any /Users//home/$HOME path survived — closes the
  gap where build_static.py's own gate ran before those generators.
  Decisions/limits (honest): **/lens & /explore kept** — neither is a pure /browse
  duplicate (explore=overview counts/facets, lens=thematic views); delinking would lose
  working curated pages. **prices/regions widgets NOT ported into /market** — the market
  page already carries native price/term/regional/temporal trends (trendsBand); the
  standalone widgets remain shareable at /w/. Verified: scratch build has the removed
  pages gone, kept pages present, **zero dead links** to deleted routes, privacy gate
  passes; live wiki navs confirmed (Profiles in, Widgets/dashboard/lens out); market geo
  link renders. Auto-publishes within the hour.
- 2026-07-13 — **P0 privacy leak (from dr's work-brief gemba): FIXED + purged.**
  `api/build-info.json` + `api/status.json` were publishing the build machine's
  absolute path — `/Users/<realname>/Desktop/…` — on wichaa.net (real name + local
  layout, during litigation). Fix: `status_snapshot()` (wiki.py) and the build-info
  writer (build_static.py) now emit **basenames only** (`catalog.db`/`store`), field
  shape unchanged. Added a **build-time privacy gate**: build_static.py aborts the
  publish if any `/Users/`/`/home/`/home-path string reaches the output tree. Rebuilt +
  redeployed (live JSON verified clean via cache-busted fetch). **Git history rewritten**
  with git-filter-repo + force-push; fresh clone from GitHub confirms 0 occurrences of
  name/path across all 50 commits. Old (leaking) history saved locally at
  `Developer/claude code projects/Lanna-history-backup-20260713-091514.bundle` (keep
  private; delete when confident). RESIDUALS (out of our hands): GitHub may keep old
  commits reachable by SHA until it GCs (ask Support to purge); any forks keep old
  history; web archives may have snapshotted it.
- 2026-07-13 — **P1 dead-link system (DB-backed, not CI).** The brief specced a GitHub
  Action, but the site is built locally from catalog.db (hourly LaunchAgent), so a CI job
  writing to docs/ would be clobbered. Built it where the crawler lives instead:
  `manuscript-crawler/linkcheck.py` — a scheduler job that HEAD/GETs commerce source_urls,
  throttled, and stamps `items.dead_since`/`link_checked` (new columns, idempotent
  migration). **Classifier uses a POSITIVE signal** (presence of `pdpTrackingData` product
  payload), NOT a "not found" string — verified the hard way: Lazada's LIVE HTML contains
  "ไม่พบสินค้า" as boilerplate, so the naive text test marked every live listing dead
  (measure-don't-guess, again). Dead only on 404/410 or redirect-off-product-path; bot-wall
  / ambiguous = inconclusive (left alive, re-checked); aborts a run without writing if the
  dead-rate is implausibly high (bot-wall guard) or after 5 consecutive 429/403. Scheduler:
  `linkcheck-market` weekly + `linkcheck-iiif` monthly (report-only). Build/site consumes
  it: `market_snapshot()` exposes `deadSince` (defensive — tolerates a DB without the
  column); the market page HIDES listings dead > 30d by default, with a toggle, an
  "🗄 archived" badge, and "source listing gone" in place of the dead link — never deletes
  (dead listings stay as price history). Verified end-to-end (marked one item dead 60d,
  confirmed hidden→toggle→shown, then reverted). Also repointed the homepage's hardcoded
  Lazada PDP link (would rot) to a durable Lazada **search** for the charm type.
  NOT DONE (optional, noted): a separate `api/linkcheck.json` summary + auto-GitHub-issue
  (CI-flavored; the market page's archived count already surfaces the state), and
  per-manuscript IIIF dead badging (manuscripts already degrade gracefully).
- 2026-07-12 — **Three navigation/link bugs** (NaN report: "on-page navigation not
  good — no way back to menu after scrolling; 404s persist on menu-bar items; 'view
  at source' links all seem dead"):
  1. **No way back to the nav after scrolling.** Added a floating "▲ Menu" pill to
     the shared `page()` template (`_TOMENU` + `#tomenu` CSS in STYLE): hidden until
     you scroll >320px, then smooth-scrolls to top where the header nav lives.
     Sitewide (every page uses `page()`), 44px tap target, hidden in print. Verified
     on a widget page: appears on scroll.
  2. **Widgets menu item 404'd on wichaa.net.** `/w/` and `/w/<name>` (geo/prices/
     regions/trends) plus `/api/w/*.json` were served by the live wiki but never
     written by `build_static.py` — same export-gap class as the earlier /read and
     /diagrams bugs. Added a widgets export block (index + 4 data pages + JSON dumps
     + geo.geojson) and two shim rules: `/api/w/<name>` → `<name>.json` for fetches,
     and the same rewrite for the "⬇ JSON" download links. `traffic` is live-only
     (counts requests to the running server) so it exports a page with an empty
     snapshot that renders its honest "no traffic recorded" state, not a frozen
     number. Verified in a scratch build: all `/w/*` routes 200, geo widget renders
     77 province circles with real totals.
  3. **"View at source" links all dead.** CrossAsia changed their site: the stored
     `source_url` (`/s/lanna/collections/…`, on all ~6,960 crawled mss) now 404s
     (page title "Search"), and 30 contributed volumes carry a dead `local:` path.
     The IIIF manifest URL (`/madoc/api/manifests/…/export/source`) still resolves
     (200 JSON, canonical library record). Rewrote the DETAIL_PAGE link JS to make
     the manifest the "View at source library (IIIF)" link and suppress `source_url`
     when it's `local:` or the dead collections route. Verified: crawled ms shows one
     working IIIF link, contributed ms shows zero dead links.
  Fixes live in `wiki.py` (bugs 1+3) and `build_static.py` (bug 2), so they apply to
  both the live wiki and the next static publish. **docs/ NOT regenerated** — the
  publish step stays a deliberate user trigger (demure rule); verified against a
  scratch build only.
- 2026-07-12 — **Mobile-responsive pass** (dr's feedback item 1): the header `nav`
  had `display:flex` with no `flex-wrap` and no breakpoint, so its ~11 buttons
  overflowed and forced horizontal scroll on phones. Added a `@media(max-width:760px)`
  block to STYLE in wiki.py: nav drops below the title (`order:2`), goes full-width,
  and wraps into rows; header/main/card padding and type tighten; global safety nets
  (`img{max-width:100%}`, `table{overflow-x:auto}`). Verified at a real 374px viewport
  (iframe test): media query fires, nav wraps, **zero horizontal overflow**. Applies to
  every page since STYLE is shared. Deeper per-page audits (graph, wide tables) can
  follow, but the reported bug is fixed sitewide.
- 2026-07-12 — Custom domain live at wichaa.net; llms.txt/robots/sitemap/OpenAPI/
  JSON-LD/glossary/curated landing all shipped. See project memory for the full list.
- 2026-07-12 — Three broken-link bugs (NaN report: "diagrams 404, some browse links
  broken, glossary layout funny"):
  1. `/diagrams`, `/findings` — DIAGRAMS_PAGE/FINDINGS_PAGE existed in wiki.py but
     were never in build_static.py's `pages` dict, so the static export never wrote
     them (same class of bug as the earlier /read fix). Added both, plus their
     `/api/*.json` dumps and shim NOARG entries.
  2. `/activity` — same gap, but activity is inherently live data on the dynamic
     wiki; exported as a build-time SNAPSHOT (consistent with this whole site's
     "consistent, not live" design), not a fake live feed — a truly live dashboard
     on a static host is a separate, bigger feature (see the dr-feedback item below,
     "watch the bots work" donor reward).
  3. Glossary grid → 1-column stack after the first domain: `draw()` in glossary.py
     opened a new `<div class="grid">` on every domain change but never closed the
     previous one, so all-but-the-last grid ended up nested inside each other
     instead of siblings. Fixed (close-before-open). Verified via DOM inspection:
     12 domain grids, all direct siblings of `#main`, zero nesting.
  All three verified in a real test build + browser before considering it done.
