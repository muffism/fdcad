"""Print orientation and the build volume check (PLAN Phase 2, DECISIONS D353)."""

from __future__ import annotations

import pytest
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

from fdcad.core.features.face_picks import outward_normal
from fdcad.core.io import fdef
from fdcad.core.naming.names import NamedShape
from fdcad.core.naming.select import reference_for
from fdcad.core.printing import orientation
from fdcad.core.printing.orientation import (
    OrientationError,
    build_direction,
    check_fit,
    down_face,
    print_shape,
    volume_shapes,
)
from fdcad.core.printing.profiles import GENERIC, PrinterProfile
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.samples.make import SAMPLE_DIR, measure


def _plate() -> NamedShape:
    doc = fdef.load(SAMPLE_DIR / "plate_with_holes.fdprt")
    body = RebuildEngine().rebuild(doc).body
    assert body is not None
    return body


def _face(body: NamedShape, normal: tuple[float, float, float]) -> object:
    found = [
        f
        for f in orientation.faces_of(body.shape)
        if outward_normal(f) is not None
        and all(abs(a - b) < 1e-9 for a, b in zip(outward_normal(f), normal, strict=True))
    ]
    assert len(found) == 1
    return found[0]


def _volume(shape: object) -> float:
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return float(props.Mass())


def test_no_orientation_prints_as_modelled() -> None:
    body = _plate()
    assert down_face(body, {"down_face": None}) is None
    assert down_face(body, {}) is None
    assert print_shape(body.shape, None, GENERIC) is body.shape
    assert build_direction(None) == (0.0, 0.0, 1.0)
    fit = check_fit(body.shape, None, GENERIC)
    assert fit.fits and fit.size == pytest.approx((100, 60, 10))


def test_side_face_laid_flat_stands_the_plate_up() -> None:
    body = _plate()
    side = _face(body, (1.0, 0.0, 0.0))
    ref = reference_for(body, side)
    assert ref is not None
    face = down_face(body, {"down_face": ref})
    assert face is not None and face.IsSame(side)
    assert build_direction(face) == pytest.approx((-1.0, 0.0, 0.0))
    fit = check_fit(body.shape, face, GENERIC)
    assert fit.size[2] == pytest.approx(100)
    assert sorted(fit.size[:2]) == pytest.approx([10, 60])
    printed = print_shape(body.shape, face, GENERIC)
    box = measure(printed)["bbox"]
    assert box[2] == pytest.approx(0, abs=1e-6)  # stands on the bed
    assert (box[0] + box[3]) / 2 == pytest.approx(110)  # in the middle of the bed
    assert (box[1] + box[4]) / 2 == pytest.approx(110)
    assert _volume(printed) == pytest.approx(_volume(body.shape))
    assert measure(body.shape)["bbox"] == pytest.approx([0, 0, 0, 100, 60, 10])  # unchanged


def test_too_large_axes_are_named() -> None:
    body = _plate()
    small = PrinterProfile("Small", bed_x=80, bed_y=80, height=5)
    fit = check_fit(body.shape, None, small)
    assert not fit.fits and fit.too_large == ("X", "Z")
    fit = check_fit(body.shape, _face(body, (0.0, 1.0, 0.0)), small)
    assert "Z" in fit.too_large  # stood on its long side it is 60 mm tall


def test_bed_is_drawn_under_the_part_in_model_coordinates() -> None:
    body = _plate()
    bed, box = volume_shapes(body.shape, None, GENERIC)
    bed_box = measure(bed)["bbox"]
    assert bed_box[2] == pytest.approx(0) and bed_box[5] == pytest.approx(0)
    assert bed_box[3] - bed_box[0] == pytest.approx(220)
    assert (bed_box[0] + bed_box[3]) / 2 == pytest.approx(50)  # centred under the part
    edges = measure(box)
    assert edges["edges"] == 12
    assert edges["bbox"][5] - edges["bbox"][2] == pytest.approx(250)
    side = _face(body, (1.0, 0.0, 0.0))
    bed, _box = volume_shapes(body.shape, side, GENERIC)
    bed_box = measure(bed)["bbox"]
    assert bed_box[0] == pytest.approx(100) and bed_box[3] == pytest.approx(100)  # at the face


