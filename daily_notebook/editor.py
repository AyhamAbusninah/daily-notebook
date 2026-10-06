"""The writing area: plain text where any line can be a checkbox task."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import (QColor, QFont, QGuiApplication, QSyntaxHighlighter,
                           QTextCharFormat, QTextCursor)
from PySide6.QtWidgets import QFrame, QTextEdit

from .core import GLYPH_DONE, GLYPH_OPEN, is_task_line

ACCENT_LIGHT = "#9b3d2e"
ACCENT_DARK = "#d9826f"


def is_dark() -> bool:
    return QGuiApplication.palette().window().color().lightness() < 128


def prefix_len(text: str) -> int:
    """Length of the checkbox prefix ('☐ ') of a task line."""
    return min(2, len(text))


class TaskHighlighter(QSyntaxHighlighter):
    def __init__(self, document, base_pt: float):
        super().__init__(document)
        self.base_pt = base_pt

    def highlightBlock(self, text: str) -> None:
        if not is_task_line(text):
            return
        accent = QColor(ACCENT_DARK if is_dark() else ACCENT_LIGHT)
        glyph = QTextCharFormat()
        glyph.setForeground(accent)
        glyph.setFontPointSize(self.base_pt * 1.25)
        self.setFormat(0, 1, glyph)
        if text[0] == GLYPH_DONE and len(text) > 2:
            done = QTextCharFormat()
            done.setFontStrikeOut(True)
            done.setForeground(QColor("#8a8472"))
            self.setFormat(2, len(text) - 2, done)


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
        self.cursorPositionChanged.connect(self._guard_cursor)

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

    def toggle_done(self, block) -> None:
        text = block.text()
        if is_task_line(text):
            self._replace(block, 0, 1, GLYPH_OPEN if text[0] == GLYPH_DONE else GLYPH_DONE)

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
            if make and not is_task_line(text):
                self._replace(b, 0, 0, GLYPH_OPEN + " ")
            elif not make and is_task_line(text):
                self._replace(b, 0, prefix_len(text), "")
        edit.endEditBlock()
        self.setFocus()

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
        task = is_task_line(text)
        pos = cur.positionInBlock()
        plen = prefix_len(text)
        is_enter = key in (Qt.Key.Key_Return, Qt.Key.Key_Enter)

        if ctrl and key == Qt.Key.Key_T:
            self.toggle_task_lines()
            return
        if ctrl and is_enter:
            if task:
                self.toggle_done(block)
            return
        if is_enter and not ctrl and not cur.hasSelection():
            if task and pos >= plen:
                if text[plen:].strip() == "":
                    self._replace(block, 0, len(text), "")  # empty task + Enter = plain line
                else:
                    cur.insertText("\n" + GLYPH_OPEN + " ")
                    self.setTextCursor(cur)
                return
            if shift:  # avoid the invisible 'line separator' character
                cur.insertBlock()
                self.setTextCursor(cur)
                return
        if not (ctrl or alt) and not cur.hasSelection():
            if key == Qt.Key.Key_Backspace and task and pos == plen:
                self._replace(block, 0, plen, "")  # back to plain text
                return
            if key == Qt.Key.Key_Left and not shift and task and pos == plen:
                prev = block.previous()
                if prev.isValid():
                    self._place_cursor(prev.position() + len(prev.text()))
                return
            if key == Qt.Key.Key_Delete and pos == len(text):
                nxt = block.next()
                if nxt.isValid() and is_task_line(nxt.text()):
                    self._replace(nxt, 0, prefix_len(nxt.text()), "")  # joined line becomes plain
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
        text = block.text()
        if is_task_line(text) and c.positionInBlock() < prefix_len(text):
            self._guarding = True
            c.setPosition(block.position() + prefix_len(text))
            self.setTextCursor(c)
            self._guarding = False

    # ---------- mouse ----------
    def _on_checkbox(self, block, pt) -> bool:
        c0 = QTextCursor(block)
        c0.setPosition(block.position())
        c1 = QTextCursor(block)
        c1.setPosition(block.position() + 1)
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
