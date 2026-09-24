#!/bin/bash
# Installs (or re-installs) the daily update as a launchd agent for this user, then checks that
# macOS lets it read this folder (Desktop is privacy-protected: python3 needs Full Disk Access once).
#     bash install_schedule.sh            # install / update, then probe
#     bash install_schedule.sh remove     # turn it off
# Check it later:  launchctl list | grep draftboard      Log: logs/daily.log
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
PY=/Library/Frameworks/Python.framework/Versions/3.14/bin/python3     # the python3 that has pybaseball
LABEL=com.seanvargas.draftboard
# The job STARTS at 4:45 so the site is LIVE by 5:30: the MLB build and first publish take ~25 min, the Pages
# deploy a couple more. (It used to start at 5:30, which put the day's numbers up closer to 6.)
HOUR=4
MINUTE=45
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
if [ "$1" = "remove" ]; then rm -f "$PLIST"; echo "removed $LABEL"; exit 0; fi
mkdir -p "$HOME/Library/LaunchAgents" "$HERE/logs"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>$PY</string><string>$HERE/daily_update.py</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>$HOUR</integer><key>Minute</key><integer>$MINUTE</integer></dict>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/draftboard.out</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/draftboard.err</string>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string></dict>
</dict>
</plist>
PL
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "installed: $LABEL runs daily_update.py every day at $HOUR:$MINUTE am, live by ~5:15 (asleep then? it runs when the Mac next wakes)"

# probe: can launchd's python3 read this folder?
PROBE=$HOME/Library/LaunchAgents/$LABEL.probe.plist
OUT=$HOME/Library/Logs/draftboard.probe
rm -f "$OUT"
cat > "$PROBE" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>$LABEL.probe</string>
<key>ProgramArguments</key><array><string>$PY</string><string>-c</string><string>open('$HERE/daily_update.py').close(); print('PASS')</string></array>
<key>StandardOutPath</key><string>$OUT</string><key>StandardErrorPath</key><string>$OUT</string>
</dict></plist>
PL
launchctl bootout "gui/$(id -u)/$LABEL.probe" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PROBE" && launchctl kickstart "gui/$(id -u)/$LABEL.probe"
sleep 3
launchctl bootout "gui/$(id -u)/$LABEL.probe" 2>/dev/null || true
rm -f "$PROBE"
if grep -q PASS "$OUT" 2>/dev/null; then
  echo "permission check: PASS — the schedule will work"
else
  cat <<MSG
permission check: BLOCKED — macOS won't let a background job read the Desktop folder yet. One-time fix:
  System Settings -> Privacy & Security -> Full Disk Access -> "+" -> press Cmd+Shift+G and paste
      /Library/Frameworks/Python.framework/Versions/3.14/Resources/Python.app
  -> Open ("Python" appears in the list) -> make sure its switch is on. Then run this script again to re-check.
MSG
fi
