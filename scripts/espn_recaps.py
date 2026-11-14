#!/usr/bin/env python3
"""Box scores + recaps for the current season's games, from ESPN, nightly.

For one date (default: yesterday, Eastern time) fetch the Division I
scoreboard, pull the box score of every FINAL game, store it in the
archive's own format, and write a recap paragraph for both teams:

  archives/espn/espn_{season}_pending.json   store-format entries keyed
                                             '{year}/{a}-vs-{b}-{date}',
                                             merged by ship_store.sh like
                                             any other pending file
  recaps/{espnId}.json                       date -> recap prose, read by the
                                             server-rendered season pages
  archives/espn/espn_{season}_games.json     {espnId: {date: log row}} in the
                                             games/ slice format, and the rows
                                             are applied to games/{espnId}.json
                                             (+ games/index.json) so the current
                                             season's pages exist DURING the
                                             season; split_games.py re-applies
                                             them whenever slices are rebuilt

generate_game_recaps.py also reads the pending files, so a store rebuild
never drops these recaps. Idempotent: re-running a date replaces its games.

Usage: python3 scripts/espn_recaps.py [--date YYYY-MM-DD] [--dry-run]
"""

import datetime
import json
import os
import re
import sys
import time
import urllib.request
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from json_io import save_json_atomic  # noqa: E402
import generate_game_recaps as recaps  # noqa: E402

UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36')
API = 'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball'
PAUSE = 0.35  # seconds between summary calls


def fetch_json(url, tries=3):
    for i in range(tries):
        try:
            # ESPN has 403'd some custom agents while serving urllib's default
            # (nightly_sync.py, 2026-09): alternate between the two on retries.
            headers = {'Accept': 'application/json'}
            if i % 2 == 0:
                headers['User-Agent'] = UA
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            if i == tries - 1:
                print(f'  fetch failed {url}: {e}', file=sys.stderr)
                return None
            time.sleep(2 * (i + 1))


def season_label(date_str):
    y, m = int(date_str[:4]), int(date_str[5:7])
    start = y if m >= 8 else y - 1
    return f'{start}-{str(start + 1)[2:]}'


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def parse_stat_line(labels, stats):
    """ESPN stat row -> archive player dict. Missing columns stay absent."""
    row = dict(zip(labels, stats))
    out = {}
    def num(v):
        try:
            return int(str(v).strip())
        except (TypeError, ValueError):
            return None
    for src, dst in (('MIN', 'min'), ('REB', 'reb'), ('AST', 'ast'), ('STL', 'stl'),
                     ('BLK', 'blk'), ('TO', 'to'), ('PF', 'pf'), ('PTS', 'pts')):
        if src in row:
            v = num(row[src])
            if v is not None:
                out[dst] = v
    for src, dst in (('FG', 'fg'), ('3PT', 'tp'), ('FT', 'ft')):
        if src in row and re.match(r'^\d+-\d+$', str(row[src]).strip()):
            out[dst] = str(row[src]).strip()
    return out


def log_rows(box, event, sr_slug_by_id):
    """games/ slice rows for both teams of one final: {tid: row}."""
    comp = (event.get('competitions') or [{}])[0]
    home_away = {str(c.get('team', {}).get('id')): c.get('homeAway') for c in comp.get('competitors', [])}
    neutral = bool(comp.get('neutralSite'))
    venue = (comp.get('venue') or {}).get('fullName') or ''
    period = (comp.get('status') or {}).get('period') or 0
    ot = '' if period <= 2 else ('OT' if period == 3 else '{}OT'.format(period - 2))
    a, b = box['teams']
    rows = {}
    for me, opp in ((a, b), (b, a)):
        row = {
            'date': box['date'],
            'opp_slug': sr_slug_by_id.get(opp['espnId']) or slugify(opp['name']),
            'loc': 'N' if neutral else ('H' if home_away.get(me['espnId']) == 'home' else 'A'),
            'w': me['score'] > opp['score'],
            'pts': me['score'], 'opp_pts': opp['score'],
            'opp': opp['espnId'],
        }
        if venue:
            row['arena'] = venue
        if ot:
            row['ot'] = ot
        if box.get('espnEventId'):
            row['eid'] = box['espnEventId']   # lets the season page open the ESPN box score
        rows[me['espnId']] = row
    return rows


