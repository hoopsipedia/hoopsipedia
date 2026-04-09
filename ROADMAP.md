# Hoopsipedia Roadmap

**Last updated:** 2026-04-08 (Post-Tournament / Offseason)

**Mission: "Nobody connects the dots across 80+ years of basketball. That's our lane."**

## ✅ SHIPPED (v0.1.0 → v0.5.0)

### Core Features
- [x] Team profiles with all-time stats, rankings, season-by-season records
- [x] Head-to-head comparisons (Winsipedia-style)
- [x] Live bracket integration — true connected NCAA tournament bracket
- [x] AP Top 25 rankings + conference filter
- [x] Global search with autocomplete + fuzzy aliases (Zags, UNC, Nova, etc.)
- [x] Shareable URLs (readable slugs + dynamic OG tags + share buttons)
- [x] Coach Head-to-Head Comparisons (search, stat bars, coaching journey)
- [x] Coaches Leaderboard (Top 100 All-Time Wins)
- [x] Overlaid season history chart in Full Program Comparison
- [x] Tournament Resume per team (color-coded grid, clickable badges)
- [x] Dynamic H2H metrics by decade
- [x] Browser back button support

### Tournament Experience
- [x] Live scores on game cards (in-progress, halftime, final, OT)
- [x] NCAA Tournament / NIT badges + filter tabs + conference dropdown
- [x] Greatest Tournament Upsets page — 340+ verified upsets, era filters, clickable seed pairing cards
- [x] Relive the Moment game pages — cinematic hero with dynamic team colors, YouTube highlights, box scores
- [x] Live Historical Context Engine — seed matchup badges on bracket + game cards
- [x] Live Upset Watch cards — prominent homepage alerts when upsets are brewing
- [x] "On This Day" tournament history ticker — real games from our database + iconic moments
- [x] Game Center — prominent box score at top of comparison for live/recent games, auto-refreshes
- [x] Box scores everywhere — 12,067 ESPN game IDs, 240 SR box scores, clickable H2H game rows
- [x] Live game tracker — polls ESPN, auto-updates records + coach wins when games go Final
- [x] 87 Championship Run pages (all 87 champions 1939-2026) with game-by-game tournament paths, stories, video highlights, and MOP
- [x] Team-colored hero backgrounds using luminance-aware color system (3-tier dark/medium/light detection)
- [x] Static box scores for pre-2002 championship games (Sports Reference data for 1985-1999 title games)
- [x] Championship year badges clickable → run pages or Sports Reference
- [x] Bracket winner fun facts — "First NCAA Tournament win in history", drought/absence facts, blowout callouts
- [x] R32+ matchup preview facts — clickable H2H series history, links to comparison page
- [x] Hardcoded bracket structure — deterministic R32 slot placement, correct feeder ordering
- [x] Bracket R64 historical seed context badges — "16-seeds are 2-152 all-time vs 1-seeds"
- [x] Upset Color Takeover — site accent colors shift to upset winner's colors (nav, buttons, footer, hero)
- [x] Milestone banners — "First ever NCAA Tournament win!" celebration banners for historic moments
- [x] Game card sorting — live games first, today's scheduled next, previous days below with day headers
- [x] Shareable OG tags for Relive the Moment pages + Championship Run pages (unique social previews)
- [x] Share buttons on both Relive the Moment and Championship Run pages
- [x] Dark/white logo variants on hero backgrounds (prevents logo-on-same-color invisibility)

### Starting 5 Comparison
- [x] Side-by-side starting lineups with per-player stats and position assignments
- [x] **Actual starters from ESPN box scores** — uses starter=true flags from most recent game, not minutes heuristic
- [x] Bench comparison toggle
- [x] Tied position edge display
- [x] Shareable Starting 5 links

