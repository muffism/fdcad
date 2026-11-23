"""Read a STEP file as a base body: shape healing, colours and a healing report
(PLAN Phase 3, PHASE3_SPEC P3.5, DECISIONS D290).

The file is read through OpenCascade's document reader, so face and solid
colours come with the shape. The shape is then healed:

1. ``ShapeFix_Shape`` repairs invalid faces, wires, small edges and tolerances.
2. When the file holds open shells or loose faces (no solids), they are sewn
   together and every closed shell becomes a solid.

Each step that changed something adds a plain sentence to the report. Colours
follow the faces through healing. Reading happens off the UI thread: the
rebuild calls it from the import feature.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.IFSelect import IFSelect_RetDone
from OCP.Quantity import Quantity_Color
from OCP.ShapeExtend import ShapeExtend_DONE
from OCP.ShapeFix import ShapeFix_Shape, ShapeFix_Solid
from OCP.TopAbs import TopAbs_FACE, TopAbs_ShapeEnum, TopAbs_SHELL, TopAbs_SOLID
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.naming.names import faces_of

#: Sewing tolerance in mm for loose faces (DECISIONS D290 item 3).
SEW_TOLERANCE = 1e-3


class StepImportError(Exception):
    """The STEP file cannot be used. The message is shown to the user."""


@dataclass
class StepImport:
    """A healed STEP shape, the colour of each face, and what healing fixed."""

    shape: TopoDS_Shape
    face_colors: list[tuple[TopoDS_Face, str]] = field(default_factory=list)
    report: list[str] = field(default_factory=list)
    valid: bool = True


def compound(shapes: list[TopoDS_Shape]) -> TopoDS_Shape:
    """Group shapes into one compound."""
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    comp = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(comp)
    for s in shapes:
        builder.Add(comp, s)
    return comp


def _hex(color: Quantity_Color) -> str:
    text = str(Quantity_Color.ColorToHex_s(color, False).ToCString()).upper()
    return text if text.startswith("#") else f"#{text}"


def _shapes_of(shape: TopoDS_Shape, kind: TopAbs_ShapeEnum) -> list[TopoDS_Shape]:
    out = []
    explorer = TopExp_Explorer(shape, kind)
    while explorer.More():
        out.append(explorer.Current())
        explorer.Next()
    return out


def _free_shells(shape: TopoDS_Shape) -> list[TopoDS_Shape]:
    """Shells that are not inside a solid."""
    explorer = TopExp_Explorer(shape, TopAbs_SHELL, TopAbs_SOLID)
    out = []
    while explorer.More():
        out.append(explorer.Current())
        explorer.Next()
    return out


def _free_faces(shape: TopoDS_Shape) -> list[TopoDS_Shape]:
    """Faces that are not inside a shell."""
    explorer = TopExp_Explorer(shape, TopAbs_FACE, TopAbs_SHELL)
    out = []
    while explorer.More():
        out.append(explorer.Current())
        explorer.Next()
    return out


def _read_document(path: Path) -> tuple[TopoDS_Shape, list[tuple[TopoDS_Shape, str]]]:
    """The file's shape and the colour of every coloured face or solid."""
    from OCP.collections import (
        IndexedDataMap_TopoDS_Shape_XCAFPrs_Style_TopTools_ShapeMapHasher as StyleMap,
    )
    from OCP.collections import Sequence_TDF_Label
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopLoc import TopLoc_Location
    from OCP.XCAFDoc import XCAFDoc_DocumentTool
    from OCP.XCAFPrs import XCAFPrs

    doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(False)
    reader.SetLayerMode(False)
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise StepImportError(
            "The file is not a STEP file or it is damaged. Export it again and import the new file."
        )
    if not reader.Transfer(doc):
        raise StepImportError(
            "The STEP file holds no shapes that can be read. "
            "Export it again and import the new file."
        )
    tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    labels = Sequence_TDF_Label()
    tool.GetFreeShapes(labels)
    shapes: list[TopoDS_Shape] = []
    colors: list[tuple[TopoDS_Shape, str]] = []
    for i in range(1, labels.Length() + 1):
        label = labels.Value(i)
        shapes.append(tool.GetShape_s(label))
        styles = StyleMap()
        XCAFPrs.CollectStyleSettings_s(label, TopLoc_Location(), styles)
        for k in range(1, styles.Extent() + 1):
            style = styles.FindFromIndex(k)
            if style.IsSetColorSurf():
                colors.append((styles.FindKey(k), _hex(style.GetColorSurf())))
    if not shapes:
        raise StepImportError(
            "The STEP file holds no shapes that can be read. "
            "Export it again and import the new file."
        )
    shape = shapes[0] if len(shapes) == 1 else compound(shapes)
    return shape, colors


