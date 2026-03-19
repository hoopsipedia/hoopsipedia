#!/usr/bin/env python3
"""
Scrape box score data from Sports Reference for NCAA tournament upset games (2005-2025).
Uses pre-mapped URLs from boxscore_urls.json (generated from tournament bracket pages).
Falls back to schedule page lookup if URL 404s.
Saves to sr_boxscores_modern.json.
"""

import json
import os
import sys
import time
import re
import argparse
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, "sr_boxscores_modern.json")
GAMES_FILE = os.path.join(BASE_DIR, "boxscore_urls.json")

RATE_LIMIT = 4.0  # seconds between requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
}


def fetch(url, retries=2):
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers=HEADERS)
            resp = urlopen(req, timeout=30)
            return resp.read().decode("utf-8", errors="replace")
        except HTTPError as e:
            if e.code == 429:
                wait = 60 * (attempt + 1)
                print(f"    429 rate limited, waiting {wait}s...")
                time.sleep(wait)
            elif e.code == 404:
                return None
            else:
                print(f"    HTTP {e.code}")
                return None
        except Exception as e:
            print(f"    Error: {e}")
            if attempt < retries:
                time.sleep(10)
    return None


def parse_boxscore(html):
    """Parse SR box score HTML, return list of team dicts."""
    table_ids = re.findall(r'id="box-score-basic-([^"]+)"', html)
    if not table_ids:
        return None

    teams = []
    for slug in table_ids:
        tid = f"box-score-basic-{slug}"
        pat = f'<table[^>]*id="{tid}"[^>]*>(.*?)</table>'
        m = re.search(pat, html, re.DOTALL)
        if not m:
            continue
        thtml = m.group(1)

        # Players from tbody
        tbody = re.search(r'<tbody>(.*?)</tbody>', thtml, re.DOTALL)
        if not tbody:
            continue
        players = []
        for row in re.findall(r'<tr[^>]*>(.*?)</tr>', tbody.group(1), re.DOTALL):
            if 'class="thead"' in row:
                continue
            cells = re.findall(r'<(?:td|th)[^>]*data-stat="([^"]*)"[^>]*>(.*?)</(?:td|th)>', row, re.DOTALL)
            if not cells:
                continue
            d = {k: re.sub(r'<[^>]+>', '', v).strip() for k, v in cells}
            name = d.get("player", "")
            if not name or name in ("Starters", "Reserves"):
                continue
            players.append({
                "name": name, "mp": d.get("mp", ""), "pts": d.get("pts", ""),
                "fg": d.get("fg", ""), "fga": d.get("fga", ""),
                "fg3": d.get("fg3", ""), "fg3a": d.get("fg3a", ""),
                "ft": d.get("ft", ""), "fta": d.get("fta", ""),
                "trb": d.get("trb", ""), "ast": d.get("ast", ""),
                "stl": d.get("stl", ""), "blk": d.get("blk", ""),
                "tov": d.get("tov", ""),
            })

        # Totals from tfoot
        totals = {}
        tfoot = re.search(r'<tfoot>(.*?)</tfoot>', thtml, re.DOTALL)
        if tfoot:
            cells = re.findall(r'<(?:td|th)[^>]*data-stat="([^"]*)"[^>]*>(.*?)</(?:td|th)>', tfoot.group(1), re.DOTALL)
            totals = {k: re.sub(r'<[^>]+>', '', v).strip() for k, v in cells}

        teams.append({"sr_slug": slug, "players": players, "totals": totals})

    return teams if teams else None


