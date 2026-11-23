# Import, export and print

FDCAD reads STEP and mesh files, writes STEP, STL, 3MF, DXF and SVG files, and has tools that get a part ready for a 3D printer. Imported files are stored inside the `.fdprt` part file, so the part opens on any computer without the original file. Print orientation and printer profiles change only what is exported. They never change the model.

Where to find it: the Bodies tab, Import group; the 3D Print tab; the Insert menu; File, Save As and File, Export; Tools, Preferences, Printing.

## Opening STEP, IGES and mesh files

File, **Open** (Ctrl+O) accepts `.step`, `.stp`, `.igs`, `.iges`, `.stl`, `.3mf` and `.obj` files as well as `.fdprt` parts and older `.fdef` parts.

You can also drop part, STEP, IGES and mesh files onto the FDCAD window to open them.

1. Choose File, Open and pick a STEP, IGES or mesh file.
2. FDCAD makes a new, unsaved part. The file becomes the first feature after the default planes.
3. Read the status bar after the rebuild. It says what was imported and what was repaired.
4. Save the part as a `.fdprt` file to keep your work.

Tip: STL and OBJ files have no units, so FDCAD reads them as millimetres. If the file was saved in inches, centimetres or metres, edit the Mesh feature and choose that unit in its panel. 3MF files carry their own unit. 3MF objects made of components, and mirrored items, are read too.

## Import STEP Body

**Import STEP Body** adds the body from a STEP or IGES file to the part that is open. It keeps the colours from a STEP file.

1. Open the part you want to add to.
2. Click **Import STEP Body** on the Bodies tab, or choose Insert, Import STEP Body.
3. Pick a `.step`, `.stp`, `.igs` or `.iges` file.
4. The import appears in the feature tree as one feature. Undo removes it in one step.
5. Read the status bar for the import report.

Main options (double click the feature to edit it):

- File: the name of the imported file.
- Merge with the part: join the imported solid to the part's body. When it is off, the import stays a separate body.

Tips:

- FDCAD heals the shape on import. Loose faces and open shells are sewn together, and every closed shell becomes a solid. The report names what changed.
- Faces keep their colours from the file. Colours you set with **Appearance** win over them.
- An imported body has no sketches or feature values. Change it with **Move Face**, **Offset Face** and **Delete Face** (see [modify.md](modify.md)), or add features on top of it.

Common errors:

- "No closed solid" after healing: the file holds only surfaces. FDCAD works with solids only. Export a solid from the program that made the file.
- "The surfaces do not close a volume" (IGES): the message says how many gaps are left and where. Right click the import and choose **Heal...**, then type a larger gap, for example 0.1 mm. FDCAD reads the file again and closes gaps up to that size. Undo takes the heal back.
- A warning that the solid is still invalid: run **Geometry Check** to find the bad faces, then try Delete Face on them. See [evaluate.md](evaluate.md).

## Pick Bodies

When a STEP or IGES file holds more than one body, Insert, STEP opens a list of its bodies after the file is read. Each row gives the body's number, volume and size, and the ticked bodies are drawn in the view.

1. Untick the bodies you do not want.
2. Click OK. The import keeps only the ticked bodies.

To change the choice later, right click the import in the feature tree and choose **Pick Bodies...**. Faces keep their names, so features built on a kept body stay in place.

## Replace From File

Right click an imported STEP or mesh body in the feature tree and choose **Replace From File...** to read a new version of the file in its place. The import keeps its name and place in the tree, and the features after it rebuild on the new body. A feature whose picked faces or edges are not on the new body shows the usual lost reference error, with its fixes. A STEP or IGES import takes a STEP or IGES file, and a mesh import a mesh file. Undo goes back to the old file.

## Insert Part

**Insert Part** (Bodies tab, Import group, in the dropdown with Import STEP Body) brings the bodies of another FDCAD part into this part as one feature. A part in the same folder or below it is stored by its path from this part's file, so a folder of parts can move to another folder or computer. Pick the part file; the panel then sets:

