#!/usr/bin/env python3
"""
Backfill missing 2026 postseason games into games_1/2/3.json.

Game logs were snapshotted mid-March 2026: NCAA tournament (and some
NIT) games are absent — including the champion's entire run. For each
team, fetches the ESPN 2026 postseason schedule (seasontype=3) and
appends completed games that are missing from the log.

Safety:
- Only completed events are considered.
- A game is "missing" only if no existing record matches opp + date
  (+/-1 day); existing rows are never modified.
- ESPN UTC timestamps are converted to ET (EDT, UTC-4: all 2026
  postseason dates fall after the Mar 8 DST switch).
- Appends go to each team's winning part file under split_games.py's
  last-wins merge semantics.
- Cross-checks every appended game against game_ids_bulk.json entries
  when the event is mapped there; any score disagreement aborts.
- Dry-run by default; pass --write to persist.
"""

import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from json_io import save_json_atomic

BASE_DIR = Path(__file__).resolve().parent
PART_FILES = ["games_1.json", "games_2.json", "games_3.json"]
SCHEDULE_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/"
    "mens-college-basketball/teams/{tid}/schedule?season=2026&seasontype=3"
)
DELAY = 0.3


def fetch_json(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            })
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                json.JSONDecodeError):
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
    return None


def utc_to_et_date(iso_ts):
    """ESPN gives UTC like 2026-04-07T01:00Z; 2026 postseason is EDT."""
    ts = iso_ts.replace("Z", "")
    try:
        dt = datetime.strptime(ts[:16], "%Y-%m-%dT%H:%M")
    except ValueError:
        return iso_ts[:10]
    return (dt - timedelta(hours=4)).strftime("%Y-%m-%d")


def near(d1, d2):
    try:
        a = datetime.strptime(d1, "%Y-%m-%d")
        b = datetime.strptime(d2, "%Y-%m-%d")
        return abs((a - b).days) <= 1
    except ValueError:
        return False


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def extract_score(competitor):
    score = competitor.get("score")
    if isinstance(score, dict):
        score = score.get("value", score.get("displayValue", 0))
    try:
        return int(float(score))
    except (ValueError, TypeError):
        return 0


