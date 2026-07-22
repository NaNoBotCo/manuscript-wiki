#!/usr/bin/env bash
# sync_to_server.sh — push a fresh catalog.db + store_pages + epub/ to the live
# wiki server. Translation/crawling/OCR all happen HERE (need pdftoppm, tesseract,
# playwright, the external image drive) — the VPS only ever serves a read copy of
# what those tools produced. Run this after a translate.py / build_toc.py /
# epub_volume.py pass to publish the new work.
#
# Does NOT ship: raw manuscript scans (served on-demand via IIIF, never local),
# contributed/ source PDFs (only the crawler-side bots need these, not the live
# server), woven/ (a local preview artifact, not wired into the live wiki).
#
#   HOST=you@your-vps ./deploy/sync_to_server.sh
#   HOST=you@your-vps DRY_RUN=1 ./deploy/sync_to_server.sh   # preview, no changes

set -euo pipefail

HOST="${HOST:?set HOST=user@your-vps-ip-or-domain}"
REMOTE_ROOT="${REMOTE_ROOT:-/opt/lanna}"
DRY="${DRY_RUN:+--dry-run}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"          # manuscript-wiki/
CRAWLER="$(cd "$HERE/../manuscript-crawler" && pwd)"

echo "syncing catalog + images + epubs to $HOST:$REMOTE_ROOT"

rsync -avz $DRY --progress \
  "$CRAWLER/crawler/catalog.db" \
  "$HOST:$REMOTE_ROOT/manuscript-crawler/crawler/catalog.db"

rsync -avz $DRY --progress --delete \
  "$CRAWLER/store_pages/" \
  "$HOST:$REMOTE_ROOT/manuscript-crawler/store_pages/"

rsync -avz $DRY --progress --delete \
  "$CRAWLER/epub/" \
  "$HOST:$REMOTE_ROOT/manuscript-crawler/epub/"

if [ -z "${DRY_RUN:-}" ]; then
  echo "restarting the live server"
  ssh "$HOST" "sudo systemctl restart lanna-wiki"
else
  echo "(dry run — nothing copied, service not restarted)"
fi
