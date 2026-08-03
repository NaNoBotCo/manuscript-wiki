# ADR-002 — Wayfinding: navigation as a projection of the knowledge graph

**Status:** accepted (2026-07-22 — all 8 decisions resolved with the owner; execution not
started) · **Decision owner:** you · **Scope:** discovery, navigation,
sharing, giving, and machine surfaces, sitewide · **Executed:** nothing — this document is the
whole deliverable of the planning session. A full read-only survey of the built site, the
generators, catalog.db, the vault, and BOTS.md was done first; every number below is measured,
not guessed.

---

## The brief (your words, distilled into principles)

> "a vast store of interconnected obscure knowledge, purposely repurposed and archived for
> posterity, in which relationships between things lead to discovery and creativity, and even
> the bots are able to learn. Sharability, opportunities to donate, and the delight of
> wandering at the forefront… it's built like a small site… growing exponentially."

1. **Relationships are the product.** A link that names *why* two things connect is discovery;
   a bare "see also" is furniture. Every connection shown should say its reason.
2. **Wandering is a first-class mode**, coequal with searching and browsing. The site should
   reward aimlessness the way a good market does.
3. **Bots are visitors and residents.** External agents get a legible graph to traverse;
   the house bots (GATHER→…→SCRIBE) get to *write* relationships they can defend with
   evidence. Learning = edges accumulating provenance, never LLM-prior assertions.
4. **Sharing and tam-boon ride along everywhere**, beside the value, never a gate
   (posture already established on /support).
5. **Navigation must scale sublinearly with content.** Menus are O(hand-edits); the corpus is
   growing exponentially. Anything hand-enumerated will lose. The menu stays constant-size
   forever; depth is carried by graph + search.

## Context — what the survey found (2026-07-22)

**Scale today:** 1,540 HTML pages / 241 MB in `nanobotco-lanna/docs`; 8,553 JSON files / 150 MB
under `api/`. Addressable things: 6,990 manuscripts · 13,020 market items · 1,494 places ·
192 Expedite shrines · 142 na glyphs · 33 glossary terms · 33 articles · 31 textbooks ·
3 reader volumes · 10 tools/widget pages. **The site is a client-rendered shell**: most classes
are one template HTML + N per-entity JSON (the SHIM in `build_static.py:62–271` maps `/api/…`
to static files). Only `place/` (1,494) and `read/` (3) are real per-item HTML.

**Navigation today is enumerative and flat.** `routes.py` (26 routes; 16 in nav, 16 landing
doors) generates the header, the doors, and crawler descriptions — a real registry with a
drift-check that stops the build. It works. But it governs only the ~22 hand-authored section
pages; the *bulk* namespaces (`place/`, `w/`, `read/`, `wats/app/`) are wired in separate
scripts the registry never sees. Consequence already visible: **`/w/` is orphaned** — six built,
carded, sitemapped analysis widgets with zero inbound links (only `/market`→`/w/geo` survives).
The drift-guard can't catch what it can't see. Orphans are now structural, not careless.

**Cross-linking is boutique.** What exists: manuscripts get 6 same-facet siblings
(`wiki._related`); articles have authored `see_also` edges that feed the /graph page and
`api/graph.jsonld` (typed edges even outrank generic ones, wiki.py:1615); na glyphs link
same-source; scribe.py can write evidence-linked `derived:` blocks into articles (used in 1 of
30). What doesn't: **place pages — the largest page class — have zero lateral links** (the
vault's `walk_cluster` field sits unused); market items have no pages of their own; the four
mechanism pages (/moon /jovilabe /redspot /hun) are cul-de-sacs; glossary terms link to
aggregates, not to the manuscripts that contain them. Breadcrumbs exist on exactly one page
type. **The graph machinery exists — at 33-article scale, while the corpus is ~22,000 nodes.**

**The vault is not yet a web.** `wichaa-vault/` holds 1,499 notes with gorgeous frontmatter
(35 fields — `walk_cluster`, `story_hook`, `confidence`…) and a total of **4 wikilinks**. The
second vault (`content/`, 30 articles) is hand-linked via `see_also`. `obsidian_export.py`
already exports the article graph to an Obsidian canvas + MOC — one-way. The desire-path layer
[[project-taxonomy-nodes]] assumes humans author links somewhere; today there is nearly nowhere
to author them.

