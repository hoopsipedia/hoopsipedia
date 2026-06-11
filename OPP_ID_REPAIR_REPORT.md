# Opponent-ID Repair Report — 2026-06-11

Repair of wrong `opp` ESPN ids in `games_1/2/3.json` caused by historical
substring slug matching (e.g. `houston` → 2534 Sam Houston State instead of
248 Houston). Performed by `fix_opp_ids.py`.

## Backups

- `/tmp/games_backup/games_1.json`, `games_2.json`, `games_3.json` (pre-repair copies)
- `~/Backups/hoopsipedia/hoopsipedia-data-2026-06-11.tar.gz` (pre-existing)
- `/tmp/games_backup/before_efficiency_ratings.json`, `before_htss_v2_results.json` (pre-repair engine outputs)

## Method

1. Inverted `espn_to_sr.json` (id → SR slug) with **exact match only** — the
   map is bijective (365 ids ↔ 365 slugs, zero collisions, verified at load).
2. For every row whose stored `opp` disagreed with the slug-derived id, the
   correction was applied **only after mirror-row verification**: the
   candidate opponent's own log must contain the reciprocal row — same date,
   scores swapped, win flag flipped, and `opp_slug` pointing back at the team.
3. Rows that could not be verified were left untouched and counted.
4. Only `opp` values changed. Verified by full structural diff against the
   backups: 569,820 rows compared, 26,627 `opp` diffs, **0 non-opp diffs**,
   key order, row order, and entry formats (dict-with-games vs legacy bare
   array) identical. Writes via `save_json_atomic`, `separators=(',', ':')`.

## Rows changed

| File | Corrected | Flagged unfixable (untouched) | Size after |
|---|---|---|---|
| games_1.json | 11,729 | 348 | 21.4 MB |
| games_2.json | 10,959 | 575 | 21.5 MB |
| games_3.json | 3,939 | 583 | 21.1 MB |
| **Total** | **26,627** | **1,506** | all < 25 MB Cloudflare limit |

Note: actual corrections (26,627) exceed the ~21,190 prior estimate; the
estimate apparently undercounted. All 26,627 new ids exist in `data.json` H.

Full row accounting (569,820 rows): 455,835 already correct · 26,627
corrected · 1,506 flagged · 83,074 have no `opp` key at all (never modified;
no keys added) · 2,778 have an `opp_slug` not in `espn_to_sr.json` (mostly
non-D1 opponents — their stored `opp` may also be substring-corrupt but is
unresolvable from the exact-match map; left untouched).

## Flagged-unfixable detail (needs Josh's judgment)

These 1,506 rows still carry the **wrong** old id; the slug-derived
correction could not be mirror-verified:

- **1,064 rows**: `opp_slug=virginia-military-institute`, stored `opp=157`.
  Correct id is 2678 (VMI), but the games are absent from 2678's log — they
  appear to live in the phantom team log keyed `157` (1,913 legacy-format
  rows, no slug, not in `espn_to_sr.json` or `data.json` H). `157` and
  `2678` look like duplicate scrapes of the same program. The other phantom
  team keys are `2563`, `2566`, `2631` (has slug `tulsa`), `2656` — see
  PHANTOM_TEAMS_REPORT.md. Decide whether to merge `157` into `2678`, then
  re-run `fix_opp_ids.py`.
- **442 rows**: slug maps cleanly (arizona 154, minnesota 148, california 33,
  maryland 24, houston 20, indiana 20, utah 19, texas 14, others <5) but the
  true opponent's log has **no game at all on that date** — coverage gaps in
  the opponent's log (e.g. Arizona's mid-1990s seasons). The slug-derived id
  is almost certainly right, but per the verify-before-correct rule they were
  withheld rather than guessed.

## Spot checks (10/10 passed)

| Team | opp_slug | Date | Old opp | New opp |
|---|---|---|---|---|
| Duke (150) | houston | 2024-03-29 | 2534 (Sam Houston St) | 248 (Houston) |
| Kentucky (96) | houston | 1956-12-29 | 2534 | 248 |
| Duke (150) | indiana | 1987-03-20 | 85 (IUPUI) | 84 (Indiana) |
| Kentucky (96) | indiana | 1965-12-18 | 85 | 84 |
| UCLA (26) | california | 1950-01-06 | 2934 (CSU Bakersfield) | 25 (California) |
| Stanford (24) | california | 1950-01-13 | 2934 | 25 |
| Duke (150) | maryland | 1950-01-04 | 2352 (Loyola MD) | 120 (Maryland) |
| UNC (153) | maryland | 1950-01-02 | 2352 | 120 |
| UCLA (26) | arizona | 1951-01-26 | 2464 (N. Arizona) | 12 (Arizona) |
| USC (30) | arizona | 1953-12-26 | 2464 | 12 |

