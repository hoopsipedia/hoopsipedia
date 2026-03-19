#!/usr/bin/env python3
"""
Fetch all-time win-loss records from Sports Reference for all Hoopsipedia teams.
Updates data.json H[espnId][4] (ATW) and H[espnId][5] (ATL).
"""

import json
import re
import time
import urllib.request
import urllib.error
import sys

DATA_FILE = "/Users/joshdavis/Projects/hoopsipedia/data.json"
MAPPING_FILE = "/Users/joshdavis/Projects/hoopsipedia/espn_to_sr.json"
DELAY = 4  # seconds between requests
RETRY_DELAY = 30  # seconds after 429
MAX_RETRIES = 3  # retry up to 3 times on 429

# Load data
with open(DATA_FILE) as f:
    data = json.load(f)

with open(MAPPING_FILE) as f:
    espn_to_sr = json.load(f)

H = data["H"]

# Build list of teams to fetch: only those in H with an SR slug
teams_to_fetch = []
for espn_id, team_data in H.items():
    if espn_id in espn_to_sr:
        slug = espn_to_sr[espn_id]
        teams_to_fetch.append((espn_id, slug, team_data[0]))

print(f"Teams to fetch: {len(teams_to_fetch)}")
sys.stdout.flush()

# Patterns to extract record from SR page
# Actual format: <strong>Record (since YYYY-YY):</strong>\n  WINS-LOSSES .XXX W-L%
RECORD_PATTERNS = [
    # Primary pattern: "Record (since YYYY-YY):</strong>\n  2367-935"
    re.compile(r'Record\s*\(since\s+\d{4}-\d{2,4}\):</strong>\s*(\d+)-(\d+)'),
    # Variant without "since" clause
    re.compile(r'Record:</strong>\s*(\d+)-(\d+)'),
    # More flexible
    re.compile(r'Record[^<]*:</strong>\s*(\d+)-(\d+)'),
    # Even more flexible - record on next line
    re.compile(r'Record[^<]*:</strong>\s*\n\s*(\d+)-(\d+)'),
    # Generic W-L near "record" keyword
    re.compile(r'Record[^<]{0,60}?(\d{3,5})-(\d{3,5})', re.IGNORECASE),
]

updated = 0
changed = 0
failed = []

for i, (espn_id, slug, name) in enumerate(teams_to_fetch):
    url = f"https://www.sports-reference.com/cbb/schools/{slug}/men/"

    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            # Try each pattern
            wins = losses = None
            for pattern in RECORD_PATTERNS:
                m = pattern.search(html)
                if m:
                    wins = int(m.group(1))
                    losses = int(m.group(2))
                    break

            if wins is not None and losses is not None:
                old_w, old_l = H[espn_id][4], H[espn_id][5]
                H[espn_id][4] = wins
                H[espn_id][5] = losses
                marker = ""
                if old_w != wins or old_l != losses:
                    marker = f" CHANGED (was {old_w}-{old_l})"
                    changed += 1
                print(f"[{i+1}/{len(teams_to_fetch)}] {name}: {wins}-{losses}{marker}")
                updated += 1
            else:
                print(f"[{i+1}/{len(teams_to_fetch)}] {name}: RECORD NOT FOUND on page")
                failed.append((espn_id, name, slug, "pattern_not_found"))

            sys.stdout.flush()
            break  # success, no retry needed

        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES - 1:
                wait = RETRY_DELAY * (attempt + 1)
                print(f"[{i+1}/{len(teams_to_fetch)}] {name}: 429 rate limited, waiting {wait}s (attempt {attempt+1})...")
                sys.stdout.flush()
                time.sleep(wait)
                continue
            elif e.code == 404:
                print(f"[{i+1}/{len(teams_to_fetch)}] {name}: 404 not found ({slug})")
                failed.append((espn_id, name, slug, "404"))
                break
            else:
                print(f"[{i+1}/{len(teams_to_fetch)}] {name}: HTTP {e.code}")
                failed.append((espn_id, name, slug, f"HTTP_{e.code}"))
                break
        except Exception as e:
            print(f"[{i+1}/{len(teams_to_fetch)}] {name}: ERROR {e}")
            failed.append((espn_id, name, slug, str(e)))
            break

    # Rate limit delay
    if i < len(teams_to_fetch) - 1:
        time.sleep(DELAY)

# Save updated data
data["H"] = H
with open(DATA_FILE, "w") as f:
    json.dump(data, f, separators=(",", ":"))

print(f"\n=== SUMMARY ===")
print(f"Updated: {updated}")
print(f"Changed: {changed}")
print(f"Failed: {len(failed)}")
if failed:
    print("\nFailed teams:")
    for espn_id, name, slug, reason in failed:
        print(f"  ESPN {espn_id} | {name} | {slug} | {reason}")
print(f"\ndata.json saved.")
