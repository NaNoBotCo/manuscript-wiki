#!/bin/bash
# ============================================================================
#  Stop the Lanna Manuscript Wiki.  Double-click this to shut it down.
#  (Only needed if you want it fully off — normally you can just leave it.)
# ============================================================================
PORT=4190
PIDS=$(lsof -nP -iTCP:${PORT} -sTCP:LISTEN -t 2>/dev/null)
if [ -z "$PIDS" ]; then
  echo "The Lanna Wiki is not running. Nothing to stop."
else
  echo "Stopping the Lanna Wiki (process $PIDS)…"
  kill $PIDS 2>/dev/null
  sleep 1
  echo "Done."
fi
sleep 2
