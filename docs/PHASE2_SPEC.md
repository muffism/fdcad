# Phase 2 tool behaviour spec

Behaviour only, written by the manager on 2026-10-29 from the vendor's public online help (2027 pages), in our own words, with generic names (CLAUDE.md section 7 and 10). Implementers build from this file and PLAN.md only. Items marked [Later] are outside PLAN.md Phase 2 and are listed so they are not forgotten; do not build them without a PLAN change.

Common rules for every Phase 2 feature: the panel follows TOOL_SPEC T5 (header, OK, Cancel, live preview with the W6.4 timing, value fields accept expressions T14.6), every pick is stored by topological name, a lost pick is an error that asks the user to pick again, and kernel work runs off the UI thread.

## P2.1 Extrude additions (PLAN Phase 2 item 1)

1. New end conditions for Direction 1 and Direction 2: Up to Vertex (pick a vertex or sketch point; the end is a plane parallel to the sketch plane through it), Up to Face (pick a face or plane; the end follows that face, which must fully cover the profile carried along the direction), Offset from Face (as Up to Face, plus a distance; Reverse offset and a Translate surface option that moves the face instead of offsetting it).
2. Draft while extruding: a draft on/off button beside the depth with an angle field and Draft outward tick box. Draft applies to every side face of that direction.
3. Thin Feature group: type One Direction, Mid Plane or Two Direction, thickness fields (two for Two Direction), Reverse. Open profiles are allowed only with Thin Feature on; for closed profiles Thin Feature makes a wall around the profile. Cap ends option for closed thin profiles (cap thickness).

## P2.2 Sweep (boss and cut)

1. Panel groups: Profile and Path, Guide Curves, Options, Start and End Tangency, Thin Feature (boss), and a cut variant with the same groups.
2. Profile choices: a closed sketch profile, or Circular profile: pick a path and type a diameter to sweep a round rod along it (no profile sketch needed).
3. Path: a sketch (open or closed, one sketch), a curve, or a chain of model edges. The path must start on the profile's plane. When the path passes through the profile, offer Direction 1, Direction 2 or Both directions (guide curves and tangency are not allowed for Both).
4. Profile orientation: Follow Path (the section keeps its angle to the path) or Keep Normal Constant (the section stays parallel to the start section).
5. Profile twist: None (flat paths), Minimum Twist (3D paths), Follow first guide curve, Follow first and second guide curves, Specify Twist Angle (degrees, radians or turns; for a closed path only whole turns), Specify Direction Vector (pick a plane, face, line, edge or axis; not with Keep Normal Constant), Tangent to Adjacent Faces (when the sweep starts on existing geometry). Offer only what OpenCascade does reliably (PLAN): None, Minimum Twist, Twist Angle and Direction Vector first; the guide based twists only if the kernel supports them, else record in DECISIONS.
6. Guide curves: a list with move up and move down; each guide must touch the profile sketch. The sweep stops at the shortest guide if a guide is shorter than the path. Merge Smooth Faces tick box (off splits the result at every point where the path or guide is not smooth).
7. Start and end tangency: None or Path Tangent (the result is normal to the path at that end).
8. Merge Tangent Faces tick box; Show Sections (step through computed sections with arrows) for troubleshooting.
9. Errors: the section, path and result may not intersect themselves; say which one does.

## P2.3 Loft (boss and cut)

1. Profiles list: sketches, faces or edges, in the order picked; move up and move down; for each profile the user can drag the connection point (a dot on each profile) to control how profiles join; the preview shows connector lines between matching points.
2. Start and end constraints, each: Default (three or more profiles: a smooth natural curve), None, Direction Vector (pick an edge, axis, face or plane), Normal to Profile, Tangency to Face and Curvature to Face (only when the loft touches existing faces; a Next Face button cycles faces). With Direction Vector and Normal to Profile: a draft angle and a tangent length (influence, reaches only to the next section), each with Reverse. Apply to all: one handle per profile; off: one handle per segment, dragged in the view.
3. Guide curves list with move up and move down; guide influence: To next guide, To next sharp corner, To next edge, Whole loft; guide tangency: None, Normal to Profile, Direction Vector, Tangency to Face.
4. Centerline: optional sketch the sections follow, with a number of sections slider.
5. Options: Merge tangent faces, Close loft (joins the last profile back to the first), Show preview (see through or solid, toggled by right click), Merge result.
6. Thin Feature group as P2.1 item 3.
7. Show Sections arrows as P2.2 item 8.

