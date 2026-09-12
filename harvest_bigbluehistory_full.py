#!/usr/bin/env python3
"""Harvest EVERY Kentucky box score on bigbluehistory.net, not just the 757
in the curated GameBoxes.html index that harvest_bigbluehistory.py used.

Discovery: the site has one page per opponent (Tennessee.html,
MississippiState.html, …) and each links every meeting's game page
(Games/YYYYMMDDOpponent.html). Tennessee alone linked 183 game pages missing
from the master index. Opponent page names are derived from the UK game log's
opp_slug (CamelCase); misses are reported, never guessed.

Harvest: same parser and gates as harvest_bigbluehistory.py — bordered HTML
tables parsed by header, team score = sum of player points, and every 1949+
game must triple-match the date and both scores in Kentucky's game log
(±1 day). Pre-1949 games (no log) are tagged 'pre-log' exactly as before.

Resumable: discovery is cached, harvested/quarantined pages are checkpointed
every 25 fetches, and pages whose date already has a Kentucky box in the
store are skipped. Pacing 2.5 s per request on this one-person site.

  python3 harvest_bigbluehistory_full.py            # discover + harvest
  python3 harvest_bigbluehistory_full.py --discover # discovery only
  python3 harvest_bigbluehistory_full.py --retry-quarantine  # re-process 'log mismatch' pages
Team assignment: the page header reads "Kentucky - 69 (Head Coach: …)"; the
table whose points sum to that number is Kentucky's. Fallback: the old
'../Players/' position heuristic, then a swap if the log matches the
reversed pair (which is how the 1949-51 flips were caught).
Output: archives/kentucky/uk_boxscores_full_pending.json (merge with
merge_pending_into_store.py, then split/recaps/players as usual).
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harvest_bigbluehistory import get, parse_tables, rows_to_players, slugify, strip_tags  # noqa: E402

sys.stdout.reconfigure(line_buffering=True)
BASE = 'http://www.bigbluehistory.net/bb/Statistics/'
OUTDIR = 'archives/kentucky'
DISC = os.path.join(OUTDIR, 'bbh_game_pages.json')
OUT = os.path.join(OUTDIR, 'uk_boxscores_full_pending.json')
PACE = 2.5


def load_uk_log():
    for fn in ('games_1.json', 'games_2.json', 'games_3.json'):
        d = json.load(open(fn))
        if '96' in d:
            v = d['96']
            return v['games'] if isinstance(v, dict) else v
    return []


def camel(slug):
    return ''.join(p.capitalize() for p in slug.split('-'))


def discover(uk_log):
    if os.path.exists(DISC):
        d = json.load(open(DISC))
        print(f"discovery cached: {len(d['pages'])} game pages from {len(d['opponents'])} opponent pages ({len(d['missing'])} opponent pages not found)")
        return d
    opps = sorted({g.get('opp_slug', '') for g in uk_log if g.get('opp_slug')})
    pages, found, missing = set(), {}, []
    # the curated master index too
    try:
        idx = get(BASE + 'GameBoxes.html')
        for m in re.findall(r'href="(Games/[^"]+\.html)"', idx, re.I):
            pages.add(m)
    except Exception as e:
        print('master index failed:', e)
    time.sleep(PACE)
    for i, slug in enumerate(opps):
        name = camel(slug)
        url = BASE + name + '.html'
        try:
            html = get(url)
            links = set(re.findall(r'href="([^"]*Games/[^"]+\.html)"', html, re.I))
            links = {'Games/' + l.split('Games/')[-1] for l in links}
            found[slug] = len(links)
            pages |= links
        except Exception as e:
            missing.append((slug, name, str(e)[:40]))
        time.sleep(PACE)
        if (i + 1) % 25 == 0:
            print(f'  opponents {i+1}/{len(opps)}: {len(pages)} game pages so far, {len(missing)} misses')
    d = {'pages': sorted(pages), 'opponents': found, 'missing': missing, 'generated': datetime.now().isoformat()}
    os.makedirs(OUTDIR, exist_ok=True)
    json.dump(d, open(DISC, 'w'), indent=1)
    print(f"discovery: {len(pages)} game pages from {len(found)} opponent pages; {len(missing)} opponent pages not found")
    for m in missing[:30]:
        print('   miss:', m)
    return d


def main():
    uk_log = load_uk_log()
    log_by_date = {}
    for g in uk_log:
        log_by_date.setdefault(g.get('date', ''), []).append(g)
    log_start = min(log_by_date) if log_by_date else '1949-12-03'

    def log_match(date, uk_pts, opp_pts):
        base = datetime.strptime(date, '%Y-%m-%d')
        for off in (0, -1, 1):
            d = (base + timedelta(days=off)).strftime('%Y-%m-%d')
            for g in log_by_date.get(d, []):
                if g.get('pts') == uk_pts and g.get('opp_pts') == opp_pts:
                    return True
        return None if date >= log_start else 'pre-log'

    disc = discover(uk_log)
    if '--discover' in sys.argv:
        return

    # dates already covered in the store (skip) — any entry with Kentucky as a team
    covered = set()
    store = json.load(open('sr_boxscores.json'))
    for k, v in store.items():
        if any(t.get('name') == 'Kentucky Wildcats' for t in v.get('teams', [])):
            m = re.search(r'(\d{4}-\d{2}-\d{2})', k)
            if m:
                covered.add(m.group(1))
            elif v.get('date'):
                covered.add(v['date'])

    state = json.load(open(OUT)) if os.path.exists(OUT) else {'games': {}, 'quarantine': [], 'stats': {'ok': 0, 'log_mismatch': 0, 'parse_fail': 0, 'skipped_covered': 0}, 'done': []}
    done = set(state['done'])
    stats = state['stats']
    if '--retry-quarantine' in sys.argv:
        retry = {q[0] for q in state['quarantine'] if 'log mismatch' in q[1]}
        state['quarantine'] = [q for q in state['quarantine'] if q[0] not in retry]
        done -= retry
        stats['log_mismatch'] = 0
        # pre-log games accepted on the old position heuristic get re-run through
        # the header-based team assignment (no log to catch a flipped table there)
        prelog = [k for k, v in state['games'].items() if v.get('date', '') < log_start]
        for k in prelog:
            del state['games'][k]
        done -= {p for p in done if re.match(r'Games/(\d{8})', p) and f"{p[6:10]}-{p[10:12]}-{p[12:14]}" < log_start}
        stats['ok'] = len(state['games'])
        print(f'retrying {len(retry)} quarantined pages + {len(prelog)} pre-log games')
    todo = []
    for page in disc['pages']:
        m = re.match(r'Games/(\d{4})(\d{2})(\d{2})(.+)\.html', page)
        if not m or page in done:
            continue
        date = f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
        if date in covered:
            stats['skipped_covered'] = stats.get('skipped_covered', 0) + 1
            done.add(page)
            continue
        todo.append((page, date, m.group(4)))
    print(f'{len(todo)} game pages to harvest ({len(covered)} dates already in store, {len(done) - len(todo) if len(done) > len(todo) else len(done)} already processed)')

    def save():
        state['done'] = sorted(done)
        json.dump(state, open(OUT, 'w'), indent=1)

    for i, (page, date, opp_raw) in enumerate(todo):
        try:
            html = get(BASE + page)
        except Exception as e:
            stats['parse_fail'] += 1
            state['quarantine'].append((page, f'fetch failed: {str(e)[:60]}'))
            done.add(page)
            time.sleep(PACE)
            continue
        time.sleep(PACE)
        done.add(page)
        tables = parse_tables(html)
        if len(tables) < 2:
            stats['parse_fail'] += 1
            state['quarantine'].append((page, f'{len(tables)} stat tables'))
            continue
        opp_name = re.sub(r'(?<!^)(?=[A-Z])', ' ', opp_raw).strip()
        teams = []
        for t in tables[:2]:
            players = rows_to_players(t['headers'], t['rows'])
            teams.append({'players': players, 'score': sum(p.get('pts', 0) for p in players)})
        # Kentucky's table = the one whose points sum to the header's "Kentucky - NN"
        hm = re.search(r'Kentucky\s*[-–]\s*(\d{1,3})\b', strip_tags(html[:5000]))
        uk_first = None
        if hm:
            hs = int(hm.group(1))
            if teams[0]['score'] == hs and teams[1]['score'] != hs: uk_first = True
            elif teams[1]['score'] == hs and teams[0]['score'] != hs: uk_first = False
        if uk_first is None:
            uk_first = html.find('../Players/') < len(html) // 2
        uk_t, opp_t = (teams[0], teams[1]) if uk_first else (teams[1], teams[0])
        lm = log_match(date, uk_t['score'], opp_t['score'])
        if lm is None and log_match(date, opp_t['score'], uk_t['score']) is True:
            uk_t, opp_t = opp_t, uk_t   # tables were the other way round
            lm = True
        uk_t['name'] = 'Kentucky Wildcats'
        opp_t['name'] = opp_name
        if lm is True or lm == 'pre-log':
            season_year = int(date[:4]) + (1 if int(date[5:7]) >= 10 else 0)
            key = f"{season_year}/kentucky-wildcats-vs-{slugify(opp_name)}-{date}"
            state['games'][key] = {'source': 'bigbluehistory.net', 'date': date, 'teams': [uk_t, opp_t]}
            stats['ok'] += 1
        else:
            stats['log_mismatch'] += 1
            state['quarantine'].append((page, f"log mismatch uk {uk_t['score']}-{opp_t['score']} on {date}"))
        if (i + 1) % 25 == 0:
            save()
            print(f"  [{i+1}/{len(todo)}] ok={stats['ok']} mismatch={stats['log_mismatch']} parsefail={stats['parse_fail']}")
    save()
    print('FINAL:', stats)
    print('UK FULL HARVEST COMPLETE')


if __name__ == '__main__':
    main()
