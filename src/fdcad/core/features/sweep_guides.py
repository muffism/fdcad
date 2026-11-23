"""Guide curves for Sweep (TR55 items 1 and 4, DECISIONS D804).

The kernel's own guide mode keeps the section rigid (D219), so FDCAD builds a
guided sweep itself. Along the path, at evenly spaced stations, the profile is
carried with the least turning (as the twisted sweep's frame, D703), then
turned and scaled in the plane square to the path so that the points where it
touched the guides at the start land on the guides there: one guide sets the
turn and the size about the path; two guides set turn, size and place (the two
points fix a similarity). A smooth surface through the sections makes the
solid. The sweep stops where the shortest guide ends.

Kernel work: call from the rebuild (CLAUDE.md rule 2). Kernel failures become
FeatureError (rule 7).
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_CompCurve
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.GCPnts import GCPnts_AbscissaPoint
from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shape, TopoDS_Wire

from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, FeatureError, FeatureState, Issue
from fdcad.core.naming.names import NamedFace, NamedShape, restrict
from fdcad.core.occ import shape_list
from fdcad.core.sketch.profiles import Profile

#: Stations along the path; more give a closer surface and a slower build.
STATIONS = 41
#: How close a guide must come to the profile's outline to touch it (mm).
TOUCH = 1e-3
_GUIDE_SAMPLES = 240
#: A guide point this close to a section's plane lies on it (mm).
_ON_PLANE = 1e-9


@dataclass
class Guide:
    """One guide curve: its label for messages and its wire."""

    label: str
    wire: TopoDS_Wire


def guide_wires(feature: Feature, ctx: BuildContext) -> list[Guide]:
    """``refs.guides``: sketches or curves (``{"feature": id}``) or model edges, as wires."""
    from fdcad.core.features.curves import curve_of
    from fdcad.core.features.sketch_paths import sketch_chain

    refs = feature.refs.get("guides")
    if not isinstance(refs, list):
        return []
    out: list[Guide] = []
    for k, ref in enumerate(refs, start=1):
        label = f"Guide {k}"
        if not isinstance(ref, dict):
            continue
        if ref.get("kind") == "edge":
            from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeWire

            from fdcad.core.naming.resolve import resolve_edge

            edge, _issues = resolve_edge(ctx.body, ref, feature.name)
            out.append(Guide(label, BRepBuilderAPI_MakeWire(edge).Wire()))
            continue
        curve = curve_of(ctx, ref, feature.name)
        if curve is not None:
            out.append(Guide(label, curve))
            continue
        fid = ref.get("feature")
        sketch = ctx.result(str(fid)).sketch if isinstance(fid, str) else None
        if sketch is None:
            raise FeatureError(
                f"{feature.name}: {label} is not a sketch, curve or edge. Pick a sketch or a curve."
            )
        out.append(Guide(label, sketch_chain(sketch.model, sketch.plane, feature.name).wire))
    return out


def _stations(path: TopoDS_Wire) -> list[tuple[gp_Pnt, gp_Vec]]:
    curve = BRepAdaptor_CompCurve(path)
    u0, u1 = curve.FirstParameter(), curve.LastParameter()
    total = GCPnts_AbscissaPoint.Length_s(curve)
    out = []
    for i in range(STATIONS):
        if i == 0:
            u = u0
        elif i == STATIONS - 1:
            u = u1
        else:
            u = GCPnts_AbscissaPoint(curve, total * i / (STATIONS - 1), u0).Parameter()
        p, t = gp_Pnt(), gp_Vec()
        curve.D1(u, p, t)
        out.append((p, t.Normalized() if t.Magnitude() > 1e-12 else gp_Vec(0, 0, 1)))
    return out


def _carried(stations: list[tuple[gp_Pnt, gp_Vec]], x0: gp_Vec) -> list[gp_Vec]:
    """A direction square to the path at each station, turned as little as possible
    (double reflection)."""
    out = [x0]
    x = x0
    for (p0, t0), (p1, t1) in itertools.pairwise(stations):
        v1 = gp_Vec(p0, p1)
        c1 = v1.Dot(v1)
        if c1 > 1e-18:
            r = x.Subtracted(v1.Multiplied(2 * v1.Dot(x) / c1))
            tl = t0.Subtracted(v1.Multiplied(2 * v1.Dot(t0) / c1))
            v2 = t1.Subtracted(tl)
            c2 = v2.Dot(v2)
            x = r.Subtracted(v2.Multiplied(2 * v2.Dot(r) / c2)) if c2 > 1e-18 else r
        x = x.Subtracted(t1.Multiplied(x.Dot(t1)))
        x = x.Normalized() if x.Magnitude() > 1e-12 else out[-1]
        out.append(x)
    return out


def _meets(guide: Any, samples: list[float], p: gp_Pnt, t: gp_Vec, near: gp_Pnt) -> gp_Pnt | None:
    """Where the guide crosses the plane through ``p`` square to ``t``, nearest ``near``."""

    def side(u: float) -> float:
        return float(gp_Vec(p, guide.Value(u)).Dot(t))

    values = [side(u) for u in samples]
    found: list[gp_Pnt] = []
    for (ua, da), (ub, db) in itertools.pairwise(zip(samples, values, strict=True)):
        if abs(da) <= _ON_PLANE:
            found.append(guide.Value(ua))
            continue
        if da * db > 0 and abs(db) > _ON_PLANE:
            continue
        lo, hi, dlo = ua, ub, da
        for _ in range(60):
            mid = (lo + hi) / 2
            dm = side(mid)
            if dlo * dm <= 0:
                hi = mid
            else:
                lo, dlo = mid, dm
        found.append(guide.Value((lo + hi) / 2))
    if values and abs(values[-1]) <= _ON_PLANE:
        found.append(guide.Value(samples[-1]))
    if not found:
        return None
    return min(found, key=lambda q: q.Distance(near))


def _angle(a: gp_Vec, b: gp_Vec, axis: gp_Vec) -> float:
    return math.atan2(a.Crossed(b).Dot(axis), a.Dot(b))


def guided_sweep(
    feature: Feature,
    profile: Profile,
    path: TopoDS_Wire,
    up: gp_Vec,
    guides: Sequence[Guide],
) -> tuple[NamedShape, list[Issue]]:
    """Sweep ``profile`` along ``path`` shaped by one or two ``guides``."""
    owner, fid = feature.name, feature.id
    if not 1 <= len(guides) <= 2:
        raise FeatureError(f"{owner}: a sweep takes one or two guide curves. Remove the others.")
    stations = _stations(path)
    p0, t0 = stations[0]
    outline = profile.faces
    anchors: list[gp_Pnt] = []
    for guide in guides:
        start = _meets(BRepAdaptor_CompCurve(guide.wire), _samples(guide.wire), p0, t0, p0)
        touch = _touch_point(guide.wire, outline)
        if touch is None or (start is not None and start.Distance(touch) > 10 * TOUCH):
            raise FeatureError(
                f"{owner}: {guide.label} does not touch the profile. Move an end of the guide "
                "onto the profile's outline."
            )
        anchors.append(touch)
    for anchor, guide in zip(anchors, guides, strict=True):
        if gp_Vec(p0, anchor).Crossed(t0).Magnitude() < 1e-6:
            raise FeatureError(
                f"{owner}: {guide.label} starts on the path itself, so it cannot size the "
                "profile. Start the guide on the profile's outline, away from the path."
            )
    x0 = up.Subtracted(t0.Multiplied(up.Dot(t0)))
    if x0.Magnitude() < 1e-9:
        x0 = gp_Vec(t0.Crossed(gp_Vec(0, 0, 1)))
        if x0.Magnitude() < 1e-9:
            x0 = gp_Vec(t0.Crossed(gp_Vec(1, 0, 0)))
    frames = _carried(stations, x0.Normalized())
    curves = [(BRepAdaptor_CompCurve(g.wire), _samples(g.wire)) for g in guides]
    last = list(anchors)
    moves: list[gp_Trsf] = []
    stopped: str | None = None
    for (p, t), x in zip(stations, frames, strict=True):
        rigid = _rigid(p0, t0, frames[0], p, t, x)
        hits = []
        for k, (curve, samples) in enumerate(curves):
            hit = _meets(curve, samples, p, t, last[k])
            if hit is None:
                stopped = guides[k].label
                break
            hits.append(hit)
        if stopped is not None:
            break
        last = hits
        moves.append(_fit(rigid, anchors, hits, p, t, owner))
    if len(moves) < 2:
        raise FeatureError(
            f"{owner}: {stopped or 'a guide'} ends right at the start of the path. Make the "
            "guides run along the path."
        )
    issues: list[Issue] = []
    if stopped is not None:
        issues.append(
            Issue(
                FeatureState.WARNING,
                f"{owner}: the sweep stops where {stopped} ends, before the end of the path. "
                "Make the guide as long as the path to sweep all of it.",
                code="guide_short",
            )
        )
    return _loft_sections(fid, owner, profile, moves), issues


def _samples(wire: TopoDS_Wire) -> list[float]:
    curve = BRepAdaptor_CompCurve(wire)
    a, b = curve.FirstParameter(), curve.LastParameter()
    return [a + (b - a) * i / (_GUIDE_SAMPLES - 1) for i in range(_GUIDE_SAMPLES)]


def _touch_point(guide: TopoDS_Wire, faces: Sequence[Any]) -> gp_Pnt | None:
    """The point where ``guide`` touches the profile's outline, or None."""
    from OCP.BRepTools import BRepTools

    best: tuple[float, gp_Pnt] | None = None
    for face in faces:
        dist = BRepExtrema_DistShapeShape(guide, BRepTools.OuterWire_s(face))
        if not dist.IsDone() or dist.NbSolution() == 0:
            continue
        if best is None or dist.Value() < best[0]:
            best = (dist.Value(), dist.PointOnShape2(1))
    if best is None or best[0] > TOUCH:
        return None
    return best[1]


