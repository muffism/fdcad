# Evaluate

The Evaluate tools measure the part, look inside it and check it before you print or share it. None of them change the geometry. Some show coloured overlays that go away when you turn the tool off.

Where to find it: the Evaluate command tab (Measure, Rebuild and Curves groups) and the 3D Print tab (Print, Print Analysis and Check groups); Tools, Measure and Tools, Rebuild Statistics; the View menu and the view toolbar for Section View.

## Measure

**Measure** shows sizes, distances and angles of the items you click. Its small box stays open while you use other tools.

1. Click **Measure** on the Evaluate tab, or choose Tools, Measure.
2. Click faces, edges or vertices in the view. Click an item again to remove it. Click empty space to clear all picks.
3. Read the results in the box. Click Copy beside a value to copy it.
4. Click Measure again, or close the box, to end the tool.

What it shows:

- One item: a vertex gives its point. An edge gives its length, and a round edge also gives radius, diameter and center. An edge between two faces also gives the angle across it along its length (largest, smallest and average): 0 where the faces meet smoothly, so you can see whether a blend is smooth all along. A face gives its area and perimeter, and a cylinder also gives radius and diameter.
- Two items: the minimum distance, dX, dY, dZ between the nearest points, and the angle between straight edges or flat faces.
- Two circles or arcs: center distance, plus the minimum or maximum distance.
- Three to six items: the smallest distance between any two, the total length of the edges and the total area of the faces.

Main options:

- Pin: keep the Measure box on top of the window.
- Pause: stop adding picks, so clicks in the view select as usual.
- Clear: remove every pick.
- Units and Decimals: for the box only. Part units is the default.
- Second unit: shows each length, area, volume and point again in millimetres or inches, in brackets. The copy button copies the first value only.
- Circles: Center to center, Minimum or Maximum.
- Show dX, dY, dZ.
- XYZ from: the Part origin or a coordinate system feature.
- Projected on: None, or a plane. A plane adds the projected distance, the normal distance and the projected area of flat faces.
- History: every measurement of this session.

Tips:

- Up to six items can be picked. The oldest pick drops out after that.
- Without the tool, the status bar shows common values of the selection.
- A rebuild clears the picks.

## Section View

**Section View** cuts the view open so you can see inside the part. It is display only: the part is not changed, and the section is saved only when you ask.

1. Click **Section View** on the view toolbar, the Evaluate tab, or the View menu.
2. Choose Front, Top or Right, a plane of the part, or the flat face you selected first.
3. Set the Offset, and Rotate X and Rotate Y if needed. Tick Reverse to cut away the other side.
4. Tick Section 2 and Section 3 to add more planes.
5. Click OK to keep the section on while you work. Click Cancel to turn it off.

If you start a feature, for example Fillet, while the Section View panel is still open, the panel closes as with OK: the section stays on and the feature's own panel shows.

Main options:

- Offset: moves the plane along its normal.
- Rotate X and Rotate Y: tilt the plane about its own axes.
- Reverse: flips which side is removed.
- Cap Color: the colour of the cut faces.
- Turn Section 1 about an axis: Section 1 turns about an axis, a round face or a straight edge by an Angle.
- Show section cap: off shows the inside as hollow.
- Keep cap color after closing.
- Zones to Cut Away: with two or three planes, tick each zone to remove, such as "In front of 1, behind 2". Several separate zones can go at once.
- Save with the part: keeps the section in the part file, so it is on when the part opens. Untick it and click OK to remove it.
- Save as Cut Feature: adds a Section Cut feature at the end of the tree that removes what the section hides, then turns the section view off. It is one undo step. The cut keeps the planes as they were when you clicked it, so it does not follow later changes to reference planes. Delete it and make it again to move it.
- See Through Bodies: tick bodies to draw them see through while the section is on, and set how see through with the slider.
- Bodies Cut: with two or more bodies, untick a body to keep it whole while the section cuts the others.

Tips:

- With two or three planes and no zone ticked, only the corner in front of all planes is cut away.
- Save View while a section is on keeps the section in that view. Going to the view turns the section on again.
- Run Section View again to turn the section off.
- Measure works on the cut faces: while a section is on, click a cut face or its edges with Measure open to get its area, lengths and distances.
- While a section is on, the feature tree shows a Section Planes folder with one row per plane. Click a plane to show its arrow and two rings in the 3D view: drag the arrow to move the plane and drag a ring to turn it about the plane's X or Y axis. Double click a plane, or right click it, to edit the section or turn it off.

