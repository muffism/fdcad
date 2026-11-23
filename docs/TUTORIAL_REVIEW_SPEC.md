# Tutorial review: missing behaviour (TR1 to TR34)

Written on 2026-11-02 by the manager session after reading public CAD learning material: the vendor's online tutorials (getting started, part lessons, fillets, revolve and sweep, loft, patterns, sheet metal, multibody, equations, design tables, import and export), its saved help pages, and public tips pages. Sources and dates are in the clean room record (kept privately, outside this repository).

Each item below is behaviour that the tutorials use and that FDCAD does not have yet. Everything is in FDCAD's own words and uses FDCAD's names and values. Nothing here is built yet. The owner approved every item on 2026-11-02 (DECISIONS D683); they are PLAN.md Phase 7A. TR22 uses the keys set in D683.

Priority: **High** means a common step in the first lessons, which a new user will miss. **Medium** means it is used in later lessons or saves real time. **Low** means it is nice to have.

## 1. Sketch

### TR1 Move, Copy, Rotate, Scale and Stretch entities [High]

1. Five sketch commands in one group: Move Entities, Copy Entities, Rotate Entities, Scale Entities and Stretch Entities. Each works on sketch entities picked before or after starting.
2. Move and Copy: From and To (pick a base point, then a target point, with the usual snaps), or Delta X and Delta Y fields. Copy leaves the originals and has a number of copies; each copy is one more step away.
3. Rotate: a centre point (picked or typed) and an angle.
4. Scale: a base point, a factor, and Copy with a number of copies.
5. Stretch: pick entities with a crossing box; points inside the box move by the From and To or Delta values, points outside stay, so lines that cross the box get longer or shorter.
6. Keep relations (on by default): relations between moved entities stay. Relations to entities that did not move are removed and named in the status bar. With it off, all relations of the moved entities are removed.
7. The values show in the view as the T15 value labels while the preview follows the cursor. Enter applies the value and keeps the tool going (TOOL_SPEC T15, item 5 already names these tools).
8. Undo puts everything back in one step.

### TR2 Split Entities [Medium]

1. A sketch command: click a line, arc, circle, ellipse or spline to add a split point there. A closed curve needs two points; it then becomes two pieces.
2. The split point is a sketch point that can be dimensioned and dragged along the curve. Deleting it joins the pieces again when nothing else uses it.

### TR3 Copy and paste in a sketch, and pasting a whole sketch [High]

1. In a sketch, Ctrl+C and Ctrl+V copy picked entities with their relations between them and their dimensions. The copy appears at the cursor and follows it until a click places it.
2. In the part, a sketch picked in the tree can be copied and pasted onto a picked plane or flat face. The pasted sketch is a new sketch on that plane, with the same entities and dimensions, placed so its origin is on the new plane's origin. A loft between profiles of the same shape is the common use.
3. Relations to model edges cannot carry over; they are dropped and the status bar says how many.

### TR4 Midpoint Line [Medium]

1. A line tool where the first click is the middle and the second click is one end; the other end mirrors it. The middle point gets a Midpoint relation, so the line stays centred when its length changes.

### TR5 Insert a DXF file into a sketch [Medium]

1. In an open sketch, a command reads lines, arcs, circles, polylines, ellipses and splines from a DXF file into the sketch, at true scale in the file's units.
2. A panel before placing: units (from the file, or chosen), scale, a base point, angle, and layers to include. A preview shows where the geometry lands; dragging moves it.
3. The new entities are under defined and can be dimensioned and moved like any other. A file with nothing usable says so.

### TR6 Intersection curves and silhouette entities [Low]

1. Intersection Curves: pick the part's faces (or the whole body); the curves where the sketch plane cuts them are added as sketch geometry linked to the model, like Convert Entities.
2. Silhouette Entities: the outline of a body as seen square to the sketch plane is added as linked sketch geometry.

### TR7 3D sketch [Owner decision: large]

1. A sketch that is not on one plane: lines, splines and points anywhere in space, used as a sweep path or pipe path. A simpler first step is a 3D sketch made of plane sketches: each part of it is drawn on its own plane inside one sketch, with relations between the planes.
2. Tab switches the working plane among the part's three main planes while drawing; points snap to model vertices and edges.
3. Dimensions are true 3D lengths and angles; relations include Along X, Along Y and Along Z.
4. This is a new sketch kind and needs solver work, so the owner should decide if it is in scope.

