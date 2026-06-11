# Hoopsipedia

**[hoopsipedia.com](https://www.hoopsipedia.com)** — a college basketball history encyclopedia. 365+ Division I programs, 77 seasons of records (1949–2026), NCAA Tournament history, proprietary HTSS rankings, retroactive KenPom-style efficiency ratings, and an AI chat assistant ("Ask Hoopsipedia").

## Stack

- **Frontend:** a single hand-written `index.html` (vanilla JS, hash-routed SPA, no framework, no build step) plus static pages (`about.html`, `privacy.html`, `terms.html`, `contact.html`). PWA via `sw.js` + `manifest.json`.
- **Backend:** Cloudflare Pages Functions
  - `functions/api/chat.js` — AI chat endpoint (Claude tool-use over the site's datasets, SSE streaming)
  - `functions/[[path]].js` — dynamic Open Graph meta tags for social sharing
- **Data:** flat JSON files at repo root, served as static assets (no database)
- **Pipeline:** Python scrapers (Sports-Reference, ESPN) + Node.js analytics engines

## Architecture / data flow

```
Sports-Reference + ESPN APIs
        │  (Python scrapers: scrape_*.py, compile_*.py, fetch_*.py)
        ▼
root JSON files (games_1/2/3.json, seasons.json, sr_boxscores.json, data.json, h2h.json, …)
        │  (Node engines: htss_v2.js, efficiency_engine.js, time_machine.js)
        ▼
results JSON (htss_v2_results.json, efficiency_ratings.json, time_machine_results.json)
        │
        ├──► fetched by the browser SPA (index.html)
        └──► read server-side by the chat function's tools
```

`nightly_sync.py` (installed via `setup_cron.sh`) updates current-season records in `data.json` nightly and pushes to git, which triggers a redeploy.

## Deploy

Hosted on **Cloudflare Pages**, connected to this repo — push to `main` deploys automatically. There is no build step; the repo root is the deploy artifact.

- `ANTHROPIC_API_KEY` must be set as an environment variable in the Cloudflare Pages dashboard (production) and in `.dev.vars` (local, gitignored).
- Pages rejects files over **25MB** — the games data is split into `games_1/2/3.json` for this reason. Watch `sr_boxscores.json` (growing with scrape runs).
- Local preview: `npx wrangler pages dev .`

## Local setup

```bash
pip install -r requirements.txt   # Python scraper deps (requests, beautifulsoup4)
./scripts/install-hooks.sh        # install the pre-push validation hook (required)
python3 validate_setup.py         # sanity-check files + dependencies
python3 test_scraper.py           # scraper smoke tests
```

**The pre-push hook is mandatory.** It validates the JS in `index.html` and the deploy-critical JSON files. Never bypass it with `--no-verify` — a syntax error in `index.html` takes down the whole site.

## Data backup & restore

The JSON data files are the project's crown jewels — weeks of rate-limited scraping. Back them up before risky pipeline changes:

```bash
./scripts/backup_data.sh                                  # → ~/Backups/hoopsipedia/hoopsipedia-data-YYYY-MM-DD.tar.gz
tar -xzf ~/Backups/hoopsipedia/hoopsipedia-data-YYYY-MM-DD.tar.gz sr_boxscores.json   # restore one file
```

Copy the tarball off-machine (cloud drive / external disk) — a local backup doesn't survive a dead laptop. All pipeline writes go through `json_io.save_json_atomic()` so a crashed scrape can't truncate a data file, but backups cover everything else.

## Key files

| Path | Purpose |
|---|---|
| `index.html` | The entire frontend application |
| `functions/api/chat.js` | AI chat endpoint |
| `functions/[[path]].js` | OG-tag injection |
| `htss_v2.js` | HTSS ranking engine (v2 — the live one) |
| `efficiency_engine.js` | Adjusted efficiency ratings (1949–2026) |
| `time_machine.js` | Cross-era matchup simulator |
| `nightly_sync.py` | Nightly current-season record sync (cron) |
| `scrape_batch.py` | Game-by-game scraper (the model for safe JSON merging) |
| `espn_to_sr.json` | ESPN ID ↔ Sports-Reference slug mapping (canonical) |
| `scripts/hooks/pre-push` | Versioned copy of the pre-push validation hook |

## Documentation

- `docs/DEPLOY.md` — deploy & operations runbook
- `ROADMAP.md` — feature roadmap and status
- `VISION.md` — project mission
- `DATA_AUDIT.md` — data verification against the NCAA record book
- `REPO_AUDIT_2026_06.md` — full repo audit + improvement plan (June 2026)
- `RANKING_RESEARCH.md` — ranking methodology research
- Scraper docs (`README_SCRAPER.md`, `SCRAPER_SETUP.md`, `QUICK_START.md`, `SCRAPER_INDEX.md`) are partially stale — trust the code and `REPO_AUDIT_2026_06.md` over them.

## Data sources

Sports-Reference (historical baseline) → ESPN (real-time) → **NCAA official record book** (ultimate source of truth; vacated wins are not counted). See `DATA_AUDIT.md` for the reconciliation methodology.
