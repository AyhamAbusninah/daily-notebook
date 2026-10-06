import datetime as dt

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from daily_notebook import core
from daily_notebook.app import HistoryDialog, MainWindow

G_OPEN, G_DONE = core.GLYPH_OPEN, core.GLYPH_DONE


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(qapp, tmp_path):
    w = MainWindow(core.Journal(tmp_path))
    w.show()
    yield w
    w.dirty = False
    w.close()


def type_(w, text):
    QTest.keyClicks(w.editor, text)


def key(w, k, mods=Qt.KeyboardModifier.NoModifier):
    QTest.keyClick(w.editor, k, mods)


def text(w):
    return w.editor.toPlainText()


def test_plain_text_stays_plain(win):
    type_(win, "hello world")
    assert text(win) == "hello world"


def test_bracket_shortcut_makes_task(win):
    type_(win, "[] buy milk")
    assert text(win) == G_OPEN + " buy milk"


def test_enter_continues_and_ends_task_list(win):
    type_(win, "[] one")
    key(win, Qt.Key.Key_Return)
    assert text(win) == G_OPEN + " one\n" + G_OPEN + " "
    type_(win, "two")
    key(win, Qt.Key.Key_Return)
    key(win, Qt.Key.Key_Return)          # empty task + Enter -> plain line
    type_(win, "just a note")
    assert text(win) == G_OPEN + " one\n" + G_OPEN + " two\njust a note"


def test_ctrl_t_toggles_task(win):
    type_(win, "write report")
    key(win, Qt.Key.Key_T, Qt.KeyboardModifier.ControlModifier)
    assert text(win) == G_OPEN + " write report"
    key(win, Qt.Key.Key_T, Qt.KeyboardModifier.ControlModifier)
    assert text(win) == "write report"


def test_ctrl_t_on_several_lines(win):
    win.editor.setPlainText("a\nb\nc")
    win.editor.selectAll()
    key(win, Qt.Key.Key_T, Qt.KeyboardModifier.ControlModifier)
    assert text(win) == "\n".join(G_OPEN + " " + c for c in "abc")


def test_ctrl_enter_ticks(win):
    type_(win, "[] x")
    key(win, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    assert text(win) == G_DONE + " x"
    assert win.meta.text().endswith("0 open, 1 done")


def test_backspace_after_checkbox_makes_plain(win):
    type_(win, "[] x")
    key(win, Qt.Key.Key_Home)
    key(win, Qt.Key.Key_Backspace)
    assert text(win) == "x"


def test_click_on_checkbox_toggles(win):
    type_(win, "[] x")
    block = win.editor.document().firstBlock()
    from PySide6.QtGui import QTextCursor
    c = QTextCursor(block)
    c.setPosition(block.position())
    r0 = win.editor.cursorRect(c)
    c.setPosition(block.position() + 1)
    r1 = win.editor.cursorRect(c)
    pt = ((r0.x() + r1.x()) // 2, r0.center().y())
    QTest.mouseClick(win.editor.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     __import__("PySide6.QtCore", fromlist=["QPoint"]).QPoint(*pt))
    assert text(win) == G_DONE + " x"


def test_arabic_task_roundtrip(win):
    type_(win, "[] ")
    win.editor.insertPlainText("\u0627\u0634\u062a\u0631\u064a \u062d\u0644\u064a\u0628")
    win.save_now()
    assert win.journal.read(win.day) == "- [ ] \u0627\u0634\u062a\u0631\u064a \u062d\u0644\u064a\u0628"


def test_saves_file_format_and_reloads(win):
    type_(win, "[] a")
    key(win, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    key(win, Qt.Key.Key_End)
    key(win, Qt.Key.Key_Return)
    key(win, Qt.Key.Key_Return)
    type_(win, "note")
    win.save_now()
    assert win.journal.read(win.day) == "- [x] a\nnote"
    win.load()
    assert text(win) == G_DONE + " a\nnote"


def test_navigation_and_carry_over(win):
    today = dt.date.today()
    win.journal.write(today - dt.timedelta(days=3), "- [ ] old task\n- [x] finished\nnote")
    win.load()
    assert text(win) == G_OPEN + " old task\n\n"
    assert win.journal.read(today) == "- [ ] old task\n\n"     # written immediately
    win.go(-1)
    assert text(win) == ""
    win.go(1)
    assert text(win).startswith(G_OPEN + " old task")


def test_jump_far_back_and_history_search(win, qapp):
    far = dt.date.today() - dt.timedelta(days=45)
    win.journal.write(far, "- [ ] call the bank\nnotes")
    dlg = HistoryDialog(win.journal, win.day, win)
    dlg.search.setText("bank")
    assert dlg.results.count() == 1 and not dlg.calendar.isVisibleTo(dlg)
    dlg._pick_first_result()
    assert dlg.selected == far
    win.jump(dlg.selected)
    assert text(win) == G_OPEN + " call the bank\nnotes"


def test_clearing_page_never_deletes_file(win):
    type_(win, "important")
    win.save_now()
    win.editor.selectAll()
    key(win, Qt.Key.Key_Delete)
    win.save_now()
    assert win.journal.path(win.day).exists()


def test_selftest_entrypoint(qapp):
    from daily_notebook.app import selftest
    assert selftest() == 0
