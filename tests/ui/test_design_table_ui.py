"""The design table editor (PHASE4_SPEC P4.10 item 3, D392)."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fdcad.core import configurations as configs
from fdcad.core import design_table as dt
from fdcad.core.features.solids import volume_of
from fdcad.ui import strings_config as text
from fdcad.ui.equations.table_dialog import DesignTableDialog, column_choices
from fdcad.ui.main_window.window import DocumentTab, MainWindow
from fdcad.ui.session import DocumentSession
from tests.core.equations.test_equations import _plate
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def _open(qtbot: QtBot, window: MainWindow) -> DocumentTab:  # noqa: F811
    session = DocumentSession(_plate(), None, window)
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        tab = window.add_session(session)
    return tab


def _dialog(window: MainWindow) -> DesignTableDialog:  # noqa: F811
    window.commands.actions["tools.design_table"].trigger()
    dialog = window.design_table_dialog  # type: ignore[attr-defined]
    assert isinstance(dialog, DesignTableDialog)
    return dialog


def test_build_a_table_and_apply_it(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    session = tab.session
    ext = session.document.features[-1].id
    assert f"{ext}.depth" in column_choices(session)
    assert "var.Width" in column_choices(session)
    dialog = _dialog(window)
    assert dialog.table.rowCount() == 1 and dialog.columns() == []
    assert dialog.add_column(f"{ext}.depth")
    assert dialog.current().rows == [("Default", ["10"])]
    row = dialog.add_row("Deep")
    dialog.set_cell(row, f"{ext}.depth", "25")
    count = session.undo.count()
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        dialog.accept()
    assert session.undo.count() == count + 1
    assert configs.names(session.document) == ["Default", "Deep"]
    stored = dt.stored(session.document)
    assert stored is not None and stored.columns == [f"{ext}.depth"]
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.configurations.activate("Deep")  # type: ignore[attr-defined]
    report = session.report
    assert report is not None and report.body is not None
    assert volume_of(report.body.shape) == 60 * 40 * 25


def test_bad_cell_shows_a_message_and_changes_nothing(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = _open(qtbot, window)
    ext = tab.session.document.features[-1].id
    dialog = _dialog(window)
    dialog.add_column(f"{ext}.depth")
    dialog.set_cell(0, f"{ext}.depth", "=Width +")
    count = tab.session.undo.count()
    dialog.accept()
    assert "incomplete" in dialog.message.text()
    assert tab.session.undo.count() == count


def test_csv_export_and_import(qtbot: QtBot, window: MainWindow, tmp_path: Path) -> None:  # noqa: F811
    tab = _open(qtbot, window)
    ext = tab.session.document.features[-1].id
    dialog = _dialog(window)
    dialog.add_column("var.Width")
    dialog.add_column(f"{ext}.depth")
    out = tmp_path / "table.csv"
    assert dialog.export_csv(out)
    assert out.read_bytes()[:3] == bytes([0xEF, 0xBB, 0xBF])  # a byte order mark (D724)
    assert out.read_text(encoding="utf-8-sig").splitlines() == [
        f"Configuration,var.Width,{ext}.depth",
        "Default,60,10",
    ]
    out.write_text(
        f"Configuration,var.Width,{ext}.depth\nSmall,40,5\nBig,100,20\n", encoding="utf-8"
    )
    assert dialog.import_csv(out)
    assert dialog.current().rows == [("Small", ["40", "5"]), ("Big", ["100", "20"])]
    from PySide6.QtWidgets import QMessageBox

    asked: list[str] = []
    real = QMessageBox.question
    QMessageBox.question = lambda *a, **k: (  # type: ignore[method-assign]
        asked.append(str(a[2])),
        QMessageBox.StandardButton.Yes,
    )[1]
    try:
        with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
            dialog.accept()
    finally:
        QMessageBox.question = real  # type: ignore[method-assign]
    assert asked and "Default" in asked[0]  # it asks before deleting (audit D3 item 11)
    # Rows are the configurations: Default had no row, so it was deleted.
    assert configs.names(tab.session.document) == ["Small", "Big"]
    bad = tmp_path / "bad.csv"
    bad.write_text("Configuration\n", encoding="utf-8")
    dialog = _dialog(window)
    assert not dialog.import_csv(bad)
    assert "value column" in dialog.message.text()


def test_renaming_a_row_renames_its_configuration(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = _open(qtbot, window)
    session = tab.session
    ext = session.document.features[-1].id
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.configurations.add("Long")  # type: ignore[attr-defined]
    with qtbot.waitSignal(session.rebuilt, timeout=20000):
        window.configurations.add("Short")  # type: ignore[attr-defined]
    # A value that is not in the table: Default is suppressed only in Default.
    configs.set_scoped(session.document, f"{ext}.suppressed", True, "chosen", ["Default"])
    dialog = _dialog(window)
    assert dialog.add_column("var.Width")
    dialog.table.item(0, 0).setText("Short")  # Default and Short swap names
    dialog.table.item(2, 0).setText("Default")
    dialog.accept()
    doc = session.document
    assert configs.names(doc) == ["Short", "Long", "Default"]  # order kept
    short = next(i for i in configs.items(doc) if i["name"] == "Short")
    assert short["overrides"][f"{ext}.suppressed"] is True  # the old Default's value


def test_export_to_a_missing_folder_says_what_to_do(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    tmp_path: Path,
) -> None:
    _open(qtbot, window)
    dialog = _dialog(window)
    assert not dialog.export_csv(tmp_path / "missing" / "table.csv")
    assert "Choose another folder" in dialog.message.text()


def test_copy_and_paste_through_the_clipboard(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    """TR304 (D930): tab separated copy, and paste of tabs or commas."""
    tab = _open(qtbot, window)
    ext = tab.session.document.features[-1].id
    dialog = _dialog(window)
    dialog.add_column("var.Width")
    copied = dialog.copy_table()
    assert copied.splitlines() == ["Configuration\tvar.Width", "Default\t60"]
    from PySide6.QtWidgets import QApplication

    assert QApplication.clipboard().text() == copied
    other = _dialog(window)
    assert other.paste_table(f"Configuration\tvar.Width\t{ext}.depth\nSmall\t40\t5\n")
    assert other.current().rows == [("Small", ["40", "5"])]
    assert other.paste_table("Configuration,var.Width\nBig,90\n")
    assert other.current().rows == [("Big", ["90"])]
    assert not other.paste_table("  ")
    assert "no table" in other.message.text()


def test_column_summary_follows_the_current_cell(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """TR198 (D966): the sum, average and range of the current number column."""
    tab = _open(qtbot, window)
    ext = tab.session.document.features[-1].id
    dialog = _dialog(window)
    assert dialog.add_column(f"{ext}.depth")
    row = dialog.add_row("Deep")
    dialog.set_cell(row, f"{ext}.depth", "30")
    dialog.table.setCurrentCell(0, 1)
    shown = dialog.update_summary()
    assert "2 values" in shown and "40" in shown and "20" in shown  # sum and average
    dialog.table.setCurrentCell(0, 0)
    assert dialog.update_summary() == text.TABLE_SUMMARY_NONE
    dialog.reject()


def test_add_values_adds_several_columns(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """TR90 (D969): one button adds a column for each ticked value."""
    tab = _open(qtbot, window)
    ext = tab.session.document.features[-1].id
    dialog = _dialog(window)
    offered: list[list[str]] = []

    def pick(choices: list[str]) -> list[str]:
        offered.append(choices)
        return ["var.Width", f"{ext}.depth"]

    dialog.pick_columns = pick  # type: ignore[method-assign]
    assert dialog.ask_columns() == 2
    assert dialog.columns() == ["var.Width", f"{ext}.depth"]
    assert "var.Width" in offered[0]
    assert dialog.ask_columns() == 0  # both are columns already
    dialog.reject()


def test_description_and_colour_columns(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """TR90 item 1 (D2100): description and part colour columns, shown by name."""
    tab = _open(qtbot, window)
    session = tab.session
    assert dt.DESCRIPTION in column_choices(session)
    assert configs.PART_COLOR in column_choices(session)
    dialog = _dialog(window)
    assert dialog.add_column(dt.DESCRIPTION)
    assert dialog.add_column(configs.PART_COLOR)
    header = dialog.table.horizontalHeaderItem(1)
    assert header is not None and header.text() == text.TABLE_DESCRIPTION_HEADER
    dialog.set_cell(0, dt.DESCRIPTION, "Plain plate")
    dialog.set_cell(0, configs.PART_COLOR, "#112233")
    dialog.accept()
    assert configs.items(session.document)[0]["description"] == "Plain plate"
    assert session.document.appearance["part_color"] == "#112233"
    panel = window.configurations  # type: ignore[attr-defined]
    panel.set_session(session)
    assert panel.list.item(0).toolTip() == "Plain plate"
