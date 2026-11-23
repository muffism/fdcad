# Patterns and bodies

Pattern tools copy features, faces or whole bodies so you model a detail once and repeat it. Body tools work on whole solid bodies: they join them, cut them apart, move them, delete them or scale them. Read the multibody basics first if your part will have more than one body.

Where to find it: the Modify group of the Features tab (a Pattern dropdown with the linear, circular and sketch driven patterns, and a Mirror button) and the Bodies group of the Bodies tab (a Combine and Intersect dropdown, Move and Copy Body, Transform Handles, then Split, Scale and Delete and Keep Body). The same commands are in the Insert menu. None of them has a default key, but you can add one in the shortcut editor.

## Multibody basics

A part can hold several solid bodies. The feature tree shows them in the **Solid Bodies** folder with a count, and the status bar shows the body count too. Bodies with the same shape, such as the copies of a pattern, sit together in an **Identical Bodies** folder inside it, with their count, so you can see how many of each part to print. Right click a body and choose **Feature History** to list the features that made it, in build order; click one to find it in the tree.

Bodies can sit in folders of your own inside Solid Bodies. Right click a body and choose **Move to Folder...**, then type a new or an existing folder name; leave it empty to take the body out of its folder. A body stays in its folder when the part is rebuilt. Right click a folder for commands that act on all its bodies: **Hide Bodies**, **Show Bodies**, **Colour...**, **Delete Bodies** (adds one Delete Body feature, so Undo or deleting that feature brings them back), **Rename Folder...** and **Remove Folder** (the bodies go back to Solid Bodies).

1. Most boss features have a **Merge result** tick box. It is on by default, so a new boss joins the part. Untick it to keep a separate body.
2. When a feature makes a separate body you did not ask for, FDCAD shows a warning. You choose to keep it or undo.
3. Body tools pick a body by any of its faces. Click a face in the view and the pick box shows "Body 1", "Body 2" and so on. Bodies are numbered in the order the part holds them.
4. A pick box takes clicks while it is active. Click a listed body again to remove it. Press Delete to remove the selected rows.

### Which bodies a feature acts on

In a part with two or more bodies, Extruded and Revolved Boss and Cut, Swept and Lofted Boss and Cut, and the Hole Tool have a **Bodies** box (other features, such as Dome, Wrap, threads and Mounting Boss, act on every body): **All bodies** (the default) or **Selected bodies**. With Selected bodies, click any face of a body in the view to add it; only the picked bodies are cut or joined, the others stay as they are. A boss with Merge result off keeps its own body either way.

## Linear Pattern

**Linear Pattern** copies features, faces or bodies along one direction, or two.

1. Click **Linear Pattern**.
2. In Direction 1, click a straight edge, flat face or plane in the view for the direction. You can also choose a plane from the list.
3. Type the spacing and the number of instances. The count includes the original.
4. To add a second direction, tick the Direction 2 group and fill it in the same way.
5. In Items to Copy, tick the features, or click the faces or bodies to copy. The list offers bosses, cuts and Hole Tool holes; other features (ribs, domes, wraps, mounting bosses, threads) are copied by their faces or with Geometry pattern.
6. Check the preview and click OK.

Options in the property panel:

