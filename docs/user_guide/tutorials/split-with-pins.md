# Split with pins

## What you will make

A 300 by 120 by 30 mm block that is too long for a printer with a 220 mm bed. **Split for Printing** cuts it into two pieces that fit, with two 5 mm alignment pins across the seam.

## What you will learn

- Checking the part against the printer with **Build Volume**.
- **Split for Printing** with Fit Build Volume and Alignment Pins.
- How pins and pieces become separate bodies.

## Steps

1. Choose File, **New Part** (Ctrl+N) and pick millimetres.
2. Select Front Plane and click **Sketch** (S).
3. Pick **Corner Rectangle** (R). Draw a rectangle from the origin and dimension it 300 by 120 with **Smart Dimension** (D).
4. Exit the sketch and rename it to `Block Sketch`.
5. Click **Extruded Boss** (Shift+E). Choose Blind and a depth of `30`. Click OK. Rename it to `Block`.
6. Click **Build Volume** on the 3D Print tab. The overlay is red and the status bar says the part does not fit: X is too large. Click Build Volume again to turn it off.
7. Click **Split for Printing** on the 3D Print tab (also Insert, Split for Printing).
8. In Cuts, choose Fit Build Volume. Type `220`, `220` and `250` for the build volume X, Y and Z.
9. In Connectors, choose Alignment Pins. Type `5` for the pin diameter, `10` for the pin length and `0.2` for the clearance.
10. Click OK. Rename the feature to `Print Split`.

The block is cut once across its length, into two 150 mm pieces. The cut face is 120 mm long, more than six pin diameters, so it gets two pins. Each pin is 10 mm long, so 5 mm goes into each piece. The holes are 0.2 mm wider all round, and deeper, so the pins fit.

## Check your result

1. Choose File, Open, go to the samples folder and open `split_with_pins.fdprt`.
2. Compare the feature tree: Block Sketch, Block, Print Split.
3. Check the Solid Bodies folder: there should be four bodies, two pieces and two pins.
4. Click **Print Estimate** on the 3D Print tab. The total volume should be about 1079.92 cm³.
5. Turn on **Build Volume** again. Each piece now fits.

## Try this

- Edit Block and change the depth to 300 mm, so the block is too tall as well. Rebuild and look at how the pieces change.
- Edit Print Split and choose Dovetail Keys instead of pins. Set the key width and key depth and compare the seam.

See also [../import-export-print.md](../import-export-print.md) and [../evaluate.md](../evaluate.md).
