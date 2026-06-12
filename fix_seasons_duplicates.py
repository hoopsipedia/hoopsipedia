#!/usr/bin/env python3
"""Remove impostor season histories from seasons.json.

The original compile_history.py scrape matched school slugs by name-prefix
substring, so 16 small schools were assigned a flagship program's
byte-identical season history (e.g. USC Upstate carried South Carolina's
2017 Final Four). One additional id (245 Texas A&M) turned out to hold
Texas Longhorns data outright.

Ownership was verified per group (2026-06-12) by recomputing per-season W/L
from each candidate's own game log in games_1/2/3.json and comparing to the
seasons.json records: rightful owners match 57-96% of overlapping seasons
within +/-1 (older logs are incomplete), impostors match 0-17%. Full
evidence in SEASONS_DUPLICATE_REPORT.md.

Deletion is the whole entry: no real history beats wrong history. Victims'
real histories are re-scraped later via compile_history.py (with exact slug
matching).

Idempotent: re-running after the fix makes 0 changes and does not rewrite
the file.

Run:  python3 fix_seasons_duplicates.py [--dry-run]
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from json_io import save_json_atomic

ROOT = os.path.dirname(os.path.abspath(__file__))
SEASONS_PATH = os.path.join(ROOT, 'seasons.json')

# espn_id -> (team it belongs to per data.json H, whose history it actually held)
IMPOSTORS = {
    '50':   ('Florida A&M Rattlers',                'Florida Gators (57)'),
    '526':  ('Florida Gulf Coast Eagles',           'Florida Gators (57)'),
    '2428': ('North Carolina Central Eagles',       'North Carolina Tar Heels (153)'),
    '2448': ('North Carolina A&T Aggies',           'North Carolina Tar Heels (153)'),
    '3084': ('Utah Valley Wolverines',              'Utah Utes (254)'),
    '3101': ('Utah Tech Trailblazers',              'Utah Utes (254)'),
    '2569': ('South Carolina State Bulldogs',       'South Carolina Gamecocks (2579)'),
    '2908': ('South Carolina Upstate Spartans',     'South Carolina Gamecocks (2579)'),
    '2466': ('Northwestern State Demons',           'Northwestern Wildcats (77)'),
    '140':  ('Kansas City Roos',                    'Kansas Jayhawks (2305)'),
    '2623': ('Missouri State Bears',                'Missouri Tigers (142)'),
    # Special case: 245 is mapped to Texas A&M in data.json H, but its
    # seasons entry is Texas Longhorns data (verified: identical W/L to
    # 251's entry in all 119 common seasons; Longhorns coaches Sean
    # Miller/Rodney Terry/Chris Beard/Shaka Smart; 78% within +/-1 vs
    # Texas's game log, 12% vs Texas A&M's). 357 carried the same Texas
    # data. Texas's real entry lives under 251 and is kept.
    '245':  ('Texas A&M Aggies',                    'Texas Longhorns (251)'),
    '357':  ('Texas A&M-Corpus Christi Islanders',  'Texas Longhorns (251)'),
    '2277': ('Houston Christian Huskies',           'Houston Cougars (248)'),
    '2010': ('Alabama A&M Bulldogs',                'Alabama Crimson Tide (333)'),
    '2870': ('Purdue Fort Wayne Mastodons',         'Purdue Boilermakers (2509)'),
    '2634': ('Tennessee State Tigers',              'Tennessee Volunteers (2633)'),
}


def main():
    dry_run = '--dry-run' in sys.argv[1:]
    with open(SEASONS_PATH, 'r', encoding='utf-8') as f:
        seasons = json.load(f)

    removed = []
    for tid in sorted(IMPOSTORS, key=int):
        if tid in seasons:
            del seasons[tid]
            removed.append(tid)

    for tid in removed:
        owner_of, stolen_from = IMPOSTORS[tid]
        print('remove %-5s %-40s [held %s history]' % (tid, owner_of, stolen_from))

    if not removed:
        print('seasons.json already clean: 0 changes, file not rewritten.')
        return

    if dry_run:
        print('DRY RUN: would remove %d entries, file untouched.' % len(removed))
        return

    # Preserve the file's compact formatting (no indent, no spaces).
    save_json_atomic(SEASONS_PATH, seasons, separators=(',', ':'))
    print('removed %d impostor entries; %d teams remain in seasons.json.'
          % (len(removed), len(seasons)))


if __name__ == '__main__':
    main()
