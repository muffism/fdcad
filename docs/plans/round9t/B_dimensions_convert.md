# Round 9t group B: dimensions and convert

Design note for D515 to D517, updated to match what was built.

## a. Decisions

D515: Arc length dimension (TOOL_SPEC T4.1, "an arc, then its two end points"). (1) In Smart Dimension, an arc and both of its end points, picked in any order (arc first, end points first, or an end point, the arc and the other end point), give an arc length dimension; the next click places it, as for other dimensions. A third pick is taken only when it completes such a set, so two end points alone still give a distance as before. (2) It is stored as a new sketch dimension type `arc_length` whose `entities` holds only the arc id: the end points are the arc's own, so naming them again adds nothing and the dimension can never disagree with them. (3) Solver: the planegcs arc length constraint on the arc with a fixed value; measure: radius times the counter clockwise sweep (`solver.arc_length`). Driving and reference both work; a driving one that conflicts goes through the same over define prompt or setting as other dimensions. Construction arcs take it too. (4) Display: the dimension line is an arc concentric with the measured arc, 24 pixels outside it when placed automatically or through the dragged text, with extension lines from the arc's end points; the value is plain (no prefix). The value box, the cursor preview, label drag (`label` offset from the point halfway along the arc), the Dimension panel ("Arc Length") and equations names (`d4@Sketch 1`) work as for every other dimension. (5) File: `arc_length` is an optional new value in the existing list of dimension types (FDEF_SPEC 6 item 5), an addition to schema 1; files without it open and save unchanged. Unknown dimension types are read and written back unchanged by every FDCAD version, and the solver stops at them with "Unknown dimension type", so an older FDCAD shows a sketch error on such a sketch but loses nothing on save.
Status: Default
Reason: Holding only the arc keeps the file small and needs no new key, and the solver already has an exact arc length constraint.

D516: Shift click picks Nearest or Farthest (TOOL_SPEC T4.3 item 3). (1) In Smart Dimension, a circle or arc clicked with Shift held is measured to its near or far side instead of its centre. The side is read from the click when the dimension is placed: Nearest when the click point is closer to the other picked item than the circle's centre is, Farthest otherwise. The other item is measured square to it for a line, or from its centre for another circle or arc. (2) The circle may be picked first or second; the click point is kept with the pick. Two Shift clicked circles each decide against the other's centre. The preview that follows the cursor already shows the chosen side. (3) As T4.3.2 and D123 say, there is no side with a point, so Shift does nothing there; it also does nothing when two circles are placed as a horizontal or vertical distance, which always run between centres. (4) Without Shift nothing changes: the centre is used, and the Dimension panel's Measure to choice still changes the side afterwards. The side is stored in the existing `measure_to` key (no new key).
Status: Default
Reason: Comparing the click with the centre against the other item gives the side the user clicked on without any extra prompt.

D517: Convert curve features into a sketch (IDEAS.md item 2, D438, D292 item 5). (1) Convert Entities also takes curve features: every feature whose result carries a curve (contour curves, projected curves, composite curves, helices and spirals, and the other curve features of PHASE3_SPEC P3.6 and P3.7). While the tool is active, clicking a curve feature in the feature tree converts it, and the curve features are drawn as faint dotted reference curves in the sketch view, where hovering one highlights the whole feature and a click converts it (a part outline edge under the cursor comes first). Only curve features above the sketch in the tree and not suppressed are offered (for a new sketch, all of them), so a sketch never copies a later feature. (2) When the sketch opens, every edge of those curves is projected onto the sketch plane along the sketch normal in a background job (CLAUDE.md rule 2; `core/sketch/curve_projection.py`). A straight edge becomes a line; a round edge whose axis is along the sketch normal becomes an arc or a full circle; an edge whose projection is straight (a circle seen edge on, worked out exactly from the circle) becomes a line; every other edge becomes a spline (the D278 entity) through 8 to 64 points spread evenly along its parameter, as many as the kernel needs to keep within 0.01 mm, with smooth default handles (a closed curve also stays smooth where it closes). Neighbouring pieces share exact end coordinates, so the copy of a closed loop is a closed contour that makes a profile. (3) Edges that project to a point or to less than 0.0001 mm are skipped, and the status bar says so: "Converted Contour 1: 6 curves. 6 edges were skipped because they project to a point." A piece that already has a fixed curve on it is not copied again, so contour loops stacked on top of each other (seen along the contour direction) are copied once; a curve already fully in the sketch gives "Contour 1 is already in the sketch.", and a tree pick of another feature says it is not a curve feature above this sketch. (4) The copies are fixed, like converted part edges (D275), and For construction makes construction curves. They are not linked to the curve feature: the existing link (FDEF_SPEC 6 item 9, D250) names a part edge or corner of the solid body and is checked against the body's projected edges in the sketch rebuild; curve features are not part of the body, and splines have no link target, so a link would need a new source kind, a new matcher and a new file key. A copy that never moves silently is the safe default (rule 12). (5) The whole conversion of one feature is one sketch undo step. No file key is added. The pure part (pieces, adding them to the sketch, the duplicate check) is `core/sketch/curve_convert.py`, with no kernel import so the sketch tools stay light.
Status: Default
Reason: Reusing Convert Entities, the fixed copy rule and the spline entity turns contour curves into sketch geometry with no new command and no file change.

## b. CHANGELOG (Added)

- Sketch: Convert Entities copies curve features (contours, projected and composite curves, helices) onto the sketch plane as lines, arcs, circles and splines. Pick the curve in the feature tree or its dotted outline in the sketch (D517).
- Sketch: arc length dimensions (pick an arc and its two end points), and Shift click on a circle or arc in Smart Dimension measures to its near or far side (D515, D516).

## c. User guide

Page `docs/user_guide/sketching.md`.

Under "Convert Entities", add:

> Convert Entities also copies curve features, such as contour curves, projected curves and helices. While the tool is active, click the curve feature in the feature tree, or click its dotted outline in the sketch. Only curve features above the sketch in the tree are offered. Each edge is projected straight onto the sketch plane. Straight and round edges become lines, arcs and circles; other edges become splines. Edges that project to a point are skipped, and the status bar says how many. Contour loops that land on top of each other are copied once. The copies are fixed and do not follow later changes to the curve.

Under "Smart Dimension", add to the list of picks:

> - Arc length: click an arc and both of its end points, in any order, then click where the text goes.
> - Hold Shift when you click a circle or arc to measure to its near or far side instead of its centre. Click the side that faces the other item for the nearest distance, or the far side for the farthest. This works with a line or another circle, not with a point.

## d. Left out

- A link from a converted curve feature copy back to its feature (D517 item 4): the link mechanism only knows part edges and corners of the solid body.
- Picking curve feature edges in the 3D view while sketching: the sketch editor replaces the 3D view, so the tree and the sketch view are the two ways to pick.

## e. Found on the way (not changed, outside this group)

- `core/sketch/projection.py` samples free form part edges with `GCPnts_QuasiUniformDeflection`, which returns only the two end points for a helix shaped B-spline edge. Model snapping (D250) then draws such an edge as a straight chord. Curve conversion samples with its own evenly spread parameters and is not affected.
