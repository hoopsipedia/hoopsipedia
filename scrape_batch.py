#!/usr/bin/env python3
"""
Batch game-by-game scraper with full validation.
Scrapes teams from Sports Reference, validates data integrity,
and safely merges into games_1/2/3.json without corrupting existing data.

Usage:
    python scrape_batch.py --count 10        # Scrape 10 teams by NET priority
    python scrape_batch.py --ids 202,300     # Scrape specific ESPN IDs
"""

import json
import time
import re
import argparse
import sys
import os
from pathlib import Path
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: requests and beautifulsoup4 required. Run: pip install requests beautifulsoup4")
    sys.exit(1)

DATA_DIR = Path(__file__).parent
MIN_REQUEST_INTERVAL = 14.0
BASE_URL = "https://www.sports-reference.com/cbb/schools"


def load_json(filename):
    path = DATA_DIR / filename
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def get_teams_to_scrape(count=10, specific_ids=None):
    """Get prioritized list of teams that need scraping."""
    scraped = set()
    for fn in ['games_1.json', 'games_2.json', 'games_3.json']:
        data = load_json(fn)
        scraped.update(data.keys())

    data = load_json('data.json')
    H = data.get('H', {})
    NET = data.get('NET', {})
    espn_to_sr = load_json('espn_to_sr.json')

    if specific_ids:
        teams = []
        for eid in specific_ids:
            eid = str(eid)
            if eid in espn_to_sr:
                teams.append((eid, espn_to_sr[eid], H.get(eid, ['Unknown'])[0]))
            else:
                print(f"  WARNING: No SR mapping for ESPN ID {eid}")
        return teams

    need = []
    for eid, val in H.items():
        if eid not in scraped and eid in espn_to_sr:
            rank = NET.get(eid, {}).get('rank', 999)
            need.append((eid, espn_to_sr[eid], val[0], rank))

    need.sort(key=lambda x: x[3])
    return [(eid, slug, name) for eid, slug, name, _ in need[:count]]


