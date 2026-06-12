#!/usr/bin/env python3
"""Split sr_boxscores.json into per-year boxscores/{year}.json files.

Wave 2b (audit M2.2): the first historical box-score view currently
fetches all 18MB of sr_boxscores.json. Game keys start with the
tournament year ("YYYY/..."), so per-year slices let the frontend fetch
only the season it needs (~100-700KB).

- sr_boxscores.json is READ-ONLY input; it stays deployed for one
  release so stale cached frontends don't 404.
- Keys inside each year file are the ORIGINAL full game keys
  ("YYYY/slug-vs-slug") so frontend lookup code is unchanged.
- The top-level _metadata key is preserved in boxscores/index.json
  (under "_metadata"), not duplicated into year files.
- boxscores/index.json maps year -> entry count.
- Deterministic, atomic, idempotent. Validates totals before exiting.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from json_io import save_json_atomic

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, 'sr_boxscores.json')
OUT_DIR = os.path.join(ROOT, 'boxscores')


def main():
    with open(SOURCE) as f:
        src = json.load(f)

    metadata = src.get('_metadata')
    by_year = {}
    skipped = []
    for key, val in src.items():
        if key == '_metadata':
            continue
        year = key.split('/', 1)[0]
        if not (len(year) == 4 and year.isdigit()):
            skipped.append(key)
            continue
        by_year.setdefault(year, {})[key] = val

    if skipped:
        print(f'VALIDATION FAILED: {len(skipped)} keys not "YYYY/..." shaped: {skipped[:5]}',
              file=sys.stderr)
        sys.exit(1)

    os.makedirs(OUT_DIR, exist_ok=True)

    written_total = 0
    index = {}
    for year in sorted(by_year):
        entries = by_year[year]
        out = {k: entries[k] for k in sorted(entries)}
        save_json_atomic(os.path.join(OUT_DIR, f'{year}.json'), out,
                         separators=(',', ':'))
        index[year] = len(entries)
        written_total += len(entries)

    index_doc = {'years': index}
    if metadata is not None:
        index_doc['_metadata'] = metadata
    save_json_atomic(os.path.join(OUT_DIR, 'index.json'), index_doc,
                     separators=(',', ':'))

    # ── Validation ──
    source_total = len(src) - (1 if '_metadata' in src else 0)
    errors = []
    if written_total != source_total:
        errors.append(f'entry count mismatch: wrote {written_total}, source has {source_total}')

    # Spot-check: every source key resolvable through its year file
    reread_total = 0
    for year in sorted(by_year):
        with open(os.path.join(OUT_DIR, f'{year}.json')) as f:
            reread = json.load(f)
        reread_total += len(reread)
        for k in by_year[year]:
            if k not in reread:
                errors.append(f'key {k} missing from boxscores/{year}.json')
                break
    if reread_total != source_total:
        errors.append(f're-read count mismatch: {reread_total} vs {source_total}')

    if errors:
        for e in errors:
            print(f'VALIDATION FAILED: {e}', file=sys.stderr)
        sys.exit(1)

    print(f'OK: wrote {len(index)} year files + index.json to boxscores/')
    print(f'    total entries: {written_total} (source: {source_total}), '
          f'years {min(index)}-{max(index)}')


if __name__ == '__main__':
    main()
