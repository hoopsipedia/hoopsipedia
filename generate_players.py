#!/usr/bin/env python3
"""Build players.json from the box-score archive (sr_boxscores.json).

Aggregates per-player stat lines into a player index keyed by normalized
player name + team slug. The archive mixes many source generations, so
lines are recognised by CONTENT (does this row carry any stat column?)
rather than by any one schema's marker field — see parse_player_line.

Unparseable lines are skipped and counted, never guessed at.

IMPORTANT: these are "games in our box-score archive" aggregates — NOT
career statistics. Coverage is uneven by program, so archive TOTALS rank
harvest depth rather than players; per-game rates are the comparable
figure. A stat the source never recorded stays null, never 0. See
PLAYERS_NOTES.md.

players.json is the full-fidelity master; scripts/split_players.py emits
the per-team players/ slices the browser actually fetches. Output is
deterministic (sorted keys, stable rounding), written atomically via
json_io.save_json_atomic.

Usage: python3 generate_players.py [--cap]
  --cap  apply the legacy 5MB payload cap (destructive: truncates stat
         detail, then drops the lowest-scoring players). Off by default.
"""

import json
import os
import re
import sys
from collections import Counter

from json_io import save_json_atomic

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, 'sr_boxscores.json')
OUT = os.path.join(ROOT, 'players.json')

SIZE_CAP_BYTES = 5 * 1024 * 1024

# Minimum inclusion: >= 2 recorded games OR >= 15 points in a single game.
MIN_GAMES = 2
MIN_SINGLE_GAME_PTS = 15

DATE_RE = re.compile(r'(\d{4}-\d{2}-\d{2})')

# ---------------------------------------------------------------------------
# Team-name canonicalization.
#
# The archive mixes two team-naming generations: short school names
# ("Texas A&M", "Navy") in older entries and school+nickname forms
# ("Texas A&M Aggies", "Navy Midshipmen") in newer ones. To keep one
# player on one team under a single slug, a long form is folded onto a
# short form that is a strict word-boundary prefix of it — but ONLY when
# the remainder is a nickname, not a school-distinguishing word
# ("Alabama State" must NOT fold onto "Alabama").
# ---------------------------------------------------------------------------

# If the first word of the remainder is one of these (or starts with A&M),
# the prefix match is a DIFFERENT school, so do not fold.
_SCHOOL_WORD_BLOCKLIST = {
    'State', 'Tech', 'Southern', 'Miss', 'Utah', 'Illinois', 'Atlantic',
    'Gulf', 'International', 'Baptist', 'Asheville', 'Greensboro',
    'Wilmington',
}


def slugify(name):
    """Deterministic slug: lowercase, apostrophes removed, '&' kept,
    every other non-alphanumeric run collapsed to '-'."""
    s = name.lower().replace("'", '').replace('’', '')
    s = re.sub(r'[^a-z0-9&]+', '-', s).strip('-')
    return s


def build_team_canonical_map(all_team_names):
    """Map long-form team names to their short-form school name when safe."""
    names = sorted(all_team_names)
    mapping = {}
    for name in names:
        best = None
        for cand in names:
            if cand != name and name.startswith(cand + ' '):
                if best is None or len(cand) > len(best):
                    best = cand
        if best is None:
            continue
        remainder_first = name[len(best):].strip().split(' ')[0]
        if remainder_first in _SCHOOL_WORD_BLOCKLIST:
            continue
        if remainder_first.startswith('A&M'):
            continue
        mapping[name] = best
    return mapping


def normalize_player_name(name):
    """Normalization used for merge keys: case/punctuation-insensitive."""
    return slugify(name)


def _to_int(v):
    """Parse a stat value that may be an int or a numeric string.

    Returns None for a value that is absent-in-disguise (null, empty
    string, '-'), which callers must treat as NOT RECORDED rather than
    zero — see parse_player_line."""
    if v is None:
        return None
    if isinstance(v, bool):
        raise ValueError('bool is not a stat')
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        s = v.strip()
        if s == '' or s == '-':
            return None
        return int(s)
    raise ValueError('unparseable stat value: %r' % (v,))