class SafeScraper:
    """Game-by-game scraper with validation."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15'
        })
        self.sr_to_espn = {v: k for k, v in load_json('espn_to_sr.json').items()}
        self.slug_aliases = load_json('slug_aliases.json')
        self.last_request_time = 0
        self._consecutive_429s = 0

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)
        self.last_request_time = time.time()

    def _fetch(self, url):
        self._rate_limit()
        for attempt in range(3):
            try:
                resp = self.session.get(url, timeout=15)
                if resp.status_code == 429:
                    wait = 30 * (attempt + 1)
                    print(f"      429 rate limited, waiting {wait}s...")
                    time.sleep(wait)
                    self.last_request_time = time.time()
                    self._consecutive_429s += 1
                    continue
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                self._consecutive_429s = 0
                return resp.text
            except requests.RequestException as e:
                if attempt < 2:
                    print(f"      Retry {attempt+1}: {e}")
                    time.sleep(5)
                else:
                    print(f"      Failed: {e}")
                    return None
        return None

    def _resolve_opp(self, opp_slug):
        """Resolve opponent slug to ESPN ID using all available mappings."""
        if not opp_slug:
            return None
        # Direct SR->ESPN mapping
        eid = self.sr_to_espn.get(opp_slug)
        if eid:
            return eid
        # Slug aliases
        eid = self.slug_aliases.get(opp_slug)
        if eid:
            return str(eid)
        return None

    def _parse_date(self, date_str):
        try:
            parts = date_str.split(', ', 1)
            if len(parts) > 1:
                date_str = parts[1]
            dt = datetime.strptime(date_str, '%b %d, %Y')
            return dt.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            return None

    def _get_seasons(self, slug):
        """Get available season years for a team."""
        url = f"{BASE_URL}/{slug}/men/"
        html = self._fetch(url)
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        years = set()
        for link in soup.find_all('a', href=True):
            match = re.search(r'/cbb/schools/[^/]+/men/(\d{4})', link['href'])
            if match:
                year = int(match.group(1))
                if 1950 <= year <= 2030:
                    years.add(year)
        return sorted(years)

    def scrape_season(self, slug, year):
        """Scrape one season's schedule."""
        url = f"{BASE_URL}/{slug}/men/{year}-schedule.html"
        html = self._fetch(url)
        if not html:
            return []

        try:
            soup = BeautifulSoup(html, 'html.parser')
            table = soup.find('table', {'id': 'schedule'})
            if not table:
                return []

            tbody = table.find('tbody')
            rows = tbody.find_all('tr') if tbody else table.find_all('tr')
            games = []

            for row in rows:
                if row.get('class') and any(c in ('thead', 'over_header') for c in row.get('class', [])):
                    continue

                date_cell = row.find(['td', 'th'], {'data-stat': 'date_game'})
                if not date_cell:
                    continue
                date = self._parse_date(date_cell.get_text(strip=True))
                if not date:
                    continue

                # Skip future games
                if date > datetime.now().strftime('%Y-%m-%d'):
                    continue

                opp_cell = row.find(['td', 'th'], {'data-stat': 'opp_name'})
                if not opp_cell:
                    continue
                opp_link = opp_cell.find('a')
                opp_slug = None
                if opp_link and opp_link.get('href'):
                    match = re.search(r'/cbb/schools/([^/]+)/', opp_link['href'])
                    if match:
                        opp_slug = match.group(1)
                opp_name = opp_cell.get_text(strip=True)

                loc_cell = row.find(['td', 'th'], {'data-stat': 'game_location'})
                loc_text = loc_cell.get_text(strip=True) if loc_cell else ''
                loc = 'A' if loc_text == '@' else ('N' if loc_text == 'N' else 'H')

                result_cell = row.find(['td', 'th'], {'data-stat': 'game_result'})
                result = result_cell.get_text(strip=True) if result_cell else ''
                if not result:
                    continue  # Skip games without results
                won = result.startswith('W')

                pts_cell = row.find(['td', 'th'], {'data-stat': 'pts'})
                opp_pts_cell = row.find(['td', 'th'], {'data-stat': 'opp_pts'})
                try:
                    pts = int(pts_cell.get_text(strip=True)) if pts_cell else 0
                except (ValueError, TypeError):
                    pts = 0
                try:
                    opp_pts = int(opp_pts_cell.get_text(strip=True)) if opp_pts_cell else 0
                except (ValueError, TypeError):
                    opp_pts = 0

                if pts == 0 and opp_pts == 0:
                    continue  # Skip games with no score

                ot_cell = row.find(['td', 'th'], {'data-stat': 'overtimes'})
                ot = ot_cell.get_text(strip=True) if ot_cell else ''

                game = {
                    'date': date,
                    'opp_slug': opp_slug or opp_name,
                    'loc': loc,
                    'w': won,
                    'pts': pts,
                    'opp_pts': opp_pts,
                }
                opp_id = self._resolve_opp(opp_slug)
                if opp_id:
                    game['opp'] = opp_id
                if ot:
                    game['ot'] = ot

                games.append(game)

            return games
        except Exception as e:
            print(f"      Parse error: {e}")
            return []

    def scrape_team(self, espn_id, slug, name):
        """Scrape all seasons for a team with validation."""
        print(f"\n  [{espn_id}] {name} (slug: {slug})")

        seasons = self._get_seasons(slug)
        if not seasons:
            print(f"    No seasons found!")
            return None

        print(f"    Found {len(seasons)} seasons ({seasons[0]}-{seasons[-1]})")

        all_games = []
        for i, year in enumerate(seasons):
            if self._consecutive_429s >= 3:
                print(f"    Persistent rate limiting. Taking 5-minute break...")
                time.sleep(300)
                self._consecutive_429s = 0

            games = self.scrape_season(slug, year)
            all_games.extend(games)

            if (i + 1) % 20 == 0:
                print(f"      {i+1}/{len(seasons)} seasons, {len(all_games)} games")

        if not all_games:
            print(f"    No games found!")
            return None

        # VALIDATION
        print(f"    Raw: {len(all_games)} games")
        all_games = self._validate(espn_id, all_games, name)
        return all_games

    def _validate(self, espn_id, games, name):
        """Validate scraped games data."""
        errors = []

        # 1. Remove duplicates (same date + same opponent)
        seen = set()
        deduped = []
        for g in games:
            key = (g['date'], g.get('opp_slug', ''), g['pts'], g['opp_pts'])
            if key not in seen:
                seen.add(key)
                deduped.append(g)
        if len(deduped) < len(games):
            print(f"    Removed {len(games) - len(deduped)} duplicate games")
        games = deduped

        # 2. Check W/L consistency with scores
        fixed = 0
        for g in games:
            if g['pts'] > g['opp_pts'] and not g['w']:
                g['w'] = True
                fixed += 1
            elif g['pts'] < g['opp_pts'] and g['w']:
                g['w'] = False
                fixed += 1
        if fixed:
            print(f"    Fixed {fixed} W/L inconsistencies")

        # 3. Check for unreasonable scores
        bad_scores = [g for g in games if g['pts'] > 200 or g['opp_pts'] > 200]
        if bad_scores:
            print(f"    WARNING: {len(bad_scores)} games with scores > 200")

        # 4. Check date ordering
        dates = [g['date'] for g in games]
        if dates != sorted(dates):
            games.sort(key=lambda g: g['date'])
            print(f"    Sorted games by date")

        # 5. Compute W-L totals for sanity check
        wins = sum(1 for g in games if g['w'])
        losses = sum(1 for g in games if not g['w'])
        print(f"    Validated: {len(games)} games, {wins}W-{losses}L")

        # 6. Check against NCAA record book (data.json H field)
        data = load_json('data.json')
        h = data.get('H', {}).get(espn_id)
        if h:
            h_wins, h_losses = h[4], h[5]
            h_total = h_wins + h_losses
            if h_total > 0:
                sr_total = wins + losses
                coverage_pct = sr_total / h_total * 100 if h_total > 0 else 0
                win_gap = h_wins - wins
                loss_gap = h_losses - losses
                print(f"    NCAA record book: {h_wins}W-{h_losses}L ({h_total} games)")
                print(f"    SR coverage: {coverage_pct:.0f}% of NCAA total ({sr_total}/{h_total} games)")
                if coverage_pct < 50:
                    print(f"    ⚠️  LOW COVERAGE: SR has less than 50% of NCAA games — likely missing early history")
                elif coverage_pct < 80:
                    print(f"    ⚠️  PARTIAL COVERAGE: SR missing {h_total - sr_total} games ({win_gap}W, {loss_gap}L)")
                elif wins > h_wins + 5:
                    print(f"    ⚠️  DATA CONFLICT: SR has MORE wins than NCAA record book — needs investigation")
                else:
                    print(f"    ✅ Coverage looks good (gap: {win_gap}W, {loss_gap}L — likely current season delta)")

        # 7. Check opponent resolution rate
        resolved = sum(1 for g in games if 'opp' in g)
        pct = resolved / len(games) * 100 if games else 0
        print(f"    Opponent resolution: {resolved}/{len(games)} ({pct:.0f}%)")

        return games


