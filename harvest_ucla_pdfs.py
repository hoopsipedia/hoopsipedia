#!/usr/bin/env python3
"""Download UCLA per-season box-score PDFs from uclabruins.com archives.

The archive page lists each season as `<strong>YYYY-YY Season</strong>` followed by
links; the "Box Scores (PDF)" href (/documents/{uuid}.pdf) returns an HTML wrapper
whose <object data="..."> points at the real PDF on storage.googleapis.com.
"""
import re, sys, time, json, pathlib, urllib.request

BASE = "https://uclabruins.com"
ARCHIVE_URL = f"{BASE}/ucla-basketball-archives"
OUT_DIR = pathlib.Path("archives/ucla")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read()


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html = get(ARCHIVE_URL).decode("utf-8", "replace")

    # season blocks: <strong>2025-26 Season</strong> ... links until next <strong>
    pairs = []  # (season, wrapper_url)
    blocks = re.split(r"<strong>", html)
    for b in blocks:
        m = re.match(r"(\d{4}-\d{2})\s*Season", b)
        if not m:
            continue
        season = m.group(1)
        link = re.search(r'href="(/documents/[^"]+\.pdf)"[^>]*>Box Scores \(PDF\)', b)
        if link:
            pairs.append((season, BASE + link.group(1)))

    print(f"{len(pairs)} seasons with Box Scores (PDF)")
    manifest = {}
    for season, wrapper_url in pairs:
        dest = OUT_DIR / f"{season}_boxscores.pdf"
        if dest.exists() and dest.stat().st_size > 10000:
            manifest[season] = {"file": str(dest), "skipped": True}
            continue
        try:
            wrapper = get(wrapper_url).decode("utf-8", "replace")
            m = re.search(r'(https://storage\.googleapis\.com/[^"\'<> ]+)', wrapper)
            if not m:
                print(f"{season}: NO storage URL in wrapper {wrapper_url}", flush=True)
                manifest[season] = {"error": "no_storage_url", "wrapper": wrapper_url}
                continue
            pdf_url = m.group(1)
            data = get(pdf_url, timeout=120)
            if not data.startswith(b"%PDF"):
                print(f"{season}: not a PDF ({len(data)} bytes) {pdf_url}", flush=True)
                manifest[season] = {"error": "not_pdf", "url": pdf_url}
                continue
            dest.write_bytes(data)
            manifest[season] = {"file": str(dest), "bytes": len(data), "url": pdf_url}
            print(f"{season}: {len(data):,} bytes", flush=True)
        except Exception as e:
            print(f"{season}: ERROR {e}", flush=True)
            manifest[season] = {"error": str(e), "wrapper": wrapper_url}
        time.sleep(1.5)

    (OUT_DIR / "download_manifest.json").write_text(json.dumps(manifest, indent=1))
    ok = sum(1 for v in manifest.values() if "file" in v)
    print(f"done: {ok}/{len(pairs)} PDFs")


if __name__ == "__main__":
    main()
