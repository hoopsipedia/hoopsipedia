#!/usr/bin/env python3
"""Build players.json from the box-score archive (sr_boxscores.json).

Aggregates per-player tournament stat lines into a player index keyed by
normalized player name + team slug. Handles BOTH box-score schemas that
coexist in sr_boxscores.json:

  1. Canonical schema (int values):
       {name, min, pts, fg "8-14", tp, ft, reb, ast, stl, blk, to}
     (a small subset of older canonical lines lacks the "tp" key)
  2. Older regex-scraper schema (string values, sr_boxscores_modern.json era):
       {name, mp, pts, fg, fga, fg3, fg3a, ft, fta, trb, ast, stl, blk, tov}

Unparseable player lines are skipped and counted, never guessed at.

IMPORTANT: these are "games in our box-score archive" aggregates
(NCAA-tournament-heavy, ~2.9K games) — NOT career statistics.

Output is deterministic (sorted keys, stable rounding) and written
atomically via json_io.save_json_atomic. Target size: < 5MB; if the
payload exceeds the cap, stat detail is truncated before any player
is dropped (see _shrink_to_cap).

Usage: python3 generate_players.py
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
    """Parse a stat value that may be an int or a numeric string."""
    if isinstance(v, bool):
        raise ValueError('bool is not a stat')
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        s = v.strip()
        if s == '':
            return 0
        return int(s)
    raise ValueError('unparseable stat value: %r' % (v,))


def parse_player_line(p):
    """Return (name, stats dict) for either schema, or raise ValueError."""
    if not isinstance(p, dict):
        raise ValueError('player line is not a dict')
    name = p.get('name')
    if not isinstance(name, str) or not name.strip():
        raise ValueError('missing player name')
    name = ' '.join(name.split())
    if 'total' in name.lower():
        raise ValueError('totals row, not a player')
    if 'mp' in p:  # older regex-scraper schema (string values)
        stats = {
            'pts': _to_int(p.get('pts', 0)),
            'reb': _to_int(p.get('trb', 0)),
            'ast': _to_int(p.get('ast', 0)),
            'stl': _to_int(p.get('stl', 0)),
            'blk': _to_int(p.get('blk', 0)),
        }
    elif 'min' in p:  # canonical schema (int values; 'tp' sometimes absent)
        stats = {
            'pts': _to_int(p.get('pts', 0)),
            'reb': _to_int(p.get('reb', 0)),
            'ast': _to_int(p.get('ast', 0)),
            'stl': _to_int(p.get('stl', 0)),
            'blk': _to_int(p.get('blk', 0)),
        }
    else:
        raise ValueError('unrecognized player-line schema: %s'
                         % sorted(p.keys()))
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
                        'best': None,
                        'years': [],
                    }
                rec['names'][pname] += 1
                rec['games'] += 1
                for f, v in stats.items():
                    rec['totals'][f] += v
                if year is not None:
                    rec['years'].append(year)
                best = rec['best']
                game_ref = {'pts': stats['pts'], 'year': year,
                            'date': date, 'opponent': opponent}
                if best is None or (stats['pts'], year or 0) > \
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
        totals = {f: int(rec['totals'].get(f, 0))
                  for f in ('pts', 'reb', 'ast', 'stl', 'blk')}
        per_game = {f: round(totals[f] / g, 1) for f in totals}
        years = sorted(rec['years']) or [None]
        out[pkey] = {
            'name': name,
            'teams': [rec['team']],
            'games': g,
            'totals': totals,
            'perGame': per_game,
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
    ranked = sorted(out, key=lambda k: (out[k]['totals']['pts'], k))
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
    with open(SRC) as f:
        data = json.load(f)
    players, parsed, skipped, games_seen = aggregate(data)
    out = finalize(players)
    out, shrink_steps = _shrink_to_cap(out)
    save_json_atomic(OUT, out, separators=(',', ':'), ensure_ascii=False,
                     sort_keys=True)
    size = os.path.getsize(OUT)
    top10 = sorted(out.values(),
                   key=lambda r: (-r['totals']['pts'], r['name']))[:10]
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
