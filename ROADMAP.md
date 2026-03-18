# Hoopsipedia Roadmap

**Last updated:** 2026-03-18 evening (eve of tournament)

**Mission: "Nobody connects the dots across 80+ years of basketball. That's our lane."**

## ✅ SHIPPED (v0.1.0 → v0.3.0)

### Core Features
- [x] Team profiles with all-time stats, rankings, season-by-season records
- [x] Head-to-head comparisons (Winsipedia-style)
- [x] Live bracket integration — **true connected NCAA tournament bracket**
- [x] AP Top 25 rankings + conference filter
- [x] Global search with autocomplete + **fuzzy aliases** (Zags, UNC, Nova, etc.)
- [x] Shareable URLs (readable slugs + dynamic OG tags + share buttons)
- [x] Coach Head-to-Head Comparisons (search, stat bars, coaching journey)
- [x] Coaches Leaderboard (Top 100 All-Time Wins)
- [x] Overlaid season history chart in Full Program Comparison
- [x] Tournament Resume per team (color-coded grid)
- [x] Dynamic H2H metrics by decade
- [x] Browser back button support

### Tournament Experience
- [x] Live scores on game cards (in-progress, halftime, final, OT)
- [x] NCAA Tournament / NIT badges + filter tabs + conference dropdown
- [x] **Greatest Tournament Upsets page** — clickable seed pairing cards, 214 verified upsets with scores, era filters
- [x] **Relive the Moment game pages** — cinematic hero, YouTube highlights embedded, "Why This Mattered", "What Happened Next?"
- [x] **Live Historical Context Engine** — seed matchup badges on bracket + game cards, upset alerts
- [x] **Box scores** — full player stats for upset games + live tournament games + completed bracket games
- [x] **Live game tracker** — polls ESPN every 2 min, auto-updates team records + coach wins when games go Final
- [x] **Live record enrichment** — W-L updates from ESPN API on page load

### Polish & Infrastructure
- [x] **Real arena photo backgrounds** — 110 teams with CC-licensed Wikimedia Commons photos, photographer credit
- [x] **Mobile-responsive UI** — tables scroll, 44px tap targets, 390px iPhone SE breakpoint, premium card feel
- [x] **Skeleton loaders + error fallbacks** — shimmer loading states for every view
- [x] **Error isolation** — each homepage section wrapped in try/catch, one crash can't kill others
- [x] **Sitemap.xml** — 145+ URLs for Google indexing
- [x] **Dynamic OG Tags** via Cloudflare Pages Function
- [x] **NCAA data audit** — 297 corrections across 129 teams, vacated wins handled (Kansas -15, Louisville -123, Syracuse -101)
- [x] **QA sweep** — all 68 tournament teams verified loading correctly
- [x] SR slug alias map for H2H matching (UMBC, UTEP, VCU, etc.)
- [x] Contact page → contact@hoopsipedia.com
- [x] GitHub Releases v0.2.0 + v0.3.0 published

### Data
- [x] 207 teams in data.json, 163 teams with full game-by-game data (289K+ games)
- [x] 110 arena photos curated from Wikimedia Commons
- [x] 68 team history blurbs researched (team_history.json)
- [x] 214 verified upset games with scores (upset_history.json)
- [x] Ranking formula research complete (RANKING_RESEARCH.md)
- [x] Full data audit report (DATA_AUDIT.md)

## 🔥 Pre-Tip Priority (Wednesday Night)
- [ ] **Wire team history blurbs into profiles** — founding year, mascot origin, iconic moment, fun fact
- [ ] **Arena photo scroll behavior** — photos should scroll with page to reveal packed arena, not stay fixed at top
- [ ] **Championship game on bracket** — needs more significance, not just floating in the middle. Use NCAA Final Four logo + championship trophy image
- [ ] **Bracket sizing** — regions should fit on screen without horizontal scroll
- [ ] **Multi-conference filter** — let users select Big Ten AND Big 12 simultaneously on Rankings/Teams pages
- [ ] **Remove CUNY conference** — D3, not D1. Remove from Rankings and Teams pages but keep data across site (historically significant)
- [ ] **Remove empty bubble** next to "All" on team rankings page
- [ ] Final backup + confirm Cloudflare deploy is clean

