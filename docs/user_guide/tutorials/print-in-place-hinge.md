# Print in place hinge

## What you will make

A hinge that prints as one piece: two 35 mm leaves joined by three 10 mm knuckles round a pin. A 0.4 mm gap all round the moving leaf keeps the parts apart, so the hinge turns as soon as it comes off the bed. Print it standing on the knuckle ends.

## What you will learn

- Sketches on reference planes offset from the Front plane.
- A gap set by one variable, `Gap`, that every clearance follows.
- Keeping a second body apart with Merge result off.

## Steps

1. Choose File, **New Part** (Ctrl+N) and pick millimetres. In **Equations** add `Gap = 0.4mm` and `Knuckle = 10mm`.
2. Sketch on Front Plane: a rectangle 35 by 3 from (-35, -1.5). Extrude it `=3 * Knuckle`. Rename it to `Leaf A`.
3. Sketch on Front Plane: a circle 10 mm across on the origin. Extrude it `=3 * Knuckle`. Rename it to `Knuckles`.
4. Add a **Plane** offset `=Knuckle - Gap` from Front Plane and rename it to `Room Plane`. Sketch on it a circle `=10mm + 2 * Gap` across, then click **Extruded Cut**, Blind `=Knuckle + 2 * Gap`, up into the part. Rename it to `Room`: it clears space for the middle knuckle.
5. Sketch a circle 5 mm across on the origin on `Room Plane` and extrude it `=Knuckle + 2 * Gap`. This is the `Pin`, part of leaf A.
6. Add a **Plane** offset `=Knuckle` from Front Plane and rename it to `Leaf B Plane`. Sketch on it two circles, 10 mm and `=5mm + 2 * Gap` across, and extrude the ring `=Knuckle` with Merge result off. Rename it to `Leaf B Knuckle`.
7. Sketch a rectangle 31 by 3 from (4, -1.5) on `Leaf B Plane` and extrude it `=Knuckle`. It joins the ring as `Leaf B`.

## Check your result

1. Open `print_in_place_hinge.fdprt` from the samples folder.
2. It has two bodies, and Evaluate, **Interference** finds no overlap between them.

## Try this

- Set `Gap` to `0.3mm` for a stiffer hinge, or `0.5mm` if the hinge is fused after printing.
- Set `Knuckle` to `15mm` for a taller hinge; every part follows.
