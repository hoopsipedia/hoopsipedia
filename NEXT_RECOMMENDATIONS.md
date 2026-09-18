# What To Do Next — Recommendation for Josh (2026-09-11)

Supersedes the 2026-07-28 version. That document was written for a site that,
it turned out, nobody could see: **production had been frozen on the July 24
build for seven weeks** because `sr_boxscores.json` crossed Cloudflare
Pages' 25 MiB per-file limit and every deploy since failed silently while CI
stayed green. Fixed 2026-09-11 (`63c69df`): the store ships only as
`sr_boxscores.json.gz`, the hook and CI enforce it, and CI now fails on any
tracked file over 25 MiB. **Rule: after every push, confirm the live
`app.js?v=` hash matches `index.html`.**

## Where things stand (all live, verified on production)

| Area | State |
|---|---|
| Data | 365 programs, 284,905 unique games, 46% with a box score (92% for 2010+, 1–4% pre-2000), 53,916 players, 107 → 2 missing team-seasons, 157 NCAA-vacated seasons shown with an asterisk and excluded from rankings |
| Performance | HTML shell 1.8 MB → 52 KB; CLS 0 everywhere; home 0.78–0.80, rankings 0.80, team page 0.82 (Lighthouse mobile, real throttling). Analytics/AdSense tags load after first paint. |
| SEO surface | Forever URLs with server-rendered content for `/rankings`, `/time-machine` (+ any matchup), `/players`, `/rivalries` (+ each), `/coaches`, `/teams`, `/champions`, `/bracket`, `/upsets`, `/classics`; every season page has a computed story + prev/next links; titles say "Basketball" (season pages had been ranking for football queries) |
| Search Console | 15.9K pages indexed; last 28 days 100 clicks / 15.8K impressions (+450%); sitemap resubmitted 2026-09-11 |
| Analytics | Site was tagged with a measurement ID nobody could read; retagged to the owned property (528509623, hoopsipedia@gmail.com) 2026-09-11 — first human numbers arrive 09-12 |
| Tooling | `scripts/google_reports.py` (GA4 + GSC, service account, launchd Mon 08:00), `scripts/daily_content.py` (4 post drafts/day, launchd 07:00 → `content/drafts/latest.md`), `scripts/indexnow_ping.py` (Bing et al., 584 URLs submitted), `scripts/render_share_cards.py` (1200×630 og:image cards for every team, section, featured matchup and rivalry) |
| Traffic reality | Cloudflare "uniques" (3K–11K/day) are ~90% bots (Amazonbot, Perplexity, SEO crawlers). Humans are still on the order of 100–200/day. `/api/chat` sees 0–2 human requests a day. |

## The season calendar is the plan

Tipoff ≈ **Nov 3, 2026**. Selection Sunday **Mar 14, 2027**. Phase 1
(technical foundation) is done. Phase 2 (content engine before tipoff) is
next; Phase 3 (ride the season, peak in March) follows.

## Decisions only you can make — these gate Phase 2

1. **Ranking weights.** The three questions in `RANKING_METHODOLOGY.md`. The
   unified "Hoopsipedia Ranking" page is one tuning session away and is the
   brand asset the whole marketing motion hangs on.
2. **Social accounts + newsletter tool.** X, Bluesky, Threads, the college
   basketball subreddit, and Buttondown/Beehiiv. Drafts are already being
   generated daily; nothing can be posted without accounts.
3. **AdSense status.** Confirm in the hoopsipedia@gmail.com account. If
   approved, ad units go on team and season pages only.
4. **Michigan as 2026 champion** in `data.json` — still the 10-second check.

## Recommended order for the next working sessions

1. **Ranking page** (after #1 above): ship `unified_rankings.json` as a named
   ranking with its own forever URL, SSR, share card, and a "how it works"
   section. Preseason all-time program rankings are the launch moment.
2. **Time Machine share flow**: the matchup pages exist with forever URLs and
   cards; add a share button that copies the URL, and a "matchup of the day"
   module on the homepage fed by `daily_content.py`'s pick.
3. **Post automation** once accounts exist: turn `daily_content.py` drafts
   into scheduled posts (Buffer/Typefully API or direct X API), with Josh
   approving the day's set from `content/drafts/latest.md`.
4. **Data-driven news hooks for the season**: when a top-25 team loses,
   generate "worst loss since…" from the database within the hour. The
   ingredients (game logs, HTSS, efficiency) all exist; needs the live
   scoreboard hook in `nightly_sync.py` and a template.
5. **Box-score archaeology** continues as idle-machine work, not the main
   thrust: remaining custompages/PDF layers per `SCRAPE_STATUS.md`; the
   `newspapers.com` phase when the free tier is exhausted.

## Housekeeping worth doing when convenient

- `games_1/2/3.json` are 22 MB each against the 25 MiB limit; plan a 4th shard
  (or stop deploying the monoliths) before the next big fill.
- Best-practices score 0.79 is third-party cookies (AdSense/doubleclick and a
  Wikimedia arena photo) — self-host the arena photos if it matters.
- The August cloud session's branch is merged; `.git` is 1.7 GB — a history
  rewrite to drop old `sr_boxscores.json` blobs would shrink clones 10×.
- GA history before 2026-09-11 is unrecoverable; treat that date as day one.

## What I would explicitly NOT do next

- Don't chase Cloudflare "uniques" — they are bots. Google Analytics and
  Search Console are the only traffic numbers that mean anything now.
- Don't start another multi-week harvesting campaign before the ranking page
  and the distribution channels exist. The site is data-rich and
  distribution-poor; that is the constraint.
