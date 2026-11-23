# Tutorial review 2: missing behaviour (TR35 on)

Written on 2026-11-02 by the manager session. The first round (TR35 to TR100) read the vendor's online help and what's new pages, university course notes and workbooks, reseller tips pages, and certification practice topics. The second round (TR101 to TR224) read the whole saved vendor help copy section by section, every saved lesson and workbook, what's new summaries for 2010 to 2027, textbook contents and certification outlines, the public documentation of other CAD tools, design for printing lessons, and public user questions. The third and later rounds (TR225 to TR420) read reseller blog archives, course outlines, the help of eight other CAD tool families, open source and code based CAD, manufacturing service design guides, standards scope, the OpenCascade kernel documentation, CAD usability research, hobby and robotics communities, user voted wish lists, open source issue trackers, feature matrices, slicer file formats, printer makers' knowledge bases, platform guidelines and release notes of other tools. Code checks of every item against the phase1 source corrected items that were partly built, and walk throughs of classic exercises against the code found defects in existing features (section 20); a full audit of the user guide and specs against the code is in `docs/AUDIT_2026-11-02.md`. Sources by kind and date are in the clean room record (kept privately, outside this repository). This follows `docs/TUTORIAL_REVIEW_SPEC.md` (TR1 to TR34, approved in D683) and does not repeat it.

Each item below is behaviour that the material uses and that FDCAD does not have yet. Everything is in FDCAD's own words and uses FDCAD's names. Nothing here is built. The owner approved every item, including those marked for an owner decision, on 2026-11-02 (DECISIONS D750); they are PLAN.md Phase 7B, after the audit defects.

Priority: **High** means a common step in lessons and exercises, which a new user will miss. **Medium** means it is used in later lessons or saves real time. **Low** means it is nice to have. **Owner decision** marks an item that changes a locked decision, needs heavy new engine work, or whose value depends on the owner's view of scope.

Where an item says "check what exists", the research could not confirm from the user guide alone whether part of the behaviour is already built. The implementer reads the code first and builds only the difference.

## 0. Summary for the owner

1. 386 items: 33 High, 199 Medium, 154 Low. Sections 1 to 18 hold the items; 19 to 21 are risks, defects and tests in what FDCAD already has; 22 to 24 add detail to existing items; 25 is out of scope; 26 is what FDCAD already has.
2. Read first, because they are defects, not wishes: section 19 (kernel risks; the twisted sweep gives wrong volumes, confirmed by a probe), section 20 (defects found by walk throughs, for example spline paths silently dropped, Hole Tool features not offered as pattern seeds, colours lost in 3MF export, 3MF names not escaped), and `docs/AUDIT_2026-11-02.md` (the user guide and specs against the code; its Read first list leads with topological naming that silently picks the wrong face in hard cases, and a unit change that rescales the model).
3. Owner decisions (20 items): TR55 guide curves, TR78 to TR82 material, mass properties and custom properties (locked by D6 and D29), TR88 display states, TR98 freeze bar, TR112 drag without solving, TR130 replace face, TR131 no tangent propagation (D213), TR163 textures, TR222 custom command tabs, TR223 3D mouse, TR273 goal seek, TR281 several sheet metal bodies, TR312 mouse presets, TR342 limit dimensions, TR362 weak relations, TR375 Mac Redo key (D19).
4. High items: TR35 Fully Define Sketch, TR36 Check Sketch for Feature, TR55 guide curves, TR57 Fill Pattern, TR79 Mass Properties, TR125 repair lost references, TR150 interference and gap check, TR175 to TR178 support free holes, bridging, bed edge chamfer and printable threads, TR182 mesh export options, TR244 machining corner relief, TR253 more screw heads and thread series, TR261 merge faces, TR263 to TR265 Move Face rules, neighbour modes and set a size, TR284 enclosed cavities, TR286 to TR288 model health, change test and error cause, TR292 status without colour alone, TR295 to TR297 manufacturing checks, TR337 signed distances, TR375 to TR378 Mac Redo, Mac menus, file drop and Windows contrast themes, TR381 and TR382 slicer ready 3MF and body roles.
5. Many Medium items are small options on existing tools; sections 22 to 24 list details that belong with items already written, so an approved item should be read with its additions.

## 1. Sketch

### TR35 Fully Define Sketch [High]

1. A sketch command that adds relations and dimensions until the sketch is fully defined, so the user does not place each one by hand.
2. A panel with: the entities to use (the whole sketch or the picked ones), a tick box for relations, a tick box for dimensions, a dimension scheme (Chain: each distance to the next item; Baseline: every distance from one datum; Datum Pairs: horizontal and vertical distances from a datum point), and a datum picker for the horizontal and vertical datums (default: the sketch origin).
3. Calculate shows a list of what would be added. Apply adds them. Nothing in the geometry moves: new dimensions take the current sizes.
4. Entities that are already defined are skipped. A sketch with a conflict says so and does nothing.
5. One undo step removes everything the command added.

### TR36 Check Sketch for Feature [High]

1. A sketch command that answers "will this sketch work for this feature?". The user picks a feature kind (Boss, Cut, Revolve, Sweep profile, Sweep path, Loft profile, Rib, Wrap, Flange) in a list.
2. It reports the problems that kind cannot accept: open contours with the gap size, overlapping or duplicate entities, three or more curves meeting at a point, end points that nearly meet but do not (a near miss below a small tolerance), and a single open contour where the kind needs closed ones (or the reverse). Crossing curves are not an error (D116 item 1) and are not reported. Construction geometry is ignored.
3. Each result row has a Zoom to Problem button that frames and highlights the spot. A clean sketch says "No problems found for this feature".
4. The checks already exist in the sketch topology code and run when a feature uses the sketch (PLAN.md section 5A item 9), but nothing in the UI shows them before that. This command exposes them, and names the checks the same way as the feature errors do.
5. The feature kinds accept these contour kinds: one open contour (rib, sweep path, thin features), one closed contour (sweep profile, loft profile), several separate closed contours (boss, cut, revolve), or any mix (wrap, split).
6. A preference, Use Only Fully Defined Sketches, makes features refuse an under defined sketch with a message naming the sketch. Off by default.

### TR37 Repair Sketch [Medium]

1. A sketch command that lists small faults: gaps between end points smaller than a tolerance, overlapping segments, tiny segments, duplicate points, zero length lines, zero radius arcs, and relations that point at the wrong kind of entity. The tolerance can be typed.
2. Each fault has a Fix button and the list has Fix All. A fix joins the points, merges the overlap, or removes the tiny segment. Fixes are offered, never silent (CLAUDE.md section 5 item 12).
3. A fix shows the amount it moves points by. Undo puts everything back in one step.
4. Common use: a sketch brought in from a DXF file (TR5) that does not close.

### TR38 Sketch problem list [Medium]

1. Today a sketch status is Under, Fully or Over defined. A relation or dimension that points at a deleted item only raises a solver error, and the sketch shows as over defined. Add two statuses: Dangling (a relation or dimension to a deleted item, shown in a warning colour) and No Solution. Also Invalid for geometry, for example a line of zero length or a spline that crosses itself.
2. A list opens from the status bar. It names each problem item, with Zoom to Item. For dangling items, buttons: Pick New Item, Delete, and Repair All Dangling, which offers a replacement for each one where a single clear match exists (the user confirms each). Hovering a dangling item draws a faint image of the item it lost.
3. The relations panel already filters conflicting items and the over define prompt offers Make Reference or Keep Driving. Add: the list separates Redundant (harmless, the sketch still solves) from Conflicting, groups each conflict set, and offers Diagnose, which steps through the possible ways out (delete or make reference one item of the set) with a preview of what would move. Most conflicts in practice come from a duplicate dimension, so a duplicate dimension is offered first as "make it a reference dimension".
4. Clicking a list row selects the items involved. A button selects all under defined items.

### TR39 Select regions and chains in a sketch [Medium]

1. Clicking inside a closed region of a sketch with no tool active shades it and selects every entity of its border. Dragging from there moves the whole shape with the solver keeping the relations.
2. A small gap in a border shows the region unshaded, so the user can see which contours are not closed.
3. Select Chain already exists in the right click menu. Add: Ctrl and Select Chain adds another chain to the selection.
4. A shaded region can be used as input to Mirror, Offset and Move Entities, and Alt and click on one starts Extruded Boss with that region chosen.
5. Hovering a contour that cannot be picked for the active feature shows a tooltip with the reason (for example "this contour is open").

### TR40 Merge relation [Medium]

1. A relation that joins two separate sketch points into one point. Both points keep their other relations. After the merge the point is one item that can be dragged and dimensioned.
2. Available when two points are picked (end points, centres or free points). Different from Coincident, which keeps two points that sit together.

### TR41 Relations on ellipses and splines [Medium]

1. Today a point can be Coincident with an ellipse or partial ellipse, and Tangent works for lines, circles and arcs only. Ellipses get Tangent (to a line, arc or other ellipse), Concentric, Equal (same axes) and Midpoint of a partial ellipse, through the solver's ellipse entity.
2. Splines are not solver entities today: their through points and handle ends are ordinary points, so only point relations work. Tangent between a spline end and a line or arc can be made from the end handle direction (a relation between the handle point and the line). Equal Curvature at a spline end needs a design choice by the implementer, recorded in DECISIONS.md.
3. Already built: the relation list offers only relations that apply to the pick.

### TR42 Spline edit tools [Medium]

1. Insert Spline Point: click a spline to add a through point at the click. The curve keeps its shape until the point is dragged.
2. Fit Spline: pick a connected chain of lines and arcs (or other splines) and replace it with one spline. A Tolerance field sets how far the spline may differ. The originals are removed or kept as construction (a tick box).
3. Simplify Spline: reduces the point count while the curve stays within a typed tolerance. The result and the number of points left are shown before OK.

### TR43 Spline handles [Medium]

1. Each through point of a spline can show a tangent handle. Dragging it changes the tangent direction and the handle length. Pinning a handle keeps it fixed while other points move.
2. The handle angle and length can be dimensioned and used in relations (for example Tangent to a line).
3. A Reset Handle command removes the pin from the picked point.

### TR44 Spline analysis aids [Low]

1. Next to the curvature combs, a spline can show its control polygon, its inflection points as small marks, and the point of smallest radius with the radius value.
2. All are display only and are not saved.

### TR45 Baseline, ordinate, chamfer and path length dimensions [Medium]

1. Baseline Dimension: pick a base item, then each item to measure from it. The distances stack, each row one step further out.
2. Ordinate Dimension: pick a zero point, then points. Each shows its distance along one axis from the zero point as a short leader and a number. The group moves together.
3. Chamfer Dimension: pick a chamfer line and then either a length and an angle, or two lengths.
4. Path Length Dimension: pick a connected chain of curves. The driving value is the total length of the chain, which can be used in equations and solved for.
5. All four are driving by default and can be made reference like other dimensions.

### TR46 Dimension tolerance and display [Low]

1. A dimension has optional display settings: tolerance kind (none, bilateral, limit, symmetric), the plus and minus values, and the number of decimals.
2. A circle dimension can show as radius, diameter or a linear diameter. An angle dimension can show the inner angle or its supplement.
3. Text can have a prefix and suffix. Arrow placement can be inside or outside.
4. These affect display only. The solver always uses the nominal value.

### TR47 Trim: keep the pieces as construction [Low]

1. Trim has a tick box, Keep Trimmed Pieces as Construction. The cut away part stays in the sketch as construction geometry, so the sketch stays defined.
2. In the drag trim mode, dragging back over the trimmed place undoes that trim.

### TR48 Sketch fillet and chamfer on more curves [Medium]

1. Sketch Fillet and Sketch Chamfer work on two lines only today. Extend them to arcs and splines in any pairing (line and arc, arc and arc, line and spline).
2. If the pair cannot take the size, the status bar says what failed and what to try (smaller radius, longer pieces), as the line case does today.
3. Dragging the preview arc sizes the fillet. Several fillets made in one run with the same radius get one dimension and Equal relations, not one dimension each.

### TR49 Derived sketch [Medium]

1. A command that makes a linked copy of a picked sketch on another plane or flat face. The copy cannot change shape; it follows the original when the original changes.
2. The copy can be moved and rotated as a whole by dragging or by typed values. Relations to the original cannot be added.
3. A Break Link command makes the copy a normal sketch.

### TR50 Move, rotate and scale a whole sketch [Low]

1. Move, Rotate and Scale Entities already work on picked entities (TR1). Add Modify Sketch: one command that acts on the whole sketch with no picking, with a base point and typed or dragged values. Dimensions scale with a scale factor.
2. Flip the whole sketch about its X axis, Y axis or both.
3. One undo step.

### TR51 Sketch from a picked edge [Low]

1. With an edge or curve picked, a new sketch can start on a plane square to it at the end nearest the click. Reference Geometry Plane (Normal to curve) is the manual way; this saves a step.

### TR52 Parabola and Jog Line [Low]

1. Parabola: click a focus, then the apex, then the two ends. The curve is a sketch curve with a focus, an apex and handles.
2. Jog Line: click a line, then a point to place the step. The line breaks into two parallel pieces joined by a short line, with a width and depth that can be dimensioned.

### TR53 Sketch drag keys [Low]

1. Ctrl already turns snapping off while drawing. Add: Shift while dragging an under defined item moves it as a rigid piece with no new relations (today Shift adds to the selection, so the key must be chosen in the shortcut editor), and dragging any item of a box selected group moves the whole group.

### TR54 Text linked to a value [Low]

1. Sketch Text can include a value of the part: a global variable, a dimension, or a custom property (TR82), typed as a field in the text. The text updates when the value changes.

## 2. Part and features

### TR55 Guide curves for Sweep and Loft [High, owner decision]

1. Swept Boss and Cut get a Guide Curves list of one or two sketch or edge chains. The section is scaled and shaped to stay on the guides along the path. A guide must touch the profile.
2. Lofted Boss and Cut get a Guide Curves list with any number of guides. Each guide must touch every profile. The sides of the loft follow the guides.
3. Loft also gets Centerline: pick one curve. The middle sections are kept square to it, with a Number of Sections field.
4. Errors say which guide missed which profile and what to do.
5. Owner decision: D219 and D220 left guide curves out because the kernel is unreliable for them. The owner decides if the risk is acceptable. If yes, the implementer should first test the kernel on a set of sample guide cases and report back.

### TR56 Sweep tangency and merge options [Medium]

1. Start and End Tangency: None, Path Tangent, or Tangent to Adjacent Faces, so the sweep blends into the faces it starts on or ends on.
2. Merge Tangent Faces: when the path is smooth, the swept side faces join into one face where possible. Not built today (the existing Merge result joins bodies, not faces).
3. Twist can also be set as a number of turns, besides an angle. On a closed path the twist must be whole turns.
4. Orientation gets a third choice that follows the path's curvature (good for helices), besides Follow Path and Keep Normal Constant.

### TR57 Fill Pattern [High]

1. A pattern that fills a flat face or a closed sketch region with copies of a seed feature or of a simple cut shape (circle, square, diamond or polygon with a size and rotation).
2. Layouts: Grid, Staggered Grid (with a stagger angle), and Rings (circular, square or polygon rings). Inputs: spacing (one or two directions), margin from the border, direction and start point.
3. Validate Count drops copies that do not fit on the material. The number of copies shows in the panel and can be used in an equation.
4. Instances to skip are picked in the view or typed, like other patterns.
5. Common uses: grilles, vents and weight reduction holes.

### TR58 Table Driven Pattern [Medium]

1. A pattern from a table of X and Y positions measured from a picked origin and a reference point. The table can be typed in the panel, pasted from a spreadsheet, or read from a text file. Save and load of the table is offered.
2. Rows can be skipped with a tick box. A seed feature or face set is picked as in other patterns.

### TR59 Varying pattern instances [Medium]

1. Linear and Circular Pattern get a Vary option: spacing grows by an increment from copy to copy, and chosen dimensions of the seed feature grow by their own increments.
2. Already built: skipped instances keep their numbers.
3. Clicking an instance marker in the view overrides the values of that one instance. A negative increment reverses the direction.
4. A second option, Vary Sketch, lets copies re-solve their sketch relations against the faces and edges they land on, so a cut that follows a sloping edge stays attached. Low priority part of this item.

### TR60 Split Line [Medium]

1. A command that divides a face into regions without changing the volume. Three methods: Projection (a sketch projected onto the faces), Silhouette (the outline of the body along a pull direction), and Intersection (where a plane or another body meets the faces).
2. The new edges can be used to colour one region, to pick a region for Draft or Move Face, or as the edge for a Fillet.
3. Rebuilds follow the usual naming rules (PLAN.md section 6). Deleting the feature joins the faces again.

### TR61 Curve through points [Medium]

1. Curve Through XYZ Points: a table of X, Y and Z values typed in the panel, or read from a text file with three columns. A Reload button reads the file again. A coordinate system can be picked. Tick Closed to join the ends.
2. Curve Through Reference Points: pick vertices, sketch points or reference points in order. Tick Closed to join the ends.
3. The result is a curve feature that sweeps, lofts and pipes can use as a path.

### TR62 Fillet methods and profiles [Medium]

1. Constant Size fillets get a Method choice: Radius (today), Asymmetric (two distances, with Reverse) and Chord Width.
2. Profile choice: Circular (today), Conic with a shape value between 0 and 1 (or a conic radius), and Curvature Continuous, which blends with no jump in curvature at the two ends. Asymmetric also allows an elliptic profile.
3. Errors name the edges that cannot take the profile, as the existing fillet errors do.

### TR63 Setback fillet at corners [Medium]

1. When three filleted edges meet at a vertex, a Setback group lets the user pick the vertex and type a setback distance for each of the three edges (Set All, Set Unassigned). The corner blends smoothly instead of ending in a flat patch.

### TR64 Small fillet and chamfer options [Low]

1. Keep Features: a large fillet does not swallow bosses and cuts it passes over, it rounds around them.
2. Round Corners: at a joint of three rounded edges, the corner gets a smooth blend.
3. Overflow: for rounds that run past another edge, choose Keep Edge or Keep Surface.
4. Select Through Faces: pick hidden edges through the faces in front.
5. Partial Edges for Chamfer, like the fillet option that already exists (start and end by Distance or Percent), and for both: the end set by a picked vertex or reference.
6. Omit Attach Edges: when a whole feature is picked, the edges where it joins the earlier body are left sharp.

### TR65 Thin feature auto fillet [Medium]

1. A thin Extrude, Revolve or Sweep from an open sketch gets Auto Fillet Corners with an inside radius. The outside radius is that radius plus the wall. A tube or bracket can be made from one open sketch.

### TR66 Hole Tool size carry over setting [Low]

1. Already built: Hole Tool favourites (save, apply, update, delete, export, import) and size carry over by name when the hole type changes.
2. Missing: a setting to turn the carry over off, so each hole type remembers its own last size.

### TR67 More Deform modes [Medium]