## Mirror-consistency rate

Share of opp-bearing rows whose opponent's log contains the reciprocal row
(same date, swapped scores, flipped result, `opp` pointing back):

- Before: **77.12%** (373,491 / 484,300 in-dataset rows)
- After: **84.89%** (411,110 / 484,300)

The residual ~15% is dominated by mirrors that lack an `opp` key entirely
(83K such rows) and one-sided coverage gaps, not wrong ids.

## Downstream regeneration

`efficiency_engine.js` reads `game.opp` directly (preferring it over the
slug), so it was computing with corrupted opponent identities;
`htss_v2.js` consumes `efficiency_ratings.json`. Both rerun on the repaired
data (run logs in `/tmp/games_backup/after_*.log`). Large ranking shifts are
**expected and correct** — adjusted efficiency had been crediting/penalizing
the wrong opponents for ~26.6K rows.

### Efficiency engine — all-time top 25 (adjEM)

| # | Before | adjEM | After | adjEM |
|---|---|---|---|---|
| 1 | UCLA 1971-72 | 47.12 | Duke 1998-99 | 47.41 |
| 2 | Kentucky 1950-51 | 43.08 | UCLA 1971-72 | 46.97 |
| 3 | Kentucky 1951-52 | 42.81 | Kentucky 2014-15 | 44.29 |
| 4 | Duke 1998-99 | 42.80 | UCLA 1967-68 | 44.00 |
| 5 | UCLA 1966-67 | 42.36 | Duke 1997-98 | 43.32 |
| 6 | Ohio State 1959-60 | 42.21 | Kentucky 1995-96 | 43.30 |
| 7 | Kentucky 1953-54 | 42.09 | Duke 2000-01 | 43.02 |
| 8 | UCLA 1972-73 | 42.02 | Duke 2024-25 | 42.94 |
| 9 | UCLA 1967-68 | 41.69 | UCLA 1972-73 | 42.87 |
| 10 | Cincinnati 1959-60 | 41.24 | Duke 2025-26 | 42.69 |
| 11 | Indiana 1991-92 | 40.90 | Indiana 1991-92 | 42.58 |
| 12 | Indiana 1974-75 | 40.83 | Houston 2024-25 | 42.44 |
| 13 | Kansas State 1950-51 | 40.80 | UCLA 1966-67 | 42.25 |
| 14 | UNLV 1990-91 | 40.59 | Kentucky 1996-97 | 42.21 |
| 15 | UCLA 1968-69 | 40.54 | Kansas State 1950-51 | 41.95 |
| 16 | Kentucky 1995-96 | 40.29 | Indiana 1974-75 | 41.39 |
| 17 | Duke 1997-98 | 39.51 | Michigan 2025-26 | 41.36 |
| 18 | Cincinnati 1961-62 | 39.31 | UCLA 1968-69 | 41.27 |
| 19 | Kentucky 1996-97 | 39.22 | Kentucky 1951-52 | 40.64 |
| 20 | California 1959-60 | 39.15 | UNLV 1990-91 | 40.51 |
| 21 | UCLA 1973-74 | 38.87 | Kentucky 1953-54 | 40.50 |
| 22 | Kentucky 2014-15 | 38.85 | Ohio State 1959-60 | 40.22 |
| 23 | Indiana 1975-76 | 38.82 | San Francisco 1954-55 | 40.04 |
| 24 | Gonzaga 2018-19 | 38.64 | Kansas 1996-97 | 40.03 |
| 25 | Duke 2025-26 | 38.53 | UNC 1992-93 | 39.92 |

Dropped out of top 25: Kentucky 1950-51, California 1959-60, Cincinnati
1959-60 & 1961-62, UCLA 1973-74, Indiana 1975-76, Gonzaga 2018-19.
New to top 25: San Francisco 1954-55, UNC 1992-93, Kansas 1996-97, Duke
2000-01 & 2024-25, Houston 2024-25, Michigan 2025-26.

