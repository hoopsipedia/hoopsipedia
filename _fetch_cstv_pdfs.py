#!/usr/bin/env python3
"""Download one school's cstv box PDFs from the CDX list via Wayback."""
import re, sys, time, urllib.request, os
sys.stdout.reconfigure(line_buffering=True)
school = sys.argv[1]
outdir = f'archives/cstv/{school}'
os.makedirs(outdir, exist_ok=True)
rows = []
for line in open('cstv_box_pdfs_full.txt'):
    parts = line.split()
    if len(parts) >= 2 and f'schools/{school}/' in parts[0]:
        rows.append((parts[0], parts[1]))
print(len(rows), 'PDFs listed')
ok = 0
for orig, ts in rows:
    name = re.sub(r'[^A-Za-z0-9._-]', '_', orig.rsplit('/', 1)[-1])
    dest = f'{outdir}/{name}'
    if os.path.exists(dest) and os.path.getsize(dest) > 5000:
        ok += 1; continue
    url = f'http://web.archive.org/web/{ts}id_/{orig}'
    for attempt in range(4):
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=120).read()
            if data.startswith(b'%PDF'):
                open(dest, 'wb').write(data); ok += 1
                print(f'{name}: {len(data):,}b')
            else:
                print(f'{name}: not pdf')
            break
        except Exception as e:
            if attempt == 3: print(f'{name}: FAIL {e}')
            else: time.sleep(20)
    time.sleep(1.0)
print(f'DONE {ok}/{len(rows)}')
