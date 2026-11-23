"""Fill Pattern: fill a flat or cylinder face with copies (TR57, D792; TR398, D1903).

Copies a seed (``features``, ``faces`` or ``bodies``, as the other patterns) or
cuts a built-in shape at points laid out over one flat face, keeping only the
copies that fit: grilles, vents and weight reduction holes.

Params:

- ``layout``: ``grid``, ``staggered`` or ``rings``.
- ``spacing`` (length): between copies; ``row_spacing`` (optional length): between
  grid rows, or between rings (else ``spacing``).
- ``stagger_angle`` (optional angle, default 60 degrees): a staggered grid's rows
  lean by it, so 60 degrees gives an even triangular layout.
- ``ring_shape`` (optional): ``circle``, ``square`` or ``polygon`` rings; ``sides``
  (number) for polygon rings and shapes.
- ``margin`` (optional length): how far every copy stays from the face's edges.
  A negative margin lets copies run past the edge by that much.
- ``fit`` (optional): ``shape`` (default, the whole copy with the margin must lie
  on the material) or ``centre`` (only the centre, the margin away from the edge).
- ``shape`` (optional): ``none`` (copy the seed), ``circle``, ``square``,
  ``diamond`` or ``polygon`` with ``size`` (length, across), ``shape_angle``
  (optional angle) and ``depth`` (optional length; else through the part).
- ``surface_spacing`` (TR398, D1903): on a cylinder face, ``mapped`` (default: the
  spacing round the face is measured along the surface) or ``projected`` (measured
  in the plane touching the face at the start, as seen from straight on).
- ``size_end`` (TR324, D1518): optional length; the shapes grow or shrink from
  ``size`` at ``refs.gradient_from`` (a point or vertex, or an edge; else the start
  point) to ``size_end`` at the farthest copy. Each copy must fit with its own size.

Refs: ``face`` (the flat face to fill) or ``sketch`` (a sketch whose closed region
is filled, with optional picked ``regions``: the one holding ``point``, else the
largest; cuts go against the sketch plane's normal), optional ``direction`` (a straight edge:
the grid's first direction, else the face plane's own) and ``point`` (where the
layout starts, else the face's centre), and the seed. Key ``skip``: ``[k, 1]``
pairs, ``k`` counting the kept copies from 1 in layout order.

The number of copies is in the result's ``extras["count"]``. Face roles of the
built-in shape: ``cut/<k>/face#j``.
"""

from __future__ import annotations

import itertools
import math
import threading
from typing import Any

import numpy as np

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    Vec3,
    register,
)
from fdcad.core.features.linear_pattern import COMMON_PARAMS, MAX_INSTANCES
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind

#: The count the last preview build kept, per thread, so preview_info need not build twice.
_LAST_COUNT = threading.local()

LAYOUTS = ("grid", "staggered", "rings")
SHAPES = ("none", "circle", "square", "diamond", "polygon")
#: What must lie on the material for a copy to count: its whole shape or its centre.
FITS = ("shape", "centre")
RING_SHAPES = ("circle", "square", "polygon")


def _value(feature: Feature, name: str, default: float) -> float:
    v = feature.params.get(name)
    return v.value if isinstance(v, Param) else default


