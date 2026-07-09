#!/usr/bin/env python3
"""Harvest Arkansas box scores from hogstats.com (fan archive, launched 2005).

Site claims 1,837 box scores across 103 seasons (62% of all 2,886 games).
Schedule pages (schedule.php?season=YYYY-YY) link boxscore.php?date=YYYY-MM-DD
for games that have one. Box pages hold two uniform stat tables
(Name/FG-A/3FG-A/FT-A/OR/DR/REB/PF/TP/A/TO/BLK/S/MIN; columns vary by era).
Page title line "Arkansas vs. X: won 126-88" always lists Arkansas's score first.

Deterministic parse, two validation gates (bigbluehistory pattern):
  1. checksum: each team's player TP must sum to its score from the title line
  2. date+scores must triple-match Arkansas's game log (team id 8), date +/-1
Output: archives/arkansas/hogstats_boxscores_pending.json
Respectful pacing: 2.5s between requests on this personal site.
"""

import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta

sys.stdout.reconfigure(line_buffering=True)

BASE = 'https://www.hogstats.com/'
OUT = 'archives/arkansas/hogstats_boxscores_pending.json'
FIRST_SEASON = 1923  # founded 1924 (=1923-24 season)
LAST_SEASON = 2026


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    return urllib.request.urlopen(req, timeout=30).read().decode('utf-8', errors='ignore')


def strip_tags(s):
    return re.sub(r'<[^>]+>', '', s).strip()


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def parse_stat_tables(html):
    """Stat tables: a header row (first cell ends with 'Name', has a 'TP' col)
    followed by player rows. Table nesting on the page can merge page chrome
    into the header's first cell, so match by suffix, not equality."""
    out = []
    for tm in re.finditer(r'(?is)<table[^>]*>(.*?)</table>', html):
        rows = [
            [strip_tags(c) for c in re.findall(r'(?is)<td[^>]*>(.*?)</td>', r)]
            for r in re.findall(r'(?is)<tr[^>]*>(.*?)</tr>', tm.group(1))
        ]
        hdr_i = next((i for i, cells in enumerate(rows)
                      if cells and 'TP' in cells and cells[0].endswith('Name')), None)
        if hdr_i is None:
            continue
        headers = ['Name'] + rows[hdr_i][1:]
        out.append({'headers': headers, 'rows': [c for c in rows[hdr_i + 1:] if c]})
    return out


COLMAP = {'REB': 'reb', 'PF': 'pf', 'A': 'ast', 'TO': 'to', 'BLK': 'blk',
          'S': 'stl', 'TP': 'pts', 'OR': 'oreb', 'DR': 'dreb'}
PAIRMAP = {'FG-A': 'fg', 'FT-A': 'ft', '3FG-A': 'tp'}


def rows_to_players(headers, rows):
    players = []
    idx = {h: i for i, h in enumerate(headers)}
    for cells in rows:
        if len(cells) != len(headers):
            continue
        name = cells[idx['Name']]
        if not name or name.lower().startswith(('team', 'totals', 'total')):
            continue
        p = {'name': name}
        for h, key in COLMAP.items():
            if h in idx and cells[idx[h]].isdigit():
                p[key] = int(cells[idx[h]])
        for h, key in PAIRMAP.items():
            if h in idx:
                m = re.match(r'(\d+)-(\d+)$', cells[idx[h]])
                if m:
                    p[key] = m.group(0)
        if h_min := idx.get('MIN'):
            m = re.match(r'(\d+):(\d{2})$', cells[h_min])
            if m and m.group(0) != '0:00':
                p['min'] = int(m.group(1))
        if 'pts' in p:
            players.append(p)
    return players


