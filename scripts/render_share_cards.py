#!/usr/bin/env python3
"""Render 1200×630 social share cards (Open Graph / Twitter images) with the
site's own fonts and colours, using headless Chrome as the rasterizer.

Why: every page's og:image was either an 800×800 ESPN logo or the square
site logo — squashed or cropped on X, Slack, iMessage, Reddit. A shared Time
Machine matchup or team page should look like a card someone designed.

Cards written to share/<kind>/<slug>.jpg plus share/index.json (the Pages
Function reads the manifest to pick og:image):

  default            share/default.jpg
  sections           share/section/{rankings,time-machine,players,...}.jpg
  teams              share/team/{team-slug}.jpg            (365)
  time machine       share/tm/{a}--{seasonA}--{b}--{seasonB}.jpg  (featured)
  rivalries          share/rivalry/{slug}.jpg

  python3 scripts/render_share_cards.py            # everything
  python3 scripts/render_share_cards.py --only sections,tm,rivalry
  python3 scripts/render_share_cards.py --only team --limit 5   # smoke test

Idempotent; re-run after data.json / time_machine_results.json / rivalries.json
change. ~1s per card.
"""
import html
import json
import os
import re
import subprocess
import sys
import tempfile

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'share')
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
FONTS = os.path.join(ROOT, 'fonts')
LOGO = os.path.join(ROOT, 'branding', 'hoopsipedia-logo.jpg')
from types import SimpleNamespace
F = SimpleNamespace(NAME=0, MASCOT=1, CONF=2, COLOR=3, ATW=4, ATL=5, NC=6, NCY=7, FF=8)


def slug(name):
    return re.sub(r'(^-|-$)', '', re.sub(r'[^a-z0-9]+', '-', name.lower()))


def esc(s):
    return html.escape(str(s))


def logo_url(espn_id, size=400):
    return f'https://a.espncdn.com/combiner/i?img=/i/teamlogos/ncaa/500/{espn_id}.png&w={size}&h={size}&transparent=true'


CSS = f"""
@font-face {{ font-family:'Lobster'; src:url(file://{FONTS}/lobster-400-latin.woff2) format('woff2'); }}
@font-face {{ font-family:'Roboto Slab'; font-weight:400 900; src:url(file://{FONTS}/roboto-slab-var-latin.woff2) format('woff2'); }}
@font-face {{ font-family:'DM Sans'; font-weight:400 700; src:url(file://{FONTS}/dm-sans-var-latin.woff2) format('woff2'); }}
@font-face {{ font-family:'Stint Ultra Condensed'; src:url(file://{FONTS}/stint-ultra-condensed-400-latin.woff2) format('woff2'); }}
@font-face {{ font-family:'JetBrains Mono'; font-weight:400 700; src:url(file://{FONTS}/jetbrains-mono-var-latin.woff2) format('woff2'); }}
* {{ box-sizing:border-box; margin:0; padding:0; }}
html,body {{ width:1200px; height:630px; overflow:hidden; }}
body {{ background:#1B2A4A; color:#F5F3EE; font-family:'DM Sans',sans-serif; position:relative; }}
.bg {{ position:absolute; inset:0; background:
  radial-gradient(ellipse at 15% 0%, rgba(232,124,30,0.22), transparent 55%),
  radial-gradient(ellipse at 100% 100%, rgba(201,168,108,0.18), transparent 50%); }}
.rule {{ position:absolute; left:64px; right:64px; height:3px; background:#C9A86C; }}
.brand {{ position:absolute; left:64px; top:44px; display:flex; align-items:center; gap:16px; }}
.brand img {{ width:56px; height:56px; }}
.brand .word {{ font-family:'Lobster',cursive; font-size:44px; color:#C9A86C; line-height:1; }}
.kicker {{ position:absolute; right:64px; top:56px; font-family:'JetBrains Mono',monospace; font-size:18px; letter-spacing:0.18em; color:rgba(245,243,238,0.7); text-transform:uppercase; }}
.foot {{ position:absolute; left:64px; right:64px; bottom:40px; display:flex; justify-content:space-between; font-family:'JetBrains Mono',monospace; font-size:18px; letter-spacing:0.14em; color:rgba(245,243,238,0.65); text-transform:uppercase; }}
.title {{ font-family:'Roboto Slab',serif; font-weight:800; line-height:1.05; letter-spacing:-0.01em; }}
.sub {{ font-family:'DM Sans',sans-serif; color:rgba(245,243,238,0.85); }}
.mono {{ font-family:'JetBrains Mono',monospace; }}
.display {{ font-family:'Stint Ultra Condensed',sans-serif; text-transform:uppercase; letter-spacing:0.02em; }}
"""


