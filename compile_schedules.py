#!/usr/bin/env python3
"""
Game-Level Schedule Scraper
Fetches game-by-game results from Sports Reference for specified teams
and compiles into games.json for the Hoopsipedia web app.

Each team's season schedule page has individual game results with:
date, opponent, location (home/away/neutral), result (W/L), score, opponent score.

Output format (keyed by ESPN ID):
{
    "150": {  // Duke
        "games": [
            {"date": "2024-11-04", "opp": "153", "loc": "H", "w": true, "pts": 78, "opp_pts": 65},
            ...
        ]
    }
}

Usage:
    python compile_schedules.py                    # All teams
    python compile_schedules.py --conf ACC         # Just ACC teams
    python compile_schedules.py --slugs duke,nc-state  # Specific teams
"""

import json
import time
import re
import argparse
from pathlib import Path
from typing import Optional, Dict, List, Any
import requests
from bs4 import BeautifulSoup
from datetime import datetime


class ScheduleCompiler:
    """Compiler for game-by-game schedule data from Sports Reference."""

    BASE_URL = "https://www.sports-reference.com/cbb/schools"
    MIN_REQUEST_INTERVAL = 14.0
    DATA_DIR = Path(__file__).parent

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15'
        })
        self.slug_mapping = self._load_json('slug_mapping.json')
        self.espn_to_sr = self._load_json('espn_to_sr.json')
        self.sr_to_espn = {v: k for k, v in self.espn_to_sr.items()}
        self.games_data = self._load_json('games.json') or {}
        self.last_request_time = 0
        self.teams_processed = 0
        self.teams_failed = 0

    def _load_json(self, filename):
        path = self.DATA_DIR / filename
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return {}

    def _save_progress(self):
        path = self.DATA_DIR / 'games.json'
        with open(path, 'w') as f:
            json.dump(self.games_data, f, separators=(',', ':'))
        total_games = sum(len(v.get('games', [])) for v in self.games_data.values())
        size_kb = path.stat().st_size / 1024
        print(f"  >> Saved: {len(self.games_data)} teams, {total_games} games ({size_kb:.0f} KB)")

    def _rate_limit_sleep(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)
        self.last_request_time = time.time()

    def _fetch_page(self, url: str) -> Optional[str]:
        self._rate_limit_sleep()
        for attempt in range(3):
            try:
                response = self.session.get(url, timeout=15)
                if response.status_code == 429:
                    wait = 30 * (attempt + 1)
                    print(f"    429 Rate Limited. Waiting {wait}s (attempt {attempt+1}/3)...")
                    time.sleep(wait)
                    self.last_request_time = time.time()
                    continue
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                self._consecutive_429s = 0  # Reset on success
                return response.text
            except requests.RequestException as e:
                if attempt < 2:
                    print(f"    Retry {attempt+1}: {e}")
                    time.sleep(5)
                else:
                    print(f"    Error: {e}")
                    return None
        # All 5 attempts were 429s
        self._consecutive_429s = getattr(self, '_consecutive_429s', 0) + 1
        return None

    def _extract_opp_slug(self, href: str) -> Optional[str]:
        match = re.search(r'/cbb/schools/([^/]+)/', href)
        return match.group(1) if match else None

    def _parse_date(self, date_str: str) -> Optional[str]:
        """Convert 'Mon, Nov 6, 2023' to '2023-11-06'."""
        try:
            # Remove day-of-week prefix
            parts = date_str.split(', ', 1)
            if len(parts) > 1:
                date_str = parts[1]
            dt = datetime.strptime(date_str, '%b %d, %Y')
            return dt.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            return None

    def _get_team_seasons(self, slug: str, espn_id: str = None) -> List[int]:
        """Get list of season years for a team from seasons.json."""
        seasons_file = self.DATA_DIR / 'seasons.json'
        if not seasons_file.exists():
            return []

        with open(seasons_file) as f:
            seasons = json.load(f)

        # Try ESPN ID directly first (most reliable)
        team_data = seasons.get(espn_id, {}) if espn_id else {}

        # If not found, try reverse lookup from slug_mapping
        if not team_data.get('seasons'):
            sr_id = next((k for k, v in self.slug_mapping.items() if v == slug), None)
            if sr_id:
                team_data = seasons.get(sr_id, {})

        years = []
        for s in team_data.get('seasons', []):
            year_str = s.get('year', '')
            match = re.match(r'^(\d{4})', year_str)
            if match:
                # SR uses the end year for the URL (e.g., 2023-24 -> 2024)
                start_year = int(match.group(1))
                years.append(start_year + 1)
        return sorted(years)

    def _fetch_season_schedule(self, slug: str, year: int) -> List[Dict]:
        """Fetch one season's schedule for a team."""
        url = f"{self.BASE_URL}/{slug}/men/{year}-schedule.html"
        html = self._fetch_page(url)
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

                # Date
                date_cell = row.find(['td', 'th'], {'data-stat': 'date_game'})
                if not date_cell:
                    continue
                date_text = date_cell.get_text(strip=True)
                date = self._parse_date(date_text)
                if not date:
                    continue

                # Opponent
                opp_cell = row.find(['td', 'th'], {'data-stat': 'opp_name'})
                if not opp_cell:
                    continue
                opp_link = opp_cell.find('a')
                opp_slug = None
                if opp_link and opp_link.get('href'):
                    opp_slug = self._extract_opp_slug(opp_link['href'])
                opp_name = opp_cell.get_text(strip=True)

                # Location
                loc_cell = row.find(['td', 'th'], {'data-stat': 'game_location'})
                loc_text = loc_cell.get_text(strip=True) if loc_cell else ''
                if loc_text == '@':
                    loc = 'A'
                elif loc_text == 'N':
                    loc = 'N'
                else:
                    loc = 'H'

                # Result
                result_cell = row.find(['td', 'th'], {'data-stat': 'game_result'})
                result = result_cell.get_text(strip=True) if result_cell else ''
                won = result.startswith('W')

                # Scores
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

                # OT
                ot_cell = row.find(['td', 'th'], {'data-stat': 'overtimes'})
                ot = ot_cell.get_text(strip=True) if ot_cell else ''

                # Venue
                arena_cell = row.find(['td', 'th'], {'data-stat': 'arena'})
                arena = arena_cell.get_text(strip=True) if arena_cell else ''

                # Map opponent slug to ESPN ID
                opp_espn_id = self.sr_to_espn.get(opp_slug) if opp_slug else None

                game = {
                    'date': date,
                    'opp_slug': opp_slug or opp_name,
                    'loc': loc,
                    'w': won,
                    'pts': pts,
                    'opp_pts': opp_pts,
                }
                if opp_espn_id:
                    game['opp'] = opp_espn_id
                if ot:
                    game['ot'] = ot
                if arena:
                    game['arena'] = arena

                games.append(game)

            return games

        except Exception as e:
            print(f"    Error parsing: {e}")
            return []

    def compile_team(self, slug: str, espn_id: str):
        """Compile all schedule data for one team."""
        seasons = self._get_team_seasons(slug, espn_id)

        # Only scrape seasons from 1950 onward (schedule data starts there)
        seasons = [y for y in seasons if y >= 1950]

        if not seasons:
            # If no seasons data, try to scrape the main page to find available years
            print(f"    No seasons found in seasons.json, trying main page...")
            url = f"{self.BASE_URL}/{slug}/men/"
            html = self._fetch_page(url)
            if html:
                soup = BeautifulSoup(html, 'html.parser')
                # Find links to season pages (year links in the seasons table)
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    # Match both schedule links and season links
                    match = re.search(r'/cbb/schools/[^/]+/men/(\d{4})', href)
                    if match:
                        year = int(match.group(1))
                        if 1950 <= year <= 2030:
                            seasons.append(year)
                seasons = sorted(set(seasons))

            if not seasons:
                # Last resort: try generating year range from 1950 to current year
                print(f"    Fallback: generating year range 1950-2026")
                seasons = list(range(1950, 2027))

            if not seasons:
                print(f"    Could not determine seasons for {slug}")
                return

        # Check if we already have this team's data
        if espn_id in self.games_data:
            existing_games = len(self.games_data[espn_id].get('games', []))
            if existing_games > 0:
                print(f"    Already have {existing_games} games, skipping")
                return

        print(f"    Scraping {len(seasons)} seasons ({seasons[0]}-{seasons[-1]})")

        all_games = []
        self._consecutive_429s = 0
        for i, year in enumerate(seasons):
            # If we've hit 3+ consecutive 429 failures, take a long break
            if getattr(self, '_consecutive_429s', 0) >= 3:
                print(f"    ⚠️  Persistent rate limiting detected. Taking 20-minute cooldown...")
                time.sleep(1200)
                self._consecutive_429s = 0
                print(f"    Resuming scrape...")
            games = self._fetch_season_schedule(slug, year)
            all_games.extend(games)
            if (i + 1) % 20 == 0:
                print(f"      {i+1}/{len(seasons)} seasons, {len(all_games)} games so far")

        if all_games:
            self.games_data[espn_id] = {'games': all_games, 'slug': slug}
            print(f"    -> {len(all_games)} games")
        else:
            print(f"    -> No games found")

    def compile_conference(self, conf_name: str):
        """Compile schedule data for all teams in a conference."""
        print(f"\n{'=' * 70}")
        print(f"SCHEDULE COMPILER - {conf_name}")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 70}\n")

        # Load data.json to find conference teams
        data_file = self.DATA_DIR / 'data.json'
        with open(data_file) as f:
            data = json.load(f)

        conf_teams = []
        for eid, team in data['H'].items():
            if team[2] == conf_name:  # conf is index 2
                sr_slug = self.espn_to_sr.get(eid)
                if sr_slug:
                    conf_teams.append((eid, team[0], sr_slug))

        conf_teams.sort(key=lambda x: x[1])
        print(f"Found {len(conf_teams)} {conf_name} teams\n")

        for i, (espn_id, name, slug) in enumerate(conf_teams):
            self.teams_processed += 1
            print(f"[{i+1}/{len(conf_teams)}] {name} (ESPN {espn_id}, slug: {slug})")
            self.compile_team(slug, espn_id)

            # Save every 3 teams
            if (i + 1) % 3 == 0:
                self._save_progress()

        self._save_progress()

        print(f"\n{'=' * 70}")
        print(f"COMPLETE - {conf_name}")
        total_games = sum(len(v.get('games', [])) for v in self.games_data.values())
        print(f"Teams: {len(self.games_data)}, Total games: {total_games}")
        print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 70}\n")

    def compile_slugs(self, slugs: List[str]):
        """Compile schedule data for specific teams by slug."""
        for slug in slugs:
            espn_id = self.sr_to_espn.get(slug)
            if not espn_id:
                print(f"No ESPN ID for slug {slug}, skipping")
                continue
            print(f"Compiling {slug} (ESPN {espn_id})")
            self.compile_team(slug, espn_id)
            self._save_progress()


def main():
    parser = argparse.ArgumentParser(description='Compile game-level schedule data')
    parser.add_argument('--conf', help='Conference name (e.g., ACC, SEC, Big 12)')
    parser.add_argument('--slugs', help='Comma-separated SR slugs (e.g., duke,nc-state)')
    args = parser.parse_args()

    compiler = ScheduleCompiler()

    if args.conf:
        compiler.compile_conference(args.conf)
    elif args.slugs:
        compiler.compile_slugs(args.slugs.split(','))
    else:
        print("Specify --conf or --slugs")


if __name__ == '__main__':
    main()
