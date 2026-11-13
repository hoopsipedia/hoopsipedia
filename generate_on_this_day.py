#!/usr/bin/env python3
"""Precompute an 'On This Day in college basketball' dataset.

Reads the repo's dated game logs (games_1/2/3.json, 1941-2026), team
metadata (data.json H: name idx 0, NC count idx 6, NCY championship
years idx 7), seed-upset history (upset_history.json) and the
sr_boxscores.json URL dates, and writes on_this_day.json keyed by
'MM-DD' for all 366 calendar days. Each day holds up to MAX_EVENTS
events sorted by a significance score.

Event types (significance):
  championship  101        title game, from the champion's season row (v2) or
                100        the NCY-flagged last win of a title season (v1 fallback)
  tournament    50-99      any NCAA Tournament game, dated from the LOSER's
                           season row (ncaaTourney round) + the winner's row
                           one round deeper + the mirror log row; seeds shown
  upset         70+2*gap   NCAA first-round seed upsets from upset_history
  ranked        55-90      both teams in that week's AP Top 25
  upset         50-85      unranked team beats an AP-ranked team
  rivalry       48-56      one of the 40 rivalries in rivalries.json
  ot            36-70      overtime games (single OT counts now)
  high_score    <=42       highest combined-score games (filler)
  blowout       <=40       biggest margins (filler, max 3 per day)
Modifiers: rivalry +12, overtime +6/+12, AP-ranked team involved +4.
Every event carries the winner's season label and hasBox (an ESPN event id
or a Sports-Reference box score exists for that exact game), so the UI can
link the headline straight to the box score.

ACCURACY RULE: every fact in a headline comes directly from a data
field; no embellishment. See OTD_NOTES.md for heuristics and risks.

Usage: python3 generate_on_this_day.py
"""

import datetime
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from json_io import save_json_atomic  # noqa: E402

GAMES_FILES = ['games_1.json', 'games_2.json', 'games_3.json']
DATA_JSON = 'data.json'
UPSETS_JSON = 'upset_history.json'
SR_BOX_JSON = 'sr_boxscores.json'
OUT_JSON = 'on_this_day.json'

MAX_EVENTS = 10
MAX_FILLERS_PER_DAY = 3   # blowout + high_score
AP_JSON = 'ap_polls.json'
RIVALRIES_JSON = 'rivalries.json'
SEASONS_DIR = 'seasons'
GAME_IDS_DIR = 'game_ids'
BOX_DIR = 'boxscores'
BOX_INDEX_JSON = 'boxscore_match_index.json'
# Championship-game search window (earliest NCAA final in our era:
# 1953-03-18; latest modern finals: ~April 8).
CHAMP_WINDOW = ((3, 15), (4, 15))
HIGH_SCORE_MIN_TOTAL = 220
BLOWOUT_MIN_MARGIN = 35

# Historical-name aliases: upset_history.json uses the team name at the
# time of the game; data.json H uses the current ESPN name. Mapping is
# rename-only (same program, same ESPN id) so we can locate the game in
# the logs. Headlines keep the historical name from upset_history.
NAME_ALIASES = {
    'Arkansas-Little Rock Trojans': '2031',     # Little Rock Trojans
    'College of Charleston Cougars': '232',     # Charleston Cougars
    'Connecticut Huskies': '41',                # UConn Huskies
    'George Washington Colonials': '45',        # George Washington Revolutionaries
    'Grand Canyon Antelopes': '2253',           # Grand Canyon Lopes
    'Hawaii Rainbow Warriors': '62',            # Hawai'i Rainbow Warriors
    'Miami Hurricanes': '2390',                 # Miami (FL) Hurricanes
    'Penn Quakers': '219',                      # Pennsylvania Quakers
    "Southwest Louisiana Ragin' Cajuns": '309', # Louisiana Ragin' Cajuns
    'Southwest Missouri State Bears': '2623',   # Missouri State Bears
    'UMass Minutemen': '113',                   # Massachusetts Minutemen
    'Valparaiso Crusaders': '2674',             # Valparaiso Beacons
    'Wisconsin-Green Bay Phoenix': '2739',      # Green Bay Phoenix
    'Wisconsin-Milwaukee Panthers': '270',      # Milwaukee Panthers
}


def load_json(name):
    with open(os.path.join(ROOT, name)) as f:
        return json.load(f)


