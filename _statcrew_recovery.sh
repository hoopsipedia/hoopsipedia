#!/bin/zsh
# Recovery pass — re-harvest under-yielders that were cut short (each stuck at 3 games).
cd /Users/joshdavis/Projects/hoopsipedia
for src in long-beach-state-beach utah-utes ohio-state-buckeyes unlv-rebels; do
  rm -f "archives/$src/statcrew_boxscores_pending.json"
  echo "=== harvesting $src ==="
  python3 -u harvest_statcrew.py $src 2>&1 | tail -4
  echo "--- $src pending: $([ -f archives/$src/statcrew_boxscores_pending.json ] && python3 -c "import json;print(len(json.load(open('archives/$src/statcrew_boxscores_pending.json'))))" || echo 0) games ---"
done
echo "RECOVERY COMPLETE"
