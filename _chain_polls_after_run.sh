#!/bin/bash
# Waits for the overnight SR run to finish, then harvests AP polls 1949-2026.
cd "$(dirname "$0")"
while ! grep -q "OVERNIGHT RUN COMPLETE" overnight_sr_run.log 2>/dev/null; do
  sleep 120
done
sleep 30  # let the SR budget breathe
echo "$(date): POLLS HARVEST START" >> overnight_sr_run.log
python3 -u harvest_ap_polls.py --delay 3.2 >> polls_harvest.log 2>&1
echo "$(date): POLLS HARVEST COMPLETE" >> overnight_sr_run.log
