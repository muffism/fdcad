# Sheet metal

Sheet metal tools make parts from a sheet of even thickness: a flat plate or a bent wall, with flanges and bends added later. FDCAD can unfold the part into a flat pattern with exact lengths and export it for cutting.

Where to find it: the Sheet Metal command tab. The Sheet Metal group has **Base Flange**, **Edge Flange** and **Sketched Bend**, plus **Sheet Metal Parameters**, **Load Bend Table** and **Load Gauge Table**. The Flanges group has **Miter Flange**, **Hem** and **Jog**. The Corners group has **Closed Corner**, **Break Corner** and **Gusset**. The Cuts and Marks group has **Rip**, **Tab and Slot** and **Cross Break**. The Convert group has **Convert to Sheet Metal** and **Insert Bends**. The Forms group has **Forming Tool** and **Stamp**. The Flat Pattern group has **Flatten**, **Export Flat Pattern**, **Unfold** and **Fold**. The same commands are in the Insert menu. None has a default key.

## How a sheet metal part is built

1. The first sheet metal feature is a Base Flange, or Convert to Sheet Metal or Insert Bends, which turn an existing solid into sheet metal.
2. A **Sheet Metal** folder near the top of the feature tree holds the part's thickness, bend radius, bend allowance and relief. Editing it updates every sheet metal feature that uses the defaults.
3. A **Flat Pattern** feature is always last in the tree. It shows the part flat or folded.
4. Planes, axes, points, sketches and curves never stop flattening. Cuts, holes and fillets that only remove material from flat walls are cut from the flat pattern too. A feature that adds material, or a cut that reaches a bend or a form, shows a warning that names it. To cut across a bend, use Unfold, the cut, then Fold.
6. **Several sheet bodies.** A part may hold more than one sheet metal body, beside solid bodies. Click **Base Flange** (or Convert to Sheet Metal, or Insert Bends) again in a part that already has a sheet: a new **Sheet Metal** folder is added for the new body and its panel opens first, so it can have its own thickness, bend values and relief. Each sheet body gets its own **Flat Pattern**. A tool you start works on the sheet you picked in the view (an edge or a face of it), else on the newest sheet. Solid features on another body do not stop a sheet from flattening. Bend Table and Export Flat Pattern use the first Flat Pattern; flatten the other sheet with its own Flat Pattern feature.
5. Mirrors and patterns can copy cuts and holes in a sheet metal part, but not flanges, hems, tabs or other sheet metal features: the copies would not unfold. Add more flanges with Edge Flange, which takes several edges at once. Mirroring or patterning the whole body works, but then the part cannot be flattened.

## Sheet Metal Parameters

**Sheet Metal Parameters** edits the part's defaults in the Sheet Metal folder.

1. Click **Sheet Metal Parameters**.
2. Set the values and click OK. Every flange and bend that uses the defaults rebuilds.

Options in the property panel:

* Sheet: **Thickness** (1 mm by default) and **Bend radius**, the inside radius of the bends (1 mm by default).
* Bend Allowance: **Method** is K-factor, Bend allowance, Bend deduction or Bend table. **K-factor** (0.44 by default) says where the neutral layer lies, as a fraction of the thickness from the inside. Bend allowance and Bend deduction take a length in **Value**.
* Relief: **Relief type** is Rectangular, Obround or Tear. **Size by** a Ratio of thickness (0.05 to 2, default 0.5) or a Width and depth.

* Relief also has **Corner relief**: Rectangular clears the corner where two bends of one Edge Flange meet down to the bend lines; Circular also cuts a round hole of **Corner size** (diameter) where the bend lines cross. Bends that would reach the hole stop at it.

Tips: with a K-factor, the bend allowance is pi x (R + K x T) x A / 180, where R is the inside radius, T the thickness and A the bend angle in degrees. Reliefs are cut where a bend stops short of an edge. Tear is a thin slit with no depth.

## Sheet Metal Rules

