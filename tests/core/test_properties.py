"""Custom properties (TR82, D810)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fdcad.core.equations import solve
from fdcad.core.io import fdef
from fdcad.core.materials import Material
from fdcad.core.properties import Row, metadata, name_problem, rows, shown
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import plate


def _with(doc, *items: Row) -> None:  # type: ignore[no-untyped-def]
    doc.properties = [r.to_data() for r in items]


def test_kinds_formulas_and_part_values() -> None:
    doc, _ext = plate()  # 50 by 50 by 10: 25000 mm3
    doc.material = Material("Aluminium", 2.7).to_data()
    _with(
        doc,
        Row("Part number", "text", "BR-104"),
        Row("Width", "number", "50"),
        Row("Mass", "number", '="mass@Part"'),
        Row("Twice", "number", '="Width@Properties" * 2'),
        Row("Made", "date", "2026-11-04"),
        Row("Bought", "yes_no", "no"),
        Row("Broken", "date", "4 Nov"),
    )
    rebuild(doc)
    found = {s.name: s for s in shown(doc)}
    assert found["Part number"].text == "BR-104"
    assert found["Mass"].number == pytest.approx(25000 * 2.7 / 1000)
    assert found["Twice"].number == 100
    assert found["Bought"].text == "No" and found["Made"].error == ""
    assert "YYYY-MM-DD" in found["Broken"].error
    assert solve(doc).namespace["Width@Properties"][1] == 50
    assert "Broken" not in metadata(doc) and metadata(doc)["Part number"] == "BR-104"


def test_per_configuration_values_and_the_file(tmp_path: Path) -> None:
    from fdcad.core import configurations as configs

    doc, _ext = plate()
    _with(doc, Row("Revision", "text", "A", (("Default", "B"),)))
    assert shown(doc)[0].text == ("B" if configs.active_name(doc) == "Default" else "A")
    back = fdef.loads(fdef.dumps(doc))
    assert rows(back) == rows(doc)
    back = fdef.loads(fdef.dumps(type(doc)()))
    assert back.properties == []
    raw = fdef.loads(fdef.dumps(doc))
    raw.properties.append({"name": 3})
    assert len(rows(raw)) == 1
    assert (
        name_problem("Revision", ["Revision"])
        and name_problem("9x", [])
        and not name_problem("Part number", [])
    )


def test_properties_go_into_3mf(tmp_path: Path) -> None:
    import zipfile

    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    from fdcad.core.io.export import export_3mf
    from tests.core.io.test_3mf_conformance import _check

    out = tmp_path / "props.3mf"
    export_3mf(BRepPrimAPI_MakeBox(1, 2, 3).Shape(), out, metadata={"Part number": "A&B 7"})
    package = _check(out)
    text = package.read("3D/3dmodel.model").decode()
    assert 'name="fdcad:Part_number">A&amp;B 7<' in text
    assert zipfile.is_zipfile(out)


def test_printer_fit_values_in_formulas() -> None:
    """The printer's fit tolerance and fit presets as equation names (TR180, D812)."""
    from fdcad.core.equations.engine import PRINTER_KEY

    doc, ext = plate()
    names = solve(doc).namespace
    assert names["fit_tolerance@Printer"][1] == pytest.approx(0.2)  # FDCAD's default
    assert names["clearance_fit@Printer"][1] == pytest.approx(0.4)
    assert names["press_fit@Printer"][1] == 0
    feature = doc.feature(ext)
    from fdcad.core.document.model import Param

    feature.params["depth"] = Param('=10mm + "slip_fit@Printer"', 10.2)
    doc.measured[PRINTER_KEY] = {"fit_tolerance": 0.3}
    rebuild(doc)
    assert feature.params["depth"].value == pytest.approx(10.3)
