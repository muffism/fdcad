# Turned shaft

## What you will make

A stepped shaft 120 mm long, turned about the X axis: 40 mm at 30 mm diameter, 30 mm at 20 mm diameter and 50 mm at 25 mm diameter. A small groove is cut into the thin step.

## What you will learn

- Sketching half a profile with lines and a centerline.
- **Revolved Boss** and **Revolved Cut** about a centerline.

## Steps

1. Choose File, **New Part** (Ctrl+N) and pick millimetres.
2. Select Front Plane in the feature tree and click **Sketch** (S).
3. Pick **Line** (L). Start on the origin and draw a closed outline through these points, in order (X, Y in mm):

   | Point | X | Y |
   | --- | --- | --- |
   | 1 | 0 | 0 |
   | 2 | 120 | 0 |
   | 3 | 120 | 12.5 |
   | 4 | 70 | 12.5 |
   | 5 | 70 | 10 |
   | 6 | 40 | 10 |
   | 7 | 40 | 15 |
   | 8 | 0 | 15 |

   End the last line on the origin to close the outline. Every line is horizontal or vertical.
4. Pick **Smart Dimension** (D) and dimension the lines so the outline is fully defined: 120 along the bottom, 12.5, 50, 2.5, 30 and 5 round the steps. The rest follow from the closed loop.
5. Pick **Centerline** (Alt+C). Draw a horizontal line along the X axis from X = -10 to X = 130. Dimension it to 140.
6. Exit the sketch. Rename it to `Shaft Profile`.
7. With the sketch selected, click **Revolved Boss** (Shift+R). The centerline is picked as the axis because it is the only one. Leave Direction 1 on Blind and check that the angle is `360`. Click OK. Rename the feature to `Shaft`.
8. Select Front Plane again and click **Sketch**.
9. Pick **Corner Rectangle** (R). Draw a rectangle with its lower left corner at X = 55, Y = 8.5. Dimension it 4 wide and 3 high, and dimension the corner from the origin.
10. Draw a horizontal centerline from X = -10 to X = 130 on the X axis, as before.
11. Exit the sketch and rename it to `Groove Profile`.
12. With the sketch selected, click **Revolved Cut** (Ctrl+Shift+R). Leave Direction 1 on Blind with an angle of `360`. Click OK. Rename the feature to `Groove`.

The rectangle runs from 8.5 to 11.5 mm off the axis. The thin step has a 10 mm radius, so the groove is 4 mm wide and 1.5 mm deep.

## Check your result

1. Choose File, Open, go to the samples folder and open `turned_shaft.fdprt`.
2. Compare the feature tree: Shaft Profile, Shaft, Groove Profile, Groove.
3. Click **Print Estimate** on the 3D Print tab. The volume should be about 61.89 cm³.
4. Use **Section View** with Front to see the groove from the side. See [../evaluate.md](../evaluate.md).

## Try this

- Edit Shaft Profile and change the 50 mm length of the last step to 80 mm. The shaft grows to 150 mm, and the groove stays in the thin step. (The 120 mm overall length is not a dimension of its own: the thick step takes up what the others leave.)
- Edit Groove and set the angle to 180. Only half the groove is cut.

See also [../sketching.md](../sketching.md) and [../boss-and-cut.md](../boss-and-cut.md).