def layout_points(
    layout: str,
    spacing: float,
    spacing2: float,
    stagger: float,
    ring_shape: str,
    sides: int,
    reach: float,
) -> list[tuple[float, float]]:
    """Layout points (u, v) about the start, out to ``reach`` in every direction, in a
    stable order. Grids go row by row; rings go out from the middle."""
    if spacing <= 0 or spacing2 <= 0:
        raise ValueError("spacing must be more than 0")
    out: list[tuple[float, float]] = []
    if layout in ("grid", "staggered"):
        if layout == "grid":
            du, dv, row = (spacing, 0.0), (0.0, spacing2), 0.0
        else:
            du = (spacing, 0.0)
            dv = (spacing * math.cos(stagger), spacing * math.sin(stagger))
            row = 1.0
        rows = int(reach / max(abs(dv[1]), 1e-9)) + 2
        cols = int(reach / spacing) + 2 + (rows if row else 0)
        for j in range(-rows, rows + 1):
            for i in range(-cols, cols + 1):
                u = i * du[0] + j * dv[0]
                v = i * du[1] + j * dv[1]
                if abs(u) <= reach + spacing and abs(v) <= reach + spacing:
                    out.append((u, v))
        if len(out) > 4 * MAX_INSTANCES:
            raise ValueError("too many copies")
        return out
    out.append((0.0, 0.0))
    for k in range(1, int(reach / spacing2) + 2):
        r = k * spacing2
        if ring_shape == "circle":
            n = max(1, round(2 * math.pi * r / spacing))
            out += [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n))
                    for i in range(n)]  # fmt: skip
            continue
        corners = 4 if ring_shape == "square" else max(3, sides)
        # A square ring has its corners at (+-r, +-r); a polygon ring at radius r.
        radius = r * math.sqrt(2) if ring_shape == "square" else r
        verts = [
            (radius * math.cos(2 * math.pi * c / corners + math.pi / corners),
             radius * math.sin(2 * math.pi * c / corners + math.pi / corners))
            for c in range(corners)
        ]  # fmt: skip
        for a, b in zip(verts, verts[1:] + verts[:1], strict=True):
            n = max(1, round(math.dist(a, b) / spacing))
            out += [(a[0] + (b[0] - a[0]) * t / n, a[1] + (b[1] - a[1]) * t / n) for t in range(n)]
        if len(out) > 4 * MAX_INSTANCES:
            raise ValueError("too many copies")
    return out


def shape_outline(shape: str, size: float, angle: float, sides: int) -> list[tuple[float, float]]:
    """The built-in shape's corners about its centre (a circle gives no corners)."""
    half = size / 2
    if shape == "square":
        pts = [(-half, -half), (half, -half), (half, half), (-half, half)]
    elif shape == "diamond":
        pts = [(half, 0.0), (0.0, half), (-half, 0.0), (0.0, -half)]
    elif shape == "polygon":
        n = max(3, sides)
        pts = [(half * math.cos(2 * math.pi * k / n), half * math.sin(2 * math.pi * k / n))
               for k in range(n)]  # fmt: skip
    else:
        return []
    c, s = math.cos(angle), math.sin(angle)
    return [(x * c - y * s, x * s + y * c) for x, y in pts]


def gradient_sizes(
    feature: Feature,
    ctx: BuildContext,
    region: _Region,
    start: tuple[float, float],
    centres: list[tuple[float, float]],
    near: float,
    far: float,
) -> list[float]:
    """Each copy's size for a size gradient (TR324, D1518): ``near`` at the gradient's
    origin, ``far`` at the copy farthest from it, in proportion between. The origin is
    ``refs.gradient_from`` (a vertex, sketch point or point, or an edge: the distance to
    it), else the layout's start point."""
    ref = feature.refs.get("gradient_from")
    if isinstance(ref, list):
        ref = ref[0] if ref else None
    pts = np.array(centres, dtype=float)
    if isinstance(ref, dict) and ref.get("kind") == "edge":
        from OCP.BRepAdaptor import BRepAdaptor_Curve
        from OCP.GCPnts import GCPnts_QuasiUniformDeflection

        from fdcad.core.features.lookup import resolve_edge

        assert ctx.body is not None
        edge, _issues = resolve_edge(ctx.body, ref, feature.name)
        sampler = GCPnts_QuasiUniformDeflection(BRepAdaptor_Curve(edge), 0.01)
        line = np.array(
            [region.flat(sampler.Value(i)) for i in range(1, sampler.NbPoints() + 1)], dtype=float
        )
        segments = np.hstack([line[:-1], line[1:]]) if len(line) > 1 else np.hstack([line, line])
        dist = _Region.distances(segments, pts)
    else:
        origin = start
        if isinstance(ref, dict):
            from OCP.gp import gp_Pnt

            from fdcad.core.features.geometry_refs import resolve_placement

            place = resolve_placement(ctx, ref, feature.name, "point")
            origin = region.flat(gp_Pnt(*place.point))
        dist = np.hypot(pts[:, 0] - origin[0], pts[:, 1] - origin[1])
    top = float(np.max(dist)) if len(dist) else 0.0
    if top <= 1e-9:
        return [near] * len(centres)
    return [float(near + (far - near) * d / top) for d in dist]


