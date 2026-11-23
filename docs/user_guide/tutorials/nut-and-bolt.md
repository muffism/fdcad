# Nut and bolt

## What you will make

An M8 bolt with a 13 mm hexagon head and 17 mm of thread, and its nut beside it, with a 0.1 mm printing clearance on both threads. Print both and screw the nut on to check your printer's threads.

## What you will learn

- Hexagons drawn with the Polygon tool and sized across the flats.
- Two bodies in one part: the nut is extruded with Merge result turned off.
- Thread (modelled) with a clearance for printing.

## Steps

1. Choose File, **New Part** (Ctrl+N) and pick millimetres. In **Equations** add `Flats = 13mm`, `Head = 5.5mm` and `NutHeight = 6.5mm`.
2. Sketch on Front Plane. Draw a six sided Polygon at the origin, set its circle to `=Flats` and make one side horizontal. Exit and rename it to `Head Sketch`.
3. Click **Extruded Boss** (Shift+E), Blind, depth `=Head`. Rename it to `Head`.
4. Sketch on the head's top face: a circle 8 mm across on the centre. Extrude it 20 mm. Rename it to `Shaft`.
5. Sketch on Front Plane again: a polygon `=Flats` across centred 25 mm along X, and a circle 7.25 mm across on the same centre. Extrude it `=NutHeight` with **Merge result** off. Rename it to `Nut`.
6. Click **Thread (modelled)** and pick the top edge of the shaft. Diameter 8, Pitch 1.25, Cut, Blind 17 mm, Clearance 0.1. Rename it to `Bolt Thread`.
7. Add a second thread on the top edge of the nut's hole, Blind 6.5 mm, with the same values. Rename it to `Nut Thread`.

## Check your result

1. Open `nut_and_bolt.fdprt` from the samples folder.
2. It has two bodies with a total volume of about 2279.0 mm³.

## Try this

- Set the clearance of both threads to `0.2` if the printed nut is tight.
- Change the Form of both threads to Printable: the 45 degree flanks print upright without supports. The nut's 7.25 mm hole suits that form too.