* **Reverse**: copy the other way along the direction.
* **Fill**: "Spacing and instances", "Up to reference", or "Total length and instances". Up to reference fills the space up to a vertex, edge, face or plane, less an **Offset**. Total length spreads the instances evenly from the seed to the **Total length**, so 5 instances over 100 mm are 25 mm apart. Spacing and overall size makes as many copies **Spacing** apart as fit in the **Total length**, the original included, so a spacing of 12 mm in 25 mm makes 3.
* **Spacing law**: Even (the usual), Growing (each gap is the **Growth ratio** times the one before, starting from the spacing, for things like heat sink fins that spread out), or Random (each copy moves by up to **Random move** percent of the spacing either way; the same **Random seed** always gives the same layout), or List of fractions (type one number per copy in **Fractions**, such as `0.1, 0.3, 1`: each copy sits at that share of the run from the original to where the last copy would be with even spacing). Growing by an increment makes each gap the one before plus the **Increment**, so a spacing of 10 and an increment of 2 gives gaps of 10, 12, 14; a negative increment closes the gaps up.
* A pattern with more than 200 copies asks before it is built, because it can take a long time. Press No to change the count.
* **Pattern seed only** (Direction 2): only the original is repeated in direction 2.
* **Vary values** (Items to Copy): make each copy a little different. Type a value name of the copied feature and its step per copy, such as `depth 2`, and separate several with semicolons (`depth 2; draft_angle 1`). Lengths are in mm and angles in degrees. Copy 2 grows by one step, copy 3 by two, and so on along each direction. Each copy is built again, so it is slower, and it does not work with Geometry pattern.
* **Copy values** (Items to Copy): give one copy its own values. Type the instance number, a colon and the values, such as `3: depth 8`, and separate copies with semicolons (`3: depth 8; 2.2: depth 4, draft_angle 2`). The value replaces the original's value and any Vary step for that copy. Instance numbers are the same as in Instances to Skip. A negative Vary step makes the copies shrink instead of grow. While the pattern is open, each copy shows a small numbered marker in the view (`#3`, `#2.2`): click one to start that copy's entry in Copy values, then type its values. Drag a box over markers to add those copies to Instances to Skip; hold Ctrl while you drag to bring skipped copies back. A skipped copy keeps its marker.
* **Seed cell**: which cell along the direction holds the original, counted from 1. With 5 instances and seed cell 3, two copies go each way. It cannot be used with Symmetric.
* **Rotate pattern** (Direction 2): turns the whole grid in its own plane by this angle, so the rows need not follow the picked edges.
* **Geometry pattern**: copy the faces exactly instead of building each feature again. It is faster, but faces merged into the rest of the part cannot be copied this way.
* **Check copies**: Full (the usual) tests that every copy touches the part, and names the copies that fall off. Fast skips that test, which saves time on large patterns whose copies sit well on the material; a copy that misses the part is then not reported.
* Patterns of patterns: an earlier Linear, Circular, Sketch or Table Pattern that copies features is in the list of features to copy. Tick it to repeat the whole pattern, its original and every copy, at each new place. Mirror can copy such a pattern too. A pattern that copies faces or bodies is not in the list; turn on Geometry pattern and pick its faces instead.
* **Merge result** (bodies only): the copies become one body with the original.
* **Propagate colours**: copies take the colours of the original's faces.
* **Preview**: Full shows every copy. Partial shows only the first copy in each direction, which is faster for large patterns.

Tips: faces to copy must form a whole feature, such as every face of a boss or a hole. A pattern can have at most 1000 instances.

Common errors:

* "The Up to reference lies behind the seed." Tick Reverse.
* "The picked faces do not form a whole feature." Pick the rest of its faces, or pick the feature instead.
* A copy that falls off the part makes the whole pattern fail. The errors panel offers **Skip copies that failed**, which keeps the other copies; nothing changes until you click it.

## Circular Pattern

**Circular Pattern** copies features, faces or bodies around an axis.

1. Click **Circular Pattern**.
2. Click an axis in the view: a straight edge, a round edge or a cylinder face. Or choose a reference axis, or the origin's X, Y or Z axis, in the list above the pick box.
3. Leave **Equal spacing** ticked and type the number of instances. The copies share 360 degrees.
4. Pick the items to copy and click OK.

Options:

* **Equal spacing**: the **Angle** is the total angle. Untick it and the angle is between each copy.
* **Reverse**: turn the other way.
* **Spacing law**: Even (the usual), Growing by an increment (each step is the one before plus the **Increment** angle), or Per copy angles: type one angle in degrees for each copy in **Copy angles**, such as `30, 75, 160`. Each angle is measured from the original, so the copies can sit anywhere round the axis.
* Direction 2 turns the other way round the axis. **Symmetric** uses the values of direction 1.
* Items to Copy, Instances to Skip and the Options group work as in Linear Pattern.

