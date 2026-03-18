# Hoopsipedia Roadmap

**Last updated:** 2026-03-17 evening (Tournament Day — v0.2.0 released)

## MVP (Before Tournament Thursday) — NEARLY COMPLETE
- [x] Team profiles with all-time stats, rankings, season-by-season records
- [x] Head-to-head comparisons (Winsipedia-style)
- [x] Live bracket integration (ESPN API)
- [x] AP Top 25 rankings
- [x] Conference rankings filter
- [x] Global search
- [x] Shareable URLs (readable slug format: `#team/duke-blue-devils`)
- [x] Mobile-responsive UI
- [x] About page with NCAA record book as source of truth
- [x] Enhanced coaching history (W-L, win%, best season, Top 100 badges)
- [x] Coaches Leaderboard (Top 100 All-Time Wins)
- [x] Active coach highlighting (green ACTIVE badge)
- [x] Browser back button support (hash-based SPA navigation)
- [x] Live scores on game cards (in-progress, halftime, final, OT) — redesigned with prominent scoreboard
- [x] NCAA Tournament / NIT badges on game cards (logo + round + region)
- [x] Tournament / NIT / All Games filter tabs + conference dropdown
- [x] Tournament Resume per team (color-coded grid of every NCAA appearance)
- [x] Fixed empty space on team profile pages (3-column stats grid)
- [x] Fixed H2H cache bug (series lead flipping on reload)
- [x] Fixed Howard → Michigan click bug (data.json now 140 teams)
- [x] Cloudflare deploy fix (games.json split into games_1.json + games_2.json for 25MB limit)
- [x] Final Four badge → bronze gradient
- [x] Arena name truncation fix in H2H view
- [x] Upcoming tournament game delineation in matchup view (dashed blue border + badge)
- [x] Dynamic H2H metrics by decade (streaks + series record update when decade filter clicked)
- [x] Coach Head-to-Head Comparisons (search, autocomplete, stat bars, coaching journey timeline)
- [x] Coaches button in main navigation bar
- [x] Overlaid season history chart in Full Program Comparison
- [x] SR slug alias map for H2H matching (UMBC, UTEP, VCU, etc.)
- [x] Fixed disappearing finished games on homepage (fetch yesterday's scoreboard)
- [x] Fixed "No Matchup History" for in-progress/recent games (UTC timezone fix)
- [ ] Complete game data scrape (all conferences) — **IN PROGRESS, 3 batches running (140 teams done)**
- [ ] Populate all 362 teams in H (currently 140, up from 108) — consistent data across all programs
- [ ] Fix John Thompson name collision (Jr vs III counted as same person — 935 ghost wins)
- [ ] Coaching data gaps: pre-1950 seasons and missing schools (Northeastern for Calhoun, Montana Tech for Sampson, early Army for Knight)
- [ ] Fix ESPN ID 245 mapping (Texas A&M in H but contains Texas data — needs real Texas A&M scrape)
- [ ] Final ESPN API fallback cleanup (remove stale fallbacks #1 and #5 after scrape completes)

## Active Scrape Status
Three batch processes running (restarted after getting stuck):
- **Batch 1:** drake, washington-state, pacific, san-diego, north-carolina-wilmington, fordham
- **Batch 2:** george-mason (done), la-salle, loyola-il, saint-josephs, virginia-commonwealth, liberty, loyola-marymount, umbc, pepperdine, portland, seattle, ccny, texas-el-paso, texas-southern
- **Batch 3:** WCC conference

**After scrape completes:**
- [ ] Re-split games.json → games_1.json + games_2.json
- [ ] Compile H2H data from all games
- [ ] Recompile coaches with new team data
- [ ] Push updated files live

## Launch Day (Thursday)
- [ ] Final backup: copy updated seasons.json, data.json, games.json to Google Drive (replace old backups)
- [ ] Verify Time Machine is running on Mac (System Settings → General → Time Machine)
- [ ] Test site on mobile + desktop before sharing any links
- [ ] Keep a browser tab open on hoopsipedia.com to spot-check during the day

## Short-Term (During Tournament — First Weekend Priority)
- [ ] Dynamic Open Graph tags via Cloudflare Worker (shared links show team/matchup-specific previews instead of generic) **← force multiplier on ALL sharing**
- [ ] ESPN API live update for active coaches (win count updates after each game)
- [ ] Cinderella / upset history tracker (biggest upsets by seed differential, historical 12-5 matchups, etc.) **← perennial viral topic**
- [ ] Dual record view: on-court record vs NCAA official record (show vacated wins transparently)
- [ ] Friend UX feedback items (pending)
- [ ] Medium UI upgrades between tournament rounds

## Medium-Term (Post-Launch)
- [ ] Mid-major conference data fill-out (~22 conferences, ~230 teams): Missouri Valley, CAA, Sun Belt, MAC, C-USA, MAAC, Horizon, Big West, Big Sky, SoCon, Ivy, WAC, ASUN, Summit, Patriot, Southland, Big South, NEC, OVC, America East, MEAC, SWAC
- [ ] Backfill all-time stats (ATW, ATL, NC, FF, S16, etc.) for newly added teams from NCAA record book
- [ ] Historical player stats (top 20 scorers, rebounders, etc. per team)
- [ ] Coach career timelines across schools (visual timeline component)
- [ ] Coaching era analysis (program strength under each coach vs overall)
- [ ] Conference realignment history tracker
- [ ] Decade-by-decade program strength
- [ ] Rivalry pages (dedicated pages for historic rivalries)
- [ ] Clickable H2H game rows → game detail view (box score, player stats, shooting splits, lead changes) — click any game in any head-to-head matchup to see full game stats

## Long-Term Vision

### Blue Blood Index
- Proprietary composite ranking of all-time program strength
- Weight factors: championships, Final Fours, win %, recruiting, NBA draft picks, AP poll presence
- Will generate debate and engagement

### March Madness History
- Tournament journey view for every team's NCAA tournament runs
- Round-by-round brackets for historical tournaments
- Cinderella tracker (biggest upsets by seed differential)

### "Relive the Moment"
- Embed or link to game highlights for historical tournament games
- Partner with YouTube, NCAA archives for video content
- Interactive tournament brackets with highlight links

### The Hoopsipedia Ranking (TRADEMARK CANDIDATE)
- Reverse engineer every weighted formula used in March Madness selection:
  - NET (NCAA Evaluation Tool) - efficiency, winning, schedule strength, scoring margin, quality wins
  - KenPom - adjusted offensive/defensive efficiency, tempo
  - BPI (ESPN) - strength of record, game predictions
  - Sagarin - ELO-based ratings, schedule strength
  - KPI, SOR, RPI (legacy metrics)
- Analyze which individual measurements from each system are the strongest predictors of tournament success
- Drop all the weak/redundant signals
- Combine the best-of-the-best into one proprietary super-metric
- Backtest against historical tournament results to validate
- Goal: Create THE definitive ranking that becomes part of college basketball's lexicon
- Trademark the formula and name

### Time Machine: Cross-Era Team Matchups & All-Time Rankings
- Use The Hoopsipedia Ranking metrics to score every team-season in history
- Normalize across eras (strength of schedule, pace, conference strength, tournament depth)
- **Head-to-head simulator**: pit any two team-seasons against each other across decades (e.g. 2015 Kentucky vs 1976 Indiana)
- **All-Time Best Teams stack ranking**: definitive top 100 (or 500) team-seasons ever
- Shareable results ("According to Hoopsipedia, 1996 Kentucky is the #3 team of all time")
- Filter by era, conference, seed, or championship teams only
- Debate fuel: fans argue the rankings, share on social, come back for more
- **Random Historical Matchup generator**: one-click button serves a random cross-era matchup with a predicted score (e.g. "1992 Duke 78, 2008 Memphis 72") — infinite replayability, shareable results, homepage widget potential

### Additional Long-Term Ideas
- Program trajectory analysis (rising/falling programs over 5/10/20 years)
- Recruiting pipeline visualization
- Transfer portal impact tracker
- NIL impact on program performance
- Conference strength index over time
- "What If" simulator (what if X team was in Y conference?)
