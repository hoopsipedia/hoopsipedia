#!/usr/bin/env python3
"""Give VMI (2678) its real game log back; collapse the Valparaiso duplicate.

Found by audit_boxscore_integrity.py after the 2026-07 box-score expansion:
every VMI box score audited CONTRADICTED because the games files store

  - games_1.json["157"]   VMI's actual log (1,913 games, 1950-2026; top
                          opponents Citadel/Furman/Davidson — Southern
                          Conference) under an ORPHAN id: 157 is not in
                          data.json H, so no team page owns these games.
                          1,064 opp-id references across all three shards
                          point at 157.
  - games_3.json["2678"]  VMI's official id, but the entry is a byte-level
                          duplicate of Valparaiso's log (2674) in the
                          {slug, games}+arena format — so the VMI team page
                          renders Valparaiso's game history.
  - games_3.json["2674"]  Valparaiso's log again, list format, with opp ids
                          but no arena data.

Repair (same shape as the 2026-06-11 Drake 263 dedup):
  1. games_3["2674"] becomes the {slug: "valparaiso", games} entry with
     arena data, grafting each game's opp id from the old list copy
     (matched on date+opp_slug+scores). games_3["2678"] is deleted.
  2. games_1["157"] is rekeyed to games_1["2678"] — VMI's page now shows
     VMI's games, in exactly one shard.
  3. Every row with opp == "157" is rewritten to opp == "2678".

seasons.json / h2h.json / team_history.json / draft_history.json for 2678
were verified to already hold real VMI data (they are compiled from SR by
slug, not from the games files) and are untouched.

Also removes the other two orphan duplicate logs the same audit pass
surfaced: 2563 (exact copy of South Dakota, 233) and 2566 (exact copy of
South Dakota State, 2571). Neither id exists in data.json H, and unlike
VMI the official ids already hold correct logs — the orphans just ship
dead slices and split the audit's mirror voting. Stray opp refs to them
are remapped to the official ids.

Idempotent: re-running after the fix makes 0 changes.

Run:  python3 repair_vmi_identity.py [--dry-run]
"""

import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from json_io import save_json_atomic

ROOT = os.path.dirname(os.path.abspath(__file__))
ORPHAN, VMI, VALPO = '157', '2678', '2674'

# orphan id -> official id whose log it duplicates (orphan game set must be
# a subset of the official's; complementary opp/arena fields are grafted
# onto the official rows before the orphan is dropped)
ORPHAN_DUPES = {
    '2563': '233',    # South Dakota (exact copy)
    '2566': '2571',   # South Dakota State (exact copy)
    '2656': '2655',   # Tulane (orphan carries ~300 extra opp ids)
    '2631': '202',    # Tulsa (orphan carries the arena data)
}


def rows_of(entry):
    return entry['games'] if isinstance(entry, dict) else entry


def game_key(g):
    return (g['date'], g['opp_slug'], g['pts'], g['opp_pts'])


def main():
    dry = '--dry-run' in sys.argv
    shards = {}
    for i in (1, 2, 3):
        path = os.path.join(ROOT, 'games_{}.json'.format(i))
        with open(path) as f:
            shards[path] = json.load(f)
    g1 = shards[os.path.join(ROOT, 'games_1.json')]
    g3 = shards[os.path.join(ROOT, 'games_3.json')]
    changed = set()

    # ---- 1+2: entry surgery (skip cleanly if already repaired) ----
    if ORPHAN in g1:
        vmi_rows = rows_of(g1[ORPHAN])
        opps = Counter(r['opp_slug'] for r in vmi_rows)
        assert opps.most_common(1)[0][0] == 'citadel', \
            'games_1["157"] does not look like VMI: top opp {}'.format(opps.most_common(3))
        assert VMI in g3 and isinstance(g3[VMI], dict) \
            and g3[VMI].get('slug') == 'valparaiso', 'games_3["2678"] is not the Valpo duplicate'
        dup_rows, valpo_rows = rows_of(g3[VMI]), rows_of(g3[VALPO])
        assert {game_key(r) for r in dup_rows} == {game_key(r) for r in valpo_rows}, \
            '2678/2674 game sets differ — not the known exact duplicate'

        opp_by_key = {game_key(r): r['opp'] for r in valpo_rows if r.get('opp')}
        grafted = 0
        for r in dup_rows:
            if 'opp' not in r and game_key(r) in opp_by_key:
                r['opp'] = opp_by_key[game_key(r)]
                grafted += 1
        g3[VALPO] = {'slug': 'valparaiso', 'games': dup_rows}
        del g3[VMI]
        assert VMI not in g1
        g1[VMI] = g1.pop(ORPHAN)
        changed.update(('games_1.json', 'games_3.json'))
        print('VMI: rekeyed games_1 157 -> 2678 ({} games)'.format(len(vmi_rows)))
        print('Valparaiso: kept arena copy under 2674, grafted {} opp ids, '
              'deleted duplicate 2678'.format(grafted))
    else:
        print('157 not present — entry surgery already done')

    # ---- 3: drop orphan duplicate logs, grafting complementary fields ----
    entries = {}   # id -> (path, entry) for every id involved
    for path, data in shards.items():
        for k in list(ORPHAN_DUPES) + list(ORPHAN_DUPES.values()):
            if k in data:
                entries[k] = (path, data[k])
    for oid, canon in ORPHAN_DUPES.items():
        if oid not in entries:
            continue
        opath, oentry = entries[oid]
        cpath, centry = entries[canon]
        orows, crows = rows_of(oentry), rows_of(centry)
        by_key = {game_key(r): r for r in orows}
        assert set(by_key) <= {game_key(r) for r in crows}, \
            '{} is not a subset duplicate of {}'.format(oid, canon)
        grafted = 0
        for r in crows:
            src = by_key.get(game_key(r))
            if not src:
                continue
            for field in ('opp', 'arena'):
                if field not in r and field in src:
                    r[field] = src[field]
                    grafted += 1
        del shards[opath][oid]
        changed.update((os.path.basename(opath), os.path.basename(cpath)) if grafted
                       else (os.path.basename(opath),))
        print('dropped orphan {} ({} games, subset of {}), grafted {} fields onto {}'.format(
            oid, len(orows), canon, grafted, canon))

    # ---- 4: opp-id rewrite ----
    remap = dict(ORPHAN_DUPES)
    remap[ORPHAN] = VMI
    for path, data in shards.items():
        n = 0
        for entry in data.values():
            for r in rows_of(entry):
                if r.get('opp') in remap:
                    r['opp'] = remap[r['opp']]
                    n += 1
        if n:
            changed.add(os.path.basename(path))
            print('{}: rewrote {} orphan opp refs'.format(os.path.basename(path), n))

    if not changed:
        print('Nothing to do.')
        return
    if dry:
        print('--dry-run: would write ' + ', '.join(sorted(changed)))
        return
    for path, data in shards.items():
        if os.path.basename(path) in changed:
            save_json_atomic(path, data, separators=(',', ':'))
            print('wrote', os.path.basename(path))


if __name__ == '__main__':
    main()
