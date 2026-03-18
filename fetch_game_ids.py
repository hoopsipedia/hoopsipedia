#!/usr/bin/env python3
"""
Fetch ESPN game IDs for postseason + significant regular season games
for all teams in games.json.

Strategy:
1. Fetch postseason schedules (seasontype=3) for years 2006-2026
2. Fetch regular season schedules (seasontype=2) for recent years 2022-2026
3. From regular season, pick biggest point differential games
4. Deduplicate (same game on both teams' schedules)
5. Save mapping to game_ids_bulk.json
"""

import json
import time
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime

BASE_DIR = "/Users/joshdavis/Projects/hoopsipedia"
OUTPUT_FILE = os.path.join(BASE_DIR, "game_ids_bulk.json")
PROGRESS_FILE = os.path.join(BASE_DIR, "game_ids_progress.json")

ESPN_SCHEDULE_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/{team_id}/schedule?season={year}&seasontype={stype}"

DELAY = 0.3  # seconds between requests

def load_team_ids():
    """Load all team ESPN IDs from games.json"""
    with open(os.path.join(BASE_DIR, "games.json")) as f:
        data = json.load(f)
    team_ids = list(data.keys())
    print(f"Loaded {len(team_ids)} teams from games.json")
    return team_ids

def load_progress():
    """Load progress from previous run if exists"""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"games": {}, "fetched_schedules": [], "errors": []}

def save_progress(progress):
    """Save progress to file"""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f)

def save_final(games):
    """Save final output file"""
    output = {
        "_metadata": {
            "count": len(games),
            "lastUpdated": datetime.now().strftime("%Y-%m-%d")
        },
        "games": games
    }
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved {len(games)} games to {OUTPUT_FILE}")

def fetch_json(url):
    """Fetch JSON from URL with error handling"""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # Team didn't exist that year or no postseason
        raise
    except Exception as e:
        return None

def extract_games_from_schedule(schedule_data, season_type):
    """Extract game info from ESPN schedule response"""
    games = {}
    if not schedule_data:
        return games

    events = schedule_data.get("events", [])
    if not events:
        return games

    for event in events:
        game_id = event.get("id")
        if not game_id:
            continue

        date = event.get("date", "")[:10]  # YYYY-MM-DD

        competitions = event.get("competitions", [{}])
        if not competitions:
            continue
        comp = competitions[0]

        competitors = comp.get("competitors", [])
        if len(competitors) < 2:
            continue

        teams_info = []
        for c in competitors:
            team = c.get("team", {})
            team_id = team.get("id", "")
            score = c.get("score", {})
            if isinstance(score, dict):
                pts = score.get("value", 0)
            else:
                try:
                    pts = int(score) if score else 0
                except (ValueError, TypeError):
                    pts = 0

            winner = c.get("winner", False)
            teams_info.append({
                "id": str(team_id),
                "score": pts,
                "winner": winner
            })

        # Determine game type
        game_type = "postseason" if season_type == 3 else "regular"

        # Check if it's NCAA tournament
        notes = event.get("notes", [])
        note_text = ""
        if notes:
            note_text = notes[0].get("headline", "").lower() if isinstance(notes[0], dict) else ""

        if "ncaa" in note_text or "march madness" in note_text:
            game_type = "ncaa"
        elif "nit" in note_text:
            game_type = "nit"
        elif season_type == 3:
            # Check if conference tournament
            if "conference" in note_text or "tournament" in note_text:
                game_type = "conf_tourney"
            else:
                game_type = "postseason"

        # Sort teams by ID for consistent key
        teams_info.sort(key=lambda x: x["id"])

        games[game_id] = {
            "date": date,
            "t1": teams_info[0]["id"],
            "t2": teams_info[1]["id"],
            "s1": teams_info[0].get("score", 0),
            "s2": teams_info[1].get("score", 0),
            "type": game_type
        }

    return games

def main():
    team_ids = load_team_ids()
    progress = load_progress()
    all_games = progress.get("games", {})
    fetched = set(progress.get("fetched_schedules", []))
    errors = progress.get("errors", [])

    # Phase 1: Postseason schedules (2006-2026)
    postseason_years = list(range(2026, 2005, -1))  # Most recent first

    # Phase 2: Regular season for recent years (for big games)
    regular_years = [2026, 2025, 2024, 2023, 2022]

    # Build fetch list
    fetch_list = []
    for team_id in team_ids:
        for year in postseason_years:
            key = f"{team_id}_post_{year}"
            if key not in fetched:
                fetch_list.append((team_id, year, 3, key))

    for team_id in team_ids:
        for year in regular_years:
            key = f"{team_id}_reg_{year}"
            if key not in fetched:
                fetch_list.append((team_id, year, 2, key))

    total = len(fetch_list)
    print(f"Need to fetch {total} schedules ({len(fetched)} already done)")
    print(f"Currently have {len(all_games)} unique games")

    request_count = 0
    games_before = len(all_games)

    for i, (team_id, year, stype, key) in enumerate(fetch_list):
        url = ESPN_SCHEDULE_URL.format(team_id=team_id, year=year, stype=stype)

        try:
            data = fetch_json(url)
            if data:
                new_games = extract_games_from_schedule(data, stype)
                # For regular season, only keep games with large point differentials
                if stype == 2:
                    filtered = {}
                    for gid, g in new_games.items():
                        diff = abs(g.get("s1", 0) - g.get("s2", 0))
                        # Keep games with 15+ point differential or that involve our teams
                        if diff >= 15:
                            filtered[gid] = g
                    # Also keep close games (potential buzzer beaters)
                    for gid, g in new_games.items():
                        diff = abs(g.get("s1", 0) - g.get("s2", 0))
                        if diff <= 3 and g.get("s1", 0) > 0:
                            g["type"] = "close"
                            filtered[gid] = g
                    new_games = filtered

                all_games.update(new_games)

            fetched.add(key)
            request_count += 1

            # Progress logging
            if request_count % 50 == 0:
                new_count = len(all_games) - games_before
                print(f"  [{request_count}/{total}] {len(all_games)} games total (+{new_count} new) | team={team_id} year={year} type={'post' if stype==3 else 'reg'}")

            # Save progress every 200 requests
            if request_count % 200 == 0:
                progress["games"] = all_games
                progress["fetched_schedules"] = list(fetched)
                progress["errors"] = errors
                save_progress(progress)
                print(f"  [SAVED PROGRESS] {len(all_games)} games")

            time.sleep(DELAY)

        except Exception as e:
            err_msg = f"Error {team_id}/{year}/{stype}: {str(e)}"
            errors.append(err_msg)
            if request_count % 100 == 0:
                print(f"  ERROR: {err_msg}")
            time.sleep(1)  # Extra delay on error

    # Final save
    print(f"\n=== COMPLETE ===")
    print(f"Total requests: {request_count}")
    print(f"Total unique games: {len(all_games)}")
    print(f"New games found: {len(all_games) - games_before}")
    print(f"Errors: {len(errors)}")

    # Count by type
    type_counts = {}
    for g in all_games.values():
        t = g.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    print(f"By type: {type_counts}")

    # Save final output
    save_final(all_games)

    # Save progress too
    progress["games"] = all_games
    progress["fetched_schedules"] = list(fetched)
    progress["errors"] = errors
    save_progress(progress)

if __name__ == "__main__":
    main()
