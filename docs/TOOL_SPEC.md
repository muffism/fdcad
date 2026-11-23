# Tool behaviour spec (Phase 1 tools)

This file says, tool by tool, how every Phase 1 tool must behave. It completes `docs/WORKFLOW_SPEC.md` (the order of steps) with the detail of each tool (what each click does, what is shown, what options exist). It was written by the manager from public learning material (logged in the clean room record (kept privately, outside this repository)) in our own words. It holds no copied text, names, icons or screenshots.

Tags:
- **[P1]** must work for the 0.1.0 release.
- **[Later: Phase N]** described so the Phase 1 code does not block it; not built now.
- **[Built: Dnnn]** a former [Later] item that is now built; the decision says how (round 9t, D510).
- **(Owner note N)** links to the owner's test notes from 0.1.0-dev testing (listed at the end).

## T1. Common sketch behaviour

### T1.1 Starting and ending a tool [P1]
1. A sketch tool stays active after each shape so the user can draw several in a row.
2. A tool ends with Esc, by clicking its button again, by picking another tool, by clicking Select, or by OK in its panel. Right click while a tool is active shows a menu whose first item is "Select" (end the tool), see T9.
3. Two ways to draw every two click shape: click, move, click (click click); or press, drag, release (click drag). Both give the same result.
4. While a tool is active, the left panel shows that tool's panel (T7) instead of the feature tree.

### T1.2 Snapping (owner notes 1, 4, 8) [P1]
Snapping means the cursor jumps to a meaningful point when it is within a small screen distance (about 8 px, scaled for high DPI) of it. Snapping works in every sketch tool, in Smart Dimension and while dragging sketch geometry.

1. Snap targets, all on by default:
   - The sketch origin.
   - End points of lines, arcs and centerlines, and sketch points.
   - Centres of circles and arcs. The centre of a circle or arc is hidden until the cursor passes over the curve; then the centre appears and can be snapped to (owner note 8: today this does not work).
   - Midpoints of lines and arcs.
   - Quadrant points of circles and arcs (0, 90, 180, 270 degrees in sketch axes).
   - Intersections of two sketch curves.
   - Nearest point on a curve (lowest priority).
2. Model geometry (owner note 1): edges, vertices, circular edge centres and the projected origin of the part, all projected onto the sketch plane, are snap targets too. Snapping to model geometry adds the matching relation to a fixed copy of the model point (D113).
3. Priority when several are in range: origin and end points, then centres, then midpoints and quadrants, then intersections, then nearest on curve.
4. Feedback: the target point highlights, and a small symbol next to the cursor shows the snap kind (end point, centre, midpoint, quadrant, intersection, on curve).
5. Alignment guides: when the cursor lines up horizontally or vertically with a known point (including the origin and circle centres), a dotted guide line shows it, and the cursor snaps onto that line.
6. Direction snaps for lines: a line close to horizontal or vertical snaps to it; a line close to parallel or perpendicular to another line snaps to that.
7. Holding Ctrl while moving turns snapping off for that move.
8. Settings (Preferences > Sketch): snapping on or off; snap to model geometry on or off; automatic relations on or off; each snap kind on or off. [P1 for the first three, rest Later: Phase 2]

### T1.3 Automatic relations [P1]
1. When a click lands on a snap, the matching relation is added at once: on a point or origin gives Coincident; on a curve gives Coincident (point on curve); on a midpoint gives Midpoint; on a centre gives Coincident with the centre (or Concentric when a circle is drawn from it); along a horizontal or vertical snap gives Horizontal or Vertical; parallel or perpendicular snaps give those relations; a tangent arc start gives Tangent.
2. Relations show as small tags beside the geometry (WORKFLOW_SPEC W3.3). Hovering a tag names it. Clicking a tag selects the relation; Delete removes it.
3. Turning automatic relations off keeps snapping but adds no relations.

### T1.4 Sketch status and colours [P1]
1. Each entity and each point has a state shown by colour: under defined (blue), fully defined (black, white in dark theme), over defined or unsolvable (red), selected (accent), driven (reference) dimension (grey).
2. End points are drawn as small filled dots in their state colour.
3. The status bar shows the state of the whole sketch. The tree marks an under defined sketch with a "(-)" prefix and an over defined one with "(+)".
4. Adding a dimension that would over define the sketch asks: "This dimension over defines the sketch. Make it a reference dimension?" with buttons Make Reference and Keep Driving. Reference dimensions show the value in parentheses and in grey; they update but cannot be edited.