def main():
    os.makedirs('archives/arkansas', exist_ok=True)

    # Arkansas game log (team id 8) for the triple-match gate
    ark_log = []
    for fn in ('games_1.json', 'games_2.json', 'games_3.json'):
        d = json.load(open(fn))
        if '8' in d:
            v = d['8']
            ark_log = v['games'] if isinstance(v, dict) else v
            break
    log_by_date = {}
    for g in ark_log:
        log_by_date.setdefault(g.get('date', ''), []).append(g)
    print(f'Arkansas game log: {len(ark_log)} games')

    def log_match(date, ark_pts, opp_pts):
        base = datetime.strptime(date, '%Y-%m-%d')
        for off in (0, -1, 1):
            d = (base + timedelta(days=off)).strftime('%Y-%m-%d')
            for g in log_by_date.get(d, []):
                if g.get('pts') == ark_pts and g.get('opp_pts') == opp_pts:
                    return True
        return False

    # resume support
    results, quarantine = {}, []
    stats = {'ok': 0, 'checksum_fail': 0, 'log_mismatch': 0, 'parse_fail': 0}
    done_dates = set()
    if os.path.exists(OUT):
        prev = json.load(open(OUT))
        results = prev.get('games', {})
        quarantine = prev.get('quarantine', [])
        stats = prev.get('stats', stats)
        done_dates = {g['date'] for g in results.values()}
        done_dates |= {q[0] for q in quarantine}
        print(f'resuming: {len(results)} games, {len(quarantine)} quarantined')

    # 1. enumerate box-score dates from every season schedule
    dates = []
    for y in range(FIRST_SEASON, LAST_SEASON + 1):
        season = f'{y}-{str(y + 1)[-2:].zfill(2)}'
        try:
            html = get(f'{BASE}schedule.php?season={season}')
        except Exception as e:
            print(f'{season}: schedule fetch failed ({e})')
            time.sleep(2.5)
            continue
        time.sleep(2.5)
        found = re.findall(r"href=['\"]boxscore\.php\?date=(\d{4}-\d{2}-\d{2})['\"]", html)
        dates.extend(found)
        if found:
            print(f'{season}: {len(found)} box scores')
    dates = sorted(set(dates))
    print(f'TOTAL: {len(dates)} box-score dates ({len(done_dates)} already done)')

    # 2. fetch + parse each box score
    todo = [d for d in dates if d not in done_dates]
    for i, date in enumerate(todo):
        try:
            html = get(f'{BASE}boxscore.php?date={date}')
        except Exception as e:
            stats['parse_fail'] += 1
            quarantine.append((date, f'fetch error {e}'))
            time.sleep(2.5)
            continue
        time.sleep(2.5)

        title = re.search(
            r"(?:#\d+\s*)?Arkansas vs\.\s*(.+?):\s*(won|lost)\s*(\d+)-(\d+)",
            strip_tags(html))
        tables = parse_stat_tables(html)
        if not title or len(tables) < 2:
            stats['parse_fail'] += 1
            quarantine.append((date, f'title={bool(title)} tables={len(tables)}'))
            continue
        opp_name = re.sub(r'^#\d+\s*', '', title.group(1).strip())
        ark_score, opp_score = int(title.group(3)), int(title.group(4))

        teams = []
        for t in tables[:2]:
            players = rows_to_players(t['headers'], t['rows'])
            teams.append({'players': players, 'score': sum(p['pts'] for p in players)})

        # assign tables by checksum against the title-line scores
        if teams[0]['score'] == ark_score and teams[1]['score'] == opp_score:
            ark_t, opp_t = teams
        elif teams[1]['score'] == ark_score and teams[0]['score'] == opp_score:
            ark_t, opp_t = teams[1], teams[0]
        else:
            stats['checksum_fail'] += 1
            quarantine.append((date, f'checksum: title {ark_score}-{opp_score}, '
                               f'tables sum {teams[0]["score"]}/{teams[1]["score"]}'))
            continue
        ark_t['name'] = 'Arkansas Razorbacks'
        opp_t['name'] = opp_name

        if not log_match(date, ark_score, opp_score):
            stats['log_mismatch'] += 1
            quarantine.append((date, f'log mismatch ark {ark_score}-{opp_score}'))
            continue

        season_year = int(date[:4]) + (1 if int(date[5:7]) >= 10 else 0)
        key = f'{season_year}/arkansas-razorbacks-vs-{slugify(opp_name)}-{date}'
        results[key] = {'source': 'hogstats.com', 'date': date, 'teams': [ark_t, opp_t]}
        stats['ok'] += 1

        if (i + 1) % 25 == 0:
            json.dump({'games': results, 'quarantine': quarantine, 'stats': stats}, open(OUT, 'w'))
            print(f'  [{i + 1}/{len(todo)}] ok={stats["ok"]} checksum_fail={stats["checksum_fail"]} '
                  f'mismatch={stats["log_mismatch"]} parsefail={stats["parse_fail"]}')

    json.dump({'games': results, 'quarantine': quarantine, 'stats': stats}, open(OUT, 'w'), indent=1)
    print('FINAL:', stats)
    print('HOGSTATS HARVEST COMPLETE')


if __name__ == '__main__':
    main()
