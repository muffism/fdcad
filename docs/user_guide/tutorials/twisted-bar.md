# Twisted bar

## What you will make

A 20 by 20 mm square bar, 120 mm long, twisted a quarter turn (90 degrees) from one end to the other.

## What you will learn

- **Twist**, one of the deform features.
- How the triad and the two trim planes set where the deformation happens.

## Steps

1. Choose File, **New Part** (Ctrl+N) and pick millimetres.
2. Select Front Plane and click **Sketch** (S).
3. Pick **Center Rectangle**. Put the centre on the origin and draw a square. Dimension it 20 by 20 with **Smart Dimension** (D).
4. Exit the sketch and rename it to `Bar Sketch`.
5. Click **Extruded Boss** (Shift+E). Choose Blind and a depth of `120`. Click OK. Rename it to `Bar`.
6. Click **Twist** in the Deform group of the Bodies tab (also in the Insert menu).
7. Click a face of the bar to add it to the bodies list.
8. In the Twist group, type `90` for the angle.
9. Look at the Triad and Trim Planes group. The triad is centred on the bar and its third axis is Z, along the bar. Origin Z is 60. The Start plane is at -60 and the End plane at 60, so they sit at the two ends of the bar. Leave these values.
10. Leave Tolerance at 0.01 mm in Options.
11. Click OK. The feature is named Twist 1.

Only the part between the two trim planes deforms. Here the planes are at the ends, so the whole bar twists evenly along its length.

## Check your result

1. Choose File, Open, go to the samples folder and open `twisted_bar.fdprt`.
2. Compare the feature tree: Bar Sketch, Bar, Twist 1.
3. Click **Print Estimate** on the 3D Print tab. The volume should be about 48.00 cm³, the same as the straight bar: a twist does not change the volume.
4. Look at the bar from the Isometric view (Ctrl+7) or the Right view. The far end is turned 90 degrees from the near end. (From the Front view you look along the bar, and a square turned a quarter turn looks the same.)

## Try this

- Edit Twist 1 and set the Start plane to 0. Now only the far half of the bar twists. The near half stays straight.
- Edit Bar and change the depth to 200. The twist keeps its trim plane values, so check them in Twist 1 and move the End plane to the new end.

See also [../deform.md](../deform.md).
