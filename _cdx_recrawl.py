#!/usr/bin/env python3
"""Re-crawl ONLY the 109 CDX pages that had matches (from cdx_enum.log)."""
import re, time, urllib.request, sys
sys.stdout.reconfigure(line_buffering=True)
OUT = 'cstv_box_pdfs_full.txt'
BASE = ('http://web.archive.org/cdx/search/cdx?url=grfx.cstv.com/photos/schools/*'
        r'&filter=original:.*m-baskbl.*box.*\.pdf&collapse=urlkey&fl=original,timestamp')
pages = sorted({int(x) for x in re.findall(r'page (\d+): \+', open('cdx_enum.log').read())})
print(f'{len(pages)} pages to re-crawl')
total = 0
with open(OUT, 'w') as f:
    for page in pages:
        for attempt in range(5):
            try:
                req = urllib.request.Request(f'{BASE}&page={page}', headers={'User-Agent': 'Mozilla/5.0'})
                data = urllib.request.urlopen(req, timeout=180).read().decode()
                rows = [l for l in data.splitlines() if l.strip()]
                for r in rows:
                    f.write(r + '\n')
                f.flush()
                total += len(rows)
                print(f'page {page}: +{len(rows)} (total {total})')
                break
            except Exception as e:
                print(f'page {page}: {type(e).__name__}; wait 45s')
                time.sleep(45)
        time.sleep(2.5)
print(f'RECRAWL COMPLETE: {total}')
