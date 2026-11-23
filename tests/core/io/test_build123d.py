"""build123d script export (PLAN Phase 5, D342)."""

from __future__ import annotations

import pytest

from fdcad.core.io import fdef
from fdcad.core.io.build123d import script_for
from fdcad.samples.make import SAMPLE_DIR
from fdcad.samples.parts import SAMPLES


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_every_sample_gives_valid_python(name: str) -> None:
    doc = fdef.load(SAMPLE_DIR / f"{name}.fdprt")
    script = script_for(doc, name)
    compile(script, f"{name}.py", "exec")
    assert script.startswith(f'"""{name}, exported from FDCAD')
    assert "from build123d import *" in script and "result = part.part" in script


def test_plate_sketches_holes_and_cuts() -> None:
    doc = fdef.load(SAMPLE_DIR / "plate_with_holes.fdprt")
    script = script_for(doc, "Plate")
    assert "# Variable Width = 100mm (100)" in script
    assert "Plane(origin=(0, 0, 0), x_dir=(1, 0, 0), z_dir=(0, 0, 1))" in script
    assert script.count("        Line(") == 4
    assert script.count("Circle(4, mode=Mode.ADD)") == 4  # a sketch of circles only
    assert "Circle(10, mode=Mode.ADD)" in script
    assert "extrude(sketch_f5.sketch, amount=10, dir=(0, 0, 1), mode=Mode.ADD)" in script
    assert "# Through All, written as a long extrude" in script
    assert "mode=Mode.SUBTRACT)" in script.split("# Holes")[1]


def test_revolve_axis_and_unsupported_features_become_comments() -> None:
    shaft = script_for(fdef.load(SAMPLE_DIR / "turned_shaft.fdprt"), "Shaft")
    assert "revolve(sketch_f5.sketch, axis=Axis((-10, 0, 0), (140, 0, 0))" in shaft
    assert "revolution_arc=360" in shaft
    sheet = script_for(fdef.load(SAMPLE_DIR / "sheet_metal_bracket.fdprt"), "Bracket")
    assert "# Not exported: base_flange features" in sheet
    assert sheet.count("Circle(3, mode=Mode.SUBTRACT)") == 2  # holes inside the outline
    assert "# Not exported: flatten features" in sheet


def test_arcs_and_mid_plane() -> None:
    import math

    from fdcad.core.document.model import Feature, Param, new_document
    from fdcad.samples.builder import FRONT, SketchBuilder, add_sketch

    doc = new_document()
    sk = SketchBuilder()
    s = sk.sk
    s.add_line(0, 0, 10, 0)
    s.add_arc(10, 5, 5, -math.pi / 2, math.pi / 2)
    s.add_line(10, 10, 0, 10)
    s.add_line(0, 10, 0, 0)
    sid = add_sketch(doc, sk, {"feature": FRONT}, "Slot")
    doc.features.append(
        Feature(
            doc.new_feature_id(), "extrude", "Slot", refs={"sketch": {"feature": sid}},
            params={"operation": "boss", "end_condition": "mid_plane", "depth": Param("4", 4.0)},
        )
    )  # fmt: skip
    script = script_for(doc)
    compile(script, "slot.py", "exec")
    assert "CenterArc((10, 5), 5, -90, 180)" in script
    assert "amount=2, both=True" in script


def test_revolve_end_conditions_export_or_say_why_not() -> None:
    """TOOL_SPEC T16 item 2: a full turn exports, picked ends become a comment."""
    from tests.core.features.test_features import shaft

    doc, rev = shaft(90, end_condition="through_all")
    assert "revolution_arc=360" in script_for(doc, "Shaft")
    doc.feature(rev).params["end_condition"] = "up_to_face"
    doc.feature(rev).refs["end_ref"] = {"feature": "f4"}
    assert "# Not exported: revolve end condition up_to_face." in script_for(doc, "Shaft")


def test_revolve_thin_feature_becomes_a_comment() -> None:
    """D523: a thin revolve has no direct build123d call, so it says why."""
    from fdcad.core.document.model import Param
    from tests.core.features.test_features import shaft

    doc, _rev = shaft(90, thin_type="one_direction", thin_thickness=Param("1", 1.0))
    assert "# Not exported: revolve Thin Feature." in script_for(doc, "Shaft")
