#!/usr/bin/env python3
"""
Scrape box score data from Sports Reference for pre-2005 NCAA tournament upsets.
Sports Reference rate limit: ~20 req/min, so we use 3+ second delays.

URL pattern: https://www.sports-reference.com/cbb/boxscores/{YYYY-MM-DD}-{loser-slug}.html
The "loser" in an upset is the higher seed, which SR typically treats as the home team.
"""

import json
import time
import re
import sys
import os
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from html.parser import HTMLParser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UPSET_HISTORY = os.path.join(SCRIPT_DIR, "upset_history.json")
ESPN_TO_SR = os.path.join(SCRIPT_DIR, "espn_to_sr.json")
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "sr_boxscores.json")

# NCAA tournament first round date ranges by year
# These are approximate; the script will try multiple dates
TOURNEY_DATES = {
    1985: ["1985-03-14", "1985-03-15"],
    1986: ["1986-03-13", "1986-03-14"],
    1987: ["1987-03-12", "1987-03-13", "1987-03-19", "1987-03-20"],
    1988: ["1988-03-17", "1988-03-18"],
    1989: ["1989-03-16", "1989-03-17"],
    1990: ["1990-03-15", "1990-03-16"],
    1991: ["1991-03-14", "1991-03-15"],
    1992: ["1992-03-19", "1992-03-20"],
    1993: ["1993-03-18", "1993-03-19"],
    1994: ["1994-03-17", "1994-03-18"],
    1995: ["1995-03-16", "1995-03-17"],
    1996: ["1996-03-14", "1996-03-15"],
    1997: ["1997-03-13", "1997-03-14"],
    1998: ["1998-03-12", "1998-03-13"],
    1999: ["1999-03-11", "1999-03-12"],
    2000: ["2000-03-16", "2000-03-17"],
    2001: ["2001-03-15", "2001-03-16"],
    2002: ["2002-03-14", "2002-03-15"],
    2003: ["2003-03-20", "2003-03-21"],
    2004: ["2004-03-18", "2004-03-19"],
}

