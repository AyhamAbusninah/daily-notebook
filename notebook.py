#!/usr/bin/env python3
"""Notebook: one page per day. Plain writing, and any line can be a checkbox task.

Storage: ~/journal/YYYY-MM-DD.md (plain text, grep/git friendly).
A task line is saved as "- [ ] text" or "- [x] text"; everything else is saved as-is.

Keys:
  Ctrl+T          make the current line a task / turn it back into plain text
  Ctrl+Enter      tick / untick the task on the current line
  Enter           on a task line: next task; on an empty task: back to plain text
  Alt+Left/Right  previous / next day
"""
import datetime
import glob
import os
import re

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

DIR = os.path.expanduser("~/journal")
TODO_RE = re.compile(r"^- \[( |x)\]( |$)")
OLD_SEP = "\n---\n"  # separator used by an earlier version of this app
ANCHOR = "\ufffc"  # the character GTK uses for an embedded widget

CSS = """
.page { border-left: 4px solid #9b3d2e; padding: 14px 18px; margin: 12px; }
.page-title { font-family: Georgia, serif; font-size: 22px; }
.page-meta { font-size: 13px; opacity: 0.6; margin-bottom: 6px; }
textview { font-family: Georgia, serif; font-size: 17px; }
"""


def path_for(day):
    return os.path.join(DIR, day.isoformat() + ".md")


def migrate(text):
    """Very old files were 'todo lines --- notes'. Merge them into one text."""
    head, sep, notes = text.partition(OLD_SEP)
    if sep and all(not l.strip() or TODO_RE.match(l) for l in head.splitlines()):
        head = head.strip("\n")
        return (head + "\n\n" + notes) if head else notes
    return text


