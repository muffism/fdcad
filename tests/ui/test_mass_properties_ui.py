"""Mass Properties window (TR79, D764)."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QGuiApplication
from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.mass_properties import ORIGIN, TYPED
from fdcad.ui.main_window.window import MainWindow
from tests.core.features.test_multibody import BLOCK
from tests.ui.test_body_display import _face_of, _open
from tests.ui.test_revolve_edge_axis import _folders, window  # noqa: F401  (fixtures)


def test_command_and_icon() -> None:
    from fdcad.ui.icons.audit import audit

    command = BY_ID["evaluate.mass_properties"]
    assert command.label == "Mass Properties" and command.keys == ()
    assert audit("evaluate.mass_properties") == []


def _values(tool) -> dict[str, str]:  # type: ignore[no-untyped-def]
    return dict(tool.rows)


def test_whole_part_then_picked_body_with_a_typed_density(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    tab = _open(qtbot, window)
    tool = window.mass_properties
    assert window.commands.trigger("evaluate.mass_properties")
    assert tool.panel.isVisible()
    qtbot.waitUntil(lambda: tool.result is not None, timeout=20000)
    assert tool.result.bodies == 2
    assert tool.result.volume == pytest.approx(2 * BLOCK)
    assert _values(tool)["Bodies"] == "2"
    tool.density.setValue(2.0)  # typing a density picks Typed density
    assert tool.material.currentData() == TYPED
    tab.selection = [_face_of(tab, 1)]
    tool.scope.setCurrentIndex(tool.scope.findData("picked"))
    tool.result = None
    assert tool.calculate()
    qtbot.waitUntil(lambda: tool.result is not None, timeout=20000)
    assert tool.result.bodies == 1
    assert tool.result.mass == pytest.approx(BLOCK * 2.0 / 1000)
    tool.copy_values()
    assert "Mass\t" in QGuiApplication.clipboard().text()
    assert not tab.session.is_dirty  # nothing in the part changed


def test_inertia_about_the_origin(qtbot: QtBot, window: MainWindow) -> None:  # noqa: F811
    _open(qtbot, window)
    tool = window.mass_properties
    window.commands.trigger("evaluate.mass_properties")
    qtbot.waitUntil(lambda: tool.result is not None, timeout=20000)
    tool.about.setCurrentIndex(tool.about.findData(ORIGIN))
    tool.result = None
    tool.calculate()
    qtbot.waitUntil(lambda: tool.result is not None, timeout=20000)
    assert any("about part origin" in label for label in _values(tool))


def test_section_of_a_picked_face_and_of_a_sketch(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
) -> None:
    """TR81 (D1019): area and moments of a flat face, or of a sketch picked in the tree."""
    from fdcad.ui.main_window.mass_properties import SECTION

    tab = _open(qtbot, window)
    tool = window.mass_properties
    window.commands.trigger("evaluate.mass_properties")
    qtbot.waitUntil(lambda: tool.result is not None, timeout=20000)
    tool.scope.setCurrentIndex(tool.scope.findData(SECTION))
    tab.selection = []
    window.tree.clearSelection()
    assert not tool.calculate()
    assert "pick a flat face" in tool.values.text()
    tab.selection = [_face_of(tab, 1)]
    assert tool.calculate()
    qtbot.waitUntil(lambda: tool.section is not None, timeout=20000)
    assert tool.section.area > 0
    assert "Polar moment J" in _values(tool)
    tool.section = None
    tab.selection = []
    sketch = next(f for f in tab.session.document.features if f.type == "sketch")
    from fdcad.ui.tree.feature_tree import FID_ROLE

    root = window.tree.invisibleRootItem()
    stack = [root.child(i) for i in range(root.childCount())]
    while stack:
        row = stack.pop()
        if row.data(0, FID_ROLE) == sketch.id:
            row.setSelected(True)
            break
        stack += [row.child(i) for i in range(row.childCount())]
    assert sketch.id in window.tree.selected_features()
    assert tool.calculate()
    qtbot.waitUntil(lambda: tool.section is not None, timeout=20000)
    assert tool.section.area > 0
    tool.copy_values()
    assert "Area\t" in QGuiApplication.clipboard().text()
    assert not tab.session.is_dirty


def test_override_shows_a_mark_and_undoes(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TR80 (D1021): typed mass and centre replace the measured ones, with a mark."""
    from PySide6.QtWidgets import QDialog

    from fdcad.ui.main_window import mass_override

    tab = _open(qtbot, window)
    tool = window.mass_properties
    window.commands.trigger("evaluate.mass_properties")
    qtbot.waitUntil(lambda: tool.result is not None, timeout=20000)

    def typed(dialog: mass_override.MassOverrideDialog) -> int:
        dialog.mass.setValue(123.0)
        dialog.use_centre.setChecked(True)
        dialog.centre[0].setValue(7.0)
        dialog.try_accept()
        return int(dialog.result())

    monkeypatch.setattr(mass_override, "run", typed)
    tool.result = None
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        assert tool.edit_override()
    qtbot.waitUntil(lambda: tool.result is not None, timeout=20000)
    assert tool.result.mass == pytest.approx(123.0)
    assert tool.result.centre[0] == pytest.approx(7.0)
    assert "centre typed" in _values(tool)["Typed values (Override)"]
    assert tab.session.document.mass_override["mass"] == pytest.approx(123.0)

    def bad(dialog: mass_override.MassOverrideDialog) -> int:
        dialog.use_inertia.setChecked(True)
        dialog.inertia[2].setValue(100.0)  # Izz alone: no real body has it
        dialog.try_accept()
        assert "cannot be used" in dialog.note.text()
        return int(QDialog.DialogCode.Rejected)

    monkeypatch.setattr(mass_override, "run", bad)
    assert not tool.edit_override()
    with qtbot.waitSignal(tab.session.rebuilt, timeout=20000):
        tab.session.undo.undo()
    assert tab.session.document.mass_override == {}
