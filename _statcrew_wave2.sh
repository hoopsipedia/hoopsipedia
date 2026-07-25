#!/bin/zsh
# Census wave-2 — 72 confirmed sport-specific programs, biggest first.
# Sequential + resumable: skips any program whose pending already exists, so a
# restart after an archive.org throttle/crash picks up where it left off.
cd /Users/joshdavis/Projects/hoopsipedia
KEYS=$(cat _wave2_keys.txt)
n=$(echo $KEYS | wc -w | tr -d ' ')
i=0
for src in ${(z)KEYS}; do
  i=$((i+1))
  if [ -f "archives/$src/statcrew_boxscores_pending.json" ]; then
    echo "[$i/$n] skip $src (already harvested)"
    continue
  fi
  echo "=== [$i/$n] $src ==="
  python3 -u harvest_statcrew.py $src 2>&1 | tail -3
done
echo "WAVE2 COMPLETE"
