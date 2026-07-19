#!/usr/bin/env python3
"""Scrape a single team and merge immediately."""
import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from scrape_batch import SafeScraper, load_json, find_smallest_games_file, DATA_DIR
from json_io import save_json_atomic

def main():
    eid = sys.argv[1]
    espn_to_sr = load_json('espn_to_sr.json')
    data = load_json('data.json')
    H = data.get('H', {})
    
    if eid not in espn_to_sr:
        print(f"No SR mapping for {eid}")
        sys.exit(1)
    
    slug = espn_to_sr[eid]
    name = H.get(eid, ['Unknown'])[0]
    
    # Check if already scraped
    for fn in ['games_1.json', 'games_2.json', 'games_3.json']:
        d = load_json(fn)
        if eid in d:
            print(f"SKIP: {name} ({eid}) already scraped")
            sys.exit(0)
    
    print(f"Scraping {name} ({eid}, slug: {slug})...")
    scraper = SafeScraper()
    games = scraper.scrape_team(eid, slug, name)
    
    if not games:
        print(f"FAILED: No games for {name}")
        sys.exit(1)
    
    # Merge immediately
    target = find_smallest_games_file()
    with open(DATA_DIR / target) as f:
        target_data = json.load(f)
    
    target_data[eid] = games
    save_json_atomic(DATA_DIR / target, target_data, separators=(',', ':'))
    
    # Verify
    with open(DATA_DIR / target) as f:
        json.load(f)
    
    print(f"SUCCESS: {name} ({eid}) -> {target}: {len(games)} games")

if __name__ == '__main__':
    main()
