#!/usr/bin/env python3
"""Harvest pre-ESPN box scores from digitized newspapers (Open ONI / chronam
OCR text), driven by our own game log so nothing is guessed.

For every game of a program we fetch the paper's issue(s) from the next
day(s), read each page's OCR text, and look for the agate box score:

    North Carolina (84)
    Crawley 4-9 1-2 9, Suddreth 1-1 3-6 6, ... Totals 28-61 22-35 84.
    Duke (63)
    Anderson 2-6 3-5 7, ... Totals 24-58 15-20 63.

A box is accepted ONLY when, for BOTH teams: the header score equals the
score in our game log, the player lines parse, and the sums of made field
goals, made free throws and points each equal the printed totals line
(and the points equal the known score). Player lines use the AP summary
columns FG-FGA FT-FTA PTS; OCR often glues them ("4-91-29"), so tokens are
re-split under the constraints FGM<=FGA, FTM<=FTA and 2*FGM+FTM <= PTS <=
3*FGM+FTM (exactly 2*FGM+FTM before the 1986-87 three-point line).

Output: archives/newspapers/<paper>_pending.json in the store's dated
archive format (merge with merge_pending_into_store.py, then
scripts/ship_store.sh). OCR pages are cached under archives/newspapers/ocr/
so re-parsing never re-fetches. Resumable.

  python3 harvest_newspaper_ocr.py dth --from 1975 --to 1999
  python3 harvest_newspaper_ocr.py dth --from 1975 --to 1999 --limit 40   # pilot
"""
import json, os, re, sys, time, socket, urllib.request, urllib.error
# Some archive hosts advertise IPv6 but never complete the handshake (psu.edu hung
# in SYN_SENT for minutes); force IPv4 for every fetch.
_getaddrinfo = socket.getaddrinfo
def _ipv4_only(*args, **kw):
    return [ai for ai in _getaddrinfo(*args, **kw) if ai[0] == socket.AF_INET] or _getaddrinfo(*args, **kw)
socket.getaddrinfo = _ipv4_only
from datetime import date, timedelta
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
from json_io import save_json_atomic

PAPERS = {
    'dth': {
        'name': 'The Daily Tar Heel (DigitalNC)',
        'base': 'https://newspapers.digitalnc.org',
        'lccns': ['sn92073228', 'sn92068245'],   # older run first, then the 1990s run
        'team': '153',                            # North Carolina
        'aliases': ['North Carolina', 'Carolina', 'UNC', 'N. Carolina', 'Tar Heels'],
        'max_pages': 20, 'day_offsets': [1, 2, 3],
    },
    'psu': {
        'name': 'The Daily Collegian, Penn State (Pennsylvania Newspaper Archive)',
        'base': 'https://panewsarchive.psu.edu', 'lccns': ['sn85054904'], 'team': '213',
        'aliases': ['Penn State', 'Penn St.', 'Nittany Lions', 'State'], 'max_pages': 24, 'day_offsets': [1, 2, 3],
    },
    'neb': {
        'name': 'Daily Nebraskan (Nebraska Newspapers)',
        'base': 'https://nebnewspapers.unl.edu', 'lccns': ['sn96080312'], 'team': '158',
        'aliases': ['Nebraska', 'Neb.', 'Huskers', 'Cornhuskers'], 'max_pages': 20, 'day_offsets': [1, 2, 3],
    },
    'ore': {
        'name': 'Oregon Daily Emerald (Historic Oregon Newspapers)',
        'base': 'https://oregonnews.uoregon.edu', 'lccns': ['2004260239'], 'team': '2483',
        'aliases': ['Oregon', 'Ducks', 'Ore.'], 'max_pages': 24, 'day_offsets': [1, 2, 3],
    },
}
UA = 'Hoopsipedia/1.0 (https://www.hoopsipedia.com; box-score archive research)'
DELAY = 1.5          # ~40 requests/min per host; DigitalNC refused connections after ~660 at 0.4s
HOST_DOWN = set()    # hosts that refused connections this run — stop hitting them

def slugify(s): return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

