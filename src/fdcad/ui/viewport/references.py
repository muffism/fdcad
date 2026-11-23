"""Display data that features return in ``FeatureResult.extras`` (DECISIONS D290):
face colours (imported STEP colours and the part's face colours) and reference
shapes such as curves and meshes, which are drawn but are not part of the body.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from OCP.TopoDS import TopoDS_Shape

    from fdcad.core.document.model import Document
    from fdcad.core.rebuild.engine import RebuildReport


def face_colors(report: RebuildReport, doc: Document) -> list[tuple[TopoDS_Shape, str]]:
    """Faces of the finished part with their own colour.

    Colours from imports come first; colours the user set on faces (FDEF_SPEC 10)
    win. Names that no longer resolve are skipped.
    """
    body = report.body
    if body is None:
        return []
    names: dict[str, str] = {}
    for result in report.results.values():
        names.update(result.extras.get("face_colors", {}))
    faces = doc.appearance.get("faces", {})
    if isinstance(faces, dict):
        names.update({str(k): str(v) for k, v in faces.items()})
    if not names:
        return []
    from fdcad.core.appearance import propagating, seed_name

    propagate = propagating(doc)
    out: list[tuple[TopoDS_Shape, str]] = []
    for name, face in body.faces:
        base = name.split("#", 1)[0]
        color = names.get(name, names.get(base))
        seed = seed_name(name, propagate) if color is None and propagate else None
        if seed is not None:  # a propagating copy takes its seed face's colour (D717)
            color = names.get(seed, names.get(seed.split("#", 1)[0]))
        if color is not None:
            out.append((face, color))
    return out


#: Feature types whose drawn reference is a curve (View > Show Types, Curves, TR215).
CURVE_TYPES = frozenset(
    {"helix", "projected_curve", "composite_curve", "contour", "point_curve", "curve_array"}
)


def reference_shapes(
    report: RebuildReport, doc: Document, hidden: set[str] | None = None
) -> list[TopoDS_Shape]:
    """Reference curves and meshes of the features that built, in tree order; curves are
    left out while ``hidden`` holds "curves"."""
    out: list[TopoDS_Shape] = []
    no_curves = hidden is not None and "curves" in hidden
    for feature in doc.features:
        result = report.results.get(feature.id)
        if result is None or feature.suppressed:
            continue
        if no_curves and feature.type in CURVE_TYPES:
            continue
        shape = result.extras.get("reference")
        if shape is not None:
            out.append(shape)
    return out


def show_extras(
    viewport: Any, report: RebuildReport, doc: Document, hidden: set[str] | None = None
) -> None:
    """Send face colours and reference shapes to the 3D view."""
    colors = getattr(viewport, "set_face_colors", None)
    if colors is not None:
        colors(face_colors(report, doc))
    references = getattr(viewport, "show_references", None)
    if references is not None:
        references(reference_shapes(report, doc, hidden))
