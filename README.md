# Daily Notebook

A tiny desktop notebook for Linux: **one page per day**, free writing, and any line can become a **checkbox task**. Old pages stay available, and unfinished tasks carry over to the next day.

Built with Python + GTK4. One file (`notebook.py`), no dependencies beyond GTK4.

## Features

- One page per day. Flip through days with the arrows, or open the day list to see every past page with a preview.
- Write normally. A line is only a task when you make it one (`Ctrl+T`), so notes and tasks live on the same page.
- Real checkboxes. Ticking a task strikes it through; the header shows `N open, M done`.
- Unfinished tasks from your last page are copied to today's page automatically.
- Notes are plain text files in `~/journal/`, so you can `grep` them, back them up, or put them in git.

## Install

You need Python 3 and GTK4 for Python. On **Fedora Workstation** they are already installed.

```bash
git clone https://github.com/AyhamAbusninah/daily-notebook.git
cd daily-notebook
./install.sh
```

Then open **Daily Notebook** from your app launcher (press `Super` and type "notebook"), or run `daily-notebook` in a terminal.

If `install.sh` says GTK4 is missing, install it and run the script again:

| Distro | Command |
|---|---|
| Fedora | `sudo dnf install python3-gobject gtk4` |
| Debian / Ubuntu | `sudo apt install python3-gi gir1.2-gtk-4.0` |
| Arch | `sudo pacman -S python-gobject gtk4` |

No sudo is needed for the app itself. Everything is installed under `~/.local`.

## Run without installing

```bash
python3 notebook.py
```

## Keyboard shortcuts

| Keys | Action |
|---|---|
| `Ctrl+T` | Make the current line a task, or turn a task back into plain text |
| `Ctrl+Enter` | Tick / untick the task on the current line |
| `Enter` (on a task) | Start the next task |
| `Enter` (on an empty task) | Leave the task list, back to plain text |
| `Alt+Left` / `Alt+Right` | Previous / next day |

You can also click a checkbox, and use the checkbox button in the header bar instead of `Ctrl+T`.

## Where your notes are

`~/journal/YYYY-MM-DD.md`, one file per day. Tasks are saved as `- [ ] text` and `- [x] text`; everything else is saved exactly as typed.

To keep a history of everything you write:

```bash
cd ~/journal && git init && git add . && git commit -m "journal"
```

## Update

```bash
cd daily-notebook
git pull
./install.sh
```

## Uninstall

```bash
./uninstall.sh
```

This removes the app only. Your notes in `~/journal` are not touched.

## Troubleshooting

- **The app is not in the launcher.** Log out and back in, or run `update-desktop-database ~/.local/share/applications`.
- **After an update the old version opens.** The app is single-instance. Run `pkill -f notebook.py` and start it again.
- **`daily-notebook: command not found`.** Add `~/.local/bin` to your `PATH`, or launch it from the app launcher.

## License

MIT
