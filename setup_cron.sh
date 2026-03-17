#!/bin/bash
# Set up cron jobs for Hoopsipedia nightly sync
# Run this script once to install the cron schedule

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON=$(which python3)

# Create the cron schedule
# Tournament game days (Thu-Sun): every 30 min from noon-midnight ET
# Off days (Mon-Wed): once at 2 AM ET
CRON_JOBS=$(cat <<EOF
# Hoopsipedia Nightly Sync
# Tournament days (Thu-Sun): every 30 min, noon to midnight ET
*/30 12-23 * 3 4-7 cd $SCRIPT_DIR && $PYTHON nightly_sync.py >> /private/tmp/hoopsipedia_sync.log 2>&1
# Off days (Mon-Wed): once at 2 AM ET
0 2 * 3 1-3 cd $SCRIPT_DIR && $PYTHON nightly_sync.py >> /private/tmp/hoopsipedia_sync.log 2>&1
# April: nightly at 2 AM (later tournament rounds)
0 2 * 4 * cd $SCRIPT_DIR && $PYTHON nightly_sync.py >> /private/tmp/hoopsipedia_sync.log 2>&1
EOF
)

# Install cron jobs (preserve any existing non-hoopsipedia jobs)
(crontab -l 2>/dev/null | grep -v "Hoopsipedia" | grep -v "nightly_sync"; echo "$CRON_JOBS") | crontab -

echo "✅ Cron jobs installed:"
crontab -l
echo ""
echo "Sync logs: /private/tmp/hoopsipedia_sync.log"
echo "Data logs: $SCRIPT_DIR/sync_log.txt"
