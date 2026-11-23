"""Tab (TR165, DECISIONS D1100): a sketched piece of wall joined to the sheet.

Type ``sheet_tab``. A closed sketch drawn on a flat face of a wall (or on a plane
level with one) adds a piece exactly one sheet thickness thick to that wall, in
the wall's own frame, so it folds and flattens with the wall. Each closed region
of the sketch is one tab, so a sketch pattern of profiles makes a row of tabs.
Every tab must touch the wall it joins.

Params: none. Refs: ``sketch``, ``sheet_metal``.

Face roles: ``<fid>/side/<entity>`` and the wall's own roles.
"""

from __future__ import annotations

from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Trsf, gp_Vec

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    register,
)
from fdcad.core.features.extrude import sketch_input_raw
from fdcad.core.features.sheetmetal.common import require_sheet
from fdcad.core.features.sheetmetal.locate import bounds, local_vector
from fdcad.core.features.sheetmetal.model import (
    SheetModel,
    SheetResult,
    apply,
    box,
    common_with,
    volume,
)
from fdcad.core.features.solids import prism, solids, transform
from fdcad.core.naming.names import NamedShape

TYPE = "sheet_tab"
_TOL = 1e-5


@register
class SheetTab(FeatureType):
    """Adds sketched pieces of wall, one sheet thickness thick."""

    type_name = TYPE
    makes_solid = True
    params = ()

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Join the tabs to their wall and rebuild the sheet."""
        model = self.model(feature, ctx)
        return SheetResult(body=model.build(feature.id, feature.name), sheet=model)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The part with the tabs, for the live preview."""
        return self.model(feature, ctx).build(feature.id, feature.name)

    def model(self, feature: Feature, ctx: BuildContext) -> SheetModel:
        """The sheet with the tabs joined to their wall."""
        name, fid = feature.name, feature.id
        model = require_sheet(feature, ctx)
        sketch = sketch_input_raw(feature, ctx)
        if sketch.profile is None:
            raise FeatureError(f"{name}: the tab sketch must be closed. Close the contour.")
        t = model.thickness
        n = sketch.plane.normal
        # A prism through the sketch plane, three thicknesses long, cut to the wall's slab.
        long = gp_Vec(n[0] * 3 * t, n[1] * 3 * t, n[2] * 3 * t)
        world = prism(fid, sketch.profile, long)
        shift = gp_Vec(-n[0] * 1.5 * t, -n[1] * 1.5 * t, -n[2] * 1.5 * t)
        move = gp_Trsf()
        move.SetTranslation(shift)
        world = transform(world, move)
        places = model.placements(False)
        for wid in model.walls:
            if wid not in places:
                continue
            inv = places[wid].Inverted()
            if abs(abs(local_vector(inv, n)[2]) - 1) > 1e-6:
                continue
            level = apply(inv, sketch.plane.origin)[2]
            if abs(level) > _TOL and abs(level - t) > _TOL:
                continue
            local = transform(world, inv)
            lo, hi = bounds(local)
            slab = box(f"{fid}/slab", (lo[0] - 1, lo[1] - 1, 0.0), (hi[0] + 1, hi[1] + 1, t))
            tab = common_with(fid, local, slab)
            piece = model.piece(wid)
            dist = BRepExtrema_DistShapeShape(tab.shape, piece.shape)
            if not dist.IsDone() or dist.Value() > _TOL:
                continue
            before = volume(piece.shape)
            model.add_material(wid, [tab])
            joined = model.piece(wid)
            if len(solids(joined.shape)) != 1:
                raise FeatureError(
                    f"{name}: a tab does not touch the wall. Draw each tab so it meets "
                    "the edge of the wall."
                )
            if volume(joined.shape) - before <= _TOL:
                raise FeatureError(
                    f"{name}: the tabs lie inside the wall and add nothing. Draw them past "
                    "the edge of the wall."
                )
            return model
        raise FeatureError(
            f"{name}: the sketch is not on a flat face of a wall, or the tab does not touch "
            "the wall. Draw the sketch on a wall face and let it meet the wall's edge."
        )
