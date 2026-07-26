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

import html
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
    r'^\s*(?:TOTALS?|Totals?)\.*\s+(?P<fg>\d+-\d+)\s+(?P<tp3>\d+-\d+)\s+(?P<ft>\d+-\d+)\s+'
    r'\d+\s+\d+\s+\d+\s+\d+\s+(?P<tp>\d+)')

# Variant B: 1999-era FansOnly/OCSN template — made/attempted as SEPARATED
# columns ("FG FGA FG FGA FT FTA OF DE TOT PF TP A TO BLK S MIN"), names
# space-padded instead of dot-padded.
PLAYER_B_RE = re.compile(
    r'^\s*\d{1,3}\s+(?P<name>[A-Za-z].*?)\s{2,}(?:[fcg]\s+)?'
    r'(?P<fgm>\d+)\s+(?P<fga>\d+)\s+(?P<t3m>\d+)\s+(?P<t3a>\d+)\s+'
    r'(?P<ftm>\d+)\s+(?P<fta>\d+)\s+(?P<of>\d+)\s+(?P<de>\d+)\s+(?P<tot>\d+)\s+'
    r'(?P<pf>\d+)(?:-\d+)?\s+(?P<tp>\d+)\s+(?P<a>\d+)\s+(?P<to>\d+)\s+(?P<blk>\d+)\s+'
    r'(?P<s>\d+)\s+(?P<min>\d+)\s*$')
TOTALS_B_RE = re.compile(
    r'^\s*(?:TOTALS?|Totals?)\.*\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+'
    r'\d+\s+\d+\s+\d+\s+\d+(?:-\d+)?\s+(?P<tp>\d+)')
TEAM_HDR_RE = re.compile(
    r'^\s*(?:VISITORS?|HOME\s*TEAM)\s*:\s*(?P<name>.+?)\s*(?:\d+-\d+.*)?$')
DATE_RE = re.compile(r'^(?P<m>\d{1,2})[-/](?P<d>\d{1,2})[-/](?P<y>\d{2,4})\b')


def mk_date(y, m, d):
    """Build YYYY-MM-DD, or None if the source printed an impossible date.

    Real box scores do contain typos (a Troy 2007 file says "11/31/07"). An
    invalid date means we can't trust the game key, so the caller quarantines
    that game rather than storing it — and a bad date can no longer crash a
    whole harvest run mid-flight."""
    try:
        return datetime(y, m, d).strftime('%Y-%m-%d')
    except ValueError:
        return None


def clean_name(s):
    """Collapse whitespace, then strip trailing dot-leaders / starter asterisk
    the newer (mo2do) template appends after the name ("Rebassoo....... *").
    Trailing-only, so mid-name initials ("A.J. Smith") are preserved."""
    return re.sub(r'[.*\s]+$', '', re.sub(r'\s+', ' ', s).strip())


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
                date = mk_date(y, int(dm.group('m')), int(dm.group('d')))
        hm = TEAM_HDR_RE.match(plain)
        # Guard against the mo2do/CSTV template (post-2005): the SAME "HOME TEAM:"
        # prefix heads the play-by-play columns ("...TIME SCORE MAR VISI"). Reject
        # those, and cap at the first complete box so a duplicated box can't add a
        # 3rd/4th team and break the len(teams)==2 check.
        if (hm and 'Player Name' not in plain
                and 'SCORE' not in plain and 'TIME' not in plain):
            if len(teams) < 2:
                cur = {'name': hm.group('name').strip().title(), 'players': []}
                teams.append(cur)
            continue
        if cur is None:
            continue
        tm = TOTALS_RE.match(plain) or TOTALS_B_RE.match(plain)
        if tm:
            cur['score'] = int(tm.group('tp'))
            cur = cur if len(teams) < 2 else None
            continue
        pm = PLAYER_RE.match(plain)
        if pm:
            p = {'name': clean_name(pm.group('name')),
                 'fg': pm.group('fg'), 'tp': pm.group('tp3'), 'ft': pm.group('ft'),
                 'reb': int(pm.group('tot')), 'pf': int(pm.group('pf')),
                 'pts': int(pm.group('tp')), 'ast': int(pm.group('a')),
                 'to': int(pm.group('to')), 'blk': int(pm.group('blk')),
                 'stl': int(pm.group('s'))}
            if pm.group('min'):
                p['min'] = int(pm.group('min'))
            cur['players'].append(p)
            continue
        pb = PLAYER_B_RE.match(plain)
        if pb:
            cur['players'].append(
                {'name': clean_name(pb.group('name')),
                 'fg': f"{pb.group('fgm')}-{pb.group('fga')}",
                 'tp': f"{pb.group('t3m')}-{pb.group('t3a')}",
                 'ft': f"{pb.group('ftm')}-{pb.group('fta')}",
                 'reb': int(pb.group('tot')), 'pf': int(pb.group('pf')),
                 'pts': int(pb.group('tp')), 'ast': int(pb.group('a')),
                 'to': int(pb.group('to')), 'blk': int(pb.group('blk')),
                 'stl': int(pb.group('s')), 'min': int(pb.group('min'))})
    if not date or len(teams) != 2:
        return parse_variant_c(text)
    for t in teams:
        if 'score' not in t or not t['players']:
            return parse_variant_c(text)
        # checksum: totals row vs player sum
        if sum(p['pts'] for p in t['players']) != t['score']:
            return parse_variant_c(text)
    return {'date': date, 'teams': teams}


