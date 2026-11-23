"""Imported STEP body (PLAN Phase 3, PHASE3_SPEC P3.5, DECISIONS D290).

Params: ``merge`` (optional boolean): when the part already has a body, join the
imported solid to it. Off by default, so an inserted file becomes its own body.
``heal_gap`` (optional length): the largest gap healing closes, set by Heal
(TR31, D760); without it the usual 0.001 mm.

Refs: ``source``: ``{"embedded": "b1"}``, the STEP file stored in the part
(FDEF_SPEC 11). The file is never read from disk again. A block with
``format: "iges"`` holds an IGES file instead (TR31), read by ``iges_import``.

``keep_bodies`` (optional text, TR302 item 2, D1203): the numbers of the file's
bodies that come in, from 1 in the healed shape's order, such as "1, 3"; empty
or missing for all of them. Faces keep the names they have in the whole file.

Face roles: ``face/<k>``, numbered from 1 in the kernel's order of the healed
shape. The same file always gives the same order, so names are stable.
Colours from the file are returned in ``extras["face_colors"]`` by face name, and
what healing fixed in ``extras["report"]``.
"""

from __future__ import annotations

from typing import Any

from OCP.TopoDS import TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Document, Feature, Param, new_document
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
from fdcad.core.features.solids import combine, compound
from fdcad.core.io.embedded import EmbeddedError, block_bytes, make_block, new_block_id
from fdcad.core.io.step_import import StepImport, StepImportError, read_step
from fdcad.core.naming.names import NamedFace, NamedShape, faces_of, restrict
from fdcad.core.units import Kind, UnitSystem


def imported_faces(fid: str, shape: TopoDS_Shape) -> list[NamedFace]:
    """``<fid>/face/<k>`` for every face, in the shape's own order."""
    return [(f"{fid}/face/{k}", face) for k, face in enumerate(faces_of(shape), start=1)]


def color_names(named: list[NamedFace], colors: list[tuple[TopoDS_Face, str]]) -> dict[str, str]:
    """Face name to colour for the coloured faces."""
    out: dict[str, str] = {}
    for name, face in named:
        for colored, color in colors:
            if colored.IsSame(face):
                out[name] = color
                break
    return out


