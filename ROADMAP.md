# Hoopsipedia Roadmap

**Last updated:** 2026-03-18 late evening (tournament tips off tomorrow)

**Mission: "Nobody connects the dots across 80+ years of basketball. That's our lane."**

## ✅ SHIPPED (v0.1.0 → v0.4.0)

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
- [x] Greatest Tournament Upsets page — 339 verified upsets, era filters, clickable seed pairing cards
- [x] Relive the Moment game pages — cinematic hero, 199 YouTube highlights, box scores
- [x] Live Historical Context Engine — seed matchup badges on bracket + game cards
- [x] Live Upset Watch cards — prominent homepage alerts when upsets are brewing
- [x] "On This Day" tournament history ticker — real games from our database + iconic moments
- [x] Game Center — prominent box score at top of comparison for live/recent games, auto-refreshes
- [x] Box scores everywhere — 12,067 ESPN game IDs, 240 SR box scores, clickable H2H game rows
- [x] Live game tracker — polls ESPN, auto-updates records + coach wins when games go Final
- [x] 5 Championship Run pages (Virginia 2019, Villanova 2018, UConn 2023/2024, Florida 2025)
- [x] Championship year badges clickable → run pages or Sports Reference

### Team Profile Enrichment
- [x] NET Rankings table + NET rank badge on profiles
- [x] Quad Record section (Q1-Q4 W-L) with expandable game details
- [x] Program History — founding year, mascot origin, iconic moment, "Did You Know?"
- [x] NBA Draft History — 85 teams with lottery picks, #1 overall picks, full draft tables
- [x] Advanced Stats toggle — PPG, SRS, SOS, scoring margin, conference record
- [x] Player Roster & Stats — full roster with headshots, sortable by any stat
- [x] Player vs Player comparison — side-by-side stat bars, shareable links
- [x] Real arena photo backgrounds — 110 teams with CC-licensed photos
- [x] "Coming Soon" for shell teams instead of false data

### Polish & Infrastructure
- [x] Mobile-responsive UI — tables scroll, 44px tap targets, premium card feel
- [x] Skeleton loaders + error fallbacks for every view
- [x] Error isolation — each section wrapped in try/catch
- [x] Sitemap.xml — 145+ URLs for Google indexing
- [x] Dynamic OG Tags via Cloudflare Pages Function
- [x] NCAA data audit — 297 corrections, vacated wins handled
- [x] QA sweep — all 68 tournament teams verified
- [x] Staging branch for DR environment
- [x] No emojis (except live red dot + upset siren)

### Data
- [x] 363 teams in data.json across 32 conferences
- [x] 189+ teams with full game-by-game data (320K+ games)
- [x] 12,067 ESPN game IDs for instant box score lookup
- [x] 339 verified upset games with scores
- [x] 199 YouTube highlight clips for upsets
- [x] 240 Sports Reference box scores (1985-2025)
- [x] 85 teams with NBA Draft History
- [x] 68 team history blurbs
- [x] 110 arena photos
- [x] Ranking formula research complete (RANKING_RESEARCH.md)

---

## 🔥 STACK-RANKED PRIORITIES (Easiest Lift → Highest Value)

### Tier 1: Quick wins, massive impact (< 2 hours each)
1. **Starting 5 Comparison Tool** — BUILDING NOW. Side-by-side starting lineups with stats. Most-shared screenshot feature during tournament.
2. **Upset Color Takeover** — When a big upset happens, site accent colors temporarily shift to the winner's colors for 30 min. Viral screenshot moment.
3. **Multi-conference filter** — Let users select Big Ten AND Big 12 simultaneously. Simple filter logic change.
4. **Injury/availability alerts** — Surface key player status on comparison pages. ESPN has some injury data.
5. **Remove CUNY from Rankings/Teams** — D3, not D1. Quick filter.
6. **Fix bracket sizing** — Regions should fit on screen without horizontal scroll.

### Tier 2: Medium lift, high value (2-6 hours each)
7. **More Championship Run pages** — 17 runs for Duke/UK/UNC/Kansas/UCLA are building. Add defining moments with YouTube clips inline.
8. **Conference Realignment Tracker** — Timeline visualization of every conference move. High interest topic right now.
9. **"Best Teams of All Time" page** — Use our existing data to rank top team-seasons. Even without HTSS, we can use win%, SRS, tournament finish.
10. **Rivalry pages** — Dedicated pages for Duke-UNC, UK-Louisville, etc. with full historical context, embedded highlights of classic games.
11. **Top 10 Moments per team** — Curated YouTube clips for every program's greatest moments embedded on profiles.
12. **H2H highlights for craziest finishes** — Link buzzer beaters and OT games in H2H history.

### Tier 3: Big lift, transformative value (1-2 weeks)
13. **Blue Blood Index (BBI)** — Proprietary all-time program ranking. Formula is researched and ready (RANKING_RESEARCH.md).
14. **Historical Team-Season Score (HTSS)** — Score every team-season for cross-era comparison. Powers the Time Machine.
15. **Time Machine simulator** — "1992 Duke vs 2015 Kentucky: who wins?" with predicted score. THE signature feature.
16. **AI-powered natural language search** — "Show me the biggest upset ever" → routes to the right page.
17. **Random Historical Matchup generator** — Homepage widget with predicted score. Engagement flywheel.

### Tier 4: Long-term moat (ongoing)
18. **247Sports data integration** — Transfer portal, recruiting rankings, NIL impact analysis.
19. **Full player profiles** — College career stats, NBA career tracking, All-American history.
20. **Championship Run pages for EVERY champion** — Complete archive, not just 5.
21. **Pre-1985 historical upsets** — By program strength, not seed.
22. **Game detail pages for ALL games** — Not just upsets. Every game clickable with box score + highlights.
23. **Nightly data sync automation** — Records, scores, coaches, NET rankings auto-update.
24. **Embeddable widgets** — Let bloggers/podcasters embed our comparisons.
25. **"What If" conference simulator** — What if Duke was in the Big Ten?
26. **Program trajectory analysis** — Rising/falling programs over 5/10/20 years.

---

## 💡 Feature Ideas (Backlog)
- Team origin stories expanded to Wikipedia-level depth (cross-referenced with official school athletics pages)
- "This Day in CBB History" — daily auto-generated content (shipped basic version)
- Tournament-specific SEO pages — history of 12-5 upsets, best Cinderella runs
- Dual record view: on-court record vs NCAA official record (show vacated wins transparently)
- Auto-generated OG images for comparison pages
- Decade-by-decade program strength visualizations
- Coach career timelines across schools (visual timeline)
- Coaching era analysis (program strength under each coach)
