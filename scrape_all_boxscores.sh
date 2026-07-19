#!/bin/bash
# Sequential box score scraper — runs ONE year at a time with 6-second delays
# to avoid SR rate limiting. Saves incrementally to sr_boxscores_all.json.
#
# Usage: ./scrape_all_boxscores.sh
# Resume: If interrupted, it picks up where it left off (skips existing keys).

cd "$(dirname "$0")"

OUTPUT="sr_boxscores_all.json"
DELAY=6
LOG="scrape_boxscores.log"

echo "$(date): Starting sequential box score scrape" | tee -a "$LOG"
echo "Output: $OUTPUT, Delay: ${DELAY}s" | tee -a "$LOG"

# All tournament years from 1985 to 2026 (skip 2020 - COVID)
YEARS=(1985 1986 1987 1988 1989 1990 1991 1992 1993 1994 1995 1996 1997 1998 1999 2000 2001 2002 2003 2004 2005 2006 2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2021 2022 2023 2024 2025 2026)

for year in "${YEARS[@]}"; do
    echo "" | tee -a "$LOG"
    echo "$(date): ===== YEAR $year =====" | tee -a "$LOG"
    python3 scrape_boxscores.py --year "$year" --output "$OUTPUT" --delay "$DELAY" 2>&1 | tee -a "$LOG"

    # Check if we got rate limited
    if grep -q "429" <<< "$(tail -5 "$LOG")"; then
        echo "$(date): Rate limited! Waiting 5 minutes..." | tee -a "$LOG"
        sleep 300
    fi

    # Brief pause between years
    sleep 10
done

echo "" | tee -a "$LOG"
echo "$(date): All years complete!" | tee -a "$LOG"

# Count results
if [ -f "$OUTPUT" ]; then
    count=$(python3 -c "import json; d=json.load(open('$OUTPUT')); print(len([k for k in d if k != '_metadata']))")
    echo "Total box scores: $count" | tee -a "$LOG"
fi