## Rebuild Statistics

**Rebuild Statistics** shows how long each feature took in the last rebuild. Use it to find slow features.

1. Choose Tools, **Rebuild Statistics**, or click it in the Rebuild group of the Evaluate tab.
2. Read the table: Feature, Time (ms) and Last rebuild.

Tips:

- Last rebuild says Rebuilt or Reused from cache. FDCAD rebuilds only the features that changed and those after them.
- The summary line gives the total time and the memory in use.
- **Force Rebuild** (Ctrl+Q) rebuilds every feature, which is useful for comparing times.

## Model Health

**Model Health** (Evaluate tab, Rebuild group) gives advice on how the part is built. It never changes the part by itself.

It points out:

- sketches not tied to the origin or anything fixed, which can float when edited;
- level lines held by dimensions where a Horizontal or Vertical relation would do;
- features that use faces or edges made by a fillet or chamfer;
- fillets and chamfers early in the tree (select one and click **Move to End** if nothing after it needs it);
- cuts that remove nothing, and blind holes that came out through;
- features that keep their default names;
- three or more sketches with one circle of the same size, which one sketch and a pattern would do.

Click a row to select its feature in the tree. Click **Check** again after changes.

## Change Test

**Change Test** (Evaluate tab, Rebuild group) checks how far each value can change before the part breaks. It works on a copy: nothing in your part changes.

1. Choose the **Step** in percent and how many **Steps each way**.
2. Click **Run**. Each value typed as a number (feature values, sketch dimensions and global variables) is stepped up and down, and the copy is rebuilt each time.
3. Values that make a feature fail, or change how many faces the part has, are listed first, with the range that is safe and what went wrong. Click a row to select its feature in the tree.
4. Click **Stop** to end early.

Values set by a formula follow other values, so they are not stepped themselves.

## Curvature Graph

**Curvature Graph** draws curvature combs on edges and curves. See [curves.md](curves.md).

## Mass Properties

**Mass Properties** (Evaluate tab, beside Measure) shows the mass, volume, surface area, centre of mass, principal moments and axes, and the moments of inertia of the part.

1. Choose the command. The values show at once for the whole part.
2. To measure some bodies only, pick a face of each, choose **The picked bodies** and click **Calculate**. Tick **Include hidden bodies** to count hidden ones too.
3. Choose a **Material** (the list from Print Estimate), or type a **Density** in g/cm^3.
4. **Inertia about** gives the moments of inertia about the centre of mass, the part origin or a coordinate system.
5. Click **Copy** to put every value on the clipboard.

Values use the part's unit: millimetres and grams, or inches and pounds.

### Typed mass properties

For a part made of imported or simplified bodies, the measured values may not be the real ones. Click **Override** and type the **Mass**; tick **Type the centre of mass** or **Type the inertia about the centre of mass** to type those too (Ixx, Iyy, Izz and the products Ixy, Ixz, Iyz, in model axes). Without a typed inertia the measured one is scaled to the typed mass. Values that no real body could have are refused with a note. The typed values are saved in the part and used for **The whole part**; a **Typed values (Override)** row at the top marks them. **Clear Override** goes back to the measured values, and Undo works for both.

### Section properties

Choose **Section of the picked face or sketch** in **Bodies** to measure a flat shape instead of a solid. Pick one or more flat faces in one plane in the view, or select a sketch in the feature tree (its closed outlines are measured, holes taken out), then click **Calculate**. You get the area, the centroid, the second moments of area Ixx and Iyy about axes through the centroid along the plane's X and Y directions, their product Ixy, the polar moment J, and the principal moments with their axes and the angle from X to the first one. For a sketch, X and Y are the sketch's own axes. Density and **Inertia about** are not used. Copy works the same way.

## Interference Check

**Interference Check** (Evaluate tab, under Measure) finds bodies of a part that overlap, touch, or come closer than a gap you choose. Use it for parts printed in place, where moving pieces must keep a gap, and to check that split pieces fit.

1. Type the gap in **Report gaps under**. Tick **Count touching bodies** to list bodies that just touch too.
2. Untick any body in **Bodies** to leave it out.
3. Click **Check**. Each pair found is a row: an overlap with its volume, or a gap with its smallest size.
4. Click a row to see it: an overlap shows as a red see through volume, a gap as a line between the two closest points.
5. **Ignore Pair** takes the selected pair out of the list while the part is open.

## Compare Bodies

**Compare Bodies** (Evaluate tab, under Measure) shows how two bodies differ.