1. Deform Point: pick a point and a direction on a face, edge or vertex. Inputs: distance, radius of influence and stiffness. Faces and edges can be kept fixed.
2. Deform Curve to Curve: an initial curve and a target curve; the body follows. Match: None or Tangent. Fixed faces and edges as above.
3. Surface Push is Low: a tool shape (sphere, ellipsoid, rectangle, or a picked body) pushes into a face.
4. These use the same checks as the other deform tools (docs/user_guide/deform.md, tolerance and approximate warning).

### TR68 Indent [Low]

1. A command that reshapes a target body around a tool body. Inputs: Thickness and Clearance, Keep or Remove the picked side, and a Cut mode. Used for pockets that follow an inserted part.

### TR69 Bounding Box [Medium]

1. A feature that makes a rectangular or cylindrical bounding body, oriented by best fit, by a picked plane or by a coordinate system. It reports length, width, height and volume, which equations can read (for example for stock size). Directions can be locked to the axes.
2. The box is a reference shape. It is shown as a thin outline and is not a solid body unless the user ticks Make Solid.

### TR70 Select bodies by size [Low]

1. A command that selects bodies smaller or larger than a size limit set with a slider (percent of the largest body). Delete or Keep follow in one step. Used after imports and splits.

### TR71 Insert Part [Medium]

1. Bring the bodies, sketches and planes of another FDCAD part into this part as one feature. A list chooses what to transfer. A position can be typed or picked.
2. Optional link: the inserted items update when the source file changes. Break Link makes them normal. A missing source file is an error that says where it looked.

### TR72 Library features [Medium]

1. Save the picked features to a file as a library feature. Insert it on any plane or face from a panel: it asks for the faces the saved feature was attached to, then makes the features again at the new place. Internal dimensions are hidden. Placement dimensions can be edited after insertion.
2. TR9 (feature copy and paste) is built and is the in session form of this item. Only the library file form is new.
3. Options at insert: keep a link to the library file (the features update when it changes), or dissolve it into normal features. A library feature cannot hold booleans between bodies.

### TR73 Mirror Part to a new file [Low]

1. File menu: Mirror Part makes a new part that is the opposite hand of the open one, saved to a new file. The original is not changed.

### TR74 More plane methods [Low]

1. Tangent to a Curved Face: a cylinder or cone face, and a reference plane or point to set which tangent plane.
2. Through a Line and a Point: pick an edge or sketch line and a point.

### TR75 Rib and wrap small options [Low]

1. Rib with draft: choose where the thickness applies: on the sketch plane, or where the rib meets the wall. Next Reference changes which side the draft starts from.
2. Wrap: Pull Direction (a line, edge or plane) so the emboss or deboss walls do not have to be square to the sketch plane.
3. Single line fonts for scribe wrap and for sketch text, so engraving and pen plotting follow one stroke instead of an outline. Today text uses system outline fonts only. FDCAD would ship one single line font of its own or under a GPL compatible licence (recorded in DECISIONS.md).

### TR76 Sheet metal: flat pattern options [Medium]

1. No Bends: rolls the sheet metal part back to its flat shape so cuts can be made on the flat. The cuts become features after the bends and fold with the part.
2. Flat pattern options: Merge Faces, Simplify Bends, a Corner Trim for the flat corners, and a list of faces to leave out of the flat.
3. Base Flange can start from a picked face or offset from a plane.
4. The existing Flatten and Export Flat Pattern keep working unchanged.

### TR77 Sheet metal stamp [Low]

1. Stamp: a closed sketch is pressed into the sheet with Depth, Draft, Punch Radius, Die Radius and Corner Radius. The thickness stays constant. It appears in the flat pattern as the outline of the stamp.

## 3. Evaluate and part information

### TR78 Part material [Medium, owner decision]

1. Each part can have a material from a library: a name, a density, and optionally a colour. Materials the user adds are saved in Preferences. Imperial and metric density units both show.
2. The material is stored in the part file and shows in the feature tree. Print Estimate uses it as its default, and Mass Properties (TR79) uses it.
3. Owner decision: D29 limits materials to Print Estimate. This item widens that.

### TR79 Mass Properties [High, owner decision]

1. An Evaluate command shows, for the whole part or picked bodies: mass, volume, surface area, centre of mass, principal axes, and the moments of inertia about the centre of mass or a chosen coordinate system.
2. A Copy button copies the values. Units follow the part. A tick box includes hidden bodies. Mass uses the part material (TR78) or a typed density.
3. Why: nearly every course and every certification practice set ends by reading the mass of a finished part. The kernel computes all of these values.
4. Owner decision: D6 and D29 keep full mass properties out of scope. This item needs a change to those locked decisions.

### TR80 Centre of mass and mass overrides [Low, owner decision]

1. A reference point at the centre of mass that follows the model, with a show and hide toggle in the view.
2. Override Mass Properties: type a mass, centre of mass and inertia for an imported or simplified body. The override shows with a mark.
3. Needs TR79.

### TR81 Section properties [Low, owner decision]

1. For a picked flat face or closed sketch: area, centroid, moments of area and principal axes. Needs TR79.

### TR82 Custom properties [Medium, owner decision]

1. A panel of named rows per part: text, number, date and yes or no. Typical rows: description, part number, material, revision. A value can be an equation or a measured value such as mass or volume.
2. Rows are saved in the part file, can be set per configuration, and can be used in equations and sketch text (TR54). Export formats that can carry them (3MF, STEP) include them.
3. Owner decision: needs a file format key (FDEF_SPEC.md). The main users of these values, parts lists and drawings, are out of scope.

### TR83 Undercut analysis [Medium]

1. An Evaluate command for moulded parts. The user picks a pull direction (and can rotate it live). Faces are coloured by whether they can be seen from that direction: Visible from Above, Visible from Below, Hidden from Both (an undercut), Straddle (partly visible) and Not Visible.
2. The count of faces in each class shows in the panel. Different from Draft Analysis, which tests the angle of faces. Zoom to Face works for each class.
3. Display only.

### TR84 Parting Line [Medium]

1. Using a pull direction, the command finds the edge chain where faces change from positive to negative draft and adds it as a curve feature. A tick box splits straddle faces at the line (using TR60).
2. A closed loop is reported as closed; a broken one lists the gaps.

### TR85 Mould Cavity [Low]

1. A command to make the negative of a part in a block: pick the block and the part, a Scale about the Centroid, the Origin or a coordinate system, uniform or per axis (for shrinkage), and the cavity is subtracted from the block.
2. A simple Tooling Split with a flat parting plane may follow. Surface based mould tools are out of scope.

### TR86 Sensors [Low]

1. A Sensor row in the tree watches a value (a dimension, an equation, volume, mass) and shows a warning mark on the row when the value goes outside a limit that the user typed. The mark's hover text names the value and the limit.

### TR87 More geometry check classes [Low]

1. Geometry Check also reports a smallest curvature radius under a typed limit, edges with gaps, knife edges, and edges where faces do not join smoothly but should.
2. Wall Thickness Analysis gets a typed target thickness, and a hover reading of the thickness at the cursor.
3. A Symmetry Check tells if the part is the same on both sides of a picked plane, and which faces differ.

### TR88 Display states [Low, owner decision]

1. Named display states store which bodies are shown and their colours and transparency. Configurations can link to one. The owner decides if this is worth a file format key.

## 4. Equations and configurations

### TR89 More expression functions [Low]

1. Already built: `if`, `and`, `or`, `not` and the comparisons. Add `exp`, `ln`, `log10`, `sign`, `trunc` and `mod` to the safe expression parser.
2. Document in typing-values.md that `if` and the comparisons exist, that `-3^2` means `-(3^2)`, and that `==` on two computed lengths can fail by rounding, so a tolerance test such as `abs(a - b) < 0.001` is safer.

### TR90 Design table extras [Low]

1. Optional columns for a configuration description, a configuration colour and (with TR82) custom properties. A configuration can be made from a parent configuration, so it starts with the parent's values.
2. Add Parameters to Table: one button adds columns for the picked variables and equations.

### TR91 Deleting a feature and its equations [Low]

1. Deleting a feature or sketch lists the equations and variables that only it used and offers to delete them too. Nothing is deleted without the user's click.

## 5. Selection, tree and files

### TR92 Select Loop and Select Tangent [Medium]

1. Right click an edge or face: Select Loop picks the edges around one face, with a handle to flip to the next face. Select Partial Loop: pick the first edge, then right click the last. Select Tangent picks every face or edge that joins the picked one smoothly.
2. While a face is picked, Ctrl and click an inner edge of it switches to the inner loop.
3. Fillet, Chamfer, Offset and Convert use the selection as it stands.

### TR93 Select Previous and Invert [Low]

1. Select Previous restores the selection before it was cleared. Invert Selection picks the items that are not picked, within the current selection filter.

### TR94 Selection sets [Low]

1. A group of picked items can be saved under a name and picked again later. A pick by property selects all faces of one colour, all edges over a length, or all faces of one feature.

### TR95 Tree filter box [Medium]

1. A box above the feature tree: typing a name shows only the rows that match, with their parents. Clearing it shows the full tree. Optional: filter by state (errors, suppressed, comments from TR23).

### TR96 Parent and child arrows [Low]

1. Hovering or picking a feature draws arrows in the tree to its parents and children (two different colours). A parent inside a closed folder points at the folder. Off by default; turned on from the part row's right click menu.
2. Check the Parents and Children dialog: the user guide names it in the tree menu, but the code check did not find the menu entry. A dependency helper exists in the core. If the dialog is missing, add it: it lists both, and double click walks to the next parent or child.

### TR97 Save a Copy [Medium]

1. File, Save a Copy: saves the open part to a new file and keeps the open one as it is. Save a Copy and Open also opens the new file in a new tab. Neither changes the open file's name.

### TR98 Freeze bar [Low, owner decision]

1. A second bar beside the rollback bar. Features above it are not rebuilt and cannot be edited until it is moved. It saves rebuild time on large parts. FDCAD's background rebuild may make it unnecessary, so the owner decides.

### TR99 Isolate display choices [Low]

1. Isolate gets a choice for the other bodies: Hidden (today), Transparent or Wireframe. The panel returns the bodies to normal when closed.

### TR100 Up direction for new parts [Low]

1. New Part and Preferences get a Y Up or Z Up choice (default Z Up). It only sets which plane is Front and which view the standard orientation faces. Geometry is not rotated.

## 6. Sketch, second round (TR101 to TR124)

### TR101 Pierce relation [Medium]

1. A relation linking a sketch point to a curve, edge or helix that crosses the sketch plane: the point stays where the curve passes through the plane, and follows it when the curve changes.
2. Needed to place a sweep profile exactly on a path or guide (TR55), and a spring profile on a helix start. The lessons use it often.
3. Related: curve features cannot be clicked in the 3D view while sketching today (curves.md). Picking a curve feature for this relation must work.

### TR102 Snap to grid, length steps and angle steps [Medium]

1. A grid spacing (major and minor) per part, and Snap to Grid that works when the grid is shown or always (a choice).
2. Length snap: while drawing, the length steps in a set increment when a key is held. Angle snap: the angle steps in a set increment (a preference).
3. A snap filter on the right click menu limits the next click to one snap kind (end point, midpoint, centre, tangent, nearest).
4. The grid is shown today but nothing snaps to it.

### TR103 Segment a curve [Medium]

1. Pick a line, arc, circle, ellipse or spline and a count. The curve is split into that many equal pieces, or gets that many equally spaced points on it, with relations that keep them equal when the curve changes. The count can be edited later.

### TR104 Replace Entity [Medium]

1. Pick a sketch entity and a new entity. Relations and dimensions of the old one move to the new one where they make sense, features that used edges made from the old one keep working, and the old one is deleted or turned into construction. Items that cannot move are listed.

### TR105 Corner point at rounded corners [Medium]

1. Sketch Fillet and Chamfer already accept a corner point pick. What is missing is a point that stays at the corner where two entities would meet if extended, after the fillet or chamfer is made. Dimensions and relations to it keep working when the fillet or chamfer is added or changed.
2. Made automatically when Sketch Fillet or Sketch Chamfer removes a corner that had dimensions, so those dimensions survive. Shown as a small mark.

### TR106 Close Sketch to Model [Low]

1. An open sketch profile whose ends sit on model edges can be closed by those edges. A prompt shows the two possible closed shapes and the user picks one side.

### TR107 Sketch pattern options [Medium]

1. Already built: skip by clicking an instance mark, Fix Direction, the angle between the two directions, and a direction from a sketch line.
2. Missing: an instance count shown in the sketch that can be edited there, a direction taken from a model edge, and for circular sketch patterns the radius and arc angle as values.

### TR108 Relation groups and equal length of any curves [Medium]

1. Equal already takes two or more entities but is stored as a chain of pairs. One Parallel, Equal, Collinear or Equal Radius relation joins many entities at once, shown by one numbered tag.
2. Equal rejects mixed kinds today (lines only, or circles and arcs only). Equal Length works between any two curves: line, arc, ellipse arc and spline (same curve length).

### TR109 Turn a relation or dimension off [Medium]

1. A relation or dimension can be switched off without deleting it. It is drawn greyed out and has no effect until switched on again. Used to try another arrangement.
2. With configurations, a relation or dimension can be off in some configurations only.

### TR110 Dimension preview on selection [Medium]

1. Smart Dimension already previews while placing. New: with one or two entities picked and no tool active, a faint dimension is shown that a click places, and the value box opens. For several entities, a small choice of the likely dimensions (distance, angle, diameter) is shown.

### TR111 Dimension placement details [Low]

1. While placing, right click locks the dimension type (horizontal, vertical, aligned) so the cursor position no longer changes it.
2. Angle to an imaginary horizontal or vertical line through a line end. Symmetric angle about a centerline (half or full angle).
3. Per arc end of a distance: Minimum, Centre or Maximum. Two points on the same arc. Flip the arrows. Hide the dimension or extension line.
4. A zero or negative value reverses the direction instead of failing.
5. Set many dimensions to reference at once, and a Driven drawing mode where new dimensions are reference.

### TR112 Drag without solving [Low, owner decision]

1. A drag mode that moves entities without solving, then asks whether to delete the relations that no longer hold.
2. A preference where dragging a dimensioned entity rewrites its driving dimensions to the new value. This conflicts with TOOL_SPEC T2 (drag never changes a dimension), so the owner decides.
3. Detach Segment on Drag: dragging one end of a segment away from the ends it shares, breaking the join.

### TR113 Cut away the model in front of the sketch plane [Medium]

1. A tick per sketch, and a key, hides the part of the model in front of the sketch plane while sketching, so a sketch inside a part can be seen. Display only.

### TR114 Rectangle and polygon extras [Low]

1. Rectangle tools: add construction centrelines from corner to corner or from midpoint to midpoint, rounded corners with a radius, and an inner offset frame, in the same tool.
2. A polygon can be edited later (sides, inscribed or circumscribed, size, angle); today these are set only when drawing. A triangle preset.
3. Ellipse gets construction axes made automatically.

### TR115 Line, arc and spline small options [Low]

1. Infinite construction line, trimmed later.
2. Flip the tangent direction of a tangent arc at a junction.
3. A buffer around the last clicked point so quick click drawing does not make tiny segments.
4. Splines: raise or lower the degree, weight of a control point as a value, convert any line or arc chain to a spline, a spline length dimension, Relax Spline (smooth with fixed ends).

### TR116 Sketch picture extras [Low]

1. One transparency level exists. Add transparency from the image file's own alpha, or a picked colour made see through.
2. Trace: pick a region by colour or a box and get sketch curves of its outline, which the user can edit.

### TR117 Insert SVG into a sketch [Medium]

1. Like Insert DXF (TR5): read paths, lines, arcs, circles and curves from an SVG file into an open sketch, with scale, a base point, angle and a preview. Curves become splines or arcs. A logo is the common use.

### TR118 Convert Entities extras [Low]

1. Picking a face converts its outer loop and all inner loops at once, with a tick to leave the inner loops out. Ctrl and click a loop edge after picking a face takes only that loop.

### TR119 Keep proportions on the first dimension [Low]

1. A preference: the first dimension added to a sketch of unsized geometry scales the whole sketch to match, so the shape keeps its proportions.

### TR120 Leaving a sketch [Low]

1. Exit the sketch by double clicking empty space (a preference). Exit without saving (discard the changes made since the sketch was opened, after a prompt). Esc with no tool active leaves the sketch (a preference, off by default).

### TR121 Text extras [Low]

1. Explode text into sketch curves that can be edited.
2. Bold and italic exist for a whole text. Add bold, italic and rotation per character.
3. A number in a text that counts up across the instances of a pattern (each copy shows its own number).

### TR122 Merge sketches and linked copies [Low]

1. Merge two sketches on the same plane into one.
2. Copy Entities with a Linked tick: the copy's dimensions follow the original's by formula.

### TR123 Sketch on hover with a tool active [Low]

1. With a sketch tool chosen and no sketch open, hovering a flat face or plane shows it as the target, and the first click opens a sketch on it and starts drawing.

### TR124 Swap axis relations [Low]

1. One command turns Horizontal and Vertical relations of a picked shape into Parallel and Perpendicular, so the shape can be rotated and stay square.

## 7. Part and features, second round (TR125 to TR164)

### TR125 Repair lost references [High]

1. A feature with lost references shows them in its panel in a warning colour, each with Remove and Pick Again, plus Clear All Missing.
2. While picking again, the lost face or edge is drawn faintly where it was, so the user can see what to pick.
3. Repair All for one feature, and for the part: for each lost reference with one clear match, the match is offered, and the user confirms each or all (CLAUDE.md section 5 item 12).
4. Lost fillet and chamfer edges and broken pattern seeds are the common cases.

### TR126 Esc stops a rebuild or a long calculation [Medium]

1. Esc stops a running rebuild, a slow fillet, chamfer or pattern preview, after a short confirm. The model shows the last finished state, and the rollback bar stays after the last built feature. Today a new edit cancels a rebuild and slow work has a Cancel button, but Esc only closes the panel.

### TR127 Primitive solids [Medium]

1. Add or cut a box, cylinder, sphere, cone, torus, wedge, prism or tube by typed size, placed on a plane, face or coordinate system, with no sketch. Each is a feature with editable values and Merge result.

### TR128 Combine options [Medium]

1. Keep Tools: a tick on Combine Add, Subtract and Common that keeps the tool bodies.
2. Exclusive: keeps only the volume that is inside an odd number of the picked bodies.
3. Keep Largest: after a Subtract or Split gives many pieces, keep only the largest.
4. Clearance: Subtract leaves a gap of a typed size between tool and target, on all faces or picked ones. Useful for print fits.

### TR129 Offset Body [Medium]

1. Grow or shrink every face of a body by a distance, as one feature. Corner join Rounded or Sharp. Offset Face (one or more faces) already exists.
2. Shell gets the same Rounded or Sharp choice for outside corners.

### TR130 Replace Face [Medium, owner decision]

1. Pick faces and a target face or plane. The picked faces are removed and the body is extended or trimmed to the target. Common use: flatten a bumpy imported face onto a plane.
2. With a plane or flat face as target this is solid work. With a curved target it is close to surface tools, so the owner decides the extent.

### TR131 Fillet and chamfer without tangent propagation [Medium, owner decision]

