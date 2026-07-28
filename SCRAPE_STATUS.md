# Scrape Status

_Updated 2026-07-28. Previous versions archived at `docs/archive/SCRAPE_STATUS_2026-03.md` (the 187-teams-missing error); the superseded 2026-06-11 figures are noted inline below._

## Game results: COMPLETE (with known season gaps)

- **365/365** Division I teams in `data.json` have game histories in `games_1/2/3.json`, and the games files now map **1:1 onto data.json H** — no orphan keys.
- **561,224** team-game rows total (each game appears once per D1 participant, so unique games are roughly half that).
- 2026-07-28: the previous 567,738 figure (2026-06-11) included six orphan/duplicate logs, found when the box-score integrity audit contradicted every VMI box score:
  - **VMI's real 1,913-game log sat under orphan id 157** while VMI's official id 2678 held a byte-duplicate of Valparaiso's log — the VMI page was rendering Valpo's history. Repaired by `repair_vmi_identity.py` (rekey + 1,064 opp-ref rewrites).
  - Orphan duplicate logs removed: 2563 (South Dakota), 2566 (South Dakota St), 2656 (Tulane — its ~300 extra opp ids grafted onto 2655 first), 2631 (Tulsa — its 2,118 arena strings grafted onto 202 first).
- 2026-07-28: 1,997 double-encoded UTF-8 strings (en-dashes, accents) in opp/arena fields repaired (`fix_games_mojibake.py`).

### Known season gaps (need SR re-scrape, queued in boxscore_rescrape_queue.json)

| Team | Season | Evidence |
|---|---|---|
| Michigan (130) | 1991-92 | log holds ONLY the two Final Four games — the whole Fab Five regular season + early tournament is missing |
| Oklahoma State (197) | 1991-92 | zero rows in the season window |
| BYU (252) | 1956-57 | suspected: the one remaining CONTRADICTED box score (`1957/byu-vs-idaho-state`) is internally consistent but absent from BYU's log |
| Purdue (2509) | 1995-96 | documented in BOXSCORE_INTEGRITY_REPORT.md (June) |

## Player-line box scores

- **20,320** unique games have player-level box scores in `sr_boxscores.json` (up from 2,895 on 2026-06-11 — the July custompages/StatCrew Wayback expansion added ~17,400).
- 359 duplicate entries were collapsed on 2026-07-28 (`dedupe_boxscore_store.py`): the same game had been stored under two key generations, e.g. `1996/princeton-vs-ucla` and `1996/princeton-tigers-vs-ucla-bruins`. That inflated `players.json` game counts for 4,703 players. 28 further groups are listed in `boxscore_duplicates_removed.json` for manual merge — their rosters differ, so collapsing them would drop a real player.
- Integrity (2026-07-28 audit): **19,143 VERIFIED** against the game logs, 1,176 UNCHECKABLE (mostly non-D1/defunct opponents and pre-log-coverage games), **1 CONTRADICTED** (the BYU gap above). `upset_history.json` is **332/332 VERIFIED** — first zero-contradiction state.
- 8 corrupt/unverifiable entries are parked in `sr_boxscores_quarantine.json` (self-pair opponents, pre-coverage UCA games, one duplicated-roster 1957 entry) pending source re-fetch.
- 2,455 opponent sides that no name-level canon could safely resolve ("Miami", "ASU", "UMKC", old program names, filename junk) were renamed per-game from log evidence (`resolve_ambiguous_opponents.py`); 872 sides remain deliberately unresolved (Hartford, Oklahoma City, NYU, Centenary — no D1 log to match against).
- `sr_boxscores_modern.json` is a 179-entry legacy subset, still deployed as a transition fallback; corrections are mirrored into it.

## Constraints

- Sports-Reference politeness limits govern scrape pace — sequential, rate-limited requests only. Do not parallelize against SR.
- Wayback Machine (web.archive.org) is unreachable from remote Claude Code sessions (network egress policy); archive harvesting runs only on the laptop.
