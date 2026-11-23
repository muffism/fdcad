# FDCAD feature test plan

Every feature, and every option of every feature, with the result to expect. Run it on the installed app. Write what you saw in **Actual** and mark **P** (pass) or **F** (fail). For a fail, add a screenshot name or a short note.

The option lists come from the app itself (each feature's panel was opened and its choices listed on 2026-11-01), so every choice in the app has a row here.

## 1. Test parts

Make these once and save them. Most rows start from one of them.

| Part | How to make it | Volume |
|---|---|---|
| **T1 Block** | Sketch on the Top plane: Center Rectangle 100 x 60 on the origin. Extruded Boss, Blind, 20 mm. | 120000 mm3 |
| **T2 Cylinder** | Sketch on the Top plane: Circle, diameter 40, on the origin. Extruded Boss, Blind, 60 mm. | 75398 mm3 |
| **T3 Open box** | T1, then Shell 2 mm with the top face removed. | 23232 mm3 |
| **T4 Sheet** | New part. Sketch on the Top plane: Corner Rectangle 120 x 80. Base Flange, thickness 2, bend radius 1, K-factor 0.44. | 19200 mm3 |

Read volumes with **Print Estimate** (3D Print tab). Allow 0.1% for rounding. "mm3" means cubic millimetres.

## 2. Checks for every feature

Do these once for each feature in sections 4 to 12, on top of its own rows. Write the feature's name and any fails in the table.

| ID | Check | Expected |
|---|---|---|
| G1 | Open the feature with nothing picked | The panel opens, says what to pick, and OK is off or shows that message. No crash. |
| G2 | Change any value | The preview updates within about a second. The value label in the view shows the new value. |
| G3 | Type a formula (for example `10*2`) and a unit (`1in`) | The field accepts it and shows the value in mm under the box. |
| G4 | Type a bad value (`abc`, a negative length) | The box turns red with a message. OK does not build a broken feature. |
| G5 | OK | The feature is in the tree with its icon and the part shows the result. |
| G6 | Cancel (also Esc) | The part is exactly as before. Nothing is added to the tree. |
| G7 | Undo, then Redo | Undo removes the feature in one step. Redo puts it back. |
| G8 | Edit the feature again (double click in the tree) | The panel opens with every value as you left it. Cancel changes nothing. |
| G9 | Suppress, then unsuppress | The feature's effect goes away and comes back. Later features rebuild. |
| G10 | Drag the rollback bar above it, then back | The part shows the state before and after it. |
| G11 | Save, close and reopen the part | The feature is there with the same values and the same volume. |
| G12 | Make it fail on purpose (too big a value) | The tree shows an error mark. The message says what failed and what to do. The app keeps running. |
| G13 | Drag handles in the view, where the feature has them | The value follows the mouse. Its field in the panel follows. |

| Feature | G checks failed | Notes |
|---|---|---|
| | | |

## 3. Sketch

Start a sketch on the Top plane of a new part.

| ID | Tool or option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| SK-01 | Line | Click two points, then a third | A chain of two lines, joined at the middle point. Esc ends the chain. | | |
| SK-02 | Centerline | Click two points | A dashed construction line. It is not part of a profile. | | |
| SK-03 | Corner Rectangle | Click two corners | Four lines with horizontal and vertical relations. | | |
| SK-04 | Center Rectangle | Click the centre, then a corner | A rectangle centred on the first click. | | |
| SK-05 | 3 Point Corner Rectangle | Click three corners | A rectangle that can be turned at any angle. | | |
| SK-06 | 3 Point Center Rectangle | Click centre, side middle, corner | A turned rectangle centred on the first click. | | |
| SK-07 | Parallelogram | Click three corners | Opposite sides parallel, corners not square. | | |
| SK-08 | Circle | Click centre, then a point | A circle through the second point. | | |
| SK-09 | Perimeter Circle | Click three points | A circle through all three. | | |
| SK-10 | Centerpoint Arc | Centre, start, end | An arc around the centre. | | |
| SK-11 | Tangent Arc | Start at a line end | The arc is tangent to the line. | | |
| SK-12 | 3 Point Arc | Start, end, a point on the arc | An arc through all three. | | |
| SK-13 | Point | Click once | A sketch point. | | |
| SK-14 | Slot | Click two centres, then the width | A slot with two half circles. | | |
| SK-15 | Polygon | Centre, then a corner; set 6 sides | A regular hexagon. | | |
| SK-16 | Spline | Click 4 points, Esc | A smooth curve through the points. | | |
| SK-17 | Ellipse | Centre, major axis end, minor size | An ellipse. | | |
| SK-18 | Partial Ellipse | As Ellipse, then start and end | An elliptical arc. | | |
| SK-19 | Sketch Fillet | Pick a rectangle corner, radius 5 | The corner is rounded with radius 5; lines are trimmed. | | |
| SK-20 | Sketch Chamfer | Pick a corner, distance 5 | The corner is cut at 5 mm each way. | | |
| SK-21 | Trim | Click a line piece between two crossings | Only that piece is removed. | | |
| SK-22 | Extend | Click near a line end | The line grows to the next entity it meets. | | |
| SK-23 | Offset | Pick a closed chain, 5 mm | A copy 5 mm outside; Reverse puts it inside. | | |
| SK-24 | Mirror | Pick lines and a centerline | Mirrored copies with symmetric relations. | | |
| SK-25 | Convert Entities | Pick a part edge (sketch on a face) | A sketch line on that edge, linked to it. | | |
| SK-26 | Linear Sketch Pattern | Pick a circle, 3 copies, 20 mm | Three circles in a row, 20 mm apart. | | |
| SK-27 | Circular Sketch Pattern | Pick a circle, 6 copies, 360 deg | Six circles evenly around the centre. | | |
| SK-28 | Sketch Picture | Insert an image | The image shows under the sketch at the size set. | | |
| SK-29 | Smart Dimension: Distance | Pick a line | The line takes the typed length. | | |
| SK-30 | Horizontal and Vertical Distance | Pick two points | Only the X (or Y) gap is driven. | | |
| SK-31 | Angle | Pick two lines | The angle between them is driven. | | |
| SK-32 | Radius and Diameter | Pick an arc, then a circle | The size is driven. Text shows R or the diameter mark. | | |
| SK-33 | Doubled Distance | Pick a line and a centerline | Distance across the centerline (twice the offset). | | |
| SK-34 | Arc Length | Pick an arc | The arc length is driven. | | |
| SK-35 | Each relation: Horizontal, Vertical, Coincident, Collinear, Parallel, Perpendicular, Tangent, Concentric, Equal, Midpoint, Symmetric, Coradial, Intersection, Fixed, Offset | Pick suitable items and add each relation | The sketch moves to satisfy it and the relation shows a tag. Deleting the tag frees it. | | |
| SK-36 | Fully defined | Dimension and fix every entity | The status shows fully defined; lines turn the defined colour. | | |
| SK-37 | Over defined | Add one more dimension | You are asked to make it a reference (or it becomes one, as set in Preferences). | | |
| SK-38 | Exit sketch with OK, and with Cancel | | OK keeps the edits; Cancel puts the sketch back. | | |

## 4. Boss and cut

Use T1, or a new sketch as stated.

### Extruded Boss and Extruded Cut

| ID | Option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| EX-01 | From: Sketch Plane | T1 as made | Starts on the sketch plane. Volume 120000. | | |
| EX-02 | From: Surface/Face/Plane | Pick a plane 10 mm above (Offset plane) | The body starts on that plane, not the sketch plane. | | |
| EX-03 | From: Vertex | Pick a vertex 5 mm above | Starts on the plane through that vertex. | | |
| EX-04 | From: Offset 5 | | Starts 5 mm from the sketch plane. **Reverse offset** puts it 5 mm the other way. | | |
| EX-05 | End: Blind 20 | | 20 mm deep. Volume 120000. | | |
| EX-06 | End: Through All (cut) | Ø10 circle on the top face | Hole all the way through. Volume 118429. | | |
| EX-07 | End: Through All Both (cut) | Ø10 circle on a mid plane | Hole through in both directions. | | |
| EX-08 | End: Up to Next (cut) | Ø10 circle above a stepped part | Stops at the next face it meets. | | |
| EX-09 | End: Up to Vertex | Pick a vertex | Ends on the plane through the vertex. | | |
| EX-10 | End: Up to Face | Pick a face | Ends on that face, following its shape. | | |
| EX-11 | End: Offset from Face 5 | Pick a face | Ends 5 mm short of the face. **Translate surface** keeps the end flat. | | |
| EX-12 | End: Up to Body | Pick another body | Ends where it meets that body. | | |
| EX-13 | End: Mid Plane 20 | | 10 mm each side of the sketch plane. Volume 120000. | | |
| EX-14 | Reverse direction | | The body goes the other way. | | |
| EX-15 | Direction 2: Blind 10 | Tick Direction 2 | 20 up and 10 down. Volume 180000. | | |
| EX-16 | Draft 5 deg | | Side faces lean inward. Top face smaller than bottom. Volume less than 120000. | | |
| EX-17 | Draft outward | | Side faces lean outward. Volume more than 120000. | | |
| EX-18 | Merge result off | Boss touching T1 | Two bodies (status bar). On: one body. | | |
| EX-19 | Thin Feature: One Direction 2 | Rectangle profile | A wall 2 mm thick, open top and bottom. | | |
| EX-20 | Thin: Mid Plane, Two Direction | | Mid Plane: 1 mm each side of the line. Two Direction: each side its own thickness. | | |
| EX-21 | Thin: Cap ends | Closed profile | Top and bottom are closed with the cap thickness. | | |
| EX-22 | Contours: Clear and pick regions | Sketch with two loops | Only the picked regions are extruded. Clear removes the picks. | | |
| EX-23 | Cut with Reverse side | | The material outside the profile is removed instead. | | |

### Revolved Boss and Revolved Cut

Sketch on the Front plane: a centerline on the Y axis and a 10 x 20 rectangle from X 20 to 30.

| ID | Option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| RV-01 | Axis: pick each line in the Axis list | | Each line can be the axis. With the centerline: a ring. | | |
| RV-02 | End: Blind 360 | | A full ring. Volume 31416. | | |
| RV-03 | End: Blind 90 | | A quarter ring. Volume 7854. | | |
| RV-04 | End: Mid Plane 90 | | 45 deg each side of the sketch. | | |
| RV-05 | End: Up to Vertex, Up to Face, Offset from Face | Pick references | The turn ends at that reference. | | |
| RV-06 | End: Through All (cut) | | Cuts the full turn. | | |
| RV-07 | Direction 2 | Tick it, 45 | Turns 90 one way, 45 the other. | | |
| RV-08 | Thin Feature, Cap ends | | A thin shell of revolution; caps close the ends. | | |
| RV-09 | Merge result | | As EX-18. | | |
| RV-10 | Axis crosses the profile | Move the rectangle over the axis | Error that says the profile crosses the axis. No crash. | | |

### Swept Boss and Swept Cut

Path: a sketch line plus arc on the Front plane. Profile: a circle on a plane square to the path start.

| ID | Option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| SW-01 | Profile: Sketch profile | | The circle follows the path. | | |
| SW-02 | Profile: Circular profile, diameter 8 | No profile sketch | A round tube of diameter 8 along the path. | | |
| SW-03 | Orientation: Follow Path | | The profile turns with the path. | | |
| SW-04 | Orientation: Keep Normal Constant | | The profile keeps its direction. | | |
| SW-05 | Twist: None | | No twist. | | |
| SW-06 | Twist: Minimum Twist | | Smooth, least twist on a 3D path. | | |
| SW-07 | Twist: Specify Twist Angle 90 | Square profile | The square turns 90 deg along the path. | | |
| SW-08 | Twist: Specify Direction Vector | Pick a plane | The profile keeps facing that direction. | | |
| SW-09 | Thin Feature (One Direction, Mid Plane, Two Direction), Cap ends | | A hollow sweep; caps close it. | | |
| SW-10 | Merge result | | As EX-18. | | |
| SW-11 | Swept Cut through T1 | | Material removed along the path. | | |

### Lofted Boss and Lofted Cut

Profiles: a 40 x 40 square on the Top plane and a Ø20 circle on a plane 40 mm above.

| ID | Option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| LO-01 | Two profiles | | A smooth shape from square to circle. | | |
| LO-02 | Add Profile, Move Up, Move Down, Remove | Three profiles | The loft goes through them in list order. | | |
| LO-03 | Start: Default, None, Normal to Profile, Direction Vector | Start length 20 | The shape leaves the first profile as set; Normal leaves square to it. | | |
| LO-04 | End: same four choices | | Same at the last profile. | | |
| LO-05 | Close loft | Three or more profiles | The last profile joins back to the first. | | |
| LO-06 | Thin Feature, Cap ends | | A hollow loft. | | |
| LO-07 | Merge result | | As EX-18. | | |
| LO-08 | Lofted Cut | Profiles inside T1 | Material removed in the loft shape. | | |

## 5. Modify

### Fillet

On T1. Expected volume for one top long edge, radius 5: 119463.5.

| ID | Option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| FI-01 | Constant Size, one edge, R5 | | The edge is round. Volume 119463.5. | | |
| FI-02 | Several edges and a face | Pick 2 edges and the top face | All picked edges and the face's edges are round. | | |
| FI-03 | Add Feature | On the More tab, pick Extrude in the list | Every edge of that feature is round. | | |
| FI-04 | Add Convex Edges, Add Concave Edges | On the More tab: scope Whole Part, then one feature | Only outside (or inside) edges are added. | | |
| FI-05 | Remove | Select an item, Remove | It leaves the list and the preview. | | |
| FI-06 | Multiple radius | Two edges, R5 and R2 | Each edge gets its own radius. | | |
| FI-07 | Partial Edges: Distance | Start 10, end 10 | The round stops 10 mm from each end. | | |
| FI-08 | Partial Edges: Percent | 20% and 20% | The round covers the middle 60%. | | |
| FI-09 | Variable Size | Start 2, end 8 | The round grows along the edge. Set All copies the radius to every row. | | |
| FI-10 | Variable: control points | 2 points, 5 each | Radius passes through the points. | | |
| FI-11 | Variable: Smooth transition, Straight transition | | Smooth curves between points; Straight changes linearly. | | |
| FI-12 | Face fillet | Face Set 1 and Face Set 2 | A round between the two face sets. | | |
| FI-13 | Full Round | Side, centre, side face sets on a 10 mm rib | The centre face becomes a full half round. | | |
| FI-14 | **Full preview** | 3 edges | The finished part: smooth rounds in blue, no lines, no stripes. | | |
| FI-15 | **Partial preview** | 3 edges | The part stays sharp. Blue lines show where each round starts and ends. | | |
| FI-16 | **No preview** | | Nothing is drawn. OK still builds. | | |
| FI-17 | Radius too big (R40) | | Error mark and a message naming the edge, with fix buttons. | | |
| FI-18 | Fix button | Click "Fillet the rest" | The failing edges leave the list and the rest build. Only after the click. | | |

### Chamfer

On T1. One top long edge, 5 x 5 removes 1250 mm3.

| ID | Option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| CH-01 | Distance Distance, Symmetric 5 | One edge | 45 deg cut, 5 each way. Volume 118750. | | |
| CH-02 | Distance Distance, Asymmetric 5 and 10 | | Uneven cut. Volume 117500. Flip swaps the sides. | | |
| CH-03 | Angle Distance 5, 45 deg | | Same as CH-01. At 30 deg the cut is shallower. | | |
| CH-04 | Vertex, 5/5/5 | Pick a corner vertex | The corner is cut off as a small triangle. | | |
| CH-05 | Vertex, Equal distance off | 5/8/10 | Three different distances. | | |
| CH-06 | Offset Face | Pick a face | Its edges are cut by the offset distance. | | |
| CH-07 | Face to Face: Symmetric, Asymmetric, Width | Face Set 1 and 2 | A chamfer between the face sets. Width sets the chamfer face width. | | |
| CH-08 | **Full preview** | 3 edges | The finished part with the cut faces in blue. | | |
| CH-09 | **Partial preview** | 3 edges | The part is unchanged. Blue lines show the chamfer outlines. | | |
| CH-10 | **No preview** | | Nothing is drawn. | | |

### Shell

| ID | Option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| SH-01 | Thickness 2, remove top | T1 | Open box. Volume 23232. | | |
| SH-02 | No face removed | | A closed hollow body (looks solid outside). | | |
| SH-03 | Shell outward | Remove top | Walls grow outward. Volume 26432. | | |
| SH-04 | Multi Thickness | One side face at 5 | That wall is 5 mm, the rest 2. | | |
| SH-05 | Show preview off | | No preview; OK still builds. | | |
| SH-06 | Thickness 40 | | Error with a message. | | |

### Draft

On T1.

| ID | Option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| DR-01 | Neutral Plane, 5 deg | Click the bottom face first (Pick Neutral Face is on, so it becomes the neutral face), then the 4 sides | Sides lean 5 deg; the bottom stays the same size. Volume 125680.9 (wider at the top). Reverse: 114482.4. | | |
| DR-02 | Pick Neutral Face | Click the button, then a face | That face becomes the neutral face. | | |
| DR-03 | Propagation: None, Along tangent, All faces, Inner faces, Outer faces | Pick one side face | The draft spreads to the faces that option names. | | |
| DR-04 | Add Faces That Need Draft | | Every face under the draft angle is added. | | |
| DR-05 | Parting Line | Pull direction: Top Plane; edges around the middle | Faces above and below are drafted from the line. | | |
| DR-06 | Other side, Draft both sides, second angle | | The other side drafts; both sides use their own angles. | | |
| DR-07 | Step Draft | | A step forms at the parting line. | | |
| DR-08 | Show changed faces | | The faces that will change are marked. | | |

### Rib

Open sketch line inside T3 on the Front plane.

| ID | Option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| RB-01 | First Side, Both Sides, Second Side, thickness 3 | | A 3 mm wall on that side of the line, grown until it meets the box. | | |
| RB-02 | Parallel to Sketch, Normal to Sketch | | The wall grows in the sketch plane, or out of it. | | |
| RB-03 | Flip Material Side | | Grows the other way. | | |
| RB-04 | Draft 2 deg, Draft Outward | | The rib tapers. Outward makes it wider at the end. | | |
| RB-05 | Linear, Natural (spline line) | | Linear extends the end straight; Natural follows the curve. | | |

### Dome

| ID | Option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| DO-01 | Distance 10 | Top face of T2 | A dome 10 mm high. | | |
| DO-02 | Reverse | | A dish sunk 10 mm. | | |
| DO-03 | Elliptical Dome | | An elliptical profile. | | |
| DO-04 | Continuous Dome | Top face of T1 | One smooth dome over a non round face. | | |

### Wrap

Sketch text or a rectangle on a plane tangent to T2.

| ID | Option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| WR-01 | Emboss 1 mm | | The shape rises 1 mm on the cylinder. | | |
| WR-02 | Deboss 1 mm | | The shape is sunk 1 mm. | | |
| WR-03 | Scribe | | Only lines are split on the face; volume unchanged. | | |
| WR-04 | Analytical, Spline Surface | | Analytical works on cylinders and flat faces; Spline Surface on other curved faces. | | |
| WR-05 | Reverse | | Wraps the other way round. | | |

## 6. Holes and fastening

On T1, top face.

| ID | Option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| HO-01 | Simple, Drill Size 6, Blind 10, Drill Point | Click the face twice | Two holes, 10 mm deep with a cone tip. "2 hole(s)". | | |
| HO-02 | Flat end | | Flat bottom. | | |
| HO-03 | Counterbore, ISO Metric M5, Screw Clearance, Close, Normal, Loose | | Clearance grows from Close to Loose. Counterbore sized for the head. | | |
| HO-04 | Countersink M5 | | Cone at the top. | | |
| HO-05 | Near Side Countersink, Far Side Countersink | Through All | Cone at the top, at the bottom, or both. | | |
| HO-06 | Straight Tapped M6, Tap Drill | | Tap drill size hole. Cosmetic Thread shows thread marks; Modelled Thread cuts a real thread. | | |
| HO-07 | ANSI Inch, 1/4-20 | | Inch sizes are listed and used. | | |
| HO-08 | Heat Set Insert | Edit Insert Table, Save | Hole sized from the insert table. Edits are kept. | | |
| HO-09 | Hex Nut Trap M3 | | A hex pocket for the nut. | | |
| HO-10 | Captive Nut Slot M3 | Slot offset, length, span, angle | A slot the nut slides into from the side. | | |
| HO-11 | Fit: None, Clearance, Slip, Press | | The hole grows by the fit tolerance (or shrinks for Press). | | |
| HO-12 | End: Through All, Up to Next, Up to Vertex, Up to Face | | Depth follows the end condition. | | |
| HO-13 | Slot, Centre to Centre, Overall | | Holes become slots; length measured as chosen. | | |
| HO-14 | Points, End Points, Centres | Sketch with points and arcs | Holes go on those sketch items. Remove Point takes one out. | | |
| HO-15 | Presets: Save, Apply, Update | | A saved preset brings back every value. | | |

| ID | Feature and option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| CT-01 | Cosmetic Thread M6, Blind 10 | Edge of a Ø5 hole | Thread marks 10 mm deep. Volume unchanged. | | |
| CT-02 | Cosmetic Thread Full Length, Reverse, own diameter and pitch | | Full length; Reverse starts from the other end. | | |
| MT-01 | Modeled Thread, Cut Thread M6, Blind 10 | Edge of a Ø5 hole | A real thread is cut 10 mm deep. | | |
| MT-02 | Extrude Thread | Edge of a Ø6 shaft | Thread added outside. | | |
| MT-03 | Revolutions 5, Up to Selection | | Thread length by turns, or up to a face. | | |
| MT-04 | Right Hand, Left Hand, starts 2 | | Hand and number of starts change. | | |
| MT-05 | Offset, start angle, Reverse, Keep Thread Length | | The thread moves and turns; length stays when ticked. | | |
| MB-01 | Mounting Boss: Screw Boss, Thread Side | Pick a face and a point | A boss with a screw hole. | | |
| MB-02 | Screw Boss, Head Side | | A boss with a counterbore for the head. | | |
| MB-03 | Pin Boss, Pin and Pin Boss, Hole | | A pin; and a boss with the matching hole. | | |
| MB-04 | Fins: count 4, Equally Spaced, angles, sizes, draft | | Four fins around the boss. | | |
| MB-05 | Chamfer distance and angle | | Chamfer at the boss top. | | |
| SN-01 | Snap Hook | Pick a face and an edge | A hook of the typed sizes. | | |
| SN-02 | Reverse Up, Reverse Hook | | The hook points the other way. | | |
| SN-03 | Snap Groove | Pick the hook and the face | A groove that fits the hook with the clearances. | | |
| LG-01 | Lip and Groove | Two bodies of a split box | A lip on one rim, a matching groove in the other. | | |
| LG-02 | Link Matched Values | | Changing the lip changes the groove to fit. | | |
| VE-01 | Vent: Boundary, Rib, Spar, Fill In Boundary, Not Used | Sketch with an outline and lines | Each sketch item plays the chosen role; the vent is cut with ribs and spars. | | |
| VE-02 | Widths, depths, offsets | | Ribs and spars take the sizes. | | |
| ALL-P | Presets on Mounting Boss, Snap Hook, Snap Groove, Lip and Groove, Vent: Save, Apply, Update, Delete, Export, Import | | Presets save, apply, export to a file and import back. | | |

## 7. Patterns and bodies

On T1 with a Ø10 cut hole at (-30, 0).

| ID | Option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| LP-01 | Linear Pattern: Spacing and instances, 3 at 20 | Direction: an edge | Three holes 20 mm apart. | | |
| LP-02 | Up to reference | Pick a face | Instances fill up to that face. | | |
| LP-03 | Reverse, Direction 2 (2 x 3) | | Other way; a 2 by 3 grid. | | |
| LP-04 | Pattern seed only | | Direction 2 copies only the seed. | | |
| LP-05 | Full, Partial | | Partial: you choose instances to skip. | | |
| LP-06 | Geometry pattern | | Copies faces as they are (faster, no end condition). | | |
| LP-07 | Merge result, Propagate colours | | One body; colours copied. | | |
| CP-01 | Circular Pattern: 6, Equal spacing, 360 | Axis: T2 axis | Six copies evenly around. | | |
| CP-02 | Reverse, Symmetric, Direction 2 | | Opposite way; spread both ways; a second ring. | | |
| CP-03 | Full, Partial, Geometry pattern, Merge, Propagate colours | | As LP rows. | | |
| MI-01 | Mirror about Right Plane | Pick the hole | A mirrored hole at (30, 0). | | |
| MI-02 | Mirror seed only, Geometry pattern, Merge, Propagate colours, Full and Partial | | As LP rows. | | |
| SP-01 | Sketch Pattern | Pick sketch points | One copy at each point. Full and Partial, Merge, colours. | | |
| CA-01 | Curve Array: Spread Over Curve, count 5 | Pick a curve | Five copies along the curve. | | |
| CA-02 | Set Spacing 10, Orient to Curve, Merge | | Copies 10 mm apart, turned with the curve. | | |
| CO-01 | Combine: Add, Subtract, Common | Two overlapping bodies | Union, difference, overlap only. | | |
| SL-01 | Split by Front Plane, Cut | | Two bodies. | | |
| SL-02 | Invert, Save Bodies as FDCAD Part, STEP, STL, 3MF | | Each body saves to its own file in that format. | | |
| IN-01 | Intersect: Overlap regions, Internal regions, Both | Two bodies | The chosen regions become bodies. Select All and Invert choose them. | | |
| IN-02 | Cap flat openings, Merge result | | Openings are closed; bodies merge. | | |
| MC-01 | Move/Copy Body: Translate, Delta X Y Z | 10, 0, 0 | The body moves 10 mm in X. | | |
| MC-02 | Translate Along an edge, Vertex to vertex | | Moves by the edge length, or from one vertex to the other. | | |
| MC-03 | Rotate about Along an edge, Rotation origin, Centre of the bodies | 90 deg | Turns about that axis or point. | | |
| MC-04 | Copy, Reverse | | Leaves the original; moves the other way. | | |
| SC-01 | Scale 2, Uniform, about Centre of the bodies | | Volume 8 times larger. | | |
| SC-02 | Non uniform (X 2, Y 1, Z 1); about Rotation origin; about A point | | Stretches in X; the fixed point is as chosen. | | |
| DB-01 | Delete Body, Keep bodies | Two bodies | Delete removes the picked ones; Keep removes the others. | | |

## 8. Direct editing

On T1.

| ID | Option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| MF-01 | Move Face: Offset 5 | Top face | The block grows 5 mm. Volume 150000. | | |
| MF-02 | Translate: Distance along a direction, Delta X Y Z | Side face | The face moves; neighbours stretch. | | |
| MF-03 | Translate: Up to Vertex, Up to Face, Offset from Face, Up to Body | | The face stops at that reference. | | |
| MF-04 | Rotate about an axis or Rotation origin | 5 deg | The face tilts. | | |
| MF-05 | Fit: None, Clearance, Slip, Press | Hole face | The hole grows or shrinks by the fit. | | |
| MF-06 | Reverse, Copy | | Other way; Copy keeps the face. | | |
| OF-01 | Offset Face 2 | Top face | The face moves out 2 mm. | | |
| DF-01 | Delete Face: Delete | A fillet face | The face is removed (open body). | | |
| DF-02 | Delete and Patch, Delete and Fill, Tangent fill | | The gap is closed by growing neighbours, or a new fill face (smooth with Tangent fill). | | |

## 9. Reference geometry and curves

| ID | Option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| RP-01 | Plane: Offset distance 10, Flip side | Top plane | A plane 10 mm above; Flip puts it below. | | |
| RP-02 | At angle 30 | Plane and an edge | A plane turned 30 deg about the edge. | | |
| RP-03 | Three points | Three vertices | Through them. Points in a line: error. | | |
| RP-04 | Normal to curve, Set origin on curve | Edge and point | Square to the edge at the point. | | |
| RP-05 | Mid plane | Two parallel faces | Halfway. Non parallel: error. | | |
| RP-06 | Parallel through a point | | Parallel, through the point. | | |
| RP-07 | Project onto a face, Along Sketch Normal | | Through the projected point, normal to the face. | | |
| RP-08 | Parallel to screen, Use Current View | | Faces you; does not move when the view turns. | | |
| RP-09 | Flip normal on every method | | The plane turns over. | | |
| RA-01 | Axis: Along a line or edge; Two planes; Two points; Cylinder axis; Point and face | | The axis is where expected. Errors for parallel planes or same points. | | |
| RA-02 | Reverse direction | | The axis points the other way. | | |
| RT-01 | Point: Arc centre, Centre of face, Intersection, Projection, On a point, X Y Z values | | The point is where expected. | | |
| RT-02 | Along curve: Distance, Distance as percent, Reverse direction | | Measured from the start, as a percent, or from the end. | | |
| CS-01 | Coordinate System: Origin and directions | Pick origin, X and Z | Three axes as picked. Nothing picked: matches the model axes. | | |
| CS-02 | Rotation angles X, Y, Z | 90, 0, 0 | Turned 90 about X, applied X then Y then Z. | | |
| HX-01 | Helix: Pitch and Turns, Height and Turns, Height and Pitch | Circle sketch | Height and pitch follow the typed pair. | | |
| HX-02 | Spiral | | A flat spiral. | | |
| HX-03 | Variable Pitch, Add Row, Remove Row | | Pitch and diameter change at each row. | | |
| HX-04 | Reverse, Clockwise, Taper Outward, taper angle, start angle | | Direction, hand, taper and start change. | | |
| PC-01 | Projected Curve: Sketch on Faces | Sketch and T2 face | The sketch lies on the face. | | |
| PC-02 | Sketch on Sketch | Two sketches on Front and Top | A 3D curve where both meet. | | |
| PC-03 | Direction, Reverse, Both Directions | | Projects along that way. | | |
| CC-01 | Composite Curve: Remove, Move Up, Move Down | Joined edges | One curve; gaps give an error. | | |
| PI-01 | Pipe: outer 10 | Pick a curve | A solid rod of diameter 10 along it. | | |
| PI-02 | Hollow inner 6, Cap Ends, Merge | | A tube; caps close it. | | |
| CN-01 | Contour: plane, spacing 2 | | Contour lines every 2 mm. | | |

## 10. Deform

| ID | Option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| DE-01 | Bend: Angle 90, axis Z, X, Y | T1 | Bends between the trim planes about that axis. | | |
| DE-02 | Bend: Radius | | Bend set by radius. | | |
| DE-03 | Twist 90, axis Z, X, Y | T1 | Turns evenly from start to end plane. | | |
| DE-04 | Taper 0.5, axis Z, X, Y | | Full size at the start, half at the end. | | |
| DE-05 | Stretch 2, axis Z, X, Y | | The region between the planes doubles in length. | | |
| DE-06 | Flow Along Curve, axis Z, X, Y, Fit to curve length | Long thin bar and a curve | The bar follows the curve; Fit stretches it to the curve length. | | |
| DE-07 | Approximate warning | Tight tolerance | A warning, not an error. | | |

## 11. Sheet metal

| ID | Option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| SM-01 | Sheet Metal Parameters: thickness, bend radius | Edit on T4 | Every flange rebuilds with the new values. | | |
| SM-02 | Bend allowance: K-factor, Bend allowance, Bend deduction, Bend table | | Flat size changes as each method says. | | |
| SM-03 | Relief: Rectangular, Obround, Tear; Ratio, Width and depth; Corner relief Rectangular, Circular | | Reliefs are cut in that shape and size. | | |
| SM-04 | Load Bend Table, Load Gauge Table | CSV files | Values come from the file. | | |
| BF-01 | Base Flange: closed profile | | A flat plate. Flat Pattern added last in the tree. | | |
| BF-02 | Open profile, Blind, Mid Plane, Up to Vertex, Up to Face, Offset from Face, Direction 2 | | A bent wall; every corner is a bend. | | |
| BF-03 | Reverse thickness, Symmetric, Own Bend Values | | Thickness on the other side or split; own radius used. | | |
| EF-01 | Edge Flange: angle 90, length 20 | One edge of T4 | A 20 mm wall bent up. | | |
| EF-02 | Angle from Typed, Perpendicular to face, Parallel to face; Reverse | | The wall takes that angle. | | |
| EF-03 | End Blind, Up to Vertex; Measure from Outer virtual sharp, Inner virtual sharp, Bend tangent | | Length measured as chosen. | | |
| EF-04 | Position: Material inside, Material outside, Bend outside, Virtual sharp | | The wall sits as chosen. | | |
| EF-05 | Several edges, Length 2 to 8, Trim side bends, Gap 1 | Two edges at a corner | Each own length; corner trimmed with a 1 mm gap. | | |
| EF-06 | Own Bend Values, Own Relief | | Used for this flange only. | | |
| SB-01 | Sketched Bend: Position Bend centreline, Material inside, Material outside, Bend outside; Reverse; Flip fixed side | Line on T4 | Bends along the line as set. | | |
| FL-01 | Flatten, then Flatten again | | Flat with bend lines, then folded. One undo step each. | | |
| FL-02 | Flat Pattern: Show bend lines, Show bounding box, Grain direction | Edit the Flat Pattern | Lines and box show; Flat size follows the grain edge. | | |
| FL-03 | Export Flat Pattern STEP, DXF, SVG | | True scale files; OUTLINE and BEND_LINES layers. | | |
| HM-01 | Hem: Closed, Open (Gap), Teardrop, Rolled | Edge of T4 | Each hem shape as named. | | |
| HM-02 | Length, Position, Reverse, Corner gap | | Size and side as set. | | |
| MF-S | Miter Flange: Gap | Edge chain and profile | Walls along the chain, mitred at corners. | | |
| JG-01 | Jog: Offset, Measure offset Face to same face, Between inside faces, Overall; Angle; Reverse; Position; Flip fixed side | Line on T4 | A Z step of that offset. | | |
| CC-S | Closed Corner: Overlap, Underlap, Butt, Gap | Two flanges | Corner closed as chosen. | | |
| BC-01 | Break Corner: Chamfer distance, Fillet radius | Corner edges | Corners cut or rounded. | | |
| RI-01 | Rip: sketched and edge, Gap, Flip | | Slits cut; Flip cuts the other wall. | | |
| TS-01 | Tab and Slot: Tabs, Tab length, Depth, Spacing, Clearance | | Tabs and matching slots. Spacing 0 spreads them. | | |
| CV-01 | Convert to Sheet Metal | T1 with a fixed face and bend edges | Walls and bends; outside size kept. | | |
| IB-01 | Insert Bends | T3 | Sheet metal with bends; wrong thickness gives the stated error. | | |
| XB-01 | Cross Break, Reverse direction | Face of T4 | Two corner lines; volume unchanged. | | |
| UF-01 | Unfold (All bends, or picked), cut across a bend, Fold | | The cut wraps onto the bend after Fold. | | |
| FT-01 | Forming Tool: Dimple, Louvre, Embossed rib; Reverse | Line on T4 | Each form pressed into the wall. | | |

## 12. 3D print, import and evaluate

| ID | Option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| SFP-01 | Split for Print: Fit Build Volume, build 200 x 200 x 200 | Large part | Cut into pieces that fit. | | |
| SFP-02 | At Planes | Pick planes | Cut at those planes. Bodies to Cut limits it. | | |
| SFP-03 | Joints: None, Alignment Pins, Dovetail Keys; sizes; clearance | | Pins or keys with the clearance. | | |
| PR-01 | Lay Flat, Clear Orientation | Pick a face | The face goes down on the bed; Clear puts it back. | | |
| PR-02 | Open in Slicer | | The slicer opens with the part. | | |
| IM-01 | Import Mesh: Convert to Solid, Merge, Subtract | An STL | Imported as a mesh or solid; merged or cut. | | |
| IS-01 | Import STEP: Convert to Solid, Merge, Subtract | A STEP file | Same as IM-01 for STEP. | | |
| EV-01 | Measure | Two faces | Distance and angle shown. | | |
| EV-02 | Print Estimate | T1 | Volume 120000 and a weight. | | |
| EV-03 | Overhang, Wall Thickness, Draft Analysis, Geometry Check, Build Volume, Curvature | T3 | Each colours the part or lists problems as its help says. | | |

## 13. View

| ID | Option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| VW-01 | Section View, one plane | T1 | The part is cut. The cut face is filled. | | |
| VW-02 | **Section arrow** | Look at the arrow | A flat 2D arrow. It is whole, never cut by the section. | | |
| VW-03 | Drag the section arrow | | The plane moves; Offset in the panel follows. | | |
| VW-04 | Two planes, axis, cap colour | | Only the corner in front of both is cut. | | |
| VW-05 | Shaded, Shaded with edges, Wireframe, Hidden lines, Transparency | | Each display style shows. | | |
| VW-06 | Standard views, Normal To, Zoom, Fit, Previous | | The view goes there. | | |
| VW-07 | Show or hide planes, sketches, origins, bodies, relations | | Items show and hide. | | |
| VW-08 | Command tabs: hold and drag, ▾ menu to hide, Show All Tabs, Reset Tab Order | | Order kept after restart; hidden tabs stay hidden. | | |
| VW-09 | Appearance rows: Delete, right click, double click | | Colour removed, changed, all undoable. | | |
| VW-10 | **Isometric frames the part** (D682) | A 20 mm part with the planes shown. Ctrl+7, then Zoom to Fit | The part is in the middle and fills the view; the planes are not what is framed. | | |
| VW-11 | Shift+arrow after a pan | Ctrl+Left three times, then Shift+Right | The part turns 90 degrees and is back in the middle, at the same zoom. | | |

Fillet extra row (D681):

| ID | Option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| FI-20 | **Rounds that run into each other** | Tube 20 mm across with a 10 mm hole, 10 mm long. Chamfer 2 on both end edges, then Fillet R2 on the end face | No thin sliver. The message names "edge 2" (not a stored name), the edge that fits is rounded, and the panel offers to skip the other edge or reduce the radius. | | |

## 14. Feature tree and editing

Added from the tutorial review on 2026-11-02. On T1 with a 10 mm hole cut through it (Extruded Cut, Through All) and Fillet R2 on the top face.

| ID | Option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| TE-01 | Rollback bar drag | Drag the bar above the fillet | The fillet greys out and the part shows without it. | | |
| TE-02 | Add while rolled back | Rolled back above the fillet, add Chamfer 1 on one bottom edge | The chamfer goes just above the bar. Roll to End rebuilds both. | | |
| TE-03 | Roll Forward, Roll to Previous, Roll to End | Right click in the tree | Each moves the bar as named. | | |
| TE-04 | Arrow keys on the bar | Select the bar, press Up and Down | The bar moves one feature a step. | | |
| TE-05 | Bar saved | Roll back, save, close, open | The bar is where it was. | | |
| TE-06 | Reorder allowed | Drag the fillet above the cut | Allowed, since the fillet does not use the cut. The part rebuilds. | | |
| TE-07 | Reorder not allowed | Drag the cut above Extrude 1 | The cursor shows not allowed; nothing moves. | | |
| TE-08 | Edit Feature | Right click the cut, Edit Feature, change to Blind 5 | The panel opens with its values; OK rebuilds. | | |
| TE-09 | Edit Sketch | Right click the cut, Edit Sketch, change the diameter to 12 | The sketch opens; exiting rebuilds with a 12 mm hole. | | |
| TE-10 | Edit Sketch Plane | Right click the cut's sketch, Edit Sketch Plane, pick the bottom face | The sketch moves there and the part rebuilds. | | |
| TE-11 | Dimensions on the model | Click Extrude 1 in the tree, double click its 20 | The value box opens; type 30, Enter. The part is 30 mm thick. | | |
| TE-12 | Rename | Rename the cut to "Centre hole" | The tree shows the new name; undo restores it. | | |
| TE-13 | Suppress and unsuppress | Suppress the cut | The hole goes away and the row is grey; unsuppress brings it back. | | |
| TE-14 | Delete with children | Roll back above the cut, then delete Extrude 1 | A confirm names the features that use it. Cancel keeps all; Undo after a delete brings all back. | | |
| TE-15 | Error mark | Edit the fillet to R50 | The fillet row is red with a mark; clicking it shows the message and Edit Feature. The part name shows the mark too. | | |
| TE-16 | Remembered values | Make Fillet R3, then start a new Fillet | The new panel starts at R3. | | |
| TE-17 | Repeat last command | After a fillet, press Enter in the view | Fillet starts again. | | |
| TE-18 | Recent commands | Right click empty view | Recent Commands lists the last commands used. | | |

## 15. Equations, configurations and design tables

On T1. Name the extrude depth `depth@Extrude 1` as the app shows it.

| ID | Option | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| EQ-01 | Global variable | Tools, Equations: add `"wall" = 3` | The variable shows in the Equations folder of the tree. | | |
| EQ-02 | Value from a variable | In Shell, type `="wall"` for the thickness | The shell is 3 mm. Changing `wall` to 4 makes it 4 mm after Rebuild. | | |
| EQ-03 | Equation between values | `"depth@Extrude 1" = "wall" * 10` | The block is 30 mm thick. The Evaluates to column shows 30. | | |
| EQ-04 | Pick a value in the view | In the value cell, click the 100 of the sketch | Its name goes in the cell. | | |
| EQ-05 | If expression | `"depth@Extrude 1" = if("wall" > 3, 40, 20)` | 20 at wall 3, 40 at wall 4. | | |
| EQ-06 | Circular reference | `"a" = "b" + 1`, `"b" = "a" + 1` | Both rows show an error; nothing else breaks. | | |
| EQ-07 | Bad syntax | `"c" = 3 +` | The row shows a syntax mark; OK does not apply it. | | |
| EQ-08 | Pattern spacing from an equation | Circular pattern of the hole, 3 copies, spacing `= 360 / count` | Changing the count to 4 in the view sets the spacing to 90. | | |
| CF-01 | New configuration | Configurations: add "Thin" | Two configurations listed; the active one is marked. | | |
| CF-02 | Value per configuration | In "Thin", set the depth to 10, This configuration | "Thin" is 10 mm, the default is still 20. | | |
| CF-03 | Suppress per configuration | In "Thin", suppress the fillet | The fillet is gone only in "Thin". | | |
| CF-04 | Switch | Switch between configurations | The part rebuilds each time with that configuration's values. | | |
| DT-01 | Design table | Tools, Design Table: columns depth and wall, three rows | Three configurations, one per row. | | |
| DT-02 | CSV export and import | Export, change one value in the file, import | The changed value is used after import. | | |

## 16. Tutorial style walk throughs

Whole parts made the way common beginner lessons make them, with FDCAD's own sizes. Each should be possible without leaving FDCAD.

| ID | Part | Steps | Expected | Actual | P/F |
|---|---|---|---|---|---|
| WT-01 | **Plate with a ring and a hole** | Extruded Boss first, pick the Top plane, circle diameter 90, depth 12. On the top face: circle 70, Offset Entities 6 inward, extrude 8. Hole diameter 20 Through All in the middle. Fillet R2 on the ring's top edges | Every step works from the feature first flow; the sketch opens on the picked plane; the result is one body. | | |
| WT-02 | **Box with a shell and a boss** | Corner rectangle 110 x 70 from the origin, depth 40. On the front face a circle 50 dimensioned 35 and 30 from two edges, depth 20. Fillet R4 on the four vertical edges. Shell 2 removing the back face. Cut a 30 hole through the boss | The circle turns fully defined after the two position dimensions. The shell keeps the fillets. | | |
| WT-03 | **Turned part with a swept handle** | Revolve a profile with lines, a tangent arc and a 3 point arc about a centerline. On the Front plane, a path of a line and two tangent arcs; on the Right plane an ellipse at the path start. Swept Boss. Cut 15 deep with a 10 degree draft | The sweep follows the path; the cut is tapered. | | |
| WT-04 | **Lofted head** | Square 50 on the Front plane; offset planes at 20, 40 and 60; circles on them; Lofted Boss through the four profiles, picking near the same corner each time | The loft is not twisted. Move up and down in the profile list change the order. | | |
| WT-05 | **Knob with drafted grip and mirror** | Half disc: centerpoint arc 180 degrees, line through the origin, depth 8. Grip on the Right plane, depth 6. Draft 8 degrees on three grip faces with the Right plane as neutral. Mirror the body about the Right plane. Fillets: face fillet, asymmetric 1 and 2, variable with Set All | One body after the mirror; each fillet type works. | | |
| WT-06 | **Housing with patterns** | Revolve a housing; thin extrude 3 with Reverse; Shell 3 removing top and bottom. Oblong cut through all; linear pattern along its 60 dimension, 4 copies 12 apart; circular pattern of the linear pattern, 3 copies, then 4 | Patterns follow the dimension direction and the axis; the count change updates the spacing when it comes from an equation. | | |
| WT-07 | **Sheet metal bracket** | Base flange from an open L profile; miter flange along two edges; mirror the part; edge flange with Edit Profile; a tab; a cut across a bend after Unfold, then Fold; Closed Corner | The flat pattern exports; the cut is in the right place after folding. | | |

## 17. Not built yet (from the tutorial review)

These rows test the items in `docs/TUTORIAL_REVIEW_SPEC.md`. The owner approved all of them (D683, PLAN.md Phase 7A). Until each is built, mark its row **N** (not built) instead of F.

| ID | Item | Steps | Expected when built | Actual | P/F |
|---|---|---|---|---|---|
| TR-01 | TR1 Move and Copy Entities | In a sketch with a circle, Copy Entities, 3 copies, Delta X 15 | Three circles 15 apart, relations between copies kept. | | |
| TR-02 | TR1 Rotate, Scale, Stretch | Rotate a rectangle 30 degrees; scale it 2; stretch one side 10 | Each changes the picked entities only; undo in one step. | | |
| TR-03 | TR2 Split Entities | Split a line at its middle | Two lines meeting at a sketch point that can be dimensioned. | | |
| TR-04 | TR3 Copy and paste in a sketch | Ctrl+C, Ctrl+V a slot | A copy follows the cursor; a click places it. | | |
| TR-05 | TR3 Paste a sketch on a plane | Copy a sketch in the tree, pick a plane, Ctrl+V | A new sketch on that plane with the same entities. | | |
| TR-06 | TR4 Midpoint Line | Click the origin, then a point | A line centred on the origin. | | |
| TR-07 | TR5 Insert DXF | Insert a DXF with a circle and a rectangle | Both appear at true size, under defined. | | |
| TR-08 | TR9 Copy and paste a feature | Copy the hole cut, pick another face, paste | A new cut on that face with the same values. | | |
| TR-09 | TR13 Hidden Lines Visible | Choose the style | Hidden edges show dashed. | | |
| TR-10 | TR14 Saved view | Save View "Side", turn the view, pick "Side" | The camera goes back. Saved in the file. | | |
| TR-11 | TR16 Split view | Four views | Front, Top, Right and Isometric; a pick shows in all. | | |
| TR-12 | TR17 Temporary axes | Show them on T2, use one as a circular pattern axis | The axis shows and can be picked. | | |
| TR-13 | TR22 Next part tab | Two parts open, press the chosen keys | The other part's tab comes forward. | | |
| TR-14 | TR23 Folder and comment | Put two features in a folder; add a comment | Folder row with both; comment mark with hover text; both saved. | | |
| TR-15 | TR24 Save Image | Save the view as PNG | The PNG matches the view. | | |
| TR-16 | TR29 Hold line | Face fillet with a hold line | The round's edge follows the hold line. | | |
| TR-17 | TR30 Link to thickness | Sheet metal cut with Link to thickness, then change the thickness | The cut depth follows the thickness. | | |
| TR-18 | TR32 Named dimension | Name the shell thickness `wall`, use it in an equation | The equation shows `wall`; renaming updates it. | | |
| TR-19 | TR33 Cut chosen bodies | Two overlapping bodies, a cut through both with Selected bodies, one picked | Only the picked body is cut. | | |
