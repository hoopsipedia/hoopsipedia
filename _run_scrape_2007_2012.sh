#!/bin/bash
cd /Users/joshdavis/Projects/hoopsipedia
export PYTHONUNBUFFERED=1

LOG="/Users/joshdavis/Projects/hoopsipedia/_scrape_2007_2012.log"
echo "=== Scrape started at $(date) ===" > "$LOG"

# Wait for SR rate limit to clear
echo "Waiting for SR rate limit to clear..." >> "$LOG"
while true; do
    STATUS=$(python3 -c "
import requests
s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15'})
r = s.get('https://www.sports-reference.com/cbb/postseason/men/2007-ncaa.html', timeout=20)
print(r.status_code)
" 2>/dev/null)
    
    if [ "$STATUS" = "200" ]; then
        echo "SR is accessible (status 200)! Starting scrape at $(date)" >> "$LOG"
        break
    else
        echo "Still blocked (status $STATUS) at $(date). Waiting 120s..." >> "$LOG"
        sleep 120
    fi
done

# Run the actual scrape
python3 scrape_boxscores.py --years 2007-2012 --output sr_boxscores_2007_2012.json --delay 4 >> "$LOG" 2>&1

echo "=== Scrape finished at $(date) ===" >> "$LOG"
