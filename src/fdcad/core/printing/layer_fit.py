"""Layer fit check: heights and wall thicknesses that are not a whole number of layers
or line widths of the printer profile (TR187 item 1, DECISIONS D1209).

Heights are the levels of flat faces that face up or down, measured from the
lowest point of the part as it lies on the bed. Walls are the gaps between two
flat faces that face away from each other, sideways, with material between
them. A slicer rounds each to whole layers or lines, so such sizes print a
little off. Kernel work: run it off the UI thread.
"""

from __future__ import annotations

from dataclasses import dataclass

from OCP.TopoDS import TopoDS_Shape

#: How far from a whole number of layers or lines a size may be, as a share of one.
SHARE = 0.1
#: Walls thicker than this many line widths are solid infill, not walls: not listed.
WALL_LINES = 8
#: The most flat faces looked at; more are left out of the wall pairs.
FACE_LIMIT = 1500


@dataclass(frozen=True)
class Misfit:
    """One size that is not whole: ``kind`` "height" or "wall", the size in mm, how
    many layers or lines it is, and the nearest whole size."""

    kind: str
    size: float
    count: float
    nearest: float


def _flat_faces(
    shape: TopoDS_Shape,
) -> list[tuple[tuple[float, float, float], tuple[float, float, float], float]]:
    """(normal, centre, area) of every flat face, normals out of the material."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepGProp import BRepGProp
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_REVERSED

    from fdcad.core.naming.names import faces_of

    out = []
    for face in faces_of(shape)[: FACE_LIMIT * 4]:
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Plane:
            continue
        d = surface.Plane().Axis().Direction()
        n = (d.X(), d.Y(), d.Z())
        if face.Orientation() == TopAbs_REVERSED:
            n = (-n[0], -n[1], -n[2])
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        c = props.CentreOfMass()
        out.append((n, (c.X(), c.Y(), c.Z()), props.Mass()))
        if len(out) >= FACE_LIMIT:
            break
    return out


def _misfit(kind: str, size: float, unit: float) -> Misfit | None:
    count = size / unit
    whole = round(count)
    if abs(count - whole) <= SHARE or size < unit * 0.5:
        return None
    return Misfit(kind, size, count, max(whole, 1) * unit)


def check(shape: TopoDS_Shape, layer_height: float, line_width: float) -> list[Misfit]:
    """The heights and walls of ``shape`` (as it lies on the bed) that are not whole."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    from fdcad.core.occ import point_inside

    if layer_height <= 0 or line_width <= 0:
        raise ValueError("the layer height and line width must be above zero")
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    if box.IsVoid():
        return []
    bottom = box.CornerMin().Z()
    faces = _flat_faces(shape)
    found: dict[tuple[str, float], Misfit] = {}
    for n, c, _area in faces:
        if abs(n[2]) > 1 - 1e-6:
            height = round(c[2] - bottom, 6)
            if height > 1e-6:
                hit = _misfit("height", height, layer_height)
                if hit is not None:
                    found.setdefault(("height", height), hit)
    sides = [(n, c) for n, c, _a in faces if abs(n[2]) < 1e-6]
    limit = WALL_LINES * line_width
    for i, (n1, c1) in enumerate(sides):
        for n2, c2 in sides[i + 1 :]:
            if n1[0] * n2[0] + n1[1] * n2[1] + n1[2] * n2[2] > -1 + 1e-6:
                continue  # not facing away from each other
            gap = (c2[0] - c1[0]) * n1[0] + (c2[1] - c1[1]) * n1[1] + (c2[2] - c1[2]) * n1[2]
            thickness = -gap  # face 2 lies behind face 1, inside the material
            if not 1e-6 < thickness <= limit:
                continue
            middle = (c1[0] - n1[0] * thickness / 2, c1[1] - n1[1] * thickness / 2,
                      c1[2] - n1[2] * thickness / 2)  # fmt: skip
            if not point_inside(shape, middle, 1e-7):  # each body on its own (D1082)
                continue
            size = round(thickness, 6)
            hit = _misfit("wall", size, line_width)
            if hit is not None:
                found.setdefault(("wall", size), hit)
    return sorted(found.values(), key=lambda m: (m.kind, m.size))


def describe(misfit: Misfit) -> str:
    """One line for the list, such as "Height 5.1 mm is 25.50 layers; 5.2 mm is whole"."""
    what = "layers" if misfit.kind == "height" else "line widths"
    label = "Height" if misfit.kind == "height" else "Wall"
    return (
        f"{label} {misfit.size:.4g} mm is {misfit.count:.2f} {what}; "
        f"{misfit.nearest:.4g} mm is whole"
    )