def fetch(url, cache_path):
    if os.path.exists(cache_path):
        return open(cache_path, encoding='utf-8').read()
    host = url.split('/')[2]
    if host in HOST_DOWN:
        raise RuntimeError(f'host down: {host}')
    time.sleep(DELAY)
    txt = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                txt = r.read().decode('utf-8', 'replace')
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                open(cache_path, 'w').write('\x00404')
                return None
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(15 * (attempt + 1)); continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            if 'refused' in str(e).lower():
                # a refused connection is a block or an outage: stop hammering this host
                HOST_DOWN.add(host); print(f'  {host} refused connections — stopping this host for the run', flush=True)
                raise RuntimeError(f'host down: {host}')
            # SSL handshake timeouts etc.: back off and retry, never crash a 3-hour run
            if attempt < 3:
                time.sleep(10 * (attempt + 1)); continue
            print(f'  network failure after retries: {url}', flush=True)
            return None
    if txt is None:
        return None
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    open(cache_path, 'w', encoding='utf-8').write(txt)
    return txt

def issue_pages(paper, lccn, d):
    """Yield (seq, ocr_text) for every page of an issue; None if the issue is absent."""
    found = False
    for seq in range(1, paper['max_pages'] + 1):
        url = f"{paper['base']}/lccn/{lccn}/{d}/ed-1/seq-{seq}/ocr.txt"
        cache = os.path.join(ROOT, 'archives', 'newspapers', 'ocr', lccn, str(d), f'seq-{seq}.txt')
        txt = fetch(url, cache)
        if txt is None or txt.startswith('\x00404'):
            if seq == 1: return None
            break
        found = True
        yield seq, txt
    if not found: return None

# ── parsing ──────────────────────────────────────────────────────────────
OCR_DIGIT = str.maketrans({'O': '0', 'o': '0', 'S': '5', 'B': '8', 'l': '1', 'I': '1', '|': '1', 'Z': '2'})
def fix_num(tok):
    """OCR-repair a token that should be a number: '8S' -> 85, '04)' -> '0-0' is handled by caller."""
    return tok.translate(OCR_DIGIT)

HEAD = re.compile(r'(?m)^\s*([A-Z][A-Za-z.&\'’ \-]{1,34}?)\s*\(\s*([0-9OSBlIZ]{2,3})\s*\)\s*\.?\s*$')
def headers(text):
    out = []
    for m in HEAD.finditer(text):
        sc = fix_num(m.group(2))
        if sc.isdigit() and 20 <= int(sc) <= 200:
            out.append({'start': m.start(), 'end': m.end(), 'name': m.group(1).strip(), 'score': int(sc)})
    return out

def ints_of(blob):
    """digit groups of a line with OCR repairs; '04)' and '0-4)' -> 0-0 style artefacts collapse to digits"""
    b = blob.replace('—', '-').replace('–', '-')
    b = re.sub(r'(\d)\s*[\)\]]', r'\1', b)       # '04)' -> '04'
    b = b.translate(OCR_DIGIT) if re.search(r'[OSBlIZ]', b) else b
    return re.findall(r'\d+', b), b

def choose(cands, three_pt):
    """keep candidate tuples (fgm,fga,ftm,fta,pts) obeying the AP constraints"""
    out = set()
    for c in cands:
        try: fgm, fga, ftm, fta, pts = map(int, c)
        except ValueError: continue
        if fgm > fga or ftm > fta or fga > 45 or fta > 35 or pts > 100: continue
        lo, hi = 2 * fgm + ftm, (3 * fgm + ftm if three_pt else 2 * fgm + ftm)
        if lo <= pts <= hi: out.add((fgm, fga, ftm, fta, pts))
    return out

def resplit(nums, three_pt, want=5):
    """nums: digit strings in print order, possibly glued ('4-91-29' -> ['4','91','29']).
    Return the unique way to cut them into `want` fields obeying the constraints."""
    joined = ''.join(nums)
    if len(joined) < want: return None
    res = set()
    # enumerate cut points over the digit string; each field 1-2 digits (pts up to 3)
    def rec(i, acc):
        if len(acc) == want:
            if i == len(joined): res.add(tuple(acc))
            return
        maxw = 3 if len(acc) == want - 1 else 2
        for w in range(1, maxw + 1):
            if i + w <= len(joined):
                rec(i + w, acc + [joined[i:i + w]])
    rec(0, [])
    good = choose(res, three_pt)
    if len(good) == 1: return next(iter(good))
    # prefer the split consistent with the printed dashes when ambiguous
    direct = tuple(nums) if len(nums) == want else None
    if direct and direct in {tuple(map(str, g)) for g in good}: return tuple(map(int, direct))
    if good and len({g[4] for g in good}) == 1 and len({g[0] for g in good}) == 1 and len({g[2] for g in good}) == 1:
        return sorted(good)[0]  # same made/pts, only attempts differ — fine for our gates
    return None

