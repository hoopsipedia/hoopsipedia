# tests/

## test_engine_invariants.py

Invariant regression tests for the ranking engines' data files
(`efficiency_ratings.json`, `htss_v2_results.json`, `unified_rankings.json`,
`data.json` H table, `on_this_day.json`, `games_1/2/3.json`).

Pure stdlib, no pytest:

```
python3 tests/test_engine_invariants.py
```

Exit code 0 = all invariants hold; 1 = at least one FAIL. Runs in CI as the
`data-invariants` job (`.github/workflows/ci.yml`).

### Why invariants, not golden values

These files are regenerated whenever game coverage improves, so exact numbers
are intentionally NOT snapshotted. Every assertion is a structural or
mathematical property that must hold for any correct regeneration (e.g.
`adjEM == adjOE - adjDE`, league-average adjEM ~= 0 per season, rankings
sorted descending, cross-file espnId resolvability).

### Documented invariant decisions

- **D1 — htss allTimeTop100 "strictly descending" relaxed to non-increasing.**
  Published `htss` scores are rounded to 2 decimals, and the current (correct)
  output contains exact ties at that precision (e.g. two entries at 79.49).
  Requiring strict descent at 2-dp precision would be a false invariant. The
  test instead requires: scores non-increasing AND `rank` fields exactly
  `1..100` in order, which preserves the real intent (a totally ordered
  top-100) without being broken by rounding ties. Same relaxation applies to
  `unified_rankings.json` score lists.

- **D2 — data.json H: `NCY == ""` accepted as an empty championship list.**
  66 of 365 teams with zero championships serialize index 7 (NCY) as `""`
  rather than `[]`. This is the established format consumed by the site, so
  the test treats `""` as an empty list. `len(NCY) == NC` and year range
  1939-2030 are still enforced for all teams.

- **No `ATW >= ATL` check** — deliberately omitted (losing programs exist;
  not a real invariant).

### Known data issues / SKIP list

The `KNOWN_DATA_ISSUES` dict at the top of the test file converts a named
check into a loud SKIP (never a silent pass) when a confirmed upstream data
problem is awaiting a fix. **Currently empty** — all invariants hold against
live data as of 2026-06-11. Any entry added there must be documented here
with the failing detail and a link/owner for the fix.
