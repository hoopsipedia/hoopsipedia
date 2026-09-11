#!/usr/bin/env python3
"""Tell IndexNow-participating search engines (Bing, Yandex, Seznam, Naver…)
which URLs changed. Google does not use IndexNow — resubmit sitemap.xml in
Search Console for Google.

The key is public by design (IndexNow verifies ownership by fetching
/indexnow-<key>.txt from the site), so it lives in the repo.

  python3 scripts/indexnow_ping.py                 # section pages + team pages + rivalries
  python3 scripts/indexnow_ping.py --all-seasons   # also the 26K season pages (batched)
  python3 scripts/indexnow_ping.py URL [URL...]    # specific URLs

Run after a deploy that adds or materially changes pages.
"""
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = "f3733ad6f50e0a718789bf17db782aab"
HOST = "www.hoopsipedia.com"
ENDPOINT = "https://api.indexnow.org/indexnow"


def urls_from_sitemap(name):
    xml = open(os.path.join(ROOT, name)).read()
    return re.findall(r"<loc>([^<]+)</loc>", xml)


def submit(urls):
    sent = 0
    for i in range(0, len(urls), 10000):
        batch = urls[i:i + 10000]
        body = json.dumps({"host": HOST, "key": KEY, "keyLocation": f"https://{HOST}/indexnow-{KEY}.txt", "urlList": batch}).encode()
        req = urllib.request.Request(ENDPOINT, data=body, headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                print(f"  batch of {len(batch)}: HTTP {r.status}")
        except urllib.error.HTTPError as e:
            print(f"  batch of {len(batch)}: HTTP {e.code} {e.read()[:200]!r}")
            return sent
        sent += len(batch)
    return sent


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        urls = args
    else:
        urls = urls_from_sitemap("sitemap-core.xml") + urls_from_sitemap("sitemap-teams.xml") + urls_from_sitemap("sitemap-coaches.xml")
        if "--all-seasons" in sys.argv:
            for n in (1, 2, 3):
                p = os.path.join(ROOT, f"sitemap-seasons-{n}.xml")
                if os.path.exists(p):
                    urls += urls_from_sitemap(f"sitemap-seasons-{n}.xml")
    urls = list(dict.fromkeys(urls))
    print(f"submitting {len(urls)} URLs to IndexNow")
    print(f"submitted {submit(urls)}")


if __name__ == "__main__":
    main()
