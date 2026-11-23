"""Equations manager comfort: type ahead, sort, filter, several rows, Disable and
Replace Name (TR194, D830)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.equations.comfort import FormulaEdit, word_at
from fdcad.ui.equations.dialog import NAME, RESULT
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_equations_manager import _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_word_at_and_type_ahead(qtbot: QtBot) -> None:
    assert word_at('=2 * "Wid', 9) == (5, '"Wid')
    assert word_at("=sq", 3) == (1, "sq")
    edit = FormulaEdit(lambda: ['"Width"', "sqrt("])
    qtbot.addWidget(edit)
    edit.setText('=2 * "Wi')
    edit.setCursorPosition(len(edit.text()))
    edit.take('"Width"')
    assert edit.text() == '=2 * "Width"'


def test_sort_filter_disable_and_replace(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = _open(qtbot, window)
    dialog = window.equations_tool.open()  # type: ignore[attr-defined]
    zed = dialog.add("variable", "Zed", "=1")
    alpha = dialog.add("variable", "Alpha", "=2")
    dialog.sort_rows()
    names = [i.text(NAME) for i in dialog.items() if i.data(0, 256) == "variable"]
    assert names == sorted(names, key=lambda n: n.strip('"').lower())
    dialog.apply_filter("alp")
    assert not alpha.isHidden() and zed.isHidden()
    dialog.apply_filter("")
    assert '"Width"' in dialog.names()
    eq = dialog.add("equation", '"Gone@Nothing 1"', '="Width"')
    dialog.tree.setCurrentItem(eq)
    assert dialog.replace_reference("Alpha")
    assert eq.text(NAME) == '"Alpha"'
    dialog.tree.setCurrentItem(zed)
    zed.setSelected(True)
    alpha.setSelected(True)
    dialog.tree.setCurrentItem(alpha)
    eq_rows = [i for i in dialog.items() if i.data(0, 256) == "equation"]
    for item in dialog.tree.selectedItems():
        item.setSelected(False)
    if eq_rows:
        first = eq_rows[0]
        dialog.tree.setCurrentItem(first)
        first.setSelected(True)
        dialog.toggle_disabled()
        assert first.text(RESULT) == "Disabled"
        assert any(r.disabled for r in dialog.rows())
    zed.setSelected(True)
    alpha.setSelected(True)
    before = len(dialog.items())
    dialog.delete_row()
    assert len(dialog.items()) <= before - 2
    assert tab.session.document.variables  # the part is untouched until OK
    dialog.reject()
