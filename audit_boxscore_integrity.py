#!/usr/bin/env python3
"""Cross-check sr_boxscores.json and upset_history.json against the game logs.

For every sr_boxscores.json entry with parseable teams (+ date when the
boxscore URL embeds one) and every upset in upset_history.json, look for
the game in both teams' logs (games_1/2/3.json), mirror-verified where
possible. The stored `opp` id field in the logs is unreliable (substring
matching bug, see OTD_NOTES.md); we trust opp_slug + date + scores and
re-derive slug->team ids by mirror voting, exactly like
generate_on_this_day.py.

Classification:
  VERIFIED      the game appears in the logs with matching teams + scores
                (sub-tagged mirror / one-sided when only one team's log
                covers the game)
  CONTRADICTED  a covered team's log shows a different game that day (or
                that season for undated entries), or no such game at all
                while the log demonstrably covers the period
  UNCHECKABLE   a team cannot be resolved to a logged program, the logs
                do not cover the period, or the period extends past the
                scrape cutoff (logs end 2026-03-19)

Usage:
  python3 audit_boxscore_integrity.py           # audit only (deterministic)
  python3 audit_boxscore_integrity.py --apply   # audit + apply the vetted
                                                # corrections (see APPLY
                                                # section at bottom)

--apply only ever touches a hardcoded whitelist of entries, and only
after this run's own audit re-confirms each one as CONTRADICTED (for
deletions) or finds the exact log-verified replacement game (for score
fixes). Writes go through json_io.save_json_atomic.
"""

import json
import os
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from json_io import save_json_atomic  # noqa: E402

GAMES_FILES = ['games_1.json', 'games_2.json', 'games_3.json']
SR_BOX_JSON = os.path.join(ROOT, 'sr_boxscores.json')
UPSETS_JSON = os.path.join(ROOT, 'upset_history.json')
DATA_JSON = os.path.join(ROOT, 'data.json')

# Same rename-only alias map as generate_on_this_day.py.
NAME_ALIASES = {
    'Arkansas-Little Rock Trojans': '2031',
    'College of Charleston Cougars': '232',
    'Connecticut Huskies': '41',
    'George Washington Colonials': '45',
    'Grand Canyon Antelopes': '2253',
    'Hawaii Rainbow Warriors': '62',
    'Miami Hurricanes': '2390',
    'Penn Quakers': '219',
    "Southwest Louisiana Ragin' Cajuns": '309',
    'Southwest Missouri State Bears': '2623',
    'UMass Minutemen': '113',
    'Valparaiso Crusaders': '2674',
    'Wisconsin-Green Bay Phoenix': '2739',
    'Wisconsin-Milwaukee Panthers': '270',
}

# SR/ESPN short display names used in the bulk-scraped sr_boxscores
# entries, mapped to the slug system the game logs use (verified against
# data.json ids; 'Hartford' has no log presence and stays unresolved).
SHORT_NAME_SLUGS = {
    'UNC': 'north-carolina',
    'Pitt': 'pittsburgh',
    "St. John's (NY)": 'st-johns-ny',
    'UMass': 'massachusetts',
    'Penn': 'pennsylvania',
    'FDU': 'fairleigh-dickinson',
    'ETSU': 'east-tennessee-state',
    'Louisiana': 'louisiana-lafayette',
    'LIU': 'long-island-university',
    'SIU-Edwardsville': 'southern-illinois-edwardsville',
}

# Log-side opp_slug variants for programs with no usable log of their own
# (mirror voting needs the opponent's log to exist, so these never get a
# vote). VMI's log is the Valparaiso duplicate and is merged away.
SLUG_ALIASES = {
    'virginia-military-institute': '2678',   # VMI Keydets
    'vmi': '2678',
}

URL_DATE_RE = re.compile(r'/boxscores/(\d{4}-\d{2}-\d{2})-')
SCORE_RE = re.compile(r'^(\d+)-(\d+)')


def slugify(name):
    return re.sub(r'-{2,}', '-', re.sub(r'[^a-z0-9]+', '-', name.lower())).strip('-')


def season_window(year):
    """Season Y spans Nov 1 of Y-1 through Apr 30 of Y."""
    return '{}-11-01'.format(year - 1), '{}-04-30'.format(year)