**Machine door is already good** — llms.txt + llms-full.txt, robots.txt explicitly welcoming
GPTBot/ClaudeBot/et al., machine-first sitemap (8,544 URLs, mostly per-entity JSON),
api/index.json, OpenAPI, ai-plugin.json, JSON Feed, graph.jsonld/.ttl, Dataset JSON-LD, and
schema.org Place on every place page. What a visiting agent *cannot* get: the relationships.
graph.jsonld covers the article layer only.

**Share + give are half-built.** Share bar sitewide (LINE included), per-card share on 6,990
browse cards, ko-fi tam-boon in 1,536/1,540 pages. But ~99% of pages unfurl with the same
default og.jpg — 12 bespoke card masters exist (`publishing/cards/`), hand-rasterized
[[feedback_share_cards]]; `/m` detail cards are generic (one SPA shell, known gap); market
items aren't individually shareable at all.

**Search** is client-side and real (19 MB `searchdocs.json`, bilingual thesaurus expansion) but
ships whole and grows linearly — a scale bomb with a long fuse.

**Failure points, named:** hand-rasterized cards; registry blind to bulk namespaces; 19 MB
search index; 1.5 MB sitemap; 1,494 dead-end pages; article prose (30) as the only
human-linked layer over 22k nodes.

## Key finding — three lucky breaks

The overhaul is *smaller than it looks*, because three hard parts already exist in miniature:

1. **The graph already runs** — typed, provenance-aware, JSON-LD-exported, with a live /graph
   view and an authored-edge convention. It just covers 0.15% of the corpus. This is a
   scale-up, not an invention.
2. **The registration pattern is proven twice** — routes.py for pages, `WIDGETS` for analytics
   ("one registration buys page + API + embed + share card + offline copy"). The move is to
   make *registration* the only human act for any new surface, and make everything else a
   build-time projection.
3. **The bots are already organized for it** — BOTS.md has a T4b *Cartographers* tier with a
   `propose_edges` job, T3 curiosity detectors that literally find cross-tradition echoes
   (`antique_modern_echoes`), and scribe.py's delimited machine-block mechanism for writing
   findings into pages. The learning loop exists; it lacks a corpus-scale edge store to write
   into and chrome to surface it.

## Decision (proposed)

**Rebuild wayfinding as projections of one knowledge graph.**

- **Node** = anything addressable: item, manuscript, place, shrine, glyph, term, article,
  textbook, tool page, taxonomy node (tradition/deity/material/function/…), trail, and *gap*.
