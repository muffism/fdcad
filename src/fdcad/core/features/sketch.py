"""Sketch feature: solves the sketch and makes its profile (FDEF_SPEC 6).

Refs: ``plane`` is a plane feature (``{"feature": "f2"}``) or a planar face of
the part (``{"kind": "face", "name": "f6/cap/end", ...}``).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.Standard import Standard_Failure
from OCP.TopoDS import TopoDS_Face

from fdcad.core.document.model import Document, Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureState,
    FeatureType,
    Fix,
    Issue,
    SketchOutput,
    register,
)
from fdcad.core.plane_normal import plane_normal
from fdcad.core.sketch.model import Sketch, sketch_from_data
from fdcad.core.sketch.profiles import ProfileError, SketchPlane, build_profile, region_profile
from fdcad.core.sketch.solver import SketchSolveError, SketchStatus, solve

if TYPE_CHECKING:
    from fdcad.core.sketch.regions import Region


def face_plane(face: TopoDS_Face) -> SketchPlane | None:
    """Sketch placement on a flat face, seen from outside the part (DECISIONS D74).

    The origin is the model origin projected onto the face. The sketch X axis is
    model X projected onto the face, or model -Z when the face is square to X,
    which matches the default planes (D67).
    """
    surface = BRepAdaptor_Surface(face)
    n = plane_normal(face)
    if n is None:
        return None
    loc = surface.Plane().Location()
    dist = loc.X() * n[0] + loc.Y() * n[1] + loc.Z() * n[2]
    origin = (dist * n[0], dist * n[1], dist * n[2])
    axis = (1.0, 0.0, 0.0) if abs(n[0]) < 0.999 else (0.0, 0.0, -1.0)
    along = axis[0] * n[0] + axis[1] * n[1] + axis[2] * n[2]
    x = (axis[0] - along * n[0], axis[1] - along * n[1], axis[2] - along * n[2])
    length = (x[0] ** 2 + x[1] ** 2 + x[2] ** 2) ** 0.5
    x_dir = (x[0] / length, x[1] / length, x[2] / length)
    return SketchPlane(origin, n, x_dir)


def plane_of(ref: dict[str, Any], ctx: BuildContext, owner: str) -> tuple[SketchPlane, list[Issue]]:
    """Resolve a sketch plane reference to a placement."""
    if "feature" in ref:
        plane = ctx.result(str(ref["feature"])).plane
        if plane is None:
            raise FeatureError(
                f"{owner}: the chosen feature is not a plane. Choose a plane or a flat face."
            )
        return plane, []
    # Imported here: naming.resolve imports features.base, which loads this package.
    from fdcad.core.naming.resolve import resolve_face

    face, issues = resolve_face(ctx.body, ref, owner)
    plane = face_plane(face)
    if plane is None:
        raise FeatureError(f"{owner}: the chosen face is not flat. Choose a flat face or a plane.")
    return plane, issues


@register
class SketchFeature(FeatureType):
    """Solves the sketch. The profile is made now and used by later features."""

    type_name = "sketch"

    def key_data(self, feature: Feature, doc: Document, results: dict[str, FeatureResult]) -> Any:
        """The values the text fields show (TR54), so the text follows them."""
        texts = feature.data.get("texts") if isinstance(feature.data, dict) else None
        if not texts or "{" not in str(texts):
            return None
        from fdcad.core.sketch.model import sketch_from_data
        from fdcad.core.sketch.text_fields import used_values

        try:
            return used_values(doc, sketch_from_data(feature.data))
        except (ValueError, KeyError):
            return None

    def reads_body(self, feature: Feature) -> bool:
        """Copies of part geometry are checked against the part (D250)."""
        pierced = any(  # a point pierced by a part edge (TR101)
            isinstance(p, dict)
            and isinstance(p.get("curve"), dict)
            and p["curve"].get("kind") == "edge"
            for p in feature.refs.get("pierce") or []
        )
        return pierced or any(
            isinstance(e, dict) and "source" in e for e in feature.data.get("entities", [])
        )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Solve and build the profile. A sketch that is not closed is fine on its own."""
        plane_ref = feature.refs.get("plane")
        if not isinstance(plane_ref, dict):
            raise FeatureError(
                f"{feature.name} has no sketch plane. Choose a plane or a flat face."
            )
        plane, issues = plane_of(plane_ref, ctx, feature.name)
        try:
            sketch = sketch_from_data(feature.data)
            derived = feature.refs.get("derived_from")
            if isinstance(derived, dict) and isinstance(derived.get("feature"), str):
                sketch = _derived(feature, derived["feature"], ctx)  # TR49
            links = _link_issues(feature, sketch, plane, ctx)
            if feature.refs.get("pierce"):
                from fdcad.core.sketch.pierce import place_pierced

                links += place_pierced(sketch, plane, feature.refs["pierce"], ctx, feature.name)
            solved = solve(sketch)
        except (ValueError, SketchSolveError) as exc:
            raise FeatureError(f"{feature.name}: {exc}") from exc
        issues.extend(links)
        if solved.status is SketchStatus.OVER or not solved.solved:
            issues.append(Issue(FeatureState.ERROR, f"{feature.name}: {solved.message}"))
        profile, profile_error = None, None
        from fdcad.core.sketch.text_fields import expand, field_values, has_fields

        if sketch.texts and has_fields(sketch.texts):  # TR54: {name} fields in text
            values = field_values(ctx.document, sketch, ctx.copy_number)
            for text in sketch.texts:
                text.text = expand(text.text, values)
        try:
            profile = build_profile(sketch, plane)
        except ProfileError as exc:
            profile_error = str(exc)
        return FeatureResult(
            body=ctx.body,
            issues=issues,
            plane=plane,
            sketch=SketchOutput(plane, sketch, solved, profile, profile_error),
        )


