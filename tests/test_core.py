import datetime as dt
import zipfile

from daily_notebook import core

D = dt.date


def test_text_roundtrip():
    f = "- [ ] a\n- [x] b\nplain\n- [ ] "
    e = core.to_editor_text(f)
    assert e == "\u2610 a\n\u2611 b\nplain\n\u2610 "
    assert core.to_file_text(e) == f


def test_line_separator_is_normalised():
    assert core.to_file_text("a\u2028b") == "a\nb"


def test_count_tasks():
    assert core.count_tasks("\u2610 a\n\u2611 b\n\u2610 c\nx") == (2, 1)


def test_write_read_never_deletes(tmp_path):
    j = core.Journal(tmp_path)
    j.write(D(2026, 1, 1), "")          # empty + no file: nothing created
    assert not j.path(D(2026, 1, 1)).exists()
    j.write(D(2026, 1, 1), "hello")
    assert j.read(D(2026, 1, 1)) == "hello"
    j.write(D(2026, 1, 1), "")          # clearing keeps an (empty) file
    assert j.path(D(2026, 1, 1)).exists() and j.read(D(2026, 1, 1)) == ""
    assert j.days() == []                # blank pages are not listed
    assert not list(tmp_path.glob("*.tmp"))


def test_carry_over(tmp_path):
    j = core.Journal(tmp_path)
    j.write(D(2026, 1, 1), "- [ ] old\n- [x] done\nnote")
    assert j.open_tasks_before(D(2026, 1, 2)) == "- [ ] old\n\n"
    j.write(D(2026, 1, 2), "- [x] old")
    assert j.open_tasks_before(D(2026, 1, 3)) == ""   # latest page has none left
    assert j.open_tasks_before(D(2026, 1, 1)) == ""


def test_search_newest_first(tmp_path):
    j = core.Journal(tmp_path)
    j.write(D(2026, 1, 1), "buy Milk")
    j.write(D(2026, 3, 1), "- [ ] milk again\nother")
    r = j.search("milk")
    assert [d for d, _ in r] == [D(2026, 3, 1), D(2026, 1, 1)]
    assert r[0][1] == "\u2610 milk again"
    assert j.search("") == []


def test_export_and_backup_and_copy(tmp_path):
    j = core.Journal(tmp_path / "a")
    j.write(D(2026, 1, 1), "one")
    j.write(D(2026, 1, 2), "- [ ] two")
    out = tmp_path / "all.md"
    assert j.export_markdown(out) == 2
    text = out.read_text(encoding="utf-8")
    assert text.index("2026-01-01") < text.index("2026-01-02") and "- [ ] two" in text
    z = tmp_path / "b.zip"
    assert j.backup_zip(z) == 2
    assert sorted(zipfile.ZipFile(z).namelist()) == ["2026-01-01.md", "2026-01-02.md"]
    assert j.copy_to(tmp_path / "b") == 2
    assert j.copy_to(tmp_path / "b") == 0   # never overwrites


def test_migrate_old_format():
    assert core.migrate("- [ ] a\n---\nnotes") == "- [ ] a\n\nnotes"
    assert core.migrate("hello\n---\nworld") == "hello\n---\nworld"


def test_default_dir_prefers_existing_journal(tmp_path, monkeypatch):
    monkeypatch.setattr(core.Path, "home", classmethod(lambda cls: tmp_path))
    assert core.default_notes_dir() == tmp_path / "Documents" / "Daily Notebook"
    (tmp_path / "journal").mkdir()
    (tmp_path / "journal" / "2026-01-01.md").write_text("x")
    assert core.default_notes_dir() == tmp_path / "journal"
