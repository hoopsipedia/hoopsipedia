#!/usr/bin/env python3
"""Invariant regression tests for Hoopsipedia's ranking-engine data files.

Pure stdlib, no pytest. Run as:  python3 tests/test_engine_invariants.py

These are INVARIANT tests, not golden-value snapshots: the underlying data
files are regenerated as game coverage improves, so we assert structural and
mathematical properties that must hold for ANY correct regeneration, never
exact current numbers.

Files covered:
  - efficiency_ratings.json   (efficiency engine output)
  - htss_v2_results.json      (HTSS v2 team-season rankings)
  - unified_rankings.json     (unified program / season rankings)
  - data.json                 (H team table)
  - on_this_day.json          (daily events)
  - games_1.json / games_2.json / games_3.json (per-team game logs)
  - seasons.json              (per-team season histories)

Exit code 1 on any FAIL. See tests/README.md for documented invariant
decisions and the SKIP list policy.
"""

import datetime
import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Checks listed here are reported loudly as SKIP instead of FAIL.
# Each entry: check name -> reason (documented in tests/README.md).
# Do NOT add entries to silently weaken invariants -- only for confirmed
# data issues awaiting an upstream fix.
KNOWN_DATA_ISSUES = {}

_failures = 0
_passes = 0
_skips = 0


def check(name, ok, detail=""):
    global _failures, _passes, _skips
    if name in KNOWN_DATA_ISSUES:
        _skips += 1
        print("SKIP  %s -- KNOWN DATA ISSUE: %s" % (name, KNOWN_DATA_ISSUES[name]))
        print("      *** WARNING: this invariant is suspended, not satisfied. "
              "See tests/README.md ***")
        return
    if ok:
        _passes += 1
        print("PASS  %s" % name)
    else:
        _failures += 1
        print("FAIL  %s -- %s" % (name, detail))


def _reject_constant(token):
    raise ValueError("non-finite JSON constant leaked into file: %r" % token)


def load(fname):
    """Parse JSON, rejecting NaN/Infinity tokens outright."""
    path = os.path.join(ROOT, fname)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f, parse_constant=_reject_constant)


def is_num(v):
    """Finite real number (bool excluded)."""
    if isinstance(v, bool):
        return True is False  # bools are never valid numerics here
    if isinstance(v, int):
        return True
    if isinstance(v, float):
        return math.isfinite(v)
    return False


