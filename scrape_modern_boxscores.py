#!/usr/bin/env python3
"""
DEPRECATED — do not use.

This script (2005+ pre-mapped URL scraper, regex-based) has been consolidated
into scrape_boxscores.py, which uses the shared sr_parser.py library. The 404
schedule-page fallback that lived here was absorbed into sr_parser.py
(find_alt_boxscore_url).

Equivalent usage (same boxscore_urls.json input, same sr_boxscores_modern.json
output):
    python3 scrape_boxscores.py --urls-file boxscore_urls.json [--limit N] [--start N]

This file is kept as a stub until the consolidated scraper has run
successfully in production; it will be deleted afterwards.
"""

import sys


def main():
    print("DEPRECATED: use scrape_boxscores.py")
    print("  e.g. python3 scrape_boxscores.py --urls-file boxscore_urls.json")
    sys.exit(1)


if __name__ == "__main__":
    main()