def season_of(date_str):
    """Season label = calendar year the season ends in (Nov-Dec roll forward)."""
    y, m = int(date_str[:4]), int(date_str[5:7])
    return y + 1 if m >= 11 else y


def in_champ_window(date_str):
    m, d = int(date_str[5:7]), int(date_str[8:10])
    return CHAMP_WINDOW[0] <= (m, d) <= CHAMP_WINDOW[1]


def load_teams():
    h = load_json(DATA_JSON)['H']
    teams = {}
    for tid, v in h.items():
        ncy = v[7] if isinstance(v[7], list) else []
        teams[tid] = {'name': v[0], 'nc': v[6] or 0, 'ncy': ncy}
    return teams


def build_slug_map(per_team, stats):
    """Resolve opp_slug -> espn id by mirror-row voting.

    The stored 'opp' id field is unreliable: it was produced by substring
    matching and points at the wrong program for thousands of rows
    (e.g. slug 'houston' -> 2534 Sam Houston Bearkats, 'indiana' -> 85
    IU Indianapolis, 'california' -> 2934 Cal State Bakersfield). We
    therefore ignore it and re-derive ids: for each distinct opp_slug,
    look at the rows carrying it and find which team's own log contains
    the mirror row (same date, scores swapped, result flipped). The true
    opponent wins the vote overwhelmingly; we require >=5 votes, a
    >=75% share, and >=5x the runner-up (coincidental same-score games
    on the same date add ~5-10% noise). Slugs that never resolve
    (mostly non-D1 opponents) get no id.
    """
    mirror_index = defaultdict(list)  # (date, pts, opp_pts) -> [tid]
    for tid, rows in per_team.items():
        for g in rows:
            mirror_index[(g['date'], g['pts'], g['opp_pts'])].append(tid)

    votes = defaultdict(Counter)
    for tid, rows in per_team.items():
        for g in rows:
            c = votes[g['opp_slug']]
            if sum(c.values()) >= 200:
                continue
            for cand in mirror_index.get(
                    (g['date'], g['opp_pts'], g['pts']), []):
                if cand != tid:
                    c[cand] += 1

    slug_map = {}
    for slug, c in votes.items():
        if not c:
            continue
        ranked = c.most_common(2)
        best, n = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else 0
        if n >= 5 and n / sum(c.values()) >= 0.75 and n >= 5 * runner_up:
            slug_map[slug] = best
    stats['slugs_seen'] = len(votes)
    stats['slugs_resolved'] = len(slug_map)
    return slug_map


def load_games(stats):
    """Return (per_team, canonical).

    per_team: tid -> list of raw game rows (deduped within team), with
    g['opp'] rewritten to the slug-map-resolved espn id (or None).
    canonical: dedup across the two mirrored team rows; key
    (date, idA, idB sorted) -> dict with winner/loser orientation.
    Only games where both espn ids are known go in canonical.
    """
    per_team = defaultdict(list)
    seen_rows = set()
    for fname in GAMES_FILES:
        data = load_json(fname)
        for tid, obj in data.items():
            rows = obj['games'] if isinstance(obj, dict) else obj
            for g in rows:
                row_key = (tid, g['date'], g['opp_slug'],
                           g['pts'], g['opp_pts'])
                if row_key in seen_rows:
                    continue
                seen_rows.add(row_key)
                per_team[tid].append(g)

    slug_map = build_slug_map(per_team, stats)
    for tid, rows in per_team.items():
        for g in rows:
            resolved = slug_map.get(g['opp_slug'])
            if g.get('opp') and resolved and g['opp'] != resolved:
                stats['opp_id_corrected'] += 1
            g['opp'] = resolved

    canonical = {}
    for tid, rows in per_team.items():
        for g in rows:
            opp = g.get('opp')
            if not opp:
                continue
            key = (g['date'],) + tuple(sorted((tid, opp)))
            if key in canonical:
                continue
            if g['w']:
                w_id, w_pts, l_id, l_pts = tid, g['pts'], opp, g['opp_pts']
            else:
                w_id, w_pts, l_id, l_pts = opp, g['opp_pts'], tid, g['pts']
            canonical[key] = {
                'date': g['date'], 'w_id': w_id, 'l_id': l_id,
                'w_pts': w_pts, 'l_pts': l_pts, 'ot': g.get('ot', ''),
            }
    return per_team, canonical


def team_name(teams, tid, fallback=None):
    t = teams.get(tid)
    return t['name'] if t else (fallback or 'Unknown')


