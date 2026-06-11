#!/usr/bin/env python3
"""
Shared Sports Reference fetching/parsing library for Hoopsipedia box score scrapers.

Consolidates the common logic that previously lived in three scripts:
  - scrape_boxscores.py        (BeautifulSoup parser — the canonical implementation)
  - scrape_modern_boxscores.py (404 schedule-page fallback for 2005+ games)
  - scrape_sr_boxscores.py     (team-name -> SR slug mappings, tournament dates, pre-2005)

Entry point: scrape_boxscores.py. This module makes no network requests on import.

Rate limiting: SRFetcher enforces a minimum of MIN_REQUEST_INTERVAL (4.0s)
between requests and backs off on HTTP 429 (honoring Retry-After when present).
All JSON writes go through json_io.save_json_atomic.
"""

import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from json_io import save_json_atomic

DATA_DIR = Path(__file__).parent
SR_BASE = "https://www.sports-reference.com/cbb"
MIN_REQUEST_INTERVAL = 4.0  # hard floor: seconds between requests to SR

USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15'
)

# ---------------------------------------------------------------------------
# NCAA tournament first-round dates by year (MM-DD), used when guessing or
# verifying box score URLs from schedule pages. 1985-2004 absorbed from
# scrape_sr_boxscores.py TOURNEY_DATES; 2005-2025 from scrape_modern_boxscores.py.
# ---------------------------------------------------------------------------
FIRST_ROUND_DATES = {
    1985: ['03-14', '03-15'],
    1986: ['03-13', '03-14'],
    1987: ['03-12', '03-13', '03-19', '03-20'],
    1988: ['03-17', '03-18'],
    1989: ['03-16', '03-17'],
    1990: ['03-15', '03-16'],
    1991: ['03-14', '03-15'],
    1992: ['03-19', '03-20'],
    1993: ['03-18', '03-19'],
    1994: ['03-17', '03-18'],
    1995: ['03-16', '03-17'],
    1996: ['03-14', '03-15'],
    1997: ['03-13', '03-14'],
    1998: ['03-12', '03-13'],
    1999: ['03-11', '03-12'],
    2000: ['03-16', '03-17'],
    2001: ['03-15', '03-16'],
    2002: ['03-14', '03-15'],
    2003: ['03-20', '03-21'],
    2004: ['03-18', '03-19'],
    2005: ['03-17', '03-18'],
    2006: ['03-16', '03-17'],
    2007: ['03-15', '03-16'],
    2008: ['03-20', '03-21'],
    2009: ['03-19', '03-20'],
    2010: ['03-18', '03-19'],
    2011: ['03-17', '03-18'],
    2012: ['03-15', '03-16'],
    2013: ['03-21', '03-22'],
    2014: ['03-20', '03-21'],
    2015: ['03-19', '03-20'],
    2016: ['03-17', '03-18'],
    2017: ['03-16', '03-17'],
    2018: ['03-15', '03-16'],
    2019: ['03-21', '03-22'],
    2021: ['03-19', '03-20'],
    2022: ['03-17', '03-18'],
    2023: ['03-16', '03-17'],
    2024: ['03-21', '03-22'],
    2025: ['03-20', '03-21'],
}

# ---------------------------------------------------------------------------
# Manual full-team-name -> SR slug mapping for teams whose slug can't be
# derived mechanically from the name. Absorbed from scrape_sr_boxscores.py.
# ---------------------------------------------------------------------------
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
}


# ---------------------------------------------------------------------------
# JSON helpers (all writes are atomic)
# ---------------------------------------------------------------------------

def load_json(filename):
    """Load a JSON file from the data dir; return {} if missing."""
    path = DATA_DIR / filename
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def save_json(filename, data):
    """Atomically save JSON to the data dir."""
    path = DATA_DIR / filename
    save_json_atomic(path, data, indent=2, ensure_ascii=False)
    print(f"  Saved {len(data)} entries to {filename}")


# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------

def team_slug(full_name):
    """Generate URL-friendly slug from team name, matching JS teamSlug()."""
    return re.sub(r'(^-|-$)', '', re.sub(r'[^a-z0-9]+', '-', full_name.lower()))


