# Deploy & Operations Runbook

How hoopsipedia.com gets built, deployed, and kept healthy.

## Deployment model

- **Cloudflare Pages auto-deploys `main` on every push.** There is no build
  step — the repo contents are served as-is (static site + Pages Functions in
  `functions/`).
- A typical deploy is: commit on `main` → `git push` → Cloudflare Pages picks
  it up and publishes within a couple of minutes. There is nothing else to run.

## Environment variables

- `ANTHROPIC_API_KEY` — set in the Cloudflare Pages dashboard under
  **Production**, type **Secret**. Used by the Pages Functions that call the
  Anthropic API.
- **Changing an env var does NOT take effect until a redeploy.** After editing
  the variable, trigger a redeploy (push a commit, or use "Retry deployment" /
  "Create deployment" in the Pages dashboard).

## Limits

- **Cloudflare Pages enforces a 25 MB per-file limit.** Large data files must
  stay under it — this is why big JSON payloads are split (e.g.
  `games_1.json` / `games_2.json` / `games_3.json`) and why unused large
  artifacts live in `archive/` (which keeps them out of harm's way; verify
  anything >25 MB never lands in the deployed output).

## Quality gates

Two gates run the same checks, so the hook and CI cannot drift apart:

1. **Pre-push hook** (`.git/hooks/pre-push`) — validates `index.html` JS
   syntax via `scripts/validate_index_js.js` and checks that deploy-critical
   JSON files parse. **Never bypass with `--no-verify`** — if it fails, fix
   the code. A bad push crashes the live site.
2. **CI** (`.github/workflows/ci.yml`) — runs the same validation on GitHub.

## Scheduled jobs

- **`nightly_sync.py`** runs on a cron and pushes nightly data updates to
  `main` (which triggers a Pages deploy like any other push). If overnight
  data looks stale, check that this cron ran and that its push passed the
  pre-push hook.

## Season rollover checklist

At the start of each new season:

1. Update the **`SEASON_CONFIG` block in `index.html`** (single source of
   truth for the current season year/labels — added June 2026).
2. Confirm nightly sync is picking up the new season's games.
3. Spot-check live pages (homepage compare, bracket, coaches) against a known
   source before announcing anything.
4. Rotate the `ANTHROPIC_API_KEY` if it is due (see env var notes above —
   remember the redeploy).