**Sheet Metal Rules** (Sheet Metal group) keeps named rules, such as "Steel 2 mm", in a shared library file, so a team uses the same thickness, bend radius, unfold rule, reliefs and kerf.

1. Click **Sheet Metal Rules**. The window lists the rules in the library file.
2. **Save Current** saves this part's Sheet Metal Parameters as a rule; type its name. **Delete** removes the picked rule.
3. Pick a rule and click **Apply**: its values are copied into this part's Sheet Metal Parameters in one undo step, and the rule's name is kept there.
4. **Library File** picks another file, for example one on a shared drive. FDCAD remembers the last one.

A part keeps its own copy of the values, so it opens the same without the library file. A feature's **Own Bend Values** still override the rule for that feature.

## Load Bend Table

**Load Bend Table** reads bend allowances from a CSV file and sets the Bend table method.

1. Make a CSV file with one row per bend: thickness (mm), radius (mm), angle (degrees) and allowance (mm). A header row is allowed.
2. Click **Load Bend Table** and choose the file.
3. The status bar says how many rows were loaded.

Tips: a bend uses the rows with the same thickness and radius, and works out values between the listed angles. It never guesses past the first or last angle.

Common error: a bend whose angle is outside the table, or with no matching rows, fails. Add rows that cover it.

## Load Gauge Table

**Load Gauge Table** reads named sheet sizes from a CSV file and picks one.

1. Make a CSV file with one row per gauge: a name, the thickness (mm) and one or more inside bend radii (mm). A header row is allowed.
2. Click **Load Gauge Table** and choose the file.
3. Pick the gauge to use, or "No gauge" to keep the typed thickness. The thickness and the first radius of the gauge are set.

Tips: while a gauge is in use, the thickness comes from the table and the bend radius must be one of the gauge's radii. The typed values are kept, so turning the gauge off loses nothing.

Common error: "Gauge allows the bend radii 1, 2 mm. Enter one of them."

## Base Flange

**Base Flange** makes the first wall from a sketch.

1. Draw the sketch. A closed profile makes a flat plate. An open chain of lines and arcs makes a bent wall: every sharp corner becomes a bend of the default radius, and every arc becomes a bend of the arc's own radius.
2. Click **Base Flange**. In a new part, the Sheet Metal Parameters panel opens first. Set the sheet values and click OK.
3. Choose the **Sketch**.
4. For an open profile, set Direction 1: **End** and **Depth**.
5. Click OK. A Flat Pattern feature is added at the end of the tree.

Options:

* **Reverse thickness**: thicken to the other side. **Symmetric**: half the thickness each side; when both are ticked, Symmetric is used.
* From: **Start** at the Sketch Plane, a Surface/Face/Plane, a Vertex or an Offset. The start must be parallel to the sketch.
* Direction 1 **End**: Blind, Mid Plane, Up to Vertex, Up to Face or Offset from Face. **Reverse direction** flips it. Direction 2 is a tick group.
* Own Bend Values: tick to use a radius and bend allowance for this feature only.

Common errors:

* "An open profile must start and end with a line."
* "The profile has gaps. Join the lines end to end."
* "Line is too short for the bends at its ends." Make it longer or use a smaller bend radius.

Base Flange can start from a picked face or plane parallel to the sketch, or at an offset, with the **Start** list (Sketch Plane, Surface/Face/Plane, Vertex, Offset).

## Edge Flange

**Edge Flange** adds a bent wall along each picked edge.

1. Click **Edge Flange**.
2. Click one or more straight edges of flat faces of the sheet.
3. Set the angle and length. Each flange gets a length handle in the view. Click OK.

Options:

