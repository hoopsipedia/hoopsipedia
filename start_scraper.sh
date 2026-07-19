#!/bin/bash
# Wait for SR rate limit to clear, then start sequential scraper
cd "$(dirname "$0")"
LOG="scrape_boxscores.log"

echo "" >> "$LOG"
echo "$(date): Waiting for SR rate limit to clear..." >> "$LOG"

while true; do
    status=$(curl -s -o /dev/null -w "%{http_code}" -m 10 "https://www.sports-reference.com/cbb/postseason/men/2024-ncaa.html" 2>/dev/null)
    if [ "$status" = "200" ]; then
        echo "$(date): SR accessible (status=200)! Starting scraper..." >> "$LOG"
        break
    else
        echo "$(date): Still rate limited (status=$status), waiting 60s..." >> "$LOG"
        sleep 60
    fi
done

# Start the sequential scraper
exec ./scrape_sequential_boxscores.sh