# Manual name-to-SR-slug mapping for teams not easily derived
TEAM_SR_SLUGS = {
    "Richmond Spiders": "richmond",
    "Syracuse Orange": "syracuse",
    "Santa Clara Broncos": "santa-clara",
    "Arizona Wildcats": "arizona",
    "Coppin State Eagles": "coppin-state",
    "South Carolina Gamecocks": "south-carolina",
    "Hampton Pirates": "hampton",
    "Iowa State Cyclones": "iowa-state",
    "Cleveland State Vikings": "cleveland-state",
    "Indiana Hoosiers": "indiana",
    "Arkansas-Little Rock Trojans": "arkansas-little-rock",
    "Notre Dame Fighting Irish": "notre-dame",
    "Austin Peay Governors": "austin-peay",
    "Illinois Fighting Illini": "illinois",
    "Murray State Racers": "murray-state",
    "NC State Wolfpack": "north-carolina-state",
    "Siena Saints": "siena",
    "Stanford Cardinal": "stanford",
    "Northern Iowa Panthers": "northern-iowa",
    "Missouri Tigers": "missouri",
    "Xavier Musketeers": "xavier",
    "Nebraska Cornhuskers": "nebraska",
    "East Tennessee State Buccaneers": "east-tennessee-state",
    "Old Dominion Monarchs": "old-dominion",
    "Villanova Wildcats": "villanova",
    "Weber State Wildcats": "weber-state",
    "Michigan State Spartans": "michigan-state",
    "Chattanooga Mocs": "chattanooga",
    "Georgia Bulldogs": "georgia",
    "South Carolina Gamecocks": "south-carolina",
    "North Carolina Tar Heels": "north-carolina",
    "Navy Midshipmen": "navy",
    "LSU Tigers": "louisiana-state",
    "Southwest Missouri State Bears": "southwest-missouri-state",
    "Clemson Tigers": "clemson",
    "Penn State Nittany Lions": "penn-state",
    "UCLA Bruins": "ucla",
    "Southwest Louisiana Ragin' Cajuns": "southwestern-louisiana",
    "Oklahoma Sooners": "oklahoma",
    "Southern Jaguars": "southern",
    "Georgia Tech Yellow Jackets": "georgia-tech",
    "Wisconsin-Green Bay Phoenix": "green-bay",
    "California Golden Bears": "california",
    "Manhattan Jaspers": "manhattan",
    "Princeton Tigers": "princeton",
    "College of Charleston Cougars": "college-of-charleston",
    "Maryland Terrapins": "maryland",
    "Valparaiso Crusaders": "valparaiso",
    "Ole Miss Rebels": "mississippi",
    "Kent State Golden Flashes": "kent-state",
    "Indiana State Sycamores": "indiana-state",
    "UNC Wilmington Seahawks": "unc-wilmington",
    "USC Trojans": "southern-california",
    "Tulsa Golden Hurricane": "tulsa",
    "Dayton Flyers": "dayton",
    "Kentucky Wildcats": "kentucky",
    "Washington Huskies": "washington",
    "DePaul Blue Demons": "depaul",
    "Virginia Cavaliers": "virginia",
    "Wyoming Cowboys": "wyoming",
    "South Alabama Jaguars": "south-alabama",
    "Alabama Crimson Tide": "alabama",
    "Minnesota Golden Gophers": "minnesota",
    "Kansas State Wildcats": "kansas-state",
    "Ball State Cardinals": "ball-state",
    "Oregon State Beavers": "oregon-state",
    "Eastern Michigan Eagles": "eastern-michigan",
    "Mississippi State Bulldogs": "mississippi-state",
    "Temple Owls": "temple",
    "Purdue Boilermakers": "purdue",
    "New Mexico State Aggies": "new-mexico-state",
    "George Washington Colonials": "george-washington",
    "New Mexico Lobos": "new-mexico",
    "Miami (OH) RedHawks": "miami-oh",
    "Drexel Dragons": "drexel",
    "Memphis Tigers": "memphis",
    "TCU Horned Frogs": "texas-christian",
    "Florida State Seminoles": "florida-state",
    "Charlotte 49ers": "charlotte",
    "Wisconsin Badgers": "wisconsin",
    "Utah State Aggies": "utah-state",
    "Ohio State Buckeyes": "ohio-state",
    "Creighton Bluejays": "creighton",
    "Miami Hurricanes": "miami-fl",
    "Oregon Ducks": "oregon",
    "Wake Forest Demon Deacons": "wake-forest",
    "Florida Gators": "florida",
    "Butler Bulldogs": "butler",
    "Nevada Wolf Pack": "nevada",
    "Gonzaga Bulldogs": "gonzaga",
    "Pacific Tigers": "pacific",
    "Providence Friars": "providence",
    "Tulsa Golden Hurricane": "tulsa",
    "Arkansas-Little Rock Trojans": "arkansas-little-rock",
    "Purdue Boilermakers": "purdue",
    "College of Charleston Cougars": "college-of-charleston",
}


def team_slug(full_name):
    """Generate URL-friendly slug from team name, matching JS teamSlug()."""
    return re.sub(r'(^-|-$)', '', re.sub(r'[^a-z0-9]+', '-', full_name.lower()))


def get_sr_slug(full_name):
    """Get Sports Reference slug for a team."""
    if full_name in TEAM_SR_SLUGS:
        return TEAM_SR_SLUGS[full_name]
    # Fallback: derive from name
    # Remove mascot: "Duke Blue Devils" -> "duke"
    # This is imperfect but helps for simple cases
    slug = team_slug(full_name)
    return slug