1. A Tangent Propagation tick on Fillet and Chamfer, on by default. Off, only the picked edge is rounded, not the edges joined smoothly to it.
2. D213 left this out for kernel reasons (the round must stop at a smooth join). The lessons use it with variable fillets. The owner decides after the implementer tests the kernel.

### TR132 Change existing fillets and drafts [Medium]

1. Change one edge of a multi edge fillet (its radius, or remove it from the feature) from the view, without editing the feature.
2. Filter the part's fillets by radius and change them together.
3. Change Drafts: list the part's drafts by angle or pull direction, change the angle or remove a draft.

### TR133 Variable fillet point positions [Medium]

1. Control points of a variable fillet can be placed by percent of the edge, added and deleted, not only evenly spaced as today.

### TR134 Change a chamfer to a fillet and back [Low]

1. Right click a fillet or chamfer feature: change it to the other kind, keeping the edges and a matching size.

### TR135 Loft to a point [Medium]

1. The first or last loft profile can be a point (a vertex or sketch point), giving a pointed end. The end constraint applies at the point.

### TR136 Loft connectors and end constraints [Medium]

1. Connectors: several per profile, dragged in the view to move the matching point and untwist the loft locally, with Reset.
2. End constraints: None, Normal, Direction and Default exist with a length. Add Tangent to the adjacent faces and Curvature to the adjacent faces.
3. Add Loft Section: insert a new section into an existing loft at a picked position, then edit it.

### TR137 Sweep with a profile part way along the path, and several profiles [Medium]

1. The profile can sit anywhere on the path. Direction: one way, the other way, or both, with its own twist for each side.
2. Several profiles placed along one path: the section changes smoothly from one to the next.
3. At sharp corners of the path: keep the sharp corner, make a mitre, or round it.

### TR138 More inputs for sweeps and lofts [Low]

1. A sweep path can already be a chain of model edges. Add: the profile can be a model face or loop, and loft profiles can be loops of edges.
2. A group picker in the panel combines pieces from several sketches and edges into one open or closed chain, with trim and extend of open chains.
3. Swept Cut with a solid tool body that moves along the path (for a milling cutter path).

### TR139 Better sweep and loft errors [Medium]

1. The loft self crossing message already names the profile order and connection points. When a sweep fails because it would cross itself, the message names where along the path, and suggests a larger path radius, a smaller profile, or splitting the path.
2. Show Sections: step through the sections the loft or sweep would make, by number, to find where it goes wrong.

### TR140 Symmetric linear pattern [Medium]

1. A Symmetric tick on Linear Pattern: copies are made the same number and spacing on both sides of the seed. Circular Pattern already has Symmetric.

### TR141 Pattern chains and patterns of patterns [Medium]

1. A pattern feature made of several steps applied in order (mirror, linear, circular, scale), with the step order changeable. Each step's copies feed the next.
2. A pattern can use another pattern feature as its seed, for features and for bodies.

### TR142 Pattern small options [Low]

1. Patterns of reference planes, axes and points.
2. Edit Seed: right click any instance to edit the seed feature.
3. Linear Pattern by a typed total length as well as by spacing. Circular Pattern already has total angle (equal spacing) and step.
4. A prompt before a pattern with a very large instance count.
5. A reference point for sketch and table patterns: seed centroid, a vertex, or a sketch point.

### TR143 Hole placement without a sketch [Medium]

1. Hole Tool positions by distance from two picked edges, or concentric with a round edge or cylinder face, with the values typed in the view.
2. Using all points, end points or centres of a sketch already works. Add: skip an instance by clicking it.

### TR144 More hole shapes [Medium]

0. Already built: near and far countersinks, a drill point with tip angle, head clearance, and up to vertex.
1. A hole built from a stack of elements from the near side and the far side (counterbore, countersink, straight, tapped), reorderable, for one off holes the standard types do not cover.
2. Counterdrill type: a counterbore with a cone at its bottom.
3. Whole hole taper angle. A tick for whether the depth includes the drill point. A start plane other than the clicked face.
4. User hole standards: a user file adds sizes and head types (diameter, depth, countersink angle) to the hole tables.

### TR145 Tapered threads [Low]

1. Tapered pipe threads in the Hole Tool and Thread, with the taper angle and the standard sizes compiled from the published standards (CLAUDE.md section 7 item 6).

### TR146 Fastening feature extras [Medium]

1. Mounting Boss: height up to a mating face plus a clearance, pin size from a mating edge, a step on the boss, and fin direction from picked faces or edges.
2. Lip and Groove: jump gaps where ribs meet the wall, keep the wall's draft, pick the rim by edges, and lip only or groove only on a body.
3. Vent: fillet radius, draft and an offset from the face for each element group.
4. Snap Hook height up to a mating face is already built.

### TR147 Draft, shell and dome small options [Low]

1. Parting line draft: allow a reduced angle where the full angle fails. Step draft: tapered or square steps.
2. Shell: a Check button that finds the faces where the thickness is too large for the curvature and names the smallest radius.
3. Dome: a direction vector and a constraint sketch for the dome shape.

### TR148 Several planes or points in one command [Medium]

1. Plane gets a Number of Planes field: several offset planes at even spacing, or several angled planes at even steps, from one feature.
2. Point on a curve gets a count, spaced by distance, by percent, or evenly over the curve.

### TR149 Offsets with rotations for reference geometry [Low]

1. Every plane, axis and coordinate system method gets an extra offset in its own axes (three distances and three rotations) and a Flip tick, applied after the method.

### TR150 Interference and gap check between bodies [High]

1. An Evaluate command for multibody parts: lists every pair of bodies that overlap, with the overlap volume, and every pair closer than a typed gap, with the smallest gap. Overlaps and gaps are coloured in the view; other bodies can be shown see through.
2. Exclude bodies, ignore a pair, and a tick for whether touching faces count.
3. Main uses: print in place parts (moving parts must keep a gap) and checking that split pieces fit.

### TR151 Slices and saved sections [Low]

1. Slice: several parallel planes (or planes around an axis) cut a body and leave section sketches in a folder, for laser cut stacks.
2. Turn the current section view into a cut body feature.

### TR152 Named faces and edges [Low]

1. A face, edge or body can be given a name. A list shows the names and highlights each one. Equations and the node editor can refer to a named item.

### TR153 Body folders and body history [Low]

1. Folders inside the Solid Bodies folder, with Hide, Delete and Colour for the whole folder.
2. Show Feature History on a body: the features that made it, in order.

### TR154 Linked body copy [Medium]

1. A copy of a body that follows later changes of the original but has its own position (typed or by a coordinate system). Break Link makes it independent. Move and Copy Body copies are independent today.

### TR155 Move a feature to another body [Low]

1. In a multibody part, a feature (with its sketch) can be moved so it acts on another body.

### TR156 Project onto a curved face [Low]

1. Project a sketch along a direction onto any face, and optionally raise or sink the projected shape by a height (emboss or engrave). Wrap covers cylinders and flat faces only.

### TR157 Cut with an open sketch [Low]

1. An Extruded Cut from one open line or chain, Through All or by a distance, removes the material on one side of it. A Flip Side tick chooses the side. Today an open sketch needs Thin Feature.

### TR158 Remove history from a body [Low]

1. Turn the features of a body into one plain body feature (the geometry stays, the history goes), after a prompt. Used to share a simple part.

### TR159 Purge unused and delete below the bar [Low]

1. Purge Unused: lists sketches nothing uses, suppressed features and unused variables, and deletes the ticked ones.
2. Delete everything below the rollback bar, after a prompt.

### TR160 Copy values and edit by rule [Low]

1. Copy Values: pick a feature, then other features of the same kind; their values are set to match (for example a hole size).
2. Find features by a rule (kind and value, for example fillets under a size) and change them together.

### TR161 Gear profile [Medium]

1. A sketch tool or curve feature that draws an involute spur gear profile from module (or diametral pitch), tooth count and pressure angle, with root fillet, profile shift and an internal gear option. Extrude, twist or pattern it as usual. Also a chain sprocket profile from chain size and tooth count.
2. Gears are among the most common lesson projects and printing questions.

### TR162 Fastener and spring shapes [Low]

1. Samples or node graphs that make a hex bolt, nut and washer from a standard size, using FDCAD's thread and hole tables.
2. Helix end options: closed ends and ground flat ends for springs (a flat cut at each end and a tighter pitch over the last turn).

### TR163 Surface texture and knurl [Medium, owner decision]

1. Knurl: a straight or diamond knurl on a cylinder face, by pitch and depth, as real geometry.
2. Texture from an image: a grey image raises or sinks a face by its brightness, with a depth and size. This makes many small faces or a mesh, so the owner decides if it fits.

### TR164 Show new and changed faces in a preview [Low]

1. A detailed preview tick for Extrude, Rib and Draft colours the faces the feature adds or changes, or shows only new bodies.

## 8. Sheet metal, second round (TR165 to TR174)

### TR165 Sheet metal Tab [Medium]

1. A closed sketch on a sheet face, or on a face square to the sheet, adds a wall piece exactly one sheet thickness thick, joined to the part. It can be patterned. Today only Base Flange adds the first wall. Bosses in sheet metal also get Link to thickness (TR30 has it for cuts).

### TR166 Edge flange profile and edge choices [Medium]

1. Edit Flange Profile: the flange outline sketch can be edited, so the flange is narrower, wider, notched or shaped. The sketch may run past the ends of the edge.
2. Edge flanges on curved and tangent edge chains. End the flange at a picked point. Change the lengths of several flanges at once.

### TR167 Edit Bends [Medium]

1. A command to change the radius, allowance or deduction of one bend, a group or all bends of a part after they are made, including bends of a converted or imported sheet metal body.

### TR168 Corner Relief feature [Medium]

1. A feature that adds relief cuts at corners where two or three bends meet, with Collect All Corners and one choice per corner. Types: Rectangular, Circular, Tear, Obround and Constant Width. Size by ratio of thickness or by value, centred on the bend lines or tangent to the bends.
2. Today corner relief is a part default with two types only.

### TR169 Bend notches [Medium]

1. Small notches (triangle, circle or rectangle) at both ends of each bend line in the flat pattern, size typed, so a press brake operator can line up the bend. Shown in the flat pattern and its DXF.

### TR170 Miter flange extras [Low]

1. Start and end offset (a partial miter flange), trim the side bends, its own relief and allowance, and arcs in the profile.

### TR171 Convert to Sheet Metal extras [Medium]

1. Keep the original body, so one solid can be converted more than once.
2. Rip sketches to choose the rips, and rip types (open, butt, overlap) with a gap and an overlap ratio per rip.
3. Rounded edges of the solid become bends with their radius. Collect All Bends on sheet like imported parts.

### TR172 Flat pattern data for quoting [Medium]

1. The flat pattern shows and can export: blank area, outer and inner cut length, number of cut outs, number of bends, and the flat bounding box length and width. These can be used in equations.

### TR173 Flat pattern DXF output options [Medium]

1. A panel when exporting the flat pattern: which items to write (outline, bend lines, sketches, form marks), the origin and axis directions, single or one file per body, colours for up and down bend lines, and a preview where items can be removed.

### TR174 Sheet metal small options [Low]

1. Hem: width per edge, own allowance and relief.
2. Closed Corner has overlap, underlap and butt with a gap. Add an overlap ratio, open or closed bend region, and several corners at once.
3. Cross Break: break radius and angle values (only Reverse today).
4. Rip on hollow cylinders and cones with gap, position and angle.
5. Break Corner has chamfer and fillet. Add internal corners only, and Collect All Corners.
6. Tab and Slot has count, spacing and clearance. Add equal offsets, centre on the edge, skipped instances, and use inside patterns and mirrors.
7. A warning when the flat pattern is larger than a typed sheet size.

## 9. 3D printing (TR175 to TR189)

### TR175 Support free hole tops [High]

1. A Hole Tool and Extruded Cut option for holes that run sideways: the top of the round hole gets a pointed or flat top (a teardrop or a flat bridge) so it prints without supports. The direction comes from the print orientation or a picked up direction.

### TR176 Bridging under counterbores [High]

1. For counterbored and countersunk holes printed head down, an option adds a thin sacrificial layer over the hole, or two stepped layers that bridge across the bore, sized from the printer profile layer height. The user drills or cuts it out after printing.

### TR177 Bed edge chamfer [High]

1. One command chamfers every edge on the face that sits on the bed (from the print orientation or a picked face), including hole edges, by a small typed size, to stop the first layers spreading.

### TR178 Printable thread profile and fit [High]

1. Thread (modelled) gets a printable profile with a flatter angle that prints without supports, a clearance per side typed or taken from the fit presets, and a lead in so the start of the thread is not a thin edge.
2. A coarse round profile for caps and jars, with a custom pitch.

### TR179 Magnet pocket [Medium]

1. A Hole Tool type for round and block magnets: size from a table, a snug fit from the fit presets, optional relief slots, and an option to leave a thin closed skin so the magnet is sealed in during printing.

### TR180 Print fit tolerance as a variable [Medium]

1. The printer profile has a fit tolerance that the Hole Tool print fit uses. It is not in the equation names today. Make the fit presets and the printer profile's tolerance available in equations as named values, so one value drives every mating feature, and changing printer updates them.

### TR181 Split for Printing connectors [Medium]

1. Add connectors: screw and nut holes across the cut, magnet pockets, a glue gap, and draft on keys. Today pins and dovetails exist.
2. A stepped or shaped cut from a sketch path, not only a plane.

### TR182 Mesh export options [High]

1. STL and 3MF export get a panel: quality presets (coarse, fine) or a custom deviation and angle, binary or text STL, unit, and which bodies (all, shown, or picked). The panel shows the triangle count and file size before saving.
2. The core export already takes mesh settings (deviation and angle), but the UI always uses the defaults. The work is the panel and remembering the setting per part.

### TR183 3MF names and metadata [Low]

1. 3MF export writes one object per body named by a counter ("title body N"), because bodies have no lasting names (D254), and only one metadata item. Add the part's title, designer, description, licence and dates, a part number, and the body's own name once bodies have lasting names. Orca style slicers rename a lone object to the file name, so names matter mostly for several bodies.
2. A package thumbnail picture, so file browsers and print queues show the part (TR381).

### TR184 Multi colour inlays [Medium]

1. A helper for two colour prints: pick sketch text or a shape and a face; it makes the inlay as a separate body and the matching pocket in the base, with a typed depth, and exports both as one 3MF with named bodies.

### TR185 Scale to fit the printer [Medium]

1. Print preparation can scale the part to fit the printer's build volume, and turn it to fit. The part file is not changed unless the user saves the scale as a feature.

### TR186 Mesh repair and reduce [Medium]

1. Before Convert to Solid, a mesh body can be repaired: fill holes, fix edges shared by more than two triangles, remove tiny pieces. Reduce: lower the triangle count by percent or to a target, with a largest error and a keep boundary tick. Today Convert fails on open meshes and large meshes only warn.

### TR187 Layer aware sizes and infill weight [Low]

1. A check that lists heights and wall thicknesses that are not a whole number of layers or line widths of the printer profile.
2. Print Estimate gets an infill percent and a wall count, so the weight is closer to the real print.

### TR188 Printing sample parts [Medium]

1. Samples with tutorials: a fit test plate (pins and holes with stepped gaps, and a nut and bolt), a print in place hinge, a living hinge, and a storage bin on a base grid made with variables.

### TR189 Small printing helpers [Low]

1. Polygon holes: a round hole made as a polygon whose flats hit the nominal size.
2. Corner ears: thin round discs at the corners of the bed face against warping, removed after printing.
3. Drain holes for hollow resin prints at the lowest points.
4. Heat set insert entry chamfer and a depth margin in the insert table.

## 10. Evaluate, variables and configurations, second round (TR190 to TR199)

### TR190 Measured values in formulas [Medium]

1. A variable can read a measured value of the model: a distance, an edge length, a diameter, a face area, a body's volume or bounding box size. It updates on rebuild. The reading uses face references with the usual naming rules.

### TR191 Saved measurements [Medium]

1. A measurement can be kept as a label in the view and saved in the part, with optional X, Y and Z parts. It updates on rebuild. Today Measure keeps a history for the session only.

### TR192 Measure free points [Low]

1. Point to Point mode: the distance between two points picked anywhere on faces, not only vertices and nearest points. A position readout for one picked point.

### TR193 Linked values [Low]

1. Pick several dimensions and give them one shared name. Any of them then drives the others, with no equation.

### TR194 Equation editor comfort [Medium]

1. Type ahead of variable, dimension and function names while typing a formula.
2. Sort and filter the list, select several rows, and Disable an equation (kept, but not used).
3. Replace Reference for an equation left pointing at a deleted feature.

### TR195 Linked child configurations [Medium]

1. A configuration made from a parent stays linked: values not changed in the child follow the parent. Values the child changes are marked. New features added while the child is active can be suppressed in the others. TR90 only copies the parent's values once.

### TR196 Export each configuration [Medium]

1. Export all or picked configurations as separate part files, STEP, STL or 3MF files in a folder, named by configuration, with a log of any that failed.

### TR197 More values per configuration [Low]

1. Face and body colour, a sketch's plane, and whether a dimension is driving or reference, set per configuration.
2. Preview a configuration in a small view without making it active.

### TR198 Table functions and lookups [Low]

1. Sum, average, min, max and count over design table columns.
2. A variable read from a CSV table by row index or label.

### TR199 Curvature and deviation display [Low]

1. Edge curvature combs and the curvature graph exist. Add curvature colours on faces with a scale and a readout under the cursor.
2. Deviation along an edge: the angle between the two faces at sampled points, with largest, smallest and average.

## 11. Window, tree, view and files, second round (TR200 to TR224)

### TR200 Tree follows the selection [Medium]

1. Picking a face or edge in the view opens and scrolls the tree to its feature (a preference). Clicking empty space puts the scroll back.
2. Right click a face or edge: Go To Feature.
3. Hovering a tree row highlights its geometry in the view (a preference).

### TR201 Delete with a list of dependents [Medium]

1. A yes or no warning that names the children already exists. Make it a list of the features and sketches that depend on the feature: a basic choice deletes all of them, an advanced one has a tick per item. With several faces picked, Delete offers Delete Feature or Delete Face.

### TR202 Errors list as a table [Medium]

1. The errors panel is a list with fix buttons today. Make it a table: type, feature and description, sortable, with Show Errors and Show Warnings ticks. A preference opens it after any rebuild with errors. Selecting a marked feature shows its message beside it.

### TR203 Message bars and hidden messages [Low]

1. Information and warning bars at the top of the view that stay until closed and have Don't Show Again. Preferences lists hidden messages and can restore them.

### TR204 Recent commands in a sketch [Low]

1. A Recent Commands submenu already exists in the right click menu. Add a separate list while a sketch is open, so sketch tools are not pushed out by part commands.

### TR205 Menu access keys [Low]

1. The File menu has an access letter. Check and finish every menu and its entries, so Alt and a letter reaches every command on Windows. This is an accessibility gain.

### TR206 Property panel behaviour [Medium]

1. A pin keeps the panel open after OK so the same feature can be made again.
2. Tab moves through every control, Space toggles ticks, arrows change choices. Groups collapse and remember it.
3. Pick boxes: the active one is highlighted, right click gives Delete and Clear Selections, and the box grows with its list.

