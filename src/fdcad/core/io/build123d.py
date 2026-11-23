"""One way export of a part as a build123d Python script (PLAN Phase 5, D342).

The script rebuilds the sketches, extrudes and revolves of the part with the
build123d library. Every other feature, and every option build123d cannot
take directly, is written as a comment that says what was left out. Lengths
are millimetres; sketch planes are written out in full, as the rebuild placed
them, so sketches on faces land where they should.

The script is text only: FDCAD never runs it (CLAUDE.md rule 10).
"""

from __future__ import annotations

import math

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.engine import RebuildEngine, RebuildReport
from fdcad.core.sketch.model import Arc, Circle, Line, Sketch
from fdcad.core.sketch.profiles import SketchPlane

_BUILT_IN = {"origin", "plane"}
_JOIN = 1e-6

Point2 = tuple[float, float]


def _n(x: float) -> str:
    """A number as short, exact enough text (9 significant digits)."""
    text = f"{x:.9g}"
    return "0" if text in ("-0", "0", "-0.0") else text


def _v(p: tuple[float, ...]) -> str:
    return "(" + ", ".join(_n(c) for c in p) + ")"


def _var(fid: str) -> str:
    return f"sketch_{fid}"


def _plane(plane: SketchPlane) -> str:
    return f"Plane(origin={_v(plane.origin)}, x_dir={_v(plane.x_dir)}, z_dir={_v(plane.normal)})"


def _loops(sketch: Sketch) -> list[list[Line | Arc]]:
    """Lines and arcs grouped into joined chains, in entity order."""
    curves = [c for c in sketch.curves() if isinstance(c, Line | Arc)]

    def ends(c: Line | Arc) -> tuple[Point2, Point2]:
        a, b = (c.p1, c.p2) if isinstance(c, Line) else (c.start, c.end)
        return sketch.xy(a), sketch.xy(b)

    def near(p: Point2, q: Point2) -> bool:
        return math.hypot(p[0] - q[0], p[1] - q[1]) < _JOIN

    loops: list[list[Line | Arc]] = []
    left = list(curves)
    while left:
        loop = [left.pop(0)]
        grew = True
        while grew:
            grew = False
            for c in list(left):
                if any(near(p, q) for p in ends(c) for x in loop for q in ends(x)):
                    loop.append(c)
                    left.remove(c)
                    grew = True
        loops.append(loop)
    return loops


def _polygon(sketch: Sketch, loop: list[Line | Arc]) -> list[Point2]:
    out: list[Point2] = []
    for c in loop:
        if isinstance(c, Line):
            out.append(sketch.xy(c.p1))
        else:
            out.append(sketch.xy(c.start))
    return out


def _inside(p: Point2, poly: list[Point2]) -> bool:
    """Even odd rule: True when ``p`` is inside the polygon."""
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1], strict=True):
        if (y1 > p[1]) != (y2 > p[1]):
            x = x1 + (p[1] - y1) * (x2 - x1) / (y2 - y1)
            if x > p[0]:
                hit = not hit
    return hit


def _sketch_lines(fid: str, name: str, sketch: Sketch, plane: SketchPlane) -> list[str]:
    """A BuildSketch block for one sketch."""
    out = [f"# {name}", f"with BuildSketch({_plane(plane)}) as {_var(fid)}:"]
    loops = _loops(sketch)
    polygons = [_polygon(sketch, loop) for loop in loops]
    body: list[str] = []
    for k, loop in enumerate(loops):
        first = polygons[k][0] if polygons[k] else (0.0, 0.0)
        holes = sum(_inside(first, polygons[j]) for j in range(len(loops)) if j != k)
        mode = "Mode.SUBTRACT" if holes % 2 else "Mode.ADD"
        body.append("    with BuildLine():")
        for c in loop:
            if isinstance(c, Line):
                body.append(f"        Line({_v(sketch.xy(c.p1))}, {_v(sketch.xy(c.p2))})")
            else:
                centre = sketch.xy(c.center)
                radius = sketch.radius(c.id)
                sx, sy = sketch.xy(c.start)
                ex, ey = sketch.xy(c.end)
                a0 = math.degrees(math.atan2(sy - centre[1], sx - centre[0]))
                a1 = math.degrees(math.atan2(ey - centre[1], ex - centre[0]))
                sweep = (a1 - a0) % 360.0 if c.ccw else -((a0 - a1) % 360.0)
                body.append(f"        CenterArc({_v(centre)}, {_n(radius)}, {_n(a0)}, {_n(sweep)})")
        body.append(f"    make_face(mode={mode})")
    for circle in (c for c in sketch.curves() if isinstance(c, Circle)):
        centre = sketch.xy(circle.center)
        holes = sum(_inside(centre, poly) for poly in polygons)
        mode = "Mode.SUBTRACT" if holes % 2 else "Mode.ADD"
        body.append(f"    with Locations({_v(centre)}):")
        body.append(f"        Circle({_n(circle.radius)}, mode={mode})")
    if not body:
        body.append("    pass  # the sketch has no curves")
    return out + body + [""]


def _num(feature: Feature, name: str, default: float = 0.0) -> float:
    value = feature.params.get(name)
    return value.value if isinstance(value, Param) else default


