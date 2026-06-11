#!/usr/bin/env python3
"""ESPN schedule backfill for teams missing game-by-game data.

Computes the missing team set (IDs in data.json 'H' minus IDs present in
games_1/2/3.json), then pulls each missing team's schedules from ESPN's
public site API for seasons 2003-2026 (regular season + postseason) and
converts them to the exact games_N.json schema:

    { "<espn_id>": { "games": [ {date, opp_slug, loc, w, pts, opp_pts,
                                 opp, arena?}, ... ],
                     "slug": "<sports-reference slug or ''>" } }

- Completed games only (status.type.completed == true with both scores).
- 0.4s delay between requests; 3 retries w/ exponential backoff on 429/5xx.
- Resumable: progress tracked in espn_backfill_progress.json (atomic).
- Output written incrementally to games_espn_backfill.json (atomic).
- STAGING ONLY: never writes games_1/2/3.json. Merge separately using the
  validated-merge pattern in scrape_batch.py (merge_safely).

Usage:
    python3 espn_backfill_games.py                 # all missing teams
    python3 espn_backfill_games.py --teams 2698,2385,2330   # explicit IDs
    python3 espn_backfill_games.py --limit 5       # first N missing teams
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from json_io import save_json_atomic

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_JSON = os.path.join(ROOT, 'data.json')
GAMES_FILES = [os.path.join(ROOT, f'games_{n}.json') for n in (1, 2, 3)]
ESPN_TO_SR = os.path.join(ROOT, 'espn_to_sr.json')
OUT_FILE = os.path.join(ROOT, 'games_espn_backfill.json')
PROGRESS_FILE = os.path.join(ROOT, 'espn_backfill_progress.json')

API = ('https://site.api.espn.com/apis/site/v2/sports/basketball/'
       'mens-college-basketball/teams/{tid}/schedule')
SEASONS = range(2003, 2027)        # ESPN season param = season END year
SEASON_TYPES = (2, 3)              # 2 = regular, 3 = postseason
DELAY = 0.4                        # seconds between requests
RETRIES = 3
TIMEOUT = 30
# ESPN event dates are UTC; convert to US/Eastern so the calendar date
# matches the Sports-Reference convention used in games_1/2/3.json.
EASTERN_OFFSET = timedelta(hours=-5)


def load_json(path):
    with open(path) as f:
        return json.load(f)


def compute_missing():
    """IDs in data.json H minus IDs present in games_1/2/3.json."""
    h_ids = set(load_json(DATA_JSON)['H'].keys())
    present = set()
    for path in GAMES_FILES:
        present |= set(load_json(path).keys())
    return sorted(h_ids - present, key=int), h_ids


class EspnBackfiller:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers['User-Agent'] = (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) hoopsipedia-backfill')
        self.espn_to_sr = load_json(ESPN_TO_SR)
        self.last_request = 0.0
        self.requests_made = 0
        self.out = load_json(OUT_FILE) if os.path.exists(OUT_FILE) else {}
        self.progress = (load_json(PROGRESS_FILE)
                         if os.path.exists(PROGRESS_FILE)
                         else {'done_units': [], 'done_teams': []})
        self._done_units = set(self.progress['done_units'])

    # -- HTTP -------------------------------------------------------------
    def _fetch(self, tid, season, seasontype):
        url = API.format(tid=tid)
        params = {'season': season, 'seasontype': seasontype}
        for attempt in range(RETRIES):
            wait = DELAY - (time.time() - self.last_request)
            if wait > 0:
                time.sleep(wait)
            try:
                resp = self.session.get(url, params=params, timeout=TIMEOUT)
                self.last_request = time.time()
                self.requests_made += 1
                if resp.status_code == 429 or resp.status_code >= 500:
                    backoff = 2 ** attempt * 5
                    print(f'      HTTP {resp.status_code}, retry in {backoff}s')
                    time.sleep(backoff)
                    continue
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValueError) as e:
                self.last_request = time.time()
                if attempt < RETRIES - 1:
                    backoff = 2 ** attempt * 5
                    print(f'      {e} — retry in {backoff}s')
                    time.sleep(backoff)
                else:
                    print(f'      FAILED {tid} s{season} t{seasontype}: {e}')
        return None

    # -- conversion -------------------------------------------------------
    @staticmethod
    def _event_date(iso):
        """ESPN UTC timestamp -> US/Eastern calendar date YYYY-MM-DD."""
        try:
            dt = datetime.strptime(iso[:16], '%Y-%m-%dT%H:%M').replace(
                tzinfo=timezone.utc)
            return (dt + EASTERN_OFFSET).strftime('%Y-%m-%d')
        except ValueError:
            return iso[:10]

    def _convert_event(self, tid, event):
        comp = (event.get('competitions') or [None])[0]
        if not comp:
            return None
        status = ((comp.get('status') or {}).get('type') or {})
        if not status.get('completed'):
            return None

        me = other = None
        for c in comp.get('competitors', []):
            if str(c.get('id')) == tid:
                me = c
            else:
                other = c
        if not me or not other:
            return None

        def score_of(c):
            s = c.get('score')
            if isinstance(s, dict):
                v = s.get('value', s.get('displayValue'))
            else:
                v = s
            try:
                return int(float(v))
            except (TypeError, ValueError):
                return None

        pts, opp_pts = score_of(me), score_of(other)
        if pts is None or opp_pts is None or (pts == 0 and opp_pts == 0):
            return None

        won = me.get('winner')
        if won is None:
            won = pts > opp_pts
        loc = ('N' if comp.get('neutralSite')
               else 'H' if me.get('homeAway') == 'home' else 'A')

        opp_id = str(other.get('id'))
        game = {
            'date': self._event_date(event.get('date', '')),
            'opp_slug': self.espn_to_sr.get(
                opp_id, (other.get('team') or {}).get('displayName', '')),
            'loc': loc,
            'w': bool(won),
            'pts': pts,
            'opp_pts': opp_pts,
            'opp': opp_id,
        }
        arena = ((comp.get('venue') or {}).get('fullName'))
        if arena:
            game['arena'] = arena
        return game, event.get('id')

    # -- persistence ------------------------------------------------------
    def _save(self):
        save_json_atomic(OUT_FILE, self.out, separators=(',', ':'))
        self.progress['done_units'] = sorted(self._done_units)
        save_json_atomic(PROGRESS_FILE, self.progress, indent=1)

    # -- main loop --------------------------------------------------------
    def run_team(self, tid, name):
        if tid in self.progress['done_teams']:
            print(f'  [{tid}] {name} — already complete, skipping')
            return
        print(f'\n  [{tid}] {name}')
        entry = self.out.setdefault(
            tid, {'games': [], 'slug': self.espn_to_sr.get(tid, '')})
        seen_events = set()
        seen_keys = {(g['date'], g.get('opp'), g['pts'], g['opp_pts'])
                     for g in entry['games']}

        for season in SEASONS:
            for stype in SEASON_TYPES:
                unit = f'{tid}:{season}:{stype}'
                if unit in self._done_units:
                    continue
                data = self._fetch(tid, season, stype)
                added = 0
                for event in (data or {}).get('events', []):
                    converted = self._convert_event(tid, event)
                    if not converted:
                        continue
                    game, eid = converted
                    key = (game['date'], game['opp'], game['pts'],
                           game['opp_pts'])
                    if eid in seen_events or key in seen_keys:
                        continue
                    seen_events.add(eid)
                    seen_keys.add(key)
                    entry['games'].append(game)
                    added += 1
                if added:
                    print(f'    season {season} type {stype}: +{added} games')
                self._done_units.add(unit)
            # persist once per season-year (both types done)
            entry['games'].sort(key=lambda g: g['date'])
            self._save()

        wins = sum(1 for g in entry['games'] if g['w'])
        print(f'    => {len(entry["games"])} games '
              f'({wins}W-{len(entry["games"]) - wins}L)')
        if not entry['games']:
            print(f'    WARNING: no completed games found on ESPN for {tid}')
        self.progress['done_teams'].append(tid)
        self._save()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--teams', help='comma-separated ESPN team IDs '
                    '(overrides the computed missing set)')
    ap.add_argument('--limit', type=int, help='only process first N teams')
    args = ap.parse_args()

    h = load_json(DATA_JSON)['H']
    missing, h_ids = compute_missing()
    print(f'data.json H teams: {len(h_ids)}')
    print(f'missing from games_1/2/3: {len(missing)}')

    if args.teams:
        targets = [t.strip() for t in args.teams.split(',') if t.strip()]
        unknown = [t for t in targets if t not in h_ids]
        if unknown:
            print(f'WARNING: not in data.json H: {unknown}')
    else:
        targets = missing
    if args.limit:
        targets = targets[:args.limit]

    if not targets:
        print('Nothing to do — no missing teams.')
        return

    bf = EspnBackfiller()
    start = time.time()
    for tid in targets:
        name = h.get(tid, ['(unknown)'])[0]
        bf.run_team(tid, name)
    print(f'\nDone: {len(targets)} teams, {bf.requests_made} requests, '
          f'{time.time() - start:.0f}s')
    print(f'Staging output: {OUT_FILE}')
    print('NOT merged into games_1/2/3.json — use scrape_batch.py '
          'merge_safely pattern after review.')


if __name__ == '__main__':
    main()