## P2.4 Fillet

1. Panel remembers its last settings within a session. Type list: Constant Size and Variable Size (PLAN Phase 2). [Built: D518, D519] face fillet, full round fillet, an automatic fillet assistant.
2. Items to fillet: edges, faces (all edges of the face), features (all edges of the feature) and loops, picked in the view. Tangent propagation (on by default) adds edges tangent to the picked ones. Preview mode: Full (all edges), Partial (one edge at a time, the A key steps to the next), None (fast).
3. Constant size methods: Symmetric (one radius), Asymmetric (two distances with a flip button). Multiple radius tick box: each picked edge gets its own radius label in the view that can be edited; corners where three edges of different radii meet must still work. Cross section: Circular, or [Later, kernel cannot: D519] conic and curvature continuous.
4. Variable size: a list of the end points of the picked edges plus control points; each item gets a radius (Set All copies one value to all). A number of control points per edge (evenly spaced, each with its own radius). Transition between radii: Smooth or Straight (linear).
5. Options: Select through faces (pick hidden edges through faces), Keep features (a small boss or cut that a large fillet would swallow is kept), Round corners (adjacent filleted edges meet with a round corner instead of a sharp mitre), Overflow behaviour for closed edges (Default, Keep edge, Keep surface).
6. Setback at a corner vertex [Later, kernel cannot: D519], partial edge fillets (start and end by distance or percent [Built: D519], or reference [Later: D529]).
7. Robustness (PLAN 5A items 4 and 5): before running, check each edge (radius larger than the adjacent faces allow, edge too short) and show which edges will fail. If some edges fail, offer a result with the edges that work plus a list of failed edges, never a silent drop; the user confirms.

## P2.5 Chamfer

1. Types: Angle and distance (a handle in the view shows which side the distance is measured on; click it or Flip to swap), Distance and distance (Symmetric: one value; Asymmetric: two values), Vertex (three distances around a picked vertex, or Equal distance with one value). [Built: D520] offset face chamfer, face to face chamfer.
2. Items: edges, faces and loops (vertex for the vertex type). Tangent propagation, preview mode (Full, Partial, None) as fillet.
3. Options: Select through faces, Keep features (as fillet).
4. When a chamfer has lost references after an upstream edit, the lost items are listed at the top of the items box so the user can repick them (CLAUDE.md 5.12).

## P2.6 Shell

1. Fields: Thickness (expressions allowed), Faces to remove (picked in the view; none gives a hollow closed part), Shell outward tick box (the wall grows outside the original part instead of inside), Show preview.
2. Multi thickness: a second list of faces each with its own thickness; the default thickness applies to the rest.
3. In a part with more than one body and no face picked, a body pick box appears.
4. Diagnostics (PLAN 5A item 4): when the shell fails, run a check that finds faces whose curvature radius is smaller than the thickness and highlights them, with the message which face and the smallest radius it has.

## P2.7 Draft (neutral plane method)

1. Fields: Draft angle (measured from the pull direction, expressions allowed), Neutral plane (a plane or flat face; Reverse flips which way the faces tilt), Faces to draft.
2. Face propagation: None (only the picked faces), Along tangent, All faces, Inner faces, Outer faces.
3. Preview option to highlight new or changed faces in a different colour.
4. [Built: D521, D522] parting line draft, step draft, an automatic draft assistant, draft analysis colouring (Phase 2 has overhang analysis instead).

## P2.8 Sketch tools (PLAN Phase 2 sketch tools item)

Each tool is a command in the Sketch tab and in the command list (rebindable), works with the snapping, automatic relations and undo rules of TOOL_SPEC T1, and shows a small panel while active.

