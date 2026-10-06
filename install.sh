#!/usr/bin/env bash
# Linux installer (per user, no sudo).
#  - From a release tarball (has a DailyNotebook/ folder next to this script): installs the ready-made app.
#  - From a git checkout: creates a Python virtualenv and installs the app + PySide6 from PyPI.
set -euo pipefail

APP_ID="io.github.dailynotebook"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHARE="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN="$HOME/.local/bin"
DEST="$SHARE/daily-notebook"

# stop a running copy (older versions too) so the new one starts
pkill -f "daily-notebook/(notebook\.py|venv|app)" 2>/dev/null || true

rm -rf "$DEST"
mkdir -p "$DEST" "$BIN" "$SHARE/applications" "$SHARE/icons/hicolor/scalable/apps"

if [ -x "$SRC/DailyNotebook/DailyNotebook" ]; then
  cp -r "$SRC/DailyNotebook" "$DEST/app"
  TARGET="$DEST/app/DailyNotebook"
else
  if ! command -v python3 >/dev/null; then
    echo "python3 not found. Install it first (Fedora: sudo dnf install python3)."; exit 1
  fi
  if ! python3 -m venv "$DEST/venv" 2>/dev/null; then
    echo "Could not create a Python virtualenv."
    echo "  Debian/Ubuntu: sudo apt install python3-venv"
    echo "  Fedora:        sudo dnf install python3"
    exit 1
  fi
  echo "Installing (downloads PySide6, about 100 MB)..."
  "$DEST/venv/bin/pip" install --quiet --upgrade pip
  "$DEST/venv/bin/pip" install --quiet "$SRC"
  TARGET="$DEST/venv/bin/daily-notebook"
fi

cat > "$BIN/daily-notebook" <<LAUNCHER
#!/usr/bin/env bash
exec "$TARGET" "\$@"
LAUNCHER
chmod 755 "$BIN/daily-notebook"

install -m 644 "$SRC/data/$APP_ID.svg" "$SHARE/icons/hicolor/scalable/apps/$APP_ID.svg"
cat > "$SHARE/applications/$APP_ID.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Daily Notebook
Comment=One page per day: free writing with checkbox tasks
Exec=$BIN/daily-notebook
Icon=$APP_ID
Terminal=false
Categories=Utility;TextEditor;
StartupNotify=true
DESKTOP

update-desktop-database "$SHARE/applications" 2>/dev/null || true
gtk-update-icon-cache -q -t "$SHARE/icons/hicolor" 2>/dev/null || true

echo "Installed. Open 'Daily Notebook' from your app launcher (press Super and type 'notebook')."
case ":$PATH:" in
  *":$BIN:"*) echo "Or run it from a terminal: daily-notebook" ;;
  *) echo "To run it from a terminal: $BIN/daily-notebook" ;;
esac
