#!/bin/zsh
# One program: skip if already harvested, else harvest and echo full tail.
cd /Users/joshdavis/Projects/hoopsipedia
src=$1
f="archives/$src/statcrew_boxscores_pending.json"
if [ -f "$f" ]; then echo "[skip] $src (already harvested)"; exit 0; fi
out=$(python3 -u harvest_statcrew.py "$src" 2>&1 | tail -4)
echo "=== $src ==="
echo "$out"