def load_logs():
    """per_team: tid -> deduped rows; slug_of: tid -> own slug (when known)."""
    per_team = defaultdict(list)
    slug_of = {}
    seen = set()
    for fname in GAMES_FILES:
        with open(os.path.join(ROOT, fname)) as f:
            data = json.load(f)
        for tid, obj in data.items():
            if isinstance(obj, dict):
                slug_of[tid] = obj['slug']
                rows = obj['games']
            else:
                rows = obj
            for g in rows:
                key = (tid, g['date'], g['opp_slug'], g['pts'], g['opp_pts'])
                if key in seen:
                    continue
                seen.add(key)
                per_team[tid].append(g)
    for rows in per_team.values():
        rows.sort(key=lambda g: (g['date'], g['opp_slug'], g['pts'], g['opp_pts']))
    merge_duplicate_logs(per_team, slug_of)
    return per_team, slug_of


def merge_duplicate_logs(per_team, slug_of):
    """The games files store three teams' logs twice under two different
    ids (Valparaiso under both 2674 and VMI's 2678 with slug 'valparaiso';
    South Dakota under 233 and 2563; South Dakota St under 2571 and 2566).
    Collapse exact-duplicate logs onto the id whose data.json name is
    consistent, so mirror voting is not split between the copies."""
    with open(DATA_JSON) as f:
        names = {tid: v[0] for tid, v in json.load(f)['H'].items()}
    groups = defaultdict(list)
    for tid, rows in per_team.items():
        groups[frozenset((g['date'], g['opp_slug'], g['pts'], g['opp_pts'])
                         for g in rows)].append(tid)
    for tids in groups.values():
        if len(tids) < 2:
            continue

        def rank(tid):
            name, slug = names.get(tid), slug_of.get(tid)
            consistent = 1
            if name and slug:
                ns = slugify(name)
                consistent = int(bool(set(ns.split('-')) & set(slug.split('-'))))
            return (name is not None, consistent, tid)

        canon = sorted(tids, key=rank, reverse=True)[0]
        for tid in tids:
            if tid == canon:
                continue
            if tid in slug_of:
                slug_of.setdefault(canon, slug_of[tid])
                del slug_of[tid]
            del per_team[tid]
            print('  merged duplicate log {} ({}) -> {} ({})'.format(
                tid, names.get(tid, '?'), canon, names.get(canon, '?')))


def build_slug_map(per_team, slug_of):
    """opp_slug -> tid by mirror voting (same thresholds as the OTD generator),
    seeded with each scraped team's own slug."""
    mirror_index = defaultdict(list)
    for tid, rows in per_team.items():
        for g in rows:
            mirror_index[(g['date'], g['pts'], g['opp_pts'])].append(tid)

    votes = defaultdict(Counter)
    for tid, rows in per_team.items():
        for g in rows:
            c = votes[g['opp_slug']]
            if sum(c.values()) >= 200:
                continue
            for cand in mirror_index.get((g['date'], g['opp_pts'], g['pts']), []):
                if cand != tid:
                    c[cand] += 1

    slug_map = {}
    for slug, c in votes.items():
        if not c:
            continue
        ranked = c.most_common(2)
        best, n = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else 0
        if n >= 5 and n / sum(c.values()) >= 0.75 and n >= 5 * runner_up:
            slug_map[slug] = best
    # A team's own slug is authoritative.
    for tid, slug in slug_of.items():
        slug_map[slug] = tid
    return slug_map


def build_name_map(slug_map):
    with open(DATA_JSON) as f:
        h = json.load(f)['H']
    exact = {v[0]: tid for tid, v in h.items()}
    exact.update(NAME_ALIASES)

    def resolve(name):
        if name in exact:
            return exact[name]
        if name in SHORT_NAME_SLUGS:
            return slug_map.get(SHORT_NAME_SLUGS[name])
        s = slugify(name)
        if s in slug_map:
            return slug_map[s]
        # Unique "location-only" prefix of a full ESPN name.
        pref = [tid for full, tid in exact.items() if full.startswith(name + ' ')]
        if len(set(pref)) == 1:
            return pref[0]
        return None

    return resolve


