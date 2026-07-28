# What To Do Next — Recommendation for Josh (2026-07-28)

Supersedes the 2026-06-12 version, which predates the July box-score
expansion (2,895 → 20,679 games) and the integrity pass that followed it.

## Where things stand

The July harvest grew the box-score archive 7x. This session audited what
that growth produced and repaired it. The archive is now *verified* rather
than merely large:

| | before | after |
|---|---|---|
| box scores contradicted by the game logs | 84 | **1** |
| box scores log-verified | 16,906 | **19,502** |
| `upset_history.json` contradictions | 13 | **0** (332/332) |
| unparseable player stat lines | 33,413 (8.2%) | **174 (0.04%)** |
| players indexed | 11,768 | **54,377** |
| invariant tests | 48 | **54** |

Everything below is on `claude/hoopsipedia-work-kctyau` (13 commits), not
merged. **Nothing here is deployed yet.**

### The three findings that matter

1. **VMI's team page was rendering Valparaiso's history.** VMI's real
   1,913-game log sat under orphan id `157`, which no page owns, while
   VMI's own id held a byte-copy of Valpo's log. Four more orphan duplicate
   logs (South Dakota, South Dakota St, Tulane, Tulsa) were double-counting
   games into the ranking engine's opponent adjustment, which is why every
   team's efficiency rating shifted slightly when it was regenerated. The
   games files now map 1:1 onto the 365 teams and a test enforces it.

2. **The player parser was rejecting every pre-1980 box score.** It
   dispatched on the presence of a minutes column, which those sources
   don't print, so a third of a million real stat lines were discarded as
   "unparseable". Recovering them brought back exactly the historical
   population the site exists for — Austin Carr, Issel, Bradds, Maravich's
   64-point game.

3. **The archive stopped being tournament-shaped, which broke a premise.**
   It is now ~72% regular season and unevenly harvested (Arkansas 69.6% of
   its games, Duke 13.7%). Any leaderboard sorted by archive totals ranks
   *harvest depth*, not players: Laettner drops off entirely and Hofstra's
   Charles Jenkins tops it. `PLAYERS_NOTES.md`'s old instruction to label
   this data "tournament archive" was obsolete and actively misleading, and
   is rewritten.

## Recommended priority order

### 1. Review and merge the branch
13 commits, all data-integrity work, 54 tests passing. Worth reading the
commit messages rather than the diffs — the regenerated data files dominate
the diff but the reasoning is in the messages. Nothing yet reads `players/`,
so merging changes no user-facing behaviour except the corrected data.

### 2. Narrative repair pass (unchanged from June — still the top content risk)
354 findings, **245 provably wrong**, including wholesale fabrications, all
still live on team pages. Mechanics unchanged: an agent drafts corrections
from the already-collected sources, you approve in batches of ~25, a script
applies only approved entries. Two or three 20-minute sessions.

### 3. Re-scrape the four known season gaps — needs your laptop
`web.archive.org` and the live site are both blocked from Claude Code's
cloud sessions, so all harvesting has to run locally. Queued in
`boxscore_rescrape_queue.json`:
- **Michigan 1991-92** — the entire Fab Five regular season is missing from
  the game log (only the two Final Four games are present).
- Oklahoma State 1991-92, BYU 1956-57, Purdue 1995-96.
- Plus the 8 entries in `sr_boxscores_quarantine.json` needing a source
  re-fetch, and the 17 deleted season histories from the June impostor fix
  (Texas A&M first — still showing zero season history).

### 4. Build the players page — the data is now ready and honest
`players/index.json` carries per-team coverage denominators so the UI can
state the true thing ("1,355 of Virginia's 2,215 games are archived"). Two
non-negotiables, both documented in `PLAYERS_NOTES.md`: default the sort to
**per-game, not totals**, and render a `null` stat as an em dash, never 0 —
4,258 players have blocks that were never recorded, and printing 0 would
assert a fact about eras that didn't count them.

### 5. Wave 3: index.html modularization
The 23.5K-line monolith is the last structural debt, and it gates the
queued UI work (On This Day module, unified-rankings page, XSS/CSP polish,
mobile/a11y sweep). I deliberately did **not** start this — it is a large
frontend refactor and mixing it into a data-repair branch would make both
unreviewable. Worth its own branch.

### 6. Payload cut, continued
`players.json` (18.5MB) joins `games_1/2/3` and `sr_boxscores` as a master
build artifact the browser never fetches. The transition fallbacks are
still deployed; dropping them is still one release cycle away.

## Open decisions only you can make
- **Ranking weights** — 3 questions in `RANKING_METHODOLOGY.md`; still the
  one tuning session between you and a shippable unified-rankings page.
- **Michigan as 2026 champion** in data.json (NCY) — 10-second check.
- **Fact-check review** — the two FACTCHECK_FINDINGS files.
- **Backups off-machine** — tarballs still live only on the laptop.
- **`players.json` in git** — 18.5MB of build artifact per rebuild is real
  repo weight. Fine for now; worth deciding whether it belongs in the repo
  at all or should be generated at deploy time.

## Smaller things I noticed but did not act on
- The 2011 FSU–Notre Dame upset "highlight" video is the 2011 Champs Sports
  Bowl — **football**. Wrong video id, needs a replacement.
- `upset_boxscores.json` / `upset_highlights_data.json` carry pre-existing
  orphan keys from slug-format drift (`miami-hurricanes` vs
  `miami-fl-hurricanes`); worth a key-normalization pass.
- 872 box-score opponent sides stay deliberately unresolved (Hartford,
  Oklahoma City, NYU, Centenary — no D-I log to match against). Correct as
  is; listed so it isn't rediscovered as a bug.
- 11 D-I programs have no archived players at all — mostly recent D-I
  additions (Bellarmine, Stonehill, Le Moyne, Mercyhurst, Lindenwood).

## What I'd explicitly NOT do next
- Don't bulk-apply narrative fixes without batch approval — accuracy
  culture is the product.
- Don't ship a players page ranked by archive totals. See finding 3.
- Don't delete the monoliths until one full release cycle has passed.