* **Link to the file** (on): the bodies follow every change saved to that file. If the file is moved or deleted, the feature fails and says where it looked; pick the file again, or break the link.
* **Bodies to bring in**: body numbers such as `1, 3`; empty brings every body.
* **Bring in sketches** and **Bring in planes**: the part's sketch outlines and its own planes show as reference lines.
* **Place by**: an Offset with Delta X, Y, Z and turns, or **On a coordinate system** (the part's origin goes onto the picked coordinate system or plane).

Right click the feature and choose **Break Link** to keep the bodies as they are now, stored in this part; the file is then not read again. A part cannot insert itself, also not through another part. Opening a part never runs anything from the inserted file; it is read as data.

## Import Mesh

**Import Mesh** adds an STL, 3MF or OBJ mesh to the open part. By default the mesh is a reference body: it is drawn in the view but is not part of the solid.

1. Click **Import Mesh** on the Bodies tab, or choose Insert, Import Mesh.
2. Pick an `.stl`, `.3mf` or `.obj` file.
3. The mesh appears in the feature tree and in the view.
4. Double click the feature to see its panel. It shows the file name and the number of triangles.

Main options:

- Convert to Solid: turn the mesh into a solid with flat faces, so features can use it. Large meshes take a while.
- Merge with the part: shown once Convert to Solid is on. It joins the converted solid to the part's body.
- Repair: before the mesh is shown or converted, fills holes, removes repeated triangles, triangles on edges that more than two triangles share, and tiny loose pieces. The status bar says what was fixed. Tick it when Convert to Solid says the mesh has holes.
- Reduce: **Keep percent** or **Keep count** lowers the number of triangles, for meshes that are slow to show or convert. **Largest move** limits how far a corner may move, which can keep more triangles than you asked for. **Keep open edges** keeps the rim of an open mesh where it is.
- One body per part (3MF files from a slicer, once Convert to Solid is on): each part of the file becomes its own body, named as in the slicer. Bambu Studio, OrcaSlicer, PrusaSlicer and Cura project files are read, as well as 3MF files from FDCAD.
- Keep slicer roles: also brings in the modifier, negative volume and support parts, with their print roles, so a later 3MF export gives them back to the slicer. Left off, those parts are left out. You can rename a body or change its role on the body row as usual.

Tips:

- Above 100,000 triangles the feature shows a warning. The mesh still works, but converting it is slow.
- Converting joins triangles that lie in one plane into one face.

Common error: the mesh has holes. Convert to Solid needs a closed mesh. Repair the mesh in a mesh program, or keep it as a reference body.

## STEP export

File, Export, **STEP...** writes the part as a STEP file for other CAD programs.

File, **Save As** (Ctrl+Shift+S) does the same when you pick STEP, STL or 3MF as the file type, or type a name ending in .step, .stp, .stl or .3mf. The part itself stays unsaved; save it as an FDCAD part to keep your features.

1. Choose File, Export, STEP...
2. Pick a folder and a file name, then click Save.
3. The status bar says "Exported" with the file name when it is done.

After you choose the file name, an options window opens:

- **Unit**: millimetres, inches or metres. The sizes are converted, so the part comes in at its true size in any program.
- **Y up**: turns the model so its up direction is Y, for programs that use Y up. FDCAD parts are Z up.
- **Body names**: writes each body with its name (see Rename Body) or Body N, so other programs list them by name.
- **One file per body**: writes each body to its own file, named after the file you chose and the body, for example "bracket_Lid.step".
- **Include hidden bodies**: hidden bodies are left out unless you tick this.

The part keeps your choice for its next STEP export, also from Save As.

Tips:

- STEP files are written in the AP214 form, with the part and face colours.
- STEP export always uses model coordinates. Print orientation does not apply to it.

## STL and 3MF export

After you choose the file name, an options window opens:

- **Quality**: Coarse, Standard or Fine, or type your own **Chord deviation** (how far the triangles may be from the true surface) and **Angle**.
- **Format** (STL only): Binary, the small usual kind, or Text.
- **Unit**: millimetres or inches. STL files have no unit, so most programs read the numbers as millimetres.
- **Bodies**: all bodies, the shown ones, or the picked ones.
- **Largest edge**: splits triangles until no edge is longer than this. No limit is the usual choice; slicers do not need it. Some simulation, sculpting and engraving tools want short edges on flat faces.
- **Largest aspect ratio**: mends thin triangles until none is thinner than this. 1 is an equilateral triangle; limits below 2 count as 2. Long thin triangles on flat faces and along curved sides are cut across and turned into round ones. A few thin triangles along a curved edge, such as round the rim of a hole, may stay; the worst aspect ratio shown below tells you what is left.
- **Show the mesh in the view**: draws the triangles on the part while the window is open.

Beside the triangle count the window shows the longest edge, the worst aspect ratio (1 is a triangle with equal sides; long thin triangles have high numbers) and how many triangles are thinner than 20. Thin triangles on long flat faces are normal and print fine.

The window shows the triangle count and the file size before you save. A 3MF file keeps the bodies together as parts of one object, gives each body its own colour for slicers that pick a filament by colour, and carries a small picture of the part. The part keeps your choice for its next export and for Open in Slicer (which always uses millimetres).

File, Export, **STL...** and **3MF...** write a triangle mesh for 3D printing.

1. Choose File, Export, STL... or 3MF...
2. Pick a folder and a file name, then click Save.

Tips:

- Both use a fine mesh with a chord deviation of 0.01 mm. 3MF also keeps units, colours and several bodies.
- Both follow the print orientation set with **Lay Face Flat**. The model is not changed. 3MF keeps face colours, also when the part is laid flat and when it goes to the slicer.
- File, Export, **Export Bodies** writes each body to its own file (STL, 3MF, STEP or FDCAD Part) in a folder you pick, for example the pieces of a Split for Printing. STL and 3MF follow Lay Face Flat: the whole part is laid flat and each body keeps its place in it.
- A new Split for Printing takes its build size and its clearance from the active printer profile.
- Right click a body under Solid Bodies and choose **Rename Body...** to give it a name of its own. The name stays with the body when the part is rebuilt, shows in the tree, and names the body's object in a 3MF file, so a slicer lists "Lid" and "Base" instead of numbered bodies. Leave the name empty to go back to Body N.
- A 3MF file names the part for file browsers and print sites: its title is the part name, or a custom property called **Title**. Custom properties called **Designer** (or Author), **Description**, **Copyright**, **Licence** and **Created** go in as the matching standard 3MF items, and the export date goes in as the modification date.

Common error: "The part is empty. Add a feature before exporting." There is no solid yet. Build a feature first.

### Print roles for bodies

A part with several bodies can tell the slicer how to use each one. Right click a body under Solid Bodies and choose **Print Role**:

- **Part**: printed, the default.
- **Modifier**: not printed; the slicer can give the region it covers its own settings, for example more infill.
- **Negative Volume**: not printed; it is cut out of the other bodies in the slicer.
- **Support Enforcer** and **Support Blocker**: not printed; support is added inside, or kept out of, the region.

The body row shows its role. Roles change only the 3MF file, never the model.

Slicers read roles in two different layouts, so the 3MF options have a **Slicer** choice: **Bambu Studio, OrcaSlicer or Cura** (the default), **PrusaSlicer**, **Cura only**, or **Plain 3MF** for any other program (bodies, colours and names, but no roles or print settings). A line under the choice says what that slicer keeps. After the export the status bar says what each slicer keeps. Cura has no negative volume: it leaves such a body out but does not cut it, and it prints a support enforcer as support in the body's shape. A file made for PrusaSlicer opens in the other slicers as one object with every body printed. Open in Slicer uses the same choice.

### Print settings for bodies

Right click a body under Solid Bodies and choose **Print Settings...** to give it its own slicer settings: **Layer height**, **Wall count**, **Infill density**, **Infill pattern**, **Supports** and **Extruder**. Tick a setting to write it; settings left unticked come from the slicer's profile. The 3MF file carries them in the keys each slicer reads. Cura has no layer height per body, so that one is left out for Cura, and Plain 3MF writes none.

FDCAD does not also change the shape for what the slicer compensates, such as hole shrink or first layer spread, so the effect never doubles.

### Settings by height

Print, **Settings by Height** keeps a list of heights above the print bed, each with a change:

- **Pause**: the printer stops so you can drop in magnets, nuts or other inserts, then you resume it.
- **Colour change**: the printer stops for a filament change.
- **Setting change**: a new **Layer height**, **Infill** or **Walls** from that height up to the next change of the same setting.

Click **Add** for each change and enter its height. The list goes into the 3MF file and Open in Slicer for Bambu Studio, OrcaSlicer and PrusaSlicer. Cura and plain 3MF files have no place for it. Heights are measured on the bed, after Lay Face Flat.

## IGES, BREP, PLY and glTF

**File, Save As** also writes these, chosen by the file type or the name's ending:

- **IGES** (.igs, .iges) and **OpenCascade BREP** (.brep) keep the exact shape, for programs that read them.
- **PLY** (.ply), **Wavefront OBJ** (.obj) and **glTF binary** (.glb) write a triangle mesh with the part's mesh settings: PLY and OBJ in millimetres, glTF in metres as that format asks, for viewers, games and web pages.
- **3D DXF wireframe** (.dxf) writes every edge of the part in 3D, in millimetres: straight edges as lines and curved edges as 3D polylines that keep within 0.01 mm of the curve. Use it for programs that take a wire model, such as some CAM and laser tube tools. For a flat drawing of a face or a sheet metal flat pattern, use DXF and SVG export below.

## DXF and SVG export

**Export DXF** and **Export SVG** write one flat face or one sketch as a 2D drawing at true scale.

1. Pick one flat face in the 3D view, or select a sketch in the feature tree.
2. Choose File, Export, Export DXF or Export SVG.
3. Pick a file name and click Save.

Tips:

- Drawings are in the part's units. Construction curves and points of a sketch are left out.
- Lines, circles and arcs are exact. Splines and ellipses become short straight pieces within 0.01 mm.

Common errors:

- "Pick one flat face in the 3D view or a sketch in the feature tree, then export again.": nothing usable is selected, or the face is curved.
- "The sketch has not been built": rebuild the part (Ctrl+B) and export again.

## Export Section and Outline

File, Export, **Export Section and Outline** makes a flat drawing for a laser cutter, a router or a plotter from the whole part:

- **Source**: **Section at a plane** draws where the plane cuts the bodies. **Outline seen along the axis** draws each body's shadow, the shape you see looking straight along the axis; holes that go right through stay holes.
- **Plane**: Top, Front or Right. **Offset** moves the section plane along its normal.
- **Kerf or tool offset**: grows each shape by this much (shrinks it when negative), for the width of the laser or the cutter.
- **Scale**: 1 is true size; 0.5 draws at half size.
- **Use** of each body: **Cut**, **Engrave** or **Ignore**. Cut and engrave shapes go on their own layers, CUT and ENGRAVE in DXF, and red and blue groups in SVG, so the laser program can give each its own power and speed.

Then pick a .dxf or .svg file name. The status bar says how many lines and arcs were written.

## Save Image

File, Save Image saves the 3D view of the active part as a PNG picture. Choose the size of the view on screen, or type a width and height (up to 8000 pixels). Untick Include the background for a PNG that is see through around the part; the axis triad is left out then.

## Export Flat Pattern

**Export Flat Pattern** saves the flat pattern of a sheet metal part as STEP, DXF or SVG. See [sheet-metal.md](sheet-metal.md).

## Split for Printing

**Split for Printing** cuts the part into pieces that fit your printer. It can add alignment pins or dovetail keys so the pieces line up when you glue them.

1. Build the part.
2. Click **Split for Printing** on the 3D Print tab, or choose Insert, Split for Printing.
3. Choose how to cut in the Cuts group.
4. Choose a connector in the Connectors group and set its sizes.
5. Click OK. The pieces and connectors appear as separate bodies.

Main options:

- Fit Build Volume: cuts evenly so every piece fits the build volume X, Y and Z you type. The default is 220, 220 and 250 mm. It does not turn pieces to fit better.
- At Planes: cuts at the planes you pick in the list or the flat faces you click. Each plane is treated as endless.
- Along Sketch: cuts along the curves of a sketch you pick in Path sketch, pushed right through the part along the sketch's normal. Draw an open line with steps or a shaped curve across the part for a seam that locks or hides better. Connectors go on the flat faces of the cut. A glue gap needs plane cuts.
- Connectors: None, Alignment Pins, Dovetail Keys, Magnet Pockets or Screws and Nuts. Each pin or key is its own body, printed on its own.
- Magnet Pockets: a round pocket of the magnet's diameter and depth in each piece, the clearance larger. Glue the magnets in with their poles facing each other the right way.
- Screws and Nuts: a hole of the screw's diameter right through the part across the cut, and a hexagon pocket for the nut where the hole leaves the part. Put the nut in the pocket and screw through from the other side.
- Glue gap: trims each piece on the far side of a cut back by this much, so the joint has room for glue. The part gets that much shorter.
- Pin diameter and Pin length: half of the pin goes into each piece.
- Key width and Key depth: the size of a dovetail key at the seam.
- Key draft: the key and its pocket narrow by this angle (up to 10 degrees) along the way the key slides in, so it wedges tight. Slide it in from the wide end. Zero gives a straight key.
- Clearance: extra room all round each pin or key so it fits. The default is 0.2 mm.

Tips:

- A cut face longer than six pin diameters gets two pins. Shorter faces get one. A pin with no room round its hole is left out, with a warning.
- The tutorial [split-with-pins.md](tutorials/split-with-pins.md) walks through an example.

Common errors:

- A warning that the part already fits: nothing is cut. Use At Planes if you still want to cut it.
- Planes that miss the part are an error. Pick planes that cross the part.

## Lay Face Flat

**Lay Face Flat** sets the print orientation: the face you pick lies on the printer bed. Only STL, 3MF and Open in Slicer use it.

1. Click **Lay Face Flat** on the 3D Print tab, Print group.
2. Pick a flat face in the 3D view. You can also pick it first and then click the command.
3. The status bar says "Print orientation set: the picked face lies on the bed. The model is unchanged."

Tips:

- The part turns so the face points straight down, then moves so it sits on the bed, centred.
- Turn on **Build Volume** to see the part on the bed. See [evaluate.md](evaluate.md).
- Undo works on the orientation like any other change.

Common errors:

- "The picked item is not a flat face.": pick a flat face.
- If the face is later removed or is no longer flat, the part exports as modelled and the status bar says so.

## Bed Edge Chamfer

**Bed Edge Chamfer** (3D Print tab) chamfers every edge of the face that sits on the printer bed, hole edges too, so the first layers do not spread past the model.

1. Set the print orientation with **Lay Face Flat**, or pick the bottom face.
2. Choose **Bed Edge Chamfer** and type the size (0.4 mm to start).
3. A Chamfer feature named Bed Chamfer appears in the tree. Edit or delete it like any chamfer.

## Suggest Orientation

Print, **Suggest Orientation** tries laying the part on each of its largest flat faces and lists the ways, best first: those that fit the printer, then the least overhang (area that would need support), then the lowest height. Pick one and click **Apply** to lay that face flat. Undo puts the old orientation back.

## Arrange on Bed

Print, **Arrange on Bed** lays the bodies of a part with several bodies out on the printer bed, side by side, with the spacing you enter. It keeps clear of the printer's no print zones. Each moved body gets a Move and Copy Body feature in the tree, so the layout is part of the model and goes into every export. One undo takes the whole layout back.

## Coating Allowance

A coat of paint, powder or anodising makes holes smaller and pins larger. Print, **Coating Allowance** keeps the coating's thickness in the part. STL and 3MF exports and Open in Slicer then take that much off every face, so holes print larger and outsides smaller, and the coated part ends at the size you modelled. The model itself does not change. Enter 0 to turn it off.

To see the change in the model instead, add **Offset Body** with Inward ticked and the coating thickness as the distance.

## Suction Cups and Islands

Evaluate, **Suction Cups and Islands** looks at the part as it lies on the bed:

- A **suction cup** is a hollow that opens toward the bed. Air or resin is trapped in it while printing, which can tear a resin print off the plate or leave a filament print hollow. The message gives the count and the deepest one.
- A **floating island** is a low point that is not on the bed, so printing it starts in mid air and needs support.

Each one is marked in the view. Click **Add Drain Holes** to start Drain Holes, or **Suggest Orientation** to turn the part another way. Suggest Orientation counts islands too.

## Layer Fit Check

Evaluate, **Layer Fit Check** lists heights that are not a whole number of layers, and walls that are not a whole number of line widths, for the active printer profile. The slicer rounds such sizes, so a 5.1 mm step with 0.2 mm layers prints at 5.0 or 5.2 mm. Change the size to the whole value the list gives if it matters. Walls thicker than eight lines are left out, since the slicer fills them.

## Clear Print Orientation

**Clear Print Orientation** on the 3D Print tab, Print group, removes the orientation set with Lay Face Flat. The part then prints as modelled.

## Open in Slicer

**Open in Slicer** sends the part to your slicer as a 3MF file in one click.

1. Click **Open in Slicer** on the 3D Print tab, Print group, or in the File menu.
2. FDCAD writes the part to a temporary 3MF file and opens it in the slicer of the active printer profile.

Tips:

- With no slicer set, the system's default app for 3MF files opens the file.
- Sending again overwrites the same temporary file. The file follows the print orientation.

Common error: "Could not open the slicer". The slicer path is wrong. Set it in Tools, Preferences, Printing.

## Fit Calibration

Every printer prints holes a little differently. Print, **Fit Calibration** makes a test plate so you can measure yours.

1. Choose Print, **Fit Calibration**.
2. Enter the **First gap** (the gap per side of the first hole), the **Step** added from hole to hole and the number of **Holes** (2 to 10), then click OK.
3. The plate opens as a new part: one 5 mm pin and a row of holes, each with its gap cut into the plate beside it. The gaps are variables (Gap1, Gap2 ...), so you can change them in Equations and the holes and labels follow.
4. Print the plate and find the tightest hole the pin turns in.
5. Choose Print, **Keep Measured Fit** and enter that hole's gap. It becomes the active printer profile's Fit tolerance, and parts that use `fit_tolerance@Printer` rebuild.

## Printer profiles

Printer profiles hold your printer's sizes and settings. The print tools use the active profile.

1. Choose Tools, **Preferences** (Ctrl+,) and open the Printing page.
2. Pick a profile in Printer profile, or click Add to copy the current one.
3. Edit the values and close the dialog.

Main options:

- Name, and Build volume X, Y and Z.
- Nozzle, Overhang angle, Minimum wall and Fit tolerance.
- Slicer: click Browse... to pick your slicer program. Empty uses the default app for 3MF files.
- **Keep out zones**: bed areas the printer cannot print on, such as clips or a purge area, as x0 y0 x1 y1 in mm from the bed's front left corner, separated by semicolons. **Head clearance**: the height under the print head's gantry for printing parts one at a time (0 when not set). Build Volume warns when a body reaches into a zone, or when more than one body is taller than the clearance.
- Material densities (g/cm³): the materials used by **Print Estimate**. Reset Densities restores the presets.

Tips:

- The default profile is a generic printer with a 220 by 220 by 250 mm build volume, a 0.4 mm nozzle, a 45 degree overhang angle and a 0.2 mm fit tolerance.
- Remove deletes a profile, but never the last one.
- The Hole Tool uses the fit tolerance for print fits. See [holes-and-fastening.md](holes-and-fastening.md).
- Profiles belong to FDCAD on your computer, not to the part file.

## Two colour inlays

Draw text or a shape in a sketch on a face of the part, then choose **Inlay** (3D Print tab, with Lip and Groove and Vent). Pick the sketch and type the **Depth**. The shape is cut into the face as a pocket, and the piece it removes stays as a separate body of exactly the same shape, so it fills the pocket. Give the two bodies different colours, or export a 3MF: each body is its own part in the file, so the slicer can print the inlay in another filament.

## Cable tie channels

Put points in a sketch on a face where cables should be tied down, then choose **Cable Tie** (3D Print tab, with Inlay). At each point FDCAD cuts two slots into the face and joins them with a tunnel underneath, so a cable tie can go down one slot, under the face and up the other.

- **Tie width** and **Tie thickness**: the strap's size. **Clearance** is added on every side.
- **Span**: how far apart the two slots are. **Angle** turns the loop from the sketch's X direction.
- **Cover**: how much material stays over the tunnel. The tunnel's top is pointed at 45 degrees so it prints without supports; when the cover is too thin for the point, the top is flat at half the cover.

## Crush ribs

Printed holes and pins are never exactly to size. **Crush Ribs** adds small wedge shaped ribs inside a hole (or on a pin) that get squashed when the parts are pressed together, so the fit holds even when the print is a little off. Click the round face, then set the number of **Ribs**, their **Rib width** at the wall, **Rib height** (how much they are crushed, usually 0.2 to 0.4 mm), **Rib length** (empty for the whole face) and the **Tip width** (a small flat so the rib prints cleanly). The first part of each rib ramps up from nothing, so the mating part starts in easily. Make the hole itself a slip fit and let the ribs do the gripping.

Large flat parts can lift at their corners while printing. **Corner Ears** adds a thin disc at each sharp outer corner of the face that lies on the bed. Click that face, then set the **Ear diameter**, the **Ear thickness** (one or two layers, so the ears peel off) and **Corners up to** (corners with this inside angle or sharper get an ear; 120 degrees covers square corners). Inside corners get none. Cut or snap the ears off after printing.

A hollow resin print traps liquid resin inside. **Drain Holes** cuts one hole from each closed hollow of the part (one left by Shell with no face removed) straight out through the wall: from the hollow's lowest point downward, or with **Drain toward** set to Top from its highest point upward. A flat floor drains from its middle. Set the **Hole diameter**; 2 to 4 mm drains well and is easy to plug after washing.

Small round holes printed upright often come out undersize. **Polygon Holes** turns the round holes you click into polygons whose flat sides touch the hole's circle, so the flats sit exactly at the hole's size and the printer lays straight runs there. Leave **Sides** empty to use twice the diameter in mm (a 3 mm hole gets 6 sides), or type a count from 3 to 64.

**Base Pad** adds a thin removable pad under the part, as a body of its own, for a part with a small or uneven footprint. Click the face that lies on the bed, then set the **Pad thickness**, the **Margin** (how far the pad reaches past the face) and the **Air gap** between the pad and the part, so the pad peels off after printing. Export both bodies together.

**Material Interlock** locks two bodies printed in different materials, such as a hard core and a soft grip, so the joint does not peel apart. Click the flat face of one body where it lies against the other, then set the **Tooth size** (the side of each square tooth) and the **Tooth depth**. The boundary gets a checkerboard of teeth: on half of the squares the first body reaches into the second, on the other half the second reaches back. Both stay separate bodies, so each can get its own material in the slicer.

## Lattice Fill

**Lattice Fill** makes a body light but stiff by filling it with a lattice, as a feature in the tree.

1. Click **Lattice Fill** on the 3D Print tab.
2. Click the bodies to fill, or leave the box empty to fill every body.
3. Pick the **Lattice**: Gyroid or Diamond (smooth sheets that are strong every way and print without supports) or Honeycomb (straight hexagon walls along Z).
4. Set the **Cell size**, the **Wall** thickness and the **Skin**, a solid outer wall kept round the lattice so the part stays closed. Enter 0 for the bare lattice.
5. Click OK.

Tips:

- Gyroid and Diamond are built from many small flat faces, so they take a few seconds and make large STEP files. Keep the cell at least a few millimetres; a cell too small for the body is an error that asks for a larger cell. In a body with large curved faces, such as a spring or a sweep, a fine Gyroid or Diamond lattice costs much more to fit. FDCAD refuses one that would take too long and names the cell size that fits.
- The wall must be thinner than half the cell.
- Lattice Fill, Mark, Ring Groove, O Ring Groove, Shaft Shape, Edge Profile, Rib, Roof, Vent and the Split for Printing connectors change only the body they were put on. A body that touches it is left alone. Lattice Fill fills touching bodies each on its own.
- Gyroid and Diamond keep every wall, even one thinner than an eighth of the cell.
- Slicers can also print gyroid infill. Use Lattice Fill when the lattice should be part of the model, for example to show it or to leave the skin open.

## Mark

**Mark** puts text and lines onto a face, for etching part numbers with a laser or engraving them lightly.

1. Sketch on the face to mark: add Text and any lines.
2. Click **Mark** on the 3D Print tab and pick the sketch.
3. Leave **Depth** at 0 for marks with no depth: the part does not change, and the marks show as lines on the face. Enter a small depth (up to 5 mm) to cut closed shapes and letters into the part.
4. Click OK.

Tips:

- Open lines can only be marks with no depth.
- On a sheet metal part, marks with no depth on the base wall go to a MARKS layer in the flat pattern DXF and SVG. See [sheet-metal.md](sheet-metal.md).

## Hinge

**Hinge** adds a knuckle hinge where two bodies meet, such as a box and its lid modelled as separate bodies.

1. Model the two bodies so they touch along a straight edge, the hinge line.
2. Click **Hinge** on the 3D Print tab and click that edge.
3. Pick the **Form**: Pin (a hole right through all knuckles for a metal pin or a piece of filament) or Print in place (cone pins and sockets, so the hinge prints as one part and turns once it comes off the bed).
4. Set the number of **Knuckles**, the **Knuckle diameter** and the **Clearance**, the gap round every moving part. For Pin, set the **Pin hole**. For Print in place, set the **Cone angle**: use your printer's overhang limit, usually 45 degrees.
5. Tick **Detent bumps** for small bumps that click into dimples so the hinge holds its place.
6. Click OK.

Tips:

- The body that owns the edge you click gets the first knuckle; the other body the next, and so on.
- Print a Print in place hinge with the hinge line upright, so the cones print within the overhang limit.
- A clearance of 0.3 to 0.5 mm suits most printers. Fit Calibration helps you find yours.

Common errors:

1. "No second body touches the edge. Pick an edge where two bodies meet." The picked edge lies on one body only.
2. The bodies no longer meet on the picked edge, for example after one body was made a little thicker, so its top edge now stands above the other. When they still meet on a nearby edge of the same wall, the message says how far apart the two bodies' edges are, names that edge and highlights it. Click the "Move the hinge to ..." button to use that edge in place of your pick, or make the bodies line up again. Nothing changes until you click the button, and you can undo it.

## Face Seats

**Face Seats** sets copies of a small body over a curved face, each turned to stand square on the face: studs on a drum, rivet heads on a tube, dimples on a ball.

1. Model the seed as a separate body (Merge result off) at the origin, with +Z pointing the way it should stand out of the face. A stud is a short cylinder from the Front plane up; a dimple is a sphere at the origin.
2. Click **Face Seats** on the 3D Print tab.
3. Click the **Face to cover**, then a face of the **Seed body**.
4. Pick Add (studs and rivets) or Cut (dimples), and set the **Copies across** and **Copies along** the face and the **Sink**, how far each copy goes into the face so it joins or bites.
5. Click OK. The seed body is used up.

Tips:

- The copies are spread evenly over the face's own directions: round a cylinder and along it, or round a sphere and from pole to pole. Copies whose spot is off the face are left out.
- Each copy's +X follows the face's first direction, so a long seed lines up the same way on every spot.

## Stone Setting

**Stone Setting** cuts a seat for a round stone into a flat face and adds the prongs that hold it, for ring and pendant masters.

1. Click **Stone Setting** on the 3D Print tab (in the dropdown with Face Seats).
2. Click the **Seat face**. To place the stone somewhere other than the middle of the face, click a point for the **Centre point**: a vertex, a sketch point or a reference point.
3. Enter the **Stone diameter** (the girdle, the stone's widest part), the **Girdle depth** (the straight wall below the face) and the **Pavilion angle**: the seat narrows below the wall to a point at that slope, 41 degrees for a round brilliant.
4. Enter how many **Prongs**, 0 to 12, with their **Prong diameter** and **Prong height** above the face. Each prong stands a quarter of its diameter inside the girdle so it holds the stone's edge, and has a round tip.

## Sprue Tree

**Sprue Tree** joins feeds to your parts: sprues from a pouring cup for a casting master, or a kit frame runner round the parts like a model kit.

1. Click **Sprue Tree** on the 3D Print tab (in the dropdown with Face Seats).
2. Click the **Feed points**, where each part is fed: vertices, sketch points or reference points.
3. For a **Sprue tree**, click the **Cup point**, the middle of the pouring cup's open end. The cup narrows over the **Cup depth** to the trunk, which runs straight toward the parts as far as the farthest point; a thin gate runs square from the trunk to each point.
4. For a **Kit frame**, set the **Margin**: a rectangular runner goes round all the points that far outside them, and a gate runs from each point to the nearest side.
5. Set the **Sprue diameter** (the trunk or the runner) and the **Gate diameter**, and click OK. Everything is joined into one body.

## Mirror Part

For a left and right hand pair, finish one hand, then choose **File > Mirror Part** and pick a name for the new file. FDCAD mirrors the finished part about the Right plane (left becomes right), saves it as a new part and opens it. The new part holds the mirrored shape as an imported body, so you can add features to it; it does not follow later changes to the original, and the original is not changed.

## Batch export

**File > Export > Batch Export** makes a family of files from one part. In the table, type values for the variables to change: a list such as `10, 20, 30`, or a range such as `10..30 step 5`. Leave the others empty. Pick the file kind (STEP, STL, 3MF or part file), a folder, and optionally a **File names** template such as `{part} {width}x{height}`. FDCAD rebuilds every combination in the background and writes one file each; the open part does not change. An `Export log.txt` in the folder lists each combination and whether it worked.

## Overlapping bodies

Bodies that overlap print the shared part twice, which can leave blobs or confuse the slicer. STL and 3MF export say which bodies overlap and by how much. In the export options, **Overlapping bodies** chooses what to do: **Warn only** (the default), **Join them** (overlapping bodies become one), or **First body wins** (each body gives up the part an earlier body already has). The part itself is not changed; only the exported file.

## Living hinges

To make a flat wooden or plastic part bend, draw the bending area as a closed outline in a sketch on the plate, then choose **Living Hinge** and pick that sketch. FDCAD cuts rows of slits through the plate inside the outline, along the sketch's X direction. **Slit length** and **Bridge** (the material left between slits) set each row; **Row spacing** sets how close the rows are (closer bends more); every other row is shifted by half a slit so the bridges stagger. Set **Slit width** to about your laser's cut width.

## Hose barbs and luer fittings

On the 3D Print tab, open the Cable Tie list and choose **Hose Fitting**. Pick the **Face** it stands on and, if you like, a **Point**: a vertex, or a round edge for its centre. With no point it goes in the middle of the face. Choose the **Fitting**:

- **Hose barb**: a stem the size of the hose's inside, with **Barbs** that step out to the **Barb diameter** facing the part and taper toward the tip, so the hose slides on and does not pull off.
- **Luer male** and **Luer female**: the standard 6 percent luer taper on a round base. Printed luer fittings are for prototypes and lab use, not for medical use.

**Base height** is the plain round part next to the face. The **Bore** runs through the fitting and **Bore depth into part** below the face; join it to a channel inside the part.

## Fixing overhangs

A flat face that faces down in mid air (the underside of a ledge) cannot print without support. **Fix Overhangs** (3D Print tab) finds every such face in the current print orientation, leaving out the face on the bed, asks for a size, and adds one Chamfer feature on their edges. A 45 degree chamfer prints without support. It is an ordinary feature, so you can edit, suppress or undo it. **Overhang Analysis** also says when some overhanging faces are fillets: a chamfer prints better on an edge that faces the bed.

## Twist Lock

**Twist Lock** (3D Print tab, under Half Lap) makes a bayonet joint for a printed lid. Model the lid with a round plug that sits inside the box's opening, as a separate body. Pick the plug's outer round face. Lugs stand out of it, and the box gets an L shaped slot for each lug: a straight way in from the open end, then a turn round the axis. Push the lid in and twist it to lock.

* **Lugs**: how many, evenly round the plug (1 to 12).
* **Lug width**, **Lug height** and **Lug depth**: each lug's size round the plug, along the axis, and how far it stands out.
* **Depth from the open end**: from the end of the round face to the middle of the lugs.
* **Twist**: how far the lid turns to lock.
* **Clearance**: the gap left round each lug in its slot, so a printed lid turns freely.
* **Other end is open**: the slots open at the other end of the round face.
* **Clockwise**: the lid turns clockwise to lock, seen from the open end; off, it turns anticlockwise.

If the slots would run into each other, use fewer or narrower lugs or a smaller twist. A bore is refused: pick the plug's outside face.
