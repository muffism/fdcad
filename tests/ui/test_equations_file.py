"""Equations to and from a text file, and a linked file (TR25, D749)."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.core.io import fdef
from fdcad.ui.equations.dialog import NAME, VALUE, EquationsDialog
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_equations_manager import _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def _width(dialog: EquationsDialog) -> str:
    return next(i.text(VALUE) for i in dialog.items() if i.text(NAME) == '"Width"')


def test_export_then_import_into_the_manager(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    tab = _open(qtbot, window)
    dialog = window.equations_tool.open()  # type: ignore[attr-defined]
    target = tmp_path / "values.txt"
    assert dialog.export_file(target)
    assert '"Width" = 60' in target.read_text(encoding="utf-8")
    assert "values.txt" in dialog.message.text()
    target.write_text('[variables]\n"Width" = 70mm\n"Gap" = 0.2mm\n', encoding="utf-8")
    assert dialog.import_file(target)
    assert _width(dialog) == "70mm"
    assert "Read 2 changed rows" in dialog.message.text()
    assert tab.session.document.variables[0].expr == "60"  # only OK applies it
    dialog.accept()
    assert [v.expr for v in tab.session.document.variables] == ["70mm", "0.2mm"]
    tab.session.undo.undo()
    assert [v.expr for v in tab.session.document.variables] == ["60"]


def test_a_bad_file_says_which_line(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    _open(qtbot, window)
    dialog = window.equations_tool.open()  # type: ignore[attr-defined]
    bad = tmp_path / "bad.txt"
    bad.write_text("Width = 70\n", encoding="utf-8")
    assert not dialog.import_file(bad)
    assert "line 1" in dialog.message.text() and _width(dialog) == "60"
    assert not dialog.import_file(tmp_path / "gone.txt")
    assert "gone.txt not read" in dialog.message.text()


def test_link_is_read_on_open_and_on_rebuild(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    tab = _open(qtbot, window)
    dialog = window.equations_tool.open()  # type: ignore[attr-defined]
    shared = tmp_path / "shared.txt"
    shared.write_text('[variables]\n"Width" = 70mm\n', encoding="utf-8")
    assert dialog.link_file(shared)
    assert "shared.txt" in dialog.link_label.text() and dialog.unlink_button.isEnabled()
    dialog.accept()
    doc = tab.session.document
    assert doc.equations_file == str(shared.resolve()) and doc.variables[0].expr == "70mm"
    # On Rebuild the file is read again, as one undo step.
    shared.write_text('[variables]\n"Width" = 80mm\n', encoding="utf-8")
    window.rebuild()
    assert doc.variables[0].expr == "80mm"
    assert "Read 1 changed values from shared.txt" in window.status.text()
    tab.session.undo.undo()
    assert doc.variables[0].expr == "70mm"
    # Saved, then opened after the file changed: the part opens with the new value.
    part = tmp_path / "plate.fdprt"
    tab.session.save(part)
    shared.write_text('[variables]\n"Width" = 90mm\n', encoding="utf-8")
    window.tabs.removeTab(window.tabs.indexOf(tab))
    window.open_path(part)
    opened = window.current
    assert opened is not None and opened.session.document.variables[0].expr == "90mm"
    assert not opened.session.undo.canUndo()  # read while opening, not an undo step
    assert fdef.load(part).variables[0].expr == "70mm"  # the saved file is unchanged


def test_a_missing_linked_file_keeps_the_values_and_says_so(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    tab = _open(qtbot, window)
    tab.session.document.equations_file = str(tmp_path / "gone.txt")
    window.rebuild()
    assert "gone.txt not read" in window.status.text()
    assert "remove the link" in window.status.text()
    assert tab.session.document.variables[0].expr == "60"


def test_remove_link(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    tab = _open(qtbot, window)
    tab.session.document.equations_file = str(tmp_path / "shared.txt")
    dialog = window.equations_tool.open()  # type: ignore[attr-defined]
    dialog.unlink()
    assert not dialog.unlink_button.isEnabled()
    dialog.accept()
    assert tab.session.document.equations_file == ""
    tab.session.undo.undo()
    assert tab.session.document.equations_file == str(tmp_path / "shared.txt")
