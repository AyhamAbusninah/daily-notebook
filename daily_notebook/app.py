"""Daily Notebook: one page per day, free writing, checkbox tasks."""
from __future__ import annotations

import datetime as dt
import os
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QDate, QLockFile, QStandardPaths, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut, QTextCharFormat, QFont, QColor
from PySide6.QtWidgets import (QApplication, QCalendarWidget, QDialog, QFileDialog, QFrame,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMainWindow, QMenu, QMessageBox, QPushButton, QToolButton,
                               QVBoxLayout, QWidget)

from . import __version__, core
from .editor import ACCENT_DARK, ACCENT_LIGHT, TaskEditor, is_dark
from .icon import app_icon

APP_ID = "io.github.dailynotebook"

PAGE_QSS = """
#title { font-family: Georgia, 'DejaVu Serif', 'Noto Serif', serif; font-size: 24px; }
#meta { font-size: 13px; color: gray; }
"""


class HistoryDialog(QDialog):
    """Jump to any day with a calendar, or search the text of every page."""

    def __init__(self, journal: core.Journal, current: dt.date, parent=None):
        super().__init__(parent)
        self.setWindowTitle("History")
        self.resize(400, 460)
        self.journal = journal
        self.selected: dt.date | None = None

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search all pages...")
        self.search.setClearButtonEnabled(True)
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(False)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.results = QListWidget()
        self.results.setVisible(False)

        layout = QVBoxLayout(self)
        layout.addWidget(self.search)
        layout.addWidget(self.calendar)
        layout.addWidget(self.results)

        marked = QTextCharFormat()
        marked.setFontWeight(QFont.Weight.Bold)
        marked.setForeground(QColor("#ffffff"))
        marked.setBackground(QColor(ACCENT_DARK if is_dark() else ACCENT_LIGHT))
        plain = QTextCharFormat()
        plain.setForeground(self.palette().text().color())
        for wd in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
            self.calendar.setWeekdayTextFormat(wd, plain)  # no red weekends: red is for pages
        for d in journal.days():
            self.calendar.setDateTextFormat(QDate(d.year, d.month, d.day), marked)
        self.calendar.setSelectedDate(QDate(current.year, current.month, current.day))

        self.calendar.clicked.connect(self._pick_date)
        self.calendar.activated.connect(self._pick_date)
        self.search.textChanged.connect(self._search)
        self.search.returnPressed.connect(self._pick_first_result)
        self.results.itemActivated.connect(self._pick_item)
        self.results.itemClicked.connect(self._pick_item)
        self.search.setFocus()

    def _pick_date(self, qd: QDate) -> None:
        self.selected = dt.date(qd.year(), qd.month(), qd.day())
        self.accept()

    def _search(self, text: str) -> None:
        text = text.strip()
        self.results.clear()
        self.calendar.setVisible(not text)
        self.results.setVisible(bool(text))
        if not text:
            return
        hits = self.journal.search(text)
        for d, line in hits:
            item = QListWidgetItem("%s   %s" % (d.isoformat(), line))
            item.setData(Qt.ItemDataRole.UserRole, d)
            self.results.addItem(item)
        if not hits:
            item = QListWidgetItem("No matches")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.results.addItem(item)

    def _pick_item(self, item: QListWidgetItem) -> None:
        d = item.data(Qt.ItemDataRole.UserRole)
        if d:
            self.selected = d
            self.accept()

    def _pick_first_result(self) -> None:
        if not self.results.isHidden() and self.results.count():
            self._pick_item(self.results.item(0))