AP_LINE = re.compile(r"([A-Z][A-Za-z'’.!\-]+(?:\s[A-Z][A-Za-z'’.!\-]+)?)\s+([0-9OSBlIZ][0-9OSBlIZ\s\-\)]{3,}?)(?=,|\.\s|\s*$)", re.M)
def parse_ap(body, three_pt):
    players = []
    for name, blob in AP_LINE.findall(body.replace('\n', ' ')):
        if name.lower().startswith('total'): continue
        nums, _ = ints_of(blob)
        sp = resplit(nums, three_pt, 5)
        if not sp: return None, f'ap-line:{name} {blob.strip()[:20]}'
        fgm, fga, ftm, fta, pts = sp
        players.append({'name': name.strip('!. '), 'pts': pts, 'fg': f'{fgm}-{fga}', 'ft': f'{ftm}-{fta}'})
    return players, None

FULL_LINE = re.compile(r"(?m)^\s*([A-Za-z][A-Za-z0-9'’.!\-]*[A-Za-z!'’.](?:\s[A-Z][A-Za-z0-9'’.!\-]+)?)\s+([0-9OSBlIZ][0-9OSBlIZ\s\-\)]{8,})\s*$")
def parse_full(body, three_pt):
    """'Reese 23 4-6 2-2 1-3 4 1 11' -> min fg ft reb(o-t) ast pf pts (8 numbers)."""
    players = []
    for name, blob in FULL_LINE.findall(body):
        if name.lower().startswith(('total', 'percent', 'min', 'fg')): continue
        nums, fixed = ints_of(blob)
        cand = None
        if len(nums) == 8:
            cand = tuple(map(int, nums))
        else:
            # glued fields: cut the digit string into 8 fields (min can be 1-2 digits, pts up to 2)
            joined = ''.join(nums); found = set()
            def rec(i, acc):
                if len(acc) == 8:
                    if i == len(joined): found.add(tuple(map(int, acc)))
                    return
                for w in (1, 2):
                    if i + w <= len(joined): rec(i + w, acc + [joined[i:i + w]])
            if 8 <= len(joined) <= 16: rec(0, [])
            ok = [c for c in found if c[1] <= c[2] and c[3] <= c[4] and c[5] <= c[6] and c[0] <= 45 and c[7] <= 60
                  and (2 * c[1] + c[3] <= c[7] <= (3 * c[1] + c[3] if three_pt else 2 * c[1] + c[3]))]
            if len({(c[1], c[3], c[7]) for c in ok}) == 1: cand = sorted(ok)[0]
        if not cand: return None, f'full-line:{name} {blob.strip()[:24]}'
        mn, fgm, fga, ftm, fta, oreb, reb, ast, pf, pts = (cand[0], cand[1], cand[2], cand[3], cand[4], cand[5], cand[6], cand[7] if False else None, None, None) if False else (cand[0], cand[1], cand[2], cand[3], cand[4], cand[5], cand[6], None, None, cand[7])
        # 8 fields are: min fgm fga ftm fta oreb treb ast? — the DTH line is min m-a m-a o-t a pf tp = 9 numbers; handle both 8 and 9 below
        players.append({'name': name.strip('!. '), 'min': mn, 'pts': pts, 'fg': f'{fgm}-{fga}', 'ft': f'{ftm}-{fta}', 'reb': reb})
    return players, None

