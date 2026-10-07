"""The writing area: plain text where any line can be a checkbox task, with one level of subtasks."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import (QColor, QFont, QGuiApplication, QSyntaxHighlighter,
                           QTextCharFormat, QTextCursor)
from PySide6.QtWidgets import QFrame, QTextEdit

from .core import GLYPH_DONE, GLYPH_OPEN, INDENT, is_task_line, task_info

ACCENT_LIGHT = "#9b3d2e"
ACCENT_DARK = "#d9826f"


def is_dark() -> bool:
    return QGuiApplication.palette().window().color().lightness() < 128


class TaskHighlighter(QSyntaxHighlighter):
    def __init__(self, document, base_pt: float):
        super().__init__(document)
        self.base_pt = base_pt

    def highlightBlock(self, text: str) -> None:
        info = task_info(text)
        if info is None:
            return
        depth, glyph_char, plen = info
        idx = len(INDENT) * depth
        accent = QColor(ACCENT_DARK if is_dark() else ACCENT_LIGHT)
        glyph = QTextCharFormat()
        glyph.setForeground(accent)
        glyph.setFontPointSize(self.base_pt * 1.25)
        self.setFormat(idx, 1, glyph)
        if glyph_char == GLYPH_DONE and len(text) > plen:
            done = QTextCharFormat()
            done.setFontStrikeOut(True)
            done.setForeground(QColor("#8a8472"))
            self.setFormat(plen, len(text) - plen, done)


class TaskEditor(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont()
        font.setFamilies(["Georgia", "DejaVu Serif", "Noto Serif", "Times New Roman", "serif"])
        font.setPointSizeF(13.5)
        self.setFont(font)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAcceptRichText(False)  # paste as plain text
        self.setPlaceholderText("Write here. Type [] and a space to add a task.")
        self.setTabChangesFocus(False)
        # each paragraph picks its own direction, so Arabic lines are right-to-left
        opt = self.document().defaultTextOption()
        opt.setTextDirection(Qt.LayoutDirection.LayoutDirectionAuto)
        self.document().setDefaultTextOption(opt)
        self._highlighter = TaskHighlighter(self.document(), font.pointSizeF())
        self._guarding = False
        self._sync_enabled = True
        self._sync_scheduled = False
        self.cursorPositionChanged.connect(self._guard_cursor)
        self.textChanged.connect(self._schedule_sync)

    def setPlainText(self, text: str) -> None:
        """Loading a page must not change it (no parent auto-ticking)."""
        self._sync_enabled = False
        super().setPlainText(text)
        self._sync_enabled = True

    # ---------- small edit helpers ----------
    def _replace(self, block, start: int, end: int, text: str) -> None:
        c = QTextCursor(block)
        c.setPosition(block.position() + start)
        c.setPosition(block.position() + end, QTextCursor.MoveMode.KeepAnchor)
        c.insertText(text)

    def _place_cursor(self, pos: int, keep_anchor: bool = False) -> None:
        c = self.textCursor()
        mode = QTextCursor.MoveMode.KeepAnchor if keep_anchor else QTextCursor.MoveMode.MoveAnchor
        c.setPosition(pos, mode)
        self.setTextCursor(c)

    def _set_glyph(self, block, glyph: str) -> None:
        info = task_info(block.text())
        if info and info[1] != glyph:
            idx = len(INDENT) * info[0]
            self._replace(block, idx, idx + 1, glyph)

    def _children(self, block) -> list:
        """The subtasks directly below a main task."""
        kids = []
        b = block.next()
        while b.isValid():
            info = task_info(b.text())
            if info and info[0] == 1:
                kids.append(b)
                b = b.next()
            else:
                break
        return kids

    # ---------- parent / subtask rule ----------
    # A main task that has subtasks is done exactly when all of its subtasks are done.
    def _sync_changes(self) -> list:
        changes = []
        b = self.document().firstBlock()
        while b.isValid():
            info = task_info(b.text())
            if info and info[0] == 0:
                kids = self._children(b)
                if kids:
                    all_done = all(task_info(k.text())[1] == GLYPH_DONE for k in kids)
                    want = GLYPH_DONE if all_done else GLYPH_OPEN
                    if info[1] != want:
                        changes.append((b, want))
            b = b.next()
        return changes

    def _schedule_sync(self) -> None:
        if self._sync_enabled and not self._sync_scheduled:
            self._sync_scheduled = True
            QTimer.singleShot(0, self._sync_parents)

    def _sync_parents(self) -> None:
        self._sync_scheduled = False
        changes = self._sync_changes()
        if not changes:
            return
        edit = QTextCursor(self.document())
        edit.joinPreviousEditBlock()  # same undo step as the edit that caused it
        for b, want in changes:
            self._set_glyph(b, want)
        edit.endEditBlock()

    # ---------- task actions ----------
    def toggle_done(self, block) -> None:
        info = task_info(block.text())
        if info is None:
            return
        depth, glyph, _plen = info
        new = GLYPH_OPEN if glyph == GLYPH_DONE else GLYPH_DONE
        edit = QTextCursor(self.document())
        edit.beginEditBlock()
        self._set_glyph(block, new)
        if depth == 0:
            for kid in self._children(block):  # ticking a main task ticks all its subtasks
                self._set_glyph(kid, new)
        else:
            for b, want in self._sync_changes():  # the parent follows its subtasks
                self._set_glyph(b, want)
        edit.endEditBlock()

    def toggle_task_lines(self) -> None:
        """Ctrl+T / '+ Task' button: make the current line(s) tasks, or plain text again."""
        cur = self.textCursor()
        doc = self.document()
        first = doc.findBlock(cur.selectionStart())
        last = doc.findBlock(cur.selectionEnd())
        if cur.hasSelection() and last.blockNumber() > first.blockNumber() \
                and cur.selectionEnd() == last.position():
            last = last.previous()
        blocks = []
        b = first
        while b.isValid() and b.blockNumber() <= last.blockNumber():
            blocks.append(b)
            b = b.next()
        if len(blocks) > 1:
            blocks = [b for b in blocks if b.text().strip()]
        if not blocks:
            return
        make = not all(is_task_line(b.text()) for b in blocks)
        edit = QTextCursor(doc)
        edit.beginEditBlock()
        for b in reversed(blocks):
            text = b.text()
            info = task_info(text)
            if make and info is None:
                self._replace(b, 0, 0, GLYPH_OPEN + " ")
            elif not make and info is not None:
                self._replace(b, 0, info[2], "")
        edit.endEditBlock()
        self.setFocus()

    def _indent(self, block) -> None:
        """Tab: make a task a subtask of the task above it."""
        prev = block.previous()
        if prev.isValid() and is_task_line(prev.text()) and not self._children(block):
            self._replace(block, 0, 0, INDENT)

    def _outdent(self, block) -> None:
        self._replace(block, 0, len(INDENT), "")

    # ---------- keyboard ----------
    def keyPressEvent(self, e) -> None:
        key = e.key()
        mods = e.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        alt = bool(mods & Qt.KeyboardModifier.AltModifier)
        cur = self.textCursor()
        block = cur.block()
        text = block.text()
        info = task_info(text)
        task = info is not None
        depth = info[0] if task else 0
        plen = info[2] if task else 0
        pos = cur.positionInBlock()
        is_enter = key in (Qt.Key.Key_Return, Qt.Key.Key_Enter)

        if ctrl and key == Qt.Key.Key_T:
            self.toggle_task_lines()
            return
        if ctrl and is_enter:
            if task:
                self.toggle_done(block)
            return
        if task and key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab) and not (ctrl or alt):
            if key == Qt.Key.Key_Backtab or shift:
                if depth == 1:
                    self._outdent(block)
            elif depth == 0:
                self._indent(block)
            return
        if is_enter and not ctrl and not cur.hasSelection():
            if task and pos >= plen:
                if text[plen:].strip() == "":
                    if depth == 1:
                        self._outdent(block)  # empty subtask + Enter: back to a main task
                    else:
                        self._replace(block, 0, len(text), "")  # empty task + Enter: plain line
                else:
                    new_depth = depth
                    if depth == 0 and pos == len(text) and self._children(block):
                        new_depth = 1  # Enter at the end of a task that has subtasks: add one
                    cur.insertText("\n" + INDENT * new_depth + GLYPH_OPEN + " ")
                    self.setTextCursor(cur)
                return
            if shift:  # avoid the invisible 'line separator' character
                cur.insertBlock()
                self.setTextCursor(cur)
                return
        if not (ctrl or alt) and not cur.hasSelection():
            if key == Qt.Key.Key_Backspace and task and pos == plen:
                if depth == 1:
                    self._outdent(block)  # subtask -> main task
                else:
                    self._replace(block, 0, plen, "")  # main task -> plain text
                return
            if key == Qt.Key.Key_Left and not shift and task and pos == plen:
                prev = block.previous()
                if prev.isValid():
                    self._place_cursor(prev.position() + len(prev.text()))
                return
            if key == Qt.Key.Key_Delete and pos == len(text):
                nxt = block.next()
                nxt_info = task_info(nxt.text()) if nxt.isValid() else None
                if nxt_info:
                    self._replace(nxt, 0, nxt_info[2], "")  # joined line becomes plain
        if key == Qt.Key.Key_Home and not ctrl and task:
            self._place_cursor(block.position() + plen, keep_anchor=shift)
            return

        super().keyPressEvent(e)

        if e.text() == " " and not cur.hasSelection():
            self._autoconvert()

    def _autoconvert(self) -> None:
        """'[] ' or '[ ] ' or '- [ ] ' typed at the start of a line becomes a checkbox."""
        c = self.textCursor()
        block = c.block()
        text = block.text()
        pos = c.positionInBlock()
        for prefix in ("- [ ] ", "[ ] ", "[] "):
            if text.startswith(prefix) and pos == len(prefix):
                edit = QTextCursor(self.document())
                edit.beginEditBlock()
                self._replace(block, 0, len(prefix), GLYPH_OPEN + " ")
                edit.endEditBlock()
                self._place_cursor(block.position() + 2)
                return

    def _guard_cursor(self) -> None:
        """Keep the caret after the checkbox, never in front of it."""
        if self._guarding:
            return
        c = self.textCursor()
        if c.hasSelection():
            return
        block = c.block()
        info = task_info(block.text())
        if info and c.positionInBlock() < info[2]:
            self._guarding = True
            c.setPosition(block.position() + info[2])
            self.setTextCursor(c)
            self._guarding = False

    # ---------- mouse ----------
    def _on_checkbox(self, block, pt) -> bool:
        info = task_info(block.text())
        idx = len(INDENT) * info[0]
        c0 = QTextCursor(block)
        c0.setPosition(block.position() + idx)
        c1 = QTextCursor(block)
        c1.setPosition(block.position() + idx + 1)
        r0, r1 = self.cursorRect(c0), self.cursorRect(c1)
        x0, x1 = sorted((r0.x(), r1.x()))
        return x0 - 4 <= pt.x() <= x1 + 4 and r0.top() - 2 <= pt.y() <= r0.bottom() + 2

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and not self.textCursor().hasSelection():
            pt = e.position().toPoint()
            block = self.cursorForPosition(pt).block()
            if is_task_line(block.text()) and self._on_checkbox(block, pt):
                self.toggle_done(block)
                e.accept()
                return
        super().mouseReleaseEvent(e)
