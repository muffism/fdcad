"""Flat pattern export as STEP, DXF and SVG (PHASE5_SPEC P5.5 item 5, D340).

Drawings are at true scale in millimetres, in the frame of the first wall
(seen from its z = thickness side). Layers: ``OUTLINE`` (cut lines),
``BEND_LINES`` (bend centre lines, with up or down and the angle in the SVG
title) and the optional ``BOUNDING_BOX``.
"""

from __future__ import annotations

import itertools
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Line, GeomAbs_Plane
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS

from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.core.features.sheetmetal.model import apply
from fdcad.core.features.solids import transform
from fdcad.core.io.export import ExportError, export_step
from fdcad.core.naming.names import faces_of
from fdcad.core.occ import ShapeMap

if TYPE_CHECKING:
    from fdcad.core.features.sheetmetal.flat_output import FlatOutput

Vec2 = tuple[float, float]
FORMATS = ("step", "dxf", "svg", "csv")


@dataclass(frozen=True)
class Segment:
    """A straight piece of a drawing."""

    a: Vec2
    b: Vec2


@dataclass(frozen=True)
class ArcPiece:
    """A circular arc running counter clockwise from ``start`` to ``end`` (degrees)."""

    centre: Vec2
    radius: float
    start: float
    end: float

    @property
    def full(self) -> bool:
        """True for a whole circle."""
        return abs((self.end - self.start) % 360.0) < 1e-9 and abs(self.end - self.start) > 1


@dataclass(frozen=True)
class BendMark:
    """A bend line with its direction ("up" or "down") and angle in degrees."""

    a: Vec2
    b: Vec2
    direction: str
    angle: float
    #: Step in the bending order, 0 without one (TR282, D1110).
    order: int = 0


@dataclass
class FlatDrawing:
    """Everything a 2D flat pattern file holds."""

    outline: list[Segment | ArcPiece] = field(default_factory=list)
    bends: list[BendMark] = field(default_factory=list)
    box: list[Vec2] = field(default_factory=list)
    marks: list[tuple[Segment, str]] = field(default_factory=list)  # cross breaks (D539)
    #: Marks for etching (TR330, D2006), on their own MARKS layer.
    engraving: list[Segment] = field(default_factory=list)

    def extent(self) -> tuple[float, float, float, float]:
        """min x, min y, max x, max y of the outline."""
        xs: list[float] = []
        ys: list[float] = []
        for item in self.outline:
            if isinstance(item, Segment):
                xs += [item.a[0], item.b[0]]
                ys += [item.a[1], item.b[1]]
            else:
                xs += [item.centre[0] - item.radius, item.centre[0] + item.radius]
                ys += [item.centre[1] - item.radius, item.centre[1] + item.radius]
        for p in self.box:
            xs.append(p[0])
            ys.append(p[1])
        if not xs:
            return (0.0, 0.0, 0.0, 0.0)
        return (min(xs), min(ys), max(xs), max(ys))


def _edge_items(edge: object) -> list[Segment | ArcPiece]:
    curve = BRepAdaptor_Curve(TopoDS.Edge(edge))
    first, last = curve.FirstParameter(), curve.LastParameter()
    p, q = curve.Value(first), curve.Value(last)
    kind = curve.GetType()
    if kind == GeomAbs_Line:
        return [Segment((p.X(), p.Y()), (q.X(), q.Y()))]
    if kind == GeomAbs_Circle:
        circ = curve.Circle()
        c = circ.Location()
        ccw = circ.Axis().Direction().Z() > 0
        a0 = math.degrees(math.atan2(p.Y() - c.Y(), p.X() - c.X()))
        a1 = math.degrees(math.atan2(q.Y() - c.Y(), q.X() - c.X()))
        if abs(last - first - 2 * math.pi) < 1e-9:
            return [ArcPiece((c.X(), c.Y()), circ.Radius(), 0.0, 360.0)]
        start, end = (a0, a1) if ccw else (a1, a0)
        return [ArcPiece((c.X(), c.Y()), circ.Radius(), start % 360.0, end % 360.0)]
    sampler = GCPnts_QuasiUniformDeflection(curve, 0.01)
    points = [sampler.Value(i) for i in range(1, sampler.NbPoints() + 1)]
    return [Segment((a.X(), a.Y()), (b.X(), b.Y())) for a, b in itertools.pairwise(points)]


