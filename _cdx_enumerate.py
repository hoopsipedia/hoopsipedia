#!/usr/bin/env python3
"""Full paged CDX enumeration: every m-baskbl box PDF on grfx.cstv.com."""
import urllib.request, time, sys
sys.stdout.reconfigure(line_buffering=True)
OUT='/private/tmp/claude-501/-Users-joshdavis-Projects-hoopsipedia/1fb24a29-95f3-4629-84b1-969add39a738/scratchpad/cstv_box_pdfs_full.txt'
BASE=('http://web.archive.org/cdx/search/cdx?url=grfx.cstv.com/photos/schools/*'
      r'&filter=original:.*m-baskbl.*box.*\.pdf&collapse=urlkey&fl=original,timestamp')
total=0
with open(OUT,'w') as f:
    page=0
    while page < 1104:
        try:
            req=urllib.request.Request(f'{BASE}&page={page}', headers={'User-Agent':'Mozilla/5.0'})
            data=urllib.request.urlopen(req, timeout=180).read().decode()
        except Exception as e:
            print(f'page {page}: {type(e).__name__}; wait 60s'); time.sleep(60); continue
        rows=[l for l in data.splitlines() if l.strip()]
        for r in rows: f.write(r+'\n')
        total+=len(rows)
        if rows: print(f'page {page}: +{len(rows)} (total {total})')
        page+=1
        time.sleep(2.5)
print(f'FULL ENUMERATION COMPLETE: {total} box PDFs')