def _extrude(feature: Feature, plane: SketchPlane, sketch_fid: str, size: float) -> list[str]:
    params = feature.params
    mode = "Mode.SUBTRACT" if params.get("operation") == "cut" else "Mode.ADD"
    n = plane.normal
    sign = -1.0 if params.get("reverse") else 1.0
    forward = (n[0] * sign, n[1] * sign, n[2] * sign)
    back = (-forward[0], -forward[1], -forward[2])
    target = f"{_var(sketch_fid)}.sketch"
    end = str(params.get("end_condition", "blind"))
    out: list[str] = []
    skipped: list[str] = [
        k
        for k in ("start_condition", "end_condition2", "draft_angle", "thin_type", "cut_outside")
        if k in params and params.get(k) not in (None, False, "sketch_plane")
    ]
    if "regions" in feature.refs:
        skipped.append("selected regions (the whole sketch is used)")
    if end == "mid_plane":
        half = _n(_num(feature, "depth") / 2)
        out.append(f"    extrude({target}, amount={half}, both=True, mode={mode})")
    elif end in ("blind", "two_directions"):
        depth = _n(_num(feature, "depth"))
        out.append(f"    extrude({target}, amount={depth}, dir={_v(forward)}, mode={mode})")
        if end == "two_directions":
            out.append(
                f"    extrude({target}, amount={_n(_num(feature, 'depth2'))}, dir={_v(back)}, "
                f"mode={mode})"
            )
    elif end == "through_all":
        out.append(f"    # Through All, written as a long extrude of {_n(size)} mm.")
        out.append(f"    extrude({target}, amount={_n(size)}, dir={_v(forward)}, mode={mode})")
    else:
        return [f"    # Not exported: end condition {end} has no direct build123d equivalent."]
    if skipped:
        out.insert(0, f"    # Not exported: {', '.join(skipped)}.")
    return out


def _revolve(feature: Feature, plane: SketchPlane, sketch: Sketch, sketch_fid: str) -> list[str]:
    params = feature.params
    axis = feature.refs.get("axis")
    entity = axis.get("sketch_entity") if isinstance(axis, dict) else None
    line = sketch.entities.get(str(entity)) if entity else None
    if not isinstance(line, Line):
        return ["    # Not exported: the revolve axis is not a line of its sketch."]
    a, b = plane.to_3d(*sketch.xy(line.p1)), plane.to_3d(*sketch.xy(line.p2))
    origin = (a.X(), a.Y(), a.Z())
    direction = (b.X() - a.X(), b.Y() - a.Y(), b.Z() - a.Z())
    if "thin_type" in params:
        return ["    # Not exported: revolve Thin Feature."]
    mode = "Mode.SUBTRACT" if params.get("operation") == "cut" else "Mode.ADD"
    angle = math.degrees(_num(feature, "angle", 2 * math.pi))
    end = str(params.get("end_condition", "blind"))
    if end == "through_all":
        angle = 360.0
    elif end != "blind":
        return [f"    # Not exported: revolve end condition {end}."]
    if params.get("reverse"):
        angle = -angle
    if params.get("direction", "one_direction") != "one_direction":
        return ["    # Not exported: mid plane and two direction revolves."]
    return [
        f"    revolve({_var(sketch_fid)}.sketch, axis=Axis({_v(origin)}, {_v(direction)}), "
        f"revolution_arc={_n(angle)}, mode={mode})"
    ]


def script_for(doc: Document, title: str = "Part", report: RebuildReport | None = None) -> str:
    """The build123d script of ``doc``. Rebuilds the part when no ``report`` is given."""
    report = report or RebuildEngine().rebuild(doc)
    size = 1000.0
    if report.body is not None:
        from fdcad.core.features.solids import bounding_size

        size = 2 * bounding_size(report.body.shape) + 10.0
    head = [
        f'"""{title}, exported from FDCAD as a build123d script (one way).',
        "",
        "Lengths are millimetres and angles degrees. Features build123d cannot",
        "make directly are written as comments.",
        '"""',
        "",
        "from build123d import *  # noqa: F403",
        "",
    ]
    for var in doc.variables:
        head.append(f"# Variable {var.name} = {var.expr} ({_n(var.value)})")
    if doc.variables:
        head.append("")
    sketches: list[str] = []
    part: list[str] = ["with BuildPart() as part:"]
    for feature in doc.features:
        if feature.suppressed or feature.type in _BUILT_IN:
            continue
        result = report.results.get(feature.id)
        if result is None:
            part.append(f"    # Not exported: {feature.name} is rolled back.")
            continue
        if result.state is FeatureState.ERROR:
            part.append(f"    # Not exported: {feature.name} has an error in FDCAD.")
            continue
        if feature.type == "sketch" and result.sketch is not None:
            sketches += _sketch_lines(
                feature.id, feature.name, result.sketch.model, result.sketch.plane
            )
            continue
        ref = feature.refs.get("sketch")
        sid = ref.get("feature") if isinstance(ref, dict) else None
        source = report.results.get(str(sid)) if isinstance(sid, str) else None
        out_sketch = source.sketch if source is not None else None
        part.append(f"    # {feature.name}")
        if feature.type == "extrude" and out_sketch is not None:
            part += _extrude(feature, out_sketch.plane, str(sid), size)
        elif feature.type == "revolve" and out_sketch is not None:
            part += _revolve(feature, out_sketch.plane, out_sketch.model, str(sid))
        else:
            part.append(
                f"    # Not exported: {feature.type} features have no build123d equivalent here."
            )
    if not any(not line.strip().startswith("#") for line in part[1:]):
        part.append("    pass  # nothing build123d can make")
    tail = ["", "result = part.part", ""]
    return "\n".join(head + sketches + part + tail)
