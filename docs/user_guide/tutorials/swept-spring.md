# Swept spring

## What you will make

A compression spring: a 2 mm round wire wound along a helix of 20 mm diameter, with a 6 mm pitch and 5 turns. The helix is 30 mm tall; with the 2 mm wire the spring is about 32 mm.

## What you will learn

- **Helix and Spiral** from a sketch circle.
- **Swept Boss** with a circular profile, so you need no profile sketch.

## Steps

1. Choose File, **New Part** (Ctrl+N) and pick millimetres.
2. Select Front Plane and click **Sketch** (S).
3. Draw a **Circle** (C) centred on the origin. Dimension it to a diameter of 20 with **Smart Dimension** (D).
4. Exit the sketch and rename it to `Spring Circle`.
5. With the sketch selected, click **Helix and Spiral** in the Curves dropdown of the Features tab, Reference and Curves group (also Insert, Curves).
6. In Defined By, choose Pitch and Turns. Type `6` for Pitch and `5` for Turns. Leave Constant Pitch.
7. Click OK. Rename the curve to `Spring Path`.
8. Click **Swept Boss** (Shift+S).
9. In Profile and Path, choose Circular profile. Pick Spring Path as the path. Type `2` for Diameter.
10. Click OK. Rename the feature to `Spring Wire`.

## Check your result

1. Choose File, Open, go to the samples folder and open `swept_spring.fdprt`.
2. Compare the feature tree: Spring Circle, Spring Path, Spring Wire.
3. Click **Print Estimate** on the 3D Print tab. The volume should be about 0.99 cm³.
4. Click **Measure** and pick the round edge at the end of the wire. The diameter should be 2 mm. (The swept wire's face is not a cylinder, so it shows no diameter.)

## Try this

- Edit Spring Path and change Turns to 8. The spring gets taller: 8 turns at 6 mm is 48 mm.
- Edit Spring Circle and change the diameter to 30. The helix and the wire follow.
- Tick Clockwise in Spring Path to wind the spring the other way.

See also [../curves.md](../curves.md) and [../boss-and-cut.md](../boss-and-cut.md).