def fetch_page(url):
    """Fetch a page with proper headers, return HTML string or None."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=15) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except HTTPError as e:
        if e.code == 404:
            return None
        if e.code == 429:
            print(f"  Rate limited! Waiting 60s...")
            time.sleep(60)
            return fetch_page(url)
        print(f"  HTTP {e.code} for {url}")
        return None
    except URLError as e:
        print(f"  URL error: {e.reason}")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


def parse_box_score(html, winner_name, loser_name, winner_seed, loser_seed, score_str):
    """Parse SR box score HTML and extract player stats."""
    if not html:
        return None

    # Parse the winner and loser scores from the score string
    parts = score_str.split('-')
    winner_score = int(parts[0])
    loser_score = int(parts[1]) if len(parts) > 1 else 0

    result = {
        "source": "sports-reference",
        "teams": []
    }

    # SR box scores have two tables with id like "box-score-basic-{slug}"
    # Find all basic box score tables
    # Pattern: <table ... id="box-score-basic-{slug}" ...>
    table_pattern = re.compile(
        r'<table[^>]*id="box-score-basic-([^"]*)"[^>]*>(.*?)</table>',
        re.DOTALL
    )
    tables = table_pattern.findall(html)

    if len(tables) < 2:
        # Try alternate pattern - sometimes tables use different id format
        table_pattern2 = re.compile(
            r'<table[^>]*class="[^"]*stats_table[^"]*"[^>]*>(.*?)</table>',
            re.DOTALL
        )
        tables_alt = table_pattern2.findall(html)
        if len(tables_alt) >= 2:
            tables = [("team1", tables_alt[0]), ("team2", tables_alt[1])]

    if len(tables) < 2:
        return None

    # Extract team names from the page to match winner/loser
    # SR uses <h1> or team name divs
    team_names_in_order = []

    for table_slug, table_html in tables:
        team_data = parse_team_table(table_html, table_slug)
        if team_data:
            team_names_in_order.append(team_data)

    if len(team_names_in_order) < 2:
        return None

    # Try to match teams to winner/loser
    # The first table is usually the away team (winner in upsets often)
    # We'll match by checking which team name is closer to winner/loser
    for i, td in enumerate(team_names_in_order):
        team_name_lower = td.get("detected_name", "").lower()
        winner_lower = winner_name.lower()
        loser_lower = loser_name.lower()

        # Check if this team is the winner or loser
        winner_words = set(winner_lower.split())
        loser_words = set(loser_lower.split())
        name_words = set(team_name_lower.replace('-', ' ').split())

        winner_match = len(winner_words & name_words)
        loser_match = len(loser_words & name_words)

        if winner_match > loser_match:
            td["is_winner"] = True
            td["name"] = winner_name
            td["seed"] = winner_seed
            td["score"] = winner_score
        else:
            td["is_winner"] = False
            td["name"] = loser_name
            td["seed"] = loser_seed
            td["score"] = loser_score

    # Ensure winner is first in the output
    team_names_in_order.sort(key=lambda x: not x.get("is_winner", False))

    for td in team_names_in_order:
        team_out = {
            "name": td["name"],
            "seed": td["seed"],
            "score": td["score"],
            "players": td.get("players", []),
            "totals": td.get("totals", {})
        }
        result["teams"].append(team_out)

    return result


def parse_team_table(table_html, table_slug):
    """Parse a single team's box score table."""
    team_data = {
        "detected_name": table_slug.replace('-', ' '),
        "players": [],
        "totals": {}
    }

    # Find header row to get column indices
    # Headers are in <thead>
    thead_match = re.search(r'<thead>(.*?)</thead>', table_html, re.DOTALL)
    if not thead_match:
        return None

    # Get column headers from the last <tr> in thead (some have multi-row headers)
    header_rows = re.findall(r'<tr[^>]*>(.*?)</tr>', thead_match.group(1), re.DOTALL)
    if not header_rows:
        return None

    last_header = header_rows[-1]
    headers = re.findall(r'<th[^>]*>(.*?)</th>', last_header, re.DOTALL)
    # Clean HTML from headers
    headers = [re.sub(r'<[^>]+>', '', h).strip() for h in headers]

    # Map column names to indices
    col_map = {}
    for i, h in enumerate(headers):
        h_upper = h.upper().strip()
        if h_upper in ('MP', 'MIN'):
            col_map['min'] = i
        elif h_upper == 'FG':
            col_map['fg_made'] = i
        elif h_upper == 'FGA':
            col_map['fg_att'] = i
        elif h_upper in ('3P', '3FG'):
            col_map['tp_made'] = i
        elif h_upper in ('3PA', '3FGA'):
            col_map['tp_att'] = i
        elif h_upper == 'FT':
            col_map['ft_made'] = i
        elif h_upper == 'FTA':
            col_map['ft_att'] = i
        elif h_upper in ('TRB', 'REB'):
            col_map['reb'] = i
        elif h_upper == 'ORB':
            col_map['orb'] = i
        elif h_upper == 'DRB':
            col_map['drb'] = i
        elif h_upper == 'AST':
            col_map['ast'] = i
        elif h_upper == 'STL':
            col_map['stl'] = i
        elif h_upper == 'BLK':
            col_map['blk'] = i
        elif h_upper in ('TOV', 'TO'):
            col_map['to'] = i
        elif h_upper == 'PTS':
            col_map['pts'] = i
        elif h_upper == 'PF':
            col_map['pf'] = i

    # Find tbody rows
    tbody_match = re.search(r'<tbody>(.*?)</tbody>', table_html, re.DOTALL)
    if not tbody_match:
        return None

    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbody_match.group(1), re.DOTALL)

    for row in rows:
        # Skip separator rows
        if 'class="thead"' in row or 'Reserves' in row or 'Starters' in row:
            continue

        cells = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row, re.DOTALL)
        if not cells or len(cells) < 3:
            continue

        # First cell is player name (in <th> or <td>)
        player_name = re.sub(r'<[^>]+>', '', cells[0]).strip()

        # Check if this is the totals row
        if player_name.lower() in ('team totals', 'totals', 'school totals', 'total'):
            totals = {}
            def safe_int(idx_name):
                if idx_name in col_map and col_map[idx_name] < len(cells):
                    val = re.sub(r'<[^>]+>', '', cells[col_map[idx_name]]).strip()
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        return 0
                return 0

            fg_m = safe_int('fg_made')
            fg_a = safe_int('fg_att')
            tp_m = safe_int('tp_made')
            tp_a = safe_int('tp_att')
            ft_m = safe_int('ft_made')
            ft_a = safe_int('ft_att')

            totals['pts'] = safe_int('pts')
            totals['fg'] = f"{fg_m}-{fg_a}"
            totals['tp'] = f"{tp_m}-{tp_a}"
            totals['ft'] = f"{ft_m}-{ft_a}"
            totals['reb'] = safe_int('reb')
            if totals['reb'] == 0 and 'orb' in col_map and 'drb' in col_map:
                totals['reb'] = safe_int('orb') + safe_int('drb')
            totals['ast'] = safe_int('ast')
            totals['stl'] = safe_int('stl')
            totals['blk'] = safe_int('blk')
            totals['to'] = safe_int('to')
            team_data['totals'] = totals
            continue

        # Skip "Did Not Play" rows
        if 'Did Not Play' in row or 'did not play' in row.lower():
            continue

        # Regular player row
        player = {"name": player_name}

        def get_val(idx_name):
            if idx_name in col_map and col_map[idx_name] < len(cells):
                val = re.sub(r'<[^>]+>', '', cells[col_map[idx_name]]).strip()
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return 0
            return 0

        def get_str(idx_name):
            if idx_name in col_map and col_map[idx_name] < len(cells):
                return re.sub(r'<[^>]+>', '', cells[col_map[idx_name]]).strip()
            return "0"

        # Minutes - might be "MM:SS" format on SR
        if 'min' in col_map and col_map['min'] < len(cells):
            min_str = re.sub(r'<[^>]+>', '', cells[col_map['min']]).strip()
            if ':' in min_str:
                parts = min_str.split(':')
                player['min'] = int(parts[0]) + (1 if int(parts[1]) >= 30 else 0)
            else:
                try:
                    player['min'] = int(min_str)
                except (ValueError, TypeError):
                    player['min'] = 0
        else:
            player['min'] = 0

        player['pts'] = get_val('pts')

        fg_m = get_val('fg_made')
        fg_a = get_val('fg_att')
        player['fg'] = f"{fg_m}-{fg_a}"

        tp_m = get_val('tp_made')
        tp_a = get_val('tp_att')
        player['tp'] = f"{tp_m}-{tp_a}"

        ft_m = get_val('ft_made')
        ft_a = get_val('ft_att')
        player['ft'] = f"{ft_m}-{ft_a}"

        player['reb'] = get_val('reb')
        if player['reb'] == 0 and 'orb' in col_map and 'drb' in col_map:
            player['reb'] = get_val('orb') + get_val('drb')

        player['ast'] = get_val('ast')
        player['stl'] = get_val('stl')
        player['blk'] = get_val('blk')
        player['to'] = get_val('to')

        team_data['players'].append(player)

    return team_data


