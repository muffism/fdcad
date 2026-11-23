"""Cosmetic thread (PHASE4_SPEC P4.2, DECISIONS D314).

A thread shown on a round face as a pattern and kept as metadata (size, pitch,
length). The part's geometry does not change.

Params (FDEF_SPEC 5.3.22):

- ``standard``, ``size``: what the values were filled from (display only).
- ``diameter``: length, the major diameter. ``pitch``: length.
- ``end_condition``: ``blind`` (with ``length``) or ``full`` (the whole face).
- ``reverse``: optional boolean, run the other way along the axis.

Refs: ``edge``, one round edge where the thread starts (on a hole or a shaft).
Face roles: none (no geometry is made).

Tapped holes with ``cosmetic_thread`` make the same marks (``hole.py``).
"""

from __future__ import annotations

from dataclasses import replace

from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Cylinder
from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt
from OCP.TopoDS import TopoDS_Edge, TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureState,
    FeatureType,
    Issue,
    ParamSpec,
    ThreadMark,
    Vec3,
    register,
)
from fdcad.core.features.modify import edge_faces, require_body, resolve_edges
from fdcad.core.features.solids import compound, extent_along
from fdcad.core.units import Kind

#: Most rings drawn for one thread; longer threads draw rings further apart.
MAX_RINGS = 40


def _vec(p: gp_Pnt) -> Vec3:
    return (p.X(), p.Y(), p.Z())


def round_edge(edge: TopoDS_Edge) -> tuple[Vec3, Vec3, float] | None:
    """Centre, axis and radius of a circular edge, or None."""
    curve = BRepAdaptor_Curve(edge)
    if curve.GetType() != GeomAbs_Circle:
        return None
    circle = curve.Circle()
    axis = circle.Axis()
    d = axis.Direction()
    return _vec(circle.Location()), (d.X(), d.Y(), d.Z()), circle.Radius()


def cylinder_at(
    body: TopoDS_Shape, edge: TopoDS_Edge
) -> tuple[TopoDS_Face, Vec3, Vec3, float, bool, float] | None:
    """The cylindrical face at a round edge: (face, start, direction into the face,
    radius, internal, face length). None when no cylinder meets the edge."""
    found = round_edge(edge)
    if found is None:
        return None
    centre, axis, radius = found
    for face in edge_faces(body, edge):
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Cylinder:
            continue
        if abs(surface.Cylinder().Radius() - radius) > 1e-6:
            continue
        span = extent_along(face, axis)
        if span is None:
            continue
        here = sum(c * a for c, a in zip(centre, axis, strict=True))
        lo, hi = span
        direction = axis if abs(hi - here) > abs(lo - here) else (-axis[0], -axis[1], -axis[2])
        length = max(abs(hi - here), abs(lo - here))
        internal = _is_internal(face, centre, axis)
        return face, centre, direction, radius, internal, length
    return None


def _is_internal(face: TopoDS_Face, centre: Vec3, axis: Vec3) -> bool:
    """True when the part's material is outside the cylinder (a hole)."""
    from fdcad.core.features.hole import outward_normal

    surface = BRepAdaptor_Surface(face)
    u = (surface.FirstUParameter() + surface.LastUParameter()) / 2
    v = (surface.FirstVParameter() + surface.LastVParameter()) / 2
    normal = outward_normal(face, u, v)
    p = surface.Value(u, v)
    rel = (p.X() - centre[0], p.Y() - centre[1], p.Z() - centre[2])
    along = sum(r * a for r, a in zip(rel, axis, strict=True))
    radial = tuple(r - a * along for r, a in zip(rel, axis, strict=True))
    if normal is None:
        return False
    return bool(sum(n * r for n, r in zip(normal, radial, strict=True)) < 0)


def thread_pattern(marks: list[ThreadMark]) -> TopoDS_Shape | None:
    """Rings along each thread, drawn just off its face so they show (display only)."""
    edges: list[TopoDS_Shape] = []
    for mark in marks:
        if mark.length <= 0 or mark.surface <= 0:
            continue
        step = max(mark.pitch, mark.length / MAX_RINGS) if mark.pitch > 0 else mark.length / 8
        count = max(1, int(mark.length / step + 1e-9))
        offset = -0.01 if mark.internal else 0.01
        radius = mark.surface / 2 * (1 + offset)
        d = gp_Dir(*mark.direction)
        for k in range(count + 1):
            t = min(k * step, mark.length)
            c = gp_Pnt(*(o + dd * t for o, dd in zip(mark.origin, mark.direction, strict=True)))
            edges.append(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(c, d), radius)).Edge())
    return compound(edges) if edges else None