def make_event(date, etype, headline, w_id, w_name, l_id, l_name,
               w_pts, l_pts, sig, **extra):
    ev = {
        'date': date,
        'type': etype,
        'headline': headline,
        'teams': [
            {'espnId': w_id, 'name': w_name},
            {'espnId': l_id, 'name': l_name},
        ],
        'score': '{}-{}'.format(w_pts, l_pts),
        'sig': round(sig, 1),
    }
    ev.update(extra)
    return ev


def detect_championships(teams, per_team, stats):
    """For each NCY year Y of team T: T's last game of season Y must be a
    win inside CHAMP_WINDOW -> championship-game candidate. Cross-check:
    the opponent (when present in the dataset) has a mirror row on that
    date and it is also the opponent's last game of the season.
    """
    # Latest date in the whole dataset: used to skip an in-progress season.
    global_max = max((g['date'] for rows in per_team.values() for g in rows),
                     default='0000-00-00')
    events = []
    for tid, rows in per_team.items():
        ncy = teams.get(tid, {}).get('ncy') or []
        for year in ncy:
            # Skip seasons our data has not finished scraping.
            if (season_of(global_max) == year
                    and global_max < '{}-04-01'.format(year)):
                stats['champ_skipped_incomplete_season'] += 1
                continue
            season_games = [g for g in rows if season_of(g['date']) == year]
            if not season_games:
                stats['champ_no_season_games'] += 1
                continue
            last = max(season_games, key=lambda g: g['date'])
            if not (last['w'] and in_champ_window(last['date'])):
                stats['champ_last_game_not_window_win'] += 1
                continue
            opp = last.get('opp')
            opp_name = team_name(teams, opp, last.get('opp_slug'))
            opp_season = [g for g in per_team.get(opp, [])
                          if season_of(g['date']) == year] if opp else []
            if opp_season:
                # Title game must also be the opponent's season finale.
                mirror = [g for g in opp_season
                          if g['date'] == last['date'] and g.get('opp') == tid
                          and g['pts'] == last['opp_pts']
                          and g['opp_pts'] == last['pts']]
                opp_last = max(g['date'] for g in opp_season)
                if not mirror or opp_last != last['date']:
                    stats['champ_cross_check_failed'] += 1
                    continue
                stats['champ_cross_checked'] += 1
            else:
                # Opponent absent from logs for that season (non-D1-era
                # gap or vacated season, e.g. Michigan 1992/93, Memphis
                # 2008): accept on the team's own log alone.
                stats['champ_no_opponent_data'] += 1
            name = teams[tid]['name']
            headline = ('{}: {} beats {} {}-{} in the final game of their '
                        '{} national championship season').format(
                last['date'], name, opp_name, last['pts'], last['opp_pts'],
                year)
            events.append(make_event(
                last['date'], 'championship', headline,
                tid, name, opp, opp_name,
                last['pts'], last['opp_pts'], 100))
    return events