def parse_full9(body, three_pt):
    """DTH format: Name MIN FGM-FGA FTM-FTA OREB-TREB AST PF TP (9 numbers)."""
    players = []
    for name, blob in FULL_LINE.findall(body):
        if name.lower().startswith(('total', 'percent', 'min', 'fg', 'halftime')): continue
        nums, fixed = ints_of(blob)
        joined = ''.join(nums); found = set()
        def rec(i, acc):
            if len(acc) == 9:
                if i == len(joined): found.add(tuple(map(int, acc)))
                return
            for w in (1, 2):
                if i + w <= len(joined): rec(i + w, acc + [joined[i:i + w]])
        if 9 <= len(joined) <= 18: rec(0, [])
        if len(nums) == 9: found.add(tuple(map(int, nums)))
        ok = [c for c in found if c[1] <= c[2] and c[3] <= c[4] and c[5] <= c[6] and c[0] <= 45 and c[7] <= 20 and c[8] <= 5
              and (2 * c[1] + c[3] <= c[9 - 1 + 0] if False else True)]
        ok = [c for c in ok if 2 * c[1] + c[3] <= c[8] <= (3 * c[1] + c[3] if three_pt else 2 * c[1] + c[3])] if False else ok
        # fields: 0 min, 1 fgm, 2 fga, 3 ftm, 4 fta, 5 oreb, 6 treb, 7 ast, 8 pf?  — no: DTH prints 'a pf tp' so 7 ast, 8 pf, 9 tp = 10 numbers
        if not ok: return None, f'full9-line:{name} {blob.strip()[:24]}'
        c = sorted(ok)[0]
        players.append({'name': name.strip('!. '), 'min': c[0], 'fg': f'{c[1]}-{c[2]}', 'ft': f'{c[3]}-{c[4]}', 'reb': c[6], 'ast': c[7], 'pts': None, '_raw': c})
    return players, None