def flat_drawing(result: FlatResult, bounding_box: bool = True) -> FlatDrawing:
    """The flat pattern as 2D cut lines, bend lines and an optional box."""
    if result.flat is None or result.sheet is None:
        raise ExportError("There is no flat pattern to export. Fix the Flat Pattern first.")
    model = result.sheet
    to_local = model.frame.Inverted()
    flat = transform(result.flat, to_local)
    t = model.thickness
    drawing = FlatDrawing()
    edges = ShapeMap()
    for face in faces_of(flat.shape):
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Plane:
            continue
        pln = surface.Plane()
        if abs(abs(pln.Axis().Direction().Z()) - 1) > 1e-9:
            continue
        if abs(pln.Location().Z() - t) > 1e-6:
            continue
        TopExp.MapShapes_s(face, TopAbs_EDGE, edges)
    for i in range(1, edges.Extent() + 1):
        drawing.outline.extend(_edge_items(edges.FindKey(i)))
    for a, b, bend in result.lines:
        la, lb = apply(to_local, a), apply(to_local, b)
        drawing.bends.append(
            BendMark(
                (la[0], la[1]),
                (lb[0], lb[1]),
                "up" if bend.up > 0 else "down",
                math.degrees(bend.angle),
                result.order.get(bend.bid, 0),
            )
        )
    for a, b, title in result.marks:
        la, lb = apply(to_local, a), apply(to_local, b)
        drawing.marks.append((Segment((la[0], la[1]), (lb[0], lb[1])), title))
    for edge in result.extras.get("engraving", []):  # TR330 (D2006)
        moved = BRepBuilderAPI_Transform(edge, to_local, True).Shape()
        drawing.engraving.extend(_segments(moved))
    if bounding_box:
        drawing.box = _box(drawing, result.grain_angle)
    return drawing


def _segments(edge: object) -> list[Segment]:
    """An edge as short straight pieces in XY (0.01 mm from the curve)."""
    curve = BRepAdaptor_Curve(TopoDS.Edge(edge))
    sampler = GCPnts_QuasiUniformDeflection(curve, 0.01)
    points = [sampler.Value(i) for i in range(1, sampler.NbPoints() + 1)]
    return [Segment((a.X(), a.Y()), (b.X(), b.Y())) for a, b in itertools.pairwise(points)]


def _box(drawing: FlatDrawing, angle: float) -> list[Vec2]:
    """Corners of the outline's box with its length along ``angle``."""
    c, s = math.cos(angle), math.sin(angle)
    pts: list[Vec2] = []
    for item in drawing.outline:
        if isinstance(item, Segment):
            pts += [item.a, item.b]
        else:
            r = item.radius
            pts += [(item.centre[0] + dx * r, item.centre[1] + dy * r) for dx, dy in _ring()]
    if not pts:
        return []
    us = [p[0] * c + p[1] * s for p in pts]
    vs = [-p[0] * s + p[1] * c for p in pts]
    corners = [(min(us), min(vs)), (max(us), min(vs)), (max(us), max(vs)), (min(us), max(vs))]
    return [(u * c - v * s, u * s + v * c) for u, v in corners]


def _ring() -> list[Vec2]:
    return [(math.cos(k * math.pi / 36), math.sin(k * math.pi / 36)) for k in range(72)]


