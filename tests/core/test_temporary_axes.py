"""Temporary axes through round faces (TR17, D693)."""

from __future__ import annotations

import pytest

from fdcad.core.features.base import FeatureState
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.links import ModelGeometry
from fdcad.core.sketch.profiles import BASIS_PLANES
from fdcad.core.temporary_axes import temporary_axes, with_axes
from fdcad.samples.make import SAMPLE_DIR


def _bracket_shape() -> object:
    doc = fdef.loads((SAMPLE_DIR / "bracket.fdprt").read_text(encoding="utf-8"))
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None
    return report.body.shape


def test_one_axis_per_hole_running_past_the_part() -> None:
    axes = temporary_axes(_bracket_shape())  # type: ignore[arg-type]
    assert len(axes) == 4  # two base holes, two leg holes
    for axis in axes:
        d = axis.direction
        assert max(abs(c) for c in d) == pytest.approx(1.0)  # along a model axis
        length = sum((b - a) ** 2 for a, b in zip(axis.start, axis.end, strict=True)) ** 0.5
        assert length >= 8 + 2 * 5 - 1e-9  # the 8 mm plate, plus at least 5 mm each side
        assert axis.faces


def test_no_round_faces_no_axes() -> None:
    assert temporary_axes(None) == []


def test_axes_become_sketch_snap_lines() -> None:
    axes = temporary_axes(_bracket_shape())  # type: ignore[arg-type]
    geometry = with_axes(ModelGeometry(), axes, BASIS_PLANES["xy"])
    assert isinstance(geometry, ModelGeometry)
    # Axes along Z are square to the Front plane and are left out.
    seen = [a for a in axes if abs(a.direction[2]) < 0.5]
    assert len(geometry.lines) == len(seen) == len(geometry.polylines)


def test_revolve_refuses_a_round_face_axis_off_the_sketch_plane() -> None:
    from fdcad.core.document.model import Feature, Param
    from fdcad.core.naming.select import reference_for

    doc = fdef.loads((SAMPLE_DIR / "bracket.fdprt").read_text(encoding="utf-8"))
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None
    face = temporary_axes(report.body.shape)[0].faces[0]
    ref = reference_for(report.body, face)
    assert ref is not None
    doc.features.append(
        Feature(
            doc.new_feature_id(),
            "revolve",
            "Revolve 1",
            params={"angle": Param("90deg", 1.5707963267948966)},
            refs={"sketch": {"feature": "f5"}, "axis": ref},
        )
    )
    result = RebuildEngine().rebuild(doc).results[doc.features[-1].id]
    assert result.state is FeatureState.ERROR
    assert "not in the sketch plane" in " ".join(i.message for i in result.issues)


def test_a_round_face_on_the_second_axis_joins_it() -> None:
    # D2610: matching a face to an axis found earlier than the first compared tuples
    # of numpy arrays, which raised; the sketch then lost all its part snap targets.
    # On the nut and bolt it happened every time a sketch opened with axes shown.
    from OCP.BRep import BRep_Builder
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCP.TopoDS import TopoDS_Compound

    def cylinder(x: float, z: float, r: float) -> object:
        return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, 0, z), gp_Dir(0, 0, 1)), r, 5).Shape()

    parts = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(parts)
    for piece in (cylinder(0, 0, 3), cylinder(20, 0, 3), cylinder(20, 5, 5)):  # a counterbore
        builder.Add(parts, piece)
    axes = temporary_axes(parts)
    assert len(axes) == 2
    second = next(a for a in axes if abs(a.start[0] - 20) < 1e-9)
    assert len(second.faces) == 2
    assert min(second.start[2], second.end[2]) < 0 and max(second.start[2], second.end[2]) > 10
