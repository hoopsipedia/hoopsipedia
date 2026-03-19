#!/bin/bash
# Scrape the 9 WCC teams that were added after the main scrape chain started
cd /Users/joshdavis/Projects/hoopsipedia

echo "=========================================="
echo "WCC REMAINING TEAMS SCRAPE"
echo "Time: $(date)"
echo "=========================================="

# Wait for the ENTIRE main scrape chain to finish (avoid parallel rate limiting)
echo "Waiting for main scrape chain to complete..."
while ! grep -q "ALL SCRAPING COMPLETE" /private/tmp/scrape_chain.output 2>/dev/null; do
    sleep 60
done
echo "Main scrape chain done! Starting remaining WCC teams..."
sleep 120  # Extra cooldown before hitting Sports Reference again

PYTHONUNBUFFERED=1 python3 compile_schedules.py --conf "WCC"

# Rebuild coaching data with new teams
python3 compile_coaches.py

# Push to live
git add games.json seasons.json data.json && git commit -m "Add remaining WCC teams (complete 12-team conference)

Santa Clara, LMU, Pepperdine, Portland, San Diego, Pacific, Seattle, Oregon State, Washington State

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>" && git push origin main

echo ""
echo "WCC COMPLETE (12/12) ✅ at $(date)"
