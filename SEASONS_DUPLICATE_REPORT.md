# Seasons.json Duplicate-History Fix Report

Date: 2026-06-12
Backup: `/tmp/seasons_backup.json` (pre-fix copy of seasons.json)
Fix script: `fix_seasons_duplicates.py` (idempotent; re-run = 0 changes, no rewrite)

## Root cause

The original `compile_history.py` scrape matched school slugs by name-prefix
substring, so 16 small schools were assigned a flagship program's
**byte-identical** season history in `seasons.json`. A 17th id (245) held the
wrong flagship's history outright (see Texas special case). User-visible bug:
`renderTournamentResume()` trusts `SEASONS_DATA[espnId]`, so e.g. USC Upstate's
live profile showed South Carolina's 2017 Final Four.

## Detection sweep (independent re-run)

Fingerprint = (number of seasons, first year/record/coach, last year/record),
grouped over all 365 entries. Result: exactly the 12 expected groups, **no
additional groups found**. Every group's entries were verified byte-identical
(full JSON equality), confirming wholesale copies rather than coincidence.

## Ownership verification method

For each candidate id in a group, per-season W/L was recomputed from that id's
**own** game log in `games_1/2/3.json` (team-side `w` flag only; opp identity
not used) and compared to the shared seasons.json records across **all**
overlapping seasons (not just 3 — three era-spread samples shown below).
Tolerance ±1 W and ±1 L. Older logs are incomplete, so rightful owners land at
57–96% within-±1 rather than 100%; impostors land at 0–17%.

| Group | Candidate (espnId) | Overlap seasons | Within ±1 | Sample evidence (seasons.json vs own log) |
|---|---|---|---|---|
| Florida | **Florida 57 (owner)** | 75 | 76% | 1988-89: 21-13 vs 21-13; 2025-26: 26-7 vs 26-7 |
| | Florida A&M 50 | 45 | 0% | 2025-26: 26-7 vs 15-16 |
| | Florida Gulf Coast 526 | 19 | 11% | 2025-26: 26-7 vs 16-18 |
| North Carolina | **UNC 153 (owner)** | 76 | 96% | 1987-88: 27-7 vs 27-7; 2025-26: 24-8 vs 24-8 |
| | NC Central 2428 | 19 | 0% | 2007-08: 36-3 vs 3-22 |
| | NC A&T 2448 | 53 | 0% | 2025-26: 24-8 vs 11-19 |
| Utah | **Utah 254 (owner)** | 76 | 79% | 2025-26: 10-22 vs 10-22 |
| | Utah Valley 3084 | 22 | 14% | 2025-26: 10-22 vs 25-9 |
| | Utah Tech 3101 | 6 | 0% | 2025-26: 10-22 vs 19-15 |
| South Carolina | **South Carolina 2579 (owner)** | 77 | 77% | 1949-50: 13-9 vs 13-9; 2025-26: 13-19 vs 13-19 |
| | SC State 2569 | 53 | 6% | 1973-74: 22-5 vs 1-8 |
| | USC Upstate 2908 | 19 | 5% | 2007-08: 14-18 vs 6-22 |
| Northwestern | **Northwestern 77 (owner)** | 72 | 81% | 2025-26: 15-19 vs 15-19 |
| | Northwestern State 2466 | 45 | 9% | 2025-26: 15-19 vs 10-22 |
| Kansas | **Kansas 2305 (owner)** | 76 | 87% | 2025-26: 23-10 vs 23-10 |
| | Kansas City 140 | 36 | 0% | 2007-08: 37-3 vs 11-21 |
| Missouri | **Missouri 142 (owner)** | 73 | 82% | 1949-50: 14-10 vs 14-10; 2025-26: 20-12 vs 20-12 |
| | Missouri State 2623 | 41 | 15% | 1982-83: 26-8 vs 11-15 |
| Texas A&M* | Texas A&M 245 | 76 | **12%** | 2025-26: 18-14 vs 21-11 — see special case |
| | TAMU-Corpus Christi 357 | 24 | 17% | 2002-03: 26-7 vs 14-15 |
| Houston | **Houston 248 (owner)** | 75 | 57% | 1988-89: 17-14 vs 17-14; 2025-26: 28-6 vs 28-6 |
| | Houston Christian 2277 | 34 | 0% | 2025-26: 28-6 vs 12-20 |
| Alabama | **Alabama 333 (owner)** | 76 | 75% | 1988-89: 23-8 vs 23-8; 2025-26: 23-9 vs 23-9 |
| | Alabama A&M 2010 | 27 | 0% | 2012-13: 23-13 vs 11-20 |
| Purdue | **Purdue 2509 (owner)** | 74 | 89% | 1988-89: 15-16 vs 15-16 |
| | Purdue Fort Wayne 2870 | 24 | 12% | 2002-03: 19-11 vs 9-21 |
| Tennessee | **Tennessee 2633 (owner)** | 77 | 87% | 1987-88: 16-13 vs 16-13; 2025-26: 22-11 vs 22-11 |
| | Tennessee State 2634 | 49 | 4% | 2001-02: 15-16 vs 11-17 |

## Texas A&M special case (245 / 357 / 251)

The `compile_coaches.py` bad_ids comment proved correct. Findings:

- 245's seasons entry lists **Texas Longhorns coaches** (Sean Miller, Rodney
  Terry, Chris Beard, Shaka Smart) for recent seasons.
- 245's entry matches **Texas 251's game log at 78%** within ±1 — the same
  rate as 251's own entry vs 251's log — and matches Texas A&M 245's own game
  log at only **12%** and Corpus Christi 357's at 17%.
