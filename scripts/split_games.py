#!/usr/bin/env python3
"""Split games_1/2/3.json into per-team games/{espnId}.json files.

Wave 2b (audit M2.1): first-time visitors currently download ~67MB of
game data upfront. This script produces per-team slices (~50-300KB each)
so the frontend and the chat worker can lazy-load only the teams a view
actually needs.

- games_1/2/3.json are READ-ONLY inputs. They stay deployed for one
  release so stale cached frontends don't 404.
- Output shape is normalized: {"games": [...], "slug": "..."}. Legacy
  bare-array entries are wrapped; missing slugs are filled from
  espn_to_sr.json when available.
- games/index.json is a manifest {espnId: gameCount} the frontend loads
  upfront (tiny) to answer "does this team have games data?" without
  fetching the slice.
- Deterministic (sorted keys, stable separators), atomic, idempotent.

Validates before exiting:
  1. Total game count across games/ equals total in the source files
     (last-wins merge across parts, mirroring the old frontend merge).
  2. Every data.json H id has a games/{id}.json file.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from json_io import save_json_atomic

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_FILES = ['games_1.json', 'games_2.json', 'games_3.json']
OUT_DIR = os.path.join(ROOT, 'games')


def load(path):
    with open(os.path.join(ROOT, path)) as f:
        return json.load(f)


def main():
    espn_to_sr = load('espn_to_sr.json')

    # Merge parts with last-wins semantics — mirrors the frontend's old
    # Object.assign({}, g1, g2, g3) and chat.js's games_3-first lookup.
    merged = {}
    for fname in SOURCE_FILES:
        part = load(fname)
        for espn_id, entry in part.items():
            merged[str(espn_id)] = entry
    # Source total under last-wins merge semantics
    source_total = 0
    for entry in merged.values():
        games = entry if isinstance(entry, list) else entry.get('games', [])
        source_total += len(games)

    os.makedirs(OUT_DIR, exist_ok=True)

    # Current-season rows from ESPN (scripts/espn_recaps.py) live outside the
    # SR masters until the post-season scrape lands; re-apply them here so a
    # rebuild never drops the season in progress. SR rows win on a date clash.
    import glob
    espn_rows = {}
    for path in sorted(glob.glob(os.path.join(ROOT, 'archives', 'espn', 'espn_*_games.json'))):
        for tid, by_date in load(os.path.relpath(path, ROOT)).items():
            espn_rows.setdefault(str(tid), {}).update(by_date)

    index = {}
    written_total = 0
    espn_added = 0
    wrapped = 0
    slug_filled = 0
    for espn_id in sorted(merged, key=lambda k: (len(k), k)):
        entry = merged[espn_id]
        if isinstance(entry, list):
            entry = {'games': entry}
            wrapped += 1
        else:
            # shallow copy so we never mutate the source object shape
            entry = {'games': entry.get('games', []),
                     **{k: v for k, v in entry.items() if k != 'games'}}
        if not entry.get('slug'):
            slug = espn_to_sr.get(espn_id)
            if slug:
                entry['slug'] = slug
                slug_filled += 1
        extra = espn_rows.get(espn_id)
        if extra:
            have = {g['date']: g for g in entry['games']}
            new_rows = []
            for d, r in sorted(extra.items()):
                cur = have.get(d)
                if cur is None:
                    new_rows.append(r)
                elif str(cur.get('opp')) == str(r.get('opp')):
                    for k, v in r.items():   # eid / arena / ot onto an SR row
                        cur.setdefault(k, v)
            if new_rows:
                entry['games'] = sorted(entry['games'] + new_rows, key=lambda g: g['date'])
                espn_added += len(new_rows)
        out = {'games': entry['games']}
        for k in sorted(entry):
            if k != 'games':
                out[k] = entry[k]
        save_json_atomic(os.path.join(OUT_DIR, f'{espn_id}.json'), out,
                         separators=(',', ':'), sort_keys=False)
        index[espn_id] = len(entry['games'])
        written_total += len(entry['games'])

    save_json_atomic(os.path.join(OUT_DIR, 'index.json'),
                     {k: index[k] for k in sorted(index, key=lambda k: (len(k), k))},
                     separators=(',', ':'))

    # ── Validation ──
    errors = []
    if written_total - espn_added != source_total:
        errors.append(f'game count mismatch: wrote {written_total} ({espn_added} ESPN current-season rows), source has {source_total}')

    data = load('data.json')
    h_ids = set(data.get('H', {}).keys())
    missing = sorted(i for i in h_ids if not os.path.exists(os.path.join(OUT_DIR, f'{i}.json')))
    if missing:
        errors.append(f'{len(missing)} data.json H ids missing from games/: {missing[:10]}')

    # Re-read a sample file to confirm normalized shape
    sample_id = next(iter(index))
    with open(os.path.join(OUT_DIR, f'{sample_id}.json')) as f:
        sample = json.load(f)
    if not isinstance(sample, dict) or 'games' not in sample:
        errors.append(f'sample games/{sample_id}.json is not normalized: {type(sample)}')

    if errors:
        for e in errors:
            print(f'VALIDATION FAILED: {e}', file=sys.stderr)
        sys.exit(1)

    print(f'OK: wrote {len(index)} team files + index.json to games/')
    print(f'    total games: {written_total} (source: {source_total})')
    print(f'    legacy bare arrays wrapped: {wrapped}, slugs filled from espn_to_sr: {slug_filled}')
    print(f'    all {len(h_ids)} data.json H ids present')


if __name__ == '__main__':
    main()
