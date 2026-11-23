# Phase 3 tool behaviour spec

Behaviour only, written by the manager on 2026-10-30 from the vendor's public online help (2027 pages), in our own words, with generic names (CLAUDE.md sections 7 and 10). Implementers build from this file and PLAN.md only. Items marked [Later] are outside PLAN.md Phase 3; do not build them without a PLAN change.

Common rules: as PHASE2_SPEC.md (panel conventions of TOOL_SPEC T5, live preview, expressions in number fields, picks stored by topological name, lost picks are errors that ask the user to pick again, kernel work off the UI thread, undoable commands).

## P3.1 Direct editing (owner's favourite commands: build these with extra care)

Each is a feature in the tree, so it can be edited, suppressed, rolled back and reordered like any other. They work on native bodies and on imported STEP bodies alike. Right click on a face offers Move Face and Delete Face directly (TOOL_SPEC T9 face menu), with the clicked face already picked.

### P3.1.1 Move Face

1. Panel: a mode switch with three choices, Offset, Translate, Rotate; a Faces box; a Copy tick box (Translate and Rotate only); mode parameters.
2. Picking faces: click faces in the view. A small helper bar appears beside the last picked face with one click selections: all coplanar faces, all inner loops (for example every hole wall in that face), all outer and inner loops, all faces around it, all tangent faces, all coplanar and connected faces, all full cylinders or cones with the same axis direction, all full cylinders or cones on the same axis. Hovering a helper button highlights what it would add.
3. Offset: every picked face moves along its own normal by a distance (a curved face changes radius; a hole wall offset grows or shrinks the hole). One distance field with Reverse.
4. Translate: the picked faces move as a group without changing shape. Direction from a picked plane, flat face, straight edge or axis plus a distance; or Delta X, Y, Z fields; or end conditions: Up to Vertex (from a face, plane or vertex to a vertex), Up to Face (from a face or plane to a face or plane), Offset from Face (as Up to Face plus a distance), Up to Body.
5. Rotate: the picked faces turn as a group about a picked straight edge or axis by an angle; or about a rotation origin (X, Y, Z fields) with angles about X, Y and Z.
6. In the view: the transform handles (CLAUDE.md naming: transform handles) appear on the picked faces. Dragging an arrow translates, dragging a ring rotates. While dragging, a ruler (for distance) or a protractor (for angle) appears; near it the value snaps to its ticks, away from it the value is free. The value beside the handle is clickable and opens the value box (as TOOL_SPEC T5.2.3). The panel fields follow the drag.
7. The neighbouring faces of the part stretch or shrink to stay joined to the moved faces (the body stays closed). If the move cannot be healed (a face would leave the body or cross another face), the feature fails with a message naming the face and what blocked it, and the preview shows the last valid state; nothing is changed silently (CLAUDE.md 5.12).
8. Copy (Translate, Rotate): leaves the original faces and adds a moved copy of the face group, which must join the same body (no separate pieces).

### P3.1.2 Delete Face

1. Panel: a Faces box and three options:
   - Delete: removes the faces and leaves an open shell (the body becomes a surface body; only allowed when PLAN surface bodies exist, else the option is shown greyed with a tooltip saying why) [Later until surface bodies are in PLAN; not built in round 9t: D510].
   - Delete and Patch: removes the faces and grows the neighbouring faces until they meet, so the body stays a closed solid. This is the main use: removing fillets, chamfers, holes, bosses and small details from native or imported parts.
   - Delete and Fill: removes the faces and closes the gap with one new smooth face; a Tangent fill tick box makes the new face meet its neighbours smoothly instead of just touching.
2. The same face picking helpers as Move Face (P3.1.1 item 2) are available, for example all inner loops to pick every hole wall at once.
3. Preview shows the result live. If patching fails for a face, the message names that face; with several faces, the panel offers to keep the faces that worked (user confirms, PLAN 5A style partial results).

### P3.1.3 Offset Face (PLAN item)

The same as Move Face in Offset mode but as its own command for quick access (it opens Move Face with Offset preselected).

## P3.2 Patterns

