#!/usr/bin/env python3
"""
Harvest historical AP poll data from Sports Reference season poll pages.

For each season 1949-2026, fetches /cbb/seasons/men/{year}-polls.html and
parses the weekly AP poll table into:
    ap_polls.json  — {"<season>": {"weeks": [{"date"|"label", "ranks": {rank: espnId|name}}...],
                      "final": {...}}}
Normalizes school names to ESPN team IDs via espn_to_sr.json + data.json
aliases; unmatched names are kept verbatim and reported.

Validation: every NCAA champion 1949-2026 must appear in its season's final
poll top 10 (poll eras vary; report any miss loudly rather than fail).

Usage: python3 harvest_ap_polls.py [--delay 3.2] [--start 1949] [--end 2026]
"""

import argparse
import json
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(line_buffering=True)

BASE = "https://www.sports-reference.com/cbb/seasons/men/{year}-polls.html"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def build_alias_index():
    """normalized school name -> espn id, from espn_to_sr + data.json names."""
    with open("espn_to_sr.json") as f:
        e2s = json.load(f)
    with open("data.json") as f:
        H = json.load(f)["H"]
    idx = {}
    for eid, slug in e2s.items():
        idx[norm(slug)] = eid
    for eid, fields in H.items():
        idx[norm(fields[0])] = eid       # full name
        # SR poll tables use school names (no mascot): strip last word(s)
        parts = fields[0].split()
        for cut in (1, 2):
            if len(parts) > cut:
                idx.setdefault(norm(" ".join(parts[:-cut])), eid)
    # common SR-specific spellings
    extra = {
        "unc": "153", "nc state": "152", "ole miss": "145", "lsu": "99",
        "smu": "2567", "byu": "252", "tcu": "2628", "ucla": "26",
        "usc": "30", "uconn": "41", "umass": "113", "unlv": "2439",
        "utep": "2638", "texas western": "2638", "memphis state": "235",
        "pitt": "221", "saint johns ny": "2599", "st johns": "2599",
        "st bonaventure": "179", "st louis": "139",
    }
    for k, v in extra.items():
        idx[norm(k)] = v
    return idx


def parse_polls_page(html):
    """Returns list of week-columns: [{'label': str, 'ranks': {name: rank}}]"""
    soup = BeautifulSoup(re.sub(r"<!--|-->", "", html), "html.parser")
    table = soup.find("table", id=re.compile("ap-polls"))
    if table is None:
        # fall back: first table containing 'Pre' or 'Final' header
        for t in soup.find_all("table"):
            head = t.find("thead")
            if head and ("Final" in head.get_text() or "Pre" in head.get_text()):
                table = t
                break
    if table is None:
        return None
    head_cells = [th.get_text(strip=True)
                  for th in table.find("thead").find_all("tr")[-1].find_all("th")]
    # first column is School (row header)
    week_labels = head_cells[1:]
    weeks = [{"label": lbl, "ranks": {}} for lbl in week_labels]
    for tr in table.find("tbody").find_all("tr"):
        th = tr.find("th")
        if th is None:
            continue
        school = th.get_text(strip=True)
        if not school or school == "School":
            continue
        for i, td in enumerate(tr.find_all("td")):
            txt = td.get_text(strip=True)
            if txt and txt.isdigit() and i < len(weeks):
                weeks[i]["ranks"][school] = int(txt)
    return weeks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=3.2)
    ap.add_argument("--start", type=int, default=1949)
    ap.add_argument("--end", type=int, default=2026)
    args = ap.parse_args()

    alias = build_alias_index()
    unmatched = {}
    out = {}

    for year in range(args.start, args.end + 1):
        url = BASE.format(year=year)
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
        except requests.RequestException as e:
            print(f"{year}: fetch error {e}")
            time.sleep(args.delay)
            continue
        time.sleep(args.delay)
        if r.status_code == 429:
            print(f"{year}: 429 — cooling off 15 min")
            time.sleep(900)
            continue
        if r.status_code != 200:
            print(f"{year}: http {r.status_code} (no polls page)")
            continue
        weeks = parse_polls_page(r.text)
        if not weeks:
            print(f"{year}: no AP table found")
            continue
        season_weeks = []
        for w in weeks:
            ranks = []  # list, not dict: AP ties give duplicate ranks
            for school, rank in sorted(w["ranks"].items(), key=lambda x: x[1]):
                eid = alias.get(norm(school))
                entry = {"rank": rank}
                if eid:
                    entry["id"] = eid
                else:
                    entry["name"] = school
                    unmatched.setdefault(school, 0)
                    unmatched[school] += 1
                ranks.append(entry)
            season_weeks.append({"label": w["label"], "ranks": ranks})
        out[str(year)] = {"weeks": season_weeks}
        n_weeks = len(season_weeks)
        n_teams = len(season_weeks[-1]["ranks"]) if season_weeks else 0
        print(f"{year}: {n_weeks} polls, final poll has {n_teams} teams")

    with open("ap_polls.json", "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"\nSeasons harvested: {len(out)}")
    print(f"Unmatched school names ({len(unmatched)}):")
    for k, v in sorted(unmatched.items(), key=lambda x: -x[1])[:40]:
        print(f"  {k}: {v} appearances")

    # validation: champions should appear high in final polls
    try:
        with open("data.json") as f:
            H = json.load(f)["H"]
        champs = {}
        for eid, fields in H.items():
            for y in fields[7] or []:
                champs[str(y)] = (eid, fields[0])
        misses = []; checked = 0
        for y, (eid, name) in sorted(champs.items()):
            season = out.get(y)
            if not season or not season["weeks"]:
                continue
            checked += 1
            final = season["weeks"][-1]["ranks"]
            rank = next((e["rank"] for e in final if e.get("id") == eid), None)
            if rank is None or rank > 10:
                misses.append((y, name, rank))
        print(f"\nChampion-in-final-poll check: {checked-len(misses)}/{checked} harvested-season champions in top 10")
        for y, name, rank in misses:
            print(f"  CHECK: {y} champion {name} final-poll rank = {rank}")
    except Exception as e:
        print("validation error:", e)


if __name__ == "__main__":
    main()
