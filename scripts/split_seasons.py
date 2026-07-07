#!/usr/bin/env python3
"""Split seasons.json into per-team seasons/{espnId}.json files.

The Pages Function ([[path]].js) server-renders a season-by-season table
on ?team= pages. Parsing the full 5.4MB seasons.json per request would
blow the Workers CPU budget, so it fetches one team's ~15KB slice instead.
The frontend can also lazy-load these slices later.

- seasons.json stays the READ-ONLY source of truth; this script derives
  the slices from it and must be re-run (or wired into the sync) whenever
  seasons.json changes.
- Output shape matches the source per-team value: {"seasons": [...]}.
- Deterministic (sorted keys, stable separators), atomic, idempotent.

Validates before exiting:
  1. Every team id in seasons.json has a slice with the same season count.
  2. Total season count across slices equals the source total.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from json_io import save_json_atomic

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_FILE = os.path.join(ROOT, 'seasons.json')
OUT_DIR = os.path.join(ROOT, 'seasons')


def main():
    with open(SOURCE_FILE) as f:
        source = json.load(f)

    os.makedirs(OUT_DIR, exist_ok=True)

    total_written = 0
    for espn_id, entry in sorted(source.items()):
        out_path = os.path.join(OUT_DIR, f'{espn_id}.json')
        save_json_atomic(out_path, entry, separators=(',', ':'), sort_keys=True)
        total_written += len(entry.get('seasons', []))

    # Validate: re-read every slice and compare counts against the source.
    total_source = 0
    for espn_id, entry in source.items():
        expected = len(entry.get('seasons', []))
        total_source += expected
        with open(os.path.join(OUT_DIR, f'{espn_id}.json')) as f:
            actual = len(json.load(f).get('seasons', []))
        if actual != expected:
            print(f'FAIL: {espn_id} has {actual} seasons, expected {expected}')
            sys.exit(1)

    if total_written != total_source:
        print(f'FAIL: wrote {total_written} seasons, source has {total_source}')
        sys.exit(1)

    print(f'OK: {len(source)} team slices, {total_source} seasons total -> {OUT_DIR}/')


if __name__ == '__main__':
    main()
