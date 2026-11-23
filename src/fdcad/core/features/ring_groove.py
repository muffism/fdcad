"""Retaining ring grooves (TUTORIAL_REVIEW_SPEC_2 TR249, DECISIONS D874).

Type ``ring_groove``. Pick the round face of a shaft or a bore (``refs.face``). A
groove for a retaining ring is cut ``position`` from one end of the face
(``from_end``), sized from the round's diameter:

- ``ring`` on a shaft: an external retaining ring (DIN 471 table).
- ``ring`` in a bore: an internal retaining ring (DIN 472 table).
- ``e_clip``: an E clip on a shaft (DIN 6799 table, by shaft range).

The tables give the groove diameter and width, compiled from the published
standards. A diameter with no ring in the table is an error naming the nearest
sizes. New faces are ``<fid>/groove``.
"""

from __future__ import annotations

from typing import Any

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.units import Kind

KINDS = ("ring", "e_clip")

#: External rings: shaft diameter to (groove diameter, groove width).
SHAFT_RINGS: dict[float, tuple[float, float]] = {
    3: (2.8, 0.5),
    4: (3.8, 0.5),
    5: (4.8, 0.7),
    6: (5.7, 0.8),
    8: (7.6, 0.9),
    10: (9.6, 1.1),
    12: (11.5, 1.1),
    15: (14.3, 1.1),
    17: (16.2, 1.1),
    20: (19.0, 1.3),
    25: (23.9, 1.3),
    30: (28.6, 1.6),
    35: (33.0, 1.6),
    40: (37.5, 1.85),
    50: (47.0, 2.15),
}
#: Internal rings: bore diameter to (groove diameter, groove width).
BORE_RINGS: dict[float, tuple[float, float]] = {
    8: (8.4, 0.9),
    10: (10.4, 1.1),
    12: (12.5, 1.1),
    15: (15.7, 1.1),
    19: (20.0, 1.1),
    22: (23.0, 1.1),
    24: (25.2, 1.3),
    28: (29.4, 1.3),
    32: (33.7, 1.3),
    35: (37.0, 1.6),
    40: (42.5, 1.85),
    47: (49.5, 1.85),
    52: (55.0, 2.15),
}
#: E clips: (shaft over, shaft up to, groove diameter, groove width).
E_CLIPS: tuple[tuple[float, float, float, float], ...] = (
    (2.5, 3.0, 1.9, 0.54),
    (3.0, 4.0, 2.3, 0.64),
    (4.0, 5.0, 3.2, 0.64),
    (5.0, 7.0, 4.0, 0.74),
    (6.0, 8.0, 5.0, 0.74),
    (7.0, 9.0, 6.0, 0.74),
    (8.0, 11.0, 7.0, 0.94),
    (9.0, 12.0, 8.0, 0.94),
    (10.0, 14.0, 9.0, 1.05),
    (11.0, 15.0, 10.0, 1.15),
    (13.0, 18.0, 12.0, 1.35),
    (16.0, 24.0, 15.0, 1.55),
)
#: How close a round must be to a table diameter (mm).
MATCH = 0.3


def groove_for(kind: str, diameter: float, shaft: bool) -> tuple[float, float]:
    """(groove diameter, groove width) for a ring of ``kind`` on this round. Raises
    ValueError with a message that says what to do when no ring fits."""
    if kind == "e_clip":
        if not shaft:
            raise ValueError("E clips go on shafts. Pick a shaft face or choose Ring.")
        fits = [row for row in E_CLIPS if row[0] < diameter <= row[1] + 1e-9]
        if not fits:
            raise ValueError(
                f"No E clip fits a {diameter:.4g} mm shaft (2.5 to 24 mm). Choose Ring."
            )
        # The largest clip whose groove still leaves the shaft strong enough.
        _low, _high, groove, width = max(fits, key=lambda row: row[2])
        return groove, width
    table = SHAFT_RINGS if shaft else BORE_RINGS
    nearest = min(table, key=lambda d: abs(d - diameter))
    if abs(nearest - diameter) > MATCH:
        sizes = sorted(table, key=lambda d: abs(d - diameter))[:2]
        listed = " or ".join(f"{d:g} mm" for d in sorted(sizes))
        where = "shaft" if shaft else "bore"
        raise ValueError(
            f"No standard ring fits a {diameter:.4g} mm {where}. Change the {where} to {listed}."
        )
    return table[nearest]


def _value(feature: Feature, key: str, default: float) -> float:
    found = feature.params.get(key)
    return found.value if isinstance(found, Param) else default


@register
class RingGroove(FeatureType):
    """A retaining ring or E clip groove on a shaft or in a bore."""

    type_name = "ring_groove"
    makes_solid = True
    params = (
        ParamSpec("ring_type", choices=KINDS, default="ring"),
        ParamSpec("position", kind=Kind.LENGTH),
        ParamSpec("from_end", choices=("start", "end"), optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut the groove."""
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
        from OCP.gp import gp_Ax2, gp_Ax3, gp_Dir, gp_Pnt, gp_Vec

        from fdcad.core.features.bodies import in_body_of
        from fdcad.core.features.shaft_shape import _placed, _round_face
        from fdcad.core.features.solids import check_result, solids
        from fdcad.core.naming.names import NamedShape, carry, restrict
        from fdcad.core.occ import BRepAlgoAPI_Cut

        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part is empty. Add a body first.")
        kind = str(feature.params.get("ring_type", "ring"))
        if kind not in KINDS:
            raise FeatureError(f"{name}: unknown ring '{kind}'. Choose a ring in the panel.")
        axis, face, r, v0, v1, shaft = _round_face(feature, ctx)
        try:
            groove, width = groove_for(kind, 2 * r, shaft)
        except ValueError as exc:
            raise FeatureError(f"{name}: {exc}") from exc
        position = _value(feature, "position", 0.0)
        if position < 0 or position + width > v1 - v0 + 1e-9:
            raise FeatureError(
                f"{name}: the groove does not fit on the face there. "
                f"Enter a position from 0 to {v1 - v0 - width:.4g} mm."
            )
        start = (
            v0 + position
            if feature.params.get("from_end", "start") == "start"
            else (v1 - position - width)
        )
        direction = gp_Dir(axis.Direction().XYZ())
        frame = gp_Ax3(axis.Location().Translated(gp_Vec(direction).Multiplied(start)), direction)
        outer, inner = (r + 1.0, groove / 2) if shaft else (groove / 2, max(r - 1.0, 0.01))
        ring = BRepAlgoAPI_Cut(
            BRepPrimAPI_MakeCylinder(
                gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), outer, width
            ).Shape(),
            BRepPrimAPI_MakeCylinder(
                gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), inner, width
            ).Shape(),
        ).Shape()
        tool = _placed(ring, frame)

        # The groove is cut from the body of the picked face only (D2622): the ring
        # reaches 1 mm past the round, and cut into a hub on the shaft as well.
        def run(part: NamedShape) -> NamedShape:
            op: Any = BRepAlgoAPI_Cut(part.shape, tool)
            op.Build()
            if not op.IsDone() or not solids(op.Shape()):
                raise FeatureError(f"{name}: the groove could not be cut. Move it along the face.")
            shape = op.Shape()
            return NamedShape(
                shape, restrict(carry(part.faces, op.History()), shape, f"{feature.id}/groove")
            )

        result = in_body_of(ctx.body, face, feature.id, run)
        return FeatureResult(
            body=result, issues=check_result(feature.id, name, ctx.body, result, None)
        )
