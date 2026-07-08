#!/bin/bash
# Overnight SR run 2026-07-08:
#   Phase A: pre-1985 tournament box scores (1984 -> 1939, newest first)
#   Phase B: regular-season box-score coverage probe (by decade)
# Adaptive throttle: 3.2s base (SR policy ~20 req/min); 429 => 15 min cooloff.
cd "$(dirname "$0")"
LOG="overnight_sr_run.log"
DELAY=3.2

echo "$(date): OVERNIGHT RUN START (delay=${DELAY}s)" >> "$LOG"

# --- Phase A: pre-1985 tournaments, newest first ---
for year in $(seq 1984 -1 1939); do
    echo "$(date): ===== YEAR $year =====" >> "$LOG"
    python3 -u scrape_boxscores.py --year "$year" --output sr_boxscores.json --delay "$DELAY" >> "$LOG" 2>&1

    # 429-aware backoff: check recent log lines
    if tail -8 "$LOG" | grep -q "429"; then
        echo "$(date): 429 detected — cooling off 15 min, then slowing to 5s" >> "$LOG"
        DELAY=5
        sleep 900
    fi
    sleep 8
done
echo "$(date): PHASE A COMPLETE" >> "$LOG"
python3 -c "
import json
d=json.load(open('sr_boxscores.json'))
ks=[k for k in d if k!='_metadata']
pre=[k for k in ks if k[:4].isdigit() and int(k[:4])<1985]
print('total box scores:', len(ks), '| pre-1985:', len(pre))
" >> "$LOG" 2>&1

# --- Phase B: coverage probe ---
echo "$(date): PHASE B PROBE START" >> "$LOG"
python3 -u sr_coverage_probe.py --delay "$DELAY" >> "$LOG" 2>&1
echo "$(date): OVERNIGHT RUN COMPLETE" >> "$LOG"
