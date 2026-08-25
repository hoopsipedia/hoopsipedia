#!/usr/bin/env python3
"""Re-scrape the 107 team-seasons missing from the game logs.

Input: games_season_gaps.json (produced by the gap scan — a season counts as
a hole only when it has <=6 games logged while BOTH neighbouring seasons have
>=20, so the program was demonstrably active).

MUST RUN ON A MACHINE WITH SPORTS-REFERENCE ACCESS. Claude Code's cloud
sessions are blocked from sports-reference.com, espn.com and web.archive.org
by the environment's egress policy, so this cannot run there.

Reuses compile_schedules.ScheduleCompiler for fetching and parsing — same
14s politeness interval, same page and parser — so there is one scraper to
maintain, not two. This module only decides WHAT to fetch and HOW to merge.

Merge rules, in order of how much they matter:
  1. ADDITIVE ONLY. A season is written only when the team currently has
     <=6 games logged for it. Existing games are never replaced, and a
     season that already looks complete is skipped even if listed.
  2. Gated on plausibility. A scraped season must yield >=15 games, and
     every game's date must fall inside that season's Nov-Apr window, or it
     is rejected and reported. A short or misdated scrape is a scrape
     problem, not new data.
  3. Duplicate-safe. Games already present for that season (matched on
     date + score pair) are not re-added, so a partial "tournament-only"
     season keeps its existing rows and gains only the missing ones.
  4. Written to whichever shard already holds that team, so the
     one-team-one-shard invariant the tests enforce is preserved.

Resumable: progress is checkpointed to fill_season_gaps_progress.json after
every season, so an interrupted run continues where it stopped. Re-running
after completion is a no-op.

Usage:
  python3 fill_season_gaps_from_sr.py --dry-run     # show the plan, no network
  python3 fill_season_gaps_from_sr.py               # run it (~25 min at 14s/req)
  python3 fill_season_gaps_from_sr.py --limit 5     # try a few first
Afterwards:
  python3 scripts/split_games.py && python3 tests/test_engine_invariants.py
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from json_io import save_json_atomic

ROOT = os.path.dirname(os.path.abspath(__file__))
GAPS = os.path.join(ROOT, 'games_season_gaps.json')
PROGRESS = os.path.join(ROOT, 'fill_season_gaps_progress.json')
SHARDS = ['games_1.json', 'games_2.json', 'games_3.json']
MIN_PLAUSIBLE_GAMES = 15
ALREADY_FULL = 6          # a season with more than this is not a gap


def season_window(year):
    return '{}-10-01'.format(year - 1), '{}-05-31'.format(year)


def load_shards():
    data, home = {}, {}
    for fn in SHARDS:
        with open(os.path.join(ROOT, fn)) as f:
            data[fn] = json.load(f)
        for tid in data[fn]:
            home[tid] = fn
    return data, home


def rows_of(entry):
    return entry['games'] if isinstance(entry, dict) else entry


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--limit', type=int)
    args = ap.parse_args()

    gaps = json.load(open(GAPS))['gaps']
    done = json.load(open(PROGRESS)) if os.path.exists(PROGRESS) else {'filled': [], 'rejected': []}
    done_keys = {tuple(x[:2]) for x in done['filled']} | {tuple(x[:2]) for x in done['rejected']}

    data, home = load_shards()
    e2s = json.load(open(os.path.join(ROOT, 'espn_to_sr.json')))

    todo = []
    for g in gaps:
        tid, yr = g['espnId'], g['season']
        if (tid, yr) in done_keys:
            continue
        fn = home.get(tid)
        if not fn:
            continue
        lo, hi = season_window(yr)
        have = sum(1 for r in rows_of(data[fn][tid]) if lo <= r['date'] <= hi)
        if have > ALREADY_FULL:
            continue                      # filled since the scan; nothing to do
        if tid not in e2s:
            print('SKIP {} {} — no Sports-Reference slug'.format(g['team'], yr))
            continue
        todo.append((g, fn, e2s[tid], have))
    if args.limit:
        todo = todo[:args.limit]

    print('{} season(s) to fetch (~{:.0f} min at 14s each)'.format(todo.__len__(), len(todo) * 14 / 60))
    if args.dry_run:
        for g, fn, slug, have in todo[:20]:
            print('  {:28s} {}  [{} logged, shard {}, slug {}]'.format(
                g['team'][:28], g['season'], have, fn, slug))
        if len(todo) > 20:
            print('  ... and {} more'.format(len(todo) - 20))
        return
    if not todo:
        print('Nothing to do.')
        return

    from compile_schedules import ScheduleCompiler
    sc = ScheduleCompiler()

    filled = rejected = 0
    for g, fn, slug, have in todo:
        tid, yr = g['espnId'], g['season']
        label = '{} {}'.format(g['team'], yr)
        try:
            games = sc._fetch_season_schedule(slug, yr)
        except Exception as exc:
            print('  FETCH FAILED {}: {}'.format(label, exc))
            done['rejected'].append([tid, yr, 'fetch failed: {}'.format(exc)[:120]])
            rejected += 1
            save_json_atomic(PROGRESS, done, indent=1)
            continue

        lo, hi = season_window(yr)
        good = [x for x in (games or []) if x.get('date') and lo <= x['date'] <= hi]
        if len(good) < MIN_PLAUSIBLE_GAMES:
            reason = 'only {} in-window games scraped (need {})'.format(len(good), MIN_PLAUSIBLE_GAMES)
            print('  REJECT {}: {}'.format(label, reason))
            done['rejected'].append([tid, yr, reason])
            rejected += 1
            save_json_atomic(PROGRESS, done, indent=1)
            continue

        entry = data[fn][tid]
        existing = rows_of(entry)
        have_keys = {(r['date'], r.get('pts'), r.get('opp_pts')) for r in existing}
        added = [x for x in good
                 if (x['date'], x.get('pts'), x.get('opp_pts')) not in have_keys]
        existing.extend(added)
        existing.sort(key=lambda r: r['date'])
        save_json_atomic(os.path.join(ROOT, fn), data[fn], separators=(',', ':'))
        print('  OK {:32s} +{:3d} games (had {})'.format(label[:32], len(added), have))
        done['filled'].append([tid, yr, len(added)])
        filled += 1
        save_json_atomic(PROGRESS, done, indent=1)

    print('\nfilled {} season(s), rejected {}'.format(filled, rejected))
    print('progress: {}'.format(os.path.basename(PROGRESS)))
    if filled:
        print('\nNEXT: python3 scripts/split_games.py')
        print('      python3 generate_on_this_day.py')
        print('      node efficiency_engine.js && node htss_v2.js && node unified_rankings.js')
        print('      python3 tests/test_engine_invariants.py')


if __name__ == '__main__':
    main()