1. Linear pattern: Features, Faces, Bodies or Reference geometry (one plane or axis) to pattern; Direction 1: a straight edge, axis, sketch line, flat face normal or a linear dimension, Reverse, spacing, instance count, or Up to reference (fill to a vertex, edge, face or plane with an offset); Direction 2 the same plus Pattern seed only (only the seed is repeated in direction 2). Instances to skip: dots appear at each instance in the view; clicking a dot skips it (and back).
2. Circular pattern: axis from an axis, round edge, straight edge, cylinder or revolved face, or an angular dimension; Reverse; Equal spacing (total angle 360 by default) or angle between instances; instance count; Direction 2 with a Symmetric option; same Features, Faces, Bodies, Reference geometry boxes; Instances to skip.
3. Sketch driven pattern: a sketch with points; reference point is the seed's centroid or a picked point; one instance per sketch point.
4. Options for all: Geometry pattern (copies faces exactly instead of rerunning each feature; faster, but faces merged into the rest of the part cannot be copied this way), Propagate colours, Full or Partial preview.
5. Faces to pattern must stay inside the face they sit on; when an instance falls off it, that instance fails with a message, the others are kept (user confirms).
6. Curve driven pattern [Covered by Array along curve: D292, D510]; Array along curve (PLAN P3 item) covers that need, see P3.7.

## P3.3 Mirror

1. Mirror face or plane (a plane or flat face). Optional second mirror plane (makes up to three copies), with Mirror seed only when the planes are perpendicular.
2. Features, Faces or Bodies to mirror. Options: Geometry pattern, Merge solids (seed and mirror become one body when mirroring bodies), Propagate colours, Full or Partial preview.

## P3.4 Multibody

1. Combine: Add (all picked bodies into one), Subtract (a main body minus the picked tool bodies; Make main body see through helps picking), Common (keep only where the picked bodies overlap). Show preview.
2. Intersect: pick solids and planes; creates the regions where they overlap and any closed internal regions (choice: overlap regions, internal regions, or both); Cap flat openings option; after Intersect a region list appears where regions can be excluded (Select all, Invert); Merge result (touching regions become one body) or one body per region; preview shows included solid and excluded see through.
3. Split: trim tools are planes, flat faces (treated as endless), sketches (cut through all both ways) or curved faces; a Cut button shows the resulting bodies with numbered callouts; tick which bodies to keep. Target bodies: all bodies or picked bodies. [Built: D528] saving bodies to separate files.
4. Move and copy body: pick bodies; Copy with a number of copies; Translate by Delta X, Y, Z (each with Reverse), along a picked edge with a distance, or vertex to vertex; Rotate about a picked edge or about an origin with X, Y, Z angles; transform handles in the view as P3.1.1 item 6.
5. Delete and keep body: pick bodies; Delete the picked ones or Keep only the picked ones.
6. Isolate, hide and show bodies; show hovered body; show all hidden (SHORTCUTS.md keys I, H, Shift+Tab, Ctrl+Shift+Tab, deferred from Phase 1 by D116 item 4).

## P3.5 STEP import as a base body

1. File open or Insert: the STEP file is healed on import (report what was fixed), colours kept, and embedded in the `.fdef` (PLAN). The body appears as an Imported feature at the top of the tree. Direct editing (P3.1) is the main way to change it.

## P3.6 Curves

1. Helix and spiral: from a sketch with one circle. Defined by Pitch and turns, Height and turns, Height and pitch, or Spiral (pitch and turns, flat). Constant or variable pitch (a table of regions with turns, height, diameter and pitch). Reverse (helix grows backwards; spiral goes inward), start angle, clockwise or counterclockwise, taper angle with taper outward (constant pitch only).
2. Projected curve: Sketch onto faces (pick a sketch, a direction from an axis, line, edge, plane or flat face, the faces; Reverse and Both directions) or Sketch onto sketch (the 3D curve where two sketches on crossing planes meet).
3. Composite curve: join connected sketch curves, edges and curves into one curve, usable as a sweep path.

## P3.7 Pipe, array along curve, transform handles, contour curves, curvature graph

1. Pipe: as the circular profile option of the sweep (PHASE2_SPEC P2.2 item 2) plus an inner diameter for a hollow tube and cap ends; path from a curve or a chain of edges.
2. Array along curve: bodies or features along a curve; count or spacing; orient to curve or keep orientation; instances to skip.
3. Transform handles: as P3.1.1 item 6, used by Move and copy body; the result is written to the tree as an editable feature.
4. Contour curves: section a body at a spacing along a direction; reference curves usable in sketches and features.
5. Curvature graph: display only combs for curves and edges with scale and density sliders.

## P3.8 Scale

1. Bodies to scale (multibody only), scale about the centroid, the origin or a picked coordinate system, Uniform (one factor) or per axis (X, Y, Z factors).
2. Sketch scale (Sketch tab): pick curves, a base point, a factor, Copy with number of copies.

## P3.9 Split for printing, mesh import

Original FDCAD features (PLAN), no vendor equivalent: follow PLAN.md Phase 3 wording. Mesh import: STL, 3MF, OBJ as a reference body; warn above 100,000 triangles; convert to a faceted solid on request; the original mesh is embedded in the `.fdef`.