Pattern: the corruption had been deflating elite teams whose schedules
contained big-name slugs mis-mapped to weak mid/low-major programs
(SOS undercounted), inflating 1950s teams relatively. Modern Duke/Houston/
Kentucky seasons rise sharply; several pre-1963 seasons fall.

### HTSS v2 — all-time top 25

| # | Before | htss | After | htss |
|---|---|---|---|---|
| 1 | UCLA 1972-73 | 91.37 | UCLA 1972-73 | 91.71 |
| 2 | Indiana 1975-76 | 89.90 | Indiana 1975-76 | 89.26 |
| 3 | UCLA 1971-72 | 88.66 | UCLA 1971-72 | 88.16 |
| 4 | UCLA 1966-67 | 86.82 | UCLA 1967-68 | 87.71 |
| 5 | UCLA 1967-68 | 86.21 | UCLA 1966-67 | 86.62 |
| 6 | UCLA 1968-69 | 85.59 | UNC 1981-82 | 85.61 |
| 7 | Duke 2018-19 | 84.60 | Duke 2000-01 | 85.51 |
| 8 | Villanova 2017-18 | 84.19 | UCLA 1968-69 | 85.01 |
| 9 | NC State 1973-74 | 83.98 | NC State 1973-74 | 84.76 |
| 10 | Duke 2014-15 | 83.91 | Kentucky 2014-15 | 84.74 |
| 11 | UNC 2016-17 | 83.76 | Kentucky 1995-96 | 83.81 |
| 12 | Virginia 2018-19 | 83.36 | Duke 2009-10 | 83.69 |
| 13 | UCLA 1974-75 | 82.69 | Duke 1998-99 | 83.46 |
| 14 | UConn 2023-24 | 82.12 | UCLA 1974-75 | 82.65 |
| 15 | Duke 2009-10 | 82.03 | Duke 2014-15 | 81.83 |
| 16 | Kentucky 1995-96 | 81.87 | Indiana 1974-75 | 81.76 |
| 17 | Villanova 2015-16 | 81.63 | UNC 1992-93 | 81.65 |
| 18 | Gonzaga 2020-21 | 81.39 | San Francisco 1954-55 | 81.31 |
| 19 | UCLA 1973-74 | 81.38 | UNC 2016-17 | 81.25 |
| 20 | Indiana 1974-75 | 81.28 | Kansas 2021-22 | 81.19 |
| 21 | Duke 1998-99 | 81.11 | UNC 2004-05 | 81.06 |
| 22 | UNC 1981-82 | 81.08 | Duke 1997-98 | 81.00 |
| 23 | Kentucky 2014-15 | 81.02 | Virginia 2018-19 | 80.95 |
| 24 | UConn 2008-09 | 80.89 | UCLA 1973-74 | 80.91 |
| 25 | UConn 1998-99 | 80.72 | UConn 2023-24 | 80.82 |

Dropped out: UConn 1998-99 & 2008-09, Villanova 2015-16 & 2017-18, Duke
2018-19, Gonzaga 2020-21. New: San Francisco 1954-55, UNC 1992-93, Duke
1997-98 & 2000-01, UNC 2004-05, Kansas 2021-22. Top 3 unchanged.

## Other artifacts — stale or unaffected?

- **h2h.json — unaffected.** Confirmed by reading `compile_h2h.py`: it
  scrapes SR's own `head-to-head.html` pages directly and never reads
  `games_*.json` or the `opp` field.
- **on_this_day.json — unaffected** by the corruption: `generate_on_this_day.py`
  deliberately ignores the stored `opp` field and re-derives ids by
  mirror-voting. Regenerating is harmless but not required.
- **time_machine_results.json — unaffected**: `time_machine.js` reads only
  date/pts/opp_pts/w, never the `opp` id.
- **efficiency_ratings.json, htss_v2_results.json — regenerated** in this
  repair (8.4 MB and 2.3 MB respectively, well under 25 MB).
- Any consumer caching old efficiency/HTSS numbers (site pages built from
  these JSONs) will pick up the new values on next deploy.

## Open items for Josh

1. The 157↔2678 VMI duplicate-log question (1,064 rows blocked on it).
2. The 442 mirror-gap rows: accept slug-only correction, or backfill the
   opponent-log gaps first?
3. The 2,778 rows with slugs outside `espn_to_sr.json`: their stored `opp`
   ids are substring-era output and untrustworthy; consider nulling them or
   extending the slug map.
4. Top-25 shifts above go live whenever the regenerated JSONs deploy —
   review the magnitude before pushing.
