# Daily Notebook

A small desktop notebook for **Linux and Windows**: one page per day, free writing, and any line can be a checkbox task. Old pages stay available, and unfinished tasks carry over to the next day.

Built with Python and Qt (PySide6). Right-to-left text (Arabic, Hebrew) works: those lines are right-aligned and the checkbox sits on the right.

## Download and run

Go to the **[Releases page](https://github.com/AyhamAbusninah/daily-notebook/releases/latest)** and download the file for your system.

### Windows

1. Download `DailyNotebook-windows-x64.zip` and unzip it.
2. Double-click `DailyNotebook.exe` inside the folder.

The app is not code-signed, so Windows SmartScreen may warn you the first time. Click **More info**, then **Run anyway**.

### Linux

1. Download `DailyNotebook-linux-x86_64.tar.gz`.
2. Install it:
   ```bash
   mkdir daily-notebook && tar -xzf DailyNotebook-linux-x86_64.tar.gz -C daily-notebook
   cd daily-notebook && ./install.sh
   ```
3. Open **Daily Notebook** from your app launcher (press `Super` and type "notebook").

No sudo is needed. Everything is installed under `~/.local`.

### Linux, from source (if you prefer)

```bash
git clone https://github.com/AyhamAbusninah/daily-notebook.git
cd daily-notebook
./install.sh
```

This needs Python 3 with `venv` (on Debian/Ubuntu: `sudo apt install python3-venv`). It downloads PySide6 (about 100 MB) into a private virtualenv.

## How to use

- **Write normally.** A line is a task only when you make it one.
- **Make a task:** type `[]` and a space at the start of a line, or press `Ctrl+T`, or click **+ Task**. Select several lines first to convert them all at once.
- **Tick a task:** click its checkbox, or press `Ctrl+Enter`. Done tasks are struck through.
- **Enter** on a task starts the next task. **Enter** on an empty task goes back to plain text. **Backspace** right after a checkbox turns it back into plain text.
- **Go to another day:** the arrows, **Today**, or **History** (`Ctrl+F`): a calendar where days with pages are highlighted, plus a search box that looks through every page.
- **Subtasks:** press `Tab` on a task to make it a subtask of the task above, and `Shift+Tab` to bring it back. `Enter` on a subtask adds another subtask; `Enter` on an empty subtask goes back to a main task. A task with subtasks is marked done automatically when all its subtasks are done, and reopens if you add or untick one. Ticking the main task ticks all its subtasks. (One level of subtasks.)
- Unfinished tasks from your last page are copied to today's page automatically.

| Keys | Action |
|---|---|
| `[]` + space | Make a task |
| `Ctrl+T` | Make the line(s) a task, or plain text again |
| `Ctrl+Enter` | Tick / untick the task |
| `Ctrl+F` | History: calendar and search |
| `Tab` / `Shift+Tab` | Make a task a subtask / back to a main task |
| `Alt+Left` / `Alt+Right` | Previous / next day |

## Your notes

Each day is one plain text file, `YYYY-MM-DD.md`, in your notes folder:

- **Windows / Linux default:** `Documents/Daily Notebook` (or `~/journal` if you already used an older version).
- Menu **...** > **Open notes folder** shows it. **Change notes folder...** moves the app to another folder (and can copy your pages there).

Tasks are saved as `- [ ] text` and `- [x] text`; everything else is saved exactly as typed. The app never deletes a page: clearing a page leaves an empty file.

**Keeping your notes for good:**

- **Export all pages as one Markdown file** (menu **...**): one readable file with every day in order. Good as a keepsake.
- **Back up all pages as .zip** (menu **...**).
- The folder is plain files, so you can also sync it (Syncthing, OneDrive, Dropbox) or put it in git. Close the app before editing the files from another device.

## Uninstall

- **Windows:** delete the `DailyNotebook` folder.
- **Linux:** run `./uninstall.sh` from the folder you installed from.

Your notes are never removed.

## Troubleshooting

- **Linux: the app does not start from the tarball and mentions `xcb`.** Install the missing Qt library: Fedora `sudo dnf install xcb-util-cursor`, Debian/Ubuntu `sudo apt install libxcb-cursor0`.
- **Linux: the app is not in the launcher.** Log out and back in, or run `update-desktop-database ~/.local/share/applications`.
- **"Daily Notebook is already running."** Only one copy can be open, so two windows never edit the same page.
- **A page did not save.** The line under the date shows a warning. Check that the notes folder exists and is writable.

## Development

```bash
pip install PySide6-Essentials pytest
QT_QPA_PLATFORM=offscreen python -m pytest      # core logic + UI tests, no display needed
python -m daily_notebook                         # run from source
```

- `daily_notebook/core.py`: storage, search, export, carry-over (no GUI code).
- `daily_notebook/editor.py`: the text editor with checkbox lines.
- `daily_notebook/app.py`: window, History dialog, menu.

### Publishing a release

Pushing a version tag builds the Windows and Linux packages on GitHub and attaches them to a release:

```bash
git tag v1.0.0
git push origin v1.0.0
```

The build runs the tests, packages the app with PyInstaller, and runs `--selftest` on the packaged app (on both Windows and Linux) before publishing.

## License

MIT
