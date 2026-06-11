# Phantom Teams Verification Report (Audit M1.4)

**Date:** 2026-06-11
**Scope:** ESPN IDs 2314, 2332, 2907, 2902, 2901, 2078 flagged in `FULL_AUDIT_2026_04.md` (section 6) as phantom 0-0 entries in `data.json`'s `H` map.

## Key finding: already removed

None of the 6 IDs exist in the current `data.json` (no key in `H`, zero raw occurrences anywhere in the file). They were deleted in commit **ba1687f** ("Audit cleanup: remove dead code, fix API hammering, clean takeover system", 2026-04-06), which dropped the `H` map from 373 to 367 teams. Current count is 365 (two further teams were removed by later, unrelated changes — see git history of `data.json`).

This task therefore made **no edits to data.json**. The verification below confirms the April removal was correct for all six teams.

## Verification table

Pre-removal entries were recovered from git (`git show ba1687f^:data.json`). All six had empty conference strings and ATW=0, ATL=0 (indices 4, 5).

| ESPN ID | Name (in old H map) | ESPN API status | Actual program level | Evidence | Verdict | Action taken |
|---|---|---|---|---|---|---|
| 2314 | Knoxville Bulldogs | `isActive: false` | Knoxville College — defunct HBCU small-college program (SIAC, D2/D3/NAIA-level); never D1 MBB | lostcolleges.com/knoxville-college; masseyratings.com/3853 | REMOVE (already removed) | None — verified |
| 2332 | Lewis Flyers | `isActive: false` | NCAA Division II, Great Lakes Valley Conference (Romeoville, IL) | en.wikipedia.org/wiki/Lewis_Flyers; glvcsports.com | REMOVE (already removed) | None — verified |
| 2907 | Trinity International Trojans | `isActive: false` | NAIA (CCAC, Deerfield, IL); program ended when campus closed in 2023 | en.wikipedia.org/wiki/Trinity_International_University; tiutrojans.com | REMOVE (already removed) | None — verified |
| 2902 | Fredonia State Blue Devils | `isActive: false` (ESPN: "SUNY Fredonia Blue Devils") | NCAA Division III, SUNYAC | en.wikipedia.org/wiki/Fredonia_Blue_Devils; sunyacsports.com | REMOVE (already removed) | None — verified |
| 2901 | Staten Island Dolphins | `isActive: false` | NCAA D3 (CUNYAC) through 2019-20, then D2 (East Coast Conference); never D1 | csi.cuny.edu/about-csi/ncaa-division-ii; ncaa.com/schools/staten-island | REMOVE (already removed) | None — verified |
| 2078 | Bridgeport Purple Knights | `isActive: false` | NCAA Division II (ECC, now CACC); never D1 MBB | en.wikipedia.org/wiki/Bridgeport_Purple_Knights; ubknights.com | REMOVE (already removed) | None — verified |

## Residual references in other files

Checked via JSON key-membership and raw-string grep (`"<id>"` and `:<id>,`/`:<id>}` patterns):

| File | References to any of the 6 IDs |
|---|---|
| seasons.json | None |
| h2h.json | None |
| games_1.json | None |
| games_2.json | None |
| games_3.json | None |
| espn_to_sr.json | None |
| game_ids_bulk.json | None |
| sr_boxscores.json | None |

**No follow-up cleanup needed in other files.**

## Validation

```
Before: 365 teams
After:  365 teams (0 removed — all 6 IDs were already absent)
```

## Notes / follow-ups (not fixed here)

- `FULL_AUDIT_2026_04.md` section 6 ("FIX: Remove from data.json") is now resolved and could be marked done in the audit doc.
- Current `H` count (365) is 2 lower than the post-removal count in ba1687f (367); the delta comes from later commits unrelated to these six IDs (e.g. the NET rankings replacement commit 114c672 era changes). Not investigated further — out of scope.
