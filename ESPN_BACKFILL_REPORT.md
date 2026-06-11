# ESPN Backfill Report — 2026-06-11

## Headline finding: the missing set is EMPTY

The task assumed ~187 teams with no game-by-game data, per `SCRAPE_STATUS.md`.
That file is **stale** (last committed 2026-03-18). Recomputing the missing set
as specified — IDs in `data.json` `H` minus IDs present in
`games_1/2/3.json` — yields **0 missing teams**:

- `data.json` H: 365 teams
- Present across games_1/2/3: 370 keys (5 extras not in H: 157, 2563, 2566, 2631, 2656)
- Missing: **0**

The games files were rewritten on **Apr 8** (after SCRAPE_STATUS was written);
spot-checks confirm teams listed as missing in SCRAPE_STATUS (Tulsa 202,
Austin Peay 2046, Bryant 2803, West Georgia 2698, Queens 2511) all now have
full histories. Coverage is also healthy: 361/365 teams have 100+ games; the
only low-count teams are recent D-I transitions (West Georgia, Mercyhurst,
Le Moyne, etc.) and defunct CCNY (2609, data correctly ends 1953). Only CCNY
lacks 2025-26 games — correctly, since the program is defunct.

**A full 187-team backfill run is not needed.** The script is still delivered,
tested, and useful as a fast gap-filler if a regression or new team appears.

## What was built

- `espn_backfill_games.py` — computes the missing set dynamically; for each
  target team fetches `site.api.espn.com/.../teams/{id}/schedule` for seasons
  2003-2026 (ESPN season = end year), seasontype 2 and 3. 0.4s delay, 3
  retries with exponential backoff on 429/5xx, resumable via
  `espn_backfill_progress.json` (per team+season+type units). All writes via
  `json_io.save_json_atomic`. Writes ONLY to the staging file. Supports
  `--teams id,id,...` override and `--limit N`.
- `games_espn_backfill.json` — staging output (3 sample teams).
- ESPN UTC timestamps are converted to US/Eastern dates to match the SR date
  convention (validated below).

## 3-team sample validation

Since the true missing set is empty, the sample used `--teams 2698,2385,2330`
(West Georgia, Mercyhurst, Le Moyne — small, recent D-I programs):

| Team | ESPN games | Record | opp resolved to SR slug |
|---|---|---|---|
| 2698 West Georgia | 66 | 22W-44L | 63/66 |
| 2385 Mercyhurst | 66 | 32W-34L | 59/66 |
| 2330 Le Moyne | 100 | 39W-61L | 92/100 |

Run stats: 144 requests, 76s wall (~0.53s/request incl. latency).

Schema check vs `games_1.json['2']` — exact match:
- Wrapper: `{"games": [...], "slug": "<sr-slug>"}` (slug from `espn_to_sr.json`)
- Game fields/types identical: `date` str, `opp_slug` str, `loc` str (H/A/N),
  `w` bool, `pts` int, `opp_pts` int, `opp` str (ESPN id), `arena` str (when
  ESPN provides a venue). W/L consistent with scores; games date-sorted;
  deduped by event id and (date, opp, pts, opp_pts).

Cross-check against existing SR data for the same teams, 2024-25/2025-26
overlap: **192/192 games agree** on (date, pts, opp_pts) — espn-only: 0,
sr-only: 0. This also validates the UTC-to-Eastern date conversion.

Resume test: immediate re-run made 0 requests and skipped all 3 teams.

## Estimated full-run cost (if ever needed)

Per team: 24 seasons x 2 seasontypes = 48 requests, ~25s.
187 teams ~ 8,976 requests ~ **75-85 minutes** (within the 40-90 min estimate).

## Data-quality caveats for any merge

1. **Stray pre-transition games**: ESPN lists D-I "money games" played while
   a team was still D-II (e.g., West Georgia at FIU 2008, at Auburn 2010;
   Le Moyne one-offs 2008-2019). Scores verified real, but they predate D-I
   membership — decide whether they belong before merging.
2. **opp_slug fallback**: when `espn_to_sr.json` lacks the opponent (mostly
   non-D-I opponents), `opp_slug` falls back to ESPN displayName (e.g.
   "Edward Waters Tigers") — same convention scrape_batch.py uses
   (`opp_slug or opp_name`), but `opp` is then a non-D-I ESPN id not in
   data.json H.
3. ESPN coverage is thin before ~2005 and absent before 2002; SR remains the
   only source for deep history.

## Recommended merge procedure (do NOT merge the current staging file —
its 3 teams already have better SR data)

Follow `scrape_batch.py`'s validated-merge pattern:
1. Run each staged team through the equivalent of `_validate()` (dedupe,
   W/L-vs-score fix, >200-pt warning, date sort, NCAA record-book coverage
   check against `data.json H[id][4:6]`, opp-resolution rate).
2. Use `find_smallest_games_file()` to pick the target file for balance.
3. Use `merge_safely()` semantics: snapshot existing data, add ONLY teams not
   already present (never overwrite SR data with ESPN data), post-merge
   assert existing teams byte-identical, write via `save_json_atomic`.

## Open questions for Josh

1. SCRAPE_STATUS.md is 3 months stale and now misleading — regenerate or
   delete it? (Not touched; outside my file list.)
2. The 5 game-file keys not in data.json H (157, 2563, 2566, 2631, 2656) —
   intentional (defunct/renamed programs) or orphans?
3. Should pre-D-I "money games" from ESPN be included in team histories if
   this backfill is ever used for a real gap?
4. Keep `espn_backfill_progress.json` and the 3-team staging file, or delete
   both since no real backfill is needed? (Both are scratch; safe to delete.)

## Files

- Created: `espn_backfill_games.py`, `games_espn_backfill.json`,
  `espn_backfill_progress.json` (progress scratch), `ESPN_BACKFILL_REPORT.md`
- Not touched: games_1/2/3.json, index.html, functions/, scrape_*/compile_*
