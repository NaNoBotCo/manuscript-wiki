#!/bin/bash
# ============================================================================
#  publish_site.sh — refresh the public GitHub Pages copy of the Lanna Wiki.
#
#  What it does, every time it runs:
#    1. rebuilds the static site from the LIVE catalogue  (build_static.py)
#    2. drops it into the site repo's  docs/  folder
#    3. commits ONLY if something actually changed, then pushes
#
#  If nothing in the catalogue moved, the rebuilt files are byte-identical and
#  this does nothing — so it is safe to run on a timer as often as you like.
#  "Consistent, not live": the public site catches up to your work each run.
#
#  Site: https://nanobotco.github.io/Lanna/   (repo NaNoBotCo/Lanna, main /docs)
#
#  One-time setup: double-click  "Set up publishing.command"  once. It signs you in
#  and does the first publish. After that this script (by hand or on the timer) keeps
#  the public copy in step with your catalogue.
# ============================================================================
set -euo pipefail

OWNER="NaNoBotCo"
REPO="Lanna"
# ---- custom domain --------------------------------------------------------
# Fill this in when you own one (e.g. CUSTOM_DOMAIN="lannawiki.org"), or export it
# in the environment. When set: the site builds for the domain ROOT ("/") instead of
# the /<REPO>/ subpath, site_meta.py writes the CNAME file GitHub Pages needs, and
# every absolute link (llms.txt, sitemap, OpenAPI, JSON-LD) points at the domain.
# Also flip repo Settings → Pages → Custom domain, and add the DNS records —
# see publishing/DOMAIN_SETUP.md for the exact checklist.
CUSTOM_DOMAIN="${CUSTOM_DOMAIN:-wichaa.net}"

if [ -n "$CUSTOM_DOMAIN" ]; then
  SITE_BASE="/"
  export SITE_URL="https://${CUSTOM_DOMAIN}"
else
  # The public site lives under /<REPO>/, so the build must know that URL prefix.
  SITE_BASE="/${REPO}/"
  # Absolute origin+path of the published site, so shared-link previews carry an
  # absolute og:image (FB/Twitter won't unfurl a relative one). GitHub Pages hosts
  # are always lowercase; keep this in step with OWNER/REPO above.
  export SITE_URL="https://nanobotco.github.io/${REPO}"
fi
WIKI_DIR="$HOME/Developer/claude code projects/manuscript-wiki"
SITE_REPO="${SITE_REPO:-$HOME/Developer/claude code projects/nanobotco-lanna}"
export CATALOG_DB="${CATALOG_DB:-$HOME/Developer/claude code projects/manuscript-crawler/crawler/catalog.db}"
export STORE_DIR="${STORE_DIR:-$HOME/Developer/claude code projects/manuscript-crawler/crawler/store}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "Refreshing the public Lanna Wiki snapshot…"

if [ ! -d "$SITE_REPO/.git" ]; then
  echo "No site repo at: $SITE_REPO"
  echo "Run the one-time setup first: double-click \"Set up publishing.command\""
  echo "(or set SITE_REPO to wherever you cloned $OWNER/$REPO), then run this again."
  exit 1
fi

PY=$(command -v python3 || command -v python)
if [ -z "$PY" ]; then echo "Python 3 not found."; exit 1; fi

# 0. SNAPSHOT THE CATALOGUE before building anything.
#
# The crawler (com.lanna.crawler.forever → scheduler.py) writes catalog.db
# continuously, and the DB is in journal_mode=delete. wiki.py opens it read-only
# ("file:…?mode=ro"), and a read-only connection CANNOT roll back a hot journal
# left by an in-flight writer — it fails with "unable to open database file".
# That made publishing a coin-flip: fine between writes, dead during one, and it
# killed a run after build_static.py had already wiped docs/ (leaving the repo
# looking like 7,000 deletions, CNAME included).
#
# Fix: build from a point-in-time copy. sqlite3's online backup API takes a
# consistent snapshot even while another process writes, and opening the source
# read-write lets it recover a hot journal first — which is exactly what a
# read-only opener could not do. The build then reads a private file nobody is
# touching, so a publish can no longer race the crawler. This also matches the
# script's own "consistent, not live" contract: a snapshot, not a moving target.
SNAP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/lanna-catalog-XXXXXX")"
cleanup_snapshot() { [ -n "${SNAP_DIR:-}" ] && rm -rf "$SNAP_DIR"; }
trap cleanup_snapshot EXIT
log "Snapshotting catalogue (immune to the live crawler) → $SNAP_DIR"
if "$PY" - "$CATALOG_DB" "$SNAP_DIR/catalog.db" <<'SNAPPY'
import sqlite3, sys
src_path, dst_path = sys.argv[1], sys.argv[2]
# read-write on the source so a hot journal gets rolled back; .backup() only reads
src = sqlite3.connect(src_path, timeout=60)
dst = sqlite3.connect(dst_path)
with dst:
    src.backup(dst)
