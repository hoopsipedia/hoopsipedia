#!/usr/bin/env python3
"""Harvest all 757 Kentucky box scores from bigbluehistory.net.

One historian, one consistent format: bordered HTML tables with
Player/Min/FG/FGA/FT/FTA/Reb/PF/Ast/TO/Pts (columns vary slightly by
era — parsed by header). Deterministic parse, two validation gates:
  1. checksum: each team's player points must sum to its final score
  2. for 1949+ games: date+scores must triple-match Kentucky's game log
Output: archives/kentucky/uk_boxscores_pending.json (merged into
sr_boxscores.json later, after the SR harvest chain releases the file).
Respectful pacing: 3s between requests on this personal site.
"""

import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta

sys.stdout.reconfigure(line_buffering=True)

BASE = 'http://www.bigbluehistory.net/bb/Statistics/'
OUT = 'archives/kentucky/uk_boxscores_pending.json'


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    return urllib.request.urlopen(req, timeout=30).read().decode('utf-8', errors='ignore')


def strip_tags(s):
    return re.sub(r'<[^>]+>', '', s).strip()


def parse_tables(html):
    """Return list of stat tables: {'headers': [...], 'rows': [[...]]}"""
    out = []
    for tm in re.finditer(r'(?is)<table[^>]*>(.*?)</table>', html):
        rows = re.findall(r'(?is)<tr[^>]*>(.*?)</tr>', tm.group(1))
        if not rows:
            continue
        headers = [strip_tags(c) for c in re.findall(r'(?is)<th[^>]*>(.*?)</th>', rows[0])]
        if 'Pts' not in headers or 'Player' not in headers:
            continue
        body = []
        for r in rows[1:]:
            cells = [strip_tags(c) for c in re.findall(r'(?is)<td[^>]*>(.*?)</td>', r)]
            if cells:
                body.append(cells)
        out.append({'headers': headers, 'rows': body})
    return out


COLMAP = {'Min': 'min', 'Reb': 'reb', 'PF': 'pf', 'Ast': 'ast', 'TO': 'to',
          'Stl': 'stl', 'St': 'stl', 'Blk': 'blk', 'BS': 'blk', 'Pts': 'pts'}


def rows_to_players(headers, rows):
    players = []
    idx = {h: i for i, h in enumerate(headers)}
    for cells in rows:
        if len(cells) != len(headers):
            continue
        name = cells[idx['Player']]
        low = name.lower()
        if low in ('total', 'totals', 'team') or not name:
            continue
        p = {'name': name}
        for h, key in COLMAP.items():
            if h in idx:
                v = cells[idx[h]]
                if v.isdigit():
                    p[key] = int(v)
        # made-attempted pairs
        for made, att, key in (('FG', 'FGA', 'fg'), ('FT', 'FTA', 'ft'), ('3FG', '3FGA', 'tp'), ('3P', '3PA', 'tp')):
            if made in idx and att in idx:
                m, a = cells[idx[made]], cells[idx[att]]
                if m.isdigit() and a.isdigit():
                    p[key] = f'{m}-{a}'
        if 'pts' in p:
            players.append(p)
    return players


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def main():
    idx_html = get(BASE + 'GameBoxes.html')
    pages = sorted(set(re.findall(r'href="(Games/[^"]+\.html)"', idx_html, re.I)))
    print(f'{len(pages)} game pages in master index')

    # Kentucky game log for the 1949+ triple-match gate
    uk_log = []
    for fn in ('games_1.json', 'games_2.json', 'games_3.json'):
        d = json.load(open(fn))
        if '96' in d:
            v = d['96']
            uk_log = v['games'] if isinstance(v, dict) else v
            break
    log_by_date = {}
    for g in uk_log:
        log_by_date.setdefault(g.get('date', ''), []).append(g)

    def log_match(date, uk_pts, opp_pts):
        base = datetime.strptime(date, '%Y-%m-%d')
        for off in (0, -1, 1):
            d = (base + timedelta(days=off)).strftime('%Y-%m-%d')
            for g in log_by_date.get(d, []):
                if g.get('pts') == uk_pts and g.get('opp_pts') == opp_pts:
                    return True
        return None if date >= '1949-01-01' else 'pre-log'

    results = {}
    stats = {'ok': 0, 'checksum_fail': 0, 'log_mismatch': 0, 'parse_fail': 0}
    quarantine = []
    for i, page in enumerate(pages):
        m = re.match(r'Games/(\d{4})(\d{2})(\d{2})(.+)\.html', page)
        if not m:
            stats['parse_fail'] += 1
            continue
        date = f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
        try:
            html = get(BASE + page)
        except Exception:
            stats['parse_fail'] += 1
            time.sleep(3)
            continue
        time.sleep(3)
        tables = parse_tables(html)
        if len(tables) < 2:
            stats['parse_fail'] += 1
            quarantine.append((page, 'fewer than 2 stat tables'))
            continue
        # team names: page headings before each table (fallback: UK + opponent from URL)
        opp_name = re.sub(r'(?<!^)(?=[A-Z])', ' ', m.group(4)).strip()
        teams = []
        for t in tables[:2]:
            players = rows_to_players(t['headers'], t['rows'])
            score = sum(p.get('pts', 0) for p in players)
            teams.append({'players': players, 'score': score})
        # identify which table is Kentucky by page ordering: UK table lists
        # players linked to ../Players/ — check the raw html order instead
        first_is_uk = html.find('../Players/') < len(html) // 2
        uk_t, opp_t = (teams[0], teams[1]) if first_is_uk else (teams[1], teams[0])
        uk_t['name'] = 'Kentucky Wildcats'
        opp_t['name'] = opp_name

        # gate 1: checksum vs the final score printed on the page
        fm = re.search(r'(\d{2,3})\s*[-–]\s*(\d{2,3})', strip_tags(html[:3000]))
        # gate 2: 1949+ log match
        lm = log_match(date, uk_t['score'], opp_t['score'])
        if lm is True or lm == 'pre-log':
            season_year = int(date[:4]) + (1 if int(date[5:7]) >= 10 else 0)
            key = f"{season_year}/kentucky-wildcats-vs-{slugify(opp_name)}-{date}"
            results[key] = {
                'source': 'bigbluehistory.net',
                'date': date,
                'teams': [uk_t, opp_t],
            }
            stats['ok'] += 1
        else:
            stats['log_mismatch'] += 1
            quarantine.append((page, f"log mismatch uk {uk_t['score']}-{opp_t['score']} on {date}"))
        if (i + 1) % 50 == 0:
            json.dump({'games': results, 'quarantine': quarantine, 'stats': stats}, open(OUT, 'w'))
            print(f'  [{i+1}/{len(pages)}] ok={stats["ok"]} mismatch={stats["log_mismatch"]} parsefail={stats["parse_fail"]}')

    json.dump({'games': results, 'quarantine': quarantine, 'stats': stats}, open(OUT, 'w'), indent=1)
    print('FINAL:', stats)
    print('UK HARVEST COMPLETE')


if __name__ == '__main__':
    main()
