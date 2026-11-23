"""Fillet rules: items that find their edges again after changes (TR320, D1408).

A rule is an item in ``refs.auto_edges`` with a ``rule`` key:

- ``"attach"``: the edges where feature ``feature`` meets the earlier body.
- ``"feature"``: every edge of the faces feature ``feature`` made.
- ``"free"``: the feature's own edges, not the attach edges.
- ``"parallel"``: straight edges parallel to ``axis`` ("x", "y" or "z"), of the
  feature when ``feature`` is given, else of the whole part.

``exclude`` lists edge names the rule leaves out. ``radius`` names a length param
(``rule_radius_<n>``) with the rule's own radius; without it the fillet's radius is
used. Smooth (tangent) edges are never found by a rule. The fillet assistant items
(``convexity``, D519) are the other kind of ``auto_edges`` item.
"""

from __future__ import annotations

from OCP.TopoDS import TopoDS_Edge, TopoDS_Face

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureError
from fdcad.core.naming.names import NamedShape

RULES = ("attach", "feature", "free", "parallel")
AXES = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}


def _made(feature: Feature, body: NamedShape, fid: str) -> list[TopoDS_Face]:
    # Primary names only: a face merged with a coplanar face of an earlier feature
    # belongs to the earlier one, so its edges are not this feature's.
    made: list[TopoDS_Face] = []
    for _n, face in body.faces:
        primary = body.primary_name(face) or ""
        if primary.startswith(f"{fid}/") and not any(face.IsSame(m) for m in made):
            made.append(face)
    if not made:
        raise FeatureError(
            f"{feature.name}: feature {fid} of a fillet rule has no faces in the part now. "
            "Remove the rule or pick another feature.",
            highlight=[fid],
        )
    return made


def _all_faces_made(body: NamedShape, edge: TopoDS_Edge, made: list[TopoDS_Face]) -> bool:
    from fdcad.core.features.modify import edge_faces

    return all(any(f.IsSame(m) for m in made) for f in edge_faces(body.shape, edge))


def _parallel(edge: TopoDS_Edge, axis: tuple[float, float, float]) -> bool:
    import math

    from fdcad.core.features.solids import line_ends

    ends = line_ends(edge)
    if ends is None:
        return False
    d = [ends[1][i] - ends[0][i] for i in range(3)]
    length = math.sqrt(sum(c * c for c in d))
    if length < 1e-9:
        return False
    return abs(sum(d[i] * axis[i] for i in range(3))) / length > 1 - 1e-9


def rule_radius(feature: Feature, ref: dict[str, object]) -> float | None:
    """The rule's own radius in mm, or None to use the fillet's radius."""
    name = ref.get("radius")
    if not isinstance(name, str):
        return None
    value = feature.params.get(name)
    return value.value if isinstance(value, Param) else None


def rule_edges(
    feature: Feature, body: NamedShape, ref: dict[str, object]
) -> list[tuple[str, TopoDS_Edge]]:
    """The named edges one rule finds in ``body`` now."""
    from fdcad.core.features.fillet_faces import edges_by_convexity
    from fdcad.core.features.modify import edges_of

    rule = ref.get("rule")
    if rule not in RULES:
        raise FeatureError(f"{feature.name}: a fillet rule is damaged. Remove it and add it again.")
    fid = str(ref["feature"]) if "feature" in ref else None
    made = _made(feature, body, fid) if fid is not None else None
    if rule != "parallel" and made is None:
        raise FeatureError(
            f"{feature.name}: a fillet rule needs a feature. Remove it and add it again."
        )
    sharp = {name for c in ("convex", "concave") for name, _e in edges_by_convexity(body, c, made)}
    listed = ref.get("exclude")
    exclude = {str(n) for n in listed} if isinstance(listed, list) else set()
    axis = AXES.get(str(ref.get("axis", "z")), AXES["z"])
    candidates = edges_of(body.shape) if made is None else [e for f in made for e in edges_of(f)]
    out: list[tuple[str, TopoDS_Edge]] = []
    for edge in candidates:
        name = body.edge_name(edge)
        if name is None or name not in sharp or name in exclude:
            continue
        if any(edge.IsSame(e) for _n, e in out):
            continue
        if made is not None and rule in ("attach", "free"):
            inside = _all_faces_made(body, edge, made)
            if (rule == "attach") == inside:
                continue
        if rule == "parallel" and not _parallel(edge, axis):
            continue
        out.append((name, edge))
    return out
