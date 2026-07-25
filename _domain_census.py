#!/usr/bin/env python3
"""Free CDX census: probe hunter-found athletics hosts for StatCrew box-score
archives against the 4 proven URL patterns. Counts box-matching files per
host/pattern via the Wayback CDX API (statuscode:200). No downloads — pure
census so we know which hosts to wire into harvest_statcrew.py SOURCE_DEFS.

Concurrent + legacy-first + resumable: probes the ~300 legacy-era hosts
(fansonly/cstv/ocsn/collegesports — where StatCrew boxes actually live) before
current/static hosts, runs a small thread pool so archive.org latency overlaps,
and writes _domain_census_results.json incrementally so it resumes on restart.
"""
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

WF_OUT = ('/private/tmp/claude-501/-Users-joshdavis-Projects-hoopsipedia/'
          '323f47a0-5c35-4b64-8513-ef1c9c62aa7a/tasks/w3wgapkfn.output')
RESULTS = '_domain_census_results.json'
WORKERS = 3  # dialed down to run gently in parallel with the wave-2 harvest

KNOWN = {
    'static.charlotte49ers.com', 'static.bgsufalcons.com', 'static.gocsucougars.com',
    'static.unipanthers.com', 'airforcesports.com', 'uconnhuskies.com', 'brownbears.com',
    'usfdons.com', 'ohiobobcats.com', 'thesundevils.com', 'calbears.com', 'clemsontigers.com',
    'umassathletics.com', 'bucknellbison.com', 'scarletknights.com', 'uncbears.fansonly.com',
    'goviks.fansonly.com', 'static.gohighlanders.com', 'wsuraiders.com',
}
LEGACY_MARKERS = ('fansonly', 'cstv', 'ocsn', 'collegesports')

PATTERNS = [
    ('m-baskbl', '/sports/m-baskbl/stats/*', re.compile(r'/stats/\d{6}[a-z]{3}\.html?$')),
    ('bko',      '/bko/bkc/*',               re.compile(r'/bko/bkc/.*box.*\.html?$', re.I)),
    ('mbb-boxes','/mbasketball/*',           re.compile(r'/mbasketball/\d{4}boxes/\d+\.html?$', re.I)),
    ('custompages', '/custompages/*',        re.compile(r'/custompages/.*\d{6}.*\.html?$', re.I)),
]

_lock = threading.Lock()


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 hoopsipedia-census'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def cdx_count(host, suffix, file_re, attempts=3):
    url = ('http://web.archive.org/cdx/search/cdx?url=' +
           urllib.parse.quote(host + suffix, safe='/*') +
           '&filter=statuscode:200&collapse=urlkey&fl=original&limit=6000&output=text')
    for i in range(attempts):
        try:
            body = get(url).decode('utf-8', 'replace')
            rows = [ln for ln in body.splitlines() if ln.strip()]
            matched = sum(1 for ln in rows if file_re.search(ln.split('?')[0]))
            return matched, len(rows)
        except Exception as e:
            if i == attempts - 1:
                return None, f'ERR:{type(e).__name__}'
            time.sleep(6)
    return None, 'ERR'


def probe_host(host, programs):
    rec = {'host': host, 'programs': sorted(programs), 'patterns': {}}
    best = 0
    for name, suffix, file_re in PATTERNS:
        matched, total = cdx_count(host, suffix, file_re)
        rec['patterns'][name] = {'boxes': matched, 'rows': total}
        if isinstance(matched, int):
            best = max(best, matched)
        if name == 'm-baskbl' and isinstance(matched, int) and matched >= 20:
            break  # healthy trove found; skip remaining patterns
        time.sleep(0.3)
    rec['best'] = best
    return rec


def host_of(s):
    s = s.strip().lower()
    s = re.sub(r'^https?://', '', s).split('/')[0]
    return s if ('.' in s and ' ' not in s) else None


def main():
    wf = json.load(open(WF_OUT))
    result = wf['result'] if isinstance(wf.get('result'), dict) else json.loads(wf['result'])
    programs = result['programs']

    host_progs = {}
    for p in programs:
        cands = []
        for key in ('current_domain', 'historical_domains'):
            v = p.get(key)
            cands += [v] if isinstance(v, str) else (v or [])
        cd = host_of(p.get('current_domain') or '')
        if cd and not cd.startswith('static.'):
            cands.append('static.' + cd)
        for c in cands:
            h = host_of(c)
            if h and h not in KNOWN:
                host_progs.setdefault(h, set()).add(p['program'])

    # legacy-era hosts first (highest yield), then the rest
    all_hosts = list(host_progs)
    legacy = sorted(h for h in all_hosts if any(m in h for m in LEGACY_MARKERS))
    other = sorted(h for h in all_hosts if h not in set(legacy))
    ordered = legacy + other
    print(f'{len(programs)} programs -> {len(ordered)} hosts ({len(legacy)} legacy-era first, then {len(other)})', flush=True)

    done = {}
    if os.path.exists(RESULTS):
        try:
            done = {r['host']: r for r in json.load(open(RESULTS))}
            print(f'resuming: {len(done)} hosts already probed', flush=True)
        except Exception:
            done = {}

    todo = [h for h in ordered if h not in done]
    results = list(done.values())
    n_done = len(done)

    def save():
        results.sort(key=lambda r: -r.get('best', 0))
        json.dump(results, open(RESULTS, 'w'), indent=1)

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(probe_host, h, host_progs[h]): h for h in todo}
        for fut in as_completed(futs):
            rec = fut.result()
            with _lock:
                results.append(rec)
                n_done += 1
                flag = '  <<< HIT' if rec['best'] >= 5 else ''
                print(f'[{n_done}/{len(ordered)}] {rec["host"]:40s} best={rec["best"]}{flag}', flush=True)
                if n_done % 10 == 0:
                    save()
        with _lock:
            save()

    results.sort(key=lambda r: -r.get('best', 0))
    hits = [r for r in results if r.get('best', 0) >= 5]
    print(f'\nCENSUS COMPLETE: {len(hits)} hosts with >=5 box files', flush=True)
    for r in hits[:80]:
        pats = ','.join(f'{k}={v["boxes"]}' for k, v in r['patterns'].items()
                        if isinstance(v.get('boxes'), int) and v['boxes'])
        print(f'  {r["best"]:5d}  {r["host"]:38s} [{pats}]  {",".join(r["programs"])[:45]}', flush=True)


if __name__ == '__main__':
    main()
