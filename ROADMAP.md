# Hoopsipedia Roadmap

**Last updated:** 2026-03-18 overnight (post-v0.3.0 session)

**Mission: "Nobody connects the dots across 80+ years of basketball. That's our lane."**

## ✅ SHIPPED (v0.1.0 → v0.3.0)
- [x] Team profiles with all-time stats, rankings, season-by-season records
- [x] Head-to-head comparisons (Winsipedia-style)
- [x] Live bracket integration — **true connected NCAA tournament bracket**
- [x] AP Top 25 rankings + conference filter
- [x] Global search with autocomplete + **fuzzy aliases** (Zags, UNC, Nova, etc.)
- [x] Shareable URLs (readable slugs + dynamic OG tags + share buttons)
- [x] Mobile-responsive UI
- [x] Coach Head-to-Head Comparisons (search, stat bars, coaching journey)
- [x] Coaches Leaderboard (Top 100 All-Time Wins)
- [x] Live scores on game cards (in-progress, halftime, final, OT)
- [x] NCAA Tournament / NIT badges + filter tabs + conference dropdown
- [x] Tournament Resume per team (color-coded grid)
- [x] Dynamic H2H metrics by decade
- [x] Overlaid season history chart in Full Program Comparison
- [x] **Greatest Tournament Upsets page** — clickable seed pairing cards, 214 verified upsets with scores, era filters
- [x] **Relive the Moment game pages** — cinematic hero, YouTube highlights embedded, "Why This Mattered", "What Happened Next?"
- [x] **Live Historical Context Engine** — seed matchup badges on bracket + game cards, upset alerts
- [x] **Live game tracker** — polls ESPN every 2 min, auto-updates team records + coach wins when games go Final
- [x] **Live record enrichment** — W-L updates from ESPN API on page load
- [x] **Skeleton loaders + error fallbacks** — shimmer loading states for every view
- [x] **Sitemap.xml** — 145 URLs for Google indexing
- [x] **Dynamic OG Tags** via Cloudflare Pages Function
- [x] SR slug alias map for H2H matching (UMBC, UTEP, VCU, etc.)
- [x] Fixed 22 teams with missing all-time records (were showing 0-0)
- [x] Browser back button support
- [x] Contact page → contact@hoopsipedia.com
- [x] GitHub Release v0.2.0 published

## 🔥 Pre-Thursday Priority
- [ ] **Team history & origin stories** — founding year, mascot origin, arena name, notable facts on every team profile. Cross-check with official school athletics pages (NOT just Wikipedia). Hyperlinked to other team pages for rabbit-hole exploration.
- [ ] **Team page backgrounds** — subtle, opaque background images (campus beauty shots or packed arenas) unique to each team. Must not distract from data — low opacity overlay. Feels homey to alums, interesting to casual fans.
- [ ] Mobile audit — test every page on 375px (iPhone SE) and 390px (iPhone 14)
- [ ] Fix John Thompson name collision (Jr vs III counted as same person — 935 ghost wins)
- [ ] Fix ESPN ID 245 mapping (Texas A&M in H but contains Texas data)

## 🏀 Short-Term (During Tournament — First Weekend)
- [ ] **Conference Realignment Tracker** — timeline visualization of every D1 conference move, before/after metrics, "what if" comparisons. Timely, shareable, nobody else does this well.
- [ ] **NET Rankings + Quad Wins** — current NET rankings, quad W/L breakdowns, historical NET (2018+), quad record on team pages. THE March destination feature.
- [ ] **Championship Run pages** — full tournament path for every champion. Linked from "What Happened Next?" on upset pages. E.g., Virginia's 2019 redemption arc after UMBC loss.
- [ ] **Relive the Moment enrichment** — box scores from Sports Reference for upset games, expand beyond 11 curated highlights to all upsets with available video
- [ ] Dual record view: on-court record vs NCAA official record (show vacated wins transparently)
- [ ] Auto-generated OG images for comparison pages
- [ ] Cinderella tracker — real-time during tournament

## 📊 Medium-Term (Post-Launch)
- [ ] **Players & Draft History** — Notable Players on team pages, All-Americans, NBA Draft history by program, "Draft Factory" rankings, player search. Table stakes.
- [ ] **Clickable H2H game rows → game detail** — box score, player stats, shooting splits for ANY game in ANY matchup (not just upsets)
- [ ] Mid-major conference data expansion (~22 conferences, ~230 teams) — **in progress, 159+ teams scraped**
- [ ] Coach career timelines across schools (visual timeline)
- [ ] Coaching era analysis (program strength under each coach)
- [ ] Decade-by-decade program strength visualizations
- [ ] Rivalry pages (dedicated pages for historic rivalries with full context)
- [ ] Embeddable widgets for bloggers/podcasters

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

### Live Historical Context Engine (Enriched)
- Move beyond seed-based stats to HTSS-powered context
- "According to Hoopsipedia, Siena beating Duke would be the 14th biggest tournament upset of all time, and the 5th biggest in the 3-point era"
- Era filters: 3-point line (1987), 64-team bracket (1985), NIL (2021), shot clock changes
- Pre-game context cards on every tournament matchup

### Data Moats (Leverage 247Sports Subscription)
- Transfer Portal Impact Analysis — quantify portal winners/losers
- Recruiting → Results Pipeline — map recruiting classes to outcomes
- NIL impact on program performance
- Conference strength index over time

### Content & Engagement
- **Team origin stories & mascot history** — Wikipedia-style narrative content, hyperlinked across teams
- **"This Day in CBB History"** — daily auto-generated content for return visits
- **Tournament-specific SEO pages** — history of 12-5 upsets, best Cinderella runs, seed performance history
- **"What If" simulator** — what if X team was in Y conference?
- **Program trajectory analysis** — rising/falling programs over 5/10/20 years