### TR8 Shift click a circle for Nearest or Farthest [Low]

1. While placing a Smart Dimension between a circle or arc and another item, holding Shift on the click sets Measure to Nearest (or Farthest, whichever side the cursor is on) without opening the panel (TOOL_SPEC T4.3).

## 2. Part and features

### TR9 Copy and paste features [High]

1. Copy a feature from the tree (for example a cut or a hole) and paste it onto a picked flat face. The paste makes a new feature with the same values and a copy of its sketch on the new face.
2. If the feature's sketch had relations or dimensions to model edges, the paste lists them in a small dialog: keep them (when the same kinds of edges exist on the new face), or remove them.
3. Ctrl and drag of a feature from the tree onto a face does the same as copy and paste.

### TR10 Offset plane by dragging [Low]

1. Ctrl and drag the border of a shown plane makes a new offset plane where the drag ends and opens the Plane panel with the offset distance filled in, so a typed value can replace it.

### TR11 Replace an imported body with a new file [Medium]

1. Right click an imported STEP or mesh body in the tree: Replace From File. The new file takes the old one's place; later features rebuild on it.
2. References that cannot be found on the new body are shown as the usual lost reference errors on those features (the D116 rules), never silently dropped.

### TR12 Sheet metal gusset and normal cut [Medium]

1. Gusset: pick two flat walls joined by a bend; a stiffening rib is pressed into the bend, with depth, width, profile (round or flat) and position along the bend. It flattens as a cut out or is skipped in the flat pattern (a tick box).
2. Normal cut: an extruded cut in a sheet metal part always cuts square to the sheet, so the cut faces stay square when it is folded and flat. On by default for sheet metal; off gives the plain cut.

### TR29 Face fillet with a hold line [Low]

1. Face fillet gets a Method choice: Radius (today) or Hold Line. With Hold Line, the user picks edges on one face set; the round runs so its edge follows those edges, and its size changes along them as the gap needs. A face fully between the hold line and the other set is removed.

### TR30 Sheet metal: small options [Medium]

1. Extruded Cut in a sheet metal part: a Link to thickness tick box sets the Blind depth to the sheet thickness and follows it when the thickness changes.
2. Edge flange position: an Offset choice with a distance moves the flange that far in from the picked edge, with the material inside, outside or bend outside rules applied at the new place.
3. Miter flange: Propagate adds every edge tangent to the picked one, stopping at a cut or a corner that is not tangent.

### TR31 IGES import and healing [Owner decision]

1. Import IGES files as well as STEP. When the surfaces close a volume, they are joined into a solid; when they do not, the import says how many gaps are left and where.
2. A Heal command for imported bodies: tries to close small gaps between faces and lists faces it could not fix, each with Zoom to Selection. Building new surfaces is out of scope (PLAN.md), so a part that will not close stays an error.

### TR32 Named dimensions and showing all dimensions [Medium]

1. A dimension (in a sketch or a feature value) can be given a name in its panel, for example `wall`. Equations and design table columns then show that name instead of the automatic one. Renaming updates every equation and column that uses it (as D527 does for features).
2. Show All Dimensions (part right click): every sketch and feature value of the part shows on the model at once, each can be double clicked to change it. Turning it off goes back to showing only the selected feature's values.

### TR33 Bodies a feature acts on [Medium]

