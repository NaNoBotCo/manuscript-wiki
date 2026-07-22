# ADR-001 — Re-root the site from "Lanna Manuscript Wiki" to "wichaa"

**Status:** proposed (2026-07-14) · **Decision owner:** you · **Scope:** wichaa.net identity + information architecture

## Context — the problem

The site presents itself as **The Lanna Manuscript Wiki**. Its own `<title>` is
`wichaa · วิชา The Lanna Manuscript Wiki` — "wichaa" is used as a *poetic gloss*
("wichaa means knowledge") while the concrete noun it claims to **be** is a Lanna
manuscript archive.

That is an inverted root. **Wichaa is the subject; Lanna manuscripts are one corpus
of it.** The site is built as *a manuscript archive that also has some other stuff*,
when it should be *the study of wichaa, of which the Lanna manuscript archive is one
tradition among several* (Lanna manuscripts · Thai market amulets · St. Expedite · and
more to come — museum CC0 objects are already crawled in).

**The smoking gun** is in the landing copy: amulets are introduced as *"living amulets,
tied back **to the manuscripts** by shared sacred words."* Everything is defined by its
relation to the manuscript trunk. That framing survives only because Thai market amulets
really do share katha with the manuscripts. **St. Expedite breaks it**: not Lanna, not
Thai, no manuscript, no shared sacred words — nothing to "tie back." Expedite is homeless
under the current architecture, which exposes a contradiction that was always latent.

This also completes the project's own governing rule — *"the seam is provenance, not
structure"* ([[project-seamless-corpus]]). Today the **structure privileges one
provenance** (manuscripts) as the spine. Expedite forces the architecture to finally
become what it already claimed to be.

## Key finding — the fix is mostly presentational

The datastore is **already tradition-agnostic**:

- `sources` (27 rows) — provenance is a first-class entity: manuscript libraries,
  contributed texts, **Lazada commerce (src 23/27)**, **Cleveland/Met/Smithsonian CC0
  (src 24–26)**. The store already spans cultures and media.
- `items` (11,793 rows) — generic spine: `source_id`, `kind`, `method`, `medium`,
  `title_*`, `date_ce_estimate`. Multi-source by design.
- `manuscripts` (6,990) is a **specialization** hanging off that spine, not the spine.
- `articles`, `tags`, `pages`, `images` round it out.

So the database believes in a many-traditions world. **The lie is in the presentation
layer only** — the identity strings, the landing hero, the nav. That is a cheap, mostly
reversible change. The deep change (ingesting Expedite as data) is optional and can come
later without redoing the first.

## Decision

Re-root the site's identity and IA around **wichaa as the universal category** — practical,
efficacious sacred knowledge, where no line is drawn between science, magic, medicine and
nature — and demote **"Lanna manuscripts" from the root to a coequal tradition node**,
sibling to Thai market amulets and St. Expedite.

Concretely, introduce a top-level **TRADITION / source-domain axis** whose values are
nodes (`lanna-manuscript`, `thai-market-amulet`, `st-expedite`, …), coequal with the
existing facet axes (reliability, register, function). "Lanna manuscripts" stops being
the room everything lives in and becomes one label on the wall. This is the exact
value→node model already proven on the language decomposition ([[project-taxonomy-nodes]]).

## Two layers (do them in this order — each ships independently)

### Layer 1 — Identity & IA re-frame (cheap, reversible, high signal)
The site *says* it is about wichaa, and offers traditions as peer doors.

