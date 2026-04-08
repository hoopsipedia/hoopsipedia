#!/usr/bin/env python3
"""
Compile enhanced coaching data from seasons.json into data.json.

For each coach at each team:
- Overall record (W-L) at that school
- Win percentage
- Best season (year + record)

Also generates:
- COACH_LB: Top 100 all-time career wins leaderboard
- COACH_RANK: Lookup map for top 100 coaches by name -> rank
"""

import json
import sys
from collections import defaultdict

def parse_year(year_str):
    """Extract end year from season string like '2025-26' -> 2026"""
    if '-' in year_str:
        parts = year_str.split('-')
        return int(parts[0]) + 1
    return int(year_str)

# Name disambiguation for coaches where Sports Reference uses the same name
# for different people. Format: base_name -> [(year_cutoff, disambiguated_name)]
# If season year >= cutoff, use the disambiguated name; otherwise use the fallback.
NAME_DISAMBIGUATION = {
    'John Thompson': {
        # John Thompson Jr. coached Georgetown 1972-1999
        # John Thompson III coached Princeton 2000-2004, Georgetown 2004-2017
        'cutoff': 2000,
        'before': 'John Thompson Jr.',
        'after': 'John Thompson III',
    },
}

def disambiguate_coach_name(name, season_year):
    """Resolve name collisions for coaches with same name but different people."""
    if name in NAME_DISAMBIGUATION:
        rule = NAME_DISAMBIGUATION[name]
        try:
            yr = parse_year(season_year) if isinstance(season_year, str) else season_year
            if yr >= rule['cutoff']:
                return rule['after']
            else:
                return rule['before']
        except:
            return name
    return name

