# Scrape Status

_Updated 2026-07-28. Previous versions archived at `docs/archive/SCRAPE_STATUS_2026-03.md` (the 187-teams-missing error); the superseded 2026-06-11 figures are noted inline below._

## Game results: COMPLETE (with known season gaps)

- **365/365** Division I teams in `data.json` have game histories in `games_1/2/3.json`, and the games files now map **1:1 onto data.json H** — no orphan keys.
- **561,224** team-game rows total (each game appears once per D1 participant, so unique games are roughly half that).
- 2026-07-28: the previous 567,738 figure (2026-06-11) included six orphan/duplicate logs, found when the box-score integrity audit contradicted every VMI box score:
  - **VMI's real 1,913-game log sat under orphan id 157** while VMI's official id 2678 held a byte-duplicate of Valparaiso's log — the VMI page was rendering Valpo's history. Repaired by `repair_vmi_identity.py` (rekey + 1,064 opp-ref rewrites).
  - Orphan duplicate logs removed: 2563 (South Dakota), 2566 (South Dakota St), 2656 (Tulane — its ~300 extra opp ids grafted onto 2655 first), 2631 (Tulsa — its 2,118 arena strings grafted onto 202 first).
- 2026-07-28: 1,997 double-encoded UTF-8 strings (en-dashes, accents) in opp/arena fields repaired (`fix_games_mojibake.py`).

### Known season gaps — 107 team-seasons (was 4)

A systematic scan replaced the hand-listed four. A season counts as a hole
only when it has **≤6 games logged while BOTH adjacent seasons have ≥20** —
the program was demonstrably active, so this is missing data rather than an
inactive year. Full list in **`games_season_gaps.json`**; queued in
`boxscore_rescrape_queue.json`.

- **107 team-seasons across 67 programs.** 91 are completely empty; 16 are
  "tournament-only" — the regular season is gone and just the NCAA games
  survive, which is the Michigan-1991-92 signature.
- Worst by decade: 1990s (36), 1970s (29), 1980s (16), 2000s (11).
- Examples: Arizona 1999 (one game — the first-round loss to Oklahoma, with
  35 and 34 games in the surrounding seasons), Purdue 1996 (two tournament
  games), UConn 1996 (three), Kentucky 1988 (three), Michigan **1992 and
  1993** (two and six — most of the Fab Five era).

Two classes are deliberately EXCLUDED, having been checked and found to be
correct absences rather than data loss:
- **2021 (13 cases)** — the Ivy League cancelled its 2020-21 season and
  several MEAC and other programs were curtailed by COVID.
- **Programs entering or leaving Division I** — Abilene Christian (D-I from
  2014), Seattle U (left 1980, returned 2009), Akron, Denver and similar.
  The both-neighbours-full rule filters these out automatically.

## Player-line box scores

**Overall coverage: 7.2% of the ~280,600 unique games in the logs.** By decade:
1940s 62.7% (tiny sample), 1950s 2.9%, 1960s 3.7%, 1970s 4.8%, 1980s 5.1%,
1990s 5.9%, **2000s 15.2%**, 2010s 8.7%, **2020s 2.2%**. The 2020s are the
least-covered decade despite being the most accessible — worth a pass, since
recent seasons are reachable through the ESPN event map rather than Wayback.

Marquee coverage is much better than the headline rate: **73 of 74**
resolvable NCAA title games have a box score (only 1950 CCNY-Bradley is
missing).

- **20,320** unique games have player-level box scores in `sr_boxscores.json` (up from 2,895 on 2026-06-11 — the July custompages/StatCrew Wayback expansion added ~17,400).
- 359 duplicate entries were collapsed on 2026-07-28 (`dedupe_boxscore_store.py`): the same game had been stored under two key generations, e.g. `1996/princeton-vs-ucla` and `1996/princeton-tigers-vs-ucla-bruins`. That inflated `players.json` game counts for 4,703 players. 28 further groups are listed in `boxscore_duplicates_removed.json` for manual merge — their rosters differ, so collapsing them would drop a real player.
- Integrity (2026-07-28 audit): **19,143 VERIFIED** against the game logs, 1,176 UNCHECKABLE (mostly non-D1/defunct opponents and pre-log-coverage games), **1 CONTRADICTED** (the BYU gap above). `upset_history.json` is **332/332 VERIFIED** — first zero-contradiction state.
- 8 corrupt/unverifiable entries are parked in `sr_boxscores_quarantine.json` (self-pair opponents, pre-coverage UCA games, one duplicated-roster 1957 entry) pending source re-fetch.
- 2,455 opponent sides that no name-level canon could safely resolve ("Miami", "ASU", "UMKC", old program names, filename junk) were renamed per-game from log evidence (`resolve_ambiguous_opponents.py`); 872 sides remain deliberately unresolved (Hartford, Oklahoma City, NYU, Centenary — no D1 log to match against).
- `sr_boxscores_modern.json` is a 179-entry legacy subset, still deployed as a transition fallback; corrections are mirrored into it.

## Constraints

- Sports-Reference politeness limits govern scrape pace — sequential, rate-limited requests only. Do not parallelize against SR.
- Wayback Machine (web.archive.org) is unreachable from remote Claude Code sessions (network egress policy); archive harvesting runs only on the laptop.
