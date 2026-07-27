#!/usr/bin/env python3
"""Build team_name_canon.json: every team-name string in the store -> canonical slug.

The store holds 2,100+ distinct name strings for ~365 programs ("UNC" vs
"North Carolina" vs "North Carolina Tar Heels"; "UCLA" vs "UCLA Bruins"). Any
grouping by team — H2H, team pages, the ranking/efficiency engine — needs one
identity per program.

Kept as a SIDE LOOKUP rather than a field on each team: the store is already
56MB against GitHub's 100MB limit, and 39k inline fields would add to that for
no benefit a 60KB map can't provide.

Reuses merge_pending_into_store's alias map (SR's opp_slug convention), plus
explicit fixes where SR's own slugs disagree with team_history.
"""
import json, collections, sys
sys.path.insert(0, '.')
from merge_pending_into_store import build_alias_map, make_canon

# SR's game logs and team_history disagree on a few programs; pick one winner.
OVERRIDE = {'unc': 'north-carolina'}

store = json.load(open('sr_boxscores.json'))
alias = build_alias_map()
canon = make_canon(alias)

names = collections.Counter()
for v in store.values():
    for t in v.get('teams', []):
        n = (t.get('name') or '').strip()
        if n:
            names[n] += 1

out, unresolved = {}, []
for n, c in names.items():
    s = canon(n)
    s = OVERRIDE.get(s, s)
    out[n] = s
    if s not in alias and OVERRIDE.get(s, s) not in alias:
        unresolved.append((c, n, s))

json.dump(out, open('team_name_canon.json', 'w'), indent=0, sort_keys=True)
groups = collections.Counter(out.values())
print(f'{len(out):,} name strings -> {len(groups):,} canonical programs')
print(f'unresolved (no alias-map hit): {len(unresolved)} '
      f'covering {sum(c for c, _, _ in unresolved)} team-games')
for c, n, s in sorted(unresolved, reverse=True)[:12]:
    print(f'   {c:4d}  {n!r} -> {s!r}')
print('\nsanity:')
for t in ['UNC', 'North Carolina', 'North Carolina Tar Heels', 'UCLA', 'UCLA Bruins',
          'Miami (OH)', 'Miami (FL)']:
    print(f'   {t!r:28s} -> {out.get(t)!r}')
