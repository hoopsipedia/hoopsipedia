#!/usr/bin/env python3
"""Stanford Daily box scores via the archive's public article search.

The Stanford Daily archive (archives.stanforddaily.com) exposes a CloudSearch
endpoint that returns full article text with the publish date; game stories
are titled with the final score ("USF 87, Stanford 82") and carry the box in
the text: "Stanford FG FT R F PTS Schweitzer 10-19 2-4 16 4 22 ... Totals
37-78 8-17 47 30 82". We match each article to Stanford's game log by date
(±3 days) and both scores, then parse both teams with the shared gated
parser (harvest_newspaper_ocr.parse_block): accepted only when every player
line parses and points sum to the known score.

  python3 harvest_stanford.py --from 1950 --to 1999
Output: archives/newspapers/stanford_pending.json (merge_pending_into_store.py).
"""
import json, os, re, sys, time, urllib.parse, urllib.request
from datetime import date, timedelta
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
from json_io import save_json_atomic
import importlib.util
_spec = importlib.util.spec_from_file_location('hn', os.path.join(ROOT, 'harvest_newspaper_ocr.py'))
hn = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(hn)

API = 'https://ehabp6fuc5.execute-api.us-east-1.amazonaws.com/prod'
TEAM = '24'  # Stanford Cardinal
ALIASES = ('stanford', 'cardinal', 'cards', 'indians', 'tribe')

def search(year, start=0, size=100):
    q = f'article_text:(Totals AND Stanford) AND publish_date:[{year}-01-01T00:00:00Z TO {year}-12-31T23:59:59Z]'
    url = f'{API}?q.parser=lucene&q={urllib.parse.quote(q)}&size={size}&start={start}&sort={urllib.parse.quote("publish_date asc")}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Hoopsipedia/1.0 (box-score archive research)'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode('utf-8'))

def field(f, k):
    v = f.get(k); return (v[0] if isinstance(v, list) and v else v) or ''

def to_lines(text):
    """The API flattens the box to one line; put each player, and Totals, on its own line."""
    t = re.sub(r'\s+', ' ', text)
    t = re.sub(r'(?<=[\d\)]) (?=(?:Team Reb|Totals|Percentages|Halftime)\b)', '\n', t)
    t = re.sub(r'(?<=\d) (?=[A-Z][A-Za-z\'.]+(?: [A-Z][A-Za-z\'.]+)? \d)', '\n', t)
    t = re.sub(r'(?<=PTS) ', '\n', t)
    return t

def main():
    y0 = int(sys.argv[sys.argv.index('--from') + 1]) if '--from' in sys.argv else 1950
    y1 = int(sys.argv[sys.argv.index('--to') + 1]) if '--to' in sys.argv else 1999
    H = json.load(open(os.path.join(ROOT, 'data.json')))['H']
    log = json.load(open(os.path.join(ROOT, 'games', f'{TEAM}.json'))); games = log.get('games', log)
    by_date = {}
    for g in games:
        if g.get('date'): by_date.setdefault(g['date'], []).append(g)
    out_path = os.path.join(ROOT, 'archives', 'newspapers', 'stanford_pending.json')
    pending = json.load(open(out_path)) if os.path.exists(out_path) else {}
    stats = {'hits': 0, 'matched_game': 0, 'accepted': 0}; reasons = {}
    for year in range(y0, y1 + 1):
        start = 0
        while True:
            try: d = search(year, start)
            except Exception as e: print(f'  {year} search failed: {e}'); break
            hits = d.get('hits', {}).get('hit', [])
            for h in hits:
                f = h.get('fields', {}); stats['hits'] += 1
                title = field(f, 'title'); pub = field(f, 'publish_date')[:10]; text = field(f, 'article_text')
                if 'Totals' not in text and 'TOTALS' not in text: continue
                try: pd = date.fromisoformat(pub)
                except ValueError: continue
                # Candidate games: Stanford's games in the four days before publication
                # (the story runs the next morning; weekend games wait for Monday).
                cands = []
                for off in (1, 2, 3, 0, 4):
                    for g in by_date.get((pd - timedelta(days=off)).isoformat(), []):
                        if str(g.get('opp')) in H: cands.append(g)
                if not cands: reasons['no-nearby-game'] = reasons.get('no-nearby-game', 0) + 1; continue
                lines = to_lines(text)
                game = None; parsed = {}
                for g in cands:
                    my, opp = int(g['pts']), int(g['opp_pts'])
                    three_pt = date.fromisoformat(g['date']) >= date(1986, 11, 1)
                    segs = re.split(r'(?mi)^\s*Totals?.*$', lines)
                    got = {}
                    for seg in segs[:-1]:
                        body = seg[-4000:]
                        for who, sc in (('me', my), ('opp', opp)):
                            if who in got: continue
                            res, how = hn.parse_block(body, three_pt, sc)
                            if res: got[who] = res; break
                    if not ('me' in got and 'opp' in got):
                        res, _ = hn.find_box_by_totals(lines, my, opp)
                        if res: got = res
                    if 'me' in got or 'opp' in got:
                        game, parsed = g, got
                        if 'me' in got and 'opp' in got: break
                if not game:
                    reasons['no-box-for-nearby-games'] = reasons.get('no-box-for-nearby-games', 0) + 1
                    if os.environ.get('DUMP'):
                        os.makedirs(os.environ['DUMP'], exist_ok=True)
                        open(os.path.join(os.environ['DUMP'], f'{pub}.txt'), 'w').write(f"CANDS {[(g['date'], g['pts'], g['opp_pts']) for g in cands]}\n{lines}")
                    continue
                my, opp = int(game['pts']), int(game['opp_pts'])
                stats['matched_game'] += 1
                key = f"{(date.fromisoformat(game['date']).year + (1 if date.fromisoformat(game['date']).month >= 8 else 0))}/stanford-cardinal-vs-{hn.slugify(H[str(game['opp'])][0])}-{game['date']}"
                if key in pending: continue
                if not ('me' in parsed and 'opp' in parsed):
                    # 1950s-60s four-column boxes (FG FT PF PTS): Totals-anchored parser
                    res, _ = hn.find_box_by_totals(lines, my, opp)
                    if res: parsed = res
                if 'me' in parsed and 'opp' in parsed:
                    pending[key] = {'source': 'The Stanford Daily (archives.stanforddaily.com)', 'date': game['date'],
                                    'url': f"https://archives.stanforddaily.com/{pub[:4]}/{pub[5:7]}/{pub[8:10]}",
                                    'teams': [{'name': 'Stanford Cardinal', 'score': my, 'players': parsed['me']},
                                              {'name': H[str(game['opp'])][0], 'score': opp, 'players': parsed['opp']}]}
                    stats['accepted'] += 1
                else:
                    r = 'opp-block' if 'me' in parsed else ('me-block' if 'opp' in parsed else 'no-blocks'); reasons[r] = reasons.get(r, 0) + 1
            if len(hits) < 100: break
            start += 100; time.sleep(0.5)
        time.sleep(0.5)
    save_json_atomic(out_path, pending, separators=(',', ':'))
    print('DONE', stats, '| pending', len(pending)); print('reasons', sorted(reasons.items(), key=lambda x: -x[1]))

if __name__ == '__main__':
    main()
