#!/usr/bin/env python3
"""Merge gated pending box-score files into sr_boxscores.json.

Pending files are produced by harvest_bigbluehistory.py / harvest_hogstats.py /
merge_team_extractions.py — every game in them has already passed the checksum
and game-log gates. This script only handles store semantics:
  - exact-key duplicates are skipped (idempotent re-runs as fleets grow pendings)
  - tournament dedupe: an SR entry for the same season with the same two teams
    (keys like "1985/navy-midshipmen-vs-lsu-tigers", no date) wins over an
    archive copy of the same game — archive version skipped
  - after merging, run scripts/split_boxscores.py to regenerate slices+index.

Usage: python3 merge_pending_into_store.py <pending.json> [<pending2.json> ...]
"""
import json
import re
import sys


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def build_alias_map():
    """name-slug -> canonical short slug (SR's opp_slug convention).

    Game logs pair opp team id with SR's canonical slug; team_history pairs
    id with the full name ("Duke Blue Devils"). Together they normalize any
    of "Duke" / "Duke Blue Devils" / "duke-blue-devils" to "duke"."""
    slug_by_id = {}
    for fn in ('games_1.json', 'games_2.json', 'games_3.json'):
        d = json.load(open(fn))
        for v in d.values():
            games = v['games'] if isinstance(v, dict) else v
            for g in games:
                if g.get('opp') and g.get('opp_slug'):
                    slug_by_id[str(g['opp'])] = g['opp_slug']
    alias = {}
    th = json.load(open('team_history.json'))
    for tid, v in th.items():
        canon = slug_by_id.get(tid)
        if not canon:
            continue
        alias[canon] = canon
        alias[slugify(v.get('team', ''))] = canon
    return alias


def make_canon(alias):
    def canon(name):
        s = slugify(re.sub(r'^#\d+\s*', '', name or ''))
        if s in alias:
            return alias[s]
        s2 = re.sub(r'\bst\b', 'state', s.replace('-', ' ')).replace(' ', '-')
        return alias.get(s2, s)
    return canon


def main():
    store = json.load(open('sr_boxscores.json'))
    canon = make_canon(build_alias_map())
    # Two dedupe identities, both on CANONICAL team slugs (name conventions
    # vary: SR tournament uses short names, archives use full or freeform):
    #  - date-less SR tournament entries: (year, pair) — one matchup = one
    #    tournament game. Dated games never dedupe on (year, pair): conference
    #    teams meet 2-3x a season.
    #  - dated entries: (date, pair) — catches the same game arriving from
    #    two teams' archives under mirrored keys.
    existing_pairs = set()
    existing_dated = set()
    for k, v in store.items():
        if k == '_metadata' or not isinstance(v, dict):
            continue
        year = k.split('/', 1)[0]
        names = frozenset(canon(t.get('name', '')) for t in v.get('teams', []))
        if v.get('date'):
            existing_dated.add((v['date'], names))
        else:
            existing_pairs.add((year, names))

    total_added = 0
    for path in sys.argv[1:]:
        pending = json.load(open(path))
        games = pending.get('games', pending)
        added = skipped_key = skipped_pair = 0
        for key, g in games.items():
            if key in store:
                skipped_key += 1
                continue
            year = key.split('/', 1)[0]
            names = frozenset(canon(t.get('name', '')) for t in g.get('teams', []))
            if (year, names) in existing_pairs or (g.get('date'), names) in existing_dated:
                skipped_pair += 1
                continue
            store[key] = g
            if g.get('date'):
                existing_dated.add((g['date'], names))
            added += 1
        total_added += added
        print(f'{path}: +{added} (skipped {skipped_key} same-key, {skipped_pair} same-matchup)')

    if '_metadata' in store:
        store['_metadata']['totalGames'] = len(store) - 1
    json.dump(store, open('sr_boxscores.json', 'w'), separators=(',', ':'))
    n = len(store) - (1 if '_metadata' in store else 0)
    print(f'store now {n} games (+{total_added})')


if __name__ == '__main__':
    main()
