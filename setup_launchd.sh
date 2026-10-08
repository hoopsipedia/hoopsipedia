#!/bin/bash
# Install Hoopsipedia's scheduled jobs as macOS launchd agents (replaces setup_cron.sh).
#
# Why launchd and not cron: cron silently skips any job whose time passes while
# the Mac is asleep. In the week of 2026-09-11 the 07:00 drafts ran 2 of 7
# mornings and the Monday Google report never ran. launchd runs a missed
# StartCalendarInterval job at the next wake, so a closed lid delays a job
# instead of dropping it. Same three jobs, same commands, same logs.
#
#   ./setup_launchd.sh            # install/reload all agents, remove the old cron lines
#   ./setup_launchd.sh --status   # show what is loaded and when each last ran
#   ./setup_launchd.sh --remove   # unload and delete the agents
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-/Library/Frameworks/Python.framework/Versions/3.14/bin/python3}"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"
AGENTS="$HOME/Library/LaunchAgents"
PREFIX="com.hoopsipedia"
UID_="$(id -u)"

if [ "${1:-}" = "--status" ]; then
  for j in sync drafts report refresh; do
    printf '%-24s ' "$PREFIX.$j"
    launchctl print "gui/$UID_/$PREFIX.$j" 2>/dev/null | grep -E "state =|last exit code|runs =" | tr -s ' ' | tr '\n' ' ' || printf 'not loaded'
    echo
  done
  echo "logs: /private/tmp/hoopsipedia_{sync,content,reports}.log"
  exit 0
fi
if [ "${1:-}" = "--remove" ]; then
  for j in sync drafts report refresh; do
    launchctl bootout "gui/$UID_/$PREFIX.$j" 2>/dev/null || true
    rm -f "$AGENTS/$PREFIX.$j.plist"
  done
  echo "removed"; exit 0
fi

mkdir -p "$AGENTS"

# Emit one <dict> per calendar slot.
# The sync agent fires daily at 02:00 and every 30 min from noon to 23:30, all
# year; nightly_sync.py decides from the date whether a firing does anything
# (Nov-Apr nightly, March Thu-Sun every slot, otherwise exit in milliseconds).
# The calendar used to live here as Month-restricted slots, but launchd ran the
# March every-30-min slots in September 2026 (15-21 runs a day, 365 ESPN calls
# each), so the Month key cannot be trusted and the gating moved into Python.
slot() { printf '      <dict>'; for kv in "$@"; do printf '<key>%s</key><integer>%s</integer>' "${kv%%=*}" "${kv##*=}"; done; printf '</dict>\n'; }
sync_slots() {
  slot Hour=2 Minute=0
  for h in $(seq 12 23); do for mi in 0 30; do slot Hour=$h Minute=$mi; done; done
}

# write_plist label log-file slots-function command...
write_plist() {
  local label="$1" log="$2" slots="$3"; shift 3
  local cmd="$*"
  cmd="${cmd//&/&amp;}"; cmd="${cmd//</&lt;}"; cmd="${cmd//>/&gt;}"   # XML-escape the shell command
  cat > "$AGENTS/$label.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>-lc</string><string>$cmd</string></array>
  <key>WorkingDirectory</key><string>$SCRIPT_DIR</string>
  <key>StartCalendarInterval</key>
  <array>
$($slots)
  </array>
  <key>StandardOutPath</key><string>$log</string>
  <key>StandardErrorPath</key><string>$log</string>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string><key>LANG</key><string>en_US.UTF-8</string></dict>
</dict>
</plist>
PLIST
}

write_plist "$PREFIX.sync"   /private/tmp/hoopsipedia_sync.log    sync_slots \
  "cd '$SCRIPT_DIR' && '$PYTHON' nightly_sync.py"
write_plist "$PREFIX.drafts" /private/tmp/hoopsipedia_content.log "slot Hour=7 Minute=0" \
  "cd '$SCRIPT_DIR' && '$PYTHON' scripts/daily_content.py"
write_plist "$PREFIX.report" /private/tmp/hoopsipedia_reports.log "slot Weekday=1 Hour=8 Minute=0" \
  "cd '$SCRIPT_DIR' && set -a && . \$HOME/.config/hoopsipedia/google.env && set +a && '$PYTHON' scripts/google_reports.py"

# Once a year, after the title game: re-pull every program's season row so the
# tournament results land (the 2026 bracket went missing for six months).
write_plist "$PREFIX.refresh" /private/tmp/hoopsipedia_refresh.log "slot Month=4 Day=10 Hour=3 Minute=0" \
  "cd '$SCRIPT_DIR' && ./scripts/post_tournament_refresh.sh"

for j in sync drafts report refresh; do
  plutil -lint "$AGENTS/$PREFIX.$j.plist" >/dev/null
  launchctl bootout "gui/$UID_/$PREFIX.$j" 2>/dev/null || true
  launchctl bootstrap "gui/$UID_" "$AGENTS/$PREFIX.$j.plist"
done

# Retire the cron lines these agents replace (keep anything that is not ours).
if crontab -l 2>/dev/null | grep -qE "nightly_sync|daily_content|google_reports"; then
  (crontab -l 2>/dev/null | grep -v "Hoopsipedia" | grep -vE "nightly_sync|daily_content|google_reports") | crontab - || true
  echo "removed the Hoopsipedia cron lines"
fi

echo "✅ launchd agents installed:"
"$0" --status
