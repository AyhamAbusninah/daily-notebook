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


# ---------- subtasks ----------
from PySide6.QtWidgets import QApplication as _QA  # noqa: E402

SUB = "    "


def pump():
    _QA.processEvents()


def blocks(w):
    return text(w).split("\n")


def make_parent_with_kids(w):
    type_(w, "[] trip")
    key(w, Qt.Key.Key_Return)
    type_(w, "tickets")
    key(w, Qt.Key.Key_Tab)
    key(w, Qt.Key.Key_Return)
    type_(w, "hotel")
    pump()


def test_tab_makes_subtask_and_enter_continues_it(win):
    make_parent_with_kids(win)
    assert text(win) == f"{G_OPEN} trip\n{SUB}{G_OPEN} tickets\n{SUB}{G_OPEN} hotel"


def test_tab_without_task_above_does_nothing(win):
    type_(win, "[] only")
    key(win, Qt.Key.Key_Tab)
    assert text(win) == G_OPEN + " only"


def test_shift_tab_and_backspace_outdent(win):
    make_parent_with_kids(win)
    key(win, Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier)
    pump()
    assert blocks(win)[2] == G_OPEN + " hotel"
    key(win, Qt.Key.Key_Tab)
    pump()
    assert blocks(win)[2] == SUB + G_OPEN + " hotel"
    key(win, Qt.Key.Key_Home)
    key(win, Qt.Key.Key_Backspace)                  # subtask -> main task
    assert blocks(win)[2] == G_OPEN + " hotel"
    key(win, Qt.Key.Key_Home)
    key(win, Qt.Key.Key_Backspace)                  # main task -> plain
    assert blocks(win)[2] == "hotel"


def test_empty_subtask_enter_outdents_then_ends(win):
    make_parent_with_kids(win)
    key(win, Qt.Key.Key_Return)                     # new empty subtask
    assert blocks(win)[3] == SUB + G_OPEN + " "
    key(win, Qt.Key.Key_Return)                     # -> main task
    assert blocks(win)[3] == G_OPEN + " "
    key(win, Qt.Key.Key_Return)                     # -> plain
    assert blocks(win)[3] == ""


def test_parent_completes_when_all_subtasks_done(win):
    make_parent_with_kids(win)
    doc = win.editor.document()
    win.editor.toggle_done(doc.findBlockByNumber(1))
    pump()
    assert blocks(win)[0].startswith(G_OPEN)         # one subtask still open
    win.editor.toggle_done(doc.findBlockByNumber(2))
    pump()
    assert blocks(win) == [f"{G_DONE} trip", f"{SUB}{G_DONE} tickets", f"{SUB}{G_DONE} hotel"]
    assert win.meta.text().endswith("0 open, 1 done")
    win.editor.toggle_done(doc.findBlockByNumber(2))  # untick one subtask
    pump()
    assert blocks(win)[0].startswith(G_OPEN)


def test_ticking_parent_ticks_and_unticks_all_subtasks(win):
    make_parent_with_kids(win)
    doc = win.editor.document()
    win.editor.toggle_done(doc.findBlockByNumber(0))
    pump()
    assert blocks(win) == [f"{G_DONE} trip", f"{SUB}{G_DONE} tickets", f"{SUB}{G_DONE} hotel"]
    win.editor.toggle_done(doc.findBlockByNumber(0))
    pump()
    assert blocks(win) == [f"{G_OPEN} trip", f"{SUB}{G_OPEN} tickets", f"{SUB}{G_OPEN} hotel"]


def test_new_subtask_reopens_a_done_parent(win):
    make_parent_with_kids(win)
    doc = win.editor.document()
    win.editor.toggle_done(doc.findBlockByNumber(0))
    pump()
    key(win, Qt.Key.Key_End, Qt.KeyboardModifier.ControlModifier)
    key(win, Qt.Key.Key_Return)
    type_(win, "extra")
    pump()
    assert blocks(win)[0].startswith(G_OPEN)
    assert blocks(win)[3] == SUB + G_OPEN + " extra"


def test_enter_at_end_of_parent_adds_first_subtask(win):
    make_parent_with_kids(win)
    win.editor.moveCursor(win.editor.textCursor().MoveOperation.Start)
    key(win, Qt.Key.Key_End)
    key(win, Qt.Key.Key_Return)
    assert blocks(win)[1] == SUB + G_OPEN + " "


def test_parent_with_subtasks_cannot_be_indented(win):
    win.editor.setPlainText(f"{G_OPEN} a\n{G_OPEN} b\n{SUB}{G_OPEN} c")
    win.editor.moveCursor(win.editor.textCursor().MoveOperation.Start)
    key(win, Qt.Key.Key_Down)
    key(win, Qt.Key.Key_Tab)
    assert blocks(win)[1] == G_OPEN + " b"


def test_subtasks_saved_in_markdown_and_loaded_back(win):
    make_parent_with_kids(win)
    win.save_now()
    assert win.journal.read(win.day) == "- [ ] trip\n  - [ ] tickets\n  - [ ] hotel"
    win.load()
    assert text(win) == f"{G_OPEN} trip\n{SUB}{G_OPEN} tickets\n{SUB}{G_OPEN} hotel"


def test_loading_a_page_does_not_change_it(win):
    win.journal.write(win.day, "- [x] parent\n  - [ ] kid")      # inconsistent on purpose
    win.load()
    pump()
    assert text(win) == f"{G_DONE} parent\n{SUB}{G_OPEN} kid"


def test_one_undo_reverts_tick_and_parent_together(win):
    make_parent_with_kids(win)
    doc = win.editor.document()
    win.editor.toggle_done(doc.findBlockByNumber(1))
    win.editor.toggle_done(doc.findBlockByNumber(2))
    pump()
    assert blocks(win)[0].startswith(G_DONE)
    win.editor.undo()
    pump()
    assert blocks(win) == [f"{G_OPEN} trip", f"{SUB}{G_DONE} tickets", f"{SUB}{G_OPEN} hotel"]


def test_click_on_subtask_checkbox(win):
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QTextCursor
    make_parent_with_kids(win)
    block = win.editor.document().findBlockByNumber(1)
    c = QTextCursor(block)
    c.setPosition(block.position() + 4)
    r0 = win.editor.cursorRect(c)
    c.setPosition(block.position() + 5)
    r1 = win.editor.cursorRect(c)
    QTest.mouseClick(win.editor.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     QPoint((r0.x() + r1.x()) // 2, r0.center().y()))
    pump()
    assert blocks(win)[1] == SUB + G_DONE + " tickets"
