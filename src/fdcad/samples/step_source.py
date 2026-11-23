"""Write coloured STEP files in code, for the import sample part and its tests.

The file is written through OpenCascade's document writer so face and solid
colours are kept. The header time stamp is replaced by a fixed one, so the same
shape always gives the same bytes and the saved sample does not change.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.Quantity import Quantity_Color
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_AsIs
from OCP.TCollection import TCollection_AsciiString, TCollection_ExtendedString
from OCP.TDocStd import TDocStd_Document
from OCP.TopoDS import TopoDS_Face, TopoDS_Shape
from OCP.XCAFDoc import XCAFDoc_ColorGen, XCAFDoc_ColorSurf, XCAFDoc_DocumentTool

_STAMP = re.compile(rb"FILE_NAME\('([^']*)','[^']*'")
_PRODUCT = re.compile(rb"Open CASCADE STEP translator [0-9.]+ [0-9]+")


def _color(hex_color: str) -> Quantity_Color:
    color = Quantity_Color()
    if not Quantity_Color.ColorFromHex_s(hex_color, color):
        raise ValueError(f"Not a colour: {hex_color}")
    return color


def colored_step_bytes(
    shape: TopoDS_Shape,
    color: str | None = None,
    face_colors: list[tuple[TopoDS_Face, str]] | None = None,
) -> bytes:
    """STEP AP214 text of ``shape`` with a body colour and per face colours."""
    doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    shapes = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    colors = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    label = shapes.AddShape(shape, False)
    if color is not None:
        colors.SetColor(label, _color(color), XCAFDoc_ColorGen)
    for face, hex_color in face_colors or []:
        sub = shapes.AddSubShape(label, face)
        colors.SetColor(sub, _color(hex_color), XCAFDoc_ColorSurf)
    # Other code (STEP export) may have changed the writer's global settings.
    Interface_Static.SetCVal_s("write.step.schema", "AP214IS")
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(False)
    if not writer.Transfer(doc, STEPControl_AsIs):
        raise RuntimeError("The shape could not be written as STEP.")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "source.step"
        if writer.Write(TCollection_AsciiString(str(path)).ToCString()) != IFSelect_RetDone:
            raise RuntimeError("The STEP file could not be written.")
        data = path.read_bytes()
    data = _PRODUCT.sub(b"FDCAD sample", data)
    return _STAMP.sub(rb"FILE_NAME('\1','2026-01-01T00:00:00'", data, count=1)
