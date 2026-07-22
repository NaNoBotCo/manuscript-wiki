# Widget architecture — GIS, introspection, and anything countable

One pattern for every analytical view. A **widget** is one snapshot function
registered in `WIDGETS` (wiki.py); that single registration buys it, uniformly:

| Surface | URL | Purpose |
|---|---|---|
| Data | `/api/w/<name>` | JSON — the machine door; also the "⬇ JSON" download |
| Page | `/w/<name>` | standalone SHAREABLE page: own title + OG description (links unfurl), share bar (copy link / copy iframe embed / download data), site nav |
| Embed | `/w/<name>?embed=1` | chromeless, for `<iframe>` on any other site |
| Interop | `/api/w/geo.geojson` | standards files where a standard exists (GeoJSON → QGIS/kepler.gl/Felt) |

**To add a widget:** write `foo_widget()` (read catalog.db / data files, return a
dict; NEVER write), add renderer JS to `_WIDGET_JS["foo"]`, add one `WIDGETS`
entry `(fn, title, og_description)`. ~30 lines total. Widgets follow the house
rules: extract-don't-author (counts and verbatim data only), honest-empty states.

## Shipped widgets

- **`geo`** — the corpus↔market seam made geographic: manuscript provenance
  (teal) vs live amulet-market seller provinces (gold) on one dot map, all-77
  province centroid table (`THAI_PROVINCE_COORDS`, Thai-keyed; manuscripts'
  English names join via inverted `PROVINCE_EN`). First render already showed a
  finding: Phrae 2,133 mss / 5 listings vs Bangkok 21 mss / 1,357 listings —
  the antique heartland and the living market are geographically inverted.
- **`traffic`** — introspection: daily human/bot volume, crawler leaderboard
  (GPTBot, ClaudeBot…), top pages, top API endpoints, rough uniques.
- **`products`** — the newest amulet listings as a shelf (title/price/province/
  terms/source link), verbatim from the market crawl. Not linked from the nav
  yet — reachable via /w/ and /w/products while it builds out.
- **`answers`** — first subscriber to the Thai Answers project's JSON Feed
  (`../thai-answers/docs/feed.json`, override with THAI_ANSWERS_FEED; becomes a
  URL fetch when that site deploys). Honest-empty until the feed is built.
  Feed items carry no url until thai-answers sets BASE_URL, so the widget never
  links a page that doesn't exist. Also not on the nav yet.

## The traffic substrate (privacy by construction)

`_record_traffic()` appends one JSONL line per request to `data/traffic.jsonl`
(20 MB rotation, one generation kept): timestamp, path (query VALUES dropped),
surface (api/page/img), agent (`human` or matched bot name), and a visitor hash
= sha256(day + ip)[:12] — rough daily uniques with **no raw IP ever stored**.
No third-party analytics, no cookies. When the site is deployed publicly, this
is how you'll SEE the GPTBot/ClaudeBot crawls and API adoption the llms.txt
front door invites.

## Widget ideas (same pattern, when wanted)

term-productivity (search_terms audit as a live chart) · translation-progress
(pages/day, sponsor-funded vs free) · price-distribution by province ·
genre×geography heat table · sponsor wall · corpus-growth timeline.

## Static export note

Widgets are JSON + JS, so they export via the existing shim pattern (dump
`/api/w/*.json`, emit `/w/<name>/index.html`) — not yet wired into
build_static.py; `traffic` should stay live-only (its data is server-side).
