#!/usr/bin/env python3
"""
Test script for the college basketball scraper.
Tests slug mapping, fetches sample pages, and validates output structure.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup


class ScraperTester:
    """Test utilities for the scraper."""

    BASE_URL = "https://www.sports-reference.com/cbb/schools"

    def __init__(self):
        self.data_dir = Path(__file__).parent
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def load_slug_mapping(self) -> Dict[str, str]:
        """Load slug mapping."""
        mapping_file = self.data_dir / 'slug_mapping.json'
        if not mapping_file.exists():
            print(f"ERROR: {mapping_file} not found")
            return {}
        with open(mapping_file) as f:
            return json.load(f)

    def load_seasons_data(self) -> Dict:
        """Load existing seasons.json."""
        seasons_file = self.data_dir / 'seasons.json'
        if not seasons_file.exists():
            print(f"No existing seasons.json found")
            return {}
        with open(seasons_file) as f:
            return json.load(f)

    def test_slug_mapping(self):
        """Test that slug mapping is valid."""
        print("\n" + "="*70)
        print("TEST 1: Slug Mapping Validation")
        print("="*70)

        mapping = self.load_slug_mapping()
        if not mapping:
            print("FAILED: No slug mapping loaded")
            return False

        print(f"✓ Loaded {len(mapping)} team mappings")

        # Check for duplicates
        slugs = list(mapping.values())
        unique_slugs = set(slugs)
        if len(slugs) != len(unique_slugs):
            print(f"⚠ WARNING: {len(slugs) - len(unique_slugs)} duplicate slugs detected")
            duplicates = {slug: slugs.count(slug) for slug in slugs if slugs.count(slug) > 1}
            for slug, count in duplicates.items():
                print(f"  {slug}: appears {count} times")
            return False

        print("✓ No duplicate slugs found")

        # Check format
        invalid_slugs = []
        for espn_id, slug in mapping.items():
            if not slug or not isinstance(slug, str):
                invalid_slugs.append((espn_id, slug))
            elif not all(c.isalnum() or c == '-' for c in slug):
                invalid_slugs.append((espn_id, slug))

        if invalid_slugs:
            print(f"⚠ Found {len(invalid_slugs)} invalid slugs:")
            for espn_id, slug in invalid_slugs[:5]:
                print(f"  ESPN ID {espn_id}: '{slug}'")
            return False

        print("✓ All slugs have valid format (alphanumeric + hyphens)")
        return True

    def test_sample_fetch(self, espn_id: str = "96", max_retries: int = 3):
        """Test fetching a single team's page."""
        print("\n" + "="*70)
        print("TEST 2: Sample Page Fetch")
        print("="*70)

        mapping = self.load_slug_mapping()
        if espn_id not in mapping:
            print(f"ERROR: ESPN ID {espn_id} not in mapping")
            return False

        slug = mapping[espn_id]
        url = f"{self.BASE_URL}/{slug}/men/"
        print(f"Fetching sample: ESPN ID {espn_id} ({slug})")
        print(f"URL: {url}")

        for attempt in range(max_retries):
            try:
                print(f"  Attempt {attempt + 1}/{max_retries}...", end=' ')
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                print("✓")

                # Parse HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.find('h1')
                if title:
                    print(f"✓ Page title: {title.get_text(strip=True)}")

                # Check for seasons table
                table = soup.find('table')
                if table:
                    rows = table.find_all('tr')
                    print(f"✓ Found table with {len(rows)} rows")
                    return True
                else:
                    print("✗ No table found on page")
                    return False

            except requests.Timeout:
                print("⏱ Timeout")
            except requests.ConnectionError as e:
                print(f"✗ Connection error: {e}")
            except requests.HTTPError as e:
                print(f"✗ HTTP error: {e.response.status_code}")
                if attempt == max_retries - 1:
                    print(f"  May be rate limited. Wait before retrying.")
                return False
            except Exception as e:
                print(f"✗ Error: {e}")
                return False

        return False

    def test_output_structure(self):
        """Test the structure of generated seasons.json."""
        print("\n" + "="*70)
        print("TEST 3: Output Structure Validation")
        print("="*70)

        seasons_data = self.load_seasons_data()
        if not seasons_data:
            print("⚠ No seasons.json data to validate (run scraper first)")
            return True  # Not a failure

        print(f"✓ Loaded {len(seasons_data)} teams")

        # Validate structure
        errors = []
        for espn_id, team_data in list(seasons_data.items())[:5]:
            if not isinstance(team_data, dict):
                errors.append(f"Team {espn_id}: not a dict")
                continue

            if 'seasons' not in team_data:
                errors.append(f"Team {espn_id}: no 'seasons' key")
                continue

            seasons = team_data['seasons']
            if not isinstance(seasons, list):
                errors.append(f"Team {espn_id}: 'seasons' is not a list")
                continue

            # Check season structure
            for season in seasons[:2]:  # Check first 2 seasons
                if not isinstance(season, dict):
                    errors.append(f"Team {espn_id}: season is not a dict")
                    continue

                required_keys = ['year', 'record']
                for key in required_keys:
                    if key not in season:
                        errors.append(f"Team {espn_id}: missing '{key}' in season")

        if errors:
            print(f"⚠ Found {len(errors)} structure errors:")
            for error in errors[:10]:
                print(f"  - {error}")
            return False

        print("✓ Output structure is valid")

        # Print sample
        sample_id = next(iter(seasons_data))
        sample = seasons_data[sample_id]
        print(f"\n  Sample team (ESPN ID {sample_id}):")
        if sample['seasons']:
            season = sample['seasons'][0]
            print(f"    Year: {season.get('year')}")
            print(f"    Record: {season.get('record')}")
            print(f"    Coach: {season.get('coach')}")
            print(f"    Postseason: {season.get('postseason')}")
            print(f"    AP Rank: {season.get('apRank')}")

        return True

    def run_all_tests(self):
        """Run all tests."""
        print("\n" + "="*70)
        print("COLLEGE BASKETBALL SCRAPER - TEST SUITE")
        print("="*70)

        tests = [
            ("Slug Mapping", self.test_slug_mapping),
            ("Sample Fetch", self.test_sample_fetch),
            ("Output Structure", self.test_output_structure),
        ]

        results = []
        for name, test_func in tests:
            try:
                result = test_func()
                results.append((name, result))
            except Exception as e:
                print(f"ERROR in {name}: {e}")
                results.append((name, False))

        # Summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        passed = sum(1 for _, result in results if result)
        total = len(results)
        print(f"\nPassed: {passed}/{total}")
        for name, result in results:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"  {status}: {name}")

        return all(result for _, result in results)


def main():
    """Main entry point."""
    tester = ScraperTester()

    # Allow specific test
    if len(sys.argv) > 1:
        test_name = sys.argv[1]
        if test_name == "mapping":
            tester.test_slug_mapping()
        elif test_name == "fetch":
            sample_id = sys.argv[2] if len(sys.argv) > 2 else "96"
            tester.test_sample_fetch(sample_id)
        elif test_name == "structure":
            tester.test_output_structure()
        else:
            print(f"Unknown test: {test_name}")
            print("Available tests: mapping, fetch, structure")
    else:
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