### T1.5 Exiting a sketch [P1]
1. Exit and keep: confirmation corner sketch mark, Exit Sketch button, or the right click menu item. The view stays as it is.
2. Exit and discard: the red X in the confirmation corner, with a confirmation question if anything changed. The view returns to where it was before the sketch opened.

## T2. Sketch tools

Every tool has a panel (T7) with its options and, once a shape is drawn, the shape's editable values.

### T2.1 Line [P1]
1. Click the start, click the end. The tool then continues from the end point (chain), so the next click makes the next segment.
2. Double click, Esc or right click > End Chain ends the chain but keeps the tool. Clicking the start of the chain closes the loop and ends the chain.
3. Line to arc switch: after a segment, moving the cursor back onto the end point and away again previews a tangent arc instead of a line; clicking places it, and the chain continues with a line. A shortcut key can also switch between line and arc without going back to the end point (no default key, see T12.5).
4. Panel options: orientation (As drawn, Horizontal, Vertical, Angle), For construction, and after drawing: length and angle fields.
5. While drawing, the length and angle show next to the cursor.

### T2.2 Centerline [P1]
1. Same input as Line, without the line to arc switch. Always construction geometry, drawn dashed.
2. Used as the revolve axis (T5) and for symmetric relations and doubled distances (T4.4).

### T2.3 Rectangles [P1]
1. Corner rectangle: click one corner, click the opposite corner. Adds Horizontal and Vertical relations to the sides.
2. Centre rectangle: click the centre, click a corner. Adds construction diagonals from corner to corner meeting at the centre point, and the side relations. Shift while drawing makes a square (adds Equal).
3. The corners are points that can be snapped and dimensioned.
4. [Built: D511] 3 point corner rectangle, 3 point centre rectangle, parallelogram.

### T2.4 Circle [P1]
1. Centre circle: click the centre, click a point on the circle (sets the radius). The centre shows as a small plus mark.
2. [Built: D512] Perimeter circle (three points on the circle).
3. Panel after drawing: centre X, Y and radius fields, For construction.

### T2.5 Arcs [P1]
1. Centre point arc: click the centre, click the start (sets the radius), click the end (the arc follows the cursor around the centre, either way round).
2. Tangent arc: click an end point of a line or arc, then move and click. Moving away along the end direction gives an arc tangent to it; moving sideways gives an arc normal (perpendicular) to it. Returning to the end point and leaving in a new direction switches between the two.
3. 3 point arc: click the start, click the end, then move to set the bulge and click.
4. All arcs show their centre while selected or hovered, and it can be snapped to.

### T2.6 Point [P1]
Click to place a sketch point. Points are construction only (not part of profiles) but can be dimensioned and related.

### T2.7 Construction toggle [P1]
Any selected entity can be switched between normal and construction geometry from its panel, the context toolbar or the right click menu. Construction geometry is dashed and never forms a profile.

### T2.8 Dragging geometry [P1]
With no tool active, dragging an under defined entity or point moves it while the solver keeps all relations and dimensions. Fully defined geometry does not move. Dimensions are never changed by a drag.

## T3. Relations

### T3.1 Relation types [P1]
Each relation, which selections it accepts, and what it does:

| Relation | Selection | Result |
|---|---|---|
| Horizontal / Vertical | one or more lines, or two or more points | lines lie along the sketch X or Y axis; points line up along X or Y |
| Collinear | two or more lines | the lines lie on the same infinite line |
| Parallel | two or more lines | same direction |
| Perpendicular | two lines | at 90 degrees |
| Tangent | a line or arc with an arc or circle | they touch smoothly |
| Coincident | a point with a point, line, arc or circle (including the origin and model points) | the point lies on the other item |
| Midpoint | a point with a line or arc | the point stays at the middle |
| Concentric | two or more arcs or circles, or a point with an arc or circle | they share a centre |
| Coradial | two or more arcs or circles | same centre and same radius |
| Equal | two or more lines, or two or more arcs and circles | equal lengths, or equal radii |
| Symmetric | a centerline and two points, lines or arcs | mirror images about the centerline |
| Intersection | two lines and a point | the point stays where the lines cross |
| Fix | any entity | the entity cannot move or resize |

Notes, as behaviour the user will notice:
1. A relation to a line acts on its infinite extension, so items can line up without touching.
2. A relation to an arc acts on its full circle.
3. A relation to model geometry acts on its projection onto the sketch plane.

