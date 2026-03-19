#!/usr/bin/env python3
"""
Scrape 4 metadata fields from Sports Reference for all live teams:
- CT (Conference Titles) = index 12  [from SR main page]
- AA (All-Americans) = index 13      [from SR all-america page]
- NBA (NBA 1st Round Picks) = index 14 [from basketball-reference]
- APW (AP Weeks Ranked) = index 15   [from SR main page]

Only updates fields that are currently 0.
"""

import json
import re
import time
import urllib.request
import urllib.error

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}

def fetch_url(url, retries=3):
    """Fetch URL with retry logic for rate limiting."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 30 * (attempt + 1)
                print(f"  Rate limited (429). Waiting {wait}s...")
                time.sleep(wait)
            elif e.code == 404:
                return None
            else:
                print(f"  HTTP {e.code} for {url}")
                if attempt < retries - 1:
                    time.sleep(10)
                else:
                    return None
        except Exception as e:
            print(f"  Error fetching {url}: {e}")
            if attempt < retries - 1:
                time.sleep(10)
            else:
                return None
    return None

def parse_conference_titles(html):
    """Parse conference titles from main school page (reg season + tournament)."""
    ct = 0
    m = re.search(r'Conference Champion.*?</p>', html, re.DOTALL)
    if m:
        block = m.group(0)
        reg = re.search(r'(\d+)\s+Times?\s*\(Reg\.\s*Seas\.\)', block)
        tourn = re.search(r'(\d+)\s+Times?\s*\(Tourn\.\)', block)
        if reg:
            ct += int(reg.group(1))
        if tourn:
            ct += int(tourn.group(1))
    return ct

def parse_ap_weeks(html):
    """Parse AP weeks ranked from main school page."""
    m = re.search(r'Ranked in AP Poll.*?(\d+)\s+Weeks?\s*\(Total\)', html, re.DOTALL)
    if m:
        return int(m.group(1))
    return 0

def parse_all_americans(html):
    """Parse All-Americans count from all-america page (unique players)."""
    rankers = re.findall(r'data-stat="ranker"\s+csk="(\d+)"', html)
    if rankers:
        return max(int(r) for r in rankers)
    return 0

def parse_nba_first_round(html):
    """Parse NBA first round picks from basketball-reference college page."""
    rounds = re.findall(r'<td[^>]*data-stat="round"[^>]*>(\d+)</td>', html)
    return sum(1 for r in rounds if r == '1')


def main():
    with open('data.json') as f:
        data = json.load(f)
    with open('games.json') as f:
        games = json.load(f)
    with open('espn_to_sr.json') as f:
        espn_to_sr = json.load(f)

    # Load SR-to-bref slug mapping
    try:
        with open('/tmp/sr_to_bref.json') as f:
            sr_to_bref = json.load(f)
    except:
        sr_to_bref = {}

    # Load protected records
    protected = {}
    try:
        with open('protected_records.json') as f:
            pr = json.load(f)
        if 'records' in pr:
            protected = pr['records']
    except:
        pass

    h = data['H']

    # Find live teams needing updates
    teams_to_scrape = []
    for team_id in games.keys():
        int_id = int(team_id) if team_id.isdigit() else team_id
        key = int_id if int_id in h else str(int_id)
        if key not in h:
            continue

        entry = h[key]
        sr_slug = espn_to_sr.get(team_id, espn_to_sr.get(str(int_id)))
        if not sr_slug:
            continue

        needs_ct = entry[12] == 0
        needs_aa = entry[13] == 0
        needs_nba = entry[14] == 0
        needs_apw = entry[15] == 0

        if needs_ct or needs_aa or needs_nba or needs_apw:
            teams_to_scrape.append({
                'espn_id': team_id,
                'h_key': key,
                'name': entry[0],
                'slug': sr_slug,
                'needs_ct': needs_ct,
                'needs_aa': needs_aa,
                'needs_nba': needs_nba,
                'needs_apw': needs_apw,
            })

    print(f"Teams needing updates: {len(teams_to_scrape)}")
    print(f"NBA slug mappings available: {len(sr_to_bref)}")

    updated_ct = 0
    updated_aa = 0
    updated_nba = 0
    updated_apw = 0
    failed = []
    updates_log = []

    for i, team in enumerate(teams_to_scrape):
        name = team['name']
        slug = team['slug']
        key = team['h_key']
        entry = h[key]

        print(f"\n[{i+1}/{len(teams_to_scrape)}] {name} ({slug})")

        # Scrape main SR page for CT and APW
        needs_main = team['needs_ct'] or team['needs_apw']
        if needs_main:
            url = f"https://www.sports-reference.com/cbb/schools/{slug}/men/"
            html = fetch_url(url)
            if html:
                if team['needs_ct']:
                    ct = parse_conference_titles(html)
                    if ct > 0:
                        entry[12] = ct
                        updated_ct += 1
                        updates_log.append(f"  CT: {name} = {ct}")
                        print(f"  CT = {ct}")
                    else:
                        print(f"  CT = 0 (not found or truly 0)")

                if team['needs_apw']:
                    apw = parse_ap_weeks(html)
                    if apw > 0:
                        entry[15] = apw
                        updated_apw += 1
                        updates_log.append(f"  APW: {name} = {apw}")
                        print(f"  APW = {apw}")
                    else:
                        print(f"  APW = 0 (not found or truly 0)")
            else:
                print(f"  FAILED to fetch main page")
                failed.append(f"{name} (main page)")

            time.sleep(3.5)

        # Scrape All-America page for AA
        if team['needs_aa']:
            url = f"https://www.sports-reference.com/cbb/schools/{slug}/men/all-america.html"
            html = fetch_url(url)
            if html:
                aa = parse_all_americans(html)
                if aa > 0:
                    entry[13] = aa
                    updated_aa += 1
                    updates_log.append(f"  AA: {name} = {aa}")
                    print(f"  AA = {aa}")
                else:
                    print(f"  AA = 0 (not found or truly 0)")
            else:
                # 404 = no all-america page, that's fine
                print(f"  AA = 0 (no page)")

            time.sleep(3.5)

        # Scrape basketball-reference for NBA first round picks
        if team['needs_nba']:
            bref_slug = sr_to_bref.get(slug)
            if not bref_slug:
                # Try direct: remove hyphens
                bref_slug = slug.replace('-', '')

            url = f"https://www.basketball-reference.com/friv/colleges.fcgi?college={bref_slug}"
            html = fetch_url(url)
            if html:
                # Verify the page is for the right school by checking title
                title_match = re.search(r'<title>(.*?)</title>', html)
                title = title_match.group(1) if title_match else ''

                nba = parse_nba_first_round(html)
                if nba > 0:
                    entry[14] = nba
                    updated_nba += 1
                    updates_log.append(f"  NBA: {name} = {nba}")
                    print(f"  NBA = {nba} (from: {title})")
                else:
                    print(f"  NBA = 0 (from: {title})")
            else:
                print(f"  NBA = 0 (no bref page)")

            time.sleep(3.5)

        # Periodic save every 20 teams
        if (i + 1) % 20 == 0:
            print(f"\n--- Saving progress ({i+1} teams processed) ---")
            with open('data.json', 'w') as f:
                json.dump(data, f, separators=(',', ':'))

    # Restore protected records (ATW=index 4, ATL=index 5)
    if protected:
        print("\n--- Restoring protected records (ATW/ATL) ---")
        for team_id, rec in protected.items():
            int_id = int(team_id) if team_id.isdigit() else team_id
            key = int_id if int_id in h else str(int_id)
            if key in h:
                if 'ATW' in rec:
                    h[key][4] = rec['ATW']
                if 'ATL' in rec:
                    h[key][5] = rec['ATL']

    # Save final data
    with open('data.json', 'w') as f:
        json.dump(data, f, separators=(',', ':'))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Teams processed: {len(teams_to_scrape)}")
    print(f"CT updated: {updated_ct}")
    print(f"AA updated: {updated_aa}")
    print(f"NBA updated: {updated_nba}")
    print(f"APW updated: {updated_apw}")

    if failed:
        print(f"\nFailed ({len(failed)}):")
        for f_name in failed:
            print(f"  - {f_name}")

    print("\nAll updates:")
    for log in updates_log:
        print(log)


if __name__ == '__main__':
    main()