def apply_rows_to_slices(games_by_team):
    """Append ESPN rows to games/{tid}.json for dates the slice lacks
    (Sports-Reference rows, when they arrive, take precedence) and refresh
    games/index.json counts. Returns the number of rows added."""
    gdir = os.path.join(ROOT, 'games')
    idx_path = os.path.join(gdir, 'index.json')
    index = json.load(open(idx_path)) if os.path.exists(idx_path) else {}
    added = 0
    for tid, by_date in games_by_team.items():
        path = os.path.join(gdir, '{}.json'.format(tid))
        if not os.path.exists(path):
            continue
        doc = json.load(open(path))
        rows = doc['games'] if isinstance(doc, dict) else doc
        have = {r['date']: r for r in rows}
        new, merged = [], 0
        for d, r in sorted(by_date.items()):
            cur = have.get(d)
            if cur is None:
                new.append(r)
            elif str(cur.get('opp')) == str(r.get('opp')):
                # same game already logged (SR or an earlier ESPN run): add
                # fields it lacks (eid, arena, ot) without overriding SR values
                for k, v in r.items():
                    if k not in cur:
                        cur[k] = v
                        merged += 1
        if not new and not merged:
            continue
        rows.extend(new)
        rows.sort(key=lambda r: r['date'])
        if isinstance(doc, dict):
            doc['games'] = rows
        else:
            doc = {'games': rows}
        save_json_atomic(path, doc, separators=(',', ':'))
        index[tid] = len(rows)
        added += len(new)
    save_json_atomic(idx_path, {k: index[k] for k in sorted(index, key=lambda k: (len(k), k))},
                     separators=(',', ':'))
    return added


def box_from_summary(summary, names_by_id):
    """-> ({'source','date','espnEventId','teams':[...]}, [espnIds]) or None."""
    try:
        comp = summary['header']['competitions'][0]
    except (KeyError, IndexError, TypeError):
        return None
    if not (comp.get('status', {}).get('type', {}).get('completed')):
        return None
    # Game date in Eastern time: ESPN timestamps are UTC, so a 7pm ET tip is
    # already "tomorrow" in UTC. The game logs and recaps key on the ET date.
    date = ''
    try:
        ts = datetime.datetime.fromisoformat((comp.get('date') or '').replace('Z', '+00:00'))
        date = ts.astimezone(ZoneInfo('America/New_York')).strftime('%Y-%m-%d')
    except ValueError:
        pass
    players_by_team = {str(p['team']['id']): p for p in summary.get('boxscore', {}).get('players', []) if p.get('team')}
    teams, ids = [], []
    for c in comp.get('competitors', []):
        tid = str(c.get('team', {}).get('id', ''))
        try:
            score = int(c.get('score'))
        except (TypeError, ValueError):
            return None
        name = names_by_id.get(tid) or c.get('team', {}).get('displayName') or 'Unknown'
        plist = []
        block = players_by_team.get(tid)
        if block:
            for stat in block.get('statistics', []):
                labels = stat.get('labels') or stat.get('names') or []
                for a in stat.get('athletes', []):
                    if a.get('didNotPlay'):
                        continue
                    line = parse_stat_line(labels, a.get('stats', []))
                    pname = (a.get('athlete') or {}).get('displayName')
                    if pname and line:
                        line = dict(name=pname, **line)
                        plist.append(line)
        teams.append({'name': name, 'espnId': tid, 'score': score, 'players': plist})
        ids.append(tid)
    if len(teams) != 2:
        return None
    return {'source': 'espn', 'date': date, 'espnEventId': str(summary.get('header', {}).get('id', '')),
            'teams': teams}, ids