class Window(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Notebook")
        self.set_default_size(560, 700)
        self.day = datetime.date.today()
        self.loading = False
        self.fix_pending = False
        self.checks = {}  # TextChildAnchor -> Gtk.CheckButton (one per task line)

        css = Gtk.CssProvider()
        try:
            css.load_from_string(CSS)
        except AttributeError:
            css.load_from_data(CSS.encode(), -1)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # Header bar: < > [days]                      [task] Today
        header = Gtk.HeaderBar()
        prev_b = Gtk.Button(icon_name="go-previous-symbolic", tooltip_text="Previous day (Alt+Left)")
        next_b = Gtk.Button(icon_name="go-next-symbolic", tooltip_text="Next day (Alt+Right)")
        today_b = Gtk.Button(label="Today")
        task_b = Gtk.Button(icon_name="checkbox-checked-symbolic",
                            tooltip_text="Make this line a task (Ctrl+T)")
        prev_b.connect("clicked", lambda *_: self.go(-1))
        next_b.connect("clicked", lambda *_: self.go(1))
        today_b.connect("clicked", lambda *_: self.jump(datetime.date.today()))
        task_b.connect("clicked", self.on_task_button)

        self.days_list = Gtk.ListBox()
        self.days_list.set_placeholder(Gtk.Label(label="No pages yet", margin_top=12, margin_bottom=12))
        self.days_list.connect("row-activated", self.on_day_row)
        days_sw = Gtk.ScrolledWindow(min_content_width=320, min_content_height=360)
        days_sw.set_child(self.days_list)
        self.pop = Gtk.Popover()
        self.pop.set_child(days_sw)
        self.pop.connect("notify::visible", self.on_pop_visible)
        days_btn = Gtk.MenuButton(icon_name="view-list-symbolic", tooltip_text="All days")
        days_btn.set_popover(self.pop)

        header.pack_start(prev_b)
        header.pack_start(next_b)
        header.pack_start(days_btn)
        header.pack_end(today_b)
        header.pack_end(task_b)
        self.set_titlebar(header)

        # Page: title, meta line, one writing area
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        page.add_css_class("page")
        self.title_label = Gtk.Label(xalign=0)
        self.title_label.add_css_class("page-title")
        self.meta_label = Gtk.Label(xalign=0)
        self.meta_label.add_css_class("page-meta")
        self.view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, vexpand=True,
                                 left_margin=0, right_margin=8, top_margin=10,
                                 bottom_margin=10, pixels_below_lines=6)
        self.buf = self.view.get_buffer()
        self.buf.create_tag("done", strikethrough=True, foreground="#8a8472")
        self.buf.connect("changed", self.on_changed)
        self.buf.connect("notify::cursor-position", self.on_cursor)

        key = Gtk.EventControllerKey()
        key.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key.connect("key-pressed", self.on_key)
        self.view.add_controller(key)

        sw = Gtk.ScrolledWindow(vexpand=True)
        sw.set_child(self.view)
        page.append(self.title_label)
        page.append(self.meta_label)
        page.append(sw)
        self.set_child(page)

        self.load()

    # ---------- navigation ----------
    def go(self, n):
        self.jump(self.day + datetime.timedelta(days=n))

    def jump(self, day):
        self.day = day
        self.load()

    # ---------- persistence ----------
    def load(self):
        self.loading = True
        p = path_for(self.day)
        existed = os.path.exists(p)
        if existed:
            with open(p, encoding="utf-8") as f:
                text = migrate(f.read())
        elif self.day == datetime.date.today():
            text = self.carry_over()
        else:
            text = ""
        self.populate(text)
        self.title_label.set_label(self.day.strftime("%A, %d %B %Y"))
        self.loading = False
        self.retag()
        if text and not existed:
            self.save()
        self.buf.place_cursor(self.buf.get_end_iter())
        self.view.grab_focus()

    def populate(self, text):
        """Fill the buffer: '- [ ] x' lines become a checkbox + text."""
        b = self.buf
        b.begin_irreversible_action()  # so Ctrl+Z can't undo the page load
        b.set_text("")
        for i, line in enumerate(text.split("\n")):
            if i:
                b.insert(b.get_end_iter(), "\n", -1)
            m = TODO_RE.match(line)
            if m:
                self.new_task(b.get_end_iter(), m.group(1) == "x")
                line = line[m.end():]
            b.insert(b.get_end_iter(), line, -1)
        b.end_irreversible_action()

    def carry_over(self):
        """Unfinished tasks from the most recent earlier page."""
        files = sorted(glob.glob(os.path.join(DIR, "????-??-??.md")))
        files = [f for f in files if os.path.basename(f)[:10] < self.day.isoformat()]
        for f in reversed(files):
            with open(f, encoding="utf-8") as fh:
                lines = migrate(fh.read()).splitlines()
            open_tasks = []
            for l in lines:
                m = TODO_RE.match(l)
                if m and m.group(1) == " ":
                    open_tasks.append(l)
            if open_tasks:
                return "\n".join(open_tasks) + "\n\n"
            if any(l.strip() for l in lines):
                return ""
        return ""

    def serialize(self):
        out = []
        for off, line in self.lines():
            chk = self.check_at(off) if line.startswith(ANCHOR) else None
            if chk is not None:
                out.append("- [%s] %s" % ("x" if chk.get_active() else " ",
                                          line[1:].replace(ANCHOR, "")))
            else:
                out.append(line.replace(ANCHOR, ""))
        return "\n".join(out)

    def save(self):
        if self.loading:
            return
        text = self.serialize()
        p = path_for(self.day)
        if not text.strip():
            if os.path.exists(p):
                os.remove(p)
            return
        os.makedirs(DIR, exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, p)

    # ---------- buffer helpers ----------
    def lines(self):
        """[(char_offset, line_text), ...]; a task checkbox counts as 1 char (ANCHOR)."""
        text = self.buf.get_slice(self.buf.get_start_iter(), self.buf.get_end_iter(), True)
        out, off = [], 0
        for line in text.split("\n"):
            out.append((off, line))
            off += len(line) + 1
        return out

    def at(self, offset):
        return self.buf.get_iter_at_offset(offset)

    def check_at(self, off):
        """The checkbox of the task line starting at char offset off, or None."""
        anchor = self.at(off).get_child_anchor()
        return self.checks.get(anchor) if anchor is not None else None

    def cursor_line(self):
        it = self.buf.get_iter_at_mark(self.buf.get_insert())
        off, line = self.lines()[it.get_line()]
        return off, line, it.get_line_offset()

    def new_task(self, it, done=False):
        anchor = self.buf.create_child_anchor(it)
        chk = Gtk.CheckButton(active=done, margin_end=6, valign=Gtk.Align.CENTER)
        chk.connect("toggled", self.on_check)
        self.view.add_child_at_anchor(chk, anchor)
        self.checks[anchor] = chk

    # ---------- styling / bookkeeping ----------
    def on_changed(self, _buf):
        if self.loading:
            return
        self.retag()
        self.save()

    def on_check(self, _chk):
        if not self.loading:
            self.retag()
            self.save()

    def retag(self):
        b = self.buf
        for a in [a for a in self.checks if a.get_deleted()]:
            chk = self.checks.pop(a)
            try:
                if chk.get_parent() is not None:
                    self.view.remove(chk)
            except Exception:
                pass
        start, end = b.get_bounds()
        b.remove_tag_by_name("done", start, end)
        open_n = done_n = 0
        stray = False
        for off, line in self.lines():
            chk = self.check_at(off) if line.startswith(ANCHOR) else None
            if ANCHOR in (line[1:] if chk is not None else line):
                stray = True
            if chk is None:
                continue
            if chk.get_active():
                done_n += 1
                b.apply_tag_by_name("done", self.at(off + 1), self.at(off + len(line)))
            else:
                open_n += 1
        parts = []
        if self.day == datetime.date.today():
            parts.append("Today")
        if open_n or done_n:
            parts.append("%d open, %d done" % (open_n, done_n))
        self.meta_label.set_label("  \u00b7  ".join(parts))
        if stray and not self.fix_pending:
            self.fix_pending = True
            GLib.idle_add(self.fix_stray)

    def fix_stray(self):
        """Remove checkboxes that ended up mid-line (e.g. after joining two lines)."""
        self.fix_pending = False
        offs = []
        for off, line in self.lines():
            for i, ch in enumerate(line):
                if ch == ANCHOR and not (i == 0 and self.check_at(off) is not None):
                    offs.append(off + i)
        for o in reversed(offs):
            self.buf.delete(self.at(o), self.at(o + 1))
        return False

    def on_cursor(self, *_):
        """Keep the cursor after the checkbox, never before it."""
        if self.loading:
            return
        it = self.buf.get_iter_at_mark(self.buf.get_insert())
        if it.get_line_offset() == 0 and it.get_child_anchor() is not None:
            it.forward_char()
            self.buf.move_mark(self.buf.get_insert(), it)

    # ---------- input ----------
    def on_key(self, _ctrl, keyval, _keycode, state):
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        alt = bool(state & Gdk.ModifierType.ALT_MASK)
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        if alt and keyval == Gdk.KEY_Left:
            self.go(-1)
            return True
        if alt and keyval == Gdk.KEY_Right:
            self.go(1)
            return True
        if ctrl and keyval in (Gdk.KEY_t, Gdk.KEY_T):
            self.toggle_task_at_cursor()
            return True
        if ctrl and keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            off, _line, _col = self.cursor_line()
            chk = self.check_at(off)
            if chk is not None:
                chk.set_active(not chk.get_active())
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and not shift and not ctrl:
            return self.continue_task()
        if keyval == Gdk.KEY_Left and not (ctrl or shift or alt):
            return self.left_over_checkbox()
        return False

    def left_over_checkbox(self):
        """Left arrow right after a checkbox: jump to the end of the previous line."""
        off, _line, col = self.cursor_line()
        if col == 1 and self.check_at(off) is not None:
            if off > 0:
                self.buf.place_cursor(self.at(off - 1))
            return True
        return False

    def on_task_button(self, _btn):
        self.toggle_task_at_cursor()
        self.view.grab_focus()

    def toggle_task_at_cursor(self):
        off, _line, _col = self.cursor_line()
        self.buf.begin_user_action()
        if self.check_at(off) is not None:
            self.buf.delete(self.at(off), self.at(off + 1))  # back to plain text
        else:
            self.new_task(self.at(off))
        self.buf.end_user_action()

    def continue_task(self):
        off, line, col = self.cursor_line()
        if self.check_at(off) is None or col < 1:
            return False  # normal Enter
        b = self.buf
        b.begin_user_action()
        if line[1:].strip() == "":
            b.delete(self.at(off), self.at(off + 1))  # empty task + Enter = plain line
        else:
            b.insert_at_cursor("\n", -1)
            self.new_task(b.get_iter_at_mark(b.get_insert()))
        b.end_user_action()
        return True

    # ---------- days list ----------
    def on_pop_visible(self, pop, _pspec):
        if pop.get_visible():
            self.refresh_days()

    def refresh_days(self):
        while (row := self.days_list.get_first_child()) is not None:
            self.days_list.remove(row)
        for f in sorted(glob.glob(os.path.join(DIR, "????-??-??.md")), reverse=True):
            try:
                day = datetime.date.fromisoformat(os.path.basename(f)[:10])
                with open(f, encoding="utf-8") as fh:
                    text = migrate(fh.read())
            except (ValueError, OSError):
                continue
            lines = [l for l in text.splitlines() if l.strip()]
            if not lines:
                continue
            open_n = 0
            for l in lines:
                m = TODO_RE.match(l)
                if m and m.group(1) == " ":
                    open_n += 1
            first = lines[0]
            m = TODO_RE.match(first)
            if m:
                first = ("\u2611 " if m.group(1) == "x" else "\u2610 ") + first[m.end():]
            preview = first if len(first) <= 48 else first[:48] + "\u2026"
            head = day.strftime("%a %d %b %Y")
            if open_n:
                head += "   \u00b7   %d open" % open_n
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                          margin_top=6, margin_bottom=6, margin_start=10, margin_end=10)
            l1 = Gtk.Label(label=head, xalign=0)
            l1.add_css_class("heading")
            l2 = Gtk.Label(label=preview, xalign=0)
            l2.add_css_class("dim-label")
            box.append(l1)
            box.append(l2)
            row = Gtk.ListBoxRow()
            row.set_child(box)
            row.day = day
            self.days_list.append(row)

    def on_day_row(self, _listbox, row):
        self.pop.popdown()
        self.jump(row.day)


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="io.github.dailynotebook")

    def do_activate(self):
        win = self.props.active_window or Window(self)
        win.present()


if __name__ == "__main__":
    App().run()