def detect_upsets(teams, canonical, stats):
    """Date the seed upsets in upset_history.json (which stores only the
    year) by matching teams + winner + exact score against the game logs
    in March/April of that year; fall back to the boxscore URL date in
    sr_boxscores.json. Unmatchable upsets are skipped, never guessed.
    """
    upsets_doc = load_json(UPSETS_JSON)

    name_to_id = {t['name']: tid for tid, t in teams.items()}
    name_to_id.update(NAME_ALIASES)

    # Index canonical games: (w_id, l_id, year) -> games
    by_pair_year = defaultdict(list)
    # ... and (team_id, date) -> games, to contradiction-check the SR fallback
    by_team_date = defaultdict(list)
    for g in canonical.values():
        if g['date'][5:7] in ('03', '04'):
            by_pair_year[(g['w_id'], g['l_id'], int(g['date'][:4]))].append(g)
        by_team_date[(g['w_id'], g['date'])].append(g)
        by_team_date[(g['l_id'], g['date'])].append(g)

    # Fallback index from sr_boxscores: (year, frozenset(names)) -> date
    sr_dates = {}
    sr = load_json(SR_BOX_JSON)
    url_re = re.compile(r'/boxscores/(\d{4}-\d{2}-\d{2})-')
    for v in sr.values():
        url = v.get('url', '')
        m = url_re.search(url)
        if not m or 'year' not in v or not isinstance(v.get('teams'), list):
            continue
        names = frozenset(t.get('name', '') for t in v['teams'])
        sr_dates[(v['year'], names)] = m.group(1)

    # Collect raw entries first so duplicates of the same game — which exist in
    # upset_history.json with conflicting scores/seeds — can be resolved against
    # the logs instead of silently publishing whichever sorts higher.
    raw = []
    for key, group in upsets_doc.items():
        if key == 'metadata':
            continue
        for up in group.get('upsets', []):
            m = re.match(r'^(\d+)-(\d+)', up.get('score', ''))
            if not m:
                stats['upset_bad_score'] += 1
                continue
            raw.append((up, int(m.group(1)), int(m.group(2))))

    by_matchup = defaultdict(list)
    for entry in raw:
        up = entry[0]
        by_matchup[(up['year'], frozenset((up['winnerFull'], up['loserFull'])))].append(entry)

    def log_dated(up, w_pts, l_pts):
        """Date an upset via the game logs (exact score match), else None."""
        w_id = name_to_id.get(up['winnerFull'])
        l_id = name_to_id.get(up['loserFull'])
        if not (w_id and l_id):
            return None
        for g in by_pair_year.get((w_id, l_id, up['year']), []):
            if g['w_pts'] == w_pts and g['l_pts'] == l_pts:
                return g['date']
        return None

    events = []
    for matchup_key, entries in by_matchup.items():
        if len(entries) > 1:
            # Duplicate entries for the same game: keep the single log-verified
            # one; if zero or several verify (conflicting seeds), publish none.
            verified = [e for e in entries if log_dated(*e)]
            seeds = {(e[0]['winnerSeed'], e[0]['loserSeed']) for e in verified}
            if len(verified) != 1 and len(seeds) != 1:
                stats['upset_dup_conflict_skipped'] += len(entries)
                continue
            entries = verified[:1] if verified else []
            if not entries:
                stats['upset_dup_conflict_skipped'] += 1
                continue

        for up, w_pts, l_pts in entries:
            w_name, l_name = up['winnerFull'], up['loserFull']
            w_id = name_to_id.get(w_name)
            l_id = name_to_id.get(l_name)
            date = log_dated(up, w_pts, l_pts)
            if date is None:
                date = sr_dates.get((up['year'], frozenset((w_name, l_name))))
                if date:
                    # Contradiction guard: if either team's log shows ANY game on
                    # the fallback date that is not this exact game, the SR entry
                    # is wrong (fabricated entries exist) — skip, never guess.
                    contradicted = False
                    for tid in (w_id, l_id):
                        if not tid:
                            continue
                        for g in by_team_date.get((tid, date), []):
                            same = ({g['w_id'], g['l_id']} == {w_id, l_id}
                                    and g['w_pts'] == w_pts and g['l_pts'] == l_pts)
                            if not same:
                                contradicted = True
                    if contradicted:
                        stats['upset_sr_fallback_contradicted'] += 1
                        continue
                    stats['upset_dated_via_sr_boxscores'] += 1
            else:
                stats['upset_dated_via_game_logs'] += 1
            if date is None:
                stats['upset_undated_skipped'] += 1
                continue
            gap = up['winnerSeed'] - up['loserSeed']
            sig = 70 + 2 * gap
            n_ot = up.get('overtimes', 0)
            ot_note = ''
            if n_ot == 1:
                ot_note = ' in overtime'
            elif n_ot > 1:
                ot_note = ' in {} overtimes'.format(n_ot)
            headline = ('{}: {}-seed {} stuns {}-seed {} {}-{}{} in the '
                        'NCAA Tournament first round').format(
                date, up['winnerSeed'], w_name, up['loserSeed'], l_name,
                w_pts, l_pts, ot_note)
            events.append(make_event(date, 'upset', headline,
                                     w_id, w_name, l_id, l_name,
                                     w_pts, l_pts, sig))
    return events


def article(n):
    """'a' vs 'an' before a spoken number (80-89 -> 'an eighty...')."""
    return 'an' if (80 <= n <= 89 or n in (8, 11, 18)) else 'a'


def ot_count(ot):
    if not ot:
        return 0
    return 1 if ot == 'OT' else int(ot[:-2])


def ot_suffix(n):
    return {0: '', 1: ' in overtime', 2: ' in double overtime',
            3: ' in triple overtime'}.get(n, ' in {} overtimes'.format(n))