class MainWindow(QMainWindow):
    def __init__(self, journal: core.Journal, documents: Path | None = None):
        super().__init__()
        self.journal = journal
        self.documents = documents
        self.day = dt.date.today()
        self.loading = False
        self.dirty = False
        self.setWindowTitle("Daily Notebook")
        self.setWindowIcon(app_icon())
        self.resize(620, 760)

        # top bar
        self.prev_b = QToolButton()
        self.prev_b.setArrowType(Qt.ArrowType.LeftArrow)
        self.prev_b.setToolTip("Previous day (Alt+Left)")
        self.next_b = QToolButton()
        self.next_b.setArrowType(Qt.ArrowType.RightArrow)
        self.next_b.setToolTip("Next day (Alt+Right)")
        today_b = QPushButton("Today")
        history_b = QPushButton("History")
        history_b.setToolTip("Calendar and search (Ctrl+F)")
        task_b = QPushButton("+ Task")
        task_b.setToolTip("Make this line a task (Ctrl+T, or type [] and a space)")
        menu_b = QToolButton()
        menu_b.setText("\u22ef")
        menu_b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(menu_b)
        menu.addAction("Open notes folder", self.open_folder)
        menu.addAction("Change notes folder...", self.change_folder)
        menu.addSeparator()
        menu.addAction("Export all pages as one Markdown file...", self.export_md)
        menu.addAction("Back up all pages as .zip...", self.backup_zip)
        menu_b.setMenu(menu)
        self.menu_b = menu_b

        bar = QHBoxLayout()
        for w in (self.prev_b, self.next_b, today_b):
            bar.addWidget(w)
        bar.addStretch(1)
        for w in (history_b, task_b, menu_b):
            bar.addWidget(w)

        # page
        self.title = QLabel()
        self.title.setObjectName("title")
        self.meta = QLabel()
        self.meta.setObjectName("meta")
        self.editor = TaskEditor()
        stripe = QFrame()
        stripe.setFixedWidth(4)
        stripe.setStyleSheet("background-color: %s;" % (ACCENT_DARK if is_dark() else ACCENT_LIGHT))
        content = QVBoxLayout()
        content.setContentsMargins(0, 4, 0, 4)
        content.addWidget(self.title)
        content.addWidget(self.meta)
        content.addWidget(self.editor, 1)
        page = QWidget()
        page.setStyleSheet(PAGE_QSS)
        pl = QHBoxLayout(page)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(14)
        pl.addWidget(stripe)
        pl.addLayout(content, 1)

        root = QWidget()
        lay = QVBoxLayout(root)
        lay.addLayout(bar)
        lay.addWidget(page, 1)
        self.setCentralWidget(root)

        # saving: shortly after typing stops, on page change, and on close
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(600)
        self.timer.timeout.connect(self.save_now)
        self.editor.textChanged.connect(self._changed)

        self.prev_b.clicked.connect(lambda: self.go(-1))
        self.next_b.clicked.connect(lambda: self.go(1))
        today_b.clicked.connect(lambda: self.jump(dt.date.today()))
        history_b.clicked.connect(self.open_history)
        task_b.clicked.connect(self.editor.toggle_task_lines)
        QShortcut(QKeySequence("Alt+Left"), self, activated=lambda: self.go(-1))
        QShortcut(QKeySequence("Alt+Right"), self, activated=lambda: self.go(1))
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.open_history)

        self.load()

    # ---------- pages ----------
    def go(self, n: int) -> None:
        self.jump(self.day + dt.timedelta(days=n))

    def jump(self, day: dt.date) -> None:
        self.save_now()
        self.day = day
        self.load()

    def load(self) -> None:
        self.loading = True
        text = self.journal.read(self.day)
        existed = text is not None
        if not existed:
            text = self.journal.open_tasks_before(self.day) if self.day == dt.date.today() else ""
        self.editor.setPlainText(core.to_editor_text(text))
        self.editor.document().clearUndoRedoStacks()
        self.loading = False
        self.dirty = bool(text) and not existed  # carried-over tasks get written right away
        self.title.setText(self.day.strftime("%A, %d %B %Y"))
        self._update_meta()
        self.save_now()
        cursor = self.editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def _changed(self) -> None:
        if self.loading:
            return
        self.dirty = True
        self.timer.start()
        self._update_meta()

    def _update_meta(self, error: str = "") -> None:
        parts = []
        if self.day == dt.date.today():
            parts.append("Today")
        open_n, done_n = core.count_tasks(self.editor.toPlainText())
        if open_n or done_n:
            parts.append("%d open, %d done" % (open_n, done_n))
        if error:
            parts.append("\u26a0 could not save: " + error)
        self.meta.setText("  \u00b7  ".join(parts))

    def save_now(self) -> None:
        self.timer.stop()
        if not self.dirty or self.loading:
            return
        try:
            self.journal.write(self.day, core.to_file_text(self.editor.toPlainText()))
            self.dirty = False
            self._update_meta()
        except OSError as exc:
            self._update_meta(str(exc))
            self.timer.start(5000)  # try again in a few seconds

    def closeEvent(self, event) -> None:
        self.save_now()
        event.accept()

    # ---------- history ----------
    def open_history(self) -> None:
        self.save_now()
        dlg = HistoryDialog(self.journal, self.day, self)
        if dlg.exec() and dlg.selected:
            self.jump(dlg.selected)

    # ---------- storage menu ----------
    def open_folder(self) -> None:
        self.journal.root.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.journal.root)))

    def change_folder(self) -> None:
        self.save_now()
        chosen = QFileDialog.getExistingDirectory(self, "Choose notes folder", str(self.journal.root))
        if not chosen:
            return
        new = Path(chosen)
        if new.resolve() == self.journal.root.resolve():
            return
        n = len(self.journal.days())
        if n:
            ans = QMessageBox.question(
                self, "Copy your pages?",
                "Copy your %d existing pages to the new folder?\n(The originals stay where they are.)" % n)
            if ans == QMessageBox.StandardButton.Yes:
                self.journal.copy_to(new)
        settings = core.load_settings()
        settings["notes_dir"] = str(new)
        core.save_settings(settings)
        self.journal = core.Journal(new)
        self.menu_b.setToolTip(str(new))
        self.load()

    def export_md(self) -> None:
        self.save_now()
        name = "daily-notebook-%s.md" % dt.date.today().isoformat()
        path, _ = QFileDialog.getSaveFileName(self, "Export as Markdown", str(Path.home() / name),
                                              "Markdown (*.md)")
        if path:
            n = self.journal.export_markdown(Path(path))
            QMessageBox.information(self, "Exported", "Exported %d pages to\n%s" % (n, path))

    def backup_zip(self) -> None:
        self.save_now()
        name = "daily-notebook-backup-%s.zip" % dt.date.today().isoformat()
        path, _ = QFileDialog.getSaveFileName(self, "Back up as zip", str(Path.home() / name),
                                              "Zip file (*.zip)")
        if path:
            n = self.journal.backup_zip(Path(path))
            QMessageBox.information(self, "Backed up", "Saved %d pages to\n%s" % (n, path))