## 🏀 Short-Term (During Tournament — First Weekend)
- [ ] **Conference Realignment Tracker** — timeline visualization of every D1 conference move, before/after metrics, "what if" comparisons
- [ ] **NET Rankings + Quad Wins** — current NET rankings, quad W/L breakdowns, historical NET (2018+)
- [ ] **Championship Run pages** — full tournament path for every champion with embedded highlights. Linked from "What Happened Next?" on upset pages. E.g., Virginia's 2019 redemption arc
- [ ] **Relive the Moment enrichment** — box scores for ALL upsets, expand video curation beyond 11 iconic games. Replace full-game YouTube clips with 2-5 min highlight reels
- [ ] **Pre-1985 historical upsets** — upsets by program strength differential (not seed), powered by HTSS when ready
- [ ] **Upset page filters** — same multi-conference filter logic from Rankings page
- [ ] **"Did You Know" hyperlinks** — link facts to team tournament journeys with game data
- [ ] Dual record view: on-court record vs NCAA official record (show vacated wins transparently)
- [ ] Cinderella tracker — real-time during tournament
- [ ] Auto-generated OG images for comparison pages

## 📊 Medium-Term (Post-First Weekend)
- [ ] **Players & Draft History** — Notable Players on team pages, All-Americans, NBA Draft history by program, "Draft Factory" rankings, player search
- [ ] **Clickable H2H game rows → full game detail** — box score, player stats, shooting splits for ANY game in ANY matchup (not just upsets). The ultimate deep dive.
- [ ] **Team origin stories & mascot history** — Wikipedia-style narrative content, hyperlinked across teams for rabbit-hole exploration
- [ ] Mid-major conference data expansion (~22 conferences, ~230 teams)
- [ ] Coach career timelines across schools (visual timeline)
- [ ] Coaching era analysis (program strength under each coach)
- [ ] Decade-by-decade program strength visualizations
- [ ] Rivalry pages (dedicated pages for historic rivalries with full context)
- [ ] Embeddable widgets for bloggers/podcasters
- [ ] Nightly data sync automation (records, scores, coaches)

## 🏆 Long-Term Vision

### The Hoopsipedia Ranking (TRADEMARK CANDIDATE)
**"Nobody connects the dots across 80+ years of basketball. That's our lane."**

#### Blue Blood Index (BBI)
- Proprietary composite ranking of all-time program strength
- 8 weighted pillars: Championship Capital (30%), Tournament Depth (20%), Win Consistency (15%), Poll Prestige (12%), Talent Production (10%), Conference Dominance (5%), Coaching Prestige (5%), Current Momentum (3%)
- Era multipliers to normalize across tournament field sizes
- Dynamic — updates as current season progresses
- Full research: RANKING_RESEARCH.md

#### Historical Team-Season Score (HTSS) & Time Machine
- Score every individual team-season in history using z-score era-normalization
- 5 components: Dominance (35%), SOS (20%), Tournament (20%), Peak Perception (15%), Conference (10%)
- **Cross-era matchup simulator**: "Who wins: 1992 Duke vs 2015 Kentucky?"
- **All-Time Best Teams stack ranking**: definitive top 100 team-seasons ever
- **Random Historical Matchup generator**: one-click with predicted score — homepage widget
- **Live upset context**: "This would be the 14th biggest upset of all time" — powered by HTSS, not just seeds

### Live Historical Context Engine (HTSS-Enriched)
- Move beyond seed-based stats to HTSS-powered context
- "According to Hoopsipedia, Siena beating Duke would be the 14th biggest tournament upset of all time, and the 5th biggest in the 3-point era"
- Era filters: 3-point line (1987), 64-team bracket (1985), NIL (2021), shot clock changes
- Pre-game context cards on every tournament matchup
- Track trends: "How have 12s fared vs 5s since the intro of NIL? Since the 3-point shot? Since the dunk?"

### Data Moats (Leverage 247Sports Subscription)
- Transfer Portal Impact Analysis — quantify portal winners/losers
- Recruiting → Results Pipeline — map recruiting classes to outcomes
- NIL impact on program performance
- Conference strength index over time

### Content & Engagement
- **Top 10 Moments per team** — curated YouTube clips for every program's greatest moments (not just tournament — regular season buzzer beaters, rivalry games, historic wins). Embedded on team profiles with context cards. The ultimate rabbit hole feature.
- **Championship Run pages** — full tournament path for every champion with embedded highlights, opponent links, box scores. Connected from "What Happened Next?" on upset pages.
- **"This Day in CBB History"** — daily auto-generated content for return visits
- **Tournament-specific SEO pages** — history of 12-5 upsets, best Cinderella runs, seed performance history
- **"What If" simulator** — what if X team was in Y conference?
- **Program trajectory analysis** — rising/falling programs over 5/10/20 years