# ── AP poll ranks at a given date ──────────────────────────────────────
def load_ap_polls():
    """season end-year -> [(iso_date, {tid: rank}), ...] sorted by date.
    Week labels are 'Pre', 'Conf' (skipped) or 'M/D' (poll release date;
    Sep-Dec belong to the season's first calendar year)."""
    out = {}
    for yr, doc in load_json(AP_JSON).items():
        try:
            end = int(yr)
        except ValueError:
            continue
        polls = []
        for w in doc.get('weeks', []):
            label = str(w.get('label', ''))
            ranks = {str(r['id']): int(r['rank'])
                     for r in w.get('ranks', []) if r.get('id')}
            if not ranks:
                continue
            if label == 'Pre':
                d = datetime.date(end - 1, 10, 1)
            else:
                m = re.match(r'^(\d{1,2})/(\d{1,2})$', label)
                if not m:
                    continue
                mo, dy = int(m.group(1)), int(m.group(2))
                try:
                    d = datetime.date(end - 1 if mo >= 9 else end, mo, dy)
                except ValueError:
                    continue
            polls.append((d.isoformat(), ranks))
        polls.sort()
        out[end] = polls
    return out


def rank_at(ap, date_str, tid):
    """AP rank of tid in the most recent poll on or before date_str."""
    polls = ap.get(season_of(date_str))
    if not polls:
        return None
    cur = None
    for d, ranks in polls:
        if d <= date_str:
            cur = ranks
        else:
            break
    return cur.get(tid) if cur else None


def load_rivalries():
    out = {}
    for r in load_json(RIVALRIES_JSON):
        name = r.get('name') or ''
        if r.get('team1Id') and r.get('team2Id') and name:
            out[frozenset((str(r['team1Id']), str(r['team2Id'])))] = name
    return out


def rivalry_phrase(name):
    """' in the Tobacco Road Rivalry' / ' in Bedlam'; plain 'A vs B' names
    (no nickname) add nothing to the headline."""
    if ' vs ' in name:
        return ''
    if name in ('Bedlam', "Braggin' Rights"):
        return ' in ' + name
    return ' in the ' + re.sub(r'^The\s+', '', name).strip()


# ── NCAA Tournament games from the season rows ─────────────────────────
ROUND_DEPTH = {
    'Opening Round': 0, 'First Four': 0, 'First Round': 1, 'Second Round': 2,
    'Third Round': 3, 'Regional Semifinal': 4, 'Regional Final': 5,
    'Regional Final (Final Four)': 5, 'National Semifinal': 6,
    'National Final': 7,
}
ROUND_LABEL = {
    'First Round': 'first round', 'Second Round': 'second round',
    'Third Round': 'second round', 'Regional Semifinal': 'Sweet 16',
    'Regional Final': 'Elite Eight', 'Regional Final (Final Four)': 'Elite Eight',
    'National Semifinal': 'Final Four',
    'National Final': 'national championship game',
}
ROUND_SIG = {
    'First Four': 50, 'first round': 58, 'second round': 66, 'Sweet 16': 78,
    'Elite Eight': 86, 'Final Four': 93, 'national championship game': 101,
}


def round_label(rnd, end_year):
    if rnd in ('Opening Round', 'First Four'):
        return 'First Four'
    if 2011 <= end_year <= 2015:
        # Sports-Reference labels for the 68-team era before 2016: the
        # First Four was 'First Round', the round of 64 'Second Round'
        # and the round of 32 'Third Round'.
        return {'First Round': 'First Four', 'Second Round': 'first round',
                'Third Round': 'second round'}.get(rnd) or ROUND_LABEL.get(rnd)
    return ROUND_LABEL.get(rnd)


def round_phrase(label):
    if label in ('first round', 'second round'):
        return 'in the NCAA Tournament ' + label
    return 'in the ' + label