class _Region:
    """The face to fill, flattened into its own plane for fast fit tests."""

    def __init__(self, face: Any, origin: Vec3, u: Vec3, v: Vec3) -> None:
        from OCP.BRepAdaptor import BRepAdaptor_Curve
        from OCP.GCPnts import GCPnts_QuasiUniformDeflection
        from OCP.TopAbs import TopAbs_EDGE
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopoDS import TopoDS

        self.face, self.origin, self.u, self.v = face, origin, u, v
        segments: list[tuple[float, float, float, float]] = []
        ex = TopExp_Explorer(face, TopAbs_EDGE)
        while ex.More():
            curve = BRepAdaptor_Curve(TopoDS.Edge(ex.Current()))
            ex.Next()
            sampler = GCPnts_QuasiUniformDeflection(curve, 0.01)
            pts = [self.flat(sampler.Value(i)) for i in range(1, sampler.NbPoints() + 1)]
            for a, b in itertools.pairwise(pts):
                segments.append((a[0], a[1], b[0], b[1]))
        self.segments = np.array(segments, dtype=float).reshape(-1, 4)

    def flat(self, p: Any) -> tuple[float, float]:
        d = (p.X() - self.origin[0], p.Y() - self.origin[1], p.Z() - self.origin[2])
        return (sum(a * b for a, b in zip(d, self.u, strict=True)),
                sum(a * b for a, b in zip(d, self.v, strict=True)))  # fmt: skip

    def point(self, u: float, v: float) -> Vec3:
        o, a, b = self.origin, self.u, self.v
        return (o[0] + a[0] * u + b[0] * v, o[1] + a[1] * u + b[1] * v, o[2] + a[2] * u + b[2] * v)

    def reach(self, start: tuple[float, float]) -> float:
        if not len(self.segments):
            return 0.0
        ends = self.segments.reshape(-1, 2)
        return float(np.max(np.hypot(ends[:, 0] - start[0], ends[:, 1] - start[1])))

    def clearance(self, points: np.ndarray) -> np.ndarray:
        """Each point's distance to the face's edges (whole arrays, PLAN 5A.2)."""
        return self.distances(self.segments, points)

    @staticmethod
    def distances(segments: np.ndarray, points: np.ndarray) -> np.ndarray:
        """Each point's distance to the nearest of ``segments`` (rows ax, ay, bx, by)."""
        if not len(segments) or not len(points):
            return np.zeros(len(points))
        ax, ay, bx, by = (segments[:, i][None, :] for i in range(4))
        px, py = points[:, 0][:, None], points[:, 1][:, None]
        ex, ey = bx - ax, by - ay
        size = ex * ex + ey * ey
        t = np.clip(((px - ax) * ex + (py - ay) * ey) / np.where(size == 0, 1, size), 0, 1)
        d = np.hypot(px - (ax + ex * t), py - (ay + ey * t))
        return np.min(d, axis=1)

    def inside(self, u: float, v: float) -> bool:
        from OCP.BRepClass import BRepClass_FaceClassifier
        from OCP.gp import gp_Pnt
        from OCP.TopAbs import TopAbs_IN

        state = BRepClass_FaceClassifier(self.face, gp_Pnt(*self.point(u, v)), 1e-6).State()
        return bool(state == TopAbs_IN)

    def normal(self) -> Vec3:
        """The face normal at the layout origin; cuts go against it."""
        u, v = self.u, self.v
        return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])

    def motion(self, to: tuple[float, float], start: tuple[float, float]) -> Any:
        """The move that takes a copy at layout point ``start`` to ``to``."""
        from fdcad.core.features.direct import translation

        p, q = self.point(*to), self.point(*start)
        return translation((p[0] - q[0], p[1] - q[1], p[2] - q[2]))

    def default_depth(self, size: float) -> float:
        """How deep a shape cuts with no depth typed: through the part."""
        return 2.0 * size + 1.0

    def lift(self, usual: float) -> float:
        """How far above the face each shape starts."""
        return usual


#: How a layout is laid on a round face (TR398 item 1, D1903).
SURFACE_SPACINGS = ("mapped", "projected")


