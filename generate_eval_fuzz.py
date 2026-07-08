#!/usr/bin/env python3
"""
Compositional eval fuzzer — samples the combinatorial question space.

Instead of fixed questions, randomly composes cross-era comparisons and
filtered superlatives from the site's actual data, e.g.:
    "Compare 1967 Kentucky, 2022 Creighton, and 1993 Duke."
Each sampled team-season carries its ground truth (record, conf record,
SRS, AP high) pulled from seasons/{id}.json. Grading = factual fidelity:
the answer must cite each team's correct record (win count present near
loss count); the subjective "who wins" is never graded. Transcripts are
kept for a claim-extraction judge pass.

Fresh randomness every run by default (--seed for reproducibility).
Output: chat_eval_suite_fuzz.json
"""

import argparse
import json
import random

F_NAME = 0

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=40)
ap.add_argument("--seed", type=int, default=None)
args = ap.parse_args()
if args.seed is not None:
    random.seed(args.seed)

with open("data.json") as f:
    H = json.load(f)["H"]

# load all team-season rows once
team_seasons = {}
for tid in H:
    try:
        with open(f"seasons/{tid}.json") as fh:
            rows = json.load(fh).get("seasons", [])
    except Exception:
        continue
    usable = [s for s in rows if s.get("wins") is not None
              and s.get("losses") is not None and s.get("year")]
    if usable:
        team_seasons[tid] = usable

tids = list(team_seasons)
suite = []


def school(tid):
    full = H[tid][F_NAME]
    nick = H[tid][1] or ""
    if nick and full.endswith(nick):
        base = full[: -len(nick)].strip()
    else:
        base = full.rsplit(" ", 1)[0]
    # strip dangling mascot fragments ("Presbyterian Blue" -> "Presbyterian")
    FRAG = {"Blue", "Great", "Golden", "Fighting", "Red", "Black", "Crimson",
            "Scarlet", "Green", "Purple", "Mean", "Running", "Runnin'", "Ragin'",
            "Demon", "Horned", "Yellow", "Delta"}
    parts = base.split()
    while len(parts) > 1 and parts[-1] in FRAG:
        parts.pop()
    return " ".join(parts)


def sample_ts():
    tid = random.choice(tids)
    s = random.choice(team_seasons[tid])
    return tid, s


TEMPLATES_KWAY = [
    "Compare {teams}. Which was the best team?",
    "Rank these teams: {teams}.",
    "If {teams} played each other, who would win and why?",
    "Break down {teams} — records, strength of schedule, how far each went.",
]

for i in range(1, args.n + 1):
    k = random.choice([2, 2, 3, 3, 4])  # mostly 2-3 way
    picks = []
    seen = set()
    while len(picks) < k:
        tid, s = sample_ts()
        key = (tid, s["year"])
        if key in seen:
            continue
        seen.add(key)
        picks.append((tid, s))
    team_strs = [f"{s['year']} {school(tid)}" for tid, s in picks]
    if k == 2:
        teams_txt = f"{team_strs[0]} and {team_strs[1]}"
    else:
        teams_txt = ", ".join(team_strs[:-1]) + f", and {team_strs[-1]}"
    q = random.choice(TEMPLATES_KWAY).format(teams=teams_txt)

    # factual fidelity: each team's record must appear (W-L in either
    # hyphen style); grading groups are per-team any-of
    expected = []
    truth = []
    for tid, s in picks:
        w, l = s["wins"], s["losses"]
        expected.append([f"{w}-{l}", f"{w}–{l}", f"{w} wins"])
        truth.append({"team": school(tid), "year": s["year"], "record": f"{w}-{l}",
                      "srs": s.get("srs"), "confRecord": s.get("confRecord"),
                      "apHigh": s.get("apHigh")})
    suite.append({"id": f"F{i:03d}", "q": q, "expected": expected, "forbidden": [],
                  "tags": {"kind": f"fuzz_{k}way", "tool": "multi",
                           "truth": truth}})

with open("chat_eval_suite_fuzz.json", "w") as fh:
    json.dump(suite, fh, indent=1, ensure_ascii=False)

print(f"fuzzed {len(suite)} compositional questions from "
      f"{len(tids)} teams x {sum(len(v) for v in team_seasons.values())} team-seasons")
for x in suite[:5]:
    print(" ", x["q"])
