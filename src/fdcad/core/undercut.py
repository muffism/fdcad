"""Undercut analysis (TUTORIAL_REVIEW_SPEC_2 TR83, DECISIONS D864).

For a pull direction, each face is sorted by whether it can be seen from above
(looking against the pull) or from below, using rays: a few points on the face
look along the pull and against it, and a point is seen from a side when its
face turns toward that side and nothing of the part is in the way.

- ``above``: every point seen from above. ``below``: every point seen from below.
- ``straddle``: some points seen, some not.
- ``undercut``: no point seen from either side (the mould could not reach it).
- ``side``: a wall along the pull direction, seen from neither side.

Display only; no Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

GROUPS = ("above", "below", "straddle", "undercut", "side")
#: Normals closer to square than this (cosine) count as walls along the pull.
_WALL = 1e-3
#: Points tried on each face along its U and V.
_GRID = 3


@dataclass
class FaceSight:
    """One face and its group."""

    face: Any
    group: str


def _samples(face: Any) -> list[tuple[Any, Any]]:
    """Points inside ``face`` with the outward normal there."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.BRepTools import BRepTools
    from OCP.TopAbs import TopAbs_IN, TopAbs_REVERSED

    u0, u1, v0, v1 = BRepTools.UVBounds_s(face)
    surface = BRepAdaptor_Surface(face)
    out = []
    for i in range(_GRID):
        for j in range(_GRID):
            u = u0 + (u1 - u0) * (i + 0.5) / _GRID
            v = v0 + (v1 - v0) * (j + 0.5) / _GRID
            props = BRepLProp_SLProps(surface, u, v, 1, 1e-7)
            if not props.IsNormalDefined():
                continue
            point = props.Value()
            if BRepClass_FaceClassifier(face, point, 1e-6).State() != TopAbs_IN:
                continue
            normal = props.Normal()
            if face.Orientation() == TopAbs_REVERSED:
                normal.Reverse()
            out.append((point, normal))
    return out


def undercut_faces(shape: Any, pull: tuple[float, float, float]) -> list[FaceSight]:
    """Every face of ``shape`` with its group for the pull direction."""
    from OCP.gp import gp_Dir, gp_Lin, gp_Vec
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector

    from fdcad.core.naming.names import faces_of

    up = gp_Dir(*pull)
    shooter = IntCurvesFace_ShapeIntersector()
    shooter.Load(shape, 1e-7)
    out: list[FaceSight] = []
    for face in faces_of(shape):
        seen = hidden = walls = 0
        up_ok = down_ok = 0
        points = _samples(face)
        for point, normal in points:
            facing = normal.Dot(up)
            if abs(facing) < _WALL:
                walls += 1
                continue
            way = up if facing > 0 else up.Reversed()
            start = point.Translated(gp_Vec(way).Multiplied(1e-4))
            shooter.Perform(gp_Lin(start, way), 0.0, 1e100)
            clear = not (shooter.IsDone() and shooter.NbPnt() > 0)
            if clear:
                seen += 1
                if facing > 0:
                    up_ok += 1
                else:
                    down_ok += 1
            else:
                hidden += 1
        tried = seen + hidden
        if not points or (walls and not tried):
            group = "side"
        elif seen and hidden:
            group = "straddle"
        elif not seen:
            group = "undercut"
        elif up_ok and not down_ok:
            group = "above"
        elif down_ok and not up_ok:
            group = "below"
        else:
            group = "straddle"
        out.append(FaceSight(face, group))
    return out
