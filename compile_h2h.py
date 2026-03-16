#!/usr/bin/env python3
"""
Head-to-Head Historical Data Compiler
Fetches all-time head-to-head records from Sports Reference for all D1 teams
and compiles into h2h.json for the Hoopsipedia web app.

Each team's H2H page lists their all-time record against every opponent
(since 1949-50, D1 teams only). We scrape all 361 teams and cross-reference
by Sports Reference slug to map back to ESPN IDs.

Output format:
{
    "2305": {  // ESPN ID
        "127": {"w": 15, "l": 10, "g": 25},  // opponent ESPN ID
        "150": {"w": 8, "l": 12, "g": 20},
        ...
    }
}
"""

import json
import time
import re
from pathlib import Path
from typing import Optional, Dict, Any
import requests
from bs4 import BeautifulSoup
from datetime import datetime


class HeadToHeadCompiler:
    """Compiler for all-time head-to-head records from Sports Reference."""

    BASE_URL = "https://www.sports-reference.com/cbb/schools"
    MIN_REQUEST_INTERVAL = 3.1  # Respect 20 requests/minute rate limit
    DATA_DIR = Path(__file__).parent

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.slug_mapping = self._load_slug_mapping()
        self.reverse_slug = {v: k for k, v in self.slug_mapping.items()}
        self.h2h_data = self._load_existing_h2h()
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

    def _load_existing_h2h(self) -> Dict[str, Dict[str, Any]]:
        """Load existing h2h.json if it exists for resuming."""
        h2h_file = self.DATA_DIR / 'h2h.json'
        if h2h_file.exists():
            with open(h2h_file) as f:
                data = json.load(f)
            print(f"Loaded existing h2h.json with {len(data)} teams")
            return data
        return {}

    def _save_progress(self):
        """Save current progress to h2h.json."""
        h2h_file = self.DATA_DIR / 'h2h.json'
        with open(h2h_file, 'w') as f:
            json.dump(self.h2h_data, f, separators=(',', ':'))
        size_kb = h2h_file.stat().st_size / 1024
        print(f"  >> Progress saved: {len(self.h2h_data)} teams in h2h.json ({size_kb:.0f} KB)")

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

    def _extract_slug_from_href(self, href: str) -> Optional[str]:
        """Extract the Sports Reference slug from an opponent link."""
        match = re.search(r'/cbb/schools/([^/]+)/', href)
        return match.group(1) if match else None

    def _fetch_team_h2h(self, espn_id: str, slug: str) -> Optional[Dict[str, Dict[str, int]]]:
        """Fetch and parse H2H data for a single team."""
        url = f"{self.BASE_URL}/{slug}/men/head-to-head.html"

        html = self._fetch_page(url)
        if not html:
            return None

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Find the head-to-head table
            table = soup.find('table', {'id': 'head-to-head'})
            if not table:
                # Fallback: find any table with opp_name data-stat
                for t in soup.find_all('table'):
                    if t.find(['td', 'th'], {'data-stat': 'opp_name'}):
                        table = t
                        break

            if not table:
                print(f"    No H2H table found for {slug}")
                return None

            tbody = table.find('tbody')
            rows = tbody.find_all('tr') if tbody else table.find_all('tr')

            opponents = {}
            for row in rows:
                # Skip header/separator rows
                if row.get('class') and any(c in ('thead', 'over_header') for c in row.get('class', [])):
                    continue

                # Get opponent name cell and extract slug from link
                opp_cell = row.find(['td', 'th'], {'data-stat': 'opp_name'})
                if not opp_cell:
                    continue

                opp_link = opp_cell.find('a')
                if not opp_link or not opp_link.get('href'):
                    continue

                opp_slug = self._extract_slug_from_href(opp_link['href'])
                if not opp_slug:
                    continue

                # Look up ESPN ID for this opponent
                opp_espn_id = self.reverse_slug.get(opp_slug)
                if not opp_espn_id:
                    # Opponent not in our mapping (non-D1 or missing), skip
                    continue

                # Extract W, L, G
                games_cell = row.find(['td', 'th'], {'data-stat': 'games'})
                wins_cell = row.find(['td', 'th'], {'data-stat': 'wins'})
                losses_cell = row.find(['td', 'th'], {'data-stat': 'losses'})

                if not (games_cell and wins_cell and losses_cell):
                    continue

                try:
                    games = int(games_cell.get_text(strip=True))
                    wins = int(wins_cell.get_text(strip=True))
                    losses = int(losses_cell.get_text(strip=True))
                except (ValueError, TypeError):
                    continue

                if games > 0:
                    opponents[opp_espn_id] = {
                        'w': wins,
                        'l': losses,
                        'g': games
                    }

            return opponents if opponents else None

        except Exception as e:
            print(f"    Error parsing H2H page: {e}")
            return None

    def compile_all_h2h(self):
        """Main method: compile H2H data for all teams."""
        print("\n" + "=" * 70)
        print("HEAD-TO-HEAD HISTORICAL DATA COMPILER")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70 + "\n")

        total_teams = len(self.slug_mapping)
        completed_teams = len(self.h2h_data)

        print(f"Total teams to process: {total_teams}")
        print(f"Already completed: {completed_teams}")
        print(f"Remaining: {total_teams - completed_teams}\n")

        for espn_id, slug in sorted(self.slug_mapping.items()):
            # Skip if already processed
            if espn_id in self.h2h_data:
                self.teams_processed += 1
                continue

            self.teams_processed += 1
            print(f"[{self.teams_processed}/{total_teams}] ESPN {espn_id} - {slug}", end="")

            h2h = self._fetch_team_h2h(espn_id, slug)

            if h2h:
                self.h2h_data[espn_id] = h2h
                print(f" -> {len(h2h)} opponents")
            else:
                # Store empty dict so we don't retry on resume
                self.h2h_data[espn_id] = {}
                print(f" -> FAILED (0 opponents)")
                self.teams_failed += 1

            # Save progress every 10 teams
            if self.teams_processed % 10 == 0:
                self._save_progress()

        # Final save
        self._save_progress()

        print("\n" + "=" * 70)
        print("COMPILATION COMPLETE")
        print(f"Teams processed: {self.teams_processed}")
        print(f"Teams with H2H data: {sum(1 for v in self.h2h_data.values() if v)}")
        print(f"Teams failed: {self.teams_failed}")
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70 + "\n")

    def validate_output(self):
        """Validate the output and print statistics."""
        h2h_file = self.DATA_DIR / 'h2h.json'
        if not h2h_file.exists():
            print("ERROR: h2h.json not found")
            return False

        with open(h2h_file) as f:
            data = json.load(f)

        total_matchups = sum(len(opps) for opps in data.values())
        teams_with_data = sum(1 for v in data.values() if v)
        max_opponents = max((len(v) for v in data.values()), default=0)
        max_team = max(data.items(), key=lambda x: len(x[1]), default=None)

        print(f"\nValidating h2h.json:")
        print(f"  Total teams: {len(data)}")
        print(f"  Teams with H2H data: {teams_with_data}")
        print(f"  Total matchup entries: {total_matchups}")
        print(f"  Most opponents: {max_opponents} (ESPN ID {max_team[0] if max_team else 'N/A'})")
        print(f"  File size: {h2h_file.stat().st_size / 1024:.0f} KB")

        # Cross-reference check: verify symmetry
        mismatches = 0
        for team_id, opponents in data.items():
            for opp_id, record in opponents.items():
                if opp_id in data and team_id in data[opp_id]:
                    opp_record = data[opp_id][team_id]
                    # Team A's wins vs B should equal B's losses vs A
                    if record['w'] != opp_record['l'] or record['l'] != opp_record['w']:
                        mismatches += 1

        if mismatches:
            print(f"  WARNING: {mismatches} asymmetric matchups found (minor discrepancies expected)")
        else:
            print(f"  Symmetry check: PASSED")

        # Sample output
        sample_id = next((k for k, v in data.items() if len(v) > 50), None)
        if sample_id:
            slug = self.slug_mapping.get(sample_id, 'unknown')
            opps = data[sample_id]
            print(f"\n  Sample: {slug} (ESPN {sample_id}) - {len(opps)} opponents")
            for opp_id, rec in list(opps.items())[:3]:
                opp_slug = self.slug_mapping.get(opp_id, 'unknown')
                print(f"    vs {opp_slug}: {rec['w']}-{rec['l']} ({rec['g']} games)")

        return True


def main():
    """Entry point."""
    compiler = HeadToHeadCompiler()
    compiler.compile_all_h2h()
    compiler.validate_output()


if __name__ == '__main__':
    main()
