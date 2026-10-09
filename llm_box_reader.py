#!/usr/bin/env python3
"""LLM reading tier for newspaper OCR box scores (prototype).

Takes OCR text the deterministic parser rejected, asks Claude to reconstruct
the box score for ONE known game, then applies the same arithmetic gates the
parser uses: every team's player points must sum to the known final score,
and (when FG/FT are printed) each player's points must equal 2*FG + FT
(+3*3PM once the arc exists). Nothing reaches the store on the model's say-so.

Usage:
  python3 llm_box_reader.py dth   [--limit N] [--model M]   # cached DigitalNC pages with a Totals line
  python3 llm_box_reader.py stan  [--limit N] [--model M]   # scratchpad/stan_fail/*.txt dumps
Writes archives/newspapers/llm_<src>_pending.json (same shape as the harvester) and a run report.
"""
import glob, json, os, re, sys, time
from datetime import date, timedelta
import anthropic

ROOT = os.path.dirname(os.path.abspath(__file__))
SCRATCH = '/private/tmp/claude-501/-Users-joshdavis-Projects-hoopsipedia/87911194-c48a-4107-a006-397591596f98/scratchpad'

def api_key():
    if os.environ.get('ANTHROPIC_API_KEY'): return os.environ['ANTHROPIC_API_KEY']
    for line in open(os.path.join(ROOT, '.dev.vars')):
        if line.startswith('ANTHROPIC_API_KEY='): return line.split('=', 1)[1].strip().strip('"')
    sys.exit('no ANTHROPIC_API_KEY')

PLAYER = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Surname as printed, OCR errors corrected only when obvious"},
        "pts": {"type": "integer"},
        "fg": {"type": ["integer", "null"], "description": "field goals made, null if not printed"},
        "fga": {"type": ["integer", "null"]},
        "ft": {"type": ["integer", "null"], "description": "free throws made"},
        "fta": {"type": ["integer", "null"]},
        "tp": {"type": ["integer", "null"], "description": "three-pointers made, null if not printed"},
        "reb": {"type": ["integer", "null"]},
        "ast": {"type": ["integer", "null"]},
        "pf": {"type": ["integer", "null"]},
    },
    "required": ["name", "pts", "fg", "fga", "ft", "fta", "tp", "reb", "ast", "pf"],
    "additionalProperties": False,
}
TEAM = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "score": {"type": "integer", "description": "final score as printed in the box's Totals line"},
        "players": {"type": "array", "items": PLAYER},
        "totals_pts": {"type": ["integer", "null"], "description": "points figure on the printed Totals line, if any"},
    },
    "required": ["name", "score", "players", "totals_pts"],
    "additionalProperties": False,
}
SCHEMA = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean", "description": "true only if the varsity box score for the requested game is present"},
        "columns": {"type": "string", "description": "the column layout you inferred, e.g. 'FG FT PF TP' or 'FG-FGA FT-FTA REB PF TP'"},
        "home": {"type": ["object", "null"], "properties": TEAM["properties"], "required": TEAM["required"], "additionalProperties": False},
        "away": {"type": ["object", "null"], "properties": TEAM["properties"], "required": TEAM["required"], "additionalProperties": False},
        "notes": {"type": "string"},
    },
    "required": ["found", "columns", "home", "away", "notes"],
    "additionalProperties": False,
}

SYSTEM = """You reconstruct college basketball box scores from noisy newspaper OCR text.
The OCR often splits a table into column-major runs (all the names, then all the FG numbers, then all the FT numbers, ...), glues digits together (e.g. '3174' = '31 74', '6.8' = '6 8'), or drops characters. Reassemble rows carefully: the k-th number in each column run belongs to the k-th player.
You are told which game to look for and its final score. Return found=false if the page does not contain the men's varsity box for that exact game (ignore freshman / JV / 'Wolflets'-style games, other sports, and other dates).
Rules: never invent a player or a number. If a value is unreadable, omit that player's optional fields (null) rather than guessing. Points per player must be consistent with 2*FG + FT (+3*3PT) when those columns are present. Put the team that the newspaper lists first in 'away' unless the text says otherwise; the requesting team's identity is given.
Use the OCR text only; do not use outside knowledge of the game to fill in numbers."""

