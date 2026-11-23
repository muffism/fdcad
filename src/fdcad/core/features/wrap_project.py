"""Wrap, Project method: a sketch projected along a direction onto any face, raised
or sunk by a height (TR156, D2113).

The sketch's closed regions are swept along the direction (the pull direction, or
the sketch plane's normal) right through the part. The body is offset by the height
(out for emboss, in for deboss) to give a skin of that height, the sweeps are cut to
the skin, and only the pieces on the picked face nearest the sketch are kept, so the
raised or sunk shape follows the face, whatever its shape, with walls along the
direction. Lengths are not kept along a curved face, unlike the
Analytical and Spline methods: the outline is a shadow of the sketch. Kernel work:
rebuild thread only.

The kernel cannot offset every body: a frame of joined tubes with rounds at the
joints fails. Then only the picked face is made thick by the height (D1044), which
gives the same skin under the face and does not depend on the rest of the part.
"""

from __future__ import annotations

from typing import Any

from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Trsf, gp_Vec

from fdcad.core.features import fastening as fx
from fdcad.core.features.base import FeatureError
from fdcad.core.features.solids import bounding_size, solids, volume_of
from fdcad.core.occ import BRepAlgoAPI_Common, BRepAlgoAPI_Cut


def _offset(solid: Any, distance: float) -> Any | None:
    from OCP.BRepOffset import BRepOffset_MakeOffset, BRepOffset_Skin
    from OCP.GeomAbs import GeomAbs_Arc
    from OCP.Message import Message_ProgressRange

    maker = BRepOffset_MakeOffset()
    maker.Initialize(solid, distance, 1e-6, BRepOffset_Skin, False, False, GeomAbs_Arc, False)
    try:
        maker.MakeOffsetShape(Message_ProgressRange())
    except Exception:
        return None
    if not maker.IsDone() or maker.Shape().IsNull() or not solids(maker.Shape()):
        return None
    return solids(maker.Shape())[0]


def _thick_face(face: Any, solid: Any, height: float, outward: bool) -> Any | None:
    """The skin under (or over) ``face`` alone: the face made thick by ``height``,
    kept to the material of ``solid`` (deboss) or to the room outside it (emboss).
    None when the kernel cannot thicken the face."""
    from OCP.BRepOffset import BRepOffset_MakeOffset, BRepOffset_Skin
    from OCP.GeomAbs import GeomAbs_Arc
    from OCP.Message import Message_ProgressRange

    maker = BRepOffset_MakeOffset()
    distance = height if outward else -height
    maker.Initialize(face, distance, 1e-6, BRepOffset_Skin, False, False, GeomAbs_Arc, True)
    try:
        maker.MakeOffsetShape(Message_ProgressRange())
    except Exception:
        return None
    if not maker.IsDone() or maker.Shape().IsNull() or not solids(maker.Shape()):
        return None
    thick = solids(maker.Shape())[0]
    kept = BRepAlgoAPI_Cut(thick, solid) if outward else BRepAlgoAPI_Common(thick, solid)
    if not kept.IsDone() or not solids(kept.Shape()):
        return None
    return kept.Shape()


def _slab(owner: str, face: Any, body: Any, height: float, outward: bool) -> Any:
    """The skin of the body holding ``face``: the room ``height`` outside it (emboss)
    or the material ``height`` inside it (deboss)."""
    from fdcad.core.features.bodies import solid_of_face

    index = solid_of_face(body, face)
    solid = solids(body)[index] if index >= 0 else body
    moved = _offset(solid, height if outward else -height)
    if moved is None:
        skin = _thick_face(face, solid, height, outward)  # D1044
        if skin is not None:
            return skin
        raise FeatureError(
            f"{owner}: the body could not be grown by the height. Reduce the height."
        )
    skin = BRepAlgoAPI_Cut(moved, solid) if outward else BRepAlgoAPI_Cut(solid, moved)
    if not skin.IsDone():
        raise FeatureError(f"{owner}: the face could not be made thick. Reduce the height.")
    return skin.Shape()


