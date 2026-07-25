#!/bin/zsh
cd /Users/joshdavis/Projects/hoopsipedia
for src in utah-utes long-beach-state-beach; do
  rm -f "archives/$src/statcrew_boxscores_pending.json"
  echo "=== harvesting $src ==="
  python3 -u harvest_statcrew.py $src 2>&1 | tail -5
done
echo "VARIANTD COMPLETE"
