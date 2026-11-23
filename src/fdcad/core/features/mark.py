"""Mark: text and lines put on a face for laser etching or engraving (TR330, D2006).

Type ``mark``. Refs: ``sketch`` (``{"feature": id}``): its drawn curves and its
text are the marks. Params: ``depth`` (optional length): 0 or left out leaves the
part as it is and keeps the marks as lines with no depth; above 0 the closed
shapes of the sketch (letters, closed outlines) are cut that deep into the part
along the sketch normal, from the sketch plane.

The marks are kept in ``extras["marks"]`` (3D edges) and shown in the view. A
mark with no depth does not change the part, so it does not block sheet metal
work: the flat pattern writes marks that lie on the fixed wall to their own
``MARKS`` layer in DXF and SVG.

Face roles (depth above 0): faces of the part keep their names; the cut's faces
are ``<fid>/mark#k``.
"""

from __future__ import annotations

from typing import Any

from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Vec
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Edge

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.features.solids import FUZZY_TOLERANCE, compound, solids, volume_of
from fdcad.core.naming.names import NamedShape, carry, faces_of, restrict
from fdcad.core.occ import BRepAlgoAPI_Cut, ShapeMap
from fdcad.core.units import Kind

#: The deepest mark (mm); deeper is a cut, not a mark.
MOST_DEPTH = 5.0


def _sketch(feature: Feature, ctx: BuildContext) -> Any:
    owner = feature.name
    ref = feature.refs.get("sketch")
    fid = ref.get("feature") if isinstance(ref, dict) else None
    if not isinstance(fid, str) or ctx.results.get(fid) is None:
        raise FeatureError(f"{owner}: pick a sketch with the text or lines to mark.")
    out = ctx.result(fid).sketch
    if out is None:
        raise FeatureError(f"{owner}: the marks must come from a sketch. Pick a sketch.")
    return out


def mark_edges(out: Any, owner: str) -> list[TopoDS_Edge]:
    """The sketch's drawn curves and the outlines of its text, as 3D edges."""
    from fdcad.core.features.curves import sketch_curve_edges
    from fdcad.core.sketch.text import text_faces

    edges = list(sketch_curve_edges(out, owner))
    for face in text_faces(out.model, out.plane):
        explorer = TopExp_Explorer(face, TopAbs_EDGE)
        while explorer.More():
            edges.append(TopoDS.Edge(explorer.Current()))
            explorer.Next()
    return edges


@register
class Mark(FeatureType):
    """Text and lines on a face, with no depth or a small one."""

    type_name = "mark"
    makes_solid = True
    params = (ParamSpec("depth", kind=Kind.LENGTH, optional=True),)

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Keep the marks, and cut them in when they have a depth."""
        owner = feature.name
        out = _sketch(feature, ctx)
        edges = mark_edges(out, owner)
        if not edges:
            raise FeatureError(f"{owner}: the sketch has nothing to mark. Add text or lines.")
        value = feature.params.get("depth")
        depth = value.value if isinstance(value, Param) else 0.0
        if depth < 0 or depth > MOST_DEPTH:
            raise FeatureError(
                f"{owner}: the depth must be 0 to {MOST_DEPTH:g} mm. Enter a smaller depth."
            )
        body = ctx.body
        result = FeatureResult(body=body)
        if depth > 1e-9:
            if body is None:
                raise FeatureError(f"{owner}: the part is empty. Add a body to mark first.")
            # The marks are cut into the body of the face the sketch was drawn on
            # (D2622). They were cut into the whole part, which side cut more: on a
            # thin plate with a block lying on it, that was the block. A sketch on a
            # plane still marks every body it meets.
            from fdcad.core.features.bodies import in_body_of, sketch_face

            on = sketch_face(feature, ctx)

            def run(part: NamedShape) -> NamedShape:
                return self._cut(feature, out, part, depth)

            result.body = run(body) if on is None else in_body_of(body, on, feature.id, run)
        result.extras["marks"] = edges
        result.extras["reference"] = compound(edges)
        return result

    @staticmethod
    def _cut(feature: Feature, out: Any, body: NamedShape, depth: float) -> NamedShape:
        owner, fid = feature.name, feature.id
        profile = out.profile
        faces = list(profile.faces) if profile is not None else []
        if not faces:
            raise FeatureError(
                f"{owner}: only closed shapes and text can have a depth. Enter 0 for the depth "
                "or close the shapes."
            )
        n = out.plane.normal
        best = None
        for sign in (-1.0, 1.0):  # into the material, whichever side of the plane it is
            step = gp_Vec(n[0] * depth * sign, n[1] * depth * sign, n[2] * depth * sign)
            tool = compound([BRepPrimAPI_MakePrism(f, step).Shape() for f in faces])
            cut = BRepAlgoAPI_Cut(body.shape, tool)
            cut.SetFuzzyValue(FUZZY_TOLERANCE)
            cut.Build()
            if not cut.IsDone():
                continue
            removed = volume_of(body.shape) - volume_of(cut.Shape())
            if best is None or removed > best[0]:
                best = (removed, cut)
        if best is None or best[0] <= 1e-9:
            raise FeatureError(
                f"{owner}: the marks do not touch the part. Draw the sketch on the face to mark."
            )
        cut = best[1]
        shape = compound(solids(cut.Shape()))
        names = carry(body.faces, cut.History())
        named = ShapeMap()
        for _n, f in names:
            named.Add(f)
        k = 0
        for face in faces_of(shape):
            if not named.Contains(face):
                k += 1
                names.append((f"{fid}/mark#{k}", face))
        return NamedShape(shape, restrict(names, shape, fid))
