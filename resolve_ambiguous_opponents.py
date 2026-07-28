#!/usr/bin/env python3
"""Resolve unresolvable opponent names in sr_boxscores.json per-game.

The store carries ~870 distinct opponent-name strings that no name-level
canon can safely map: genuinely ambiguous bases ("Miami", "Loyola", "ASU",
"USF"), abbreviations ("UMKC", "ULM", "W&M"), old program names ("Baptist
College", "Northeast Louisiana", "Texas-Pan American"), and outright
filename junk ("Chistmb", "Usdmbb", "Eiumens"). A name-level merge is
unsafe precisely because one string can mean two programs — but a
PER-GAME resolution is safe, because each box score names one specific
game whose opponent the game logs already know.

Method, per store entry with one unresolvable side and one resolved side:
  1. Find rows in the RESOLVED side's log with exactly the entry's two
     scores, constrained to the entry's embedded date (+/- 1 day) or, for
     undated entries, its season window.
  2. Map each row's opp_slug to a program via the audit's slug map
     (mirror-vote + variant folding).
  3. Only if every matching row agrees on ONE program, rename the
     unresolvable side to that program's data.json display name.
Ambiguous bases split correctly under this rule: "Miami" resolves to
Miami (OH) in 38 games and Miami (FL) in 32; "ASU" to Arkansas State in 3
and Arizona State in 1; "USF" to South Florida and San Francisco.

Every distinct (old name -> program) pair produced by the 2026-07-28 run
was manually reviewed before this was applied. Names with no log match
(Hartford, Oklahoma City, NYU, Centenary, other non-D1/defunct opponents)
are left untouched — an unmerged name beats a wrong merge.

Mirrors renames into sr_boxscores_modern.json for shared keys.
Idempotent: renamed sides resolve on re-run and are skipped.

Run:  python3 resolve_ambiguous_opponents.py [--apply]   (default dry-run)
"""

import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from json_io import save_json_atomic
import audit_boxscore_integrity as A

ROOT = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(ROOT, 'sr_boxscores.json')
MODERN = os.path.join(ROOT, 'sr_boxscores_modern.json')
DATE_RE = re.compile(r'(\d{4}-\d{2}-\d{2})')


def main():
    apply = '--apply' in sys.argv
    per_team, slug_of = A.load_logs()
    slug_map = A.build_slug_map(per_team, slug_of)
    resolve = A.build_name_map(slug_map)
    A.extend_slug_map(slug_map, per_team, resolve)
    with open(os.path.join(ROOT, 'data.json')) as f:
        hname = {tid: v[0] for tid, v in json.load(f)['H'].items()}

    store = json.load(open(STORE))
    modern = json.load(open(MODERN))

    renames = Counter()          # (old, new) -> games
    skipped = Counter()          # old name -> games (no/ambiguous candidate)
    touched_keys = []
    for key, v in store.items():
        if key == '_metadata':
            continue
        teams = v.get('teams') or []
        if len(teams) != 2 or any(not isinstance(t.get('score'), int) for t in teams):
            continue
        tids = [resolve(t['name']) for t in teams]
        for i, (t, tid) in enumerate(zip(teams, tids)):
            if tid or not tids[1 - i]:
                continue
            other, otid = teams[1 - i], tids[1 - i]
            rows = [g for g in per_team.get(otid, [])
                    if g['pts'] == other['score'] and g['opp_pts'] == t['score']]
            m = DATE_RE.search(key) or DATE_RE.search(v.get('url', '') or '')
            if m:
                d = m.group(1)
                near = [g for g in rows if g['date'][:7] == d[:7]
                        and abs(int(g['date'][8:10]) - int(d[8:10])) <= 1]
                rows = near or [g for g in rows if g['date'][:4] == d[:4]]
            else:
                lo, hi = A.season_window(int(key.split('/')[0]))
                rows = [g for g in rows if lo <= g['date'] <= hi]
            cands = {c for c in (slug_map.get(g['opp_slug']) for g in rows) if c}
            if len(cands) != 1:
                skipped[t['name']] += 1
                continue
            new_name = hname.get(next(iter(cands)))
            if not new_name or new_name == t['name']:
                continue
            renames[(t['name'], new_name)] += 1
            touched_keys.append(key)
            if apply:
                t['name'] = new_name

    print('{} team-sides renamed across {} distinct (old -> new) pairs; {} left unresolved'.format(
        sum(renames.values()), len(renames), sum(skipped.values())))
    for (o, n), c in renames.most_common():
        print('  {:4d}  {!r} -> {!r}'.format(c, o, n))
    print('\nunresolved (no unique log candidate), top 20:')
    for o, c in skipped.most_common(20):
        print('  {:4d}  {!r}'.format(c, o))

    if not apply:
        print('\nDRY RUN — re-run with --apply to write')
        return
    # mirror: modern's entries are independent objects — copy the whole
    # fixed entry for shared keys
    n_mirror = 0
    for key in set(touched_keys):
        if key in modern:
            modern[key] = store[key]
            n_mirror += 1
    save_json_atomic(STORE, store)   # compact: stays under GitHub's 100MB
    save_json_atomic(MODERN, modern, indent=2)
    print('\nAPPLIED: sr_boxscores.json written, {} entries mirrored into modern'.format(n_mirror))


if __name__ == '__main__':
    main()
