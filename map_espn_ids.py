#!/usr/bin/env python3
"""
Map ESPN event IDs for NCAA tournament games 2002-2010 using team schedule API.

For each year, queries every known ESPN team's postseason schedule to find
NCAA tournament games. Outputs espn_tournament_ids_2002_2010.json.
"""

import json
import time
import urllib.request
import urllib.error
from collections import Counter
from datetime import date
from pathlib import Path

from json_io import save_json_atomic

BASE_DIR = Path(__file__).resolve().parent

TEAM_SCHEDULE_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/"
    "mens-college-basketball/teams/{team_id}/schedule?season={year}&seasontype=3"
)

DELAY = 0.5


def fetch_json(url, retries=3):
    """Fetch JSON from URL with retries."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
            if attempt < retries - 1:
                time.sleep(1)
    return None


def extract_score(competitor):
    """Extract numeric score from competitor data."""
    score = competitor.get("score")
    if score is None:
        return 0
    if isinstance(score, dict):
        val = score.get("value", score.get("displayValue", 0))
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return 0
    try:
        return int(float(score))
    except (ValueError, TypeError):
        return 0


def is_nit_or_other(notes_list):
    """Return True if notes indicate NIT/CBI/CIT (not NCAA tournament)."""
    if not notes_list:
        return False
    text = notes_list[0].get("headline", "").upper()
    if not text:
        return False
    for kw in ["NIT ", "NIT-", "CBI ", "CIT ", "VEGAS", "COLLEGEINSIDER"]:
        if kw in text:
            return True
    return False


def scan_year(year, espn_ids, skip_ids):
    """Query team schedules to find all tournament games for a year."""
    games = {}
    teams_with = 0

    print(f"\n--- {year} ---", flush=True)
    for i, tid in enumerate(espn_ids):
        if (i + 1) % 75 == 0:
            print(f"  {i+1}/{len(espn_ids)} teams checked, "
                  f"{len(games)} games found...", flush=True)

        data = fetch_json(TEAM_SCHEDULE_URL.format(team_id=tid, year=year))
        time.sleep(DELAY)
        if not data:
            continue

        found = False
        for event in data.get("events", []):
            eid = str(event.get("id", ""))
            if not eid or eid in skip_ids or eid in games:
                continue

            st = event.get("seasonType", {})
            if st.get("type") != 3:
                continue

            comps = event.get("competitions", [])
            if not comps:
                continue
            comp = comps[0]

            if is_nit_or_other(comp.get("notes", [])):
                continue

            competitors = comp.get("competitors", [])
            if len(competitors) < 2:
                continue

            t1 = str(competitors[0].get("team", {}).get("id", ""))
            t2 = str(competitors[1].get("team", {}).get("id", ""))
            s1 = extract_score(competitors[0])
            s2 = extract_score(competitors[1])
            gdate = comp.get("date", event.get("date", ""))[:10]

            games[eid] = {
                "date": gdate,
                "t1": t1,
                "t2": t2,
                "s1": s1,
                "s2": s2,
                "type": "postseason",
            }
            found = True

        if found:
            teams_with += 1

    print(f"  {year}: {len(games)} games from {teams_with} teams", flush=True)
    return games


def main():
    # Load existing
    bulk_path = BASE_DIR / "game_ids_bulk.json"
    existing_ids = set()
    if bulk_path.exists():
        with open(bulk_path) as f:
            existing_ids = set(json.load(f).get("games", {}).keys())
    print(f"Existing game IDs: {len(existing_ids)}", flush=True)

    # Load ESPN team IDs
    espn_sr_path = BASE_DIR / "espn_to_sr.json"
    espn_ids = []
    if espn_sr_path.exists():
        with open(espn_sr_path) as f:
            espn_ids = sorted(json.load(f).keys(), key=lambda x: int(x))
    print(f"ESPN team IDs: {len(espn_ids)}", flush=True)

    all_games = {}
    for year in range(2002, 2011):
        skip = existing_ids | set(all_games.keys())
        year_games = scan_year(year, espn_ids, skip)
        all_games.update(year_games)
        print(f"  Running total: {len(all_games)} games", flush=True)

    # Save
    output = {
        "_metadata": {
            "description": "ESPN tournament game IDs for 2002-2010",
            "source": "ESPN Team Schedule API (seasontype=3)",
            "generated": date.today().isoformat(),
            "total_games": len(all_games),
        },
        "games": all_games,
    }
    out_path = BASE_DIR / "espn_tournament_ids_2002_2010.json"
    save_json_atomic(out_path, output, indent=2)

    # Summary
    print(f"\n{'='*60}", flush=True)
    print("RESULTS", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"Total games: {len(all_games)}", flush=True)
    yc = Counter(g["date"][:4] for g in all_games.values())
    for yr in sorted(yc):
        print(f"  {yr}: {yc[yr]} games", flush=True)
    overlap = set(all_games.keys()) & existing_ids
    print(f"Overlap with existing: {len(overlap)}", flush=True)
    print(f"Truly new: {len(all_games) - len(overlap)}", flush=True)
    print(f"Saved to: {out_path}", flush=True)


if __name__ == "__main__":
    main()
