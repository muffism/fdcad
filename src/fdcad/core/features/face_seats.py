"""Face Seats: copies of a seed body set over a curved face (TR405, DECISIONS D2009).

Type ``face_seats``. Refs: ``on_face`` (the face to cover: a cylinder, sphere, cone,
torus or free form face) and ``seed`` (a face of a separate body, the seed: it is
modelled at the origin with +Z pointing out of the face it will sit on). The seed
body is used up. Params:

- ``count_u`` and ``count_v``: copies along the face's two directions (1 to 100
  each); copies whose spot is off the face are left out.
- ``sink``: optional length: how far each copy sinks into the face along the
  normal (so studs join and dimples bite).
- ``operation``: ``boss`` (default: join the copies, for studs and rivets) or
  ``cut`` (cut them away, for dimples).

Each copy's origin goes to a spot on the face, its +Z to the face's outward
normal there and its +X along the face's first direction. Copy faces are
``<fid>/seat<k>/...`` (boss) or ``<fid>/seat#k`` (cut).
"""

from __future__ import annotations

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.BRepLProp import BRepLProp_SLProps
from OCP.BRepTools import BRepTools
from OCP.gp import gp_Ax3, gp_Dir, gp_Pnt, gp_Pnt2d, gp_Trsf, gp_Vec
from OCP.TopAbs import TopAbs_IN, TopAbs_REVERSED
from OCP.TopoDS import TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.features.solids import compound, solids
from fdcad.core.naming.names import NamedShape, faces_of, restrict
from fdcad.core.occ import ShapeMap
from fdcad.core.units import Kind

#: Most copies along one direction.
MOST_COPIES = 100


def _count(feature: Feature, name: str) -> int:
    value = feature.params.get(name)
    return round(value.value) if isinstance(value, Param) else 1


def spots(face: TopoDS_Face, count_u: int, count_v: int) -> list[tuple[gp_Pnt, gp_Vec, gp_Vec]]:
    """(point, outward normal, first direction) at the middles of a count_u by
    count_v grid over the face's parameter range, for the spots on the face."""
    u0, u1, v0, v1 = BRepTools.UVBounds_s(face)
    surface = BRepAdaptor_Surface(face)
    flip = face.Orientation() == TopAbs_REVERSED
    out = []
    for i in range(count_u):
        for j in range(count_v):
            u = u0 + (u1 - u0) * (i + 0.5) / count_u
            v = v0 + (v1 - v0) * (j + 0.5) / count_v
            if BRepClass_FaceClassifier(face, gp_Pnt2d(u, v), 1e-7).State() != TopAbs_IN:
                continue
            props = BRepLProp_SLProps(surface, u, v, 1, 1e-7)
            if not props.IsNormalDefined():
                continue
            n = gp_Vec(props.Normal())
            if flip:
                n.Reverse()
            du = gp_Vec(props.D1U().XYZ())
            du = du.Subtracted(n.Multiplied(du.Dot(n)))
            if du.Magnitude() < 1e-9:
                continue
            out.append((props.Value(), n.Normalized(), du.Normalized()))
    return out


def _placed(seed: TopoDS_Shape, point: gp_Pnt, normal: gp_Vec, along: gp_Vec, sink: float):  # type: ignore[no-untyped-def]
    at = point.Translated(normal.Multiplied(-sink))
    trsf = gp_Trsf()
    trsf.SetDisplacement(gp_Ax3(), gp_Ax3(at, gp_Dir(normal), gp_Dir(along)))
    return BRepBuilderAPI_Transform(seed, trsf, True).Shape()


@register
class FaceSeats(FeatureType):
    """Copies of a seed body turned to a curved face's normal."""

    type_name = "face_seats"
    makes_solid = True
    params = (
        ParamSpec("count_u", kind=Kind.NUMBER),
        ParamSpec("count_v", kind=Kind.NUMBER),
        ParamSpec("sink", kind=Kind.LENGTH, optional=True),
        ParamSpec("operation", choices=("boss", "cut"), default="boss"),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Place the copies and join or cut them."""
        from fdcad.core.features.bodies import body_index
        from fdcad.core.features.lookup import resolve_face

        owner, fid = feature.name, feature.id
        body = ctx.body
        if body is None:
            raise FeatureError(f"{owner}: the part is empty. Add a body and a seed first.")
        face_ref, seed_ref = feature.refs.get("on_face"), feature.refs.get("seed")
        if isinstance(face_ref, list):
            face_ref = face_ref[0] if face_ref else None
        if isinstance(seed_ref, list):
            seed_ref = seed_ref[0] if seed_ref else None
        if not isinstance(face_ref, dict):
            raise FeatureError(f"{owner}: pick the face to cover.")
        if not isinstance(seed_ref, dict):
            raise FeatureError(f"{owner}: pick the seed body, modelled at the origin.")
        face, issues = resolve_face(body, face_ref, owner)
        seed_index, more = body_index(ctx, seed_ref, owner)
        issues += more
        pieces = solids(body.shape)
        seed = pieces[seed_index]
        if any(f.IsSame(face) for f in faces_of(seed)):
            raise FeatureError(f"{owner}: the face is on the seed. Pick a face of another body.")
        count_u, count_v = _count(feature, "count_u"), _count(feature, "count_v")
        if not (1 <= count_u <= MOST_COPIES and 1 <= count_v <= MOST_COPIES):
            raise FeatureError(
                f"{owner}: use 1 to {MOST_COPIES} copies each way. Enter smaller counts."
            )
        value = feature.params.get("sink")
        sink = value.value if isinstance(value, Param) else 0.0
        found = spots(face, count_u, count_v)
        if not found:
            raise FeatureError(f"{owner}: no copy lands on the face. Enter other counts.")
        copies = [_placed(seed, p, n, d, sink) for p, n, d in found]
        rest = [s for i, s in enumerate(pieces) if i != seed_index]
        operation = str(feature.params.get("operation", "boss"))
        seed_faces = ShapeMap()
        for f in faces_of(seed):
            seed_faces.Add(f)
        target = NamedShape(
            compound(rest), [(n, f) for n, f in body.faces if not seed_faces.Contains(f)]
        )
        # Through ``combine`` (D1055): a plain fuse with every other body of the part
        # also joined bodies that had nothing to do with the copies but shared a face
        # with each other (two halves left by a split, an inlay in its pocket).
        from fdcad.core.features.solids import combine

        try:
            done = combine(
                fid, owner, target, NamedShape(compound(copies), []),
                "cut" if operation == "cut" else "boss", pieces=True,
            )  # fmt: skip
        except FeatureError:
            raise FeatureError(
                f"{owner} failed: the copies could not be joined to the part. Change the sink "
                "or the counts."
            ) from None
        if not solids(done.shape):
            raise FeatureError(
                f"{owner} failed: the copies could not be joined to the part. Change the sink "
                "or the counts."
            )
        # The copies' faces come back with the fallback name; they are the seats.
        plain = f"{fid}/face#"
        names = [
            (f"{fid}/seat#{n[len(plain) :]}" if n.startswith(plain) else n, f)
            for n, f in done.faces
        ]
        shape = done.shape
        return FeatureResult(body=NamedShape(shape, restrict(names, shape, fid)), issues=issues)
