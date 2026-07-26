#!/bin/zsh
cd /Users/joshdavis/Projects/hoopsipedia
for src in hofstra-pride bowling-green-falcons troy-trojans eastern-michigan-eagles uc-riverside-highlanders purdue-fort-wayne-mastodons longwood-lancers iupui-jaguars; do
  rm -f "archives/$src/statcrew_boxscores_pending.json"
  echo "=== $src ==="
  python3 -u harvest_statcrew.py $src 2>&1 | grep -E 'STATS|wrote|games from CDX|gave up' | tail -3
done
echo "CUSTOMPAGES_HARVEST COMPLETE"