def extend_slug_map(slug_map, per_team, resolve):
    """Fold opp_slug VARIANTS onto the tids their canonical slugs map to.

    The games files are not slug-clean: some rows carry long-form slugs
    ('virginia-military-institute' where the canonical slug is 'vmi') and
    some carry raw display names ('Idaho State', 'Elon', 'Omaha' — see the
    1950s NCAA-tournament rows and the 1998-2012 gap-fill rows). Mirror
    voting cannot map a variant when the opponent has no log of its own,
    so without this step every such row reads as "some other opponent" and
    a real game audits as CONTRADICTED.

    Additions are setdefault-only: a slug the voting already resolved is
    never overridden. A variant is added only when it lands on an already
    known tid (via data.json full-name slugs, the curated SLUG_ALIASES, a
    slugified form already in the map, or the display-name resolver), so
    this can never invent a program."""
    with open(DATA_JSON) as f:
        h = json.load(f)['H']
    for tid, v in h.items():
        slug_map.setdefault(slugify(v[0]), tid)
    for slug, tid in SLUG_ALIASES.items():
        slug_map.setdefault(slug, tid)
    variants = {g['opp_slug'] for rows in per_team.values() for g in rows}
    for s in variants:
        if s in slug_map:
            continue
        tid = slug_map.get(slugify(s)) or resolve(s)
        if tid:
            slug_map[s] = tid


# ---------------------------------------------------------------- matching

def covered_on(per_team, tid, date):
    """True when tid's log has games on/before AND on/after `date` within
    that date's season — a missing game there is a real contradiction."""
    lo, hi = season_window(int(date[:4]) + (1 if date[5:7] >= '11' else 0))
    rows = [g['date'] for g in per_team.get(tid, []) if lo <= g['date'] <= hi]
    return bool(rows) and min(rows) <= date <= max(rows)


def covered_in(per_team, tid, lo, hi):
    return any(lo <= g['date'] <= hi for g in per_team.get(tid, []))


def rows_on(per_team, tid, date):
    return [g for g in per_team.get(tid, []) if g['date'] == date]


def fmt_row(g):
    return '{} vs {} {}-{} ({})'.format(
        g['date'], g['opp_slug'], g['pts'], g['opp_pts'],
        'W' if g['w'] else 'L')


def check_dated(per_team, slug_map, a, b, date, global_max):
    """a/b: dicts {tid, slug, name, score}. Returns (verdict, detail)."""
    if date > global_max:
        return 'UNCHECKABLE', 'date {} beyond log cutoff {}'.format(date, global_max)
    sides, n_match, n_covered = [], 0, 0
    for me, other in ((a, b), (b, a)):
        if not me['tid']:
            sides.append('{}: unresolved team'.format(me['name']))
            continue
        rows = rows_on(per_team, me['tid'], date)
        match = [g for g in rows if g['pts'] == me['score']
                 and g['opp_pts'] == other['score']
                 and slug_map.get(g['opp_slug'], other['tid']) == other['tid']]
        if match:
            n_match += 1
            n_covered += 1
            sides.append('{}: log row matches ({})'.format(me['name'], fmt_row(match[0])))
        elif rows:
            return 'CONTRADICTED', '{} log shows a different game on {}: {}'.format(
                me['name'], date, '; '.join(fmt_row(g) for g in rows))
        elif covered_on(per_team, me['tid'], date):
            return 'CONTRADICTED', '{} log covers {} (season games before and after) but has no game that day'.format(
                me['name'], date)
        else:
            sides.append('{}: log does not cover {}'.format(me['name'], date))
    if n_match == 2:
        return 'VERIFIED', 'mirror: ' + ' | '.join(sides)
    if n_match == 1:
        return 'VERIFIED', 'one-sided: ' + ' | '.join(sides)
    return 'UNCHECKABLE', ' | '.join(sides)