1. Choose the **First** body, and the **Second**: another body of the part, or **STEP file...** to compare with a file.
2. Click **Compare**.
3. The faces of the first body that changed turn red. What only the first body has shows see through in red, and what only the second has in blue. The window lists how many faces differ and both volumes.

Choose the command again to close it and give the part its own colours back. Nothing in the part changes.

## Zebra Stripes

**Zebra Stripes** (Evaluate tab, beside Curvature Graph) shows black and white stripes reflected in the faces, as if the part stood in a striped room. Turn the view to see them move.

- Where two faces join smoothly, the stripes run on unbroken.
- Where the faces meet at an angle, the stripes jump.
- Where the faces meet with no angle but a sudden change in curvature, the stripes bend sharply.

A small window sets the number of stripes and their direction. Choose the command again to turn the stripes off. They only change what you see: nothing is saved.

## Curvature Colors

**Curvature Colors** (Evaluate tab, Curves group) colours each face by how curved it is: blue for the least curved face shown, through green and yellow, to red for the most curved.

1. Click **Curvature Colors**. A small window opens.
2. Choose what to show: Largest curvature (one over the tightest radius), Mean curvature, or Gaussian curvature.
3. Read the scale: the values at its ends are the smallest and largest on the part.
4. Move the pointer over a face. Under the cursor shows the value there and the tightest radius, or "flat".

Tips:

- Planes, cylinders and spheres get their exact value. Other faces are sampled at a few points and take their most curved point, so a face shows where it is tightest.
- The colours are worked out again after each rebuild. Choose the command again to turn them off. Nothing is saved.

## Build Volume

**Build Volume** draws the printer bed and the build volume of the active printer profile under the part. It tells you whether the part fits.

1. Click **Build Volume** on the 3D Print tab, Print group. It stays on until you click it again.
2. Look at the overlay: green when the part fits, red when it does not.
3. Read the status bar. It gives the part's size on the bed, the build volume, and the axes that are too large.

Tips:

- The part is shown as it would print, using the orientation from **Lay Face Flat**. See [import-export-print.md](import-export-print.md).
- The check runs again after each rebuild, orientation change or tab change.

Common errors:

- "The part does not fit": lay another face flat, scale the part, or use **Split for Printing**.

## Overhang Analysis

**Overhang Analysis** colours faces that lean further than the printer can print without supports.

1. Click **Overhang Analysis** on the 3D Print tab, Print Analysis group. It stays on until you click it again.
2. Faces where nearly all the area overhangs are red. Faces where part of the area overhangs are orange.
3. Read the status bar for the counts.

Tips:

- The angle is the Overhang angle of the active printer profile. The default is 45 degrees.
- The build direction follows the print orientation, or +Z when none is set.
- Vertical walls never overhang. Faces on the bed never count.
- The colours are painted over the part's own colours and go away when you turn the tool off.

## Draft Analysis

**Draft Analysis** (3D Print tab, Check group) colours faces by how they release along a direction of pull. It stays on until you click it again.

1. Pick the direction in the small window: a plane, or a flat face with Use Selected Face. Reverse flips it.
2. Set the minimum angle (1 degree by default).
3. Green faces have at least the minimum angle of positive draft. Red faces have at least the minimum angle of negative draft (an undercut). Yellow faces need draft. Blue faces straddle: part of the face is positive and part negative.

The colours are not saved and never change the part.

## Wall Thickness Analysis

Turn on **Wall Thickness Analysis** in the 3D Print tab to see walls that are too thin to print. Faces on walls thinner than the active printer profile's minimum wall are painted purple, and pink where only part of the face is thin. The colours update after every rebuild and never change the part. Turn the command off to hide them.

To look for another thickness than the profile's minimum wall, type it in Preferences, Printing, **Wall analysis target** (0 uses the minimum wall). While the analysis is on, hold the cursor over the part: the status bar reads the wall under the cursor, for example "Wall here: 1.50 mm (target 0.8 mm)".

## Layer Preview

**Layer Preview** (3D Print tab, Check group, in the drop down with Enclosed Cavities and Edge Angle Analysis) draws a line on the part at every layer of the active printer profile, across the build direction of the print orientation, so you can see how small details, text and thin walls fall on the layers. Click it again to turn it off. A tall part with very many layers draws every few layers only and says so. On a part with free form faces, such as a loft or a thread, the lines are cut from the shaded mesh, so they show in under a second and follow the part as it is drawn. On other parts they are the exact cuts. When the part cannot be meshed, the status bar says "Layer Preview failed" and why, in place of the layer count.

