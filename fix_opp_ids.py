#!/usr/bin/env python3
"""Repair wrong 'opp' ESPN ids in games_1/2/3.json.

~21K game rows carry a wrong 'opp' ESPN id produced by historical
substring matching (slug 'houston' -> 2534 Sam Houston State instead of
248 Houston, 'indiana' -> 85 IUPUI instead of 84 Indiana, 'california'
-> 2934 CSU Bakersfield instead of 25 California, etc.).

Repair approach (mirrors the proven logic in generate_on_this_day.py):

1. Ground truth: espn_to_sr.json maps ESPN id -> Sports-Reference slug.
   Invert it with EXACT matching only (no substring matching — that is
   what caused the corruption). The map is verified bijective at load
   time; any collision aborts the run.
2. For each game row whose stored 'opp' disagrees with the slug-derived
   id, the correction is applied ONLY after mirror-row verification:
   the candidate opponent's own log must contain the reciprocal row —
   same date, scores swapped, win flag flipped, and (when the team's
   own slug is known) an opp_slug pointing back at this team.
3. Rows that cannot be verified (opponent not in our dataset, slug not
   in espn_to_sr, no mirror row) are left untouched and counted.

Only the value of the 'opp' field ever changes. Rows without an 'opp'
key are never modified (no keys are added). Both entry formats —
{"games": [...], "slug": ...} and the legacy bare array — are preserved
as-is. Files are re-serialized compactly (separators=(',', ':')) via
save_json_atomic.

Usage: python3 fix_opp_ids.py
"""

import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from json_io import save_json_atomic  # noqa: E402

GAMES_FILES = ['games_1.json', 'games_2.json', 'games_3.json']
ESPN_TO_SR = 'espn_to_sr.json'
DATA_JSON = 'data.json'

# Known-corrupt spot-check cases: (team id, opp_slug, expected new opp id).
# Team ids: Duke 150, Kentucky 96, Kansas 2305, UCLA 26, North Carolina 153.
SPOT_CHECKS = [
    ('150', 'houston', '248'),       # Duke vs Houston, not Sam Houston St (2534)
    ('96', 'houston', '248'),        # Kentucky vs Houston
    ('150', 'indiana', '84'),        # Duke vs Indiana, not IUPUI (85)
    ('96', 'indiana', '84'),         # Kentucky vs Indiana
    ('26', 'california', '25'),      # UCLA vs California, not CSU Bakersfield (2934)
    ('24', 'california', '25'),      # Stanford vs California
    ('150', 'maryland', '120'),      # Duke vs Maryland, not Loyola MD (2352)
    ('153', 'maryland', '120'),      # North Carolina vs Maryland
    ('26', 'arizona', '12'),         # UCLA vs Arizona, not Northern Arizona (2464)
    ('30', 'arizona', '12'),         # USC vs Arizona
]


def load_json(name):
    with open(os.path.join(ROOT, name)) as f:
        return json.load(f)


def rows_of(entry):
    return entry['games'] if isinstance(entry, dict) else entry


def build_slug_to_id():
    """Invert espn_to_sr.json. EXACT match only; abort on any collision."""
    espn_to_sr = load_json(ESPN_TO_SR)
    slug_to_id = {}
    for tid, slug in espn_to_sr.items():
        if slug in slug_to_id:
            print('FATAL: slug collision in espn_to_sr.json: {!r} -> {} and {}'
                  .format(slug, slug_to_id[slug], tid), file=sys.stderr)
            sys.exit(1)
        slug_to_id[slug] = tid
    return espn_to_sr, slug_to_id


def loc_compatible(a, b):
    """Mirror rows should have flipped H/A or both-N locations. Missing
    loc on either side is tolerated (older rows lack it)."""
    if not a or not b:
        return True
    if a == 'N' or b == 'N':
        return a == b or 'N' in (a, b)  # tolerate H-vs-N semi-home quirks
    return {a, b} == {'H', 'A'}


