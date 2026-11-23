# Surface modelling spec

Written on 2026-11-04 by the manager session (DECISIONS D850). Behaviour only. It holds no wording, command names, icons, screenshots or example values from any reference. Every name below is FDCAD's own, and every test value is our own.

Implementers build from this file, the repository and the other specs in `docs/` only (CLAUDE.md section 10). Do not look up how other CAD tools do surfacing.

## How to read this spec

1. SF0 comes first. No surface tool can ship before surface bodies exist in the part, the tree, the view, the file and the exports.
2. Each tool section has: purpose, inputs, options, result and face naming, errors, a kernel note, a priority and tests.
3. Priority: **High** tools make the first release of the phase. **Medium** tools follow. **Low** tools come last.
4. Kernel notes use three marks. **Reliable**: the kernel does this well. **Test first**: write the listed probe test before building the panel. **Risky**: build only after the probe passes, and keep a clear error for the cases that fail.
5. The kernel is OpenCascade 8.0.1 through cadquery-ocp 8.0.1.1.0 (D53). The kernel notes were checked against that version, not only against 7.x.
6. Parameter keys and type names are working names. The implementer may change them and records the final names in DECISIONS.md and in the FDEF_SPEC.md change list (SF0.8).
7. Errors follow CLAUDE.md section 8 item 4: say what failed and what to do next.
8. Commands added here have no default keys (as D750 item 4).

## Words used here

- **Surface body**: a body with no thickness. It is one face, or a set of faces joined along their edges. It may be open (it has free edges) or closed (it encloses a volume but was not turned into a solid).
- **Solid body**: what FDCAD calls a body today.
- **Free edge** (open edge): an edge used by only one face of its body.
- **Join**: sew surface bodies together along edges that touch.
- **Consume**: a feature that takes a surface body as input and removes it from the part, so only its result is left.

---

## SF0. Surface bodies in FDCAD (High)

### SF0.1 Body model

1. The part stays one shape: a compound that holds solid bodies and surface bodies. A part with one solid and no surfaces is still that one solid, as today.
2. A surface body is a face or a shell in that compound. A closed shell that is not a solid is still a surface body until the user turns it into a solid (SF13, SF15).
3. Body order: solid bodies first, in today's order, then surface bodies in the order the features made them. Bodies have no stored ids, as today. The tree labels them by position.
4. Today almost every body helper goes through `solids()` in `core/features/solids.py`, which sees solids only. Keep `solids()` as it is. Add `surfaces(shape)` (faces and shells that are not inside a solid) and `bodies(shape)` (solids, then surfaces), each with a kind. Then go through every caller of `solids()` and decide, one by one, whether it means "solids only" or "all bodies". Record the list in the decision. The code survey found these callers: the body helpers in `bodies.py`, `body_visibility.py`, `appearance.body_faces`, `RebuildReport.body_count`, the tree folder, `printing/estimate.py`, `print_tools/export_bodies.py`, 3MF export, `check_result`, `combine`, Split, Combine and Delete Body.
5. `RebuildReport` gets `surface_count` beside `body_count` (solids). `body_count` keeps its meaning.
6. A face name list (`NamedShape.faces`) covers surface body faces the same way as solid faces. Edge and vertex names come from their faces, as today. A free edge has one face, so its name is `edge(<face>|free)`. A seam edge keeps today's rule. Record the exact form in the decision.
7. Result checks for surface features: valid by `BRepCheck`, at least one face, area above a tiny limit, and no self crossing where the kernel note asks for it. Volume checks (`volume_sane`, `zero_thickness`) apply to solids only.
8. The `separate_body` warning (a feature made an extra body) applies to solids only. A surface feature always makes a new surface body, and that is not a warning.

### SF0.2 Feature tree

1. A **Surface Bodies (n)** folder sits right below the Solid Bodies folder. It shows only when n is 1 or more.
2. One row per surface body, labelled "Surface 1", "Surface 2" and so on, with its own icon (drawn for FDCAD: a thin curved sheet, no thickness shown). Hidden surfaces fade like hidden solids.
3. The right click menu of a surface row: Hide, Show, Isolate, Show All Bodies, Delete Body, Move or Copy Body, Appearance, and the three surface to solid tools (Thicken, Join Surfaces with the solid option, Cut by Surface). Commands that do not apply are left out, not greyed.
4. Feature rows of surface features get the surface feature icon. Their default names are the command name plus a number ("Offset Surface 2").
5. Clicking a surface row selects the body (as a solid row does).

### SF0.3 Selection

1. The selection filter bar gets a **Surface Bodies** button beside Solid Bodies. As today (D719), a body is picked by clicking one of its faces.
2. The Faces, Edges and Vertices filters work on surface bodies as on solids.
3. A box selection picks surface faces and edges as it does solid ones.
4. Every picking field that takes a body says which kinds it takes. A field for solids ignores surface faces when the user clicks, and shows "That is a surface body. This field takes solid bodies." in the status bar. The same rule works the other way for fields that take surfaces only.

### SF0.4 Hide, show and display

1. Hide and Show use today's `hidden_bodies` list (one face name per hidden body, D410). No new key is needed.
2. Show All Bodies shows surfaces too. Isolate works on a surface body.
3. Surface bodies are drawn on both sides. The back side has a different shade of the body colour so the user can see which way the surface faces. The front side is the side the face normal points to.
4. Free edges of surface bodies are drawn in a colour of their own, in every theme, so open gaps stand out. Pick the colour by the UI_POLISH_SPEC contrast rules; it must differ from the edge, selection and preview colours.
5. A view setting, **Show Free Edges** (Evaluate tab), also draws free edges on solids. It is off by default. It helps find gaps before Join Surfaces.