# Variant C: 1998-99 FansOnly template — team blocks headed by
# "{team}   M-A ... PF-D ...", starter asterisks, fouls as "PF-D" pairs,
# team-name-led totals rows, and prose dates ("January 2, 1999").
MONTHS = {m: i + 1 for i, m in enumerate(
    ['January', 'February', 'March', 'April', 'May', 'June', 'July',
     'August', 'September', 'October', 'November', 'December'])}
DATE_C_RE = re.compile(r'\b(' + '|'.join(MONTHS) + r')\s+(\d{1,2}),\s*(\d{4})')
PLAYER_C_RE = re.compile(
    r'^\s*\*?(?P<name>[A-Za-z][A-Za-z .\'-]*?)\s{2,}'
    r'(?P<fg>\d+-\d+)\s+(?P<tp3>\d+-\d+)\s+(?P<ft>\d+-\d+)\s+'
    r'(?P<of>\d+)\s+(?P<de>\d+)\s+(?P<tot>\d+)\s+(?P<pf>\d+)-\d+\s+'
    r'(?P<tp>\d+)\s+(?P<a>\d+)\s+(?P<to>\d+)\s+(?P<blk>\d+)\s+(?P<s>\d+)\s+(?P<min>\d+)\s*$')
TEAMROW_C_RE = re.compile(
    r'^\s*(?:#\d+\s+)?(?P<name>[A-Za-z][A-Za-z .&\'-]*?)\s{2,}'
    r'\d+-\d+\s+\d+-\d+\s+\d+-\d+\s+\d+\s+\d+\s+\d+\s+\d+-\d+\s+'
    r'(?P<tp>\d+)\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s*$')
HDR_C_RE = re.compile(r'^\s*(?:#\d+\s+)?(?P<name>[A-Za-z][A-Za-z .&\'-]*?)\s{2,}M-A\s+M-A')


def parse_variant_c(text):
    lines = [strip_tags(l) for l in text.split('\n')]
    date = None
    teams, cur = [], None
    for plain in lines:
        if date is None:
            dm = DATE_C_RE.search(plain)
            if dm:
                date = mk_date(int(dm.group(3)), MONTHS[dm.group(1)], int(dm.group(2)))
        hm = HDR_C_RE.match(plain)
        if hm:
            cur = {'name': hm.group('name').strip(), 'players': []}
            teams.append(cur)
            continue
        if cur is None:
            continue
        tm = TEAMROW_C_RE.match(plain)
        if tm and 'score' not in cur and tm.group('name').strip() == cur['name']:
            cur['score'] = int(tm.group('tp'))
            cur = None
            continue
        pm = PLAYER_C_RE.match(plain)
        if pm and pm.group('name').strip().lower() != 'team':
            p = {'name': pm.group('name').strip(),
                 'fg': pm.group('fg'), 'tp': pm.group('tp3'), 'ft': pm.group('ft'),
                 'reb': int(pm.group('tot')), 'pf': int(pm.group('pf')),
                 'pts': int(pm.group('tp')), 'ast': int(pm.group('a')),
                 'to': int(pm.group('to')), 'blk': int(pm.group('blk')),
                 'stl': int(pm.group('s')), 'min': int(pm.group('min'))}
            cur['players'].append(p)
    if not date or len(teams) != 2:
        return parse_variant_d(text)
    for t in teams:
        if 'score' not in t or not t['players']:
            return parse_variant_d(text)
        if sum(p['pts'] for p in t['players']) != t['score']:
            return parse_variant_d(text)
    return {'date': date, 'teams': teams}


