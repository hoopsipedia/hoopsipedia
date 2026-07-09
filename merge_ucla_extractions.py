#!/usr/bin/env python3
"""Merge per-page UCLA vision extractions into a gated pending file.

Reads the ucla_extracted/*.json files written by workflow agents (one per PDF
page), then applies the two gates from the bigbluehistory pattern:
  1. checksum: each team's player pts must sum to its final score (recomputed
     here — never trust the agent's checksum_ok flag)
  2. date+scores must triple-match UCLA's game log (team id 26), date +/-1 day
Output: archives/ucla/ucla_boxscores_pending.json

Usage: python3 merge_ucla_extractions.py <extracted_dir>
"""
import glob
import json
import re
import sys
from datetime import datetime, timedelta

EXTRACT_DIR = sys.argv[1] if len(sys.argv) > 1 else '/private/tmp/claude-501/-Users-joshdavis-Projects-hoopsipedia/d6742d03-59c5-448c-add9-02caae51f5f2/scratchpad/ucla_extracted'
OUT = 'archives/ucla/ucla_boxscores_pending.json'


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def main():
    ucla_log = []
    for fn in ('games_1.json', 'games_2.json', 'games_3.json'):
        d = json.load(open(fn))
        if '26' in d:
            v = d['26']
            ucla_log = v['games'] if isinstance(v, dict) else v
            break
    log_by_date = {}
    for g in ucla_log:
        log_by_date.setdefault(g.get('date', ''), []).append(g)
    print(f'UCLA game log: {len(ucla_log)} games')

    def log_match(date, ucla_pts, opp_pts):
        base = datetime.strptime(date, '%Y-%m-%d')
        for off in (0, -1, 1):
            d = (base + timedelta(days=off)).strftime('%Y-%m-%d')
            for g in log_by_date.get(d, []):
                if g.get('pts') == ucla_pts and g.get('opp_pts') == opp_pts:
                    return True
        return False

    results, quarantine = {}, []
    stats = {'ok': 0, 'checksum_fail': 0, 'log_mismatch': 0, 'bad_shape': 0, 'dup': 0}
    for path in sorted(glob.glob(f'{EXTRACT_DIR}/*.json')):
        try:
            page = json.load(open(path))
        except Exception as e:
            quarantine.append((path, f'unreadable: {e}'))
            stats['bad_shape'] += 1
            continue
        for g in page.get('games', []):
            date = g.get('date', '')
            teams = g.get('teams', [])
            if not re.match(r'\d{4}-\d{2}-\d{2}$', date) or len(teams) != 2:
                quarantine.append((path, f'bad shape {date}'))
                stats['bad_shape'] += 1
                continue
            ucla_t = next((t for t in teams if 'UCLA' in t.get('name', '')), None)
            opp_t = next((t for t in teams if 'UCLA' not in t.get('name', '')), None)
            if not ucla_t or not opp_t:
                quarantine.append((path, f'{date}: no UCLA/opp team split'))
                stats['bad_shape'] += 1
                continue
            # gate 1: recompute checksum from player lines
            def as_int(v):
                try:
                    return int(v)
                except (TypeError, ValueError):
                    return 0
            bad = False
            for t in (ucla_t, opp_t):
                for p in t.get('players', []):
                    if 'pts' in p:
                        p['pts'] = as_int(p['pts'])
                psum = sum(p.get('pts', 0) for p in t.get('players', []))
                t['score'] = as_int(t.get('score'))
                if psum != t.get('score'):
                    quarantine.append((path, f"{date} {t.get('name')}: players sum {psum} != score {t.get('score')}"))
                    stats['checksum_fail'] += 1
                    bad = True
            if bad:
                continue
            # gate 2: log triple-match
            if not log_match(date, ucla_t['score'], opp_t['score']):
                quarantine.append((path, f"{date}: log mismatch ucla {ucla_t['score']}-{opp_t['score']}"))
                stats['log_mismatch'] += 1
                continue
            ucla_t['name'] = 'UCLA Bruins'
            season_year = int(date[:4]) + (1 if int(date[5:7]) >= 10 else 0)
            key = f"{season_year}/ucla-bruins-vs-{slugify(opp_t['name'])}-{date}"
            if key in results:
                stats['dup'] += 1
                continue
            results[key] = {'source': 'uclabruins.com archives', 'date': date,
                            'teams': [ucla_t, opp_t]}
            stats['ok'] += 1

    json.dump({'games': results, 'quarantine': quarantine, 'stats': stats},
              open(OUT, 'w'), indent=1)
    print('STATS:', stats)
    print(f'wrote {OUT}: {len(results)} games, {len(quarantine)} quarantined')


if __name__ == '__main__':
    main()
