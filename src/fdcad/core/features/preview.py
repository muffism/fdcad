"""Live feature preview geometry (PHASE1_CORRECTIONS C2, WORKFLOW_SPEC W6.4).

``build_preview`` makes the solid a feature would add or remove, on its own,
from the edited feature and the last rebuild's results. It runs off the UI
thread. Errors never escape: they come back as a message.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from OCP.TopoDS import TopoDS_Shape

from fdcad.core.document.model import Document, Feature
from fdcad.core.features import REGISTRY
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    Fix,
    PreviewHandle,
)
from fdcad.core.features.preview_lines import LINE_FEATURES, lines_of
from fdcad.core.features.solids import compound
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind

#: What to do when a preview fails (CLAUDE.md 8.4, bug hunt B5).
PREVIEW_NEXT = "Change a value, or press OK to see the full error."


@dataclass
class PreviewGeometry:
    """What the preview shows: the feature's own solid and its drag arrows."""

    shape: TopoDS_Shape | None
    handles: list[PreviewHandle] = field(default_factory=list)
    error: str | None = None
    #: Names of picked items that fail, and the fixes offered (PLAN 5A items 4 and 5).
    failed: list[str] = field(default_factory=list)
    fixes: list[Fix] = field(default_factory=list)
    #: Values for the panel, such as a vent's open area (P4.4).
    info: dict[str, float] = field(default_factory=dict)
    #: Where value labels without a drag handle sit (T15.2, D440), or None.
    anchor: tuple[float, float, float] | None = None
    #: True when ``shape`` holds only the faces the feature makes (and, for Move Face,
    #: the held and stretched ones), drawn see-through over the unchanged part (D1032).
    replaces_part: bool = False
    #: True when ``shape`` holds only outline edges, drawn as lines over the part (D585).
    outline: bool = False
    #: Faces of ``shape`` the feature made, drawn in the preview colour (D1032).
    accent: list[TopoDS_Shape] = field(default_factory=list)
    #: Move Face: faces held still and faces that stretch, in their own colours (D798).
    held: list[TopoDS_Shape] = field(default_factory=list)
    stretched: list[TopoDS_Shape] = field(default_factory=list)
    #: Fillet and Chamfer Full: cross lines across each made face, as an edge compound (PV3).
    lines: TopoDS_Shape | None = None
    #: Pattern instance markers: each copy's number and point (TR59 item 4, D2400).
    markers: list[tuple[str, tuple[float, float, float]]] = field(default_factory=list)


def _result_view(tool: NamedShape | None) -> tuple[TopoDS_Shape | None, bool, list[TopoDS_Shape]]:
    """The shape to preview, whether it is an overlay of faces, and the accent faces.

    The shape is only the faces drawn over the part, never the whole result, so the
    view meshes nothing it does not draw (PV7, D1032).
    """
    from fdcad.core.features.modify import ResultPreview

    if isinstance(tool, ResultPreview) and tool.full is not None:
        faces = [*tool.accent, *tool.held, *tool.stretched]
        if faces:
            return compound(faces), True, list(tool.accent)
        return tool.full, True, list(tool.accent)
    return (tool.shape if tool is not None else None), False, []


def detailed_view(before: NamedShape, after: NamedShape | None, fid: str) -> NamedShape | None:
    """The detailed preview (TR164, D1417): the result with the faces the feature adds
    tinted (accent) and the faces it changes in the second colour (stretched); when the
    feature makes new bodies, only those bodies are shown."""
    from fdcad.core.features.modify import ResultPreview, new_faces
    from fdcad.core.features.solids import compound, solids

    if after is None:
        return None
    old_names = {n for n, _f in before.faces}
    fresh = new_faces(before.shape, after)
    added: list[TopoDS_Shape] = []
    changed: list[TopoDS_Shape] = []
    for face in fresh:
        names = after.names_of(face)
        if not names or all(n not in old_names for n in names):
            added.append(face)
        else:
            changed.append(face)
    full = after.shape
    old_solids = solids(before.shape)
    new_solids = [s for s in solids(after.shape) if not any(s.IsSame(o) for o in old_solids)]
    if len(solids(after.shape)) > len(old_solids) and new_solids:
        from fdcad.core.naming.names import faces_of

        full = compound(new_solids)
        inside = faces_of(full)
        added = [f for f in added if any(f.IsSame(g) for g in inside)]
        changed = []
    preview = ResultPreview(compound(fresh), [], full=full, accent=added)
    preview.stretched = changed
    return preview


