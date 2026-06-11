#!/usr/bin/env python3
"""
Sports Reference Box Score Scraper for Hoopsipedia.

Scrapes box scores from sports-reference.com and outputs structured JSON
matching the sr_boxscores.json format. Can scrape:
  1. Individual box score pages by URL
  2. All tournament games for a given year
  3. All games from a tournament bracket page

Usage:
    python scrape_boxscores.py --year 1992                    # All 1992 tournament games
    python scrape_boxscores.py --years 1985-2001              # All pre-ESPN tournament years
    python scrape_boxscores.py --url URL                      # Single box score page
    python scrape_boxscores.py --championship 1992/duke       # All games for a championship run
    python scrape_boxscores.py --output my_boxscores.json     # Custom output file
"""

import json
import time
import re
import argparse
import sys
import os
from pathlib import Path
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

from json_io import save_json_atomic

DATA_DIR = Path(__file__).parent
MIN_REQUEST_INTERVAL = 4.0  # seconds between requests to SR
SR_BASE = "https://www.sports-reference.com/cbb"

# SR school abbreviations → full slug mapping (built dynamically)
SR_ABBREV_TO_SLUG = {}


def load_json(filename):
    path = DATA_DIR / filename
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def save_json(filename, data):
    path = DATA_DIR / filename
    save_json_atomic(path, data, indent=2, ensure_ascii=False)
    print(f"  Saved {len(data)} entries to {filename}")