### T3.2 Adding relations by hand (owner note 5) [P1]
1. Ctrl click two or more items (sketch entities, points, the origin, model edges or vertices). The panel shows "Add Relations" with only the relations that fit the selection, as buttons with icons. Clicking one adds it; the list refreshes so another can be added.
2. The context toolbar (T8) shows the same fitting relations as small buttons.
3. The origin is a valid item: origin plus a point offers Coincident, Horizontal and Vertical (owner note 5, missing today).
4. The panel also lists the existing relations of the selection, each with a delete button, and shows the selection's state (under, fully or over defined).

### T3.3 Showing and deleting relations [P1]
1. A "Relations" panel (Sketch tab button) lists every relation in the sketch with a filter: All, Over defining or not solved, Model references.
2. Selecting a row highlights the related items. Delete and Delete All remove relations (undoable).

## T4. Dimensions (Smart Dimension)

### T4.1 What one tool does [P1]
Smart Dimension chooses the kind of dimension from what is clicked and where the text is placed. The tool stays active after each dimension. Esc removes the last picked item; a second Esc ends the tool.

| Clicks | Dimension |
|---|---|
| a line or a straight model edge | its length |
| two parallel lines (or a line and a parallel edge) | the distance between them |
| two lines that are not parallel | the angle between them; which of the four angles depends on where the text is placed |
| a point and a line or edge | perpendicular distance |
| two points (sketch points, end points, origin, model vertices) | distance; placing the text above or below gives horizontal, left or right gives vertical, along the line gives true distance |
| a circle | diameter |
| an arc | radius |
| an arc, then its two end points | arc length [Built: D515] |
| a circle or arc and any other item (point, line, origin, edge, circle) | distance to its centre by default (owner note 10) |
| a line and a centerline, with the text placed on the far side of the centerline | doubled distance (shown as a diameter), for revolve profiles |

### T4.2 Placing and typing (owner note 2, 3) [P1]
1. After the clicks, the dimension follows the cursor, semi transparent, until a click places it.
2. On placement the value box opens right beside the dimension text, never in a fixed place on screen, with the current value selected. It has OK, Cancel, Rebuild (apply and keep the box open), Reverse (for signed distances) and a spin increment control. [Built without the Reverse button; audit 2026-11-02 D2 item 12.]
3. Mouse wheel over the box or up and down arrows change the value by the spin step (1 mm or 1 degree by default); with Ctrl, ten times the step; with Alt, a tenth.
4. The box accepts expressions and units (PLAN section 7). Enter accepts, Esc cancels and removes the new dimension.
5. While Smart Dimension is active, the left panel shows a Dimension panel (owner note 3) with: the value field (same as the box), whether the dimension is driving or reference, and for distances involving circles or arcs, the measure to setting (T4.3). Selecting an existing dimension shows the same panel.

### T4.3 Distances to circles and arcs (owner note 10) [P1]
1. By default a distance to a circle or arc is measured to its centre, even if the user clicked the curve.
2. For a circle or arc with a line, or with another circle or arc, the Dimension panel offers "Measure to" for each circle: Centre, Nearest (closest point of the curve) or Farthest (far side of the curve).
3. Holding Shift while clicking the curve picks Nearest or Farthest directly, based on which side was clicked. [Built: D516]

### T4.4 Editing dimensions [P1]
1. Double clicking any dimension opens the same value box beside it (WORKFLOW_SPEC W4.2).
2. Dimensions can be dragged to new places while Smart Dimension or Select is active. Dragging the text across the line changes which side the dimension sits on, not its value.
3. Delete removes the selected dimension.
4. Right click on a dimension: Edit Value, Reference or Driving, Delete.

## T5. Extrude and Extruded Cut

### T5.1 Panel [P1]
1. Header: feature icon and name, OK, Cancel.
2. **From** group [P1, owner request 2026-10-29, D116 item 6]: a start condition list with four choices. The same list for Extrude and Extruded Cut. The profile is always the sketch's profile; only where the feature starts changes.
   - **Sketch Plane** (default): the feature starts on the sketch plane, as today.
   - **Surface/Face/Plane**: a pick box takes one face of the part or one reference plane. The profile is carried along the extrude direction onto that face, and the feature starts there. On a flat face or plane the start is flat. On a curved face the start follows the face's shape. If the carried profile does not land fully on the face, the feature shows an error saying so and suggests another face or Sketch Plane.
   - **Vertex**: a pick box takes one vertex of the part or one sketch point. The feature starts on a plane parallel to the sketch plane through that point.
   - **Offset**: a distance field with its own Reverse Direction button. The feature starts on a plane parallel to the sketch plane at that distance. It uses the value box behaviour (wheel and arrows step, expressions).
   - Direction 1 depth is measured from the start, not from the sketch plane. Mid Plane splits around the start. Through All still goes through the whole part from the start.
   - The picked face, plane or vertex is stored by topological name (FDEF_SPEC 7), like other references. If it is lost after an edit, the feature shows an error naming the lost pick and asks the user to pick again (CLAUDE.md 5.12).
   - The preview and drag handle follow the start (T5.2).
