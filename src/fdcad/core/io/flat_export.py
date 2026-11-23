"""DXF and SVG export of a flat face or a sketch, true scale, in the part's units (PLAN Phase 2).

The edges are moved into the plane's own coordinates, so a face anywhere in the
model comes out flat at its true size. Lines, circles and arcs are written as
exact entities; any other curve (spline, ellipse) becomes a polyline within
``DEFLECTION`` mm of the curve (DECISIONS D350).
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Line
from OCP.gp import gp_Ax3, gp_Trsf
from OCP.Standard import Standard_Failure
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Compound, TopoDS_Shape

from fdcad.core.io.export import ExportError
from fdcad.core.plane_normal import plane_frame

#: Largest distance in mm between a curve and the polyline written for it.
DEFLECTION = 0.01
#: Points per polyline are capped so one curve never becomes a large point set.
MAX_POINTS = 2000
_INCH = 25.4


@dataclass(frozen=True)
class FlatLine:
    """A straight line from ``a`` to ``b``."""

    a: tuple[float, float]
    b: tuple[float, float]


@dataclass(frozen=True)
class FlatArc:
    """A circle (``start == end``) or an arc running anticlockwise from ``start`` to ``end``.

    Angles are in degrees from the X axis.
    """

    center: tuple[float, float]
    radius: float
    start: float = 0.0
    end: float = 360.0

    @property
    def full(self) -> bool:
        """True for a whole circle."""
        return abs((self.end - self.start) % 360.0) < 1e-9 and self.end != self.start


@dataclass(frozen=True)
class FlatPolyline:
    """Any other curve as points, an (n, 2) array."""

    points: NDArray[np.float64]


FlatItem = FlatLine | FlatArc | FlatPolyline


def face_plane(face: TopoDS_Shape) -> gp_Ax3:
    """The plane of a flat face, as a coordinate system. ExportError when it is not flat."""
    if face.ShapeType() != TopAbs_FACE:
        raise ExportError("Pick a flat face or a sketch to export.")
    plane = plane_frame(TopoDS.Face(face))  # seen from outside the part
    if plane is None:
        raise ExportError("The picked face is not flat. Pick a flat face or a sketch.")
    return plane


def face_edges(face: TopoDS_Shape) -> list[TopoDS_Shape]:
    """Every edge of ``face``: its outer outline and its holes."""
    out: list[TopoDS_Shape] = []
    explorer = TopExp_Explorer(face, TopAbs_EDGE)
    while explorer.More():
        out.append(explorer.Current())
        explorer.Next()
    return out


def sketch_items(model: Any, plane: Any) -> tuple[list[TopoDS_Shape], gp_Ax3]:
    """The drawn (not construction) curves of a sketch as 3D edges, with the sketch plane."""
    edges, ax3, _left = sketch_items_left_out(model, plane)
    return edges, ax3


def sketch_items_left_out(model: Any, plane: Any) -> tuple[list[TopoDS_Shape], gp_Ax3, int]:
    """``sketch_items`` and how many sketch items the file leaves out: text, and curves
    that cannot be made into edges (spec 2 section 20 item 21, D715)."""
    from fdcad.core.sketch.model import Point
    from fdcad.core.sketch.profiles import ProfileError, _EdgeMaker

    maker = _EdgeMaker(model, plane)
    edges: list[TopoDS_Shape] = []
    left = len(getattr(model, "texts", []) or [])
    for ent in model.entities.values():
        if isinstance(ent, Point) or getattr(ent, "construction", False):
            continue
        try:
            edges.append(maker.edge(ent.id))
        except (ProfileError, Standard_Failure, KeyError, ValueError):
            left += 1
    return edges, plane.ax3(), left


def _angle(x: float, y: float) -> float:
    return math.degrees(math.atan2(y, x)) % 360.0


def _flat_edge(edge: TopoDS_Shape) -> FlatItem | None:
    e = TopoDS.Edge(edge)
    if BRep_Tool.Degenerated_s(e):
        return None
    curve = BRepAdaptor_Curve(e)
    first, last = curve.FirstParameter(), curve.LastParameter()
    kind = curve.GetType()
    if kind == GeomAbs_Line:
        p, q = curve.Value(first), curve.Value(last)
        return FlatLine((p.X(), p.Y()), (q.X(), q.Y()))
    if kind == GeomAbs_Circle:
        circle = curve.Circle()
        c, r = circle.Location(), circle.Radius()
        if abs(abs(last - first) - 2 * math.pi) < 1e-9:
            return FlatArc((c.X(), c.Y()), r)
        p, q = curve.Value(first), curve.Value(last)
        a0, a1 = _angle(p.X() - c.X(), p.Y() - c.Y()), _angle(q.X() - c.X(), q.Y() - c.Y())
        if circle.Axis().Direction().Z() < 0:  # runs clockwise: swap ends
            a0, a1 = a1, a0
        return FlatArc((c.X(), c.Y()), r, a0, a1)
    sampler = GCPnts_QuasiUniformDeflection(curve, DEFLECTION, first, last)
    if not sampler.IsDone() or sampler.NbPoints() < 2:
        return None
    count = min(sampler.NbPoints(), MAX_POINTS)
    step = (sampler.NbPoints() - 1) / (count - 1)
    picks = [round(i * step) + 1 for i in range(count)]
    pts = np.array([(sampler.Value(i).X(), sampler.Value(i).Y()) for i in picks])
    return FlatPolyline(pts)


def flatten(edges: list[TopoDS_Shape], plane: gp_Ax3, scale: float = 1.0) -> list[FlatItem]:
    """Edges as 2D items in ``plane``'s coordinates, divided by ``scale`` (25.4 for inches)."""
    from OCP.BRep import BRep_Builder

    if not edges:
        raise ExportError("There is nothing to export. Pick a flat face or a sketch with curves.")
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for edge in edges:
        builder.Add(compound, edge)
    to_plane = gp_Trsf()
    to_plane.SetTransformation(plane)
    if scale != 1.0:
        shrink = gp_Trsf()
        shrink.SetScaleFactor(1.0 / scale)
        to_plane = shrink.Multiplied(to_plane)
    moved = BRepBuilderAPI_Transform(compound, to_plane, True).Shape()
    items: list[FlatItem] = []
    explorer = TopExp_Explorer(moved, TopAbs_EDGE)
    while explorer.More():
        item = _flat_edge(explorer.Current())
        explorer.Next()
        if item is not None:
            items.append(item)
    if not items:
        raise ExportError("There is nothing to export. Pick a flat face or a sketch with curves.")
    return items