def find_boxscore_url(year, loser_full, winner_full):
    """Try to find the correct SR box score URL by trying different dates and slug variants."""
    loser_slug = get_sr_slug(loser_full)
    winner_slug = get_sr_slug(winner_full)

    dates = TOURNEY_DATES.get(year, [])
    if not dates:
        # Generate fallback dates
        dates = [f"{year}-03-{d:02d}" for d in range(12, 22)]

    # Try loser slug first (higher seed = home team on SR), then winner slug
    slugs_to_try = [loser_slug, winner_slug]

    for date in dates:
        for slug in slugs_to_try:
            url = f"https://www.sports-reference.com/cbb/boxscores/{date}-{slug}.html"
            print(f"  Trying: {url}")
            html = fetch_page(url)
            time.sleep(3.5)  # Rate limit

            if html:
                # Verify this is the right game by checking both team names appear
                html_lower = html.lower()
                # Check for either team name (short version)
                loser_short = loser_full.split()[-1].lower() if loser_full else ""
                winner_short = winner_full.split()[-1].lower() if winner_full else ""
                # Also check first word for uniqueness
                loser_first = loser_full.split()[0].lower() if loser_full else ""
                winner_first = winner_full.split()[0].lower() if winner_full else ""

                if (loser_short in html_lower or loser_first in html_lower) and \
                   (winner_short in html_lower or winner_first in html_lower):
                    print(f"  FOUND! {url}")
                    return url, html

                # Even if name check is loose, if we got a valid page with box score tables, use it
                if 'box-score-basic' in html_lower or 'stats_table' in html_lower:
                    print(f"  Found page (weak name match): {url}")
                    return url, html

    return None, None