def is_nonneg_int(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def first_bad(items):
    """Format a small sample of offending items for the FAIL detail."""
    sample = items[:3]
    extra = "" if len(items) <= 3 else " (+%d more)" % (len(items) - 3)
    return "%s%s" % (sample, extra)


# --------------------------------------------------------------------------
# efficiency_ratings.json
# --------------------------------------------------------------------------

def test_efficiency_ratings():
    name = "efficiency_ratings.json"
    try:
        d = load(name)
    except Exception as e:
        check(name + ": parses", False, str(e))
        return
    check(name + ": parses", True)

    seasons = d.get("seasons")
    ok = isinstance(seasons, dict) and len(seasons) >= 70
    check(name + ": covers >= 70 seasons", ok,
          "got %s seasons" % (len(seasons) if isinstance(seasons, dict) else "non-dict"))
    if not isinstance(seasons, dict):
        return

    bad_fields = []
    bad_identity = []
    bad_avgs = []
    for season, teams in seasons.items():
        if not isinstance(teams, dict) or not teams:
            bad_fields.append((season, "season is not a non-empty dict"))
            continue
        ems = []
        for tid, t in teams.items():
            if not isinstance(t, dict):
                bad_fields.append((season, tid, "not a dict"))
                continue
            vals = {}
            broken = False
            for f in ("adjOE", "adjDE", "adjEM"):
                v = t.get(f)
                if not is_num(v):
                    bad_fields.append((season, tid, f, repr(v)))
                    broken = True
                else:
                    vals[f] = v
            if broken:
                continue
            if abs(vals["adjEM"] - (vals["adjOE"] - vals["adjDE"])) > 0.1:
                bad_identity.append((season, tid, vals))
            ems.append(vals["adjEM"])
        if ems:
            avg = sum(ems) / len(ems)
            if abs(avg) > 1.0:
                bad_avgs.append((season, round(avg, 3)))

    check(name + ": adjOE/adjDE/adjEM all numeric, no NaN/null leakage",
          not bad_fields, first_bad(bad_fields))
    check(name + ": adjEM == adjOE - adjDE (tol 0.1)",
          not bad_identity, first_bad(bad_identity))
    check(name + ": league-average adjEM per season ~= 0 (tol 1.0)",
          not bad_avgs, first_bad(bad_avgs))


# --------------------------------------------------------------------------
# htss_v2_results.json
# --------------------------------------------------------------------------

# Blue-blood matchers (lowercased team name). Word-anchored so e.g.
# 'North Carolina State' and 'Kansas State' do NOT count.
BLUE_BLOODS = {
    "UCLA": re.compile(r"\bucla\b"),
    "Kentucky": re.compile(r"^kentucky\b"),
    "North Carolina": re.compile(r"^north carolina (?!state)"),
    "Duke": re.compile(r"^duke\b"),
    "Kansas": re.compile(r"^kansas (?!state)"),
}


def blue_blood_hits(team_names):
    lowered = [str(n).lower() for n in team_names]
    return sorted(bb for bb, pat in BLUE_BLOODS.items()
                  if any(pat.search(n) for n in lowered))


def test_htss_v2():
    name = "htss_v2_results.json"
    try:
        d = load(name)
    except Exception as e:
        check(name + ": parses", False, str(e))
        return
    check(name + ": parses", True)

    top = d.get("allTimeTop100")
    ok = isinstance(top, list) and len(top) == 100
    check(name + ": allTimeTop100 has 100 entries", ok,
          "got %s" % (len(top) if isinstance(top, list) else "non-list"))
    if isinstance(top, list) and top:
        scores = [e.get("htss") for e in top]
        all_num = all(is_num(s) for s in scores)
        check(name + ": allTimeTop100 htss scores numeric", all_num,
              first_bad([(i, repr(s)) for i, s in enumerate(scores) if not is_num(s)]))
        if all_num:
            # Descending; ties allowed because scores are published at
            # 2-decimal precision (see tests/README.md, decision D1).
            asc = [(i, scores[i], scores[i + 1])
                   for i in range(len(scores) - 1) if scores[i] < scores[i + 1]]
            check(name + ": allTimeTop100 scores descending (ties allowed at "
                  "2-dp precision)", not asc, first_bad(asc))
            ranks = [e.get("rank") for e in top]
            check(name + ": allTimeTop100 ranks are exactly 1..100 in order",
                  ranks == list(range(1, 101)), "ranks malformed: %s..." % ranks[:5])
            out = [(i, s) for i, s in enumerate(scores) if not (0 <= s <= 120)]
            check(name + ": allTimeTop100 scores within 0-120", not out,
                  first_bad(out))

    prog = d.get("programRankings")
    ok = isinstance(prog, list) and len(prog) >= 10
    check(name + ": programRankings has >= 10 entries", ok,
          "got %s" % (len(prog) if isinstance(prog, list) else "non-list"))
    if ok:
        names10 = [e.get("team", "") for e in prog[:10]]
        hits = blue_blood_hits(names10)
        check(name + ": programRankings top-10 contains >= 4 of "
              "{UCLA, Kentucky, North Carolina, Duke, Kansas}",
              len(hits) >= 4, "only matched %s in top-10 %s" % (hits, names10))

    by_team = d.get("byTeam")
    if isinstance(by_team, dict):
        total = sum(len(v) for v in by_team.values() if isinstance(v, list))
        check(name + ": byTeam total season count > 20000", total > 20000,
              "got %d" % total)
    else:
        check(name + ": byTeam total season count > 20000", False,
              "byTeam is %s" % type(by_team).__name__)


# --------------------------------------------------------------------------
# unified_rankings.json (+ cross-check against data.json H)
# --------------------------------------------------------------------------

def test_unified_rankings(data_h):
    name = "unified_rankings.json"
    try:
        d = load(name)
    except Exception as e:
        check(name + ": parses", False, str(e))
        return
    check(name + ": parses", True)

    prog = d.get("programAllTime")
    ok = isinstance(prog, list) and len(prog) >= 10
    check(name + ": programAllTime is a list with >= 10 entries", ok,
          "got %s" % (len(prog) if isinstance(prog, list) else "non-list"))
    if ok:
        scores = [e.get("score") for e in prog]
        all_num = all(is_num(s) for s in scores)
        check(name + ": programAllTime scores numeric", all_num,
              first_bad([(i, repr(s)) for i, s in enumerate(scores) if not is_num(s)]))
        if all_num:
            asc = [(i, scores[i], scores[i + 1])
                   for i in range(len(scores) - 1) if scores[i] < scores[i + 1]]
            check(name + ": programAllTime scores descending (ties allowed)",
                  not asc, first_bad(asc))
        names10 = [e.get("team", "") for e in prog[:10]]
        hits = blue_blood_hits(names10)
        check(name + ": programAllTime top-10 contains >= 4 of "
              "{UCLA, Kentucky, North Carolina, Duke, Kansas}",
              len(hits) >= 4, "only matched %s in top-10 %s" % (hits, names10))

    sea = d.get("seasonAllTime")
    ok = isinstance(sea, list) and len(sea) > 0
    check(name + ": seasonAllTime is a non-empty list", ok, "")
    if ok:
        if data_h is None:
            check(name + ": seasonAllTime espnIds resolvable in data.json H",
                  False, "data.json H unavailable, cannot cross-check")
        else:
            missing = [(e.get("rank"), e.get("team"), e.get("espnId"))
                       for e in sea if str(e.get("espnId")) not in data_h]
            check(name + ": seasonAllTime espnIds resolvable in data.json H",
                  not missing, first_bad(missing))


# --------------------------------------------------------------------------
# data.json (H team table)
# --------------------------------------------------------------------------

H_NAME, H_ATW, H_ATL, H_NC, H_NCY = 0, 4, 5, 6, 7


def test_data_json():
    name = "data.json"
    try:
        d = load(name)
    except Exception as e:
        check(name + ": parses", False, str(e))
        return None
    check(name + ": parses", True)

    h = d.get("H")
    ok = isinstance(h, dict) and len(h) > 0
    check(name + ": H is a non-empty dict", ok, "")
    if not ok:
        return None

    bad_name = []
    bad_types = []
    bad_ncy = []
    for tid, row in h.items():
        if not isinstance(row, list) or len(row) < 8:
            bad_types.append((tid, "row not a list of >= 8 elements"))
            continue
        if not isinstance(row[H_NAME], str) or not row[H_NAME].strip():
            bad_name.append((tid, repr(row[H_NAME])))
        if not is_nonneg_int(row[H_ATW]) or not is_nonneg_int(row[H_ATL]):
            bad_types.append((tid, "ATW/ATL not non-negative ints",
                              repr(row[H_ATW]), repr(row[H_ATL])))
        nc, ncy = row[H_NC], row[H_NCY]
        # Established serialization quirk: NCY is '' (empty string) for
        # teams with zero championships (see tests/README.md, decision D2).
        if ncy == "":
            ncy = []
        if not is_nonneg_int(nc) or not isinstance(ncy, list):
            bad_ncy.append((tid, row[H_NAME], "NC/NCY types", repr(nc), repr(row[H_NCY])[:40]))
            continue
        if len(ncy) != nc:
            bad_ncy.append((tid, row[H_NAME], "len(NCY)=%d != NC=%s" % (len(ncy), nc)))
            continue
        for y in ncy:
            if not isinstance(y, int) or isinstance(y, bool) or not (1939 <= y <= 2030):
                bad_ncy.append((tid, row[H_NAME], "NCY year out of 1939-2030", repr(y)))

    check(name + ": H team names are non-empty strings", not bad_name,
          first_bad(bad_name))
    check(name + ": H ATW/ATL are non-negative ints", not bad_types,
          first_bad(bad_types))
    check(name + ": H len(NCY) == NC and years within 1939-2030", not bad_ncy,
          first_bad(bad_ncy))
    return h


# --------------------------------------------------------------------------
# on_this_day.json
# --------------------------------------------------------------------------

MMDD_RE = re.compile(r"^\d{2}-\d{2}$")


def test_on_this_day():
    name = "on_this_day.json"
    try:
        d = load(name)
    except Exception as e:
        check(name + ": parses", False, str(e))
        return
    check(name + ": parses", True)

    ok = isinstance(d, dict) and len(d) == 366
    check(name + ": exactly 366 day keys", ok,
          "got %s" % (len(d) if isinstance(d, dict) else "non-dict"))
    if not isinstance(d, dict):
        return

    bad_keys = [k for k in d if not MMDD_RE.match(str(k))]
    check(name + ": keys are MM-DD formatted", not bad_keys, first_bad(bad_keys))

    over = [(k, len(v)) for k, v in d.items()
            if not isinstance(v, list) or len(v) > 8]
    check(name + ": <= 8 events per day", not over, first_bad(over))

    bad_date = []
    bad_score = []
    bad_team = []
    for k, events in d.items():
        if not isinstance(events, list):
            continue
        for e in events:
            if not isinstance(e, dict):
                bad_date.append((k, "event not a dict"))
                continue
            date = e.get("date", "")
            if not (isinstance(date, str) and len(date) == 10 and date[5:] == k):
                bad_date.append((k, date))
            headline = e.get("headline", "")
            score = e.get("score", "")
            if not (isinstance(headline, str) and isinstance(score, str)
                    and score and score in headline):
                bad_score.append((k, score, headline[:60]))
            for t in e.get("teams", []):
                tname = t.get("name", "") if isinstance(t, dict) else ""
                if not tname or tname not in headline:
                    bad_team.append((k, tname, headline[:60]))

    check(name + ": every event dated inside its MM-DD key", not bad_date,
          first_bad(bad_date))
    check(name + ": every headline contains its own score", not bad_score,
          first_bad(bad_score))
    check(name + ": every headline contains both team names", not bad_team,
          first_bad(bad_team))


# --------------------------------------------------------------------------
# games_1/2/3.json
# --------------------------------------------------------------------------

def valid_iso_date(s):
    if not isinstance(s, str) or len(s) != 10:
        return False
    try:
        datetime.date.fromisoformat(s)
        return True
    except ValueError:
        return False


def test_games_file(fname):
    try:
        d = load(fname)
    except Exception as e:
        check(fname + ": parses", False, str(e))
        return
    check(fname + ": parses", True)

    ok = isinstance(d, dict) and len(d) > 0
    check(fname + ": non-empty dict of teams", ok, "")
    if not ok:
        return

    bad_shape = []
    bad_game = []
    n_games = 0
    for tid, tv in d.items():
        # Two known shapes:
        #   A) {"games": [...], "slug": "<str>"}
        #   B) bare list of game objects
        if isinstance(tv, dict):
            games = tv.get("games")
            if not isinstance(games, list) or not isinstance(tv.get("slug"), str):
                bad_shape.append((tid, "dict shape missing games list / slug str"))
                continue
        elif isinstance(tv, list):
            games = tv
        else:
            bad_shape.append((tid, "team value is %s" % type(tv).__name__))
            continue

        for g in games:
            n_games += 1
            if not isinstance(g, dict):
                bad_game.append((tid, "game entry not a dict"))
                continue
            if not valid_iso_date(g.get("date")):
                bad_game.append((tid, "bad date", repr(g.get("date"))))
            if not is_nonneg_int(g.get("pts")) or not is_nonneg_int(g.get("opp_pts")):
                bad_game.append((tid, "bad pts/opp_pts",
                                 repr(g.get("pts")), repr(g.get("opp_pts"))))

    check(fname + ": every team entry matches one of the two known shapes",
          not bad_shape, first_bad(bad_shape))
    check(fname + ": game entries have valid ISO dates and non-negative int "
          "pts/opp_pts (%d games)" % n_games, not bad_game, first_bad(bad_game))


# --------------------------------------------------------------------------
# seasons.json
# --------------------------------------------------------------------------

def test_seasons_no_duplicate_histories(data_h):
    # The original compile_history.py scrape matched slugs by name-prefix
    # substring, assigning 16 small schools a flagship's byte-identical
    # season history (fixed 2026-06-12, see SEASONS_DUPLICATE_REPORT.md).
    # Invariant: no two data.json-H teams may share an identical season
    # fingerprint (length + first-10 seasons' year:W-L), which would mean
    # one team is wearing another's history.
    name = "seasons.json"
    try:
        d = load(name)
    except Exception as e:
        check(name + ": parses", False, str(e))
        return
    check(name + ": parses", True)
    if data_h is None:
        check(name + ": no two data.json-H teams share an identical season "
              "fingerprint", False, "data.json H unavailable, cannot cross-check")
        return

    fingerprints = {}
    for tid, entry in d.items():
        if str(tid) not in data_h:
            continue
        seasons = entry.get("seasons") if isinstance(entry, dict) else None
        if not isinstance(seasons, list) or len(seasons) < 3:
            continue
        fp = (len(seasons), "|".join(
            "%s:%s-%s" % (s.get("year"), s.get("wins"), s.get("losses"))
            for s in seasons[:10]))
        fingerprints.setdefault(fp, []).append(tid)

    dupes = [(ids, fp[0]) for fp, ids in fingerprints.items() if len(ids) > 1]
    check(name + ": no two data.json-H teams share an identical season "
          "fingerprint", not dupes, first_bad(dupes))


# --------------------------------------------------------------------------

def test_games_shard_disjointness(fnames):
    # Consumers merge the shards last-wins (Object.assign / dict update), so a
    # team key present in two files silently shadows one copy of its game log
    # (this happened to 263/Drake across games_2 and games_3, June 2026).
    seen = {}
    dupes = []
    for fname in fnames:
        try:
            d = load(fname)
        except Exception:
            return  # parse failures already reported by test_games_file
        if not isinstance(d, dict):
            continue
        for tid in d:
            if tid in seen:
                dupes.append((tid, seen[tid], fname))
            else:
                seen[tid] = fname
    check("games shards: every team key appears in exactly one file",
          not dupes, first_bad(dupes))


def main():
    print("Hoopsipedia ranking-engine data invariants")
    print("root: %s" % ROOT)
    print("-" * 70)
    test_efficiency_ratings()
    test_htss_v2()
    data_h = test_data_json()
    test_unified_rankings(data_h)
    test_on_this_day()
    test_seasons_no_duplicate_histories(data_h)
    games_files = ("games_1.json", "games_2.json", "games_3.json")
    for f in games_files:
        test_games_file(f)
    test_games_shard_disjointness(games_files)
    print("-" * 70)
    print("%d passed, %d failed, %d skipped (known data issues)"
          % (_passes, _failures, _skips))
    if _skips:
        print("*** %d invariant(s) SUSPENDED via KNOWN_DATA_ISSUES -- "
              "see tests/README.md ***" % _skips)
    sys.exit(1 if _failures else 0)


if __name__ == "__main__":
    main()