* Angle: **Angle from** a Typed angle, Perpendicular to face or Parallel to face (then pick the **Face**; the angle is worked out at the first picked edge and used for every flange). **Reverse direction** bends the other way. Angles are between 0 and 180 degrees.
* Flange Length: **End** is Blind or Up to Vertex. **Measure from** the Outer virtual sharp, Inner virtual sharp or Bend tangent. With several edges, **Length 2** to **Length 8** give each edge its own length. A ninth edge and later ones use Length 1, and a warning says so; split the flange into two features to give them their own lengths.
* Flange Position: Material inside, Material outside, Bend outside, Virtual sharp or **Offset**: the flange sits the **Offset distance** in from the picked edge, with **Material at the offset** (inside, outside or bend outside) applied at that new place.
* **Trim side bends** and **Gap**: flanges that meet at a corner are shortened so they do not overlap, with a gap between them (1 mm by default).
* Own Bend Values and Own Relief: tick groups for this feature only.
* **Flange profile**: pick a sketch with a closed outline to shape the flange (one edge, Blind end). The outline is read in the sketch's own X and Y: X runs along the edge from the start of the bend, Y runs up the flange and is measured the way **Measure from** measures Length. The part of the outline above Y = 0 is the flange, so it can be narrower than the edge, wider (running past the ends of the edge), notched or any shape. Where it crosses Y = 0 sets the width of the bend. A narrower flange gets a relief at each end that stops inside the edge. Edit the sketch to change the flange.

Common errors:

* "The flange profile does not reach the edge." Draw the outline down to Y = 0 of its sketch.
* "Edge is not a straight outside edge of a flat wall." Pick an edge of a flat face of the sheet.
* "Flange is shorter than its bend." Enter a longer length.

## Cuts in sheet metal

An **Extruded Cut** in a sheet metal part has **Link to thickness**: the Blind depth becomes the sheet thickness and follows it when the thickness changes, so the cut always goes exactly through the sheet. It works for a Blind first direction only. An **Extruded Boss** in a sheet metal part has the same tick box: the boss is then one sheet thick.

**Normal cut** (on by default) cuts square to the sheet: where the cut meets a wall, it goes straight through the wall's thickness, so the cut faces stand straight both folded and in the flat pattern, which shows the holes. A cut that crosses a bend is cut as drawn; the flat pattern still shows it, wrapped round the bend. Untick it for the plain cut along the sketch direction. The cut is also made the plain way when a feature that is not sheet metal sits between the last sheet metal feature and the cut.

## Tab

**Tab** (Flanges group) adds a piece of wall, one sheet thickness thick, from a closed sketch.

1. Draw a closed sketch on a flat face of a wall. Let each closed outline meet or overlap the edge of the wall.
2. Choose **Tab** and pick the sketch.

Each closed outline is one tab, so a sketch pattern makes a row of tabs. A tab belongs to its wall: it folds with it and shows in the flat pattern. A tab that does not touch the wall, or that lies inside it, is an error.

## Corner Relief

**Corner Relief** (Corners group) cuts a relief where two or three bends meet, so the corner can be bent without tearing.

