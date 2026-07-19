#!/bin/bash
cd /Users/joshdavis/Projects/hoopsipedia

echo "=== Chain scrape restarted at $(date) ===" >> scrape_chain_log.txt

for i in $(seq 1 30); do
    echo "--- Batch $i starting at $(date) ---" >> scrape_chain_log.txt
    python3 -u scrape_batch.py --count 1 >> scrape_chain_log.txt 2>&1
    RET=$?
    echo "--- Batch $i finished (exit $RET) at $(date) ---" >> scrape_chain_log.txt
    
    python3 -c "
import json
total = sum(len(json.load(open(f))) for f in ['games_1.json','games_2.json','games_3.json'])
print(f'Current total: {total} teams')
if total >= 266:
    print('TARGET REACHED! 266+ teams')
" >> scrape_chain_log.txt 2>&1
    
    # 60 second pause to be gentle with SR
    sleep 60
done

echo "=== Chain scrape finished at $(date) ===" >> scrape_chain_log.txt
