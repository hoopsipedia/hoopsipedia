# Hoopsipedia Repo Audit & Improvement Plan — June 2026

Auditor: Claude (Fable 5) · Date: 2026-06-11 · Scope: full repo, analysis only (no code modified)

---

## Executive Summary

**Overall health grade: C.** The product works, ships features fast, has rigorous data verification culture (DATA_AUDIT.md), and a clever serverless architecture — but it is carrying three loads that will break it: a 23,567-line single-file frontend that grew 23% in two months, ~67MB of JSON downloaded by every first-time visitor, and a data pipeline whose primary outputs are written non-atomically (one crash mid-write corrupts weeks of scraping). There is no CI; the only automated safety net is a single local pre-push hook.

**Top 3 risks:**
1. **Data-loss/corruption:** box-score scrapers write `sr_boxscores.json` (18.5MB, weeks of rate-limited scraping) with plain `json.dump()` — a crash mid-write truncates the file (`scrape_sr_boxscores.py:620`, `scrape_boxscores.py:421-430`, `scrape_modern_boxscores.py:237-241`).
2. **Cost abuse on the AI chat endpoint:** `/api/chat` has `Access-Control-Allow-Origin: *`, per-isolate in-memory rate limiting that resets constantly and is trivially bypassed, and no per-message size cap — anyone can burn the Anthropic API budget (`functions/api/chat.js:27-41, 1007, 1044-1050`).
3. **Frontend collapse-by-growth:** every page load fetches ~67MB of games JSON upfront (`index.html:6041-6048`) and the monolith (19,172 → 23,567 lines since April) has no module boundaries, making each new feature riskier than the last.

**Top 3 opportunities:** (1) lazy-load the games/box-score data — likely a 10×+ improvement in first-load experience for ~a day of work; (2) a minimal GitHub Actions CI running the validators that already exist (`validate_setup.py`, the pre-push checks) — cheap, immediate safety; (3) extract the chat function's data-access layer and the scrapers' shared parser into reusable modules, cutting the 60-70% duplication that triples maintenance cost.

---

## Phase 1 — Repo Map

**Purpose:** Hoopsipedia (hoopsipedia.com) — a college basketball history encyclopedia: 365+ D1 programs, 77 seasons of records, proprietary HTSS rankings and KenPom-style retro efficiency ratings, NCAA tournament history, and an "Ask Hoopsipedia" AI chat assistant. Solo-developer, live production site with ads (AdSense `index.html:8`), analytics, PWA support, and a trademark filing (`branding/`). Maturity: **production indie product**, ~3 months post-launch.

**Stack:**
- **Frontend:** one hand-written `index.html` (23,567 lines / 1.7MB: ~5,200 lines CSS, ~560 lines HTML, ~17,700 lines vanilla JS). Hash-based SPA router (`handleHashRoute()` at `index.html:7889`). No framework, no build step. PWA via `sw.js` + `manifest.json`.
- **Backend:** Cloudflare Pages Functions — `functions/api/chat.js` (Claude Haiku tool-use chat over SSE, 15 tools) and `functions/[[path]].js` (dynamic OG meta tags via HTMLRewriter).
- **Data pipeline:** ~19 Python scripts (scrape Sports-Reference + ESPN) and 13 shell orchestrators at repo root; 4 Node.js analytics engines (`htss_algorithm.js`, `htss_v2.js`, `efficiency_engine.js`, `time_machine.js`) producing ranking JSONs.
- **Storage:** everything is JSON committed to git (~150MB tracked; `.git` is 464MB). No database.
- **Deploy:** Cloudflare Pages (inferred — no wrangler.toml, no CI, no documented deploy procedure anywhere).

**Data flow:** scrapers → root JSONs (`games_1/2/3.json`, `seasons.json`, `sr_boxscores.json`, …) → Node engines → results JSONs (`htss_v2_results.json`, `efficiency_ratings.json`, …) → consumed twice: fetched by the browser SPA, and read server-side by the chat function's tools. `nightly_sync.py` (cron) updates current-season records in `data.json` and auto-pushes to git, which redeploys the site.