def thread_label(size: str, diameter: float, pitch: float) -> str:
    """Text such as "M5x0.8, 10 mm" for the metadata."""
    name = size or f"D{diameter:.4g}"
    return f"{name}x{pitch:.4g}"


@register
class CosmeticThread(FeatureType):
    """Marks a thread on a round face as metadata, without changing the part."""

    type_name = "cosmetic_thread"
    makes_solid = False
    params = (
        ParamSpec("diameter", kind=Kind.LENGTH),
        ParamSpec("pitch", kind=Kind.LENGTH),
        ParamSpec("end_condition", choices=("blind", "full"), default="blind"),
    )

    def kind_of(self, name: str) -> Kind | None:
        """``length`` is a length too."""
        if name == "length":
            return Kind.LENGTH
        return super().kind_of(name)

    def mark(self, feature: Feature, ctx: BuildContext) -> ThreadMark:
        """The thread mark from the picked edge."""
        body = require_body(feature, ctx)
        picked, _issues = resolve_edges(feature, ctx, "edge")
        found = cylinder_at(body.shape, picked[0][1])
        if found is None:
            raise FeatureError(
                f"{feature.name}: the picked edge is not the round end of a hole or shaft. "
                "Pick a round edge of a cylindrical face."
            )
        _face, start, direction, radius, internal, face_length = found
        if feature.params.get("reverse") is True:
            direction = (-direction[0], -direction[1], -direction[2])
        diameter = self.number(feature, "diameter")
        pitch = self.number(feature, "pitch")
        if diameter <= 0 or pitch <= 0:
            raise FeatureError(
                f"{feature.name}: the diameter and pitch must be greater than zero. "
                "Enter larger values."
            )
        if feature.params.get("end_condition", "blind") == "full":
            length = face_length
        else:
            length = self.number(feature, "length")
            if length <= 0:
                raise FeatureError(
                    f"{feature.name}: the thread length must be greater than zero. "
                    "Enter a longer length."
                )
        size = str(feature.params.get("size", ""))
        return ThreadMark(
            start,
            direction,
            diameter,
            pitch,
            length,
            2 * radius,
            internal,
            thread_label(size, diameter, pitch),
        )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """The part is unchanged; the result carries the thread mark.

        A thread longer than its face is drawn and exported only as long as the face,
        with a warning (D2647): it was stored, drawn and written to STEP as typed, so
        it ran on past the end of the shaft or hole. The typed length is kept.
        """
        mark = self.mark(feature, ctx)
        picked, issues = resolve_edges(feature, ctx, "edge")
        found = cylinder_at(require_body(feature, ctx).shape, picked[0][1])
        face_length = found[5] if found is not None else mark.length
        if mark.length > face_length + 1e-6:
            issues = [
                *issues,
                Issue(
                    FeatureState.WARNING,
                    f"{feature.name}: the thread is {mark.length:g} mm long but its face is "
                    f"only {face_length:.4g} mm long, so it is shown {face_length:.4g} mm "
                    "long. Enter a shorter length, or choose Full Length.",
                    code="thread_too_long",
                ),
            ]
            mark = replace(mark, length=face_length)
        return FeatureResult(body=ctx.body, issues=issues, threads=[mark])


def step_notes(marks: list[ThreadMark]) -> list[str]:
    """One plain text line per thread for the STEP file description (D314)."""
    out = []
    for m in marks:
        o = ", ".join(f"{v:.6g}" for v in m.origin)
        d = ", ".join(f"{v:.6g}" for v in m.direction)
        kind = "internal" if m.internal else "external"
        out.append(
            f"Cosmetic thread {m.label} {kind}, major diameter {m.diameter:.6g} mm, "
            f"pitch {m.pitch:.6g} mm, length {m.length:.6g} mm, start ({o}), axis ({d})"
        )
    return out


def hole_marks(
    origin: Vec3, direction: Vec3, wall: float, major: float, pitch: float, length: float, size: str
) -> ThreadMark:
    """The mark of one tapped hole."""
    return ThreadMark(
        origin, direction, major, pitch, length, wall, True, thread_label(size, major, pitch)
    )


def basic_major(minor: float, pitch: float) -> float:
    """Major diameter from a tap drill diameter when none is stored (ISO 68 basic profile)."""
    return minor + 1.0825 * pitch