def _n(x: float) -> str:
    text = f"{x:.6f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def dxf_text(drawing: FlatDrawing, colours: tuple[int, int] | None = None) -> str:
    """The drawing as an ASCII DXF (R12) in millimetres. With ``colours`` (DXF colour
    numbers for up and down bends) the bend lines go on BEND_UP and BEND_DOWN layers
    instead of BEND_LINES (TR173, D1108)."""
    out: list[str] = []

    def put(code: int, value: str) -> None:
        out.extend([str(code), value])

    if colours is None:
        layers = [("OUTLINE", 7), ("BEND_LINES", 1), ("BOUNDING_BOX", 3)]
    else:
        layers = [
            ("OUTLINE", 7),
            ("BEND_UP", colours[0]),
            ("BEND_DOWN", colours[1]),
            ("BOUNDING_BOX", 3),
        ]
    if drawing.marks:
        layers.append(("CROSS_BREAKS", 5))
    if drawing.engraving:
        layers.append(("MARKS", 6))
    if any(b.order for b in drawing.bends):
        layers.append(("BEND_ORDER", 2))
    put(0, "SECTION")
    put(2, "HEADER")
    put(9, "$ACADVER")
    put(1, "AC1009")
    put(9, "$INSUNITS")
    put(70, "4")
    put(0, "ENDSEC")
    put(0, "SECTION")
    put(2, "TABLES")
    put(0, "TABLE")
    put(2, "LTYPE")
    put(70, "1")
    put(0, "LTYPE")
    put(2, "CONTINUOUS")
    put(70, "0")
    put(3, "Solid line")
    put(72, "65")
    put(73, "0")
    put(40, "0")
    put(0, "ENDTAB")
    put(0, "TABLE")
    put(2, "LAYER")
    put(70, str(len(layers)))
    for name, colour in layers:
        put(0, "LAYER")
        put(2, name)
        put(70, "0")
        put(62, str(colour))
        put(6, "CONTINUOUS")
    put(0, "ENDTAB")
    put(0, "ENDSEC")
    put(0, "SECTION")
    put(2, "ENTITIES")

    def line(layer: str, a: Vec2, b: Vec2) -> None:
        put(0, "LINE")
        put(8, layer)
        put(10, _n(a[0]))
        put(20, _n(a[1]))
        put(30, "0")
        put(11, _n(b[0]))
        put(21, _n(b[1]))
        put(31, "0")

    for item in drawing.outline:
        if isinstance(item, Segment):
            line("OUTLINE", item.a, item.b)
            continue
        put(0, "CIRCLE" if item.full else "ARC")
        put(8, "OUTLINE")
        put(10, _n(item.centre[0]))
        put(20, _n(item.centre[1]))
        put(30, "0")
        put(40, _n(item.radius))
        if not item.full:
            put(50, _n(item.start))
            put(51, _n(item.end))
    for bend in drawing.bends:
        layer = "BEND_LINES" if colours is None else f"BEND_{bend.direction.upper()}"
        line(layer, bend.a, bend.b)
        if bend.order:  # the step number at the middle of the bend line (D1110)
            put(0, "TEXT")
            put(8, "BEND_ORDER")
            put(10, _n((bend.a[0] + bend.b[0]) / 2))
            put(20, _n((bend.a[1] + bend.b[1]) / 2))
            put(30, "0")
            put(40, "3")
            put(1, str(bend.order))
    for k, corner in enumerate(drawing.box):
        line("BOUNDING_BOX", corner, drawing.box[(k + 1) % len(drawing.box)])
    for mark, _title in drawing.marks:
        line("CROSS_BREAKS", mark.a, mark.b)
    for piece in drawing.engraving:
        line("MARKS", piece.a, piece.b)
    put(0, "ENDSEC")
    put(0, "EOF")
    return "\n".join(out) + "\n"


