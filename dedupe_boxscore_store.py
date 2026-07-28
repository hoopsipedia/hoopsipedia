#!/usr/bin/env python3
"""Collapse duplicate box scores in sr_boxscores.json.

The store accumulated the same game under two key generations — a
short-name key from the early bulk scrape ("1996/princeton-vs-ucla") and a
full-name key from the later one ("1996/princeton-tigers-vs-ucla-bruins").
Both are real; neither was wrong; nothing deduped them.

Why it matters beyond the entry count:
  - players.json counts a player once PER STORED GAME, so anyone in a
    duplicated game had their games inflated and their per-game averages
    dragged toward that one game. These duplicates are concentrated in
    famous NCAA upsets (Princeton-UCLA 1996, Richmond-Syracuse 1991,
    Santa Clara-Arizona 1993), i.e. exactly the games a player page would
    showcase.
  - index.html matches a game to a box score by team-name overlap within a
    year, takes the FIRST hit and stops, so which copy a user sees is
    iteration order. The two copies differ: the full-name copy carries
    seeds and a source url, the short-name copy carries neither.

Grouping key: tournament year + the two canonicalized programs + the score
pair. Within a group the keeper is chosen by, in order: most player lines,
then most FULL player names, then has seeds, then has a source url, then a
dated key, then the lexicographically smallest key for determinism.

Full-name count ranks that high on purpose. The two copies of 1990
UCLA-UAB hold identical rosters, but one prints "Darrick Martin"/"Alan Ogg"
and the other prints "Martin"/"Ogg". players.json keys on the player name,
and surname-only lines collide different humans from different eras onto
one entry — so keeping the richer-named copy is worth more than keeping a
seed or a url.

Three guards, because a "duplicate" can be a real second meeting and the
two copies do not always carry the same roster:
  1. If two entries carry DIFFERENT explicit dates, they are different
     games — the group is left alone entirely.
  2. The keeper must have at least as many player lines as every entry it
     replaces.
  3. The keeper's roster must COVER the duplicate's, compared at surname
     level. The comparison has to be format-aware: the copies variously
     print "Mouring, Albert", "Albert Mouring" and "Mouring", and surnames
     may be multi-word or hyphenated ("El-Amin", "Van Dyke"), so a naive
     last-token split produces false differences — it reported 89 losses
     where a format-aware comparison finds 31.

Groups failing 2 or 3 are skipped and listed in the report for manual
merge. Never trade player data away for a tidier key.

Removed entries are written to boxscore_duplicates_removed.json with the
key that superseded them, so nothing is silently dropped.

Run: python3 dedupe_boxscore_store.py [--dry-run]
Then: scripts/split_boxscores.py, generate_players.py, scripts/split_players.py,
      scripts/generate_game_recaps.py, build_team_canon.py
"""

import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from json_io import save_json_atomic

ROOT = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(ROOT, 'sr_boxscores.json')
MODERN = os.path.join(ROOT, 'sr_boxscores_modern.json')
REPORT = os.path.join(ROOT, 'boxscore_duplicates_removed.json')
DATE_RE = re.compile(r'(\d{4}-\d{2}-\d{2})')