3. **Direction 1** group: Reverse Direction button; end condition list; depth field with its own value box behaviour (wheel and arrows step, expressions); Merge Result tick box for bosses after the first body.
   - End conditions [P1]: Blind (depth), Through All (cuts, both bosses and cuts may use it once a body exists), Mid Plane (depth split equally on both sides).
   - [Built: D210, D460, D461, D510] Up to Next, Up to Vertex, Up to Face, Offset from Face, Up to Body, Draft (angle, inward or outward).
4. **Direction 2** group (tick box, collapsed): the same end conditions in the other direction. Not available with Mid Plane.
5. **Cut Outside** tick box (cuts only): removes material outside the profile instead of inside. [P1]
6. **Selected Regions** group (owner note 9) [P1]: see T5.3.
7. [Built: D211, D510] Thin Feature group (thickness one way, both ways equally, or two values; required for open profiles).

### T5.2 Preview and drag handles (owner note 7) [P1]
1. The preview updates on every change (WORKFLOW_SPEC W6.4).
2. An arrow handle sits at the end of each active direction. Dragging it changes the depth live. While dragging, a ruler appears along the drag direction with tick marks; when the cursor is over the ruler the depth snaps to the tick steps, when away from it the depth is free.
3. The value shown beside the handle is clickable: clicking it opens the value box there to type the depth (owner note 7). Enter applies; the panel field and preview update.
4. Holding Alt while dragging and moving over a model face or vertex snaps the end to it (sets Blind depth to that distance). [Built: D525]
5. Dragging past the sketch plane flips the direction.

### T5.3 Selected regions (owner note 9) [P1]
1. A sketch's curves split its plane into closed regions, including regions made by curves that cross or by one shape inside another.
2. In the Selected Regions box, hovering the viewport highlights the region under the cursor (fill in the accent colour, light); clicking adds it (stronger fill); clicking again removes it. Ctrl is not needed.
3. Several regions can be picked; they may touch or be apart. Only picked regions are used. An empty box means the whole sketch as today (all outer loops with their holes).
4. Picks are stored by topological name so they survive edits to the sketch where the region still exists; if a picked region disappears, the feature shows an error saying which pick was lost and asks the user to repick (no silent change, CLAUDE.md 5.12).
5. The same sketch can be used by several features with different regions (a shared sketch). The tree then shows it under the first feature and as a link icon under the others.
6. Applies to Extrude, Extruded Cut, Revolve and Revolved Cut.

### T5.4 Without the panel (drag a sketch) [Built: D525]
With a finished sketch, clicking inside one of its regions shows an arrow handle; dragging it makes a boss or cut directly (a region on a face of the part starts as a cut, a region off the part starts as a boss), and a small toolbar after release lets the user switch boss and cut.

## T6. Revolve and Revolved Cut

### T6.1 Panel [P1]
1. **Axis** box: a centerline, a sketch line or a straight model edge. With exactly one centerline in the sketch it is picked automatically.
2. **Direction 1**: Reverse Direction; type Blind (angle, default 360 degrees) or Mid Plane (angle split both ways); angle field with value box behaviour.
3. **Direction 2** (tick box): a second angle the other way round. Total cannot exceed 360 degrees.
4. Merge Result (bosses), Cut Outside (cuts), Selected Regions (T5.3).
5. [Built: D462 to D464, D523] Up to Vertex, Up to Face, Offset from Face, Thin Feature.

### T6.2 Rules [P1]
1. Profiles must not cross the axis. If one does, the feature shows "Revolve 1 failed: the profile crosses the axis. Move the profile to one side of the axis or pick regions on one side." and highlights the crossing.
2. A profile may touch the axis along an edge (the common turned part case).
3. With more than one centerline the user must pick one; the panel says "Pick the axis of revolution".

### T6.3 Preview and handle [P1]
1. Arc shaped handle at the end of the revolve with an angular ruler while dragging (snaps to 5 degree ticks when over the ruler).
2. The value beside the handle is clickable to type the angle (owner note 7).

### T6.4 Dimensions on revolve profiles [P1]
Dimensioning from a line to the axis centerline with the text placed on the same side gives a radius; with the text on the other side of the axis it gives a diameter (doubled distance), shown with the diameter symbol.

## T7. The left panel while working (owner note 3) [P1]