def main():
    write = "--write" in sys.argv

    parts = {fn: json.load(open(BASE_DIR / fn)) for fn in PART_FILES}
    # winning part per team under last-wins merge
    winner = {}
    for fn in PART_FILES:
        for tid in parts[fn]:
            winner[str(tid)] = fn
    merged = {}
    for fn in PART_FILES:
        merged.update(parts[fn])

    with open(BASE_DIR / "game_ids_bulk.json") as f:
        bulk = json.load(f)["games"]

    def entry_games(tid):
        v = merged[tid]
        return v["games"] if isinstance(v, dict) else v

    def slug_for(tid, espn_team):
        v = merged.get(str(tid))
        if isinstance(v, dict) and v.get("slug"):
            return v["slug"]
        loc = espn_team.get("location") or espn_team.get("displayName") or tid
        return slugify(loc)

    team_ids = sorted(merged.keys(), key=int)
    additions = {}       # tid -> [records]
    bulk_checked = 0
    bulk_conflicts = []
    seen_events = {}     # eid -> (tid) to sanity-track both sides

    for i, tid in enumerate(team_ids):
        data = fetch_json(SCHEDULE_URL.format(tid=tid))
        time.sleep(DELAY)
        if not data:
            continue
        existing = entry_games(tid)
        for event in data.get("events", []):
            eid = str(event.get("id", ""))
            comps = event.get("competitions", [])
            if not comps:
                continue
            comp = comps[0]
            status = (comp.get("status") or event.get("competitions", [{}])[0]
                      .get("status") or {}).get("type", {})
            if not status.get("completed", False):
                continue
            competitors = comp.get("competitors", [])
            if len(competitors) < 2:
                continue
            me = next((c for c in competitors
                       if str(c.get("team", {}).get("id")) == tid), None)
            opp = next((c for c in competitors
                        if str(c.get("team", {}).get("id")) != tid), None)
            if not me or not opp:
                continue
            opp_id = str(opp.get("team", {}).get("id", ""))
            gdate = utc_to_et_date(comp.get("date", event.get("date", "")))
            # already in the log?
            if any(rec.get("opp") == opp_id and near(rec.get("date", ""), gdate)
                   for rec in existing):
                continue
            pts, opp_pts = extract_score(me), extract_score(opp)
            if pts == 0 and opp_pts == 0:
                continue  # no score data; skip rather than guess
            # cross-check against the bulk event map when present
            if eid in bulk:
                b = bulk[eid]
                pair = {str(b["t1"]): b["s1"], str(b["t2"]): b["s2"]}
                if pair.get(tid) != pts or pair.get(opp_id) != opp_pts:
                    bulk_conflicts.append((eid, tid, pts, opp_pts, b))
                else:
                    bulk_checked += 1
            loc = "N" if comp.get("neutralSite") else (
                "H" if me.get("homeAway") == "home" else "A")
            rec = {
                "date": gdate,
                "opp_slug": slug_for(opp_id, opp.get("team", {})),
                "loc": loc,
                "w": pts > opp_pts,
                "pts": pts,
                "opp_pts": opp_pts,
                "opp": opp_id,
            }
            venue = (comp.get("venue") or {}).get("fullName")
            if venue:
                rec["arena"] = venue
            period = status.get("period") or (comp.get("status") or {}).get("period")
            # status.type has no period; comp.status.period holds it
            period = (comp.get("status") or {}).get("period", 2)
            if isinstance(period, int) and period > 2:
                # games-file convention is the display string ('OT', '2OT'),
                # not an int — generate_on_this_day parses g['ot'][:-2]
                n_ot = period - 2
                rec["ot"] = "OT" if n_ot == 1 else "{}OT".format(n_ot)
            additions.setdefault(tid, []).append(rec)
            seen_events.setdefault(eid, []).append(tid)
        if (i + 1) % 75 == 0:
            print(f"  {i+1}/{len(team_ids)} teams, "
                  f"{sum(len(v) for v in additions.values())} additions so far",
                  flush=True)

    total = sum(len(v) for v in additions.values())
    print(f"\nTeams with additions: {len(additions)} | games to add: {total}")
    print(f"Cross-checked vs game_ids_bulk: {bulk_checked} agree, "
          f"{len(bulk_conflicts)} conflicts")
    if bulk_conflicts:
        for c in bulk_conflicts[:10]:
            print("  CONFLICT:", c)
        print("ABORTING — resolve conflicts first.")
        sys.exit(1)

    # summary of notable runs
    for tid, label in (("130", "Michigan"), ("150", "Duke"), ("41", "UConn")):
        if tid in additions:
            adds = sorted(additions[tid], key=lambda r: r["date"])
            print(f"  {label}: +{len(adds)} -> "
                  + ", ".join(f"{r['date']} {'W' if r['w'] else 'L'} "
                              f"{r['pts']}-{r['opp_pts']}" for r in adds))

    if not write:
        print("\nDRY RUN — rerun with --write to persist.")
        return

    # persist: append into each team's winning part file, sorted by date
    touched = set()
    for tid, recs in additions.items():
        fn = winner[tid]
        entry = parts[fn][tid]
        games = entry["games"] if isinstance(entry, dict) else entry
        games.extend(recs)
        games.sort(key=lambda r: r.get("date", ""))
        touched.add(fn)
    for fn in touched:
        save_json_atomic(BASE_DIR / fn, parts[fn], separators=(",", ":"))
        # re-parse to verify integrity
        json.load(open(BASE_DIR / fn))
        print(f"wrote {fn}")
    print(f"DONE: {total} games appended across {len(touched)} part files.")


if __name__ == "__main__":
    main()
