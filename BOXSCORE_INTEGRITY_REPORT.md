# Box Score Integrity Report — 2026-06-11

Cross-check of `sr_boxscores.json` and `upset_history.json` against the team
game logs (`games_1/2/3.json`, 569K rows, cutoff 2026-03-19), produced by
`audit_boxscore_integrity.py`. Re-run any time with:

```
python3 audit_boxscore_integrity.py            # audit only, deterministic
python3 audit_boxscore_integrity.py --apply    # re-apply the vetted corrections
```

Method: every entry is matched against both teams' logs (mirror-verified
where both logs cover the game). The logs' `opp` id field is ignored
(known substring-matching bug); opponents are identified by
`opp_slug` + date + scores with slug→id resolution by mirror voting, the
same approach as `generate_on_this_day.py`. Verdicts: **VERIFIED**
(game found in logs), **CONTRADICTED** (a covered log shows a different
game or no such game), **UNCHECKABLE** (team unresolvable, season gap in
logs, or period past the 2026-03-19 scrape cutoff — the audit never
contradicts inside the in-progress 2026 window).

## Classification counts

| file | entries | VERIFIED | CONTRADICTED | UNCHECKABLE |
|---|---|---|---|---|
| sr_boxscores.json (before) | 2,894 | 2,536 | 25 | 333* |
| sr_boxscores.json (after corrections) | 2,892 | 2,804 | 23 | 65 |
| upset_history.json (before) | 343 | 320 | 19 | 4 |
| upset_history.json (after corrections) | 339 | 322 | 13 | 4 |

\* the before-run predates short-name resolution (UNC/Pitt/FDU/…); with the
final resolver the before-state is 2,804 / 25 / 65. The 65 uncheckable are:
46 season-2026 entries (logs end mid-tournament), 4 entries whose teams' whole
seasons are missing from the logs (see "games-file gaps" below), and entries
involving never-scraped programs (e.g. Hartford).

## Corrections applied (all gated on this run's own audit verdicts)

### upset_history.json (343 → 339 upsets; 4 deletions, 2 score fixes)