def load_tourney_rows(stats):
    """(tid, season_end_year) -> {depth, round, won, seed, vacated} from
    the ncaaTourney field of seasons/{tid}.json rows."""
    out = {}
    for path in glob.glob(os.path.join(ROOT, SEASONS_DIR, '*.json')):
        tid = os.path.basename(path)[:-5]
        if tid == 'index':
            continue
        with open(path) as f:
            doc = json.load(f)
        rows = doc.get('seasons', []) if isinstance(doc, dict) else doc
        for r in rows:
            t = r.get('ncaaTourney')
            y = str(r.get('year', ''))
            if not t or not re.match(r'^\d{4}-\d{2}$', y):
                continue
            end = int(y[:4]) + 1
            vac = t.endswith('*')
            m = re.match(r'^(Won|Lost) NCAA Tournament (.+?)\*?$', t)
            if not m:
                continue
            won = m.group(1) == 'Won'
            rnd = m.group(2)
            depth = 8 if won else ROUND_DEPTH.get(rnd)
            if depth is None:
                stats['tourney_round_unmapped'] += 1
                continue
            seed = r.get('seed')
            try:
                seed = int(seed) if seed not in (None, '') else None
            except (TypeError, ValueError):
                seed = None
            out[(tid, end)] = {'depth': depth, 'round': rnd, 'won': won,
                               'seed': seed, 'vacated': vac}
    return out


def seeded(seed, name):
    return '({}) {}'.format(seed, name) if seed else name


def detect_tournament_games(teams, per_team, trows, ap, stats):
    """Every NCAA Tournament game we can prove: the LOSER's season row
    names the round it lost in, so its last loss of that March/April is
    that game. Accept only when the winner's own row is at least one round
    deeper (or the title) and the winner's log carries the mirror row."""
    events, keys = [], set()
    for (tid, end), row in trows.items():
        if row['won']:
            continue
        season = sorted((g for g in per_team.get(tid, [])
                         if season_of(g['date']) == end),
                        key=lambda g: g['date'], reverse=True)
        # Consolation games (third-place, pre-1982) can follow the loss:
        # look at the last two games, take the first that proves out.
        for last in season[:2]:
            if last['w'] or last['date'][5:7] not in ('03', '04'):
                continue
            opp = last.get('opp')
            orow = trows.get((opp, end)) if opp else None
            if not orow or orow['depth'] <= row['depth']:
                stats['tourney_cross_check_failed'] += 1
                continue
            mirror = [g for g in per_team.get(opp, [])
                      if g['date'] == last['date'] and g.get('opp') == tid
                      and g['pts'] == last['opp_pts']
                      and g['opp_pts'] == last['pts'] and g['w']]
            if not mirror:
                stats['tourney_mirror_missing'] += 1
                continue
            label = round_label(row['round'], end)
            if not label:
                continue
            w_name, l_name = team_name(teams, opp), team_name(teams, tid)
            if 'Unknown' in (w_name, l_name):
                continue
            w_pts, l_pts = last['opp_pts'], last['pts']
            margin = w_pts - l_pts
            ws, ls = orow['seed'], row['seed']
            if ws and ls and ws - ls >= 4:
                verb = 'stuns'
            elif ws and ls and ws > ls:
                verb = 'upsets'
            elif margin <= 2:
                verb = 'edges'
            elif margin >= 25:
                verb = 'routs'
            else:
                verb = 'beats'
            n_ot = ot_count(last.get('ot', ''))
            vac = (row['vacated'] or orow['vacated'] or last.get('vacated')
                   or mirror[0].get('vacated'))
            head = '{}: {} {} {} {}-{} {}{}{}'.format(
                last['date'], seeded(ws, w_name), verb, seeded(ls, l_name),
                w_pts, l_pts, round_phrase(label), ot_suffix(n_ot),
                ' (later vacated)' if vac else '')
            sig = ROUND_SIG[label]
            if ws and ls and ws > ls:
                sig += 2 * (ws - ls)
            if n_ot:
                sig += 6 * min(n_ot, 2)
            rw, rl = rank_at(ap, last['date'], opp), rank_at(ap, last['date'], tid)
            if rw or rl:
                sig += 4
            etype = 'championship' if label == 'national championship game' else 'tournament'
            events.append(make_event(last['date'], etype, head, opp, w_name,
                                     tid, l_name, w_pts, l_pts, sig,
                                     round=label))
            keys.add((last['date'],) + tuple(sorted((tid, opp))))
            stats['tourney_events'] += 1
            break
    return events, keys