1. **Offset**: pick sketch curves, model edges or a model face (its outer loop). Fields: distance (dragging in the view shows a live preview and sets it), Add dimension (the distance becomes a sketch dimension), Reverse, Select chain (all connected curves), Both directions, Make base construction and Make offset construction, Cap ends for open chains (both directions or one direction; cap type arcs or lines). The offset keeps a link to its source: when the source changes, the offset follows (an offset relation stored in the sketch). Curves that would cross themselves at that distance are refused with a message.
2. **Trim**: modes in the panel: Drag trim (hold and drag across curves; each crossed curve loses the piece between its nearest intersections, and the path leaves a short trail; dragging along a curve from its end extends it along its own path), Corner (pick two curves; both are trimmed or extended to meet), Trim inside (pick two boundary curves, then the open curves to cut between them), Trim outside (keep only what lies between two boundaries), Trim to nearest (click a piece; it is removed up to the nearest intersections, or the curve is extended to the nearest curve when clicked past its end). Relations and dimensions on removed pieces are removed with them and listed in the status bar.
3. **Extend**: hover a line or arc to preview it extended to the next curve in the direction of the half under the cursor; click to apply; dragging on continues past further curves.
4. **Mirror**: pick curves to mirror and a mirror line (a sketch line, a straight model edge, or a plane or flat face in the sketch plane). Copy on keeps the originals; off replaces them. Each pair of mirrored points gets a Symmetric relation about the mirror line. [Built: D514] dynamic mirror while drawing.
5. **Convert**: pick model edges, a face (its loops), or curves of another sketch; they become sketch curves with an On Edge link and fixed position (D113 style copies, but they follow the source on rebuild when the source can be resolved by name; a lost source becomes the D116 item 3 warning). Select chain picks all connected edges. For construction option.
6. **Sketch fillet**: pick a corner point, or two curves; radius field; Keep constrained corners (a construction point keeps the old corner for its dimensions; off asks before deleting them); Dimension each fillet (off: later fillets get Equal to the first instead of their own dimension).
7. **Sketch chamfer**: Angle and distance, or Distance and distance with an Equal distance tick box; distance 1 applies to the first picked curve.
8. **Linear sketch pattern**: pick curves; Direction 1 (an axis, sketch line or model edge, with Reverse and an angle from X), spacing, instance count, Add spacing dimension, Fix direction; optional Direction 2 the same; Instances to skip (click instances in the view). Options to add the dimensions that make the pattern fully defined.
9. **Circular sketch pattern**: centre (sketch origin by default, or X and Y, or a picked point), Reverse, total angle, Equal spacing, instance count, radius and arc angle fields, Add radius and angle dimensions, Instances to skip. When the centre is not the origin, it gets a Coincident to the picked point.
10. **Spline**: click points (a press and drag at a point sets its tangent handle), double click to finish. The spline panel lists its points with X and Y fields, tangent handles that can be dragged and dimensioned, For construction, Show curvature (combs) [Built: D514].
11. **Slots**: Straight (two end centres, then width), Centre straight (centre, end, width), 3 point arc slot, Centre point arc slot. Option Add dimensions; length measured Centre to centre or Overall. The slot panel shows centre X and Y, width, length, and for arc slots radius and angle. A slot is stored as lines and arcs with the relations that keep it a slot.
12. **Polygon**: centre then a vertex; panel: sides (3 to 40), Inscribed or Circumscribed construction circle, centre X and Y, circle diameter, angle, New polygon button. Stored as lines with Equal and a construction circle.
13. **Ellipse**: centre, end of the major axis, then the minor size. **Partial ellipse**: centre, first axis, second axis, then sweep along the outline and click to end. Both need a new sketch entity type in the solver; if planegcs supports ellipses, use it, else record in DECISIONS and leave them out.

## P2.9 Sketch picture

