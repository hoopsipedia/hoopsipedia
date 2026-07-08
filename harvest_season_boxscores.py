#!/usr/bin/env python3
"""Harvest EVERY available SR box score for a full season (all teams).

Phase 1: crawl each D1 team's SR schedule page for the season and
collect every /cbb/boxscores/ link (regular season + all postseason).
Phase 2: scrape each unique box score page with the existing parser and
merge into sr_boxscores.json under the tournament-year key convention.

Usage: python3 harvest_season_boxscores.py --season 1979 [--delay 3.2]
(--season is the END year: 1979 = the 1978-79 season)
"""

import argparse
import json
import re
import sys
import time

import requests

from json_io import save_json_atomic
from sr_parser import SRFetcher, parse_boxscore_html, url_to_game_key

sys.stdout.reconfigure(line_buffering=True)

SCHED = 'https://www.sports-reference.com/cbb/schools/{school}/men/{yr}-schedule.html'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--season', type=int, required=True)
    ap.add_argument('--delay', type=float, default=3.2)
    args = ap.parse_args()
    yr = args.season

    with open('espn_to_sr.json') as f:
        schools = sorted(set(json.load(f).values()))
    print(f'season {yr}: crawling {len(schools)} school schedule pages')

    box_urls = set()
    ok_pages = 0
    for i, school in enumerate(schools):
        url = SCHED.format(school=school, yr=yr)
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
        except requests.RequestException:
            time.sleep(args.delay)
            continue
        time.sleep(args.delay)
        if r.status_code == 429:
            print(f'429 at {school} — cooling 15 min')
            time.sleep(900)
            continue
        if r.status_code != 200:
            continue
        ok_pages += 1
        for m in re.finditer(r'href="(/cbb/boxscores/\d{4}-\d{2}-\d{2}-[^"]+\.html)"', r.text):
            box_urls.add('https://www.sports-reference.com' + m.group(1))
        if (i + 1) % 50 == 0:
            print(f'  {i+1}/{len(schools)} schools | {len(box_urls)} unique box URLs')

    print(f'PHASE 1 DONE: {ok_pages} schedule pages, {len(box_urls)} unique box scores available')

    with open('sr_boxscores.json') as f:
        existing = json.load(f)
    have_keys = set(existing.keys())

    fetcher = SRFetcher(delay=args.delay)
    scraped = 0
    skipped = 0
    failed = 0
    for i, url in enumerate(sorted(box_urls)):
        html = fetcher.fetch(url)
        if not html:
            failed += 1
            continue
        parsed = parse_boxscore_html(html, url)
        if parsed:
            key = url_to_game_key(url, parsed)
            if not key or key in have_keys:
                skipped += 1
                continue
            have_keys.add(key)
            existing[key] = parsed
            scraped += 1
            if scraped % 25 == 0:
                save_json_atomic('sr_boxscores.json', existing, separators=(',', ':'))
                print(f'  [{i+1}/{len(box_urls)}] scraped {scraped} (skipped {skipped}, failed {failed})')
        else:
            failed += 1

    save_json_atomic('sr_boxscores.json', existing, separators=(',', ':'))
    json.load(open('sr_boxscores.json'))
    print(f'PHASE 2 DONE: +{scraped} new box scores | already had {skipped} | failed {failed}')
    print(f'total in file: {len(existing)-1}')
    print('SEASON HARVEST COMPLETE')


if __name__ == '__main__':
    main()
