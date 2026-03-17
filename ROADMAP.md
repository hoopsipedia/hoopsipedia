# Hoopsipedia Roadmap

## MVP (Before Tournament Thursday)
- [x] Team profiles with all-time stats, rankings, season-by-season records
- [x] Head-to-head comparisons (Winsipedia-style)
- [x] Live bracket integration (ESPN API)
- [x] AP Top 25 rankings
- [x] Conference rankings filter
- [x] Global search
- [x] Shareable URLs
- [x] Mobile-responsive UI
- [x] About page with NCAA record book as source of truth
- [x] Enhanced coaching history (W-L, win%, best season, Top 100 badges)
- [x] Coaches Leaderboard (Top 100 All-Time Wins)
- [x] Active coach highlighting (green ACTIVE badge)
- [ ] Complete game data scrape (all conferences)
- [ ] Populate all 362 teams in H (not just 108) — consistent data across all programs
- [ ] Fix John Thompson name collision (Jr vs III counted as same person — 935 ghost wins)
- [ ] Coaching data gaps: pre-1950 seasons and missing schools (Northeastern for Calhoun, Montana Tech for Sampson, early Army for Knight)
- [ ] Fix ESPN ID 245 mapping (Texas A&M in H but contains Texas data — needs real Texas A&M scrape)
- [ ] Final ESPN API fallback cleanup (remove stale fallbacks #1 and #5 after scrape completes)

## Stretch Goals (Before Thursday if possible)
- [ ] Fix empty space on left side of team profile pages **← first impression on every profile visit, can't look broken**
- [ ] Coach head-to-head comparisons (same engine as teams — W-L, win%, championships, tournament wins, best seasons side by side) **← DEBATE FUEL for every matchup announcement**
- [ ] Tournament resume per team (dedicated view: every tournament appearance, round reached, year) **← #1 searched topic during March Madness**

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

### Additional Long-Term Ideas
- Program trajectory analysis (rising/falling programs over 5/10/20 years)
- Recruiting pipeline visualization
- Transfer portal impact tracker
- NIL impact on program performance
- Conference strength index over time
- "What If" simulator (what if X team was in Y conference?)