1. **Retitle** the ~15 hardcoded identity strings from "Lanna Manuscript Wiki" → "wichaa"
   (with a generalized subtitle, e.g. *"an open archive of wichaa — living traditions of
   sacred, practical knowledge"*). Locations found:
   - `landing.html`: `<title>`, `og:title`, the `<h1>` ("The Lanna Manuscript Wiki").
   - `site_meta.py`: ~11 occurrences — the LLMs.txt header (l.103, 221), API `name`
     (l.390, 418, 449), licensing name/attribution (l.502–558), social-meta title (l.755).
     **Note:** attribution string changes have downstream effect — see Risks.
   - `wiki.py`: `OG_TITLE` (l.2509), page-title suffixes (l.4414, 4445), the crawler
     notice (l.4065).
2. **Re-frame the landing hero**: lead with wichaa as the subject; present the corpora as
   **peer entry doors** — "the Lanna manuscript archive," "the living amulet market," "the
   St. Expedite cult" — none subordinate. Rewrite the "tied back to the manuscripts" line
   so amulets are a *sibling* expression of the same wichaa, not a satellite.
3. **Add St. Expedite as a peer door** on the landing/nav, linking (for now) to its own
   built site. This alone answers "where's the Expedite link?" at the corpus level.

*Reversibility:* pure string/template edits; `git` revert restores the old identity. No
data migration.

### Layer 2 — Unify the store (the real seamless-corpus fulfillment; optional, later)
Bring St. Expedite into the **same `catalog.db`** so it shares taxonomy, facets, search,
and the tradition axis with everything else — instead of being a federated island.

- New `sources` rows for the Expedite provenances (Wikimedia Commons imagery, OSM shrines,
  the verified research corpus, the ngram/trends data).
- Expedite content lands in `items` (kind e.g. `saint-shrine`, `devotional-image`) and
  `articles`, **not** `manuscripts` — which cleanly demonstrates that the manuscript table
  is a specialization, not the corpus.
- Promote a `tradition` / source-domain facet (derivable from `source_id` → tradition map)
  and expose it as a top-level browse axis in `wiki.py`.
- The St. Expedite standalone site can persist as a themed *view*, or be retired once its
  content lives in the shared wiki. **Decide later.**

*Reversibility:* additive (new rows, new facet). The manuscript machinery is untouched.

## Options considered

| Option | What | Verdict |
|---|---|---|
| **A. Identity re-frame only** (Layer 1) | Rename + re-hero + add Expedite as a federated peer door | **Recommended first step.** Fixes the stated problem, cheap, reversible. |
| **B. Full unification now** (Layer 1+2 together) | Re-frame *and* ingest Expedite into catalog.db in one pass | More faithful to seamless-corpus, but bigger and riskier for a live/published site; better as a deliberate second pass. |
| **C. Do nothing / bolt Expedite under manuscripts** | Keep the manuscript root, hang Expedite off it | Rejected — it's the exact inversion that caused the problem; Expedite has nothing to hang on. |

## Naming decision — RESOLVED (2026-07-14)

**Wichaa is the universal root.** It names the whole human category of practical, efficacious
sacred knowledge; Lanna magic and Catholic folk-sainthood (Expedite) are dialects of it. This
is the ontological claim the site now makes openly. Consequences for execution:
- Subtitle generalizes wichaa beyond "the north" (e.g. *"an open archive of wichaa — living
  traditions of sacred, practical knowledge, across cultures"*). Keep the existing "no line
  between science, magic, medicine and nature" line — it already carries the universal sense.
- The tradition/source-domain axis is *within* wichaa; `lanna-manuscript` is a node, not the root.
- Thai script / วิชา stays as the brand's origin mark, not a scope limit.

## Risks & notes

- **Attribution/licensing strings** (`site_meta.py` l.142, 502–558) are load-bearing —
  they're the credit users must give and appear in API/schema.org output. Renaming the
  attributed entity is fine but should be deliberate and consistent (and ideally announced
  if anyone already cites "Lanna Manuscript Wiki").
- **Published site**: changes are made in `manuscript-wiki/` and rebuilt into
  `nanobotco-lanna/docs` via `build_static.py` — a separate deliberate publish step
  ([[project-static-export]], [[feedback-demure-mindful]]). Nothing goes live automatically.
- **SEO/inbound**: the domain is wichaa.net already, so re-rooting to "wichaa" *strengthens*
  name/URL alignment rather than breaking it.
- **Scope discipline**: Layer 1 is the whole ask ("the page structure needs to change").
  Layer 2 is the more ambitious follow-through; keep it separate so the first stays small.

## Recommended path

Ship **Layer 1** as one reviewable change (identity re-frame + Expedite peer door), publish
when you're happy, then decide separately whether/when to do **Layer 2** (unify the store).
Answer the naming question first — it sets the subtitle and axis labels everything else uses.
