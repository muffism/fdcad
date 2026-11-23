"""Rip (PHASE5_SPEC P5.6, DECISIONS D535): narrow cuts that let the sheet unfold.

Type ``rip``. Params: ``gap`` (slit width), ``flip`` (cut the other wall of an edge rip).

Refs: ``sketch`` (lines on flat faces: sketched rips), ``edges`` (edges where two
walls touch: edge rips), ``sheet_metal``. Either or both. Or ``tube_faces`` (TR174,
D1813) with ``tube_angle`` and ``tube_offset``: slits along cylinders and cones of a
plain solid, see ``tube_rip``.

Face roles: ``<fid>/slit<k>/<role>``, ``<fid>/edge<k>/<role>``.
"""

from __future__ import annotations

import math

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Pnt

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.extrude import sketch_input_raw
from fdcad.core.features.lookup import resolve_edge
from fdcad.core.features.sheetmetal.common import require_sheet, value
from fdcad.core.features.sheetmetal.locate import bounds
from fdcad.core.features.sheetmetal.model import (
    SheetModel,
    SheetResult,
    Vec2,
    box,
    oriented_box,
    unit2,
    volume,
)
from fdcad.core.features.sheetmetal.sketched_bend import wall_of
from fdcad.core.features.solids import line_ends, transform
from fdcad.core.naming.names import NamedShape
from fdcad.core.occ import BRepAlgoAPI_Common
from fdcad.core.sketch.model import Line
from fdcad.core.units import Kind

_TOL = 1e-6


@register
class Rip(FeatureType):
    """Cuts narrow slits along sketched lines, or between walls that touch."""

    type_name = "rip"
    makes_solid = True
    params = (
        ParamSpec("gap", kind=Kind.LENGTH, optional=True),
        ParamSpec("flip", default=False, optional=True),
        ParamSpec("tube_angle", kind=Kind.ANGLE, optional=True),  # TR174 (D1813)
        ParamSpec("tube_offset", kind=Kind.LENGTH, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut the rips and rebuild the sheet; tube faces (TR174, D1813) are slit as a
        plain solid."""
        if feature.refs.get("tube_faces"):
            from fdcad.core.features.sheetmetal.tube_rip import tube_rip
            from fdcad.core.features.solids import check_result

            body, found = tube_rip(feature, ctx)
            found = found + check_result(feature.id, feature.name, ctx.body, body, None)
            return FeatureResult(body=body, issues=found)
        model, issues = self.model(feature, ctx)
        return SheetResult(body=model.build(feature.id, feature.name), issues=issues, sheet=model)

    def model(self, feature: Feature, ctx: BuildContext) -> tuple[SheetModel, list[Issue]]:
        """The sheet with the rips cut."""
        name, fid = feature.name, feature.id
        model = require_sheet(feature, ctx)
        t = model.thickness
        gap = value(feature, "gap", 0.0)
        if gap <= 0:
            raise FeatureError(f"{name}: the rip gap must be greater than zero. Enter a gap.")
        has_sketch = isinstance(feature.refs.get("sketch"), dict)
        edges = feature.refs.get("edges")
        if not has_sketch and not (isinstance(edges, list) and edges):
            raise FeatureError(f"{name}: pick a sketch of rip lines or the edges to rip.")
        issues: list[Issue] = []
        if has_sketch:
            sketch = sketch_input_raw(feature, ctx)
            curves = sketch.model.curves()
            if not curves or any(not isinstance(c, Line) for c in curves):
                raise FeatureError(
                    f"{name}: a rip sketch can hold only lines. "
                    "Replace the other curves with lines."
                )
            for k, line in enumerate(curves, start=1):
                assert isinstance(line, Line)
                ends = []
                for pid in (line.p1, line.p2):
                    p = sketch.plane.to_3d(*sketch.model.xy(pid))
                    ends.append((p.X(), p.Y(), p.Z()))
                wid, a, b, _top = wall_of(model, ends[0], ends[1], name)
                d = unit2((b[0] - a[0], b[1] - a[1]))
                w: Vec2 = (-d[1], d[0])
                size = math.hypot(b[0] - a[0], b[1] - a[1])
                model.walls[wid].cuts.append(
                    oriented_box(
                        f"{fid}/slit{k}", a, w, (0.0, -gap / 2, -1.0), (size, gap / 2, t + 1.0)
                    )
                )
        if isinstance(edges, list):
            flip = feature.params.get("flip") is True
            for k, ref in enumerate(edges, start=1):
                if not isinstance(ref, dict):
                    raise FeatureError(f"{name}: an edge pick is damaged. Pick the edges again.")
                edge, found = resolve_edge(ctx.body, ref, name)
                issues.extend(found)
                self._edge_rip(model, fid, k, edge, gap, flip, name)
        return model, issues

    @staticmethod
    def _edge_rip(
        model: SheetModel, fid: str, k: int, edge: object, gap: float, flip: bool, name: str
    ) -> None:
        ends = line_ends(edge)
        if ends is None:
            raise FeatureError(f"{name}: edge {k} is not straight. Pick a straight edge.")
        mid = gp_Pnt(*((ends[0][i] + ends[1][i]) / 2 for i in range(3)))
        vertex = BRepBuilderAPI_MakeVertex(mid).Vertex()
        places = model.placements(False)
        near = []
        for wid in model.walls:
            if wid not in places:
                continue
            placed = transform(model.piece(wid), places[wid])
            if BRepExtrema_DistShapeShape(vertex, placed.shape).Value() < 1e-4:
                near.append(wid)
        if len(near) != 2:
            raise FeatureError(
                f"{name}: edge {k} is not where two walls touch. Pick an edge between two "
                "walls that meet without a bend."
            )
        options = []
        for cut_wall, other in ((near[0], near[1]), (near[1], near[0])):
            lo, hi = bounds(model.piece(other))
            grown = box(
                f"{fid}/edge{k}",
                (lo[0] - gap, lo[1] - gap, lo[2] - gap),
                (hi[0] + gap, hi[1] + gap, hi[2] + gap),
            )
            local = transform(grown, places[cut_wall].Inverted().Multiplied(places[other]))
            common = BRepAlgoAPI_Common(model.piece(cut_wall).shape, local.shape)
            removed = volume(common.Shape()) if common.IsDone() else 0.0
            options.append((removed, cut_wall, local))
        options = [o for o in options if o[0] > _TOL]
        if not options:
            raise FeatureError(
                f"{name}: the walls at edge {k} do not touch. No rip is needed. "
                "Remove that edge from the list."
            )
        options.sort(key=lambda o: o[0])
        choice = options[-1] if flip and len(options) > 1 else options[0]
        cut: NamedShape = choice[2]
        model.walls[choice[1]].cuts.append(cut)
