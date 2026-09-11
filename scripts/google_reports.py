#!/usr/bin/env python3
"""Human-traffic and search-visibility report from Google Analytics 4 and
Google Search Console — the bot-proof numbers Cloudflare cannot give us.

Auth: a read-only service account key at ~/.config/hoopsipedia/google-sa.json
(never in the repo). The service account must be a Viewer on the GA4
property and a user on the Search Console property.

  python3 scripts/google_reports.py                    # last 28 days vs the 28 before
  python3 scripts/google_reports.py --days 7
  python3 scripts/google_reports.py --property 123456789   # GA4 property id
  python3 scripts/google_reports.py --discover          # list GA4 properties / GSC sites the key can see

GA4_PROPERTY_ID may also be set in the environment. Output: markdown to
stdout and content/reports/google-<date>.md (gitignored).
"""
import datetime
import json
import os
import sys

import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY_PATH = os.path.expanduser('~/.config/hoopsipedia/google-sa.json')
SCOPES = ['https://www.googleapis.com/auth/analytics.readonly',
          'https://www.googleapis.com/auth/webmasters.readonly']
GSC_SITE_CANDIDATES = ['sc-domain:hoopsipedia.com', 'https://www.hoopsipedia.com/', 'https://hoopsipedia.com/']
OUT_DIR = os.path.join(ROOT, 'content', 'reports')


def session():
    if not os.path.exists(KEY_PATH):
        sys.exit(f'missing service-account key at {KEY_PATH}')
    creds = service_account.Credentials.from_service_account_file(KEY_PATH, scopes=SCOPES)
    creds.refresh(Request())
    s = requests.Session()
    s.headers['Authorization'] = f'Bearer {creds.token}'
    return s


def get(s, url, **kw):
    r = s.get(url, timeout=60, **kw)
    if r.status_code >= 400:
        raise RuntimeError(f'{r.status_code} {url}: {r.text[:300]}')
    return r.json()


def post(s, url, body):
    r = s.post(url, json=body, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f'{r.status_code} {url}: {r.text[:300]}')
    return r.json()


# ── discovery ────────────────────────────────────────────────────────────
def discover(s):
    print('GA4 properties visible to the service account (needs Analytics Admin API enabled):')
    try:
        acc = get(s, 'https://analyticsadmin.googleapis.com/v1beta/accountSummaries')
        for a in acc.get('accountSummaries', []):
            for p in a.get('propertySummaries', []):
                print(f"  {p['property'].split('/')[-1]:>12}  {p.get('displayName')}  ({a.get('displayName')})")
        if not acc.get('accountSummaries'):
            print('  none — add the service account as Viewer on the property first')
    except RuntimeError as e:
        print(f'  could not list: {e}')
    print('Search Console sites visible to the service account:')
    try:
        sites = get(s, 'https://www.googleapis.com/webmasters/v3/sites')
        for x in sites.get('siteEntry', []):
            print(f"  {x['siteUrl']}  ({x['permissionLevel']})")
        if not sites.get('siteEntry'):
            print('  none — add the service account as a user in Search Console first')
    except RuntimeError as e:
        print(f'  could not list: {e}')


# ── GA4 ──────────────────────────────────────────────────────────────────
def ga_report(s, prop, start, end, dims, mets, limit=10, order_met=None):
    body = {
        'dateRanges': [{'startDate': start, 'endDate': end}],
        'dimensions': [{'name': d} for d in dims],
        'metrics': [{'name': m} for m in mets],
        'limit': limit,
    }
    if order_met:
        body['orderBys'] = [{'metric': {'metricName': order_met}, 'desc': True}]
    r = post(s, f'https://analyticsdata.googleapis.com/v1beta/properties/{prop}:runReport', body)
    rows = []
    for row in r.get('rows', []):
        rows.append(([d['value'] for d in row.get('dimensionValues', [])], [float(m['value']) for m in row.get('metricValues', [])]))
    return rows


def ga_totals(s, prop, start, end):
    rows = ga_report(s, prop, start, end, [], ['activeUsers', 'sessions', 'screenPageViews', 'engagementRate', 'averageSessionDuration'], limit=1)
    return rows[0][1] if rows else [0, 0, 0, 0, 0]


def fmt_pct(a, b):
    if not b:
        return 'n/a'
    return f'{(a - b) / b * 100:+.0f}%'


def ga_section(s, prop, start, end, pstart, pend):
    cur, prev = ga_totals(s, prop, start, end), ga_totals(s, prop, pstart, pend)
    lines = [f'## Google Analytics (humans), {start} → {end}', '',
             '| Metric | This period | Previous | Change |', '|---|---|---|---|']
    for name, i, f in [('Active users', 0, '{:,.0f}'), ('Sessions', 1, '{:,.0f}'), ('Pageviews', 2, '{:,.0f}'),
                       ('Engagement rate', 3, '{:.0%}'), ('Avg session (s)', 4, '{:,.0f}')]:
        lines.append(f'| {name} | {f.format(cur[i])} | {f.format(prev[i])} | {fmt_pct(cur[i], prev[i])} |')
    days = (datetime.date.fromisoformat(end) - datetime.date.fromisoformat(start)).days + 1
    lines += ['', f'Average {cur[0] / days:,.0f} active users per day.', '']

    lines += ['### Top pages (by views)', '', '| Page | Views | Users |', '|---|---|---|']
    for dims, mets in ga_report(s, prop, start, end, ['pagePath'], ['screenPageViews', 'activeUsers'], 15, 'screenPageViews'):
        lines.append(f'| {dims[0]} | {mets[0]:,.0f} | {mets[1]:,.0f} |')
    lines += ['', '### Traffic sources', '', '| Channel | Sessions | Users |', '|---|---|---|']
    for dims, mets in ga_report(s, prop, start, end, ['sessionDefaultChannelGroup'], ['sessions', 'activeUsers'], 10, 'sessions'):
        lines.append(f'| {dims[0]} | {mets[0]:,.0f} | {mets[1]:,.0f} |')
    lines += ['', '### Countries', '', '| Country | Users |', '|---|---|']
    for dims, mets in ga_report(s, prop, start, end, ['country'], ['activeUsers'], 8, 'activeUsers'):
        lines.append(f'| {dims[0]} | {mets[0]:,.0f} |')
    lines += ['', '### Daily active users', '', '| Date | Users | Sessions |', '|---|---|---|']
    daily = ga_report(s, prop, start, end, ['date'], ['activeUsers', 'sessions'], 60)
    for dims, mets in sorted(daily):
        d = dims[0]
        lines.append(f'| {d[:4]}-{d[4:6]}-{d[6:]} | {mets[0]:,.0f} | {mets[1]:,.0f} |')
    return lines