def check_undated(per_team, slug_map, a, b, lo, hi, global_max,
                  require_winner=None):
    """Match a-vs-b with scores a['score']-b['score'] anywhere in [lo, hi].
    require_winner: tid that must have w=True on the matched row (upsets)."""
    pair_rows = []   # (owner_side, row) — any game between the two teams
    exact = []
    for me, other in ((a, b), (b, a)):
        if not me['tid']:
            continue
        for g in per_team.get(me['tid'], []):
            if not (lo <= g['date'] <= hi):
                continue
            opp_tid = slug_map.get(g['opp_slug'])
            is_pair = (opp_tid == other['tid'] if opp_tid and other['tid']
                       else g['opp_slug'] == other['slug']
                       or slugify(g['opp_slug']) == other['slug'])
            if not is_pair:
                continue
            pair_rows.append((me, g))
            if (g['pts'] == me['score'] and g['opp_pts'] == other['score']
                    and (require_winner is None
                         or g['w'] == (me['tid'] == require_winner))):
                exact.append((me, g))
    if exact:
        dates = sorted({g['date'] for _, g in exact})
        n_sides = len({id(me) for me, _ in exact})
        tag = 'mirror' if n_sides == 2 else 'one-sided'
        return 'VERIFIED', '{}: matched on {} ({})'.format(
            tag, dates[0], '; '.join(fmt_row(g) for _, g in exact[:2])), dates[0]
    if hi > global_max:
        # In-progress scrape (2026): a later, not-yet-scraped meeting could
        # still match — never contradict inside an incomplete window.
        return 'UNCHECKABLE', 'window extends past log cutoff {} (logs incomplete)'.format(global_max), None
    if pair_rows:
        return 'CONTRADICTED', 'teams met in window but never with this score/result: {}'.format(
            '; '.join(sorted({fmt_row(g) for _, g in pair_rows}))), None
    cov = [me for me in (a, b) if me['tid'] and covered_in(per_team, me['tid'], lo, hi)]
    # A contradiction needs a season-DENSE log: a stray row or two in the
    # window (Michigan's 1991-92 log holds only the two Final Four games)
    # says nothing about what's absent from the rest of the season.
    dense = [me for me in cov if sum(
        lo <= g['date'] <= hi for g in per_team.get(me['tid'], [])) >= 8]
    if dense and a['tid'] and b['tid']:
        # Both programs identified, and a game involves both teams: its
        # absence from one team's season-complete log is a contradiction.
        names = ' and '.join(m['name'] for m in dense)
        return 'CONTRADICTED', 'no game between the teams in {}..{}, though the {} log{} cover the window'.format(
            lo, hi, names, '' if len(dense) == 1 else 's'), None
    missing = [m['name'] + (' (unresolved)' if not m['tid'] else
                            '' if m in cov else ' (no coverage)')
               for m in (a, b)]
    return 'UNCHECKABLE', 'insufficient coverage/resolution: ' + ', '.join(missing), None


# ------------------------------------------------------------------ audits

def audit_sr(per_team, slug_map, resolve, global_max):
    with open(SR_BOX_JSON) as f:
        sr = json.load(f)
    results = []
    for key, v in sr.items():
        if key == '_metadata':
            continue
        teams = v.get('teams') or []
        m = re.match(r'^(\d{4})/(.+)$', key)
        if len(teams) != 2 or not m or any(
                not isinstance(t.get('score'), int) for t in teams):
            results.append((key, 'UNCHECKABLE', 'unparseable entry'))
            continue
        year = int(m.group(1))
        halves = m.group(2).split('-vs-') if '-vs-' in m.group(2) else ['', '']
        sides = []
        for t in teams:
            s = slugify(t['name'])
            half = next((h for h in halves
                         if h == s or h.startswith(s) or s.startswith(h)), s)
            tid = resolve(t['name']) or slug_map.get(half)
            sides.append({'tid': tid, 'slug': half,
                          'name': t['name'], 'score': t['score']})
        a, b = sides
        date_m = URL_DATE_RE.search(v.get('url', ''))
        if date_m:
            verdict, detail = check_dated(per_team, slug_map, a, b,
                                          date_m.group(1), global_max)
            detail = 'dated {}: {}'.format(date_m.group(1), detail)
            if verdict == 'CONTRADICTED':
                # Wrong-URL/date detection: same teams + scores elsewhere
                # in the season means only the date metadata is bad.
                lo, hi = season_window(year)
                v2, d2, dt = check_undated(per_team, slug_map, a, b,
                                           lo, hi, global_max)
                if v2 == 'VERIFIED':
                    detail += ' | HOWEVER the exact game exists on {} — URL/date metadata is wrong, game is real'.format(dt)
        else:
            lo, hi = season_window(year)
            verdict, detail, _ = check_undated(per_team, slug_map, a, b,
                                               lo, hi, global_max)
            detail = 'undated (season {}): {}'.format(year, detail)
        if a['tid'] and a['tid'] == b['tid']:
            verdict = 'CONTRADICTED'
            detail = 'CORRUPT ENTRY: the same team appears on both sides ({} / {}) | '.format(
                a['name'], b['name']) + detail
        if verdict == 'CONTRADICTED':
            detail += ' | player-pts sums: ' + ', '.join(
                '{}={} (claimed {})'.format(
                    t['name'],
                    sum(int(p['pts']) for p in t.get('players', [])
                        if str(p.get('pts', '')).lstrip('-').isdigit()) or '-',
                    t['score'])
                for t in teams)
        results.append((key, verdict, detail))
    return results