def main():
    espn_to_sr, slug_to_id = build_slug_to_id()
    data_h = set(load_json(DATA_JSON)['H'].keys())

    docs = {fname: load_json(fname) for fname in GAMES_FILES}

    # ── Index every team's rows (across all files) for mirror lookups ──
    # team slug: prefer espn_to_sr, fall back to the entry's own 'slug'.
    team_slug = {}
    per_team_by_date = defaultdict(lambda: defaultdict(list))  # tid -> date -> rows
    counts_before = {}  # (fname, tid) -> row count, for validation
    for fname, doc in docs.items():
        for tid, entry in doc.items():
            if tid in espn_to_sr:
                team_slug[tid] = espn_to_sr[tid]
            elif isinstance(entry, dict) and entry.get('slug'):
                team_slug.setdefault(tid, entry['slug'])
            rows = rows_of(entry)
            counts_before[(fname, tid)] = len(rows)
            for g in rows:
                per_team_by_date[tid][g['date']].append(g)

    def has_mirror(tid, g, cand):
        """True iff cand's own log contains the reciprocal of g."""
        my_slug = team_slug.get(tid)
        soft = []
        for m in per_team_by_date.get(cand, {}).get(g['date'], ()):
            if m['pts'] != g['opp_pts'] or m['opp_pts'] != g['pts']:
                continue
            if bool(m['w']) == bool(g['w']):
                continue
            if my_slug is not None and m.get('opp_slug') != my_slug:
                continue
            if not loc_compatible(g.get('loc'), m.get('loc')):
                soft.append(m)  # scores+slug match but loc odd: count, accept
                continue
            return True, False
        if soft:
            return True, True
        return False, False

    # ── Repair pass ──
    stats = Counter()
    changed_per_file = Counter()
    flagged_per_file = Counter()
    changed_ids_ok = 0
    changed_ids_missing_in_h = []
    spot_results = {sc: None for sc in SPOT_CHECKS}
    examples_flagged = Counter()  # slug -> count, for the report

    for fname, doc in docs.items():
        for tid, entry in doc.items():
            for g in rows_of(entry):
                stats['rows_total'] += 1
                slug = g.get('opp_slug')
                if 'opp' not in g:
                    stats['rows_no_opp_key'] += 1
                    continue
                cur = g['opp']
                if not cur:
                    stats['rows_empty_opp_value'] += 1
                    continue
                if not slug:
                    stats['rows_no_opp_slug'] += 1
                    continue
                cand = slug_to_id.get(slug)
                if cand is None:
                    stats['rows_slug_unmapped'] += 1
                    continue
                if cur == cand:
                    stats['rows_already_correct'] += 1
                    continue
                # Disagreement: verify via mirror row before correcting.
                ok, loc_soft = has_mirror(tid, g, cand)
                if ok:
                    g['opp'] = cand
                    stats['rows_corrected'] += 1
                    changed_per_file[fname] += 1
                    if loc_soft:
                        stats['rows_corrected_loc_mismatch'] += 1
                    if cand in data_h:
                        changed_ids_ok += 1
                    else:
                        changed_ids_missing_in_h.append((fname, tid, g['date'], cand))
                    key = (tid, slug, cand)
                    if key in spot_results and spot_results[key] is None:
                        spot_results[key] = (fname, g['date'], cur, cand)
                else:
                    stats['rows_flagged_unfixable_no_mirror'] += 1
                    flagged_per_file[fname] += 1
                    examples_flagged[slug] += 1

    # ── Write (atomic, compact, structure preserved) ──
    for fname, doc in docs.items():
        save_json_atomic(os.path.join(ROOT, fname), doc,
                         separators=(',', ':'), ensure_ascii=False)

    # ── Validation: reload and compare per-team row counts ──
    count_errors = []
    for fname in GAMES_FILES:
        reloaded = load_json(fname)
        for tid, entry in reloaded.items():
            if len(rows_of(entry)) != counts_before[(fname, tid)]:
                count_errors.append((fname, tid))
        for key in counts_before:
            if key[0] == fname and key[1] not in reloaded:
                count_errors.append(key)

    # ── Report ──
    print('=== fix_opp_ids.py results ===')
    for k in sorted(stats):
        print('  {}: {}'.format(k, stats[k]))
    print('changed per file:')
    for fname in GAMES_FILES:
        print('  {}: {} corrected, {} flagged-unfixable'.format(
            fname, changed_per_file[fname], flagged_per_file[fname]))
    print('new opp ids present in data.json H: {} / {}'.format(
        changed_ids_ok, stats['rows_corrected']))
    if changed_ids_missing_in_h:
        print('FLAG: corrected ids NOT in data.json H:')
        for item in changed_ids_missing_in_h[:20]:
            print('   ', item)
    print('top flagged-unfixable slugs:')
    for slug, n in examples_flagged.most_common(15):
        print('   {}: {}'.format(slug, n))
    print('spot checks (team, slug -> expected id):')
    spot_fail = 0
    for (tid, slug, exp), res in spot_results.items():
        if res:
            fname, date, old, new = res
            verdict = 'OK' if new == exp else 'MISMATCH'
            if verdict != 'OK':
                spot_fail += 1
            print('   [{}] {} vs {!r} {} ({}): {} -> {}'.format(
                verdict, tid, slug, date, fname, old, new))
        else:
            print('   [NO ROW CORRECTED] {} vs {!r} (already correct or absent)'
                  .format(tid, slug))
    if count_errors:
        print('FATAL: per-team game counts changed:', count_errors[:10],
              file=sys.stderr)
        sys.exit(1)
    print('per-team game counts: unchanged in all files')
    for fname in GAMES_FILES:
        size = os.path.getsize(os.path.join(ROOT, fname))
        flag = '' if size < 25 * 1024 * 1024 else '  EXCEEDS 25MB LIMIT'
        print('  {}: {:.1f} MB{}'.format(fname, size / 1024 / 1024, flag))
        if flag:
            sys.exit(1)
    if spot_fail:
        print('FATAL: {} spot checks mismatched'.format(spot_fail),
              file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
