#!/usr/bin/env python3
"""Draft the day's social posts from the database — every line a fact with a
forever URL behind it. Phase 2 marketing plumbing: until accounts and
automation exist, Josh reads content/drafts/<date>.md and posts by hand.

Four drafts per day, all deterministic for the date (re-running gives the
same text) so a scheduled job can produce them unattended:

  1. On This Day        — the two most significant games played on this date
                          (on_this_day.json), linked to their season pages
  2. Time Machine       — one featured cross-era matchup with the model's
                          prediction, linked to its forever URL
  3. Greatest Season    — one of the HTSS top-100 team-seasons, linked
  4. Record Book        — one all-time leaderboard, top 5, linked to /rankings

  python3 scripts/daily_content.py               # today
  python3 scripts/daily_content.py 2026-11-03    # a given date
  python3 scripts/daily_content.py --print       # also echo to stdout

Output: content/drafts/YYYY-MM-DD.md (gitignored) + content/drafts/latest.md
"""
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGIN = 'https://www.hoopsipedia.com'
OUT_DIR = os.path.join(ROOT, 'content', 'drafts')


def load(name):
    with open(os.path.join(ROOT, name), encoding='utf-8') as f:
        return json.load(f)


def slug(name):
    return re.sub(r'(^-|-$)', '', re.sub(r'[^a-z0-9]+', '-', name.lower()))


def season_key_for(date_str):
    y, m = int(date_str[:4]), int(date_str[5:7])
    start = y if m >= 8 else y - 1
    return f'{start}-{str(start + 1)[2:]}'


def end_year(season):
    return int(season[:4]) + 1


def nick(name):
    parts = name.split(' ')
    return ' '.join(parts[1:]) if len(parts) > 1 else name


def x_len(text):
    # X counts every URL as 23 characters
    return len(re.sub(r'https?://\S+', 'x' * 23, text))


def draft_on_this_day(date, otd):
    key = date.strftime('%m-%d')
    items = sorted(otd.get(key, []), key=lambda x: -x.get('sig', 0))[:2]
    out = []
    for it in items:
        teams = it.get('teams', [])
        if len(teams) < 2:
            continue
        winner, loser = teams[0], teams[1]
        yr = it['date'][:4]
        season = season_key_for(it['date'])
        link = f"{ORIGIN}/teams/{slug(winner['name'])}/{season}"
        headline = it.get('headline', '').split(': ', 1)[-1]
        out.append(f"On this day in {yr}: {headline}.\n\nFull season, game by game: {link}\nMore from {date.strftime('%B %-d')}: {ORIGIN}/on-this-day/{key}")
    return out


def draft_time_machine(date, tm):
    matchups = tm.get('matchups', [])
    if not matchups:
        return []
    m = matchups[date.timetuple().tm_yday % len(matchups)]
    a, b, p = m['teamA'], m['teamB'], m['prediction']
    link = f"{ORIGIN}/time-machine/{slug(a['name'])}/{a['season']}/{slug(b['name'])}/{b['season']}"
    text = (f"Time Machine: {end_year(a['season'])} {a['name']} ({a['record']}) vs {end_year(b['season'])} {b['name']} ({b['record']}).\n\n"
            f"Our model: {p['winner']} {p['winnerScore']}-{p['loserScore']} "
            f"({max(p['winProbA'], p['winProbB']):.0f}% win probability). Argue with it: {link}")
    return [text]


def draft_greatest_season(date, htss):
    top = htss.get('allTimeTop100', [])
    if not top:
        return []
    s = top[(date.timetuple().tm_yday * 7) % len(top)]
    link = f"{ORIGIN}/teams/{slug(s['team'])}/{s['season']}"
    result = s.get('tourneyResult') or ''
    result_txt = {
        'champion': 'won the national title', 'runner_up': 'lost the national final',
        'final_four': 'reached the Final Four', 'elite_eight': 'reached the Elite Eight',
        'sweet_sixteen': 'reached the Sweet Sixteen', 'round_of_32': 'reached the second round',
        'round_of_64': 'lost in the first round', 'none': 'missed the NCAA Tournament',
    }.get(result, result.replace('_', ' ') if result else 'played before the modern bracket')
    text = (f"The {end_year(s['season'])} {s['team']} went {s['record']} under {s['coach']} and {result_txt}. "
            f"HTSS ranks it the #{s['rank']} team-season since 1949 (score {s['htss']}).\n\n{link}")
    return [text]


def draft_record_book(date, H):
    cats = [
        (4, 'all-time wins', lambda t: f"{t[4]:,}"),
        (6, 'national championships', lambda t: str(t[6])),
        (8, 'Final Fours', lambda t: str(t[8])),
    ]
    idx, label, fmt = cats[date.timetuple().tm_yday % len(cats)]
    teams = sorted(H.values(), key=lambda t: -(t[idx] or 0))[:5]
    lines = [f"{i + 1}. {t[0]} — {fmt(t)}" for i, t in enumerate(teams)]
    text = f"Most {label} in Division I history:\n" + '\n'.join(lines) + f"\n\nEvery program, every era: {ORIGIN}/rankings"
    return [text]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    date = datetime.date.fromisoformat(args[0]) if args else datetime.date.today()
    otd, tm, htss, H = load('on_this_day.json'), load('time_machine_results.json'), load('htss_v2_results.json'), load('data.json')['H']

    sections = [
        ('On This Day', draft_on_this_day(date, otd)),
        ('Time Machine', draft_time_machine(date, tm)),
        ('Greatest Season', draft_greatest_season(date, htss)),
        ('Record Book', draft_record_book(date, H)),
    ]
    lines = [f"# Hoopsipedia drafts — {date.isoformat()}", '',
             'Every number below comes from the database; links are forever URLs. '
             'Character counts are for X (URLs count as 23).', '']
    for title, drafts in sections:
        if not drafts:
            continue
        lines.append(f'## {title}')
        for d in drafts:
            lines += ['', f'_{x_len(d)} chars_', '', '```', d, '```', '']
    body = '\n'.join(lines)

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f'{date.isoformat()}.md')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(body)
    with open(os.path.join(OUT_DIR, 'latest.md'), 'w', encoding='utf-8') as f:
        f.write(body)
    print(f'wrote {os.path.relpath(path, ROOT)}')
    if '--print' in sys.argv:
        print(body)


if __name__ == '__main__':
    main()