1. While a sketch tool, Smart Dimension, a relation selection or a feature is active, the left panel shows its panel in place of the feature tree. A small tab strip at the top of the left panel lets the user peek at the tree without ending the tool.
2. Sketch tool panels: options (orientation, construction), then the drawn shape's values (lengths, angle, centre, radius), which can be typed to change the shape.
3. Selecting a sketch entity with no tool active shows its panel: existing relations (with delete), add relations (fitting ones), parameters, For construction, Fix.
4. Selecting a dimension shows the Dimension panel (T4.2.5).

## T8. Context toolbar on selection [P1]

1. Selecting an item (click in the viewport or tree) shows a small toolbar near the cursor with the most used actions for that item. It fades as the cursor moves away and disappears on the next click elsewhere.
2. Contents by selection:
   - Plane or flat face: Sketch, Normal To, Hide or Show.
   - Feature: Edit Feature, Edit Sketch, Hide or Show, Delete.
   - Sketch (finished): Edit Sketch, Extrude, Revolve, Hide or Show.
   - Sketch entities (in a sketch): fitting relations (T3.2), Construction toggle, Smart Dimension.
3. Right clicking while it is shown adds the full right click menu below it.

## T9. Right click menus (owner note 6) [P1]

Right click in the viewport or tree opens a menu for what is under the cursor. Items that do not apply are hidden, not greyed. Each menu ends with Zoom to Fit and the view orientations submenu where it makes sense.

1. **Empty viewport, no sketch**: Select, Zoom to Fit, Previous View, View Orientation, Display Style, Recent Commands.
2. **Empty viewport, in a sketch**: Select, Exit Sketch, Discard Changes, Smart Dimension, Snapping on or off, the last used sketch tool, Normal To, Zoom to Fit.
3. **While a sketch tool is active**: Select (end tool), End Chain (lines), Snapping on or off, Zoom to Fit.
4. **While a feature panel is open**: OK, Cancel, Reverse Direction, then view items.
5. **Plane**: Sketch, Normal To, Hide or Show, Rename.
6. **Face**: Sketch, Normal To, Hide or Show Body, Select Other (lists everything under the cursor, see below).
7. **Edge or vertex**: Select Other, Select Midpoint (edge, used by Smart Dimension).
8. **Sketch entity**: Delete, Construction toggle, Smart Dimension, Add Relation (fitting ones), Fix, Select Chain.
9. **Dimension**: Edit Value, Reference or Driving, Delete.
10. **Any feature in tree or viewport** (Extrude, Cut, Revolve, Revolve Cut, and every later feature type): Edit Feature, Edit Sketch, Hide or Show Sketch, Rename, Delete (asks whether to keep the sketch), Roll Back to here, Move Up and Move Down are Later.
11. **Sketch in tree**: Edit Sketch, Hide or Show, Rename, Delete.
12. Shift+F10 or the Menu key opens the menu for the current selection; arrows and Enter work in it.
13. **Select Other**: shows a short list of all items under the cursor (faces behind faces, edges); hovering a row highlights it, clicking selects it.

## T10. Shortcut bar and gestures [P1]

1. Pressing Q in the viewport (SHORTCUTS.md 6.1) opens the shortcut bar at the cursor with the most used commands for the current mode (part or sketch) and a search box to find any command. Arrows and Enter work in it; Esc closes it. Built; check the search box and keyboard use.
2. Right drag gestures (SHORTCUTS.md 7, built): right drag in one of four directions runs the command assigned to that direction; a guide with the four commands appears after a short drag; releasing inside the guide cancels. A plain right click without dragging still opens the right click menu (T9). Check the guide is shown and that right click menus and gestures do not get in each other's way.

## T12. Keyboard shortcuts (SHORTCUTS.md) [P1]

