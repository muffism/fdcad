"""Table Driven Pattern panel table (TR58, D821)."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.ui.body_tools.xy_table import XYTable


def test_rows_paste_tick_and_file(qtbot: QtBot, tmp_path: Path) -> None:
    table = XYTable([[1.0, 2.0], [3.0, 4.0, False]])
    qtbot.addWidget(table)
    assert table.value() == [[1.0, 2.0], [3.0, 4.0, False]]
    assert table.paste("X\tY\n5\t6\n7\t8\n") == 2
    assert table.value()[-1] == [7.0, 8.0]
    path = tmp_path / "rows.txt"
    assert table.save_file(str(path))
    other = XYTable([])
    qtbot.addWidget(other)
    assert other.load_file(str(path)) == 4
    assert other.value() == [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]]
    other.table.item(0, 1).setText("x")
    assert other.value() is None
