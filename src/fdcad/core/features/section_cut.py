"""Section Cut: a section view kept as a cut body feature (TR151 item 2, D2205).

Type ``section_cut``. No refs and no params. Data key ``zones``: the zones the
section view cut away when the feature was made, each a list of one to three
planes, each plane a dict with ``origin`` and ``normal`` (three numbers each, mm
and a unit vector in part space). Material in front of every plane of a zone
(on the normal side) is removed, as the section view hides it (D253, D1603).

The planes are a copy of the section view, so they do not follow later changes.
Cut faces are ``<fid>/zone<z>.plane<p>`` (from 1).
"""

from __future__ import annotations

import math
from typing import Any

from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Vec
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    register,
)
from fdcad.core.features.booleans import boolean_named
from fdcad.core.features.solids import bounding_size, compound, polygon_face, solids
from fdcad.core.naming.names import NamedFace, NamedShape, faces_of
from fdcad.core.occ import BRepAlgoAPI_Common

Vec3 = tuple[float, float, float]
#: Most zones a section has: three planes give eight zones, one of which stays.
MOST_ZONES = 7


def _unit(v: Vec3) -> Vec3 | None:
    n = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
    return None if n < 1e-12 else (v[0] / n, v[1] / n, v[2] / n)


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def _vec(raw: Any) -> Vec3:
    values = [float(x) for x in raw]
    if len(values) != 3 or not all(math.isfinite(x) for x in values):
        raise ValueError("a point needs three numbers")
    return values[0], values[1], values[2]


def read_zones(feature: Feature) -> list[list[tuple[Vec3, Vec3]]]:
    """The zones of ``feature`` as (origin, unit normal) planes. Raises FeatureError."""
    raw = feature.data.get("zones")
    try:
        if not isinstance(raw, list) or not 1 <= len(raw) <= MOST_ZONES:
            raise ValueError("no zones")
        zones: list[list[tuple[Vec3, Vec3]]] = []
        for zone in raw:
            if not isinstance(zone, list) or not 1 <= len(zone) <= 3:
                raise ValueError("a zone needs one to three planes")
            planes = []
            for plane in zone:
                normal = _unit(_vec(plane["normal"]))
                if normal is None:
                    raise ValueError("a plane has no normal")
                planes.append((_vec(plane["origin"]), normal))
            zones.append(planes)
    except (KeyError, TypeError, ValueError) as exc:
        raise FeatureError(
            f"{feature.name}: its section planes are damaged ({exc}). Delete it and make it "
            "again from the section view."
        ) from None
    return zones


def zones_data(zones: list[list[tuple[Vec3, Vec3]]]) -> dict[str, Any]:
    """Feature data for the zones (origin, normal) a section view cuts away."""
    return {"zones": [[{"origin": list(o), "normal": list(n)} for o, n in zone] for zone in zones]}


def _slab(origin: Vec3, normal: Vec3, centre: Vec3, size: float) -> TopoDS_Shape:
    """A box on the front side of the plane, reaching ``size`` past ``centre`` each way."""
    seed = (1.0, 0.0, 0.0) if abs(normal[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = _unit(_cross(normal, seed))
    assert u is not None
    v = _cross(normal, u)
    d = sum((centre[i] - origin[i]) * normal[i] for i in range(3))
    foot = tuple(centre[i] - d * normal[i] for i in range(3))
    corners = [
        tuple(foot[i] + a * size * u[i] + b * size * v[i] for i in range(3))
        for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))
    ]
    face = polygon_face(corners)  # type: ignore[arg-type]
    depth = 2 * size + abs(d)
    prism = BRepPrimAPI_MakePrism(face, gp_Vec(*(normal[i] * depth for i in range(3))))
    return prism.Shape()


@register
class SectionCut(FeatureType):
    """Removes what a section view hid (TR151 item 2, D2205)."""

    type_name = "section_cut"
    #: It changes the part (D1063). It was marked as not doing so: the rebuild then
    #: gave the next feature the part from before the cut, so the cut was gone as soon
    #: as anything was added after it, and the cut was not made again when a feature
    #: before it changed.
    makes_solid = True

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        owner = feature.name
        body = ctx.body
        if body is None or not solids(body.shape):
            raise FeatureError(f"{owner}: the part is empty. Add a body first.")
        zones = read_zones(feature)
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib

        box = Bnd_Box()
        BRepBndLib.Add_s(body.shape, box)
        lo, hi = box.CornerMin(), box.CornerMax()
        centre = ((lo.X() + hi.X()) / 2, (lo.Y() + hi.Y()) / 2, (lo.Z() + hi.Z()) / 2)
        size = bounding_size(body.shape) + 10.0
        tools: list[TopoDS_Shape] = []
        names: list[NamedFace] = []
        for z, zone in enumerate(zones, start=1):
            piece: TopoDS_Shape | None = None
            for origin, normal in zone:
                slab = _slab(origin, normal, centre, size)
                if piece is None:
                    piece = slab
                    continue
                common = BRepAlgoAPI_Common(piece, slab)
                if not common.IsDone():
                    raise FeatureError(
                        f"{owner} failed: the section planes could not be combined. "
                        "Turn the planes slightly and make it again."
                    )
                piece = common.Shape()
            assert piece is not None
            tools.append(piece)
            for face in faces_of(piece):
                k = _plane_of(face, zone)
                if k is not None:
                    names.append((f"{feature.id}/zone{z}.plane{k}", face))
        try:
            cut = boolean_named("cut", body, NamedShape(compound(tools), names), feature.id, owner)
        except FeatureError as exc:
            raise FeatureError(
                f"{exc} The section may remove the whole part: move the section planes "
                "and make it again."
            ) from None
        return FeatureResult(body=cut)


def _plane_of(face: Any, zone: list[tuple[Vec3, Vec3]]) -> int | None:
    """Which plane of ``zone`` the flat ``face`` lies on (from 1), or None."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    c = props.CentreOfMass()
    for k, (origin, normal) in enumerate(zone, start=1):
        d = sum(((c.X(), c.Y(), c.Z())[i] - origin[i]) * normal[i] for i in range(3))
        if abs(d) < 1e-6:
            return k
    return None
