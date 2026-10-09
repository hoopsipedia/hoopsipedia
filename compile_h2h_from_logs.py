#!/usr/bin/env python3
"""Build h2h.json from our own game logs instead of scraping Sports Reference.

The scraped file (compile_h2h.py) was last run 2026-04-08 and only knows
D1-vs-D1 games since 1949-50; by October 2026 it disagreed with the logs
on 28% of pairs with 10+ meetings. The logs are the source of truth for
every other page, so head-to-head comes from them too.

Each game is keyed by (date, lower id, higher id) and counted once even
when both programs' logs carry it; a game present in only one log still
counts. Only pairs where both ids are programs in data.json are written.
Output shape is unchanged: {teamId: {oppId: {"w", "l", "g"}}}.
"""
import json, os, sys
from collections import defaultdict
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
from json_io import save_json_atomic

def main():
    H = json.load(open(os.path.join(ROOT, 'data.json')))['H']
    idx = json.load(open(os.path.join(ROOT, 'games', 'index.json')))
    games = {}  # (date, a, b) -> winner id or None
    for tid in idx:
        if tid not in H:
            continue
        d = json.load(open(os.path.join(ROOT, 'games', f'{tid}.json')))
        for g in (d.get('games', d) if isinstance(d, dict) else d):
            opp = str(g.get('opp') or '')
            if not opp or opp not in H or opp == tid or not g.get('date'):
                continue
            a, b = sorted([tid, opp])
            key = (g['date'], a, b)
            winner = tid if g.get('w') else opp
            if key in games and games[key] != winner:
                # the two logs disagree on the winner — trust the log whose team won by score
                try:
                    winner = tid if int(g['pts']) > int(g['opp_pts']) else opp
                except (TypeError, ValueError, KeyError):
                    pass
            games[key] = winner
    h2h = defaultdict(lambda: defaultdict(lambda: {'w': 0, 'l': 0, 'g': 0}))
    for (date, a, b), winner in games.items():
        for me, them in ((a, b), (b, a)):
            rec = h2h[me][them]; rec['g'] += 1
            if winner == me: rec['w'] += 1
            else: rec['l'] += 1
    out = {k: dict(v) for k, v in h2h.items()}
    save_json_atomic(os.path.join(ROOT, 'h2h.json'), out, separators=(',', ':'))
    pairs = sum(len(v) for v in out.values()) // 2
    print(f'h2h.json: {len(out)} programs, {pairs:,} pairs, {len(games):,} games')
    for a, b, label in (('150', '153', 'Duke–UNC'), ('153', '152', 'UNC–NC State'), ('356', '142', 'Illinois–Missouri'), ('96', '97', 'Kentucky–Louisville')):
        print(f'  {label}: {out.get(a, {}).get(b)}')

if __name__ == '__main__':
    main()
