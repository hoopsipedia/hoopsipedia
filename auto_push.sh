#!/bin/bash
cd /Users/joshdavis/Projects/hoopsipedia
LAST_COUNT=153

while true; do
    sleep 120  # Check every 2 minutes
    
    CURRENT=$(python3 -c "
import json
with open('games.json') as f:
    data = json.load(f)
print(len(data))
" 2>/dev/null)
    
    if [ -z "$CURRENT" ]; then continue; fi
    
    DIFF=$((CURRENT - LAST_COUNT))
    
    if [ "$DIFF" -ge 10 ]; then
        echo "$(date): $CURRENT teams (up $DIFF) — re-splitting and pushing..."
        
        # Re-split games
        python3 -c "
import json, os
with open('games.json') as f:
    data = json.load(f)
keys = list(data.keys())
mid = len(keys) // 2
with open('games_1.json', 'w') as f:
    json.dump({k: data[k] for k in keys[:mid]}, f)
with open('games_2.json', 'w') as f:
    json.dump({k: data[k] for k in keys[mid:]}, f)
games = sum(len(v.get('games',[])) for v in data.values())
print(f'Split: {len(data)} teams, {games} games')
"
        
        # Commit and push
        git add games_1.json games_2.json
        git commit -m "Auto-update: $CURRENT teams scraped ($DIFF new since last push)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
        if git push origin main; then
            LAST_COUNT=$CURRENT
            echo "$(date): Pushed $CURRENT teams live"
        else
            # Push failed (network, pre-push hook, remote rejection, ...).
            # Do NOT exit, do NOT force, NEVER --no-verify — the commit is local,
            # so leave LAST_COUNT unchanged and retry on the next cycle.
            echo "$(date): ERROR — git push failed for $CURRENT teams; will retry next cycle" >&2
        fi
    fi
    
    # Check if scrapes are still running
    PROCS=$(ps aux | grep compile_schedules | grep -v grep | wc -l | tr -d ' ')
    if [ "$PROCS" -eq "0" ]; then
        # Final push if anything remaining
        if [ "$CURRENT" -gt "$LAST_COUNT" ]; then
            echo "$(date): Scrapes done — final push of $CURRENT teams"
            python3 -c "
import json
with open('games.json') as f:
    data = json.load(f)
keys = list(data.keys())
mid = len(keys) // 2
with open('games_1.json', 'w') as f:
    json.dump({k: data[k] for k in keys[:mid]}, f)
with open('games_2.json', 'w') as f:
    json.dump({k: data[k] for k in keys[mid:]}, f)
"
            git add games_1.json games_2.json
            git commit -m "Final scrape update: $CURRENT teams total

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
            if ! git push origin main; then
                # Final push failed — keep the monitor alive so it retries next
                # cycle instead of exiting with unpushed work.
                echo "$(date): ERROR — final git push failed; will retry next cycle" >&2
                continue
            fi
        fi
        echo "$(date): All scrapes complete. Exiting monitor."
        exit 0
    fi
done
