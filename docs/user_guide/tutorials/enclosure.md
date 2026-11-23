# Enclosure

## What you will make

An 80 by 60 by 40 mm box with rounded corners, open at the top, with 2 mm walls. It is a starting point for a printed case.

## What you will learn

- **Fillet** along a chain of smooth edges.
- **Shell** with a face removed.
- Why the order of fillet and shell matters.

## Steps

1. Choose File, **New Part** (Ctrl+N) and pick millimetres.
2. Select Front Plane and click **Sketch** (S).
3. Pick **Corner Rectangle** (R). Draw a rectangle from the origin. Dimension it 80 by 60 with **Smart Dimension** (D).
4. Exit the sketch and rename it to `Box Sketch`.
5. Click **Extruded Boss** (Shift+E). Choose Blind and a depth of `40`. Click OK. Rename the feature to `Box`.
6. Click **Fillet** (Shift+F). Choose Constant Size and a radius of `8`.
7. Click the four upright corner edges of the box (the edges that run along Z). Click OK. Rename the feature to `Corner Fillet`.
8. Click **Fillet** again. Choose Constant Size and a radius of `3`.
9. Click one edge of the bottom outline (the face on the Front plane). The fillet always follows edges that join smoothly, so the whole outline round the bottom is rounded, corners included. Click OK. Rename it to `Bottom Fillet`.
10. Click **Shell**. Type `2` for the thickness.
11. Click in Faces to remove, then click the top face of the box (the face at 40 mm). Click OK. Rename it to `Shell`.

Fillet first, then shell. The shell then follows the rounded outside, and the inside corners are rounded too.

## Check your result

1. Choose File, Open, go to the samples folder and open `enclosure.fdprt`.
2. Compare the feature tree: Box Sketch, Box, Corner Fillet, Bottom Fillet, Shell.
3. Click **Print Estimate** on the 3D Print tab. The volume should be about 28.80 cm³.
4. Use **Section View** to look at the wall thickness. Use **Measure** on the inside and outside faces of a wall: the distance should be 2 mm.

## Try this

- Edit Shell and change the thickness to 2.5. The walls get thicker and the inside gets smaller. (At 3 mm the 3 mm bottom fillet leaves the inside corner no room and the shell fails with a tight bend message.)
- Edit Corner Fillet and change the radius to 12. The inside corners round off more too, because the shell follows the outside. Use **Roll Back One Feature** to see the part before the shell, and **Roll to End** to go back.

See also [../modify.md](../modify.md) and [../evaluate.md](../evaluate.md).