Tip: with an equal spacing of less than a full turn, the last copy lands on the end angle.

Common error: "The angle must be greater than zero." Type a positive angle.

## Sketch Driven Pattern

**Sketch Driven Pattern** puts one copy at each point of a sketch.

1. Draw a sketch with points where the copies should go. See [Sketching](sketching.md).
2. Click **Sketch Driven Pattern** and choose the sketch.
3. Optional: click a vertex as the **Reference point**. Without one, the centre of the original is used.
4. Pick the items to copy and click OK.

Tip: only points of their own count. End points and centres of lines and arcs are left out, and so are construction points. The points are numbered in the order they were drawn, for Instances to Skip; a point that sits on the original is the original and gets no copy, but keeps its number.

Common error: "Pick a sketch with points." Add points to the sketch, or choose another one.

Tick **Symmetric** in a direction of a Linear Pattern to make the same number of copies, as far apart, on the other side of the seed too. For Instances to Skip, the copies on the far side are numbered after those on the near side.

## Fill Pattern

**Fill Pattern** (in the pattern dropdown) fills a flat face with copies, for grilles, vents and weight reduction holes. Only copies that fit on the face, with the **Margin** from its edges, are made.

1. Pick the flat face to fill.
2. Choose the **Layout**: **Grid** (Spacing and Row spacing), **Staggered Grid** (each row leans by the **Stagger angle**; 60 gives an even triangular layout) or **Rings** (circular, square or polygon rings out from the start).
3. Choose what to copy: pick features, faces or bodies as the seed, or choose a **Cut shape** (Circle, Square, Diamond or Polygon) with its **Size** and **Shape angle**. A **Depth** of 0 cuts through the part.
4. Optional: pick an edge for the **Direction** and a vertex where the layout starts; otherwise it follows the face and starts at its middle.
5. Optional: choose a **Sketch** to fill a closed sketch region instead of the whole face, for example a vent area drawn on the face. With several regions the one holding the start vertex is used, else the largest.
6. On a cylinder face (the outside of a tube, or a bore), choose **Round face spacing**: **Along the surface** measures the spacing round the face as if it were unrolled flat, so the copies are evenly spread on the surface; **As seen from the front** measures it as seen from straight on at the start point, so the copies crowd together toward the sides. Copies turn with the face, so they stay square to it. A cut shape with no depth cuts in to the axis from outside, or out through the wall from a bore. The Direction pick is not used on a cylinder; the rows run along its axis. Other curved faces cannot be filled.
6. **Fit**: **Whole Shape** keeps a copy when all of it lies on the material, the Margin away from the edge; **Centre Only** needs just its centre that far in. A negative Margin lets copies run past the edge.

Size gradient (cut shapes): tick **Size gradient** and type the **End size**. The shapes have the **Size** where the gradient starts and the End size at the copy farthest from it, in proportion between, for decorative and lightening patterns that thin out toward an edge. **Gradient from** takes a vertex or point (the shapes grow away from it) or an edge (they grow with the distance from it); left empty, the start point is used. Each copy must fit with its own size, so large copies near the edge are dropped while small ones stay.

The panel shows how many **Copies** fit. Formulas can use the number as `"count@Fill Pattern 1"`, for example to set a vent's depth from its number of holes. Use it only in features below the pattern: a feature above it builds before the copies are counted, and says so.

## Pattern Chain

Pattern Chain runs several pattern steps one after another. Each step copies everything the steps before it made.

1. Choose **Features > Pattern Chain**.
2. Type the **Step order**, for example `linear, circular`. The steps are mirror, linear, circular and scale, each used once. Change the order by retyping it: `linear, circular` makes a row and turns the whole row round the axis, while `circular, linear` turns the original first and then moves every turned copy along.
3. Fill in the group of each listed step: **Linear Step** (a direction, spacing and instances), **Circular Step** (an axis, the total angle and instances; 360 degrees spreads them evenly), **Mirror Step** (a plane) and **Scale Step** (a factor, instances and an optional centre point; each copy is factor times the size of the one before).
4. Pick the features, faces or bodies to copy, as in Linear Pattern.