_TOUCH = 1e-4


def _box(shape: Any) -> Any:
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box, False)  # from the geometry: never smaller than the shape
    return box


def _touches(shape: Any, face: Any, face_box: Any = None) -> bool:
    """True when ``shape`` comes within 1e-4 mm of ``face``.

    The distance from a solid to a large lofted face is slow (4.5 s for the ten letters
    on a bike frame's down tube, D1090), so two quick answers come first: no, when the
    bounding boxes are apart, and yes, when a corner of the shape lies on the face (a
    piece of the skin under the face has its top corners on it).
    """
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer

    if face_box is None:
        face_box = _box(face)
    if _box(shape).Distance(face_box) > _TOUCH:
        return False
    corners = TopExp_Explorer(shape, TopAbs_VERTEX)
    while corners.More():
        gap = BRepExtrema_DistShapeShape(corners.Current(), face)
        if gap.IsDone() and gap.Value() <= _TOUCH:
            return True
        corners.Next()
    gap = BRepExtrema_DistShapeShape(shape, face)
    return bool(gap.IsDone() and gap.Value() <= _TOUCH)


def _cut_to_skin(sweeps: list[Any], slab: Any) -> list[Any]:
    """The pieces of ``slab`` inside the ``sweeps``: one boolean for all of them when no
    two sweeps' boxes meet, else one each (D1090)."""
    from fdcad.core.features.solids import compound

    boxes = [_box(s) for s in sweeps]
    apart = all(
        boxes[i].IsOut(boxes[j]) for i in range(len(boxes)) for j in range(i + 1, len(boxes))
    )
    groups = [compound(sweeps)] if apart and len(sweeps) > 1 else sweeps
    out: list[Any] = []
    for tool in groups:
        common = BRepAlgoAPI_Common(tool, slab)
        if common.IsDone():
            out.extend(solids(common.Shape()))
    return out


def projected(
    owner: str,
    regions: list[Any],
    direction: fx.Vec3,
    face: Any,
    body: Any,
    height: float,
    outward: bool,
    origin: fx.Vec3 = (0.0, 0.0, 0.0),
) -> list[Any]:
    """The raised or sunk solids of the sketch ``regions`` projected along
    ``direction`` onto ``face``. Raises FeatureError."""
    slab = _slab(owner, face, body, height, outward)
    d = fx.unit(direction)
    reach = 2.0 * bounding_size(body) + 2.0 * height + 1.0
    shift = gp_Trsf()
    shift.SetTranslation(gp_Vec(*fx.add((0, 0, 0), d, -reach)))
    sweeps = []
    for region in regions:
        start = BRepBuilderAPI_Transform(region, shift, True).Shape()
        sweeps.append(
            BRepPrimAPI_MakePrism(start, gp_Vec(*fx.add((0, 0, 0), d, 2 * reach))).Shape()
        )
    face_box = _box(face)
    # Keep only the pieces on the picked face, not where the sweeps cross others.
    out = [
        p for p in _cut_to_skin(sweeps, slab) if volume_of(p) > 1e-9 and _touches(p, face, face_box)
    ]
    if out:  # the first surface the sketch meets, not the far side of the part

        def along(shape: Any) -> float:
            from OCP.BRepGProp import BRepGProp
            from OCP.GProp import GProp_GProps

            props = GProp_GProps()
            BRepGProp.VolumeProperties_s(shape, props)
            c = props.CentreOfMass()
            return abs(fx.dot(fx.sub((c.X(), c.Y(), c.Z()), origin), d))

        nearest = min(along(p) for p in out)
        out = [p for p in out if along(p) <= nearest + 2 * height + 1e-6]
    if not out:
        raise FeatureError(
            f"{owner}: the sketch does not fall on the face along the direction. "
            "Move the sketch over the face or pick another direction."
        )
    return out