# Variant D: FansOnly / Student Advantage AP-agate prose box (~1998-2001).
# Not fixed-width — a wire-service recap: a "Team A NN, Team B NN" score head,
# a prose date, then per-team blocks of comma-separated "Name FG-FGA FT-FTA PTS"
# entries that wrap freely across lines, closed by "Totals FG-FGA FT-FTA PTS."
# Thin box (per-player FG/FT/PTS only; rebounds/assists live in the footer), but
# the Totals-row checksum still gates every game. Example (Utah 74, Ripon 49):
#   RIPON (4-2)
#        Becker 4-14 2-2 10, VanDyken 6-11 2-2 17, ... Totals 15-42 14-16 49.
TEAMHDR_D_RE = re.compile(r'^\s*(?P<name>[A-Z][A-Za-z.&\'-]+(?:\s+[A-Z][A-Za-z.&\'-]+)*)\s*\(\d+-\d+\)\s*$')
TOTALS_D_RE = re.compile(r'\bTotals\s+\d+-\d+\s+\d+-\d+\s+(?P<tp>\d+)\s*\.')
PLAYER_D_RE = re.compile(
    r'(?P<name>[A-Za-z][A-Za-z.\'-]*(?:\s[A-Za-z.\'-]+)*?)\s+'
    r'(?P<fg>\d+-\d+)\s+(?P<ft>\d+-\d+)\s+(?P<pts>\d+)\s*(?=[,.])')


def parse_variant_d(text):
    lines = [strip_tags(l) for l in text.split('\n')]
    dm = DATE_C_RE.search('\n'.join(lines))
    if not dm:
        return parse_variant_e(text)
    date = mk_date(int(dm.group(3)), MONTHS[dm.group(1)], int(dm.group(2)))
    if not date:
        return None
    teams = []
    i = 0
    while i < len(lines) and len(teams) < 2:
        hm = TEAMHDR_D_RE.match(lines[i])
        if not hm:
            i += 1
            continue
        # accumulate this team's block until (and including) its Totals row
        blob, j = [], i + 1
        while j < len(lines):
            blob.append(lines[j])
            if TOTALS_D_RE.search(lines[j]):
                break
            j += 1
        if j >= len(lines):
            break
        joined = re.sub(r'\s+', ' ', ' '.join(blob))
        tm = TOTALS_D_RE.search(joined)
        # cut the blob at Totals so the footer/notes can't leak in as players
        body = joined[:tm.start()]
        players = []
        for pm in PLAYER_D_RE.finditer(body):
            nm = pm.group('name').strip()
            if nm.lower() in ('team', 'totals'):
                continue
            players.append({'name': nm, 'fg': pm.group('fg'),
                            'ft': pm.group('ft'), 'pts': int(pm.group('pts'))})
        teams.append({'name': hm.group('name').strip().title(),
                      'score': int(tm.group('tp')), 'players': players})
        i = j + 1
    if len(teams) != 2:
        return parse_variant_e(text)
    for t in teams:
        if not t['players'] or sum(p['pts'] for p in t['players']) != t['score']:
            return parse_variant_e(text)
    return {'date': date, 'teams': teams}


# Variant E: DakStats "custompages" HTML-TABLE box score (~2008-2013), e.g.
# hawaiiathletics.com/custompages/Stats/Mbskb/01022010.HTM. Not <pre>: each
# player is a <tr> of 15 <td> cells
#   [##, "Last,First", p, fg m-a, 3pt m-a, ft m-a, off-def, tot, pf, tp, a, to,
#    blk, stl, min]
# The page holds several tables (full-game box for each team, a "1st Half Box
# Score", and play-analysis tables). Only the two FULL-GAME boxes are wanted:
# they appear first and their per-player minutes sum to ~200 (half-boxes ~100),
# so we accept only the first two player tables whose min-sum > 150 and STOP.
# Each team's printed final is an independent <h4>Team   NN</h4> caption above
# its table; the checksum gate is sum(player tp) == that printed final (NOT the
# player sum itself), matching the other parsers' gate.
def _e_cells(tr):
    tds = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S | re.I)
    return [re.sub(r'\s+', ' ', html.unescape(strip_tags(c)).replace('\xa0', ' ')).strip()
            for c in tds]


