#!/usr/bin/env python3
"""Generate per-game recap prose from the box-score store.

For every DATED game in sr_boxscores.json, compose a 1-2 sentence recap from
the box data (winner, margin flavor, top scorers on both sides, OT) for each
participating team we can resolve to an ESPN id. Output: recaps/{espnId}.json
mapping date -> recap string, which the SSR season pages render next to the
game log. Sentence structure is varied deterministically (hash of the game
key) so pages don't read as one repeated template.

Run after any box-score store merge: python3 scripts/generate_game_recaps.py
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def build_name_to_espn():
    """name-slug -> espnId, via data.json names plus games-log alias slugs."""
    data = json.load(open(os.path.join(ROOT, 'data.json')))
    by_slug = {}
    for eid, fields in data['H'].items():
        by_slug[slugify(fields[0])] = eid
    # short/canonical slugs from the game logs (opp id <-> opp_slug pairs)
    for fn in ('games_1.json', 'games_2.json', 'games_3.json'):
        d = json.load(open(os.path.join(ROOT, fn)))
        for v in d.values():
            games = v['games'] if isinstance(v, dict) else v
            for g in games:
                if g.get('opp') and g.get('opp_slug'):
                    by_slug.setdefault(g['opp_slug'], str(g['opp']))
    return by_slug


MARGIN_WORDS = [
    (1, 3, ['edged', 'held off', 'survived']),
    (4, 9, ['beat', 'defeated', 'got past']),
    (10, 19, ['handled', 'pulled away from', 'beat']),
    (20, 200, ['routed', 'rolled past', 'blew out']),
]


def margin_verb(margin, h):
    for lo, hi, words in MARGIN_WORDS:
        if lo <= margin <= hi:
            return words[h % len(words)]
    return 'beat'


def stat_int(v):
    """Stat value as int, or None.

    The archive stores counts as ints in most sources but as numeric
    STRINGS in the older regex-scraper schema. An isinstance(v, int) test
    silently skips those: 3,154 player lines across 168 games, which then
    got a recap with no scorer named in it."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        s = v.strip()
        if s.isdigit():
            return int(s)
    return None


def top_scorer(team):
    best = None
    for p in team.get('players', []):
        pts = stat_int(p.get('pts'))
        if pts is not None and (best is None or pts > best[1]):
            best = (p.get('name', ''), pts)
    return best


def line_extras(team):
    """Best secondary stat line among players (20+ pts noted separately)."""
    for p in team.get('players', []):
        reb = stat_int(p.get('reb'))
        if reb is not None and reb >= 15:
            return f"{p.get('name', '')} grabbed {reb} rebounds"
    return None


def compose(key, g, own, opp):
    date = g.get('date', '')
    h = sum(ord(c) for c in key)
    winner, loser = (own, opp) if own['score'] > opp['score'] else (opp, own)
    margin = winner['score'] - loser['score']
    verb = margin_verb(margin, h)
    ts_w = top_scorer(winner)
    ts_l = top_scorer(loser)

    s1_forms = [
        f"{winner['name']} {verb} {loser['name']} {winner['score']}–{loser['score']}",
        f"Behind {ts_w[0]}'s {ts_w[1]} points, {winner['name']} {verb} {loser['name']} {winner['score']}–{loser['score']}" if ts_w else None,
        f"{winner['name']} {verb} {loser['name']} {winner['score']}–{loser['score']}" + (f" as {ts_w[0]} scored a team-high {ts_w[1]}" if ts_w else ''),
    ]
    s1_forms = [s for s in s1_forms if s]
    s1 = s1_forms[h % len(s1_forms)]

    bits = [s1 + '.']
    used_ts_w = 'points,' in s1 or 'team-high' in s1
    if ts_w and not used_ts_w and ts_w[1] >= 10:
        bits.append(f" {ts_w[0]} led the winners with {ts_w[1]} points.")
    if ts_l and ts_l[1] >= 12:
        bits.append(f" {ts_l[0]} had {ts_l[1]} for {loser['name']}.")
    extra = line_extras(winner) or line_extras(loser)
    if extra:
        bits.append(f" {extra}.")
    # names ending in an abbreviation ("Murray St.") would double the period
    return ''.join(re.sub(r'\.\.$', '.', b) for b in bits)


def main():
    store = json.load(open(os.path.join(ROOT, 'sr_boxscores.json')))
    by_slug = build_name_to_espn()
    out = {}  # espnId -> {date: recap}
    made = skipped = 0
    for key, g in store.items():
        if key == '_metadata' or not isinstance(g, dict):
            continue
        date = g.get('date')
        teams = g.get('teams', [])
        if not date or len(teams) != 2:
            skipped += 1
            continue
        a, b = teams
        if not isinstance(a.get('score'), int) or not isinstance(b.get('score'), int):
            skipped += 1
            continue
        recap = compose(key, g, a, b)
        for t in teams:
            eid = by_slug.get(slugify(t.get('name', '')))
            if eid:
                out.setdefault(eid, {})[date] = recap
                made += 1

    os.makedirs(os.path.join(ROOT, 'recaps'), exist_ok=True)
    for eid, recaps in out.items():
        json.dump(recaps, open(os.path.join(ROOT, 'recaps', f'{eid}.json'), 'w'),
                  separators=(',', ':'))
    print(f'wrote {len(out)} team recap files, {made} team-game recaps ({skipped} dateless/short games skipped)')


if __name__ == '__main__':
    main()