### TR207 Right click to move on [Medium]

1. While a feature panel is open, right click in the view moves to the next pick box. When the panel is ready, right click offers OK and Cancel.

### TR208 Undo list [Medium]

1. A drop down beside Undo lists recent steps by name. Picking one undoes back to it in one go.

### TR209 Rotate about a picked item [Medium]

1. Pick a turning centre with the middle button (a point, edge or face under the cursor); dragging with the middle button then turns the view about it. A preference locks the up direction while turning.

### TR210 Axis triad clicks and an orientation popup [Medium, owner decision on the key]

1. Clicking an axis of the corner triad looks along it. Clicking again turns to the other side. Shift and click turns by a quarter turn.
2. A key opens a popup with the standard views, saved views (TR14), split view layouts (TR16) and New View. Space is the common key; FDCAD uses Ctrl+Space for the view selector, so the owner chooses the key.
3. Normal To with two faces picked: the first faces the screen, the second sets which way is up.

### TR211 Zoom keys and mouse settings [Low, owner decision on the key]

1. A Zoom Out key (Z is Repeat Last Command today, so the owner chooses), and double middle click for Zoom to Fit.
2. Preferences: reverse the wheel direction, zoom about the screen centre or the cursor, arrow key turn step, turn speed, and Zoom to Fit when a standard view is chosen.

### TR212 Edge display options [Medium]

1. Smooth edges between tangent faces: shown, dashed, or removed. Hidden edges: dashed or solid. Highlight all edges of a selected feature.

### TR213 Section view extras [Medium]

1. Two or three section planes already work, but a section is never saved. Add: save a section with the part and as part of a saved view, choose which bodies are cut, and keep section planes in a tree folder, each with a drag handle and rotation rings. Measure works on the cut faces. (IDEAS item 6, Edit Section, is related.)

### TR214 Display quality [Medium]

1. A per part slider for how finely faces are drawn, with the deviation value shown, and a lower quality while turning the view on large parts. This fixes jagged circles on small details.

### TR215 Hide and show by type [Medium]

1. Separate toggles exist for planes, origins, sketches, temporary axes and dimensions. Add one menu with a tick per type: planes, axes, temporary axes, points, coordinate systems, sketches, curves, sketch dimensions, relation tags, origins. Hide All Types turns everything off and back on as it was. A key shows and hides all planes.

### TR216 Display mode per body [Low]

1. The bodies column (F8) gets a display mode per body (shaded, shaded with edges, hidden lines, wireframe) and transparency, besides visibility and colour.

### TR217 Part templates [Medium]

1. Save the current part's settings as a template: units, decimals, variables, colours, grid and display settings, printer profile and (with TR78) material. New Part offers the templates.

### TR218 File commands and start page [Low]

1. Recent files and autosave recovery exist. Add Save All, Close All, Revert to Saved, and reopen the last session's parts at start.
2. A start page with recent parts as thumbnails, pin and remove, Show in Folder, and drag a file onto the window to open it. The part file stores a thumbnail.
3. Keep a chosen number of older backup copies in a chosen folder.

### TR219 Safe start without graphics hardware [Medium]

1. A start option that uses software drawing, for machines whose graphics driver fails, with a link to it in the crash message. Fits the rule that FDCAD never needs a GPU.

### TR220 Low memory and disk warnings [Low]

1. A warning before memory or disk space gets so low that work could be lost, with a Save button.

### TR221 Small tree and status options [Low, owner decision on the key]

1. Recently edited features list. Name new features on creation (rename opens at once). A Collapse All key (Shift+C is taken, so the owner chooses).
2. A feature description separate from its name.
3. Status bar shows the hovered edge's length, radius or the angle between two faces.

### TR222 Custom command tabs and a simple mode [Low, owner decision]

1. Add and remove buttons on command tabs, make a custom tab, and large buttons with text. A simple mode with fewer commands for new users. The owner decides against the command tab spec (docs/RIBBON_SPEC.md).

### TR223 3D mouse [Low, owner decision]

1. Support for 3D mice through the platform's driver. Needs a dependency with a licence check (CLAUDE.md section 2 item 2).

### TR224 Selection small options [Low]

1. Select through see through faces, with Shift to pick the see through face itself.
2. After picking one edge, Ctrl+A picks all edges (the same for faces).
3. A box or lasso drag that can start on top of the model (a key held).
4. A before and after slider in a feature preview that fades between the old and new model.

## 12. Sketch, third round (TR225 to TR238)

### TR225 Slot along picked curves [Medium]

1. Pick one or more lines, arcs, ellipses, splines or a chain as the centre line. A slot of one shared width is made around them; a chain gives one continuous slot with trimmed joins. The width is one dimension.

### TR226 Ratio and difference relations [Medium]

1. Length Ratio: line or arc A divided by B equals a value. Length Difference: A minus B equals a value. Equal Angle between two pairs of lines. Equal distance from a point to two lines.

### TR227 Round All Corners [Medium]

1. One command rounds every corner of a picked profile or region with one radius, inside and outside corners, with a list to override single corners. The result is sketch fillets with one shared dimension (see TR48 item 3).

### TR228 Triangle, trapezoid and other shapes [Low]

1. Triangle by three sides, two sides and an angle, or one side and two angles; trapezoid by widths and height. A new tool; TR114's triangle preset is not built either.
2. Less common shapes as presets: keyhole, rounded polygon of constant width, egg, superellipse.

### TR229 Convex hull [Low]

1. Sketch: the convex outline around picked curves becomes new sketch geometry. Part: a smooth solid bridge around two or more bodies.

### TR230 Text along any curve [Low]

1. Text already follows a sketch line or arc, with full justify. Add splines and full circles (a circle is refused today) and a start offset along the curve.

### TR231 Control of relations offered while drawing [Medium]

1. While drawing, a relation the tool is about to add can be locked (it must hold), turned off for this entity, or skipped, with a key or click. Tab cycles when several are offered.
2. Preferences have a tick per kind of automatic relation (horizontal, vertical, parallel, perpendicular, tangent, equal, midpoint, coincident).
3. Overlapping relation tags stack, and right click cycles them.

### TR232 Temporary guide lines [Low]

1. Hovering a point for a moment, or dragging from it with a key held, makes a temporary dashed guide through it. Its ends, midpoint and fractions along it become snap points. Guides vanish when the tool ends.

### TR233 Colour per sketch [Low]

1. A sketch can be given its own display colour, so layout sketches and traced pictures are easy to tell apart. Status colours (TR38) still win while editing.

### TR234 Sketch on a face without splitting it [Low]

1. A tick per sketch: drawing on a part face does not split that face into regions for picking.

### TR235 Show formulas on dimensions [Low]

1. A toggle shows each dimension's formula above its value. A dimension can carry a short comment shown on hover.

### TR236 Step a dimension through a range [Low]

1. Pick a dimension, a range and a step count; the sketch is solved at each step and shown in turn, so the user can see that it moves as intended. Nothing is saved.

### TR237 Explain a relation [Low]

1. Right click a relation tag: Explain shows in words what the relation holds and which items it links.

### TR238 Sketch settings [Low]

1. Lock changed dimensions while dragging, a polar grid (angle step and rings), and highlight crossings and joins.

## 13. Part and features, third round (TR239 to TR268)

### TR239 Extrude in a picked direction [Medium]

1. Extruded Boss and Cut get a Direction pick: an edge, axis, sketch line or a typed vector instead of the sketch normal, with the depth measured along it or square to the sketch (a choice). Today extrudes go square to the sketch only.

### TR240 Extrude with twist and end scale [Medium]

1. Extrude gets an end twist angle and an end scale factor (one value, or X and Y), so the profile turns and grows or shrinks along the height. Common for vases and twisted columns.

### TR241 Sweep with scale along the path [Medium]

1. The profile scales from a start factor to an end factor along the path, linearly or smoothly. It cannot be combined with a twist angle; the panel says so.

### TR242 Different depths per region in one extrude [Medium]

1. With several regions picked, each region can have its own depth (or share one). When the sketch changes, new regions appear at zero depth with a warning, a split region becomes two rows at the old depth, and removed regions drop out.

### TR243 Edge profiles [Medium]

1. Sweep a profile along picked edges or a face's outer loop as a cut or an addition, with rounded corner joins. Presets for common router shapes (cove, round over, rabbet, ogee, chamfer with flat) and any closed sketch.

### TR244 Machining corner relief [High]

1. Inside corners of a pocket or slot get a relief so a round cutter can reach them: dogbone (along the diagonal), T shape (along one side), or a corner fillet. The size comes from a tool diameter, plus a clearance, and can be a variable. Applies to picked edges or all inside vertical edges of a feature.

### TR245 Lightening pockets [Medium]

1. On a picked plate face: keep regions (around holes, along edges) and a web width, corner radius and border; the rest of the face is pocketed or cut through as triangles or free shapes between the keep regions.

### TR246 Finger joints between plates [Medium]

1. Pick two plate bodies that meet at an edge. Fingers and slots are cut into both from material thickness, finger count or width, a fit clearance and a kerf allowance. Used for laser cut boxes.

### TR247 Shaft and bore shapes [Medium]

1. Shaft end and bore cut presets: hex, D flat, double D, and keyway, sized from the shaft diameter with a fit clearance.

### TR248 Keyways and keyseats [Medium]

1. From a shaft or bore diameter, the standard key width and depth for the shaft keyseat and the hub keyway are cut, for parallel and inch square keys, and half moon keys. Sizes compiled from the published standards.

### TR249 Retaining ring grooves [Medium]

1. A groove cut on a shaft or in a bore for a retaining ring or E clip, sized from the diameter and ring type from the published standards, at a picked position.

### TR250 O ring groove [Medium]

1. Pick a cylinder face or a flat face and an O ring size (inch dash sizes and metric sizes, compiled from the standards). The groove is cut for the use: face seal, rod or piston, static or moving, with the squeeze and fill checked and shown.

### TR251 Bearing seat [Medium]

1. A Hole Tool type for common ball bearings by designation: the bore for the outer ring, a shoulder, an optional retaining groove, and a press or slip fit. Linear bearing and motor face patterns may follow (TR72 library content).

### TR252 Dowel holes and a fit helper [Medium]

1. A Hole Tool type for dowel pins with press or slip choice.
2. A fit helper: from a nominal size and a fit code (hole and shaft classes) it gives the hole and shaft limits, usable in equations. Data compiled from the published standard.

### TR253 More screw heads and thread series [High]

1. Today the tables cover metric coarse and the inch coarse series with two fine sizes, and socket head and flat head counterbores. Add button head, low head socket, pan and cheese heads, the other countersunk head form, a washer seat, metric fine pitches, the inch fine and extra fine series, the smallest inch gauge sizes, and larger metric sizes.
2. Drill size names (number, letter, fraction) shown beside the mm value.

### TR254 More thread forms [Medium]

1. Thread (modelled) gets profiles besides the 60 degree V: trapezoidal metric, ACME, square, buttress, round, the 55 degree pipe form, and a user profile from a sketch. End finishes: fade out, chamfer, square.

### TR255 Hole for self tapping screws [Medium]

1. A Hole Tool type sized below the tap drill, with an entry bevel, for screws that form their own thread in plastic. Size table from FDCAD's own rules, editable.

### TR256 Thread relief and end chamfer [Low]

1. Hole Tool and Thread options for a thread run out groove (undercut) and an end chamfer sized from the pitch, compiled from the published standards.

### TR257 Airfoil profile [Medium]

1. A sketch tool that draws an airfoil from a four or five digit code, or from a two column point file. Chord, angle, trailing edge thickness, open or closed trailing edge. The curve is a smooth spline with few control points, not a dense polyline.

### TR258 Roof and grow by a shape [Low]

1. Roof: a sloped top over any closed outline at a slope angle.
2. Grow a body by a small sphere or other shape (rounded offset of every edge).

### TR259 Rebuild fillets after a direct edit [Medium]

1. A Reapply Fillets tick on Move Face, Delete Face, Draft and Combine: rounded edges next to the change are removed first and made again after, with the same radius.

### TR260 Remove and change fillets on imported bodies [Medium]

1. Find fillet faces on a body with no history (optionally in a radius range), then remove them or change their radius, in small batches in reverse order of size. Extends TR132.

### TR261 Merge faces and remove extra edges [High]

1. Pick faces, or an edge between two faces that lie on the same or nearly the same surface, and replace them with one face. Imports and Delete Face leave such edges and later fillets and drafts fail on them.
2. Combine and Split get a tolerance so near touching faces of imported bodies are treated as touching.

### TR262 Geometry Check with fixes [Medium]

1. Each Geometry Check finding gets a Fix button where a fix exists (merge a sliver face into its neighbour, close a gap, make a nearly smooth edge exactly smooth, square up a nearly square hole or face within a typed angle). Findings can be marked Ignore.
2. A tour: Next and Back through findings, zoomed, with a clip sphere around each.
3. More classes: duplicate faces, short edges under a typed length, inexact edges.

### TR263 Rules for Move Face [High]

1. Move Face (its offset, translate and rotate modes) and Offset Face get a rule panel with a tick per rule: keep coplanar faces, keep concentric faces, keep parallel and perpendicular faces, keep tangent faces, keep symmetry about a plane, keep equal radii, keep faces locked to the main planes. Faces found by an active rule join the move.
2. The preview shows the faces that move, the faces held still and the faces that stretch in three colours, and each found rule shows whether it changes the result.
3. Suspend All Rules for one edit, and suppress one rule for one face.

### TR264 How neighbours follow a moved face [High]

1. A choice in Move Face: Extend (neighbours keep their angle and are extended or trimmed), Tip (neighbours may tilt to meet the moved face), or Lift (the face moves unchanged and new side faces are made). Today neighbours only stretch.
2. Next and Previous buttons cycle through other valid ways the face can rejoin the body. A Keep This Solution tick makes a later rebuild fail rather than silently pick another.
3. Rounds on the moved face's edges can move with it or be made again after.

### TR265 Set a size on a face [High]

1. Resize Face: for a cylinder, sphere, cone or torus face, type the new diameter (or angle for a cone, with which end stays). Neighbouring rounds adapt.
2. Set Measured Size: in Move Face or Offset Face, pick two items (a hole centre and an edge, two walls); the box shows the current distance; type the wanted value and the face moves by the difference.
3. Dimensions placed on model edges and faces can be edited directly: arrows show which side moves, a Symmetric button moves both, and a lock holds a dimension during other edits.

### TR266 Lasting face relations on bodies with no history [Medium]

1. On an imported body, add relations between faces (concentric, coplanar, parallel, perpendicular, tangent, symmetric, equal radius, offset, fixed). Kept relations are listed in a folder and hold during later Move Face edits.

### TR267 Push and pull by sign [Medium]

1. A Push Pull command on a flat face or a closed sketch region on a face: a positive distance adds material and a negative one cuts, with no Boss or Cut choice.
2. While dragging any distance, Tab jumps to the next parallel face as a target, nearest first. A key switches any distance between one side and symmetric.
3. Double click another face to apply the same distance there.

### TR268 Place bodies by picks [Medium]

1. Move and Copy Body by relations: coincident faces, distances and angles between faces of the body and target faces or planes, several in one feature.
2. Orient Body: map a picked frame (origin and axes from faces, edges, circles) onto another.
3. The transform handles get a pivot choice (bounding box centre, a picked point, the last pick) and an axis choice (body, plane, world), and a mode that moves only the handle.

## 14. More part and features, third round (TR269 to TR285)

### TR269 Lock a body [Medium]

1. A body can be locked: it stays visible and can be snapped to, but cannot be picked or changed. It is drawn greyed. Used for reference bodies such as an imported board.

### TR270 Pattern explode and small pattern options [Low]

1. Turn a pattern into one independent feature per instance.
2. Choose which grid cell holds the seed, rotate the whole linear pattern, and hide instances in the view only for speed.
3. Skip instances by dragging a box over their markers.

### TR271 Fillet: limit failing areas, edges to keep, limiting plane [Medium]

1. Limit Failing Areas: round what works and leave the failing areas sharp, offered as a fix button.
2. Edges to Keep: named edges are protected from a fillet that would swallow them.
3. A limiting plane or face trims the end of a fillet.

### TR272 Thin feature joined at its ends [Low]

1. An open thin wall can be trimmed to the existing material at its ends (Merge Ends), so it meets the walls without overlap.

### TR273 Goal seek and value sweep [Medium, owner decision]

1. Pick a variable and a measured value (volume, a distance, an area). Sweep: the variable steps through a range and a table shows the result per step. Goal Seek: FDCAD changes the variable until the measured value hits a typed target. Runs in the background worker, and nothing is saved until the user accepts the result.

### TR274 Variables with allowed values [Medium]

1. A variable can be a single value, a list of choices, or a range with minimum and maximum. Fields that use it show a choice box or warn when out of range.

### TR275 Tick boxes as formulas [Medium]

1. Any tick box in a feature panel (Reverse, Merge result, Direction 2) can be set by a formula that gives true or false, like the existing suppression formulas.

### TR276 Pause rebuilds [Medium]

1. A manual update mode for heavy parts: edits are collected, the part shows an out of date mark, and Rebuild applies them. Leave by Rebuild, Rebuild and Stay Paused, or Discard.
2. A checkpoint tick on a feature pauses a rebuild after it and asks to stop or go on.

### TR277 Replace a reference everywhere [Medium]

1. Pick a sketch, face or plane used by several features and a new one: every feature switches to the new one, with a Delete Old tick. Deleting an item can also offer a substitute.

### TR278 Skip one face as a fix [Medium]

1. When Shell or Offset Body cannot treat one face, a fix button leaves that face out and names it. Reset Skipped Faces undoes it later (CLAUDE.md section 5 item 12).

### TR279 Own forming tools [Medium]

1. A user builds a form shape as a part and marks its stop face, faces to remove (which leave holes) and an insert point. It is saved to a library and placed on a flat wall with a rotation, and can be patterned and mirrored. FDCAD's Forming Tool has fixed shapes today.

### TR280 Bodies to linked part files [Medium]

1. Write picked bodies, or the pieces of a Split, to separate part files that stay linked to the master, so master changes flow on. Also write each body to its own STEP, STL or 3MF file in one command.

### TR281 Several sheet metal bodies [Medium, owner decision]

1. A part may hold several sheet metal bodies, each with its own thickness and bend values and its own flat pattern, mixed with solid bodies. Today the sheet metal folder is one per part and Base Flange must be the first solid.

### TR282 Bend table and bend order [Medium]

1. A table of all bends and rips: picking a row highlights it in the model and the flat pattern, and the radius and allowance can be edited per row. A bend can be turned into a rip and back.
2. Bend Order: reorder the bends to match the real bending sequence; the order goes to the flat pattern export.

### TR283 Sheet metal forms as features, and fold progress [Low]

1. Dimple, drawn cut out and bead as sketch driven sheet metal features, with several profiles and bead end shapes.
2. Fold Progress: show all bends at a percent between flat and folded. Map sketch points and curves onto the flat pattern as marks.

### TR284 Enclosed cavities [High]

