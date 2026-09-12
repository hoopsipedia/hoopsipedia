#!/bin/bash
# Everything that must run after box scores are merged into sr_boxscores.json,
# in order, stopping on the first failure. Usage:
#   ./scripts/ship_store.sh archives/kentucky/uk_boxscores_full_pending.json [more pending files...]
# Then review `git status`, commit the data files (never archives/**/*.pdf), push,
# and confirm the live app.js hash matches index.html.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ "$#" -gt 0 ]; then
  echo "== merge pending into store"
  python3 merge_pending_into_store.py "$@"
fi
echo "== box-score slices";        python3 scripts/split_boxscores.py | tail -2
echo "== game recaps";             python3 scripts/generate_game_recaps.py | tail -2
echo "== players.json";            python3 generate_players.py | tail -2
echo "== player slices";           python3 scripts/split_players.py | tail -2
echo "== box-score match index";   python3 scripts/build_boxscore_match_index.py | tail -2
echo "== pack store (25MiB rule)"; python3 scripts/pack_store.py
echo "== invariant tests";         python3 tests/test_engine_invariants.py | tail -1
echo "== store size";              python3 -c "import json; print(len(json.load(open('sr_boxscores.json'))), 'box scores')"
echo "SHIP_STORE COMPLETE — now: git add sr_boxscores.json.gz boxscores/ recaps/ players/ players.json boxscore_match_index.json <pending files>; commit; push"
