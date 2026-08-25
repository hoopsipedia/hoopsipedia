#!/usr/bin/env python3
"""Build boxscore_match_index.json — team-name -> ESPN id, for box-score matching.

index.html pairs a game with its box score by comparing team NAMES. It did
this with last-word overlap, which cannot tell programs apart: measured over
the store, 51.9% of entries matched more than one game in their own year and
5,776 of those collisions were with a different pair of programs entirely
(`arkansas-vs-iowa` against `arkansas-vs-iowa-st`; anything where both teams
end in "State"). Which box score a user saw was iteration order.

This ships the identity the comparison actually needs: one map from every
team-name string that appears in the store — and every name the site itself
uses — to an ESPN id. The frontend resolves both sides to ids and compares
ids, falling back to the old fuzzy test only when a name does not resolve,
so coverage gaps degrade to today's behaviour rather than to a wrong answer.

Sources, in precedence order:
  1. data.json H — full name, the school part (name minus its nickname), and
     the Sports-Reference slug from espn_to_sr.json.
  2. team_name_canon.json — every store name -> canonical slug -> ESPN id.
  3. SLUG_ALIASES below, for programs whose archive spelling matches no
     data.json or SR form.

DELIBERATELY UNRESOLVED: genuinely ambiguous bare names ("Louisiana",
"Miami", "Loyola", "Southern"). A name that could mean two programs must
stay unresolved — the fallback is a fuzzy match, but a wrong id is a
confidently wrong box score.

Conflicts (one name, two ids) are reported and dropped, never guessed.

Run: python3 scripts/build_boxscore_match_index.py
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from json_io import save_json_atomic

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'boxscore_match_index.json')

# Archive slug -> Sports-Reference slug, where the two disagree. Same gap
# build_team_canon.py's ABBREV closes for the name canon.
SLUG_ALIASES = {
    'vmi': 'virginia-military-institute', 'etsu': 'east-tennessee-state',
    'the-citadel': 'citadel', 'bowling-green': 'bowling-green-state',
    'southern-miss': 'southern-mississippi', 'uc-irvine': 'california-irvine',
    'uc-davis': 'california-davis', 'uc-riverside': 'california-riverside',
    'uc-san-diego': 'california-san-diego',
    'uc-santa-barbara': 'california-santa-barbara',
    'unc-asheville': 'north-carolina-asheville',
    'unc-greensboro': 'north-carolina-greensboro',
    'unc-wilmington': 'north-carolina-wilmington',
    'siu-edwardsville': 'southern-illinois-edwardsville',
    'umass-lowell': 'massachusetts-lowell', 'umass': 'massachusetts',
    'kansas-city': 'missouri-kansas-city', 'umkc': 'missouri-kansas-city',
    'umbc': 'maryland-baltimore-county', 'utsa': 'texas-san-antonio',
    'utep': 'texas-el-paso', 'uab': 'alabama-birmingham',
    'uic': 'illinois-chicago', 'ucf': 'central-florida',
    'unlv': 'nevada-las-vegas', 'smu': 'southern-methodist',
    'tcu': 'texas-christian', 'byu': 'brigham-young', 'lsu': 'louisiana-state',
    'uconn': 'connecticut', 'pitt': 'pittsburgh', 'usc': 'southern-california',
    'vcu': 'virginia-commonwealth', 'ole-miss': 'mississippi',
    'nc-state': 'north-carolina-state', 'penn': 'pennsylvania',
    'ualr': 'arkansas-little-rock', 'ulm': 'louisiana-monroe',
    'fiu': 'florida-international', 'fau': 'florida-atlantic',
    'wku': 'western-kentucky', 'uni': 'northern-iowa',
    'nicholls': 'nicholls-state', 'lmu': 'loyola-marymount',
}

# Names that must never resolve: each could mean two or more programs.
AMBIGUOUS = {
    'louisiana', 'miami', 'loyola', 'southern', 'columbia', 'trinity',
    'st-francis', 'saint-francis', 'st-marys', 'saint-marys', 'st-thomas',
    'sw-missouri-state',
    'saint-thomas', 'usf', 'asu', 'sfa', 'nu', 'bu', 'cu', 'usa',
}


def norm(s):
    """Canonical lookup key. Must stay byte-identical to the JS `bxNorm`
    in index.html or the shipped map cannot be read.

    '&' is DELETED rather than treated as punctuation so that the archive's
    "Florida A&M" and Sports-Reference's "florida-am" land on the same key;
    collapsing it to a separator would give 'florida-a-m' and they would
    never meet."""
    s = str(s or '').lower().replace("'", '').replace('’', '').replace('&', '')
    return re.sub(r'-{2,}', '-', re.sub(r'[^a-z0-9]+', '-', s)).strip('-')


def main():
    h = json.load(open(os.path.join(ROOT, 'data.json')))['H']
    e2s = json.load(open(os.path.join(ROOT, 'espn_to_sr.json')))
    canon = json.load(open(os.path.join(ROOT, 'team_name_canon.json')))
    slug2id = {s: e for e, s in e2s.items()}
    for alias, real in SLUG_ALIASES.items():
        if real in slug2id:
            slug2id.setdefault(alias, slug2id[real])

    names, conflicts = {}, []

    def add(raw, eid, tier):
        k = norm(raw)
        if not k or k in AMBIGUOUS:
            return
        prev = names.get(k)
        if prev and prev[0] != eid:
            if prev[1] <= tier:          # keep the higher-precedence source
                conflicts.append((k, prev[0], eid))
                return
            conflicts.append((k, eid, prev[0]))
        names[k] = (eid, tier)

    for eid, v in h.items():
        add(v[0], eid, 1)
        nick = v[1] if len(v) > 1 else ''
        if nick and v[0].endswith(nick):
            add(v[0][:-len(nick)].strip(), eid, 1)
        if eid in e2s:
            add(e2s[eid], eid, 1)
    for name, slug in canon.items():
        eid = slug2id.get(slug)
        if eid:
            add(name, eid, 2)

    # The archive abbreviates "Iowa State" as "Iowa St" (and "Ohio St",
    # "Michigan St", ...). Emit the abbreviated key too, so those resolve
    # instead of silently falling back to the fuzzy matcher — "Iowa" vs
    # "Iowa St" is exactly the collision this index exists to prevent.
    # Only a trailing "-state" is abbreviated; a LEADING "st-" is Saint
    # ("st-johns") and is left alone.
    for k, v in list(names.items()):
        if k.endswith('-state'):
            names.setdefault(k[:-len('-state')] + '-st', v)

    out = {k: v[0] for k, v in sorted(names.items())}
    save_json_atomic(OUT, {'_metadata': {
        'purpose': 'team name -> ESPN id, for exact box-score matching in index.html',
        'names': len(out)}, 'names': out},
        separators=(',', ':'), ensure_ascii=False, sort_keys=True)

    store = json.load(open(os.path.join(ROOT, 'sr_boxscores.json')))
    both = tot = 0
    for k, e in store.items():
        if k == '_metadata' or not isinstance(e, dict):
            continue
        t = e.get('teams') or []
        if len(t) != 2:
            continue
        tot += 1
        if all(out.get(norm(x.get('name'))) for x in t):
            both += 1
    print('wrote boxscore_match_index.json: {} names, {:.0f}KB'.format(
        len(out), os.path.getsize(OUT) / 1024))
    print('store entries with BOTH sides resolvable: {} of {} ({:.1f}%)'.format(
        both, tot, 100.0 * both / tot))
    print('data.json H names resolvable: {} of {}'.format(
        sum(1 for v in h.values() if norm(v[0]) in out), len(h)))
    if conflicts:
        print('dropped {} conflicting names (kept higher-precedence source), e.g. {}'.format(
            len(conflicts), conflicts[:3]))


if __name__ == '__main__':
    main()