def main():
    args = sys.argv[1:]
    dry = '--dry-run' in args
    if '--date' in args:
        date = args[args.index('--date') + 1]
    else:
        now = datetime.datetime.now(ZoneInfo('America/New_York'))
        date = (now - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    names_by_id = {tid: v[0] for tid, v in json.load(open(os.path.join(ROOT, 'data.json')))['H'].items()}
    sr_slug_by_id = json.load(open(os.path.join(ROOT, 'espn_to_sr.json')))

    sb = fetch_json(f'{API}/scoreboard?dates={date.replace("-", "")}&groups=50&limit=300')
    events = (sb or {}).get('events', [])
    finals = [e for e in events if (e.get('status') or {}).get('type', {}).get('completed')]
    print(f'{date}: {len(events)} games on the scoreboard, {len(finals)} final')
    if not finals:
        return

    season = season_label(date)
    pending_path = os.path.join(ROOT, 'archives', 'espn', f'espn_{season}_pending.json')
    pending = json.load(open(pending_path)) if os.path.exists(pending_path) else {}
    # replace anything previously stored for this date (idempotent re-runs)
    pending = {k: v for k, v in pending.items() if v.get('date') != date}
    games_path = os.path.join(ROOT, 'archives', 'espn', f'espn_{season}_games.json')
    games_by_team = json.load(open(games_path)) if os.path.exists(games_path) else {}
    for tid in games_by_team:
        games_by_team[tid].pop(date, None)

    new_recaps = {}  # espnId -> {date: text}
    stored = 0
    for e in finals:
        summary = fetch_json(f'{API}/summary?event={e["id"]}')
        time.sleep(PAUSE)
        res = box_from_summary(summary, names_by_id) if summary else None
        if not res:
            print(f'  no box for {e.get("shortName")} ({e["id"]})')
            continue
        box, ids = res
        if not box['date']:
            box['date'] = date
        a, b = box['teams']
        key = f'{int(date[:4]) + (1 if int(date[5:7]) >= 8 else 0)}/{slugify(a["name"])}-vs-{slugify(b["name"])}-{date}'
        pending[key] = box
        stored += 1
        text = recaps.compose(key, box, a, b)
        for t in box['teams']:
            if t['espnId'] in names_by_id:
                new_recaps.setdefault(t['espnId'], {})[date] = text
        for tid, row in log_rows(box, e, sr_slug_by_id).items():
            if tid in names_by_id:
                games_by_team.setdefault(tid, {})[row['date']] = row

    print(f'  stored {stored} box scores, {sum(len(v) for v in new_recaps.values())} team recaps')
    if dry:
        for eid, d in list(new_recaps.items())[:3]:
            print('  ', names_by_id.get(eid), '->', list(d.values())[0])
        return
    os.makedirs(os.path.dirname(pending_path), exist_ok=True)
    save_json_atomic(pending_path, pending, separators=(',', ':'), ensure_ascii=False)
    save_json_atomic(games_path, games_by_team, separators=(',', ':'), ensure_ascii=False)
    added = apply_rows_to_slices(games_by_team)
    print(f'  game log: {sum(len(v) for v in games_by_team.values())} team-games this season, {added} new rows applied to games/ slices')
    rdir = os.path.join(ROOT, 'recaps')
    os.makedirs(rdir, exist_ok=True)
    for eid, by_date in new_recaps.items():
        path = os.path.join(rdir, f'{eid}.json')
        cur = json.load(open(path)) if os.path.exists(path) else {}
        cur.update(by_date)
        json.dump(cur, open(path, 'w'), separators=(',', ':'), ensure_ascii=False)
    print(f'  wrote {pending_path} ({len(pending)} games this season) and {len(new_recaps)} recap files')


if __name__ == '__main__':
    main()
