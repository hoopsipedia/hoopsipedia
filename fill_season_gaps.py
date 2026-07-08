#!/usr/bin/env python3
"""Fill remaining event-map gaps for target seasons via ESPN daily scoreboards.

For each gap game (team, date, scores), fetches that date's full D1
scoreboard (limit 300, groups=50) and matches by our team's ESPN id +
exact score pair (checking date, date-1, date+1 for UTC skew). Matched
events merge into game_ids_bulk.json; unmatched are reported as
NOT_ON_ESPN (exhibitions / games ESPN never carried).
"""

import json
import sys
import time
import urllib.request
from datetime import datetime, timedelta

from json_io import save_json_atomic

GAPS = '/private/tmp/claude-501/-Users-joshdavis-Projects-hoopsipedia/1fb24a29-95f3-4629-84b1-969add39a738/scratchpad/season_fill_gaps.json'
SB = ('https://site.api.espn.com/apis/site/v2/sports/basketball/'
      'mens-college-basketball/scoreboard?dates={d}&groups=50&limit=300')

sys.stdout.reconfigure(line_buffering=True)


def fetch(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read())
        except Exception:
            time.sleep(1.5 * (i + 1))
    return None


def main():
    gaps = json.load(open(GAPS))
    allgaps = [(season, g) for season, lst in gaps.items() for g in lst]
    dates = set()
    for _, g in allgaps:
        base = datetime.strptime(g['date'], '%Y-%m-%d')
        for off in (0, 1):  # ESPN dates are UTC; our evening games roll forward
            dates.add((base + timedelta(days=off)).strftime('%Y%m%d'))
    print(f'{len(allgaps)} gap rows across {len(dates)} scoreboard dates')

    boards = {}
    for i, d in enumerate(sorted(dates)):
        data = fetch(SB.format(d=d))
        time.sleep(0.4)
        events = (data or {}).get('events', [])
        boards[d] = events
        if (i + 1) % 40 == 0:
            print(f'  {i+1}/{len(dates)} dates fetched')

    bulk = json.load(open('game_ids_bulk.json'))
    games = bulk['games']
    matched = 0
    not_found = []
    for season, g in allgaps:
        tid, pts, opp_pts = str(g['tid']), g['pts'], g['opp_pts']
        base = datetime.strptime(g['date'], '%Y-%m-%d')
        hit = None
        for off in (0, 1):
            d = (base + timedelta(days=off)).strftime('%Y%m%d')
            for ev in boards.get(d, []):
                comp = (ev.get('competitions') or [{}])[0]
                comps = comp.get('competitors', [])
                if len(comps) != 2:
                    continue
                ids = {str(c.get('team', {}).get('id')): int(float(c.get('score') or 0)) for c in comps}
                if tid in ids and ids[tid] == pts and (sum(ids.values()) - ids[tid]) == opp_pts:
                    other = [k for k in ids if k != tid][0]
                    hit = (str(ev['id']), other, ids[other], comp.get('date', '')[:10])
                    break
            if hit:
                break
        if hit:
            eid, oid, oscore, edate = hit
            if eid not in games:
                games[eid] = {'date': g['date'], 't1': tid, 't2': oid,
                              's1': pts, 's2': opp_pts, 'type': 'regular'}
                matched += 1
        else:
            not_found.append((season, tid, g['date'], g.get('opp_slug'), f"{pts}-{opp_pts}"))

    bulk['_metadata'] = {'count': len(games), 'lastUpdated': '2026-07-08'}
    save_json_atomic('game_ids_bulk.json', bulk, separators=(',', ':'))
    json.load(open('game_ids_bulk.json'))
    print(f'RESULT: matched {matched} new events | not on ESPN: {len(not_found)}')
    with open('season_fill_notfound.json', 'w') as f:
        json.dump(not_found, f, indent=1)
    print('DONE')


if __name__ == '__main__':
    main()