def _face_colors(
    shape: TopoDS_Shape, colors: list[tuple[TopoDS_Shape, str]]
) -> list[tuple[TopoDS_Face, str]]:
    """A colour for each face of ``shape``: its own, else its solid's or shell's."""
    own: list[tuple[TopoDS_Shape, str]] = []
    whole: list[tuple[TopoDS_Shape, str]] = []
    for sub, hex_color in colors:
        (own if sub.ShapeType() == TopAbs_FACE else whole).append((sub, hex_color))
    out: list[tuple[TopoDS_Face, str]] = []
    for face in faces_of(shape):
        color: str | None = next((c for s, c in own if s.IsSame(face)), None)
        if color is None:
            for sub, c in whole:
                if any(f.IsSame(face) for f in faces_of(sub)):
                    color = c
        if color is not None:
            out.append((face, color))
    return out


def heal(
    shape: TopoDS_Shape,
    colors: list[tuple[TopoDS_Face, str]],
    tolerance: float = SEW_TOLERANCE,
) -> tuple[TopoDS_Shape, list[tuple[TopoDS_Face, str]], list[str]]:
    """Repair ``shape``; returns the new shape, the colours moved onto it and the report.
    ``tolerance`` is the largest gap sewing closes, in mm (Heal raises it, TR31)."""
    report: list[str] = []
    was_valid = BRepCheck_Analyzer(shape).IsValid()
    fixer = ShapeFix_Shape(shape)
    fixer.SetPrecision(1e-7)
    fixer.SetMaxTolerance(tolerance)
    fixer.Perform()
    fixed = fixer.Shape()
    context = fixer.Context()
    moved = [(TopoDS.Face(context.Value(f)), c) for f, c in colors]
    moved = [(f, c) for f, c in moved if not f.IsNull()]
    if fixer.Status(ShapeExtend_DONE) and not was_valid and BRepCheck_Analyzer(fixed).IsValid():
        report.append("Invalid faces and edges were repaired.")

    solids_before = _shapes_of(fixed, TopAbs_SOLID)
    loose = _free_shells(fixed) + _free_faces(fixed)
    if loose:
        sewing = BRepBuilderAPI_Sewing(tolerance)
        for item in loose:
            sewing.Add(item)
        sewing.Perform()
        sewn = sewing.SewedShape()
        moved = _follow_sewing(sewing, moved)
        made: list[TopoDS_Shape] = []
        open_shells = 0
        for shell in _shapes_of(sewn, TopAbs_SHELL):
            if not _is_closed(shell):
                open_shells += 1
                continue
            solid = ShapeFix_Solid().SolidFromShell(TopoDS.Shell(shell))
            made.append(solid)
        if made:
            report.append(
                f"Joined {len(loose)} open surface pieces into {len(made)} "
                f"{'solid' if len(made) == 1 else 'solids'}."
            )
            moved = _follow_into(made, moved)
        if open_shells:
            report.append(
                f"{open_shells} open surface {'piece was' if open_shells == 1 else 'pieces were'} "
                "left out because it does not enclose a volume."
            )
        fixed = (
            solids_before[0]
            if len(solids_before) == 1 and not made
            else compound([*solids_before, *made])
        )
    elif len(solids_before) == 1 and fixed.ShapeType() != TopAbs_SOLID:
        fixed = solids_before[0]
    elif len(solids_before) > 1 and fixed.ShapeType() != TopAbs_SOLID:
        fixed = compound(solids_before)
    return fixed, moved, report


def _is_closed(shell: TopoDS_Shape) -> bool:
    """True when every edge of the shell joins two faces."""
    from OCP.BRep import BRep_Tool

    return bool(BRep_Tool.IsClosed_s(shell))


def _follow_sewing(
    sewing: BRepBuilderAPI_Sewing, colors: list[tuple[TopoDS_Face, str]]
) -> list[tuple[TopoDS_Face, str]]:
    out = []
    for face, color in colors:
        new = face
        if sewing.IsModifiedSubShape(face):
            new = sewing.ModifiedSubShape(face)
        elif sewing.IsModified(face):
            new = sewing.Modified(face)
        if not new.IsNull() and new.ShapeType() == TopAbs_FACE:
            out.append((TopoDS.Face(new), color))
        else:
            out.append((face, color))
    return out