@register
class ImportStep(FeatureType):
    """A solid read from an embedded STEP file."""

    type_name = "import_step"
    makes_solid = True
    params = (
        ParamSpec("merge", default=False, optional=True),
        ParamSpec("heal_gap", kind=Kind.LENGTH, optional=True),  # TR31: set by Heal
        ParamSpec("keep_bodies", optional=True),  # TR302 (D1203): picked body numbers
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Decode, read and heal the file, name its faces and add it to the part."""
        owner = feature.name
        try:
            imported = read_import(ctx.document, feature)
        except (EmbeddedError, StepImportError) as exc:
            raise FeatureError(str(exc)) from exc
        fid = feature.id
        named = imported_faces(fid, imported.shape)
        tool = picked_bodies(feature, NamedShape(imported.shape, named))
        colors = color_names(named, imported.face_colors)
        issues: list[Issue] = []
        if not imported.valid:
            issues.append(
                Issue(
                    FeatureState.WARNING,
                    f"{owner}: some faces of the imported body are not valid. Later features "
                    "on them may fail. Use Delete Face to remove them.",
                    code="import_invalid",
                )
            )
        body = ctx.body
        if body is None:
            result = tool
        elif feature.params.get("merge", False) is True:
            result = combine(fid, owner, body, tool, "boss")
        else:
            shape = compound([body.shape, tool.shape])
            result = NamedShape(shape, restrict(body.faces + tool.faces, shape, fid))
        out = FeatureResult(body=result, issues=issues)
        out.extras["face_colors"] = colors
        out.extras["report"] = list(imported.report)
        return out

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape | None:
        """The imported solid on its own."""
        try:
            imported = read_import(ctx.document, feature)
        except (EmbeddedError, StepImportError):
            return None
        return picked_bodies(
            feature, NamedShape(imported.shape, imported_faces(feature.id, imported.shape))
        )


def keep_list(text: str, count: int) -> list[int]:
    """Body numbers typed as "1, 3" (from 1) as indices from 0 below ``count``, in order
    and once each. Numbers above ``count`` are left out. Raises ValueError for text
    that is not whole numbers from 1."""
    import re

    out: list[int] = []
    for word in re.split(r"[,;\s]+", text.strip()):
        if not word:
            continue
        if not word.isdigit() or int(word) < 1:
            raise ValueError(f"{word} is not a body number")
        index = int(word) - 1
        if index < count and index not in out:
            out.append(index)
    return sorted(out)


def picked_bodies(feature: Feature, whole: NamedShape) -> NamedShape:
    """The bodies of the import that ``keep_bodies`` picks (TR302, D1203); all of them
    without a pick. Raises FeatureError for a pick that is wrong or empty."""
    from fdcad.core.features.solids import solids

    keep = feature.params.get("keep_bodies")
    if not isinstance(keep, str) or not keep.strip():
        return whole
    parts = solids(whole.shape)
    owner = feature.name
    try:
        indices = keep_list(keep, len(parts))
    except ValueError:
        raise FeatureError(
            f"{owner}: the picked bodies '{keep}' are not body numbers. "
            "Use Pick Bodies to pick them again."
        ) from None
    if not indices:
        raise FeatureError(
            f"{owner}: none of the picked bodies are in the file. "
            "Use Pick Bodies to pick them again."
        )
    if len(indices) == len(parts):
        return whole
    shape = parts[indices[0]] if len(indices) == 1 else compound([parts[i] for i in indices])
    return NamedShape(shape, restrict(whole.faces, shape, feature.id))


def heal_gap(feature: Feature) -> float | None:
    """The gap Heal set for the import, in mm, or None."""
    value = feature.params.get("heal_gap")
    return float(value.value) if isinstance(value, Param) and value.value > 0 else None


def read_import(doc: Document, feature: Feature) -> StepImport:
    """The STEP or IGES file of an import feature, read and healed. Raises EmbeddedError
    or StepImportError (IgesImportError is one)."""
    from fdcad.core.io.embedded import block_of

    owner = feature.name
    source = feature.refs.get("source")
    data = block_bytes(doc, source, "step", owner)
    if block_of(doc, source, "step", owner).get("format") == "iges":
        from fdcad.core.io.iges_import import read_iges

        return read_iges(data, owner, heal_gap(feature))
    return read_step(data, owner, heal_gap(feature))


def is_iges(doc: Document, feature: Feature) -> bool:
    """True for an import whose stored file is IGES."""
    source = feature.refs.get("source")
    key = source.get("embedded") if isinstance(source, dict) else None
    block = doc.embedded.get(key) if isinstance(key, str) else None
    return isinstance(block, dict) and block.get("format") == "iges"


def import_name(doc: Document, label: str = "Imported") -> str:
    """``Imported 1``, ``Imported 2`` and so on, the next free number in the part."""
    used = {f.name for f in doc.features}
    k = 1
    while f"{label} {k}" in used:
        k += 1
    return f"{label} {k}"


def new_step_import(
    doc: Document, filename: str, data: bytes
) -> tuple[str, dict[str, Any], Feature]:
    """A block holding ``data`` and an import feature that uses it, not yet in ``doc``.

    The caller adds both in one undoable step.
    """
    bid = new_block_id(doc)
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    # An IGES file is stored as a STEP style block with its format (TR31).
    block = (
        make_block("step", filename, data, format="iges")
        if suffix in ("igs", "iges")
        else make_block("step", filename, data)
    )
    feature = Feature(
        doc.new_feature_id(),
        "import_step",
        import_name(doc),
        refs={"source": {"embedded": bid}},
    )
    return bid, block, feature


def part_from_step(filename: str, data: bytes, units: UnitSystem = UnitSystem.MM) -> Document:
    """A new part whose first feature is the imported STEP body (File, Open)."""
    doc = new_document(units)
    bid, block, feature = new_step_import(doc, filename, data)
    doc.embedded[bid] = block
    doc.features.append(feature)
    return doc
