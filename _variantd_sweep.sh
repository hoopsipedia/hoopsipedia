#!/bin/zsh
# Variant-D re-sweep: re-harvest all sub-60-yield programs with the new AP-agate
# parser to recover box scores that were silently dropped as parse_fail.
# Overwrites each pending; the store merge is additive+idempotent, so a partial
# run (archive.org throttle) is safe — worst case it recovers nothing new.
cd /Users/joshdavis/Projects/hoopsipedia
KEYS=$(cat _variantd_sweep_keys.txt)
n=$(echo $KEYS | wc -w | tr -d ' ')
i=0
for src in ${(z)KEYS}; do
  i=$((i+1))
  rm -f "archives/$src/statcrew_boxscores_pending.json"
  echo "=== [$i/$n] $src ==="
  python3 -u harvest_statcrew.py $src 2>&1 | grep -E 'STATS|wrote|games from CDX|gave up' | tail -3
done
echo "VARIANTD_SWEEP COMPLETE"