def shell(body, kicker='Built for banter · Backed by the record book'):
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div class="bg"></div>
<div class="brand"><img src="file://{LOGO}"><div class="word">Hoopsipedia</div></div>
<div class="kicker">{esc(kicker)}</div>
<div class="rule" style="top:120px"></div>
{body}
<div class="foot"><span>hoopsipedia.com</span><span>The college basketball record, 1908 → today</span></div>
</body></html>"""


def card_default():
    body = """
<div style="position:absolute;left:64px;top:160px;right:64px;">
  <div class="display" style="font-size:112px;line-height:0.92;color:#F5F3EE;">Every team.<br>Every season.<br>Every argument.</div>
  <div class="sub" style="margin-top:22px;font-size:27px;">365 programs · 284,000 games · box scores to 1908 · HTSS cross-era rankings</div>
</div>"""
    return shell(body)


SECTIONS = {
    'rankings': ('College Basketball Rankings', 'All-time programs, the greatest seasons ever, and HTSS — one scale for every era since 1949'),
    'time-machine': ('The Time Machine', 'Greatest games never played: any team-season vs any team-season, with a predicted score'),
    'players': ('Player Archive', 'Box-score leaders across 20,000+ archived games, 1908 to today'),
    'rivalries': ('College Basketball Rivalries', 'All-time series records, decade by decade, for the games that matter most'),
    'coaches': ('Winningest Coaches', 'The 100 winningest head coaches in Division I history, verified against the record book'),
    'teams': ('All 365 Division I Programs', 'Every program, every season, every result — by conference'),
    'champions': ('Championship Journeys', 'Every national champion’s path through the bracket, 1939 to today'),
    'bracket': ('NCAA Tournament Bracket', 'Live scores, seed-matchup history, upset alerts, every team’s résumé'),
    'upsets': ('Greatest Tournament Upsets', '340+ verified bracket busters, by seed and by era'),
    'classics': ('Instant Classics', 'Buzzer beaters and overtime thrillers from the latest NCAA Tournament'),
    'on-this-day': ('On This Day', 'The upsets, blowouts, overtime thrillers and title games played on this date, every year since 1908'),
}


def card_section(key):
    title, sub = SECTIONS[key]
    body = f"""
<div style="position:absolute;left:64px;top:180px;right:64px;">
  <div class="title" style="font-size:86px;color:#F5F3EE;">{esc(title)}</div>
  <div class="sub" style="margin-top:28px;font-size:32px;line-height:1.35;max-width:1000px;">{esc(sub)}</div>
</div>"""
    return shell(body)


def card_team(tid, t):
    name = t[F.NAME]
    nc, ff = t[F.NC] or 0, t[F.FF] or 0
    bits = [f"{t[F.ATW]:,}–{t[F.ATL]:,} all-time"]
    if nc: bits.append(f"{nc} national title{'s' if nc != 1 else ''}")
    if ff: bits.append(f"{ff} Final Four{'s' if ff != 1 else ''}")
    years = ', '.join(str(y) for y in (t[F.NCY] if isinstance(t[F.NCY], list) else []))
    color = t[F.COLOR] if isinstance(t[F.COLOR], str) and t[F.COLOR].startswith('#') else '#C9A86C'
    body = f"""