def user_prompt(game, text):
    return (f"Game: {game['team']} vs {game['opp']} on {game['date']} (final {game['team']} {game['team_score']}, {game['opp']} {game['opp_score']}). "
            f"Three-point line in use: {'yes' if game['three_pt'] else 'no'}.\n"
            f"Find the varsity box score for this game in the OCR text below and transcribe every player row.\n\n<ocr>\n{text}\n</ocr>")

def gate(res, game):
    """Return (ok, reason). Mirrors the harvester's acceptance tests."""
    if not res.get('found'): return False, 'model:not-found'
    teams = [t for t in (res.get('home'), res.get('away')) if t]
    if len(teams) != 2: return False, 'model:one-team'
    want = {game['team_score'], game['opp_score']}
    got = {t['score'] for t in teams}
    if got != want: return False, f'score-mismatch:{sorted(got)}'
    for t in teams:
        if len(t['players']) < 5: return False, 'too-few-players'
        s = sum(p['pts'] for p in t['players'])
        if s != t['score']: return False, f'pts-sum:{s}!={t["score"]}'
        for p in t['players']:
            if p['fg'] is not None and p['ft'] is not None:
                exp = 2 * p['fg'] + p['ft'] + (p['tp'] or 0)
                if exp != p['pts']: return False, f'row-arith:{p["name"]}'
            if p['fga'] is not None and p['fg'] is not None and p['fg'] > p['fga']: return False, f'fg>fga:{p["name"]}'
            if p['fta'] is not None and p['ft'] is not None and p['ft'] > p['fta']: return False, f'ft>fta:{p["name"]}'
    return True, 'ok'

def to_record(res, game, source, url):
    def conv(t):
        out = []
        for p in t['players']:
            r = {'name': p['name'], 'pts': p['pts']}
            if p['fg'] is not None: r['fg'] = f"{p['fg']}-{p['fga']}" if p['fga'] is not None else str(p['fg'])
            if p['ft'] is not None: r['ft'] = f"{p['ft']}-{p['fta']}" if p['fta'] is not None else str(p['ft'])
            for k in ('tp', 'reb', 'ast', 'pf'):
                if p[k] is not None: r[k] = p[k]
            out.append(r)
        return out
    teams = [res['home'], res['away']]
    mine = next(t for t in teams if t['score'] == game['team_score'] and (t['score'] != game['opp_score'] or game['team'].split()[0].lower() in t['name'].lower()))
    other = next(t for t in teams if t is not mine)
    return {'source': source, 'date': game['date'], 'url': url, 'reader': 'llm',
            'teams': [{'name': game['team'], 'score': game['team_score'], 'players': conv(mine)},
                      {'name': game['opp'], 'score': game['opp_score'], 'players': conv(other)}]}

# ---------- item sources ----------
def items_dth():
    H = json.load(open(os.path.join(ROOT, 'data.json')))['H']
    log = json.load(open(os.path.join(ROOT, 'games', '153.json'))); games = log.get('games', log)
    by_date = {g['date']: g for g in games if g.get('date')}
    state = json.load(open(os.path.join(ROOT, 'archives', 'newspapers', 'dth_state.json')))
    for f in sorted(glob.glob(os.path.join(ROOT, 'archives', 'newspapers', 'ocr', 'sn9*', '*', 'seq-*.txt'))):
        txt = open(f).read()
        if not re.search(r'totals', txt, re.I): continue
        lccn, dd, seq = f.split('/')[-3:]
        d = date.fromisoformat(dd); g = None
        for off in (1, 2, 3):
            g = by_date.get(str(d - timedelta(days=off)))
            if g and g.get('pts') is not None: break
            g = None
        if not g or state.get(g['date']) == 'ok' or lccn == 'sn96080312': continue
        game = {'team': H['153'][0], 'opp': H[str(g['opp'])][0], 'date': g['date'],
                'team_score': int(g['pts']), 'opp_score': int(g['opp_pts']), 'three_pt': g['date'] >= '1986-11-01'}
        yield {'label': f'{dd}/{seq}', 'game': game, 'text': txt[:60000],
               'source': 'The Daily Tar Heel (DigitalNC)', 'url': f'https://newspapers.digitalnc.org/lccn/{lccn}/{dd}/ed-1/{seq[:-4]}/'}

