#!/usr/bin/env python3
"""
Sports Reference Box Score Scraper for Hoopsipedia — single entry point.

Covers ALL year ranges (pre-2005 and modern). Shared fetching/parsing lives in
sr_parser.py (BeautifulSoup-based). Replaces the deprecated scrape_sr_boxscores.py
and scrape_modern_boxscores.py.

Scrapes box scores from sports-reference.com and outputs structured JSON
matching the sr_boxscores.json format. Can scrape:
  1. Individual box score pages by URL
  2. All tournament games for a given year (works for any year SR has brackets,
     including pre-2005 — this supersedes the old date-guessing approach)
  3. A pre-mapped URL list (boxscore_urls.json format, the old "modern" mode),
     with a 404 fallback that finds the game via the team's schedule page

Usage:
    python scrape_boxscores.py --year 1992                    # All 1992 tournament games
    python scrape_boxscores.py --years 1985-2001              # All pre-ESPN tournament years
    python scrape_boxscores.py --url URL                      # Single box score page
    python scrape_boxscores.py --urls-file boxscore_urls.json # Pre-mapped game URLs (old modern mode)
    python scrape_boxscores.py --output my_boxscores.json     # Custom output file
"""

import argparse
import sys
from datetime import datetime

# Force unbuffered output so logs appear in real-time
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: requests and beautifulsoup4 required. Run: pip install requests beautifulsoup4")
    sys.exit(1)

from sr_parser import (
    MIN_REQUEST_INTERVAL,
    SRFetcher,
    find_alt_boxscore_url,
    get_tournament_boxscore_urls,
    load_json,
    parse_boxscore_html,
    save_json,
    url_to_game_key,
)


def _strip_internal_keys(boxscore_data):
    """Remove parser-internal keys (sr_slug) so saved output keeps the
    established sr_boxscores.json shape."""
    if boxscore_data:
        for team in boxscore_data.get('teams', []):
            team.pop('sr_slug', None)
    return boxscore_data


class BoxScoreScraper:
    """Scrapes box scores from Sports Reference via the shared sr_parser library."""

    def __init__(self, delay=MIN_REQUEST_INTERVAL):
        self.fetcher = SRFetcher(delay=delay)
        self.errors = []

    @property
    def request_count(self):
        return self.fetcher.request_count

    def parse_boxscore_page(self, url):
        """Fetch and parse a single SR box score page into structured JSON."""
        html = self.fetcher.fetch_text(url)
        if not html:
            return None
        return parse_boxscore_html(html, url=url)

    def scrape_tournament_year(self, year, existing_keys=None, output_file=None):
        """Scrape all box scores for a tournament year. Returns dict of game_key → boxscore.
        If output_file is provided, saves incrementally after each successful scrape."""
        existing_keys = existing_keys or set()
        results = {}

        urls = get_tournament_boxscore_urls(self.fetcher, year)
        if not urls:
            print(f"  No URLs found for {year}")
            return results

        for i, url in enumerate(urls):
            print(f"  [{i+1}/{len(urls)}] {url}")

            # Parse the box score
            try:
                data = self.parse_boxscore_page(url)
            except Exception as e:
                print(f"    ERROR parsing: {e}")
                self.errors.append((url, str(e)))
                continue

            if not data:
                continue

            # Generate game key
            key = url_to_game_key(url, data)
            if not key:
                print(f"    Could not generate key for {url}")
                continue

            if key in existing_keys:
                print(f"    SKIP (already have): {key}")
                continue

            _strip_internal_keys(data)
            results[key] = data
            existing_keys.add(key)
            print(f"    OK: {key} ({data['teams'][0]['name']} {data['teams'][0]['score']} - {data['teams'][1]['name']} {data['teams'][1]['score']})")

            # Incremental save every 5 games
            if output_file and len(results) % 5 == 0:
                self._incremental_save(output_file, results)

        # Final save for any remaining
        if output_file and results:
            self._incremental_save(output_file, results)

        return results

    def _incremental_save(self, output_file, new_data):
        """Merge new data into output file and save (atomic via save_json)."""
        existing = load_json(output_file)
        merged = {**existing, **new_data}
        merged['_metadata'] = {
            'lastUpdated': datetime.now().isoformat(),
            'totalGames': len([k for k in merged if k != '_metadata']),
            'source': 'sports-reference.com'
        }
        save_json(output_file, merged)

    def scrape_single_url(self, url):
        """Scrape a single box score URL."""
        data = self.parse_boxscore_page(url)
        if data:
            key = url_to_game_key(url, data)
            _strip_internal_keys(data)
            return {key: data} if key else {}
        return {}

    def scrape_urls_file(self, urls_file, output_file, limit=0, start=0):
        """Scrape pre-mapped game URLs (boxscore_urls.json format) — the old
        scrape_modern_boxscores.py mode, now using the BeautifulSoup parser.

        Each game entry needs: key, year, matchup, score, boxscore_url,
        winner_slug, loser_slug, winner_full, loser_full, winner_seed, loser_seed.
        Falls back to schedule-page lookup if the box score URL 404s.
        Saves incrementally (atomic) after each successful scrape.
        """
        output = load_json(output_file)
        if output:
            print(f"Loaded {len(output)} existing entries")

        games = load_json(urls_file)
        if not games:
            print(f"ERROR: no games found in {urls_file}")
            return {}

        print(f"Total games to scrape: {len(games)}")

        scraped = 0
        new_data = {}

        for i, game in enumerate(games):
            if i < start:
                continue

            key = game["key"]
            if key in output:
                continue

            if limit and scraped >= limit:
                break

            url = game["boxscore_url"]
            print(f"\n[{i+1}/{len(games)}] {key}")
            print(f"  URL: {url}")

            html = self.fetcher.fetch_text(url)

            if not html:
                # Try alternate URL via schedule-page lookup (404 fallback)
                print(f"  404, trying schedule lookup...")
                alt_url = find_alt_boxscore_url(self.fetcher, game["loser_slug"], game["year"])
                if alt_url:
                    print(f"  Alt URL: {alt_url}")
                    html = self.fetcher.fetch_text(alt_url)
                    if html:
                        url = alt_url

            if not html:
                print(f"  FAILED")
                self.errors.append((key, 'fetch failed'))
                continue

            data = parse_boxscore_html(html, url=url)
            if not data or len(data.get('teams', [])) < 2:
                print(f"  FAILED: no box score tables")
                self.errors.append((key, 'parse failed'))
                continue

            # Attach seeds/names from the game record, matched by SR slug
            score_parts = game["score"].split("-")
            w_score, l_score = int(score_parts[0]), int(score_parts[1])
            ws, ls = game["winner_slug"], game["loser_slug"]

            teams_out = []
            for t in data['teams']:
                slug = t.get('sr_slug', '')
                if slug:
                    is_winner = (slug == ws or ws in slug or slug in ws)
                else:
                    # No slug parsed — fall back to score comparison
                    is_winner = t.get('score', 0) == w_score

                teams_out.append({
                    "name": game["winner_full"] if is_winner else game["loser_full"],
                    "seed": game["winner_seed"] if is_winner else game["loser_seed"],
                    "score": w_score if is_winner else l_score,
                    "players": t.get('players', []),
                    "totals": t.get('totals', {}),
                })

            output[key] = {
                "source": "sports-reference",
                "url": url,
                "year": game["year"],
                "matchup": game["matchup"],
                "teams": teams_out,
            }
            new_data[key] = output[key]

            scraped += 1
            nplayers = sum(len(t["players"]) for t in teams_out)
            print(f"  OK: {len(teams_out)} teams, {nplayers} players")

            # Save after each game (atomic)
            save_json(output_file, output)

        save_json(output_file, output)

        print(f"\n{'='*60}")
        print(f"Scraped: {scraped} new | Total: {len(output)}")
        return new_data


