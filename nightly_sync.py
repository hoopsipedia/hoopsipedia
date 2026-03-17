#!/usr/bin/env python3
"""
Hoopsipedia Nightly Sync — ESPN API Integration

Updates:
1. Current season records (CS field) for all teams in H
2. Active coach win totals in COACH_LB
3. Tournament round advancement tracking

Safe: Never touches ATW/ATL (all-time records from NCAA record book).
Only adds deltas from current season changes.
"""

import json
import urllib.request
import urllib.error
import time
import os
import subprocess
from datetime import datetime
from collections import defaultdict

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(DATA_DIR, 'data.json')
LOG_FILE = os.path.join(DATA_DIR, 'sync_log.txt')

ESPN_TEAM_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/{}"
BATCH_SIZE = 10
BATCH_DELAY = 2  # seconds between batches

def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\n')

def fetch_team_record(espn_id):
    """Fetch current season W-L from ESPN API."""
    url = ESPN_TEAM_URL.format(espn_id)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Hoopsipedia/1.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            team = data.get('team', {})
            # Extract overall record
            record = team.get('record', {})
            items = record.get('items', [])
            for item in items:
                if item.get('type') == 'total' or item.get('description') == 'Overall Record':
                    stats = {s['name']: s['value'] for s in item.get('stats', [])}
                    wins = int(stats.get('wins', 0))
                    losses = int(stats.get('losses', 0))
                    return {'w': wins, 'l': losses}
            # Fallback: try summary
            summary = item.get('summary', '') if items else ''
            if '-' in summary:
                parts = summary.split('-')
                return {'w': int(parts[0]), 'l': int(parts[1])}
    except Exception as e:
        log(f"  ERROR fetching ESPN {espn_id}: {e}")
    return None

def sync_current_season():
    """Main sync: fetch current season records, update coaches, push to live."""
    log("=" * 60)
    log("NIGHTLY SYNC STARTED")
    log("=" * 60)

    # Load data
    with open(DATA_FILE) as f:
        data = json.load(f)

    H = data.get('H', {})
    old_cs = data.get('CS', {})  # Previous current-season records
    coach_lb = data.get('COACH_LB', [])

    team_ids = list(H.keys())
    log(f"Fetching records for {len(team_ids)} teams...")

    # Batch fetch from ESPN
    new_cs = {}
    for i in range(0, len(team_ids), BATCH_SIZE):
        batch = team_ids[i:i+BATCH_SIZE]
        for eid in batch:
            result = fetch_team_record(eid)
            if result:
                new_cs[eid] = result
        if i + BATCH_SIZE < len(team_ids):
            time.sleep(BATCH_DELAY)

    log(f"Got records for {len(new_cs)}/{len(team_ids)} teams")

    # Calculate deltas (new wins/losses since LAST sync)
    # IMPORTANT: If CS is empty (first run), this is a baseline capture only.
    # Sports Reference data already includes the current season, so we must NOT
    # add the full ESPN season as a delta — that would double-count.
    # Only subsequent runs (where old_cs has data) produce real deltas.
    is_first_run = len(old_cs) == 0
    if is_first_run:
        log("FIRST RUN: Setting ESPN baseline. No coach updates (SR data already includes this season).")

    changes = []
    if not is_first_run:
        for eid, new_rec in new_cs.items():
            old_rec = old_cs.get(eid, None)
            if old_rec is None:
                continue  # New team, no baseline to compare
            delta_w = new_rec['w'] - old_rec.get('w', 0)
            delta_l = new_rec['l'] - old_rec.get('l', 0)
            if delta_w > 0 or delta_l > 0:
                team_name = H[eid][0] if eid in H else f'ESPN:{eid}'
                changes.append({
                    'eid': eid,
                    'name': team_name,
                    'old': old_rec,
                    'new': new_rec,
                    'delta_w': delta_w,
                    'delta_l': delta_l
                })

    if changes:
        log(f"\n{len(changes)} teams with record changes:")
        for c in changes:
            log(f"  {c['name']}: {c['old'].get('w',0)}-{c['old'].get('l',0)} -> {c['new']['w']}-{c['new']['l']} (+{c['delta_w']}W, +{c['delta_l']}L)")
    else:
        log("No record changes detected.")

    # Update active coaches in COACH_LB
    # Build map: espn_id -> coach entries that have this as their most recent school
    coach_updates = 0
    for coach in coach_lb:
        if not coach.get('schools'):
            continue
        # Most recent school is last in the list (sorted by start year)
        latest_school = coach['schools'][-1]
        latest_eid = str(latest_school[0])
        # Check if this coach is active (yearsEnd >= current year)
        if coach.get('yearsEnd', 0) < datetime.now().year:
            continue
        # Find delta for this school
        for c in changes:
            if c['eid'] == latest_eid:
                old_wins = coach['wins']
                coach['wins'] += c['delta_w']
                coach['losses'] += c['delta_l']
                total = coach['wins'] + coach['losses']
                coach['pct'] = round(coach['wins'] / total * 100, 1) if total > 0 else 0
                log(f"  Coach update: {coach['name']} {old_wins} -> {coach['wins']} wins ({c['name']})")
                coach_updates += 1
                break

    if coach_updates:
        # Re-sort leaderboard by wins
        coach_lb.sort(key=lambda c: c['wins'], reverse=True)
        # Rebuild rank lookup
        coach_rank = {}
        for i, coach in enumerate(coach_lb):
            coach_rank[coach['name']] = i + 1
        data['COACH_RANK'] = coach_rank
        log(f"Updated {coach_updates} active coaches")

    # Save updated current season records
    data['CS'] = new_cs
    data['COACH_LB'] = coach_lb
    data['SYNC_TIME'] = datetime.now().isoformat()

    # Write data
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

    log(f"Data saved. {len(new_cs)} season records, {coach_updates} coach updates.")

    return len(changes) > 0

def push_to_live():
    """Git add, commit, push."""
    os.chdir(DATA_DIR)
    try:
        subprocess.run(['git', 'add', 'data.json'], check=True)
        result = subprocess.run(['git', 'diff', '--cached', '--quiet'], capture_output=True)
        if result.returncode == 0:
            log("No changes to commit.")
            return
        msg = f"Nightly sync: update current season records and coaching data\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
        subprocess.run(['git', 'commit', '-m', msg], check=True)
        subprocess.run(['git', 'push', 'origin', 'main'], check=True, timeout=60)
        log("Pushed to live ✅")
    except Exception as e:
        log(f"Git push failed: {e}")

if __name__ == '__main__':
    import sys
    had_changes = sync_current_season()
    if had_changes or '--force-push' in sys.argv:
        push_to_live()
    else:
        log("No changes, skipping push.")
    log("SYNC COMPLETE\n")
