#!/usr/bin/env python3
"""Deterministic parser + harvester for StatCrew box scores.

The 'Official Basketball Box Score -- GAME TOTALS' fixed-width format was
produced by StatCrew software and published (as <pre> HTML on CSTV-template
sites, or as text-layer PDFs) by most athletics departments ~1997-2010.
One parser covers them all.

Usage (Charlotte reference source):
  python3 harvest_statcrew.py charlotte
Sources are configured in SOURCES below; each yields (label, text) box-score
documents. Gates (bigbluehistory pattern): totals-row checksum (player TP sum
must equal the printed Totals TP) + date/scores triple-match against the
team's game log. Output: archives/{source}/statcrew_boxscores_pending.json
"""

import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta

sys.stdout.reconfigure(line_buffering=True)
UA = {'User-Agent': 'Mozilla/5.0'}


def get(url, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def strip_tags(s):
    return re.sub(r'<[^>]+>', '', s)


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


# ---------- StatCrew text parser ----------

PLAYER_RE = re.compile(
    r'^\s*\d{0,3}\s+(?P<name>[A-Za-z].*?)(?:\.{2,}|\s\s)\s*(?:[fcg]\s+)?'
    r'(?P<fg>\d+-\d+)\s+(?P<tp3>\d+-\d+)\s+(?P<ft>\d+-\d+)\s+'
    r'(?P<of>\d+)\s+(?P<de>\d+)\s+(?P<tot>\d+)\s+(?P<pf>\d+)\s+'
    r'(?P<tp>\d+)\s+(?P<a>\d+)\s+(?P<to>\d+)\s+(?P<blk>\d+)\s+(?P<s>\d+)'
    r'(?:\s+(?P<min>\d+))?\s*$')
TOTALS_RE = re.compile(
    r'^\s*Totals\.*\s+(?P<fg>\d+-\d+)\s+(?P<tp3>\d+-\d+)\s+(?P<ft>\d+-\d+)\s+'
    r'\d+\s+\d+\s+\d+\s+\d+\s+(?P<tp>\d+)')
TEAM_HDR_RE = re.compile(
    r'^\s*(?:VISITORS?|HOME\s*TEAM)\s*:\s*(?P<name>.+?)\s*(?:\d+-\d+.*)?$')
DATE_RE = re.compile(r'^(?P<m>\d{1,2})[-/](?P<d>\d{1,2})[-/](?P<y>\d{2,4})\b')


def parse_statcrew(text):
    """Parse one StatCrew box score text -> game dict or None."""
    lines = text.split('\n')
    date = None
    teams = []       # [{'name', 'players', 'score'}]
    cur = None
    for ln in lines:
        plain = strip_tags(ln)
        if date is None:
            dm = DATE_RE.match(plain.strip())
            if dm:
                y = int(dm.group('y'))
                y += 2000 if y < 50 else (1900 if y < 100 else 0)
                date = f"{y:04d}-{int(dm.group('m')):02d}-{int(dm.group('d')):02d}"
        hm = TEAM_HDR_RE.match(plain)
        if hm and 'Player Name' not in plain:
            cur = {'name': hm.group('name').strip().title(), 'players': []}
            teams.append(cur)
            continue
        if cur is None:
            continue
        tm = TOTALS_RE.match(plain)
        if tm:
            cur['score'] = int(tm.group('tp'))
            cur = cur if len(teams) < 2 else None
            continue
        pm = PLAYER_RE.match(plain)
        if pm:
            p = {'name': re.sub(r'\s+', ' ', pm.group('name')).strip(),
                 'fg': pm.group('fg'), 'tp': pm.group('tp3'), 'ft': pm.group('ft'),
                 'reb': int(pm.group('tot')), 'pf': int(pm.group('pf')),
                 'pts': int(pm.group('tp')), 'ast': int(pm.group('a')),
                 'to': int(pm.group('to')), 'blk': int(pm.group('blk')),
                 'stl': int(pm.group('s'))}
            if pm.group('min'):
                p['min'] = int(pm.group('min'))
            cur['players'].append(p)
    if not date or len(teams) != 2:
        return None
    for t in teams:
        if 'score' not in t or not t['players']:
            return None
        # checksum: totals row vs player sum
        if sum(p['pts'] for p in t['players']) != t['score']:
            return None
    return {'date': date, 'teams': teams}


# ---------- Sources ----------

def get_retry(url, timeout=180, attempts=6, wait=30):
    for i in range(attempts):
        try:
            return get(url, timeout=timeout)
        except Exception as e:
            print(f'  cdx retry {i + 1}/{attempts} ({e}); wait {wait}s')
            time.sleep(wait)
    raise RuntimeError(f'gave up on {url}')


def charlotte_docs():
    """Enumerate the live legacy stats dir via Wayback CDX, fetch LIVE files."""
    cdx = get_retry('http://web.archive.org/cdx/search/cdx?url=static.charlotte49ers.com/old_site/sports/m-baskbl/stats/*&collapse=urlkey&fl=original&limit=2000').decode()
    files = sorted({u.strip().split('?')[0] for u in cdx.splitlines()
                    if re.search(r'/stats/\d{6}[a-z]{3}\.html?(\?|$)', u)})
    # also probe the live dir listing pattern beyond what wayback saw
    print(f'{len(files)} game files from CDX')
    for u in files:
        live = re.sub(r'^https?://[^/]+', 'https://static.charlotte49ers.com', u)
        try:
            yield live, get(live).decode('utf-8', 'replace')
        except Exception as e:
            print(f'  fetch fail {live}: {e}')
        time.sleep(0.5)


SOURCES = {
    'charlotte': {'team_id': '2429', 'team_name': 'Charlotte 49ers',
                  'site': 'static.charlotte49ers.com legacy archive',
                  'docs': charlotte_docs},
}


def main():
    src = SOURCES[sys.argv[1]]
    outdir = f'archives/{sys.argv[1]}'
    os.makedirs(outdir, exist_ok=True)

    log = []
    for fn in ('games_1.json', 'games_2.json', 'games_3.json'):
        d = json.load(open(fn))
        if src['team_id'] in d:
            v = d[src['team_id']]
            log = v['games'] if isinstance(v, dict) else v
            break
    by_date = {}
    for g in log:
        by_date.setdefault(g.get('date', ''), []).append(g)
    log_start = min(by_date) if by_date else '9999'
    print(f"{src['team_name']}: log {len(log)} games from {log_start}")

    def log_match(date, own, opp):
        if date < log_start:
            return True
        base = datetime.strptime(date, '%Y-%m-%d')
        for off in (0, -1, 1):
            dd = (base + timedelta(days=off)).strftime('%Y-%m-%d')
            for g in by_date.get(dd, []):
                if g.get('pts') == own and g.get('opp_pts') == opp:
                    return True
        return False

    name_key = src['team_name'].split()[0].lower()
    results, quarantine = {}, []
    stats = {'ok': 0, 'parse_fail': 0, 'checksum_fail': 0, 'log_mismatch': 0}
    for label, text in src['docs']():
        g = parse_statcrew(text)
        if not g:
            stats['parse_fail'] += 1
            quarantine.append((label, 'parse/checksum fail'))
            continue
        own = next((t for t in g['teams'] if name_key in t['name'].lower()), None)
        opp = next((t for t in g['teams'] if t is not own), None)
        if not own:
            stats['parse_fail'] += 1
            quarantine.append((label, 'no own-team match'))
            continue
        if not log_match(g['date'], own['score'], opp['score']):
            stats['log_mismatch'] += 1
            quarantine.append((label, f"log mismatch {own['score']}-{opp['score']} {g['date']}"))
            continue
        own['name'] = src['team_name']
        season = int(g['date'][:4]) + (1 if int(g['date'][5:7]) >= 10 else 0)
        key = f"{season}/{slugify(src['team_name'])}-vs-{slugify(opp['name'])}-{g['date']}"
        results[key] = {'source': src['site'], 'date': g['date'], 'teams': [own, opp]}
        stats['ok'] += 1

    out = f'{outdir}/statcrew_boxscores_pending.json'
    json.dump({'games': results, 'quarantine': quarantine, 'stats': stats},
              open(out, 'w'), indent=1)
    print('STATS:', stats)
    print(f'wrote {out}: {len(results)} games')


if __name__ == '__main__':
    main()
