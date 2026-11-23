"""Custom Properties window (TR82, D810)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.properties import rows
from fdcad.ui.main_window import properties_dialog
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_add_rows_work_them_out_and_undo(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    tab, _ids = _open(qtbot, window)
    session = tab.session

    def fill(dialog: properties_dialog.PropertiesDialog) -> bool:
        from fdcad.core.properties import Row

        dialog.add_row(Row("Part number", "text", "BR-1"))
        dialog.add_row(Row("Volume", "number", '="volume@Part"'))
        dialog.add_row(Row("Bad", "number", "lots"))
        dialog.refresh()
        assert "Bad" in dialog.message.text()
        dialog.table.removeRow(2)
        return True

    monkeypatch.setattr(properties_dialog, "run", fill)
    assert window.edit_properties()
    assert [r.name for r in rows(session.document)] == ["Part number", "Volume"]
    session.undo.undo()
    assert session.document.properties == []


def test_the_printer_in_use_drives_the_fit_names(qtbot: QtBot, window: MainWindow) -> None:
    """Changing printer updates the fit values formulas read (TR180, D812)."""
    from dataclasses import replace

    from fdcad.core.equations import solve
    from fdcad.core.printing.profiles import PrinterProfile
    from fdcad.ui.preferences import print_settings

    tab, _ids = _open(qtbot, window)
    doc = tab.session.document
    assert (
        solve(doc).namespace["fit_tolerance@Printer"][1]
        == print_settings.active_profile(window.settings).fit_tolerance
    )
    tight = replace(PrinterProfile(), name="Tight", fit_tolerance=0.1)
    print_settings.set_profiles(window.settings, [tight], "Tight")
    window._printer_changed()
    assert solve(doc).namespace["slip_fit@Printer"][1] == pytest.approx(0.1)