1. `SHORTCUTS.md` is the owner's list and wins over anything in this file.
2. Every shortcut and every gesture can be changed by the user in Preferences (shortcut editor and gesture editor, built). A changed shortcut takes effect at once, is saved across restarts, and Reset puts back the defaults. Assigning a key that is in use says which command loses it. Every command added for this spec (view selector, hide, isolate, snap options, line to arc switch, relations panel and the rest) must be registered in the command list so it appears in the shortcut editor, the gesture editor and the shortcut bar search, with its default key from SHORTCUTS.md or none.
3. Built today: file and edit keys, view keys (Ctrl+1 to Ctrl+8, N, F, Shift+Z, Ctrl+Shift+Z, Ctrl+R, Shift+W, Shift+Q, Shift+T), F9, F10, F11, Ctrl+Page Up and Down, Q, A, Home, End, Ctrl+F, viewport arrow keys, sketch keys (S, L, Alt+C, R, C, P, D) and feature keys (Shift+E, Shift+C, Shift+R, Ctrl+Shift+R).
4. Missing for commands that exist in Phase 1, to add now:
   - Ctrl+Space: view selector (WORKFLOW_SPEC W7.2). The command itself is missing too: a small cube shaped picker at the cursor with the standard views; clicking a face, edge or corner of it turns the view to match.
   - H: hide or show the selected sketch, plane or body.
   - Ctrl+H: hide all reference geometry (planes, origin, axes) and show it again.
   - F3: snap options (opens the snapping settings of T1.2.8 as a small popup at the cursor).
   - I: isolate the selected body (hide all others until I or Esc).
   - Ctrl+T: flat tree view (features in one list, no nesting).
   - Shift+Tab and Ctrl+Shift+Tab: show the body under the cursor, show all hidden bodies.
5. Keys used inside tools: Esc ends the tool; Enter accepts (feature panels, value box); in Line, the line to arc switch has no default key because A belongs to "Move Confirmation Corner to Cursor". It is listed in the shortcut editor so the user can give it one.
6. Later commands get their SHORTCUTS.md keys when they are built (Trim, Offset, Mirror, Convert, patterns, Fillet, Chamfer, Measure and so on).

## T11. Sketch preferences [P1]

Preferences > Sketch:
1. Turn the view normal to the sketch when opening a sketch (on).
2. Show circle and arc centres (on).
3. Show end points as dots coloured by state (on).
4. Snapping, snap to model geometry, automatic relations (all on).
5. Over defining dimension: ask, or always make reference.
6. On screen value input while drawing (off): when on, drawing a shape shows small value fields for its sizes next to the cursor, and typing a value fixes it with a dimension. [Built: D513]

## T13. Reference planes in the 3D view (owner request, 2026-10-29) [P1]

1. A shown plane (D114) is drawn as a thin outline with a light smoke grey fill that is mostly see through (about 85 to 90 percent transparent), so the part and anything behind it stay readable. No strong colour. Light and dark themes each get a fitting outline and fill colour.
2. The plane's name from the feature tree is drawn as small text just inside one corner of the outline, in the outline colour, with no box behind it. The label follows the plane when the view turns and is never picked.
3. Planes offered for picking (W1, when a sketch or feature asks for a plane) use the same look and labels. The plane under the cursor shows in the accent colour (D111); the others stay smoke grey.
4. A selected plane uses the selection colour for its outline and label; the fill stays light.

## T14. Second research pass: selection, views, tree, errors, inputs [P1]

Written 2026-10-29 from a second reading of the vendor public help, in our own words. Only Phase 1 items from PLAN.md.

### T14.1 Sketch tools
1. Corner Rectangle: works by click click and by press, drag, release. Holding Shift while placing the second corner makes a square (equal sides).
2. 3 Point Arc: first click sets the start, second click sets the end, then moving the mouse sets the bulge (radius) live and a third click places it.
3. Point: selecting a sketch point shows a point panel with its relations (each row highlights its tag when hovered), its status (under, fully or over defined), an Add Relations list that offers only relations valid for a point, and X and Y fields that move the point when no relation fixes it.

### T14.2 Sketch planes
1. A sketch can be started on a default plane, a flat face of the part, or by first picking a sketch tool or a feature command with nothing selected (then the user is asked for a plane, W1).
2. Edit Sketch Plane (tree right click on a sketch): a small panel with one pick box takes a new plane or flat face (from the 3D view or the tree). OK moves the sketch there and rebuilds. Dimensions and relations to model edges that no longer exist become errors, never silent changes.

### T14.3 Selection
1. Select Other (T9.13): the list shows every item under the cursor in depth order, each with a type icon (face, edge, vertex, plane, sketch). Hovering a row highlights it in the view; Tab or the mouse wheel steps through the rows; clicking a row or the view selects. A right click on a face while the list is open hides that face for the moment so the items behind it can be seen; closing the list shows it again.
2. Selection filters: a filter bar (toggle F5 per SHORTCUTS.md if free, else no default) with buttons for vertices, edges, faces, solid bodies, planes, axes, sketches, sketch segments, sketch points and dimensions; Clear All and Select All; a toggle that turns the active filters on or off at once (F6). Keys E, X and V switch the edge, face and vertex filters. With a filter on, only those item types highlight and select, and the cursor shows a small filter mark.
3. Box selection: dragging from left to right selects only items fully inside the box; dragging from right to left also selects items the box crosses. In a part the default items are edges; in a sketch they are sketch entities and dimensions. With Shift the box adds everything inside to the selection; with Ctrl it toggles everything inside. Selections outside the box stay as they were.

