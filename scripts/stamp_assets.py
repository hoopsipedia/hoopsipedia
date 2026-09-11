#!/usr/bin/env python3
"""Stamp cache-busting versions onto index.html's external asset references.

index.html loads /app.css and /app.js (extracted from the old monolith so the
HTML shell is small and the assets cache independently). Browsers and the
service worker may hold either file for up to an hour, so every reference
carries a content hash: `<link href="/app.css?v=abc12345">`. A changed asset
therefore always arrives with a changed URL.

  python3 scripts/stamp_assets.py          # rewrite index.html in place
  python3 scripts/stamp_assets.py --check  # exit 1 if index.html is stale

The pre-push hook and CI run --check, mirroring the slice-freshness gates.
"""
import hashlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = ['app.css', 'app.js']


def short_hash(path):
    with open(path, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()[:10]


def main():
    check = '--check' in sys.argv
    html_path = os.path.join(ROOT, 'index.html')
    html = open(html_path, encoding='utf-8').read()
    updated = html
    for name in ASSETS:
        h = short_hash(os.path.join(ROOT, name))
        pattern = re.compile(r'(["\'])/' + re.escape(name) + r'\?v=[A-Za-z0-9]+\1')
        matches = pattern.findall(updated)
        if not matches:
            print(f'❌ index.html has no versioned reference to /{name}')
            sys.exit(1)
        updated = pattern.sub(lambda m: f'{m.group(1)}/{name}?v={h}{m.group(1)}', updated)
    if updated == html:
        print('✅ Asset versions are current')
        return
    if check:
        print('❌ index.html asset versions are stale — run python3 scripts/stamp_assets.py and commit')
        sys.exit(1)
    open(html_path, 'w', encoding='utf-8').write(updated)
    print('✅ Stamped asset versions into index.html')


if __name__ == '__main__':
    main()