def score_games(teams, canonical, ap, rivals, tourney_keys, stats):
    """Score every non-tournament canonical game: AP-ranked matchups and
    upsets, rivalry games, overtime, then the scoring/margin fillers."""
    events = []
    for key, g in canonical.items():
        if key in tourney_keys:
            continue
        w_name = team_name(teams, g['w_id'])
        l_name = team_name(teams, g['l_id'])
        if 'Unknown' in (w_name, l_name):
            continue
        date = g['date']
        rw, rl = rank_at(ap, date, g['w_id']), rank_at(ap, date, g['l_id'])
        riv = rivals.get(frozenset((g['w_id'], g['l_id'])))
        n_ot = ot_count(g['ot'])
        total = g['w_pts'] + g['l_pts']
        margin = g['w_pts'] - g['l_pts']
        cands = []
        if rw and rl:
            cands.append(('ranked', 55 + (26 - min(rw, rl)) * 0.9
                          + (26 - max(rw, rl)) * 0.5))
        elif rl and not rw:
            cands.append(('upset', 50 + (26 - rl) * 1.4))
        if riv:
            cands.append(('rivalry', 48 + (8 if margin <= 3 else 0)))
        if n_ot:
            cands.append(('ot', {1: 36, 2: 50, 3: 62}.get(n_ot, 70)))
        if total >= HIGH_SCORE_MIN_TOTAL:
            cands.append(('high_score',
                          min(42, 25 + (total - HIGH_SCORE_MIN_TOTAL) * 0.4)))
        if margin >= BLOWOUT_MIN_MARGIN:
            cands.append(('blowout', min(40, 20 + margin * 0.4)))
        if not cands:
            continue
        etype, sig = max(cands, key=lambda c: c[1])
        if riv and etype != 'rivalry':
            sig += 12
        if n_ot and etype != 'ot':
            sig += 6 * min(n_ot, 2)
        if etype not in ('ranked', 'upset') and (rw or rl):
            sig += 4

        wn = 'No. {} {}'.format(rw, w_name) if rw else w_name
        ln = 'No. {} {}'.format(rl, l_name) if rl else l_name
        score = '{}-{}'.format(g['w_pts'], g['l_pts'])
        if etype == 'ranked':
            verb = 'edges' if margin <= 2 else ('routs' if margin >= 25 else 'beats')
            head = '{} {} {} {}'.format(wn, verb, ln, score)
        elif etype == 'upset':
            verb = 'stuns' if rl <= 5 else 'upsets'
            head = 'Unranked {} {} {} {}'.format(w_name, verb, ln, score)
        elif etype == 'rivalry':
            verb = 'edges' if margin <= 2 else ('routs' if margin >= 25 else 'beats')
            head = '{} {} {} {}'.format(wn, verb, ln, score)
        elif etype == 'ot':
            head = '{} outlasts {} {}'.format(wn, ln, score)
        elif etype == 'high_score':
            head = '{} outguns {} {} in a {}-point shootout'.format(
                wn, ln, score, total)
        else:
            head = '{} routs {} {}, {} {}-point margin'.format(
                wn, ln, score, article(margin), margin)
        if n_ot and etype != 'high_score':
            head += ot_suffix(n_ot)
        if riv:
            head += rivalry_phrase(riv)
        if g.get('vacated'):
            head += ' (later vacated)'
        events.append(make_event(date, etype, '{}: {}'.format(date, head),
                                 g['w_id'], w_name, g['l_id'], l_name,
                                 g['w_pts'], g['l_pts'], sig))
        stats['type_' + etype] += 1
    return events


# ── Box-score availability (so the headline can link to it) ───────────
def bx_norm(s):
    """Byte-identical to norm() in scripts/build_boxscore_match_index.py."""
    s = str(s or '').lower().replace("'", '').replace('’', '').replace('&', '')
    return re.sub(r'-{2,}', '-', re.sub(r'[^a-z0-9]+', '-', s)).strip('-')


class BoxLocator(object):
    def __init__(self):
        self.names = load_json(BOX_INDEX_JSON).get('names', {})
        self._gid = {}
        self._box = {}

    def _game_ids(self, tid):
        if tid not in self._gid:
            path = os.path.join(ROOT, GAME_IDS_DIR, '{}.json'.format(tid))
            try:
                with open(path) as f:
                    self._gid[tid] = json.load(f)
            except (IOError, ValueError):
                self._gid[tid] = {}
        return self._gid[tid]

    def _boxes(self, year):
        if year not in self._box:
            path = os.path.join(ROOT, BOX_DIR, '{}.json'.format(year))
            try:
                with open(path) as f:
                    self._box[year] = json.load(f)
            except (IOError, ValueError):
                self._box[year] = {}
        return self._box[year]

    def has_box(self, ev):
        w, l = str(ev['teams'][0]['espnId']), str(ev['teams'][1]['espnId'])
        date = ev['date']
        w_pts, l_pts = (int(x) for x in ev['score'].split('-'))
        if date >= '2002':
            d0 = datetime.date.fromisoformat(date)
            for e in self._game_ids(w).values():
                if not e or not e.get('date'):
                    continue
                if {str(e.get('t1')), str(e.get('t2'))} != {w, l}:
                    continue
                try:
                    dd = abs((datetime.date.fromisoformat(e['date']) - d0).days)
                except ValueError:
                    continue
                if dd <= 1:
                    return True
        pair, scores = {w, l}, {w_pts, l_pts}
        for v in self._boxes(season_of(date)).values():
            t = v.get('teams') if isinstance(v, dict) else None
            if not isinstance(t, list) or len(t) < 2:
                continue
            try:
                if {int(t[0].get('score')), int(t[1].get('score'))} != scores:
                    continue
            except (TypeError, ValueError):
                continue
            ids = {self.names.get(bx_norm(x.get('name'))) for x in t[:2]}
            if ids == pair:
                return True
        return False


