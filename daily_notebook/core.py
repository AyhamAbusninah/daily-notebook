"""Storage and text logic. No GUI imports, so it is easy to test.

On disk, every day is one plain text file: <notes folder>/YYYY-MM-DD.md
Tasks are stored as "- [ ] text" / "- [x] text"; everything else is stored as typed.
Inside the editor, a task line starts with a checkbox character instead:
"\u2610 text" (open) or "\u2611 text" (done).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path

GLYPH_OPEN = "\u2610"
GLYPH_DONE = "\u2611"
TODO_RE = re.compile(r"^- \[( |x)\]( |$)")
OLD_SEP = "\n---\n"  # separator used by a very early version of the app
FILE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")


# ---------- text conversion ----------
def is_task_line(line: str) -> bool:
    return line[:1] in (GLYPH_OPEN, GLYPH_DONE) and (len(line) == 1 or line[1] == " ")


def to_editor_text(file_text: str) -> str:
    out = []
    for line in file_text.split("\n"):
        m = TODO_RE.match(line)
        if m:
            glyph = GLYPH_DONE if m.group(1) == "x" else GLYPH_OPEN
            out.append(glyph + " " + line[m.end():])
        else:
            out.append(line)
    return "\n".join(out)


def to_file_text(editor_text: str) -> str:
    out = []
    for line in editor_text.replace("\u2028", "\n").split("\n"):
        if is_task_line(line):
            mark = "x" if line[0] == GLYPH_DONE else " "
            out.append("- [%s] %s" % (mark, line[2:]))
        else:
            out.append(line)
    return "\n".join(out)


def migrate(text: str) -> str:
    """Very old files were 'task lines --- notes'. Merge them into one text."""
    head, sep, notes = text.partition(OLD_SEP)
    if sep and all(not l.strip() or TODO_RE.match(l) for l in head.splitlines()):
        head = head.strip("\n")
        return (head + "\n\n" + notes) if head else notes
    return text


def count_tasks(editor_text: str) -> tuple[int, int]:
    """(open, done) task counts of an editor text."""
    open_n = done_n = 0
    for line in editor_text.split("\n"):
        if is_task_line(line):
            if line[0] == GLYPH_DONE:
                done_n += 1
            else:
                open_n += 1
    return open_n, done_n


# ---------- settings ----------
def config_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "DailyNotebook"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "daily-notebook"


def load_settings() -> dict:
    try:
        with open(config_dir() / "config.json", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(settings: dict) -> None:
    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "config.json", "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def default_notes_dir(documents: Path | None = None) -> Path:
    """~/journal if it already holds pages (older versions used it), else Documents/Daily Notebook."""
    legacy = Path.home() / "journal"
    try:
        if legacy.is_dir() and any(FILE_RE.match(p.name) for p in legacy.iterdir()):
            return legacy
    except OSError:
        pass
    return (documents or Path.home() / "Documents") / "Daily Notebook"


def resolve_notes_dir(documents: Path | None = None) -> Path:
    chosen = load_settings().get("notes_dir")
    return Path(chosen) if chosen else default_notes_dir(documents)


# ---------- journal ----------
class Journal:
    def __init__(self, root: Path):
        self.root = Path(root)

    def path(self, day: dt.date) -> Path:
        return self.root / (day.isoformat() + ".md")

    def read(self, day: dt.date) -> str | None:
        """File text of a day, or None if there is no file."""
        try:
            with open(self.path(day), encoding="utf-8") as f:
                return migrate(f.read())
        except FileNotFoundError:
            return None

    def write(self, day: dt.date, text: str) -> None:
        """Atomic + durable write. Never deletes: clearing a page leaves an empty file."""
        p = self.path(day)
        if not text.strip() and not p.exists():
            return
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)

    def _files(self) -> list[tuple[dt.date, Path]]:
        out = []
        try:
            names = sorted(self.root.iterdir())
        except OSError:
            return out
        for p in names:
            if FILE_RE.match(p.name):
                try:
                    out.append((dt.date.fromisoformat(p.name[:10]), p))
                except ValueError:
                    pass
        return out

    def _read_path(self, p: Path) -> str:
        try:
            with open(p, encoding="utf-8") as f:
                return migrate(f.read())
        except OSError:
            return ""

    def days(self) -> list[dt.date]:
        """Days that have some content, oldest first."""
        return [d for d, p in self._files() if self._read_path(p).strip()]

    def open_tasks_before(self, day: dt.date) -> str:
        """Unfinished tasks of the most recent earlier page, as file text (for carry-over)."""
        for d, p in reversed([x for x in self._files() if x[0] < day]):
            lines = self._read_path(p).splitlines()
            tasks = []
            for l in lines:
                m = TODO_RE.match(l)
                if m and m.group(1) == " ":
                    tasks.append(l)
            if tasks:
                return "\n".join(tasks) + "\n\n"
            if any(l.strip() for l in lines):
                return ""
        return ""

    def search(self, query: str, limit: int = 300) -> list[tuple[dt.date, str]]:
        """Lines containing query (case-insensitive), newest day first. Lines are in editor form."""
        q = query.strip().lower()
        if not q:
            return []
        results = []
        for d, p in reversed(self._files()):
            for line in to_editor_text(self._read_path(p)).split("\n"):
                if q in line.lower():
                    results.append((d, line.strip()))
                    if len(results) >= limit:
                        return results
        return results

    def export_markdown(self, dest: Path) -> int:
        """All pages in one Markdown file, oldest first. Returns the number of pages."""
        n = 0
        with open(dest, "w", encoding="utf-8", newline="\n") as f:
            f.write("# Daily Notebook\n")
            for d, p in self._files():
                text = self._read_path(p).strip("\n")
                if not text.strip():
                    continue
                f.write("\n## %s (%s)\n\n%s\n" % (d.isoformat(), d.strftime("%A"), text))
                n += 1
        return n

    def backup_zip(self, dest: Path) -> int:
        n = 0
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            for d, p in self._files():
                z.write(p, p.name)
                n += 1
        return n

    def copy_to(self, new_root: Path) -> int:
        """Copy pages into another folder without overwriting existing ones."""
        new_root = Path(new_root)
        if new_root.resolve() == self.root.resolve():
            return 0
        new_root.mkdir(parents=True, exist_ok=True)
        n = 0
        for _d, p in self._files():
            target = new_root / p.name
            if not target.exists():
                shutil.copy2(p, target)
                n += 1
        return n
