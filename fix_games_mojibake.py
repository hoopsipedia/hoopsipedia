#!/usr/bin/env python3
"""Repair double-encoded UTF-8 (mojibake) in the games files.

Some scrape path decoded UTF-8 bytes as latin-1, so every en-dash and
accented character in opp_slug/arena strings was mangled: the en-dash
U+2013 (bytes E2 80 93) became the three characters 'a-circumflex + two
controls', 'Coliseo Ruben Rodriguez' lost its accents, etc. 1,997 rows
were affected on 2026-07-28 — non-D1 opponent names ('Southern-New
Orleans', 'Michigan-Dearborn', 'Embry-Riddle') and arena names
('Oakland-Alameda County Coliseum Arena', 'Dunn-Oliver Acadome').

The repair is the classic round-trip: re-encode the mangled string as
latin-1 and decode as UTF-8. Only applied when the round-trip succeeds,
so correctly-encoded text (which fails the round-trip) is never touched.
Slug matching is unaffected either way (slugify folds any dash), but the
strings render on team pages.

Idempotent: fixed strings no longer round-trip differently.
Run:  python3 fix_games_mojibake.py
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from json_io import save_json_atomic

ROOT = os.path.dirname(os.path.abspath(__file__))
NON_ASCII = re.compile(r'[^\x00-\x7f]')


def demojibake(s):
    if not NON_ASCII.search(s):
        return s
    try:
        return s.encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def main():
    total = 0
    for i in (1, 2, 3):
        path = os.path.join(ROOT, 'games_{}.json'.format(i))
        d = json.load(open(path))
        n = 0
        for v in d.values():
            for g in (v['games'] if isinstance(v, dict) else v):
                for f in ('opp_slug', 'arena'):
                    s = g.get(f)
                    if isinstance(s, str):
                        fixed = demojibake(s)
                        if fixed != s:
                            g[f] = fixed
                            n += 1
        if n:
            save_json_atomic(path, d, separators=(',', ':'))
        print('games_{}.json: fixed {}'.format(i, n))
        total += n
    if total:
        print('re-run scripts/split_games.py to refresh the games/ slices')
    else:
        print('Nothing to do.')


if __name__ == '__main__':
    main()
