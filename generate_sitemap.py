#!/usr/bin/env python3
"""Generate sitemap.xml for Hoopsipedia from data.json.

Includes:
  - Homepage
  - Static ?view= pages (bracket, rankings, teams, coaches, upsets,
    classics, champions — the views the [[path]].js Pages function serves
    OG/meta for)
  - One ?team= URL per team in data.json's H object (slug built the same
    way functions/[[path]].js builds it)
  - One ?championship=YEAR/slug URL per championship year listed in each
    team's NCY field (index 7 of the H array)

Writes atomically (temp file + os.replace) and validates the result with
xml.etree before swapping it in.
"""

import json
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from datetime import date

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(REPO_ROOT, 'data.json')
SITEMAP_PATH = os.path.join(REPO_ROOT, 'sitemap.xml')

BASE_URL = 'https://www.hoopsipedia.com/'  # must match the pinned canonical host in functions/[[path]].js

# H array field indexes (mirror of F in functions/[[path]].js)
F_NAME = 0
F_NCY = 7  # list of national championship years (may be '' / [] when none)

VIEWS = ['bracket', 'rankings', 'teams', 'coaches', 'upsets', 'classics', 'champions']


def team_slug(name):
    """Convert team name to URL slug: 'Duke Blue Devils' -> 'duke-blue-devils'.

    Must stay in sync with teamSlug() in functions/[[path]].js.
    """
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = re.sub(r'(^-|-$)', '', slug)
    return slug


def xml_escape(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def build_urls(data):
    h = data.get('H', {})
    urls = []
    seen = set()

    def add(loc, priority):
        if loc in seen:
            return
        seen.add(loc)
        urls.append({'loc': loc, 'priority': priority})

    # Homepage
    add(BASE_URL, '1.0')

    # Static view pages
    for view in VIEWS:
        add(f'{BASE_URL}?view={view}', '0.6')

    # Team pages, sorted by team name for stable diffs
    teams = sorted(h.values(), key=lambda t: t[F_NAME])
    for team in teams:
        slug = team_slug(team[F_NAME])
        add(f'{BASE_URL}?team={slug}', '0.8')

    # Championship pages: ?championship=YEAR/slug for every title year
    champ_pairs = []
    for team in teams:
        ncy = team[F_NCY]
        if not isinstance(ncy, list):
            continue
        slug = team_slug(team[F_NAME])
        for year in ncy:
            champ_pairs.append((int(year), slug))
    for year, slug in sorted(champ_pairs):
        add(f'{BASE_URL}?championship={year}/{slug}', '0.7')

    return urls


def render_sitemap(urls, lastmod):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for url in urls:
        lines.append('  <url>')
        lines.append(f'    <loc>{xml_escape(url["loc"])}</loc>')
        lines.append(f'    <lastmod>{lastmod}</lastmod>')
        lines.append(f'    <priority>{url["priority"]}</priority>')
        lines.append('  </url>')
    lines.append('</urlset>')
    return '\n'.join(lines) + '\n'


def write_atomic(path, content):
    """Write content to path atomically: temp file in same dir + os.replace."""
    dirname = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(dir=dirname, prefix='.sitemap_', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
        # Validate XML before swapping it into place
        ET.parse(tmp_path)
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def main():
    with open(DATA_PATH, 'r') as f:
        data = json.load(f)

    urls = build_urls(data)
    content = render_sitemap(urls, date.today().isoformat())
    write_atomic(SITEMAP_PATH, content)

    n_teams = sum(1 for u in urls if '?team=' in u['loc'])
    n_champs = sum(1 for u in urls if '?championship=' in u['loc'])
    n_views = sum(1 for u in urls if '?view=' in u['loc'])
    print(f'Generated sitemap.xml: {len(urls)} URLs '
          f'(1 homepage + {n_views} views + {n_teams} teams + {n_champs} championships)')


if __name__ == '__main__':
    main()
