#!/bin/bash
# Sequential scrape pipeline - runs everything one at a time to avoid rate limits
# Auto-pushes to live after each conference/batch

cd /Users/joshdavis/Projects/hoopsipedia

echo "=========================================="
echo "SCRAPE PIPELINE STARTED at $(date)"
echo "Waiting 10 minutes for rate limit to clear..."
echo "=========================================="
sleep 600

# Phase 1: Finish SEC
echo ""
echo "=========================================="
echo "PHASE 1: SEC (continuing from where we left off)"
echo "Time: $(date)"
echo "=========================================="
PYTHONUNBUFFERED=1 python3 compile_schedules.py --conf SEC
git add games.json && git commit -m "Add SEC game data

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>" && git push origin main
echo "SEC PUSHED LIVE ✅"

# Phase 2: Small conference tournament teams
echo ""
echo "=========================================="
echo "PHASE 2: Small conference tournament teams"
echo "Time: $(date)"
echo "=========================================="
PYTHONUNBUFFERED=1 python3 compile_schedules.py --slugs akron,cal-baptist,furman,hawaii,high-point,hofstra,howard,idaho,lehigh,long-island-university,mcneese-state,miami-oh,north-dakota-state,northern-iowa,penn,prairie-view,santa-clara,siena,tennessee-state,troy,umbc,utah-state,wright-state
git add games.json && git commit -m "Add game data for small conference tournament teams

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>" && git push origin main
echo "SMALL CONF TEAMS PUSHED LIVE ✅"

# Phase 3: Major conferences one at a time
CONFERENCES=("Big Ten" "Big 12" "Big East" "WCC" "AAC" "MWC" "A-10")

for CONF in "${CONFERENCES[@]}"; do
    echo ""
    echo "=========================================="
    echo "PHASE 3: $CONF"
    echo "Time: $(date)"
    echo "=========================================="
    PYTHONUNBUFFERED=1 python3 compile_schedules.py --conf "$CONF"
    git add games.json && git commit -m "Add ${CONF} game data

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>" && git push origin main
    echo "$CONF PUSHED LIVE ✅"
done

echo ""
echo "=========================================="
echo "ALL SCRAPING COMPLETE at $(date)"
echo "=========================================="