def get_sr_slug(full_name):
    """Get the Sports Reference slug for a full team name."""
    if full_name in TEAM_SR_SLUGS:
        return TEAM_SR_SLUGS[full_name]
    # Fallback: derive mechanically from the name (imperfect for mascot names)
    return team_slug(full_name)


# ---------------------------------------------------------------------------
# Fetching (rate-limited, 429-aware)
# ---------------------------------------------------------------------------

class SRFetcher:
    """Rate-limited HTTP fetcher for sports-reference.com.

    Enforces a hard floor of MIN_REQUEST_INTERVAL seconds between requests
    and backs off on HTTP 429 (honoring Retry-After when present).
    """

    def __init__(self, delay=MIN_REQUEST_INTERVAL):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
        # Never allow callers to go faster than the SR-safe floor
        self.delay = max(float(delay), MIN_REQUEST_INTERVAL)
        self.last_request_time = 0
        self.request_count = 0

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request_time = time.time()

    def fetch(self, url, retries=5):
        """Fetch a URL with rate limiting and retries. Returns a Response or None."""
        self._rate_limit()
        self.request_count += 1

        for attempt in range(retries):
            try:
                resp = self.session.get(url, timeout=30)
                if resp.status_code == 429:
                    # Use Retry-After header if available, otherwise escalate
                    retry_after = resp.headers.get('Retry-After')
                    if retry_after:
                        wait = int(retry_after) + 5  # Add 5s buffer
                        print(f"    429 rate limited, Retry-After: {retry_after}s, waiting {wait}s...")
                    else:
                        wait = 90 * (attempt + 1)
                        print(f"    429 rate limited, waiting {wait}s...")
                    time.sleep(wait)
                    # Reset delay timer after long wait
                    self.last_request_time = time.time()
                    continue
                if resp.status_code == 404:
                    print(f"    404 not found: {url}")
                    return None
                if resp.status_code != 200:
                    print(f"    HTTP {resp.status_code}: {url}")
                    if attempt < retries - 1:
                        time.sleep(15)
                    continue
                return resp
            except requests.exceptions.RequestException as e:
                print(f"    Request error (attempt {attempt+1}): {e}")
                if attempt < retries - 1:
                    time.sleep(15)
        return None

    def fetch_text(self, url, retries=5):
        """Fetch a URL and return its body text, or None."""
        resp = self.fetch(url, retries=retries)
        return resp.text if resp is not None else None


# ---------------------------------------------------------------------------
# Parsing (BeautifulSoup, from the canonical scrape_boxscores.py implementation)
# ---------------------------------------------------------------------------

