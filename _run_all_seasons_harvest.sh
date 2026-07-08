#!/bin/bash
# Track 1: harvest EVERY pre-2002 season's available SR box scores.
# Waits for the running 1979/1976 chain, then walks 2001 -> 1950
# (newest first = richest coverage first). Resumable: the harvester
# skips keys already in sr_boxscores.json.
cd "$(dirname "$0")"
while ! grep -q "OLD SEASON HARVESTS COMPLETE" harvest_1976.log 2>/dev/null; do sleep 300; done
for yr in $(seq 2001 -1 1950); do
  if [ "$yr" = "1979" ] || [ "$yr" = "1976" ]; then continue; fi
  echo "$(date): season $yr" >> harvest_all.log
  python3 -u harvest_season_boxscores.py --season $yr --delay 3.2 >> harvest_all.log 2>&1
  sleep 20
done
echo "ALL SEASONS HARVEST COMPLETE" >> harvest_all.log