def _rigid(p0: gp_Pnt, t0: gp_Vec, x0: gp_Vec, p: gp_Pnt, t: gp_Vec, x: gp_Vec) -> gp_Trsf:
    """The rigid move taking the start frame (p0; t0, x0) to (p; t, x)."""
    from OCP.gp import gp_Ax3

    start = gp_Ax3(p0, gp_Dir(t0), gp_Dir(x0))
    here = gp_Ax3(p, gp_Dir(t), gp_Dir(x))
    trsf = gp_Trsf()
    trsf.SetDisplacement(start, here)
    return trsf


def _fit(
    rigid: gp_Trsf, anchors: list[gp_Pnt], hits: list[gp_Pnt], p: gp_Pnt, t: gp_Vec, owner: str
) -> gp_Trsf:
    """``rigid`` then a turn and scale in the section's plane (and, with two guides, a move
    in it) taking the carried anchor points onto the guides."""
    a = [anchor.Transformed(rigid) for anchor in anchors]

    def flat(v: gp_Vec) -> gp_Vec:
        return v.Subtracted(t.Multiplied(v.Dot(t)))

    if len(a) == 1:
        va, vq = flat(gp_Vec(p, a[0])), flat(gp_Vec(p, hits[0]))
        centre = p
    else:
        va, vq = flat(gp_Vec(a[0], a[1])), flat(gp_Vec(hits[0], hits[1]))
        centre = a[0]
    if va.Magnitude() < 1e-9 or vq.Magnitude() < 1e-9:
        raise FeatureError(
            f"{owner}: the guides meet each other or the path, so the profile would shrink to "
            "nothing. Keep the guides apart along the path."
        )
    turn = gp_Trsf()
    turn.SetRotation(gp_Ax1(centre, gp_Dir(t)), _angle(va, vq, t))
    scale = gp_Trsf()
    scale.SetScale(centre, vq.Magnitude() / va.Magnitude())
    shape = scale.Multiplied(turn).Multiplied(rigid)
    if len(a) == 2:
        moved = anchors[0].Transformed(shape)
        shift = gp_Trsf()
        shift.SetTranslation(flat(gp_Vec(moved, hits[0])))
        shape = shift.Multiplied(shape)
    return shape