class _RoundRegion(_Region):
    """A cylinder face to fill (TR398 item 1, D1903), laid out in (u, v): ``v`` along
    the axis and ``u`` round it. "mapped" measures ``u`` along the surface (the face
    unrolled), "projected" measures it in the plane touching the face at the start, so
    the spacing is as seen from straight on. Copies turn about the axis and slide along
    it, so they stay square to the surface."""

    def __init__(self, face: Any, start: Vec3, mode: str) -> None:
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.TopAbs import TopAbs_REVERSED

        cyl = BRepAdaptor_Surface(face).Cylinder()
        ax = cyl.Axis()
        loc, z = ax.Location(), ax.Direction()
        self.radius = cyl.Radius()
        self.mode = mode
        self.axis_dir = (z.X(), z.Y(), z.Z())
        d = (start[0] - loc.X(), start[1] - loc.Y(), start[2] - loc.Z())
        along = sum(a * b for a, b in zip(d, self.axis_dir, strict=True))
        base = (loc.X(), loc.Y(), loc.Z())
        self.axis_point = tuple(
            c + a * along for c, a in zip(base, self.axis_dir, strict=True)
        )  # the axis point level with the start, so the start is (0, 0)
        out = tuple(s - c for s, c in zip(start, self.axis_point, strict=True))
        size = math.sqrt(sum(c * c for c in out))
        if size < 1e-9:
            raise ValueError("start on the axis")
        self.x0 = tuple(c / size for c in out)
        a, b = self.axis_dir, self.x0
        self.y0 = (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
        self.outward = face.Orientation() != TopAbs_REVERSED
        super().__init__(face, self.axis_point, self.y0, self.axis_dir)
        if mode != "projected" and len(self.segments):
            # A seam at the back lands at u = +pi r or -pi r by rounding: use both sides.
            far = math.pi * self.radius - 1e-6
            seg = self.segments
            seam = seg[(np.abs(seg[:, 0]) >= far) & (np.abs(seg[:, 2]) >= far)]
            flipped = seam * np.array([-1.0, 1.0, -1.0, 1.0])
            self.segments = np.vstack([seg, flipped])

    def _theta(self, u: float) -> float | None:
        if self.mode == "projected":
            return math.asin(u / self.radius) if abs(u) < self.radius else None
        theta = u / self.radius
        return theta if abs(theta) < math.pi - 1e-9 else None

    def flat(self, p: Any) -> tuple[float, float]:
        d = [p.X() - self.origin[0], p.Y() - self.origin[1], p.Z() - self.origin[2]]
        x = sum(a * b for a, b in zip(d, self.x0, strict=True))
        y = sum(a * b for a, b in zip(d, self.y0, strict=True))
        z = sum(a * b for a, b in zip(d, self.axis_dir, strict=True))
        theta = math.atan2(y, x)
        if self.mode != "projected":
            return self.radius * theta, z
        # Seen from straight on, the back half lies behind the outline at u = +-radius.
        u = self.radius * (math.sin(theta) if abs(theta) < math.pi / 2 else math.copysign(1, theta))
        return u, z

    def point(self, u: float, v: float) -> Vec3:
        theta = self._theta(u)
        t = 0.0 if theta is None else theta
        c, s = math.cos(t) * self.radius, math.sin(t) * self.radius
        o, x, y, z = self.origin, self.x0, self.y0, self.axis_dir
        return (o[0] + x[0] * c + y[0] * s + z[0] * v,
                o[1] + x[1] * c + y[1] * s + z[1] * v,
                o[2] + x[2] * c + y[2] * s + z[2] * v)  # fmt: skip

    def inside(self, u: float, v: float) -> bool:
        if self._theta(u) is None:
            return False  # past the far side (mapped) or the edge as seen (projected)
        return super().inside(u, v)

    def normal(self) -> Vec3:
        x = self.x0
        return x if self.outward else (-x[0], -x[1], -x[2])

    def motion(self, to: tuple[float, float], start: tuple[float, float]) -> Any:
        from fdcad.core.features.direct import rotation, translation

        turn = (self._theta(to[0]) or 0.0) - (self._theta(start[0]) or 0.0)
        z = self.axis_dir
        slide = translation((z[0] * (to[1] - start[1]),
                             z[1] * (to[1] - start[1]),
                             z[2] * (to[1] - start[1])))  # fmt: skip
        return slide.Multiplied(rotation(self.axis_point, z, turn))

    def lift(self, usual: float) -> float:
        # In a hole, start on the axis plane: the flat shape then clears the curved wall
        # at its edges and never reaches the wall on the far side.
        return usual if self.outward else self.radius

    def default_depth(self, size: float) -> float:
        # An outside face cuts in to the axis, so a tube is cut through one wall only.
        return self.radius if self.outward else 2.0 * size + 1.0


def _face_middle(face: Any) -> Vec3:
    """The point in the middle of ``face``'s parameter range (a round face's centroid
    lies off the face, on its axis for a whole cylinder)."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepTools import BRepTools
    from OCP.TopoDS import TopoDS

    f = TopoDS.Face(face)
    u0, u1, v0, v1 = BRepTools.UVBounds_s(f)
    p = BRepAdaptor_Surface(f).Value((u0 + u1) / 2, (v0 + v1) / 2)
    return (p.X(), p.Y(), p.Z())


@register
class FillPattern(FeatureType):
    """Fills a flat face with copies of a seed or a cut shape."""

    type_name = "fill_pattern"
    makes_solid = True
    params = (
        *COMMON_PARAMS,
        ParamSpec("layout", choices=LAYOUTS, default="grid"),
        ParamSpec("spacing", kind=Kind.LENGTH),
        ParamSpec("row_spacing", kind=Kind.LENGTH, optional=True),
        ParamSpec("stagger_angle", kind=Kind.ANGLE, optional=True),
        ParamSpec("ring_shape", choices=RING_SHAPES, optional=True),
        ParamSpec("sides", kind=Kind.NUMBER, optional=True),
        ParamSpec("margin", kind=Kind.LENGTH, optional=True),
        ParamSpec("fit", choices=FITS, optional=True),
        ParamSpec("shape", choices=SHAPES, optional=True),
        ParamSpec("size", kind=Kind.LENGTH, optional=True),
        ParamSpec("size_end", kind=Kind.LENGTH, optional=True),  # TR324 (D1518)
        ParamSpec("gradient", default=False, optional=True),
        ParamSpec("shape_angle", kind=Kind.ANGLE, optional=True),
        ParamSpec("depth", kind=Kind.LENGTH, optional=True),
        ParamSpec("surface_spacing", choices=SURFACE_SPACINGS, optional=True),  # TR398
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Lay the copies out, keep those that fit, and copy or cut them."""
        from fdcad.core.features.solids import check_result

        body, issues, count = self._build(feature, ctx)
        issues += check_result(feature.id, feature.name, ctx.body, body, None)
        if feature.refs.get("bodies"):
            issues = [i for i in issues if i.code != "separate_body"]
        return FeatureResult(body=body, issues=issues, extras={"count": count})

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The filled part, for the live preview."""
        body, _issues, count = self._build(feature, ctx)
        _LAST_COUNT.value = (id(feature), count)
        return body

    def preview_info(self, feature: Feature, ctx: BuildContext) -> dict[str, float]:
        """The number of copies kept, for the panel (TR57 item 3)."""
        last = getattr(_LAST_COUNT, "value", None)
        if last is not None and last[0] == id(feature):
            return {"count": float(last[1])}
        return {"count": float(self._build(feature, ctx)[2])}

    def _frame(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[_Region, tuple[float, float], list[Issue]]:
        from fdcad.core.features.geometry_refs import resolve_placement
        from fdcad.core.features.modify import require_body, resolve_faces
        from fdcad.core.features.sketch import face_plane
        from fdcad.core.naming.names import centroid

        name = feature.name
        require_body(feature, ctx)
        if isinstance(feature.refs.get("face"), dict):  # a single pick box stores one ref
            feature = Feature(
                feature.id,
                feature.type,
                feature.name,
                params=feature.params,
                refs={**feature.refs, "face": [feature.refs["face"]]},
                data=feature.data,
            )
        if feature.refs.get("sketch"):
            face, issues = self._sketch_region(feature, ctx)
        else:
            picked, issues = resolve_faces(feature, ctx, "face")
            face = picked[0][1]
        plane = face_plane(face)
        if plane is None:
            return self._round_frame(feature, ctx, face, issues)
        n = plane.normal
        u = plane.x_dir
        if feature.refs.get("direction"):
            place = resolve_placement(ctx, feature.refs["direction"], name, "direction")
            issues += place.issues
            d = place.direction
            along = sum(a * b for a, b in zip(d, n, strict=True))
            d = (d[0] - n[0] * along, d[1] - n[1] * along, d[2] - n[2] * along)
            size = math.sqrt(sum(c * c for c in d))
            if size < 1e-6:
                raise FeatureError(
                    f"{name}: the direction runs square to the face. Pick an edge along the face."
                )
            u = (d[0] / size, d[1] / size, d[2] / size)
        v = (n[1] * u[2] - n[2] * u[1], n[2] * u[0] - n[0] * u[2], n[0] * u[1] - n[1] * u[0])
        region = _Region(face, plane.origin, u, v)
        if feature.refs.get("point") is not None:
            place = resolve_placement(ctx, feature.refs["point"], name, "point")
            issues += place.issues
            start = place.point
        else:
            start = centroid(face)
        from OCP.gp import gp_Pnt

        return region, region.flat(gp_Pnt(*start)), issues

    def _round_frame(
        self, feature: Feature, ctx: BuildContext, face: Any, issues: list[Issue]
    ) -> tuple[_Region, tuple[float, float], list[Issue]]:
        """A cylinder face laid out round and along its axis (TR398 item 1, D1903)."""
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.GeomAbs import GeomAbs_Cylinder

        from fdcad.core.features.geometry_refs import resolve_placement

        name = feature.name
        if BRepAdaptor_Surface(face).GetType() != GeomAbs_Cylinder:
            raise FeatureError(
                f"{name}: the face to fill must be flat or a cylinder. Pick a flat or "
                "cylinder face."
            )
        if feature.refs.get("point") is not None:
            place = resolve_placement(ctx, feature.refs["point"], name, "point")
            issues = [*issues, *place.issues]
            start = place.point
        else:
            start = _face_middle(face)
        mode = str(feature.params.get("surface_spacing", "mapped"))
        try:
            region = _RoundRegion(face, start, mode)
        except ValueError:
            raise FeatureError(
                f"{name}: the start point lies on the cylinder's axis. Pick a point on the face."
            ) from None
        return region, (0.0, 0.0), issues

    def _sketch_region(self, feature: Feature, ctx: BuildContext) -> tuple[Any, list[Issue]]:
        """The closed sketch region to fill (``refs.sketch``, with its picked regions):
        the region holding the start point, else the largest (TR57 item 1)."""
        from fdcad.core.features.geometry_refs import resolve_placement
        from fdcad.core.features.sketch import sketch_for
        from fdcad.core.features.solids import face_area

        picked = sketch_for(feature, ctx)
        issues = list(picked.issues)
        profile = picked.sketch.profile
        if profile is None or not profile.faces:
            why = picked.sketch.profile_error or "it has no closed region"
            raise FeatureError(
                f"{feature.name}: the sketch cannot be filled: {why}. Close the sketch."
            )
        faces = list(profile.faces)
        if len(faces) > 1 and feature.refs.get("point") is not None:
            from OCP.BRepClass import BRepClass_FaceClassifier
            from OCP.gp import gp_Pnt
            from OCP.TopAbs import TopAbs_IN

            place = resolve_placement(ctx, feature.refs["point"], feature.name, "point")
            for face in faces:
                state = BRepClass_FaceClassifier(face, gp_Pnt(*place.point), 1e-3).State()
                if state == TopAbs_IN:
                    return face, issues
        return max(faces, key=lambda f: face_area([f])), issues

    def kept(
        self,
        feature: Feature,
        ctx: BuildContext,
        footprint: float,
        frame: tuple[_Region, tuple[float, float], list[Issue]] | None = None,
        seed: tuple[float, float] | None = None,
    ) -> tuple[_Region, list[tuple[float, float]], list[Issue]]:
        """The layout points (in the face plane) whose copy fits, with the margin. The
        ``seed`` point always counts: the seed's own cut may already open the face there."""
        name = feature.name
        region, start, issues = frame if frame is not None else self._frame(feature, ctx)
        spacing = _value(feature, "spacing", 0.0)
        spacing2 = _value(feature, "row_spacing", spacing) or spacing
        try:
            points = layout_points(
                str(feature.params.get("layout", "grid")),
                spacing,
                spacing2,
                _value(feature, "stagger_angle", math.radians(60.0)),
                str(feature.params.get("ring_shape", "circle")),
                round(_value(feature, "sides", 6.0)),
                region.reach(start),
            )
        except ValueError as exc:
            if "spacing" in str(exc):
                raise FeatureError(
                    f"{name}: the spacing must be more than 0. Type a spacing."
                ) from exc
            raise FeatureError(
                f"{name}: the layout makes more than {MAX_INSTANCES} copies. Use a larger spacing."
            ) from exc
        margin = _value(feature, "margin", 0.0)
        if feature.params.get("fit") == "centre":  # only the centre must be on the material
            footprint = 0.0
        centres = np.array([(start[0] + a, start[1] + b) for a, b in points], dtype=float)
        room = region.clearance(centres)
        out = [
            (float(c[0]), float(c[1]))
            for c, r in zip(centres, room, strict=True)
            if (seed is not None and math.hypot(c[0] - seed[0], c[1] - seed[1]) < 1e-6)
            or (r >= footprint + margin - 1e-9 and region.inside(float(c[0]), float(c[1])))
        ]
        if len(out) > MAX_INSTANCES:
            raise FeatureError(
                f"{name}: {len(out)} copies fit, more than {MAX_INSTANCES}. Use a larger spacing."
            )
        return region, out, issues

    def _build(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue], int]:
        from fdcad.core.features.patterns import skipped

        shape = str(feature.params.get("shape", "none"))
        skip = skipped(feature)
        if shape != "none":
            return self._cut_shapes(feature, ctx, shape, skip)
        return self._copy_seed(feature, ctx, skip)

    def _cut_shapes(
        self, feature: Feature, ctx: BuildContext, shape: str, skip: set[tuple[int, int]]
    ) -> tuple[NamedShape, list[Issue], int]:
        from OCP.BRepBuilderAPI import (
            BRepBuilderAPI_MakeEdge,
            BRepBuilderAPI_MakeFace,
            BRepBuilderAPI_MakePolygon,
            BRepBuilderAPI_MakeWire,
        )
        from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
        from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Vec

        from fdcad.core.features.modify import require_body
        from fdcad.core.features.solids import bounding_size, combine, compound
        from fdcad.core.naming.names import restrict

        name = feature.name
        body = require_body(feature, ctx)
        size = _value(feature, "size", 0.0)
        if size <= 0:
            raise FeatureError(f"{name}: the shape size must be more than 0. Type a size.")
        angle = _value(feature, "shape_angle", 0.0)
        sides = round(_value(feature, "sides", 6.0))
        corners = shape_outline(shape, size, angle, sides)
        footprint = size / 2 if not corners else max(math.hypot(x, y) for x, y in corners)
        per_size = footprint / size  # the footprint grows with the size
        frame = self._frame(feature, ctx)
        end = feature.params.get("size_end")
        if feature.params.get("gradient") is False:
            end = None  # the panel's tick is off
        if isinstance(end, Param):  # TR324 (D1518): a size gradient across the face
            if end.value <= 0:
                raise FeatureError(f"{name}: the end size must be more than 0. Type a size.")
            footprint = per_size * min(size, end.value)
        region, centres, issues = self.kept(feature, ctx, footprint, frame=frame)
        keep = [c for k, c in enumerate(centres, start=1) if (k, 1) not in skip]
        sizes = [size] * len(keep)
        if isinstance(end, Param) and keep:
            sizes = gradient_sizes(feature, ctx, region, frame[1], keep, size, end.value)
            if feature.params.get("fit") != "centre":
                margin = _value(feature, "margin", 0.0)
                room = region.clearance(np.array(keep, dtype=float))
                pairs = [
                    (c, s)
                    for c, s, r in zip(keep, sizes, room, strict=True)
                    if r >= per_size * s + margin - 1e-9
                ]
                keep, sizes = [c for c, _s in pairs], [s for _c, s in pairs]
        if not keep:
            return body, issues, 0
        u, v = region.u, region.v
        n = region.normal()
        depth = _value(feature, "depth", 0.0) or region.default_depth(bounding_size(body.shape))
        lift = 1e-3 if _value(feature, "depth", 0.0) else bounding_size(body.shape) + 1.0
        lift = region.lift(lift)
        tools = []
        round_face = isinstance(region, _RoundRegion)
        for c, here in zip(keep, sizes, strict=True):
            # A round face builds each shape at the start and turns it into place (D1903).
            centre = region.point(0.0, 0.0) if round_face else region.point(*c)
            base = (centre[0] + n[0] * lift, centre[1] + n[1] * lift, centre[2] + n[2] * lift)
            corners = shape_outline(shape, here, angle, sides)
            if corners:
                poly = BRepBuilderAPI_MakePolygon()
                for x, y in corners:
                    poly.Add(gp_Pnt(base[0] + u[0] * x + v[0] * y,
                                    base[1] + u[1] * x + v[1] * y,
                                    base[2] + u[2] * x + v[2] * y))  # fmt: skip
                poly.Close()
                wire = poly.Wire()
            else:
                circle = gp_Circ(gp_Ax2(gp_Pnt(*base), gp_Dir(*n), gp_Dir(*u)), here / 2)
                wire = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circle).Edge()).Wire()
            face = BRepBuilderAPI_MakeFace(wire).Face()
            amount = depth + lift
            tool = BRepPrimAPI_MakePrism(
                face, gp_Vec(-n[0] * amount, -n[1] * amount, -n[2] * amount)
            ).Shape()
            if round_face:
                from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform

                tool = BRepBuilderAPI_Transform(tool, region.motion(c, (0.0, 0.0)), True).Shape()
            tools.append(tool)
        whole = tools[0] if len(tools) == 1 else compound(tools)
        cut = NamedShape(whole, restrict([], whole, f"{feature.id}/cut"))
        return combine(feature.id, name, body, cut, "cut"), issues, len(keep)

    def _copy_seed(
        self, feature: Feature, ctx: BuildContext, skip: set[tuple[int, int]]
    ) -> tuple[NamedShape, list[Issue], int]:
        from fdcad.core.features.patterns import Placement, apply_pattern
        from fdcad.core.features.seeds import seed_centre

        name = feature.name
        if not (
            feature.refs.get("features") or feature.refs.get("faces") or feature.refs.get("bodies")
        ):
            raise FeatureError(
                f"{name}: pick features, faces or bodies to copy, or choose a shape."
            )
        from OCP.gp import gp_Pnt

        centre = seed_centre(feature, ctx)
        frame = self._frame(feature, ctx)
        here = frame[0].flat(gp_Pnt(*centre))
        footprint = self._seed_footprint(feature, ctx, frame[0], here)
        region, centres, issues = self.kept(feature, ctx, footprint, frame, here)
        placements = []
        count = 0
        for k, c in enumerate(centres, start=1):
            count += 1
            if math.hypot(c[0] - here[0], c[1] - here[1]) < 1e-6:
                continue  # the seed itself
            placements.append(Placement((k, 1), region.motion(c, here)))
        outcome = apply_pattern(feature, ctx, [p for p in placements if p.index not in skip])
        kept = count - sum(1 for k in range(1, count + 1) if (k, 1) in skip)
        return outcome.body, issues + outcome.issues, kept

    @staticmethod
    def _seed_footprint(
        feature: Feature, ctx: BuildContext, region: _Region, here: tuple[float, float]
    ) -> float:
        """How far the seed reaches from its centre across the face: its box's corners,
        flattened into the face plane. Face and body seeds count as a point."""
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib
        from OCP.gp import gp_Pnt

        from fdcad.core.features.patterns import _seed_tools

        tools = _seed_tools(feature, ctx) if feature.refs.get("features") else []
        best = 0.0
        for _f, tool, _o in tools:
            box = Bnd_Box()
            BRepBndLib.Add_s(tool.shape, box)
            if box.IsVoid():
                continue
            lo, hi = box.CornerMin(), box.CornerMax()
            for x in (lo.X(), hi.X()):
                for y in (lo.Y(), hi.Y()):
                    for z in (lo.Z(), hi.Z()):
                        f = region.flat(gp_Pnt(x, y, z))
                        best = max(best, math.hypot(f[0] - here[0], f[1] - here[1]))
        return best
