"""Remove Fillets: find round faces on any body and remove or resize them (TR260, D1410).

For bodies with no history (an imported part), where there is no fillet feature
to edit. Params:

- ``min_radius`` and ``max_radius``: optional lengths, only rounds in this range.
- ``new_radius``: optional length. Without it the rounds are removed; with it they
  are removed and the edges they leave are rounded again at this radius.

Refs: ``faces`` (optional): the round faces to treat. Without picks every round in
the range is found.

A round is a cylinder, torus or sphere face that meets at least two neighbours
smoothly and is not a whole turn (so holes and shafts are never found). Its
radius is the cylinder radius, the torus tube radius or the sphere radius.
Rounds are removed smallest first (the reverse of the order they are usually
made), a few at a time; a batch that fails is tried one face at a time, and faces
that still fail stay and are named in a warning.

Face roles: kept faces keep their names; new rounds are ``fillet/<edge name>``.
"""

from __future__ import annotations

import math

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepOffset import BRepOffset_Analyse
from OCP.ChFiDS import ChFiDS_Tangential
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Sphere, GeomAbs_Torus
from OCP.TopoDS import TopoDS_Face

from fdcad.core.document.model import Feature, Param
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
from fdcad.core.features.solids import check_result
from fdcad.core.naming.names import NamedShape, faces_of
from fdcad.core.units import Kind

#: Rounds removed in one kernel call.
BATCH = 4


def round_radius(face: TopoDS_Face) -> float | None:
    """The radius of a cylinder, torus (tube) or sphere face, else None."""
    surface = BRepAdaptor_Surface(face)
    kind = surface.GetType()
    if kind == GeomAbs_Cylinder:
        if surface.LastUParameter() - surface.FirstUParameter() > 2 * math.pi - 1e-6:
            return None  # a whole turn: a hole or a shaft, not a round
        return float(surface.Cylinder().Radius())
    if kind == GeomAbs_Torus:
        return float(surface.Torus().MinorRadius())
    if kind == GeomAbs_Sphere:
        return float(surface.Sphere().Radius())
    return None


def find_rounds(
    body: NamedShape, low: float | None = None, high: float | None = None
) -> list[tuple[str, TopoDS_Face, float]]:
    """Every round face of ``body`` in the radius range, smallest first."""
    analyse = BRepOffset_Analyse(body.shape, 0.01)
    out: list[tuple[str, TopoDS_Face, float]] = []
    for face in faces_of(body.shape):
        radius = round_radius(face)
        if radius is None:
            continue
        if (low is not None and radius < low - 1e-9) or (high is not None and radius > high + 1e-9):
            continue
        smooth = sum(
            1
            for edge in edges_of(face)
            if any(iv.Type() == ChFiDS_Tangential for iv in analyse.Type(edge))
        )
        if smooth < 2:
            continue
        name = body.primary_name(face)
        if name is not None:
            out.append((name, face, radius))
    out.sort(key=lambda item: (item[2], item[0]))
    return out


def _neighbours(body: NamedShape, face: TopoDS_Face) -> list[str]:
    """The faces a round joins smoothly (not the faces at its ends)."""
    analyse = BRepOffset_Analyse(body.shape, 0.01)
    names: list[str] = []
    for edge in edges_of(face):
        if not any(iv.Type() == ChFiDS_Tangential for iv in analyse.Type(edge)):
            continue
        for other in edge_faces(body.shape, edge):
            if other.IsSame(face):
                continue
            name = body.primary_name(other)
            if name is not None and name not in names:
                names.append(name)
    return names


def _length(feature: Feature, name: str) -> float | None:
    value = feature.params.get(name)
    return value.value if isinstance(value, Param) else None


