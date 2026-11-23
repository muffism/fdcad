# Holes and fastening

These tools add the details that hold parts together: standard holes, threads, screw bosses, snap hooks, lips and vents. Rib, Dome and Wrap shape a part's surface. Many sizes come from published ISO and ANSI tables, and several options help printed parts fit.

Where to find it: Features tab, Remove Material group: Hole Tool, Thread and Cosmetic Thread share one dropdown button, between Extruded Cut and Revolved Cut. On the 3D Print tab, Print Features group, Mounting Boss is a large button; Snap Hook and Snap Hook Groove share a dropdown; Lip and Groove and Vent have their own buttons. Rib, Dome and Wrap each have a button in the Features tab, Modify group. All are in the Insert menu. None has a default key. A dropdown shows the tool you used last.

Favourites: every feature panel has a **Favourites** box. **Save** the current settings under a name, then **Apply** them later. You can also **Update**, **Rename**, **Delete**, **Export** and **Import** favourites; the list is in name order. **New ones start with** chooses what a new feature of that type starts with when you run its command: **Factory settings**, **Last used** (the settings of the last one you made) or one of your favourites. Picks such as faces and sketches are never saved, and a favourite never changes whether the command makes a boss or a cut.

## Hole Tool

**Hole Tool** makes holes of one type and size at points on a face. Each hole type is its own feature.

1. Click **Hole Tool**. The panel has two tabs: **Type** and **Positions**.
2. On the Type tab, choose the **Type**, **Standard** and **Size**. The values below fill in from the size table.
3. Choose the **End Condition**: Blind with a **Depth**, Through All, Up to Next (each hole stops where it first comes out of the material), Up to Vertex (each hole stops at the level of a picked vertex), or Up to Face.
4. On the Positions tab, click the face. Each click on it places another hole.
5. To move a hole, type its X and Y in the points table. **Remove Point** deletes the selected one.
6. For a ring of holes, click the centre of the ring, then type the count and the circle diameter in **Bolt Circle**, such as `5x100` (five holes on a 100 mm circle), with an optional start angle, and click **Make**. The clicked centre point is replaced by the holes. The size can be a formula, such as `6x=pcd`.
7. Click OK.

Hole types:

