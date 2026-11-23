"""Merge Faces: one face where picked faces lie on one surface (TR261, DECISIONS D787).

Imports and Delete Face can leave faces split by needless edges on one surface,
and later fillets and drafts fail on such edges. Merge Faces removes the edges
between the picked faces and makes one face of them; every other edge stays.

Params:

- ``tolerance``: optional length, how far apart the faces may be and still count
  as one surface (default 0.001 mm, the kernel's own).
- ``angle_tolerance``: optional angle, how far their directions may differ
  (default 0.1 degree).

Refs: ``faces`` (two or more faces), or ``edges`` (edges between two faces: both
faces of each edge are merged).

Face roles: the merged face keeps the name of the picked face that sorts first.
"""

from __future__ import annotations

import math

from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.modify import require_body, resolve_edges, resolve_faces
from fdcad.core.features.solids import check_result
from fdcad.core.naming.names import NamedShape, carry, restrict
from fdcad.core.units import Kind

DEFAULT_TOLERANCE = 0.001
DEFAULT_ANGLE = math.radians(0.1)


def _edges(shape: TopoDS_Shape) -> list[TopoDS_Edge]:
    out = []
    ex = TopExp_Explorer(shape, TopAbs_EDGE)
    while ex.More():
        out.append(TopoDS.Edge(ex.Current()))
        ex.Next()
    return out


def inner_edges(faces: list[TopoDS_Face]) -> list[TopoDS_Edge]:
    """The edges two of ``faces`` share."""
    out: list[TopoDS_Edge] = []
    for i, face in enumerate(faces):
        for edge in _edges(face):
            if any(edge.IsSame(e) for e in out):
                continue
            if any(any(edge.IsSame(e) for e in _edges(o)) for o in faces[i + 1 :]):
                out.append(edge)
    return out


def merge(
    body: NamedShape, faces: list[TopoDS_Face], fid: str, tolerance: float, angle: float
) -> tuple[NamedShape, int]:
    """``body`` with the edges between ``faces`` removed, and how many of those edges are
    left: 0 when the picked faces became one, -1 when they share no edge."""
    from fdcad.core.unify import unify_faces

    inner = inner_edges(faces)
    if not inner:
        return body, -1
    keep = [e for e in _edges(body.shape) if not any(e.IsSame(i) for i in inner)]
    shape, history = unify_faces(body.shape, keep, tolerance, angle)
    if history is None:
        return body, len(inner)
    left = sum(1 for e in _edges(shape) if any(e.IsSame(i) for i in inner))
    # The merged face takes the first picked name, so the picked faces go first.
    picked = [f for f in faces]
    ordered = sorted(body.faces, key=lambda nf: (not any(nf[1].IsSame(p) for p in picked), nf[0]))
    names = carry(ordered, history)
    return NamedShape(shape, restrict(names, shape, fid)), left


def _value(feature: Feature, name: str, default: float) -> float:
    value = feature.params.get(name)
    return value.value if isinstance(value, Param) and value.value > 0 else default


@register
class MergeFaces(FeatureType):
    """One face from picked faces on one surface."""

    type_name = "merge_faces"
    makes_solid = True
    params = (
        ParamSpec("tolerance", kind=Kind.LENGTH, optional=True),
        ParamSpec("angle_tolerance", kind=Kind.ANGLE, optional=True),
    )

    def _faces(self, feature: Feature, ctx: BuildContext) -> tuple[list[TopoDS_Face], list[Issue]]:
        body = require_body(feature, ctx)
        if feature.refs.get("edges"):
            from fdcad.core.features.corner_relief import faces_at

            picked, issues = resolve_edges(feature, ctx, "edges")
            faces: list[TopoDS_Face] = []
            for _name, edge in picked:
                for face in faces_at(body, edge):
                    if not any(face.IsSame(f) for f in faces):
                        faces.append(face)
            return faces, issues
        named, issues = resolve_faces(feature, ctx, "faces")
        return [f for _n, f in sorted(named, key=lambda nf: nf[0])], issues

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Merge the faces, or say why they cannot be one face."""
        body = require_body(feature, ctx)
        faces, issues = self._faces(feature, ctx)
        if len(faces) < 2:
            raise FeatureError(
                f"{feature.name}: pick two or more faces, or an edge between two faces."
            )
        tolerance = _value(feature, "tolerance", DEFAULT_TOLERANCE)
        angle = _value(feature, "angle_tolerance", DEFAULT_ANGLE)
        try:
            result, left = merge(body, faces, feature.id, tolerance, angle)
        except FeatureError:
            raise
        except Exception as exc:
            raise FeatureError(
                f"{feature.name} failed: the kernel could not merge the faces. "
                "Raise the tolerance or pick fewer faces."
            ) from exc
        if left < 0:
            raise FeatureError(
                f"{feature.name}: the picked faces do not touch. Pick faces that share an edge."
            )
        if left > 0:
            raise FeatureError(
                f"{feature.name}: the faces do not lie on one surface, so {left} edge(s) stay. "
                "Raise the tolerance, or pick only faces on one surface."
            )
        issues = issues + check_result(feature.id, feature.name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)
