#!/bin/zsh
for src in rutgers northerncolorado portlandstate wrightstate arizonastate california umass bucknell; do
  echo "=== $src ==="
  python3 -u harvest_statcrew.py $src 2>&1 | tail -2
done
echo "SWEEP6 COMPLETE"
