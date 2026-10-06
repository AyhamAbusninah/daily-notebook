#!/usr/bin/env bash
# Removes the app. Your notes are NOT touched.
set -euo pipefail
APP_ID="io.github.dailynotebook"
SHARE="${XDG_DATA_HOME:-$HOME/.local/share}"
pkill -f "daily-notebook/(notebook\.py|venv|app)" 2>/dev/null || true
rm -rf "$SHARE/daily-notebook"
rm -f "$HOME/.local/bin/daily-notebook" \
      "$SHARE/applications/$APP_ID.desktop" \
      "$SHARE/icons/hicolor/scalable/apps/$APP_ID.svg"
update-desktop-database "$SHARE/applications" 2>/dev/null || true
gtk-update-icon-cache -q -t "$SHARE/icons/hicolor" 2>/dev/null || true
echo "Removed. Your notes were not touched."
