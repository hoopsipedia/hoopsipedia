#!/usr/bin/env python3
"""Patiently download Louisville box-score PDFs from the legacy CDN.
One attempt per 10 min; on 503, wait 30 min. Wrapper HTML files in
archives/louisville/ hold the real grfx.cstv.com URLs in their <title>."""
import glob, html, os, re, time, urllib.request
import sys
sys.stdout.reconfigure(line_buffering=True)

def targets():
    out = []
    for f in sorted(glob.glob('archives/louisville/*.pdf')):
        head = open(f, errors='ignore').read(800)
        if head.startswith('%PDF'):
            continue
        m = re.search(r'<title>([^ ]+\.pdf)', head)
        if m:
            out.append((f, html.unescape(m.group(1))))
    return out

while True:
    todo = targets()
    if not todo:
        print('ALL LOUISVILLE PDFS DOWNLOADED')
        break
    f, url = todo[0]
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'})
        data = urllib.request.urlopen(req, timeout=60).read()
        if data[:4] == b'%PDF':
            open(f, 'wb').write(data)
            print(f'{time.strftime("%H:%M")} OK {os.path.basename(f)} ({len(data)//1024}KB) — {len(todo)-1} left')
            time.sleep(600)
        else:
            print(f'{time.strftime("%H:%M")} non-pdf for {os.path.basename(f)}; waiting 30m')
            time.sleep(1800)
    except Exception as e:
        print(f'{time.strftime("%H:%M")} {type(e).__name__} for {os.path.basename(f)}; waiting 30m')
        time.sleep(1800)