def audit_upsets(per_team, slug_map, resolve, global_max):
    with open(UPSETS_JSON) as f:
        doc = json.load(f)
    results = []
    for mkey, group in doc.items():
        if mkey == 'metadata':
            continue
        for up in group.get('upsets', []):
            label = '{} {} {} over {} {}'.format(
                mkey, up['year'], up['winner'], up['loser'], up.get('score', '?'))
            sm = SCORE_RE.match(up.get('score', ''))
            if not sm:
                results.append((label, 'UNCHECKABLE', 'unparseable score', None))
                continue
            w_pts, l_pts = int(sm.group(1)), int(sm.group(2))
            a = {'tid': resolve(up['winnerFull']), 'name': up['winnerFull'],
                 'score': w_pts, 'slug': slugify(up['winner'])}
            b = {'tid': resolve(up['loserFull']), 'name': up['loserFull'],
                 'score': l_pts, 'slug': slugify(up['loser'])}
            lo, hi = '{}-03-01'.format(up['year']), '{}-04-30'.format(up['year'])
            verdict, detail, date = check_undated(
                per_team, slug_map, a, b, lo, hi, global_max,
                require_winner=a['tid'])
            results.append((label, verdict, detail, date))
    return results


# ------------------------------------------------------------------- apply

# Deletions: fabricated upsets with no real game to correct to. Each must
# re-classify as CONTRADICTED in this run before it is removed.
UPSET_DELETIONS = [
    ('4v13', {'year': 1997, 'winner': 'College of Charleston',
              'loser': 'Maryland'},
     'duplicate of the real 1997 game, which was 12v5 (kept under 5v12 with corrected score)'),
    ('5v12', {'year': 1996, 'winner': 'Arkansas-Little Rock', 'loser': 'Purdue'},
     'no such game in any season; the real Little Rock-Purdue upset is the 2016 entry (85-83 2OT)'),
    ('7v10', {'year': 2014, 'winner': 'Stanford', 'loser': 'Kansas State'},
     'no Stanford-Kansas State game in 2014; score 60-57 belongs to Stanford-Kansas on 2014-03-23'),
    ('8v9', {'year': 2025, 'winner': 'Georgia', 'loser': 'Maryland'},
     'no Georgia-Maryland game in 2025; Georgia lost to Gonzaga 2025-03-20'),
]

# Score fixes: exact game found in both logs with a different score.
UPSET_SCORE_FIXES = [
    ('5v12', {'year': 1997, 'winner': 'College of Charleston',
              'loser': 'Maryland'}, '75-68', '75-66'),
    ('5v12', {'year': 1999, 'winner': 'Southwest Missouri State',
              'loser': 'Wisconsin'}, '43-41', '43-32'),
]

# sr_boxscores deletions: the two known-fabricated entries (audit must
# re-confirm CONTRADICTED). Any other contradicted sr entry is only
# reported, never deleted.
SR_DELETIONS = [
    '1999/charlotte-49ers-vs-stanford-cardinal',
    '2001/creighton-bluejays-vs-virginia-cavaliers',
]


