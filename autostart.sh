#!/usr/bin/env bash
# Install / uninstall a macOS LaunchAgent that auto-starts the Boswell menu
# bar app on login. The agent restarts the process if it crashes but respects
# a clean Quit from the menu (won't re-launch until next login).
#
# Usage:
#   ./autostart.sh install   # enable auto-launch on login, start now
#   ./autostart.sh uninstall # disable
#   ./autostart.sh status    # show whether it's loaded

set -euo pipefail

LABEL="com.${USER}.boswell"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
ENV_NAME="${BOSWELL_ENV_NAME:-boswell}"
OUT_LOG="$HOME/Library/Logs/boswell.out.log"
ERR_LOG="$HOME/Library/Logs/boswell.err.log"

# Resolve the real micromamba binary (shell function isn't visible here).
if [[ -n "${MAMBA_EXE:-}" && -x "$MAMBA_EXE" ]]; then
  MICROMAMBA="$MAMBA_EXE"
elif [[ -x "$HOME/.local/bin/micromamba" ]]; then
  MICROMAMBA="$HOME/.local/bin/micromamba"
elif [[ -n "${MAMBA_ROOT_PREFIX:-}" && -x "$MAMBA_ROOT_PREFIX/bin/micromamba" ]]; then
  MICROMAMBA="$MAMBA_ROOT_PREFIX/bin/micromamba"
else
  echo "micromamba binary not found — set \$MAMBA_EXE." >&2
  exit 1
fi

cmd="${1:-install}"

# Best-effort cleanup of the legacy notetaker launch agent if present.
LEGACY_LABEL="com.${USER}.notetaker"
LEGACY_PLIST="$HOME/Library/LaunchAgents/$LEGACY_LABEL.plist"
cleanup_legacy() {
  if [[ -f "$LEGACY_PLIST" ]]; then
    launchctl bootout "gui/$UID/$LEGACY_LABEL" 2>/dev/null || true
    rm -f "$LEGACY_PLIST"
    echo "Removed legacy agent: $LEGACY_LABEL"
  fi
  # Also catch the original hardcoded label from pre-rename installs.
  local OLD="com.rdahale.notetaker"
  local OLD_PLIST="$HOME/Library/LaunchAgents/$OLD.plist"
  if [[ -f "$OLD_PLIST" ]]; then
    launchctl bootout "gui/$UID/$OLD" 2>/dev/null || true
    rm -f "$OLD_PLIST"
    echo "Removed legacy agent: $OLD"
  fi
}

case "$cmd" in
  install)
    cleanup_legacy
    mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
    cat >"$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$MICROMAMBA</string>
        <string>run</string>
        <string>-n</string>
        <string>$ENV_NAME</string>
        <string>python</string>
        <string>-m</string>
        <string>boswell</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>ProcessType</key>
    <string>Interactive</string>
    <key>StandardOutPath</key>
    <string>$OUT_LOG</string>
    <key>StandardErrorPath</key>
    <string>$ERR_LOG</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>MAMBA_ROOT_PREFIX</key>
        <string>${MAMBA_ROOT_PREFIX:-$HOME/micromamba}</string>
    </dict>
</dict>
</plist>
EOF
    # If already loaded, bootout first so we pick up changes.
    launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
    launchctl bootstrap "gui/$UID" "$PLIST"
    launchctl kickstart -k "gui/$UID/$LABEL"
    echo "Installed and started: $LABEL"
    echo "Logs: $OUT_LOG and $ERR_LOG"
    ;;
  uninstall)
    launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    cleanup_legacy
    echo "Uninstalled: $LABEL"
    ;;
  status)
    if launchctl print "gui/$UID/$LABEL" >/dev/null 2>&1; then
      echo "Loaded."
      launchctl print "gui/$UID/$LABEL" | grep -E "state|last exit code|pid" | head
    else
      echo "Not loaded."
    fi
    ;;
  *)
    echo "Usage: $0 {install|uninstall|status}" >&2
    exit 2
    ;;
esac
