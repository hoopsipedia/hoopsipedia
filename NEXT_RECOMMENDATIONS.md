# What To Do Next — Recommendation for Josh (2026-06-12)

Written after the overhaul sessions completed. Everything below is **queued, not started** — per your instruction, no agents were launched after the final gate.

## Where things stand

All four pushes today are live and verified: the seasons.json impostor fix (17 deletions incl. the Texas A&M/Longhorns surprise), Wave 2b lazy loading (first load **81MB → 14.5MB**, chat worker memory ~67MB → KBs), the full narrative fact-check (354 findings across all 365 teams), and the players.json foundation. Every known systemic data-corruption class (substring matching in opp-ids, seasons ownership, fabricated box scores) is fixed or fenced with CI invariants.

## Recommended priority order

### 1. Narrative repair pass (highest value, needs your approval loop)
354 findings — **245 provably wrong**, several wholesale fabrications (New Hampshire's nonexistent NCAA bid, UCLA's wrong losing streak). These are live on team pages now. Recommended mechanics:
- An agent drafts a corrected sentence per finding using the already-collected sources (both FACTCHECK_FINDINGS files have suggested fixes ready).
- You approve in batches of ~25 via a simple checklist; a repair script applies only approved entries to team_history.json (atomic, backed up).
- Root cause: these narratives were clearly generated without source grounding. Any future narrative generation should require citations at write time.
Estimated: 2-3 approval sessions of 20 minutes each on your side.

### 2. Re-scrape the 17 deleted season histories — **Texas A&M first**
Texas A&M is a flagship program currently showing zero season history (better than the Longhorns' history it had, but still). The re-scrape table with each team's real D1 start year is in SEASONS_DUPLICATE_REPORT.md. This is `compile_history.py` work — politeness-bound (~14s/request), runs unattended overnight, no agents needed. **Audit espn_to_sr.json slugs for these 17 ids first** (the report flags this), then remove the dead `bad_ids` workaround in compile_coaches.py.

### 3. Wave 3: index.html modularization + the UI it unblocks
The 23.5K-line monolith is the last structural debt. Split into static CSS/JS modules (no bundler), one module per PR, CI gating each. Unblocks the queued UI work: On This Day homepage module (data is live already), the unified-rankings page (after you answer the 3 weight questions in RANKING_METHODOLOGY.md — your #1 offseason project is one tuning session away from a shippable page), XSS/CSP polish, error-state UI, and the mobile/a11y sweep.

### 4. Monolith retirement + second payload cut
games_1/2/3.json and sr_boxscores.json are still deployed as transition fallbacks. Next release: drop them from the deploy (keep locally for the pipeline, or convert scrapers to write slices directly — the pre-push freshness gate already prevents stale-slice deploys). Then split seasons.json (5.4MB) and h2h.json (3.5MB) the same way games went: first load drops from 14.5MB to ~5MB. Tighten the Lighthouse byte budget afterward.

### 5. Chat eval battery
~150 generated Q&A pairs with known answers, run against the tool layer. The Drake bug and the navigateUser answer-swallowing both sat invisible until manual curls; an eval battery catches that class automatically. Pairs well with any future tool additions.

### 6. Scheduled routines (one-time setup, runs forever)
Weekly Lighthouse is already scheduled. Worth adding: weekly `scripts/backup_data.sh` + off-machine copy, monthly sr_boxscores 25MB-limit check, and (once #5 exists) a weekly chat eval. Ask Claude to `/schedule` these.

## Open decisions only you can make
- **Michigan as 2026 champion** in data.json (NCY) — 10-second sanity check, flagged by a reviewer.
- **Ranking weights** — 3 questions in RANKING_METHODOLOGY.md; gates the unified-rankings page.
- **Fact-check review** — FACTCHECK_FINDINGS_2026-06-11.md (top 30) + FACTCHECK_FINDINGS_FULL_2026-06-12.md (the rest).
- **WAF rule** — python-urllib UAs now get 403s, so some bot protection is active; confirm the `/api/chat` rate-limit rule specifically exists (memory: project-waf-rate-limit).
- **Backups off-machine** — ~/Backups/hoopsipedia/ tarballs still live only on this laptop.

## What I'd explicitly NOT do next
- Don't bulk-apply narrative fixes without your batch approval — accuracy culture is the product.
- Don't delete the monoliths until one full release cycle has passed (stale cached frontends).
- Don't start the box-score scraping expansion until the narrative repair lands — same review bandwidth, higher current-error cost on narratives.
