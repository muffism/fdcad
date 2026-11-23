"""Add Loft Section: a new profile between two profiles of a loft (TR136 item 3, D2404).

The section sits at ``position``: 1.5 is halfway between profiles 1 and 2. Both
neighbours must be sketches on parallel planes. A reference plane is made at that
place (an offset of the first neighbour's plane) and a sketch on it holds the loft's
own cross section there, so the loft keeps its shape until the user edits the new
sketch: straight edges become lines, full circles circles, other curves short lines
through points along them. The loft takes the sketch as a profile in that place. No Qt.
"""

from __future__ import annotations

import math
from itertools import pairwise
from typing import Any

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import BuildContext, FeatureError, FeatureResult
from fdcad.core.sketch.model import Line, Sketch, sketch_to_data
from fdcad.core.sketch.profiles import SketchPlane

#: Straight pieces a curved section edge is drawn with.
PIECES = 12
_TOL = 1e-6


def _sketch_plane(loft: Feature, k: int, results: dict[str, FeatureResult]) -> tuple[str, Any]:
    refs = loft.refs.get("profiles") or []
    ref = refs[k - 1] if 0 < k <= len(refs) else None
    fid = ref.get("feature") if isinstance(ref, dict) and "kind" not in ref else None
    result = results.get(fid) if isinstance(fid, str) else None
    if result is None or result.sketch is None:
        raise FeatureError(
            f"{loft.name}: profile {k} is not a sketch, so a section cannot be placed by it. "
            "Pick a position between two sketch profiles."
        )
    return str(fid), result.sketch.plane


def section_plane(
    loft: Feature, position: float, results: dict[str, FeatureResult]
) -> tuple[str, float, SketchPlane]:
    """The neighbour sketch before the section, the offset from its plane (mm, along its
    normal) and the section's plane. Raises FeatureError with a next step."""
    count = len(loft.refs.get("profiles") or [])
    k = math.floor(position)
    fraction = position - k
    if not 1 <= k < count or fraction < 0.01 or fraction > 0.99:
        raise FeatureError(
            f"{loft.name}: the position must lie between two profiles, such as 1.5 for "
            f"halfway between profiles 1 and 2. Enter a number from 1.01 to {count - 0.01:g}."
        )
    first, a = _sketch_plane(loft, k, results)
    _second, b = _sketch_plane(loft, k + 1, results)
    dot = sum(x * y for x, y in zip(a.normal, b.normal, strict=True))
    if abs(abs(dot) - 1.0) > 1e-6:
        raise FeatureError(
            f"{loft.name}: profiles {k} and {k + 1} are not on parallel planes. Add the section "
            "between two parallel profiles."
        )
    gap = sum((q - p) * n for p, q, n in zip(a.origin, b.origin, a.normal, strict=True))
    offset = fraction * gap
    origin = tuple(p + offset * n for p, n in zip(a.origin, a.normal, strict=True))
    return first, offset, SketchPlane(origin, a.normal, a.x_dir)