def documents_dir() -> Path:
    loc = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    return Path(loc) if loc else Path.home() / "Documents"


def selftest() -> int:
    """Build the window, type, save, reload. Used by CI on the packaged app."""
    with tempfile.TemporaryDirectory() as tmp:
        win = MainWindow(core.Journal(Path(tmp)))
        win.show()
        win.editor.setPlainText("\u2610 task one\nplain note")
        win.save_now()
        saved = win.journal.read(win.day)
        win.load()
        ok = saved == "- [ ] task one\nplain note" and win.editor.toPlainText().startswith("\u2610 task one")
        print("selftest", "ok" if ok else "FAILED", "version", __version__)
        return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if "--selftest" in argv:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication(argv)
    app.setApplicationName("Daily Notebook")
    app.setDesktopFileName(APP_ID)
    app.setWindowIcon(app_icon())
    if "--selftest" in argv:
        return selftest()

    cfg = core.config_dir()
    cfg.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(cfg / "app.lock"))  # keep a reference alive until exit
    if not lock.tryLock(100):
        QMessageBox.information(None, "Daily Notebook", "Daily Notebook is already running.")
        return 0

    docs = documents_dir()
    root = core.resolve_notes_dir(docs)
    win = MainWindow(core.Journal(root), docs)
    win.menu_b.setToolTip(str(root))
    win.show()
    code = app.exec()
    lock.unlock()
    return code


if __name__ == "__main__":
    sys.exit(main())
