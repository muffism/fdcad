# Phase 4 tool behaviour spec

Behaviour only, written by the manager on 2026-10-30 from the vendor's public online help (2027 pages), in our own words, with generic names (CLAUDE.md sections 7 and 10). Implementers build from this file and PLAN.md only. [Later] marks items outside PLAN.md Phase 4. Standard size tables come from published standards (CLAUDE.md 7.6), never from another product's files.

Common rules: as PHASE2_SPEC.md. Every fastening feature panel has a Favourites box: save the current settings under a name, apply one, update, delete, export to a file and import from a file (stored in the preferences, per feature type).

## P4.1 Hole Tool

1. Two tabs in the panel: Type and Positions. The user can switch between them in any order; Positions can add more holes of the same type at any time. Different hole types are separate features.
2. Type tab: hole type (Simple, Counterbore, Countersink, Straight tapped; slot versions of Simple, Counterbore and Countersink with a slot length measured centre to centre or overall [Built: D524]); Standard (ISO metric, ANSI inch); purpose (drill sizes, tap drill, clearance for a screw size with Close, Normal or Loose fit); Size; end condition (Blind with depth, Through All, Up to Face); Options: head clearance, near side and far side countersinks, cosmetic thread for tapped holes (P4.2) or modelled thread (P4.3).
3. Positions tab: the first hole point follows the cursor with a preview of the hole, using the sketch snaps and inference lines; each click places another hole; the position sketch can be dimensioned. Holes can be placed on flat or curved faces. Option: use an existing sketch, which places a hole at every point and end point of that sketch (with tick boxes for which kinds of points count).
4. The feature owns two sketches: the position sketch and the hole profile. Deleting a hole made from an existing sketch asks whether to keep that sketch.
5. Printing additions (PLAN): heat set insert holes (editable table of common published insert sizes), hex nut traps and captive nut slots, fit presets (Clearance, Slip, Press) that apply the printer profile's fit tolerance.

## P4.2 Cosmetic threads

Shown on the face as a pattern (not modelled), stored as metadata (size, pitch, depth). Included in STEP as metadata where the format allows.

## P4.3 Modelled threads (Thread tool)

1. Pick the round edge where the thread starts (on a hole or a shaft). Optional start reference with an offset and Reverse; start angle.
2. End condition: Blind (length), Revolutions (number of turns), Up to Selection (a vertex, edge, plane or flat face parallel to the start edge); Keep thread length with an offset.
3. Specification: thread family and size from our own standard table, override diameter, override pitch; method Cut thread or Extrude thread; profile mirror and rotate options; right or left hand; Multiple start count.
4. The thread is real helical geometry that prints (PLAN). Warn that profiles are nominal.

## P4.4 Fastening features

1. Mounting boss: pick a face (flat or curved) and a position point (or a sketch point; or a round edge to centre on); direction for curved faces; boss type Screw boss (head side with a counterbore, or thread side with a hole) or Pin boss (pin or hole); diameters, heights, draft; fins: count (0 allowed), first fin direction, Equally spaced (two fins at 180 degrees) or a second direction, fin length, width, height, draft and an end chamfer distance and angle.
2. Snap hook: position (a point on an edge or face), up direction, hook direction (each with Reverse), the face the hook body sits on, body height typed or taken from a mating face; hook data: top depth, hook height, lip height, body height, base depth, overhang, total width, top draft angle.
3. Snap hook groove: pick a snap hook and the body to cut; data: offset height, hook height, gap height, groove clearance, gap clearance, offset width; the groove follows any draft of the hook.
4. Lip and groove: pick the groove body and the lip body (or only one); direction (plane, flat face or straight edge; default normal to the picked faces); faces and edges for the groove (where material is removed) and the lip (where material is added), each with tangent propagation; groove width, height, draft; lip height, width, draft; with both: spacing and the gaps between lip and groove; Link matched values (lip draft equals groove draft, groove width equals lip width plus spacing); Jump gaps (ribs touching the walls); Keep existing wall faces (a drafted wall continues up the lip).
5. Vent: from a sketch: boundary curves (closed), a face (flat or curved, the whole sketch must fit), draft on or off with inward option, fillet radius at all joins; ribs (sketch lines, depth, width, offset from the surface), spars (need at least one rib), a fill-in boundary (closed, crossed by at least one rib, with depth and offset); the panel shows the total area and the open area percentage, updated live.

## P4.5 Rib

From an open sketch: thickness on the first side, both sides or the second side; thickness measured at the sketch plane or at the wall when drafted; extrusion direction parallel to the sketch or normal to it; flip material side; draft on or off with an angle and Draft outward; type Linear (ends go straight until they meet the part) or Natural (ends continue their own curve until they meet the part); body pick in multibody parts.

## P4.6 Dome

Faces to dome (flat or curved); distance (convex, Reverse for concave; 0 on a round face makes a dome tangent to the side); optional constraint sketch of points (then distance is not used); optional direction; Elliptical dome for round ends; Continuous dome for polygon faces (slopes evenly; off: rises from each edge).

## P4.7 Wrap

1. A sketch of closed contours only, picked from the tree. Type: Emboss (raised), Deboss (sunk), Scribe (lines on the face only).
2. Method: Analytical (cylinders, cones and extruded faces; the sketch plane must touch the face) or Spline surface (any face, but cannot wrap all the way round) [Built: D528].
3. Face to wrap on, thickness, Reverse, and for emboss or deboss an optional pull direction (a line, edge or plane).

## P4.8 Sketch text

Text along picked curves or edges, or horizontal from the origin; text box; bold, italic, rotate per character; alignment left, centre, right, full (along a curve); flip vertical and horizontal; width factor and spacing percent; font choice. Text can be extruded, cut or wrapped like any closed profile.

## P4.9 Deformation features (PLAN: flow along curve, twist, bend, taper, stretch)

1. Common: pick bodies; a transform handle triad and two trim planes in the view set where the deformation starts and stops; only the region between the trim planes deforms. Dragging the triad moves the axis; dragging a trim plane moves that limit; values in the panel follow.
2. Bend: about the triad's first axis; angle and radius are linked (the bent length stays the same), the user sets one.
3. Twist: about the triad's third axis, angle.
4. Taper: along the third axis, a taper factor; the trim planes stay put.
5. Stretch: along the third axis, a distance, or drag a trim plane edge.
6. Flow along curve: PLAN wording (no vendor equivalent read).
7. PLAN rules: convert to NURBS, deform control points, rebuild and validate; tolerance setting; warning when approximate; error when not a valid solid.

## P4.10 Equations, configurations, design tables

1. Equations manager: three sections (global variables, feature values, equations); a name cell puts quotes round the name and moves to the value cell with = filled in; the value cell accepts numbers, other variables, dimensions picked in the view, functions and if expressions; a mark shows whether the syntax is valid; an Evaluates to column; comments. Circular references are detected and shown as errors (PLAN). Global variables also show in an Equations folder in the tree.
2. Configurations: create, rename, switch; per configuration overrides of any feature value and suppression; every value field with an expression offers This configuration, All configurations or Chosen configurations.
3. Design tables: a built in table editor (rows are configurations, columns are parameters), stored inside the `.fdef`, with CSV import and export (PLAN).