def _loft_sections(fid: str, owner: str, profile: Profile, moves: list[gp_Trsf]) -> NamedShape:
    """A smooth solid through the moved copies of each profile face; holes are cut."""
    from fdcad.core.features.solids import FUZZY_TOLERANCE, compound
    from fdcad.core.features.sweep import _faces, _wires
    from fdcad.core.naming.names import carry
    from fdcad.core.occ import BRepAlgoAPI_Cut

    solids: list[TopoDS_Shape] = []
    names: list[NamedFace] = []
    for face in profile.faces:
        outer, holes = _wires(face)
        made = []
        for wire in [outer, *holes]:
            loft = BRepOffsetAPI_ThruSections(True, False, 1e-6)
            loft.CheckCompatibility(False)
            first_copy = None
            for move in moves:
                copy = BRepBuilderAPI_Transform(wire, move, True)
                section = TopoDS.Wire(copy.Shape())
                if first_copy is None:
                    first_copy = copy
                loft.AddWire(section)
            try:
                loft.Build()
                ok = loft.IsDone()
            except Exception:  # kernel failure
                ok = False
            if not ok or first_copy is None:
                raise FeatureError(
                    f"{owner}: the guided sweep could not be made. Use gentler guides or a "
                    "smaller profile."
                )
            made.append(loft)
            ex = TopExp_Explorer(wire, TopAbs_EDGE)
            while ex.More():
                edge = TopoDS.Edge(ex.Current())
                ex.Next()
                entity = profile.entity_of(edge)
                image = first_copy.ModifiedShape(edge)
                if entity is None or image.IsNull():
                    continue
                for side in shape_list(loft.Generated(image)):
                    if side.ShapeType() == TopAbs_FACE:
                        names.append((f"{fid}/side/{entity}", TopoDS.Face(side)))
            if wire.IsSame(outer):
                for role, shape in (
                    ("cap/start", loft.FirstShape()),
                    ("cap/end", loft.LastShape()),
                ):
                    for f in _faces(shape):
                        names.append((f"{fid}/{role}", f))
        solid = made[0].Shape()
        for hole in made[1:]:
            cut = BRepAlgoAPI_Cut(solid, hole.Shape())
            cut.SetFuzzyValue(FUZZY_TOLERANCE)
            cut.Build()
            if not cut.IsDone():
                raise FeatureError(
                    f"{owner}: the profile's holes could not follow the guides. "
                    "Change the guides or the holes slightly."
                )
            names = carry(names, cut.History())
            solid = cut.Shape()
        solids.append(solid)
    shape = solids[0] if len(solids) == 1 else compound(solids)
    return NamedShape(shape, restrict(names, shape, fid))