**Key directories/files:**
| Path | What it is |
|---|---|
| `index.html` | The entire frontend application |
| `functions/api/chat.js` | AI chat endpoint (Claude tool-use over 13 datasets) |
| `functions/[[path]].js` | OG-tag injection for social sharing |
| `*.py`, `*.sh` (root) | Scraper/compiler pipeline + orchestration |
| `htss_v2.js`, `efficiency_engine.js`, `time_machine.js` | Ranking/simulation engines (Node CLIs) |
| `*.json` (root) | All data, committed (3×22MB games files, 18.5MB box scores, etc.) |
| 14 root `*.md` files | Docs of mixed freshness, incl. a prior audit (`FULL_AUDIT_2026_04.md`) |

**Surprises:** (1) `README.md` is a GitHub *profile* template, not project docs — the repo is `hoopsipedia/hoopsipedia`, so the README doubles as the org profile and says nothing about the project. (2) A prior audit exists (April 2026); roughly 5 of its 18 findings were fixed, and its #1 critical (dual ID-mapping systems) is still half-done. (3) The repo root contains ~30 untracked scratch/log files from scraping runs. (4) A live Anthropic API key sits in `.dev.vars` — correctly gitignored and never committed (verified via `git log --all -S 'sk-ant'`), but per project memory it is due for rotation.

---

## Phase 2 — Audit Report

Legend: each finding marked **[fact]** (verified at cited location) or **[judgment]** (assessment). Severity: Critical / High / Medium / Low.

### Architecture & design

