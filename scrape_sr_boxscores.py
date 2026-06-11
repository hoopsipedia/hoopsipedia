#!/usr/bin/env python3
"""
DEPRECATED — do not use.

This script (pre-2005 tournament upset scraper, regex-based) has been
consolidated into scrape_boxscores.py, which uses the shared sr_parser.py
library and covers all year ranges. The team-name -> SR slug mappings and
tournament date tables that lived here were absorbed into sr_parser.py
(TEAM_SR_SLUGS, FIRST_ROUND_DATES).

Equivalent usage:
    python3 scrape_boxscores.py --years 1985-2004

This file is kept as a stub until the consolidated scraper has run
successfully in production; it will be deleted afterwards.
"""

import sys


def main():
    print("DEPRECATED: use scrape_boxscores.py")
    print("  e.g. python3 scrape_boxscores.py --years 1985-2004")
    sys.exit(1)


if __name__ == "__main__":
    main()