def section_sketch(shape: Any, plane: SketchPlane) -> Sketch:
    """The cross section of ``shape`` on ``plane`` as a sketch of lines and circles."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Line
    from OCP.gp import gp_Pln
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    from fdcad.core.occ import BRepAlgoAPI_Section

    cut = BRepAlgoAPI_Section(shape, gp_Pln(plane.ax3()), True)
    sketch = Sketch()
    points: dict[tuple[int, int], str] = {}

    def point(x: float, y: float) -> str:
        key = (round(x * 1e4), round(y * 1e4))
        if key not in points:
            points[key] = sketch.add_point(x, y)
        return points[key]

    def uv(p: Any) -> tuple[float, float]:
        u, v, _h = plane.to_2d(p.X(), p.Y(), p.Z())
        return u, v

    explorer = TopExp_Explorer(cut.Shape(), TopAbs_EDGE)
    while explorer.More():
        curve = BRepAdaptor_Curve(TopoDS.Edge(explorer.Current()))
        explorer.Next()
        t0, t1 = curve.FirstParameter(), curve.LastParameter()
        start, end = uv(curve.Value(t0)), uv(curve.Value(t1))
        closed = math.dist(start, end) < _TOL
        if curve.GetType() == GeomAbs_Circle and closed:
            centre = uv(curve.Circle().Location())
            sketch.add_circle(centre[0], centre[1], curve.Circle().Radius())
            continue
        steps = 1 if curve.GetType() == GeomAbs_Line or _straight(curve, uv) else PIECES
        ids = [point(*uv(curve.Value(t0 + (t1 - t0) * i / steps))) for i in range(steps + 1)]
        for p, q in pairwise(ids):
            if p != q:
                eid = sketch.new_id()
                sketch.entities[eid] = Line(eid, p, q)
    from fdcad.core.sketch.model import Circle

    if not any(isinstance(e, Line | Circle) for e in sketch.entities.values()):
        raise FeatureError("The loft does not reach the section's place. Pick another position.")
    return sketch


def _straight(curve: Any, uv: Any) -> bool:
    """True when the curve stays on its chord (a loft between straight sides)."""
    t0, t1 = curve.FirstParameter(), curve.LastParameter()
    a, b = uv(curve.Value(t0)), uv(curve.Value(t1))
    chord = math.dist(a, b)
    if chord < _TOL:
        return False
    for i in range(1, 8):
        p = uv(curve.Value(t0 + (t1 - t0) * i / 8))
        cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        if abs(cross) / chord > 1e-4:
            return False
    return True


def add_loft_section(
    doc: Document, fid: str, position: float, results: dict[str, FeatureResult]
) -> tuple[Feature, Feature]:
    """A reference plane and a sketch for a new section of loft ``fid`` at ``position``.
    The document is not changed; :func:`insert_section` puts them in. Raises FeatureError."""
    from fdcad.core.features import REGISTRY
    from fdcad.core.features.preview import body_before

    loft = doc.feature(fid)
    if loft.type != "loft":
        raise FeatureError(
            f"{loft.name} is not a loft. Pick a loft in the feature tree to add a section."
        )
    first, offset, plane = section_plane(loft, position, results)
    ctx = BuildContext(doc, body_before(doc, loft, results), results, {})
    tool = REGISTRY["loft"].tool(loft, ctx)
    if tool is None:
        raise FeatureError(f"{loft.name} has no solid yet. Fix the loft first.")
    sketch = section_sketch(tool.shape, plane)
    base = doc.feature(first).refs.get("plane")
    flip = offset < 0
    pid = doc.new_feature_id()
    ref_plane = Feature(
        pid,
        "ref_plane",
        f"{loft.name} section plane",
        params={
            "method": "offset",
            "distance": Param(f"{abs(offset):.6g} mm", abs(offset)),
            "flip": flip,
        },
        refs={"first": dict(base) if isinstance(base, dict) else {"feature": "f2"}},
    )
    sid = doc.new_feature_id()
    new_sketch = Feature(
        sid,
        "sketch",
        f"{loft.name} section",
        refs={"plane": {"feature": pid}},
        data=sketch_to_data(sketch),
    )
    return ref_plane, new_sketch


def insert_section(
    doc: Document, fid: str, position: float, plane: Feature, sketch: Feature
) -> None:
    """Put ``plane`` and ``sketch`` just before loft ``fid`` and make the sketch the
    profile after ``floor(position)``; connection points of later profiles move along."""
    loft = doc.feature(fid)
    k = math.floor(position)
    index = next(i for i, f in enumerate(doc.features) if f.id == fid)
    doc.features[index:index] = [plane, sketch]
    profiles = list(loft.refs.get("profiles") or [])
    profiles.insert(k, {"feature": sketch.id})
    loft.refs["profiles"] = profiles
    for prefix in ("connect_", "match_"):
        moved = {}
        for key in [p for p in loft.params if p.startswith(prefix)]:
            n = key[len(prefix) :]
            if n.isdigit():
                value = loft.params.pop(key)
                moved[f"{prefix}{int(n) + 1 if int(n) > k else int(n)}"] = value
        loft.params.update(moved)