### Team Profile Enrichment
- [x] NET Rankings table + NET rank badge on profiles
- [x] Quad Record section (Q1-Q4 W-L) with expandable game details
- [x] Program History — all 366 teams with founding year, mascot origin, iconic moment, "Did You Know?"
- [x] NBA Draft History — all 367 teams with lottery picks, #1 overall picks, full draft tables
- [x] HTSS Rating section on team profiles — best season score, all-time rank, program score, sparkline chart
- [x] Advanced Stats toggle — PPG, SRS, SOS, scoring margin, conference record
- [x] Player Roster & Stats — full roster with headshots, sortable by any stat
- [x] Player vs Player comparison — side-by-side stat bars, shareable links
- [x] Real arena photo backgrounds — 110 teams with CC-licensed photos
- [x] "Coming Soon" for shell teams instead of false data

### AI & PWA
- [x] "Ask Hoopsipedia" conversational AI chat — 15 data tools, Claude Haiku, SSE streaming, navigation links
- [x] PWA support — manifest.json, service worker, installable on iOS/Android/desktop
- [x] Coaching database expanded from 100 → 557 coaches (200+ wins)
- [x] Cross-team draft search by year range
- [x] Game-by-game search tool (by season, opponent, tournament)
- [x] Championship lookup by year
- [x] Conference roster tool
- [x] Team tournament record with opponent seed filtering

### Polish & Infrastructure
- [x] Mobile-responsive UI — tables scroll, 44px tap targets, premium card feel
- [x] Mobile responsiveness audit + fixes (coaches table scroll, box score wrapping, milestone banner, upset cards, S5 sizing, 480px breakpoint)
- [x] Skeleton loaders + error fallbacks for every view
- [x] Error isolation — each section wrapped in try/catch
- [x] Sitemap.xml — 145+ URLs for Google indexing
- [x] Dynamic OG Tags via Cloudflare Pages Function (team, compare, game, championship routes)
- [x] NCAA data audit — 297 corrections, vacated wins handled
- [x] QA sweep — all 68 tournament teams verified
- [x] Staging branch for DR environment
- [x] Date rollover set to midnight MST (tournament games can end past midnight ET)
- [x] Nightly sync cron job — auto-updates current season records + coach win totals from ESPN
- [x] Comparison tabs + toggle buttons use left team's color (not hardcoded or takeover color)
- [x] Hoopsipedia bouncing basketball loading icon

### Data
- [x] 366 teams in data.json across 32 conferences (cleaned: removed Stanislaus State ghost entry, fixed VMI mapping)
- [x] 371 teams with full game-by-game data (including CCNY D1-era 1941-1953)
- [x] 367 teams with season-by-season records in seasons.json
- [x] 12,067 ESPN game IDs for instant box score lookup
- [x] 340+ verified upset games with scores (including 4 from 2026 Day 1)
- [x] 199 YouTube highlight clips for upsets
- [x] 240 Sports Reference box scores (1985-2025)
- [x] 376 teams with NET rankings
- [x] H2H data audited — 48 asymmetric entries fixed
- [x] NET quad records recomputed from games data
- [x] Validated batch scraper with dedup, opponent resolution, crash recovery
- [x] 367 teams with NBA Draft History
- [x] 366 teams with team history blurbs
- [x] 110 arena photos
- [x] Ranking formula research complete (RANKING_RESEARCH.md)
- [x] ESPN-to-SR ID mapping cleaned — removed 6 orphan duplicates (Drake, Tulsa, South Dakota, SDSU, Tulane, VMI)
- [x] Drake duplicate (2181/263) fully merged across 9 files
- [x] Virginia seasons data re-scraped with full format (was missing wins/losses/SRS/SOS/AP)

### Proprietary Analytics
- [x] HTSS v1 + v2 — Historical Team-Season Score algorithm (25,000+ team-seasons scored)
- [x] Efficiency Engine — KenPom/NET-style adjusted efficiency (adjOE/adjDE/adjEM) retroactive to 1949
- [x] HTSS Rankings page — Top 100 Seasons, Program Rankings (expandable top 5), By Era (6 eras)
- [x] Time Machine — 10 cross-era matchup simulations with predicted scores, win probability, factor breakdowns
- [x] Close-game resilience scoring with Bayesian smoothing (threshold lowered to 1 game)
- [x] Direct hash routes: #htss-rankings, #time-machine

