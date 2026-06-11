# Scrape Status

_Updated 2026-06-11. Previous version (which wrongly claimed 187 teams were missing game data) archived at `docs/archive/SCRAPE_STATUS_2026-03.md`._

## Game results: COMPLETE

- **365/365** Division I teams in `data.json` have game histories in `games_1/2/3.json`.
- Median **1,593** games per team (min 63, max 2,466); **567,738** team-game rows total (each game appears once per D1 participant, so unique games are roughly half that).
- Verified 2026-06-11 by counting keys in `data.json` (`H`) against the union of `games_1.json` + `games_2.json` + `games_3.json`. Earlier figures (569,820 rows, median 1,602) double-counted team 263 (Drake), which appeared in both `games_2.json` and `games_3.json`; the duplicate was merged into `games_3.json` (kept the `{games, slug}` entry with arena data, grafted 97 slug-verified `opp` ids from the legacy copy) and removed from `games_2.json` on 2026-06-11. Each team key now lives in exactly one shard.

## Player-line box scores: the remaining frontier

- **2,895** games have player-level box scores (`sr_boxscores.json`; `sr_boxscores_modern.json` is a 179-entry subset of it — union is still 2,895).
- That is well under 1% of the unique-game universe. Backfill priority: championship runs, tournament games, rivalry games (see memory/box-score plan).

## Constraints

- Sports-Reference politeness limits govern scrape pace — sequential, rate-limited requests only. Do not parallelize against SR.
