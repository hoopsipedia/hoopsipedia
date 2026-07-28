#!/usr/bin/env python3
"""Correct the 2026-07-28 audit's residual contradicted box scores.

After the VMI identity repair and audit matcher hardening, 16 store entries
stayed CONTRADICTED. Each was adjudicated individually using two independent
signals: the harvesting team's game log (date + both scores) and the
opponent's ROSTER as printed in the box score itself.

FIXES — the box score is real but carries the wrong opponent label (and in
the two sports-reference cases, scores stitched in from an adjacent game):

  louisville 1980-01-22  "Maryland"     -> Marquette   (roster: Sam Worthen,
                         Oliver Lee = 1979-80 Marquette; log: 76-63 vs
                         marquette that exact day, Maryland played NC State)
  virginia  1980-11-29  "UCLA"          -> VCU         (roster: Edmund Sherod,
                         Monty Knight; log: 77-62 vs virginia-commonwealth)
  ohio st   1977-12-29  "Southern Illinois" -> La Salle (roster: Michael
                         Brooks, Kurt Kanaskie; log: 86-83 vs la-salle)
  virginia  1995-03-18  "Miami (FL)"    -> Miami (OH)  (roster: Devin Davis,
                         Jamie Mahaffey; log: 60-54 vs miami-oh, 1995 NCAA
                         round of 32)
  alabama   2017-12-03  "Virginia Tech 83-86" -> UCF 65-62 (roster: Tacko
                         Fall, A.J. Davis = UCF; player sums 65/62 match the
                         log exactly; the SR url already points at the UCF
                         game — names/scores were joined from Alabama's 2018
                         NCAA win over VT)
  fsu       2011-03-18  "Notre Dame 57-71" -> Texas A&M 50-57 (roster: Khris
                         Middleton, B.J. Holmes, David Loubeau = Texas A&M;
                         sums 50/57 match the log; names/scores joined from
                         FSU's round-of-32 win over ND two days later)
  georgetown 1997-12-29 "Southern"      -> Southern-New Orleans (name
                         truncation; log row matches 85-48; non-D1 opponent,
                         so this entry becomes UNCHECKABLE — accepted)

Every fix is gated: the corrected entry must re-audit as VERIFIED against
the game logs (except Georgetown, gated on its one-sided log row match)
before anything is written.

QUARANTINE — corrupt or unresolvable entries, moved (never deleted) to
sr_boxscores_quarantine.json with reasons, pending a source re-fetch:

  4x "Central Arkansas vs Central Arkansas" self-pairs + 2 UCA entries whose
  claimed opponents' logs contradict (UCA's own log starts 2006-11-14, so
  the games predate coverage), the South Dakota and UC Davis self-pairs
  (same parser bug, logs don't cover the dates), and 1957 San Francisco vs
  Idaho State, whose "Idaho State" side is a byte-copy of USF's own roster.

LEFT IN PLACE: 1957/byu-vs-idaho-state — internally consistent (distinct
rosters, sums match claimed scores); contradicted only by a suspected gap
in BYU's 1956-57 log. Reported, not touched.

Mirrors every change into sr_boxscores_modern.json where the key exists
(legacy 179-entry transition file, still deployed).

Idempotent: re-running after the fix makes 0 changes.
Run:  python3 apply_boxscore_team_fixes.py [--dry-run]
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from json_io import save_json_atomic
import audit_boxscore_integrity as A

ROOT = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(ROOT, 'sr_boxscores.json')
MODERN = os.path.join(ROOT, 'sr_boxscores_modern.json')
QUARANTINE_PATH = os.path.join(ROOT, 'sr_boxscores_quarantine.json')
ADJUDICATED = '2026-07-28'

# (old_key, new_key, old_team_name, new_team_name, score_fixes)
# score_fixes: {team_name_after_fix: corrected_score} or None
FIXES = [
    ('1980/louisville-cardinals-vs-maryland-1980-01-22',
     '1980/louisville-cardinals-vs-marquette-golden-eagles-1980-01-22',
     'Maryland Terrapins', 'Marquette Golden Eagles', None),
    ('1981/virginia-cavaliers-vs-ucla-1980-11-29',
     '1981/virginia-cavaliers-vs-vcu-rams-1980-11-29',
     'UCLA', 'VCU Rams', None),
    ('1978/ohio-state-buckeyes-vs-southern-illinois-salukis-1977-12-29',
     '1978/ohio-state-buckeyes-vs-la-salle-explorers-1977-12-29',
     'Southern Illinois Salukis', 'La Salle Explorers', None),
    ('1995/virginia-cavaliers-vs-miami-fl-hurricanes-1995-03-18',
     '1995/virginia-cavaliers-vs-miami-oh-redhawks-1995-03-18',
     'Miami (FL) Hurricanes', 'Miami (OH) RedHawks', None),
    ('2018/alabama-crimson-tide-vs-virginia-tech-hokies',
     '2018/alabama-crimson-tide-vs-ucf-knights',
     'Virginia Tech Hokies', 'UCF Knights',
     {'UCF Knights': 65, 'Alabama Crimson Tide': 62}),
    ('2011/florida-state-seminoles-vs-notre-dame-fighting-irish',
     '2011/florida-state-seminoles-vs-texas-am-aggies',
     'Notre Dame Fighting Irish', 'Texas A&M Aggies',
     {'Texas A&M Aggies': 50, 'Florida State Seminoles': 57}),
    ('1998/georgetown-hoyas-vs-southern-new-orlean-1997-12-29',
     None,   # key already names the right opponent
     'Southern', 'Southern-New Orleans', None),
]

QUARANTINE = {
    '2001/south-dakota-coyotes-vs-south-dakota-2001-01-26':
        'self-pair (opponent parsed as own team); South Dakota log does not cover 2001',
    '2003/uc-davis-aggies-vs-uc-davis-2003-02-28':
        'self-pair; UC Davis log does not cover 2003',
    '2005/central-arkansas-bears-vs-central-arkansas-2004-12-30':
        'self-pair; UCA log starts 2006-11-14',
    '2006/central-arkansas-bears-vs-central-arkansas-2005-11-29':
        'self-pair; UCA log starts 2006-11-14',
    '2007/central-arkansas-bears-vs-central-arkansas-2006-11-11':
        'self-pair; game precedes UCA log start 2006-11-14',
    '2006/central-arkansas-bears-vs-texas-state-2006-01-06':
        "Texas State's season-complete log has no UCA game in 2005-06; UCA log starts 2006-11-14 — opponent or date unverifiable",
    '2006/central-arkansas-bears-vs-evansville-2005-12-21':
        "Evansville played Austin Peay on 2005-12-21; UCA log starts 2006-11-14 — opponent or date unverifiable",
    '1957/san-francisco-vs-idaho-state':
        "the 'Idaho State' side is a byte-copy of San Francisco's own roster (Gene Brown, Art Day, ...)",
}


def verify_entry(ctx, key, entry):
    """Re-audit a single (possibly fixed) entry; returns (verdict, detail)."""
    per_team, slug_map, resolve, global_max = ctx
    teams = entry['teams']
    year = int(key.split('/')[0])
    sides = []
    for t in teams:
        sides.append({'tid': resolve(t['name']), 'slug': A.slugify(t['name']),
                      'name': t['name'], 'score': t['score']})
    a, b = sides
    m = A.URL_DATE_RE.search(entry.get('url', ''))
    if m:
        return A.check_dated(per_team, slug_map, a, b, m.group(1), global_max)
    lo, hi = A.season_window(year)
    v, d, _ = A.check_undated(per_team, slug_map, a, b, lo, hi, global_max)
    return v, d


def main():
    dry = '--dry-run' in sys.argv
    per_team, slug_of = A.load_logs()
    slug_map = A.build_slug_map(per_team, slug_of)
    resolve = A.build_name_map(slug_map)
    A.extend_slug_map(slug_map, per_team, resolve)
    global_max = max(g['date'] for rows in per_team.values() for g in rows)
    ctx = (per_team, slug_map, resolve, global_max)

    store = json.load(open(STORE))
    modern = json.load(open(MODERN))
    quarantine = json.load(open(QUARANTINE_PATH)) if os.path.exists(QUARANTINE_PATH) else {}
    changed = {'store': False, 'modern': False, 'quarantine': False}

    for old_key, new_key, old_name, new_name, score_fixes in FIXES:
        target = new_key or old_key
        if old_key not in store:
            state = 'already applied' if target in store else 'MISSING'
            print('skip {} ({})'.format(old_key, state))
            continue
        entry = store[old_key]
        hit = [t for t in entry['teams'] if t['name'] == old_name]
        if not hit and any(t['name'] == new_name for t in entry['teams']):
            print('skip {} (already applied in place)'.format(old_key))
            continue
        assert len(hit) == 1, '{}: team {!r} not found'.format(old_key, old_name)
        hit[0]['name'] = new_name
        if score_fixes:
            for t in entry['teams']:
                t['score'] = score_fixes[t['name']]
        verdict, detail = verify_entry(ctx, target, entry)
        ok = verdict == 'VERIFIED' or (old_key.startswith('1998/georgetown')
                                       and verdict == 'UNCHECKABLE')
        if old_key.startswith('1998/georgetown') and verdict != 'VERIFIED':
            # gate on the one-sided log row instead: Georgetown 85-48 vs a
            # row whose slugified opp_slug is southern-new-orleans
            gtown = resolve('Georgetown Hoyas')
            ok = any(g['date'] == '1997-12-29' and g['pts'] == 85 and g['opp_pts'] == 48
                     and A.slugify(g['opp_slug']) == 'southern-new-orleans'
                     for g in per_team.get(gtown, []))
            detail += ' | gate: one-sided Georgetown log row match = {}'.format(ok)
        assert ok, 'fix for {} did not verify: {} {}'.format(old_key, verdict, detail)
        del store[old_key]
        store[target] = entry
        changed['store'] = True
        if old_key in modern:
            modern[target] = entry
            del modern[old_key]
            changed['modern'] = True
        print('FIX {} -> {}\n    {} -> {}{}  [{}]'.format(
            old_key, target, old_name, new_name,
            ' + scores {}'.format(score_fixes) if score_fixes else '', verdict))

    n_q = 0
    for key, reason in QUARANTINE.items():
        if key not in store:
            print('skip quarantine {} (already moved)'.format(key))
            continue
        quarantine[key] = {'entry': store.pop(key), 'reason': reason,
                           'adjudicated': ADJUDICATED}
        changed['store'] = changed['quarantine'] = True
        if key in modern:
            del modern[key]
            changed['modern'] = True
        n_q += 1
        print('QUARANTINE {}\n    {}'.format(key, reason))

    if n_q and isinstance(store.get('_metadata'), dict) and 'totalGames' in store['_metadata']:
        store['_metadata']['totalGames'] -= n_q
        print('store _metadata.totalGames -> {}'.format(store['_metadata']['totalGames']))

    if not any(changed.values()):
        print('Nothing to do.')
        return
    if dry:
        print('--dry-run: would write ' + ', '.join(k for k, v in changed.items() if v))
        return
    if changed['store']:
        # compact, single-line — the 56MB store must stay under GitHub's
        # 100MB hard limit (indent=2 balloons it to 129MB)
        save_json_atomic(STORE, store)
        print('wrote sr_boxscores.json ({} entries)'.format(
            sum(1 for k in store if k != '_metadata')))
    if changed['modern']:
        save_json_atomic(MODERN, modern, indent=2)
        print('wrote sr_boxscores_modern.json')
    if changed['quarantine']:
        save_json_atomic(QUARANTINE_PATH, quarantine, indent=2)
        print('wrote sr_boxscores_quarantine.json ({} entries)'.format(len(quarantine)))


if __name__ == '__main__':
    main()