def parse_boxscore_html(html, url=''):
    """Parse a single SR box score page (HTML string) into structured JSON.

    Returns {"source": "sports-reference", "teams": [...]} or None.
    """
    soup = BeautifulSoup(html, 'html.parser')

    # Get teams and scores from scorebox
    scorebox = soup.find(class_='scorebox')
    if not scorebox:
        print(f"    No scorebox found on {url or 'page'}")
        return None

    team_divs = scorebox.find_all('div', recursive=False)
    teams_data = []

    for div in team_divs[:2]:
        team_info = {}
        # Team name
        strong = div.find('strong')
        if strong:
            link = strong.find('a')
            team_info['name'] = link.text.strip() if link else strong.text.strip()
            if link and link.get('href'):
                # Extract SR slug from href like /cbb/schools/connecticut/2024.html
                href = link['href']
                slug_match = re.search(r'/schools/([^/]+)/', href)
                if slug_match:
                    team_info['sr_slug'] = slug_match.group(1)

        # Score
        score_div = div.find(class_='score')
        if score_div:
            try:
                team_info['score'] = int(score_div.text.strip())
            except ValueError:
                team_info['score'] = 0

        teams_data.append(team_info)

    if len(teams_data) < 2:
        print(f"    Could not find 2 teams on {url or 'page'}")
        return None

    # Parse basic box score tables
    result = {"source": "sports-reference", "teams": []}

    for team_data in teams_data:
        sr_slug = team_data.get('sr_slug', '')
        team_entry = {
            "name": team_data.get('name', 'Unknown'),
            "score": team_data.get('score', 0),
            "players": [],
            "totals": {}
        }
        if sr_slug:
            team_entry['sr_slug'] = sr_slug

        # Find the basic box score table for this team
        table_id = f'box-score-basic-{sr_slug}'
        table = soup.find('table', id=table_id)

        if not table:
            # Try finding by partial match
            for t in soup.find_all('table'):
                tid = t.get('id', '')
                if tid.startswith('box-score-basic-') and sr_slug in tid:
                    table = t
                    break

        if not table:
            # Last resort: no table found for this team
            print(f"    Warning: No table found for {sr_slug}, trying fallback...")
            result['teams'].append(team_entry)
            continue

        # Parse header to get column indices
        thead = table.find('thead')
        if not thead:
            result['teams'].append(team_entry)
            continue

        header_rows = thead.find_all('tr')
        # Use the last header row (has actual stat names)
        stat_headers = [th.text.strip() for th in header_rows[-1].find_all('th')]

        # Parse player rows
        tbody = table.find('tbody')
        if tbody:
            for row in tbody.find_all('tr'):
                # Skip separator rows
                if 'class' in row.attrs and 'thead' in ' '.join(row.get('class', [])):
                    continue

                cells = row.find_all(['th', 'td'])
                if len(cells) < 5:
                    continue

                player_name = cells[0].text.strip()

                # Skip "Team Totals" row — handle separately
                if 'Totals' in player_name or 'Team' in player_name:
                    continue

                # Skip "Reserves" header
                if player_name in ('Reserves', 'Starters', ''):
                    continue

                player = {"name": player_name}

                # Map columns to stats
                for i, cell in enumerate(cells[1:], 1):
                    if i < len(stat_headers):
                        header = stat_headers[i]
                        val = cell.text.strip()

                        if header == 'MP':
                            try:
                                player['min'] = int(val) if val else 0
                            except ValueError:
                                # Handle MM:SS format
                                if ':' in val:
                                    parts = val.split(':')
                                    player['min'] = int(parts[0])
                                else:
                                    player['min'] = 0
                        elif header == 'PTS':
                            player['pts'] = int(val) if val and val != '' else 0
                        elif header == 'FG':
                            fg = val
                            # Get FGA from next column
                            fga_idx = i + 1
                            if fga_idx - 1 < len(cells) - 1:
                                fga = cells[fga_idx].text.strip()
                                player['fg'] = f"{fg}-{fga}" if fg and fga else "0-0"
                        elif header == '3P':
                            tp = val
                            tpa_idx = i + 1
                            if tpa_idx - 1 < len(cells) - 1:
                                tpa = cells[tpa_idx].text.strip()
                                player['tp'] = f"{tp}-{tpa}" if tp and tpa else "0-0"
                        elif header == 'FT':
                            ft = val
                            fta_idx = i + 1
                            if fta_idx - 1 < len(cells) - 1:
                                fta = cells[fta_idx].text.strip()
                                player['ft'] = f"{ft}-{fta}" if ft and fta else "0-0"
                        elif header == 'TRB':
                            player['reb'] = int(val) if val and val != '' else 0
                        elif header == 'AST':
                            player['ast'] = int(val) if val and val != '' else 0
                        elif header == 'STL':
                            player['stl'] = int(val) if val and val != '' else 0
                        elif header == 'BLK':
                            player['blk'] = int(val) if val and val != '' else 0
                        elif header == 'TOV':
                            player['to'] = int(val) if val and val != '' else 0

                team_entry['players'].append(player)

        # Parse totals from tfoot
        tfoot = table.find('tfoot')
        if tfoot:
            totals_row = tfoot.find('tr')
            if totals_row:
                cells = totals_row.find_all(['th', 'td'])
                totals = {}
                for i, cell in enumerate(cells[1:], 1):
                    if i < len(stat_headers):
                        header = stat_headers[i]
                        val = cell.text.strip()
                        if header == 'FG':
                            fga_idx = i + 1
                            if fga_idx - 1 < len(cells) - 1:
                                fga = cells[fga_idx].text.strip()
                                totals['fg'] = f"{val}-{fga}"
                        elif header == '3P':
                            tpa_idx = i + 1
                            if tpa_idx - 1 < len(cells) - 1:
                                tpa = cells[tpa_idx].text.strip()
                                totals['tp'] = f"{val}-{tpa}"
                        elif header == 'FT':
                            fta_idx = i + 1
                            if fta_idx - 1 < len(cells) - 1:
                                fta = cells[fta_idx].text.strip()
                                totals['ft'] = f"{val}-{fta}"
                        elif header == 'TRB':
                            totals['reb'] = int(val) if val else 0
                        elif header == 'AST':
                            totals['ast'] = int(val) if val else 0

                team_entry['totals'] = totals

        result['teams'].append(team_entry)

    return result


