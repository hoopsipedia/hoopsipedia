#!/usr/bin/env python3
"""Download Wichita State per-season box-score PDFs from goshockers.com.

Deep-hunt find: archive page links a 'Boxes' PDF for every season 1971-72 →
present. Sidearm wrapper variant: /documents/*.pdf pages embed the real file
at s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/wichita.sidearmsports.com/...
"""
import json, pathlib, re, sys, time, urllib.request

sys.stdout.reconfigure(line_buffering=True)
UA = {"User-Agent": "Mozilla/5.0"}
OUT = pathlib.Path("archives/wichitastate")
CUTOFF = 2002


def get(url, timeout=120):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    h = get("https://goshockers.com/sports/2015/6/26/MBB_Statistics.aspx").decode("utf-8", "replace")
    # season label near a Boxes document link; take hrefs whose filename has _Boxes/_boxes
    pairs = {}
    for m in re.finditer(r'href="([^"]*documents/[^"]*[Bb]oxes[^"]*\.pdf)"', h):
        url = m.group(1)
        fm = re.search(r'(\d{4})[_-]?(\d{2})[_A-Za-z]*[Bb]oxes', url)
        if not fm:
            continue
        season = f"{fm.group(1)}-{fm.group(2)}"
        if int(fm.group(1)) >= CUTOFF or season in pairs:
            continue
        pairs[season] = url if url.startswith("http") else "https://goshockers.com" + url
    print(f"{len(pairs)} pre-{CUTOFF} Boxes PDFs listed")
    manifest = {}
    for season, wrapper in sorted(pairs.items()):
        dest = OUT / f"{season}_boxscores.pdf"
        if dest.exists() and dest.stat().st_size > 10000:
            manifest[season] = "skipped"
            continue
        try:
            wh = get(wrapper).decode("utf-8", "replace")
            m = re.search(r'<object[^>]+data="(https://[^"]+)"', wh) or \
                re.search(r'(https://s3[^"\'<> ]+\.pdf)', wh)
            if not m:
                manifest[season] = "no_asset_url"
                print(f"{season}: no asset url")
                continue
            data = get(m.group(1))
            if not data.startswith(b"%PDF"):
                manifest[season] = f"not_pdf({len(data)}b)"
                continue
            dest.write_bytes(data)
            manifest[season] = f"{len(data):,}b"
            print(f"{season}: {len(data):,}b")
        except Exception as e:
            manifest[season] = f"error: {e}"
            print(f"{season}: ERROR {e}")
        time.sleep(1.5)
    json.dump(manifest, open(OUT / "download_manifest.json", "w"), indent=1)
    ok = sum(1 for v in manifest.values() if v.endswith("b") or v == "skipped")
    print(f"DONE: {ok}/{len(pairs)}")


if __name__ == "__main__":
    main()