class BoxScoreScraper:
    """Scrapes box scores from Sports Reference."""

    def __init__(self, delay=MIN_REQUEST_INTERVAL):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15'
        })
        self.delay = delay
        self.last_request_time = 0
        self.request_count = 0
        self.errors = []

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request_time = time.time()

    def _fetch(self, url, retries=5):
        """Fetch a URL with rate limiting and retries."""
        self._rate_limit()
        self.request_count += 1

        for attempt in range(retries):
            try:
                resp = self.session.get(url, timeout=30)
                if resp.status_code == 429:
                    # Use Retry-After header if available, otherwise escalate
                    retry_after = resp.headers.get('Retry-After')
                    if retry_after:
                        wait = int(retry_after) + 5  # Add 5s buffer
                        print(f"    429 rate limited, Retry-After: {retry_after}s, waiting {wait}s...")
                    else:
                        wait = 90 * (attempt + 1)
                        print(f"    429 rate limited, waiting {wait}s...")
                    time.sleep(wait)
                    # Reset delay timer after long wait
                    self.last_request_time = time.time()
                    continue
                if resp.status_code == 404:
                    print(f"    404 not found: {url}")
                    return None
                if resp.status_code != 200:
                    print(f"    HTTP {resp.status_code}: {url}")
                    if attempt < retries - 1:
                        time.sleep(15)
                    continue
                return resp
            except requests.exceptions.RequestException as e:
                print(f"    Request error (attempt {attempt+1}): {e}")
                if attempt < retries - 1:
                    time.sleep(15)
        return None

    def parse_boxscore_page(self, url):
        """Parse a single SR box score page into structured JSON."""
        resp = self._fetch(url)
        if not resp:
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Get teams and scores from scorebox
        scorebox = soup.find(class_='scorebox')
        if not scorebox:
            print(f"    No scorebox found on {url}")
            return None

        team_divs = scorebox.find_all('div', recursive=False)
        teams_data = []

        for div in team_divs[:2]:
            team_info = {}
            # Team name
            strong = div.find('strong')
            if strong:
                link = strong.find('a')
                team_info['name'] = link.text.strip() if link else strong.text.strip()
                if link and link.get('href'):
                    # Extract SR slug from href like /cbb/schools/connecticut/2024.html
                    href = link['href']
                    slug_match = re.search(r'/schools/([^/]+)/', href)
                    if slug_match:
                        team_info['sr_slug'] = slug_match.group(1)

            # Score
            score_div = div.find(class_='score')
            if score_div:
                try:
                    team_info['score'] = int(score_div.text.strip())
                except ValueError:
                    team_info['score'] = 0

            teams_data.append(team_info)

        if len(teams_data) < 2:
            print(f"    Could not find 2 teams on {url}")
            return None

        # Parse basic box score tables
        result = {"source": "sports-reference", "teams": []}

        for team_data in teams_data:
            sr_slug = team_data.get('sr_slug', '')
            team_entry = {
                "name": team_data.get('name', 'Unknown'),
                "score": team_data.get('score', 0),
                "players": [],
                "totals": {}
            }

            # Find the basic box score table for this team
            table_id = f'box-score-basic-{sr_slug}'
            table = soup.find('table', id=table_id)

            if not table:
                # Try finding by partial match
                for t in soup.find_all('table'):
                    tid = t.get('id', '')
                    if tid.startswith('box-score-basic-') and sr_slug in tid:
                        table = t
                        break

            if not table:
                # Last resort: match by team name in table
                print(f"    Warning: No table found for {sr_slug}, trying fallback...")
                result['teams'].append(team_entry)
                continue

            # Parse header to get column indices
            thead = table.find('thead')
            if not thead:
                result['teams'].append(team_entry)
                continue

            header_rows = thead.find_all('tr')
            # Use the last header row (has actual stat names)
            stat_headers = [th.text.strip() for th in header_rows[-1].find_all('th')]

            # Parse player rows
            tbody = table.find('tbody')
            if tbody:
                for row in tbody.find_all('tr'):
                    # Skip separator rows
                    if 'class' in row.attrs and 'thead' in ' '.join(row.get('class', [])):
                        continue

                    cells = row.find_all(['th', 'td'])
                    if len(cells) < 5:
                        continue

                    player_name = cells[0].text.strip()

                    # Skip "Team Totals" row — handle separately
                    if 'Totals' in player_name or 'Team' in player_name:
                        continue

                    # Skip "Reserves" header
                    if player_name in ('Reserves', 'Starters', ''):
                        continue

                    player = {"name": player_name}

                    # Map columns to stats
                    for i, cell in enumerate(cells[1:], 1):
                        if i < len(stat_headers):
                            header = stat_headers[i]
                            val = cell.text.strip()

                            if header == 'MP':
                                try:
                                    player['min'] = int(val) if val else 0
                                except ValueError:
                                    # Handle MM:SS format
                                    if ':' in val:
                                        parts = val.split(':')
                                        player['min'] = int(parts[0])
                                    else:
                                        player['min'] = 0
                            elif header == 'PTS':
                                player['pts'] = int(val) if val and val != '' else 0
                            elif header == 'FG':
                                fg = val
                                # Get FGA from next column
                                fga_idx = i + 1
                                if fga_idx - 1 < len(cells) - 1:
                                    fga = cells[fga_idx].text.strip()
                                    player['fg'] = f"{fg}-{fga}" if fg and fga else "0-0"
                            elif header == '3P':
                                tp = val
                                tpa_idx = i + 1
                                if tpa_idx - 1 < len(cells) - 1:
                                    tpa = cells[tpa_idx].text.strip()
                                    player['tp'] = f"{tp}-{tpa}" if tp and tpa else "0-0"
                            elif header == 'FT':
                                ft = val
                                fta_idx = i + 1
                                if fta_idx - 1 < len(cells) - 1:
                                    fta = cells[fta_idx].text.strip()
                                    player['ft'] = f"{ft}-{fta}" if ft and fta else "0-0"
                            elif header == 'TRB':
                                player['reb'] = int(val) if val and val != '' else 0
                            elif header == 'AST':
                                player['ast'] = int(val) if val and val != '' else 0
                            elif header == 'STL':
                                player['stl'] = int(val) if val and val != '' else 0
                            elif header == 'BLK':
                                player['blk'] = int(val) if val and val != '' else 0
                            elif header == 'TOV':
                                player['to'] = int(val) if val and val != '' else 0

                    team_entry['players'].append(player)

            # Parse totals from tfoot
            tfoot = table.find('tfoot')
            if tfoot:
                totals_row = tfoot.find('tr')
                if totals_row:
                    cells = totals_row.find_all(['th', 'td'])
                    totals = {}
                    for i, cell in enumerate(cells[1:], 1):
                        if i < len(stat_headers):
                            header = stat_headers[i]
                            val = cell.text.strip()
                            if header == 'FG':
                                fga_idx = i + 1
                                if fga_idx - 1 < len(cells) - 1:
                                    fga = cells[fga_idx].text.strip()
                                    totals['fg'] = f"{val}-{fga}"
                            elif header == '3P':
                                tpa_idx = i + 1
                                if tpa_idx - 1 < len(cells) - 1:
                                    tpa = cells[tpa_idx].text.strip()
                                    totals['tp'] = f"{val}-{tpa}"
                            elif header == 'FT':
                                fta_idx = i + 1
                                if fta_idx - 1 < len(cells) - 1:
                                    fta = cells[fta_idx].text.strip()
                                    totals['ft'] = f"{val}-{fta}"
                            elif header == 'TRB':
                                totals['reb'] = int(val) if val else 0
                            elif header == 'AST':
                                totals['ast'] = int(val) if val else 0

                    team_entry['totals'] = totals

            result['teams'].append(team_entry)

        return result

    def get_tournament_boxscore_urls(self, year):
        """Get all box score URLs from a tournament bracket page."""
        url = f"{SR_BASE}/postseason/men/{year}-ncaa.html"
        print(f"  Fetching tournament bracket: {url}")
        resp = self._fetch(url)
        if not resp:
            # Try alternate URL format
            url = f"{SR_BASE}/postseason/{year}-ncaa.html"
            print(f"  Trying alternate: {url}")
            resp = self._fetch(url)
            if not resp:
                return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        links = soup.find_all('a', href=True)

        boxscore_urls = set()
        for link in links:
            href = link['href']
            if '/boxscores/' in href and href.endswith('.html') and href != '/cbb/boxscores/':
                full_url = f"https://www.sports-reference.com{href}" if href.startswith('/') else href
                boxscore_urls.add(full_url)

        urls = sorted(boxscore_urls)
        print(f"  Found {len(urls)} box score URLs for {year}")
        return urls

    def url_to_game_key(self, url, boxscore_data):
        """Convert a box score URL + data to a game key like 2024/winner-slug-vs-loser-slug."""
        if not boxscore_data or not boxscore_data.get('teams') or len(boxscore_data['teams']) < 2:
            return None

        # Extract year from URL
        match = re.search(r'/boxscores/(\d{4})-', url)
        if not match:
            return None
        year = match.group(1)

        t1 = boxscore_data['teams'][0]
        t2 = boxscore_data['teams'][1]

        # Determine winner/loser
        if t1['score'] >= t2['score']:
            winner, loser = t1, t2
        else:
            winner, loser = t2, t1

        def name_to_slug(name):
            slug = name.lower()
            slug = re.sub(r'[^a-z0-9\s-]', '', slug)
            slug = re.sub(r'\s+', '-', slug.strip())
            return slug

        winner_slug = name_to_slug(winner['name'])
        loser_slug = name_to_slug(loser['name'])

        return f"{year}/{winner_slug}-vs-{loser_slug}"

    def scrape_tournament_year(self, year, existing_keys=None, output_file=None):
        """Scrape all box scores for a tournament year. Returns dict of game_key → boxscore.
        If output_file is provided, saves incrementally after each successful scrape."""
        existing_keys = existing_keys or set()
        results = {}

        urls = self.get_tournament_boxscore_urls(year)
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
            key = self.url_to_game_key(url, data)
            if not key:
                print(f"    Could not generate key for {url}")
                continue

            if key in existing_keys:
                print(f"    SKIP (already have): {key}")
                continue

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
        """Merge new data into output file and save."""
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
            key = self.url_to_game_key(url, data)
            return {key: data} if key else {}
        return {}


def main():
    parser = argparse.ArgumentParser(description='Scrape box scores from Sports Reference')
    parser.add_argument('--year', type=int, help='Scrape all tournament games for a specific year')
    parser.add_argument('--years', type=str, help='Year range like 1985-2001')
    parser.add_argument('--url', type=str, help='Scrape a single box score URL')
    parser.add_argument('--output', type=str, default='sr_boxscores.json', help='Output file')
    parser.add_argument('--delay', type=float, default=MIN_REQUEST_INTERVAL, help='Seconds between requests')
    parser.add_argument('--dry-run', action='store_true', help='Only list URLs, don\'t scrape')
    args = parser.parse_args()

    # Load existing data
    existing = load_json(args.output)
    existing_keys = set(k for k in existing.keys() if k != '_metadata')
    print(f"Existing box scores: {len(existing_keys)}")

    scraper = BoxScoreScraper(delay=args.delay)
    new_data = {}

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