def get_pre_2005_upsets(upset_data):
    """Extract all upsets from years 1985-2004."""
    upsets = []
    for matchup_key, matchup_data in upset_data.items():
        if matchup_key == "metadata":
            continue
        for upset in matchup_data.get("upsets", []):
            year = upset.get("year", 0)
            if 1985 <= year <= 2004:
                upsets.append({
                    "year": year,
                    "matchup": matchup_key,
                    "winner": upset.get("winner", ""),
                    "winnerFull": upset.get("winnerFull", ""),
                    "winnerSeed": upset.get("winnerSeed", 0),
                    "loser": upset.get("loser", ""),
                    "loserFull": upset.get("loserFull", ""),
                    "loserSeed": upset.get("loserSeed", 0),
                    "score": upset.get("score", ""),
                    "notes": upset.get("notes", ""),
                })
    # Sort by year, then by how "big" the upset was (lower matchup number = bigger upset)
    matchup_order = {"1v16": 0, "2v15": 1, "3v14": 2, "4v13": 3, "5v12": 4, "6v11": 5, "7v10": 6, "8v9": 7}
    upsets.sort(key=lambda x: (x["year"], matchup_order.get(x["matchup"], 99)))
    return upsets


def main():
    # Load upset history
    with open(UPSET_HISTORY, 'r') as f:
        upset_data = json.load(f)

    # Load existing results if any
    existing = {}
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r') as f:
            existing = json.load(f)

    upsets = get_pre_2005_upsets(upset_data)
    print(f"Found {len(upsets)} pre-2005 upsets to scrape")

    # Prioritize the most iconic upsets
    iconic_keys = [
        # 2v15 upsets (rarest, most iconic)
        (1991, "Richmond Spiders"),      # First ever 15 over 2
        (1993, "Santa Clara Broncos"),    # Steve Nash
        (1997, "Coppin State Eagles"),
        (2001, "Hampton Pirates"),        # Hampton over Iowa State
        # 3v14
        (1986, "Cleveland State Vikings"),
        (1997, "Chattanooga Mocs"),
        (1998, "Richmond Spiders"),
        (1999, "Weber State Wildcats"),
        # 4v13
        (1985, "Navy Midshipmen"),        # David Robinson
        (1988, "Richmond Spiders"),
        (1996, "Princeton Tigers"),       # Pete Carril's last game
        (1998, "Valparaiso Crusaders"),   # Bryce Drew buzzer beater
        (2001, "Kent State Golden Flashes"),
    ]

    # Sort: iconic first, then the rest
    iconic_set = set(iconic_keys)
    iconic_upsets = [u for u in upsets if (u["year"], u["winnerFull"]) in iconic_set]
    other_upsets = [u for u in upsets if (u["year"], u["winnerFull"]) not in iconic_set]
    ordered_upsets = iconic_upsets + other_upsets

    found_count = 0
    not_found = []
    skipped = 0

    for upset in ordered_upsets:
        year = upset["year"]
        winner_slug = team_slug(upset["winnerFull"])
        loser_slug = team_slug(upset["loserFull"])
        game_key = f"{year}/{winner_slug}-vs-{loser_slug}"

        # Skip if already scraped
        if game_key in existing and existing[game_key].get("teams"):
            print(f"SKIP (already have): {game_key}")
            skipped += 1
            continue

        print(f"\n{'='*60}")
        print(f"Scraping: {upset['winnerFull']} ({upset['winnerSeed']}) vs {upset['loserFull']} ({upset['loserSeed']}) - {year}")
        print(f"Game key: {game_key}")
        print(f"Score: {upset['score']}")

        url, html = find_boxscore_url(year, upset["loserFull"], upset["winnerFull"])

        if html:
            box_data = parse_box_score(
                html,
                upset["winnerFull"],
                upset["loserFull"],
                upset["winnerSeed"],
                upset["loserSeed"],
                upset["score"]
            )

            if box_data and len(box_data.get("teams", [])) == 2:
                box_data["url"] = url
                box_data["matchup"] = upset["matchup"]
                box_data["year"] = year
                existing[game_key] = box_data
                found_count += 1
                print(f"  SUCCESS: {len(box_data['teams'][0].get('players', []))} + {len(box_data['teams'][1].get('players', []))} players")
            else:
                print(f"  FAILED to parse box score")
                not_found.append(game_key)
        else:
            print(f"  NOT FOUND on Sports Reference")
            not_found.append(game_key)

        # Save progress after each game
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(existing, f, indent=2)

    print(f"\n{'='*60}")
    print(f"RESULTS:")
    print(f"  Found: {found_count}")
    print(f"  Skipped (already had): {skipped}")
    print(f"  Not found: {len(not_found)}")
    if not_found:
        print(f"\nNot found games:")
        for gk in not_found:
            print(f"  - {gk}")


if __name__ == "__main__":
    main()