Instances are numbered from 1 (the original) with the first step counting fastest, so with `linear, circular`, 2 linear instances and 4 turns, number 3 is the original turned once. Skip, Copy values and Vary use these numbers. A Pattern Chain can itself be copied by a later pattern.

## Skipping instances

Every pattern has an Instances to Skip group. Type the numbers of the copies to leave out, separated by commas, for example `3, 5`.

1. The original is number 1, so the first copy is number 2. Numbers count along each direction. A number of 1, or one past the last copy, is ignored.
2. For a two direction pattern, type two numbers with a dot: the place along direction 1, then along direction 2. For example `2.2`.
3. A plain number such as `3` means place 3 in the first row, which is the second copy.

If the text is wrong, the panel says: "Type copy numbers separated by commas, such as 3, 5 or 2.2."

**Suppress region**: pick faces or closed sketches in the same group. Every copy whose centre lands over them is skipped. Set **Skip copies** to Outside the region to keep only the copies over the region instead. A copy's centre is the centre of the original's faces, moved with the copy.

**Patterns of reference geometry**: pick one plane, axis, point or coordinate system as the only item to copy in a Linear or Circular Pattern. The pattern copies it to every place and leaves the part as it is; the copies are drawn in the view. To sketch on a copied plane or pick a copied axis, explode the pattern: each copy becomes its own feature that works like any reference feature.

**Explode Pattern**: right click a pattern in the feature tree and choose Explode Pattern to turn it into one feature per copy, named `Linear Pattern 1 copy 2` and so on. Each can then be edited, suppressed or deleted on its own, or given its own values with Copy values. Skipped copies are left out. Features built on faces of the first copy keep their picks; features on faces of the other copies need them picked again. Undo brings the whole pattern back.

**Add to Pattern**: build a feature on one copy of a pattern (or on the original), for example a chamfer on one hole, then right click it in the feature tree and choose Add to Pattern. A **Follow Pattern** feature appears below it and repeats it at every other copy. It follows the pattern: change the pattern's count or spacing and the repeats follow. Edit the Follow Pattern to skip copies or change its options. A feature that neither adds nor cuts material, such as a chamfer or fillet, is copied as faces.

## Mirror

**Mirror** copies features, faces or bodies to the other side of a plane.

1. Click **Mirror**.
2. Click a plane or flat face for the **Mirror plane**.
3. Pick the items to copy and click OK.

Options:

* **Second mirror plane**: makes up to three copies.
* **Mirror seed only**: with two planes square to each other, leave out the copy mirrored about both.
* **Geometry pattern**, **Merge result**, **Propagate colours** and **Preview** work as in Linear Pattern.

Common errors: "The two mirror planes are parallel." Pick another plane. "Mirror seed only needs two planes square to each other." Turn it off or pick another plane.

## Combine

**Combine** joins bodies, subtracts bodies, or keeps only where they overlap.

1. Click **Combine** and choose the **Operation**.
2. Add: click a face of each body to join.
3. Subtract: pick the **Main body**, then the bodies to cut from it.
4. Common: pick the bodies. Only the shared volume is kept.
5. Click OK. Bodies you did not pick stay as they are.

**Tolerance**: faces closer than this count as touching, so imported bodies that nearly meet join. 0 uses the kernel's own. **Split** has the same option.

Common errors: "The part needs two or more bodies to combine." "The picked bodies do not overlap." Move the bodies so they overlap, or pick others.

## Intersect

**Intersect** makes new bodies from the regions where bodies and planes overlap.