- 245's entry is W/L-identical to 251's entry in **all 119 common seasons**
  (251 additionally has 1996-97; remaining field diffs are scrape-variant
  conf-record/rounding fields only).

Verdict: 245 and 357 were BOTH impostors carrying Texas Longhorns data.
**Texas 251's own entry was cross-checked and is the verified rightful owner
(kept).** 245 and 357 were deleted; Texas A&M's real history must be
re-scraped. Note: 245/251 were NOT byte-identical (119 vs 120 seasons), which
is why the fingerprint sweep showed them as one 245/357 group rather than a
trio.

## Deletions made (17 entries)

50, 140, 245, 357, 526, 2010, 2277, 2428, 2448, 2466, 2569, 2623, 2634, 2870,
2908, 3084, 3101. seasons.json went from 365 → 348 entries; compact
formatting (`separators=(',',':')`) preserved; written via
`json_io.save_json_atomic`. Re-running the script reports "already clean: 0
changes" without rewriting the file.

**Withheld groups: none.** All 12 groups produced unambiguous evidence.

## Verification: USC Upstate

`'2908' in seasons.json` → **False** post-fix. Its profile can no longer
render South Carolina's tournament resume from SEASONS_DATA (it will fall back
to no-seasons behavior until re-scraped).

Post-fix fingerprint sweep: **0 remaining duplicate groups**.

## Engine regeneration: before/after

`node htss_v2.js` and `node unified_rankings.js` re-run after the fix.

- **HTSS v2 programRankings top-25: IDENTICAL** before/after (both engines
  already carried a runtime `detectCloneTeams()` guard that excluded the
  impostor entries from rankings, so the victims never actually held stolen
  ranking positions in the published artifacts).
- **HTSS allTimeTop100: no victim appears** before or after.
- **Unified programAllTime top-25:** same membership except Gonzaga (19 → 26)
  and Georgetown (23 → 27) slipping just out while Virginia and Florida
  rise in; scores shift by 0.1–1.4 and a few adjacent pairs swap
  (UNC/Kentucky 2↔3, MSU/Villanova). Cause: the ranking pool grew from 347 to
  364 programs (victims re-enter, see below), shifting the z-score/percentile
  normalizations — not stolen data. Top-5 programs unchanged in membership.
- **Victims re-enter unified programAllTime at modest ranks** (e.g. Texas A&M
  #62, Missouri State #91, FGCU #212) computed **only from their own real
  data** (data.json record, efficiency engine, hardware); their
  `htssProgram` component is `null` because they have no seasons.json entry.
  Pre-fix they were hidden by the clone guard. No victim appears in
  seasonAllTime. unified_rankings.json remains a research prototype "not
  wired to the site" per its own metadata.

## New invariant test

Added `test_seasons_no_duplicate_histories` to
`tests/test_engine_invariants.py`: no two data.json-H teams may share an
identical season fingerprint (length + first-10 seasons' year:W-L) in
seasons.json.

- Full suite post-fix: **48 passed, 0 failed, 0 skipped.**
- Negative control: running the suite against the pre-fix backup FAILS the new
  invariant, listing all 12 duplicate groups (47 passed, 1 failed).
- Known limitation: the fingerprint would not have caught 245-vs-251 (not
  byte-identical); that class is caught by the coach/game-log ownership method
  documented above.

## Re-scrape list for Josh (compile_history.py, exact slug matching)

Victims now have NO seasons.json entry until re-scraped. Game-log coverage in
games_1/2/3.json shown as a floor for what we can cross-validate against
(actual program history may start earlier; SR has the authoritative start
years):

| espnId | Team | Own game-log coverage |
|---|---|---|
| 50 | Florida A&M Rattlers | 1979-80 → 2025-26 (1343 g) |
| 140 | Kansas City Roos | 1989-90 → 2025-26 (1094 g) |
| 245 | Texas A&M Aggies | 1949-50 → 2025-26 (2082 g) |
| 357 | Texas A&M-Corpus Christi Islanders | 2002-03 → 2025-26 (752 g) |
| 526 | Florida Gulf Coast Eagles | 2007-08 → 2025-26 (608 g) |
| 2010 | Alabama A&M Bulldogs | 1999-00 → 2025-26 (788 g) |
| 2277 | Houston Christian Huskies | 1973-74 → 2025-26 (931 g) |
| 2428 | North Carolina Central Eagles | 2007-08 → 2025-26 (576 g) |
| 2448 | North Carolina A&T Aggies | 1973-74 → 2025-26 (1446 g) |
| 2466 | Northwestern State Demons | 1976-77 → 2025-26 (1412 g) |
| 2569 | South Carolina State Bulldogs | 1973-74 → 2025-26 (1455 g) |
| 2623 | Missouri State Bears | 1982-83 → 2025-26 (1272 g) |
| 2634 | Tennessee State Tigers | 1977-78 → 2025-26 (1338 g) |
| 2870 | Purdue Fort Wayne Mastodons | 2002-03 → 2025-26 (750 g) |
| 2908 | South Carolina Upstate Spartans | 2007-08 → 2025-26 (597 g) |
| 3084 | Utah Valley Wolverines | 2004-05 → 2025-26 (684 g) |
| 3101 | Utah Tech Trailblazers | 2020-21 → 2025-26 (183 g) |

Priority note: Texas A&M (245) is the largest gap — a 120-year flagship-tier
program with zero season history until re-scraped. Also recommend removing
the now-dead `bad_ids = {'245', '357'}` workaround in `compile_coaches.py`
after 245 is re-scraped with correct data, and auditing `espn_to_sr.json`
slug mappings for these 17 ids before re-scraping so the substring bug cannot
recur.
