#!/bin/zsh
for src in arizonastate california clemson uconn umass bucknell airforce sanfrancisco ohio portlandstate northerncolorado; do
  echo "=== $src ==="
  python3 -u harvest_statcrew.py $src 2>&1 | tail -2
done
echo "SWEEP2 COMPLETE"
