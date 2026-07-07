#!/usr/bin/env python3
"""
Map ESPN event IDs for ALL games 2002-2026 (regular season + postseason).

For each team x season x seasontype, fetches the ESPN schedule API and
validates every event against our own game records (games_1/2/3.json)
before it can be merged: date (+/-1 day, ESPN uses UTC), both team IDs,
and both scores must match a record in our logs ("triple match").

Outputs:
  espn_event_map_progress.json  — checkpoint (resumable, per team-season)
  espn_event_map_matched.json   — validated entries, safe to merge
  espn_event_map_quarantine.json — everything else, with reasons

Run:  python3 map_all_espn_ids.py [--start-year 2002] [--end-year 2026]
"""

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from json_io import save_json_atomic

BASE_DIR = Path(__file__).resolve().parent

SCHEDULE_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/"
    "mens-college-basketball/teams/{tid}/schedule?season={year}&seasontype={stype}"
)

DELAY = 0.3
PROGRESS_PATH = BASE_DIR / "espn_event_map_progress.json"
MATCHED_PATH = BASE_DIR / "espn_event_map_matched.json"
QUAR_PATH = BASE_DIR / "espn_event_map_quarantine.json"
SAVE_EVERY = 40  # team-seasons between checkpoint writes


def fetch_json(url, retries=3):
    backoff = 1.0
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            })
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(30 * (attempt + 1))
            elif attempt < retries - 1:
                time.sleep(backoff)
                backoff *= 2
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt < retries - 1:
                time.sleep(backoff)
                backoff *= 2
    return None


def extract_score(competitor):
    score = competitor.get("score")
    if isinstance(score, dict):
        score = score.get("value", score.get("displayValue", 0))
    try:
        return int(float(score))
    except (ValueError, TypeError):
        return 0


def load_records():
    records = {}
    for fn in ("games_1.json", "games_2.json", "games_3.json"):
        with open(BASE_DIR / fn) as f:
            records.update(json.load(f))
    # index: (tid, date) -> list of game dicts, for +/-1-day lookups
    idx = {}
    for tid, v in records.items():
        games = v["games"] if isinstance(v, dict) else v
        for g in games:
            idx.setdefault((tid, g.get("date", "")), []).append(g)
    return records, idx


def near_dates(date_str):
    """The date itself plus +/-1 day (ESPN dates are UTC; ours are ET)."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return [date_str]
    return [
        (d + timedelta(days=off)).strftime("%Y-%m-%d") for off in (0, -1, 1)
    ]


def triple_match(idx, entry):
    """Return the matching local record's date, or None."""
    t1, t2, s1, s2 = entry["t1"], entry["t2"], entry["s1"], entry["s2"]
    for tid, opp, ms, os_ in ((t1, t2, s1, s2), (t2, t1, s2, s1)):
        for d in near_dates(entry["date"]):
            for rec in idx.get((str(tid), d), []):
                if rec.get("opp") == str(opp) and rec.get("pts") == ms \
                        and rec.get("opp_pts") == os_:
                    return rec.get("date")
    return None


def team_date_match(idx, entry):
    """Weaker match: teams + date only (for zero-score ESPN entries).
    Returns the local record (from t1's perspective) or None."""
    t1, t2 = entry["t1"], entry["t2"]
    for d in near_dates(entry["date"]):
        for rec in idx.get((str(t1), d), []):
            if rec.get("opp") == str(t2):
                return rec
    return None


def main():
    start_year, end_year = 2002, 2026
    args = sys.argv[1:]
    if "--start-year" in args:
        start_year = int(args[args.index("--start-year") + 1])
    if "--end-year" in args:
        end_year = int(args[args.index("--end-year") + 1])

    records, idx = load_records()
    team_ids = sorted(records.keys(), key=int)
    print(f"{len(team_ids)} teams, seasons {start_year}-{end_year}", flush=True)

    with open(BASE_DIR / "game_ids_bulk.json") as f:
        existing = set(json.load(f)["games"].keys())
    print(f"{len(existing)} event IDs already in game_ids_bulk.json", flush=True)

    progress = {"done": [], "matched": {}, "quarantine": {}}
    if PROGRESS_PATH.exists():
        with open(PROGRESS_PATH) as f:
            progress = json.load(f)
        print(f"Resuming: {len(progress['done'])} team-seasons done, "
              f"{len(progress['matched'])} matched so far", flush=True)
    done = set(progress["done"])
    matched = progress["matched"]
    quarantine = progress["quarantine"]

    def checkpoint():
        progress["done"] = sorted(done)
        save_json_atomic(PROGRESS_PATH, progress)

    pending_since_save = 0
    t0 = time.time()
    total_units = 0
    todo_units = []
    for year in range(start_year, end_year + 1):
        for stype in (2, 3):  # regular, postseason
            for tid in team_ids:
                key = f"{tid}:{year}:{stype}"
                total_units += 1
                if key not in done:
                    todo_units.append((tid, year, stype, key))

    print(f"{len(todo_units)}/{total_units} team-season units to fetch",
          flush=True)

    for n, (tid, year, stype, key) in enumerate(todo_units):
        data = fetch_json(SCHEDULE_URL.format(tid=tid, year=year, stype=stype))
        time.sleep(DELAY)
        done.add(key)
        pending_since_save += 1

        if data:
            for event in data.get("events", []):
                eid = str(event.get("id", ""))
                if not eid or eid in existing or eid in matched \
                        or eid in quarantine:
                    continue
                comps = event.get("competitions", [])
                if not comps:
                    continue
                comp = comps[0]
                competitors = comp.get("competitors", [])
                if len(competitors) < 2:
                    continue
                entry = {
                    "date": comp.get("date", event.get("date", ""))[:10],
                    "t1": str(competitors[0].get("team", {}).get("id", "")),
                    "t2": str(competitors[1].get("team", {}).get("id", "")),
                    "s1": extract_score(competitors[0]),
                    "s2": extract_score(competitors[1]),
                    "type": "postseason" if stype == 3 else "regular",
                }
                local_date = triple_match(idx, entry)
                if local_date:
                    entry["date"] = local_date  # normalize to our ET date
                    matched[eid] = entry
                elif entry["s1"] == 0 and entry["s2"] == 0:
                    rec = team_date_match(idx, entry)
                    if rec:
                        # ESPN has no score; take it from our record
                        entry["s1"], entry["s2"] = rec["pts"], rec["opp_pts"]
                        entry["date"] = rec["date"]
                        matched[eid] = entry
                    else:
                        quarantine[eid] = {**entry, "reason": "no-score-no-record"}
                else:
                    quarantine[eid] = {**entry, "reason": "no-triple-match"}

        if pending_since_save >= SAVE_EVERY:
            checkpoint()
            pending_since_save = 0
            rate = (n + 1) / max(time.time() - t0, 1)
            eta_h = (len(todo_units) - n - 1) / max(rate, 0.01) / 3600
            print(f"[{n+1}/{len(todo_units)}] matched={len(matched)} "
                  f"quarantined={len(quarantine)} eta={eta_h:.1f}h", flush=True)

    checkpoint()
    save_json_atomic(MATCHED_PATH, matched, separators=(",", ":"))
    save_json_atomic(QUAR_PATH, quarantine, indent=1)
    print(f"\nDONE: {len(matched)} matched, {len(quarantine)} quarantined",
          flush=True)


if __name__ == "__main__":
    main()
