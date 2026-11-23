"""Select Similar and selection conversion (TR303, D943).

Select Similar finds the faces of a part that are like a picked face, by rules that
combine: every chosen rule must match (all) or one of them (any), and an except rule
takes faces out. Conversion turns picks into the edges, faces or whole bodies they
belong to. Kernel code, no Qt; the UI runs it in a background job (CLAUDE.md rule 2).
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

#: The rules, in the order the dialog lists them.
RULES = ("kind_size", "parallel", "area")
#: Two faces have the same area when they differ by at most this part of it.
AREA_TOLERANCE = 0.05
_SIZE_TOLERANCE = 1e-4  # relative, for radii
_ANGLE_TOLERANCE = 1e-6  # for parallel normals and axes


@dataclass(frozen=True)
class FaceInfo:
    """What the rules compare: the surface kind and sizes, its direction, its area."""

    kind: str  # "plane", "cylinder", "cone", "sphere", "torus" or "other"
    sizes: tuple[float, ...]  # radii (cone: half angle in radians)
    direction: tuple[float, float, float] | None  # plane normal or axis, unit length
    area: float


def describe(face: Any) -> FaceInfo:
    """The rule data of one face."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepGProp import BRepGProp
    from OCP.GeomAbs import (
        GeomAbs_Cone,
        GeomAbs_Cylinder,
        GeomAbs_Plane,
        GeomAbs_Sphere,
        GeomAbs_Torus,
    )
    from OCP.GProp import GProp_GProps
    from OCP.TopoDS import TopoDS

    face = TopoDS.Face(face)
    surface = BRepAdaptor_Surface(face)
    kind = surface.GetType()
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    area = props.Mass()

    def unit(d: Any) -> tuple[float, float, float]:
        return (d.X(), d.Y(), d.Z())

    if kind == GeomAbs_Plane:
        return FaceInfo("plane", (), unit(surface.Plane().Axis().Direction()), area)
    if kind == GeomAbs_Cylinder:
        c = surface.Cylinder()
        return FaceInfo("cylinder", (c.Radius(),), unit(c.Axis().Direction()), area)
    if kind == GeomAbs_Cone:
        k = surface.Cone()
        return FaceInfo("cone", (k.SemiAngle(),), unit(k.Axis().Direction()), area)
    if kind == GeomAbs_Sphere:
        return FaceInfo("sphere", (surface.Sphere().Radius(),), None, area)
    if kind == GeomAbs_Torus:
        t = surface.Torus()
        sizes = (t.MajorRadius(), t.MinorRadius())
        return FaceInfo("torus", sizes, unit(t.Axis().Direction()), area)
    return FaceInfo("other", (), None, area)


def matches(rule: str, ref: FaceInfo, other: FaceInfo) -> bool:
    """True when ``other`` is like ``ref`` by ``rule``."""
    if rule == "kind_size":
        if ref.kind != other.kind or ref.kind == "other" or len(ref.sizes) != len(other.sizes):
            return False
        return all(
            abs(a - b) <= _SIZE_TOLERANCE * max(abs(a), 1.0)
            for a, b in zip(ref.sizes, other.sizes, strict=True)
        )
    if rule == "parallel":
        if ref.direction is None or other.direction is None:
            return False
        dot = sum(a * b for a, b in zip(ref.direction, other.direction, strict=True))
        return abs(abs(dot) - 1.0) <= _ANGLE_TOLERANCE
    if rule == "area":
        return math.isclose(other.area, ref.area, rel_tol=AREA_TOLERANCE)
    raise ValueError(f"Unknown rule '{rule}'.")


def similar_faces(
    part: Any,
    face: Any,
    must: Iterable[str],
    match_any: bool = False,
    except_rules: Iterable[str] = (),
) -> list[Any]:
    """Every face of ``part`` like ``face``: it matches all (or with ``match_any``, one)
    of the ``must`` rules and none of the ``except_rules``. The picked face is always
    in the result."""
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp

    from fdcad.core.occ import ShapeMap

    wanted, unwanted = list(must), list(except_rules)
    if not wanted:
        raise ValueError("Choose at least one rule that must match.")
    ref = describe(face)
    found = ShapeMap()
    TopExp.MapShapes_s(part, TopAbs_FACE, found)
    out: list[Any] = []
    for i in range(1, found.Extent() + 1):
        other = found.FindKey(i)
        if other.IsSame(face):
            out.append(other)
            continue
        info = describe(other)
        hits = [matches(r, ref, info) for r in wanted]
        if not (any(hits) if match_any else all(hits)):
            continue
        if any(matches(r, ref, info) for r in unwanted):
            continue
        out.append(other)
    return out


def convert(part: Any, picks: Iterable[Any], to: str) -> list[Any]:
    """Turn picks into ``to``: "edges" (picked edges, and the edges of picked faces),
    "faces" (picked faces, and the faces next to picked edges and vertices) or
    "bodies" (every face of each body a pick belongs to)."""
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SOLID, TopAbs_VERTEX
    from OCP.TopExp import TopExp, TopExp_Explorer

    from fdcad.core.occ import ShapeListMap, ShapeMap, shape_list

    def collect(shape: Any, kind: Any, out: list[Any], seen: Any) -> None:
        exp = TopExp_Explorer(shape, kind)
        while exp.More():
            item = exp.Current()
            if not seen.Contains(item):
                seen.Add(item)
                out.append(item)
            exp.Next()

    picks = list(picks)
    out: list[Any] = []
    seen = ShapeMap()
    if to == "edges":
        for p in picks:
            if p.ShapeType() == TopAbs_EDGE:
                if not seen.Contains(p):
                    seen.Add(p)
                    out.append(p)
            elif p.ShapeType() == TopAbs_FACE:
                collect(p, TopAbs_EDGE, out, seen)
        return out
    if to == "faces":
        ancestors = ShapeListMap()
        TopExp.MapShapesAndAncestors_s(part, TopAbs_EDGE, TopAbs_FACE, ancestors)
        vertex_faces = ShapeListMap()
        TopExp.MapShapesAndAncestors_s(part, TopAbs_VERTEX, TopAbs_FACE, vertex_faces)
        for p in picks:
            kind = p.ShapeType()
            if kind == TopAbs_FACE:
                if not seen.Contains(p):
                    seen.Add(p)
                    out.append(p)
                continue
            table = ancestors if kind == TopAbs_EDGE else vertex_faces
            if kind in (TopAbs_EDGE, TopAbs_VERTEX) and table.Contains(p):
                for f in shape_list(table.FindFromKey(p)):
                    if not seen.Contains(f):
                        seen.Add(f)
                        out.append(f)
        return out
    if to == "bodies":
        solids: list[Any] = []
        exp = TopExp_Explorer(part, TopAbs_SOLID)
        while exp.More():
            solids.append(exp.Current())
            exp.Next()
        for solid in solids:
            inside = ShapeMap()
            TopExp.MapShapes_s(solid, inside)
            if any(inside.Contains(p) for p in picks):
                collect(solid, TopAbs_FACE, out, seen)
        return out
    raise ValueError(f"Unknown conversion '{to}'.")
