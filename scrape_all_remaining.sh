#!/bin/bash
# Auto-scrape all remaining teams and push every 10 teams
# Run with: nohup bash scrape_all_remaining.sh > scrape_auto.log 2>&1 &

cd /Users/joshdavis/Projects/hoopsipedia

PUSH_EVERY=10
LOG="scrape_auto.log"

echo "=== Auto-scrape started at $(date) ===" | tee -a "$LOG"

# Get remaining team IDs
REMAINING=$(python3 -c "
import json
scraped = set()
for fn in ['games_1.json', 'games_2.json', 'games_3.json']:
    with open(fn) as f:
        scraped.update(json.load(f).keys())
mapping = json.load(open('espn_to_sr.json'))
remaining = sorted(set(mapping.keys()) - scraped - {'2609'})
print(','.join(remaining))
")

TOTAL=$(echo "$REMAINING" | tr ',' '\n' | wc -l | tr -d ' ')
echo "Remaining teams to scrape: $TOTAL" | tee -a "$LOG"

if [ "$TOTAL" -eq 0 ]; then
    echo "All teams already scraped!" | tee -a "$LOG"
    exit 0
fi

# Convert to array
IFS=',' read -ra IDS <<< "$REMAINING"

BATCH=""
COUNT=0
BATCH_NUM=0
START_TOTAL=$(python3 -c "
import json
s = set()
for fn in ['games_1.json', 'games_2.json', 'games_3.json']:
    with open(fn) as f: s.update(json.load(f).keys())
print(len(s))
")

for ID in "${IDS[@]}"; do
    if [ -z "$BATCH" ]; then
        BATCH="$ID"
    else
        BATCH="$BATCH,$ID"
    fi
    COUNT=$((COUNT + 1))

    if [ "$COUNT" -ge "$PUSH_EVERY" ]; then
        BATCH_NUM=$((BATCH_NUM + 1))
        echo "" | tee -a "$LOG"
        echo "--- Batch $BATCH_NUM ($COUNT teams): $BATCH ---" | tee -a "$LOG"
        echo "Started at $(date)" | tee -a "$LOG"

        python3 _scrape_sequential.py "$BATCH" 2>&1 | tee -a "$LOG"

        # Get current total
        CURRENT=$(python3 -c "
import json
s = set()
for fn in ['games_1.json', 'games_2.json', 'games_3.json']:
    with open(fn) as f: s.update(json.load(f).keys())
print(len(s))
")
        echo "Total scraped: $CURRENT/373" | tee -a "$LOG"

        # Git push
        echo "Pushing to git..." | tee -a "$LOG"
        git add games_1.json games_2.json games_3.json
        git commit -m "Scrape progress: $CURRENT teams (auto-batch $BATCH_NUM)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
        git push 2>&1 | tee -a "$LOG"

        if [ $? -ne 0 ]; then
            echo "WARNING: git push failed, pulling and retrying..." | tee -a "$LOG"
            git pull --rebase 2>&1 | tee -a "$LOG"
            git push 2>&1 | tee -a "$LOG"
        fi

        echo "Batch $BATCH_NUM complete at $(date)" | tee -a "$LOG"

        # Reset for next batch
        BATCH=""
        COUNT=0
    fi
done

# Handle any leftover teams in final partial batch
if [ -n "$BATCH" ]; then
    BATCH_NUM=$((BATCH_NUM + 1))
    echo "" | tee -a "$LOG"
    echo "--- Final batch $BATCH_NUM ($COUNT teams): $BATCH ---" | tee -a "$LOG"
    echo "Started at $(date)" | tee -a "$LOG"

    python3 _scrape_sequential.py "$BATCH" 2>&1 | tee -a "$LOG"

    CURRENT=$(python3 -c "
import json
s = set()
for fn in ['games_1.json', 'games_2.json', 'games_3.json']:
    with open(fn) as f: s.update(json.load(f).keys())
print(len(s))
")

    git add games_1.json games_2.json games_3.json
    git commit -m "Scrape progress: $CURRENT teams (auto-batch $BATCH_NUM - final)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
    git push 2>&1 | tee -a "$LOG"

    if [ $? -ne 0 ]; then
        git pull --rebase 2>&1 | tee -a "$LOG"
        git push 2>&1 | tee -a "$LOG"
    fi
fi

FINAL=$(python3 -c "
import json
s = set()
for fn in ['games_1.json', 'games_2.json', 'games_3.json']:
    with open(fn) as f: s.update(json.load(f).keys())
print(len(s))
")

echo "" | tee -a "$LOG"
echo "=== Auto-scrape COMPLETE at $(date) ===" | tee -a "$LOG"
echo "Final total: $FINAL/373 teams" | tee -a "$LOG"
echo "Started at $START_TOTAL, scraped $((FINAL - START_TOTAL)) new teams" | tee -a "$LOG"