<div style="position:absolute;left:64px;top:150px;width:330px;height:400px;display:flex;align-items:center;justify-content:center;">
  <div style="width:300px;height:300px;border-radius:50%;background:rgba(245,243,238,0.06);display:flex;align-items:center;justify-content:center;border:3px solid rgba(201,168,108,0.5)">
    <img src="{logo_url(tid, 500)}" style="width:230px;height:230px;object-fit:contain;">
  </div>
</div>
<div style="position:absolute;left:430px;top:165px;right:64px;">
  <div class="mono" style="font-size:20px;letter-spacing:0.18em;color:#C9A86C;text-transform:uppercase;">{esc(t[F.CONF] or '')} · Basketball</div>
  <div class="title" style="font-size:{'64' if len(name) > 22 else '78'}px;color:#F5F3EE;margin-top:14px;">{esc(name)}</div>
  <div style="margin-top:26px;height:4px;width:120px;background:{esc(color)};"></div>
  <div class="sub" style="margin-top:24px;font-size:30px;line-height:1.4;">{esc(' · '.join(bits))}</div>
  {'<div class="sub" style="margin-top:8px;font-size:22px;color:rgba(245,243,238,0.65);">Titles: ' + esc(years) + '</div>' if years and len(years) < 60 else ''}
</div>"""
    return shell(body, kicker='Program history · Every season · Every game')


def card_tm(m, teams_by_name):
    a, b, p = m['teamA'], m['teamB'], m['prediction']
    ida, idb = teams_by_name.get(a['name']), teams_by_name.get(b['name'])
    ya, yb = int(a['season'][:4]) + 1, int(b['season'][:4]) + 1
    winner_a = p['winner'] == a['name']

    def side(tid, yr, t, score, won, align):
        return f"""
<div style="width:420px;text-align:center;">
  <img src="{logo_url(tid, 400) if tid else ''}" style="width:170px;height:170px;object-fit:contain;">
  <div class="title" style="font-size:38px;margin-top:8px;color:#F5F3EE;">{yr} {esc(t['name'])}</div>
  <div class="sub" style="font-size:22px;color:rgba(245,243,238,0.7);margin-top:4px;">{esc(t['record'])} · {esc(t['coach'])}</div>
  <div class="display" style="font-size:96px;line-height:1;margin-top:8px;color:{'#C9A86C' if won else 'rgba(245,243,238,0.55)'};">{score}</div>
</div>"""
    body = f"""
<div style="position:absolute;left:64px;right:64px;top:140px;display:flex;align-items:center;justify-content:space-between;">
  {side(ida, ya, a, p['scoreA'], winner_a, 'left')}
  <div style="text-align:center;width:180px;">
    <div class="display" style="font-size:72px;color:#C2422D;">VS</div>
    <div class="mono" style="font-size:18px;color:rgba(245,243,238,0.7);margin-top:8px;">{max(p['winProbA'], p['winProbB']):.0f}% {esc((a['name'] if winner_a else b['name']).split(' ')[-1])}</div>
  </div>
  {side(idb, yb, b, p['scoreB'], not winner_a, 'right')}
</div>"""
    return shell(body, kicker='Time Machine · Greatest games never played')


def card_rivalry(r, H, h2h):
    t1, t2 = H[r['team1Id']], H[r['team2Id']]
    rec = (h2h.get(r['team1Id']) or {}).get(r['team2Id']) or {}
    w, l = rec.get('w'), rec.get('l')
    series = ''
    if w is not None:
        if w > l: series = f"{t1[F.NAME].split(' ')[-1]} lead {w}–{l}"
        elif l > w: series = f"{t2[F.NAME].split(' ')[-1]} lead {l}–{w}"
        else: series = f"Series tied {w}–{l}"
    body = f"""
<div style="position:absolute;left:64px;right:64px;top:150px;display:flex;align-items:center;justify-content:space-between;">
  <div style="width:380px;text-align:center;"><img src="{logo_url(r['team1Id'], 400)}" style="width:200px;height:200px;object-fit:contain;"><div class="title" style="font-size:34px;margin-top:10px;">{esc(t1[F.NAME])}</div></div>
  <div class="display" style="font-size:80px;color:#C2422D;">VS</div>
  <div style="width:380px;text-align:center;"><img src="{logo_url(r['team2Id'], 400)}" style="width:200px;height:200px;object-fit:contain;"><div class="title" style="font-size:34px;margin-top:10px;">{esc(t2[F.NAME])}</div></div>
