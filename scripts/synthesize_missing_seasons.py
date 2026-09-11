#!/usr/bin/env python3
"""Add season rows for seasons that exist in the game log but not in the
season table — almost all of them NCAA-vacated years.

Sports-Reference's season table (compile_history.py -> seasons.json) omits
seasons whose results the NCAA vacated (Michigan 1991-92/1992-93, Louisville
2012-13, Memphis 2007-08, Alcorn State 2011-14, ...), but their schedule pages
exist and the gap-fill scraped them into games_1/2/3.json. Result before this
script: 157 team-seasons with >=8 logged games and no season row, so the team
profile's season table skipped them, the sitemap omitted them, and the season
page only rendered thanks to a fallback in the Pages Function.

Per the vacated-games policy (show the history, flag it, never count it in
official totals) this script synthesizes a row from the game log:

  {year, wins, losses, record, winPct, conf, ppg, oppPpg, synthesized: true}

and inserts it in year order. Rows are flagged `synthesized` so:
  * the SPA marks them with an asterisk and a footnote,
  * the Pages Function prints the vacated note on the season page,
  * htss_v2.js and unified_rankings.js SKIP them — a vacated season must not
    enter a program's HTSS top-10 or the all-time leaderboards.

Idempotent: re-running replaces existing synthesized rows and never touches a
real row. Run after any gap-fill or compile_history run (a full recompile
rewrites seasons.json and drops these rows), then scripts/split_seasons.py.

  python3 scripts/synthesize_missing_seasons.py [--dry-run]
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from json_io import save_json_atomic  # noqa: E402

MIN_GAMES = 8


def season_key(date):
    m = re.match(r'(\d{4})-(\d{2})', date or '')
    if not m:
        return None
    y, mo = int(m.group(1)), int(m.group(2))
    start = y if mo >= 8 else y - 1
    return f"{start}-{str(start + 1)[2:]}"


def main():
    dry = '--dry-run' in sys.argv
    H = json.load(open(os.path.join(ROOT, 'data.json')))['H']
    seasons_path = os.path.join(ROOT, 'seasons.json')
    seasons = json.load(open(seasons_path))

    added, replaced = [], 0
    for path in sorted(glob.glob(os.path.join(ROOT, 'games', '*.json'))):
        tid = os.path.basename(path)[:-5]
        if tid == 'index' or tid not in H:
            continue
        payload = json.load(open(path))
        games = payload.get('games', []) if isinstance(payload, dict) else payload
        by_season = {}
        for g in games:
            k = season_key(g.get('date'))
            if k:
                by_season.setdefault(k, []).append(g)

        entry = seasons.setdefault(tid, {'seasons': []})
        rows = entry.get('seasons') or []
        real_years = {r['year'] for r in rows if r.get('year') and not r.get('synthesized')}
        # drop previously synthesized rows; they are rebuilt below
        before = len(rows)
        rows = [r for r in rows if not r.get('synthesized')]
        replaced += before - len(rows)

        for key, gs in by_season.items():
            if key in real_years or len(gs) < MIN_GAMES:
                continue
            counted = [g for g in gs if not g.get('vacated')]
            wins = sum(1 for g in counted if g.get('w'))
            losses = len(counted) - wins
            n = len(counted) or 1
            row = {
                'year': key,
                'wins': wins,
                'losses': losses,
                'record': f'{wins}-{losses}',
                'winPct': round(wins / n, 3),
                'conf': H[tid][2],
                'ppg': round(sum(g.get('pts', 0) for g in counted) / n, 1),
                'oppPpg': round(sum(g.get('opp_pts', 0) for g in counted) / n, 1),
                'synthesized': True,
                'note': 'Absent from the official season table (results vacated by the NCAA); computed from the game log.',
            }
            rows.append(row)
            added.append((H[tid][0], key, row['record']))

        # newest first, matching compile_history's order
        rows.sort(key=lambda r: str(r.get('year', '')), reverse=True)
        entry['seasons'] = rows

    print(f'synthesized rows: {len(added)} (replaced {replaced} previous synthesized rows)')
    for name, key, rec in added[:15]:
        print(f'  {name:32s} {key}  {rec}')
    if len(added) > 15:
        print(f'  ... and {len(added) - 15} more')
    if dry:
        print('dry run — seasons.json untouched')
        return
    save_json_atomic(seasons_path, seasons)
    print('wrote seasons.json — now run: python3 scripts/split_seasons.py && python3 scripts/generate_sitemaps.py')


if __name__ == '__main__':
    main()