- **Edge** = typed, weighted, and — this is the wichaa move — **provenanced**, extending "the
  seam is provenance, not structure" [[project_seamless_corpus]] from items to relationships:
  - `authored` — a human said so (article `see_also`, vault wikilinks, trail steps)
  - `adjudicated` — an entity resolver said so (the `phra_rahu` pattern: rules, fail-closed)
  - `computed` — structure says so (same walk_cluster, same province, same script family,
    same source, same era band, shared tagged term, toc membership, geo proximity)
  - `derived` — a curiosity finding says so, with its evidence link (counts + verbatim,
    extract-don't-author, per the gambling-wats lesson in PRIORITIES.md)
- **Projections, all generated from the same store:** the nav, breadcrumbs, per-page Threads,
  the wander button, the landing's living strata, trails, search enrichment, sitemap, llms.txt,
  graph exports, share-card coverage, the Obsidian canvas. Adding a node = one registration;
  every surface updates because surfaces are projections.

Edges are **recomputed at build time** from catalog.db + content/ + wichaa-vault (like
taxonomy.py's runtime nodes — no new hand-maintained table; a cache table only if compute
demands it). Weights: authored > adjudicated > multi-signal computed > single-signal computed;
derived edges carry their finding.

### The page experience — wayfinding chrome (every page answers five questions)

1. **Where am I?** A generated breadcrumb from taxonomy position: *wichaa › Lanna manuscripts ›
   divination › this leaf*. Emic-term-primary labels.
2. **What is this connected to?** A **Threads** strip — 3–8 related nodes *with the relation
   named*: "shares the katha อิติปิโส", "same walking cluster as Wat Chiang Man", "its living
   market echo (14 listings)", "held at the same wat", "appears in the 1878 divination
   manual". Named relations are the whole difference between navigation and discovery.
3. **Where next?** One **Wander** button: a weighted hop along edges, biased toward
   cross-tradition and cross-century jumps (the delightful ones), away from thin dead-ends.
   One tap, works for low vision and tired hands [[user_accessibility]].
4. **Can I share it?** (share bar exists) — plus a real unfurl card for far more pages (below).
5. **Can I help?** (tam-boon exists) — plus, on gap nodes, "this door is painted on — help
   open it."

Plus a **Your trail** ribbon (distinct from breadcrumbs): the last ~10 nodes you visited,
client-side localStorage only, private by construction — retrace, and optionally "offer this
trail" through the contribution Worker. Desire paths, opt-in, zero tracking.

### The landing — from doors to a map room

Keep the doors (they're good, and now registry-generated). Around them:

- **The mission, stated plainly** — obscure knowledge, purposely repurposed, archived for
  posterity, legible to people and machines. One paragraph, top.
- **Today at wichaa** — a date-seeded deterministic daily stroll (~8 nodes): everyone sees the
  same "today," it's shareable, and it costs zero backend (client-side seed on a curated
  wander-pool JSON).
- **The site knows what day it is** — wan phra and full-moon awareness from the `WAN_PHRA`
  table already in hunpayont.py:501, Lanna เป็ง reckoning available from coucal-clock; on
  festival days the relevant thread surfaces (Yi Peng → lanterns, lights, the northern new
  year material). Client-side date logic, static-friendly, and a reason to come back.
- **The bots' work today** — the activity snapshot reframed as the sponsorship story
  ("X of Y pages read by the bots — sponsor the rest"), the commitment made to dr in
  #skynets-basilisk (PRIORITIES item 2/3, still open).
- **The gap ledger** — coverage-as-object made navigable: "the archive knows what it doesn't
  know." Each gap is a node with an adopt CTA (contribute knowledge, or tam-boon its
  digestization). The contribution quest list, on the front door.
- **A small constellation** — an ego-graph vignette around a rotating node (inline SVG,
  1–2 hops), a living window that deep-links into the Atlas (phase G).

### Trails — wandering, made a thing you can hold

A **trail** is a first-class content object: an ordered walk through the graph with one line of
narration per step. "Follow Rahu from a palm-leaf horoscope to a live Bangkok listing."
"Seven wats one walking cluster apart." The vault's `story_hook` field is ready-made narration
fuel sitting unused. Trails get pages, cards, and share bars like anything else (registration
buys all surfaces). Humans author some; **bots propose them** from high-weight paths and
curiosity findings — published with a visible `assembled by the bots from N findings` label
(posture to confirm, open decision 3). A finished trail ends beside a tam-boon cup.

### The machine door v2 — "even the bots are able to learn"

- **Corpus-scale graph exports:** `api/graph/nodes.jsonl` + `edges.jsonl` (typed, weighted,
  provenanced, evidence-linked) alongside the existing boutique graph.jsonld. Threads arrays
  injected *into the existing per-entity JSON* (6,990 manuscript files already exist — no new
  file explosion for the big classes; places get threads at HTML build; market joins
  client-side on the aggregate).
- **llms.txt teaches traversal:** a section telling agents the graph exists, what edge types
  mean, and that every page carries a Threads block. robots.txt already invites every major
  AI crawler; give them something to learn.
- **The residents' loop:** T3 curiosity finds a pattern → T4b `propose_edges` writes
  `derived` edges with evidence → scribe.py writes Threads machine-blocks into articles
  (the `derived:` delimiter mechanism, today used once) → a human confirms in the authoring
  layer → edge becomes `authored`, weight rises. That is bots learning, with provenance,
  and zero user surveillance.
