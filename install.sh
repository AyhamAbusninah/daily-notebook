#!/usr/bin/env bash
# Installs Daily Notebook for the current user (no sudo needed).
set -euo pipefail

APP_ID="io.github.dailynotebook"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHARE="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN="$HOME/.local/bin"
DEST="$SHARE/daily-notebook"

if ! python3 -c "import gi; gi.require_version('Gtk','4.0'); from gi.repository import Gtk" 2>/dev/null; then
  echo "GTK4 for Python is missing. Install it first, then run this script again:"
  echo "  Fedora:        sudo dnf install python3-gobject gtk4"
  echo "  Debian/Ubuntu: sudo apt install python3-gi gir1.2-gtk-4.0"
  echo "  Arch:          sudo pacman -S python-gobject gtk4"
  exit 1
fi

# The app is single-instance: stop an old running copy so the new version starts.
pkill -f "daily-notebook/notebook.py" 2>/dev/null || true

mkdir -p "$DEST" "$BIN" "$SHARE/applications" "$SHARE/icons/hicolor/scalable/apps"
install -m 755 "$SRC/notebook.py" "$DEST/notebook.py"
install -m 644 "$SRC/data/$APP_ID.svg" "$SHARE/icons/hicolor/scalable/apps/$APP_ID.svg"

cat > "$BIN/daily-notebook" <<LAUNCHER
#!/usr/bin/env bash
exec python3 "$DEST/notebook.py" "\$@"
LAUNCHER
chmod 755 "$BIN/daily-notebook"

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
  *) echo "To run it from a terminal, add $BIN to your PATH, or run: $BIN/daily-notebook" ;;
esac
