"""Part material: dialog, tree row, file, and the tools that use it (TR78, D803)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.io import fdef
from fdcad.core.materials import Material, density_text, from_data, library, part_material
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window import material_dialog
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_body_tools import _open
from tests.ui.test_revolve_edge_axis import _folders, window

__all__ = ["_folders", "window"]


def test_library_file_and_damaged_values() -> None:
    from fdcad.core.document.model import new_document

    names = [m.name for m in library({"PLA": 1.3, "Oak": 0.75})]
    assert "Aluminium" in names and "Oak" in names
    assert next(m for m in library({"PLA": 1.3}) if m.name == "PLA").density == 1.3
    assert density_text(1.0) == "1 g/cm3 (0.03613 lb/in3)"
    doc = new_document()
    assert "material" not in fdef.dumps(doc)
    doc.material = Material("Brass", 8.5, "#C9A43A", 1.0).to_data()
    back = fdef.loads(fdef.dumps(doc))
    assert part_material(back) == Material("Brass", 8.5, "#C9A43A", 1.0)
    assert from_data({"name": "X", "density": -1}) is None
    assert from_data({"name": "X", "density": 2, "colour": "red"}) == Material("X", 2.0)


def test_choose_a_material_from_the_tree(
    qtbot: QtBot, window: MainWindow, monkeypatch: object
) -> None:
    assert BY_ID["tools.material"].keys == ()
    tab, _ids = _open(qtbot, window)
    session = tab.session

    def pick(dialog: material_dialog.MaterialDialog) -> bool:
        dialog.choice.setCurrentIndex(dialog.choice.findData("Aluminium"))
        dialog.use_colour.setChecked(True)
        return True

    monkeypatch.setattr(material_dialog, "run", pick)  # type: ignore[attr-defined]
    assert window.edit_material()
    found = part_material(session.document)
    assert found is not None and found.name == "Aluminium" and found.density == 2.7
    assert session.document.appearance["part_color"] == "#C4C8CC"
    tree = window.tree
    assert tree is not None
    rows = [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())]
    qtbot.waitUntil(
        lambda: (
            "Material: Aluminium"
            in [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())]
        ),
        timeout=5000,
    )
    assert rows is not None
    window.mass_properties.fill()
    assert window.mass_properties.material.currentData() == "Aluminium"
    assert window.mass_properties.density.value() == 2.7
    session.undo.undo()
    assert part_material(session.document) is None