1. Sketch tab command: pick an image file (PNG, JPEG, BMP). It is placed with its lower left corner at the sketch origin, 1 pixel to 1 mm, aspect locked, and embedded in the `.fdef` (PLAN).
2. Panel: origin X and Y, angle, width, height, Lock aspect ratio, Flip horizontally, Flip vertically, Transparency slider (whole image), Enable scale tool.
3. Scale tool: a construction line with two handles on the image; drag the first handle to a known feature, drag the second to the other end, then type the true length in the value box; the image scales so the line has that length.
4. The picture can be dragged (move) and resized by corner handles. It has no snaps. Hiding the sketch hides the picture.

## P2.10 Reference geometry (plane, axis, point, coordinate system)

1. Plane: up to three reference boxes. After each pick, the constraint choices that fit that pick appear: Coincident (through it), Parallel, Perpendicular (to an edge or curve, through a point; Set origin on curve), Project (a point onto a curved face: nearest point or along the sketch normal) [Built: D526], Parallel to screen through a vertex [Built: D526], Tangent (to a cylinder, cone or curved face, through a point or line), At angle (through an edge, axis or sketch line at an angle to a plane or flat face; number of planes), Offset distance (from a plane or face; Flip side; number of planes), Mid plane (both references set to Mid plane: halfway between two flat faces or planes). Three points also define a plane (three Coincident points). A message line and the preview colour say whether the plane is fully defined; OK is only possible when it is. Flip normal.
2. Axis: from one line, edge or temporary axis; two planes or flat faces (their line of intersection); two points or vertices; a cylinder or cone face (its axis); a point and a face or plane (through the point, normal to the face; the point must lie on a curved face).
3. Point: arc centre, centre of a face, intersection of two edges or curves (or an axis with a plane or face, or two axes), projection of a point onto a face or plane (normal to it), on a sketch point, along a curve (several points by distance, by percent of length, or evenly spaced, with a count), or by X, Y, Z values. The construction method is guessed from the picks and can be changed.
4. Coordinate system: origin from a vertex, point or midpoint, or by X, Y, Z values; each axis direction from a point (towards it), a straight edge or line (along it), a curve (towards the picked spot), or a flat face (its normal), each with Reverse; or rotations by X, Y, Z angles (applied X, then Y, then Z).
5. All reference geometry shows in the tree, can be hidden and shown (T13 look for planes), and can be picked as references by later features and sketches.

## P2.11 Appearance (part and face colours)

1. Colours can be set on the whole part, a body, a feature or single faces; the more specific one wins (face over feature over body over part). A tree item at the top lists the colours in use and opens the editor.
2. Copy and paste appearance between items. Colours are written to STEP and 3MF (PLAN).

## P2.12 Measure tool

1. Evaluate tab command; a small floating box that stays open while other tools run and can be pinned. Picks in the view (up to six) are listed; clicking a picked item again removes it; clicking empty space clears all; right click Select pauses measuring.
2. One item: its size (edge length, face area and perimeter, circle radius and diameter, point coordinates). Two or more: the smallest distance, the angle between straight edges or flat faces, and dX, dY, dZ (Show XYZ toggle). Two circles or arcs: Centre to centre, Minimum or Maximum distance (choice). Point to point mode measures between any two clicked points on the part.
3. Options: units and precision for the box only, XYZ relative to the part origin or a picked coordinate system, Projected on: none, the screen, or a picked plane or face (gives the projected and normal distance, and the projected area of picked bodies or faces).
4. Results also show as callouts in the view (toggle). A history list keeps all measurements of the session. Values can be copied with one click.
5. Without the tool, the status bar shows common values of the selection (length, area, radius, distance between two items).

## P2.13 Section view

1. View command (not a feature; display only). Section by one, two or three planes or flat faces (default Front, Top, Right buttons); each with Reverse, an offset distance, X and Y rotation, and a colour. A transform handle in the view drags the offset and rotates the plane.
2. Section 1 can instead turn about an axis or a round face (angle field or drag).
3. Options: Show section cap in a chosen colour (off: see inside), keep the cap colour after closing, offset measured from the reference plane or from the picked plane.
4. The section stays on while modelling until turned off; it is never saved into the geometry.
