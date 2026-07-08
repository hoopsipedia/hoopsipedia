#!/usr/bin/env python3
"""
Chat eval harness — baseline quality measurement for /api/chat.

Sends a tiered question suite to the live endpoint (paced under its own
20-req/5-min rate limit), captures streamed answers, and grades each
mechanically: expected substrings (any-of groups) must appear, forbidden
substrings must not. Transcripts saved for a deeper judge pass.

Tiers: A single-lookup, B multi-hop, C era/nuance, D adversarial/gap-probe.
Output: chat_eval_results.json + console summary.

Usage: python3 eval_chat.py [--endpoint https://www.hoopsipedia.com/api/chat] [--pace 20]
"""

import argparse
import json
import re
import sys
import time

import requests

sys.stdout.reconfigure(line_buffering=True)

# expected: list of groups; each group is a list of alternatives (any one
# alternative matching counts the group as satisfied). forbidden: none may appear.
SUITE = [
    # ── Tier A: single lookup ──
    {"id": "A1", "q": "How many national championships does UCLA have?",
     "expected": [["11"]], "forbidden": []},
    {"id": "A2", "q": "Who won the 1983 national championship?",
     "expected": [["NC State", "North Carolina State"]], "forbidden": []},
    {"id": "A3", "q": "What conference is Gonzaga in?",
     "expected": [["West Coast", "WCC"]], "forbidden": []},
    {"id": "A4", "q": "How many Final Fours has Duke been to?",
     "expected": [["18"]], "forbidden": []},
    {"id": "A5", "q": "What year did Michigan win its first championship?",
     "expected": [["1989"]], "forbidden": []},
    {"id": "A6", "q": "Who is the all-time wins leader in college basketball?",
     "expected": [["Kentucky", "Kansas"]], "forbidden": []},
    {"id": "A7", "q": "What is Villanova's mascot?",
     "expected": [["Wildcat"]], "forbidden": []},
    {"id": "A8", "q": "When did Mercyhurst move to Division I?",
     "expected": [["2024"]], "forbidden": [["2023"]]},
    # ── Tier B: multi-hop ──
    {"id": "B1", "q": "Who has more all-time wins, Kentucky or Kansas, and by how many?",
     "expected": [["Kentucky", "Kansas"]], "forbidden": []},
    {"id": "B2", "q": "What is the all-time head-to-head record between Duke and North Carolina?",
     "expected": [["Duke"], ["North Carolina"]], "forbidden": []},
    {"id": "B3", "q": "Compare UCLA and Kentucky: championships, Final Fours, and all-time wins.",
     "expected": [["11"], ["8"]], "forbidden": []},
    {"id": "B4", "q": "Which team was better in 2015 by efficiency: Duke or Wisconsin?",
     "expected": [["Duke", "Wisconsin"]], "forbidden": []},
    {"id": "B5", "q": "Who did Villanova beat in each round of the 2016 tournament?",
     "expected": [["North Carolina"], ["Kansas", "Oklahoma", "Iowa", "Miami", "UNC Asheville", "Asheville"]], "forbidden": []},
    {"id": "B6", "q": "Which active program has the longest current NCAA tournament appearance streak?",
     "expected": [["Kansas", "Gonzaga", "Michigan State", "streak"]], "forbidden": []},
    {"id": "B7", "q": "List the last five national champions in order.",
     "expected": [["Michigan"], ["Florida"], ["UConn", "Connecticut"], ["Baylor", "Kansas"]], "forbidden": []},
    {"id": "B8", "q": "What was Gonzaga's best season ever by HTSS score?",
     "expected": [["2021", "2017"]], "forbidden": []},
    {"id": "B9", "q": "Which coach has more career wins, Coach K or Jim Boeheim?",
     "expected": [["Krzyzewski", "Coach K"]], "forbidden": []},
    {"id": "B10", "q": "How did the 12-seeds do against 5-seeds historically in the tournament?",
     "expected": [["12", "5"]], "forbidden": []},
    # ── Tier C: era / nuance ──
    {"id": "C1", "q": "Who won the 2026 national championship and who did they beat in the final?",
     "expected": [["Michigan"], ["UConn", "Connecticut"], ["69", "63"]], "forbidden": []},
    {"id": "C2", "q": "How many championships does Houston have?",
     "expected": [["zero", "0", "none", "no national championship", "never won"]],
     "forbidden": [["2025 national championship", "won in 2025"]]},
    {"id": "C3", "q": "Tell me about UTEP's 1966 championship.",
     "expected": [["Texas Western", "1966"]], "forbidden": []},
    {"id": "C4", "q": "What happened to Louisville's 2013 championship?",
     "expected": [["vacat"]], "forbidden": []},
    {"id": "C5", "q": "Who was ranked #1 in the final AP poll of 2024?",
     "expected": [["UConn", "Connecticut", "Houston", "Purdue"]], "forbidden": []},
    {"id": "C6", "q": "How many teams from the Big East made the 2026 tournament?",
     "expected": [[""]], "forbidden": []},  # transcript-only: judge later
    {"id": "C7", "q": "What was the biggest upset in tournament history by seed?",
     "expected": [["16", "15", "UMBC", "Virginia", "Fairleigh Dickinson", "Richmond"]], "forbidden": []},
    {"id": "C8", "q": "Which team returned to Division I in 2009 after dropping down decades earlier?",
     "expected": [["Seattle"]], "forbidden": []},
    # ── Tier D: adversarial / gap probes ──
    {"id": "D1", "q": "Who won the 2020 NCAA tournament?",
     "expected": [["cancel", "COVID", "no tournament", "was not held", "wasn't held"]],
     "forbidden": []},
    {"id": "D2", "q": "Tell me about Houston winning the 2025 championship.",
     "expected": [["lost", "Florida", "did not win", "didn't win", "runner-up", "fell"]],
     "forbidden": []},
    {"id": "D3", "q": "Who was Duke's leading scorer in the 2015 championship game?",
     "expected": [[""]], "forbidden": []},  # gap probe: no player/box tool — judge honesty later
    {"id": "D4", "q": "What was the final score of the 1985 Villanova-Georgetown title game?",
     "expected": [["66", "64"]], "forbidden": []},
    {"id": "D5", "q": "Who won the 2018 women's national championship?",
     "expected": [["Notre Dame", "women", "men's"]], "forbidden": []},
    {"id": "D6", "q": "How many points did Michael Jordan score in the 1982 title game?",
     "expected": [[""]], "forbidden": []},  # gap probe: judge honesty later
    {"id": "D7", "q": "Did Kentucky make the 1988 tournament?",
     "expected": [["vacat", "1988"]], "forbidden": []},
    {"id": "D8", "q": "Which team won 38 games in 2024?",
     "expected": [["UConn", "Connecticut", "37", "38"]], "forbidden": []},
    {"id": "D9", "q": "asdfghjkl what is the meaning of basketball qwerty?",
     "expected": [[""]], "forbidden": []},  # nonsense handling: judge later
    {"id": "D10", "q": "Compare the 1996 Kentucky team to the 2021 Gonzaga team. Who wins?",
     "expected": [["Kentucky"], ["Gonzaga"]], "forbidden": []},
]


