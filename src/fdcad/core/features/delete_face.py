"""Delete Face: remove faces and heal the body (PHASE3_SPEC P3.1.2, DECISIONS D232).

Params:
- ``option``: "patch" (default) grows the neighbouring faces until they meet;
  "fill" closes the opening with one new smooth face; "delete" leaves an open
  shell and is not built until surface bodies are in PLAN (it is an error).
- ``tangent``: optional boolean for "fill": the new face meets its neighbours smoothly.
- ``hole_size``: optional length (TR388, D990): every round hole up to this diameter
  is removed too, found by the feature. ``voids``: optional boolean: enclosed voids
  are filled. With either, the picked faces may be left empty.

Refs: ``faces``: list of face references.

Face roles: kept faces keep their names. Fill adds ``fill`` (``fill#k`` for
several openings).

When patching several faces fails, each face is tried on its own and the
message names the ones that cannot be removed. The fix "Keep the faces that
worked" drops those from the pick list; it runs only when the user clicks it
(PLAN 5A items 5 and 6).
"""

from __future__ import annotations

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Fix,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.bodies import on_own_bodies
from fdcad.core.features.direct import fill, patch, patch_each, resolve_faces, short_name
from fdcad.core.features.solids import check_result
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind

OPTIONS = ("patch", "fill", "delete")

#: The fix action that removes failed picks from a list reference.
DROP_REFS = "drop_refs"


@register
class DeleteFace(FeatureType):
    """Removes faces and heals the gap, so the body stays a closed solid."""

    type_name = "delete_face"
    makes_solid = True
    params = (
        ParamSpec("option", choices=OPTIONS, default="patch"),
        ParamSpec("tangent", default=False, optional=True),
        ParamSpec("hole_size", kind=Kind.LENGTH, optional=True),  # TR388 (D990)
        ParamSpec("voids", default=False, optional=True),
        ParamSpec("reapply_fillets", default=False, optional=True),  # TR259 (D1420)
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Remove the faces and check the result."""
        body, issues = self._build(feature, ctx)
        issues += check_result(feature.id, feature.name, ctx.body, body, None)
        return FeatureResult(body=body, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The healed part, for the live preview."""
        return self._build(feature, ctx)[0]

    def _build(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        """Remove the faces; with Reapply Fillets (TR259, D1420) the rounds next to them
        are removed first and made again after."""
        from fdcad.core.features import reapply_fillets as reapply

        if reapply.wanted(feature) and ctx.body is not None and feature.refs.get("faces"):
            picked, _labels, _issues = resolve_faces(ctx, feature.refs.get("faces"), feature.name)
            return reapply.around(feature, ctx, picked, lambda c: self._remove(feature, c))
        return self._remove(feature, ctx)

    def _remove(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part is empty. Add a body first.")
        option = str(feature.params.get("option", "patch"))
        if option == "delete":
            raise FeatureError(
                f"{name}: Delete without healing leaves an open surface, which FDCAD does not "
                "have yet. Choose Delete and Patch or Delete and Fill."
            )
        from fdcad.core.document.model import Param
        from fdcad.core.features.simplify import small_holes, without_voids

        body = ctx.body
        filled = 0
        if feature.params.get("voids") is True:  # TR388: enclosed voids first
            body, filled = without_voids(body)
        size = feature.params.get("hole_size")
        diameter = size.value if isinstance(size, Param) else 0.0
        if feature.refs.get("faces") or diameter <= 0:
            faces, labels, issues = resolve_faces(ctx, feature.refs.get("faces"), name)
        else:
            faces, labels, issues = [], [], []
        if diameter > 0:
            for hole_name, face in small_holes(body, diameter):
                if not any(face.IsSame(f) for f in faces):
                    faces.append(face)
                    labels.append(hole_name)
        if not faces:
            if filled:
                return body, issues
            raise FeatureError(
                f"{name}: no hole is {diameter:g} mm across or smaller, and no face is "
                "picked. Pick faces, or enter a larger hole size."
            )
        fid = feature.id
        if option == "fill":
            tangent = feature.params.get("tangent") is True
            return on_own_bodies(
                body, faces, fid, lambda b: fill(b, faces, tangent, fid, name, labels)
            ), issues
        try:
            return on_own_bodies(
                body, faces, fid, lambda b: patch(b, faces, fid, name, labels)
            ), issues
        except FeatureError as exc:
            if len(faces) < 2:
                raise
            failed = patch_each(body, faces, labels, feature.id, name)
            if not failed or len(failed) == len(faces):
                raise
            listed = ", ".join(short_name(n) for n in failed)
            raise FeatureError(
                f"{name} failed: {listed} cannot be removed, because the faces around "
                "them cannot grow to close the gap. Keep the faces that worked, or pick the "
                "rest of that feature's faces.",
                fixes=[
                    Fix(
                        "Keep the faces that worked",
                        DROP_REFS,
                        {"feature": feature.id, "ref": "faces", "names": failed},
                    )
                ],
                highlight=failed,
            ) from exc


# Registers Replace Face (TR130, D1412), a direct edit beside Delete Face.
from fdcad.core.features import heal_edges as _heal_edges  # noqa: E402, F401  (TR262, D1807)
from fdcad.core.features import parting_line as _parting_line  # noqa: E402, F401  (TR84, D1415)
from fdcad.core.features import push_pull as _push_pull  # noqa: E402, F401  (TR267, D1413)
from fdcad.core.features import replace_face as _replace_face  # noqa: E402, F401
from fdcad.core.features import split_line as _split_line  # noqa: E402, F401  (TR60, D1414)
