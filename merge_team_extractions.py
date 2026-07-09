#!/usr/bin/env python3
"""Merge per-page vision extractions for any team into a gated pending file.

Generalizes merge_ucla_extractions.py. Reads the {dir}/*.json files written by
workflow agents (one per PDF page), then applies the bigbluehistory gates:
  1. checksum: each team's player pts must sum to its final score (recomputed
     here — never trust the agent's checksum_ok flag)
  2. date+scores must triple-match the team's game log, date +/-1 day.
     Games BEFORE the log's first date (SR logs start 1949-50) pass on
     checksum alone, counted as 'pre_log' (Kentucky precedent).

Usage: python3 merge_team_extractions.py --dir <extracted_dir> --team-id 194 \
         --team-name "Ohio State Buckeyes" --source ohiostatebuckeyes.com \
         --out archives/ohiostate/osu_boxscores_pending.json
"""
import argparse
import glob
import json
import re
from datetime import datetime, timedelta


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def as_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--team-id', required=True)
    ap.add_argument('--team-name', required=True, help='canonical name, e.g. "Ohio State Buckeyes"')
    ap.add_argument('--source', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    # the team's own-name detector: first word of canonical name must appear
    # in the extracted team name (agents write e.g. "Ohio State")
    name_key = args.team_name.split()[0]

    log = []
    for fn in ('games_1.json', 'games_2.json', 'games_3.json'):
        d = json.load(open(fn))
        if args.team_id in d:
            v = d[args.team_id]
            log = v['games'] if isinstance(v, dict) else v
            break
    log_by_date = {}
    for g in log:
        log_by_date.setdefault(g.get('date', ''), []).append(g)
    log_start = min(log_by_date) if log_by_date else '9999'
    print(f'{args.team_name} game log: {len(log)} games from {log_start}')

    def log_match(date, own_pts, opp_pts):
        if date < log_start:
            return 'pre-log'
        base = datetime.strptime(date, '%Y-%m-%d')
        for off in (0, -1, 1):
            d = (base + timedelta(days=off)).strftime('%Y-%m-%d')
            for g in log_by_date.get(d, []):
                if g.get('pts') == own_pts and g.get('opp_pts') == opp_pts:
                    return True
        return False

    results, quarantine = {}, []
    stats = {'ok': 0, 'pre_log': 0, 'checksum_fail': 0, 'log_mismatch': 0, 'bad_shape': 0, 'dup': 0}
    for path in sorted(glob.glob(f'{args.dir}/*.json')):
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
            own_t = next((t for t in teams if name_key.lower() in t.get('name', '').lower()), None)
            opp_t = next((t for t in teams if t is not own_t), None)
            if not own_t or not opp_t:
                quarantine.append((path, f'{date}: no {name_key}/opp team split'))
                stats['bad_shape'] += 1
                continue
            bad = False
            for t in (own_t, opp_t):
                for p in t.get('players', []):
                    if 'pts' in p:
                        p['pts'] = as_int(p['pts'])
                psum = sum(p.get('pts', 0) for p in t.get('players', []))
                t['score'] = as_int(t.get('score'))
                if psum != t['score']:
                    quarantine.append((path, f"{date} {t.get('name')}: players sum {psum} != score {t['score']}"))
                    stats['checksum_fail'] += 1
                    bad = True
            if bad:
                continue
            lm = log_match(date, own_t['score'], opp_t['score'])
            if lm is False:
                quarantine.append((path, f"{date}: log mismatch {own_t['score']}-{opp_t['score']}"))
                stats['log_mismatch'] += 1
                continue
            if lm == 'pre-log':
                stats['pre_log'] += 1
            own_t['name'] = args.team_name
            season_year = int(date[:4]) + (1 if int(date[5:7]) >= 10 else 0)
            key = f"{season_year}/{slugify(args.team_name)}-vs-{slugify(opp_t['name'])}-{date}"
            if key in results:
                stats['dup'] += 1
                continue
            results[key] = {'source': args.source, 'date': date, 'teams': [own_t, opp_t]}
            stats['ok'] += 1

    json.dump({'games': results, 'quarantine': quarantine, 'stats': stats},
              open(args.out, 'w'), indent=1)
    print('STATS:', stats)
    print(f'wrote {args.out}: {len(results)} games, {len(quarantine)} quarantined')


if __name__ == '__main__':
    main()
