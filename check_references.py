#!/usr/bin/env python3
"""
Check Sports Reference availability and test individual team pages.
Useful for debugging slug mapping issues.
"""

import json
import time
import sys
from pathlib import Path
from typing import Dict, Tuple
import requests
from bs4 import BeautifulSoup


class ReferenceChecker:
    """Check Sports Reference team pages."""

    BASE_URL = "https://www.sports-reference.com/cbb/schools"
    MIN_INTERVAL = 3.0  # Rate limit

    def __init__(self):
        self.data_dir = Path(__file__).parent
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.last_request = 0

    def load_mapping(self) -> Dict[str, str]:
        """Load slug mapping."""
        mapping_file = self.data_dir / 'slug_mapping.json'
        if not mapping_file.exists():
            return {}
        with open(mapping_file) as f:
            return json.load(f)

    def load_teams(self) -> Dict[str, str]:
        """Load team names from data.json."""
        data_file = self.data_dir / 'data.json'
        if not data_file.exists():
            return {}
        with open(data_file) as f:
            data = json.load(f)
        teams = {}
        for espn_id, team_data in data.get('H', {}).items():
            if isinstance(team_data, list) and len(team_data) > 0:
                teams[espn_id] = team_data[0]
        return teams

    def _rate_limit_sleep(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self.last_request
        if elapsed < self.MIN_INTERVAL:
            time.sleep(self.MIN_INTERVAL - elapsed)
        self.last_request = time.time()

    def check_url(self, espn_id: str, slug: str, team_name: str = "") -> Tuple[bool, str, int]:
        """Check if a Sports Reference URL is valid."""
        url = f"{self.BASE_URL}/{slug}/men/"
        self._rate_limit_sleep()

        try:
            response = self.session.get(url, timeout=10)
            status_code = response.status_code

            if status_code == 200:
                # Check for seasons table
                soup = BeautifulSoup(response.text, 'html.parser')
                has_table = bool(soup.find('table'))
                title = soup.find('h1')
                title_text = title.get_text(strip=True) if title else "Unknown"

                return True, f"✓ {title_text}", status_code
            else:
                return False, f"✗ HTTP {status_code}", status_code

        except requests.Timeout:
            return False, "✗ Timeout", 0
        except requests.ConnectionError:
            return False, "✗ Connection error", 0
        except Exception as e:
            return False, f"✗ Error: {str(e)[:50]}", 0

    def check_all_teams(self):
        """Check all teams in the mapping."""
        mapping = self.load_mapping()
        teams = self.load_teams()

        if not mapping:
            print("ERROR: No slug mapping found")
            return

        print("Checking all Sports Reference URLs...")
        print(f"Total teams: {len(mapping)}\n")

        results = {
            'success': [],
            'not_found': [],
            'error': []
        }

        for idx, (espn_id, slug) in enumerate(sorted(mapping.items(), key=lambda x: int(x[0])), 1):
            team_name = teams.get(espn_id, "Unknown")
            success, message, status_code = self.check_url(espn_id, slug, team_name)

            status_symbol = "✓" if success else "✗"
            print(f"[{idx:3d}/{len(mapping)}] {status_symbol} {espn_id:6s} {slug:30s} {message}")

            if success:
                results['success'].append(espn_id)
            elif status_code == 404:
                results['not_found'].append((espn_id, slug, team_name))
            else:
                results['error'].append((espn_id, slug, message))

        # Summary
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        print(f"Success: {len(results['success'])}")
        print(f"Not Found (404): {len(results['not_found'])}")
        print(f"Errors: {len(results['error'])}")

        if results['not_found']:
            print("\n⚠ Teams with 404 errors (slug may be incorrect):")
            for espn_id, slug, team_name in results['not_found'][:10]:
                print(f"  {espn_id} ({slug}) - {team_name}")

        if results['error']:
            print("\n⚠ Teams with other errors:")
            for espn_id, slug, message in results['error'][:10]:
                print(f"  {espn_id} ({slug}) - {message}")

    def check_team(self, espn_id: str):
        """Check a specific team."""
        mapping = self.load_mapping()
        teams = self.load_teams()

        if espn_id not in mapping:
            print(f"ERROR: ESPN ID {espn_id} not in mapping")
            return

        slug = mapping[espn_id]
        team_name = teams.get(espn_id, "Unknown")

        print(f"Checking ESPN ID {espn_id}: {team_name}")
        print(f"Slug: {slug}")

        success, message, status_code = self.check_url(espn_id, slug, team_name)

        print(f"URL: {self.BASE_URL}/{slug}/men/")
        print(f"Result: {message}")

        if success:
            # Try to extract some data
            url = f"{self.BASE_URL}/{slug}/men/"
            self._rate_limit_sleep()
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')

            title = soup.find('h1')
            if title:
                print(f"Page title: {title.get_text(strip=True)}")

            table = soup.find('table')
            if table:
                rows = table.find_all('tr')
                print(f"Seasons table: {len(rows)} rows")
                if rows:
                    first_row = rows[1] if len(rows) > 1 else rows[0]
                    cells = [cell.get_text(strip=True) for cell in first_row.find_all(['td', 'th'])]
                    print(f"Sample row: {cells[:5]}")

    def suggest_slug(self, team_name: str) -> str:
        """Suggest a slug based on team name."""
        # Remove common suffixes
        suffixes = ['Wildcats', 'Tar Heels', 'Spartans', 'Hoosiers', 'Boilermakers',
                    'Aggies', 'Nittany Lions', 'Badgers', 'Gophers', 'Hawkeyes',
                    'Cyclones', 'Jayhawks', 'Sooners', 'Cowboys', 'Eagles',
                    'Tigers', 'Lions', 'Bears', 'Bruins', 'Trojans', 'Mountaineers',
                    'Longhorns', 'Utes', 'Aztecs', 'Demons', 'Gamecocks']

        name = team_name
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[:-len(suffix)].strip()
                break

        slug = name.lower().replace(' ', '-').replace('&', '').replace("'", '')
        slug = '-'.join(filter(None, slug.split('-')))  # Remove empty parts
        return slug


def main():
    """Main entry point."""
    checker = ReferenceChecker()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 check_references.py all          - Check all teams")
        print("  python3 check_references.py team <ID>    - Check specific ESPN ID")
        print("  python3 check_references.py suggest <NAME> - Suggest slug for team name")
        print("\nExamples:")
        print("  python3 check_references.py team 96")
        print("  python3 check_references.py suggest 'Kentucky Wildcats'")
        return

    command = sys.argv[1]

    if command == 'all':
        checker.check_all_teams()
    elif command == 'team':
        if len(sys.argv) < 3:
            print("ERROR: ESPN ID required")
            return
        checker.check_team(sys.argv[2])
    elif command == 'suggest':
        if len(sys.argv) < 3:
            print("ERROR: Team name required")
            return
        team_name = ' '.join(sys.argv[2:])
        slug = checker.suggest_slug(team_name)
        print(f"Team name: {team_name}")
        print(f"Suggested slug: {slug}")
        print(f"\nAdd to slug_mapping.json:")
        print(f'  "XXX": "{slug}"')
    else:
        print(f"Unknown command: {command}")


if __name__ == '__main__':
    main()