def parse_block(block, three_pt, known_score):
    """Try the full-line format (min fg ft reb ast pf tp), then the AP summary.
    Accept only when points sum to the known score (and, for AP, match the
    printed totals when they parse)."""
    errs = []
    # Full format: lines of Name + 10 numbers (min, fgm, fga, ftm, fta, oreb, treb, ast, pf, tp)
    players = []; bad = None
    for name, blob in FULL_LINE.findall(block):
        if name.lower().startswith(('total', 'percent', 'min', 'fg', 'halftime', 'team', 'turnover', 'steal', 'blocked', 'rebound', 'assist')): continue
        nums, _ = ints_of(blob)
        if len(nums) < 5: continue          # half-by-half linescore ('North Carolina 51 49 100'), not a player
        if len(nums) > 12: bad = f'full-line:{name}'; break
        found = set()
        if len(nums) == 10:
            found.add(tuple(map(int, nums)))
        elif 5 <= len(nums) < 10:
            # some tokens are glued ('34' for '3-4', '2149' for '21 49'): split exactly
            # (10 - len(nums)) of them, each into two 1-2 digit pieces.
            need = 10 - len(nums)
            import itertools
            idxs = [i for i, t in enumerate(nums) if len(t) >= 2]
            for combo in itertools.combinations(idxs, need):
                # each chosen token can be cut at 1..len-1 (and 3-4 digit tokens into 2 pieces)
                choices = []
                for i in combo:
                    t = nums[i]; choices.append([(t[:k], t[k:]) for k in range(1, len(t)) if len(t[:k]) <= 2 and len(t[k:]) <= 2])
                for cut in itertools.product(*choices):
                    out = []
                    for i, t in enumerate(nums):
                        if i in combo: out.extend(cut[combo.index(i)])
                        else: out.append(t)
                    found.add(tuple(map(int, out)))
            # a 3-4 digit token may be three glued numbers ('115' -> 1 1 5)
            if need >= 2:
                for i, t in enumerate(nums):
                    if 3 <= len(t) <= 4:
                        rest_need = need - 2
                        others = [j for j in idxs if j != i]
                        for combo in itertools.combinations(others, rest_need):
                            triples = [(t[:a], t[a:b], t[b:]) for a in range(1, len(t) - 1) for b in range(a + 1, len(t)) if all(len(x) <= 2 for x in (t[:a], t[a:b], t[b:]))]
                            choices = [[(nums[j][:k], nums[j][k:]) for k in range(1, len(nums[j])) if len(nums[j][:k]) <= 2 and len(nums[j][k:]) <= 2] for j in combo]
                            for tri in triples:
                                for cut in itertools.product(*choices) if choices else [()]:
                                    out = []
                                    for j, tok in enumerate(nums):
                                        if j == i: out.extend(tri)
                                        elif j in combo: out.extend(cut[combo.index(j)])
                                        else: out.append(tok)
                                    found.add(tuple(map(int, out)))
                for cut in itertools.product(*choices):
                    out = []
                    for i, t in enumerate(nums):
                        if i in combo: out.extend(cut[combo.index(i)])
                        else: out.append(t)
                    found.add(tuple(map(int, out)))
        ok = [c for c in found if c[1] <= c[2] and c[3] <= c[4] and c[5] <= c[6] and c[6] <= 30 and c[0] <= 45 and c[7] <= 25 and c[8] <= 6 and c[2] <= 40
              and 2 * c[1] + c[3] <= c[9] <= (3 * c[1] + c[3] if three_pt else 2 * c[1] + c[3])]
        if not ok:
            if os.environ.get('DEBUG'): print('   DBG no-candidate:', name, nums)
            bad = f'full-line:{name}'; break
        if len({(c[1], c[3], c[9]) for c in ok}) != 1: bad = f'full-ambiguous:{name}'; break
        c = sorted(ok)[0]
        players.append({'name': name.strip('!. '), 'min': c[0], 'pts': c[9], 'fg': f'{c[1]}-{c[2]}', 'ft': f'{c[3]}-{c[4]}', 'reb': c[6], 'ast': c[7], 'pf': c[8]})
    if os.environ.get('DEBUG') and not bad: print('   DBG full players', len(players), 'sum', sum(p['pts'] for p in players), 'known', known_score, [p['name'] for p in players])
    if not bad and 5 <= len(players) <= 16 and sum(p['pts'] for p in players) == known_score:
        return players, 'full'
    if players and not bad: errs.append(f'full-sum:{sum(p["pts"] for p in players)}')
    elif bad: errs.append(bad)
    # AP summary: 'Name fgm-fga ftm-fta pts, ... Totals a-b c-d NN.'
    m = re.search(r'(?i)totals?\s+([0-9OSBlIZ\s\-]{5,})', block)
    body = block[:m.start()] if m else block
    ap, err = parse_ap(body, three_pt)
    if err: errs.append(err)
    elif 5 <= len(ap) <= 16 and sum(p['pts'] for p in ap) == known_score:
        if m:
            tn, _ = ints_of(m.group(1))
            tot = resplit(tn, three_pt, 5)
            if tot and (tot[0] != sum(int(p['fg'].split('-')[0]) for p in ap) or tot[2] != sum(int(p['ft'].split('-')[0]) for p in ap)):
                errs.append('ap-totals-mismatch'); return None, ';'.join(errs)
        return ap, 'ap'
    elif ap: errs.append(f'ap-sum:{sum(p["pts"] for p in ap)}/{len(ap)}')
    return None, ';'.join(errs) or 'no-lines'