def svg_text(drawing: FlatDrawing) -> str:
    """The drawing as SVG at true scale (1 user unit is 1 mm), y pointing up in the model."""
    x0, y0, x1, y1 = drawing.extent()
    margin = 1.0
    width, height = x1 - x0 + 2 * margin, y1 - y0 + 2 * margin
    left, top = x0 - margin, -(y1 + margin)

    def pt(p: Vec2) -> str:
        return f"{_n(p[0])} {_n(-p[1])}"

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_n(width)}mm" '
        f'height="{_n(height)}mm" viewBox="{_n(left)} {_n(top)} {_n(width)} {_n(height)}">',
        '<g id="OUTLINE" fill="none" stroke="#000000" stroke-width="0.1">',
    ]
    for item in drawing.outline:
        if isinstance(item, Segment):
            lines.append(f'<path d="M {pt(item.a)} L {pt(item.b)}"/>')
        elif item.full:
            c = item.centre
            lines.append(f'<circle cx="{_n(c[0])}" cy="{_n(-c[1])}" r="{_n(item.radius)}"/>')
        else:
            c, r = item.centre, item.radius
            a = (
                c[0] + r * math.cos(math.radians(item.start)),
                c[1] + r * math.sin(math.radians(item.start)),
            )
            b = (
                c[0] + r * math.cos(math.radians(item.end)),
                c[1] + r * math.sin(math.radians(item.end)),
            )
            span = (item.end - item.start) % 360.0
            large = 1 if span > 180.0 else 0
            lines.append(f'<path d="M {pt(a)} A {_n(r)} {_n(r)} 0 {large} 0 {pt(b)}"/>')
    lines.append("</g>")
    lines.append(
        '<g id="BEND_LINES" fill="none" stroke="#C03030" stroke-width="0.1" stroke-dasharray="2 1">'
    )
    for bend in drawing.bends:
        lines.append(
            f'<path d="M {pt(bend.a)} L {pt(bend.b)}">'
            f"<title>Bend {bend.direction} {_n(bend.angle)} degrees"
            f"{f', step {bend.order}' if bend.order else ''}</title></path>"
        )
    lines.append("</g>")
    if drawing.marks:
        lines.append('<g id="CROSS_BREAKS" fill="none" stroke="#3050C0" stroke-width="0.1">')
        for mark, title in drawing.marks:
            lines.append(f'<path d="M {pt(mark.a)} L {pt(mark.b)}"><title>{title}</title></path>')
        lines.append("</g>")
    if drawing.engraving:
        lines.append('<g id="MARKS" fill="none" stroke="#B030B0" stroke-width="0.1">')
        lines.extend(f'<path d="M {pt(m.a)} L {pt(m.b)}"/>' for m in drawing.engraving)
        lines.append("</g>")
    if drawing.box:
        corners = " ".join(pt(p) for p in drawing.box)
        lines.append('<g id="BOUNDING_BOX" fill="none" stroke="#308030" stroke-width="0.1">')
        lines.append(f'<polygon points="{corners}"/>')
        lines.append("</g>")
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def export_flat(
    result: FlatResult,
    path: str | os.PathLike[str],
    fmt: str,
    bounding_box: bool = True,
    output: FlatOutput | None = None,
) -> None:
    """Write the flat pattern as ``fmt`` ("step", "dxf", "svg" or "csv"). ``output`` sets
    the DXF and SVG items, placement and bend colours (TR173, D1108). Raises ExportError."""
    if fmt not in FORMATS:
        raise ExportError(
            f"Flat patterns export as STEP, DXF, SVG or CSV, not {fmt}. "
            "Choose one of those file types."
        )
    if fmt == "step":
        if result.flat is None:
            raise ExportError("There is no flat pattern to export. Fix the Flat Pattern first.")
        export_step(result.flat.shape, path)
        return
    if fmt == "csv":  # quoting data (TR172, D1106)
        from fdcad.core.features.sheetmetal.quote import quote_csv

        text = quote_csv(result.extras)
    else:
        drawing = flat_drawing(result, bounding_box)
        colours = None
        if output is not None:
            from fdcad.core.features.sheetmetal.flat_output import apply_output

            drawing = apply_output(drawing, output)
            colours = (output.up_colour, output.down_colour)
        text = dxf_text(drawing, colours) if fmt == "dxf" else svg_text(drawing)
    try:
        Path(path).write_text(text, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise ExportError(
            f"Could not write {Path(path).name} ({exc.strerror}). "
            "Check the folder and file name, then export again."
        ) from exc
