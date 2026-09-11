#!/usr/bin/env python3
"""Generate the sitemap index + child sitemaps, including forever-URL
team and season pages.

Outputs (repo root):
  sitemap.xml            — sitemap INDEX (same URL GSC already has)
  sitemap-core.xml       — homepage, views, ?championship pages (from the
                           previous flat sitemap's non-team entries)
  sitemap-teams.xml      — /teams/{slug} for all teams
  sitemap-coaches.xml    — /coaches/{slug} for the top-100 coaches
  sitemap-seasons-N.xml  — /teams/{slug}/{season}, chunked at 10,000 URLs

Season URLs are derived from seasons/{espnId}.json so every URL is
guaranteed to resolve (the Pages function 404s unknown seasons).
"""

import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGIN = 'https://www.hoopsipedia.com'
TODAY = date.today().isoformat()
CHUNK = 10000


def team_slug(name):
    return re.sub(r'(^-|-$)', '', re.sub(r'[^a-z0-9]+', '-', name.lower()))


def url_el(loc, lastmod=TODAY, priority=None):
    p = f"\n    <priority>{priority}</priority>" if priority else ''
    return (f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{lastmod}</lastmod>{p}\n  </url>")


def write_urlset(path, urls):
    body = "\n".join(urls)
    xml = (f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
           f"<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n{body}\n</urlset>\n")
    with open(os.path.join(ROOT, path), 'w') as f:
        f.write(xml)
    return len(urls)


def main():
    with open(os.path.join(ROOT, 'data.json')) as f:
        data = json.load(f)
    H = data['H']

    # core: homepage + the section forever URLs (server-rendered by the
    # Pages Function), rivalry pages, the featured Time Machine matchups, and
    # the ?championship= pages carried over from the previous core sitemap.
    SECTIONS = ['teams', 'rankings', 'time-machine', 'players', 'rivalries',
                'coaches', 'bracket', 'upsets', 'classics', 'champions']
    core = [url_el(f'{ORIGIN}/', priority='1.0')]
    core += [url_el(f'{ORIGIN}/{sec}', priority='0.9') for sec in SECTIONS]
    try:
        with open(os.path.join(ROOT, 'rivalries.json')) as f:
            core += [url_el(f"{ORIGIN}/rivalries/{r['slug']}", priority='0.8') for r in json.load(f)]
    except OSError:
        pass
    try:
        with open(os.path.join(ROOT, 'time_machine_results.json')) as f:
            for m in json.load(f).get('matchups', []):
                a, b = m['teamA'], m['teamB']
                core.append(url_el(f"{ORIGIN}/time-machine/{team_slug(a['name'])}/{a['season']}/"
                                   f"{team_slug(b['name'])}/{b['season']}", priority='0.7'))
    except (OSError, KeyError):
        pass
    prev_path = os.path.join(ROOT, 'sitemap-core.xml')
    prev = open(prev_path).read() if os.path.exists(prev_path) else open(os.path.join(ROOT, 'sitemap.xml')).read()
    for m in re.finditer(r'<url>\s*<loc>(.*?)</loc>.*?</url>', prev, re.S):
        loc = m.group(1)
        if 'championship=' in loc:
            pr = re.search(r'<priority>(.*?)</priority>', m.group(0))
            core.append(url_el(loc, priority=pr.group(1) if pr else None))
    n_core = write_urlset('sitemap-core.xml', core)

    # teams at forever URLs
    team_urls = []
    slugs = {}
    for eid, fields in H.items():
        slug = team_slug(fields[0])
        slugs[eid] = slug
        team_urls.append(url_el(f'{ORIGIN}/teams/{slug}', priority='0.8'))
    n_teams = write_urlset('sitemap-teams.xml', sorted(team_urls))

    # top-100 coaches at forever URLs (same leaderboard the Pages function
    # serves — /coaches/{slug} 404s anyone outside it)
    coach_lb = data.get('COACH_LB_TOP100') or data.get('COACH_LB') or []
    coach_urls = sorted(
        url_el(f"{ORIGIN}/coaches/{team_slug(c['name'])}", priority='0.7')
        for c in coach_lb)
    n_coaches = write_urlset('sitemap-coaches.xml', coach_urls)

    # seasons, chunked
    season_urls = []
    for eid, slug in slugs.items():
        try:
            with open(os.path.join(ROOT, 'seasons', f'{eid}.json')) as f:
                rows = json.load(f).get('seasons', [])
        except OSError:
            continue
        for s in rows:
            yr = s.get('year')
            if yr:
                season_urls.append(url_el(f'{ORIGIN}/teams/{slug}/{yr}'))
    season_urls.sort()
    chunks = [season_urls[i:i + CHUNK] for i in range(0, len(season_urls), CHUNK)]
    children = ['sitemap-core.xml', 'sitemap-teams.xml', 'sitemap-coaches.xml']
    for i, chunk in enumerate(chunks, 1):
        write_urlset(f'sitemap-seasons-{i}.xml', chunk)
        children.append(f'sitemap-seasons-{i}.xml')

    # index at the canonical sitemap.xml URL
    entries = "\n".join(
        f"  <sitemap>\n    <loc>{ORIGIN}/{c}</loc>\n    <lastmod>{TODAY}</lastmod>\n  </sitemap>"
        for c in children)
    with open(os.path.join(ROOT, 'sitemap.xml'), 'w') as f:
        f.write(f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
                f"<sitemapindex xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n{entries}\n</sitemapindex>\n")

    print(f'core: {n_core} | teams: {n_teams} | coaches: {n_coaches} | '
          f'seasons: {len(season_urls)} across {len(chunks)} chunks | '
          f'index: {len(children)} children')


if __name__ == '__main__':
    main()