def find_smallest_games_file():
    """Find which games file has the fewest teams (for balancing)."""
    sizes = {}
    for fn in ['games_1.json', 'games_2.json', 'games_3.json']:
        data = load_json(fn)
        total_games = sum(
            len(v if isinstance(v, list) else v.get('games', []))
            for v in data.values()
        )
        sizes[fn] = (len(data), total_games)
        print(f"  {fn}: {len(data)} teams, {total_games} games")
    # Pick file with fewest total games
    return min(sizes, key=lambda k: sizes[k][1])


def merge_safely(new_teams):
    """Merge new team data into games files with full validation."""
    print(f"\n{'='*60}")
    print(f"MERGING {len(new_teams)} new teams")
    print(f"{'='*60}")

    # Pre-merge: snapshot existing data
    existing_totals = {}
    for fn in ['games_1.json', 'games_2.json', 'games_3.json']:
        data = load_json(fn)
        for eid, val in data.items():
            games = val if isinstance(val, list) else val.get('games', [])
            existing_totals[eid] = len(games)

    # Check no new team already exists
    for eid, games, name in new_teams:
        if eid in existing_totals:
            print(f"  SKIP: {name} ({eid}) already in games files with {existing_totals[eid]} games")
            continue

    # Load target file (smallest)
    target = find_smallest_games_file()
    print(f"\n  Target file: {target}")

    with open(DATA_DIR / target) as f:
        target_data = json.load(f)

    added = 0
    for eid, games, name in new_teams:
        if eid in existing_totals:
            continue
        target_data[eid] = games
        added += 1
        print(f"  Added {name} ({eid}): {len(games)} games")

    if added == 0:
        print("  Nothing to add!")
        return False

    # Post-merge validation: ensure existing teams unchanged
    for eid, expected_count in existing_totals.items():
        if eid in target_data:
            actual = target_data[eid]
            actual_games = actual if isinstance(actual, list) else actual.get('games', [])
            if len(actual_games) != expected_count:
                print(f"  CORRUPTION DETECTED: {eid} had {expected_count} games, now {len(actual_games)}!")
                print(f"  ABORTING MERGE!")
                return False

    # Write back
    with open(DATA_DIR / target, 'w') as f:
        json.dump(target_data, f, separators=(',', ':'))

    total_games = sum(
        len(v if isinstance(v, list) else v.get('games', []))
        for v in target_data.values()
    )
    file_size = (DATA_DIR / target).stat().st_size / (1024 * 1024)
    print(f"\n  Saved {target}: {len(target_data)} teams, {total_games} games ({file_size:.1f} MB)")

    # Validate JSON is still parseable
    try:
        with open(DATA_DIR / target) as f:
            json.load(f)
        print(f"  JSON validation: PASSED")
    except json.JSONDecodeError as e:
        print(f"  JSON CORRUPTION: {e}")
        return False

    return True


