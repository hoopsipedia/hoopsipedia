# Hoopsipedia Roadmap

**Last updated:** 2026-03-17 late evening (post-v0.2.0, post-unbiased review)

## MVP (Before Tournament Thursday) — NEARLY COMPLETE
- [x] Team profiles with all-time stats, rankings, season-by-season records
- [x] Head-to-head comparisons (Winsipedia-style)
- [x] Live bracket integration (ESPN API) — **redesigned as true connected bracket**
- [x] AP Top 25 rankings
- [x] Conference rankings filter
- [x] Global search with autocomplete
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
- [x] Fixed Howard → Michigan click bug (data.json now 150 teams)
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
- [x] Dynamic OG Tags via Cloudflare Pages Function (team + matchup previews for social sharing)
- [x] Share buttons on team profiles and comparison views
- [x] Client-side query param → hash redirect for social crawler compatibility
- [x] True connected NCAA tournament bracket (connectors, Final Four center, region flow)
- [x] Contact page updated to contact@hoopsipedia.com
- [ ] Complete game data scrape — **150 teams done, UMBC + CCNY remaining**
- [ ] Fix John Thompson name collision (Jr vs III counted as same person — 935 ghost wins)
- [ ] Coaching data gaps: pre-1950 seasons and missing schools
- [ ] Fix ESPN ID 245 mapping (Texas A&M in H but contains Texas data)

## Pre-Thursday Polish (from unbiased review feedback)
- [ ] Loading states / skeleton loaders — never show empty tables while data loads
- [ ] Error fallback states — if ESPN or JSON fails, show cached data or clear message, never blank
- [ ] Mobile audit — test every page on 375px (iPhone SE) and 390px (iPhone 14), fix overflow/unreadable text
- [ ] Sitemap.xml — generate for all 360+ team pages so Google can index them
- [ ] Fuzzy search aliases — "Zags" → Gonzaga, "UNC" → North Carolina, "UConn" → Connecticut, etc.

## Post-Scrape Tasks (when UMBC + CCNY finish)
- [ ] Re-split games.json → games_1.json + games_2.json
- [ ] Compile H2H data from all games
- [ ] Recompile coaches with new team data
- [ ] Push updated files live

## Launch Day (Thursday)
- [ ] Final backup: copy updated seasons.json, data.json, games.json to Google Drive
- [ ] Test site on mobile + desktop before sharing any links
- [ ] Keep a browser tab open on hoopsipedia.com to spot-check during the day

## Short-Term (During Tournament — First Weekend Priority)
- [ ] Conference Realignment Tracker — timeline visualization of every D1 conference move (2000-present minimum, ideally all-time), before/after performance metrics, "what if" comparisons. Data already in seasons.json. **Timely, shareable, nobody else does this well.**
- [ ] NET Rankings + Quad Wins Integration — current NET rankings with quad W/L breakdowns, historical NET by season (2018+), bubble watch page for Feb/March, quad record on team pages. **THE March destination feature.**
- [ ] ESPN API live update for active coaches (win count updates after each game)
- [ ] Cinderella / upset history tracker (biggest upsets by seed differential, historical 12-5 matchups, etc.)
- [ ] Dual record view: on-court record vs NCAA official record (show vacated wins transparently)
- [ ] Auto-generated OG images for comparison pages (Team A logo vs Team B logo with key stats)

## Medium-Term (Post-Launch)
- [ ] Players & Draft History (MVP version) — Notable Players section on team pages (all-time scoring leaders, career stat leaders, All-Americans), NBA Draft history by program, "Draft Factory" rankings, player search. **Table stakes — "a sports site without player data is like a baseball site without batting averages"**
- [ ] Mid-major conference data fill-out (~22 conferences, ~230 teams)
- [ ] Backfill all-time stats for newly added teams from NCAA record book
- [ ] Coach career timelines across schools (visual timeline component)
- [ ] Coaching era analysis (program strength under each coach vs overall)
- [ ] Decade-by-decade program strength
- [ ] Rivalry pages (dedicated pages for historic rivalries)
- [ ] Clickable H2H game rows → game detail view (box score, player stats, shooting splits) — click any game in any head-to-head matchup to see full game stats
- [ ] Embeddable widgets — let bloggers/podcasters embed comparison or stat cards on their sites

## Long-Term Vision

### Blue Blood Index
- Proprietary composite ranking of all-time program strength
- 8 weighted pillars: Championship Capital (30%), Tournament Depth (20%), Win Consistency (15%), Poll Prestige (12%), Talent Production (10%), Conference Dominance (5%), Coaching Prestige (5%), Current Momentum (3%)
- Era multipliers to normalize across tournament field sizes
- Dynamic — updates as current season progresses
- Full research doc: RANKING_RESEARCH.md

### Historical Team-Season Score (HTSS) & Time Machine
- Score every individual team-season in history using z-score era-normalization
- 5 components: Dominance (35%), Strength of Schedule (20%), Tournament Performance (20%), Peak Perception (15%), Conference Performance (10%)
- **Head-to-head simulator**: pit any two team-seasons against each other across decades
- **All-Time Best Teams stack ranking**: definitive top 100 team-seasons ever
- **Random Historical Matchup generator**: one-click random cross-era matchup with predicted score — infinite replayability, shareable, homepage widget
- Full research doc: RANKING_RESEARCH.md

### The Hoopsipedia Ranking (TRADEMARK CANDIDATE)
- Combine best predictive signals from NET, KenPom, BPI, Sagarin
- Backtest against historical tournament results
- Goal: THE definitive ranking in college basketball's lexicon

### Data Moats (Longer-Term, Leverage 247Sports Subscription)
- Transfer Portal Impact Analysis — quantify portal winners/losers, track individual transfers, correlate with tournament success
- Recruiting → Results Pipeline — map recruiting classes to outcomes, scatter plot recruiting rank vs tournament seed, individual recruit tracker
- NIL impact on program performance
- Conference strength index over time

### Additional Ideas
- Program trajectory analysis (rising/falling programs over 5/10/20 years)
- "What If" simulator (what if X team was in Y conference?)
- "Relive the Moment" — embed highlights for historical tournament games
- "This Day in CBB History" — daily auto-generated content for return visits
- Tournament-specific content pages (history of 12-5 upsets, best Cinderella runs, seed performance history) — SEO magnets for March-only fans