### SF0.5 Colours

1. Surface bodies get a default colour of their own, distinct from the part colour, chosen by FDCAD's contrast rules. It is a theme value, not stored in the file unless the user changes it.
2. Per body colours use the `appearance.bodies` map with keys `s1`, `s2` and so on for surface bodies (solids keep `1`, `2`). Face and feature colours work as today. The precedence stays face, feature, body, part.
3. The back side shade follows whatever colour the body has.

### SF0.6 How solid features treat surface bodies

1. **Bosses and cuts** (Extrude, Revolve, Sweep, Loft, Hole Tool, Rib and the rest) never merge into or cut a surface body. "All bodies" in the bodies box means all solid bodies.
2. **End conditions that pick a face** (Up to Face, Offset from Face, Up to Body, and the same for Revolve and Move Face) accept surface body faces and surface bodies. Up to Face with a surface face still needs the face to cover the whole profile, as today; if it does not, the error says "the surface does not cover the whole profile. Extend the surface (Extend Surface) or pick a larger one."
3. **Fillet, Chamfer, Shell, Draft, Combine, Intersect bodies, Scale part, Sheet metal and the print tools** take solid bodies only. Picks on surfaces are refused as in SF0.3 item 4.
4. **Move or Copy Body, Delete Body, Linear Pattern, Circular Pattern and Mirror** in body mode accept surface bodies. Copies of a surface stay surface bodies.
5. **Split** accepts a surface body as a tool (it already takes curved faces). Splitting a surface body is Trim Surface (SF11), not Split.
6. **Intersect** keeps its `cap` parameter. With surface bodies in the part it now matters: it closes flat openings of surface bodies so they bound regions. This is Medium priority and may follow the first release.
7. **Sketch on a face, sketch references, measure, section view, temporary axes and reference geometry** work on surface faces and edges as on solid ones.
8. **Geometry check** treats free edges on a surface body as expected: it lists their count as information, not as an error. Free edges on a solid stay an error.

### SF0.7 Delete Face and the greyed Delete option (D510)

1. The Delete option of Delete Face is enabled. It removes the picked faces and leaves the rest as a surface body. Full behaviour is in SF14.
2. Remove the greyed state and the tooltip `DELETE_GREYED` from `ui/body_tools/forms.py` and `ui/strings_phase3.py`. Remove the error in `core/features/delete_face.py` that says FDCAD has no open surfaces.
3. Delete and Patch and Delete and Fill keep their behaviour on solids, and also work on surface bodies (SF14).

### SF0.8 File format

`FDEF_SPEC.md` is an owner file. Do not edit it without the owner. These are the changes it needs; the implementer drafts them as a proposal for the owner in the same branch, in a separate file `docs/plans/surfacing/FDEF_CHANGES.md`:

1. New feature types, one per tool: `extruded_surface`, `revolved_surface`, `swept_surface`, `lofted_surface`, `boundary_surface`, `filled_surface`, `planar_surface`, `ruled_surface`, `offset_surface`, `extend_surface`, `trim_surface`, `restore_surface_edges`, `join_surfaces`, `thicken`, `thicken_subtract`, `cut_by_surface`. Each with its `params` and `refs` from its section below.
2. Section 5.3.12, Delete Face: `"delete"` becomes a valid option (SF14), no longer an error.
3. Section 8, naming grammar: the face roles of the new types (listed in each section) and the free edge form `edge(<face>|free)`.
4. Section 10, appearance: body keys `s<k>` for surface bodies.
5. Section 13, local solid cache: the cached shape may hold shells and faces. Raise the cache format number so old caches are rebuilt, not read.
6. Section 15, versioning: a file that holds any surface feature, or a Delete Face with `"delete"`, is written with a new schema number (3, or the next free one). An older FDCAD then says the file needs a newer version, instead of failing feature by feature. Files with no surface features keep their lowest schema, as today. Old files open unchanged.
7. Parts saved before this phase open with the same geometry and the same face names.

### SF0.9 Export and import

1. **STEP export** writes surface bodies with the solids. The writer already uses the "as is" mode, which writes open shells as surface models. Test: a part with one solid and one open two face surface exports, reimports, and keeps the solid's volume and the surface's area and face count.
2. **STL and 3MF export** leave surface bodies out. After the export a message says: "2 surface bodies were left out because they have no thickness. Use Thicken to make them solid." (with the real count). If the part has only surface bodies, the export stops with: "Nothing to export: the part has only surface bodies. Use Thicken to make them solid."
3. **DXF and SVG export** of a face or a flat pattern accept a flat surface face as they accept a flat solid face.
4. **Save Bodies and Open in Slicer** take solid bodies only, with the same message as item 2.
5. **STEP import** (`core/io/step_import.py`) today drops open shells. Change: keep them as surface bodies. The import report says how many surface pieces came in. A file with only surfaces no longer fails; it imports as surface bodies and the report says "the file has no closed solids. It was imported as N surface bodies. Use Join Surfaces to close them into a solid." Closed shells are still turned into solids, as today.
6. **Mesh import** stays as it is: a mesh with holes is still an error, because meshes are for printing.

### SF0.10 Mass properties, measure and print tools

1. Volume, weight, mass properties, centre of mass and section properties count solid bodies only. When the part has surface bodies, the panel shows one line: "Surface bodies are not included: they have no volume."
2. Measure gives the area of surface faces and bodies, and lengths of their edges, as for solids. It never shows a volume for a surface body (the kernel gives a meaningless number for open shells).
3. Overhang, wall thickness, build volume, orientation, Lay Face Flat and Split for Printing use solid bodies only. Today some of them mesh the whole part shape; they must skip surface bodies.