def items_stan():
    H = json.load(open(os.path.join(ROOT, 'data.json')))['H']
    log = json.load(open(os.path.join(ROOT, 'games', '24.json'))); games = log.get('games', log)
    by_date = {g['date']: g for g in games if g.get('date')}
    files = sorted(glob.glob(os.path.join(SCRATCH, 'stan_fail', '*.txt')))
    # spread across decades: take every k-th file
    for f in files:
        txt = open(f).read()
        first, _, body = txt.partition('\n')
        if not first.startswith('CANDS'): continue
        cands = eval(first[6:])
        for (d, my, opp) in cands:
            g = by_date.get(d)
            if not g: continue
            game = {'team': H['24'][0], 'opp': H[str(g['opp'])][0], 'date': d, 'team_score': my, 'opp_score': opp, 'three_pt': d >= '1986-11-01'}
            yield {'label': f'{os.path.basename(f)}:{d}', 'game': game, 'text': body[:60000],
                   'source': 'The Stanford Daily (archives.stanforddaily.com)', 'url': f'https://archives.stanforddaily.com/{os.path.basename(f)[:4]}/{os.path.basename(f)[5:7]}/{os.path.basename(f)[8:10]}'}
            break

def main():
    src = sys.argv[1]
    opt = lambda k, dflt: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else dflt
    limit = int(opt('--limit', 0)); model = opt('--model', 'claude-sonnet-5-5'); stride = int(opt('--stride', 1))
    client = anthropic.Anthropic(api_key=api_key())
    items = list(items_dth() if src == 'dth' else items_stan())[::stride]
    only = opt('--only', '')
    if only: items = [it for it in items if it['game']['date'] in only.split(',')]
    if limit: items = items[:limit]
    out_path = os.path.join(ROOT, 'archives', 'newspapers', f'llm_{src}_pending.json')
    pending = json.load(open(out_path)) if os.path.exists(out_path) else {}
    report = []; usage = {'in': 0, 'out': 0}; t0 = time.time()
    for n, it in enumerate(items, 1):
        g = it['game']
        try:
            resp = client.messages.create(
                model=model, max_tokens=8000, system=SYSTEM,
                messages=[{"role": "user", "content": user_prompt(g, it['text'])}],
                output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
            )
        except anthropic.APIError as e:
            report.append((it['label'], g['date'], 'api-error', str(e)[:120])); print(n, it['label'], 'API ERROR', str(e)[:120], flush=True); continue
        usage['in'] += resp.usage.input_tokens; usage['out'] += resp.usage.output_tokens
        res = json.loads(next(b.text for b in resp.content if b.type == 'text'))
        ok, why = gate(res, g)
        if ok:
            season_end = int(g['date'][:4]) + (1 if int(g['date'][5:7]) >= 8 else 0)
            key = f"{season_end}/{re.sub(r'[^a-z0-9]+','-',g['team'].lower()).strip('-')}-vs-{re.sub(r'[^a-z0-9]+','-',g['opp'].lower()).strip('-')}-{g['date']}"
            pending[key] = to_record(res, g, it['source'], it['url'])
        report.append((it['label'], g['date'], why, res.get('columns', ''), res.get('notes', '')[:140]))
        print(f"{n}/{len(items)} {it['label']} {g['date']} {g['team_score']}-{g['opp_score']} -> {why} [{res.get('columns','')}] {res.get('notes','')[:100]}", flush=True)
        json.dump(pending, open(out_path, 'w'), separators=(',', ':'))
    acc = sum(1 for r in report if r[2] == 'ok'); nf = sum(1 for r in report if r[2] == 'model:not-found')
    print(f"\nDONE {len(report)} calls | accepted {acc} | model said not-found {nf} | failed gates {len(report)-acc-nf} | "
          f"tokens in {usage['in']} out {usage['out']} | {(time.time()-t0)/60:.1f} min | pending {len(pending)} -> {out_path}")
    json.dump(report, open(os.path.join(SCRATCH, f'llm_{src}_report.json'), 'w'), indent=1)

if __name__ == '__main__':
    main()
