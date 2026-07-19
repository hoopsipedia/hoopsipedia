#!/bin/bash
# Wait for SR rate limit to clear, then run the box score scraper
# This script handles the full lifecycle: wait -> scrape -> report

LOG="/Users/joshdavis/Projects/hoopsipedia/_scrape_2021_2026.log"
echo "$(date): Starting rate limit wait..." > "$LOG"

# Wait for rate limit to clear (check every 2 minutes)
while true; do
    code=$(curl -s -o /dev/null -w "%{http_code}" -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15" "https://www.sports-reference.com/cbb/" 2>/dev/null)
    echo "$(date): HTTP $code" >> "$LOG"
    if [ "$code" = "200" ]; then
        echo "$(date): Rate limit cleared!" >> "$LOG"
        break
    fi
    sleep 120
done

# Small additional cooldown
sleep 10

# Run the scraper
echo "$(date): Starting scraper..." >> "$LOG"
cd /Users/joshdavis/Projects/hoopsipedia
PYTHONUNBUFFERED=1 python3 scrape_boxscores.py --years 2021-2026 --output sr_boxscores_2021_2026.json --delay 4 >> "$LOG" 2>&1
echo "$(date): Scraper finished with exit code $?" >> "$LOG"
echo "SCRAPE_COMPLETE" >> "$LOG"
