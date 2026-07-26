#!/bin/zsh
# Parallel harvester: runs N programs concurrently (default 3 — the rate the
# domain census sustained against archive.org without throttling). Sequential
# per-file politeness is unchanged inside each worker; the win is program-level
# concurrency. Usage: ./_harvest_parallel.sh <keysfile> [workers]
cd /Users/joshdavis/Projects/hoopsipedia
KEYS=${1:?usage: _harvest_parallel.sh <keysfile> [workers]}
W=${2:-3}
cat $KEYS | tr ' ' '\n' | grep -v '^$' | xargs -P $W -I{} sh -c '
  f="archives/{}/statcrew_boxscores_pending.json"
  [ -f "$f" ] && { echo "[skip] {} (already harvested)"; exit 0; }
  out=$(python3 -u harvest_statcrew.py {} 2>&1 | tail -4)
  echo "=== {} ==="; echo "$out"
'
echo "PARALLEL_HARVEST COMPLETE"
