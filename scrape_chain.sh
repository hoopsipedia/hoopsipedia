#!/bin/bash
# Sequential scrape pipeline - runs everything one at a time to avoid rate limits
# Auto-pushes to live after each team/conference

cd /Users/joshdavis/Projects/hoopsipedia

echo "=========================================="
echo "SCRAPE PIPELINE STARTED at $(date)"
echo "=========================================="

# Phase 1: Small conference tournament teams (one at a time, push after each)
SMALL_CONF_SLUGS=(california-baptist howard idaho lehigh long-island-university mcneese-state miami-oh north-dakota-state northern-iowa penn prairie-view santa-clara siena tennessee-state troy umbc utah-state wright-state)

echo ""
echo "=========================================="
echo "PHASE 1: Small conference tournament teams (${#SMALL_CONF_SLUGS[@]} remaining)"
echo "Time: $(date)"
echo "=========================================="

for SLUG in "${SMALL_CONF_SLUGS[@]}"; do
    echo ""
    echo "--- Scraping: $SLUG ---"
    PYTHONUNBUFFERED=1 python3 compile_schedules.py --slugs "$SLUG"
    git add games.json && git commit -m "Add ${SLUG} game data

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>" && git push origin main
    echo "$SLUG PUSHED LIVE ✅"
done

echo ""
echo "SMALL CONF TEAMS COMPLETE ✅"

# Phase 2: Major conferences one at a time
CONFERENCES=("Big Ten" "Big 12" "Big East" "WCC" "AAC" "MWC" "A-10")

for CONF in "${CONFERENCES[@]}"; do
    echo ""
    echo "=========================================="
    echo "PHASE 2: $CONF"
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