def body_before(
    doc: Document, feature: Feature, results: Mapping[str, FeatureResult]
) -> NamedShape | None:
    """The part just before ``feature`` (or at the end, for a new feature), in the order
    the rebuild builds them (linked copies last, TR154, D2417)."""
    from fdcad.core.features.linked_copy import deferred_order

    order = deferred_order(list(doc.features))
    index = next((i for i, f in enumerate(order) if f.id == feature.id), None)
    earlier = order if index is None else order[:index]
    body: NamedShape | None = None
    for f in earlier:
        result = results.get(f.id)
        if result is not None and not f.suppressed:
            body = result.body
    return body


def build_preview(
    doc: Document,
    feature: Feature,
    results: Mapping[str, FeatureResult],
    variables: dict[str, tuple[Kind, float]] | None = None,
    cancelled: Callable[[], bool] = lambda: False,
) -> PreviewGeometry:
    """Build the preview of ``feature``. Never raises."""
    ftype = REGISTRY.get(feature.type)
    if ftype is None:
        return PreviewGeometry(None, error=f"{feature.type} has no preview.")
    from fdcad.core.features.preview_anchor import pick_anchor

    before = body_before(doc, feature, results)
    ctx = BuildContext(doc, before, dict(results), variables or {}, cancelled)
    try:
        ftype.validate(feature)
        tool = ftype.tool(feature, ctx)
        if feature.data.get("preview_detailed") and before is not None:  # TR164 (D1417)
            tool = detailed_view(before, ftype.execute(feature, ctx).body, feature.id) or tool
        handles = ftype.preview_handles(feature, ctx)
        info = ftype.preview_info(feature, ctx)
    except FeatureError as exc:
        partial = getattr(exc, "partial", None)
        part = partial if isinstance(partial, NamedShape) else None
        shape, replaces, accent = _result_view(part)
        failed = list(getattr(exc, "failed", None) or exc.highlight)
        anchor = pick_anchor(feature, before, part.shape if part is not None else None)
        return PreviewGeometry(
            shape,
            error=str(exc),
            failed=failed,
            fixes=list(exc.fixes),
            anchor=anchor,
            replaces_part=replaces,
            accent=accent,
        )
    except Exception as exc:  # kernel failure: the preview just stays empty
        error = f"Preview failed ({type(exc).__name__}). {PREVIEW_NEXT}"
        return PreviewGeometry(None, error=error, anchor=pick_anchor(feature, before, None))
    shape, replaces, accent = _result_view(tool)
    anchor = pick_anchor(feature, before, tool.shape if tool is not None else None)
    from fdcad.core.features.modify import ResultPreview
    from fdcad.core.features.pattern_markers import instance_markers

    held = list(tool.held) if isinstance(tool, ResultPreview) and replaces else []
    stretched = list(tool.stretched) if isinstance(tool, ResultPreview) and replaces else []
    lines = None
    if replaces and feature.type in LINE_FEATURES and accent:
        edges = lines_of(accent)
        lines = compound(edges) if edges else None
    return PreviewGeometry(
        shape,
        handles,
        lines=lines,
        info=info,
        anchor=anchor,
        replaces_part=replaces,
        accent=accent,
        held=held,
        stretched=stretched,
        markers=instance_markers(feature, ctx),
    )