def ask(endpoint, question, timeout=90):
    """POST and collect the streamed answer text."""
    body = {"messages": [{"role": "user", "content": question}]}
    t0 = time.time()
    try:
        resp = requests.post(endpoint, json=body, timeout=timeout, stream=True)
        if resp.status_code != 200:
            return None, resp.status_code, time.time() - t0
        text = []
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                continue
            # anthropic-style stream deltas or app-custom {text} events
            if isinstance(obj, dict):
                if obj.get("type") == "content_block_delta":
                    text.append(obj.get("delta", {}).get("text", ""))
                elif "text" in obj:
                    text.append(str(obj["text"]))
        return "".join(text), 200, time.time() - t0
    except requests.RequestException as e:
        return None, f"NETWORK: {type(e).__name__}", time.time() - t0


def grade(item, answer):
    if answer is None:
        return "ERROR", []
    notes = []
    ok = True
    for group in item["expected"]:
        if group == [""]:
            continue  # transcript-only item
        if not any(alt.lower() in answer.lower() for alt in group):
            ok = False
            notes.append(f"missing any of {group}")
    for group in item.get("forbidden", []):
        for alt in group:
            if alt.lower() in answer.lower():
                ok = False
                notes.append(f"forbidden present: {alt!r}")
    if item["expected"] == [[""]] or all(g == [""] for g in item["expected"]):
        return "JUDGE", notes  # needs human/LLM judging
    return ("PASS" if ok else "FAIL"), notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default="https://www.hoopsipedia.com/api/chat")
    ap.add_argument("--pace", type=float, default=20.0, help="seconds between questions")
    ap.add_argument("--suite", default=None, help="path to a generated suite JSON")
    ap.add_argument("--out", default="chat_eval_results.json")
    args = ap.parse_args()

    suite = SUITE
    if args.suite:
        with open(args.suite) as fh:
            suite = json.load(fh)

    results = []
    for item in suite:
        answer, status, dt = ask(args.endpoint, item["q"])
        verdict, notes = grade(item, answer)
        results.append({"id": item["id"], "q": item["q"], "verdict": verdict,
                        "status": status, "latency_s": round(dt, 1),
                        "tags": item.get("tags", {}),
                        "notes": notes, "answer": answer})
        print(f"[{item['id']}] {verdict:<6} {dt:5.1f}s  {item['q'][:60]}")
        if verdict == "FAIL":
            for n in notes:
                print(f"        {n}")
        if len(results) % 20 == 0:
            with open(args.out, "w") as f:
                json.dump(results, f, indent=1, ensure_ascii=False)
        time.sleep(args.pace)

    with open(args.out, "w") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)

    from collections import Counter
    by_tier = {}
    for r in results:
        tier = r["id"][0]
        by_tier.setdefault(tier, Counter())[r["verdict"]] += 1
    print("\n=== SUMMARY ===")
    for tier in "ABCD":
        c = by_tier.get(tier, Counter())
        print(f"Tier {tier}: {dict(c)}")
    total = Counter(r["verdict"] for r in results)
    print(f"Overall: {dict(total)}  (JUDGE items need the morning judge pass)")
    lat = [r["latency_s"] for r in results if r["status"] == 200]
    if lat:
        print(f"Latency: median {sorted(lat)[len(lat)//2]}s, max {max(lat)}s")


if __name__ == "__main__":
    main()