1. Click **Intersect**.
2. Pick two or more bodies, or a body and planes or flat faces. Planes act as large flat sheets.
3. In Regions, choose Overlap regions, Internal regions (closed spaces inside the bodies) or Both.
4. The region list shows each region by number. Untick regions to leave them out. Use **Select All** and **Invert** to change many at once.
5. Click OK. The kept regions replace the picked bodies.

Options: **Merge result** joins touching regions into one body. Untick it for one body per region. **Cap flat openings** changes nothing yet, because all bodies are closed solids.

Common error: "The kernel found no regions." Move a body slightly so faces do not almost touch.

## Split

**Split** cuts bodies into pieces.

1. Click **Split**.
2. Pick the trim tools: planes, flat faces, curved faces or sketches. Planes and flat faces are endless. Sketches cut through all, both ways.
3. Optional: pick the bodies to cut. Without any, every body is cut.
4. Click **Cut**. The panel lists the resulting bodies by number, ordered by where they sit. After an edit that changes the pieces, the numbers can point at other bodies: check the ticks. A ticked number that no longer exists gives a warning.
5. Untick the bodies you do not want to keep, then click OK.

Common errors: "The tools do not cut through any body." Move or extend the tools. "Tick at least one body to keep."

**Saving bodies to files**

1. After Cut, double click a body in the list to type its file name.
2. Pick a format (FDCAD Part, STEP, STL or 3MF) and click Save Bodies. Each ticked body is written to its own file in a folder you choose.

**Tools, Bodies to Part Files** saves the selected bodies (or every body, with nothing selected) each to its own file in one go, after the part is built: **Linked FDCAD parts** (each part holds an Insert Part of one body, linked to this part, so changes you save here flow on to them; save this part first), **FDCAD parts**, **STEP**, **STL** or **3MF** files. The files are named after the part and the body number. The pieces of a Split are bodies of the part, so this works for them too.
3. An FDCAD Part file opens as an imported body you can edit with the direct editing tools.
4. Saving does not change your part.

## Moving a feature to another body

In a part with two or more bodies, a cut, boss, sweep, loft or hole can be moved so it acts on another body. Right click the feature in the tree, choose **Move to Body...** and pick the body. The feature then cuts or joins that body only; the other bodies stay as they are. Its sketch does not move, so the feature keeps its place and shape. The feature's Bodies box shows the chosen body; set it back to All bodies to act on every body again.

## Linked Body Copy

**Linked Body Copy** (Bodies tab, in the dropdown with Move and Copy Body) copies bodies to a place of their own, and the copy follows every later change of the original: holes, fillets or bosses you add to the original afterwards, even further down the tree, show on the copy too.

