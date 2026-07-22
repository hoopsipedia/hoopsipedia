#!/bin/zsh
for src in bowlinggreen chicagostate northerniowa arizonastate california clemson umass bucknell airforce uconn brown sanfrancisco ohio rutgers northerncolorado portlandstate ucriverside wrightstate; do
  echo "=== $src ==="
  python3 -u harvest_statcrew.py $src 2>&1 | tail -3
done
echo "SWEEP COMPLETE"