### T14.4 Views
1. Normal To: works on a plane, a flat face, a cylindrical or conical face (looks along the axis), or a feature made from one sketch (looks at its sketch). Running it again on the same item turns the view 180 degrees. With Ctrl and two flat faces that are not parallel, the first faces the screen and the second is at the top. With nothing selected it snaps the view to the nearest standard direction; in a sketch it looks at the sketch.
2. View selector (Ctrl+Space, T12.4): a see through cube at the centre of the view. Hovering a face, edge or corner previews that view in a small window, with the standard view name in a corner of the preview. Clicking sets the view. Holding Alt lets the user pick the faces at the back. The cube's back faces are pushed out slightly from the centre so they can be reached without turning the view.
3. View menu and toolbar entries that are Phase 1: Previous View, Zoom to Fit, Zoom to Area, Zoom to Selection (D106), Display Style (Wireframe, Hidden Lines Removed, Shaded with Edges, Shaded), and show or hide toggles for planes, origins, sketches and sketch relations.

### T14.5 Feature tree
1. Rollback bar: dragging it up or down steps the part back or forward through the rebuild order; features below it are greyed. With the bar selected, the up and down arrow keys move it one feature at a time. The user can add or edit features while rolled back; new features go just above the bar. The bar position is saved in the file and restored on open. Right click on a feature or empty tree space offers Roll Forward (one step), Roll to Previous (the last position), Roll to End. A rolled back feature can be deleted with its dependents after a confirm that lists them.
2. Reorder: dragging a feature in the tree highlights the row it will drop under; the cursor shows allowed or not allowed. A move is allowed only when every parent still comes before its children.
3. Errors and warnings: a feature with an error has red text and an error mark, and the part name at the top gets the same mark. A feature with a warning has a warning colour and mark, and its parents show a smaller mark. Clicking a marked feature shows a small box beside it with the message, what to do next and buttons Edit Feature or Edit Sketch. Clicking the part name lists all errors and warnings; clicking a row selects that feature. Warnings still build geometry; errors do not.

### T14.6 Value fields
1. Every number field of a feature panel (depths, angles, offset distance) accepts a value or an expression starting with = that can use global variables and functions (PLAN section 7 parser). The field tooltip says so.
2. A field holding an expression shows a small button at its start that switches between showing the expression and its result. The result cannot be edited; switching back shows the expression for editing.
3. Typing = then a new name in quotes in the value box creates a global variable with that value after a confirm.

### T14.7 Shortcut editor (T12.2)
1. A search box filters the command list as the user types; a category list narrows it (all, each menu, other).
2. Columns: category, command, shortcut(s), search words. Search words are extra words the shortcut bar search will match.
3. Pressing a key that is in use asks; choosing yes moves it to the new command and removes it from the old one.
4. Letters show in upper case. Caps Lock never acts as Shift.
5. Buttons: Remove Shortcut, Reset to Defaults (shortcuts only, or everything), Copy List (plain text of category, command, shortcut to the clipboard).

## T15. Values typed in the work area (owner request, 2026-10-30) [P1]

Written by the manager from the owner's request and FDCAD's own existing behaviour (T4.2.2, T5.2.3). No reference material used.

1. Goal: every length, angle or count a feature or sketch tool asks for can be typed in the view, next to the geometry it changes, the same way a sketch dimension's value is typed (the value box of T4.2.2: expressions, units, `=` formulas, wheel and arrow steps, Enter applies, Escape cancels).
2. Features (3D view). While a feature's property panel is open, each of its main values shows as a value label in the view at a sensible place: on the drag handle where the feature already has one (extrude, revolve, move face, move or copy body, scale, deform, edge flange: unchanged), otherwise at the first picked item (fillet and chamfer: at the middle of the first edge; shell: on the first picked face, or the part's centre when none is picked; draft: at the neutral face; offset face: on the first face; hole: at the first position; rib, dome, thicken, wrap, mounting boss, vent, lip, snap hook and the sheet metal features: at their first pick or sketch). Labels never cover each other: later ones move along until they are clear.
3. Clicking a label opens the value box on it. The panel field and the label are always the same value; changing either updates the other and the preview. Tab and Shift+Tab move the box to the next and previous label of the same feature.
4. Typing a digit, a minus sign, a dot or `=` while the view has focus and a feature panel is open opens the box on the first label (or the one last used) with that character typed, so a value can be entered without touching the mouse.
5. Sketch tools (sketch canvas). Tools with a number field (offset, sketch fillet, sketch chamfer, linear and circular pattern, polygon, slot, move, copy, rotate, scale, stretch, and any other tool whose panel has a length, angle or count) show that value in the canvas as a label next to the cursor or the first picked item, as soon as there is something to preview. Clicking it, or typing a digit as in item 4, opens the value box there. Enter applies the value to the preview and keeps the tool going; a second Enter, or the tool's own finish click, finishes as before. [Slot has no number fields in its panel, so it shows no labels; audit 2026-11-02 D2 item 12.]
6. Drawing tools while drawing: typing a number while a line, rectangle, circle, arc or slot is being drawn opens the value box for its length, size or radius at the cursor; Enter fixes that size and adds the matching dimension, as if Smart Dimension had been used. The direction still follows the cursor.
7. Counts are whole numbers with no unit; angles use degrees by default; lengths use the document unit. Bad input turns the box red with the parser's message and nothing changes.
8. Every change made through a label is the same single undoable command the panel field makes. Nothing new is stored in `.fdef` files.
9. Tests: per feature and per sketch tool, the label appears, a typed value reaches the panel field and the preview, Tab moves on, Escape restores, and typing a digit opens the box.