def main():
    parser = argparse.ArgumentParser(description='Batch scrape teams with validation')
    parser.add_argument('--count', type=int, default=10, help='Number of teams to scrape')
    parser.add_argument('--ids', type=str, help='Comma-separated ESPN IDs to scrape')
    args = parser.parse_args()

    specific = args.ids.split(',') if args.ids else None
    teams = get_teams_to_scrape(count=args.count, specific_ids=specific)

    if not teams:
        print("No teams to scrape!")
        return

    print(f"{'='*60}")
    print(f"BATCH SCRAPE: {len(teams)} teams")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    scraper = SafeScraper()
    results = []

    for i, (eid, slug, name) in enumerate(teams):
        print(f"\n[{i+1}/{len(teams)}] Scraping {name}...")
        games = scraper.scrape_team(eid, slug, name)
        if games:
            results.append((eid, games, name))
            # Save intermediate results in case of crash
            interim_path = DATA_DIR / f'_scrape_interim_{eid}.json'
            with open(interim_path, 'w') as f:
                json.dump(games, f, separators=(',', ':'))

    print(f"\n\nScraping complete. {len(results)}/{len(teams)} teams succeeded.")

    if results:
        success = merge_safely(results)
        if success:
            # Clean up interim files
            for eid, _, _ in results:
                interim = DATA_DIR / f'_scrape_interim_{eid}.json'
                if interim.exists():
                    interim.unlink()
            print(f"\nDONE! {len(results)} teams merged successfully.")
        else:
            print(f"\nMERGE FAILED! Interim files preserved for recovery.")

    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()