def main():
    dry = '--dry-run' in sys.argv
    store = json.load(open(STORE))
    canon = json.load(open(os.path.join(ROOT, 'team_name_canon.json')))

    def cslug(n):
        n = str(n or '')
        return canon.get(n, re.sub(r'[^a-z0-9]+', '-', n.lower()).strip('-'))

    def entry_date(key, e):
        m = DATE_RE.search(key) or DATE_RE.search(e.get('url', '') or '')
        return m.group(1) if m else None

    groups = defaultdict(list)
    for key, e in store.items():
        if key == '_metadata' or not isinstance(e, dict):
            continue
        teams = e.get('teams') or []
        if len(teams) != 2:
            continue
        scores = sorted(t['score'] for t in teams if isinstance(t.get('score'), int))
        if len(scores) != 2:
            continue
        gkey = (key[:4], tuple(sorted(cslug(t.get('name')) for t in teams)), tuple(scores))
        groups[gkey].append(key)

    def fullnames(key):
        return sum(1 for t in (store[key].get('teams') or [])
                   for p in (t.get('players') or [])
                   if ' ' in str(p.get('name', '')).strip())

    def rank(key):
        e = store[key]
        teams = e.get('teams') or []
        return (sum(len(t.get('players') or []) for t in teams),
                fullnames(key),
                sum(1 for t in teams if t.get('seed') is not None),
                1 if e.get('url') else 0,
                1 if DATE_RE.search(key) else 0,
                [-ord(c) for c in key])          # tie-break: smallest key wins

    def nplayers(key):
        return sum(len(t.get('players') or []) for t in (store[key].get('teams') or []))

    suffix = re.compile(r'(jr|sr|ii|iii|iv|v)$')

    def surname_keys(raw):
        """Surname candidates for one printed name, format-agnostic.

        Returns a SET because the same player is printed several ways across
        source generations: "El-Amin" vs "Amin", "Van Dyke" vs "Dyke",
        "Mouring, Albert" vs "Albert Mouring". Emitting every plausible
        surname token and testing for intersection avoids inventing
        differences that are really formatting."""
        n = str(raw or '').strip()
        if not n:
            return set()
        base = n.split(',')[0] if ',' in n else n
        words = [w for w in re.split(r'[^A-Za-z-]+', base) if w]
        words = [w for w in words if not suffix.fullmatch(w.lower())] or words
        out = set()
        if words:
            last = words[-1]
            out.add(re.sub(r'[^a-z]', '', last.lower()))
            for piece in last.split('-'):            # El-Amin -> el, amin
                if piece:
                    out.add(re.sub(r'[^a-z]', '', piece.lower()))
            if len(words) > 1:                       # Van Dyke -> vandyke
                out.add(re.sub(r'[^a-z]', '', (words[-2] + last).lower()))
        return {o for o in out if o}

    def roster_covers(keeper, other):
        """True when every player in `other` has a surname candidate the
        keeper's roster also offers."""
        kept = set()
        for t in store[keeper].get('teams') or []:
            for p in t.get('players') or []:
                kept |= surname_keys(p.get('name'))
        for t in store[other].get('teams') or []:
            for p in t.get('players') or []:
                cand = surname_keys(p.get('name'))
                if cand and not (cand & kept):
                    return False, str(p.get('name'))
        return True, None

    removed, skipped = {}, []
    for gkey, keys in groups.items():
        if len(keys) < 2:
            continue
        dates = {d for d in (entry_date(k, store[k]) for k in keys) if d}
        if len(dates) > 1:
            skipped.append({'group': list(gkey), 'keys': keys,
                            'reason': 'entries carry different dates ({}) — a real second meeting, not a duplicate'.format(sorted(dates))})
            continue
        keeper = max(keys, key=rank)
        losers = [k for k in keys if k != keeper]
        if any(nplayers(l) > nplayers(keeper) for l in losers):
            skipped.append({'group': list(gkey), 'keys': keys,
                            'reason': 'a candidate for removal has MORE player lines than the keeper — needs manual merge'})
            continue
        uncovered = [(l, who) for l, (ok, who) in
                     ((l, roster_covers(keeper, l)) for l in losers) if not ok]
        if uncovered:
            skipped.append({'group': list(gkey), 'keys': keys, 'keeper': keeper,
                            'reason': 'keeper roster does not cover {}: player {!r} appears only in the duplicate'.format(
                                uncovered[0][0], uncovered[0][1])})
            continue
        for l in losers:
            removed[l] = {'supersededBy': keeper,
                          'year': gkey[0], 'teams': list(gkey[1]), 'scores': list(gkey[2]),
                          'playerLines': nplayers(l), 'keeperPlayerLines': nplayers(keeper)}

    print('duplicate groups: {}'.format(sum(1 for v in groups.values() if len(v) > 1)))
    print('entries to remove: {}'.format(len(removed)))
    print('groups skipped for manual review: {}'.format(len(skipped)))
    for s in skipped[:10]:
        print('   {} {} — {}'.format(s['group'][0], s['group'][1], s['reason']))
    if not removed:
        print('Nothing to do.')
        return
    if dry:
        for k, v in list(removed.items())[:10]:
            print('   would remove {}\n           keeping {}'.format(k, v['supersededBy']))
        print('--dry-run: nothing written')
        return

    for k in removed:
        del store[k]
    if isinstance(store.get('_metadata'), dict) and 'totalGames' in store['_metadata']:
        store['_metadata']['totalGames'] = sum(1 for k in store if k != '_metadata')
    save_json_atomic(STORE, store)
    print('wrote sr_boxscores.json ({} entries)'.format(
        sum(1 for k in store if k != '_metadata')))

    modern = json.load(open(MODERN))
    n = sum(1 for k in list(modern) if k in removed and not modern.pop(k, None) is None)
    if n:
        save_json_atomic(MODERN, modern, indent=2)
        print('wrote sr_boxscores_modern.json (removed {})'.format(n))
    save_json_atomic(REPORT, {'removed': removed, 'skippedForReview': skipped}, indent=2)
    print('wrote {} ({} removed, {} skipped)'.format(
        os.path.basename(REPORT), len(removed), len(skipped)))


if __name__ == '__main__':
    main()