def test_lost_or_curved_down_face_is_an_orientation_error() -> None:
    body = _plate()
    lost = {"kind": "face", "name": "f99/cap/end"}
    with pytest.raises(OrientationError, match="Reselect"):
        down_face(body, {"down_face": lost})
    doc = fdef.load(SAMPLE_DIR / "turned_shaft.fdprt")
    shaft = RebuildEngine().rebuild(doc).body
    assert shaft is not None
    curved = next(f for f in orientation.faces_of(shaft.shape) if outward_normal(f) is None)
    ref = reference_for(shaft, curved)
    assert ref is not None
    with pytest.raises(OrientationError, match="no longer flat"):
        down_face(shaft, {"down_face": ref})


def test_older_files_without_print_setup_print_as_modelled() -> None:
    import json

    data = json.loads((SAMPLE_DIR / "plate_with_holes.fdprt").read_text(encoding="utf-8"))
    data.pop("print_setup", None)
    doc = fdef.loads(json.dumps(data))
    assert doc.print_setup == {"down_face": None}
    body = RebuildEngine().rebuild(doc).body
    assert down_face(body, doc.print_setup) is None


def test_each_body_is_checked_on_its_own() -> None:
    """Pieces of Split for Print that each fit pass the check (D622)."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    from fdcad.core.features.solids import compound

    small = PrinterProfile("Small", bed_x=80, bed_y=80, height=50)
    left = BRepPrimAPI_MakeBox(60.0, 60.0, 10.0).Shape()
    right = BRepPrimAPI_MakeBox(gp_Pnt(60, 0, 0), 60.0, 60.0, 10.0).Shape()
    fit = check_fit(compound([left, right]), None, small)
    assert fit.fits and fit.bodies == 2 and fit.too_big == 0
    assert fit.size == pytest.approx((60, 60, 10))
    wide = BRepPrimAPI_MakeBox(gp_Pnt(200, 0, 0), 90.0, 60.0, 10.0).Shape()
    fit = check_fit(compound([left, right, wide]), None, small)
    assert not fit.fits and fit.too_big == 1 and fit.too_large == ("X",)
    assert fit.size == pytest.approx((90, 60, 10))


def test_face_colours_move_with_a_laid_flat_part(tmp_path: object) -> None:
    """Spec 2 section 20 item 12 (D714): Export 3MF with a print orientation lost every
    face colour."""
    import zipfile
    from pathlib import Path

    from fdcad.core.io.export import export_3mf

    body = _plate()
    side = _face(body, (1.0, 0.0, 0.0))
    top = _face(body, (0.0, 0.0, 1.0))
    shape, faces = orientation.print_shape_faces(body.shape, side, GENERIC, [(top, "#FF0000")])  # type: ignore[arg-type]
    assert len(faces) == 1 and not faces[0][0].IsSame(top)
    path = Path(str(tmp_path)) / "flat.3mf"
    export_3mf(shape, str(path), faces=faces)
    with zipfile.ZipFile(path) as archive:
        model = archive.read("3D/3dmodel.model").decode()
    assert "#FF0000" in model and 'p1="1"' in model  # the top face's triangles


def test_fit_to_volume_turns_first_then_scales() -> None:
    """Scale to fit the printer (TR185, D828)."""
    from dataclasses import replace

    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    from fdcad.core.printing.orientation import check_fit, fit_to_volume, print_shape

    small = replace(GENERIC, bed_x=100.0, bed_y=100.0, height=100.0)
    bar = BRepPrimAPI_MakeBox(120.0, 10.0, 10.0).Shape()  # too long, but fits turned 45 deg
    factor, angle = fit_to_volume(bar, None, small)
    assert factor == 1.0 and 0 < angle < 90
    assert check_fit(bar, None, small, (factor, angle)).fits
    block = BRepPrimAPI_MakeBox(200.0, 50.0, 50.0).Shape()  # needs shrinking
    factor, angle = fit_to_volume(block, None, small)
    assert 0.5 < factor < 1.0
    assert check_fit(block, None, small, (factor, angle)).fits
    printed = print_shape(block, None, small, (factor, angle))
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(printed, props)
    assert props.Mass() == pytest.approx(200 * 50 * 50 * factor**3, rel=1e-6)
    cube = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    assert fit_to_volume(cube, None, small) == (1.0, 0.0)
