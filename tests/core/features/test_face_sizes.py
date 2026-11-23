"""Set a size on a face (TR265, D789)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureError, FeatureState
from fdcad.core.naming.select import reference_for
from tests.core.features.test_features import body, rebuild, volume
from tests.core.features.test_hole import add_hole, on_top


def _holed() -> tuple[Document, str, str, Any]:
    """The 50 by 50 by 10 plate with one 5 mm hole 6 deep at (10, 10)."""
    doc, ext, sk, top = on_top([(10, 10)])
    hole = add_hole(doc, sk, face=top, diameter=5.0, depth=6.0)
    return doc, ext, hole, body(rebuild(doc), hole)


def _move(doc: Document, refs: dict[str, Any], **params: Any) -> Any:
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "move_face", "Move Face 1", params=params, refs=refs))
    res = rebuild(doc)[fid]
    doc.features.pop()
    return res


def test_resize_a_hole_to_a_diameter() -> None:
    doc, _ext, hole, b = _holed()
    wall = next(n for n, _f in b.faces if n.startswith(f"{hole}/hole/") and n.endswith("/wall"))
    refs = {"faces": [reference_for(b, b.face(wall))]}
    start = volume(b.shape)
    bigger = _move(doc, refs, mode="resize", diameter=Param("6", 6.0))
    assert bigger.state is not FeatureState.ERROR, bigger.issues
    assert start - volume(bigger.body.shape) == pytest.approx(
        math.pi * (3.0**2 - 2.5**2) * 6.0, rel=1e-4
    )
    smaller = _move(doc, refs, mode="resize", diameter=Param("4", 4.0))
    assert volume(smaller.body.shape) - start == pytest.approx(
        math.pi * (2.5**2 - 2.0**2) * 6.0, rel=1e-4
    )


def test_resize_refuses_a_flat_face() -> None:
    doc, ext, _hole, b = _holed()
    refs = {"faces": [reference_for(b, b.face(f"{ext}/cap/end"))]}
    res = _move(doc, refs, mode="resize", diameter=Param("6", 6.0))
    assert res.state is FeatureState.ERROR
    assert "not a cylinder, sphere or torus" in res.issues[0].message


def test_set_a_measured_size_from_a_hole_centre() -> None:
    doc, ext, hole, b = _holed()
    side = next(n for n, f in b.faces if n.startswith(f"{ext}/side/") and abs(_centre(f)[0]) < 1e-6)
    wall = next(n for n, _f in b.faces if n.startswith(f"{hole}/hole/") and n.endswith("/wall"))
    refs = {
        "faces": [reference_for(b, b.face(side))],
        "size_from": [reference_for(b, b.face(wall))],
    }
    start = volume(b.shape)
    # The side at x = 0 is 10 from the hole's axis; at 5 the plate loses a 5 mm strip.
    nearer = _move(doc, refs, mode="offset", set_size=Param("5", 5.0))
    assert nearer.state is not FeatureState.ERROR, nearer.issues
    assert start - volume(nearer.body.shape) == pytest.approx(5 * 50 * 10, rel=1e-6)
    further = _move(doc, refs, mode="offset", set_size=Param("12", 12.0))
    assert volume(further.body.shape) - start == pytest.approx(2 * 50 * 10, rel=1e-6)


def _centre(face: Any) -> tuple[float, float, float]:
    from fdcad.core.naming.names import centroid

    return centroid(face)


def test_cone_resize_keeps_the_chosen_end() -> None:
    """Resize a cone face to a new half angle, keeping the large or small end (D799)."""
    import math

    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone

    from fdcad.core.features.cone_resize import is_cone, resize_cone
    from fdcad.core.features.solids import volume_of
    from fdcad.core.naming.names import NamedShape, faces_of, restrict

    cone = BRepPrimAPI_MakeCone(10, 5, 10).Shape()
    named = NamedShape(cone, restrict([], cone, "t"))
    (face,) = [f for f in faces_of(cone) if is_cone(f)]

    def frustum(r1: float, r2: float) -> float:
        return math.pi * 10 / 3 * (r1 * r1 + r1 * r2 + r2 * r2)

    big = resize_cone(named, face, math.radians(10), "large", "f9", "Move Face 1", "cone")
    r_top = 10 - 10 * math.tan(math.radians(10))
    assert volume_of(big.shape) == pytest.approx(frustum(10, r_top), rel=1e-6)
    small = resize_cone(named, face, math.radians(10), "small", "f9", "Move Face 1", "cone")
    r_bottom = 5 + 10 * math.tan(math.radians(10))
    assert volume_of(small.shape) == pytest.approx(frustum(r_bottom, 5), rel=1e-6)
    with pytest.raises(FeatureError, match="would close"):
        resize_cone(named, face, math.radians(60), "large", "f9", "Move Face 1", "cone")


def test_resize_a_countersink_through_move_face() -> None:
    import math

    from fdcad.core.features.cone_resize import is_cone
    from fdcad.core.features.hole import defaults_for
    from tests.core.features.test_hole import add_hole, on_top

    doc, _ext, sk, top = on_top([(25, 25)])
    values = defaults_for("countersink", "iso", "M4")
    hole = add_hole(doc, sk, "countersink", top, end_condition="through_all", **values)
    b = body(rebuild(doc), hole)
    (cone,) = [f for _n, f in b.faces if is_cone(f)]
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "move_face",
            "Move Face 1",
            params={
                "mode": "resize",
                "cone_angle": Param("40", math.radians(40)),
                "keep_end": "large",
            },
            refs={"faces": [reference_for(b, cone)]},
        )
    )
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, res.issues
    (after,) = [f for _n, f in res.body.faces if is_cone(f)]
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    assert abs(BRepAdaptor_Surface(after).Cone().SemiAngle()) == pytest.approx(math.radians(40))


def _sized(doc: Document, ext: str, **params: Any) -> str:
    """A Move Face setting the plate's top to a measured size from its bottom."""
    b = body(rebuild(doc), doc.features[-1].id)
    top, bottom = b.face(f"{ext}/cap/end"), b.face(f"{ext}/cap/start")
    fid = doc.new_feature_id()
    values = {"mode": "offset", "offset_by": "measured", "set_size": Param("14", 14.0), **params}
    doc.features.append(
        Feature(
            fid,
            "move_face",
            f"Move Face {fid}",
            params=values,
            refs={"faces": [reference_for(b, top)], "size_from": [reference_for(b, bottom)]},
        )
    )
    return fid