n = dst.execute("SELECT COUNT(*) FROM manuscripts").fetchone()[0]
src.close(); dst.close()
print(f"  snapshot ok — {n} manuscripts")
SNAPPY
then
  export CATALOG_DB="$SNAP_DIR/catalog.db"
  # the snapshot is a private copy nobody else can touch — tell SQLite so, and it
  # skips locking altogether (see wiki.connect()).
  export CATALOG_IMMUTABLE=1
else
  echo "Could not snapshot the catalogue (is the crawler mid-write? try again)." >&2
  exit 1
fi

# 0b. THE VAULT IS THE SYSTEM OF RECORD — and must run BEFORE build_static.
#
# This block first sat after build_static and did nothing visible: build_static
# had already emitted docs/api/wats.json from the OLD data/wats.geojson, so the
# published site kept serving crawl output while compile.py rewrote a file
# nothing read again. `source: vault` was absent live and that was the tell.
#     sync_wats refreshes the crawl sidecar; migrate lands any new crawl records
#     as notes (never clobbering a note someone has edited); compile publishes
#     FROM the vault, so anything authored in Obsidian reaches the site and the
#     two cannot drift. Verified to be a strict superset of the crawl output —
#     nothing lost, plus aliases, emic type, geoPrecision and per-field provenance.
VAULT="$HOME/Developer/claude code projects/wichaa-vault"
if [ -d "$VAULT" ]; then
  log "Vault → notes → JSON  (migrate + compile)"
  "$PY" "$WIKI_DIR/sync_wats.py" || echo "  ! sync_wats failed"
  "$PY" "$VAULT/scripts/migrate.py" --write || echo "  ! migrate failed"
  "$PY" "$VAULT/scripts/validate.py" --strict || { echo "✗ vault validation failed — refusing to publish"; exit 1; }
  "$PY" "$VAULT/scripts/compile.py" --write || { echo "✗ compile failed"; exit 1; }
fi

# 1. + 2. rebuild straight into the repo's docs/ folder, for the /<REPO>/ URL prefix
log "Building static site → $SITE_REPO/docs  (base $SITE_BASE)"
"$PY" "$WIKI_DIR/build_static.py" --out "$SITE_REPO/docs" --base "$SITE_BASE"

# 2a. build the multilingual glossary of discovered terms (Thai/English/中文) from the
#     fresh catalogue → docs/glossary/ + docs/api/glossary.json. Before site_meta so the
#     glossary page lands in the sitemap and gets its JSON-LD.
log "Building glossary → glossary.py"
"$PY" "$WIKI_DIR/glossary.py" --docs "$SITE_REPO/docs" --site-url "$SITE_URL"

# 2a-2. the visual na-compendium: every na (sacred glyph) from manuscript #6964,
#     sliced out and paired one-by-one with the page it was drawn on. Regenerates
#     its own source data (na_compendium.py) and bundles the page images it needs.
log "Building na-compendium gallery → na_gallery.py"
"$PY" "$WIKI_DIR/na_gallery.py" --docs "$SITE_REPO/docs" --site-url "$SITE_URL"

# 2a-3. the offline app version of the wat map: an installable PWA + a
#     single-file download, wrapped around mueang-map's self-contained wats.html.
#     Rebuild that artifact first so the app ships the current catalogue.
log "Building wat map app → build_wats_app.py"
MM_DIR="$HOME/Developer/claude code projects/mueang-map"
if [ -d "$MM_DIR" ] && command -v node >/dev/null 2>&1; then
  ( cd "$MM_DIR" && node build.mjs >/dev/null && node scripts/build-wats-visual.mjs ) || \
    echo "  ! mueang-map rebuild failed; wrapping whatever wats.html exists"