def _arc_extent(item: FlatArc) -> tuple[list[float], list[float]]:
    """X and Y values bounding an arc: its ends and the quarter points it passes. A full
    circle gives all four; a part arc no longer counts the whole circle (audit D item 19,
    D742)."""
    (cx, cy), r = item.center, item.radius
    if item.full:
        return [cx - r, cx + r], [cy - r, cy + r]
    start, end = item.start % 360.0, item.end % 360.0
    sweep = (end - start) % 360.0 or 360.0
    angles = [start, start + sweep]
    angles += [
        q
        for q in (0.0, 90.0, 180.0, 270.0, 360.0, 450.0, 540.0, 630.0)
        if start < q < start + sweep
    ]
    xs = [cx + r * math.cos(math.radians(a)) for a in angles]
    ys = [cy + r * math.sin(math.radians(a)) for a in angles]
    return xs, ys


def _bounds(items: list[FlatItem]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for item in items:
        if isinstance(item, FlatLine):
            xs += [item.a[0], item.b[0]]
            ys += [item.a[1], item.b[1]]
        elif isinstance(item, FlatArc):
            px, py = _arc_extent(item)
            xs += px
            ys += py
        else:
            xs += [float(item.points[:, 0].min()), float(item.points[:, 0].max())]
            ys += [float(item.points[:, 1].min()), float(item.points[:, 1].max())]
    return min(xs), min(ys), max(xs), max(ys)


def _n(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


# DXF ---------------------------------------------------------------------------------------


def to_dxf(items: list[FlatItem], units: str = "mm", layers: list[str] | None = None) -> str:
    """A plain ASCII DXF (R12 entities) with the unit in the header (``$INSUNITS``).
    ``layers`` gives each item its layer name (TR300, D1204); else layer 0."""
    code = 1 if units == "in" else 4
    out = [
        "0", "SECTION", "2", "HEADER",
        "9", "$ACADVER", "1", "AC1009",
        "9", "$INSUNITS", "70", str(code),
        "9", "$MEASUREMENT", "70", "0" if units == "in" else "1",
        "0", "ENDSEC",
        "0", "SECTION", "2", "ENTITIES",
    ]  # fmt: skip
    for k, item in enumerate(items):
        lay = layers[k] if layers is not None and k < len(layers) else "0"
        if isinstance(item, FlatLine):
            out += ["0", "LINE", "8", lay]
            out += ["10", _n(item.a[0]), "20", _n(item.a[1]), "30", "0"]
            out += ["11", _n(item.b[0]), "21", _n(item.b[1]), "31", "0"]
        elif isinstance(item, FlatArc):
            (cx, cy), r = item.center, item.radius
            out += ["0", "CIRCLE" if item.full else "ARC", "8", lay]
            out += ["10", _n(cx), "20", _n(cy), "30", "0", "40", _n(r)]
            if not item.full:
                out += ["50", _n(item.start), "51", _n(item.end)]
        else:
            out += ["0", "POLYLINE", "8", lay, "66", "1", "10", "0", "20", "0", "30", "0"]
            for x, y in item.points.tolist():
                out += ["0", "VERTEX", "8", lay, "10", _n(x), "20", _n(y), "30", "0"]
            out += ["0", "SEQEND", "8", lay]
    out += ["0", "ENDSEC", "0", "EOF"]
    return "\n".join(out) + "\n"


# SVG ---------------------------------------------------------------------------------------


def _svg_arc(item: FlatArc, flip: float) -> str:
    (cx, cy), r = item.center, item.radius
    a0, a1 = math.radians(item.start), math.radians(item.end)
    sweep = (item.end - item.start) % 360.0
    x0, y0 = cx + r * math.cos(a0), flip - (cy + r * math.sin(a0))
    x1, y1 = cx + r * math.cos(a1), flip - (cy + r * math.sin(a1))
    large = 1 if sweep > 180.0 else 0
    # Anticlockwise in the plane is clockwise once Y points down, which SVG calls sweep 0.
    return f'<path d="M {_n(x0)} {_n(y0)} A {_n(r)} {_n(r)} 0 {large} 0 {_n(x1)} {_n(y1)}"/>'


def to_svg(items: list[FlatItem], units: str = "mm", layers: list[str] | None = None) -> str:
    """An SVG whose width and height carry the unit, so it prints and cuts at true size.

    One SVG user unit is one part unit. Y points up in the part and down in SVG,
    so every Y value is mirrored about the top of the drawing. With ``layers``
    (TR300, D1204) each layer is a group with its name as id and its own colour.
    """
    x0, y0, x1, y1 = _bounds(items)
    width, height = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
    flip = y0 + y1  # y' = flip - y keeps the drawing inside the same view box
    stroke = 0.1 if units == "mm" else 0.004
    body: list[str] = []
    for item in items:
        if isinstance(item, FlatLine):
            body.append(
                f'<line x1="{_n(item.a[0])}" y1="{_n(flip - item.a[1])}" '
                f'x2="{_n(item.b[0])}" y2="{_n(flip - item.b[1])}"/>'
            )
        elif isinstance(item, FlatArc):
            if item.full:
                (cx, cy), r = item.center, item.radius
                body.append(f'<circle cx="{_n(cx)}" cy="{_n(flip - cy)}" r="{_n(r)}"/>')
            else:
                body.append(_svg_arc(item, flip))
        else:
            pts = item.points.copy()
            pts[:, 1] = flip - pts[:, 1]
            text = " ".join(f"{_n(x)},{_n(y)}" for x, y in pts.tolist())
            body.append(f'<polyline points="{text}"/>')
    head = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
        f'width="{_n(width)}{units}" height="{_n(height)}{units}" '
        f'viewBox="{_n(x0)} {_n(y0)} {_n(width)} {_n(height)}">\n'
    )
    if layers is None:
        return (
            head
            + f'<g fill="none" stroke="#000000" stroke-width="{stroke}">\n'
            + "\n".join(body)
            + "\n</g>\n</svg>\n"
        )
    from fdcad.core.io.section_export import SVG_COLOURS

    groups = []
    for name in dict.fromkeys(layers):
        lines = [line for line, lay in zip(body, layers, strict=False) if lay == name]
        colour = SVG_COLOURS.get(name, "#000000")
        groups.append(
            f'<g id="{name}" fill="none" stroke="{colour}" stroke-width="{stroke}">\n'
            + "\n".join(lines)
            + "\n</g>"
        )
    return head + "\n".join(groups) + "\n</svg>\n"


def export_flat(
    edges: list[TopoDS_Shape],
    plane: gp_Ax3,
    path: str | os.PathLike[str],
    units: str = "mm",
) -> None:
    """Write ``edges`` flat in ``plane`` as DXF or SVG (by the file extension)."""
    target = Path(path)
    kind = target.suffix.lower()
    if kind not in (".dxf", ".svg"):
        raise ExportError("Choose a file name ending in .dxf or .svg.")
    items = flatten(edges, plane, _INCH if units == "in" else 1.0)
    text = to_dxf(items, units) if kind == ".dxf" else to_svg(items, units)
    tmp = target.with_name(f".fdcad-{target.name}")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
