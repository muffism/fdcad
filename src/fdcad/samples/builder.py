"""Helpers for building fully defined sample parts in code (no Qt)."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Any

from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Document, Feature, Param, Variable
from fdcad.core.features.sketch import face_plane
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Circle, Line, Sketch, sketch_to_data
from fdcad.core.sketch.profiles import SketchPlane
from fdcad.core.units import Kind

Vec = tuple[float, float]
Vec3 = tuple[float, float, float]
FRONT, TOP, RIGHT = "f2", "f3", "f4"


def length(expr: str, value: float) -> Param:
    """A length parameter: what the user typed and its value in mm."""
    return Param(expr, value)


class SketchBuilder:
    """Builds a sketch whose shapes are dimensioned from the fixed origin point."""

    def __init__(self) -> None:
        self.sk = Sketch()
        self.origin = self.sk.add_point(0.0, 0.0, construction=True)
        self.sk.relate("fixed", self.origin)

    def _place(self, pid: str, x: float, y: float, xexpr: str | None, yexpr: str | None) -> None:
        """Dimension a point from the origin, or join it to the origin when it is there."""
        if abs(x) < 1e-12 and abs(y) < 1e-12:
            self.sk.relate("coincident", pid, self.origin)
            return
        if abs(x) < 1e-12:
            self.sk.relate("vertical", pid, self.origin)
        else:
            self.sk.dimension(
                "horizontal_distance", [self.origin, pid], length(xexpr or f"{abs(x):g}", abs(x))
            )
        if abs(y) < 1e-12:
            self.sk.relate("horizontal", pid, self.origin)
        else:
            self.sk.dimension(
                "vertical_distance", [self.origin, pid], length(yexpr or f"{abs(y):g}", abs(y))
            )

    def outline(
        self,
        points: Sequence[Vec],
        lengths: Sequence[str | None] | None = None,
        anchor: tuple[str | None, str | None] = (None, None),
    ) -> list[str]:
        """A closed outline of horizontal and vertical lines through ``points``.

        Each line but the last two gets a length dimension (``lengths`` gives the
        typed text, None for a plain number); the closed loop fixes the other two.
        The first point is placed from the origin with ``anchor`` texts.
        """
        sk = self.sk
        n = len(points)
        lines: list[Line] = []
        for i in range(n):
            (x1, y1), (x2, y2) = points[i], points[(i + 1) % n]
            line = sk.entities[sk.add_line(x1, y1, x2, y2)]
            assert isinstance(line, Line)
            lines.append(line)
        for i in range(n):
            sk.relate("coincident", lines[i].p2, lines[(i + 1) % n].p1)
            (x1, y1), (x2, y2) = points[i], points[(i + 1) % n]
            sk.relate("horizontal" if abs(y1 - y2) < 1e-12 else "vertical", lines[i].id)
        texts = list(lengths or [None] * n)
        for i, line in enumerate(lines[:-2]):
            (x1, y1), (x2, y2) = points[i], points[(i + 1) % n]
            size = math.hypot(x2 - x1, y2 - y1)
            sk.dimension("distance", [line.id], length(texts[i] or f"{size:g}", size))
        x0, y0 = points[0]
        self._place(lines[0].p1, x0, y0, *anchor)
        return [line.id for line in lines]

    def rectangle(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        wexpr: str | None = None,
        hexpr: str | None = None,
        anchor: tuple[str | None, str | None] = (None, None),
    ) -> list[str]:
        """A rectangle from corner (x, y), width and height dimensioned."""
        return self.outline(
            [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], [wexpr, hexpr, None, None], anchor
        )

    def circle(
        self,
        cx: float,
        cy: float,
        diameter: float,
        dexpr: str | None = None,
        anchor: tuple[str | None, str | None] = (None, None),
    ) -> str:
        """A circle with its diameter and centre position dimensioned."""
        cid = self.sk.add_circle(cx, cy, diameter / 2)
        center = self.sk.entities[cid].center  # type: ignore[union-attr]
        self.sk.dimension("diameter", [cid], length(dexpr or f"{diameter:g}", diameter))
        self._place(center, cx, cy, *anchor)
        return cid

    def hexagon(
        self,
        cx: float,
        cy: float,
        flats: float,
        fexpr: str | None = None,
        anchor: tuple[str | None, str | None] = (None, None),
    ) -> list[str]:
        """A regular hexagon ``flats`` across the flats (two flats horizontal), its size
        and centre dimensioned (TR188, D2003)."""
        from fdcad.core.sketch.ops.shapes import polygon

        made = polygon(self.sk, (cx, cy), (cx, cy + flats / 2), 6, inscribed=False)
        circle = self.sk.entities[made.construction[0]]
        assert isinstance(circle, Circle)
        self.sk.dimension("diameter", [circle.id], length(fexpr or f"{flats:g}", flats))
        self._place(circle.center, cx, cy, *anchor)
        self.sk.relate("horizontal", made.curves[0])
        return made.curves

    def centerline(self, x1: float, y1: float, x2: float, y2: float) -> str:
        """A horizontal or vertical construction line, placed and sized from the origin."""
        lid = self.sk.add_line(x1, y1, x2, y2, construction=True)
        line = self.sk.entities[lid]
        assert isinstance(line, Line)
        horizontal = abs(y1 - y2) < 1e-12
        self.sk.relate("horizontal" if horizontal else "vertical", lid)
        self._place(line.p1, x1, y1, None, None)
        size = math.hypot(x2 - x1, y2 - y1)
        self.sk.dimension("distance", [lid], length(f"{size:g}", size))
        return lid


def add_variables(doc: Document, **values: tuple[str, float]) -> None:
    """Add global length variables: name to (typed text, mm)."""
    for name, (expr, value) in values.items():
        doc.variables.append(Variable(name, Kind.LENGTH, expr, value))


def add_sketch(doc: Document, builder: SketchBuilder, plane: dict[str, Any], name: str) -> str:
    """Append a sketch feature."""
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(fid, "sketch", name, refs={"plane": plane}, data=sketch_to_data(builder.sk))
    )
    return fid


def add_feature(
    doc: Document,
    ftype: str,
    name: str,
    sketch: str,
    refs: dict[str, Any] | None = None,
    **params: Any,
) -> str:
    """Append an extrude or revolve using ``sketch``."""
    fid = doc.new_feature_id()
    all_refs: dict[str, Any] = {"sketch": {"feature": sketch}}
    all_refs.update(refs or {})
    doc.features.append(Feature(fid, ftype, name, params=dict(params), refs=all_refs))
    return fid


def face_ref(
    doc: Document, normal: Vec3, point: Callable[[TopoDS_Face], bool] | None = None
) -> tuple[dict[str, Any], SketchPlane]:
    """Reference and placement of the one flat face with this outward normal (and test)."""
    report = RebuildEngine().rebuild(doc)
    body = report.body
    assert body is not None
    found: list[TopoDS_Face] = []
    explorer = TopExp_Explorer(body.shape, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face(explorer.Current())
        explorer.Next()
        plane = face_plane(face)
        if plane is None:
            continue
        same = all(abs(a - b) < 1e-9 for a, b in zip(plane.normal, normal, strict=True))
        if same and (point is None or point(face)):
            found.append(face)
    assert len(found) == 1, f"expected one face with normal {normal}, found {len(found)}"
    ref = reference_for(body, found[0])
    plane = face_plane(found[0])
    assert ref is not None and plane is not None
    return ref, plane


def edge_ref(doc: Document, test: Callable[[TopoDS_Shape], bool]) -> dict[str, Any]:
    """Reference of the one edge of the rebuilt part that passes ``test`` (TR188, D2003)."""
    from OCP.TopAbs import TopAbs_EDGE

    report = RebuildEngine().rebuild(doc)
    body = report.body
    assert body is not None
    found = []
    explorer = TopExp_Explorer(body.shape, TopAbs_EDGE)
    seen: list[TopoDS_Shape] = []
    while explorer.More():
        edge = explorer.Current()
        explorer.Next()
        if any(edge.IsSame(e) for e in seen):
            continue
        seen.append(edge)
        if test(edge):
            found.append(edge)
    assert len(found) == 1, f"expected one edge, found {len(found)}"
    ref = reference_for(body, found[0])
    assert ref is not None
    return ref


def to_local(plane: SketchPlane, p: Vec3) -> Vec:
    """Model point to sketch coordinates on ``plane``."""
    o, n, x = plane.origin, plane.normal, plane.x_dir
    y = (n[1] * x[2] - n[2] * x[1], n[2] * x[0] - n[0] * x[2], n[0] * x[1] - n[1] * x[0])
    d = (p[0] - o[0], p[1] - o[1], p[2] - o[2])
    return (
        d[0] * x[0] + d[1] * x[1] + d[2] * x[2],
        d[0] * y[0] + d[1] * y[1] + d[2] * y[2],
    )


class PointsSketch(SketchBuilder):
    """A sketch of fixed points only, for hole positions.

    It has no construction origin point, since the Hole Tool puts a hole at every
    point of the sketch it uses.
    """

    def __init__(self, points: Sequence[Vec]) -> None:
        self.sk = Sketch()
        self.origin = ""
        for x, y in points:
            self.sk.relate("fixed", self.sk.add_point(x, y))