- **Obsidian round-trip:** obsidian_export already writes the canvas out. Add the return
  path — wikilinks typed into `content/` or `wichaa-vault/` notes are parsed at build into
  `authored` edges. Obsidian becomes the human's edge-authoring cockpit; the site is the
  public projection of the same graph. (This is the concrete answer to "obsidian vaults and
  relationship mapping.")

### Scale mechanics — making the /w mistake impossible

- **Registry v2:** namespaces (`place/`, `w/`, `read/`, `wats/app/`, future classes) become
  first-class registry entries — builder + expected-count + door policy — so `routes.check()`
  and `verify_build.py` cover the bulk, not just the 22 section pages.
- **Orphan gate at build:** every built page must have ≥1 inbound link or a declared
  `hidden_reason`, or the build fails. (Would have caught /w.)
- **Card coverage:** keep the 12 hand-rasterized masters for the mechanism pages
  (masters stay in `publishing/cards/`, outside the publish path). For the long tail,
  per-class *templated* cards at build. Manuscript detail cards need per-id prerendered
  stub HTML (the known /m SPA gap; same pattern as `read/`) — a bounded, invasive-ish
  follow-up, phase F, decision 6.
- **Search:** shard `searchdocs.json` by class/initial when it crosses ~25 MB; index node
  aliases from taxonomy synonym rings so ฤๅษี = ruesi = lersi = hermit all land.
- **Publish safety:** fold in the open PRIORITIES item — the privacy gate must run LAST in
  `publish_site.sh`, after every generator (partially done, keep it true as generators
  multiply). MIN_HTML_PAGES-style floors grow with registry v2 counts.

## Options considered

| Option | What | Verdict |
|---|---|---|
| A. Keep pruning menus | More P2-style curation of a flat nav | Rejected as terminal — enumeration loses to exponential growth no matter how tasteful the pruning. |
| B. Search-first | Big search box, minimal nav | Necessary, not sufficient — serves known-item seeking; the brief is *wandering* and *relationships*. |
| **C. Graph projections** | One edge store; nav/threads/wander/trails/landing/machine surfaces all generated from it | **Recommended.** Scales sublinearly (register a node, projections update); already 3⁄4 invented in-house. |
| D. Obsidian-style graph app | Full client-side interactive graph as the primary nav | Rejected as *primary* — 22k-node hairball, heavy JS, hostile to low vision. Ego-graphs deliver the value; a full view can be one page later if wanted. (That page became Phase G, the Atlas — decision 7; still not the primary nav.) |

## Phases — each ships complete, in the dharmic-growth sense

No backlog; every phase leaves a whole site; later phases are open doors, not debts
[[project_coucal_direction]]. Order after B can flex. Effort: S ≈ a session, M ≈ 2–3, L ≈ more.

| Phase | Ships | Done when | Effort |
|---|---|---|---|
| **A. Cartography** | The edge store (build-time, from tags/taxonomy/see_also/vault frontmatter/curiosity findings) + `api/graph/*.jsonl` + a nav-audit page (orphans, dead-ends, components). No visible UI change; bots benefit immediately. | Edge counts per type/provenance published; /w orphans listed by the audit it introduces. | M |
| **B. Wayfinding chrome** | Breadcrumb + named-relation Threads + Wander button in the shared `page()` template; lateral links on all 1,494 place pages (walk_cluster + proximity); threads in the /market item drawer; mechanism pages stop being cul-de-sacs; chrome labels ship as TH/EN pairs from the string registry (decision 1); the /w fold — analysis widgets join the one tools door, /widgets aliases (decision 5). | No page class with 0 outbound related links; every thread names its relation; wander works with JS-lazy grace; no orphan widgets. | M–L |
| **C. Map room landing** | Mission graf, doors (unchanged), Today-at-wichaa, wan-phra/festival awareness, bots'-work-today (the dr commitment), gap ledger, constellation vignette. | Landing renders all strata from build outputs + client date logic; a festival day visibly changes the page. | M |
| **D. Trails** ✅ *shipped 2026-07-23* | `trails.py` + `data/trails.json`: 5 authored + 8 bot-assembled trails, `/trails` index + `/trail/<slug>/` pages, per-trail Pillow cards, trail-end tam-boon cup, 🧵 ribbon, offer-a-walk. | A trail unfurls with its own card; ribbon is localStorage-only; Worker path tested. | M |
| **E. Machine door v2 + the residents' loop** ✅ *mostly shipped 2026-07-23* | llms.txt/llms-full "Relationships — how to walk this corpus" (id scheme, edge shape, what each `prov` means); `threads` inside manuscript/place/article JSON; `howto` block inside graph/summary.json; derived edges from `propose_edges` and vault wikilinks→authored already land via cartography's layers. **Remaining: scribe.py writing Threads machine-blocks into `content/*.md`** — deliberately not done unattended, since it edits authored prose files. | A visiting agent can walk item→edges→item without HTML; a curiosity finding demonstrably becomes a visible thread with evidence. | M |
| **F. Share/give/scale polish** | Per-manuscript prerendered stubs for **all 6,990** (decision 6) + real cards (closes the /m unfurl gap); templated long-tail cards; QR on cards (for the physical world — stalls, wat notice boards); search sharding; timeline view; the "N hops from X to Y" toy. | A shared /m link unfurls with that manuscript; search cold-start ≤ a few MB. | L |
| **G. The Atlas** ✅ *first version shipped 2026-07-23* | `atlas.py` + `/atlas`: the graph folded onto its concept layer (231 concepts, 1,759 weighted links, 56 kB — `cartography.concept_projection`), canvas-drawn with a deterministic sector layout, zoom/pan/hover/click-through, class legend as filters, search-to-centre, collision-avoiding labels, and the same data as a linked list for screen readers. Own Pillow card. | Smooth on a mid-range phone; legible at every altitude (labels, contrast, big targets); any zoom/focus shareable via URL params. | L |

### What Phase G still has open (it shipped complete, not finished)
- **Item-level altitude.** Today the Atlas draws the concept layer only. Zooming into a
  cluster to load its actual manuscripts/places (the "semantic zoom" of decision 7) is the
  next altitude, and the shard files it would need do not exist yet.
- **Shareable view state.** Zoom/pan/focus are not yet in the URL, so you cannot link
  someone to a spot on the map. `?focus=<node-id>&z=<scale>` is the obvious shape.
- **Composition.** The sector layout is honest and deterministic but leans: `temple` (87)
  and `term` (66) take most of the angular budget while the heavy core sits off-centre.
  Worth a pass that weights sectors by mass rather than count.

## Phase D notes — the one thing that needs YOUR hand (2026-07-23)

**The Worker needs a deploy.** "Offer this walk" is live in the site chrome and works
today: it POSTs to `mueang-map-sync.wichaa.workers.dev/trail`, and when that answers 404
(it is not deployed yet) it falls back to copying the walk to the visitor's clipboard with
a mailto to 530kings@proton.me — nothing is ever lost. The endpoint itself is **written and
tested but NOT deployed**: `mueang-map/worker/worker.js` gains `POST /trail` (public, rate
limited, lands `trail:<uuid>` pending — never live) and `GET /trails` (admin queue), with
four new tests; `npm test` in mueang-map is **21/21 green**. Deploying is yours to run when
you want it (`wrangler deploy` from mueang-map/), because it changes a live service.

Why a new endpoint rather than reusing `/suggest`: `/suggest` validates `entry.point` and
tests it against a geographic bbox. A trail has no coordinates, so every offered walk would
have been rejected as "missing point". The moderation posture is unchanged — public in,
human out, nothing publishes unmoderated.

## Standing instructions to self (any session executing this)

1. Read this file + PRIORITIES.md first; work in `manuscript-wiki/`; **fix generators, never
   docs/** [[project_static_export]].
2. **Publish is a separate, deliberate, user-triggered act** [[feedback_demure_mindful]].
   Verify in a scratch build + local serve; leave docs/ alone unless asked.
3. **Permalinks are promises** — the site is "for posterity"; never break a published URL;
   reorganize additively, redirect if unavoidable.
4. **Privacy:** no client-side analytics ever; traffic stays the server-side substrate; the
   privacy gate runs last and stays last [[project_wichaa_privacy_incident]].
5. **Extract-don't-author:** every bot-made edge/trail shows counts or verbatim evidence,
   fails closed, and wears its provenance label. No LLM-prior assertions about named wats,
   monks, or reputations.
6. **Voice and framing:** emic terms first; no authentic/tourist sorting
   [[feedback_no_tourist_framing]]; commerce is first-class practice.
7. **Accessibility is load-bearing:** big targets, high contrast, one-tap wander, tolerant
   search, keyboardable everything [[user_accessibility]].
8. **Money posture:** ko-fi tam-boon, beside-the-value, never a gate; no new payment rails
   without an explicit decision; wichaa never in a money path it doesn't already occupy.
9. **Cards:** masters live in `publishing/cards/`, generated outside the publish path
   [[feedback_share_cards]]; templated cards are build-time.
10. **Mind the drive:** image-dependent steps must check the store mount (`plates: 0` this
    build because the Passport drive died 2026-07-12); degrade to IIIF gracefully.
11. **Grow the guards with the site:** any new namespace enters registry v2 + verify_build
    counts + the orphan gate + archive_site.py tiering (never Lazada→Wayback).
12. **Scope discipline:** narrow now, easy to widen later [[feedback_scope_conservative]] —
    per-item market pages and site-wide PWA are open doors, not phase work.
13. **Thai-friendly sitewide, sysop-safe (decision 1):** every chrome label is a TH/EN pair
    from one string registry; no parallel page trees, no locale toggle, no translation
    backlog; URLs stay neutral English; standard attested Thai now — sourced-Lanna polish is
    a display-only later pass.

## Decisions — RESOLVED (2026-07-22)

Walked through with the owner; answers 1 and 7 recorded in their own words.

1. **Language of the chrome — "very Thai friendly from the start… It's true sitewide."**
   Owner's why, verbatim: *"The internet has a big blind spot in thailand, and it cannot be
   fixed without thai participation and visitors."* Constraint: a sweet spot that "doesn't
   become a sysop nightmare," interpreted liberally. Interpretation adopted: **bilingual TH/EN
   chrome from day one** (the Hun Payont pattern, generalized) — every wayfinding/nav label is
   a Thai + English pair drawn from **one string registry**; **no parallel page trees, no
   locale toggle, no translation backlog** (that is the sysop-nightmare firewall); URLs stay
   neutral English so any renaming is display-only. Standard, attested Thai now; a
   sourced-Lanna refinement remains a cheap later polish. Thai visitors are an audience to
   win, not a localization checkbox.
2. **Tam-boon loudness:** the landing module ("the bots' work today") + a trail-end cup;
   existing footer, /support, and per-manuscript CTAs unchanged. Beside-the-value, never a
   gate.
3. **Bot-assembled trails publish immediately, wearing a visible label** ("assembled by the
   bots from N findings") with evidence links. Prunable any time.
4. **"Offer this trail" ships in phase D** through the mueang-map-sync Worker pattern
   (public suggest → moderation queue; nothing publishes unmoderated).
5. **Namespaces fold into /w/.** The "Widgets & shit" page becomes the single human door to
   every tool and analysis widget (un-orphaning all six); /widgets aliases forever —
   permalinks are promises.
6. **Per-manuscript stubs: all 6,990, one pass.** Real unfurls and inbound-linkable
   manuscripts across the whole corpus (places prove the pattern at 1,494; expect tens of MB
   in docs/).
7. **The graph goes maximal — flagship, not toy.** Owner, verbatim: *"I want to graph this
   thing out in the pimpest way possible. the graph itself is sexy and does the work."*
   Becomes **Phase G — the Atlas**: a zoomable, multi-altitude graph (taxonomy-node atlas →
   semantic zoom into clusters → items on demand), canvas-rendered and shard-lazy so ~22k
   nodes stay smooth, with its own share card; the landing constellation becomes a window
   into it. Per-page ego-vignettes remain the everyday projection, and the chrome remains the
   primary nav — the Atlas is the destination, not the doorway.
8. **Publish rhythm: quiet A, then B+C as one visible "the site learned to wander" moment**
   with its own share card; D–G ship as they finish. Publishing stays a deliberate,
   user-triggered act regardless.

## Success measures

- Adding any new page/class = **one registration**; nav, doors, sitemap, llms.txt, search,
  cards, and the orphan gate all update without further hand-edits.
- **Zero dead-end page classes**; every page shows ≥3 named threads or an honest frontier
  marker.
- A first-time visitor reaches a **cross-tradition connection in ≤3 taps** from the landing.
- A visiting LLM can traverse **item → typed edge → item** without touching HTML.
- A curiosity finding becomes a **visible, evidence-linked thread** without a human writing
  prose.
- The share of pages unfurling with a **real card** (not og.jpg) rises from ~1% toward 100%.
- You can hand someone "today at wichaa" and it's the **same today** everyone else got.
- Every piece of chrome reads in **Thai and English**, from one string registry — a Thai
  visitor never meets an English-only door.
