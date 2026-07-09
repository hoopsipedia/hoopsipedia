#!/usr/bin/env python3
"""Download pre-2002 season box-score PDFs for Ohio State, Virginia, New Mexico.

OSU: direct .pdf links on the all-time-box-scores page (1928-29 → present).
UVA / UNM: sidearm-style index pages whose /documents/{uuid}.pdf links are HTML
wrappers; the real PDF lives at an embedded storage.googleapis.com URL
(same quirk as uclabruins.com — see harvest_ucla_pdfs.py).
"""
import json, pathlib, re, sys, time, urllib.request

sys.stdout.reconfigure(line_buffering=True)
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
CUTOFF = 2002  # season starting year < CUTOFF (pre-ESPN coverage)


def get(url, timeout=120):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read()


def season_start(season):  # "1928-29" -> 1928
    m = re.match(r"(\d{4})-\d{2}$", season)
    return int(m.group(1)) if m else None


def resolve_wrapper(url):
    """Sidearm /documents/*.pdf wrapper -> storage.googleapis.com asset URL."""
    html = get(url).decode("utf-8", "replace")
    m = re.search(r'(https://storage\.googleapis\.com/[^"\'<> ]+)', html)
    return m.group(1) if m else None


def download(url, dest, wrapper=False):
    if dest.exists() and dest.stat().st_size > 10000:
        return "skipped"
    if wrapper:
        url = resolve_wrapper(url)
        if not url:
            return "no_storage_url"
    data = get(url)
    if not data.startswith(b"%PDF"):
        return f"not_pdf({len(data)}b)"
    dest.write_bytes(data)
    return f"{len(data):,}b"


def osu_pairs():
    h = get("https://ohiostatebuckeyes.com/sports/2023/6/5/mens-basketball-all-time-box-scores").decode("utf-8", "replace")
    out = []
    for u in re.findall(r'href="(https://ohiostatebuckeyes\.com/images/[^"]+\.pdf)"', h):
        season = pathlib.Path(u).stem
        if (y := season_start(season)) and y < CUTOFF:
            out.append((season, u, False))
    return out


def sidearm_pairs(index_url, base):
    h = get(index_url).decode("utf-8", "replace")
    out, seen = [], set()
    # rows pair a season label with a Box Scores document link
    for m in re.finditer(r'(\d{4}-\d{2})[^<]{0,80}?</[^>]+>.{0,400}?href="(/documents/[^"]+\.pdf)"', h, re.S):
        season, path = m.group(1), m.group(2)
        if season in seen or not (y := season_start(season)) or y >= CUTOFF:
            continue
        seen.add(season)
        out.append((season, base + path, True))
    return out


SOURCES = {
    "ohiostate": osu_pairs,
    "virginia": lambda: sidearm_pairs("https://virginiasports.com/all-time-boxscores-listed-by-season", "https://virginiasports.com"),
    "newmexico": lambda: sidearm_pairs("https://golobos.com/new-mexico-mens-basketball-historical-stats-box-scores", "https://golobos.com"),
}


def main():
    manifest = {}
    for school, enum in SOURCES.items():
        outdir = pathlib.Path(f"archives/{school}")
        outdir.mkdir(parents=True, exist_ok=True)
        try:
            pairs = enum()
        except Exception as e:
            print(f"{school}: INDEX FAILED {e}")
            manifest[school] = {"error": str(e)}
            continue
        print(f"{school}: {len(pairs)} pre-{CUTOFF} season PDFs listed")
        results = {}
        for season, url, wrapper in pairs:
            dest = outdir / f"{season}_boxscores.pdf"
            try:
                status = download(url, dest, wrapper)
            except Exception as e:
                status = f"error: {e}"
            results[season] = status
            print(f"  {school} {season}: {status}")
            time.sleep(1.5)
        manifest[school] = results
        json.dump(manifest, open("scan_pdf_manifest.json", "w"), indent=1)
    ok = sum(1 for s in manifest.values() if isinstance(s, dict)
             for v in s.values() if isinstance(v, str) and (v.endswith("b") or v == "skipped"))
    print(f"DONE: {ok} PDFs on disk")


if __name__ == "__main__":
    main()