### Bug Fixes (Tournament Days 1-2)
- [x] Fixed VCU "Why This Mattered" — `note` vs `notes` field name mismatch
- [x] Fixed year comparison bug — seasons.json uses "YYYY-YY" strings, parseInt needed for numeric comparisons
- [x] Fixed California Baptist data — had Cal Berkeley's 114 seasons + 18 tourney appearances instead of correct D-I data
- [x] Fixed Tennessee Final Fours — incorrectly showed 1, should be 0 (never made a Final Four)
- [x] Fixed bracket fun facts for droughts/absences — parseInt needed in 2 more places
- [x] Fixed upset_history.json totalGames counts for 5v12 and 7v10 (off by 1)
- [x] Fixed Texas-BYU score — 77-71 → 79-71
- [x] Fixed Starting 5 showing wrong players (bench players with high minutes picked over actual starters)
- [x] Fixed season toggle buttons — inactive button no longer looks clicked after switching
- [x] Fixed HPU bracket fun fact — now correctly shows "First NCAA Tournament win" (not "first appearance")

---

## 🔥 STACK-RANKED PRIORITIES (Easiest Lift → Highest Value)

### Tier 1: Quick wins, massive impact (< 2 hours each)
1. ~~**Starting 5 Comparison Tool**~~ — ✅ SHIPPED
2. ~~**Upset Color Takeover**~~ — ✅ SHIPPED
3. **Data validation in nightly sync** — Cross-check data.json tournament stats against seasons.json to catch discrepancies like Tennessee FF automatically
4. ~~**Multi-conference filter**~~ — ✅ SHIPPED (Rankings + Teams pages)
5. **Injury/availability alerts** — Surface key player status on comparison pages
6. **Fix bracket sizing** — Regions should fit on screen without horizontal scroll (partially done — responsive tabs at 1024px)
7. ~~**Largest comebacks in NCAA Tournament history**~~ — ✅ SHIPPED (woven into championship run narratives)

### Tier 2: Medium lift, high value (2-6 hours each)
8. ~~**More Championship Run pages**~~ — ✅ SHIPPED (all 87 champions 1939-2026)
9. **Conference Realignment Tracker** — Timeline visualization of every conference move
10. ~~**"Best Teams of All Time" page**~~ — ✅ SHIPPED (HTSS Rankings — Top 100 Seasons, Program Rankings, By Era)
11. **Rivalry pages** — Dedicated pages for Duke-UNC, UK-Louisville, etc.
12. **Top 10 Moments per team** — Curated YouTube clips for every program's greatest moments
13. **H2H highlights for craziest finishes** — Link buzzer beaters and OT games in H2H history
14. **Takeover priority logic refinement** — Better rules for which upset gets the takeover when multiple happen

### Tier 3: Big lift, transformative value (1-2 weeks)
15. ~~**Blue Blood Index (BBI)**~~ — ✅ SHIPPED (became HTSS Program Rankings — top 50 all-time programs)
16. ~~**Historical Team-Season Score (HTSS)**~~ — ✅ SHIPPED (v2 with 9 components, 25,000+ team-seasons)
17. ~~**Time Machine simulator**~~ — ✅ SHIPPED (10 matchups with predicted scores, win probability, factor breakdown)
18. ~~**AI-powered natural language search**~~ — ✅ SHIPPED ("Ask Hoopsipedia" — full LLM-backed conversational data explorer with 15 tools, streaming responses, clickable navigation links, persistent conversation. Powered by Claude Haiku on Cloudflare Pages Functions.)
19. ~~**Random Historical Matchup generator**~~ — ✅ SHIPPED (homepage "What If?" widget — random cross-era matchup from HTSS top 100, predicted score, shuffle button)

