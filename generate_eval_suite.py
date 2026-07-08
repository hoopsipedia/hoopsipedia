#!/usr/bin/env python3
"""
Generate a large chat-eval suite programmatically from the site's own data.

Every question's expected answer is computed from the JSON the chat itself
serves, so grading is mechanical. Teams are sampled across prominence tiers
(blueblood -> obscure) and years across eras, tagging each question so the
morning analysis can report failure rate by tool, era, and team obscurity.

Output: chat_eval_suite_generated.json (list of {id,q,expected,forbidden,tags})
"""

import json
import random
import re

random.seed(20260708)  # deterministic suite

F_NAME, F_CONF, F_ATW, F_ATL, F_NC, F_NCY, F_FF, F_TOURNEY = 0, 2, 4, 5, 6, 7, 8, 11

with open("data.json") as f:
    H = json.load(f)["H"]
with open("team_history.json") as f:
    TH = json.load(f)
th_by_name = {v["team"]: v for v in TH.values()}


def tier(fields):
    atw = fields[F_ATW] or 0
    nc = fields[F_NC] or 0
    if nc >= 2 or atw > 1900:
        return "blueblood"
    if atw > 1400:
        return "major"
    if atw > 900:
        return "mid"
    return "low"


teams = [(tid, fields) for tid, fields in H.items()]
by_tier = {"blueblood": [], "major": [], "mid": [], "low": []}
for tid, fields in teams:
    by_tier[tier(fields)].append((tid, fields))
for v in by_tier.values():
    random.shuffle(v)


def sample_teams(n_per_tier):
    out = []
    for t, lst in by_tier.items():
        out += [(tid, f, t) for tid, f in lst[:n_per_tier]]
    return out


suite = []
counter = {"n": 0}


def add(q, expected, tags, forbidden=None):
    counter["n"] += 1
    suite.append({"id": f"G{counter['n']:03d}", "q": q, "expected": expected,
                  "forbidden": forbidden or [], "tags": tags})


# ── 1. Championship counts (incl. zero-champ teams) ──
for tid, f, t in sample_teams(8):
    nc = f[F_NC] or 0
    name = f[F_NAME]
    if nc == 0:
        add(f"How many national championships does {name.rsplit(' ',1)[0]} have?",
            [["0", "zero", "none", "never won", "no national championship", "hasn't won", "has not won"]],
            {"tool": "lookupTeam", "tier": t, "kind": "champ_count_zero"})
    else:
        add(f"How many national championships does {name.rsplit(' ',1)[0]} have?",
            [[str(nc)]], {"tool": "lookupTeam", "tier": t, "kind": "champ_count"})

# ── 2. Champion by year (every decade) ──
champ_by_year = {}
for tid, f in teams:
    for y in (f[F_NCY] or []):
        champ_by_year[int(y)] = f[F_NAME]
years = sorted(champ_by_year)
for y in years[::2]:  # every other championship year ≈ 44 questions
    name = champ_by_year[y]
    school = name.rsplit(" ", 1)[0]
    add(f"Who won the {y} national championship?",
        [[school, name]], {"tool": "getChampionByYear", "era": f"{(y//10)*10}s", "kind": "champ_by_year"})

# ── 3. All-time wins ──
for tid, f, t in sample_teams(5):
    school = f[F_NAME].rsplit(" ", 1)[0]
    add(f"How many all-time wins does {school} have?",
        [[str(f[F_ATW])]], {"tool": "lookupTeam", "tier": t, "kind": "alltime_wins"})

# ── 4. Final Four counts ──
for tid, f, t in sample_teams(4):
    school = f[F_NAME].rsplit(" ", 1)[0]
    ff = f[F_FF] or 0
    exp = [[str(ff)]] if ff else [["0", "zero", "none", "never", "no Final Four", "hasn't"]]
    add(f"How many Final Fours has {school} made?",
        exp, {"tool": "lookupTeam", "tier": t, "kind": "ff_count"})

# ── 5. Conference membership ──
for tid, f, t in sample_teams(5):
    school = f[F_NAME].rsplit(" ", 1)[0]
    add(f"What conference does {school} play in?",
        [[f[F_CONF]]], {"tool": "lookupTeam", "tier": t, "kind": "conference"})

# ── 6. Founded year (team_history) ──
th_sample = random.sample(list(th_by_name.items()), 20)
for name, v in th_sample:
    if v.get("founded"):
        school = name.rsplit(" ", 1)[0]
        add(f"When did {school}'s basketball program begin?",
            [[str(v["founded"])]], {"tool": "getTeamHistory", "kind": "founded"})

# ── 7. Season records (per-team slices, spread across eras) ──
season_qs = 0
slice_teams = sample_teams(6)
for tid, f, t in slice_teams:
    try:
        with open(f"seasons/{tid}.json") as fh:
            seasons = json.load(fh)
        rows = seasons.get("seasons", seasons if isinstance(seasons, list) else [])
    except Exception:
        continue
    usable = [s for s in rows if s.get("wins") is not None and s.get("losses") is not None and s.get("year")]
    if not usable:
        continue
    s = random.choice(usable)
    school = f[F_NAME].rsplit(" ", 1)[0]
    yr = s["year"]
    add(f"What was {school}'s record in the {yr} season?",
        [[f"{s['wins']}-{s['losses']}", f"{s['wins']} wins", f"{s['wins']}–{s['losses']}"]],
        {"tool": "getTeamSeasons", "tier": t, "era": str(yr)[:3] + "0s", "kind": "season_record"})
    season_qs += 1

# ── 8. Head-to-head (from h2h.json where available) ──
with open("h2h.json") as fh:
    h2h = json.load(fh)
# nested {tidA: {tidB: {w,l,g}}} — prefer rivalries with real history (g >= 15)
flat = []
for a_id, opps in h2h.items():
    for b_id, rec in opps.items():
        if a_id < b_id and a_id in H and b_id in H and rec.get("g", 0) >= 15:
            flat.append((a_id, b_id, rec))
random.shuffle(flat)
for a_id, b_id, rec in flat[:24]:
    a = H[a_id][F_NAME].rsplit(" ", 1)[0]
    b = H[b_id][F_NAME].rsplit(" ", 1)[0]
    add(f"What is the all-time head-to-head record between {a} and {b}?",
        [[str(rec["w"])], [str(rec["l"])]],
        {"tool": "getHeadToHead", "kind": "h2h", "games": rec["g"]})

# ── 9. Tournament appearance counts ──
for tid, f, t in sample_teams(4):
    school = f[F_NAME].rsplit(" ", 1)[0]
    n = f[F_TOURNEY] or 0
    exp = [[str(n)]] if n else [["0", "zero", "none", "never made", "no NCAA tournament", "hasn't"]]
    add(f"How many NCAA tournament appearances does {school} have?",
        exp, {"tool": "lookupTeam", "tier": t, "kind": "tourney_count"})

with open("chat_eval_suite_generated.json", "w") as fh:
    json.dump(suite, fh, indent=1, ensure_ascii=False)

from collections import Counter
kinds = Counter(x["tags"]["kind"] for x in suite)
tiers = Counter(x["tags"].get("tier", "-") for x in suite)
print(f"generated {len(suite)} questions")
print("by kind:", dict(kinds))
print("by tier:", dict(tiers))
