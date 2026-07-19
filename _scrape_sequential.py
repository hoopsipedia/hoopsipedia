#!/usr/bin/env python3
"""Scrape teams one at a time, merging after each success."""
import json, sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
from scrape_batch import SafeScraper, load_json, find_smallest_games_file, DATA_DIR
from json_io import save_json_atomic

def get_scraped():
    scraped = set()
    for fn in ['games_1.json', 'games_2.json', 'games_3.json']:
        d = load_json(fn)
        scraped.update(d.keys())
    return scraped

def main():
    ids = sys.argv[1].split(',')
    espn_to_sr = load_json('espn_to_sr.json')
    data = load_json('data.json')
    H = data.get('H', {})
    
    scraper = SafeScraper()
    success_count = 0
    
    for i, eid in enumerate(ids):
        eid = str(eid).strip()
        
        # Re-check scraped status each iteration
        scraped = get_scraped()
        if eid in scraped:
            print(f"[{i+1}/{len(ids)}] SKIP: {eid} already scraped")
            continue
        
        if eid not in espn_to_sr:
            print(f"[{i+1}/{len(ids)}] SKIP: No SR mapping for {eid}")
            continue
        
        slug = espn_to_sr[eid]
        name = H.get(eid, ['Unknown'])[0]
        
        print(f"\n[{i+1}/{len(ids)}] Scraping {name} ({eid})...")
        games = scraper.scrape_team(eid, slug, name)
        
        if not games:
            print(f"  FAILED: No games for {name}")
            continue
        
        # Merge immediately after each team
        target = find_smallest_games_file()
        with open(DATA_DIR / target) as f:
            target_data = json.load(f)
        
        target_data[eid] = games
        save_json_atomic(DATA_DIR / target, target_data, separators=(',', ':'))
        
        # Verify
        with open(DATA_DIR / target) as f:
            json.load(f)
        
        success_count += 1
        total = sum(len(load_json(fn)) for fn in ['games_1.json', 'games_2.json', 'games_3.json'])
        print(f"  SUCCESS: {name} -> {target}: {len(games)} games (total: {total})")
    
    print(f"\nDone! {success_count}/{len(ids)} teams scraped successfully.")

if __name__ == '__main__':
    main()