def _derived(feature: Feature, source_id: str, ctx: BuildContext) -> Sketch:
    """The linked copy of sketch ``source_id`` for a derived sketch (TR49, D845)."""
    from fdcad.core.sketch.derived import derived_copy, placement

    source = ctx.result(source_id).sketch
    if source is None:
        raise FeatureError(
            f"{feature.name}: the sketch it copies is not a sketch any more. "
            "Choose Break Link on it, or delete this sketch."
        )
    return derived_copy(source.model, *placement(feature.data))


def _link_issues(
    feature: Feature, sketch: Sketch, plane: SketchPlane, ctx: BuildContext
) -> list[Issue]:
    """Warnings for copies of part geometry that no longer match the part (D116 item 3).

    The copies are never moved here (CLAUDE.md rule 12): the warning offers an
    Update Copies button that carries the new positions.
    """
    from fdcad.core.sketch.links import check_links, link_keys, link_messages, updates_to_data
    from fdcad.core.sketch.projection import find_sources

    keys = link_keys(sketch)
    if not keys:
        return []
    try:
        updates = check_links(sketch, find_sources(ctx.body, plane, keys))
    except Standard_Failure:
        return []  # the check is advice only; a kernel failure never breaks the sketch
    moved_text, lost_text = link_messages(feature.name, updates)
    issues: list[Issue] = []
    if moved_text is not None:
        moved = [u for u in updates if not u.lost]
        fix = Fix(
            "Update Copies",
            "update_links",
            {"feature": feature.id, "updates": updates_to_data(moved)},
        )
        issues.append(
            Issue(FeatureState.WARNING, moved_text, [fix], [u.entity for u in moved], "stale_links")
        )
    if lost_text is not None:
        lost = [u.entity for u in updates if u.lost]
        issues.append(Issue(FeatureState.WARNING, lost_text, [], lost, "lost_links"))
    return issues


def sketch_input(feature: Feature, ctx: BuildContext) -> SketchOutput:
    """The sketch a solid feature uses (``refs.sketch``), with a usable profile."""
    ref = feature.refs.get("sketch")
    if not isinstance(ref, dict) or "feature" not in ref:
        raise FeatureError(f"{feature.name} has no sketch. Choose a sketch.")
    out = ctx.result(str(ref["feature"])).sketch
    if out is None:
        raise FeatureError(f"{feature.name}: the chosen feature is not a sketch. Pick a sketch.")
    if out.profile is None:
        raise FeatureError(f"{feature.name}: {out.profile_error}")
    return out


@dataclass
class PickedSketch:
    """The sketch a solid feature uses, with the profile of its picked regions."""

    sketch: SketchOutput
    issues: list[Issue] = field(default_factory=list)
    #: The picked regions, or None when the whole sketch is used.
    regions: list[Region] | None = None


def sketch_for(feature: Feature, ctx: BuildContext) -> PickedSketch:
    """``refs.sketch`` with its profile limited to ``refs.regions`` when there are picks.

    Without picks this is ``sketch_input``. With picks the sketch's regions are made
    (once per sketch result) and the picks resolve by name (D190, T5.3.4).
    """
    # Imported here: naming.regions imports features.base, which loads this package.
    from fdcad.core.naming.regions import picks_of, resolve_regions

    picks = picks_of(feature)
    if not picks:
        return PickedSketch(sketch_input(feature, ctx))
    ref = feature.refs.get("sketch")
    if not isinstance(ref, dict) or "feature" not in ref:
        raise FeatureError(f"{feature.name} has no sketch. Choose a sketch.")
    sid = str(ref["feature"])
    out = ctx.result(sid).sketch
    if out is None:
        raise FeatureError(f"{feature.name}: the chosen feature is not a sketch. Pick a sketch.")
    try:
        sketch_name = ctx.document.feature(sid).name
    except KeyError:
        sketch_name = sid
    found = out.regions()
    if found.issues:
        raise FeatureError(f"{feature.name}: {found.issues[0].message}")
    chosen, issues = resolve_regions(found, picks, feature.name, sketch_name)
    try:
        profile = region_profile(out.model, out.plane, found, chosen)
    except ProfileError as exc:
        raise FeatureError(f"{feature.name}: {exc}") from exc
    return PickedSketch(replace(out, profile=profile, profile_error=None), issues, chosen)
