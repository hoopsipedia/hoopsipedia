#!/usr/bin/env python3
"""Keep the big JSON masters out of the deploy, but safe in git.

Cloudflare Pages rejects any file over 25 MiB and, because there is no
build step, the repo root IS the deploy. sr_boxscores.json crossed that
line on 2026-07-24 (store 10,652 → 12,248 games) and every deploy from then
until 2026-09-11 failed silently — production sat on the July 24 build for
seven weeks while the store grew to 61 MB. games_1/2/3.json were next in
line (21 MB each in Sept 2026), so they get the same treatment.

The site never needs a master file: it reads boxscores/{year}.json and
games/{espnId}.json slices (scripts/split_boxscores.py, split_games.py).
So each master is now:

  * <name>.json      — local working copy, gitignored, read/written by
                       every harvest / merge / recap / engine script
  * <name>.json.gz   — committed, deploys harmlessly, and is the durable copy

  python3 scripts/pack_store.py            # json -> gz for every master that changed
  python3 scripts/pack_store.py --unpack   # gz -> json (fresh clone / cloud session)
  python3 scripts/pack_store.py --check    # exit 1 if any gz is stale or missing
  python3 scripts/pack_store.py games_1.json   # just one master (any mode)

The pre-push hook and CI run --check, like the slice-freshness gates.
The gzip is written with a fixed mtime so identical content is byte-identical.
"""
import gzip
import hashlib
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTERS = ['sr_boxscores.json', 'games_1.json', 'games_2.json', 'games_3.json']


def paths(name):
    j = os.path.join(ROOT, name)
    return j, j + '.gz'


def sha(path, opener=open):
    h = hashlib.sha1()
    with opener(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def is_current(name):
    """True when <name>.json.gz holds exactly what <name>.json holds."""
    json_path, gz_path = paths(name)
    if not os.path.exists(gz_path):
        return False
    if os.path.getmtime(json_path) <= os.path.getmtime(gz_path):
        return True
    return sha(json_path) == sha(gz_path, gzip.open)


def pack(name):
    json_path, gz_path = paths(name)
    if not os.path.exists(json_path):
        print(f'⏭  {name} not present locally, leaving {name}.gz as is')
        return
    if is_current(name):
        print(f'✅ {name}.gz already current')
        return
    with open(json_path, 'rb') as src, gzip.GzipFile(gz_path, 'wb', compresslevel=9, mtime=0) as dst:
        shutil.copyfileobj(src, dst)
    print(f'✅ packed {name} ({os.path.getsize(json_path) / 1048576:.1f} MiB) -> '
          f'{name}.gz ({os.path.getsize(gz_path) / 1048576:.1f} MiB)')


def unpack(name):
    json_path, gz_path = paths(name)
    if not os.path.exists(gz_path):
        print(f'❌ {name}.gz is missing')
        sys.exit(1)
    with gzip.open(gz_path, 'rb') as src, open(json_path + '.tmp', 'wb') as dst:
        shutil.copyfileobj(src, dst)
    os.replace(json_path + '.tmp', json_path)
    print(f'✅ unpacked {name}.gz -> {name} ({os.path.getsize(json_path) / 1048576:.1f} MiB)')


def check(name):
    json_path, gz_path = paths(name)
    if not os.path.exists(gz_path):
        print(f'❌ {name}.gz is missing — run python3 scripts/pack_store.py')
        return False
    if not os.path.exists(json_path):
        print(f'✅ {name}.gz present (no local master to compare)')
        return True
    if not is_current(name):
        print(f'❌ {name} is newer than {name}.gz — run python3 scripts/pack_store.py and commit the .gz')
        return False
    print(f'✅ {name}.gz is current')
    return True


if __name__ == '__main__':
    names = [a for a in sys.argv[1:] if not a.startswith('--')] or MASTERS
    unknown = [n for n in names if n not in MASTERS]
    if unknown:
        sys.exit(f'unknown master(s) {unknown}; known: {MASTERS}')
    if '--unpack' in sys.argv:
        for n in names:
            unpack(n)
    elif '--check' in sys.argv:
        ok = all([check(n) for n in names])
        sys.exit(0 if ok else 1)
    else:
        for n in names:
            pack(n)