def compile_coaches():
    # Load data
    with open('seasons.json') as f:
        seasons_data = json.load(f)

    with open('data.json') as f:
        data = json.load(f)

    # Get team name lookup from data.json
    F = data.get('F', {})
    H = data.get('H', {})
    team_names = {}
    name_idx = F.get('NAME', 0)
    for espn_id, team_arr in H.items():
        if isinstance(team_arr, list) and len(team_arr) > name_idx:
            team_names[espn_id] = team_arr[name_idx]

    # Deduplicate seasons.json — some schools have multiple ESPN IDs with identical data
    # Keep the ID that's in H (data.json), otherwise keep the first one
    from collections import defaultdict as dd2
    fingerprints = dd2(list)
    for eid, td in seasons_data.items():
        seasons = td.get('seasons', [])
        if not seasons:
            continue
        fp = (len(seasons), seasons[0].get('year',''), seasons[0].get('coach',''), seasons[-1].get('year',''))
        fingerprints[fp].append(eid)

    # Known bad mappings: ESPN IDs in seasons.json that have WRONG school data
    # ESPN 245 is mapped to "Texas A&M" in H but seasons.json has Texas Longhorns data
    # ESPN 357 is an unmapped duplicate of Texas Longhorns data
    bad_ids = {'245', '357'}

    # Build set of IDs to skip (duplicates)
    skip_ids = set(bad_ids)  # Always skip known bad IDs
    for fp, ids in fingerprints.items():
        if len(ids) > 1:
            # Remove bad IDs from candidates
            candidates = [eid for eid in ids if eid not in bad_ids]
            if not candidates:
                candidates = ids  # Fallback if all are bad
            # Prefer the ID that's in H
            primary = next((eid for eid in candidates if eid in H), candidates[0])
            for eid in ids:
                if eid != primary:
                    skip_ids.add(eid)

    print(f"Deduplicating: skipping {len(skip_ids)} duplicate ESPN IDs")

    enhanced_coaches = {}
    # Global coach career tracking: coach_name -> {wins, losses, schools: [(espn_id, start, end, w, l)]}
    global_coaches = defaultdict(lambda: {'wins': 0, 'losses': 0, 'schools': [], 'best_yr': '', 'best_rec': '', 'best_wins': 0})

    for espn_id, team_data in seasons_data.items():
        seasons = team_data.get('seasons', [])
        if not seasons:
            continue

        # Group seasons by coach (with name disambiguation)
        coach_seasons = defaultdict(list)
        for season in seasons:
            coach = season.get('coach', '')
            if not coach or ',' in coach:  # Skip multi-coach seasons
                continue
            coach = disambiguate_coach_name(coach, season.get('year', ''))
            season = dict(season)  # Copy to avoid mutating original
            season['coach'] = coach
            coach_seasons[coach].append(season)

        # Build ordered coach list (newest first, matching current COACHES order)
        # First, determine order from season years
        coach_order = []
        seen_coaches = set()
        for season in seasons:  # Already newest-first from seasons.json
            coach = season.get('coach', '')
            if not coach or ',' in coach:
                continue
            coach = disambiguate_coach_name(coach, season.get('year', ''))
            if coach not in seen_coaches:
                coach_order.append(coach)
                seen_coaches.add(coach)

        team_coaches = []
        for coach_name in coach_order:
            c_seasons = coach_seasons[coach_name]

            total_w = sum(s.get('wins', 0) for s in c_seasons)
            total_l = sum(s.get('losses', 0) for s in c_seasons)
            total_games = total_w + total_l
            win_pct = round(total_w / total_games * 100, 1) if total_games > 0 else 0

            # Find best season by wins
            best = max(c_seasons, key=lambda s: s.get('wins', 0))
            best_yr = best.get('year', '')
            best_w = best.get('wins', 0)
            best_l = best.get('losses', 0)
            best_rec = f"{best_w}-{best_l}"

            # Determine start/end years
            years = []
            for s in c_seasons:
                try:
                    years.append(parse_year(s.get('year', '')))
                except:
                    pass

            start = min(years) if years else 0
            end = max(years) if years else 0

            coach_entry = {
                'name': coach_name,
                'start': start,
                'end': end,
                'w': total_w,
                'l': total_l,
                'pct': win_pct,
                'bestYr': best_yr,
                'bestRec': best_rec
            }
            team_coaches.append(coach_entry)

            # Track global career stats (skip duplicate IDs)
            if espn_id not in skip_ids:
                gc = global_coaches[coach_name]
                gc['wins'] += total_w
                gc['losses'] += total_l
                gc['schools'].append((espn_id, start, end, total_w, total_l))
                if best_w > gc['best_wins']:
                    gc['best_wins'] = best_w
                    gc['best_yr'] = best_yr
                    gc['best_rec'] = best_rec

        enhanced_coaches[espn_id] = team_coaches

    # Build top 100 leaderboard
    all_coaches_list = []
    for name, stats in global_coaches.items():
        total_games = stats['wins'] + stats['losses']
        if total_games == 0:
            continue
        pct = round(stats['wins'] / total_games * 100, 1)
        # Sort schools by start year
        schools_sorted = sorted(stats['schools'], key=lambda s: s[1])
        years_start = min(s[1] for s in stats['schools'])
        years_end = max(s[2] for s in stats['schools'])

        all_coaches_list.append({
            'name': name,
            'wins': stats['wins'],
            'losses': stats['losses'],
            'pct': pct,
            'schools': [[s[0], s[1], s[2]] for s in schools_sorted],  # [espn_id, start, end]
            'yearsStart': years_start,
            'yearsEnd': years_end,
            'bestYr': stats['best_yr'],
            'bestRec': stats['best_rec']
        })

    # Sort by wins descending
    all_coaches_list.sort(key=lambda c: c['wins'], reverse=True)

    # Full leaderboard: all coaches with 200+ wins (for AI chat queryability)
    full_leaderboard = [c for c in all_coaches_list if c['wins'] >= 200]
    # Top 100 subset (for display on the coaches page)
    top_100 = all_coaches_list[:100]

    # Build rank lookup (top 100 only, for display)
    coach_rank = {}
    for i, coach in enumerate(top_100):
        coach_rank[coach['name']] = i + 1

    # Update data.json
    data['COACHES'] = enhanced_coaches
    data['COACH_LB'] = full_leaderboard
    data['COACH_LB_TOP100'] = top_100
    data['COACH_RANK'] = coach_rank

    with open('data.json', 'w') as f:
        json.dump(data, f)

    # Print summary
    print(f"Enhanced coaching data for {len(enhanced_coaches)} teams")
    print(f"Total unique coaches: {len(global_coaches)}")
    print(f"\nTop 10 All-Time Wins:")
    for i, coach in enumerate(top_100[:10]):
        schools = ', '.join(team_names.get(s[0], f'ESPN:{s[0]}') for s in coach['schools'])
        print(f"  #{i+1} {coach['name']}: {coach['wins']}-{coach['losses']} ({coach['pct']}%) — {schools}")

if __name__ == '__main__':
    compile_coaches()