def main():
    parser = argparse.ArgumentParser(description='Scrape box scores from Sports Reference (all year ranges)')
    parser.add_argument('--year', type=int, help='Scrape all tournament games for a specific year')
    parser.add_argument('--years', type=str, help='Year range like 1985-2001')
    parser.add_argument('--url', type=str, help='Scrape a single box score URL')
    parser.add_argument('--urls-file', type=str, help='Pre-mapped game URL list (boxscore_urls.json format)')
    parser.add_argument('--output', type=str, default=None,
                        help='Output file (default: sr_boxscores.json; sr_boxscores_modern.json with --urls-file)')
    parser.add_argument('--delay', type=float, default=MIN_REQUEST_INTERVAL,
                        help=f'Seconds between requests (floor: {MIN_REQUEST_INTERVAL})')
    parser.add_argument('--limit', type=int, default=0, help='Max games to scrape (--urls-file mode)')
    parser.add_argument('--start', type=int, default=0, help='Start index (--urls-file mode)')
    parser.add_argument('--dry-run', action='store_true', help='Only list URLs, don\'t scrape')
    args = parser.parse_args()

    # Default output: keep the historical per-mode files
    if args.output is None:
        args.output = 'sr_boxscores_modern.json' if args.urls_file else 'sr_boxscores.json'

    scraper = BoxScoreScraper(delay=args.delay)
    new_data = {}

    if args.urls_file:
        print(f"Scraping pre-mapped URLs from: {args.urls_file}")
        new_data = scraper.scrape_urls_file(args.urls_file, args.output,
                                            limit=args.limit, start=args.start)
        # scrape_urls_file saves incrementally itself
        if scraper.errors:
            print(f"\n{len(scraper.errors)} errors:")
            for key, err in scraper.errors:
                print(f"  {key}: {err}")
        print(f"Total requests: {scraper.request_count}")
        return

    # Load existing data (tournament/single-URL modes)
    existing = load_json(args.output)
    existing_keys = set(k for k in existing.keys() if k != '_metadata')
    print(f"Existing box scores: {len(existing_keys)}")

    if args.url:
        print(f"Scraping single URL: {args.url}")
        new_data = scraper.scrape_single_url(args.url)

    elif args.year:
        print(f"Scraping tournament year: {args.year}")
        new_data = scraper.scrape_tournament_year(args.year, existing_keys, output_file=args.output)

    elif args.years:
        start, end = args.years.split('-')
        start, end = int(start), int(end)
        print(f"Scraping tournament years: {start}-{end}")
        for year in range(start, end + 1):
            print(f"\n{'='*60}")
            print(f"YEAR {year}")
            print(f"{'='*60}")
            year_data = scraper.scrape_tournament_year(year, existing_keys, output_file=args.output)
            new_data.update(year_data)
            existing_keys.update(year_data.keys())

    else:
        parser.print_help()
        return

    if new_data:
        # Merge with existing
        merged = {**existing, **new_data}
        merged['_metadata'] = {
            'lastUpdated': datetime.now().isoformat(),
            'totalGames': len([k for k in merged if k != '_metadata']),
            'source': 'sports-reference.com'
        }
        save_json(args.output, merged)
        print(f"\nDone! Added {len(new_data)} new box scores.")
    else:
        print("\nNo new box scores scraped.")

    if scraper.errors:
        print(f"\n{len(scraper.errors)} errors:")
        for url, err in scraper.errors:
            print(f"  {url}: {err}")

    print(f"Total requests: {scraper.request_count}")


if __name__ == '__main__':
    main()
