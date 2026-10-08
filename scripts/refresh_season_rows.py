#!/usr/bin/env python3
"""Re-pull one season's row for every program from Sports Reference.

Why this exists: seasons.json rows are compiled once and kept. The 2025-26
rows were pulled before March 2026, so on 2026-10-08 only the 4 programs
re-scraped in July carried a tournament result (round_max) and seed; the
other 360 looked like they had missed the tournament. Anything downstream
that reads ncaaTourney — HTSS, the Blue Blood Index, season stories — was
wrong or blind for that season.

Fetches each program's SR history page (3.1s apart, the site's limit) and
replaces ONLY the requested season's row, preserving any flags the repo
added to it (synthesized, vacated, …). Resumable: progress is kept next to
the output so a stopped run picks up where it left off.

  python3 scripts/refresh_season_rows.py 2025-26
  python3 scripts/refresh_season_rows.py 2025-26 --limit 5      # smoke test
  python3 scripts/refresh_season_rows.py 2025-26 --restart      # ignore progress

Afterwards: python3 scripts/split_seasons.py && node htss_v2.js &&
node unified_rankings.js (then commit seasons.json + slices + results).
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from compile_history import CollegeBasketballCompiler  # noqa: E402

PRESERVE_KEYS = ('synthesized', 'vacated', 'vacatedNote', 'note', 'source')


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        sys.exit(__doc__)
    season = args[0]
    limit = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else None
    progress_path = os.path.join(ROOT, f'.refresh_{season}.progress.json')
    done = set()
    if '--restart' not in sys.argv and os.path.exists(progress_path):
        done = set(json.load(open(progress_path)))

    c = CollegeBasketballCompiler()
    ids = [i for i in c.seasons_data if i in c.slug_mapping and i not in done]
    if limit:
        ids = ids[:limit]
    print(f'{len(ids)} programs to refresh for {season} ({len(done)} already done)')

    stats = {'updated': 0, 'added': 0, 'tourney': 0, 'no_row': 0, 'failed': 0}
    t0 = time.time()
    for n, eid in enumerate(ids, 1):
        rows = c._fetch_team_data(eid, c.slug_mapping[eid])
        if rows is None:
            stats['failed'] += 1
            print(f'  FAIL {eid} {c.slug_mapping[eid]}')
            continue
        fresh = next((r for r in rows if r.get('year') == season), None)
        existing = c.seasons_data[eid].setdefault('seasons', [])
        idx = next((i for i, r in enumerate(existing) if r.get('year') == season), None)
        if fresh is None:
            stats['no_row'] += 1
        else:
            if idx is not None:
                for k in PRESERVE_KEYS:
                    if k in existing[idx]:
                        fresh[k] = existing[idx][k]
                changed = fresh != existing[idx]
                existing[idx] = fresh
                stats['updated'] += int(changed)
            else:
                # seasons are stored newest-first; put it before the previous year
                existing.insert(0, fresh)
                stats['added'] += 1
            if fresh.get('ncaaTourney'):
                stats['tourney'] += 1
        done.add(eid)
        if n % 20 == 0 or n == len(ids):
            c._save_progress()
            with open(progress_path, 'w') as f:
                json.dump(sorted(done), f)
            el = time.time() - t0
            print(f'  {n}/{len(ids)} ({el/60:.1f} min) {stats}', flush=True)
    print(f'DONE {season}: {stats}')
    if not stats['failed'] and not limit:
        os.remove(progress_path)
    return 1 if stats['failed'] else 0


if __name__ == '__main__':
    sys.exit(main())
