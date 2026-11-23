"""Flat pattern DXF and SVG output options (TR173, DECISIONS D1108).

``FlatOutput`` says which items a 2D flat pattern file holds (outline, bend lines,
cross break and form marks, the box), where its origin is and which way its axes
run, the DXF colours of up and down bend lines, and single items left out after a
look at the preview. ``apply_output`` turns a ``FlatDrawing`` into the drawing to
write. Pure Python, so it is tested on its own.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field, replace

from fdcad.core.features.sheetmetal.export import ArcPiece, BendMark, FlatDrawing, Segment, Vec2

ORIGINS = ("part", "lower_left", "centre")


@dataclass(frozen=True)
class FlatOutput:
    """What a flat pattern drawing file holds and how it is placed."""

    outline: bool = True
    bend_lines: bool = True
    marks: bool = True
    box: bool = True
    origin: str = "part"  # the part's own origin, the lower left of the outline, or its centre
    flip_x: bool = False
    flip_y: bool = False
    rotate: float = 0.0  # degrees, counter clockwise, applied before the origin move
    up_colour: int = 1  # DXF colour numbers (1 red, 5 blue)
    down_colour: int = 5
    #: Items taken out in the preview: ("bend", index) or ("mark", index).
    removed: frozenset[tuple[str, int]] = field(default_factory=frozenset)


def preview_items(drawing: FlatDrawing) -> list[tuple[str, int, str]]:
    """The items the preview lists one by one: kind, index and a label."""
    out: list[tuple[str, int, str]] = []
    for k, bend in enumerate(drawing.bends):
        out.append(("bend", k, f"Bend {k + 1}: {bend.direction} {bend.angle:g} degrees"))
    for k, (_seg, title) in enumerate(drawing.marks):
        out.append(("mark", k, f"Mark {k + 1}: {title}"))
    return out


def _turn(p: Vec2, c: float, s: float) -> Vec2:
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def _map_drawing(
    drawing: FlatDrawing, move: Callable[[Vec2], Vec2], angle_shift: float, mirror: bool
) -> FlatDrawing:
    """``drawing`` with every point moved by ``move``; arcs turned by ``angle_shift``
    degrees, and their start and end swapped when ``mirror``."""
    outline: list[Segment | ArcPiece] = []
    for item in drawing.outline:
        if isinstance(item, Segment):
            outline.append(Segment(move(item.a), move(item.b)))
            continue
        start, end = item.start + angle_shift, item.end + angle_shift
        if mirror and not item.full:
            start, end = end, start
        outline.append(ArcPiece(move(item.centre), item.radius, start % 360.0, end % 360.0))
    bends = [replace(b, a=move(b.a), b=move(b.b)) for b in drawing.bends]
    marks = [(Segment(move(s.a), move(s.b)), t) for s, t in drawing.marks]
    box = [move(p) for p in drawing.box]
    engraving = [Segment(move(s.a), move(s.b)) for s in drawing.engraving]
    return FlatDrawing(outline, bends, box, marks, engraving)


def apply_output(drawing: FlatDrawing, options: FlatOutput) -> FlatDrawing:
    """The drawing as ``options`` asks: items kept, turned, mirrored and moved."""
    bends: list[BendMark] = []
    if options.bend_lines:
        bends = [b for k, b in enumerate(drawing.bends) if ("bend", k) not in options.removed]
    marks: list[tuple[Segment, str]] = []
    if options.marks:
        marks = [m for k, m in enumerate(drawing.marks) if ("mark", k) not in options.removed]
    out = FlatDrawing(
        list(drawing.outline) if options.outline else [],
        bends,
        list(drawing.box) if options.box else [],
        marks,
        list(drawing.engraving) if options.outline else [],
    )
    if options.rotate:
        c, s = math.cos(math.radians(options.rotate)), math.sin(math.radians(options.rotate))
        out = _map_drawing(out, lambda p: _turn(p, c, s), options.rotate, False)
    if options.flip_x:
        out = _map_drawing(out, lambda p: (-p[0], p[1]), 0.0, True)
        out = _mirror_arcs(out, 90.0)
    if options.flip_y:
        out = _map_drawing(out, lambda p: (p[0], -p[1]), 0.0, True)
        out = _mirror_arcs(out, 0.0)
    if options.origin != "part":
        x0, y0, x1, y1 = out.extent()
        if options.origin == "lower_left":
            dx, dy = -x0, -y0
        else:
            dx, dy = -(x0 + x1) / 2, -(y0 + y1) / 2
        out = _map_drawing(out, lambda p: (p[0] + dx, p[1] + dy), 0.0, False)
    return out


def _mirror_arcs(drawing: FlatDrawing, axis: float) -> FlatDrawing:
    """Arc angles reflected about the line at ``axis`` degrees (after the points moved)."""
    outline: list[Segment | ArcPiece] = []
    for item in drawing.outline:
        if isinstance(item, ArcPiece) and not item.full:
            # _map_drawing already swapped start and end; reflect each angle.
            outline.append(
                ArcPiece(
                    item.centre,
                    item.radius,
                    (2 * axis - item.start) % 360.0,
                    (2 * axis - item.end) % 360.0,
                )
            )
        else:
            outline.append(item)
    return FlatDrawing(outline, drawing.bends, drawing.box, drawing.marks, drawing.engraving)