* **Simple**: a plain hole. Its **Purpose** is Drill Size, Tap Drill or Screw Clearance.
* **Counterbore**: a clearance hole with a flat bore for a socket head screw.
* **Counterdrill**: a counterbore whose floor is a cone down to the hole, as a stepped drill leaves it. The **Counterdrill Angle** is the cone's included angle (118 degrees by default); the bore sizes come from the counterbore table.
* **Countersink**: a clearance hole with a cone for a flat head screw.
* **Straight Tapped**: a tap drill hole with a thread. Tick **Cosmetic Thread** to show the thread, or **Modelled Thread** to cut a real thread that prints.
* **Tapered Pipe Tapped**: a hole for a tapered pipe thread. With ANSI Inch the sizes are NPT (1/16 NPT to 2 NPT), with ISO Metric they are Rc (Rc 1/8 to Rc 2). The wall tapers 1 in 16 on the diameter from the face down to the tap drill at the thread depth, which is the standard's thread length. Tick **Cosmetic Thread** to show the thread; a modelled tapered thread is not offered.
* **Heat Set Insert**: a hole sized for a heat set insert (M2 to M8, #4-40 to 1/4-20). **Edit Insert Table** changes the sizes. They are kept in the preferences. Its **Depth margin** adds extra depth to every insert hole filled from the table, so melted plastic has room below the insert (0 by default). For an entry chamfer that guides the insert in, tick **Near Side Countersink**.
* **Hex Nut Trap**: a hexagon pocket of the nut height over a clearance hole.
* **Captive Nut Slot**: a hexagon with a slot below the face so a nut slides in from the side. Set **Slot Offset** and **Slot Length**.

Slots: tick **Slot** on the Type tab of a Simple, Counterbore or Countersink hole to make a slot at each position. Enter the **Slot Length** and choose how it is **Measured**: Centre to Centre (between the centres of the two round ends) or Overall (end to end). **Slot Angle** turns the slot in the face plane; 0 runs it along the X axis of the position sketch. The print fit widens the slot like a round hole. Slots are not offered for tapped holes, inserts and nut traps; if Slot stays ticked after changing the type, a warning says it is not used. The heat set insert table refuses a row with a missing name or a diameter or depth that is not above zero, and names the row.

Main options:

* **Standard**: ISO Metric or ANSI Inch.
* **Fit**: Close, Normal or Loose, for screw clearance holes. Inch Close and Normal holes are common drill sizes, a little tighter than many clearance hole charts; choose Normal or Loose when a screw must pass freely.
* **Bottom**: Flat (prints best) or Drill Point with a **Drill Point Angle**. Tick **Depth Includes Point** to have the tip, not the straight wall, reach the depth.
* **Head Clearance**: carries the head bore up above the face.
* **Taper** (simple, counterbore, countersink and tapped holes): the whole wall narrows toward the bottom by the **Taper Angle**, measured from the axis. A taper cannot be used with a slot or a far side countersink, and must be less than 45 degrees.
* **Near Side Countersink** for Simple, Tapped and Heat Set Insert holes, and **Far Side Countersink** for Through All holes.
* **Position Sketch**: use the points of an existing sketch. Tick **Points**, **End Points** and **Centres** to choose which points count. On the Positions tab, click near one of its points to skip it (no hole there); click it again to bring it back. The hole count follows.
* **Place by**: with **Distances from Two Edges**, pick the face, then two straight edges of it, and type how far the hole's centre is from each (measured on the face, toward its middle). With **Concentric**, pick the face and a round edge or cylinder; the hole goes on its axis, for example a counterbore over an existing hole. Either makes one hole with no sketch. **Points** places holes at clicked or sketch points as before.
* **Start plane**: optional, a flat face whose plane the holes start on instead of the face they are placed on.
* **Place by: Distance and Angle from an Axis**: pick a round or straight edge, then type the distance from its axis and the angle round it, measured on the face from its X direction, for holes on a bolt circle drawn without a sketch. **On a Point**: pick a vertex or sketch point; the hole goes there, seen straight onto the face.
* **Hole axis**: optional, a straight edge the holes run along instead of square to the face, for slanted holes.
* **Custom Stack** (hole type): type the hole's elements from the face inward in **Elements**, each a kind, a diameter and a length, separated by semicolons: `counterbore 10 3; countersink 8 90; straight 5 12`. A countersink takes its angle instead of a length and runs down to the next element. Kinds are straight, counterbore, tapped and countersink; the last must be a bore. Reorder the elements by editing the list. The hole is as deep as its elements.
* **Load User Sizes...** (Type tab): load your own sizes from a comma separated file with a header row of `name,diameter` and optionally `pitch`, `tap_drill`, `clearance_close`, `clearance_normal`, `clearance_loose`, `head_diameter`, `head_height`, `csk_diameter`, `nut_flats` and `nut_height` (mm). Choose the **User Sizes** standard to use them. They are kept for next time.

Sizes: ISO metric coarse from M1.6 to M48 and the common fine pitches (named like M10x1.25), and inch Unified coarse, fine and extra fine from #0-80 to 1 inch. Inch drill sizes show their drill name under the size, for example "Drill: #7".

Heads: a counterbore's **Head** is Socket Head, Button Head, Low Head Socket, Pan Head, Cheese Head or Socket Head on Washer (a washer seat), and fills the counterbore diameter and depth. A metric countersink's **Head** is Socket Flat Head or Cross Recessed Flat Head. A head the standard has no size for leaves the values as they are.

Print fit: **Print Fit** adds the printer's **Fit Tolerance** (per side) to every diameter of the hole (counterbores and countersinks too) and to a nut trap's width and height, inserts included. **Clearance** adds it twice, **Slip** once, and **Press** adds nothing so the part grips. The tolerance comes from the printer profile, 0.2 mm by default.

**Fit Table...** keeps a gap per side by size and direction, because printed holes come out smaller upright than lying down, and small holes more than large ones. Type one row per line: `hole` or `outside`, `flat`, `upright` or `any`, the largest diameter the row covers, the gap per side and, optionally, the nozzle size, such as `hole upright 6 0.25`. **Fit from Table** sets this hole's Fit Tolerance from the table for its diameter and direction; the note says which row was used. FDCAD then makes the hole larger in the model, so turn off the slicer's own hole compensation, or set the gap to 0 and let the slicer do it.

Print top: **Print Top** gives a hole that runs sideways a **Teardrop** (pointed) or **Flat Bridge** top toward the printer's up, so it prints without supports. Up is the model's +Z, or straight up off the bed when you used Lay Face Flat. A hole that runs up and down stays round.

Head down bridge: for a counterbore or countersink printed with its head facing down, **Head Down Bridge** leaves material so the step over the small bore prints cleanly. **Sacrificial Layer** leaves one layer over the bore, which you drill out after printing. **Stepped Layers** leaves two layers: a slot as wide as the bore across the head, then a square, which print as bridges. Set **Layer Height** to your printer's layer height.

Tips: holes work on flat and curved faces. All holes of one feature are cut together. Every value can be typed over.

Common errors:

* "Point is not over the picked face." Move the point onto the face or pick another face.
* "The counterbore diameter must be larger than the hole diameter."
* "The thread depth is larger than the hole depth." Make the thread shorter or the hole deeper.

## Cosmetic Thread

**Cosmetic Thread** marks a thread on a hole or shaft without modelling it. It shows as rings on the face and is stored as size, pitch and length. A length longer than the shaft or hole is shown only as long as the face, with a warning that says so. The length you typed is kept, so a longer shaft later shows the whole thread.

1. Click **Cosmetic Thread**.
2. Click the round edge where the thread starts.
3. Choose the **Size**. **Thread Diameter** and **Pitch** fill in.
4. Choose **End Condition**: Blind with a **Length**, or Full Length. Tick **Reverse** to run the other way.
5. Click OK.

Tip: STEP export writes each thread as a note in the file header. See [Import, export and print](import-export-print.md).

## Thread

**Thread** models a real helical thread that prints.

1. Click **Thread** and click the round edge of a hole or shaft.
2. Choose the **Size**. Diameter and pitch fill in.
3. Choose the end: Blind with a **Length**, **Revolutions**, or **Up to Selection** (a vertex, flat face or plane).
4. Choose the **Method**: Cut Thread or Extrude Thread.
5. Click OK.

Options: **Start Offset**, **Start Angle**, **Reverse**, **Keep Thread Length**, **Hand** (Right Hand or Left Hand) and **Starts** (1 to 4).

Printing: **Profile** is Standard 60 Degree (the nominal V), **Printable 90 Degree** (flanks at 45 degrees, which print standing up without supports) or **Round** (a coarse half round groove a quarter of the pitch deep, for caps and jars: set any **Pitch**). For power screws, lead screws and pipes there are also **Metric Trapezoidal 30 Degree** and **ACME 29 Degree** (half a pitch deep), **Square** (half a pitch deep, groove and land each half the pitch), **Buttress 7 and 45 Degree** (0.6 pitch deep, for loads in one direction) and **Pipe 55 Degree** (the Whitworth form of pipe threads, with flat crests and roots in place of round ones). Type the diameter and pitch of these sizes; the size list holds the 60 degree sizes. A printable thread is shallower, so its hole is larger: the thread diameter minus 0.625 times the pitch. **Print Fit** adds clearance per side from the printer's **Fit Tolerance**: a hole's thread grows, a shaft's shrinks. **Lead In** cuts a 45 degree cone at the start so the thread does not start as a thin edge.

**Taper Angle**: a tapered thread, such as a pipe thread. Type the half angle of its cone: 1.79 degrees for NPT and Rc pipe threads (1 in 16 on the diameter). A hole's thread narrows going in and a shaft's widens away from its end. Leave it at 0 for a straight thread.

**Load User Sizes...** (Thread and Cosmetic Thread): the same size file as the Hole Tool's. Its sizes join the size list; choosing one fills the diameter and pitch, and the thread class when the file has a `class` column. To put the same thread on another cylinder, press Enter (Repeat Last Command) and click the round edge: Thread remembers the last size.

**Thread Relief** (Thread, and tapped holes in the Hole Tool): a run out groove where the thread ends, sized from the pitch as in DIN 76-1. On a shaft it is the diameter less 1.6 pitches across and 3 pitches long; in a hole the diameter plus 0.3 mm across and 4 pitches long. **Entry Chamfer** (tapped holes): a 90 degree countersink to 1.05 times the thread diameter. On Thread, **Lead In** is the end chamfer.

**From a Sketch** (Profile): draw the thread's section as one closed region in any sketch and choose it in **Profile Sketch**. Its X runs along the thread and its Y is the depth into the material (or the height off the face for an extruded thread), from the region's lowest point, which sits on the face. **End Finish**: **Square** stops at full depth; **Chamfer** runs the depth out at 45 degrees; **Fade Out** runs it out over the last pitch, as a cutting tool leaves it.

**Thread Class** sets the tolerance class: capital letters (such as 6H) or B classes for a hole, small letters (such as 6g) or A classes for a shaft. Classes with an allowance (6g, 6G, 6f, 6e, 1A and 2A) make the thread that much looser, half the allowance per side, unless a clearance is typed. A tapped hole has the same list for holes; its class shows in the Hole Table's thread column, for example `M5 6H`. Choosing a shaft class for a hole, or the other way round, gives an error that says which kind to choose.

Tip: profiles are nominal. Check the fit on a test print.

Common errors: "The picked edge is not the round end of a hole or shaft." "The thread has more than 400 turns." Make it shorter or use a cosmetic thread.

## Mounting Boss

**Mounting Boss** adds a boss for a screw or a pin, with optional fins.

1. Click **Mounting Boss** and pick the **Face**, flat or curved.
2. Click on the face to set the position, or pick a vertex or round edge.
3. Choose the boss type: Screw Boss, Thread Side; Screw Boss, Head Side; Pin Boss, Pin; or Pin Boss, Hole.
4. Set the sizes and click OK.

Options: **Boss Diameter**, **Boss Height**, **Draft**, hole, head bore and pin sizes. Fins: **Number of Fins** (0 for none, at most 12), **First Fin Angle**, **Equally Spaced**, **Fin Length**, **Fin Width**, **Fin Height**, and an end chamfer.

Sizes from the mating part: click the face of the other half in **Up to Mating Face** and the boss reaches up to it, less the **Gap to Mating Face**, in place of the typed height. For a pin boss, click the round edge of the hole the pin goes into (or the pin a pin hole takes) in **Pin Size from Edge**: the pin is that size less twice the **Pin Clearance** (a pin hole: plus). The fin direction can already be set by a picked edge.

**Step Height** and **Step Diameter**: a narrower collar on top of the boss, for example to locate it in a hole of the mating part. The hole or pin starts on top of the collar. A Step Height of 0 makes none. The fin direction can also come from a picked face: the fins then point along its normal.

## Snap Hook

**Snap Hook** adds a cantilever snap hook.

1. Click **Snap Hook** and click a point on a face or edge.
2. Set the **Up Direction** and **Hook Direction** (each can be reversed).
3. Type the **Body Height**, or take it from a face with **Height From Face**.
4. Set the Hook Data and click OK.

Hook Data: **Base Depth**, **Top Depth**, **Total Width**, **Overhang**, **Hook Height**, **Lip Height** and **Top Draft**.

## Snap Hook Groove

**Snap Hook Groove** cuts the groove a snap hook catches in.

1. Click **Snap Hook Groove** and choose the **Snap Hook**.
2. Click a face of the **Body to Cut**.
3. Set the Groove Data and click OK.

Groove Data: **Offset Height**, **Hook Height**, **Gap Height**, **Groove Clearance**, **Gap Clearance** and **Offset Width**. The groove follows any draft of the hook.

## Lip and Groove

**Lip and Groove** adds a lip on one rim and a matching groove in the other, for example on the two halves of an enclosure.

1. Shell the parts first, so each has a flat rim round an opening.
2. Click **Lip and Groove**. Pick the **Lip Rim Faces**, the **Groove Rim Faces**, or both.
3. Set the sizes and click OK.

Options: **Lip Height**, **Lip Width**, **Lip Draft**, **Groove Width**, **Groove Height**, **Groove Draft**, **Spacing** and **Gap**. **Link Matched Values** makes the groove width the lip width plus spacing, and the groove depth the lip height plus gap. Spacing is the whole gap across the lip (both sides together). The printer profile's fit tolerance, the Hole Tool's Print Fit and Split for Printing's Clearance are per side, so a spacing of twice the fit tolerance gives the same fit.

Instead of the rim face you can pick an edge round the opening in **Lip Rim Edges** or **Groove Rim Edges**; the flat rim it is on is used. **Jump Gaps** runs the lip and groove straight across notches in the opening narrower than the value, such as where ribs meet the wall at the rim; 0 follows every notch. **Follow Wall Draft** leans both walls of the lip and groove with the part's wall below the rim, so a drafted wall keeps its draft; Lip Draft still narrows the lip on top of that.

Common error: a band wider than the wall fails. Make the lip or groove narrower.

## Vent

**Vent** cuts a vent with ribs and spars from a sketch.

1. Sketch the vent on or parallel to a flat face.
2. Click **Vent**, choose the **Sketch** and pick the face.
3. In the table, give each curve a role: Boundary, Rib, Spar or Fill In Boundary.
4. Set the widths, depths and offsets and click OK.

In **Draft and Fillet**, each group (ribs, spars and fill) can have its own **Draft**, which narrows its bars going into the wall, and **Fillet**, which rounds the edges of their outer face. The ends where a bar meets the opening's wall stay square, so the bars stay joined to the part. 0 leaves them square.

Tips: ribs, spars and Fill In Boundary curves must be straight sketch lines. Spars need at least one rib. The panel shows the total area and the open area percent as you edit.

Common error: "Pick the closed boundary curves of the vent." Give at least one closed set of sketch curves the Boundary role.

## Rib

**Rib** adds a wall from an open sketch. It grows until it meets the part.

1. Sketch an open chain of lines and arcs. For a grid of walls, sketch several chains in the same sketch: lines that cross, or that meet in a T, each make a wall and the walls join where they meet.
2. Click **Rib** and choose the sketch.
3. Set the **Thickness** and **Thickness Side**: First Side, Both Sides or Second Side.
4. Choose Parallel to Sketch or Normal to Sketch and click OK.

Options: **Flip Material Side**, **Ends** (Linear goes straight on, Natural keeps an end arc curving), **Draft** with **Draft Outward** (between 0 and 45 degrees; Normal to Sketch from one straight line only), and **Body** in a multibody part. With a draft, **Thickness** chooses where the rib is as thick as typed: **At Sketch Plane** (it gets thinner toward the wall) or **At Wall** (it is that thick where it meets the part and thicker toward the sketch).

## Dome

**Dome** raises flat faces into domes, or sinks them.

1. Click **Dome** and pick flat faces.
2. Type the **Distance** and click OK.

Options: **Reverse** sinks the dome. **Elliptical Dome** gives round faces a half ellipsoid. **Continuous Dome** gives polygon faces one smooth surface. A distance of 0 works only on a round face, where it makes a dome that meets the side smoothly. A face counts as round when its outline is a circle, whatever the edge is made of: one circle edge, several arcs of one circle, or the round end of a loft or a scaled sweep. Any other face with curved edges needs Continuous Dome. **Direction** (optional): click a straight edge, a flat face or a plane, and the dome rises along it instead of straight up from the face. The base stays on the face. The direction must lean at least 5 degrees away from the face. **Profile sketch** (optional): pick a sketch with a closed outline to set the dome's section. In that sketch X is the distance out from the middle of the face and Y is the height, so draw the outline at X = 0 or more and Y = 0 or more. The outline is turned round the middle of the face and trimmed to the face's edges. The Distance is not used then.

## Roof

**Roof** (Features tab, in the dropdown with Dome) adds a roof of one slope over a closed sketch outline: every face leans at the same **Slope** from the sketch plane, and they meet in hips, valleys and ridges by themselves, also over an L or U shaped outline. Holes in the outline make courtyards with roofs sloping up from them too. **Max height** cuts the roof flat at that height; 0 goes up to the ridges. Choose **Add** or **Cut**. Curved outline edges are followed as short straight pieces.

To grow a body by a small sphere, so every edge and corner becomes round, use **Offset Body** with **Rounded** corners.

## Wrap

**Wrap** puts a sketch onto a cylindrical or flat face.

1. Sketch closed contours on a plane that touches the face. For a cylinder, the plane must be parallel to its axis.
2. Click **Wrap**, choose the **Sketch** and pick the **Face to Wrap On**.
3. Choose Emboss (raised), Deboss (sunk) or Scribe (marks only), set the **Thickness** and click OK.

**Method Project** puts the sketch on any face, whatever its shape, by projecting it along a direction: the pull direction if you pick one, else square to the sketch plane. The sketch does not have to touch the face; a sketch on a plane beside the part works. The outline is the sketch's shadow on the face, so lengths are not kept on a curved face as they are with Analytical and Spline Surface. Choose Emboss or Deboss and type the height; Scribe is not offered.

**Pull Direction** (optional): pick a line, edge or plane, and the walls of the raised or sunk shape run along it instead of square to the face, for example straight up for a part that comes out of a mould. It works on flat faces and cylinders with Emboss and Deboss.

Tip: **Reverse** wraps the other way round the cylinder. Sketch text works well here. See [Sketching](sketching.md).

**Method**

1. Analytical keeps lengths exactly on cylinders and flat faces. The sketch plane must touch the face.
2. Spline Surface works on any face. The sketch origin goes to the nearest point of the face, and lengths match the sketch near that point. The sketch must stay on the face and cannot wrap all the way round.

## Self tapping holes in plastic

Hole type **Self Tapping (Plastic)** is for screws that cut or form their own thread in a printed or moulded part. Pick the screw size: the hole is 0.8 of the screw's size and 2.5 sizes deep, with a 90 degree entry bevel that opens to the screw's size so the screw starts straight. These sizes are FDCAD's own rule, not a standard; **Edit Table** changes them for your material and screws (Reset brings the rule back). Untick the near side countersink to leave out the bevel.

## Shaft Shape

**Shaft Shape** (Features, in the Cut dropdown) changes a round shaft or bore over a length. Click the **Round face**: the outside of a shaft or the inside of a hole. Choose the **Shape**:

- **Hex**: across flats 0.866 of the diameter, so the corners stay on the round.
- **D Flat**: one flat, a tenth of the diameter deep. **Double D**: two opposite flats.
- **Keyway**: a slot a quarter of the diameter wide and an eighth deep.

On a shaft the shape is cut from it. In a bore the hole takes the same shape grown by the **Clearance** on every side, so a shaft made with the same diameter slides in. **Length** limits the shape to that much of the face, measured from the **From end** you choose (leave it empty for the whole face), and **Angle** turns the flats or key about the axis. The sizes are FDCAD's own rules; for standard keys see the key sizes of your standard and type them as a cut.

## Magnet pockets

Choose **Magnet Pocket** as the hole type and pick a size from the list (round magnets by diameter x thickness, block magnets by length x width x thickness). **Diameter** is the magnet's diameter or a block's width, **Depth** is its thickness, and **Block length** is 0 for a round magnet. Set **Print Fit** to get a snug press fit for your printer.

- **Relief slots** add three narrow slots round a round pocket, or small squares at a block's corners, so air and glue can get out and the corners fit.
- **Closed skin** (blind pockets only) leaves that much material over the pocket so it is sealed inside the part. Add a pause in your slicer at the layer where the pocket closes and drop the magnet in.

## Standard keys

With **Shape** set to **Keyway**, choose a **Key standard**. FDCAD reads the shaft or bore diameter and cuts the matching slot:

- **FDCAD Rule**: a slot a quarter of the diameter wide and an eighth deep (the earlier behaviour).
- **Metric Parallel**: parallel keys for 6 to 130 mm shafts. The shaft keyseat and the hub keyway each get their standard depth.
- **Inch Square**: square keys for 5/16 to 4 1/2 inch shafts, half in the shaft and half in the hub.
- **Half Moon**: a half moon (Woodruff) key: the shaft seat is the key's round, centred along the length; the hub gets a straight keyway.

If no standard key fits the diameter, the feature says so; use the FDCAD Rule for that size.

## Dowel pin holes

Choose **Dowel Pin** as the hole type, pick the **Standard** (metric or inch) and the pin **Size**, then the **Pin fit**:

- **Press**: the hole is the pin's nominal size. Dowel pins are made slightly over size, so the pin grips.
- **Slip**: the hole is 0.02 mm larger so the pin slides in, for the part that comes apart.

The depth starts at one and a half times the pin diameter. For printed parts, also set a **Print Fit** to make up for holes printing small. A blind press fit hole traps air: a small vent hole helps.

## Bearing seats

Choose **Bearing Seat** as the hole type and pick the bearing's designation, for example **608** or **6001**. FDCAD fills in:

- the seat for the outer ring (the bearing's outside diameter, as deep as the bearing is wide),
- a smaller hole below it, half way between the bearing's bore and outside diameter, so the outer ring sits on a shoulder while the inner ring turns freely.

**Pin fit** chooses **Press** (the seat is the bearing's size) or **Slip** (0.02 mm larger). For printed parts add a **Print Fit** too. Tick **Retaining ring groove** to cut a groove for an internal ring above the bearing; the seat gets deeper by the groove plus a 0.5 mm land.

## Ring grooves

Choose **Ring Groove** (Features tab, with Shaft Shape) and click the round face of a shaft or a bore. Pick the **Ring**:

- **Retaining Ring**: on a shaft, a groove for an external ring; in a bore, one for an internal ring. The round must be a standard ring size (for example 10, 12 or 15 mm); otherwise the feature names the nearest sizes.
- **E Clip**: shafts only, for 2.5 to 24 mm shafts.

**Position** is how far the groove starts from the chosen end of the face (**From end**). The groove's diameter and width come from the standard tables.

## O ring grooves

Choose **O Ring Groove** (Features tab, with Ring Groove).

- For a seal on a shaft (piston seal) or in a bore (rod seal), click the round face and set **Position** and **From end**.
- For a seal between two flat faces, pick a sketch on the face instead: its closed curve is the centre line of the ring (a circle for a round lid, a rounded rectangle for a box).

Type the ring's **Cross section** (its cord thickness, for example 1.78, 2.62, 3.53 or 5.33 mm for the common inch series) and the **Use**: **Static** for a seal that does not move, **Moving** for a rod or piston that slides, **Face Seal** for flat faces (chosen by itself with a sketch). FDCAD sizes the groove so the ring is squeezed about 20, 15 or 25 percent and leaves room for it to swell. If the squeeze falls outside 10 to 30 percent or the ring fills more than 85 percent of the groove, the feature warns.

## Keeping the size between hole types

When you change the hole type, the Hole Tool keeps the size you had (an M5 counterbore becomes an M5 tapped hole). Untick **Keep size when the type changes** to have each hole type start with the size you last used for it instead, for example M3 for tapped holes and M5 for counterbores. The choice is remembered for every part.

## Hole Table

**Tools, Hole Table** lists every hole and thread of the part from its last rebuild: a row per hole, tagged by feature (A1, A2 for the first Hole feature, B1 for the next), with its type, size, diameter, depth (or Through), thread, how many holes the feature makes, and its X, Y and Z position. Threads from Cosmetic Thread and Thread features are listed too. Lengths are in the part's units. **Copy** puts the table on the clipboard to paste into a spreadsheet; **Save CSV** writes it to a file.

Hole values in formulas: every value a Hole feature stores, such as `"diameter@Hole 1"`, `"depth@Hole 1"` or `"cbore_diameter@Hole 1"`, can be used in a formula, and `"count@Hole 1"` is the number of holes the feature made in the last rebuild. Use the count only in features below the hole: a feature above it builds before the holes are counted, and says so.