## Print Estimate

**Print Estimate** gives the volume and weight of the part as a solid part estimate.

1. Click **Print Estimate** on the 3D Print tab, Print Analysis group.
2. Choose a Material. The Density fills in.
3. Read Bodies, Volume and Weight.

Tips:

- With faces, edges or vertices picked, only the bodies holding them are counted. Otherwise every body is.
- Volume shows in cm³ for millimetre parts and in³ for inch parts. Weight is in grams.
- At 100 % **Infill** the part is taken as fully solid. Set the slicer's infill percent and **Walls** (wall lines) to get closer to a real print: the walls, as thick as the printer profile's nozzle times the wall count, count as solid and the rest at the infill percent. The slicer still gives the real figure.
- Changing the density here changes that material in the preferences.
- The tutorials use Print Estimate to check your result against the sample files.

## Enclosed Cavities

**Enclosed Cavities** (3D Print tab, Check group) finds closed voids inside the bodies: spaces with no way out, which trap resin or powder when you print.

1. Choose the command. The voids are listed with their volume. Click one to see it.
2. Click **Add Drain Hole** to add a 3 mm hole from the nearest flat outside face into the void. It is an ordinary Hole feature: edit its size or place, or undo it.
3. Click **Find** again to check that no closed void is left.

**Cup Volume** gives how much a cup, bottle or tank holds. Pick its inside faces in the view, choose the **Opening** (the top of the picked faces, level with the Top Plane, or a plane of the part) and click **Cup Volume**.

## Geometry Check

**Geometry Check** finds faults in the bodies of the part: invalid faces, sliver faces, tiny edges and gaps.

1. Click **Geometry Check** on the 3D Print tab, Check group.
2. Wait for the list. It says "No problems found" or how many problems there are.
3. Click a row to highlight that face or edge in the view.
4. Click Check Again after a change.

Main options:

- Sliver width below: faces narrower than this are listed. The default is 0.01 mm.
- Tiny edge below: edges shorter than this are listed. The default is 0.01 mm.
- Bend radius below: tick it to list faces that bend tighter than the radius.
- Knife edge below: edges whose faces meet at less than this angle. The default is 5 degrees.
- Nearly smooth within: edges whose faces meet less than this angle short of smooth, which usually should be smooth. The default is 2 degrees.
- Nearly square within: edges between two flat faces that meet less than this angle off square, which usually should be square. The default is 1 degree.
- Duplicate faces (faces on top of each other) and inexact edges (the edge curve and its faces differ) are always listed.

Working through the list:

- Next and Back step through the findings and zoom to each. Tick **Clip around each finding** to hide everything outside a box round the finding while you step, so a finding inside the part can be seen. Untick it, or close the window, to see the whole part again. The view only clips with flat planes, so the clip is a box rather than a ball.
- Fix removes a sliver or duplicate face with a new Delete Face feature, as one undo step. On an edge with a gap or an inexact edge, Fix adds a **Heal Edges** feature: it refits the edge curves to their faces, cuts loose tolerances back to what the geometry needs and closes gaps up to its Tolerance (set a little over the gap). No face moves. If a wider gap is left, the feature warns with its size. On a nearly smooth or nearly square edge between two flat faces, Fix adds a **Move Face** that turns one of the faces about the edge by the small angle, so the edge becomes exactly smooth or exactly square. The face that leans off the X, Y and Z directions turns (the smaller one when both lean). Open edges and other findings have no fix; the message says what to change.
- Ignore hides a finding until the part is opened again.
- Symmetry Check: select a flat face in the view first. It says whether the part is the same on both sides of that face's plane, and lists the faces that differ.

Tips:

- Nothing is repaired until you click Fix. Each message says what to do.
- It checks imported STEP bodies too.
- The list shows at most 200 rows.
- Use it when a fillet or shell fails and you do not know why.

## Manufacturing Check

**Manufacturing Check** (Evaluate tab, Measure group) checks the part against the rules of a process. Nothing changes the part unless you click a fix.

1. Choose the **Process**. Its rules show in the table: change a value by typing in it.
2. Click **Check**. Click a finding to highlight its faces and edges.
3. For a sharp inside corner, **Add Corner Relief** adds a Corner Relief on that edge, sized from the profile's tool. For a hole that is not a stock drill, **Snap to Stock Size** sets the hole's diameter to the nearest stock drill.

