#!/usr/bin/env python3
"""Fill MISSING 'opp' ESPN ids in games_1/2/3.json from the opponent slug.

fix_opp_ids.py repairs WRONG ids and never adds keys. But 81,991 rows
(14.5% of the logs, found 2026-10-09) had no 'opp' at all even though
61,750 of them carry an opp_slug that matches a Division I program
exactly — 'louisiana-state', 'pennsylvania', 'north-carolina-state' …
Those games were invisible to head-to-head records, rivalry pages and
the Compare page (UNC's log showed 0 games against NC State).

Same safety rules as fix_opp_ids.py: exact slug match via espn_to_sr.json
(verified bijective), and a fill is applied ONLY when the candidate's own
log holds the mirror row (same date, scores swapped, win flag flipped).
Rows that cannot be verified are left untouched and counted. Only the
'opp' key is ever added. Run split_games.py and compile_h2h_from_logs.py
afterwards.
"""
import json, os, sys
from collections import Counter, defaultdict
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
from json_io import save_json_atomic
from fix_opp_ids import build_slug_to_id, rows_of, loc_compatible, GAMES_FILES

def main():
    espn_to_sr, slug_to_id = build_slug_to_id()
    docs = {f: json.load(open(os.path.join(ROOT, f))) for f in GAMES_FILES}
    team_slug, by_date = {}, defaultdict(lambda: defaultdict(list))
    for doc in docs.values():
        for tid, entry in doc.items():
            team_slug[tid] = espn_to_sr.get(tid) or (entry.get('slug') if isinstance(entry, dict) else None)
            for g in rows_of(entry):
                by_date[tid][g['date']].append(g)
    filled, unverified, no_slug = Counter(), Counter(), 0
    for doc in docs.values():
        for tid, entry in doc.items():
            for g in rows_of(entry):
                if g.get('opp'):
                    continue
                slug = g.get('opp_slug')
                cand = slug_to_id.get(slug) if slug else None
                if not cand:
                    no_slug += 1
                    continue
                ok = False
                for m in by_date.get(cand, {}).get(g['date'], ()):
                    if m.get('pts') == g.get('opp_pts') and m.get('opp_pts') == g.get('pts') and bool(m.get('w')) != bool(g.get('w')) \
                       and (team_slug.get(tid) is None or m.get('opp_slug') in (None, team_slug.get(tid))):
                        ok = True; break
                if ok:
                    g['opp'] = cand; filled[slug] += 1
                else:
                    unverified[slug] += 1
    for f, doc in docs.items():
        save_json_atomic(os.path.join(ROOT, f), doc, separators=(',', ':'))
    print(f'filled {sum(filled.values()):,} rows across {len(filled)} opponents; '
          f'unverified (no mirror row) {sum(unverified.values()):,}; no D1 slug {no_slug:,}')
    print('top filled:', filled.most_common(8))
    print('top unverified:', unverified.most_common(6))

if __name__ == '__main__':
    main()