# ── Search Console ───────────────────────────────────────────────────────
def gsc_site(s):
    sites = get(s, 'https://www.googleapis.com/webmasters/v3/sites').get('siteEntry', [])
    urls = [x['siteUrl'] for x in sites]
    for c in GSC_SITE_CANDIDATES:
        if c in urls:
            return c
    return urls[0] if urls else None


def gsc_query(s, site, start, end, dims, limit=10):
    from urllib.parse import quote
    body = {'startDate': start, 'endDate': end, 'dimensions': dims, 'rowLimit': limit}
    r = post(s, f'https://www.googleapis.com/webmasters/v3/sites/{quote(site, safe="")}/searchAnalytics/query', body)
    return r.get('rows', [])


def gsc_section(s, start, end, pstart, pend):
    site = gsc_site(s)
    if not site:
        return ['## Google Search Console', '', 'No site visible to the service account yet.']
    from urllib.parse import quote
    tot = lambda rows: (sum(r['clicks'] for r in rows), sum(r['impressions'] for r in rows))
    cur, prev = tot(gsc_query(s, site, start, end, ['date'], 100)), tot(gsc_query(s, site, pstart, pend, ['date'], 100))
    lines = [f'## Google Search Console ({site}), {start} → {end}', '',
             '| Metric | This period | Previous | Change |', '|---|---|---|---|',
             f'| Clicks | {cur[0]:,} | {prev[0]:,} | {fmt_pct(cur[0], prev[0])} |',
             f'| Impressions | {cur[1]:,} | {prev[1]:,} | {fmt_pct(cur[1], prev[1])} |', '']
    lines += ['### Top queries', '', '| Query | Clicks | Impressions | Position |', '|---|---|---|---|']
    for r in gsc_query(s, site, start, end, ['query'], 20):
        lines.append(f"| {r['keys'][0]} | {r['clicks']:,} | {r['impressions']:,} | {r['position']:.1f} |")
    lines += ['', '### Top pages in search', '', '| Page | Clicks | Impressions | Position |', '|---|---|---|---|']
    for r in gsc_query(s, site, start, end, ['page'], 20):
        lines.append(f"| {r['keys'][0].replace('https://www.hoopsipedia.com', '')} | {r['clicks']:,} | {r['impressions']:,} | {r['position']:.1f} |")
    try:
        sm = get(s, f'https://www.googleapis.com/webmasters/v3/sites/{quote(site, safe="")}/sitemaps').get('sitemap', [])
        lines += ['', '### Sitemaps', '', '| Sitemap | Last downloaded | Submitted | Indexed | Errors |', '|---|---|---|---|---|']
        for x in sm:
            c = (x.get('contents') or [{}])[0]
            lines.append(f"| {x['path'].replace('https://www.hoopsipedia.com', '')} | {x.get('lastDownloaded', '')[:10]} | {c.get('submitted', '')} | {c.get('indexed', '')} | {x.get('errors', 0)} |")
    except RuntimeError as e:
        lines += ['', f'(sitemaps unavailable: {e})']
    return lines


def main():
    args = sys.argv[1:]
    s = session()
    if '--discover' in args:
        discover(s)
        return
    days = int(args[args.index('--days') + 1]) if '--days' in args else 28
    prop = args[args.index('--property') + 1] if '--property' in args else os.environ.get('GA4_PROPERTY_ID')
    end = datetime.date.today() - datetime.timedelta(days=1)
    start = end - datetime.timedelta(days=days - 1)
    pend = start - datetime.timedelta(days=1)
    pstart = pend - datetime.timedelta(days=days - 1)
    iso = lambda d: d.isoformat()

    lines = [f'# Hoopsipedia — Google report, {iso(start)} → {iso(end)} (vs {iso(pstart)} → {iso(pend)})', '']
    if prop:
        try:
            lines += ga_section(s, prop, iso(start), iso(end), iso(pstart), iso(pend))
        except RuntimeError as e:
            lines += ['## Google Analytics', '', f'Error: {e}']
    else:
        lines += ['## Google Analytics', '', 'No GA4 property id — pass --property or set GA4_PROPERTY_ID (run --discover).']
    lines += ['']
    try:
        lines += gsc_section(s, iso(start), iso(end), iso(pstart), iso(pend))
    except RuntimeError as e:
        lines += ['## Google Search Console', '', f'Error: {e}']

    body = '\n'.join(lines)
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f'google-{iso(end)}.md')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(body)
    print(body)
    print(f'\n(saved to {os.path.relpath(path, ROOT)})')


if __name__ == '__main__':
    main()
