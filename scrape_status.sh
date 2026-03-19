#!/bin/bash
# Live status monitor for the scrape pipeline
# Usage: bash scrape_status.sh

GAMES_JSON="/Users/joshdavis/Projects/hoopsipedia/games.json"
SEC_LOG="/private/tmp/claude-501/-Users-joshdavis-Projects-hoopsipedia/tasks/bpgyyp9h5.output"
ALL_LOG="/private/tmp/claude-501/-Users-joshdavis-Projects-hoopsipedia/tasks/scrape_chain.output"

while true; do
    clear
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║           🏀 HOOPSIPEDIA SCRAPE STATUS 🏀                  ║"
    echo "╠══════════════════════════════════════════════════════════════╣"

    # Games.json stats
    TEAM_COUNT=$(python3 -c "import json; d=json.load(open('$GAMES_JSON')); print(len(d))" 2>/dev/null || echo "?")
    GAME_COUNT=$(python3 -c "import json; d=json.load(open('$GAMES_JSON')); print(sum(len(v.get('games',[])) for v in d.values()))" 2>/dev/null || echo "?")
    SIZE_KB=$(du -k "$GAMES_JSON" 2>/dev/null | cut -f1 || echo "?")

    echo "║  games.json: ${TEAM_COUNT} teams | ${GAME_COUNT} games | ${SIZE_KB} KB"
    echo "╠══════════════════════════════════════════════════════════════╣"

    # SEC scrape status
    if [ -f "$SEC_LOG" ]; then
        SEC_CURRENT=$(grep "^\[" "$SEC_LOG" 2>/dev/null | tail -1 || echo "not started")
        SEC_DONE=$(grep "^\[" "$SEC_LOG" 2>/dev/null | wc -l | tr -d ' ')
        SEC_GAMES=$(grep "^    -> " "$SEC_LOG" 2>/dev/null | tail -1 | sed 's/.*-> //' | sed 's/ games//' || echo "0")
        SEC_STATUS=$(grep "COMPLETE\|429\|Scraping" "$SEC_LOG" 2>/dev/null | tail -1 | head -c 55)

        if grep -q "COMPLETE" "$SEC_LOG" 2>/dev/null; then
            echo "║  SEC:  ████████████████████ DONE ✅"
        else
            BAR=""
            for i in $(seq 1 $((SEC_DONE > 16 ? 16 : SEC_DONE))); do BAR="${BAR}█"; done
            for i in $(seq $((SEC_DONE+1)) 16); do BAR="${BAR}░"; done
            echo "║  SEC:  ${BAR} ${SEC_CURRENT}"
        fi
    else
        echo "║  SEC:  not started"
    fi

    # Chain scrape status
    if [ -f "$ALL_LOG" ]; then
        CHAIN_PHASE=$(grep "^Starting:\|^PHASE\|Compiling" "$ALL_LOG" 2>/dev/null | tail -1 | head -c 50)
        CHAIN_CURRENT=$(grep "^\[\|^Compiling" "$ALL_LOG" 2>/dev/null | tail -1 | head -c 55)

        if grep -q "ALL SCRAPING COMPLETE" "$ALL_LOG" 2>/dev/null; then
            echo "║  ALL:  ████████████████████ DONE ✅"
        else
            echo "║  ALL:  ${CHAIN_PHASE}"
            echo "║        ${CHAIN_CURRENT}"
        fi
    else
        echo "║  ALL:  waiting for SEC to finish..."
    fi

    echo "╠══════════════════════════════════════════════════════════════╣"

    # Conference breakdown
    echo "║  Conference coverage:"
    python3 -c "
import json
with open('$GAMES_JSON') as f:
    games = json.load(f)
with open('data.json') as f:
    data = json.load(f)
confs = {}
for eid, gdata in games.items():
    team = data['H'].get(eid)
    if team:
        conf = team[2]
        confs.setdefault(conf, [0, 0])
        confs[conf][0] += 1
        confs[conf][1] += len(gdata.get('games', []))
for c in sorted(confs.keys()):
    total_in_conf = sum(1 for t in data['H'].values() if t[2] == c)
    pct = int(confs[c][0] / total_in_conf * 100) if total_in_conf > 0 else 0
    bar = '█' * (pct // 5) + '░' * (20 - pct // 5)
    print(f'║    {c:15s} {bar} {confs[c][0]:3d}/{total_in_conf:3d} teams  {confs[c][1]:6d} games')
" 2>/dev/null

    echo "╠══════════════════════════════════════════════════════════════╣"
    echo "║  Last updated: $(date '+%H:%M:%S')                                    ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    echo "  Press Ctrl+C to exit"

    sleep 10
done