def find_alt_url(team_slug, year):
    """If URL 404s, check team schedule for correct box score URL."""
    for path in [f"/cbb/schools/{team_slug}/men/{year}-schedule.html",
                 f"/cbb/schools/{team_slug}/{year}-schedule.html"]:
        url = f"https://www.sports-reference.com{path}"
        html = fetch(url)
        time.sleep(RATE_LIMIT)
        if not html:
            continue
        # Find March boxscore links
        links = re.findall(r'href="(/cbb/boxscores/\d{4}-03-\d{2}[^"]*\.html)"', html)
        links = list(dict.fromkeys(links))  # unique, preserve order
        # NCAA first round dates
        first_round = {
            2005: ['03-17','03-18'], 2006: ['03-16','03-17'], 2007: ['03-15','03-16'],
            2008: ['03-20','03-21'], 2009: ['03-19','03-20'], 2010: ['03-18','03-19'],
            2011: ['03-17','03-18'], 2012: ['03-15','03-16'], 2013: ['03-21','03-22'],
            2014: ['03-20','03-21'], 2015: ['03-19','03-20'], 2016: ['03-17','03-18'],
            2017: ['03-16','03-17'], 2018: ['03-15','03-16'], 2019: ['03-21','03-22'],
            2021: ['03-19','03-20'], 2022: ['03-17','03-18'], 2023: ['03-16','03-17'],
            2024: ['03-21','03-22'], 2025: ['03-20','03-21'],
        }
        dates = first_round.get(year, [])
        for link in links:
            for d in dates:
                if f"{year}-{d}" in link:
                    return f"https://www.sports-reference.com{link}"
        # Fallback: last March link with team slug
        team_links = [l for l in links if team_slug in l]
        if team_links:
            return f"https://www.sports-reference.com{team_links[-1]}"
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--start", type=int, default=0, help="Start index")
    args = parser.parse_args()

    # Load existing output
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE) as f:
            output = json.load(f)
        print(f"Loaded {len(output)} existing entries")
    else:
        output = {}

    # Load game URLs
    with open(GAMES_FILE) as f:
        games = json.load(f)

    print(f"Total games to scrape: {len(games)}")

    scraped = 0
    errors = []

    for i, game in enumerate(games):
        if i < args.start:
            continue

        key = game["key"]
        if key in output:
            continue

        if args.limit and scraped >= args.limit:
            break

        url = game["boxscore_url"]
        print(f"\n[{i+1}/{len(games)}] {key}")
        print(f"  URL: {url}")

        time.sleep(RATE_LIMIT)
        html = fetch(url)

        if not html:
            # Try alternate URL via schedule page
            print(f"  404, trying schedule lookup...")
            time.sleep(RATE_LIMIT)
            alt_url = find_alt_url(game["loser_slug"], game["year"])
            if alt_url:
                print(f"  Alt URL: {alt_url}")
                time.sleep(RATE_LIMIT)
                html = fetch(alt_url)
                if html:
                    url = alt_url

        if not html:
            print(f"  FAILED")
            errors.append(key)
            continue

        teams = parse_boxscore(html)
        if not teams:
            print(f"  FAILED: no box score tables")
            errors.append(key)
            continue

        # Build output entry
        score_parts = game["score"].split("-")
        w_score, l_score = int(score_parts[0]), int(score_parts[1])

        teams_out = []
        for t in teams:
            slug = t["sr_slug"]
            ws = game["winner_slug"]
            ls = game["loser_slug"]
            is_winner = (slug == ws or ws in slug or slug in ws)

            teams_out.append({
                "name": game["winner_full"] if is_winner else game["loser_full"],
                "seed": game["winner_seed"] if is_winner else game["loser_seed"],
                "score": w_score if is_winner else l_score,
                "players": t["players"],
                "totals": t["totals"],
            })

        output[key] = {
            "source": "sports-reference",
            "url": url,
            "year": game["year"],
            "matchup": game["matchup"],
            "teams": teams_out,
        }

        scraped += 1
        nplayers = sum(len(t["players"]) for t in teams)
        print(f"  OK: {len(teams)} teams, {nplayers} players")

        # Save after each
        with open(OUTPUT_FILE, "w") as f:
            json.dump(output, f, indent=2)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Scraped: {scraped} new | Total: {len(output)}")
    if errors:
        print(f"Errors ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
