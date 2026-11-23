# Plate with holes

## What you will make

A 100 by 60 by 10 mm plate with a hole near each corner and a larger hole in the middle. Every size comes from a global variable, so one change updates the whole plate.

## What you will learn

- Making global variables.
- Sketching a rectangle and circles, and dimensioning them with formulas.
- **Extruded Boss** and **Extruded Cut** with Through All.

## Steps

1. Choose File, **New Part** (Ctrl+N) and pick millimetres.
2. Open the Variables tab in the left panel. Click Add Variable five times and fill in the rows:

   | Name | Expression |
   | --- | --- |
   | Width | 100mm |
   | Height | 60mm |
   | Thickness | 10mm |
   | Inset | 10mm |
   | HoleDiameter | 8mm |

3. Select Front Plane in the feature tree and click **Sketch** (S).
4. Pick **Corner Rectangle** (R). Click on the origin, then click up and to the right to draw a rectangle.
5. Pick **Smart Dimension** (D). Click the bottom edge, place the dimension and type `=Width`. Click the left edge and type `=Height`.
6. Check that the rectangle corner sits on the origin. The sketch turns black when it is fully defined.
7. Click OK in the confirmation corner to exit the sketch. Rename the sketch to `Plate Sketch` (right click it in the tree, Rename).
8. With the sketch selected, click **Extruded Boss** (Shift+E). Set the end condition to Blind and the depth to `=Thickness`. Click OK. Rename the feature to `Plate`.
9. Click the face of the plate that faces away from the Front plane (the face at 10 mm). Click **Sketch**.
10. Pick **Circle** (C) and draw four circles near the corners and one in the middle.
11. Dimension each corner circle's diameter as `=HoleDiameter`. Dimension its centre from the plate edges:
    - Bottom left: `=Inset` across and `=Inset` up.
    - Bottom right: `=Width - Inset` across and `=Inset` up.
    - Top right: `=Width - Inset` across and `=Height - Inset` up.
    - Top left: `=Inset` across and `=Height - Inset` up.
12. Dimension the middle circle's diameter as `20`. Place its centre at `=Width/2` across and `=Height/2` up.
13. Exit the sketch and rename it to `Hole Sketch`.
14. With the sketch selected, click **Extruded Cut** (Shift+C). Set the end condition to Through All. Click OK. Rename the feature to `Holes`.

## Check your result

1. Choose File, Open, go to the samples folder and open `plate_with_holes.fdprt`. File, Open Sample, Plate with holes also opens it.
2. Compare its feature tree with yours: Plate Sketch, Plate, Hole Sketch, Holes.
3. Click **Print Estimate** on the 3D Print tab in both parts. The volume should be about 54.85 cm³.

## Try this

- In the Variables tab, change Width to `140mm`. The part rebuilds. The plate gets longer, and the right holes and the middle hole move with it.
- Change HoleDiameter to `5mm`. All four corner holes shrink, but the middle hole stays at 20 mm.

See also [../sketching.md](../sketching.md), [../boss-and-cut.md](../boss-and-cut.md) and [../equations-and-configurations.md](../equations-and-configurations.md).