def _to_reb(v):
    """Rebounds only — the one stat sources split offensive/defensive.

    Four dialects appear in the archive:
      5                     plain total
      {"off":1,"def":4,"tot":5}
      "1+5"                 off+def
      "0-0" / "1-1-2"       off-def, or off-def-total

    Deliberately NOT folded into _to_int: 'fg' and 'ft' use the same
    hyphen shape for made-attempted ("8-13"), so summing hyphenated
    values is only ever correct for a rebound field."""
    if isinstance(v, dict):
        for k in ('tot', 'total'):
            if isinstance(v.get(k), int):
                return v[k]
        parts = [v.get('off'), v.get('def')]
        if all(isinstance(x, int) for x in parts):
            return sum(parts)
        raise ValueError('unparseable rebound value: %r' % (v,))
    if isinstance(v, str):
        s = v.strip()
        if s and not s.lstrip('-').isdigit():
            nums = re.fullmatch(r'(\d+)\s*[-+]\s*(\d+)(?:\s*-\s*(\d+))?', s)
            if nums:
                # 3 parts: the last is the printed total. 2 parts: off+def.
                if nums.group(3) is not None:
                    return int(nums.group(3))
                return int(nums.group(1)) + int(nums.group(2))
            raise ValueError('unparseable rebound value: %r' % (v,))
    return _to_int(v)


# Per-schema source key for each stat we aggregate. The older regex-scraper
# schema names rebounds 'trb'; everything else agrees.
_STAT_KEYS = {
    'pts': ('pts',), 'reb': ('reb', 'trb'), 'ast': ('ast',),
    'stl': ('stl',), 'blk': ('blk',),
}
# Rebounds need the off/def-aware parser; every other stat is a plain count.
_STAT_PARSERS = {'reb': _to_reb}
# A line must carry at least one of these to be a player line at all.
_ANY_STAT_KEY = frozenset(
    ['pts', 'reb', 'trb', 'ast', 'stl', 'blk', 'fg', 'ft', 'min', 'mp'])
# Non-player rows that reach us as if they were players.
_NON_PLAYER_NAMES = frozenset(['totals', 'total', 'team', 'tm', 'totals.',
                               'team totals', 'opponents'])


def parse_player_line(p):
    """Return (name, stats) or raise ValueError.

    stats maps each stat to an int WHEN THE SOURCE RECORDED IT and to None
    when it did not. That distinction matters: pre-1980s box scores simply
    have no assist/steal/block columns, and early-1950s ones often print
    only pts/fg/ft. Coercing those to 0 would publish "0 rebounds" as a
    fact about players from eras that never counted rebounds.

    Schema detection is by CONTENT, not by the presence of a minutes
    column. Dispatching on 'min'/'mp' rejected 33,413 otherwise-valid
    stat lines (8.2% of the archive, concentrated in exactly the historical
    games the site cares most about) purely because they lacked a minutes
    field."""
    if not isinstance(p, dict):
        raise ValueError('player line is not a dict')
    name = p.get('name')
    if not isinstance(name, str) or not name.strip():
        raise ValueError('missing player name')
    name = ' '.join(name.split())
    low = name.lower().strip('. ')
    if 'total' in low or low in _NON_PLAYER_NAMES:
        raise ValueError('totals row, not a player')
    if not (_ANY_STAT_KEY & set(p)):
        raise ValueError('no stat columns: %s' % sorted(p.keys()))
    stats = {}
    for stat, sources in _STAT_KEYS.items():
        parse = _STAT_PARSERS.get(stat, _to_int)
        val = None
        for src in sources:
            if src in p:
                val = parse(p[src])
                if val is not None:
                    break
        stats[stat] = val
    if all(v is None for v in stats.values()):
        raise ValueError('no usable stat values: %s' % sorted(p.keys()))
    return name, stats


