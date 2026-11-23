# Sheet metal bracket

## What you will make

A bent bracket from 2 mm sheet: an 80 by 40 mm base with two 6 mm holes, and a 30 mm flange bent up along the back edge with a 2 mm bend radius. You will also show and export its flat pattern.

## What you will learn

- Setting the sheet values in **Sheet Metal Parameters**.
- **Base Flange** from a sketch, and **Edge Flange** on an edge.
- **Flatten** and **Export Flat Pattern**.

## Steps

1. Choose File, **New Part** (Ctrl+N) and pick millimetres.
2. Select Front Plane and click **Sketch** (S).
3. Pick **Corner Rectangle** (R). Draw a rectangle from the origin and dimension it 80 by 40 with **Smart Dimension** (D).
4. Draw two **Circle** (C) shapes of diameter 6 inside it. Place their centres at X = 20, Y = 15 and X = 60, Y = 15.
5. Exit the sketch and rename it to `Base Sketch`.
6. Open the Sheet Metal tab and click **Base Flange**.
7. This is the first sheet metal feature, so FDCAD first asks for the sheet values. Type `2` for Thickness and `2` for Bend radius. Leave the other values. Click OK.
8. The Base Flange panel opens on Base Sketch. Click OK. The feature is named Base Flange 1, and a Flat Pattern feature is added at the end of the tree.
9. Click the top edge along the back of the base: the 80 mm edge at Y = 40 on the upper face of the sheet.
10. Click **Edge Flange**. Type `30` for Length. Leave Measure from at Outer virtual sharp and Trim side bends ticked.
11. Click OK. The feature is named Edge Flange 1.
12. Click **Flatten** on the Sheet Metal tab. The part is shown flat, with its bend lines. Click Flatten again to fold it back.
13. To make a cutting file, click **Export Flat Pattern** and save the pattern as DXF, SVG or STEP.

## Check your result

1. Choose File, Open, go to the samples folder and open `sheet_metal_bracket.fdprt`.
2. Compare the feature tree: Sheet Metal (the folder that holds the sheet values), Base Sketch, Base Flange 1, Edge Flange 1, Flat Pattern.
3. Click **Print Estimate** on the 3D Print tab. The folded volume should be about 10.56 cm³.
4. Open `sheet_metal_bracket_flat.fdprt` too. It is the same part with the flat pattern shown. Compare it with your part after Flatten. The flat pattern should be 80 mm by about 66.52 mm.

## Try this

- Double click the Sheet Metal folder in the tree and change the thickness to 3 mm. Both walls get thicker and the flat size changes.
- Edit Edge Flange 1 and change the length to 45. Flatten again to see the longer flat pattern.

See also [../sheet-metal.md](../sheet-metal.md) and [../import-export-print.md](../import-export-print.md).
