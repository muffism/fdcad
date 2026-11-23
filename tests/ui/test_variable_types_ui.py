"""Type... and Group... in the equations manager (TR417, D2104)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui import strings_config as text
from fdcad.ui.equations.dialog import NAME
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_equations_manager import _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_type_and_group(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    session = tab.session
    dialog = window.equations_tool.open()  # type: ignore[attr-defined]
    dialog.add("variable", "Note", "Front panel")
    dialog.add("variable", "Holes", "yes")
    dialog.ask_type = lambda _names, _current: "text"  # type: ignore[method-assign]
    assert dialog.edit_type(["Note"])
    dialog.ask_group = lambda _names, _current: "Labels"  # type: ignore[method-assign]
    assert dialog.edit_group(["Note", "Holes"])
    names = [i.text(NAME) for i in dialog.items() if i.toolTip(NAME)]
    assert names == ['"Note"', '"Holes"']
    dialog.filter.setText("labels")
    assert dialog.items()[0].isHidden()  # Width has no group
    dialog.accept()
    by_name = {v.name: v for v in session.document.variables}
    assert by_name["Note"].type == "text" and by_name["Note"].group == "Labels"
    assert by_name["Holes"].type == "yes_no"
    assert text.VAR_TYPES["yes_no"] == "Yes or No"