1. Click **Linked Body Copy** and pick the bodies.
2. Choose **Place by**: **Offset** (Delta X, Y, Z and turns about X, Y and Z about the bodies' centre) or **On a coordinate system**: the copy sits on the picked coordinate system or plane the way the original sits on the origin.
3. Click OK.

Linked copies, and features built on their faces, are built after every other feature, so they always see the finished original. Right click a linked copy in the feature tree and choose **Break Link** to make it independent: the tree takes the order the features are built in, and from then on the copy stays as it is. Undo brings the link back. A Move and Copy Body copy is independent from the start.

## Move and Copy Body

**Move and Copy Body** moves, turns or copies whole bodies.

1. Click **Move and Copy Body** and pick the bodies.
2. Choose Translate or Rotate.
3. Translate by: Delta X, Y, Z; Along an edge (pick an edge and type a distance); or Vertex to vertex.
4. Rotate: about an edge with an angle, or about a rotation origin with angles about X, Y and Z. The angles are applied in that order.
5. Frame to frame: in Body frame, click the origin (a vertex, or a round edge for its centre), then a flat face or straight edge for Z, then a straight edge for X if you want it. Pick the Target frame the same way. The body moves so its frame lands on the target: its Z ends along the target's Z. Tick Reverse direction to turn the target Z round, for example to set a face down on another face.
6. By relations: in **Body items** click a flat face, round face or edge of the body for each relation, and in **Target items** what each one relates to (a face, edge, plane or axis), in the same order. In **Relations** type one relation per pair, separated by semicolons: `coincident` (two flat faces lie on each other, facing each other, or two axes line up), `distance 5` (two flat faces face each other 5 mm apart), `angle 90` (the normals or axes are that many degrees apart) or `parallel`. All of them hold at once, like mates: for example `coincident; distance 5; coincident` sets a block on a plane, 5 mm from a second plane and against a third. If they cannot all hold, the feature says so; remove one or change a value.
6. Drag the transform handles in the view if you like. Arrows move, rings turn, and the panel follows. Click OK.

Options: tick **Copy** and set **Copies**. Each copy moves one step further than the last.

## Delete and Keep Body

**Delete and Keep Body** removes bodies from the part from this point in the tree.

1. Click **Delete and Keep Body** and pick the bodies.
2. Choose Delete, to remove the picked bodies, or Keep bodies, to keep only them.
3. Click OK.

Common error: deleting every body is refused. Keep at least one.

## Hiding and isolating bodies

Use these when a part has several bodies and one is in the way.

- **Isolate** (I): show only the bodies you picked (a face, edge or vertex of each, or their rows in the Solid Bodies folder). Press it again to show the others. Preferences > General > Other bodies while isolating chooses how the others look meanwhile: Hidden (the default), Transparent or Wireframe. Transparent and wireframe bodies are only for reference: they cannot be picked. Pressing I again or Esc draws them as normal.
- **Hide or Show** (H) with a body picked: hide that body, or show it again.
- **Show Hovered Body** (Shift+Tab): hold the cursor over where a hidden body is and press it to bring that body back.
- **Show All Hidden Bodies** (Ctrl+Shift+Tab): show every hidden body.
- **Make Body See Through** (right click a body in the Solid Bodies folder): draw only that body see through, so you can look inside or behind it. Choose **Make Body Solid** to turn it back. Toggle Transparency (Shift+T) still makes the whole part see through.
- **Display Mode** (right click a body in the Solid Bodies folder): draw that body Shaded With Edges, Shaded or Wireframe whatever the view's display style. **As the View** follows the style again.
- **Display States** (View menu): save the bodies' display (which are hidden, their colours, which are see through, and their display modes) under a name with **Save Current...**, and bring it back with **Apply**. **Link to Active Configuration** makes that configuration show the state whenever it becomes active.
- **Transparency...** (same menu): how see through that body is, from 0 (solid) to 90 percent. It is saved in the part.

Hiding and see through only change what you see. Hidden bodies still take part in features, measuring and exports. Both are saved with the part and can be undone.

## Transform Handles

Pick a body (a face, edge or vertex of it, or its row in the Solid Bodies folder) and run **Transform Handles**. Arrows and rings appear on the body:

- Drag an arrow to move the body along X, Y or Z.
- Drag a ring to turn the body about its centre.

**Handle at** puts the handles on the bodies' centre or on a picked point: picking a point moves only the handle, so turns about the centre then go about that point. **Handle axes** uses the model's X, Y and Z, or a picked plane's own X, Y and normal, for Delta X, Y, Z and the turns. A ruler or a protractor appears while you drag; near it the value snaps to the ticks. Click the value beside the handle to type it. The result is a Move and Copy Body feature in the tree that you can edit later. With Scale, small cubes replace the arrow heads and dragging them sets the scale factor.

## Scale

**Scale** makes bodies larger or smaller.

1. Click **Scale**. Pick bodies, or pick none to scale every body.
2. Choose **Scale about**: the centre of the bodies, the origin, or a point typed as X, Y and Z.
3. Leave **Uniform scaling** ticked and type one **Factor**, or untick it and type X, Y and Z factors.
4. To slant the bodies, type a **Shear angle** (under 80 degrees) and choose **Shear along** and **Shear by height along**: the bodies slide along the first axis by their height along the second. A shear keeps the volume. Leave the angle at 0 for no shear.
5. Click OK.

Tips: factors must be between 0.001 and 1000. A per axis scale turns circles into ellipses.

Common error: "The scale factor must be between 0.001 and 1000." Type a factor in that range.

See also: [Typing values](typing-values.md) for units and formulas in every field.

## Table Driven Pattern

**Table Driven Pattern** copies the picked features, faces or bodies to X and Y positions from a table. Pick a **Frame** (a plane, flat face or coordinate system) to measure along its axes from its origin; without one, the part's X and Y axes are used. Pick a **Reference point** on the seed, or the seed's centre is used: each copy puts that point at a row's position, and keeps the seed's height above the frame.

Type rows in the table, **Paste** rows copied from a spreadsheet (two columns), or **Load File** to read a text file with two columns. **Save File** writes the table to a text file. Untick **Use** on a row to leave that copy out. The table is kept in the part, so the file is not needed to rebuild.

## Offset Body

**Offset Body** moves every face of a body out by a **Distance**, or in with **Shrink**. **Corners**: Sharp keeps the edges sharp, Rounded rounds the outside edges and corners with a radius equal to the distance. In a part with several bodies, click a face of the body to offset. Faces keep their names, so features after it stay attached. To move only some faces, use Offset Face.

**Shell** has the same **Corners** choice for its walls: Automatic (sharp, or rounded where sharp corners fail), Sharp or Rounded.

## Locking a body

Right click a body in the Solid Bodies folder and choose **Lock Body** for a body you only want to look at, such as an imported board. It stays visible, drawn grey, and clicks pass over it, so its faces and edges are never picked by accident and tools cannot change it. Hovering still shows it, and Measure can still use the view around it. Choose **Unlock Body** to work on it again. The lock is saved with the part and is one undo step.

## Combine options

- **Exclusive** keeps only what lies inside an odd number of the picked bodies, so where two bodies overlap is removed.
- **Fragments (every piece)** cuts the picked bodies wherever they cross and keeps every piece as its own body.
- **Inside at least** keeps only the volume inside at least **Number of bodies** of the picked bodies.
- **Keep tool bodies** leaves the tools in the part: for Subtract the bodies you subtracted, for the others every picked body but the first.
- **Keep largest piece only**: when the result falls into separate pieces (a subtract that cuts a body in two, for example), only the biggest stays.
- **Reapply fillets** (Add, Subtract and Common): rounds on a picked body that touch or reach into another picked body are removed first and made again after the combine, with the same radius, on the pieces of their edges that are left. For Subtract only the main body's rounds count. New edges where the bodies meet stay sharp.

## Counts of zero and one

A pattern count can be 1 or 0, which helps when a configuration or design table drives it. With 1 the pattern keeps just the original. With 0, or when every feature it copies is suppressed, the part is left as it was and the pattern shows a warning saying so, instead of failing.

## Half lap joints

For two plates that cross (for example the dividers of a box insert), choose **Half Lap** and pick both plate bodies. FDCAD notches the first plate from one side and the second from the other, so they slide together and finish flush.

- **Depth (%)**: how far the first plate's notch goes into the crossing; 50 splits it half and half.
- **Clearance**: added across each notch so the plates slide together.
- **Kerf**: the width your laser or saw removes; the notches are made that much narrower so the cut parts still fit. Leave it at 0 for printed parts.

## Finger joints

For a box made of plates, model the plates so they overlap at each corner (both drawn out to the outside of the box). Choose **Finger Joint** and pick the two plates of one corner. The corner block they share is split along the edge into **Fingers**: the first plate keeps every other finger and the second plate keeps the rest, so the plates lock together. Odd finger counts look the same at both ends. **Clearance** widens every gap; **Kerf** is the width your laser removes, so the gaps are made that much narrower and the cut parts fit. Then export each plate's face as a DXF for cutting.

## Point Pattern

**Point Pattern** (in the pattern list) copies features, faces or bodies to places on the part itself, without a sketch. Pick:

- **Points**: vertices, round edges (the copy goes to the circle's centre) or hole walls (to the hole's axis).
- **Faces with holes**: every round hole through these faces gets a copy. Handy for adding a counterbore or a boss at every existing hole.

Right click a face of any copy in the view and choose **Edit Seed** to open the original feature the pattern copies. The original's own spot is skipped. For round edges and holes, copies keep the original's height along the hole's axis, so a counterbore copied to every hole sits on the face like the first one. Pick a **Reference point** on the original if its centre is not the spot that should land on each point.

## Select bodies by size

After an import or a split a part can have many small leftover bodies. **Tools > Select Bodies by Size** measures every body, then the **Size limit** slider (a percent of the largest body) picks those **Smaller than the limit** or **Larger than the limit**; the box says how many. **Select** selects them in the view, **Delete** removes them, and **Keep Only These** removes all the others. Delete and Keep add one Delete Body feature, so they undo in one step and can be edited later.

## Indent

**Indent** (3D Print tab, in the Half Lap dropdown) reshapes one body round another. Pick the target body, then the tool body, for example a box and a battery or circuit board placed where it should sit. The tool body stays as it is.

* **Mode Indent** gives the target a wall of the chosen **Thickness** round the tool, a **Clearance** away from it, where the tool presses into or stands beside the target, and takes out the space the tool needs. The wall stays within one thickness of the target.
* **Mode Cut** only takes out the space the tool needs, grown by the clearance: a pocket that follows the inserted part.

If the tool does not reach the target, move it against or into the target. A tool with very small details may not grow by a large clearance: use a smaller one.

## Named faces and edges

Give a face or an edge a name of its own, such as Lid or Rim.

1. Right click the face or edge in the 3D view and choose **Name This Item**.
2. Type the name. Use letters, digits, spaces and underscores, starting with a letter.

The name stays with the face or edge when the features above it change. Naming an item that already has a name renames it. Bodies get names with Rename Body (see the printing guide).

**Tools, Named Items** lists every named face, edge and body. Click a face or edge in the list to pick it in the 3D view. Rename and Remove Name change the chosen name; the face or edge itself stays.

Uses:

- Custom property formulas can read `"area@Lid"` for a named face (mm²) and `"length@Rim"` for a named edge (mm). The values come from the finished part, so feature formulas cannot use them.
- In the node editor, a Model Reference made with Use Selection from a named face or edge keeps the name, so it follows the item.

## Mould Cavity

**Mould Cavity** cuts the shape of a part out of a block, to make a mould.

1. Make the block and the part as two bodies, with the part inside the block (untick Merge result for the second one).
2. Click **Mould Cavity**. Pick the block as **Main body** and the part as **Part**.
3. **Scale about**: the centre of the part, the origin, or a coordinate system you pick.
4. Type the scale for shrinkage, such as 1.02 for a material that shrinks 2%. Untick **Uniform** to type a scale along X, Y and Z.
5. Untick **Keep part** to leave only the block with its cavity. Click OK.

The scale must be between 0.5 and 2. To split the block into two halves, use Split with a plane after the cavity.

## Joint

**Joint** makes the cut where two bodies meet, so they fit together like woodworking joints.

1. Model the two bodies touching on a flat face, such as an upright standing on a base.
2. Click **Joint** on the 3D Print tab. Pick the body to cut first, then the body that goes in.
3. Pick the **Joint**: Groove (dado) or Rabbet (the second body's whole end goes into the first; at the first body's edge the groove is a rabbet), Mortise and tenon (a tenon smaller than the end by the **Shoulder** on every side) or Dowels (two holes across the joint for dowels of the **Dowel diameter**).
4. Set the **Depth** into the first body and the **Clearance** round the part that goes in.
5. Click OK.

Tips:

- For a groove or a tenon the second body grows by the depth; the first gets a pocket the clearance larger.
- Dowel holes go the depth into both bodies, the clearance larger than the dowel.

