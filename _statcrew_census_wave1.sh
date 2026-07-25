#!/bin/zsh
# Census wave 1 — confirmed m-baskbl hits, biggest first. Sequential + gentle
# so it coexists with the running domain census on archive.org.
cd /Users/joshdavis/Projects/hoopsipedia
for src in washington bostoncollege tcu oregon lafayette butler providence ncstate coloradostate marist fairfield clevelandstate colorado cornell; do
  echo "=== $src ==="
  python3 -u harvest_statcrew.py $src 2>&1 | tail -3
done
echo "CENSUS_WAVE1 COMPLETE"
