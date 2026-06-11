# On This Day — generator notes

`generate_on_this_day.py` -> `on_this_day.json` (320 KB, well under the 2 MB budget).
Output is keyed `MM-DD` for all 366 calendar days; each day holds up to 8 events
sorted by a significance score. 157 days have events; the other 209 (May 1 –
Oct 31 plus a few in-season gaps like Dec 24/25) are empty arrays — college
basketball simply isn't played then, so the UI needs an empty-day fallback.

## Inputs

- `games_1/2/3.json` — 569,820 team-game rows, 1941-03-18 to 2026-03-19,
  deduped to 277,783 canonical games (both teams identified).
- `data.json` `H` — team name (idx 0), NC count (idx 6), NCY title years (idx 7).
- `upset_history.json` — 343 first-round seed upsets (year + teams + seeds +
  score, **no dates**).
- `sr_boxscores.json` — only used for the `url` field, which embeds the game
  date (`/boxscores/1985-03-15-...`); used as a fallback to date upsets.

## Heuristics (and their risks)

### 1. Opponent-id repair (slug voting)
The `opp` field in the games files is unreliable — it was produced by substring
matching and is wrong on ~21,000 rows (slug `houston` -> 2534 Sam Houston
Bearkats, `indiana` -> 85 IU Indianapolis, `california` -> 2934 Cal State
Bakersfield, `maryland` -> 2352 Loyola Maryland, `arizona` -> 2464 Northern
Arizona, ...). The generator **ignores `opp` entirely** and re-derives ids per
distinct `opp_slug` by mirror voting: find which team's own log contains the
mirror row (same date, scores swapped, result flipped). Acceptance: >=5 votes,
>=75% share, >=5x the runner-up. Coincidental same-score games add ~5–10%
vote noise, hence the dominance test instead of a strict majority.
360 of 1,597 slugs resolve; the rest are mostly non-D1 opponents and are
excluded from events (so no wrong names can appear in headlines).
**This same bug presumably affects anything else that trusts `opp`.**

### 2. Championship-game detection
For team T with NCY year Y: take T's last recorded game of season Y (season =
Nov..Apr, labeled by ending year). It must be a **win** inside Mar 15–Apr 15.
Cross-check: the opponent's log must contain the mirror row on that date *and*
it must also be the opponent's season finale (both seasons end in a title game).
- 70 events cross-checked clean; 3 accepted without opponent-season data
  because the opponent's season is absent from its own log — vacated seasons
  (Michigan 1992, 1993; Memphis 2008).
- 12 NCY years have no games data at all (pre-1951 seasons: Oregon 1939,
  Indiana 1940, Wisconsin 1941, Stanford 1942, Wyoming 1943, Utah 1944,
  Oklahoma St 1945+1946, Holy Cross 1947, Kentucky 1948+1949, Marquette 1977
  — Marquette's 1977 season is missing from the logs, worth a look).
- Michigan 2026 skipped: the global max game date (2026-03-19) is inside that
  season and before Apr 1, so the season is incomplete (scrape in progress) —
  without this guard their Mar 15 round game would be a false positive.
- Residual false-positive risk: a missing true final plus an earlier in-window
  win as the last recorded game would mislabel that win. The
  both-seasons-end cross-check makes this unlikely; headline wording hedges by
  stating only what the data shows ("final game of their YYYY national
  championship season").

### 3. Upset dating
upset_history stores only the year. Date resolution: match team pair + winner
+ exact score in March/April of that year against the game logs (320 matched);
else take the date from the sr_boxscores URL (14 matched); else **skip — never
guess** (9 skipped). Historical-name renames are bridged by a 14-entry alias
map (Connecticut->UConn, Southwest Missouri State->Missouri State, ...);
headlines keep the historical name from upset_history.

Undated/skipped upsets — several look like errors in upset_history.json itself
(flagging for Josh):
- 1996 5v12 Little Rock over Purdue 65-63 — no such game exists in any year's logs; the real Little Rock–Purdue upset in the logs is **2016-03-17, 85-83 (2OT)**. The 1996 entry appears fabricated.
- 1999 5v12 SW Missouri State over Wisconsin 43-41 — game logs say **43-32**.
- 2014 7v10 Stanford over Kansas State 60-57 — logs have no such 2014 game.
- 2025 8v9 Georgia over Maryland 68-59 — logs have no such 2025 game.
- 2026 upsets (High Point–Wisconsin, VCU–UNC, Texas–BYU, Texas A&M–Saint
  Mary's) — the 2026 tournament is beyond the current scrape cutoff
  (2026-03-19); they will date themselves once the logs catch up.

### 4. Other event types (canonical games only, both teams identified)
- `ot`: multi-OT games, sig = 30 + 8*nOT (max found: 7OT).
- `high_score`: combined >= 220, sig caps at 72.
- `blowout`: margin >= 35, sig caps at 68.
One event per game (best axis); one event per (date, team pair) overall, so a
game never appears twice on a day.

## Accuracy rule
Every clause in a headline maps to a data field: teams/score/date from the
game row, "national championship season" from NCY, seeds/round from
upset_history (whose metadata scopes it to first-round upsets), OT counts from
the `ot` field. No tournament context is asserted beyond that.

## Event-count distribution
`{0: 209, 2: 2, 3: 4, 4: 3, 5: 3, 6: 1, 7: 3, 8: 141}` (n_events: n_days),
1,198 events total: 73 championship, 81 upset, 712 blowout, 311 ot,
21 high_score. In-season days are nearly all capped at 8.

## Sample days

**06-11 (today)** — 0 events (no games ever played on this date in the data).

**04-01** — 4 events, all championships: Villanova over Georgetown 66-64
(1985), Duke over Kansas 72-65 (1991), Kentucky over Syracuse 76-67 (1996),
Maryland over Indiana 64-52 (2002).

**03-16** — 8 events, led by: 16-seed UMBC over 1-seed Virginia 74-54 (2018),
15-seed Lehigh over 2-seed Duke 75-70 (2012), 15-seed Norfolk State over
2-seed Missouri 86-84 (2012), 15-seed Princeton over 2-seed Arizona 59-55 (2023).

**03-21** — 8 events: Cal 71-70 West Virginia 1959 final, UCLA 1964 + 1970
finals, then 14-over-3 upsets (Harvard 2013, Mercer 2014, Oakland 2024).

**12-23** — 8 events: Minnesota 114-34 Alabama State (80-pt margin, 1996),
Cleveland State 104-101 4OT Kent State (1993), Oklahoma 136-121 Loyola
Marymount (257 combined, 1989), etc.

## Proposed UI integration (not implemented)
1. Homepage card "On This Day in College Hoops": fetch `on_this_day.json`
   once (static asset, cacheable), pick `MM-DD` from the client clock, render
   the top 1–3 headlines with team logos via the espnIds already used by the
   compare search.
2. Empty days (May–Oct and a few others): fall back to "next date with
   events" teaser ("Season tips off in N days — on Nov 1, ...") or rotate a
   random championship event; the data supports either with no schema change.
3. Each event links to the two team pages via espnId; `type` drives a small
   badge (trophy / seed flip / OT / 100+ pts) and `sig` is available if the UI
   wants its own ordering.
4. No index.html changes were made (per scope); a later pass only needs one
   fetch + one render function, no recompute.

## Regeneration
`python3 generate_on_this_day.py` (pure stdlib, ~40 s, atomic write via
`json_io.save_json_atomic`). Re-run after any games_*.json refresh — the 2026
tournament rows will automatically add the 2026 events and Michigan's 2026
title game once scraped past Apr 6.
