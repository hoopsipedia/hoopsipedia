#!/bin/zsh
cd /Users/joshdavis/Projects/hoopsipedia
for src in wagner-seahawks-cp virginia-cavaliers-cp san-jose-state-spartans-cp njit-highlanders-cp princeton-tigers-cp portland-state-vikings-cp north-carolina-central-eagles-cp maryland-terrapins-cp kentucky-wildcats-cp washington-huskies-cp idaho-state-bengals-cp iowa-hawkeyes-cp usc-trojans-cp oregon-ducks-cp; do
  rm -f "archives/$src/statcrew_boxscores_pending.json"
  echo "=== $src ==="
  python3 -u harvest_statcrew.py $src 2>&1 | tail -4
done
echo "CUSTOMPAGES2 COMPLETE"