def aggregate(data):
    """First pass: collect raw per-(player, team-slug) aggregates."""
    team_names = set()
    for key, entry in data.items():
        if key == '_metadata' or not isinstance(entry, dict):
            continue
        for t in entry.get('teams', []) or []:
            if isinstance(t, dict) and isinstance(t.get('name'), str):
                team_names.add(t['name'])
    canon = build_team_canonical_map(team_names)

    players = {}
    parsed = 0
    skipped = 0
    games_seen = 0

    for key in sorted(k for k in data if k != '_metadata'):
        entry = data[key]
        if not isinstance(entry, dict):
            skipped += 1
            continue
        try:
            year = int(key.split('/', 1)[0])
        except (ValueError, IndexError):
            year = None
        date = None
        url = entry.get('url')
        if isinstance(url, str):
            m = DATE_RE.search(url)
            if m:
                date = m.group(1)
        teams = entry.get('teams')
        if not isinstance(teams, list):
            continue
        games_seen += 1
        for idx, team in enumerate(teams):
            if not isinstance(team, dict):
                continue
            raw_team_name = team.get('name')
            if not isinstance(raw_team_name, str):
                continue
            school = canon.get(raw_team_name, raw_team_name)
            team_slug = slugify(school)
            opp_names = [t.get('name') for j, t in enumerate(teams)
                         if j != idx and isinstance(t, dict)]
            opponent = None
            if opp_names and isinstance(opp_names[0], str):
                opponent = canon.get(opp_names[0], opp_names[0])
            for p in team.get('players', []) or []:
                try:
                    pname, stats = parse_player_line(p)
                except (ValueError, TypeError):
                    skipped += 1
                    continue
                parsed += 1
                pkey = '%s|%s' % (normalize_player_name(pname), team_slug)
                rec = players.get(pkey)
                if rec is None:
                    rec = players[pkey] = {
                        'names': Counter(),
                        'team': team_slug,
                        'games': 0,
                        'totals': Counter(),
                        'statGames': Counter(),
                        'best': None,
                        'years': [],
                    }
                rec['names'][pname] += 1
                rec['games'] += 1
                for f, v in stats.items():
                    if v is not None:
                        rec['totals'][f] += v
                        # per-stat denominator: only games whose source
                        # actually carried this column
                        rec['statGames'][f] += 1
                if year is not None:
                    rec['years'].append(year)
                pts = stats['pts']
                if pts is not None:
                    best = rec['best']
                    game_ref = {'pts': pts, 'year': year,
                                'date': date, 'opponent': opponent}
                    if best is None or (pts, year or 0) > \
                            (best['pts'], best['year'] or 0):
                        rec['best'] = game_ref
    return players, parsed, skipped, games_seen