1. Find closed voids inside a body, report each one's volume and whether it has an opening. For resin and powder printing, suggest drain or escape holes as a fix button.
2. Cavity volume: the volume of the space enclosed by picked faces and an opening plane (a cup, bottle or tank).

### TR285 Rib network [Low]

1. Rib from several open chains in one sketch makes a grid of walls that join where they meet. Rib accepts one unbranched chain only today.

## 15. Evaluate, checks and help, third round (TR286 to TR303)

### TR286 Model health report [High]

1. One advisory list for the part, with Zoom to Item, that never changes geometry: sketches not tied to the origin or a fixed item, sketches fully defined only by many dimensions where a relation would do, features that depend on a fillet or chamfer, fillets early in the tree (with a Move to End button the user confirms), features that no longer do what their kind says (a cut that removes nothing, a blind hole that came out through), features left with default names, and many single shape sketches that one sketch and a pattern would do.

### TR287 Change test [High]

1. In a background copy, step each dimension and variable up and down by a set percent. Report which values make the rebuild fail or change the number of faces, and the safe range per value. Nothing in the part changes.

### TR288 Show the cause of an error [High]

1. When a feature fails because an earlier feature changed or lost the geometry it used, the error names that earlier feature, and Show Cause jumps to it. The errors list sorts by cause first.

### TR289 Before and after comparison [Medium]

1. After a value change, a small list shows the volume change per feature. Clicking a row draws the old shape faintly over the new one.

### TR290 Result line after each command [Medium]

1. After each feature, the status bar says what it did in numbers ("Cut 2 removed 2.4 cm3 and added 3 faces"). Screen readers announce it.

### TR291 Help where it is needed [Medium]

1. The first time a tool is used, its panel shows a one line hint with a Show Me link. Hints can be turned off. A help button in each panel opens that tool's page.
2. First run lessons that check the result: each step ("draw a rectangle and fully define it") is ticked when the part shows it, with Resume Later.
3. A What's New list that can be opened at any time.

### TR292 Status without colour alone [High]

0. Contrast tests for the themes and an always visible focus ring already exist (item 2 extends them to sketch lines and selection).
1. Every status shown by colour also has a second cue (sketch status is colour only today): line style or thickness for sketch status, a shape or text for errors and warnings. A colour vision safe palette option.
2. A test checks that selection, hover, focus and sketch lines meet a 3 to 1 contrast against the background in every theme, and that the keyboard focus is always visible.

### TR293 Work without dragging [Medium]

1. Every drag (handles, dimensions, the rollback bar, tree reorder) also works as click then click, or click then type.
2. Keyboard picking: step through pick candidates under the cursor, pick the next sketch point, and nudge a picked sketch item or handle with arrow keys.

### TR294 Motion, screen readers and target size [Low]

1. Reduce Motion exists in Preferences. Make it follow the system setting by default.
2. The 3D view, sketch editor and tree rows report role, state and changes to screen readers, and a Describe Part command reads out the bodies, size and feature list.
3. A Large Controls setting for toolbar and tree targets.

### TR295 Manufacturing check [High]

1. One Evaluate command with a process choice (milling, turning, laser and sheet metal, moulding, FDM printing, resin printing, powder printing). It lists findings in a table; clicking one highlights the face or edge; nothing changes; fixes are buttons.
2. A manufacturing profile per process holds the rule values, is editable, and is saved as a file that can be shared. FDCAD ships general values of its own, not any service's tables. The printer profile gains a process type and a few fields.

### TR296 Milling checks [High]

1. Inside corner radius smaller than a set tool radius or a fraction of pocket depth (fix: raise it, or TR244 relief).
2. Pocket depth to width, hole depth to diameter, thin tall walls, slots narrower than the smallest tool.
3. Faces that no tool direction can reach from a set of setup directions, with the number of setups needed.
4. Threads longer than a set multiple of the diameter, blind tapped holes without room below the thread, hole sizes that are not stock drill sizes (Snap to Nearest button), and text that is too small or raised for milling.

### TR297 Sheet metal and laser checks [High]

1. Hole to bend, hole to edge, hole to hole, slot to bend, minimum hole size against thickness, minimum flange length, features too close to a bend, and tab and slot minimums, with values from the manufacturing profile. A bend radius below the material's minimum is a warning (needs TR78).
2. Flat pattern export preflight: open contours, duplicate lines, tiny features, holes smaller than a thickness ratio, islands that would fall out of cut text, and units.
3. Stencil bridges for sketch text, and a kerf value that Tab and Slot and finger joints (TR246) use.

### TR298 Moulding checks [Medium]

1. Wall thickness change, thick sections that may sink, corner radius against wall, rib thickness and height against wall, boss wall and height, and draft by height.
2. Rib and Mounting Boss get Size From Wall: thickness, height and base round set as ratios of a picked wall, with editable ratios.

### TR299 Printing checks [Medium]

1. Slender pins and fins by diameter to height, holes below the process minimum, details and text smaller than the nozzle or process limit, bridges longer than a set length, and minimum wall that grows with part size.
2. A modelled thread finer than the layer height allows is flagged with the suggestion of a tapped pilot hole or an insert.

### TR300 Section and outline export [Medium]

1. Export the cut at a plane, or a body's outline seen along an axis, as DXF or SVG, with a kerf or tool offset, a scale, and several faces or bodies in one file with layers per use (cut, engrave, ignore).

### TR301 Arrange on the bed and suggest an orientation [Medium]

1. Arrange several bodies on the printer bed with a spacing. Try the six face down orientations and rank them by overhang area, height and fit; one click applies Lay Face Flat.

### TR302 Export and import options [Medium]

1. STEP export: unit, Y up, body names, one file per body, and leave out hidden bodies unless ticked.
2. STEP import: a tick tree with a preview picks which bodies come in.

### TR303 Select Similar [Medium]

1. With a face picked, select all faces of the same kind: same radius cylinders, all hole walls of one size, faces parallel to it, faces of the same area range, all fillet faces of one radius. Rules combine (and, or, except). Extends TR94.
2. Selection conversion keys: keep only the edges, faces or bodies of the current selection.

## 16. Smaller items, third round (TR304 to TR316)

### TR304 Copy configuration inputs [Low]

1. Copy all configuration inputs of one part and paste them into another, and copy or paste the whole configuration table through the clipboard.

### TR305 Incremental save [Low]

1. Save and add a number to the file name (part 01, part 02).

### TR306 Mean dimensions [Low]

1. With dimension tolerances (TR46), one command sets every value to the middle of its range, and back.

### TR307 Coating allowance [Low]

1. A per part coating thickness (paint, powder, anodise) that shrinks holes and grows pins on export or as a feature, like Print Fit.

### TR308 Group identical bodies [Low]

1. In a multibody part, bodies with the same shape are grouped in one folder with a count.

### TR309 Mirror image display [Low]

1. Show a mirror image of the part about a plane, display only, to judge symmetry.

### TR310 Variable names [Low]

1. Variable names that equal a unit name (mm, in, deg) or a function name are refused with a message, because a name right after a number is read as a unit today.

### TR311 Code tag generator [Low]

1. Turn a text into a two dimensional code pattern in a sketch (square modules joined into one region) for printed tags.

### TR312 Mouse presets [Low, owner decision]

1. Navigation has Mouse and Trackpad today. Add mouse button presets for turn, pan and zoom that match the common conventions users come from, named by their behaviour, not by product.

### TR313 Pick size settings [Low]

1. Settings for how close the cursor must be to pick points, edges and vertices.

### TR314 Repeat with the same tool [Low]

1. Shift and Enter accepts a panel and opens the same tool again empty. The panel title turns red while it is not complete.

### TR315 Layer preview [Low]

1. Draw layer lines on the part at the printer profile's layer height, to judge small details.

### TR316 Hole and thread list [Low]

1. A table of all holes: type, size, depth, thread, count and position, copied or saved as CSV.

## 17. More items, third round (TR317 to TR336)

### TR317 Tangent circles and two point circle [Medium]

1. Circle tangent to three lines or curves, or tangent to two with a typed radius, and a circle from two points on its diameter. Today Circle has centre and three point modes.

### TR318 Blend curve [Medium]

1. A sketch curve that joins the nearest ends of two curves or edges smoothly, tangent or curvature matched, with a weight at each end.

### TR319 Turned outline [Medium]

1. Project a body into a sketch as it looks when spun about an axis (the outline of a turned part), for lathe drawings and revolve profiles.

### TR320 Fillet rules [Medium]

1. Already built: the fillet assistant picks all convex or all concave edges of the part or a feature.
2. Fillet rules that find edges again after changes: edges against the earlier body, edges of a feature, free edges, or edges parallel to an axis, with exclusions and a radius per rule. FDCAD's fillet assistant (Add Convex Edges and Add Concave Edges on a whole part or feature) already covers the first case; rules with exclusions are new.

### TR321 Chamfer corners [Low]

1. Where three chamfers meet: corner as chamfer, mitre or blend, with or without a setback.

### TR322 Shell both sides and minimum thickness [Low]

1. Shell gets Both Sides (half the wall inside, half outside), and an approximate mode that keeps the wall Never Thinner or Never Thicker than the value.

### TR323 More draft options [Medium]

1. A second angle on the other side of the neutral plane, angles measured absolute or relative, and a Fixed Edge type that keeps one edge and adds faces where needed.

### TR324 Size gradient pattern on a face [Medium]

1. Fill a face with shapes (circle, hexagon, square, custom sketch) in grid, hexagon, circular or radial layouts, whose size changes between two limits across the face (by distance from a point or edge), with a clear border. Used for decorative and lightening patterns.

### TR325 Landing pad on a sloped wall [Medium]

1. Rest: a flat pad pressed into or raised from a sloped or curved wall, with its own wall, clearance, draft and extent to a face. Used for screw bosses on curved housings.

### TR326 Presets for any panel [Medium]

1. Any feature panel can save its settings as a named preset, apply it, set it as the default (current, last used or factory), rename and sort. The Hole Tool already has favourites (TR66).

### TR327 User thread tables [Medium]

1. A user editable thread table (type, size, pitch, class, tap drill) for Cosmetic Thread, Thread and the Hole Tool, loaded from a file. Thread remembers the last size, and Repeat applies the same thread to another cylinder.

### TR328 Seed and boundary pick [Medium]

1. Pick boundary faces or edges and one seed face: every face between them is picked. Used for whole pockets and regions of imported parts.

### TR329 More pick tools [Low]

1. Pick everything inside, outside or touching a box, cylinder or sphere sized with handles. Paint pick by dragging over faces. A quick priority switch: bodies only, faces only, edges only.

### TR330 Engraved marks [Low]

1. A Mark feature puts text or lines onto a face as marks with no depth (or a small depth), written to their own layer in the flat pattern DXF, for laser etching part numbers.

### TR331 Configuration rules and test values [Medium]

1. Rules in the configuration table: "if Width is over a value, Depth comes from this list". Rules run top to bottom, can be turned off, and apply wherever the value is edited.
2. One choice can set several columns at once (a theme: material, colour, sheet metal values).
3. Try a set of values without adding a row.

### TR332 Sheet metal rule library [Medium]

1. Named sheet metal rules (material, thickness, radius, reliefs, unfold rule, gaps) saved to a shared file and picked per part, with a per feature override tick.

### TR333 Set the current view as front or home [Low]

1. Set the current camera as the Front view (or any standard view) or as Home, without moving geometry, with Reset.

### TR334 Extrude picks the operation [Low]

1. An option where Extrude chooses Boss, Cut or New Body from where the sketch sits, shown in the panel and changeable, with Alternate Solution when the end face is unclear.

### TR335 Show more sketch items [Low]

1. Toggles for shading closed regions and showing sketch points.

### TR336 3D print export preview [Low]

1. Mesh export can preview the mesh before saving and refine by maximum edge length and aspect ratio, and can write OBJ. Adds to TR182.

## 18. Fourth round and later items (TR337 to TR420)

### TR337 Signed distances in sketches [High]

1. A horizontal or vertical distance can be signed: its sign fixes which side of the reference the point lies, so a fully defined sketch cannot flip to a mirror solution when values change. Negative values flip the side on purpose. Many open tool users ask for this.

### TR338 Warn when a sketch jumps to another solution [Medium]

1. When an edit or drag makes the solver land on a different valid solution (mirror image, inside out), the status bar warns and offers Undo, and a Keep This Side lock can be added to the item that flipped.

### TR339 Construction geometry after the sketch is closed [Medium]

1. A closed sketch's construction lines and points can be shown in the part (a tick per sketch) and picked by later sketches and features as references.

### TR340 Detach linked geometry [Medium]

1. Converted or projected entities that follow model edges can be detached into free geometry with the same shape, keeping their dimensions, so the sketch no longer depends on the model.

### TR341 Small sketch display aids [Low]

1. Open end points of profiles are marked live while drawing, before a feature fails.
2. A direction arrow on lines and chains when it matters (offset side, chain order).
3. A faint extension of a line while a point on line or tangent relation is shown.
4. Separate show and hide for each kind of relation tag, driving and reference dimensions, and a tag size apart from text size.
5. Line weight, point marker size and dimension text size scale with the display scale and a user setting, so thin lines stay visible on very high resolution screens.

### TR342 Limits and segment relations [Low, owner decision]

1. A dimension can be a minimum or a maximum instead of an exact value (the solver keeps the value within the limit). Needs solver support.
2. Point on segment: the point stays on the part of a line between its ends, not on the infinite line.

### TR343 Move the part origin [Medium]

1. Move or turn the part's origin and main planes to a picked point, face, box centre or the centre of the bodies, for imported parts far from the origin. Geometry stays where it is in the world; all features keep their references.

### TR344 Fit offset on a boss or cut [Medium]

1. Extruded Boss and Cut get a signed profile offset (grow or shrink the profile by a value, often a print fit variable), so one sketch can make both mating parts.

### TR345 Counts of zero and one [Medium]

1. A pattern count of one builds the seed only, and a count of zero or a suppressed result leaves the body unchanged with a note, instead of an error, so size families in configurations and design tables work.

### TR346 Fillet failure help [Medium]

1. When a multi edge fillet or chamfer fails, besides skipping edges (built), fix buttons try other ways: per loop, in smaller groups, larger radius first, or splitting it into several features.
2. Every failing fillet, chamfer, shell or offset names the failing edge or face and the likely cause (radius larger than a neighbour face, wall too thin, curvature too tight), never a bare "operation failed".

### TR347 Simplify threads while editing [Medium]

1. A part setting and a global setting: modelled threads show as cosmetic while editing, and are made real only for export, print preparation and a full rebuild. Saves rebuild time on parts with many threads.

### TR348 Timing pulley and belt profiles [Medium]

1. Pulley tooth profiles for the common timing belt kinds and a gear root fillet. Extends TR161.

### TR349 Thickness at a point [Medium]

1. Measure gets Thickness at Point: click a face and get the wall thickness along the inward normal at that spot. Measuring never marks the part as changed. Measure from the origin, and change the unit of a result on the fly.

### TR350 Number display [Low]

1. Show inch values as fractions (to a chosen denominator) as well as decimals. FDCAD reads fractions today but shows decimals.
2. A rounding rule for shown values (half away from zero, half to even, truncate), and a decimal separator that follows the system or a chosen symbol.

### TR351 Find typed values that should be linked [Medium]

1. The model health report (TR286) lists dimensions whose typed number equals a variable's value but is not linked to it, and pattern counts typed by hand next to a count variable, with a Link to Variable button.

### TR352 Mark results that did not rebuild [Medium]

1. When a feature fails, every later feature is marked Not Rebuilt and the body volume and Measure results are shown as stale, so an old shape is never taken as valid.

### TR353 Point where a line meets a curved face [Low]

1. A reference point where an axis, line or curve crosses a cylinder, cone or other curved face (several points if it crosses more than once).

### TR354 Shortcuts with an input method on [Low]

1. Single letter shortcuts still work when an input method (for example a Japanese input method) is on, or the status bar says shortcuts are paused. Shortcuts can be bound by key position for non Latin layouts.

### TR355 Section view zones and transparency [Medium]

1. With two or three section planes, pick which zones are removed, so several separate areas can be cut away.
2. Chosen bodies can be shown see through in the section with a slider. Extends TR213.

### TR356 View only open [Low]

1. Open a part read only for viewing (turn, pan, zoom, measure); Edit switches to full editing.

### TR357 Twist lock joint [Low]

1. A bayonet joint helper for printed lids: lugs on one body and matching L shaped slots on the other, with a fit clearance.

### TR358 Guided calibration print [Low]

1. A fit calibration sample: several labelled test pieces with stepped offsets made from one configuration per step (label text linked to the value). The user measures the best piece and FDCAD stores that value in the fit variable (TR180). Shrink compensation scales outer sizes and pitches only, not fit features already tuned.

### TR359 Expected value checks [Medium]

1. A part can store target results with a tolerance: volume, bounding box size, face count, hole count, or a saved measurement (TR191). After each rebuild the status bar and a list show pass or fail. Uses volume and size only, so it needs no change to D6 or D29. Common in courses that grade by volume and in FDCAD's own golden results.

### TR360 Plane halfway between any two faces [Low]

1. Mid plane today needs parallel faces. For two faces that are not parallel, make the plane that bisects the angle between them.

### TR361 Diameter mode stays on in revolve sketches [Low]

1. After the first dimension past a centerline is placed as a diameter, later dimensions of lines parallel to that centerline stay in diameter mode until Esc. Today each later dimension must again be placed past the centerline to get a diameter.

### TR362 Weak automatic relations [Low, owner decision]

1. Relations added automatically while drawing are marked weak: a conflicting relation the user adds later replaces a weak one with a note, instead of making the sketch over defined. This may conflict with the solver wrapper rules, so the owner decides.

### TR363 Cable tie channels [Medium]

1. At each picked sketch point (and line end), cut a channel for a cable tie through or under a wall, with width, thickness and a support free bridge top.

### TR364 Half lap joints between crossing plates [Medium]

1. Two plates that cross get matching notches so they slot together, each notch half the height (or a typed percent), with kerf and fit clearance. TR246 covers plates meeting at an edge only. Mortise and tenon, and annular and ball snap joints may follow.

### TR365 Pattern at model points [Medium]

1. Copy a feature to picked vertices, circle centres or hole axes, or to every hole of a face, with the direction from the face normal, and no sketch.

### TR366 Pattern spacing laws [Low]

1. Linear and curve patterns get spacing laws besides even spacing: growing (geometric), a list of fractions along the length, per copy angles, and seeded random positions. Extends TR58 and TR59.

### TR367 Standard profiles [Low]

1. Sketch presets or a body of a given length for angle, channel, I beam, rectangular and round tube, T slot and V slot extrusions and DIN rail, sized from the published standards. For brackets and printed adapters; frames and weldments stay out of scope.

### TR368 Batch export over variable values [Medium]

1. Pick variables and a list or range for each; FDCAD rebuilds every combination in the background and exports each one (STEP, STL or 3MF) with a naming template, then reports any that failed. Extends TR196 and TR273.

### TR369 More export formats [Low]

1. IGES (pairs with TR31), the kernel's native BREP, glTF, and PLY. A 3D wireframe of edges or curves as 3D DXF.

