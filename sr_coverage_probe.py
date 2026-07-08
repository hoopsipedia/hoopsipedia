#!/usr/bin/env python3
"""
SR regular-season box-score coverage probe.

Samples team schedule pages across decades and counts how many games link
to a box score page, producing an evidence-based estimate of how much
pre-2002 regular-season box-score data actually exists on Sports Reference.

Output: sr_coverage_probe_results.json + human-readable log lines.
"""

import argparse
import json
import re
import sys
import time

import requests

sys.stdout.reconfigure(line_buffering=True)

SCHOOLS = ["duke", "kentucky", "kansas", "ucla", "north-carolina",
           "indiana", "villanova", "gonzaga"]
YEARS = [1955, 1965, 1975, 1985, 1990, 1995, 2000]
URL = "https://www.sports-reference.com/cbb/schools/{school}/men/{year}-schedule.html"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=3.2)
    args = ap.parse_args()

    results = []
    for year in YEARS:
        for school in SCHOOLS:
            url = URL.format(school=school, year=year)
            try:
                r = requests.get(url, headers=HEADERS, timeout=20)
            except requests.RequestException as e:
                results.append({"school": school, "year": year,
                                "status": f"error: {e}"})
                time.sleep(args.delay)
                continue
            time.sleep(args.delay)
            if r.status_code == 429:
                print(f"429 at {school}/{year} — probe cooling off 15 min")
                time.sleep(900)
                continue
            if r.status_code != 200:
                results.append({"school": school, "year": year,
                                "status": f"http {r.status_code}"})
                continue
            html = r.text
            # rows in the schedule table; box score links appear as
            # /cbb/boxscores/YYYY-MM-DD-*.html
            games = len(re.findall(r'csk="[^"]*"[^>]*data-stat="date_game"', html)) or \
                html.count('data-stat="opp_name"')
            box_links = len(set(re.findall(r'/cbb/boxscores/\d{4}-\d{2}-\d{2}-[^"]+\.html', html)))
            results.append({"school": school, "year": year, "status": "ok",
                            "games": games, "box_links": box_links})
            print(f"{year} {school:<16} games~{games:>3} box_links={box_links}")

    with open("sr_coverage_probe_results.json", "w") as f:
        json.dump(results, f, indent=1)

    # decade summary
    print("\n=== COVERAGE SUMMARY ===")
    for year in YEARS:
        rows = [x for x in results if x["year"] == year and x.get("status") == "ok"]
        if not rows:
            print(f"{year}: no data")
            continue
        g = sum(x["games"] for x in rows)
        b = sum(x["box_links"] for x in rows)
        pct = (100 * b / g) if g else 0
        print(f"{year}: {b}/{g} games with box links across {len(rows)} schools (~{pct:.0f}%)")


if __name__ == "__main__":
    main()