1. **DELETED 4v13 "1997 College of Charleston over Maryland 75-68"** —
   duplicate of the real game under wrong seeds. Logs (mirrored in both
   teams' logs): 1997-03-13, Charleston 75-66 Maryland. The 12v5 seeding is
   correct, so the 5v12 copy was kept.
2. **FIXED 5v12 1997 College of Charleston over Maryland: 75-68 → 75-66**
   (log-verified, mirror, 1997-03-13).
3. **FIXED 5v12 1999 Southwest Missouri State over Wisconsin: 43-41 → 43-32**
   (log-verified, mirror, 1999-03-12: missouri-state 43, wisconsin 32).
4. **DELETED 5v12 "1996 Arkansas-Little Rock over Purdue 65-63"** — Little
   Rock's complete March 1996 log (last game 1996-03-13 at Vanderbilt)
   contains no Purdue game; no LR–Purdue 65-63 exists in any season. The
   real LR–Purdue upset is already present: 2016-03-17, 85-83 2OT (verified).
   (Purdue's 1995-96 season is absent from its log — see gaps below.)
5. **DELETED 7v10 "2014 Stanford over Kansas State 60-57"** — no
   Stanford–KSU game in 2014 (both logs cover March 2014). The 60-57 score
   belongs to Stanford–**Kansas**, 2014-03-23 (round of 32). KSU lost to
   Kentucky 49-56 on 2014-03-21 and was done.
6. **DELETED 8v9 "2025 Georgia over Maryland 68-59"** — no Georgia–Maryland
   game in 2025. Georgia's only tournament game: lost to Gonzaga 68-89 on
   2025-03-20.

Group counters for 4v13/5v12/7v10/8v9 were re-derived to keep the file's own
invariant (`lowerSeedWins == len(upsets)`, `totalGames == higher + lower`,
`upsetPct` recomputed half-up to 2dp). `higherSeedWins` untouched.

### sr_boxscores.json (2,894 → 2,892 entries; 2 deletions)

Both confirmed CONTRADICTED and both are **franken-entries**: a real SR page
was scraped, then team names/seeds/scores were stamped over with fabricated
upset metadata, leaving another game's player lines inside:

1. **DELETED `1999/charlotte-49ers-vs-stanford-cardinal`** (claimed Charlotte
   79-77 Stanford, 1999-03-12). Charlotte played **Rhode Island** that day
   (81-70 OT, C-USA tournament, Bradley Center); Stanford played Alcorn State
   3/11 and Gonzaga 3/13. The entry's "Stanford" roster is the 1998-99 Rhode
   Island Rams (Lamar Odom, Antonio Reynolds-Dean, Preston Murphy…) and the
   player sums are 81/70 — the real CLT–URI score.
2. **DELETED `2001/creighton-bluejays-vs-virginia-cavaliers`** (claimed
   Creighton 84-69 Virginia, 2001-03-15). Creighton lost to **Iowa** 56-69
   that day; Virginia lost to Gonzaga 85-86 on 3/16. The entry's "Virginia"
   roster is the 2000-01 Iowa Hawkeyes (Reggie Evans, Dean Oliver, Duez
   Henderson…) and player sums are 56/69 — the real Creighton–Iowa score.

`_metadata.totalGames` updated 2894 → 2892. Pre-correction backups:
`/tmp/upset_history.backup.json`, `/tmp/sr_boxscores.backup.json`.

## NOT corrected — needs Josh's judgment

### upset_history.json: 13 remaining CONTRADICTED entries

Per the conservative policy only the named entries above were touched.
Log evidence for the rest (all mirror-checked):

**Likely score fixes (right game, wrong score):**
- 5v12 1992 NMSU over DePaul "68-62" → logs say **81-73** (1992-03-20)
- 5v12 2010 Cornell over Temple "78-63" → logs say **78-65** (2010-03-19)
- 6v11 2025 Drake over Missouri "74-65" → logs say **67-57** (2025-03-20)
- 7v10 2025 New Mexico over Marquette "69-63" → logs say **75-66** (2025-03-21)
- 8v9 2025 Baylor over Mississippi State "75-70" → logs say **75-72** (2025-03-21)

**Likely year fix:**
- 5v12 "1995" Drexel over Memphis 75-63 → the exact game exists on
  **1996-03-14** (Drexel 75-63 Memphis, in Drexel's log). Year off by one;
  no 1996 duplicate exists.

**Winner inverted (these "upsets" never happened — favorites won):**
- 6v11 2016 "Michigan over Notre Dame 70-63" → ND won 70-63 (2016-03-18)
- 7v10 2022 "Loyola Chicago over Ohio State 54-41" → OSU won 54-41 (2022-03-18)
- 7v10 2023 "Utah State over Missouri 76-65" → Missouri won 76-65 (2023-03-16)

**Fabricated, no plausible correction (delete candidates):**
- 5v12 1999 Charlotte over Stanford 79-77 — no such game (see deletion #1
  above; this upset entry is the source of that fabricated boxscore)
- 5v12 2001 Creighton over Virginia 84-69 — no such game. The **real** 2001
  5v12 upset, Gonzaga over Virginia 86-85 (in Virginia's log, 2001-03-16),
  is **missing** from the list — this fabrication displaced it.
- 7v10 2014 Dayton over Providence 68-65 — no such game; Dayton beat Ohio
  State 60-59 on 2014-03-20, Providence lost to UNC 3/21
- 5v12 2004 Nevada over Gonzaga 72-66 — the only 2004 Nevada–Gonzaga game is
  91-72 on 2004-03-20, which was a round-of-32 game (10-seed Nevada), not a
  first-round 5v12

**Missing real upsets noticed in passing (additions for Josh to verify):**
- 2014 7v10: Stanford(10) over New Mexico(7) 58-53 on 2014-03-21 (in logs)
- 2001 5v12: Gonzaga(12) over Virginia(5) 86-85 on 2001-03-16 (in logs)

**Five duplicate seed-conflict pairs remain** (same game filed under two
bracket keys with different seeds; the OTD generator currently skips all 10
entries as unresolvable — seeds aren't in the logs, needs an external source):
- 1987 Austin Peay–Illinois 68-67 (3v14 and 5v12)
- 1989 Minnesota–Kansas State 86-75 (5v12 and 6v11)
- 1989 South Alabama–Alabama 86-84 (5v12 and 6v11)
- 1991 Temple–Purdue 80-63 (5v12 and 7v10)
- 2019 Murray State–Marquette 83-64 (5v12 and 8v9)

**Aggregate counters are unverifiable**: `higherSeedWins`/`totalGames` were
not derived from any audited source (5v12 had 161 games, 6v11 has 162 — a
seed matchup is structurally 4 games/year). Metadata claims coverage
"through the 2026 first round" but 1v16 totals 160 games = 40 tournaments.

### sr_boxscores.json: 23 remaining CONTRADICTED entries (NOT deleted — player lines may still have value, but every one carries wrong metadata)

**Same-team-twice corruption (one team's block overwritten by the other's
name/seed/score; player lines appear to be from the real game):**
- `1986/lsu-tigers-vs-memphis-tigers` — both sides "Memphis Tigers 81"; sums 87/94; URL points at 1986-03-13 LSU–Purdue
- `1986/lsu-tigers-vs-purdue-boilermakers` — both sides "Purdue 87"; real game LSU 94-87 2OT Purdue exists 1986-03-13
- `1996/arkansas-little-rock-trojans-vs-purdue-boilermakers` — both sides "Purdue 63"; fabricated game (see deletion above)
- `2004/nevada-wolf-pack-vs-gonzaga-bulldogs` — both sides "Gonzaga 66"; scraped page was Gonzaga 76-49 Valparaiso (2004-03-18)
- `2014/stanford-cardinal-vs-kansas-state-wildcats` — both sides "Kansas State 57"; fabricated game
- `2025/arkansas-razorbacks-vs-kansas-jayhawks` — both sides "Arkansas 79"; real game Arkansas 79-72 Kansas 2025-03-20
- `2025/georgia-bulldogs-vs-maryland-terrapins` — both sides "Maryland 59"; scraped page was Maryland 81-49 Grand Canyon; fabricated game

**Real game, wrong URL/date metadata (audit found the exact game elsewhere):**
- `1994/tulsa-golden-hurricane-vs-ucla-bruins` — game real (Tulsa 112-102 UCLA 1994-03-18); URL malformed
- `2018/alabama-crimson-tide-vs-virginia-tech-hokies` — URL says 2017-12-03; the real game is 2018-03-15 (Alabama 86-83 VT) **but** player sums are 65/62, so the scraped page is some other game entirely
- `2011/florida-state-seminoles-vs-notre-dame-fighting-irish` — real game 2011-03-20 (FSU 71-57); URL dated 3/18; sums 50/57 don't match claimed 57/71

**Claimed scores contradict the real game on the same date (player sums match
the REAL scores, claimed team scores stamped from the bad upset_history
entries):**
- `1992/new-mexico-state-aggies-vs-depaul-blue-demons` — claimed 68-62, real 81-73 (sums 81/73)
- `2010/cornell-big-red-vs-temple-owls` — claimed 78-63, real 78-65 (sums 78/65)
- `2025/drake-bulldogs-vs-missouri-tigers` — claimed 74-65, real 67-57 (sums 67/57)
- `2025/new-mexico-lobos-vs-marquette-golden-eagles` — claimed 69-63, real 75-66 (sums 75/66)
- `2025/baylor-bears-vs-mississippi-state-bulldogs` — claimed 75-70, real 75-72 (sums 75/72)
- `2023/utah-state-aggies-vs-missouri-tigers` — claimed Utah St 76-65; Missouri won 76-65 (winner inverted)
- `2022/loyola-chicago-ramblers-vs-ohio-state-buckeyes` — claimed Loyola 54-41; OSU won 54-41 (winner inverted)
- `2016/michigan-wolverines-vs-notre-dame-fighting-irish` — claimed Michigan 70-63; ND won 70-63 (winner inverted)
- `2014/dayton-flyers-vs-providence-friars` — fabricated matchup; sums 60/59 = the real Dayton 60-59 Ohio State game scraped from `2014-03-20-dayton`
- `1995/drexel-dragons-vs-memphis-tigers` — URL dated 1995-03-16 hits Drexel's real 49-73 loss to Oklahoma State (NIT); the claimed game is the **1996** Drexel–Memphis 75-63
- `1997/college-of-charleston-cougars-vs-maryland-terrapins` — claimed Maryland 68; real 75-66 (sums 75/66). Candidate for a simple score fix (68 → 66) since everything else matches.

**Women's games in a men's dataset (bulk-scrape strays):**
- `2011/texas-am-vs-stanford` 63-62 — 2011 NCAA **women's** Final Four
- `2018/notre-dame-vs-uconn` 91-89 — 2018 NCAA **women's** Final Four (OT)

### games-file gaps observed (games_1/2/3.json — owned elsewhere, FYI)

- Three logs are stored twice under two ids: Valparaiso under **2674 and
  2678 (2678 is VMI Keydets in data.json — wrong id)**, South Dakota under
  233 and 2563, South Dakota State under 2571 and 2566. The audit merges
  them; the OTD generator's mirror voting is affected the same way.
- Whole seasons missing from major-team logs: Purdue 1995-96,
  Memphis 1985-86, Kentucky and Maryland 1987-88, Michigan and Oklahoma
  State 1991-92, Iowa State and California 1995-96, Arizona and Iowa 1995-96.

## generate_on_this_day.py — post-correction run

```
wrote on_this_day.json (319.6 KB)
  canonical_games: 277783
  champ_cross_checked: 70
  champ_no_opponent_data: 3
  champ_no_season_games: 12
  champ_skipped_incomplete_season: 1
  championship_events: 73
  days_with_events: 157
  opp_id_corrected: 437
  slugs_resolved: 360
  slugs_seen: 1597
  teams: 370
  upset_dated_via_game_logs: 312
  upset_dated_via_sr_boxscores: 3
  upset_dup_conflict_skipped: 10
  upset_sr_fallback_contradicted: 7
  upset_undated_skipped: 7
```

**The corrected Charleston–Maryland upset now publishes** on 03-13:

> 1997-03-13: 12-seed College of Charleston Cougars stuns 5-seed Maryland
> Terrapins 75-66 in the NCAA Tournament first round (sig 84, espn ids 232/120)

No event referencing Charlotte–Stanford or Creighton–Virginia exists in the
output. Event mix: 712 blowout, 311 ot, 81 upset, 73 championship,
21 high_score (1,198 total — same as before; the corrected Charleston event
replaces a slot, the deleted fabrications were never publishable).

## Hypothesis: how the fabricated data got in (git archaeology, read-only)

1. **2026-03-17, commit `1912a73` "Add verified upset history data (214
   games with scores)"** — every contradicted upset_history entry that
   predates 2026 is already present in this first version of the file,
   including all four deleted fabrications, both wrong scores, the
   off-by-one Drexel year, the three inverted winners, and the misseeded
   duplicates. Despite "verified" in the message the data matches no source:
   the error pattern (real adjacent details recombined — e.g. Stanford's real
   60-57 win over *Kansas* attached to Kansas *State*; the real 1995
   Stanford–Charlotte 7v10 mirrored into a fake 1999 5v12) is characteristic
   of LLM-recalled "facts" committed without checking. The commit is
   co-authored by Claude Opus 4.6.
2. **2026-03-18, commit `9ec8ca7` "Add SR box score data files (240 total
   box scores)"** — both fabricated boxscores arrive here. The scrape target
   list was generated **from upset_history.json** (games_to_scrape.json
   carries upset_history's winner/loser/seed/score fields verbatim), so the
   fabricated upsets became scrape targets. URLs were guessed as
   `{date}-{winner-slug}.html`; for the fake games those URLs resolved to
   *real* pages (Charlotte's C-USA game vs Rhode Island; Creighton's loss to
   Iowa), and the pipeline then stamped the expected names/seeds/scores over
   the parsed page — provably: the rosters and player sums inside belong to
   Rhode Island 1999 and Iowa 2001. The same stamping mechanism explains the
   seven "same-team-twice" entries and every claimed-vs-player-sum mismatch
   above: wherever upset_history was wrong, the boxscore was bent to agree
   with it instead of with the scraped page.
3. The 2,654 bulk entries added later (uncommitted, `_metadata` lastUpdated
   2026-05-07) come from crawling SR brackets directly without the stamping
   step — 2,536 of them verify cleanly against the logs and none contradict,
   except the two women's-tournament strays. The contamination is therefore
   confined to the March-18 batch of 240.

**Takeaway:** every downstream artifact generated from upset_history.json
between 2026-03-17 and today inherited these errors (the Upsets page totals,
H2H fallbacks using sr_boxscores, the old On-This-Day fallback dating). The
generator's contradiction guards (added earlier) plus this cleanup close the
known holes; the 13 remaining contradicted upsets above still render on any
page that reads upset_history.json directly.