Milling checks: sharp inside corners along the tool, inside rounds smaller than the smallest tool or too deep for it, deep holes, slots narrower than the smallest tool, thin walls, faces the tool cannot reach from the **Setups** (with how many setups the six main directions would need), long threads, blind tapped holes without room for the tap, holes that are not stock drill sizes, and small sketch text. The reach check looks at each face's direction only, not at other material in the way.

Laser and sheet metal checks read the Flat Pattern, so the part needs one. Layout: holes smaller than the smallest hole, holes and cut-outs too near the edge, a bend line or each other, and flanges too short past their bend. Distances are multiples of the sheet thickness. Before cutting: cut lines that do not close, lines drawn twice, tiny lines, pieces that would fall out of a cut-out (the middle of an O), and an outline so small or large that the units look wrong.

**Save Profile** writes the process's rules to a file to share, and **Load Profile** reads one. FDCAD starts with general values of its own. This version checks milling and laser and sheet metal; the other processes keep their rules for later checks.

## Repair Lost References

When an earlier change takes away a face or edge a feature uses, the feature reports a lost pick. **Repair Lost References** (Evaluate tab, Rebuild group, or right click the feature in the tree) lists every lost pick.

1. Each row names the feature and the lost item. When one face or edge clearly takes its place (the same kind, facing the same way, near where it was, and clearly nearer than any other), the row offers it and says how far it is from the old spot.
2. Click a row: its feature is selected and the view shows where the lost item was and the offered match.
3. Tick the rows to change (Tick All ticks every row), then **Use Offered** to put the matches in, or **Remove** to take the picks out. Either is one undo step. Nothing changes until you click.

In a feature's panel, lost items show first in red. Select one and the view draws where it was faintly; your next pick takes its place. **Clear All Missing** removes every lost item from the list.

### Turning, and the printer in use

**Turning** finds faces a lathe cannot make (not round about the turning axis, which is the axis of the biggest round face, nor square to it), grooves narrower than the narrowest groove, and thin walls. **Milling** also lists pockets deeper than a set multiple of their width, walls taller than a set multiple of their thickness, and raised text (engraving is quicker to mill).

Printer profiles (Preferences, Printing) have a **Process** (FDM, resin or powder), a **Layer height**, the **Smallest round hole** and the **Longest bridge**. In the Manufacturing Check, the process of the printer in use starts from that printer's values.

## Material

**Material** (Tools menu, or double click the **Material** row in the tree) gives the part a material from a list: common printing plastics, acrylic, plywood and common sheet metals, with FDCAD's general densities, and the materials whose densities you set in Preferences, Printing. The density shows in g/cm3 and lb/in3 and can be changed for this part. Tick **Use its colour for the part** to colour the part like the material. The material is saved in the part. Mass Properties and Print Estimate start from it, and the sheet metal Manufacturing Check warns when a bend is tighter than the material allows.

### Printing and moulding

**FDM, Resin** and **Powder Printing** list posts taller than a set multiple of their width, walls thinner than the thinnest wall plus a little more for big parts, holes smaller than the printer makes round, flat faces looking straight down that span more than the longest bridge, text too small for the nozzle, and modelled threads finer than the layers print (tap a pilot hole or use an insert instead). **Moulding** lists walls that are too thick or too thin, walls that differ a lot in thickness, ribs thicker than a share of the wall they stand on, inside corners without a round, and faces with no draft along the pull direction (Z).

## Bounding Box

**Bounding Box** (Evaluate tab, Measure group) puts the smallest box, or a cylinder, around the part, for stock sizes and quotes. **Directions**: **Part Axes** keeps it square to X, Y and Z; **Best Fit** turns it to fit the part closely (a cylinder's axis runs along the part's longest size); **Frame** lies square to a plane or flat face you pick. It is drawn as an outline; tick **Make solid** to add it as a body of its own. The feature's length, width, height and volume show in its report, and formulas can use them, for example `"length@Bounding Box 1" + 5mm` for a stock length with room to face both ends.

## Sensor

**Sensor** (Evaluate tab, Measure group) adds a row to the tree that watches a value and warns when it goes outside limits you set. In **Watch**, choose the **Volume**, **Surface area** or **Mass** of the bodies built above the sensor (mass needs a part material), or **A formula**: any variable, dimension, equation or measured value, for example `="length@Bounding Box 1"` or `=Width * 2`. Type a **Low limit**, a **High limit** or both. After every rebuild the sensor's row shows a warning mark when the value is outside them; the hover text names the value and the limit it passed. The value shows in the feature's report, and formulas further down can read it as `"value@Sensor 1"`. Put the sensor at the bottom of the tree to watch the finished part.