@register
class RemoveFillets(FeatureType):
    """Removes round faces from a body, or makes them again at a new radius."""

    type_name = "remove_fillets"
    makes_solid = True
    params = (
        ParamSpec("min_radius", kind=Kind.LENGTH, optional=True),
        ParamSpec("max_radius", kind=Kind.LENGTH, optional=True),
        ParamSpec("new_radius", kind=Kind.LENGTH, optional=True),
        ParamSpec("use_range", default=False, optional=True),  # panel ticks
        ParamSpec("resize", default=False, optional=True),
    )

    def _targets(
        self, feature: Feature, ctx: BuildContext, body: NamedShape
    ) -> tuple[list[tuple[str, TopoDS_Face, float]], list[Issue]]:
        ranged = feature.params.get("use_range", True) is not False
        low = _length(feature, "min_radius") if ranged else None
        high = _length(feature, "max_radius") if ranged else None
        found = find_rounds(body, low, high)
        issues: list[Issue] = []
        if feature.refs.get("faces"):
            from fdcad.core.features.modify import resolve_faces

            picked, issues = resolve_faces(feature, ctx, "faces")
            found = [r for r in found if any(r[1].IsSame(f) for _n, f in picked)]
        if not found:
            raise FeatureError(
                f"{feature.name}: no round faces were found in the radius range. "
                "Widen the range, or pick round faces."
            )
        return found, issues

    def _remove(
        self, feature: Feature, body: NamedShape, rounds: list[tuple[str, TopoDS_Face, float]]
    ) -> tuple[NamedShape, list[str], list[str]]:
        """Remove the rounds in batches; returns the body, removed and kept names."""
        from fdcad.core.features.direct import patch

        current = body
        removed: list[str] = []
        kept: list[str] = []
        names = [n for n, _f, _r in rounds]
        for start in range(0, len(names), BATCH):
            batch = names[start : start + BATCH]
            faces = [current.face(n) for n in batch]
            usable = [(n, f) for n, f in zip(batch, faces, strict=True) if f is not None]
            try:
                current = patch(
                    current, [f for _n, f in usable], feature.id, feature.name,
                    [n for n, _f in usable],
                )  # fmt: skip
                removed += [n for n, _f in usable]
                continue
            except FeatureError:
                pass
            for name, _face in usable:  # one at a time
                face = current.face(name)
                if face is None:
                    continue
                try:
                    current = patch(current, [face], feature.id, feature.name, [name])
                    removed.append(name)
                except FeatureError:
                    kept.append(name)
        return current, removed, kept

    def _build(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        body = require_body(feature, ctx)
        rounds, issues = self._targets(feature, ctx, body)
        pairs = {n: _neighbours(body, f) for n, f, _r in rounds}
        result, removed, kept = self._remove(feature, body, rounds)
        if not removed:
            raise FeatureError(
                f"{feature.name}: none of the {len(kept)} rounds could be removed. "
                "Pick fewer rounds, or remove the ones next to them first.",
                highlight=kept,
            )
        if kept:
            issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{feature.name}: {len(kept)} round{'s' if len(kept) != 1 else ''} could "
                    f"not be removed and stay: {', '.join(kept)}. Pick them on their own to "
                    "see why.",
                    highlight=kept,
                )
            )
        new = _length(feature, "new_radius")
        if new is not None and feature.params.get("resize", True) is not False:
            result = self._resize(feature, result, [pairs[n] for n in removed], new)
        return result, issues

    def _resize(
        self, feature: Feature, body: NamedShape, pairs: list[list[str]], radius: float
    ) -> NamedShape:
        """Round again the edges between the faces each removed round joined."""
        from fdcad.core.features.fillet import Item, round_edges

        if radius <= 0:
            raise FeatureError(f"{feature.name}: the new radius must be above zero. Enter one.")
        items: list[Item] = []
        for names in pairs:
            for i, a in enumerate(names):
                for b in names[i + 1 :]:
                    for edge in body.edges(f"edge({'|'.join(sorted([a, b]))})"):
                        if not any(edge.IsSame(x.edge) for x in items):
                            name = body.edge_name(edge) or f"edge({a}|{b})"
                            items.append(Item(name, edge, 0))
        if not items:
            return body
        made = round_edges(feature.id, body, items, lambda _i: [(0.0, radius), (1.0, radius)])
        if made is None:
            raise FeatureError(
                f"{feature.name}: the rounds could not be made again at {radius:g} mm. "
                "Use a smaller new radius, or remove the rounds without a new radius."
            )
        return made

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Remove (and maybe resize) the rounds."""
        result, issues = self._build(feature, ctx)
        issues = issues + check_result(feature.id, feature.name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)