def apply_corrections(ctx, upset_results, sr_results):
    per_team, slug_map, resolve, global_max = ctx
    changed = []

    sr_verdicts = {k: v for k, v, _ in sr_results}
    with open(SR_BOX_JSON) as f:
        sr = json.load(f)
    n_del = 0
    for key in SR_DELETIONS:
        if key not in sr:
            changed.append('SKIP sr_boxscores {}: not present'.format(key))
            continue
        if sr_verdicts.get(key) != 'CONTRADICTED':
            changed.append('SKIP sr_boxscores {}: audit verdict {} != CONTRADICTED'.format(
                key, sr_verdicts.get(key)))
            continue
        del sr[key]
        n_del += 1
        changed.append('DELETE sr_boxscores {}'.format(key))
    if n_del:
        if isinstance(sr.get('_metadata'), dict) and 'totalGames' in sr['_metadata']:
            sr['_metadata']['totalGames'] -= n_del
            changed.append('UPDATE sr_boxscores _metadata.totalGames -> {}'.format(
                sr['_metadata']['totalGames']))
        # compact, single-line — the 60MB+ store must stay under GitHub's
        # 100MB hard limit (indent=2 balloons it past that)
        save_json_atomic(SR_BOX_JSON, sr)

    upset_verdicts = {label: v for label, v, _, _ in upset_results}
    with open(UPSETS_JSON) as f:
        doc = json.load(f)
    dirty = set()
    for mkey, ident, why in UPSET_DELETIONS:
        ups = doc[mkey]['upsets']
        hits = [u for u in ups
                if all(u.get(k) == v for k, v in ident.items())]
        if len(hits) != 1:
            changed.append('SKIP upset {} {}: {} matches'.format(mkey, ident, len(hits)))
            continue
        u = hits[0]
        label = '{} {} {} over {} {}'.format(
            mkey, u['year'], u['winner'], u['loser'], u.get('score', '?'))
        if upset_verdicts.get(label) != 'CONTRADICTED':
            changed.append('SKIP upset {}: audit verdict {} != CONTRADICTED'.format(
                label, upset_verdicts.get(label)))
            continue
        ups.remove(u)
        dirty.add(mkey)
        changed.append('DELETE upset {} — {}'.format(label, why))
    for mkey, ident, old, new in UPSET_SCORE_FIXES:
        ups = doc[mkey]['upsets']
        hits = [u for u in ups
                if all(u.get(k) == v for k, v in ident.items())
                and u.get('score') == old]
        if len(hits) != 1:
            changed.append('SKIP score fix {} {}: {} matches'.format(mkey, ident, len(hits)))
            continue
        u = hits[0]
        # Gate: the corrected score must itself be log-verified.
        nm = SCORE_RE.match(new)
        a = {'tid': resolve(u['winnerFull']), 'name': u['winnerFull'],
             'score': int(nm.group(1)), 'slug': slugify(u['winner'])}
        b = {'tid': resolve(u['loserFull']), 'name': u['loserFull'],
             'score': int(nm.group(2)), 'slug': slugify(u['loser'])}
        verdict, detail, date = check_undated(
            per_team, slug_map, a, b, '{}-03-01'.format(u['year']),
            '{}-04-30'.format(u['year']), global_max, require_winner=a['tid'])
        if verdict != 'VERIFIED':
            changed.append('SKIP score fix {} {}: corrected score not log-verified ({})'.format(
                mkey, ident, detail))
            continue
        u['score'] = new
        changed.append('FIX upset {} {} {} over {}: score {} -> {} (log-verified on {})'.format(
            mkey, ident['year'], ident['winner'], ident['loser'], old, new, date))
    # Keep the derived counters consistent with the lists we just edited
    # (every group currently satisfies lowerSeedWins == len(upsets) and
    # totalGames == higherSeedWins + lowerSeedWins).
    for mkey in sorted(dirty):
        g = doc[mkey]
        g['lowerSeedWins'] = len(g['upsets'])
        g['totalGames'] = g['higherSeedWins'] + g['lowerSeedWins']
        g['upsetPct'] = float(
            (Decimal(g['lowerSeedWins'] * 100) / Decimal(g['totalGames']))
            .quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        changed.append('UPDATE {} counters: lowerSeedWins={} totalGames={} upsetPct={}'.format(
            mkey, g['lowerSeedWins'], g['totalGames'], g['upsetPct']))
    save_json_atomic(UPSETS_JSON, doc, indent=2)
    return changed


# -------------------------------------------------------------------- main

def main():
    apply_mode = '--apply' in sys.argv
    per_team, slug_of = load_logs()
    slug_map = build_slug_map(per_team, slug_of)
    resolve = build_name_map(slug_map)
    extend_slug_map(slug_map, per_team, resolve)
    global_max = max(g['date'] for rows in per_team.values() for g in rows)
    print('log rows for {} teams; {} opp_slugs resolved; log cutoff {}'.format(
        len(per_team), len(slug_map), global_max))

    sr_results = audit_sr(per_team, slug_map, resolve, global_max)
    up_results = audit_upsets(per_team, slug_map, resolve, global_max)

    for title, results in (('sr_boxscores.json', [(k, v, d) for k, v, d in sr_results]),
                           ('upset_history.json', [(k, v, d) for k, v, d, _ in up_results])):
        counts = Counter(v for _, v, _ in results)
        print('\n== {} : {} entries -> {}'.format(
            title, len(results), dict(sorted(counts.items()))))
        for verdict in ('CONTRADICTED', 'UNCHECKABLE'):
            for k, v, d in results:
                if v == verdict:
                    print('  [{}] {}\n      {}'.format(v, k, d))

    if apply_mode:
        print('\n== APPLY')
        ctx = (per_team, slug_map, resolve, global_max)
        for line in apply_corrections(ctx, up_results, sr_results):
            print('  ' + line)


if __name__ == '__main__':
    main()