1. In a part with several bodies, Extruded Cut, Revolved Cut, Swept Cut, Lofted Cut and Hole get a Bodies box: All bodies (default, today's behaviour) or Selected bodies, picked in the view or the Solid Bodies folder. Bodies not picked are left as they are.
2. Bosses with Merge result on get the same box, so a boss can join one body and not another it touches.
3. Picked bodies are stored by face reference like other body picks (D233 item 1).

### TR34 Sketch blocks [Low, owner decision]

1. A group of sketch entities saved as one block that can be moved, rotated and placed again as copies; editing the block changes every copy. Used for layout sketches of mechanisms. Not needed for single parts, so the owner should decide.

## 3. View and selection

### TR13 Hidden Lines Visible [High]

1. A display style beside Hidden Lines Removed: edges behind faces are drawn as thin dashed lines in a lighter colour. Shortcut and command list entry like the other styles.

### TR14 Dimetric and trimetric views, and saved views [Medium]

1. Two more standard views: Dimetric and Trimetric, in the view list, the view selector and the command list (no default keys).
2. Save View: the current camera is saved under a name in the part file. Saved views are listed with the standard views and can be renamed, updated and deleted.

### TR15 Perspective [Low]

1. A view toggle between the current parallel view and a perspective view. Zoom, pan and rotate work the same. Measure and dimensions show true values either way.

### TR16 Split the view [Medium]

1. A view command shows one, two (side by side, or one above the other) or four views of the part. Each has its own camera and standard view; the four view layout starts as Front, Top, Right and Isometric.
2. Picking in any view picks the same item in all of them. The active view (last clicked) gets the view commands and keys.

### TR17 Temporary axes [Medium]

1. A view toggle shows a thin axis through every cylindrical and conical face of the part. They can be picked wherever an axis is accepted (pattern axis, revolve axis, plane through an axis), and sketch tools snap to them.

### TR18 Zebra stripes [Low]

1. An evaluate display that draws black and white stripes over the faces, as if a striped room were reflected. Smooth joins show unbroken stripes; a sharp change shows a kink. Stripe count and direction can be set. Display only, not saved.

### TR19 Lasso selection [Low]

1. A selection mode where dragging draws a free loop. Clockwise picks only items inside the loop; counter clockwise also picks items it crosses, matching the box rules (TOOL_SPEC T14.3).

### TR20 Selection breadcrumbs [Low]

1. When an item is picked, a short row at the top left of the view shows its chain: the part, its body, the feature that made it, and that feature's sketch. Clicking a crumb picks that item; right click shows its menu.

### TR21 Per body transparency [Low]

1. Each body row in the Solid Bodies folder and each feature row's display column can make that body see through on its own. Toggle Transparency stays the whole part switch.

## 4. Window, tree and files

### TR22 Ctrl+Tab between open parts [Medium]

1. Ctrl+Tab goes to the next open part tab and Ctrl+Shift+Tab to the previous one, while the 3D view or the tree has focus. Mac: Control+Tab. Shift+Tab and Ctrl+Shift+Tab are taken for bodies (SHORTCUTS.md 3.13 and 3.14), so a new key pair must be chosen in the shortcut editor; the owner decides.

### TR23 Tree folders and comments [Medium]

1. Add to New Folder (tree right click on one or more neighbouring features) puts them in a folder row that can be renamed, opened and closed. Features keep their order; a folder cannot hold features that are not next to each other.
2. Each feature can have a short comment (right click, Comment). A row with a comment shows a small mark; hovering shows the text. Comments are saved in the part file.

### TR24 Save image of the view [Medium]

1. File, Save Image: saves the 3D view as a PNG at the window's size, or at a chosen width and height, with or without the background.

### TR25 Equations to and from a text file [Low]

1. The equations manager can export all variables and equations to a text file, and import them from one. A linked file is read again when the part opens and on a Rebuild, so one file can drive several parts.

### TR26 Measure in two units [Low]

1. The Measure panel can show a second unit beside the first (for example millimetres and inches), set in its options.

### TR27 Compare two bodies [Low]

1. An evaluate command that compares two bodies (two in one part, or the part and a STEP file) and colours the faces that differ, with the volume of each difference.

### TR28 Conic and equation curves [Low]

1. Conic: a sketch curve from two end points, a top point and a shape value (rho) between 0 and 1.
2. Equation curve: x and y as expressions of a parameter t between two values, using the safe expression parser only.

## 5. Already in FDCAD (checked, no change)

The tutorials also used these, and FDCAD already has them: feature first sketching (W2), the view turning to an angle when a feature panel opens, remembered last values in feature panels, rollback bar drag, Edit Sketch Plane, thin extrude, draft on extrude, face fillets with a radius, asymmetric and variable fillets with Set All, tangent propagation, mirror body about a plane, sweep with profile and path, loft with profile order and connection points, offset entities with reverse, sketch fillet keeping constrained corners, linear pattern along a dimension, circular pattern on a cylinder face or round edge, pattern counts edited in the view, equations driving pattern spacing, relation tags with hover names, status bar sketch state, units and cursor coordinates, the shortcut bar, mouse gestures, context toolbars, command search, the view selector, section view, Enter to repeat the last command.
