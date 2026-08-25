#!/usr/bin/env python3
"""Split players.json into per-team players/{team}.json slices + an index.

Same lazy-load pattern as scripts/split_games.py and split_boxscores.py:
players.json is the READ-ONLY master build artifact (like games_1/2/3.json
and sr_boxscores.json); the browser only ever fetches an index plus the one
team slice a view needs.

Why this exists beyond payload size — the archive's shape changed. When
players.json was designed (2026-06) the archive was 2,892 games and almost
purely NCAA tournament. After the July harvest it is 20,679 games and only
~10% March/April, concentrated in whichever programs had deep Wayback
archives. A raw points leaderboard over that data ranks HARVEST DEPTH, not
playing careers: Charles Jenkins (Hofstra, 118 archived games) outranks
Christian Laettner (Duke, 23), who no longer appears at all.

So the index ships coverage denominators, not just totals:

  - every team carries archivedGames vs logGames (its real game count from
    games/index.json) and the resulting coveragePct, so any UI can say
    "142 of Virginia's 2,431 games are archived" instead of implying totals
    are career numbers;
  - the primary leaderboard is PER-GAME with a minimum-games floor, which
    is coverage-robust; the totals leaderboard is retained but explicitly
    labelled `mostArchivedPoints` so it cannot be mistaken for a scoring
    record;
  - `nonD1` marks team slugs with no data.json H entry (exhibition and
    small-college opponents that leak in from box scores, e.g.
    'menlo-college'), so a leaderboard can exclude them.

Slices carry FULL detail (perGame, best.date, best.opponent) — the 5MB
truncation that the monolith needs does not apply once payloads are
per-team.

Filenames: 9 team slugs contain '&' ('texas-a&m'). The file-safe key
collapses non-alphanumerics to '-' and is recorded per team in the index
as `file`, so lookup never has to re-derive it. Collisions are asserted
against, not silently merged.

Deterministic (sorted keys, stable separators), atomic, idempotent.

Run: python3 scripts/split_players.py
"""

import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from json_io import save_json_atomic

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, 'players.json')
OUT_DIR = os.path.join(ROOT, 'players')

# Per-game leaderboard floor. 8 games is low enough to admit genuinely
# thin-coverage stars and high enough to reject 2-game flukes.
MIN_GAMES_FOR_RATE = 8
LEADERBOARD_SIZE = 250

# Archive slug -> ESPN id, for programs whose archive spelling differs from
# every data.json/Sports-Reference form (the same abbreviation gap
# build_team_canon.py's ABBREV table closes for the name canon). Without
# these, 19 real D-I programs with thousands of archived games — Bowling
# Green, the UC schools, the A&M schools, VMI — get flagged nonD1 and drop
# out of leaderboards. Each pairing is asserted against data.json H below,
# so a typo fails the build instead of silently mislabelling a program.
SLUG_TO_ESPN = {
    'bowling-green': '189',              'uc-riverside': '27',
    'uc-san-diego': '28',                'uc-irvine': '300',
    'uc-davis': '302',                   'alabama-a&m': '2010',
    'william-&-mary': '2729',            'prairie-view-a&m': '2504',
    'southern-miss': '2572',             'texas-a&m-corpus-christi': '357',
    'vmi': '2678',                       'unc-greensboro': '2430',
    'kansas-city': '140',                'unc-asheville': '2427',
    'florida-a&m': '50',                 'siu-edwardsville': '2565',
    'the-citadel': '2643',               'umass-lowell': '2349',
    'queens': '2511',
}


def file_key(slug):
    return re.sub(r'-{2,}', '-', re.sub(r'[^a-z0-9]+', '-', slug)).strip('-')


def archived_games_per_team():
    """team-slug -> distinct archived box scores featuring that team.

    Reuses generate_players' own canonicalization (same slug space as the
    player index), so the count is the true numerator for coverage."""
    import generate_players as G
    with open(os.path.join(ROOT, 'sr_boxscores.json')) as f:
        store = json.load(f)
    names = set()
    for key, entry in store.items():
        if key == '_metadata' or not isinstance(entry, dict):
            continue
        for t in entry.get('teams') or []:
            if isinstance(t, dict) and isinstance(t.get('name'), str):
                names.add(t['name'])
    canon = G.build_team_canonical_map(names)
    counts = defaultdict(int)
    for key, entry in store.items():
        if key == '_metadata' or not isinstance(entry, dict):
            continue
        for slug in {G.slugify(canon.get(t['name'], t['name']))
                     for t in entry.get('teams') or []
                     if isinstance(t, dict) and isinstance(t.get('name'), str)}:
            counts[slug] += 1
    return counts