## T16. More end conditions for Extrude and Revolve (owner request, 2026-10-30) [P1]

Written by the manager from the owner's request and FDCAD's existing Extrude end conditions (T5.1, `extrude_end.py`). No reference material used.

1. Extrude and Extruded Cut, Direction 1 list, in this order: Blind, Through All, Through All Both, Up To Next, Up To Vertex, Up To Face, Offset From Face, Up To Body, Mid Plane. Direction 2 offers the same list less Through All Both and Mid Plane.
   - **Through All Both**: Through All in both directions from the start at once. Direction 2 is then hidden. Stored as `end_condition: "through_all_both"`.
   - **Up To Next**: the feature ends at the first face of the part that the whole profile meets going along the direction. If parts of the profile meet different faces, each part stops at its own first face. If nothing is met, the error says so and suggests Blind or Through All.
   - **Up To Body**: a pick box takes one body; the feature ends where it meets that body (fully into it for a boss, through it for a cut). Stored by topological name.
2. Revolve and Revolved Cut: the Direction 1 group gets an end condition list in this order: Blind (the angle, as today), Through All (a full turn, 360 degrees; the angle field and Direction 2 are hidden), Up To Vertex, Up To Face, Offset From Face (a face pick plus an angle offset), Mid Plane (as today). Direction 2 offers Blind, Up To Vertex, Up To Face and Offset From Face.
   - Up To Vertex: the turn stops at the angle where the profile's plane passes through the picked vertex or sketch point.
   - Up To Face: the turn stops at the picked flat face or plane, which must contain the axis or be crossed by the turning profile; otherwise the error says the face cannot be reached and suggests Up To Vertex or Blind.
   - The existing `direction` values keep working: files with `one_direction`, `mid_plane` and `two_directions` open unchanged and save unchanged. New end conditions are new optional keys (`end_condition`, `end_condition2`, `end_ref`, `end_ref2`, `end_offset`), documented in FDEF_SPEC with a schema 2 compatible reader (old readers ignore unknown optional keys only if FDEF_SPEC says so; otherwise bump within schema 2 rules).
3. Drag handles: Up To and Through All directions have no drag arrow (as Extrude's Through All today). Offset From Face keeps an arrow for the offset.
4. Hole Tool keeps Blind, Through All and Up To Face; add Up To Next and Up To Vertex.
5. Swept Cut and Lofted Cut need no end condition (they follow their path or profiles).
6. Every new choice comes with core tests (volume of a known shape), file round trip tests, panel tests (the field shows and hides correctly) and a regression test that old files rebuild to the same volume.

## Owner test notes (0.1.0-dev, 2026-10-29)

1. Snap sketch points, curves and dimensions to model geometry (T1.2.2).
2. Value box opens beside the dimension being placed (T4.2.2).
3. Dimension panel in the left panel while Smart Dimension is active (T4.2.5, T7).
4. Snap to the origin with a coincident relation (T1.2.1, T1.3).
5. Origin plus point offers Coincident, Horizontal, Vertical (T3.2.3).
6. Right click menus everywhere, for every feature type (T9).
7. Clickable, typeable value beside the drag handle (T5.2.3, T6.3.2).
8. Bug: no snapping to circle and arc centres (T1.2.1).
9. Selected regions for all four sketch features (T5.3).
10. Circle dimensions: diameter alone, distance from centre to other items, centre, nearest or farthest (T4.1, T4.3).