### TR370 Sheet metal small additions [Low]

1. Extend a wall or flange to a typed distance, a plane or a face.
2. A row of short cuts along a line (a perforated fold line) for hand bending.

### TR371 Small body tools [Low]

1. Fragments: cut all picked bodies at every crossing and keep every piece.
2. Keep the volume covered by at least a number of the picked bodies.
3. Shear a body along an axis.
4. Geodesic sphere and dome by frequency.

### TR372 Shake test for sketches [Low]

1. Push all under defined points a little at random, solve, and show what moved, so the user sees the remaining freedom. A temporary Fix All Points lock for comparison.

### TR373 Array Along Curve orientation and offsets [Low]

1. Choose how copies turn (follow the curve, keep orientation, or stay square to a picked face), with a start offset and an end offset along the curve. Today there is only the Orient to Curve tick.

### TR374 Hyperbola and three expression curves [Low]

1. A partial hyperbola sketch curve. A 3D curve from x, y and z expressions of t, using the safe expression parser only (TR28 is 2D only).

### TR375 Mac Redo key [High, owner decision]

1. On a Mac the standard Redo key is Command, Shift and Z. In FDCAD that key runs Previous View (SHORTCUTS.md, Ctrl+Shift+Z), and Redo is Ctrl+Y (D19). Mac users who press the standard key get a view change instead of a redo. The owner decides whether Mac Redo takes Command, Shift and Z and Previous View moves.

### TR376 Mac menu roles and Window menu [High]

1. Set the menu roles for About, Preferences (Settings) and Quit explicitly, so they always land in the application menu on a Mac; today only About has one and Preferences relies on Qt's text guess.
2. A Window menu on the Mac with Minimize, Zoom, Bring All to Front and the list of open parts.
3. The title bar file icon (proxy icon) with its path menu, through the window's file path.

### TR377 Drop files on the window [High]

1. Dropping a part file, STEP or mesh file onto the main window opens or imports it, as on both platforms users expect. Today drops are handled only in the tree and the feature clipboard; double click and the Dock already open files.

### TR378 System contrast themes on Windows [High]

1. When Windows contrast themes are on, FDCAD switches to a theme that uses the system colours, and the four contrast themes are part of the screenshot tests. Today the themes follow light and dark only.

### TR379 Recent files in the system [Medium]

1. Add opened parts to the system recent list: the Dock menu on a Mac, the taskbar jump list on Windows (with a New Part task). Check whether the native file dialog already does part of this on Windows.
2. A second launch (double clicking a part while FDCAD runs) opens the part in the running window instead of a second copy.

### TR380 Platform small items [Low]

1. Trackpad rotate gesture rolls the view, smart zoom fits, swipe goes to the previous or next view (pinch and two finger scroll already work).
2. A Help key (F1, Command and question mark) opens the help for the active tool.
3. Select All.
4. Taskbar and Dock progress for long rebuilds, exports and slicing.
5. A check of default keys against Windows rules (no Ctrl and Alt pairs because of AltGr, no Windows key, no clash between Alt and a letter and menu access keys), and of whether Quit and Force Rebuild share Ctrl+Q on Windows (unverified).

### TR381 3MF that slicers understand [High]

1. Today FDCAD writes colour as a display colour per body and per triangle. The common slicers ignore it: one family reads only a colour group per object (and maps each distinct colour to a filament), another reads no colour, another ignores display colours. Write a colour group colour per body so those slicers give one filament per body; keep per face colours for viewers.
2. Write the bodies as components of one assembly object, with a transform per item, so a slicer keeps them together as parts of one object.
3. Write the print orientation as the item transform instead of baking it into the vertices, and keep face colours when an orientation is set (today they are dropped).
4. A thumbnail picture in the package.
5. Check every export against the public 3MF schema and the consortium's conformance files (BSD licensed) in CI.

### TR382 Body roles for printing [High, owner decision]

1. A body can be marked as Part (default), Modifier, Negative Volume, Support Blocker or Support Enforcer. Marked bodies are written in the forms the main slicers read (one family through metadata keys on the object, another through its model settings file), and are not printed as parts. A status line says what each target keeps or drops.
2. Do not write the 3MF support or surface object types; slicers drop them.

#### TR382 file forms (added 2026-11-04)

These are file format facts for interoperability. Key names, file names and values below must be written exactly as given. Each role is written per body. Every body of one FDCAD part goes into one slicer object.

Slicer families:

1. Family P is PrusaSlicer. Family B is Bambu Studio and OrcaSlicer. Family C is Cura.
2. Family P and family B need different object layouts in `3D/3dmodel.model`. One file cannot carry working roles for both. So Export 3MF gets a choice "Slicer" with two values: "Bambu Studio, OrcaSlicer or Cura" (default) and "PrusaSlicer". When no body has a role other than Part, the choice only changes the layout (items 3 and 13).

Form B (default choice): assembly layout plus `Metadata/model_settings.config`, plus Cura metadata:

3. Layout: as TR381 item 2. Each body is its own mesh object. One assembly object holds one `<component>` per body, with the body's placement as the component `transform`. The build `<item>` points at the assembly object.
4. Write the file `Metadata/model_settings.config`. Root element `<config>`. Inside it, one `<object>` element per assembly object. Its `id` attribute is the id of the assembly object (the object the build item points at).
5. Inside that `<object>`, write `<metadata key="name" value="..."/>` with the part name. Then one `<part>` element per body, in the same order as the components.
6. Each `<part>` has `id` set to the mesh object id that its component points at (the component `objectid`), and `subtype` set to the role value:
   1. Part: `normal_part`
   2. Modifier: `modifier_part`
   3. Negative Volume: `negative_part`
   4. Support Enforcer: `support_enforcer`
   5. Support Blocker: `support_blocker`
7. Inside each `<part>`, write `<metadata key="name" value="..."/>` with the body name. Write no other keys in this file. Family B treats unknown keys as print settings. Do not write a `matrix` key: family B takes the body placement from the component transform. Do not write `firstid` or `lastid` on `<part>`: current family B releases do not use triangle ranges.
8. Family B tells its own files apart by the `Application` metadata in `3D/3dmodel.model`. FDCAD writes its own name there. It must never start with `BambuStudio-` or `OrcaSlicer-` and must never contain `PrusaSlicer`. A file that is not marked as its own is still read with its `model_settings.config` by family B.
9. Family C reads roles as settings on each mesh object. On the `<model>` element declare `xmlns:cura="http://software.ultimaker.com/xml/cura/3mf/2015/10"`. On the mesh object of a marked body write a `<metadatagroup>` with one `<metadata>` element. Its `name` is the setting name with the `cura:` prefix, its text is `True`, and it has `preserve="true"`. Setting names:
   1. Modifier: `cura:infill_mesh`
   2. Support Enforcer: `cura:support_mesh`
   3. Support Blocker: `cura:anti_overhang_mesh`
   4. Negative Volume: `cura:anti_overhang_mesh` (see item 10)
   5. Part: write nothing.
10. Family C has no negative volume. A Cura anti overhang mesh is never printed. So a Negative Volume body is marked as one: Cura does not print the body, but the part prints without the cut. The status line says so.
11. Family C ignores both `.config` files. Family B and family P ignore the `cura:` metadata. Writing the Cura metadata in a form B file is safe.
12. Minimal form B example, one part and one negative volume (vertices and triangles left out):

```xml
<!-- 3D/3dmodel.model -->
<model unit="millimeter" xml:lang="en-US"
       xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
       xmlns:cura="http://software.ultimaker.com/xml/cura/3mf/2015/10">
  <metadata name="Application">FDCAD-1.1</metadata>
  <resources>
    <object id="1" type="model" name="Plate">
      <mesh>...</mesh>
    </object>
    <object id="2" type="model" name="Slot cutter">
      <metadatagroup>
        <metadata name="cura:anti_overhang_mesh" preserve="true">True</metadata>
      </metadatagroup>
      <mesh>...</mesh>
    </object>
    <object id="3" type="model" name="Plate assembly">
      <components>
        <component objectid="1" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>
        <component objectid="2" transform="1 0 0 0 1 0 0 0 1 12 0 3"/>
      </components>
    </object>
  </resources>
  <build>
    <item objectid="3" transform="1 0 0 0 1 0 0 0 1 90 90 0"/>
  </build>
</model>

<!-- Metadata/model_settings.config -->
<?xml version="1.0" encoding="UTF-8"?>
<config>
  <object id="3">
    <metadata key="name" value="Plate assembly"/>
    <part id="1" subtype="normal_part">
      <metadata key="name" value="Plate"/>
    </part>
    <part id="2" subtype="negative_part">
      <metadata key="name" value="Slot cutter"/>
    </part>
  </object>
</config>
```

Form P ("PrusaSlicer" choice): one mesh object plus `Metadata/Slic3r_PE_model.config`:

13. Layout: all bodies of the part go into one mesh object. Its vertex list is body 1's vertices, then body 2's, and so on, each as one unbroken block. Its triangle list is body 1's triangles, then body 2's, in the same order. Vertices are in the object's own coordinates, with each body's placement already applied. The build `<item>` points at this object and carries the print orientation. Family P reads an assembly as separate objects, which is why this layout is needed. Per triangle colours stay as they are.
14. Write the file `Metadata/Slic3r_PE_model.config`. Root element `<config>`. One `<object>` element per mesh object, with `id` set to the mesh object's id and `instances_count` set to the number of build items that use it.
15. Inside `<object>`, write `<metadata type="object" key="name" value="..."/>`. Then one `<volume>` element per body, in triangle order. `firstid` is the index of the body's first triangle and `lastid` the index of its last triangle, both counted from 0 in the object's triangle list, both inclusive. The ranges cover every triangle with no gaps or overlaps.
16. Inside each `<volume>` write two metadata elements, each with `type="volume"`: `key="name"` with the body name, and `key="volume_type"` with the role value:
   1. Part: `ModelPart`
   2. Modifier: `ParameterModifier`
   3. Negative Volume: `NegativeVolume`
   4. Support Enforcer: `SupportEnforcer`
   5. Support Blocker: `SupportBlocker`
17. The `type` attribute must be exactly `object` or `volume`. Any other value makes family P reject the whole file. Write no other keys: family P treats unknown keys as print settings. Do not write `matrix`, `source_file` or mesh repair statistics; they are optional. Do not write the `slic3rpe:Version3mf` metadata: FDCAD does not claim to be a family P file.
18. Family B does not read `Slic3r_PE_model.config` unless the file says PrusaSlicer made it, which FDCAD never does. So in a form P file family B and family C see one object with all bodies merged into one solid part. The status line warns of this.
19. Minimal form P example, one part (triangles 0 to 11) and one negative volume (triangles 12 to 23):

```xml
<!-- 3D/3dmodel.model -->
<model unit="millimeter" xml:lang="en-US"
       xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
  <metadata name="Application">FDCAD-1.1</metadata>
  <resources>
    <object id="1" type="model" name="Plate">
      <mesh>
        <vertices>...plate vertices 0 to 7, then cutter vertices 8 to 15...</vertices>
        <triangles>...plate triangles 0 to 11, then cutter triangles 12 to 23...</triangles>
      </mesh>
    </object>
  </resources>
  <build>
    <item objectid="1" transform="1 0 0 0 1 0 0 0 1 90 90 0"/>
  </build>
</model>

<!-- Metadata/Slic3r_PE_model.config -->
<?xml version="1.0" encoding="UTF-8"?>
<config>
  <object id="1" instances_count="1">
    <metadata type="object" key="name" value="Plate"/>
    <volume firstid="0" lastid="11">
      <metadata type="volume" key="name" value="Plate"/>
      <metadata type="volume" key="volume_type" value="ModelPart"/>
    </volume>
    <volume firstid="12" lastid="23">
      <metadata type="volume" key="name" value="Slot cutter"/>
      <metadata type="volume" key="volume_type" value="NegativeVolume"/>
    </volume>
  </object>
</config>
```

Unknown values and mismatches (why the rules above are strict):

20. Family P and family B both read an unknown role value as a normal part. The body then prints. FDCAD only writes the values listed above.
21. In family B, a component with no matching `<part>` loads as a normal part, and a `<part>` whose `id` matches no component is ignored. A config `<object>` whose `id` matches no assembly object is ignored, so every body loads as a normal part.
22. In family P, a triangle range outside the mesh fails the load. Triangles outside every range are dropped.
23. Family C ignores metadata names it does not know. A body with no recognised setting loads as a normal model.

Status line:

24. After export, one line per family states what it keeps. With the default choice: "Bambu Studio, OrcaSlicer: all roles kept. Cura: modifier, support enforcer and support blocker kept; negative volume not cut, body not printed. PrusaSlicer: roles dropped, bodies load as separate objects and all print; export with Slicer set to PrusaSlicer." With the PrusaSlicer choice: "PrusaSlicer: all roles kept. Bambu Studio, OrcaSlicer, Cura: roles dropped, all bodies merged and printed."
25. Generic 3MF viewers see marked bodies as plain meshes. The status line need not mention them.
26. Cura's support mesh is printed as support material in the body's shape. That is close to, but not the same as, the support enforcer of the other families. Help text says so.

### TR383 Per body print settings [Medium, owner decision]

1. An optional table on a body: layer height, wall count, infill density and pattern, supports on or off, extruder number, written for the slicers that read them. FDCAD must not also change geometry for things slicers already compensate (hole shrink, first layer spread), or the effect doubles.

### TR384 Settings by height [Medium, owner decision]

1. A part level list of Z heights, each with a setting change or a pause or colour change, written to the slicer files that support it. Covers inserting magnets or nuts mid print (R2 pause marker).

### TR385 Slicer target choice [Medium, owner decision]

1. The export panel and Open in Slicer get a target: plain 3MF, or one of the main slicer families, each with what it supports. Some slicer project formats are private and change between versions, so each target needs a test with the real program before release.

### TR386 Read slicer 3MF files [Medium]

1. Import a 3MF that uses components (IDEAS item 7) and the slicer parts layout, as named bodies, optionally keeping modifier and negative roles (TR382).

### TR387 Switch a feature between boss and cut [Medium]

1. An existing extrude, revolve, sweep or loft can be switched between Boss and Cut, or to and from Thin, keeping its sketch, end conditions and references. Boss and Cut are separate commands today.

### TR388 Fill cavities and simplify [Low]

1. Fill picked holes, pockets and voids, or every feature smaller than a size, to make a simpler body for export or sharing. Delete Face covers single faces today.

### TR389 Sketch layers [Low]

1. Named sets of sketch curves with their own colour, line style and visibility, solved as one sketch.

### TR390 Lattice fill as a feature [Low]

1. Fill a body or region with a gyroid, honeycomb or diamond lattice with a wall thickness, as a feature. The node editor already has Voronoi cells and a strut lattice; this adds gyroid and a direct command.

### TR391 Offset corner style [Medium]

1. Sketch Offset gets a corner choice for outward offsets of closed chains: Sharp (edges extended to meet) or Round (arcs). Today Offset has Cap Ends and Both Directions only.

### TR392 Part notes [Low]

1. A free text page stored in the part (headings, lists, links, simple tables) for notes such as how to drive the variables. Plain text only; nothing in it ever runs (CLAUDE.md section 5 item 10), and links are shown as text only, never opened over the network.

### TR393 Thread class on holes and threads [Low]

1. A tapped hole or modelled thread carries a tolerance class (metric and inch classes), shown in the hole list (TR316), and can set the allowance of a modelled thread. Extends TR252.

### TR394 Fillet pieces and transitions [Medium]

1. When a fillet chain breaks into pieces, list them as Included, Excluded or Edited; exclude a piece, or drag its end to trim or extend it.
2. Where fillets meet, show the transition on hover and let the user choose it: stop at a reference, continue past a sharp edge, sharp intersection, corner sphere or patch.
3. Corner Chamfer: pick one vertex and type a distance along each of its three edges.

### TR395 Snap a value to a point [Medium]

1. While dragging a distance handle (fillet, chamfer, hole position, depth), a key held snaps it to a vertex or point, and the value then follows that point when the model changes.

### TR396 Section sizes along a sweep [Medium]

1. A profile dimension can be a formula of the position along the path, from 0 at the start to 1 at the end (for example a width that grows along the path). Extends TR241, which scales the whole profile.
2. More orientation and twist choices: normal to a projection direction, keep the section's Y axis on the face under the path, or a second path that sets the section's X axis. Extends TR55 and TR56.

### TR397 Radial hole placement and hole values in formulas [Medium]

1. Place a hole by a distance and an angle from an axis, with no sketch, and on a point or axis that is not square to the face.
2. Hole table values (diameter, depth, head sizes) are available as named values of the feature for formulas, and the number of holes a hole feature made.

### TR398 Patterns on curved faces and by region [Medium]

1. For fill, curve and point patterns on a curved face: spacing as projected, or mapped along the surface.
2. Suppress Region: skip every copy inside or outside a picked sketch region or face. TR270 skips by a box.
3. Fill spacing mode: from a spacing and an overall size, the whole count that fits.

### TR399 Patterns that follow other patterns [Medium]

1. Add to Pattern: add a later feature (for example a chamfer on each hole) so it repeats at every copy of an existing pattern.
2. A feature built on one copy of a pattern can follow the pattern's count and layout automatically.
3. A pattern check level: fast (copies are identical and do not touch other geometry) or full, chosen automatically where safe, as a speed lever.

### TR400 Partial success for multi item tools [Medium]

1. Delete Face, Hole and Move Face with many picks finish on the items they can and list the rest, as Fillet's skip button already does. Extends TR271 and TR278.

### TR401 Joint helpers between touching bodies [Medium]

1. Pick two touching bodies and a joint type; the mating cut is made in one body from the other, with a clearance: groove (dado), rabbet, mortise and tenon, dowel pair. Lower priority types: biscuit slot, pocket hole, mitre with spline slot, scarf. Extends TR364 (half laps) and TR246 (finger joints).

### TR402 Living hinge patterns [Medium]

1. A staggered slit pattern on a plate (slit length, spacing, bridge, row offset) so a flat part bends, for laser cut wood and plastic. A printed form: a V groove that leaves a thin skin, sized from the layer height and the fold angle.

### TR403 Crush ribs [Medium]

1. Wedge ribs inside a round hole or on a pin (count, width, height, length, tip round), so a press fit holds despite print variation.

### TR404 Hinge generator [Medium]

1. A knuckle hinge pair between two bodies: knuckle count, a hole for a pin, or a print in place form with cones whose angle follows the printer overhang limit, a clearance, and optional detent bumps. TR188 plans only a sample today.

### TR405 Seats on curved faces [Medium]

1. Copies of a seed body or cut placed over a cylinder, sphere or other curved face, each turned to the face normal and sunk into the face (studs, rivets, dimples). Extends TR398.

### TR406 Hose barbs and luer fittings [Low]

1. A hose barb (size, ring count) or a luer male or female fitting placed on a point or axis and joined to the part.

### TR407 Bolt circle shorthand [Low]

1. In the Hole Tool and sketch circular pattern, typing a count and a circle size together (for example "5x100") with a start angle places a hole group in one step.

### TR408 Hobby small items [Low]

