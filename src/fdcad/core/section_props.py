"""Section properties of a flat face or a closed sketch (TR81, DECISIONS D1019).

For one or more faces in one plane: the area, the centroid, the second moments of
area about axes through the centroid along the plane's X and Y directions, their
product, the polar moment, and the principal moments with their axes. The kernel's
surface properties give the area, the centroid and the inertia tensor about the
centroid for a unit surface density; for points in the plane the tensor's in-plane
terms are the second moments of area. Kernel work, run in a kernel job.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.GeomAbs import GeomAbs_Plane
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_FACE
from OCP.TopoDS import TopoDS, TopoDS_Shape

Vec3 = tuple[float, float, float]
#: How far apart (mm, and the sine of an angle) faces may be and still count as one plane.
_FLAT = 1e-6


@dataclass(frozen=True)
class SectionProperties:
    """Everything in millimetres: area mm2, moments mm4."""

    faces: int
    area: float
    centroid: Vec3
    #: The plane's X and Y directions and its normal, in model axes.
    x_dir: Vec3
    y_dir: Vec3
    normal: Vec3
    #: Second moments about the centroid: about the axis along X (sum of y squared),
    #: about the axis along Y (sum of x squared), and the product (sum of x times y).
    ixx: float
    iyy: float
    ixy: float
    #: Polar moment about the normal through the centroid (ixx + iyy).
    polar: float
    #: Principal moments, smallest first, with their axes (in the plane, model axes).
    principal: tuple[float, float]
    axes: tuple[Vec3, Vec3]
    #: Angle in degrees from the plane's X direction to the first principal axis.
    angle: float


def _plane_axes(face: TopoDS_Shape) -> tuple[Vec3, Vec3, Vec3, Vec3]:
    """Origin, X, Y and normal of a flat face's plane. Raises ValueError for a curved face."""
    surface = BRepAdaptor_Surface(TopoDS.Face(face))
    if surface.GetType() != GeomAbs_Plane:
        raise ValueError("the face is not flat. Pick a flat face or a closed sketch.")
    pos = surface.Plane().Position()
    loc, x, y, n = pos.Location(), pos.XDirection(), pos.YDirection(), pos.Direction()
    return (
        (loc.X(), loc.Y(), loc.Z()),
        (x.X(), x.Y(), x.Z()),
        (y.X(), y.Y(), y.Z()),
        (n.X(), n.Y(), n.Z()),
    )


def section_properties(
    faces: Sequence[TopoDS_Shape], x_dir: Vec3 | None = None, normal: Vec3 | None = None
) -> SectionProperties:
    """Section properties of ``faces`` together. ``x_dir`` and ``normal`` give the axes the
    moments are about (a sketch's axes); by default the first face's plane gives them.
    Raises ValueError when there is no face, a face is curved or the faces are not in one
    plane."""
    if not faces:
        raise ValueError("there is nothing to measure. Pick a flat face or a closed sketch.")
    for face in faces:
        if face.ShapeType() != TopAbs_FACE:
            raise ValueError("only faces have section properties. Pick a flat face.")
    origin, fx, _fy, fn = _plane_axes(faces[0])
    n0 = np.array(fn)
    for face in faces[1:]:
        o, _x, _y, other_n = _plane_axes(face)
        if (
            np.linalg.norm(np.cross(n0, np.array(other_n))) > _FLAT
            or abs(float(np.dot(np.array(o) - np.array(origin), n0))) > _FLAT * 1e3
        ):
            raise ValueError("the faces are not in one plane. Pick faces in one plane.")
    n = np.array(normal if normal is not None else fn, dtype=float)
    n /= np.linalg.norm(n)
    x = np.array(x_dir if x_dir is not None else fx, dtype=float)
    x = x - float(x @ n) * n
    if np.linalg.norm(x) < _FLAT:
        raise ValueError("the X direction runs along the normal. Use another X direction.")
    x /= np.linalg.norm(x)
    y = np.cross(n, x)

    total = GProp_GProps()
    for face in faces:
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        total.Add(props)
    area = abs(total.Mass())
    if area <= 0:
        raise ValueError("the face has no area. Pick a face with an area.")
    centre = total.CentreOfMass()
    matrix = total.MatrixOfInertia()
    tensor = np.array([[matrix.Value(i, j) for j in (1, 2, 3)] for i in (1, 2, 3)])
    tensor = (tensor + tensor.T) / 2
    if total.Mass() < 0:  # reversed faces report a negative area and moments
        tensor = -tensor
    rot = np.array([x, y, n])
    local = rot @ tensor @ rot.T
    # For points in the plane: local[0][0] = sum y^2, local[1][1] = sum x^2,
    # local[0][1] = -sum x y.
    ixx, iyy, ixy = float(local[0][0]), float(local[1][1]), float(-local[0][1])
    moments, vectors = np.linalg.eigh(np.array([[ixx, -ixy], [-ixy, iyy]]))
    first = vectors[:, 0]
    if first[0] < -_FLAT or (abs(first[0]) <= _FLAT and first[1] < 0):
        first = -first  # the axis has no sign: keep the angle in (-90, 90]
    angle = math.degrees(math.atan2(float(first[1]), float(first[0])))
    axis1 = float(first[0]) * x + float(first[1]) * y
    axis2 = np.cross(n, axis1)
    axes = [tuple(float(v) for v in axis1), tuple(float(v) for v in axis2)]
    return SectionProperties(
        faces=len(faces),
        area=area,
        centroid=(centre.X(), centre.Y(), centre.Z()),
        x_dir=tuple(float(v) for v in x),  # type: ignore[arg-type]
        y_dir=tuple(float(v) for v in y),  # type: ignore[arg-type]
        normal=tuple(float(v) for v in n),  # type: ignore[arg-type]
        ixx=ixx,
        iyy=iyy,
        ixy=ixy,
        polar=ixx + iyy,
        principal=(float(moments[0]), float(moments[1])),
        axes=(axes[0], axes[1]),  # type: ignore[arg-type]
        angle=angle,
    )


def section_report(props: SectionProperties, inch: bool) -> list[tuple[str, str]]:
    """Label and value rows for the window and the Copy button."""
    unit = "in" if inch else "mm"
    k = 1 / 25.4 if inch else 1.0

    def vec(v: Vec3, scale: float = 1.0, suffix: str = "") -> str:
        return ", ".join(f"{c * scale:.6g}" for c in v) + suffix

    return [
        ("Faces", str(props.faces)),
        ("Area", f"{props.area * k**2:.6g} {unit}^2"),
        ("Centroid", vec(props.centroid, k, f" {unit}")),
        ("Plane X direction", vec(props.x_dir)),
        ("Plane normal", vec(props.normal)),
        ("Ixx (about X through the centroid)", f"{props.ixx * k**4:.6g} {unit}^4"),
        ("Iyy (about Y through the centroid)", f"{props.iyy * k**4:.6g} {unit}^4"),
        ("Ixy", f"{props.ixy * k**4:.6g} {unit}^4"),
        ("Polar moment J", f"{props.polar * k**4:.6g} {unit}^4"),
        ("Principal moment I1", f"{props.principal[0] * k**4:.6g} {unit}^4"),
        ("Principal moment I2", f"{props.principal[1] * k**4:.6g} {unit}^4"),
        ("Principal axis 1", vec(props.axes[0])),
        ("Principal axis 2", vec(props.axes[1])),
        ("Angle from X to axis 1", f"{props.angle:.6g} deg"),
    ]
