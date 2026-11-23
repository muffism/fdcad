"""Grow or shrink an extrude's profile (TUTORIAL_REVIEW_SPEC_2 TR344, DECISIONS D880).

``profile_offset`` on Extruded Boss and Cut: every profile face is offset in its
plane by the value, outward for a positive value and inward for a negative one,
with rounded outside corners, so one sketch makes both mating parts (often with a
print fit variable). Edges keep their sketch entity, so the side faces keep their
names. No Qt.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from fdcad.core.features.base import FeatureError


def offset_face(face: Any, distance: float) -> tuple[Any, list[tuple[Any, Any]]]:
    """``face`` grown by ``distance`` (negative shrinks), and (old edge, new edge) pairs."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffset
    from OCP.GeomAbs import GeomAbs_Arc
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_WIRE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    from fdcad.core.features.solids import face_area
    from fdcad.core.occ import shape_list

    maker = BRepOffsetAPI_MakeOffset(face, GeomAbs_Arc)
    maker.Perform(distance)
    if not maker.IsDone():
        raise ValueError("offset failed")
    wires = []
    exp = TopExp_Explorer(maker.Shape(), TopAbs_WIRE)
    while exp.More():
        wires.append(TopoDS.Wire(exp.Current()))
        exp.Next()
    if not wires:
        raise ValueError("offset made nothing")
    faces = [BRepBuilderAPI_MakeFace(w, True).Face() for w in wires]
    order = sorted(range(len(wires)), key=lambda i: -face_area([faces[i]]))
    build = BRepBuilderAPI_MakeFace(faces[order[0]])
    for i in order[1:]:
        build.Add(TopoDS.Wire(wires[i].Reversed()))
    made = build.Face()
    pairs: list[tuple[Any, Any]] = []
    exp = TopExp_Explorer(face, TopAbs_EDGE)
    while exp.More():
        old = TopoDS.Edge(exp.Current())
        for new in shape_list(maker.Generated(old)):
            if new.ShapeType() == TopAbs_EDGE:
                pairs.append((old, TopoDS.Edge(new)))
        exp.Next()
    return made, pairs


def offset_sketch(sketch: Any, distance: float, name: str) -> Any:
    """A copy of the SketchOutput with its profile offset by ``distance``."""
    from fdcad.core.sketch.profiles import Profile

    profile = sketch.profile
    if profile is None or abs(distance) < 1e-12:
        return sketch
    faces: list[Any] = []
    edges: list[tuple[Any, str]] = []
    for face in profile.faces:
        try:
            made, pairs = offset_face(face, distance)
        except Exception as exc:
            raise FeatureError(
                f"{name}: the profile cannot be offset by {distance:g} mm. Use a smaller offset."
            ) from exc
        faces.append(made)
        for old, new in pairs:
            entity = profile.entity_of(old)
            if entity is not None:
                edges.append((new, entity))
    return dataclasses.replace(sketch, profile=Profile(faces, edges))