def _follow_into(
    made: list[TopoDS_Shape], colors: list[tuple[TopoDS_Face, str]]
) -> list[tuple[TopoDS_Face, str]]:
    """Faces of the new solids that are the same as coloured faces keep the colour."""
    out = list(colors)
    for solid in made:
        for face in faces_of(solid):
            for old, color in colors:
                if old.IsSame(face):
                    out.append((face, color))
                    break
    return out


def read_step(data: bytes, owner: str = "The STEP file", gap: float | None = None) -> StepImport:
    """Read, heal and check STEP file contents. Raises StepImportError.

    ``owner`` starts every message, for example the feature name. ``gap`` is the
    largest gap healing closes, in mm, when Heal set one (TR31).
    """
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "import.step"
        path.write_bytes(data)
        try:
            raw, colors = _read_document(path)
        except StepImportError as exc:
            raise StepImportError(f"{owner}: {exc}") from exc
    if raw.IsNull():
        raise StepImportError(f"{owner}: the STEP file is empty. Choose another file.")
    face_colors = _face_colors(raw, colors)
    from fdcad.core.io.iges_import import MAX_GAP

    tolerance = SEW_TOLERANCE if gap is None else min(max(gap, SEW_TOLERANCE), MAX_GAP)
    shape, face_colors, report = heal(raw, face_colors, tolerance)
    if not _shapes_of(shape, TopAbs_SOLID):
        # A mesh only STEP file also lands here; point to Import Mesh (audit D item 20).
        raise StepImportError(
            f"{owner}: the STEP file has no closed solids. Close the model in the program "
            "that made it and export it again. If it is a mesh of triangles, export it as "
            "STL or 3MF and use Import Mesh instead."
        )
    valid = BRepCheck_Analyzer(shape).IsValid()
    if not valid:
        report.append(
            "Some faces could not be repaired. Later features on them may fail; "
            "use Delete Face to remove them."
        )
    left = _left_out(raw)
    if left:
        report.append(left)
    present = faces_of(shape)
    return StepImport(shape, _dedupe(face_colors, present), report, valid)


def _left_out(raw: TopoDS_Shape) -> str:
    """A sentence naming the curves, points and loose faces that are not part of a
    solid, which the import leaves out (audit D item 6, D722); empty when there are none."""
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX

    from fdcad.core.occ import ShapeMap

    def mapped(shapes: list[TopoDS_Shape], kind: TopAbs_ShapeEnum) -> ShapeMap:
        out = ShapeMap()
        for shape in shapes:
            TopExp.MapShapes_s(shape, kind, out)
        return out

    def outside(kind: TopAbs_ShapeEnum, known: ShapeMap) -> int:
        every = mapped([raw], kind)
        return sum(1 for i in range(1, every.Extent() + 1) if not known.Contains(every.FindKey(i)))

    solids = _shapes_of(raw, TopAbs_SOLID)
    faces = _shapes_of(raw, TopAbs_FACE)
    counts = [
        ("loose face", outside(TopAbs_FACE, mapped(solids, TopAbs_FACE))),
        ("curve", outside(TopAbs_EDGE, mapped(faces, TopAbs_EDGE))),
        (
            "point",
            outside(TopAbs_VERTEX, mapped([*faces, *_shapes_of(raw, TopAbs_EDGE)], TopAbs_VERTEX)),
        ),
    ]
    named = [f"{n} {word}{'s' if n != 1 else ''}" for word, n in counts if n]
    if not named:
        return ""
    return (
        f"Left out because they are not part of a solid: {', '.join(named)}. "
        "Model them as solids, or draw them again in FDCAD."
    )


def _dedupe(
    colors: list[tuple[TopoDS_Face, str]], present: list[TopoDS_Face]
) -> list[tuple[TopoDS_Face, str]]:
    """One colour per face, as the face appears in the shape. A face's own colour wins.
    Looked up through a face map, so large files stay quick (audit D item 15)."""
    from fdcad.core.occ import ShapeMap

    first: dict[int, str] = {}
    index = ShapeMap()
    for f, c in colors:
        k = index.Add(f)
        first.setdefault(k, c)
    out: list[tuple[TopoDS_Face, str]] = []
    for face in present:
        k = index.FindIndex(face)
        if k:
            out.append((face, first[k]))
    return out


__all__ = ["StepImport", "StepImportError", "heal", "read_step"]
