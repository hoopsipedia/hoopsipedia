#!/usr/bin/env python3
"""Precompute an 'On This Day in college basketball' dataset.

Reads the repo's dated game logs (games_1/2/3.json, 1941-2026), team
metadata (data.json H: name idx 0, NC count idx 6, NCY championship
years idx 7), seed-upset history (upset_history.json) and the
sr_boxscores.json URL dates, and writes on_this_day.json keyed by
'MM-DD' for all 366 calendar days. Each day holds up to MAX_EVENTS
events sorted by a significance score.

Event types (significance):
  championship  100        last game of a team's NCY-flagged title season
  upset         70+2*gap   NCAA first-round seed upsets from upset_history
  ot            30+8*nOT   multi-overtime games
  high_score    <=72       highest combined-score games
  blowout       <=68       biggest margins

ACCURACY RULE: every fact in a headline comes directly from a data
field; no embellishment. See OTD_NOTES.md for heuristics and risks.

Usage: python3 generate_on_this_day.py
"""

import datetime
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

MAX_EVENTS = 8
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
               w_pts, l_pts, sig):
    return {
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


def ot_phrase(ot):
    if ot == 'OT':
        return 'overtime'
    return '{} overtimes'.format(ot[:-2])


def score_regular_games(teams, canonical):
    """Score every canonical game on the high_score / blowout / ot axes
    and emit one event (its best axis) when any threshold is met."""
    events = []
    for g in canonical.values():
        total = g['w_pts'] + g['l_pts']
        margin = g['w_pts'] - g['l_pts']
        w_name = team_name(teams, g['w_id'])
        l_name = team_name(teams, g['l_id'])
        if w_name == 'Unknown' or l_name == 'Unknown':
            continue
        candidates = []
        if g['ot'] and g['ot'] != 'OT':
            n = int(g['ot'][:-2])
            head = '{}: {} outlasts {} {}-{} in {}'.format(
                g['date'], w_name, l_name, g['w_pts'], g['l_pts'],
                ot_phrase(g['ot']))
            candidates.append(('ot', 30 + 8 * n, head))
        if total >= HIGH_SCORE_MIN_TOTAL:
            head = '{}: {} outguns {} {}-{} in a {}-point shootout'.format(
                g['date'], w_name, l_name, g['w_pts'], g['l_pts'], total)
            candidates.append(('high_score',
                               min(72, 30 + (total - HIGH_SCORE_MIN_TOTAL) * 0.6),
                               head))
        if margin >= BLOWOUT_MIN_MARGIN:
            head = '{}: {} routs {} {}-{}, {} {}-point margin'.format(
                g['date'], w_name, l_name, g['w_pts'], g['l_pts'],
                article(margin), margin)
            candidates.append(('blowout', min(68, 25 + margin * 0.5), head))
        if not candidates:
            continue
        etype, sig, head = max(candidates, key=lambda c: c[1])
        events.append(make_event(g['date'], etype, head,
                                 g['w_id'], w_name, g['l_id'], l_name,
                                 g['w_pts'], g['l_pts'], sig))
    return events


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

    events = []
    events += detect_championships(teams, per_team, stats)
    stats['championship_events'] = sum(
        1 for e in events if e['type'] == 'championship')
    events += detect_upsets(teams, canonical, stats)
    events += score_regular_games(teams, canonical)

    by_day = defaultdict(list)
    seen = set()  # one event per (date, team pair)
    for ev in sorted(events, key=lambda e: -e['sig']):
        key = (ev['date'], frozenset(t['espnId'] or t['name']
                                     for t in ev['teams']))
        if key in seen:
            continue
        seen.add(key)
        by_day[ev['date'][5:]].append(ev)

    out = {}
    for mmdd in all_mmdd():
        day_events = sorted(by_day.get(mmdd, []),
                            key=lambda e: (-e['sig'], e['date']))[:MAX_EVENTS]
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
