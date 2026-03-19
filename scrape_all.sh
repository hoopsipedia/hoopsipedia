#!/bin/bash
# Chain scrape for full tournament coverage
# SEC is already running separately

echo "=========================================="
echo "PHASE 1: Small conference tournament teams"
echo "Time: $(date)"
echo "=========================================="
PYTHONUNBUFFERED=1 python3 compile_schedules.py --slugs akron,cal-baptist,furman,hawaii,high-point,hofstra,howard,idaho,lehigh,long-island-university,mcneese-state,miami-oh,north-dakota-state,northern-iowa,penn,prairie-view,santa-clara,siena,tennessee-state,troy,umbc,utah-state,wright-state

echo ""
echo "=========================================="
echo "PHASE 2: Major conferences"
echo "Time: $(date)"
echo "=========================================="

CONFERENCES=("Big Ten" "Big 12" "Big East" "AAC" "WCC" "MWC" "A-10")

for CONF in "${CONFERENCES[@]}"; do
    echo ""
    echo "=========================================="
    echo "Starting: $CONF"
    echo "Time: $(date)"
    echo "=========================================="
    PYTHONUNBUFFERED=1 python3 compile_schedules.py --conf "$CONF"
done

echo ""
echo "ALL SCRAPING COMPLETE at $(date)"
