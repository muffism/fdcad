# Bracket

## What you will make

An L bracket, 40 mm wide, with an 8 mm thick base leg 60 mm long and an upright leg 50 mm high. Each leg has two 6 mm holes.

## What you will learn

- Sketching an L profile.
- Extruding with Mid Plane, so the part is symmetric about the sketch plane.
- Sketching on faces of the part and cutting Through All.

## Steps

1. Choose File, **New Part** (Ctrl+N) and pick millimetres.
2. Select Front Plane and click **Sketch** (S).
3. Pick **Line** (L). Start on the origin and draw a closed L through these points (X, Y in mm): (0, 0), (60, 0), (60, 8), (8, 8), (8, 50), (0, 50), and back to the origin.
4. Pick **Smart Dimension** (D). Dimension the bottom line 60, the right end 8, the top of the base leg 52 and the inside of the upright 42. The last two lines follow from the closed loop.
5. Exit the sketch and rename it to `Bracket Profile`.
6. Click **Extruded Boss** (Shift+E). Set the end condition to Mid Plane and the depth to `40`. Click OK. Rename the feature to `Bracket`. The part now runs from Z = -20 to Z = 20.
7. Click the top face of the base leg (the face at Y = 8) and click **Sketch**.
8. Draw two **Circle** (C) shapes of diameter 6. Place their centres 38 mm from the back face of the upright (X = 38), at 10 mm on each side of the middle of the leg (Z = -10 and Z = 10).
9. Exit the sketch and rename it to `Base Holes Sketch`.
10. Click **Extruded Cut** (Shift+C) and choose Through All. Click OK. Rename the feature to `Base Holes`.
11. Click the outer face of the upright leg (the face at X = 0) and click **Sketch**.
12. Draw two circles of diameter 6 at 34 mm up from the bottom (Y = 34), at Z = -10 and Z = 10.
13. Exit the sketch and rename it to `Leg Holes Sketch`.
14. Click **Extruded Cut**, choose Through All and click OK. Rename it to `Leg Holes`.

## Check your result

1. Choose File, Open, go to the samples folder and open `bracket.fdprt`.
2. Compare the feature tree: Bracket Profile, Bracket, Base Holes Sketch, Base Holes, Leg Holes Sketch, Leg Holes.
3. Click **Print Estimate** on the 3D Print tab. The volume should be about 31.74 cm³.
4. Click **Measure** and pick the round edge at the top of each base hole. The centre distance should be 20 mm. (Picking the two hole faces gives the shortest distance between them, 14 mm.)

## Try this

- Edit Bracket and change the depth from 40 to 60. The bracket gets wider. The holes keep their places, 10 mm on each side of the middle.
- Edit Base Holes Sketch (right click it, Edit Sketch), double click a diameter and change it from 6 to 8. Only the base holes grow. The leg holes have their own sketch.

See also [../sketching.md](../sketching.md), [../boss-and-cut.md](../boss-and-cut.md) and [../evaluate.md](../evaluate.md).