def test_symmetric_size_moves_both_faces_half_each() -> None:
    from tests.core.features.test_features import bounds, plate

    doc, ext = plate()
    one = _sized(doc, ext)
    assert bounds(body(rebuild(doc), one).shape)[2::3] == pytest.approx((0, 14))
    doc.feature(one).params["symmetric"] = True
    assert bounds(body(rebuild(doc), one).shape)[2::3] == pytest.approx((-2, 12))


def test_a_locked_size_holds_when_a_later_move_takes_one_face() -> None:
    from tests.core.features.test_features import bounds, plate

    doc, ext = plate()
    sized = _sized(doc, ext, set_size=Param("10", 10.0), lock_size=True)
    b = body(rebuild(doc), sized)
    later = doc.new_feature_id()
    doc.features.append(
        Feature(
            later,
            "move_face",
            "Move Face 2",
            params={"mode": "offset", "distance": Param("3", 3.0), "reverse": True},
            refs={"faces": [reference_for(b, b.face(f"{ext}/cap/start"))]},
        )
    )
    out = body(rebuild(doc), later)
    assert bounds(out.shape)[2::3] == pytest.approx((3, 13))  # the top came along
    doc.feature(sized).params["lock_size"] = False
    out = body(rebuild(doc), later)
    assert bounds(out.shape)[2::3] == pytest.approx((3, 10))


def test_the_size_has_an_arrow_in_the_view() -> None:
    from fdcad.core.features.base import BuildContext
    from fdcad.core.features.move_face import MoveFace
    from tests.core.features.test_features import plate

    doc, ext = plate()
    fid = _sized(doc, ext)
    results = rebuild(doc)
    before = body(results, ext)
    feature = doc.feature(fid)
    (arrow,) = MoveFace().preview_handles(feature, BuildContext(doc, before, results, {}))
    assert arrow.param == "set_size" and arrow.value == pytest.approx(14)
    assert arrow.base[2] == pytest.approx(0) and arrow.direction[2] == pytest.approx(1)
    feature.params["symmetric"] = True
    (arrow,) = MoveFace().preview_handles(feature, BuildContext(doc, before, results, {}))
    assert arrow.value == pytest.approx(7) and arrow.scale == 2.0
    assert arrow.base[2] == pytest.approx(5)
