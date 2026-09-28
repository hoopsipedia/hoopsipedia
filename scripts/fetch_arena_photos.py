#!/usr/bin/env python3
"""Self-host the arena background photos as 500px Wikimedia Commons thumbnails.

Team profiles paint an arena photo at 6% opacity behind the header. Loading it
from upload.wikimedia.org set a third-party cookie (WMF-Uniq) on every team
page — Lighthouse best-practices 0.77 — and made the page depend on a host we
do not control. Commons only serves its step sizes (250/330/500/960/1280…),
so this fetches the 500px step of every photo in arena_photos.json into
arena/{espnId}.{jpg|png} and records the local path as `localImage`. The
credit line (photographer + license) is unchanged and still rendered.

  python3 scripts/fetch_arena_photos.py           # fetch missing/changed
  python3 scripts/fetch_arena_photos.py --force   # re-fetch everything
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'arena_photos.json')
OUT = os.path.join(ROOT, 'arena')
UA = 'Hoopsipedia/1.0 (https://www.hoopsipedia.com; arena photo cache)'
WIDTH = 500


def thumb_url(url, width=WIDTH):
    m = re.match(r'^(https?://upload\.wikimedia\.org/wikipedia/commons)/([0-9a-f])/([0-9a-f]{2})/([^/?#]+)$', url)
    if not m:
        return None, None
    name = m.group(4)
    ext = '.png' if name.lower().endswith(('.svg', '.png')) else '.jpg'
    return f'{m.group(1)}/thumb/{m.group(2)}/{m.group(3)}/{name}/{width}px-{name}{".png" if name.lower().endswith(".svg") else ""}', ext


def main():
    force = '--force' in sys.argv
    with open(SRC) as f:
        data = json.load(f)
    os.makedirs(OUT, exist_ok=True)
    fetched = skipped = failed = 0
    for eid, entry in data.items():
        if eid == 'metadata' or not isinstance(entry, dict) or not entry.get('imageUrl'):
            continue
        url, ext = thumb_url(entry['imageUrl'])
        if not url:
            print(f'  skip {eid}: not a Commons original URL')
            continue
        dest = os.path.join(OUT, f'{eid}{ext}')
        rel = f'/arena/{eid}{ext}'
        if not force and os.path.exists(dest) and entry.get('localImage') == rel and entry.get('sourceThumb') == url:
            skipped += 1
            continue
        try:
            body = None
            for attempt in range(4):
                try:
                    req = urllib.request.Request(url, headers={'User-Agent': UA})
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        body = resp.read()
                    break
                except urllib.error.HTTPError as e:
                    # Commons rate-limits thumbnail rendering hard (429 after ~20
                    # requests at 0.4s spacing); back off and retry.
                    if e.code == 429 and attempt < 3:
                        time.sleep(60 * (attempt + 1))
                        continue
                    raise
            if len(body) < 1000:
                raise ValueError(f'suspiciously small ({len(body)} bytes)')
            with open(dest + '.tmp', 'wb') as f:
                f.write(body)
            os.replace(dest + '.tmp', dest)
            entry['localImage'] = rel
            entry['sourceThumb'] = url
            fetched += 1
            print(f'  {eid} {entry.get("team", "")}: {len(body) // 1024} KB')
        except Exception as e:
            failed += 1
            print(f'  FAIL {eid} {entry.get("team", "")}: {e}')
        time.sleep(3)
    with open(SRC, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')
    total = sum(os.path.getsize(os.path.join(OUT, p)) for p in os.listdir(OUT)) / 1048576
    print(f'fetched {fetched}, unchanged {skipped}, failed {failed}; arena/ = {total:.1f} MiB')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