1. Transition spiral curve between a line and an arc, for track and road pieces.
2. Stone seat and prongs for ring settings.
3. Sprue tree from a cup to picked points, for casting masters, and a kit frame of parts on a runner.
4. A pocket that follows a picked outline offset by a clearance, with a finger notch, for tool holders.

### TR409 Suction cups and floating islands [Medium]

1. In the chosen print orientation, find hollows that open toward the bed and would trap air or resin, with a count and a fix button (tilt the part, or add a drain hole).
2. List the local lowest points that start in mid air (islands that need support), mark them in the view, and add the count to the orientation ranking (TR301).

### TR410 Fix overhangs from the analysis [Medium]

1. Overhang Analysis offers a fix button that chamfers the underside edges up to a typed angle. A fillet on an edge facing the bed gets a warning that suggests a chamfer.

### TR411 Overlapping bodies on export [Medium]

1. When bodies overlap, export warns that the overlap prints twice and offers to join them, or lets the user set which body wins. Adds to TR382.

### TR412 Fit values by hole size and direction [Medium]

1. The print fit value (TR180) can be a small table by hole diameter band and by direction (flat on the bed or upright), with separate values for holes and outside sizes, and can depend on the nozzle size. Slicers already compensate some of this, so FDCAD shows which side applies it (TR383).

### TR413 Printer limits [Low]

1. The printer profile gets no print zones and a head clearance for printing parts one at a time; Build Volume and Arrange check them.

### TR414 Material interlock and base pad [Low]

1. Interlocking teeth at the boundary between two bodies printed in different materials.
2. A thin removable base pad body under the part with an air gap.

### TR415 Turn style and points from a file [Low]

1. A Navigation choice for how the view turns: free, turntable (the up axis stays vertical) or arcball.
2. Read X and Y rows from a text file as plain sketch points that can be dimensioned and used (TR61 makes curves, TR58 patterns).

### TR416 Add relations to existing geometry [Medium]

1. One command finds geometry that is nearly horizontal, vertical, parallel, perpendicular, tangent, equal, symmetric or coincident within a tolerance and offers the matching relations in a preview; the user accepts all or unticks some. Today relations are added only while drawing. Useful after Insert DXF and SVG (TR5, TR117).

### TR417 Text and yes or no variables [Medium]

1. Variables can hold text (for sketch text, labels and configuration names) or true and false, not only numbers. Each variable can have a note, and the list can be grouped. Extends TR54 and TR275.

### TR418 Dimension to midpoints [Low]

1. Distance and angle dimensions can pick the midpoint of a line, arc or part edge directly, without a point. Ticks turn end, middle and centre snaps off while dimensioning.

### TR419 Hide construction and group sketch items [Low]

1. One key hides and shows all construction geometry in the open sketch.
2. Group entities to pick, hide or lock them together, without making a block (TR34).

### TR420 Edge angle display and plane display [Low]

1. Colour edges by the angle between their two faces, with a threshold, to find sharp or nearly smooth edges before a fillet, draft or print.
2. Size all reference planes to the model in one command, and show plane names in the view.

## 19. Kernel risks in existing features (no new behaviour)

The kernel research (OCCT 8.0.1, the version FDCAD pins) found risks in features FDCAD already has. These are tests and guards, not new tools. The owner decides how to schedule them.

