"""Read from CSV in the equations manager (TR198 item 2, D2102)."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.ui import strings_config as text
from fdcad.ui.equations.dialog import VALUE
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_equations_manager import _open, _row
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_read_a_variable_from_a_csv_table(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    """Read now, kept on OK, read again on Rebuild, one undo step."""
    tab = _open(qtbot, window)
    session = tab.session
    path = tmp_path / "sizes.csv"
    path.write_text("Size,Width\nSmall,40\nLarge,80\n", encoding="utf-8")
    dialog = window.equations_tool.open()  # type: ignore[attr-defined]
    dialog.ask_lookup = lambda _n, _b: {  # type: ignore[method-assign]
        "file": str(path),
        "row": "Large",
        "column": "Width",
    }
    assert dialog.edit_lookup("Width")
    assert _row(dialog, "Width").text(VALUE) == "80"
    dialog.accept()
    var = session.document.variables[0]
    assert var.expr == "80" and var.lookup is not None
    path.write_text("Size,Width\nSmall,40\nLarge,90\n", encoding="utf-8")
    note = session.read_linked_equations()
    assert note == text.CSV_LOOKUP_READ.format(count=1)
    assert session.document.variables[0].value == 90.0
    session.undo.undo()
    assert session.document.variables[0].value == 80.0