</div>
<div style="position:absolute;left:64px;right:64px;top:470px;text-align:center;">
  <div class="title" style="font-size:40px;color:#C9A86C;">{esc(r['name'])}</div>
  <div class="sub" style="font-size:26px;margin-top:6px;">{esc(series)}</div>
</div>"""
    return shell(body, kicker='Rivalry · All-time series')


def render(html_text, out_path):
    """out_path ends in .jpg; Chrome screenshots to a temp PNG, Pillow re-encodes."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write(html_text)
        tmp = f.name
    png = out_path[:-4] + '.tmp.png'
    try:
        subprocess.run([CHROME, '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
                        '--window-size=1200,630', '--force-device-scale-factor=1', '--virtual-time-budget=6000',
                        f'--screenshot={png}', f'file://{tmp}'],
                       check=True, capture_output=True, timeout=60)
        Image.open(png).convert('RGB').save(out_path, 'JPEG', quality=82, optimize=True, progressive=True)
    finally:
        os.unlink(tmp)
        if os.path.exists(png):
            os.unlink(png)


def main():
    args = sys.argv[1:]
    only = set(args[args.index('--only') + 1].split(',')) if '--only' in args else {'default', 'section', 'team', 'tm', 'rivalry'}
    limit = int(args[args.index('--limit') + 1]) if '--limit' in args else None
    H = json.load(open(os.path.join(ROOT, 'data.json')))['H']
    teams_by_name = {t[F.NAME]: tid for tid, t in H.items()}
    manifest_path = os.path.join(OUT, 'index.json')
    manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {'default': None, 'section': {}, 'team': {}, 'tm': {}, 'rivalry': {}}
    n = 0

    if 'default' in only:
        render(card_default(), os.path.join(OUT, 'default.jpg')); manifest['default'] = 'share/default.jpg'; n += 1
    if 'section' in only:
        for key in SECTIONS:
            render(card_section(key), os.path.join(OUT, 'section', f'{key}.jpg')); manifest['section'][key] = f'share/section/{key}.jpg'; n += 1
    if 'team' in only:
        for i, (tid, t) in enumerate(sorted(H.items(), key=lambda kv: kv[1][F.NAME])):
            if limit and i >= limit: break
            s = slug(t[F.NAME]); render(card_team(tid, t), os.path.join(OUT, 'team', f'{s}.jpg')); manifest['team'][s] = f'share/team/{s}.jpg'; n += 1
            if n % 25 == 0: print(f'  {n} cards…', flush=True)
    if 'tm' in only:
        tm = json.load(open(os.path.join(ROOT, 'time_machine_results.json')))
        for m in tm.get('matchups', []):
            a, b = m['teamA'], m['teamB']
            key = f"{slug(a['name'])}--{a['season']}--{slug(b['name'])}--{b['season']}"
            render(card_tm(m, teams_by_name), os.path.join(OUT, 'tm', f'{key}.jpg')); manifest['tm'][key] = f'share/tm/{key}.jpg'; n += 1
    if 'rivalry' in only:
        riv = json.load(open(os.path.join(ROOT, 'rivalries.json')))
        h2h = json.load(open(os.path.join(ROOT, 'h2h.json')))
        for r in riv:
            render(card_rivalry(r, H, h2h), os.path.join(OUT, 'rivalry', f"{r['slug']}.jpg")); manifest['rivalry'][r['slug']] = f"share/rivalry/{r['slug']}.jpg"; n += 1

    os.makedirs(OUT, exist_ok=True)
    json.dump(manifest, open(manifest_path, 'w'), indent=1, sort_keys=True)
    print(f'rendered {n} cards → share/ (manifest share/index.json)')


if __name__ == '__main__':
    main()
