#!/bin/bash
# Annual post-tournament data refresh — runs from launchd every April 10 at
# 03:00 (see setup_launchd.sh), or by hand:  ./scripts/post_tournament_refresh.sh [SEASON]
#
# Why: seasons.json rows are compiled once; the 2025-26 rows were pulled before
# March 2026 and nobody re-pulled them, so for six months HTSS, the Blue Blood
# Index and the season pages thought 360 programs had missed the 2026
# tournament. This re-pulls the just-finished season's row for every program
# from Sports Reference, rebuilds everything that reads it, and pushes only if
# the engine invariants pass (the pre-push hook still runs).
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-/Library/Frameworks/Python.framework/Versions/3.14/bin/python3}"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"
LOG=/private/tmp/hoopsipedia_refresh.log
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# Season that just ended: in April YYYY that is (YYYY-1)-YY.
if [ -n "${1:-}" ]; then SEASON="$1"; else
  # launchd has ignored Month-restricted slots before (Sept 2026), so the
  # calendar is enforced here too: unattended runs only happen in April.
  [ "$(date +%m)" = "04" ] || { echo "[$(date '+%Y-%m-%d %H:%M:%S')] not April, nothing to do" >> "$LOG"; exit 0; }
  Y=$(date +%Y); SEASON="$((Y-1))-$(printf '%02d' $((Y % 100)))"
fi
log "POST-TOURNAMENT REFRESH for $SEASON"

"$PYTHON" scripts/refresh_season_rows.py "$SEASON" --restart 2>&1 | grep -v 'Progress saved' | tail -5 | tee -a "$LOG"
"$PYTHON" scripts/split_seasons.py        | tail -1 | tee -a "$LOG"
node htss_v2.js                           | tail -1 | tee -a "$LOG"
node unified_rankings.js                  | grep -E 'sanity|passed|FAIL' | tee -a "$LOG"
node time_machine.js                      | tail -1 | tee -a "$LOG"
"$PYTHON" tests/test_engine_invariants.py | tail -1 | tee -a "$LOG"

git add seasons.json seasons htss_v2_results.json unified_rankings.json time_machine_results.json
if git diff --cached --quiet; then log "nothing changed"; exit 0; fi
git commit -q -m "Post-tournament refresh: $SEASON rows re-pulled from Sports Reference, HTSS / Blue Blood Index / Time Machine rebuilt

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push origin main 2>&1 | tail -1 | tee -a "$LOG"
log "DONE"
