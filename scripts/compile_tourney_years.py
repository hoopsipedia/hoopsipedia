#!/usr/bin/env python3
"""Derive the YEARS of each program's Final Fours, Elite Eights and Sweet 16s.

data.json's record book (H) carries counts for these but years only for
titles, which is why the Blue Blood Index could not era-weight deep runs.
This reads every program's season rows and writes tourney_years.json:

  {"150": {"ff": [1963, 1964, ...], "e8": [...], "s16": [...]}, ...}

Rules: vacated seasons (rows synthesized from the game log) are skipped per
the vacated-games policy; a Final Four counts as an Elite Eight and a Sweet
16 too; Sweet 16s count from 1975, when fields reached 32 teams and the
regional semifinal stopped being a team's first game.

The derived counts disagree with the record book for some programs (the
NCAA's own conventions, missing early rows), so the ranking keeps H's
counts and uses these years only to weight them by era.
"""
import json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from json_io import save_json_atomic

def main():
    H = json.load(open(os.path.join(ROOT, 'data.json')))['H']
    sea = json.load(open(os.path.join(ROOT, 'seasons.json')))
    out = {}
    for tid, v in sea.items():
        if tid not in H:
            continue
        ff, e8, s16 = set(), set(), set()
        for r in v.get('seasons', []):
            if r.get('synthesized'):
                continue
            t = str(r.get('ncaaTourney') or '')
            if not t:
                continue
            y = int(str(r['year'])[:4]) + 1
            if re.search(r'National Final|National Semifinal|\(Final Four\)', t, re.I):
                ff.add(y); e8.add(y); s16.add(y)
            elif re.search(r'Regional Final', t, re.I):
                e8.add(y); s16.add(y)
            elif re.search(r'Regional Semifinal|Third Round', t, re.I):
                s16.add(y)
        out[tid] = {'ff': sorted(ff), 'e8': sorted(e8), 's16': sorted(y for y in s16 if y >= 1975)}
    save_json_atomic(os.path.join(ROOT, 'tourney_years.json'), out, separators=(',', ':'))
    agree = {k: sum(1 for tid in out if len(out[tid][k]) == H[tid][i]) for k, i in (('ff', 8), ('e8', 9), ('s16', 10))}
    print(f"tourney_years.json: {len(out)} programs; derived count == record book for FF {agree['ff']}, E8 {agree['e8']}, S16 {agree['s16']} of {len(out)}")

if __name__ == '__main__':
    main()