fi
"$PY" "$WIKI_DIR/build_wats_app.py" --docs "$SITE_REPO/docs" --site-url "$SITE_URL" || \
  echo "  ! wat app skipped (no wats.html yet)"

# 2a-4. one real page per place (/place/<id>/) so a shared link unfurls with the
#     temple's own photograph and name — a #fragment never reaches an unfurler.
#     Runs BEFORE site_meta so the sitemap and JSON-LD pick the pages up.
log "Building per-place share pages → build_place_pages.py"
"$PY" "$WIKI_DIR/build_place_pages.py" --docs "$SITE_REPO/docs" --site-url "$SITE_URL" || \
  echo "  ! place pages skipped"

# 2b. add the machine-legibility layer on top of the fresh build: llms.txt, robots.txt,
#     sitemap.xml, OpenAPI + AI-plugin manifest, JSON Feed, schema.org JSON-LD in heads.
#     Post-build (not inside build_static.py) so it stays decoupled; idempotent, so it's
#     safe to re-run. SITE_URL (exported above) makes every absolute link resolve.
log "Adding machine-legibility layer → site_meta.py"
"$PY" "$WIKI_DIR/site_meta.py" --docs "$SITE_REPO/docs" --site-url "$SITE_URL" \
  ${CUSTOM_DOMAIN:+--custom-domain "$CUSTOM_DOMAIN"}

# 2b. FINAL privacy gate — runs LAST, after EVERY generator (build_static.py has its
#     own gate but glossary.py / na_gallery.py / site_meta.py all write files after it).
#     A build machine's absolute path leaks the operator's username + local layout
#     (this happened once — build-info.json/status.json shipped /Users/<name>/…). Scan
#     text files for host paths and REFUSE to publish if any survived — better a failed
#     publish than a leaked one. See memory project_wichaa_privacy_incident.
log "Privacy gate → scanning docs/ for host paths before publish"
if grep -rIl -e "/Users/" -e "/home/" -e "$HOME" "$SITE_REPO/docs" \
     --include='*.html' --include='*.json' --include='*.txt' --include='*.xml' \
     --include='*.js' --include='*.css' 2>/dev/null | head -1 | grep -q .; then
  echo "ERROR: absolute host path found in docs/ — NOT publishing. Offending files:" >&2
  grep -rIl -e "/Users/" -e "/home/" -e "$HOME" "$SITE_REPO/docs" \
     --include='*.html' --include='*.json' --include='*.txt' --include='*.xml' \
     --include='*.js' --include='*.css' 2>/dev/null | head -40 >&2
  exit 2
fi

# 2c. COMPLETENESS GATE — runs after EVERY generator, immediately before `git add`.
#     The privacy gate above catches what should not ship; this catches what did not
#     get built. On 2026-07-22 a publish pushed a site missing fifteen directories
#     (/moon, /hun, /support, /articles, /expedite …) because the build reached its
#     end, printed ERRORS: 0 and exited 0 — success only ever meant "did not crash".
#     verify_build.py was written that day but never wired in here, so on 2026-07-28
#     the same collapse shipped again: 7,049 files removed, /hun /jovilabe /need
#     serving 404 on wichaa.net. It walks routes.py against what is on disk.
#     Exit non-zero stops the publish BEFORE the commit rather than after the push.
log "Completeness gate → verify_build.py against routes.py"
"$PY" "$WIKI_DIR/verify_build.py" --docs "$SITE_REPO/docs" || {
  echo "✗ incomplete build — NOT publishing (nothing committed, nothing pushed)" >&2
  exit 3
}

# 3. commit only if the working tree changed
cd "$SITE_REPO"
git add docs
if git diff --cached --quiet; then
  log "No changes since last publish — nothing to push."
  exit 0
fi

STAMP=$(date '+%Y-%m-%d %H:%M')
git commit -q -m "Refresh Lanna Wiki snapshot — $STAMP"
log "Committed. Pushing to GitHub…"
if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
  git push -q                       # upstream already set
else
  git push -q -u origin HEAD        # first push: set upstream
fi
log "Done. GitHub Pages will rebuild in a minute or two → ${SITE_URL}/"