def get_tournament_boxscore_urls(fetcher, year):
    """Get all box score URLs from a tournament bracket page."""
    url = f"{SR_BASE}/postseason/men/{year}-ncaa.html"
    print(f"  Fetching tournament bracket: {url}")
    resp = fetcher.fetch(url)
    if not resp:
        # Try alternate URL format
        url = f"{SR_BASE}/postseason/{year}-ncaa.html"
        print(f"  Trying alternate: {url}")
        resp = fetcher.fetch(url)
        if not resp:
            return []

    soup = BeautifulSoup(resp.text, 'html.parser')
    links = soup.find_all('a', href=True)

    boxscore_urls = set()
    for link in links:
        href = link['href']
        if '/boxscores/' in href and href.endswith('.html') and href != '/cbb/boxscores/':
            full_url = f"https://www.sports-reference.com{href}" if href.startswith('/') else href
            boxscore_urls.add(full_url)

    urls = sorted(boxscore_urls)
    print(f"  Found {len(urls)} box score URLs for {year}")
    return urls


def find_alt_boxscore_url(fetcher, team_sr_slug, year):
    """404 fallback: check a team's schedule page for the correct box score URL.

    Absorbed from scrape_modern_boxscores.py. Looks for March box score links
    on the team's schedule page, preferring NCAA first-round dates for the year.
    """
    for path in [f"/cbb/schools/{team_sr_slug}/men/{year}-schedule.html",
                 f"/cbb/schools/{team_sr_slug}/{year}-schedule.html"]:
        url = f"https://www.sports-reference.com{path}"
        html = fetcher.fetch_text(url)
        if not html:
            continue
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if re.match(rf'/cbb/boxscores/{year}-03-\d{{2}}.*\.html$', href):
                if href not in links:  # unique, preserve order
                    links.append(href)
        # Prefer NCAA first-round dates
        dates = FIRST_ROUND_DATES.get(year, [])
        for link in links:
            for d in dates:
                if f"{year}-{d}" in link:
                    return f"https://www.sports-reference.com{link}"
        # Fallback: last March link containing the team slug
        slug_links = [l for l in links if team_sr_slug in l]
        if slug_links:
            return f"https://www.sports-reference.com{slug_links[-1]}"
    return None


def url_to_game_key(url, boxscore_data):
    """Convert a box score URL + data to a game key like 2024/winner-slug-vs-loser-slug."""
    if not boxscore_data or not boxscore_data.get('teams') or len(boxscore_data['teams']) < 2:
        return None

    # Extract year from URL
    match = re.search(r'/boxscores/(\d{4})-', url)
    if not match:
        return None
    year = match.group(1)

    t1 = boxscore_data['teams'][0]
    t2 = boxscore_data['teams'][1]

    # Determine winner/loser
    if t1['score'] >= t2['score']:
        winner, loser = t1, t2
    else:
        winner, loser = t2, t1

    def name_to_slug(name):
        slug = name.lower()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'\s+', '-', slug.strip())
        return slug

    winner_slug = name_to_slug(winner['name'])
    loser_slug = name_to_slug(loser['name'])

    return f"{year}/{winner_slug}-vs-{loser_slug}"
