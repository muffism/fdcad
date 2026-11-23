"""Parting Line: the edges where faces turn from positive to negative draft (TR84, D1415).

Params: ``reverse`` (optional boolean, the pull points the other way).
Refs: ``direction``: a plane or axis feature, a flat face or a straight edge; the
pull is its normal or direction.

Each face's draft is the area weighted sine of the angle between its outward
normal and the pull, from the draft analysis triangles (D522, numpy, no loops
over triangles). Faces with no draft (square to the pull) count with the positive
side, so on an undrafted box the line runs round the bottom of the walls. The
parting edges are the edges between a positive and a negative face; they are kept
as a curve, like Projected Curve.

The result says whether the edges close into loops; open chains are listed with
the gaps between their nearest free ends. Faces with both positive and negative
draft (straddle faces) are named: the line crosses them and is not found there.
With ``split_faces`` (TR84, D1811) the straddle faces that are cylinders, cones or
spheres are split along their outline (Split Line Silhouette, D1810) first, so the
line runs across them; the part then carries the split faces.
"""

from __future__ import annotations

import math

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.TopAbs import TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureState,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.modify import edge_faces, edges_of, require_body
from fdcad.core.naming.names import NamedShape

Vec3 = tuple[float, float, float]
_TOL = 1e-6


def face_signs(body: NamedShape, pull: Vec3) -> tuple[list[tuple[TopoDS_Face, int]], list[str]]:
    """+1 or -1 for each face, and the straddle face names."""
    from fdcad.core.printing.overhang import triangles_by_face

    faces, corners, owner = triangles_by_face(body.shape)
    d = np.asarray(pull, dtype=np.float64)
    d /= np.linalg.norm(d)
    signs: list[tuple[TopoDS_Face, int]] = []
    straddle: list[str] = []
    if len(faces) == 0:
        return signs, straddle
    cross = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    area = np.linalg.norm(cross, axis=1) / 2
    dot = cross @ d / 2  # area times the sine of the draft, per triangle
    count = len(faces)
    total = np.bincount(owner, weights=area, minlength=count)
    lean = np.bincount(owner, weights=dot, minlength=count)
    up = np.bincount(owner, weights=area * (dot > _TOL * area), minlength=count)
    down = np.bincount(owner, weights=area * (dot < -_TOL * area), minlength=count)
    for i, face in enumerate(faces):
        if total[i] <= 0:
            continue
        signs.append((face, 1 if lean[i] >= -_TOL * total[i] else -1))
        if up[i] > 0.02 * total[i] and down[i] > 0.02 * total[i]:
            name = body.primary_name(face)
            if name is not None:
                straddle.append(name)
    return signs, straddle


def _sign(signs: list[tuple[TopoDS_Face, int]], face: TopoDS_Face) -> int | None:
    return next((s for f, s in signs if f.IsSame(face)), None)


def parting_edges(body: NamedShape, pull: Vec3) -> tuple[list[TopoDS_Edge], list[str]]:
    """Edges between a positive and a negative face, and the straddle face names."""
    signs, straddle = face_signs(body, pull)
    out: list[TopoDS_Edge] = []
    for edge in edges_of(body.shape):
        faces = edge_faces(body.shape, edge)
        if len(faces) != 2:
            continue
        a, b = (_sign(signs, f) for f in faces)
        if a is not None and b is not None and a != b:
            out.append(edge)
    return out, straddle


def _ends(edge: TopoDS_Edge) -> list[tuple[float, float, float]]:
    out = []
    explorer = TopExp_Explorer(edge, TopAbs_VERTEX)
    while explorer.More():
        p = BRep_Tool.Pnt_s(TopoDS.Vertex(explorer.Current()))
        out.append((p.X(), p.Y(), p.Z()))
        explorer.Next()
    return out


def free_ends(edges: list[TopoDS_Edge]) -> list[tuple[float, float, float]]:
    """End points used by only one edge: none when every chain closes."""
    points: list[tuple[tuple[float, float, float], int]] = []
    for edge in edges:
        for p in _ends(edge):
            for k, (q, n) in enumerate(points):
                if math.dist(p, q) < 1e-6:
                    points[k] = (q, n + 1)
                    break
            else:
                points.append((p, 1))
    return [p for p, n in points if n % 2 == 1]


