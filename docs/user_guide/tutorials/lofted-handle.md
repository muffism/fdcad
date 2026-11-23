# Lofted handle

## What you will make

A 100 mm long grip that changes from a 24 by 16 mm rectangle at one end to a 20 mm circle at the other. It is built round an 8 mm core rod, so the loft merges into one body.

## What you will learn

- **Center Rectangle** and circles on different planes and faces.
- **Lofted Boss** between two profiles.

## Steps

1. Choose File, **New Part** (Ctrl+N) and pick millimetres.
2. Select Front Plane and click **Sketch** (S).
3. Draw a **Circle** (C) centred on the origin. Dimension it to a diameter of 8 with **Smart Dimension** (D).
4. Exit the sketch and rename it to `Core Sketch`.
5. Click **Extruded Boss** (Shift+E). Choose Blind and a depth of `100`. Click OK. Rename it to `Core`.
6. Select Front Plane again and click **Sketch**.
7. Pick **Center Rectangle**. Put the centre on the origin and draw a rectangle. Dimension it 24 wide and 16 high.
8. Exit the sketch and rename it to `Grip Base`. Leave it unused for now.
9. Click the end face of the core at 100 mm and click **Sketch**.
10. Draw a circle centred on the core's centre. Dimension it to a diameter of 20. The circle can be larger than the face it sits on.
11. Exit the sketch and rename it to `Grip End`.
12. Click **Lofted Boss**. Choose Grip Base in the sketch list and click Add Profile, then do the same for Grip End. Use Move Up and Move Down if the order is wrong.
13. Check the preview, then click OK. Rename the feature to `Grip`.

## Check your result

1. Choose File, Open, go to the samples folder and open `lofted_handle.fdprt`.
2. Compare the feature tree: Core Sketch, Core, Grip Base, Grip End, Grip.
3. Click **Print Estimate** on the 3D Print tab. The volume should be about 35.08 cm³.
4. Check that the Solid Bodies folder shows one body. The loft and the core have merged.

## Try this

- Edit Grip End and change the circle to 30 mm. The grip flares out at the end.
- Edit Core and change the depth to 120. Grip End sits on the core's end face, so it moves out with it and the grip gets longer.

See also [../sketching.md](../sketching.md) and [../boss-and-cut.md](../boss-and-cut.md).
