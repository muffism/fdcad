# Living hinge strip

## What you will make

An 80 by 20 mm strip, 1.2 mm thick, that bends in the middle: a 24 mm wide band of staggered slits makes that part flexible. Print it flat in PETG or nylon.

## What you will learn

- **Living Hinge**, which cuts rows of slits inside a sketched region.
- How slit length, bridge and row spacing change how far the strip bends.

## Steps

1. Choose File, **New Part** (Ctrl+N) and pick millimetres.
2. Select Front Plane and click **Sketch** (S). Draw an 80 by 20 rectangle from the origin. Exit and rename it to `Strip Sketch`.
3. Click **Extruded Boss** (Shift+E). Blind, depth `1.2`. Rename it to `Strip`.
4. Sketch on the top face. Draw a rectangle 24 mm wide and 18 mm tall, its corner at X 28, Y 1. Exit and rename it to `Hinge Band`.
5. Click **Living Hinge** on the 3D Print tab. Pick `Hinge Band`. Set **Slit length** `10`, **Slit width** `0.6`, **Bridge** `2` and **Row spacing** `1.5`. Click OK.

## Check your result

1. Open `living_hinge_strip.fdprt` from the samples folder.
2. Both parts have a volume of 1747.2 mm³.

## Try this

- Make the slits longer (`14`) for a softer hinge, or the bridges wider (`3`) for a stiffer one.
- Make the band wider to let the strip bend further.
