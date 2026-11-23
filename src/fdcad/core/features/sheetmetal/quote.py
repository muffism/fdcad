"""Flat pattern data for quoting (TR172, DECISIONS D1106).

From the flat part's top face: the blank area, the outer and inner cut lengths, the
number of cut outs (holes in the blank), the number of bends and the flat box length
and width. The Flat Pattern keeps them in its result's ``extras`` so equations read
them as ``blank_area@Flat Pattern`` and so on, and the panel and the CSV export show
them.
"""

from __future__ import annotations

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.BRepTools import BRepTools
from OCP.GeomAbs import GeomAbs_Plane
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_WIRE
from OCP.TopExp import TopExp_Explorer

from fdcad.core.features.sheetmetal.model import SheetModel
from fdcad.core.features.solids import transform
from fdcad.core.naming.names import NamedShape, faces_of

#: Names of the quoting values, in the order the panel and the CSV show them.
QUOTE_NAMES = (
    "blank_area",
    "outer_cut_length",
    "inner_cut_length",
    "cut_outs",
    "bends",
    "flat_length",
    "flat_width",
)


def _length(shape: object) -> float:
    props = GProp_GProps()
    BRepGProp.LinearProperties_s(shape, props)
    return float(props.Mass())


def quote_values(
    model: SheetModel, flat: NamedShape, size: tuple[float, float] | None
) -> dict[str, float]:
    """The quoting values of a merged flat part (mm and square mm)."""
    local = transform(flat, model.frame.Inverted())
    t = model.thickness
    area = outer = inner = 0.0
    holes = 0
    for face in faces_of(local.shape):
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Plane:
            continue
        pln = surface.Plane()
        if abs(abs(pln.Axis().Direction().Z()) - 1) > 1e-9 or abs(pln.Location().Z() - t) > 1e-6:
            continue
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        area += props.Mass()
        outer_wire = BRepTools.OuterWire_s(face)
        explorer = TopExp_Explorer(face, TopAbs_WIRE)
        while explorer.More():
            wire = explorer.Current()
            explorer.Next()
            if wire.IsSame(outer_wire):
                outer += _length(wire)
            else:
                inner += _length(wire)
                holes += 1
    length, width = size if size is not None else (0.0, 0.0)
    return {
        "blank_area": area,
        "outer_cut_length": outer,
        "inner_cut_length": inner,
        "cut_outs": float(holes),
        "bends": float(len(model.bends)),
        "flat_length": length,
        "flat_width": width,
    }


def quote_csv(values: dict[str, float]) -> str:
    """The quoting values as CSV text: one name and value per row, mm and square mm."""
    rows = ["name,value"]
    for name in QUOTE_NAMES:
        value = values.get(name, 0.0)
        text = f"{value:.0f}" if name in ("cut_outs", "bends") else f"{value:.4f}"
        rows.append(f"{name},{text}")
    return "\n".join(rows) + "\n"
