"""STEP export options: unit, Y up, body names, per body files (TR302 item 1, D1202)."""

from __future__ import annotations

from pathlib import Path

import pytest
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

from fdcad.core.io.export import ExportError, export_step
from fdcad.core.io.step_import import read_step
from fdcad.core.io.step_options import StepOptions, body_paths, safe_part
from tests.core.features.test_features import volume
from tests.core.io.test_3mf_conformance import _two_boxes


def _size(shape: object) -> tuple[float, float, float]:
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    lo, hi = box.CornerMin(), box.CornerMax()
    return (hi.X() - lo.X(), hi.Y() - lo.Y(), hi.Z() - lo.Z())


def test_units_convert_and_read_back(tmp_path: Path) -> None:
    shape = BRepPrimAPI_MakeBox(10, 20, 30).Shape()
    for unit, word in (("in", "INCH"), ("m", "METRE"), ("mm", "MILLI")):
        out = tmp_path / f"{unit}.step"
        export_step(shape, out, unit=unit)
        text = out.read_text(encoding="latin-1").upper()
        assert word in text
        back = read_step(out.read_bytes()).shape
        assert volume(back) == pytest.approx(6000.0, rel=1e-6)
    with pytest.raises(ExportError, match="Choose"):
        export_step(shape, tmp_path / "x.step", unit="ft")


def test_y_up_turns_the_model(tmp_path: Path) -> None:
    shape = BRepPrimAPI_MakeBox(10, 20, 30).Shape()
    out = tmp_path / "y.step"
    export_step(shape, out, y_up=True)
    dx, dy, dz = _size(read_step(out.read_bytes()).shape)
    assert (dx, dy, dz) == pytest.approx((10, 30, 20), abs=1e-4)


def test_body_names_are_products(tmp_path: Path) -> None:
    out = tmp_path / "named.step"
    export_step(_two_boxes(), out, names=["Lid", "Base clip"], color="#FF0000")
    text = out.read_text(encoding="latin-1")
    assert "'Lid'" in text and "'Base clip'" in text
    assert volume(read_step(out.read_bytes()).shape) == pytest.approx(6000 + 125, rel=1e-6)


def test_options_keep_and_damaged_values_fall_back() -> None:
    opts = StepOptions("in", True, False, True, True)
    assert StepOptions.from_data(opts.to_data()) == opts
    assert StepOptions.from_data({"unit": "ft", "y_up": "yes"}) == StepOptions()
    assert StepOptions.from_data(None) == StepOptions()


def test_per_body_file_names(tmp_path: Path) -> None:
    paths = body_paths(tmp_path / "box.step", ["Lid", "lid", "a/b:c"])
    assert [p.name for p in paths] == ["box_Lid.step", "box_lid_2.step", "box_a_b_c.step"]
    assert safe_part("...") == "body"