1. Keep **Collect all corners** ticked to take every corner of the part, or untick it and pick a face of each bend whose corners you want.
2. Choose the **Relief type**: Rectangular, Circular, Tear, Obround or Constant width.
3. Choose **Size by**: a **Ratio to thickness** (2 by default) or a **Size** you type.
4. Choose the **Placement**: Centred on the bend lines, or Bend tangent (the relief touches the bends' tangent lines on the wall).

**Type per corner** gives each corner its own type: list them in corner order, separated by commas, and leave a blank to keep the relief type, for example "circular, , tear". Rectangular is a square with its sides along the bends; Circular is a circle of the size across; Tear is a small circle on the corner point; Obround is a slot along the corner's diagonal; Constant width is a slot of the size across that runs from the corner through both bend regions. The relief is cut from the wall, both bends and both flanges, so it shows folded and in the flat pattern.

## Gusset

**Gusset** (Corners group) presses a stiffening rib into a bend.

1. Pick a face on each of the two walls the bend joins.
2. Set the **Depth** (how far the rib reaches along each wall from the bend), the **Width** (along the bend), the **Profile** (Round or Flat) and the **Position along the bend** (0 is the middle).
3. Tick **Cut out in the flat pattern** to leave a cut out where the rib is; untick it to keep the flat pattern whole.

The rib fills the inside of the bend and the same shape is pressed in from outside, so the sheet keeps its thickness at the rib's middle.

## Sketched Bend

**Sketched Bend** bends the sheet along a line.

1. Sketch exactly one line on a flat face of the sheet. The line is carried across the whole wall.
2. Click **Sketched Bend** and choose the sketch.
3. Type the **Angle** and choose the **Position**: Bend centreline, Material inside, Material outside or Bend outside.
4. Click OK.

Options: **Reverse direction** bends the other way. **Flip fixed side** keeps the other side of the line still (first wall only). Own Bend Values works as in Edge Flange.

Common error: a line that crosses another bend fails. Move the line.

## Flatten

**Flatten** switches the part between folded and flat. It is one undo step.

1. Click **Flatten**. The part shows flat, with bend lines.
2. Click it again to fold the part.

Edit the Flat Pattern feature for more options: **Flattened**, **Show bend lines**, **Show bounding box** and **Grain direction** (an edge of the first wall). The panel shows the **Flat size** as length by width.

For quoting, the panel also shows the **Blank area**, the **Outer cut length**, the **Inner cut length** (round every hole), the number of **Cut outs** and the number of **Bends**. Equations can use them as `blank_area@Flat Pattern`, `outer_cut_length@Flat Pattern`, `inner_cut_length@Flat Pattern`, `cut_outs@Flat Pattern`, `bends@Flat Pattern`, `flat_length@Flat Pattern` and `flat_width@Flat Pattern`.

**Sheet length** and **Sheet width** (2500 by 1250 mm) are the size of the stock sheet: a warning says when the flat pattern does not fit it either way round.

Tips: features added while the part is flat go after the Flat Pattern and apply only to the flat state. Features added while it is folded go before it. If pieces of the flat pattern would overlap, a warning names the feature that causes it.

### Flat pattern options

* **Merge faces** (on by default) joins the faces of walls and bends in the flat pattern. Turn it off to see where each bend region starts and ends.
* **Corner trim** cuts the square where two bend regions meet at a corner, so no material is left over in the flat corner.
* **Faces to leave out**: pick a face of a flange to leave that flange out of the flat, with its bend and every wall bent from it. The first wall cannot be left out.
* The flat bend regions are always exact straight strips, so there is no separate Simplify Bends option.
* To cut on the flat and fold the cut with the part (No Bends), use **Unfold** with All bends, make the cuts, then **Fold**. This works on converted and Insert Bends parts too.

### Fold progress

**Fold progress (%)** shows every bend at that share of its angle while the part is folded: 100 is fully folded, 0 is flat, 50 is half way. It only changes the view, so it helps to check how the walls swing past each other.

### Bend notches

The Flat Pattern's **Bend notches** cuts a small Triangle, Circle or Rectangle notch at both ends of every bend line, in the flat pattern only, so the press brake operator can line up each bend. **Notch size** is how far the notch reaches into the sheet and how wide it is at the bend end. The notches are part of the flat outline, so they show in the view and in the exported DXF, SVG and STEP. The folded part has no notches.

## Export Flat Pattern

**Export Flat Pattern** saves the flat pattern at true scale.

1. Click **Export Flat Pattern**.
2. Choose STEP, DXF, SVG or Quote data CSV and a file name. Click Save. If the name has no .step, .stp, .dxf, .svg or .csv ending, the ending of the chosen type is added.
3. For DXF and SVG the **Flat Pattern Output** window opens. Tick the items to write (Outline, Bend lines, Cross break and form marks, Bounding box), choose the **Origin** (the part's origin, the lower left corner or the centre of the outline), **Rotate** the drawing, **Flip X direction** or **Flip Y direction**, and set the DXF colour numbers of up and down bend lines. The list at the bottom shows every bend line and mark: untick one to leave it out. Click OK.

With bend colours set, the DXF has a BEND_UP and a BEND_DOWN layer instead of BEND_LINES. The Quote data CSV holds one row per quoting value.

Tips: DXF and SVG are in millimetres. They have an OUTLINE layer, a BEND_LINES layer and, when shown, a BOUNDING_BOX layer. In SVG, bend lines are dashed.

Part numbers and other etched marks: add a **Mark** before the Flat Pattern (see [import-export-print.md](import-export-print.md)). Marks with no depth on the base wall, the wall that stays put when the part is flattened, go to their own MARKS layer, so the laser can etch them instead of cutting them. Marks on bent walls are not written yet; put the sketch on the base wall.

Common error: "There is no flat pattern to export. Fix the Flat Pattern first."

## Hem

**Hem** folds picked edges back over the sheet.

1. Click **Hem** and pick one or more straight edges of flat faces.
2. Choose the **Hem type** and its sizes. Click OK.

Options:

* Hem type: Closed (lies flat on the sheet), Open (leaves a **Gap**), Teardrop (inside **Bend radius** and an **Angle** over 180 degrees, so the hem leans back) or Rolled (a curl of **Bend radius** and **Angle**, with no straight part).
* **Length**: from the outer face of the fold to the end of the hem. Except for Rolled hems, it must be more than the inside radius plus the thickness.
* **Angle** (Teardrop and Rolled only): Rolled between 90 and 350 degrees, Teardrop between 180 and 350.
* **Position**: Material inside keeps the fold within the old edge; Material outside starts the fold at the edge.
* **Reverse direction** folds under the sheet. **Corner gap** is the space left where two hems meet at a corner.
* With several edges, **Length 2** to **Length 8** give each edge its own hem length.
* **Own Bend Values**: tick it to give the hem its own **Method** and **K-factor** or **Value**. **Own Relief** works as on Edge Flange.

Common error: "The hem cuts into the sheet." Shorten the hem or reduce its angle.

## Miter Flange

**Miter Flange** runs a sketched profile along a chain of edges and mitres the corners.

1. Pick a chain of straight edges on one face of one wall, joined end to end.
2. Sketch an open chain of lines on a plane square to an end edge of the chain, starting at that edge's end point. The lines continue the picked face.
3. Click **Miter Flange**, choose the sketch and the edges, and set the **Gap** left at each mitre. Tick **Propagate** to add every edge joined smoothly to a picked one; it stops at a corner that is not smooth, at a cut and at a curved edge. Click OK.

Tips: the edges cannot form a closed loop, such as the whole rim of a box; leave one edge out. Every corner of the profile becomes a bend. A corner drawn as an arc, tangent to the lines on both sides, becomes a bend with the arc's radius on the sketch's side of the sheet; the arc must be larger than the thickness when the bend turns away from the sketch side. The profile must start and end with a line, and two arcs need a line between them. At each corner of the chain the walls are cut on the plane that halves the corner, and the bends stop short, leaving a small relief.

**Start offset** and **End offset** stop the flange short of the chain's free ends, for a partial miter flange. The chain starts at its free end with the smallest X, then Y, of the wall. The edge beyond an offset is left as it is. Tick **Own Relief** to cut a relief (Rectangular, Obround or Tear, by ratio or size) into the wall at each offset end, against the end of the bend.

Common errors: "The profile must start at an end of the edge chain." and "The edge chain turns inward at a corner."

## Jog

**Jog** offsets part of a wall with two opposite bends along a sketched line.

1. Sketch one line on a flat face of the sheet.
2. Click **Jog**, choose the sketch and type the **Offset**. Click OK.

Options: **Measure offset** Face to same face, Between inside faces or Overall. **Angle** of both bends, **Reverse direction**, **Position** of the first bend on the line and **Flip fixed side**, as in Sketched Bend.

Tips: the jog is cut from the wall, so the flat pattern keeps the wall's size.

Common error: "The offset is too small for the bend radius and angle." Enter a larger offset, a smaller radius or a smaller angle.

## Closed Corner

**Closed Corner** lengthens two flange walls so they close the corner between them.

1. Click **Closed Corner** and pick the narrow end face of a flange wall at each corner. The nearest flange wall end becomes its partner.
2. Choose the **Corner type** and the **Gap**. Click OK.

Options: Overlap (the picked wall covers the partner's end), Underlap (the partner covers the picked wall) or Butt (both meet on the plane between them). **Overlap ratio** (0 to 1) is how far across the other wall's thickness an overlap or underlap reaches: 1 covers it fully, 0.5 half way. Pick an end face at each corner to close several corners at once. **Bend region** Closed fills the corner between the two bends where their bent surfaces cross, so the folded corner has no hole; Open (the default) leaves it empty. The fill is in the folded part only: the flat pattern keeps its corner. When the two flanges do not bend from the same wall, the region stays open with a warning.

## Break Corner

**Break Corner** chamfers or rounds outside corners of the flat sheet.

1. Click **Break Corner** and pick the short edges through the sheet at the corners.
2. Choose Chamfer with a **Distance**, or Fillet with a **Bend radius**. Click OK.

Tick **Collect all corners** to take every corner of the flat outline instead of picking, and choose **Corners**: Outside corners, or Inside corners only. An inside corner is filled: the chamfer or round adds material instead of cutting it. A picked inside corner is filled too.

Common error: a corner on a bend line fails. Pick a corner of the flat outline.

## Rip

**Rip** cuts narrow slits so the sheet can unfold.

1. Sketch lines on flat faces for sketched rips, or pick edges where two walls touch without a bend.
2. Click **Rip**, set the **Gap** and click OK.

Tips: a sketched rip is only as long as its line. For an edge rip, the wall that loses less material is cut back; **Flip** cuts the other wall.

To slit a plain tube or cone before you work with it, pick its round faces under **Tube faces** instead. Each face is slit along its whole length with the **Gap**. **Slit angle** turns the slit round the axis from the face's own start, and **Slit offset** moves it sideways. This works on a plain solid, not on a sheet metal part.

## Tab and Slot

**Tab and Slot** adds tabs to one wall's edge and matching slots to the wall they pass through.

1. Click **Tab and Slot**. Pick the **Tab edge** and a **Face** of the slot wall.
2. Set **Tabs**, **Tab length**, **Depth**, **Spacing** (zero spreads the tabs over the edge) and **Clearance**. Click OK.

**Edge offset** keeps the tabs that far in from both ends of the edge, with equal offsets; with a Spacing the row stays centred on the edge. **Tabs to skip** leaves out tabs by number, for example "2, 4", with their slots.

Common error: "Tab misses the slot wall." Pick an edge that meets the slot wall, or a longer depth.

## Convert to Sheet Metal

**Convert to Sheet Metal** turns the faces of a solid into walls and bends.

1. Click **Convert to Sheet Metal**. In a part without sheet metal parameters, set the sheet values first and click OK.
2. Pick the **Face** that stays fixed and the edges to bend. Click OK.

Tips: the solid's faces become the outside of the sheet and the material goes inward, so the outside sizes are kept. Faces not reached through bend edges are left out. Edges between two walls that are not bends become rips. **Gap** (0.1 mm by default) is the space left at bend corners and rips.

**Rip type** sets how two walls meet at a rip: **Overlap** (the default: the wall nearer the fixed face covers the corner), **Underlap** (the other wall covers it), **Open** (neither covers it, so the corner is left open) or **Butt** (both walls stop at the plane that halves the corner). The Gap is kept in each case. **Keep the solid** keeps the solid you converted as its own body beside the sheet, so you can still use or copy it. It is not part of the flat pattern.

Common error: "The bend edges close a loop." Leave one of them out; it becomes a rip.

## Insert Bends

**Insert Bends** turns a thin part of even thickness (for example a shelled box) into sheet metal.

1. Click **Insert Bends** and pick a flat face on the outside of the part.
2. Click OK. The thickness is measured from the part, and every edge between outside faces becomes a bend, except an edge that would close a loop of walls, which becomes a rip. **Gap** is the space left at bend corners and rips. The part must have flat faces only: remove rounds first, or use Convert to Sheet Metal.

Common error: "The part is 3 mm thick but the sheet metal parameters say 2 mm." Set the thickness in Sheet Metal Parameters.

## Cross Break

**Cross Break** marks a wall with two cosmetic lines from corner to corner. It does not change the part.

1. Click **Cross Break** and pick a flat face of a wall. **Reverse direction** titles the break down instead of up.
2. Click OK. The lines show folded and flat, and the flat pattern DXF and SVG have them on a CROSS_BREAKS layer.
3. **Break angle** and **Break radius** are written into each line's title, so the flat pattern files carry them for the shop.

## Flat Marks

**Flat Marks** (Cuts and Marks group) copies the lines, arcs and circles of a sketch drawn on a flat face of a wall onto that wall as marks, with a **Mark title**. The marks show folded and flat, and the flat pattern DXF and SVG write them with the cross break lines, so layout lines and centre marks reach the flat blank. Arcs and circles are written as short straight pieces. The part's shape does not change.

## Extend Wall

**Extend Wall** (Flanges group) lengthens a wall out of one of its edge faces.

1. Pick the narrow face through the sheet at the edge of a wall.
2. Choose **End**: Blind with a **Distance**, or Up to plane or face, then pick the plane or flat face.

The wall keeps its outline as it grows, and the new part folds and flattens with the wall.

## Perforated Fold Line

**Perforated Fold Line** (Cuts and Marks group) cuts a row of short slots along a line, so the sheet can be bent by hand there.

1. Sketch one or more lines on a flat face of a wall.
2. Choose **Perforated Fold Line**, pick the sketch and set the **Slot length**, **Slot width** and **Bridge** (the uncut sheet between slots).

The row is centred on each line, so both ends keep the same bridge. The slots show folded and in the flat pattern.

## Edit Bends

**Edit Bends** (Sheet Metal group) changes bends after they are made: the bends of flanges, of a converted solid or of an Insert Bends part.

1. Tick **All bends**, or pick a face of each bend to change.
2. Enter the new **Bend radius** and choose the **Method** with its **K-factor** or **Value** (bend allowance or bend deduction).

Each bend keeps the line where it starts on its wall; the walls after it move with the new radius, and the flat pattern takes the new bend allowance. Suppress or delete Edit Bends to go back to the old values.

## Bend Table

**Bend Table** (Flat Pattern group) lists every bend of the part: its number, the feature that made it, up or down, the angle, the inside radius, the bend allowance and its **Step** in the bending order.

1. Click **Bend Table**. Pick a row to see that bend highlighted in the model.
2. Type a new **Radius** or **Allowance** in a row to change that bend, and type the **Step** numbers in the order the bends are made on the press brake.
3. Click OK. Each changed bend gets an **Edit Bends** feature above the Flat Pattern, and the steps become the Flat Pattern's bend order. It is one undo step.

The bend order goes to the flat pattern files: the DXF has the step number at the middle of each bend line on a BEND_ORDER layer, and the SVG bend titles end with the step.

Below the bends a second table lists the part's **Rip** features (R1, R2 and so on): the feature, the kind of rip (sketched, edge or tube) and its **Gap**. Pick a row to see the rip's cut highlighted. Type a new Gap to change that Rip feature; it is part of the same undo step. A bend cannot be turned into a rip from the table: delete the flange and add a Rip instead.

## Unfold and Fold

**Unfold** lays picked bends flat so you can cut across them; **Fold** folds them back with the cuts.

1. Click **Unfold**, tick **All bends** or pick a face of each bend, and click OK.
2. Add cuts with Extruded Cut or another cutting feature. Cuts across a bend must go through the sheet.
3. Click **Fold**. It closes the newest Unfold above it.

Tips: a cut across a bend is wrapped onto the bend exactly, using the bend allowance, so the flat pattern and the folded part match.

Common error: "A feature after Unfold adds material." Only cuts can be made between Unfold and Fold.

## Forming Tool

**Forming Tool** presses a dimple, louvre or embossed rib into a flat wall.

1. Sketch a line on a flat face for each form. A form is centred on its line and turned along it.
2. Click **Forming Tool**, choose the **Form tool** and its sizes. Click OK.

Options: Dimple (**Diameter**, **Height**), Louvre (**Length**, **Width**, **Height**; lanced along one side and raised as a hood) or Embossed rib (**Width**, **Height**; runs from end to end of the line, as a bead; **Rib ends** Round or Square). **Reverse direction** presses the other way.

Tips: forms show only in the folded part. The flat pattern keeps the flat outline; a louvre leaves its lance as a thin slit.

**Own tool (a body).** To press a shape of your own, model the tool as its own solid body in the part (for example an extrude with **Merge result** off and sloped sides). In Forming Tool choose **Own tool (a body)** and pick the tool's **Stop face of the tool body**: the flat face that sits on the sheet, with the whole tool on one side of it. Pick **Faces to remove** to leave holes there, and an **Insert point** (a vertex of the tool) if the stop face's centre is not the right point. On each sketch line the insert point goes on the line's middle and the tool turns to the line; **Rotation** turns it further and **Mirror** mirrors it across the line. Draw several lines to place several copies. The sheet keeps its thickness measured along the press, so give the tool sloped sides: straight sides come out with no wall. The tool body leaves the part once it is used. Saving tools to a library is not available yet: model the tool body in each part that uses it.

Common error: "Form runs off its wall or too near a bend or hole." Move it or make it smaller.


## Stamp

**Stamp** presses a closed sketched outline into a flat wall.

1. Sketch one closed outline of lines and arcs on a flat face of a wall.
2. Click **Stamp** (Forms group), choose the sketch, set the **Depth** and the **Draft** (the side angle; 0 gives straight sides) and click OK.

Tips: **Reverse direction** presses the stamp the other way. The sheet keeps its thickness along the press. The stamp shows in the folded part only; the flat pattern keeps the blank and draws the stamp's outline as marks, written to the DXF and SVG with the other marks. The outline must lie on one wall, a little away from bends and holes.

Rounds (all 0 by default, which leaves the edges sharp): **Punch radius** is the inside round along the top of the stamp (the outside gets the punch radius plus the thickness). **Die radius** is the round where the stamp leaves the wall, on the side it rises from (the other side gets the die radius plus the thickness). **Corner radius** rounds the corners of the outline seen from above. When the rounds do not fit, the message asks for smaller radii or a larger depth.

A sketch may hold several closed outlines: each becomes its own stamp, for example a row of dimples drawn as circles. Tick **Drawn cut out** to cut the top of each stamp away, so it becomes a hole with a drawn collar round it.

## Not built yet

Swept flange and lofted bend are not available. They need walls curved in two directions, which the flat pattern cannot unfold exactly.

See also: [Import, export and print](import-export-print.md) and [Sketching](sketching.md).

## Kerf and stencil text

**Kerf** in the Sheet Metal settings is the width the laser or cutter takes away. Tab and Slot draws each slot narrower by the kerf on each side, so after cutting the tabs fit with the clearance you set. The Manufacturing Check lists tabs shorter than the shortest tab (a multiple of the thickness) and tabs too shallow to pass through the wall.

For text cut through a sheet, tick **Stencil** in the text settings: each letter with a closed inside, such as O, A or B, gets a bridge (12 percent of the height wide, or the **Bridge width** you type), so its middle stays joined to the sheet.

