"""Where a pattern's seed is: the centre of the features, faces or bodies it copies."""

from __future__ import annotations

from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, FeatureError, Vec3
from fdcad.core.features.solids import compound
from fdcad.core.naming.names import centroid


def seed_centre(feature: Feature, ctx: BuildContext) -> Vec3:
    """Area centre of the seed's faces (features: the faces they made)."""
    from fdcad.core.features.bodies import body_indices
    from fdcad.core.features.direct import resolve_faces
    from fdcad.core.features.solids import solids

    body = ctx.body
    if body is None:
        raise FeatureError(f"{feature.name}: the part is empty. Add a body first.")
    shapes = []
    if feature.refs.get("faces"):
        faces, _labels, _issues = resolve_faces(ctx, feature.refs["faces"], feature.name)
        shapes.extend(faces)
    if feature.refs.get("features"):
        prefixes = [
            f"{r['feature']}/"
            for r in feature.refs["features"]
            if isinstance(r, dict) and isinstance(r.get("feature"), str)
        ]
        shapes.extend(f for n, f in body.faces if any(n.startswith(p) for p in prefixes))
    if feature.refs.get("bodies"):
        indices, _issues = body_indices(ctx, feature.refs["bodies"], feature.name)
        all_solids = solids(body.shape)
        shapes.extend(all_solids[i] for i in indices)
    if not shapes:
        raise FeatureError(f"{feature.name}: pick features, faces or bodies to copy.")
    return centroid(compound(shapes))
