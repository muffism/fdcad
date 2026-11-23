# Hex fasteners

## What you will make

An ISO M6 hexagon head bolt with a hexagon nut and a plain washer below it, as three bodies. Every size comes from FDCAD's screw and washer tables: 10 mm across the flats, a 4 mm head, a 5.2 mm nut, a 12 mm washer 1.6 mm thick with a 6.4 mm hole. The threads are cosmetic, so the part stays light.

## What you will learn

- Reading standard sizes from the Hole Tool's tables (the size list of the Hole Tool shows the same values).
- Three bodies in one part with Merge result turned off.
- Cosmetic threads on a shank and in a nut.

## Steps

1. Choose File, **New Part** (Ctrl+N) and pick millimetres. In **Equations** add `Flats = 10mm`, `HeadHeight = 4mm`, `NutHeight = 5.2mm`, `WasherOD = 12mm` and `WasherThickness = 1.6mm`.
2. Sketch on Front Plane. Draw a six sided Polygon at the origin, set its size to `=Flats` across the flats and make one side horizontal. Exit and rename it to `Head Sketch`.
3. Click **Extruded Boss** (Shift+E), Blind, depth `=HeadHeight`. Rename it to `Head`.
4. Sketch on the head's top face: a circle 6 mm across on the centre. Extrude it 20 mm. Rename it to `Shank`.
5. Add a reference plane 15 mm below the Front Plane (Offset, -15) and name it `Nut Plane`. Sketch on it: a polygon `=Flats` across at the origin. Extrude it `=NutHeight` with **Merge result** off. Rename it to `Nut`.
6. Sketch on `Nut Plane` again: a circle 5 mm across (the M6 tap drill) at the origin. Make it an **Extruded Cut**, Blind `=NutHeight` up into the nut. Rename it to `Nut Hole`.
7. Add a reference plane 25 mm below the Front Plane and name it `Washer Plane`. Sketch on it a circle `=WasherOD` across and a circle 6.4 mm across, both at the origin. Extrude it `=WasherThickness` with **Merge result** off. Rename it to `Washer`.
8. Click **Cosmetic Thread** and pick the top edge of the shank: diameter 6, pitch 1, Blind 16 mm. Rename it to `Bolt Thread`.
9. Add a second cosmetic thread on the top edge of the nut's hole, Blind 5.2 mm, with the same diameter and pitch. Rename it to `Nut Thread`.

## Check your result

1. Open `hex_fasteners.fdprt` from the samples folder.
2. It has three bodies with a total volume of about 1389.6 mm³.

## Try this

- Change the sizes to M8: Flats 13, HeadHeight 5.3, NutHeight 6.8, a 8 mm shank, a 6.8 mm tap drill, a 16 mm washer 1.6 mm thick with an 8.4 mm hole.
- Replace the cosmetic threads with **Thread** (modelled) and a 0.1 mm clearance to print them, as in the nut and bolt tutorial.
