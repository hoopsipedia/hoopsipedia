#!/usr/bin/env python3
"""Keep the box-score master out of the deploy, but safe in git.

Cloudflare Pages rejects any file over 25 MiB and, because there is no
build step, the repo root IS the deploy. sr_boxscores.json crossed that
line on 2026-07-24 (store 10,652 → 12,248 games) and every deploy from then
until 2026-09-11 failed silently — production sat on the July 24 build for
seven weeks while the store grew to 61 MB.

The site never needs the master file: it reads boxscores/{year}.json
slices (scripts/split_boxscores.py). So the master is now:

  * sr_boxscores.json      — local working copy, gitignored, read/written by
                             every harvest / merge / recap / players script
  * sr_boxscores.json.gz   — committed, ~7 MiB, deploys harmlessly, and is
                             the durable copy of the crown-jewel data

  python3 scripts/pack_store.py            # json -> gz (after any store change)
  python3 scripts/pack_store.py --unpack   # gz -> json (fresh clone)
  python3 scripts/pack_store.py --check    # exit 1 if the gz is stale

The pre-push hook and CI run --check, like the slice-freshness gates.
The gzip is written with a fixed mtime so identical content is byte-identical.
"""
import gzip
import hashlib
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(ROOT, 'sr_boxscores.json')
GZ_PATH = JSON_PATH + '.gz'


def sha(path, opener=open):
    h = hashlib.sha1()
    with opener(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def pack():
    with open(JSON_PATH, 'rb') as src, gzip.GzipFile(GZ_PATH, 'wb', compresslevel=9, mtime=0) as dst:
        shutil.copyfileobj(src, dst)
    print(f'✅ packed sr_boxscores.json ({os.path.getsize(JSON_PATH) / 1048576:.1f} MiB) -> '
          f'sr_boxscores.json.gz ({os.path.getsize(GZ_PATH) / 1048576:.1f} MiB)')


def unpack():
    with gzip.open(GZ_PATH, 'rb') as src, open(JSON_PATH + '.tmp', 'wb') as dst:
        shutil.copyfileobj(src, dst)
    os.replace(JSON_PATH + '.tmp', JSON_PATH)
    print(f'✅ unpacked sr_boxscores.json.gz -> sr_boxscores.json ({os.path.getsize(JSON_PATH) / 1048576:.1f} MiB)')


def check():
    if not os.path.exists(GZ_PATH):
        print('❌ sr_boxscores.json.gz is missing — run python3 scripts/pack_store.py')
        sys.exit(1)
    if not os.path.exists(JSON_PATH):
        print('✅ sr_boxscores.json.gz present (no local master to compare)')
        return
    if os.path.getmtime(JSON_PATH) > os.path.getmtime(GZ_PATH):
        # mtime says the master changed after the last pack; confirm by content
        if sha(JSON_PATH) != sha(GZ_PATH, gzip.open):
            print('❌ sr_boxscores.json is newer than sr_boxscores.json.gz — run python3 scripts/pack_store.py and commit the .gz')
            sys.exit(1)
    print('✅ sr_boxscores.json.gz is current')


if __name__ == '__main__':
    if '--unpack' in sys.argv:
        unpack()
    elif '--check' in sys.argv:
        check()
    else:
        pack()