def all_mmdd():
    """All 366 MM-DD keys in calendar order (2024 is a leap year)."""
    d = datetime.date(2024, 1, 1)
    out = []
    while d.year == 2024:
        out.append(d.strftime('%m-%d'))
        d += datetime.timedelta(days=1)
    return out


def main():
    stats = defaultdict(int)
    teams = load_teams()
    per_team, canonical = load_games(stats)
    stats['teams'] = len(per_team)
    stats['canonical_games'] = len(canonical)

    ap = load_ap_polls()
    rivals = load_rivalries()
    trows = load_tourney_rows(stats)
    stats['tourney_rows'] = len(trows)

    events = []
    events += detect_championships(teams, per_team, stats)
    stats['championship_events_v1'] = sum(
        1 for e in events if e['type'] == 'championship')
    t_events, tourney_keys = detect_tournament_games(teams, per_team, trows, ap, stats)
    events += t_events
    events += detect_upsets(teams, canonical, stats)
    events += score_games(teams, canonical, ap, rivals, tourney_keys, stats)

    by_day = defaultdict(list)
    seen = set()  # one event per (date, team pair)
    for ev in sorted(events, key=lambda e: -e['sig']):
        key = (ev['date'], frozenset(t['espnId'] or t['name']
                                     for t in ev['teams']))
        if key in seen:
            continue
        seen.add(key)
        by_day[ev['date'][5:]].append(ev)

    # Flag whether the winner's season row exists so the SSR links the season
    # page only when it will resolve (Google crawled 404s from these links, Oct 2026).
    with open(os.path.join(ROOT, 'seasons.json')) as f:
        season_years = {tid: {str(r.get('year')) for r in v.get('seasons', [])}
                        for tid, v in json.load(f).items()}
    for ev in events:
        end = season_of(ev['date'])                      # calendar year the season ends in
        label = '{}-{:02d}'.format(end - 1, end % 100)   # seasons.json uses '1996-97'
        for t in ev['teams']:
            t['hasSeason'] = label in season_years.get(str(t['espnId']), set())
    stats['events_without_season_row'] = sum(
        1 for e in events if not e['teams'][0]['hasSeason'])

    locator = BoxLocator()
    out = {}
    for mmdd in all_mmdd():
        day_events, fillers = [], 0
        for e in sorted(by_day.get(mmdd, []), key=lambda e: (-e['sig'], e['date'])):
            if e['type'] in ('blowout', 'high_score'):
                if fillers >= MAX_FILLERS_PER_DAY:
                    continue
                fillers += 1
            day_events.append(e)
            if len(day_events) >= MAX_EVENTS:
                break
        for e in day_events:
            end = season_of(e['date'])
            e['season'] = '{}-{:02d}'.format(end - 1, end % 100)
            e['hasBox'] = locator.has_box(e)
            stats['events_with_box'] += 1 if e['hasBox'] else 0
        out[mmdd] = day_events
        if day_events:
            stats['days_with_events'] += 1

    save_json_atomic(os.path.join(ROOT, OUT_JSON), out,
                     separators=(',', ':'), ensure_ascii=False)

    size = os.path.getsize(os.path.join(ROOT, OUT_JSON))
    print('wrote {} ({:.1f} KB)'.format(OUT_JSON, size / 1024))
    for k in sorted(stats):
        print('  {}: {}'.format(k, stats[k]))
    if size > 2 * 1024 * 1024:
        print('ERROR: output exceeds 2MB budget', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