- **A1 · Critical · ~67MB of game data fetched on every first page load.** [fact] `index.html:6041-6048` fetches `games_1.json` (22.4MB) + `games_2.json` (22.5MB) + `games_3.json` (22.1MB) in `initializeApp()` and merges them into one in-memory object. The April audit flagged this as Critical; the "fix" split the file for Cloudflare's 25MB limit but kept upfront loading. Consequence: multi-minute first loads on mobile, ~70MB+ of RAM in the tab, heavy CDN egress — for data most visits never use. Additionally `sw.js:40-51` caches every JSON response, so the service worker writes the same ~67MB into browser Cache Storage.
- **A2 · High · 23,567-line monolithic index.html, growing ~9%/month.** [fact] 19,172 lines in April → 23,567 now; 80+ functions, 30+ global state variables (`index.html:6124-6143`), zero module boundaries. [judgment] Past the point where each feature risks the whole site — the pre-push hook exists precisely because one syntax error takes the site down.
- **A3 · High · Dual ID-mapping systems still unresolved.** [fact] `slug_mapping.json` workflow and `espn_to_sr.json` coexist; `compile_schedules.py`, `check_references.py`, `test_scraper.py`, `validate_setup.py` still reference the deprecated one. The April audit called this its #1 critical issue, and ID mismatches have already caused wrong data on the live site once. Consequence: future scrape runs can silently attach the wrong team's data again.
- **A4 · High · Chat function merges ~67MB of parsed JSON per cold path.** [fact] `functions/api/chat.js:93-98` — `getGames()` parses all three games files and `{...spread}`s them into a *new* object on every call (the merged object is never cached; only the three parts are). Parsed JS objects are typically 2-4× the JSON text size; Workers isolates have a 128MB memory ceiling. Consequence: `searchGames`/`getTeamTournamentRecord` tool calls risk isolate OOM kills and multi-second latencies. [judgment] This probably already fails intermittently in production.
- **A5 · Medium · Git as a database.** [fact] `.git` is 464MB; `data.json` committed 111 times, `games_1.json` 36 times; largest historical blobs are 23-31MB. Consequence: clones get slower forever (history can't shrink without rewrite), and `nightly_sync.py`'s commit-to-deploy pattern compounds it nightly.

### Code quality

- **Q1 · High · Three near-identical box-score scrapers (~65-70% overlap).** [fact] `scrape_sr_boxscores.py` (635 lines), `scrape_boxscores.py` (505), `scrape_modern_boxscores.py` (252) all parse the same Sports-Reference pages with overlapping year coverage; two write to the *same* output file. Any SR HTML change must be patched three times; the regex variant and BS4 variant can drift and disagree silently.
- **Q2 · Medium · htss v1 is live-dead code.** [fact] `htss_algorithm.js` (1,101 lines) is superseded by `htss_v2.js`; site and chat use only `htss_v2_results.json` (`time_machine.js:43`, `functions/api/chat.js:69`). v2 loads v1 results just for console comparison (`htss_v2.js:1195-1203`). ~40% duplicated logic between them (clone detection, era defs, tournament parsing).
- **Q3 · Medium · No error handling on JSON I/O in the Node engines.** [fact] 18+ bare `JSON.parse(fs.readFileSync(...))` calls across the 4 engines (`htss_algorithm.js:37-39`, `efficiency_engine.js:56-68`, `time_machine.js:42-46`); only `htss_v2.js:50` checks a file exists. A truncated input (see S-pipeline risk below) crashes with a stack trace and no guidance.
- **Q4 · Medium · Bare `except:` clauses masking I/O errors.** [fact] `scrape_metadata.py:96,106` — a corrupt `protected_records.json` is silently discarded, meaning manually-corrected W/L records could be overwritten on the next metadata scrape. Also `compile_coaches.py:49,156` (benign).
- **Q5 · Low · Frontend duplication and silent catches.** [fact] Search-dropdown rendering duplicated 3+ places; skeleton HTML repeated; `.catch(() => {})` swallows at `index.html:7373, 7517, 8273, 10821` (UI shows loading skeletons forever on failure). Longest function `renderProfile()` is 418 lines (`index.html:12872-13290`).
- **Q6 · Low · Magic numbers in ranking engines without rationale.** [fact] Boost exponent changed 1.3→1.2 between HTSS v1/v2 with no comment (`htss_algorithm.js:731-738` vs `htss_v2.js:1084-1087`); tier thresholds (`efficiency_engine.js:376-391`) and win-probability divisor 4.5 (`time_machine.js:392`) undocumented. RANKING_RESEARCH.md describes a "Blue Blood Index" that was never built and does not document HTSS at all.

### Security

- **S1 · High · Chat endpoint is an open wallet.** [fact] `functions/api/chat.js:1007` sets `Access-Control-Allow-Origin: *`; rate limiting (`:27-41`) is an in-memory per-isolate Map — resets on isolate recycle, doesn't coordinate across Cloudflare's many isolates/colos, and never evicts old IPs; request validation (`:1044-1050`) caps messages at 40 but not per-message byte size or role values. Consequence: any third-party page can hammer the endpoint from browsers worldwide; a single client can send 40×huge-content messages per request. This spends real Anthropic API money. (Model is Haiku and max_tokens 1500, which bounds per-request damage — hence High, not Critical.)
- **S2 · High (operational) · Live Anthropic API key on disk, rotation overdue.** [fact] `.dev.vars` contains a production-format key. It is gitignored and was never committed (verified: `git log --all -S 'sk-ant'` is empty). [judgment] Per project memory the key was due for rotation at production deploy; it should be rotated and the prod key should exist only in the Cloudflare dashboard.
- **S3 · Low · XSS: no exploitable vector found, three fragile patterns.** [fact] Chat output is properly escaped (`escapeHtml`/`formatChatText`, `index.html:23167-23182`) — the highest-risk surface (LLM output → DOM) is handled correctly. Fragile-but-currently-safe: error `e.message` interpolated into innerHTML (`index.html:6117`), weak color sanitization in an `onerror` handler (`index.html:8177`), quote-only escaping in an inline onclick built from ESPN API data (`index.html:9190`). All interpolate trusted/internal data today.
- **S4 · Low · No security headers / CSP.** [fact] No `_headers` file or CSP meta tag exists. [judgment] Low priority for a static site, but a CSP would convert all the S3 fragilities into non-issues.

### Testing

- **T1 · High · No automated test execution at all.** [fact] No CI config exists (no `.github/workflows`, no test runner config). `test_scraper.py` (real assertions: slug-mapping uniqueness, fetch smoke test, seasons.json structure) and `validate_setup.py` (dependency/file checks) exist but only run when someone remembers. The only enforced gate is the local pre-push hook (`.git/hooks/pre-push`) validating JS syntax in index.html and JSON parseability of 5 data files — good, but it lives only on this machine and isn't in the repo.
- **T2 · Medium · Zero tests on the ranking engines and chat tools.** [judgment] The HTSS/efficiency engines are the site's proprietary differentiator and have no regression tests (e.g., "1972 UCLA stays top-5"); a data or logic regression would ship silently. The 15 chat tool functions are similarly untested.

### Performance

- **P1 · Critical · = A1** (67MB upfront client download). Same finding, both an architecture and performance issue — counted once in totals.
- **P2 · High · 18.5MB `sr_boxscores.json` fetched whole for one box score.** [fact] `index.html:15684-15693` — first historical box-score view downloads the entire file; it grows with every scrape run (project plan targets 365K games — current format would put this file >100MB, which also breaks the 25MB Pages limit long before that).
- **P3 · Medium · = A4** (chat function re-merging games data per call).
- **P4 · Low · Live ticker polls ESPN every 10s indefinitely (`index.html:7337`); rankings table renders all 373 teams unpaginated.** [fact/judgment]

### Dependencies

- **D1 · Medium · No Python dependency manifest.** [fact] `requests` + `beautifulsoup4` imported everywhere; no `requirements.txt`/`pyproject.toml` anywhere. New machine = guess-and-install.
- **D2 · Low · `package-lock.json` is an empty stub (no `package.json`).** [fact] 90 bytes, `"packages": {}` — meaningless; the Node engines use only stdlib. Delete or add a real package.json.
- **D3 · Healthy otherwise.** Zero runtime npm/pip dependencies in production code is a genuine strength — there is nothing to CVE-audit in the deployed site.

### DevEx & operations

- **O1 · High · No CI/CD, no documented deploy story.** [fact] Deployment is inferred (push to main → Cloudflare Pages). Not written down anywhere; no staging environment; `nightly_sync.py` and `auto_push.sh` push straight to production. `auto_push.sh` runs an infinite loop with no `set -e` and ignores push failures (`auto_push.sh:5,38-42`).
- **O2 · Medium · Non-atomic JSON writes through the pipeline.** [fact] All three box-score scrapers write with plain `open(...,'w')` + `json.dump` (`scrape_sr_boxscores.py:619-621`, `scrape_boxscores.py:421-430`, `scrape_modern_boxscores.py:237-241`). Only `scrape_batch.py:412-440` validates post-write and keeps interim backups. A crash/disk-full mid-dump truncates the primary data file. **This is the single highest data-loss risk in the repo** given each file represents weeks of rate-limited scraping.
- **O3 · Medium · Hardcoded `/Users/joshdavis/...` paths in 3 scripts.** [fact] `fetch_game_ids.py:22`, `fetch_sr_records.py:14-15`, `map_espn_ids.py:17`. Breaks any other machine, CI, or future contributor.
- **O4 · Medium · Repo-root chaos.** [fact] ~30 untracked scratch/log files at root (8 `.log` files, `_scrape_*` interim artifacts); `sync_log.txt` is in `.gitignore:36` yet tracked *and* currently modified — gitignore doesn't apply to already-tracked files. `.gitignore` doesn't cover `*.log` or `_*` patterns.
- **O5 · Low · Pre-push hook not versioned.** [fact] The valuable hook lives only in `.git/hooks/` (not shareable/recoverable). Strengths noted: it exists, it checks the right things, and the owner has a hard rule against bypassing it.

### Documentation

- **DOC1 · High · README.md is a GitHub profile template.** [fact] `README.md:1-17` — zero project information in the front door of the repo.
- **DOC2 · Medium · 14 root markdown docs, ~half stale.** [fact] `QUICK_START.md:17,27,66` references dead session paths and a deleted script; `SCRAPER_SETUP.md`/`README_SCRAPER.md`/`SCRAPER_INDEX.md` document a superseded workflow; `QA_REPORT.md` is a 3-line "all fixed" claim with no evidence; `privacy.html:~192` and `terms.html:~192` still mention the removed SeatGeek integration ("Last updated: March 2026").
- **DOC3 · Medium · The prior audit (FULL_AUDIT_2026_04.md) is half-addressed with no tracking.** [fact] ~5 of 18 issues verifiably fixed (empty-space bug `8138ff5`, games split `5c503a8`, ESPN API hammering, OG tags); the rest unfixed or unverifiable, including its #1 critical. [judgment] Audits without follow-through tracking become shelf-ware — this report includes a task plan precisely to avoid that.
- **DOC4 · Medium · Hardcoded "2026" staleness, already biting.** [fact] `index.html:12102, 13304, 13742-13748, 12336` hardcode season 2026 / tournament dates / `currentYear = 2026`; `index.html:14497` computes droughts as `2026 - lastWinYear`. It is June 2026 — these go wrong the moment the 2026-27 season starts.

### Strengths (preserve these)

1. **Zero-dependency production surface** — no framework/npm supply chain to maintain or audit.
2. **The pre-push hook** validating JS syntax + JSON parseability is exactly the right cheap gate for this architecture (and the no-`--no-verify` discipline backs it).
3. **Scraper politeness is excellent** — 3.5-14s intervals, 429 detection with exponential backoff, consecutive-429 circuit breaker (`scrape_batch.py:98-104`). This protects the project's most precious resource: not being banned by Sports-Reference.
4. **`scrape_batch.py` is the model citizen** — pre-merge snapshots, post-merge validation, interim backups (`:412-440, 471-475`). The pattern just needs to spread.
5. **Chat security fundamentals that matter are right** — LLM output is escaped before DOM insertion; tool-use recursion is depth-capped; tool results truncated to 4KB.
6. **Data verification culture** — DATA_AUDIT.md's NCAA-record-book reconciliation (297 corrections) is more rigor than most commercial sports sites apply.
7. **Excellent commit messages** throughout.

---

## Phase 3 — Improvement Strategy

### Theme 1: Treat the data pipeline like it holds irreplaceable assets (because it does)
Findings: O2, Q4, A3, Q1. Each scraped file embodies weeks of politeness-rate-limited work that cannot be quickly re-fetched. **Target state:** every JSON write in the pipeline is atomic (temp file + rename); the deprecated `slug_mapping.json` path is deleted; one shared SR-parser module replaces three scrapers. **Principle:** the cost of a data file is its re-acquisition time, not its byte size.

### Theme 2: Stop shipping the database to the browser
Findings: A1/P1, P2, A4/P3, A5. **Target state:** the browser fetches per-team/per-game slices on demand (split `games_*.json` into per-team files, or move to Cloudflare KV/R2 + a tiny API); `sr_boxscores.json` is split per-era or per-game; the chat function indexes into per-part caches instead of merging 67MB. **Principle:** data size may grow 100× (the 365K-game plan); access patterns must be O(slice), not O(everything).

### Theme 3: Put a floor under the monolith before it grows further
Findings: A2, Q5, T1, O5. Not a rewrite — a containment strategy. **Target state:** CSS and JS extracted from index.html into a handful of plain `<script src>` files (no bundler needed); the pre-push hook's checks committed to the repo and run in GitHub Actions on every push; staleness constants (`currentYear`, tournament dates) centralized into one config block. **Principle:** make the cheapest possible structure that lets two features change without touching the same 23K-line file.

### Theme 4: Close the open wallet
Findings: S1, S2. **Target state:** chat endpoint locked to the site origin, rate-limited durably (Cloudflare KV or the free WAF rate-limiting rule), per-message size caps, key rotated. **Principle:** anything that spends money per-request must have abuse controls that survive an isolate restart.

### Theme 5: One source of truth for "how this project works"
Findings: DOC1-4, D1, O1, O4. **Target state:** a real README (what/stack/data-flow/deploy/runbook), stale docs moved to `docs/archive/`, `requirements.txt` added, logs and scratch files corralled by `.gitignore`. **Principle:** the repo should be re-learnable by its owner in 15 minutes after six months away.

### Explicitly NOT recommending
- **No framework/TypeScript rewrite, no bundler.** The vanilla approach is working and is a deliberate strength; a rewrite would freeze features for a month for marginal payoff at this team size.
- **No git history rewrite / LFS migration now.** 464MB hurts only clones; a rewrite breaks the remote and any open clones. Revisit only if collaboration starts. (Do stop the bleeding via Theme 2 — data out of git eventually — but don't rewrite history.)
- **No frontend unit-test suite.** Testing a 23K-line DOM monolith is poor ROI; the pre-push syntax gate + CI + a handful of engine regression tests buys more safety per hour.
- **No robots.txt/legal scraping rework.** Current politeness posture is reasonable.
- **No HTSS methodology audit** — out of scope; only its defensive coding and documentation are addressed.

### Definition of done (measurable)
- CI runs on every push: JS-syntax check of index.html, JSON validation of the 5 deploy-critical files, `validate_setup.py`, `test_scraper.py --offline` — and fails the build on error.
- First-load network transfer < 3MB (currently ~70MB) measured in devtools with cold cache.
- Zero non-atomic `json.dump` writes to tracked data files (grep-verifiable pattern).
- `/api/chat` rejects cross-origin browsers and >8KB messages; rate limit survives isolate recycling.
- `slug_mapping.json` deleted; all references resolve to `espn_to_sr.json`.
- README answers: what is this, how is it deployed, how do I run the pipeline.
- Zero Critical findings open; ≤2 High findings open.

---

## Phase 4 — Task Plan

### Quick wins (do immediately — all S effort, high impact)
| # | Task | Why |
|---|---|---|
| QW1 | **Rotate the Anthropic API key**; keep prod value only in Cloudflare dashboard | S2 — overdue per project plan |
| QW2 | Replace README.md with a real project README | DOC1 |
| QW3 | `git rm --cached sync_log.txt`; add `*.log`, `_scrape_*`, `logs/` to .gitignore; `mkdir logs` and point scripts there | O4 |
| QW4 | Add `requirements.txt` (`requests`, `beautifulsoup4`, pinned) | D1 |
| QW5 | Fix 3 hardcoded `/Users/joshdavis` paths → `Path(__file__).parent` | O3 |
| QW6 | Commit the pre-push hook into `scripts/hooks/` + a one-line installer | O5 |
| QW7 | Remove SeatGeek mentions + update dates in privacy.html / terms.html | DOC2 |
| QW8 | Delete the stub package-lock.json (or add a real package.json) | D2 |

### Milestone 0 — Safety net (before touching anything load-bearing)
| Task | Description | Files | Acceptance | Effort | Risk | Deps |
|---|---|---|---|---|---|---|
| M0.1 | **GitHub Actions CI**: port the pre-push hook checks (JS syntax via node `vm`, JSON validation) + `validate_setup.py` + `test_scraper.py` (offline tests only) into a workflow on push/PR | `.github/workflows/ci.yml`, `scripts/` | CI red on injected syntax error; green on main | M | Low | QW6 |
| M0.2 | **Atomic write utility** (`scripts/json_io.py`: temp file + fsync + `os.replace`) and adopt in all scrapers/compilers that write tracked JSON | all `scrape_*.py`, `compile_*.py`, `nightly_sync.py` | grep shows no direct `json.dump(open(...,'w'))` on tracked data; kill -9 mid-write leaves old file intact | M | Low | — |
| M0.3 | **Engine input guards**: wrap JSON loads in the 4 Node engines with existence checks + clear error messages | `htss_v2.js`, `efficiency_engine.js`, `time_machine.js`, (`htss_algorithm.js` if kept) | Running with a missing/truncated input prints a named error, exit 1, no stack trace | S | Low | — |
| M0.4 | **One-time data backup** of all tracked JSON to external storage (R2/B2/external disk) + a documented restore note | n/a | Backup exists off-machine; restore tested once | S | None | — |

### Milestone 1 — Critical fixes (security & correctness)
| Task | Description | Files | Acceptance | Effort | Risk | Deps |
|---|---|---|---|---|---|---|
| M1.1 | **Harden /api/chat**: lock CORS to `https://www.hoopsipedia.com` (+ apex), enforce per-message and total-body byte caps, validate roles, move rate limiting to Cloudflare KV (or a WAF rate rule) keyed by IP | `functions/api/chat.js` | Cross-origin browser call fails preflight; 100-request burst from one IP gets 429s across colos; 1MB message rejected 400 | M | Med (don't break SSE for legit users — test streaming after) | QW1 |
| M1.2 | **Fix chat `getGames()` memory bomb**: never merge the three parts; look up `espnId` in each cached part sequentially | `functions/api/chat.js:93-98, 462-616` | `searchGames` returns identical results; no `{...g1,...g2,...g3}` allocation | S | Low | — |
| M1.3 | **Finish the ID-mapping migration**: port the 4 remaining scripts to `espn_to_sr.json`, then delete `slug_mapping.json` + its generator references; re-run `check_references.py` | `compile_schedules.py`, `check_references.py`, `test_scraper.py`, `validate_setup.py` | `grep -r slug_mapping` returns nothing; CI green; spot-check 10 teams' data correctness | M | Med (data correctness — verify per feedback memory: verify before shipping) | M0.1 |
| M1.4 | **Verify/remove the 6 phantom teams** (ESPN IDs 2314, 2332, 2907, 2902, 2901, 2078) flagged in April audit | `data.json` | Each ID either confirmed legitimate (documented) or removed everywhere | S | Low | — |
| M1.5 | **Centralize season constants**: one `CURRENT_SEASON` config object replacing hardcoded 2026s and tournament dates | `index.html:12102,13304,13742-13748,12336,14497` | Single-point season rollover; grep finds no stray hardcoded season logic | M | Med (many call sites) | M0.1 |

### Milestone 2 — High-leverage improvements
| Task | Description | Files | Acceptance | Effort | Risk | Deps |
|---|---|---|---|---|---|---|
| M2.1 | **Lazy-load games data**: split `games_*.json` into per-team files (`/games/{espnId}.json`, ~365 files, avg ~180KB) generated by a build script; frontend fetches per team on demand with cache; chat function fetches per team too | new `scripts/split_games.py`, `index.html` games access sites, `functions/api/chat.js` | First-load transfer <3MB; team page fetches only its own file; chat `searchGames` latency improves | L | Med (touches many frontend call sites; ship behind the existing try/catch fallback) | M0.1, M1.2 |
| M2.2 | **Split sr_boxscores.json per game or per year** (`/boxscores/{year}/{gameKey}.json` or per-year files) — also removes the 25MB Pages-limit time bomb | `scrape_*boxscores*.py` writers, `index.html:15684+`, splitter script | Box-score view fetches <100KB; scrapers append to per-year files | M | Med | M0.2 |
| M2.3 | **Extract frontend into static modules**: split index.html into `styles.css` + ~6-10 `<script src>` files along existing page boundaries (router, profile, compare, bracket, chat, data-layer). No bundler; just files | `index.html` → `css/`, `js/` | index.html <2,000 lines; CI syntax-checks each JS file; site byte-identical in behavior | XL → break down per page module | Med-High (do after M0.1 CI exists; one module per PR) | M0.1 |
| M2.4 | **Consolidate the 3 box-score scrapers** into one with era strategies (BS4-based; keep the 404-fallback from modern variant) | the 3 scrapers → `scrape_boxscores.py` + `sr_parser.py` | Old scripts deleted; re-scrape of 3 known games (1985, 2005, 2024) produces identical JSON | L | Med (diff outputs before deleting) | M0.2 |
| M2.5 | **Archive HTSS v1**: confirm nothing reads `htss_results.json` (grep frontend + functions), then move `htss_algorithm.js` + results to `archive/` and drop the 6MB file from deploy | `htss_algorithm.js`, `htss_results.json`, `htss_v2.js:1195-1203` | No references remain; deploy size -6MB | S | Low | — |
| M2.6 | **Document the deploy + runbook** in README/docs: Pages setup, env vars, nightly cron, what auto_push.sh does, season-rollover checklist | `README.md`, `docs/` | A cold read suffices to redeploy from scratch | S | None | QW2 |

### Milestone 3 — Quality & polish
| Task | Description | Effort | Notes |
|---|---|---|---|
| M3.1 | Engine regression tests: snapshot top-25 HTSS + 5 known efficiency ratings; CI-diff on engine changes | M | Protects the proprietary differentiator (T2) |
| M3.2 | Replace bare `except:` with typed exceptions (`scrape_metadata.py:96,106`, `compile_coaches.py:49,156`) | S | Protects protected_records.json |
| M3.3 | Fix fragile XSS patterns: textContent for `e.message` (`index.html:6117`), whitelist color validation (`:8177`), encodeURIComponent hash params (`:9190`); add a basic CSP via `_headers` | S | Belt-and-suspenders |
| M3.4 | `set -e` + push-failure handling in `auto_push.sh`; add logging | S | O1 |
| M3.5 | Surface fetch failures in UI instead of silent `.catch(() => {})` (4 sites) + skeleton timeout | M | Q5 |
| M3.6 | Docs consolidation: archive stale scraper docs + QA_REPORT + REDDIT_DRAFT to `docs/archive/`; merge live content into README/docs | S | DOC2 |
| M3.7 | Document engine parameters (boost exponents, HCA=3.5, tier thresholds, damping) in RANKING_RESEARCH.md or inline | S | Q6 |
| M3.8 | Seed time_machine.js randomness (hash of matchup key) for reproducible outputs | S | Determinism |
| M3.9 | Live-ticker backoff (pause polling when tab hidden / no live games) | S | P4 |

### Top-3 implementation sketches

**M0.2 Atomic writes** — Create `json_io.py` with `save_json_atomic(path, obj)`: `tempfile.NamedTemporaryFile(dir=path.parent, delete=False)` → `json.dump` → `flush+fsync` → `os.replace(tmp, path)` (atomic on POSIX, same filesystem because same dir). Sweep call sites with `grep -n "json.dump" *.py`. Gotchas: keep each writer's existing `indent`/`separators` argument (the games files are intentionally compact — pretty-printing them would double their size past the 25MB limit); preserve the merge-validation behavior in `scrape_batch.py` rather than replacing it.

**M1.1 Chat hardening** — (1) Replace both `Access-Control-Allow-Origin: '*'` headers with an origin allowlist check on `request.headers.get('Origin')`, echoing the origin only if allowed (note: SSE via fetch needs CORS right — test the live widget after). (2) Validate: each message `role ∈ {user, assistant}`, `JSON.stringify(content).length ≤ 8192`, total body ≤ 64KB. (3) Rate limit: simplest durable option is a Cloudflare WAF rate-limiting rule on `/api/chat` (zero code); otherwise KV with `{count, resetAt}` per IP — KV is eventually-consistent, so treat it as best-effort and keep the in-memory check as a fast first layer. Gotcha: don't break the `OPTIONS` preflight handler when tightening origins.

**M2.1 Lazy games loading** — Build `scripts/split_games.py`: read the 3 parts, write `games/{espnId}.json` per team (same inner schema), plus a tiny `games/index.json` (team→game-count) for "does data exist" checks. Frontend: replace the upfront `Promise.all` (`index.html:6043-6048`) with `async function getTeamGames(espnId)` that fetches `games/${espnId}.json` once and memoizes; callers already handle missing data thanks to the existing try/catch + ESPN fallback. Chat function: same per-team fetch in `getGames(ctx, espnId)`. Gotchas: `sw.js` will now cache small per-team files (good) — bump `CACHE_NAME` to evict the old 22MB entries; keep the old files deployed for one release so stale cached frontends don't 404; H2H/tournament tools in chat.js that scan *one* team's games are fine, but check nothing iterates *all* teams' games (only `toolGetTeamTournamentRecord` and `searchGames` use it — both are per-team ✓).

---

## Open Questions for Josh

1. **Scale intent:** the box-score plan targets 365K games. At ~50KB/game that's ~18GB — far beyond "JSON files on Pages." Is the endgame R2/KV/D1, or a sampled subset? This decides how aggressive M2.1/M2.2 splitting should be.
2. **htss v1 (`htss_algorithm.js` + 6MB results):** safe to archive, or do you still compare v1/v2 rankings during offseason algorithm work (the #1 offseason project)?
3. **Chat abuse posture:** is the WAF rate-limit rule acceptable (Cloudflare-dashboard config, zero code), or do you want it all in-repo?
4. **`auto_push.sh` / `nightly_sync.py` straight-to-prod pushes:** comfortable keeping production deploys fully unattended, or should nightly sync open a PR / push to a branch with auto-deploy preview first?
5. **Phantom teams (M1.4):** do you have NCAA-record-book context on IDs 2314/2332/2907/2902/2901/2078, or should they be re-verified from scratch?
6. **Git size:** if a collaborator ever joins, a fresh-history repo or LFS migration is worth it — any plans that would justify doing it now while the repo has one clone?
