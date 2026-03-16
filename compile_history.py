#!/usr/bin/env python3
"""
College Basketball Historical Data Compiler
Fetches season-by-season data from Sports Reference for all D1 teams
and compiles into a JSON file for the Hoopsipedia web app.
"""

import json
import time
import re
from pathlib import Path
from typing import Optional, Dict, List, Any
import requests
from bs4 import BeautifulSoup
from datetime import datetime


class CollegeBasketballCompiler:
    """Main compiler class for fetching and parsing college basketball data."""

    BASE_URL = "https://www.sports-reference.com/cbb/schools"
    MIN_REQUEST_INTERVAL = 3.1  # Respect 20 requests/minute rate limit
    DATA_DIR = Path(__file__).parent

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.slug_mapping = self._load_slug_mapping()
        self.seasons_data = self._load_existing_seasons()
        self.last_request_time = 0
        self.teams_processed = 0
        self.teams_failed = 0

    def _load_slug_mapping(self) -> Dict[str, str]:
        """Load the ESPN ID to Sports Reference slug mapping."""
        mapping_file = self.DATA_DIR / 'slug_mapping.json'
        if not mapping_file.exists():
            print(f"ERROR: slug_mapping.json not found at {mapping_file}")
            return {}

        with open(mapping_file) as f:
            mapping = json.load(f)
        print(f"Loaded {len(mapping)} team slug mappings")
        return mapping

    def _load_existing_seasons(self) -> Dict[str, Dict[str, Any]]:
        """Load existing seasons.json if it exists for resuming."""
        seasons_file = self.DATA_DIR / 'seasons.json'
        if seasons_file.exists():
            with open(seasons_file) as f:
                data = json.load(f)
            print(f"Loaded existing seasons.json with {len(data)} teams")
            return data
        return {}

    def _save_progress(self):
        """Save current progress to seasons.json."""
        seasons_file = self.DATA_DIR / 'seasons.json'
        with open(seasons_file, 'w') as f:
            json.dump(self.seasons_data, f, separators=(',', ':'))
        print(f"  >> Progress saved: {len(self.seasons_data)} teams in seasons.json")

    def _rate_limit_sleep(self):
        """Enforce rate limiting (3.1 seconds minimum between requests)."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            sleep_time = self.MIN_REQUEST_INTERVAL - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch a page with error handling and retry."""
        self._rate_limit_sleep()
        for attempt in range(3):
            try:
                response = self.session.get(url, timeout=15)
                if response.status_code == 429:
                    # Rate limited - wait longer and retry
                    wait = 30 * (attempt + 1)
                    print(f"    429 Rate Limited. Waiting {wait}s...")
                    time.sleep(wait)
                    self.last_request_time = time.time()
                    continue
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                if attempt < 2:
                    print(f"    Retry {attempt+1}: {e}")
                    time.sleep(5)
                else:
                    print(f"    Error fetching {url}: {e}")
                    return None
        return None

    def _get_cell_value(self, row, data_stat: str) -> Optional[str]:
        """Get cell value by data-stat attribute."""
        cell = row.find(['td', 'th'], {'data-stat': data_stat})
        if cell:
            text = cell.get_text(strip=True)
            return text if text else None
        return None

    def _parse_season_from_row(self, row) -> Optional[Dict[str, Any]]:
        """Parse a single season row using data-stat attributes."""
        try:
            # Skip separator/header rows
            if row.get('class') and any('thead' in c or 'over_header' in c for c in row.get('class', [])):
                return None

            # Get season year
            season = self._get_cell_value(row, 'season')
            if not season or not re.match(r'^\d{4}', season):
                return None

            season_obj = {'year': season}

            # Overall record: wins and losses
            wins = self._get_cell_value(row, 'wins')
            losses = self._get_cell_value(row, 'losses')
            if wins and losses:
                season_obj['wins'] = int(wins)
                season_obj['losses'] = int(losses)
                season_obj['record'] = f"{wins}-{losses}"

            # Win-Loss percentage
            wl_pct = self._get_cell_value(row, 'win_loss_pct')
            if wl_pct:
                try:
                    season_obj['winPct'] = float(wl_pct)
                except ValueError:
                    pass

            # Conference
            conf = self._get_cell_value(row, 'conf_abbr')
            if conf:
                season_obj['conf'] = conf

            # Conference record
            conf_wins = self._get_cell_value(row, 'wins_conf')
            conf_losses = self._get_cell_value(row, 'losses_conf')
            if conf_wins and conf_losses:
                season_obj['confWins'] = int(conf_wins)
                season_obj['confLosses'] = int(conf_losses)
                season_obj['confRecord'] = f"{conf_wins}-{conf_losses}"

            # Conference W-L%
            conf_pct = self._get_cell_value(row, 'win_loss_pct_conf')
            if conf_pct:
                try:
                    season_obj['confWinPct'] = float(conf_pct)
                except ValueError:
                    pass

            # SRS (Simple Rating System)
            srs = self._get_cell_value(row, 'srs')
            if srs:
                try:
                    season_obj['srs'] = float(srs)
                except ValueError:
                    pass

            # SOS (Strength of Schedule)
            sos = self._get_cell_value(row, 'sos')
            if sos:
                try:
                    season_obj['sos'] = float(sos)
                except ValueError:
                    pass

            # Points per game
            ppg = self._get_cell_value(row, 'pts_per_g')
            if ppg:
                try:
                    season_obj['ppg'] = float(ppg)
                except ValueError:
                    pass

            # Opponent points per game
            opp_ppg = self._get_cell_value(row, 'opp_pts_per_g')
            if opp_ppg:
                try:
                    season_obj['oppPpg'] = float(opp_ppg)
                except ValueError:
                    pass

            # AP Rankings
            ap_pre = self._get_cell_value(row, 'rank_pre')
            if ap_pre and ap_pre.isdigit():
                season_obj['apPre'] = int(ap_pre)

            ap_high = self._get_cell_value(row, 'rank_min')
            if ap_high and ap_high.isdigit():
                season_obj['apHigh'] = int(ap_high)

            ap_final = self._get_cell_value(row, 'rank_final')
            if ap_final and ap_final.isdigit():
                season_obj['apFinal'] = int(ap_final)

            # NCAA Tournament result
            ncaa = self._get_cell_value(row, 'round_max')
            if ncaa:
                season_obj['ncaaTourney'] = ncaa

            # Tournament seed
            seed = self._get_cell_value(row, 'seed')
            if seed and seed.isdigit():
                season_obj['seed'] = int(seed)

            # Coach
            coach = self._get_cell_value(row, 'coaches')
            if coach:
                # Clean coach string - remove record in parentheses
                clean = re.sub(r'\(\d+-\d+\)', '', coach).strip()
                # Handle multiple coaches separated by commas
                season_obj['coach'] = clean

            # Only return if we got at least the year and a record
            if 'wins' in season_obj:
                return season_obj

            return None

        except Exception as e:
            print(f"    Error parsing row: {e}")
            return None

    def _fetch_team_data(self, espn_id: str, slug: str) -> Optional[List[Dict[str, Any]]]:
        """Fetch and parse season data for a single team."""
        url = f"{self.BASE_URL}/{slug}/men/"

        html = self._fetch_page(url)
        if not html:
            return None

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Sports Reference uses the slug as the table ID
            table = soup.find('table', {'id': slug})

            # Fallback: find table by looking for data-stat="season" in any table
            if not table:
                for t in soup.find_all('table'):
                    if t.find(['td', 'th'], {'data-stat': 'season'}):
                        table = t
                        break

            if not table:
                print(f"    No seasons table found for {slug}")
                return None

            # Parse from tbody to skip header rows
            tbody = table.find('tbody')
            if not tbody:
                rows = table.find_all('tr')
            else:
                rows = tbody.find_all('tr')

            seasons = []
            for row in rows:
                season = self._parse_season_from_row(row)
                if season:
                    seasons.append(season)

            if seasons:
                return seasons
            else:
                print(f"    No valid seasons parsed from table")
                return None

        except Exception as e:
            print(f"    Error parsing page: {e}")
            return None

    def compile_all_teams(self):
        """Main method: compile data for all teams."""
        print("\n" + "=" * 70)
        print("COLLEGE BASKETBALL HISTORICAL DATA COMPILER")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70 + "\n")

        total_teams = len(self.slug_mapping)
        completed_teams = len(self.seasons_data)

        print(f"Total teams to process: {total_teams}")
        print(f"Already completed: {completed_teams}")
        print(f"Remaining: {total_teams - completed_teams}\n")

        for espn_id, slug in sorted(self.slug_mapping.items()):
            # Skip if already processed
            if espn_id in self.seasons_data:
                self.teams_processed += 1
                continue

            self.teams_processed += 1
            print(f"[{self.teams_processed}/{total_teams}] ESPN {espn_id} - {slug}", end="")

            seasons = self._fetch_team_data(espn_id, slug)

            if seasons:
                self.seasons_data[espn_id] = {'seasons': seasons}
                print(f" -> {len(seasons)} seasons")
            else:
                print(f" -> FAILED")
                self.teams_failed += 1

            # Save progress every 10 teams
            if self.teams_processed % 10 == 0:
                self._save_progress()

        # Final save
        self._save_progress()

        print("\n" + "=" * 70)
        print("COMPILATION COMPLETE")
        print(f"Teams processed: {self.teams_processed}")
        print(f"Teams successful: {len(self.seasons_data)}")
        print(f"Teams failed: {self.teams_failed}")
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70 + "\n")

    def validate_output(self):
        """Validate the output JSON structure."""
        seasons_file = self.DATA_DIR / 'seasons.json'
        if not seasons_file.exists():
            print("ERROR: seasons.json not found")
            return False

        with open(seasons_file) as f:
            data = json.load(f)

        print(f"\nValidating seasons.json:")
        print(f"  Total teams: {len(data)}")

        total_seasons = 0
        teams_with_tourney = 0
        teams_with_ap = 0
        for espn_id, team_data in data.items():
            if 'seasons' in team_data:
                total_seasons += len(team_data['seasons'])
                for s in team_data['seasons']:
                    if 'ncaaTourney' in s:
                        teams_with_tourney += 1
                        break
                for s in team_data['seasons']:
                    if 'apFinal' in s or 'apHigh' in s:
                        teams_with_ap += 1
                        break

        print(f"  Total seasons across all teams: {total_seasons}")
        print(f"  Teams with NCAA tourney data: {teams_with_tourney}")
        print(f"  Teams with AP ranking data: {teams_with_ap}")
        print(f"  File size: {seasons_file.stat().st_size / 1024 / 1024:.1f} MB")

        # Check a sample
        sample_id = next(iter(data)) if data else None
        if sample_id:
            sample = data[sample_id]
            print(f"\n  Sample team (ESPN ID {sample_id}):")
            if 'seasons' in sample and sample['seasons']:
                season = sample['seasons'][0]
                print(f"    Most recent: {json.dumps(season, indent=6)}")

        return True


def main():
    """Entry point."""
    compiler = CollegeBasketballCompiler()
    compiler.compile_all_teams()
    compiler.validate_output()


if __name__ == '__main__':
    main()
