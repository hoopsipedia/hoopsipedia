#!/bin/zsh
for src in ucriverside clemson uconn airforce brown sanfrancisco ohio rutgers northerncolorado portlandstate wrightstate arizonastate california umass bucknell; do
  echo "=== $src ==="
  python3 -u harvest_statcrew.py $src 2>&1 | tail -2
done
echo "SWEEP5 COMPLETE"
