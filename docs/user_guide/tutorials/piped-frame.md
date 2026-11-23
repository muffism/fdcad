# Piped frame

## What you will make

A hollow tube frame: a 20 mm tube with 2 mm walls bent round a 120 by 80 mm rectangle.

## What you will learn

- **Pipe** along a closed sketch path.
- Making a hollow tube with an inner diameter.

## Steps

1. Choose File, **New Part** (Ctrl+N) and pick millimetres.
2. Select Front Plane and click **Sketch** (S).
3. Pick **Corner Rectangle** (R). Draw a rectangle from the origin. Dimension it 120 by 80 with **Smart Dimension** (D).
4. Exit the sketch and rename it to `Frame Path`.
5. Click **Pipe** in the Curves dropdown of the Features tab, Reference and Curves group (also Insert, Curves).
6. Pick Frame Path as the path. Its four lines join end to end, so they make one path.
7. Type `20` for the outer diameter.
8. Tick Hollow and type `16` for the inner diameter. The wall is (20 - 16) / 2 = 2 mm.
9. Click OK. Rename the feature to `Frame Tube`.

## Check your result

1. Choose File, Open, go to the samples folder and open `piped_frame.fdprt`.
2. Compare the feature tree: Frame Path, Frame Tube.
3. Click **Print Estimate** on the 3D Print tab. The volume should be about 45.24 cm³.
4. Use **Section View** with Top to see the hollow inside.

## Try this

- Edit Frame Tube and untick Hollow. The tube becomes a solid rod.
- Edit Frame Path and add a **Sketch Fillet** of 15 mm to each corner. The tube now bends round soft corners.

See also [../curves.md](../curves.md), [../sketching.md](../sketching.md) and [../evaluate.md](../evaluate.md).
