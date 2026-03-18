#!/usr/bin/env python3
"""Generate sitemap.xml for Hoopsipedia from data.json."""

import json
import re
from datetime import date

def team_slug(name):
    """Convert team name to URL slug: 'Duke Blue Devils' → 'duke-blue-devils'"""
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = re.sub(r'(^-|-$)', '', slug)
    return slug

def main():
    with open('data.json', 'r') as f:
        data = json.load(f)

    today = date.today().isoformat()
    base_url = 'https://hoopsipedia.com/'

    urls = []

    # Homepage
    urls.append({'loc': base_url, 'priority': '1.0'})

    # Static view pages
    for view in ['bracket', 'rankings', 'teams', 'coaches']:
        urls.append({
            'loc': f'{base_url}?view={view}',
            'priority': '0.6',
        })

    # Team pages from H object (NAME is index 0)
    h = data.get('H', {})
    for team_id, team_data in sorted(h.items(), key=lambda x: x[1][0]):
        name = team_data[0]  # NAME field at index 0
        slug = team_slug(name)
        urls.append({
            'loc': f'{base_url}?team={slug}',
            'priority': '0.8',
        })

    # Build XML
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    for url in urls:
        lines.append('  <url>')
        lines.append(f'    <loc>{url["loc"]}</loc>')
        lines.append(f'    <lastmod>{today}</lastmod>')
        lines.append(f'    <priority>{url["priority"]}</priority>')
        lines.append('  </url>')

    lines.append('</urlset>')

    with open('sitemap.xml', 'w') as f:
        f.write('\n'.join(lines) + '\n')

    team_count = len(h)
    total = len(urls)
    print(f'Generated sitemap.xml: {total} URLs ({team_count} teams + 1 homepage + 4 views)')

if __name__ == '__main__':
    main()