def gaps(ends: list[tuple[float, float, float]]) -> list[float]:
    """Sizes of the gaps: free ends paired nearest first."""
    rest = list(ends)
    out: list[float] = []
    while len(rest) > 1:
        n = len(rest)
        best = min((math.dist(rest[i], rest[j]), i, j) for i in range(n) for j in range(i + 1, n))
        out.append(best[0])
        rest = [p for k, p in enumerate(rest) if k not in (best[1], best[2])]
    return out


@register
class PartingLine(FeatureType):
    """Finds the parting line of the part for a pull direction, as a curve."""

    type_name = "parting_line"
    params = (
        ParamSpec("reverse", default=False, optional=True),
        ParamSpec("split_faces", default=False, optional=True),  # TR84 (D1811)
    )

    def reads_body(self, feature: Feature) -> bool:
        """It reads the part as built so far, so its result is kept for that part only
        (D1064). Without this the result from before a change was shown again."""
        return True

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Find the parting edges; the part is unchanged."""
        from fdcad.core.features.curves import curve_result
        from fdcad.core.features.projected_curve import pick_direction
        from fdcad.core.features.solids import compound

        body = require_body(feature, ctx)
        pull = pick_direction(feature, ctx, "direction")
        if pull is None:
            raise FeatureError(
                f"{feature.name}: no pull direction is picked. "
                "Pick a plane, a flat face or a straight edge."
            )
        if feature.params.get("reverse") is True:
            pull = (-pull[0], -pull[1], -pull[2])
        edges, straddle = parting_edges(body, pull)
        split_issues: list[Issue] = []
        if straddle and feature.params.get("split_faces") is True:  # TR84 (D1811)
            body, split_issues = _split_straddle(feature, body, straddle, pull)
            edges, straddle = parting_edges(body, pull)
        if not edges:
            more = f" Faces {', '.join(straddle)} have both kinds of draft." if straddle else ""
            raise FeatureError(
                f"{feature.name}: no edge parts positive from negative draft. "
                f"Pick another pull direction, or add draft first.{more}"
            )
        result = curve_result(ctx, compound(edges))
        result.body = body
        result.issues.extend(split_issues)
        ends = free_ends(edges)
        if ends:
            sizes = ", ".join(f"{g:.3g} mm" for g in gaps(ends)) or "one free end"
            result.issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{feature.name}: the parting line is broken ({len(ends)} free ends, gaps "
                    f"{sizes}). Add draft to the faces at the gaps, or split them.",
                    highlight=straddle,
                )
            )
        result.extras["parting_closed"] = not ends
        if straddle and not ends:
            result.issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{feature.name}: faces {', '.join(straddle)} have both kinds of draft. "
                    "Check the line there.",
                    highlight=straddle,
                )
            )
        return result


def _split_straddle(
    feature: Feature, body: NamedShape, straddle: list[str], pull: Vec3
) -> tuple[NamedShape, list[Issue]]:
    """Split the straddle faces along their outline (TR84, D1811). Faces with no flat
    outline stay whole and are named in a warning."""
    from fdcad.core.features.curves import edges_in
    from fdcad.core.features.silhouette import silhouette_plane
    from fdcad.core.features.split_line import split_with
    from fdcad.core.occ import BRepAlgoAPI_Section

    faces: list[TopoDS_Face] = []
    edges: list[TopoDS_Edge] = []
    left: list[str] = []
    for name in straddle:
        face = body.face(name)
        if face is None:
            continue
        try:
            plane = silhouette_plane(face, pull)
        except ValueError:
            left.append(name)
            continue
        if plane is None:
            continue
        section = BRepAlgoAPI_Section(face, plane)
        section.Build()
        if section.IsDone():
            faces.append(face)
            edges += edges_in(section.Shape())
    issues: list[Issue] = []
    if left:
        issues.append(
            Issue(
                FeatureState.WARNING,
                f"{feature.name}: faces {', '.join(left)} were not split: only cylinders, "
                "cones and spheres can be split along their outline. Split them with a "
                "Split Line first.",
                highlight=left,
            )
        )
    if not edges:
        return body, issues
    return split_with(feature, body, faces, edges), issues
