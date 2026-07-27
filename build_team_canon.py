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
import json, collections, re, sys
sys.path.insert(0, '.')
from merge_pending_into_store import build_alias_map, make_canon

# SR's game logs and team_history disagree on a few programs; pick one winner.
OVERRIDE = {'unc': 'north-carolina'}

# Curated abbreviation -> canonical slug. The alias map is built from game-log
# opp_slug pairs, so programs that rarely appear as an opponent have no entry
# and a box score's shorthand ("LSU", "Ole Miss") self-canonicalizes into its
# own phantom program. Every target here was verified to exist in the alias map.
#
# DELIBERATELY ABSENT — genuinely ambiguous, a wrong merge is worse than an
# unmerged name: "Miami" (OH vs FL), "Loyola" (IL / Marymount / MD),
# "Louisiana" (Lafayette vs State), "Southern" (Southern U vs Southern Miss/Cal).
ABBREV = {
    'lsu': 'louisiana-state', 'uconn': 'connecticut', 'texas-a-m': 'texas-am',
    'ole-miss': 'mississippi', 'nc-state': 'north-carolina-state', 'n-c-state': 'north-carolina-state',
    'n-c-state-wolfpack': 'north-carolina-state', 'penn': 'pennsylvania',
    'st-john-s-ny': 'st-johns-ny', 'st-john-s': 'st-johns-ny',
    'unlv': 'nevada-las-vegas', 'pitt': 'pittsburgh', 'smu': 'southern-methodist',
    'byu': 'brigham-young', 'brigham-young-cougars': 'brigham-young',
    'tcu': 'texas-christian', 'saint-joseph-s': 'saint-josephs',
    'usc': 'southern-california', 'detroit': 'detroit-mercy',
    'prairie-view-a-m': 'prairie-view', 'vcu': 'virginia-commonwealth',
    'utep': 'texas-el-paso', 'uc-irvine': 'california-irvine',
    'uab': 'alabama-birmingham', 'central-connecticut': 'central-connecticut-state',
    'bowling-green': 'bowling-green-state', 'uc-santa-barbara': 'california-santa-barbara',
    'saint-mary-s': 'saint-marys-ca', 'mount-st-mary-s': 'mount-st-marys',
    'long-island': 'long-island-university', 'uw-green-bay': 'green-bay',
    'unc-wilmington': 'north-carolina-wilmington', 'uc-davis': 'california-davis',
    'umass': 'massachusetts', 'north-carolina-a-t': 'north-carolina-at',
    'grambling-state': 'grambling', 'memphis-state-tigers': 'memphis',
    'memphis-state': 'memphis',
    # second tier
    'southern-miss': 'southern-mississippi', 'connecticut-huskies': 'connecticut',
    'iona-college': 'iona', 'ucf': 'central-florida',
    'texas-a-m-corpus-christi': 'texas-am-corpus-christi', 'st-louis': 'saint-louis',
    'umbc': 'maryland-baltimore-county', 'umkc': 'missouri-kansas-city',
    'utsa': 'texas-san-antonio', 'uic': 'illinois-chicago',
    'ualr': 'arkansas-little-rock', 'the-citadel': 'citadel',
    'uncw': 'north-carolina-wilmington', 'unc-asheville': 'north-carolina-asheville',
    'uncg': 'north-carolina-greensboro', 'hawai-i': 'hawaii', 'hawai-i-rainbow-warriors': 'hawaii',
}
OVERRIDE.update(ABBREV)

store = json.load(open('sr_boxscores.json'))
alias = build_alias_map()
canon = make_canon(alias)

names = collections.Counter()
for v in store.values():
    for t in v.get('teams', []):
        n = (t.get('name') or '').strip()
        if n:
            names[n] += 1

def resolve(n):
    """canon() with safe fallbacks. Each fallback is ACCEPTED ONLY if it lands
    on a real alias-map slug, so a rewrite can never invent a program."""
    s = OVERRIDE.get(canon(n), canon(n))
    if s in alias or s in OVERRIDE.values():
        return s
    for variant in (
            re.sub(r'-(university|college|univ)$', '', s),   # "Rider University" -> rider
            re.sub(r'-(univ|university|college)-', '-', s),
            s.replace('-', ''),                              # "n-c-state" -> ncstate
            re.sub(r'^(the)-', '', s),
    ):
        cand = OVERRIDE.get(variant, variant)
        if cand in alias:
            return cand
        if variant in alias:
            return variant
    return s


out, unresolved = {}, []
for n, c in names.items():
    s = resolve(n)
    out[n] = s
    if s not in alias and s not in OVERRIDE.values():
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