def finalize(players):
    """Filter, shape, and deterministically order the output entries."""
    out = {}
    for pkey in sorted(players):
        rec = players[pkey]
        best_pts = rec['best']['pts'] if rec['best'] else 0
        if rec['games'] < MIN_GAMES and best_pts < MIN_SINGLE_GAME_PTS:
            continue
        # Display name: most frequent spelling, ties broken alphabetically.
        name = sorted(rec['names'].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        g = rec['games']
        # A stat recorded in NO archived game stays null all the way out:
        # reporting 0 blocks for a 1954 player would be inventing a fact.
        # perGame divides by that stat's own denominator, so a player with
        # rebounds in 4 of 11 archived games gets reb/4, not reb/11.
        stat_games = rec.get('statGames', {})
        totals, per_game = {}, {}
        for f in ('pts', 'reb', 'ast', 'stl', 'blk'):
            n = stat_games.get(f, 0)
            if n:
                totals[f] = int(rec['totals'].get(f, 0))
                per_game[f] = round(totals[f] / n, 1)
            else:
                totals[f] = None
                per_game[f] = None
        years = sorted(rec['years']) or [None]
        out[pkey] = {
            'name': name,
            'teams': [rec['team']],
            'games': g,
            'totals': totals,
            'perGame': per_game,
            'statGames': {f: stat_games.get(f, 0)
                          for f in ('pts', 'reb', 'ast', 'stl', 'blk')},
            'best': rec['best'],
            'years': [years[0], years[-1]],
        }
    return out


def _payload_size(obj):
    return len(json.dumps(obj, separators=(',', ':'), ensure_ascii=False)
               .encode('utf-8'))


def _shrink_to_cap(out):
    """Keep the payload under SIZE_CAP_BYTES. Truncate stat detail first
    (drop best-game date, then opponent, then perGame — all derivable or
    decorative), and only as a last resort drop the lowest-total players."""
    steps = []
    if _payload_size(out) <= SIZE_CAP_BYTES:
        return out, steps
    for field, action in (('date', 'dropped best.date'),
                          ('opponent', 'dropped best.opponent')):
        for rec in out.values():
            if rec.get('best'):
                rec['best'].pop(field, None)
        steps.append(action)
        if _payload_size(out) <= SIZE_CAP_BYTES:
            return out, steps
    for rec in out.values():
        rec.pop('perGame', None)
    steps.append('dropped perGame (recompute as totals/games)')
    if _payload_size(out) <= SIZE_CAP_BYTES:
        return out, steps
    # Drop lowest-total players in bulk. Serializing the whole multi-MB
    # payload once per dropped player is O(players * bytes) — hours at 20K+
    # games — so estimate each record's own serialized size (its dump plus
    # the joining comma), drop enough to clear the cap in one pass, then
    # verify and top up one at a time (the estimate is near-exact, so the
    # tail loop runs at most a handful of times).
    ranked = sorted(out, key=lambda k: (out[k]['totals']['pts'] or 0, k))
    dropped = 0
    size = _payload_size(out)
    while ranked and size > SIZE_CAP_BYTES:
        overshoot = size - SIZE_CAP_BYTES
        freed = 0
        while ranked and freed < overshoot:
            k = ranked.pop(0)
            freed += len(json.dumps({k: out.pop(k)}, separators=(',', ':'),
                                    ensure_ascii=False).encode('utf-8')) - 1
            dropped += 1
        size = _payload_size(out)
    steps.append('dropped %d lowest-scoring players' % dropped)
    return out, steps


def main():
    # players.json is the full-fidelity MASTER build artifact, like
    # games_1/2/3.json and sr_boxscores.json. The browser never fetches it —
    # scripts/split_players.py produces the per-team players/ slices that
    # ship. So the 5MB cap is opt-in (--cap): applying it by default silently
    # destroyed 21,942 players plus every perGame and best.date/best.opponent
    # field once the archive passed ~20K games.
    cap = '--cap' in sys.argv
    with open(SRC) as f:
        data = json.load(f)
    players, parsed, skipped, games_seen = aggregate(data)
    out = finalize(players)
    shrink_steps = []
    if cap:
        out, shrink_steps = _shrink_to_cap(out)
    save_json_atomic(OUT, out, separators=(',', ':'), ensure_ascii=False,
                     sort_keys=True)
    size = os.path.getsize(OUT)
    top10 = sorted(out.values(),
                   key=lambda r: (-(r['totals']['pts'] or 0), r['name']))[:10]
    report = {
        'gamesProcessed': games_seen,
        'statLinesParsed': parsed,
        'statLinesSkipped': skipped,
        'playersBeforeFilter': len(players),
        'playersWritten': len(out),
        'outputBytes': size,
        'shrinkSteps': shrink_steps,
        'top10ByArchivePoints': [
            {'name': r['name'], 'team': r['teams'][0], 'games': r['games'],
             'pts': r['totals']['pts'], 'years': r['years']}
            for r in top10
        ],
    }
    json.dump(report, sys.stdout, indent=2)
    print()


if __name__ == '__main__':
    main()
