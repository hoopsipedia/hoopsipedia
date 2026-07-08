#!/usr/bin/env python3
"""Split game_ids_bulk.json into per-team game_ids/{espnId}.json slices.

The bulk map is ~11MB — fine as a data store, far too big for browsers.
Each slice maps eventId -> entry for events involving that team, so the
frontend can lazy-load one team's map (~10-60KB) when rendering a season
page's box-score links.

Deterministic, atomic, idempotent — mirrors scripts/split_games.py.
Validates: every event appears in exactly the slices of its two teams,
and slice totals reconcile with the bulk count.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from json_io import save_json_atomic

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, 'game_ids')


def main():
    with open(os.path.join(ROOT, 'game_ids_bulk.json')) as f:
        bulk = json.load(f)
    games = bulk['games']

    per_team = {}
    for eid, g in games.items():
        for tid in (str(g['t1']), str(g['t2'])):
            per_team.setdefault(tid, {})[eid] = g

    os.makedirs(OUT_DIR, exist_ok=True)
    index = {}
    for tid in sorted(per_team, key=lambda x: int(x) if x.isdigit() else 10**9):
        save_json_atomic(os.path.join(OUT_DIR, f'{tid}.json'),
                         per_team[tid], separators=(',', ':'))
        index[tid] = len(per_team[tid])
    save_json_atomic(os.path.join(OUT_DIR, 'index.json'), index,
                     separators=(',', ':'))

    # validation: sum of slice entries == 2 * bulk (each event in 2 slices)
    total = sum(index.values())
    expected = 2 * len(games)
    ok = total == expected
    print(f'wrote {len(index)} team slices to game_ids/ '
          f'({total} slice entries vs expected {expected}) '
          f'{"OK" if ok else "MISMATCH"}')
    if not ok:
        sys.exit(1)


if __name__ == '__main__':
    main()