### SF0.11 Command tab

1. A new **Surfaces** tab after Bodies, before 3D Print (`ui/command_tabs/tabs.py`, `ui/main_window/window.py`). Apply RIBBON_SPEC R1 and R3 to it.
2. Groups, in this order:
   - **Create**: Extruded Surface, Revolved Surface, Swept Surface, Lofted Surface, Boundary Surface, Filled Surface, Planar Surface, Ruled Surface, Offset Surface.
   - **Edit**: Extend Surface, Trim Surface, Restore Surface Edges, Join Surfaces, Delete Surface.
   - **To Solid**: Thicken, Thicken and Subtract, Cut by Surface.
3. Thicken and Cut by Surface also appear on the Features tab: Thicken in the Add Material group, Thicken and Subtract and Cut by Surface in the Remove Material group.
4. A command that is not built yet is left out of the layout, as today.
5. Add a short RIBBON_SPEC section for the tab in the same branch.

### SF0.12 Tests for SF0

1. A part with one solid and one surface: tree counts, hide and show, isolate, colour, save, reopen, same names.
2. Every caller of `solids()` that now means "all bodies" has a test with a surface body in the part.
3. STEP round trip (item SF0.9.1). STL and 3MF exports skip the surface with the message.
4. Volume and weight ignore the surface and show the note.
5. An old part file from each earlier phase opens unchanged (CLAUDE.md section 4 item 4).
6. Definition of done item 3 (STEP reimport with matching volume) applies to solids. For surface bodies, check area and face count instead.

---

## SF1. Extruded Surface (High)

**Purpose.** Sweep a curve in a straight line to make a surface.

**Inputs.**
1. A sketch, or chosen contours of a sketch (selected regions, TOOL_SPEC T5), with open or closed curves. Open curves are the usual case. Crossing curves are allowed when the user picks contours.
2. Model edges, picked as a chain, as an alternative to a sketch.

**Options.**
1. Direction: normal to the sketch, or along a picked line, edge, axis or planar face normal.
2. End conditions: the same list as Extrude for a boss (Blind, Through All is left out because there is nothing to cut, Up to Vertex, Up to Face, Offset from Face, Up to Body, Mid Plane), plus a second direction.
3. Draft angle, inward or outward, with Flip.
4. **Close ends** (`cap_ends`): only for closed profiles. On, the ends are filled with flat faces. When both ends are closed, the result is a closed shell and the option **Make solid** (`make_solid`) appears. With Make solid on, the result is a solid body instead of a surface body. Off by default.

**Result and face naming.** One new surface body. Face roles: `side/<entity>` per sketch curve or edge, with `#k` when one curve gives several faces, and `cap/start`, `cap/end` when the ends are closed. These are the same roles as Extrude, so later features find faces the same way.

**Errors.**
1. "Extruded Surface 1 failed: the sketch has no curves. Add curves to the sketch or pick another one."
2. "Extruded Surface 1 failed: Close ends needs a closed profile. Close the profile or turn off Close ends."
3. Up to Face that misses: the same message as Extrude.

**Kernel note.** Reliable (prism of an edge or wire). Draft uses the same draft path as Extrude. Do not extrude a shell (it gives a compound of solids). The faces are extrusion surfaces, which the kernel will not extend directly; see SF10.

**Tests.** An open polyline of two lines, 30 and 20 mm, extruded 15 mm: two faces, area exactly 750 mm². A closed circle of 10 mm radius extruded 20 mm with Close ends and Make solid: a solid of volume pi times 100 times 20.

## SF2. Revolved Surface (High)

**Purpose.** Spin a curve about an axis to make a surface.

**Inputs.** A sketch or chosen contours, open or closed, and an axis: a sketch line or centreline, a model edge, or a reference axis. The curves may touch the axis but must not cross it.

**Options.** Angle, with Revolve's end conditions (Blind, Up to Vertex, Up to Face, Offset from Face, Mid Plane) and a second direction. Close ends and Make solid as SF1, for closed profiles that do not turn a full circle.

**Result and face naming.** One surface body. Face roles as Revolve: `side/<entity>`, `cap/start`, `cap/end`. Also fix the known gap (D529 item 5) for surface faces: faces from profile edges square to the axis get `side/<entity>` names, not fallback names.

**Errors.**
1. "Revolved Surface 1 failed: the profile crosses the axis. Move the profile to one side of the axis."
2. "Revolved Surface 1 failed: the axis lies in the profile. Pick an axis that is not one of the profile curves."

**Kernel note.** Reliable. Test first for curves that end on the axis: a curve end that is between 0 and about 1e-7 mm from the axis can give a wrong result with no error. Snap curve ends that are within the model tolerance onto the axis before the call. Faces that touch the axis have a pole; offset and thicken often fail on them (SF9, SF15).

**Tests.** A straight line from the axis to a point 12 mm out and 9 mm up, turned 360 degrees: a cone face of area pi times 12 times 15. The same line ending 1e-9 mm off the axis gives the same area and a valid face.

## SF3. Swept Surface (Medium)

**Purpose.** Move a curve along a path to make a surface.

**Inputs.**
1. Profile: a sketch, or one curve or chain of edges, open or closed.
2. Path: a sketch curve chain, a 3D curve, or model edges, tangent continuous. The path should start on the profile plane; if it does not, the sweep starts where the path meets it, and fails if it never does.
3. Guide curves (later, see options).