def load_team_context():
    """team-slug -> (espnId, logGames) for every real D-I program.

    Matching keys per team, all school-identifying (never bare nicknames —
    'Tigers' would collide across programs):
      1. the Sports-Reference slug from espn_to_sr.json ('virginia', 'duke')
         — this is the form the players archive canonicalizes to;
      2. the full data.json H name ('virginia-cavaliers');
      3. that name with its nickname suffix removed (H field 1 is the
         NICKNAME, so 'Virginia Cavaliers' - 'Cavaliers' -> 'virginia').
    """
    with open(os.path.join(ROOT, 'data.json')) as f:
        h = json.load(f)['H']
    try:
        with open(os.path.join(ROOT, 'espn_to_sr.json')) as f:
            sr = json.load(f)
    except FileNotFoundError:
        sr = {}
    try:
        with open(os.path.join(ROOT, 'games', 'index.json')) as f:
            counts = json.load(f)
    except FileNotFoundError:
        counts = {}

    def norm(s):
        s = s.lower().replace("'", '').replace('’', '')
        return re.sub(r'-{2,}', '-', re.sub(r'[^a-z0-9&]+', '-', s)).strip('-')

    ctx = {}
    for eid, fields in h.items():
        n = counts.get(eid)
        n = n.get('games') if isinstance(n, dict) else n
        full = fields[0]
        nick = fields[1] if len(fields) > 1 else ''
        school = full[:-len(nick)].strip() if nick and full.endswith(nick) else full
        for cand in {sr.get(eid, ''), norm(full), norm(school)}:
            if cand:
                ctx.setdefault(cand, (eid, n))
    for slug, eid in SLUG_TO_ESPN.items():
        if eid not in h:
            raise SystemExit('SLUG_TO_ESPN: {!r} -> unknown ESPN id {}'.format(slug, eid))
        n = counts.get(eid)
        ctx[slug] = (eid, n.get('games') if isinstance(n, dict) else n)
    return ctx


def main():
    with open(SOURCE) as f:
        players = json.load(f)

    by_team = defaultdict(dict)
    for key, rec in players.items():
        slug = (rec.get('teams') or [key.rsplit('|', 1)[-1]])[0]
        by_team[slug][key] = rec

    ctx = load_team_context()
    archived_counts = archived_games_per_team()
    os.makedirs(OUT_DIR, exist_ok=True)

    teams, seen_files = {}, {}
    for slug, recs in by_team.items():
        fk = file_key(slug)
        if fk in seen_files:
            raise SystemExit(
                'file-key collision: {!r} and {!r} both -> {!r}'.format(
                    seen_files[fk], slug, fk))
        seen_files[fk] = slug
        espn_id, log_games = ctx.get(slug, (None, None))
        archived = archived_counts.get(slug, 0)
        teams[slug] = {
            'file': fk + '.json',
            'players': len(recs),
            'archivedGames': archived,
            'espnId': espn_id,
            'logGames': log_games,
            'coveragePct': (round(100.0 * archived / log_games, 1)
                            if log_games else None),
            'nonD1': espn_id is None,
        }
        save_json_atomic(os.path.join(OUT_DIR, fk + '.json'), recs,
                         separators=(',', ':'), ensure_ascii=False,
                         sort_keys=True)

    def entry(key, r):
        e = {'key': key, 'name': r['name'], 'team': (r.get('teams') or [''])[0],
             'games': r['games'], 'pts': r['totals']['pts'],
             'years': r.get('years')}
        e['ppg'] = round(r['totals']['pts'] / r['games'], 1) if r['games'] else 0
        return e

    d1 = [(k, r) for k, r in players.items()
          if not teams.get((r.get('teams') or [''])[0], {}).get('nonD1')]
    by_rate = sorted((e for e in (entry(k, r) for k, r in d1)
                      if e['games'] >= MIN_GAMES_FOR_RATE),
                     key=lambda e: (-e['ppg'], e['name']))[:LEADERBOARD_SIZE]
    by_total = sorted((entry(k, r) for k, r in d1),
                      key=lambda e: (-e['pts'], e['name']))[:LEADERBOARD_SIZE]

    with open(os.path.join(ROOT, 'sr_boxscores.json')) as f:
        archived_total = sum(1 for k in json.load(f) if k != '_metadata')

    index = {
        '_metadata': {
            'note': ('Aggregates over archived box scores ONLY, not career '
                     'statistics. Coverage is uneven by program: totals '
                     'reflect how deeply a school was harvested. Use '
                     'pointsPerGame for comparisons and always show '
                     'archivedGames alongside any total.'),
            'minGamesForRateLeaderboard': MIN_GAMES_FOR_RATE,
            'teams': len(teams),
            'players': len(players),
            # Counts a UI can quote without double-counting: summing a
            # team's archivedGames across teams counts each game twice (once
            # per side), and slug count over-counts programs because several
            # slugs can share one ESPN id.
            'archivedGames': archived_total,
            'd1Programs': len({t['espnId'] for t in teams.values() if t['espnId']}),
        },
        'teams': teams,
        'pointsPerGame': by_rate,
        'mostArchivedPoints': by_total,
    }
    save_json_atomic(os.path.join(OUT_DIR, 'index.json'), index,
                     separators=(',', ':'), ensure_ascii=False, sort_keys=True)

    # validation: every player reachable through exactly one slice
    total = sum(t['players'] for t in teams.values())
    if total != len(players):
        raise SystemExit('slice total {} != source {}'.format(total, len(players)))
    stale = ({f[:-5] for f in os.listdir(OUT_DIR)
              if f.endswith('.json') and f != 'index.json'}
             - set(seen_files))
    for s in sorted(stale):
        os.remove(os.path.join(OUT_DIR, s + '.json'))
        print('removed stale players/{}.json'.format(s))
    n_nond1 = sum(1 for t in teams.values() if t['nonD1'])
    print('OK: wrote {} team files + index.json to players/'.format(len(teams)))
    print('    players: {} (all reachable); non-D1 team slugs flagged: {}'.format(
        total, n_nond1))


if __name__ == '__main__':
    main()