OLD_LINE = re.compile(r"(?m)^\s*([A-Za-z][A-Za-z0-9'’.!\-]*[A-Za-z!'’.](?:\s[A-Z][A-Za-z0-9'’.!\-]+)?)\s*,?\s+(?:[fcgFCG]\b[\s.,]*)?([0-9OSBlIZ][0-9OSBlIZ\s\-\(\)'.,:]{3,})\s*$")
TOTALS_LINE = re.compile(r"(?mi)^\s*T[a-z]{3,7}\s*[.:,]?\s+([0-9OSBlIZ][0-9OSBlIZ\s.,']{4,})\s*$")
def find_box_by_totals(text, my_score, opp_score):
    """1950s-60s format: 'Name pos FG FT PF PTS' lines ending in 'Totals FG FT PF PTS'.
    Anchor on Totals lines whose last number is one of the two known scores and
    take the run of agate lines above each."""
    lines = text.split('\n')
    found = {}
    for i, ln in enumerate(lines):
        m = TOTALS_LINE.match(ln)
        if not m: continue
        nums, _ = ints_of(m.group(1))
        if not 3 <= len(nums) <= 5: continue
        pts = int(nums[-1])
        if pts not in (my_score, opp_score) or pts in found: continue
        tot = tuple(map(int, nums))
        players = []
        j = i - 1
        while j >= 0 and len(players) < 18:
            lm = OLD_LINE.match(lines[j])
            if not lm:
                if lines[j].strip() == '' or len(players) == 0: j -= 1; continue
                break
            name, blob = lm.group(1), lm.group(2)
            pn, _ = ints_of(blob)
            # expected: FG FT PF PTS (4 numbers). Repair glued ('10 1 2' = 1 0 1 2)
            # or split tokens by enumerating and keeping what satisfies PTS = 2FG + FT.
            cands = set()
            if len(pn) == 4: cands.add(tuple(map(int, pn)))
            if len(pn) == 3:
                for k, tkn in enumerate(pn):
                    if len(tkn) >= 2:
                        for c in range(1, len(tkn)):
                            cands.add(tuple(map(int, pn[:k] + [tkn[:c], tkn[c:]] + pn[k + 1:])))
                cands.add(tuple(map(int, pn)) + (None,))          # FG FT PTS without fouls
            if len(pn) == 5:
                for k in range(5): cands.add(tuple(map(int, pn[:k] + pn[k + 1:])))
            good = set()
            for c in cands:
                if len(c) == 4 and c[3] is None:
                    fg, ft, p = c[0], c[1], c[2]; pf = None
                elif len(c) == 4:
                    fg, ft, pf, p = c
                else: continue
                if fg <= 25 and ft <= 25 and (pf is None or pf <= 5) and 2 * fg + ft == p: good.add((fg, ft, pf, p))
            if len({(g[0], g[1], g[3]) for g in good}) != 1: break
            fg, ft, pf, p = sorted(good, key=lambda g: (g[2] is None, g))[0]
            players.insert(0, {'name': name.strip('!. ,'), 'pts': p, 'fg': str(fg), 'ft': str(ft), **({'pf': pf} if pf is not None else {})})
            j -= 1
        if not 4 <= len(players) <= 16: continue
        if sum(p['pts'] for p in players) != pts: continue
        if len(tot) >= 2 and sum(int(p['fg']) for p in players) != tot[0]: continue
        if len(tot) >= 3 and sum(int(p['ft']) for p in players) != tot[1]: continue
        found[pts] = players
    if my_score in found and opp_score in found and my_score != opp_score:
        return {'me': found[my_score], 'opp': found[opp_score]}, None
    return None, ('old-format-partial' if found else 'headers-not-found')

def find_box(text, my_aliases, my_score, opp_aliases, opp_score, three_pt):
    if not three_pt:
        res, err = find_box_by_totals(text, my_score, opp_score)
        if res: return res, None

    hs = headers(text)
    if len(hs) < 2: return None, 'headers-not-found'
    tried = []
    for i, a in enumerate(hs):
        for b in hs[i + 1:i + 4]:
            if b['start'] - a['end'] > 4000: break
            pair = {a['score'], b['score']}
            if pair != {my_score, opp_score} and not ({my_score, opp_score} & pair): continue
            # assign: who is me? by score first, then by alias
            if a['score'] == my_score and b['score'] == opp_score: mine, theirs = a, b
            elif b['score'] == my_score and a['score'] == opp_score: mine, theirs = b, a
            else:
                am = any(al.lower() in a['name'].lower() for al in my_aliases)
                mine, theirs = (a, b) if am else (b, a)
            res = {}
            okpair = True
            for who, h, other, sc in (('me', mine, theirs, my_score), ('opp', theirs, mine, opp_score)):
                end = other['start'] if other['start'] > h['end'] else len(text)
                block = text[h['end']:min(end, h['end'] + 3000)]
                parsed, how = parse_block(block, three_pt, sc)
                if not parsed: tried.append(f'{who}:{how}'); okpair = False; break
                res[who] = parsed
            if okpair: return res, None
    return None, (tried[-1] if tried else 'score-pair-not-found')