**Options.** The same as Sweep for a boss, where it applies: orientation (follow the path, or keep the profile's normal fixed), twist (none, or a total angle), and tangent start and end. Close ends and Make solid as SF1 for closed profiles. Guide curves come after the first release and only after their probe passes (kernel note).

**Result and face naming.** One surface body. Face roles as Sweep: `side/<entity>`, with `#k` per path segment after the first; `cap/start`, `cap/end` when closed.

**Errors.**
1. "Swept Surface 1 failed: the path does not reach the profile plane. Start the path on the profile's plane."
2. "Swept Surface 1 failed: the result crosses itself. Use a path with larger bends or a smaller profile."
3. "Swept Surface 1 failed: the path has a sharp corner. Round the corner or split the sweep in two."

**Kernel note.** Reliable for the plain modes (corrected Frenet, fixed). **Risky** with a guide rail (auxiliary spine): it is distorted in 8.0.1 and the contact modes fail. The older pipe maker can crash the process on some cubic paths, so use the pipe shell maker only. Never ask the kernel for a solid from an open profile.

**Tests.** An open arc of 8 mm radius, 90 degrees, swept along a 3D spline of our own choice: one valid face, no solid. A twisted sweep with twist 0 gives the same area as no twist (the D705 check).

## SF4. Lofted Surface (Medium)

**Purpose.** Make a surface that passes through two or more section curves.

**Inputs.** Two or more sections, each one open or one closed curve chain (sketches or model edges). Open and closed sections cannot be mixed. The first and last section may be a point.

**Options.**
1. Order of sections: the pick order. Drag to reorder.
2. Start and end shape: none, normal to the section, or tangent to a picked face whose edge is the section, with a weight.
3. Straight (ruled) between sections, or smooth.
4. Close the loop (last section joins the first), for three sections or more.
5. Alignment: the user can drag the start point of each closed section, as Loft does today.
6. Guide curves: after the first release, only after their probe passes.
7. Close ends and Make solid as SF1 for closed sections.

**Result and face naming.** One surface body. Face roles as Loft: `side/<entity>` from the first section's curves, `cap/start`, `cap/end`.

**Errors.**
1. "Lofted Surface 1 failed: sections 2 and 3 are of different kinds (open and closed). Use all open or all closed sections."
2. "Lofted Surface 1 failed: the surface twists between sections 1 and 2. Move the start point of section 2."
3. "Lofted Surface 1 failed: a point can only be the first or the last section."

**Kernel note.** Test first. The loft maker can crash the process (not only raise) on sections with different edge counts and on some closed sections, and a twisted ruled loft can pass the validity check. So: check section count, kinds and edge counts before the call; run lofts in a guarded worker process if one exists, otherwise check the inputs strictly; after a ruled loft, check that matching vertices are joined (no crossing). Guides use the new network surface class of 8.0, whose exact mode failed in our probe; use its approximate mode.

**Tests.** Three open splines of our own, smooth and ruled: one face smooth, two faces ruled, both valid. A two edge section with a one edge section: valid. A section with a reversed direction is aligned and does not twist.

## SF5. Boundary Surface (Medium)

**Purpose.** Fill the space inside a loop of two, three or four curves with one smooth surface that hits the curves exactly. Use it for shapes a loft cannot make, such as a patch that must meet four given edges.

**Inputs.** Two to four boundary curves that meet end to end in a loop (sketch curves, 3D curves or model edges). Two curves are opposite sides; the surface runs straight between them.

**Options.**
1. Shape: Flattest, Even or Fullest (three filling styles). Default Flattest.
2. Per edge that is a model edge of another body: match position only, or also be tangent to that body's face. Tangent edges use the Filled Surface method (kernel note).
3. Merge into the neighbour (`merge`): join the result to the surface body whose free edges it meets (SF13 rules).

**Result and face naming.** One face, role `face`. With merge on, it joins the neighbour and the neighbour's names carry.

**Errors.**
1. "Boundary Surface 1 failed: the curves do not form a closed loop. Make the curve ends meet."
2. "Boundary Surface 1 failed: it takes two to four curves. For more sides use Filled Surface."

**Kernel note.** Test first. The boundary filling class takes 2 to 4 curves that meet within 1e-7 mm. The middle style needs at least four control points per side and raises an error on simpler curves: raise the curve degree before the call, or fall back to another style and say so. Tangency to neighbours is not in this class; use the filling class of SF6 for edges set to tangent.

**Tests.** Four splines of our own forming a saddle loop: Flattest and Fullest give valid faces whose edges are on the curves (distance 0). Even works after the degree raise.

## SF6. Filled Surface (Medium)

**Purpose.** Patch a hole or an opening of any number of sides with a smooth surface. Also used to close the openings left by Delete Face.

**Inputs.**
1. Boundary: a closed chain of model edges, sketch curves or 3D curves.
2. Optional inner curves or points the patch must pass through.

**Options.**
1. Per boundary edge that belongs to a face: **Touch** (meets the edge), or **Tangent** (also smooth with that face). Sketch curves allow Touch only. Default Tangent where a face exists.
2. **Curvature** as a third choice is left out of the first release (kernel note). If added later, mark it as approximate.
3. Reverse the patch side.
4. Merge into neighbours (`merge`): join the patch to the surface bodies around it. When this closes a shell, **Make solid** appears.
5. When the boundary is on a solid (a hole in a solid's face set), the patch closes that solid instead, as Delete and Fill does today.

**Result and face naming.** One face, role `fill` (as Delete and Fill). With merge on, the neighbours' names carry.

**Errors.**
1. "Filled Surface 1 failed: the boundary is not closed. Pick edges that form a loop."
2. "Filled Surface 1 failed: Tangent needs a face on that edge. Set the edge to Touch or pick a model edge."
3. When the patch misses a constraint by more than 0.01 mm or 1 degree, it builds but warns: "Filled Surface 1 is not tangent everywhere: up to 2.3 degrees off. Add an inner point or set some edges to Touch." (real values).

**Kernel note.** Reliable for Touch and Tangent. **Risky** for curvature: the filling class rejects the curvature value of the continuity type and only reaches curvature through a different value, and then bulges. Conflicting constraints are dropped silently, so always measure the result's distance and angle to every constraint and report it (error 3). FDCAD's `direct.fill` already uses this class; reuse it.

**Tests.** A dome on the top edge of a 10 mm radius cylinder, Tangent, with one inner point 4 mm above the centre: valid, the point is hit within 0.01 mm, the angle to the side face is under 1 degree.

## SF7. Planar Surface (High)

**Purpose.** Make a flat face from a closed flat outline. Inner loops become holes.

**Inputs.** A closed sketch region (or several), or a closed chain of flat model edges or sketch curves that lie in one plane.

**Options.** None beyond the picks. Several outer loops give several faces in one surface body (only when they touch along edges) or one body each.

**Result and face naming.** One surface body per separate outline. Face roles: `face`, or `face#k` for several.

**Errors.**
1. "Planar Surface 1 failed: the edges are not in one plane. Pick edges that lie in one plane."
2. "Planar Surface 1 failed: the outline is not closed. Close the outline."
3. "Planar Surface 1 failed: the outline crosses itself."

**Kernel note.** Reliable. After adding holes, always run the face fix step (FDCAD's `sketch/profiles.py` already does): a hole wire in the wrong direction otherwise gives a wrong area with no error. The plane test uses the model tolerance.

**Tests.** A 14 by 9 mm rectangle with a 3 mm radius circle inside: area 126 minus 9 pi. The same with the circle drawn the other way round: same area.

## SF8. Ruled Surface (Medium)

**Purpose.** Grow a band of straight lines out from model edges, or span straight lines between two curves. Typical uses: a flange around an opening, a parting band, a wall that is then thickened.

**Inputs.**
1. **From edges** mode: one or more model edges (any body, as a tangent chain or single edges).
2. **Between curves** mode: two curves or edge chains.

**Options, From edges mode.**
1. Direction of the lines, one of:
   - **Square to the face**: along the normal of the face the edge belongs to.
   - **Along the face**: in the face, square to the edge, continuing the face outward.
   - **Along a direction**: parallel to a picked line, edge, axis or plane normal.
   - **Tilted from a direction**: at a typed angle to a picked direction, all round the edge.
2. Width of the band (a length), and Flip side.
3. For edges on two faces (an edge between faces), the user picks which face the direction is taken from (Other Face button).
4. Join the bands of a chain into one body (on by default). Where two bands meet at a corner they are trimmed or filled so the band has no gap. Corners that cannot be closed are left open and reported.
5. Join to the source (`merge`): when the edges are free edges of a surface body, the band joins that body.

**Options, Between curves mode.** Swap the direction of one curve if the band twists. The ends are matched automatically by distance.

**Result and face naming.** One surface body (or merged). Face roles: `ruled/<edge name>` per source edge in From edges mode; `ruled` or `ruled#k` between curves.

**Errors.**
1. "Ruled Surface 1 failed: the lines cross each other at a tight bend. Reduce the width or round the edge."
2. "Ruled Surface 1 failed: the edge has no face to take a direction from. Use Along a direction."
3. "Ruled Surface 1: 2 corners could not be closed and were left open." (warning)

**Kernel note.** Reliable between two curves (ruled face between edges, or a ruled loft). From edges has no kernel class. Build it as: Along a direction is a straight prism of the edge (exact). Tilted from a direction uses the draft maker. Square to the face and Along the face sample points on the edge, take the face normal there, build a second curve offset by the width, and make a ruled face between the edge and that curve. Test first: check that the sampled second curve is within 0.01 mm of the true offset at the mid points, and that two curves running opposite ways are aligned before the call.

**Tests.** Between two splines of our own: the two kernel methods give the same area. From the top edge of a 20 mm radius cylinder, Square to the face, width 5: a flat ring of area pi times (625 minus 400). Along the face, width 5: a cylinder band of area 2 pi times 20 times 5.

## SF9. Offset Surface (High)

**Purpose.** Make a new surface at a fixed distance from faces of a solid or a surface body. A distance of zero makes a copy of the faces.

**Inputs.** Faces of any body (solid or surface), connected or not. Connected faces give one body.

**Options.**
1. Distance (zero allowed), and Flip side. The arrow in the preview shows the side.
2. **Skip faces that fail** (`skip_failed`): off by default. On, faces that cannot be offset are left out and listed; the result has gaps where they were.

**Result and face naming.** A new surface body per connected set. Face roles: `offset/<source face name>`.

**Errors.**
1. "Offset Surface 1 failed: the distance is larger than the tightest curve on face <name> (radius 3.2 mm). Use a distance below 3.2 mm, offset to the other side, or turn on Skip faces that fail." The radius is the measured smallest radius on the failing side.
2. "Offset Surface 1 failed: the offset faces cross each other near face <name>." with the same next steps.
3. With Skip faces that fail on: "Offset Surface 1 left out 2 faces: <names>." (warning, faces highlighted when the feature is selected).

**Kernel note.** Test first. An offset past the curvature radius reports success and valid geometry but folds through itself. The plain validity check misses it; the argument analyser with self crossing on finds it. So after every offset: run the self crossing check (only on the new faces, to keep it quick), and compare the area with the expected area. The simple mode is correct only on smooth face sets; at a sharp corner it overlaps faces and still reports valid, so use the join mode for face sets with sharp edges. The sign follows the face normal, not "outward"; FDCAD's Flip must be defined against the preview arrow. Faces with a pole and C0 spline faces are known failures.

**Tests.** A curved sheet of our own with a 5 mm curvature radius: offset 1 mm inward works; 6 mm inward is refused with error 1 (not a folded result). An L of two flat faces at 90 degrees offset 1 mm outward: area matches the trimmed corner. Distance 0: same area as the source.

## SF10. Extend Surface (Medium)

**Purpose.** Make a surface body bigger past one or more of its free edges.

**Inputs.** Free edges of a surface body, or a whole surface face (then all its free edges).

**Options.**
1. How far: a distance, up to a picked point, or up to a picked face or surface (the extension stops where it meets it).
2. Shape of the extension: **Continue** (the surface keeps its own shape, so a cylinder keeps curving) or **Straight** (flat, tangent to the surface at the edge).
3. Add tangent edges (`tangent_chain`): pick one edge, extend the whole smooth chain.

**Result and face naming.** The same surface body, bigger. The source face keeps its name when the extension is part of the same face. A straight extension adds faces named `extend/<edge name>`.

**Errors.**
1. "Extend Surface 1 failed: edge <name> is not a free edge. Pick an edge on the outside of a surface body."
2. "Extend Surface 1 failed: the extension does not reach <face>. Use a distance, or pick a face that the extension crosses."
3. "Extend Surface 1 failed: the extension crosses itself. Use a shorter distance or Straight."

**Kernel note.** Test first. The kernel's face extension rebuilds the whole face from its parameter box: it drops holes and trims (a round face came back square in our probe), extends whole sides only, and returns extrusion and revolution faces unchanged with no warning. The other extension call is broken through the Python binding (it returns nothing). So build Continue as: convert the face to a spline surface when it is not a plane, cylinder, cone, sphere or torus; extend the side the picked edge lies on; rebuild the face with its old outline plus the new strip; check the area grew by about edge length times distance. An edge that is not along a parameter side (a trimmed edge across the surface) gets Straight only, and the panel says so. Build Straight as a ruled band along the face (SF8) joined to the source (SF13).

**Tests.** A flat 10 by 10 face extended 3 mm from one edge, both shapes: area 130. A quarter cylinder face extended 5 mm with Continue: still a cylinder of the same radius. An extruded spline face extended 4 mm: area grows, no silent no-op.

## SF11. Trim Surface (High; mutual mode Medium)

**Purpose.** Cut surface bodies where they meet a tool, and throw away the pieces the user does not want.

**Inputs.**
1. **With a tool** mode: one tool (a surface body, a plane, a flat face, or a sketch, whose curves are pushed through square to its plane), and one or more surface bodies to trim.
2. **Each other** mode (mutual): two or more surface bodies that trim each other.

**Options.**
1. Pieces: after the tool cuts, the view shows each piece. The user clicks pieces. A switch says what the clicked pieces are: **Remove these** (default) or **Keep only these**. The preview shows kept pieces solid and dropped pieces faint.
2. In Each other mode, **Join the result** (`join`, on by default): the kept pieces are joined into one surface body where they meet.
3. Where a tool curve stops inside the surface without reaching its edge, the cut does nothing there. The panel offers **Continue the cut to the edge** (`continue_cut`): the cut line is carried on in a straight line from its ends to the nearest free edge. Off by default.

**Result and face naming.** The trimmed bodies. Faces that are cut keep their names with `#k` for pieces (today's split rule, ordered by position). Picked pieces are stored by a point on each piece and by name, so a later rebuild picks the same piece (use the stored position check of PLAN.md section 6).

**Errors.**
1. "Trim Surface 1 failed: the tool does not cut across Surface 2. Make the tool larger (Extend Surface), turn on Continue the cut to the edge, or pick another tool." Always check that the piece count went up; the kernel returns the surface unchanged with only a mark on it when the tool stops short.
2. "Trim Surface 1 failed: no pieces would be left. Pick fewer pieces to remove."
3. On rebuild, when a stored piece cannot be found: the lost reference warning of PLAN.md section 6, naming the piece.

**Kernel note.** Reliable when the tool crosses the surface fully (splitter). The tool that stops inside only marks the surface: detect it (error 1). Continue the cut is FDCAD's own: build the straight continuation curves, then split.

**Tests.** A 10 by 10 flat sheet cut by a curved sheet that crosses it: two pieces whose areas add to 100. Remove the smaller: one piece left, its area right. A tool that stops 2 mm short: error 1; with Continue the cut on: two pieces. Each other mode with two crossing sheets of our own: kept quarters join into one body.

## SF12. Restore Surface Edges (Low)

**Purpose.** Undo trims on a surface: fill its holes, or grow its outline back towards the surface's own full shape.

**Inputs.** A surface face, or some of its edges.

**Options.**
1. What to restore: **Holes** (inner loops only), **Outline** (the outer edges), or **Both**.
2. With edges picked: only those edges move back.
3. How far, for Outline: **Full** (the surface's own limits) or a typed length past the current edge.
4. Keep the original (`keep_original`): off by default, the face is replaced. On, the restored face is a new surface body and the source stays.

**Result and face naming.** The same face name (or `restore` for the new body when Keep the original is on).

**Errors.**
1. "Restore Surface Edges 1 failed: this face has no outer limit to restore to (it is flat or round all the way). Use a length instead of Full."
2. "Restore Surface Edges 1 failed: the face has no holes." (when Holes is picked on a face without holes)

**Kernel note.** Reliable. Holes: rebuild the face from its outer wire, or remove inner wires. Full: rebuild from the surface's own bounds. Planes and cylinders have endless bounds, so Full is refused for them (error 1). A closed round surface restored in full closes into a tube; allow it. Trimmed spline faces can have bounds much larger than expected; always show the preview. STEP export of a restored round face can lose its seam (an open kernel bug): include a STEP round trip in the tests.

**Tests.** A spline sheet of our own with a 4 mm hole: Holes gives back the full area. A flat face with Full: error 1. With a length of 2 mm: area grows by perimeter times 2, about.

## SF13. Join Surfaces (High)

**Purpose.** Sew surface bodies (and faces of solids) into one surface body along edges that touch. When they close a volume, make a solid.

**Inputs.** Two or more surface bodies, or faces (of surfaces or solids).

**Options.**
1. Gap tolerance (`tolerance`): edges closer than this are joined. Default 0.01 mm, from 0.0001 mm to 0.5 mm. A larger value warns: "A tolerance above 0.1 mm can make later features fail."
2. **Make solid** (`make_solid`): when the joined set is closed, the result is a solid body. On by default. If the set is not closed, the result stays a surface body and a warning lists the gaps.
3. Merge faces on the same surface (`merge_faces`): faces on the same plane, cylinder or spline become one face. Off by default.
4. **Gaps** list: after a preview, the panel lists every free edge pair found, with its gap size, largest first. Clicking a row zooms to it in the view. A button by each row sets the tolerance just above that gap. The list is recomputed when the tolerance changes.

**Result and face naming.** One body. The inputs are consumed. Face names carry from the inputs. Solids made from faces of solid bodies keep those faces' names.

**Errors.**
1. "Join Surfaces 1 found no edges to join. The surfaces do not touch within 0.01 mm. Raise the tolerance or close the gaps."
2. "Join Surfaces 1: the result is not closed (3 gaps, largest 0.08 mm), so it stays a surface body. Raise the tolerance above 0.08 mm or fill the gaps." (warning when Make solid is on)
3. "Join Surfaces 1 failed: three or more faces meet at edge <name>. Trim the extra surface first."
4. "Join Surfaces 1 failed: the joined set is split into 2 separate pieces. Pick surfaces that touch, or join each piece on its own."

**Kernel note.** Reliable (sewing, then making a solid and fixing its direction). The kernel's result kind varies (a face, a shell, or a mix); always split it into shells and count free edges. Sewing raises edge tolerances up to the gap size, which makes later booleans fuzzy: hence the small default and the warning. T joints (three faces on one edge) are not sewn in the normal mode: report them (error 3). Faces must not overlap; detect overlap by the sewing report and say so.

**Tests.** Six flat faces of our own box, 12 by 8 by 5 mm: one solid, volume 480. Two sheets with a 0.05 mm gap: tolerance 0.01 gives error 1 and lists the 0.05 mm gap; tolerance 0.1 joins them. Three faces on one edge: error 3.

## SF14. Delete Surface (High)

**Purpose.** Remove faces from a body and leave what is left open, as a surface body. The Surfaces tab command **Delete Surface** opens Delete Face with the Delete option set. It is the same feature type as Delete Face (D510); this section also covers Delete Face's other options on surface bodies.

**Inputs.** Faces of a solid body or of a surface body.

**Options.** Delete Face's options: **Delete** (leave the opening), **Delete and Patch** and **Delete and Fill** (close it, as today).

**Result and face naming.**
1. Delete on a solid: the solid becomes a surface body with the remaining faces. Their names do not change. The tree row moves from Solid Bodies to Surface Bodies.
2. Delete on a surface body: the faces are removed. If what is left falls into separate pieces, each piece is a surface body.
3. Patch and Fill on a surface body: the opening left by the faces is closed. Fill on a surface uses SF6's method. Patch extends the neighbours, as today.
4. Default tree name for the Delete option: "Delete Surface 1"; for the others: "Delete Face 1", as today.

**Errors.**
1. "Delete Surface 1 failed: it would delete every face of the body. Use Delete Body instead."
2. Patch on a surface where neighbours do not meet: today's message.

**Kernel note.** Reliable. Removing a face from a solid leaves an invalid solid: always take the solid's shell, remove the faces from the shell, and return the shell. The defeaturing call (Patch) refuses shells; on a surface body, Patch works face by face with extended neighbours, or is refused with a message to use Fill, after a probe. Find the openings with the free bounds analysis and draw them in the free edge colour.

**Tests.** A 10 mm cube minus its top face: one surface body of 5 faces, area 500, one free loop. Delete one of two faces on a two face surface: one face left. Delete two opposite faces of a box: one surface body (still connected).

## SF15. Thicken (High)

**Purpose.** Turn a surface body into a solid by giving it a thickness. Also turn a closed surface body into a solid by filling it.

**Inputs.** One surface body. A set of separate surfaces must be joined first (SF13); the panel says so when two bodies are picked.

**Options.**
1. Thickness (default 2 mm).
2. Side: **Front** (the side the normal points to, shown by the preview arrow), **Back**, or **Both** (half the thickness on each side, so the total is the typed value). Note that "Both" splits the typed value; this is FDCAD's choice, to match Mid Plane on Extrude.
3. Corners where the surface has a sharp edge: **Sharp** or **Round** (round on the outside of the bend).
4. **Fill the closed volume** (`fill_closed`): shown only when the surface is closed. The result is a solid that fills it, and Thickness is hidden.
5. Merge with solid bodies it touches (`merge`, on by default), with the bodies box (TR33, D697) for which solids.
6. **Consume the surface** (`consume`, on by default): the surface body is removed after the feature. Off keeps it (for example, to thicken it again elsewhere).

**Result and face naming.** A solid. Face roles: `front/<source face>`, `back/<source face>` and `wall/<free edge name>` for the faces round the edge.

**Errors.**
1. "Thicken 1 failed: the thickness is larger than the tightest curve on face <name> (radius 1.6 mm). Use a thickness below 1.6 mm or thicken to the other side." (measured radius)
2. "Thicken 1 failed: face <name> comes to a point (a pole), which cannot be thickened that way. Thicken to the other side, or trim the point off and fill it."
3. "Thicken 1 failed: the surface is made of 2 separate bodies. Join them first with Join Surfaces."
4. "Thicken 1 failed: the result is not a valid solid. Try a smaller thickness or Round corners." (when the checks below catch a bad result)

**Kernel note.** Test first. The thicken path (offset with thickening on) gives an invalid solid when the thickness passes the curvature radius, and gives garbage or throws on faces with a pole. The simple thick solid method works on smooth faces and on poles but returns an inside out solid and is wrong at sharp corners. So: try the thicken path (intersection join for Sharp, arc join for Round); check it is done, valid, and that its volume is within 30 percent of area times thickness; if not, and the surface is smooth, try the simple method and fix its direction; if both fail, give error 1, 2 or 4. Always fix the solid's direction. Run in the worker. FDCAD's `rib.py` already uses the simple method.

**Tests.** A curved sheet of our own (curvature radius 5 mm), 1 mm to each side: valid, volume near area times 1. 6 mm on the inner side: error 1, not a bad solid. An L of two flat faces at 90 degrees, Sharp and Round: exact volumes for our sizes. A revolved dome touching the axis, 1 mm: works through the fallback. A closed box surface with Fill the closed volume: the box's volume.

## SF16. Thicken and Subtract (Medium)

**Purpose.** Thicken a surface and cut the thickened shape out of solid bodies. Used to cut a groove or slot that follows a curved surface.

**Inputs.** One surface body, and the solids to cut (bodies box: all or selected, TR33).

**Options.** Thickness, Side and Corners as SF15. Consume the surface as SF15. When the cut splits a body, the pieces become separate bodies and the panel offers which to keep, as other cuts do (`keep` list).

**Result and face naming.** The cut solids. New faces: `cut/front/<source face>`, `cut/back/<source face>`, `cut/wall/<edge>`.

**Errors.** SF15's errors 1 to 4, plus: "Thicken and Subtract 1 did not touch any body. Move the surface into the body or pick other bodies."

**Kernel note.** Test first. Thicken (SF15) then a cut. A cut that touches nothing, or one the kernel gets wrong, gives no error: check the volume went down by at most the thickened volume (the D705 sanity check), and that something changed.

**Tests.** An 8 by 8 by 10 mm block minus a 1 mm slab from a curved sheet that crosses it: two bodies whose volumes add up to the block minus the slab part inside.

## SF17. Cut by Surface (High)

**Purpose.** Cut away the part of solid bodies on one side of a surface or plane.

**Inputs.** One surface body, a plane, or a flat face; and the solids to cut (bodies box, TR33).

**Options.**
1. Side: the preview arrow points to the material that is removed. **Flip** swaps it.
2. Keep both sides (`keep_both`): the cut makes two bodies and nothing is removed. Off by default. (This matches Split with one tool; the option is here because users look for it here.)
3. Consume the surface (`consume`, off by default for this tool, because the same surface often cuts several parts). Hidden by the user as any body.

**Result and face naming.** The cut solids. New faces: `cut/<surface face name>`, with `#k` for several pieces.

**Errors.**
1. "Cut by Surface 1 failed: the surface does not reach across Body 1. Make the surface larger (Extend Surface or Restore Surface Edges) so it passes the body on every side." Always check that the body was really divided: the kernel either marks the body or returns it whole, with no error, when the surface stops short.
2. "Cut by Surface 1 would remove the whole of Body 1. Flip the side."

**Kernel note.** Reliable when the surface crosses the body fully. Use the splitter, then keep the pieces on the kept side (classify a point on each piece against the surface's side), or the half space cut. A plane or flat face is extended without limit, as Split does today. A curved surface is not extended: error 1.

**Tests.** An 8 by 8 by 10 mm block cut by a curved sheet larger than the block: both sides give volumes that add up to 640. A sheet smaller than the block: error 1, not an unchanged block.

---

## SF18. Order of work

1. SF0 in full (body model, tree, selection, display, colours, solid feature rules, Delete Face option, file change proposal, export, import, mass properties, tab), with its tests, before any tool.
2. High tools: SF1, SF2, SF7, SF13, SF14, SF15, SF17, SF9, SF11 (standard mode). This set already lets a user make and print a thin curved part: build surfaces, trim, join, thicken.
3. Medium: SF3, SF4, SF6, SF5, SF8, SF10, SF16, SF11 mutual mode, SF0.6 item 6 (Intersect cap).
4. Low: SF12. Then the optional parts marked "after the first release" (sweep and loft guides, Filled curvature).

## SF19. Clean room notes for implementers

1. The tool names, option names, roles, defaults, messages and test values in this file are FDCAD's own. Use them as written or choose better FDCAD names, and record the choice.
2. Where this spec leaves a choice open, decide from general geometry and FDCAD's own tools, never from outside CAD material, and record it in DECISIONS.md.
3. D850 is the manager's decision for this phase. Implementers record their choices from D860 upward unless the manager gives another block.
