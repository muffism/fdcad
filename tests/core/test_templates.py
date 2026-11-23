"""Part templates (TR217, D833)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fdcad.core.document.model import Variable, new_document
from fdcad.core.templates import list_templates, new_from_template, save_template
from fdcad.core.units import Kind, UnitSystem
from tests.core.equations.test_equations import _plate


def test_save_list_and_start_from_a_template(tmp_path: Path) -> None:
    doc = _plate()
    doc.units = UnitSystem.IN
    doc.variables.append(Variable("Wall", Kind.LENGTH, "2", 2.0))
    doc.appearance = {"part_color": "#336699", "faces": {"f6/cap/end": "#ff0000"}}
    doc.print_setup = {"down_face": {"kind": "face"}, "mesh_export": {"deviation": 0.01}}
    doc.material = {"name": "PLA", "density": 1.24}
    path = save_template(doc, tmp_path, "Bracket: base", printer="My Printer")
    assert path.name == "Bracket base.fdprt"
    assert list_templates(tmp_path) == [("Bracket base", path)]
    made, printer = new_from_template(path)
    assert printer == "My Printer"
    assert made.units is UnitSystem.IN
    assert [v.name for v in made.variables] == ["Width", "Wall"]
    assert made.appearance == {"part_color": "#336699"}
    assert made.print_setup == {"mesh_export": {"deviation": 0.01}}
    assert made.material["name"] == "PLA"
    assert len(made.features) == len(new_document().features)  # no features of its own
    with pytest.raises(ValueError, match="Enter a template name"):
        save_template(doc, tmp_path, " / ")
    assert list_templates(tmp_path / "none") == []
