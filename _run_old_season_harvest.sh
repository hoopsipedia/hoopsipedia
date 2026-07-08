#!/bin/bash
# Fixed harvester. 1979+1976 (finish what SR has), then yield tests at
# 2001/1997/1993 to locate SR's true regular-season coverage era before
# committing to a full 1950-2001 sweep.
cd "$(dirname "$0")"
for yr in 1979 1976 2001 1997 1993; do
  echo "$(date): season $yr" >> harvest_chain.log
  python3 -u harvest_season_boxscores.py --season $yr --delay 3.2 >> harvest_chain.log 2>&1
  sleep 20
done
echo "YIELD TEST CHAIN COMPLETE" >> harvest_chain.log
