# Configured bolt family

## What you will make

A simple socket head bolt, head and shank, in three sizes: M6 x 20, M8 x 30 and M10 x 40. All three live in one file as configurations, made from a design table. The head sizes are the nominal values of ISO 4762.

## What you will learn

- Driving a part from global variables.
- Making configurations from a **Design Table** read from a CSV file.
- Switching configurations.

## Steps

1. Choose File, **New Part** (Ctrl+N) and pick millimetres.
2. Open the Variables tab and click Add Variable four times:

   | Name | Expression | Meaning |
   | --- | --- | --- |
   | D | 6mm | shank diameter |
   | L | 20mm | shank length |
   | DK | 10mm | head diameter |
   | K | 6mm | head height |

3. Select Front Plane and click **Sketch** (S). Draw a **Circle** (C) centred on the origin. Dimension its diameter as `=DK` with **Smart Dimension** (D).
4. Exit the sketch and rename it to `Head Sketch`.
5. Click **Extruded Boss** (Shift+E). Choose Blind and type `=K` for the depth. Click OK. Rename it to `Head`.
6. Click the end face of the head, away from the Front plane, and click **Sketch**.
7. Draw a circle centred on the head's centre. Dimension its diameter as `=D`.
8. Exit the sketch and rename it to `Shank Sketch`.
9. Click **Extruded Boss**. Choose Blind and type `=L` for the depth. Click OK. Rename it to `Shank`.
10. In a text editor, make a file named `bolts.csv` with these lines:

    ```
    Configuration,var.D,var.L,var.DK,var.K
    M6 x 20,6,20,10,6
    M8 x 30,8,30,13,8
    M10 x 40,10,40,16,10
    ```

11. Choose Tools, **Design Table**. Click Import CSV... and pick `bolts.csv`. The grid shows three rows and five columns: the configuration name and four values.
12. Click OK. FDCAD makes the three configurations. The Default configuration has no row in the file, so it is deleted.
13. Open the Configurations tab in the left panel. Double click M8 x 30 to show it.

## Check your result

1. Choose File, Open, go to the samples folder and open `configured_bolt_family.fdprt`. It opens with M8 x 30 active.
2. Compare the feature tree: Head Sketch, Head, Shank Sketch, Shank. Compare the Configurations tab: M6 x 20, M8 x 30, M10 x 40.
3. With M8 x 30 shown, click **Print Estimate** on the 3D Print tab. The volume should be about 2.57 cm³.
4. Use **Measure** on the head's round face: the diameter should be 13 mm. The bolt is 38 mm long overall.

## Try this

- Open the Design Table and click Add Row. Name the new row `M8 x 50` and fill in 8, 50, 13 and 8. Click OK, then show the new configuration.
- Show M6 x 20. Right click the depth field of Shank in its panel, choose Configurations, This Configuration, and type `=L + 5mm`. Only M6 x 20 changes.

See also [../equations-and-configurations.md](../equations-and-configurations.md).