### Tier 4: Long-term moat (ongoing)
20. **247Sports data integration** — Transfer portal, recruiting rankings, NIL impact analysis
21. **Full player profiles** — College career stats, NBA career tracking, All-American history
22. **Pre-1985 historical upsets** — By program strength, not seed
23. **Game detail pages for ALL games** — Not just upsets. Every game clickable with box score + highlights
24. **Embeddable widgets** — Let bloggers/podcasters embed our comparisons
25. **"What If" conference simulator** — What if Duke was in the Big Ten?
26. ~~**Program trajectory analysis**~~ — ✅ SHIPPED (Rankings → Trajectories tab — biggest risers/fallers over 5/10/20 year windows, HTSS-based sparkline charts, 15 risers + 15 fallers)
27. **Arena photos for all teams** — Currently 110/366 teams (30%). Need CC-licensed photos for remaining 257. Copyright review needed before expanding visibility beyond background watermarks.

---

## 🏗️ IN PROGRESS / KNOWN ISSUES

### Data Integrity (confirmed outstanding)
- **18 stale h2h IDs** — h2h.json has entries keyed under old ESPN IDs (4, 42, 188, 291, 317, 354, 361, 372, 377, 395, 408, 422, 430, 447, 2112, 2543, 2597, 2631). Data exists but needs remapping to current IDs.
- **4 Sun Belt teams missing conference** — Georgia Southern (290), Texas State (326), Arkansas State (2032), UL Monroe (2433) have empty conference strings
- **New Haven (2441) is D2** — Should be removed or flagged. Has corrupted game data (numeric keys 0-30).
- **10 teams missing coach data** — Southern Indiana (88), UT Arlington (250), Drake (263), Delaware State (2169), FIU (2229), Omaha (2437), Queens (2511), CCNY (2609), Tarleton State (2627), Lindenwood (2815)
- **257 teams missing arena photos** (70%) — Biggest enrichment gap, but copyright concerns under review
- **2003 Syracuse duplicate** in CHAMPIONSHIP_RUNS HTML
- **Louisville 2013** in championship runs — correctly vacated in data.json but journey page has no asterisk
- **E8 > S16 count** for 10 pre-1975 teams — bracket was smaller, counting methodology quirk

---

## 💡 Feature Ideas (Backlog)
- Team origin stories expanded to Wikipedia-level depth
- "This Day in CBB History" — daily auto-generated content (shipped basic version)
- Tournament-specific SEO pages — history of 12-5 upsets, best Cinderella runs
- Dual record view: on-court record vs NCAA official record (show vacated wins transparently)
- **Vacated tournament milestones display** — Figure out best way to present Sweet 16s, Elite 8s, Final Fours that were vacated (e.g., Michigan -2 FF, Memphis -1 FF, Ohio State -1 FF). Currently subtracted from totals but no transparency to the user about why the numbers differ from other sources. Tied to the dual record view feature above.
- Auto-generated OG images for comparison pages
- Decade-by-decade program strength visualizations
- Coach career timelines across schools (visual timeline)
- Coaching era analysis (program strength under each coach)
- **Mobile nav redesign at 375px** — 3 nav items (Upsets, Classics, Champions) are invisible with no scroll affordance. Options: hamburger menu, scrollable nav with fade indicator, two-row nav, or icon-only nav. Needs design decision before implementation.
- Player headshot fallback to school roster pages when ESPN has no photo
- Permanent system crontab for nightly sync (currently session-only)
- **Championship Run video completeness** — Many of the 87 championship journey pages are missing YouTube highlight clips for individual tournament games. Need to curate and fill in video IDs across all runs for a complete multimedia experience.
- ~~**Expanded coaching wins database**~~ — ✅ DONE. Expanded from 100 to 557 coaches (200+ career wins). AI chat queryable with win-range filtering.

---

## 📊 Traffic & Milestones
- **Day 1 (March 19):** 588 unique visitors, peak 73/hour. Zero marketing budget.
- **Day 2 (March 20):** 489 unique visitors by noon, rising. VCU Relive the Moment page driving social shares.
