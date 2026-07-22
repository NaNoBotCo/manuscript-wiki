#!/bin/bash
# ============================================================================
#  Lanna Manuscript Wiki  —  double-click to open it in your browser.
# ----------------------------------------------------------------------------
#  You can click this any time. It is smart about what's already running:
#    • If the wiki is already open, it just brings up the page.
#    • If it isn't, it starts it quietly and then opens the page.
#  You do NOT need to keep this window open — it does its job and steps aside.
#  To stop the wiki completely, run  "Stop Lanna Wiki.command".
# ============================================================================

PORT=4190
URL="http://127.0.0.1:${PORT}/"
WIKI_DIR="$HOME/Developer/claude code projects/manuscript-wiki"
export CATALOG_DB="$HOME/Developer/claude code projects/manuscript-crawler/crawler/catalog.db"
export STORE_DIR="$HOME/Developer/claude code projects/manuscript-crawler/crawler/store"

cd "$WIKI_DIR" || { echo "Could not find the wiki folder."; sleep 3; exit 1; }

is_up () { curl -s -o /dev/null --max-time 2 "$URL"; }

if is_up; then
  echo "The Lanna Wiki is already running — opening it now."
  [ -z "$LANNA_NOOPEN" ] && open "$URL"
  sleep 1
  exit 0
fi

# Friendly heads-up if the external drive with the manuscript scans isn't plugged in.
if [ ! -e "$STORE_DIR" ]; then
  echo "Note: the drive with the manuscript scans isn't connected."
  echo "The wiki will still open — the catalogue, plates and articles all work;"
  echo "only the raw scan images will be missing until the drive is plugged in."
  echo
fi

echo "Starting the Lanna Manuscript Wiki…"
nohup python3 wiki.py >/tmp/lanna-wiki.log 2>&1 &
disown 2>/dev/null

# Wait (up to ~8s) for it to answer, then open the browser.
for i in $(seq 1 25); do
  is_up && break
  sleep 0.3
done

if is_up; then
  echo "Ready. Opening $URL"
  [ -z "$LANNA_NOOPEN" ] && open "$URL"
  sleep 1
  exit 0
else
  echo "The wiki didn't start. Recent log:"
  tail -n 20 /tmp/lanna-wiki.log 2>/dev/null
  echo
  echo "Leave this window open and tell Claude what it says."
  sleep 30
  exit 1
fi