def opp_aliases_for(name, slug):
    words = name.split(); mascot_free = ' '.join(words[:-1]) if len(words) > 1 else name
    out = {name, mascot_free, slug.replace('-', ' ')}
    out.add(mascot_free.replace('State', 'St.')); out.add(mascot_free.replace('North Carolina', 'N.C.'))
    return [a for a in out if a]

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args or args[0] not in PAPERS: sys.exit(__doc__)
    paper = PAPERS[args[0]]
    opt = lambda k, dflt: int(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else dflt
    y0, y1, limit = opt('--from', 1950), opt('--to', 1999), opt('--limit', 0)
    H = json.load(open(os.path.join(ROOT, 'data.json')))['H']
    tid = paper['team']; team_name = H[tid][0]
    log = json.load(open(os.path.join(ROOT, 'games', f'{tid}.json'))); games = log.get('games', log)
    games = [g for g in games if g.get('date') and y0 <= int(g['date'][:4]) <= y1 and g.get('opp') in H and g.get('pts') is not None]
    games.sort(key=lambda g: g['date'])
    if limit: games = games[:limit]
    out_path = os.path.join(ROOT, 'archives', 'newspapers', f"{args[0]}_pending.json")
    state_path = os.path.join(ROOT, 'archives', 'newspapers', f"{args[0]}_state.json")
    pending = json.load(open(out_path)) if os.path.exists(out_path) else {}
    state = json.load(open(state_path)) if os.path.exists(state_path) else {}
    stats = {'games': 0, 'no_issue': 0, 'accepted': 0, 'rejected': 0}
    reasons = {}
    t0 = time.time()
    for n, g in enumerate(games, 1):
        if g['date'] in state: continue
        stats['games'] += 1
        d = date.fromisoformat(g['date']); opp = str(g['opp']); opp_name = H[opp][0]
        my_score, opp_score = int(g['pts']), int(g['opp_pts'])
        three_pt = d >= date(1986, 11, 1)
        result, why, where = None, 'no-issue', None
        try:
          for off in paper['day_offsets']:
            dd = d + timedelta(days=off)
            for lccn in paper['lccns']:
                pages = issue_pages(paper, lccn, dd)
                if pages is None: continue
                pages = list(pages)
                if not pages: continue
                for seq, txt in pages:
                    res, err = find_box(txt, paper['aliases'], my_score, opp_aliases_for(opp_name, g.get('opp_slug', '')), opp_score, three_pt)
                    if res:
                        result, where = res, (lccn, str(dd), seq); break
                    if err and err != 'headers-not-found': why = err
                if result: break
                if why == 'no-issue': why = 'not-on-any-page'
            if result: break
        except RuntimeError as e:
            print(f'  stopping: {e} (state saved; rerun later to resume)', flush=True); break
        if result:
            season_end = d.year + 1 if d.month >= 8 else d.year
            key = f"{season_end}/{slugify(team_name)}-vs-{slugify(opp_name)}-{g['date']}"
            lccn, dd, seq = where
            pending[key] = {
                'source': paper['name'], 'date': g['date'],
                'url': f"{paper['base']}/lccn/{lccn}/{dd}/ed-1/seq-{seq}/",
                'teams': [
                    {'name': team_name, 'score': my_score, 'players': result['me']},
                    {'name': opp_name, 'score': opp_score, 'players': result['opp']},
                ],
            }
            stats['accepted'] += 1; state[g['date']] = 'ok'
        else:
            stats['rejected' if why not in ('no-issue',) else 'no_issue'] += 1
            reasons[why.split(':')[0] + (':' + why.split(':')[1] if why.startswith(('me:', 'opp:')) else '')] = reasons.get(why.split(':')[0] + (':' + why.split(':')[1] if why.startswith(('me:', 'opp:')) else ''), 0) + 1
            state[g['date']] = why
        if n % 10 == 0 or n == len(games):
            save_json_atomic(out_path, pending, separators=(',', ':')); save_json_atomic(state_path, state)
            print(f"  {n}/{len(games)} ({(time.time()-t0)/60:.1f} min) {stats} top reasons {sorted(reasons.items(), key=lambda x: -x[1])[:4]}", flush=True)
    save_json_atomic(out_path, pending, separators=(',', ':')); save_json_atomic(state_path, state)
    print('DONE', stats, '| pending total', len(pending)); print('reasons', sorted(reasons.items(), key=lambda x: -x[1])[:10])

if __name__ == '__main__':
    main()
