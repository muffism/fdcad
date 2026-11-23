"""IGES import with joining into a solid (TR31, DECISIONS D760).

IGES files usually hold loose surfaces. They are read, then healed and sewn the
same way as STEP files (``step_import.heal``): surfaces that close a volume are
joined into a solid. When they do not, the error says how many gaps are left
and where the first ones are, so the part can be fixed or healed with a larger
gap (``gap``, the sewing tolerance in mm; Heal sets it). Surface building is
out of scope (PLAN.md), so a set of surfaces that will not close stays an error.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.io.step_import import (
    SEW_TOLERANCE,
    StepImport,
    StepImportError,
    _free_faces,
    _free_shells,
    _shapes_of,
    heal,
)

#: The largest gap Heal may close, in mm. Larger would join faces that are meant apart.
MAX_GAP = 1.0
#: How many gap places the message names.
_PLACES = 3


class IgesImportError(StepImportError):
    """The IGES file cannot be used. The message is shown to the user."""


def _read(data: bytes, owner: str) -> TopoDS_Shape:
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.IGESControl import IGESControl_Reader

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "import.igs"
        path.write_bytes(data)
        reader = IGESControl_Reader()
        try:
            status = reader.ReadFile(str(path))
        except Exception:
            status = None
        if status != IFSelect_RetDone:
            raise IgesImportError(
                f"{owner}: the file is not an IGES file the kernel can read. "
                "Export it again as IGES, or as STEP."
            )
        reader.TransferRoots()
        return reader.OneShape()


def _gaps(shape: TopoDS_Shape, gap: float) -> list[tuple[float, float, float]]:
    """The middle of each open edge loop left after sewing, one per gap."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.ShapeAnalysis import ShapeAnalysis_FreeBounds
    from OCP.TopAbs import TopAbs_WIRE
    from OCP.TopExp import TopExp_Explorer

    sewing = BRepBuilderAPI_Sewing(gap)
    for item in _free_shells(shape) + _free_faces(shape):
        sewing.Add(item)
    sewing.Perform()
    bounds = ShapeAnalysis_FreeBounds(sewing.SewedShape(), gap, False, False)
    out = []
    explorer = TopExp_Explorer(bounds.GetClosedWires(), TopAbs_WIRE)
    while explorer.More():
        props = GProp_GProps()
        BRepGProp.LinearProperties_s(explorer.Current(), props)
        c = props.CentreOfMass()
        out.append((c.X(), c.Y(), c.Z()))
        explorer.Next()
    open_wires = TopExp_Explorer(bounds.GetOpenWires(), TopAbs_WIRE)
    while open_wires.More():
        props = GProp_GProps()
        BRepGProp.LinearProperties_s(open_wires.Current(), props)
        c = props.CentreOfMass()
        out.append((c.X(), c.Y(), c.Z()))
        open_wires.Next()
    return out


def read_iges(data: bytes, owner: str = "The IGES file", gap: float | None = None) -> StepImport:
    """Read IGES file contents and join its surfaces. Raises IgesImportError."""
    if not data.strip():
        raise IgesImportError(f"{owner}: the IGES file is empty. Choose another file.")
    raw = _read(data, owner)
    if raw is None or raw.IsNull() or not _shapes_of(raw, TopAbs_FACE):
        # The kernel reads text that is not IGES as an empty file, so both say the same.
        raise IgesImportError(
            f"{owner}: the file is not an IGES file the kernel can read, or it has no "
            "surfaces. Export it again as IGES, or as STEP."
        )
    tolerance = SEW_TOLERANCE if gap is None else min(max(gap, SEW_TOLERANCE), MAX_GAP)
    shape, _colors, report = heal(raw, [], tolerance)
    if not _shapes_of(shape, TopAbs_SOLID):
        places = _gaps(raw, tolerance)
        count = len(places)
        where = "; ".join(f"near ({x:.3g}, {y:.3g}, {z:.3g})" for x, y, z in places[:_PLACES])
        noun = "gap" if count == 1 else "gaps"
        raise IgesImportError(
            f"{owner}: the surfaces do not close a volume. {count} {noun} left, "
            f"{where}. Close them in the program that made the file, or use Heal with "
            "a larger gap."
        )
    valid = BRepCheck_Analyzer(shape).IsValid()
    if not valid:
        report.append(
            "Some faces could not be repaired. Later features on them may fail; "
            "use Delete Face to remove them."
        )
    if gap is not None:
        report.append(f"Healed with a gap of {tolerance:g} mm.")
    return StepImport(shape, [], report, valid)
