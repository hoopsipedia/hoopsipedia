#!/usr/bin/env python3
"""Repair pass for UK harvest quarantine: refetch quarantined pages and
retry with table-orientation flip detection.

The main harvest guessed which stat table was Kentucky's by page
position; wrong guesses validated backwards and quarantined. Here we
try BOTH orientations against the game log and keep whichever matches.
Pre-1949 pages in quarantine get the points-checksum + result check
against UKGames.txt (the historian's own results file) instead.
"""

import json
import re
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, '.')
from harvest_bigbluehistory import get, parse_tables, rows_to_players, slugify, BASE

sys.stdout.reconfigure(line_buffering=True)

PENDING = 'archives/kentucky/uk_boxscores_pending.json'


def main():
    data = json.load(open(PENDING))
    results, quarantine = data['games'], data['quarantine']
    print(f'quarantined pages to repair: {len(quarantine)}')

    uk_log = []
    for fn in ('games_1.json', 'games_2.json', 'games_3.json'):
        d = json.load(open(fn))
        if '96' in d:
            v = d['96']
            uk_log = v['games'] if isinstance(v, dict) else v
            break
    by_date = {}
    for g in uk_log:
        by_date.setdefault(g.get('date', ''), []).append(g)

    def log_check(date, uk_pts, opp_pts):
        base = datetime.strptime(date, '%Y-%m-%d')
        for off in (0, -1, 1):
            d = (base + timedelta(days=off)).strftime('%Y-%m-%d')
            for g in by_date.get(d, []):
                if g.get('pts') == uk_pts and g.get('opp_pts') == opp_pts:
                    return True
        return False

    # historian's own results file: date -> (uk, opp) for pre-log era checks
    ukgames = {}
    txt = open('archives/kentucky/UKGames.txt', errors='ignore').read()
    for m in re.finditer(r'(\d{1,2})/(\d{1,2})/(\d{4})\t([^\t]+)\t([WL])\t[HAN]\t(\d+|-)\t(\d+|-)', txt):
        mo, dy, yr, opp, res, s1, s2 = m.groups()
        if s1.isdigit() and s2.isdigit():
            ukgames[f'{yr}-{int(mo):02d}-{int(dy):02d}'] = (int(s1), int(s2))

    repaired = 0
    still = []
    for page, reason in quarantine:
        m = re.match(r'Games/(\d{4})(\d{2})(\d{2})(.+)\.html', page)
        if not m:
            still.append((page, reason))
            continue
        date = f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
        opp_name = re.sub(r'(?<!^)(?=[A-Z])', ' ', m.group(4)).strip()
        try:
            html = get(BASE + page)
        except Exception as e:
            still.append((page, f'refetch failed: {e}'))
            time.sleep(3)
            continue
        time.sleep(3)
        tables = parse_tables(html)
        if len(tables) < 2:
            still.append((page, 'still <2 tables'))
            continue
        teams = []
        for t in tables[:2]:
            players = rows_to_players(t['headers'], t['rows'])
            teams.append({'players': players, 'score': sum(p.get('pts', 0) for p in players)})

        placed = False
        for uk_i, opp_i in ((0, 1), (1, 0)):
            uk_t, opp_t = teams[uk_i], teams[opp_i]
            ok = False
            if date >= '1949-01-01':
                ok = log_check(date, uk_t['score'], opp_t['score'])
            else:
                exp = ukgames.get(date)
                ok = bool(exp and exp == (uk_t['score'], opp_t['score']))
            if ok:
                uk_t = dict(uk_t, name='Kentucky Wildcats')
                opp_t = dict(opp_t, name=opp_name)
                season_year = int(date[:4]) + (1 if int(date[5:7]) >= 10 else 0)
                key = f"{season_year}/kentucky-wildcats-vs-{slugify(opp_name)}-{date}"
                results[key] = {'source': 'bigbluehistory.net', 'date': date,
                                'teams': [uk_t, opp_t]}
                repaired += 1
                placed = True
                break
        if not placed:
            still.append((page, f'no orientation matches (scores {teams[0]["score"]}/{teams[1]["score"]}) — {reason}'))

    data['games'] = results
    data['quarantine'] = still
    data['stats']['repaired'] = repaired
    json.dump(data, open(PENDING, 'w'), indent=1)
    print(f'repaired: {repaired} | still quarantined: {len(still)}')
    for p, r in still[:10]:
        print('  ', p, '::', r)
    print('REPAIR COMPLETE')


if __name__ == '__main__':
    main()