1. Sweep with a twist angle uses a kernel path (an auxiliary spine) that distorts the result in this kernel version (reported upstream in late October 2026, fixed on the kernel's main branch, not yet released). The existing sweep test checks a straight path by volume within 1 percent, which would not catch it, and no golden sample covers a twisted sweep (the twisted bar sample is the Twist deform). Add an exact case test and a golden sample. A probe of FDCAD's core confirmed it: the volume is wrong even at 0 degrees, by up to 5 percent at 70 mm, and any angle twist fails at 100 mm, all reported as OK (`docs/AUDIT_2026-11-02.md` section E).
2. Face merging after booleans can turn a valid body invalid in this version. It runs at about ten sites. Most are followed by the result check, but none falls back to the unmerged shape, and three sites (mesh import, the node editor geometry, sheet metal) have no later check. Add: check validity after merging and keep the unmerged shape if the merged one is invalid or the merge raises. A probe did not reproduce an invalid merge in 21 cases, but found a merge that raises an uncaught kernel failure and throws away a valid result.
3. A fillet on three edges at a loft corner can overflow the stack and kill the process, against CLAUDE.md section 5 item 7. A Python exception handler cannot catch a native stack overflow. Consider running fillets in a guarded worker process or pre checking that case.
4. Booleans and fillets can report success with a wrong result. Boolean results get only a not empty test today, and whole body validity is checked only after fillet and chamfer. A volume and validity sanity check after each operation would catch most cases and turn them into feature errors.
5. Fillet radius set through a smooth law function fails in this kernel build. FDCAD uses point tables and the two radius form, so it is already safe. Add a guard test so a future change does not switch to law functions.
6. The kernel has no conic, curvature continuous, two distance or elliptic fillet, no setback, and cannot stop tangent propagation (TR62, TR63, TR131). These need custom geometry or stay out. The guide curve mode for sweeps and lofts failed in the kernel probes (TR55); the new curve network surface in this version is a possible but unproven route.

## 20. Defects in existing features found by exercise walk throughs

Research agents walked classic exercises and printing workflows step by step against the phase1 code (read only, the app was not run). A separate page by page audit of the user guide against the code is in `docs/AUDIT_2026-11-02.md`. These are places where existing features do not do what the user guide, a decision or a common lesson expects. Each needs a quick check in the app before it is scheduled. They are bug reports for existing behaviour, not new tools.

1. [High] Hole Tool features cannot be picked as a pattern or mirror seed. The Items to Copy list shows only extrudes, revolves and features with an operation setting, so Hole, Rib, Dome, Wrap, Mounting Boss and thread features are left out. For Hole the core already supports patterning, so only the list filter blocks it; Rib, Dome, Wrap, Mounting Boss and thread features would also need core support (today they fail with "cannot be copied as a feature"). Patterning holes is the most common pattern exercise.
2. [High] Sweep paths, Pipe, Thin Feature and Rib keep only lines and arcs from a sketch chain. A spline or ellipse in the chain is dropped without a message (giving a shorter path), and a sketch with only a spline fails with an internal error. Cup handles, bottle necks and hoses need spline paths. Either support them or refuse with a clear message.
3. [High] A Reference Axis or an origin axis cannot be used as an axis (circular pattern, Move Face rotate, revolve): a feature pick is treated as a plane and the pick boxes accept only edges or faces. The user guide says an axis is handy for a circular pattern.
4. [Medium] Revolve does not accept a temporary axis (a round face), though the user guide and D693 say it can. The core accepts a face reference; only the UI pick handling is missing.
5. [Medium] Swept and Lofted Boss and Cut do not start a sketch first and do not use a sketch picked in the tree, though the guide says every tool on its page does. Fix the code or the guide.
6. [Medium] Swept Boss with Circular profile and Thin Feature ticked silently makes a solid rod: thin applies only to sketch profiles and the panel does not hide the thin group. Hide it or say so, and point to Pipe for tubes.
7. [Medium] Mirrored or patterned flanges and tabs block Flatten; the sheet metal type list has no mirror or pattern. The guide does not say so. Patterned cuts are fine.
8. [Medium] Polygon "Inscribed circle", the default, puts the corners on the construction circle, which is the opposite of the usual meaning. A hex nut drawn by the across flats size comes out too big. Rename the option or swap the default, and fix sketching.md.
9. [Low] Right clicking a face or edge offers no feature commands (Fillet, Chamfer, Extruded Cut, Hole Tool, Shell with the pick made). Picking first then running the command works.
10. [Low] Display units are mm or inch only; cm, m and ft are accepted when typed but a centimetre exercise shows mm.

A second walk through of 20 printing workflows found these (also read only):

11. [High] The 3MF writer puts the object name into the XML without escaping it. A part or tab title with "&" or "<" gives an invalid file, and FDCAD still reports success.
12. [High] Multi colour is lost in three export paths: Export 3MF with a print orientation set drops all colours, Open in Slicer never passes colours, and Save Bodies 3MF passes only the default colour. The user guide says 3MF keeps colours with no exception. (TR381 covers how slicers read colour.)
13. [High] Split for Printing pieces cannot be exported one by one: Save Bodies is only on the body Split panel; STL export writes all pieces in one file; Save Bodies STL ignores the print orientation, though the guide says STL follows Lay Face Flat.
14. [High] One print orientation for the whole part: after a split, Lay Face Flat turns and centres all pieces together, so pieces can land off the bed while Build Volume (which checks per body) says each fits. Split's automatic cuts use model axes while Build Volume uses the laid orientation. A per body orientation is needed.
15. [High] Modelled Thread has no clearance: both cut and added threads are the nominal sharp profile, so a printed cap and bottle of the same size will not turn (TR178 adds the fit).
16. [High, docs] Twelve tutorials and evaluate.md say Print Estimate, Build Volume and Draft Analysis are on the Evaluate tab; split-with-pins.md puts Split for Printing on the Features tab. In the code they are on the 3D Print tab.
17. [Medium] Split for Printing ignores the active printer profile: a fixed build size and a fixed clearance, with a stale code comment that profiles do not exist yet.
18. [Medium] Print fit defaults are fixed values in several features and mean different things: Lip and Groove spacing is the total gap, Split clearance is per side, the profile's fit tolerance is per side and only the Hole Tool and Move and Offset Face read it. Hole Tool Print Fit defaults to None, and clearance on a heat set insert is allowed with no hint.
19. [Medium] Mounting Boss has no height up to a face (Snap Hook has one), so a standoff for an imported board needs a typed height.
20. [Medium] Scale leaves an unconverted reference mesh unscaled with no message when solids exist; STL and OBJ are always read as mm with no prompt; the 3MF reader finds no triangles in files that use components or separate object files (slicer projects).
21. [Medium] DXF export of faces and sketches drops sketch text and any curve that fails, with no message; splines and ellipses become open polylines that are not joined into loops; everything is on layer 0.
22. [Low, docs] The strut lattice also stops hard at a large count, which node-editor.md does not say; Wall Thickness flags living hinge webs because its limit is the profile's minimum wall.

## 21. Robustness tests suggested by other tools' bug trackers (no new behaviour)

Common bug classes in open source CAD trackers. Each is a test FDCAD should have. The owner decides when to add them.

1. Naming: change every dimension of every sample part by a tiny amount and by about ten percent; later fillets, chamfers, face sketches and holes must keep their references or raise a lost reference error. Check that every feature kind, including revolve and pipe, returns a naming map.
2. Fillet and chamfer on one edge, on all edges, per loop and per face; no dent on untouched edges; error names the edge when the radius is too large.
3. A kernel failure on a re run after an earlier failure must be a feature error, not a crash. Pattern counts 0, 1, 2, 9, 10, 11 and 100.
4. Sketch solver branch: sweep a dimension through a wide range and assert the solution stays on one branch; dragging a fully defined sketch must not flip it. Coincident and zero distance must give the same status.
5. Closed profile detection: a spline ending on a line with a tiny gap, profiles from model edges, a revolve profile touching the axis.
6. Symmetric, mid plane and draft options with reverse on and off, on circles, rectangles and splines.
7. Booleans: stray faces, non manifold results, coincident internal faces; offsets from a thousandth to a millionth of a millimetre.
8. File compatibility: no value is reinterpreted on load; a golden test of volume and face count for files from every earlier phase (CLAUDE.md section 4 item 4 covers opening, this covers values).
9. Rebuild time and memory must not grow over a hundred repeated edits.
10. A failed save (disk full, write error half way) must leave the old file and backup intact: write to a temporary file, check it, then rename.
11. Sheet metal flats: a bend next to an inner corner, two flanges meeting at a right angle, and a flat outline made of lines and arcs only (no spline stand ins).
12. Loft and sweep: loops started in a different order, profiles with holes, spline paths; a hang must be stoppable (TR126).
13. Shell on compound curved faces, with and without removed faces.
14. Hole Tool with 1, 4 and 50 points, threaded or not, on angled faces.
15. Dependents of a suppressed feature are marked, not silently rebuilt on a stale shape (TR352).
16. Every numeric field accepts a formula, a unit and decimals; names with spaces work in formulas where quoted.
17. Screenshot tests at 100, 150 and 200 percent display scale for selection and icons.
18. A sketch on every face of a cube and of a turned body is square to its face.
19. A two distance chamfer keeps one orientation on inner and outer rings.

## 22. Additions to existing items found in the third round

1. TR35: offer several candidate sets of dimensions and relations with a preview, and a datum point picked first.
2. TR36 and TR139: when a profile is bad, highlight the exact spot (for example a loop in an offset spline).
3. TR38: keep Redundant visible by default; research shows tools rarely show it and students misjudge full definition.
4. TR41: a curvature rate match relation (beyond tangent and equal curvature) exists in several tools; Bezier to Bezier same curvature relations in one open tool are a working example.
5. TR57: a negative margin lets a fill run past the face edge; fill on curved and multi face regions; inclusion by whole shape, centroid or base point.
6. TR62: rounding sized by cut length; a negative radius flares outward. The kernel lacks conic and curvature continuous fillets (section 19).
7. TR69: the kernel's oriented box gives an exact best fit box.
8. TR72: standard mounting hole patterns (motor faces, board stacks) as library content.
9. TR73: Mirror Part with Remove Original, for left and right versions.
10. TR74: plane offset to a picked vertex; plane along a path by proportional or absolute distance; plane through two points facing the camera.
11. TR79 to TR81: the kernel gives mass, centre, inertia, principal axes and section properties exactly; the item stays locked by D6 and D29. Robotics teams and certification sets ask for it.
12. TR85: a cavity with a clearance offset for pockets that hold components (boards, batteries).
13. TR87: rib and wall ratio checks feed TR298.
14. TR89: `pow`, `random` (seeded) and hyperbolic functions.
15. TR90: rules, themes and a test row (TR331).
16. TR94: rule based selections re run on use and combine (TR303).
17. TR98: Update Frozen and update for all configurations.
18. TR125: list the faces a failing feature lost and let the user pick a replacement for each; show the last good model beside the broken one.
19. TR126: the kernel can stop booleans, sewing and meshing through a progress object, but not fillets and chamfers.
20. TR128: Exclusive works through the kernel's cells builder; Clearance is an offset tool then a subtract.
21. TR129: corner joins Arc, Sharp or Tangent; open faces left out as in Shell.
22. TR143: hole positions from round edges of an inserted reference body; hole size from a picked circular edge.
23. TR150: compare gaps with the printer profile's clearance values; cut the overlap from a chosen body.
24. TR157: Revolved Cut also gets Flip Side for an open profile; open profiles that fill out to the body.
25. TR161: rack, bevel, worm, planetary sets from a ratio, herringbone, backlash and centre distance with phase for a mating gear.
26. TR163: a set of textures (bricks, diamonds, dots, hex grid, ribs, waves), tile size, inversion, and fading to zero at the ends.
27. TR166: flange width modes (full, symmetric, two offsets), height datum and bend position.
28. TR172: number of unique bend radii, standard gauge check, holes under the minimum size.
29. TR174: rolled and teardrop hems; corner overlap ratio.
30. TR178: lead in shapes and lengths at each end; print in place gaps at least twice the layer height.
31. TR182: a scale or shrink factor; one file per body; show the mesh deviation used.
32. TR187: a minimum wall of about four layers' line widths is a common rule (make it a profile value, not fixed).
33. TR213: section caps, include and exclude lists, overlap colour.
34. TR38: name the conflicting pair or subset and highlight it; list construction lines without dimensions as the cause of "not fully defined".
35. TR37 and TR118: Join Near Ends for projected and intersection curves that look joined but are not one chain, with a stated tolerance; show unjoined ends in another colour.
36. TR55 and TR56: Follow Helix for helical sweeps, so the profile does not turn about the path.
37. TR139: "turns touch each other" for helical sweeps with a profile as large as the pitch.
38. TR150: report the smallest distance as well as overlap volume; a small interference can hide in a volume test.
39. TR186: Convert to Solid takes a gap size that closes small holes, with a count of open edges first. Segment a mesh into flat and round regions before converting.
40. TR90: per column Unconfigure and Block Model Edits, swap rows and columns, and name rules for configurations.
41. TR166 and TR174: edge flange length measured to the tangent for bends over 90 degrees; jog end conditions and fixed projected length; closed corner coplanar faces and auto propagation.
42. TR71: transfer list (bodies, axes, planes, threads, sketches, properties, coordinate systems, dimensions, hole data, sheet metal values, material), a source configuration, insert several parts in a row, and placement by distances, angles or relations.
43. TR327: custom pitch and diameter in the Hole Tool, and constant pitch series.
44. TR178: separate clearance for external and internal threads.
45. TR183: a thumbnail in the 3MF file.
46. TR196 and TR280: export all bodies as separate files in one command is among the most requested items in one open tool.
47. TR217: templates can carry starter features and variables, not only settings (seed parts); an industry study found they cut modelling time a lot.
48. TR71 and TR154: Break Link at release, and a check that no live links remain.
49. TR286: also flag sketches on faces of features that change often instead of planes, positions offset from fillet faces, and features with no position dimension.
50. TR287: report how many dimensions or features must change per edit.
51. TR8: Nearest, Farthest and Centre can be changed on an existing dimension.
52. TR141: patterns of patterns are needed for the brush bristle lesson; the pick list must also list pattern features (section 20 item 1).
53. TR143: Hole Tool positions are plain X and Y numbers today, so "a set distance from an edge" needs a dimensioned sketch.
54. TR7: a flat path that crosses itself is refused (paper clip lesson).
55. TR161: ratchet and Geneva wheels, cycloid and lantern gears, pitch circle reference lines, and a choice of tooth root radius or undercut.
56. TR163: image height relief with base and maximum height, rounding to layer height, and flat or wrapped forms.
57. TR173: bend angle text and a mark at the middle of each bend in the DXF.
58. TR175: a teardrop corner on vertical holes to hide the slicer seam; double sided teardrops.
59. TR178, TR254 and TR256: size by threads per inch, two start threads, a start offset from the edge (negative gives a chamfer) and a smooth run out.
60. TR188: a storage bin sample with bin size in grid units, label shelf, scoop and dividers, made with variables.
61. TR246: kerf as an input, screw and nut plate joints, and a box generator.
62. TR255: ribs inside a plain hole for screws that form threads in plastic, as an option.
63. TR258: a slope per edge for the roof.
64. TR287: rank features by how fragile they are.
65. TR301: nest flat parts on a stock sheet as well as on the print bed.
66. TR184: write the inlay and base as parts of one object, each with a colour group colour so slicers map them to filaments; a display colour alone does nothing there.
67. TR189 and TR176: seam helper bodies and brim ear points are also slicer data FDCAD could write (Low).
68. TR343: reset the origin to the centre of the bodies; the most voted origin request in one open tool.
69. TR74: a plane between two faces at a ratio, not only half way.
70. TR194 and TR310: decimals per variable.
71. TR224: keys to step through edge pick candidates.
72. Check: whether Combine keeps face colours through booleans (users of another tool ask for it).
73. TR178 and TR254, kernel advice: thread sweeps fail when the core cylinder is exactly tangent to the thread root, when the helix starts on the cylinder's seam, and with many turns in one boolean. Make the core slightly smaller than the root, start off the seam, or build a short thread and pattern it.
74. TR137: corner rule at sharp path corners for plain Swept Boss (transformed, mitre, round), as Pipe already has mitre.
75. TR173: include visible sketches in the flat pattern DXF, with a tick.
76. TR302: export presets and export in the background.
77. TR365: patterns at every vertex of a body or face also appear in three tutorial sources.
78. TR214: lower drawing quality while orbiting to hold a frame rate, then restore it.
79. TR231 and TR362: relations found by the tool (hints) versus kept relations, with a convert command; edits use only kept relations.
80. TR323: an All Normal Faces pick, split draft by a sketch curve, and propagation to tangent faces.
81. TR322: thin wall thickness inside, outside or both, and a different thickness per wall.
82. TR139: name sweep failure causes (path crosses itself, a bend radius smaller than the profile) and thin wall failures ("pick more end faces").
83. TR286: warn when a fillet comes before a draft on the same faces (the round turns conical).
84. TR246: one pick of all outside faces makes joints at every butting pair; inner or outer size input; dividers with half laps; sliding and hinged lids.
85. TR181: connector pins as separate printable bodies named with their size and clearance; clearance presets; split again until every piece fits the build volume.
86. TR198: editable size tables for ring sizes, bicycle and pipe fittings, wheel bolt patterns and model scales.
87. TR327: a left hand flag per thread.
88. TR300: SVG export with separate colours for cut and engrave lines, in millimetres, with hairline strokes.
89. TR161: a tooth thickness trim for printed gears and the theoretical centre distance shown beside a typed one.
90. TR172 and TR174: the flat length must not depend on the order flanges were added (test it); show the bend allowance or K factor in the flat pattern export.
91. TR173: remove duplicate overlapping lines before export so a laser does not cut twice.
92. TR186: mesh repair classes with counts (holes, flipped normals, duplicate triangles, internal walls between touching solids, small self crossings), run after cuts and booleans.
93. TR284 and TR189: when hollowing, keep regions thinner than twice the wall solid, use at least two drain holes square to the surface, and refuse a body that is not a valid solid with a message.
94. TR179 and TR384: a pocket for an insert at a pause must stay open up to the pause height; warn when a roof closes it earlier.
95. TR299: show how each wall prints as whole line widths, and flag walls between multiples or below the minimum.
96. TR338: a test that editing the only dimension of a sketch never moves the sketch as a whole.
97. TR346: Flatten names the feature that blocks it; fillet failure help lists the usual remedies.
98. TR57 and TR107: limit feature and sketch patterns to a boundary (a face, faces or a sketch region; whole shape, centroid or base point inside), with outside copies drawn faintly while editing.
99. TR59: type an irregular distance or angle for one or several copies.
100. TR346 and TR288: show the geometry that was tried when a fillet, boolean or shell fails, with the failed areas highlighted.
101. TR178 and TR180: thread clearance as a percent or an absolute value.
102. TR349: a readout of the distance between two parallel flat faces and the angle between two edges when they are picked; measure on section faces.
103. TR36: a profile inspector that shows which regions form and which gaps stop one.
104. TR54: live preview of sketch text while typing.
105. Lofted flange: sheet-metal.md lists swept flange and lofted bend as not built, and IDEAS item 5 records them; several tools have them. They stay with the owner (only developable shapes flatten exactly).

## 23. Additions to TR35 to TR100 found in the second round

1. TR55: a guide must touch every profile; the result stops at the shortest guide; any number of loft guides; sweep twist can follow a guide; the profile is placed on guides with Pierce (TR101).
2. TR57: two spacing modes per layout (target spacing with an even fit, or a count per ring); seed at a picked vertex or centred; a rotation per instance; the direction defaults to the longest straight edge; the count is read only until checked; the boundary can be a sketch, a face or coplanar faces; patterns across several faces are wanted for knurls and hex grids.
3. TR58: the text file has two columns separated by space, comma or tab.
4. TR60: silhouette split takes a draft angle; an open sketch must reach two edges; sketch text can be a split line; the new edges work with later fillets, chamfers, drafts and shells.
5. TR61: point numbers set the join order.
6. TR62: Chord Width, curvature continuous variable fillets, and Conic for asymmetric fillets.
7. TR63: a Minimal setback choice that uses the smallest working value.
8. TR67: point deform has fixed regions, three stiffness levels and an accuracy slider; curve to curve takes several curve pairs; surface push takes a picked body as the tool.
9. TR68: Indent needs one solid among target and tool and adds faces, unlike deform.
10. TR69: per body boxes, a cylindrical box aligned to a face, and directions that do not flip when sizes change.
11. TR71: insert a chosen configuration of the other part; choose bodies, sketches, planes and dimensions to bring in.
12. TR73: Mirror Part can stay linked to the original; sheet metal parts keep their bends.
13. TR76: No Bends applies to converted and Insert Bends parts.
14. TR77: stamps may cross bends.
15. TR78 (no material exists in the code yet, so these follow TR78 itself): a body can override the part material; material per configuration; the material can set the colour and the sheet metal values.
16. TR79: mass updates live as values change, follows the display decimals, and can be measured relative to a chosen coordinate system. Most practice sets ask for mass after a chain of value changes.
17. TR80: a centre of mass point can be dimensioned from.
18. TR82: values can come from dimensions and are per configuration.
19. TR85: offer a pour hole and a vent, and a parting plane that reaches past the block.
20. TR86: sensors on dimensions, measurements and volume, with a check every N rebuilds or saves.
21. TR87: wall thickness resolution set apart from part size.
22. TR90: comment, material and pattern skip columns.
23. TR91: the equation tick is in the delete dialog (TR201).
24. TR92: a small selection bar next to fillet and chamfer picks, with a tick to hide it.
25. TR94: a saved selection can be a rule (all concave edges, all faces of a feature) that runs again when the model changes; rules combine by union, subtract and intersect.
26. TR95: state words in the filter box (errors, suppressed, hidden) and tags.
27. TR98: frozen features are grey; an out of date frozen feature is flagged; Update Frozen.

## 24. Additions to the approved items TR1 to TR34

These add detail to items already approved in D683. They are not approved themselves. The owner decides whether each joins its TR item.

1. TR1: a Repeat button applies the same move, copy or stretch step again.
2. TR5: options to add the relations the drawing implies, merge points closer than a tolerance, map layers, and insert as a reference sketch that cannot be edited. TR117 adds SVG.
3. TR7: planes added inside the 3D sketch and switched by double click; a drag handle that moves geometry along an axis; dimensions along X, Y or Z.
4. TR11: an option that matches faces and edges of the new file to the old ones before reporting lost references.
5. TR12: gusset position by a reference line and point with an offset; profile by depth, or by leg lengths, or leg and angle; edge fillet and side draft. (Normal Cut is already built.)
6. TR14 and TR16: a saved view can also keep hidden items and the section; split view layouts can link zoom and pan between views.
7. TR23: selecting a folder highlights its features; suppressing a folder suppresses its contents; sub folders; Expand All and Collapse All.
8. TR24: copy the view image to the clipboard; JPEG as well as PNG; size and resolution.
9. TR27: show the source bodies see through or hidden; a threshold slider; a volume comparison.
10. TR31: Import repair: Repair Face, Delete Face, Repair Gap and Heal All; faces that are really planes or cylinders are simplified.
11. TR32: dimension names shown under values, and Show or Hide All Dimensions per feature.
12. TR34: nested blocks and Explode Block.

## 25. Out of scope (do not build)

These came up often in the material. They are outside PLAN.md section 2 or against CLAUDE.md rules.

1. Assemblies: mates, components, interference and collision checks, exploded views, motion, fasteners and standard parts libraries, large assembly modes.
2. Drawings: views, sections, detail views, dimensions on sheets, notes, parts lists, tolerance annotation, cut lists.
3. Simulation: stress, thermal, frequency, flow, plastics fill and warp.
4. Product data management and platform tools: vaults, pack and go, task schedulers, cloud properties.
5. Surfacing: surface sweep, loft, boundary, fill, knit, trim, extend, ruled, offset and thicken surfaces, freeform, style splines on surfaces, surface curves, shut off and parting surfaces for moulds.
6. Weldments: structural members, end caps, weld beads, cut lists.
7. Rendering and appearance: render engines, lights, scenes, cameras, textures, decals.
8. Scripts, macros and an API (CLAUDE.md section 5 item 10), cost estimation, design checkers, model based definition, inspection.
9. Reverse engineering: mesh to solid conversion, mesh face recognition, scan to model.
10. Smaller items judged not worth building: Silhouette defeature, Save as an older file version, hole series, a stud tool, Variable Pattern with a full dimension table beyond TR59, Cosmetic Pattern, Select Through Faces beyond TR64, dismissed message restore (only needed once "don't show again" prompts exist).

11. Seen in the second round and also out: blocks in layouts and mechanisms (beyond TR34), belt and chain sketches, cam path tools, pen and touch sketching, offset on surface, feature recognition on imported bodies, automatic feature reordering (it changes the tree without asking, against CLAUDE.md section 5 item 12), surface based mould tools (shut off and parting surfaces, side cores, cooling lines), cut lists, account and cloud sync, touch mode, macros, point clouds, scan to model, AI assistants, PMI in STEP, file formats of other commercial CAD tools, slicer side features (supports, infill patterns, variable layers).

## 26. Already in FDCAD (checked, no change)

The material also used these, and FDCAD already has them: rollback bar and Roll to End, Force Rebuild, the shortcut bar, mouse gestures, selection filters, Select Other, rename with F2, command search, Dynamic Mirror, Previous View, Zoom to Fit, feature copy and paste (TR9, built), the global variable, design table and equation suppression set; all extrude and revolve end and start conditions (extrude has no direction pick; see TR239), sweep twist by direction vector, thin with cap, selected regions; variable, face and full round fillets, partial fillet edges, all chamfer types, multi thickness shell, neutral, parting and step draft, rib, dome, wrap with emboss, deboss and scribe, geometry pattern, mirror options, Combine, Intersect, Split, Move and Copy Body, Scale; Hole Tool with slots, threads, Lip and Groove, Snap Hook, Vent, Mounting Boss; Array Along Curve (copies features and bodies, with Orient to Curve); sketch driven pattern; reference planes by offset, angle, three points, normal to curve, mid plane, parallel through a point, project onto a face and parallel to screen; reference point by coordinates; Helix and Spiral with variable pitch and taper, Projected, Composite and Contour Curves, Pipe, Curvature Graph; deform tools (Bend, Twist, Taper, Stretch, Flow Along Curve); sheet metal with Hem, Miter Flange, Jog, Closed Corner, Break Corner, Rip, Tab and Slot, Convert, Insert Bends, Cross Break, Unfold and Fold, Forming Tool, and corner relief types; Draft Analysis with undercut colours, Overhang Analysis, Geometry Check; slots, polygons, all rectangles, ellipse, partial ellipse; spline with curvature combs; all trim modes, extend, offset with caps; sketch picture with scale tool; sketch text with spacing, width and along-curve; reference dimensions; status colours; Edit Sketch Plane; configurations and design tables with CSV; an equation parser with `asin`, `acos`, `atan`, `atan2`, `floor` and `ceil`; Print Estimate with print materials; background rebuild that a new edit cancels, and a Cancel button for slow work; Hole Tool favourites with size carry over; sketch Select Chain; `if`, `and`, `or`, `not` and comparisons in expressions; partial fillet edges; instance numbering that keeps skipped numbers.

## 27. Consolidation notes for review

A separate review of the whole list found overlaps, conflicts and open points. Nothing below changes an item; it tells the owner and the implementer how to read them together. When an item is approved, read it with the items it is merged with here.

### 27.1 Merge these (keep the first number)

1. Fill patterns: TR57 with TR324 and TR398 item 3; cross reference TR245.
2. Varying patterns: TR59 with TR366 and section 22 item 99.
3. Hole placement without a sketch: TR143 with TR397 item 1 and TR407.
4. Conic curves: TR28 with TR52 item 1 and TR374 item 1.
5. Spline conversion: TR42 with TR115 item 4.
6. Nearest, Farthest and Centre on dimensions: TR8 with TR111 item 3.
7. Signed distances: TR337 with TR111 item 4 (one meaning for a negative value).
8. Relations for imported drawings: TR416 with section 24 item 2.
9. Fillet failure help: TR346 with TR271 item 1 and the fillet case of TR400; cross reference TR278.
10. Protecting edges from a fillet: TR64 item 1 with TR271 item 2.
11. Fillet and chamfer corners: TR63 with TR64 item 2 and TR394 item 2; TR321 with TR394 item 3.
12. Rounds on moved faces: TR259 with TR264 item 3. Rounded body offset: TR129 with TR258 item 2.
13. Bodies covered by a number of bodies: TR128 item 2 with TR371 item 2.
14. Geometry checks: TR262 with TR87 item 1. Thickness readouts: TR349 with TR87 item 2.
15. Value watching: TR86 with TR359 (one item, Medium).
16. 3MF thumbnail: TR381 with TR183 item 2. One file per body: TR280 with TR302 item 1 and the others that repeat it.
17. Drop a file on the window: TR377 with TR218 item 2 (High).
18. Section view extras: TR213 with TR355.
19. Before and after preview: TR289 with TR224 item 4. Select Through Faces: TR64 item 4 with TR224 item 1. Select by property: TR303 with TR94 item 2.
20. Per body transparency: approved TR21 with TR216. Display toggles: TR215 with TR335 and TR341 item 4.
21. Deleting dependents and their equations: TR201 with TR91.
22. Making the same feature again: TR206 item 1 with TR314.
23. Help for the active tool: TR291 with TR380 item 2; access keys: TR205 with TR380 item 5.
24. Threads: TR254 with TR145, TR256 and TR178 item 2; user tables: TR327 with TR144 item 4; keyways: TR248 with the keyway in TR247.
25. Drain holes: TR284 with TR189 item 3 and TR409 item 1.
26. Planes between faces: TR74 with TR360.
27. Sheet metal: TR282 with TR167; TR283 with TR77 (cross reference TR279).
28. Model health: TR286 with TR351; change test TR287 with its additions.
29. Fit values: TR180 with TR412. Gear tooth kinds: TR161 with TR348.
30. Layer aware checks: TR187 item 1 with the matching additions.
31. Boss or cut choice: TR334, TR387 and TR267 item 1 each change it; pick one design.
32. Profile scaling along a sweep: TR241 with TR396 item 1.
33. Joints: TR401 is the umbrella for TR364 and the joint parts of TR246.
34. Rebuild time savers: TR98 and TR276 together (the same owner question).
35. Edge angle display: TR199 item 2 with TR420 item 1. Linked copies: TR49 with TR122 item 2. Region limits for patterns: TR142 item 5 with TR398 item 2.

### 27.2 Conflicts to settle before building

1. TR126 (Esc stops a slow fillet) cannot stop fillets and chamfers in this kernel (section 19). Limit it to booleans, sewing and meshing, or stop between features.
2. TR62, TR63, TR394 item 2 and TR321 need fillet shapes the kernel lacks (section 19 item 6); like TR131 they are in effect owner decisions.
3. TR56 items 3 and 4, TR241 and TR396 build on the twisted sweep path that gives wrong volumes (section 19 item 1); fix that first.
4. TR346 (retry fillets in smaller groups) multiplies the crash risk in section 19 item 3; run retries in a guarded worker.
5. TR347 (cosmetic threads while editing) makes Measure, Print Estimate and Expected Value Checks disagree with the exported solid unless they always use the full threads.
6. TR345 (a count of 0 or 1 builds with a note) changes the current refusal; section 21 item 3 must test the chosen rule.
7. TR385 needs a test with the real slicer programs, which CI cannot run (CLAUDE.md section 9 item 8); keep it a manual release check.
8. TR399 item 3 (automatic pattern check level) must never change a result; default to the full check.

### 27.3 Scope and rule flags

1. Marked owner decision in this pass: TR382 to TR385 (they write slicer settings, near the slicer side out of scope list) and the key choices in TR210, TR211 and TR221.
2. Close to the out of scope list, for the owner to confirm: TR150 and TR268 (body interference and placing bodies by relations look like assembly tools, though they act on bodies of one part); TR186 mesh segmenting and TR260 fillet recognition (feature recognition); TR388 (defeaturing); TR295 to TR299 and TR286 (design checkers); TR46, TR306 and TR393 (tolerances); TR359 (inspection); TR77, TR279, TR283, TR166 item 2 and TR171 (sheet metal edge cases); TR229 item 2 and TR390 (near surfaces or very heavy geometry); TR71, TR72, TR154 and TR280 (links to other files).
3. Rule 5.12 (no geometry change without the user's click): TR119 (scale the sketch on the first dimension) and TR362 (weak relations replaced) must ask or show an undoable note; TR261 item 2 (a tolerance that makes near faces touch) must be an explicit option.
4. Rule 5.10 (files are data only): linked files and tables (TR25, TR71, TR72, TR198, TR274, TR331) read plain values only and use the safe parser for any formula.
5. Rule 5.8 (no network): the What's New list in TR291 is bundled with the app.
6. Rule 5.2 (no kernel work on the UI thread): hover readouts (TR87 item 2, TR199 item 1, TR200 item 3, TR349) need cached or background results.
7. Dependencies: TR311 needs a code encoder and TR381 item 5 uses consortium test files; each needs a DECISIONS.md entry with its licence.

### 27.4 Priority adjustments to consider

1. Raise to match their twins: TR218 item 2 (now in TR377), TR183 metadata (with TR381), TR363 (support free channel tops, as TR175), TR86 (with TR359), TR94 (with TR303).
2. Lower or explain: TR296, TR297 and TR244 are High though PLAN.md leans to printing; TR263 to TR265 are High though they are not first lesson steps (they are high value for imported parts).
3. Move TR310 (variable names read as units) to section 20 as a defect.
4. Bundles of unrelated small changes (TR111, TR115, TR142, TR174, TR341, TR371, TR408) can be approved line by line.

### 27.5 Names

Item titles are working names. Several match command names in commercial tools (for example Fully Define Sketch, Check Sketch for Feature, Pierce, Split Line, Fill Pattern, Table Driven Pattern, Replace Face, Indent, Sensors, Display States, Freeze Bar, Setback, Insert Part, Mirror Part, Show Sections, Goal Seek). Many are ordinary CAD words, but under CLAUDE.md section 10 item 2 the implementer chooses FDCAD's own label for each command when it is built, and records it in DECISIONS.md. None of the item text names a commercial product.

### 27.6 Points to define when an item is approved

Default tolerances ("small", "nearly") in TR36, TR37, TR262 and TR416; "one clear match" in TR38 and TR125; thresholds in TR286; FDCAD's own rule values in TR295 to TR299; the target for TR214; the order of solutions in TR264 item 2; rebuild order and cycles for TR190; the exact hint and announcement texts in TR290, TR291 and TR294; the conventions list in TR312; the shapes in TR330, TR409 and TR414.
