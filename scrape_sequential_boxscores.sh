#!/bin/bash
# Sequential box score scraper — one year at a time, 7-second delays
# Respects SR rate limits, saves incrementally, unbuffered output
cd "$(dirname "$0")"

OUTPUT="sr_boxscores.json"
DELAY=7
LOG="scrape_boxscores.log"

echo "$(date): Starting sequential scrape into $OUTPUT" >> "$LOG"

# Years to scrape - all tournament years (skip 2020 - COVID)
YEARS=(1985 1986 1987 1988 1989 1990 1991 1992 1993 1994 1995 1996 1997 1998 1999 2000 2001 2002 2003 2004 2005 2006 2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2021 2022 2023 2024 2025 2026)

for year in "${YEARS[@]}"; do
    echo "$(date): ===== YEAR $year =====" >> "$LOG"

    # Use -u for unbuffered Python output
    python3 -u scrape_boxscores.py --year "$year" --output "$OUTPUT" --delay "$DELAY" >> "$LOG" 2>&1
    exit_code=$?

    if [ $exit_code -ne 0 ]; then
        echo "$(date): Year $year exited with code $exit_code" >> "$LOG"
    fi

    # Check last few lines for rate limiting
    if tail -5 "$LOG" | grep -q "429"; then
        echo "$(date): Rate limited! Waiting 10 minutes..." >> "$LOG"
        sleep 600
    fi

    # Pause between years (longer to be safe)
    sleep 15
done

echo "$(date): COMPLETE" >> "$LOG"
count=$(python3 -c "import json; d=json.load(open('$OUTPUT')); print(len([k for k in d if k != '_metadata']))")
echo "Total box scores: $count" >> "$LOG"