def parse_variant_e(text):
    if 'fgm-fga' not in text:
        return None
    plain = strip_tags(text)
    dm = re.search(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', plain)
    if dm:
        mo, dy, y = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
        y += 2000 if y < 50 else (1900 if y < 100 else 0)
    else:
        # some headers write the date concatenated as "(MMDDYYYY at ...)"
        dm = re.search(r'\((\d{2})(\d{2})(\d{4})\b', plain)
        if not dm:
            return None
        mo, dy, y = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
    if not (1 <= mo <= 12 and 1 <= dy <= 31):
        return None
    date = mk_date(y, mo, dy)
    if not date:
        return None
    teams, cur, cap = [], None, None
    for tok in re.finditer(r'<h4>(?P<h4>.*?)</h4>|<tr[^>]*>(?P<tr>.*?)</tr>',
                           text, re.S | re.I):
        if tok.group('h4') is not None:
            cm = re.match(
                r'^(?P<n>.*?)\s+(?P<s>\d+)\s*$',
                html.unescape(strip_tags(tok.group('h4'))).replace('\xa0', ' ').strip())
            if cm:
                cap = (clean_name(cm.group('n')), int(cm.group('s')))
            continue
        cs = _e_cells(tok.group('tr'))
        if len(cs) == 15 and cs[0] == '##':          # column header -> new table
            cur = {'name': cap[0], 'score': cap[1], 'players': []} \
                if (cap and len(teams) < 2) else None
            continue
        if cur is None:
            continue
        if len(cs) >= 2 and cs[1].lower().startswith('total'):   # Totals row -> close
            if sum(p['min'] for p in cur['players']) > 150 and cur['players']:
                teams.append(cur)
            cur = None
            if len(teams) == 2:
                break
            continue
        if len(cs) == 15 and re.fullmatch(r'\d+', cs[0]):        # player row
            try:
                cur['players'].append(
                    {'name': clean_name(cs[1]),
                     'fg': cs[3], 'tp': cs[4], 'ft': cs[5],
                     'reb': int(cs[7]), 'pf': int(cs[8]), 'pts': int(cs[9]),
                     'ast': int(cs[10]), 'to': int(cs[11]), 'blk': int(cs[12]),
                     'stl': int(cs[13]), 'min': int(cs[14])})
            except ValueError:
                pass
    if len(teams) != 2:
        return None
    for t in teams:
        if not t['players'] or sum(p['pts'] for p in t['players']) != t['score']:
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


def make_docs(cfg):
    """Generic enumerator: Wayback CDX listing -> fetch live or via snapshot.

    cfg keys: cdx (url pattern), file_re (path filter, men's games only),
    mode ('live'|'wayback'), live_host (for live mode host rewrite)."""
    def docs():
        cdx = get_retry(
            'http://web.archive.org/cdx/search/cdx?url=' + cfg['cdx'] +
            '&filter=statuscode:200&collapse=urlkey&fl=timestamp,original&limit=4000').decode()
        rows = []
        seen = set()
        for line in cdx.splitlines():
            parts = line.strip().split(' ', 1)
            if len(parts) != 2:
                continue
            ts, orig = parts
            path = orig.split('?')[0]
            if not re.search(cfg['file_re'], path) or path in seen:
                continue
            seen.add(path)
            rows.append((ts, path))
        print(f'{len(rows)} game files from CDX')
        for ts, orig in sorted(rows, key=lambda r: r[1]):
            if cfg['mode'] == 'live':
                url = re.sub(r'^https?://[^/]+', cfg['live_host'], orig)
            else:
                url = f'http://web.archive.org/web/{ts}id_/{orig}'
            for attempt in range(3):
                try:
                    yield url, get(url).decode('utf-8', 'replace')
                    break
                except Exception as e:
                    if attempt == 2:
                        print(f'  fetch fail {url}: {e}')
                    else:
                        time.sleep(20)
            time.sleep(1.0 if cfg['mode'] == 'wayback' else 0.4)
    return docs


# Every source publishes StatCrew 'Official Basketball Box Score' text.
# file_re must select MEN'S single-game files only.
SOURCE_DEFS = {
    'charlotte':    ('2429', 'Charlotte 49ers', 'static.charlotte49ers.com legacy archive',
                     {'cdx': 'static.charlotte49ers.com/old_site/sports/m-baskbl/stats/*',
                      'file_re': r'/stats/\d{6}[a-z]{3}\.html?$', 'mode': 'live',
                      'live_host': 'https://static.charlotte49ers.com'}),
    'bowlinggreen': ('189', 'Bowling Green Falcons', 'static.bgsufalcons.com legacy archive',
                     {'cdx': 'static.bgsufalcons.com/custompages/stats/mbasketball/*',
                      'file_re': r'/mbasketball/\d{4}/[a-z0-9_-]+\.html?$', 'mode': 'live',
                      'live_host': 'https://static.bgsufalcons.com'}),
    'chicagostate': ('2130', 'Chicago State Cougars', 'static.gocsucougars.com legacy archive',
                     {'cdx': 'static.gocsucougars.com/custompages/MBBSTATS/*',
                      'file_re': r'/MBBSTATS/\d{6}/[a-z0-9_-]+\.html?$', 'mode': 'live',
                      'live_host': 'https://static.gocsucougars.com'}),
    'northerniowa': ('2460', 'Northern Iowa Panthers', 'static.unipanthers.com legacy archive',
                     {'cdx': 'static.unipanthers.com/custompages/Stats/MBB/*',
                      'file_re': r'/MBB/\d{4}MBB/HTML/game\d+\.html?$', 'mode': 'live',
                      'live_host': 'https://static.unipanthers.com'}),
    'airforce':     ('2005', 'Air Force Falcons', 'airforcesports.com (Wayback)',
                     {'cdx': 'airforcesports.com/bko/bkc/*',
                      'file_re': r'/bko/bkc/.*box.*\.html?$', 'mode': 'wayback'}),
    'uconn':        ('41', 'UConn Huskies', 'uconnhuskies.com (Wayback)',
                     {'cdx': 'uconnhuskies.com/bko/bkc/*',
                      'file_re': r'/bko/bkc/.*box.*\.html?$', 'mode': 'wayback'}),
    'brown':        ('225', 'Brown Bears', 'brownbears.com (Wayback)',
                     {'cdx': 'brownbears.com/bko/bkc/*',
                      'file_re': r'/bko/bkc/.*box.*\.html?$', 'mode': 'wayback'}),
    'sanfrancisco': ('2539', 'San Francisco Dons', 'usfdons.com (Wayback)',
                     {'cdx': 'usfdons.com/bko/bkc/*',
                      'file_re': r'/bko/bkc/.*box.*\.html?$', 'mode': 'wayback'}),
    'ohio':         ('195', 'Ohio Bobcats', 'ohiobobcats.com (Wayback)',
                     {'cdx': 'ohiobobcats.com/bko/bkc/*',
                      'file_re': r'/bko/bkc/.*box.*\.html?$', 'mode': 'wayback'}),
    'arizonastate': ('9', 'Arizona State Sun Devils', 'thesundevils.com (Wayback)',
                     {'cdx': 'thesundevils.com/sports/m-baskbl/stats/*',
                      'file_re': r'/stats/\d{6}[a-z]{3}\.html?$', 'mode': 'wayback'}),
    'california':   ('25', 'California Golden Bears', 'calbears.com (Wayback)',
                     {'cdx': 'calbears.com/sports/m-baskbl/stats/*',
                      'file_re': r'/stats/\d{6}[a-z]{3}\.html?$', 'mode': 'wayback'}),
    'clemson':      ('228', 'Clemson Tigers', 'clemsontigers.com (Wayback)',
                     {'cdx': 'clemsontigers.com/sports/m-baskbl/stats/*',
                      'file_re': r'/stats/\d{6}[a-z]{3}\.html?$', 'mode': 'wayback'}),
    'umass':        ('113', 'Massachusetts Minutemen', 'umassathletics.com (Wayback)',
                     {'cdx': 'umassathletics.com/sports/m-baskbl/stats/*',
                      'file_re': r'/stats/\d{6}[a-z]{3}\.html?$', 'mode': 'wayback'}),
    'bucknell':     ('2083', 'Bucknell Bison', 'bucknellbison.com (Wayback)',
                     {'cdx': 'bucknellbison.com/sports/m-baskbl/stats/*',
                      'file_re': r'/stats/\d{6}[a-z]{3}\.html?$', 'mode': 'wayback'}),
    'rutgers':      ('164', 'Rutgers Scarlet Knights', 'scarletknights.com (Wayback)',
                     {'cdx': 'scarletknights.com/basketball-men/stats/*',
                      'file_re': r'/stats/.*\.html?$', 'mode': 'wayback'}),
    'northerncolorado': ('2458', 'Northern Colorado Bears', 'uncbears.fansonly.com (Wayback)',
                     {'cdx': 'uncbears.fansonly.com/sports/m-baskbl/stats/*',
                      'file_re': r'/stats/\d{6}[a-z]{3}\.html?$', 'mode': 'wayback'}),
    'portlandstate': ('2502', 'Portland State Vikings', 'goviks.fansonly.com (Wayback)',
                     {'cdx': 'goviks.fansonly.com/sports/m-baskbl/stats/*',
                      'file_re': r'/stats/\d{6}[a-z]{3}\.html?$', 'mode': 'wayback'}),
    'ucriverside':  ('27', 'UC Riverside Highlanders', 'static.gohighlanders.com (Wayback)',
                     {'cdx': 'static.gohighlanders.com/custompages/MBasketball/*',
                      'file_re': r'(?i)/MBasketball/\d{6}/ucrmb[kb]\d+\.html?$', 'mode': 'wayback'}),
    'wrightstate':  ('2750', 'Wright State Raiders', 'wsuraiders.com (Wayback)',
                     {'cdx': 'wsuraiders.com/mbasketball/*',
                      'file_re': r'/mbasketball/\d{4}boxes/\d+\.html?$', 'mode': 'wayback'}),
    # ── Census wave 1 (domain-hunt CDX census, m-baskbl pattern, Wayback) ──
    'washington':    ('264', 'Washington Huskies', 'gohuskies.collegesports.com (Wayback)',
                      {'cdx': 'gohuskies.collegesports.com/sports/m-baskbl/stats/*',
                       'file_re': r'/stats/\d{6}[a-z]{3}\.html?$', 'mode': 'wayback'}),
    'bostoncollege': ('103', 'Boston College Eagles', 'bceagles.ocsn.com (Wayback)',
                      {'cdx': 'bceagles.ocsn.com/sports/m-baskbl/stats/*',
                       'file_re': r'/stats/\d{6}[a-z]{3}\.html?$', 'mode': 'wayback'}),
    'tcu':           ('2628', 'TCU Horned Frogs', 'gofrogs.cstv.com (Wayback)',
                      {'cdx': 'gofrogs.cstv.com/sports/m-baskbl/stats/*',
                       'file_re': r'/stats/\d{6}[a-z]{3}\.html?$', 'mode': 'wayback'}),
    'oregon':        ('2483', 'Oregon Ducks', 'goducks.fansonly.com (Wayback)',
                      {'cdx': 'goducks.fansonly.com/sports/m-baskbl/stats/*',
                       'file_re': r'/stats/\d{6}[a-z]{3}\.html?$', 'mode': 'wayback'}),
    'lafayette':     ('322', 'Lafayette Leopards', 'goleopards.fansonly.com (Wayback)',
                      {'cdx': 'goleopards.fansonly.com/sports/m-baskbl/stats/*',
                       'file_re': r'/stats/\d{6}[a-z]{3}\.html?$', 'mode': 'wayback'}),
    'butler':        ('2086', 'Butler Bulldogs', 'butlersports.cstv.com (Wayback)',
                      {'cdx': 'butlersports.cstv.com/sports/m-baskbl/stats/*',
                       'file_re': r'/stats/\d{6}[a-z]{3}\.html?$', 'mode': 'wayback'}),
    'providence':    ('2507', 'Providence Friars', 'friars.fansonly.com (Wayback)',
                      {'cdx': 'friars.fansonly.com/sports/m-baskbl/stats/*',
                       'file_re': r'/stats/\d{6}[a-z]{3}\.html?$', 'mode': 'wayback'}),
    'ncstate':       ('152', 'NC State Wolfpack', 'gopack.collegesports.com (Wayback)',
                      {'cdx': 'gopack.collegesports.com/sports/m-baskbl/stats/*',
                       'file_re': r'/stats/\d{6}[a-z]{3}\.html?$', 'mode': 'wayback'}),
    'coloradostate': ('36', 'Colorado State Rams', 'csurams.collegesports.com (Wayback)',
                      {'cdx': 'csurams.collegesports.com/sports/m-baskbl/stats/*',
                       'file_re': r'/stats/\d{6}[a-z]{3}\.html?$', 'mode': 'wayback'}),
    'marist':        ('2368', 'Marist Red Foxes', 'goredfoxes.collegesports.com (Wayback)',
                      {'cdx': 'goredfoxes.collegesports.com/sports/m-baskbl/stats/*',
                       'file_re': r'/stats/\d{6}[a-z]{3}\.html?$', 'mode': 'wayback'}),
    'fairfield':     ('2217', 'Fairfield Stags', 'fairfieldstags.fansonly.com (Wayback)',
                      {'cdx': 'fairfieldstags.fansonly.com/sports/m-baskbl/stats/*',
                       'file_re': r'/stats/\d{6}[a-z]{3}\.html?$', 'mode': 'wayback'}),
    'clevelandstate':('325', 'Cleveland State Vikings', 'csuvikings.fansonly.com (Wayback)',
                      {'cdx': 'csuvikings.fansonly.com/sports/m-baskbl/stats/*',
                       'file_re': r'/stats/\d{6}[a-z]{3}\.html?$', 'mode': 'wayback'}),
    'colorado':      ('38', 'Colorado Buffaloes', 'cubuffs.fansonly.com (Wayback)',
                      {'cdx': 'cubuffs.fansonly.com/sports/m-baskbl/stats/*',
                       'file_re': r'/stats/\d{6}[a-z]{3}\.html?$', 'mode': 'wayback'}),
    'cornell':       ('172', 'Cornell Big Red', 'cornellbigred.fansonly.com (Wayback)',
                      {'cdx': 'cornellbigred.fansonly.com/sports/m-baskbl/stats/*',
                       'file_re': r'/stats/\d{6}[a-z]{3}\.html?$', 'mode': 'wayback'}),
}

# Supplementary sources (census wave-2+) live in _extra_sources.json so large
# batches can be generated programmatically. Format: {key: [tid, name, site, cfg]}.
if os.path.exists('_extra_sources.json'):
    for _k, _v in json.load(open('_extra_sources.json')).items():
        SOURCE_DEFS[_k] = tuple(_v)

SOURCES = {k: {'team_id': tid, 'team_name': name, 'site': site, 'docs': make_docs(cfg)}
           for k, (tid, name, site, cfg) in SOURCE_DEFS.items()}


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
        try:
            base = datetime.strptime(date, '%Y-%m-%d')
        except (ValueError, TypeError):
            return False  # unparseable date -> quarantine this game, not the run
        for off in (0, -1, 1):
            dd = (base + timedelta(days=off)).strftime('%Y-%m-%d')
            for g in by_date.get(dd, []):
                if g.get('pts') == own and g.get('opp_pts') == opp:
                    return True
        return False

    # Disambiguate name-collision programs (first-word matching is ambiguous when
    # two teams share a first word, e.g. Michigan / Michigan St). Values are a
    # substring that uniquely identifies THIS team in a box-score team name.
    ALIASES = {
        'UConn Huskies': 'connecticut',
        'Michigan State Spartans': 'michigan st', 'Ohio State Buckeyes': 'ohio st',
        'North Carolina Tar Heels': 'north carolina', 'San Diego State Aztecs': 'san diego st',
        'San Jose State Spartans': 'san jose', 'Washington State Cougars': 'washington st',
        'Oregon State Beavers': 'oregon st', 'Illinois State Redbirds': 'illinois st',
        'Oklahoma State Cowboys': 'oklahoma st', 'Colorado State Rams': 'colorado st',
        "Hawai'i Rainbow Warriors": 'hawai',  # box name uses a backtick: "Hawai`i"
        'UC Riverside Highlanders': 'riverside',  # first word "UC" too short/ambiguous
        'Purdue Fort Wayne Mastodons': 'fort wayne',  # "purdue" matches opp Purdue North Central
        'Portland State Vikings': 'portland st',  # plain "portland" = Portland Pilots
        'Idaho State Bengals': 'idaho st',        # plain "idaho" = Idaho Vandals
        'North Carolina Central Eagles': 'central',  # first word "north" is useless
    }
    name_key = ALIASES.get(src['team_name'], src['team_name'].split()[0].lower())
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