## Keeping a measurement

In the **Measure** box, **Keep** saves what you measure as a **Measurement** feature in the tree: it measures the same faces, edges or vertices again after every change, and shows a label with its value in the view. With nothing picked it keeps the whole part's volume and area. Formulas can use its values, for example `"distance@Measurement 1"`, `"diameter@Measurement 1"`, `"area@Measurement 1"`, `"angle@Measurement 1"` (degrees) or `"dz@Measurement 1"`. Use them in features below the measurement.

## Scale to Fit Printer

**Scale to Fit Printer** (Evaluate, Print, with Lay Face Flat) finds how to fit the part in the active printer's build volume: first by turning it on the bed, then, if turning is not enough, by shrinking it as little as needed. STL and 3MF exports, Open in Slicer and the build volume check then use that turn and scale. The part itself is not changed, and the setting is not saved with the part. **Clear Print Scale** goes back to full size. **Save Print Scale as Feature** adds a Scale feature with the factor, so the part keeps the smaller size; the turn stays a print setting.

## Edge Angle Analysis

**Edge Angle Analysis** (3D Print tab, Check group, in the Enclosed Cavities list) asks for a limit angle, then colours the edges of the part by how sharply their two faces meet. Edges at the limit or more are red: sharp corners you may want to round before printing. Edges where the faces meet at a small angle, below the limit but not quite smooth, are yellow: these often make a fillet or draft fail, or show a seam in a print. Smooth (tangent) edges are not coloured. The status bar counts each kind. It is display only; choose it again to turn it off.

## Undercut Analysis

**Undercut Analysis** (Evaluate, Check, with Draft Analysis) shows what a two-part mould pulled straight apart could reach. Choose the pull direction (a plane's normal) and tick Reverse to flip it. Faces are coloured: seen from above, seen from below, straddle (partly hidden), undercut (hidden from both sides, so the mould cannot release it) and side walls along the pull. The window counts each group, and **Zoom** selects that group's faces and zooms to them. It is display only. Draft Analysis is different: it checks the angle of each face, not whether it can be reached.

### Thickness at a point

With Measure open, click one face of the part. Besides its area, the box shows **Thickness here**: how thick the wall is at the spot you clicked, measured straight in from the face. Click elsewhere on the same face (clear the pick first) to check another spot. Measuring never changes the part. The box's **Units** list changes the units of every result without touching the part's units, and **XYZ from** measures coordinates from the part origin or from a coordinate system.

Tick **Points on faces** to measure from the exact spots you click instead of whole faces, edges or vertices. One click gives that point's X, Y and Z; two give the straight distance between them and dX, dY and dZ. Points on faces cannot be kept as a Measurement feature, since they are not items of the part.

## What a feature did

After you add or edit a feature, the status bar at the bottom says what it did to the solid, for example "Cut 2 removed 2.4 cm3, 3 more faces." Volumes are in cm3 for metric parts and in3 for inch parts. Opening a part shows the rebuild time instead. Screen readers announce the line.

## Out of date results

When a feature fails, the features below it still build, but on the part from before the failure. Each of them shows a warning saying it is not rebuilt and which feature to fix first. Measure and Mass Properties show an "Out of date" note while this is so, because the part on screen is not the part the tree describes. Fix the failed feature and the notes go away.

## Expected values

**Tools > Expected Values** keeps target results with the part, for example the volume a course asks for. Add a row for each check: **Volume**, **Size X**, **Size Y** or **Size Z** of the bounding box, **Face count**, **Hole count**, or a **Measurement** feature's value, with the **Expected** value and a **Tolerance**. After every rebuild the list shows each **Actual** value and **Pass** or **Fail**, and the status bar adds "Checks: 3 of 4 pass." **Use Actual Values** copies the current results into the expected column, to lock in a part you know is right. The checks are saved with the part.

### Values that should use a variable

Model Health also lists feature values and sketch dimensions typed as a plain number that happens to equal a global variable of the same kind, for example a depth typed as 10 when the variable `thickness` is 10. Such a value will not follow when the variable changes. Select the row and press **Link to Variable** to type the variable's name in its place (one undo step).

## Before and After

After you change a value, View, **Before and After** lists the features whose part volume changed in that rebuild: the volume before, after and the change. Click a row to see the part from just after that feature, as it was before your change, drawn faintly over the part as it is now. Close the window to clear it. The list compares the last two rebuilds only.

