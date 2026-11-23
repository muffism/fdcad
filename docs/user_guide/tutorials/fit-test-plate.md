# Fit test plate

## What you will make

A 70 by 30 by 4 mm plate with a row of five pins and a row of five holes. The holes are wider than the pins by 0.2, 0.4, 0.6, 0.8 and 1.0 mm, so the gap on each side steps by 0.1 mm. Print it, try each pin in the holes of the other plate, and use the tightest gap that fits for your printer.

## What you will learn

- How global variables drive sketch dimensions (`Pin` and `Step`).
- How one test print tells you the fit value to type in **Print Fit** and the printer profile.

## Steps

1. Choose File, **New Part** (Ctrl+N) and pick millimetres.
2. Open **Equations** (Tools menu) and add three variables: `Pin = 5mm`, `Step = 0.1mm` and `Plate = 4mm`.
3. Select Front Plane and click **Sketch** (S). Draw a 70 by 30 rectangle from the origin. Exit the sketch and rename it to `Plate Sketch`.
4. Click **Extruded Boss** (Shift+E). Choose Blind and type `=Plate` for the depth. Rename it to `Plate`.
5. Sketch on the top face. Draw five circles in a row 9 mm from the front edge, at X = 11, 23, 35, 47 and 59. Dimension their diameters `=Pin + 2 * Step`, `=Pin + 4 * Step` and so on up to `=Pin + 10 * Step`. Rename the sketch to `Hole Sketch`.
6. Click **Extruded Cut**, choose **Through All** and rename it to `Holes`.
7. Sketch on the top face again. Draw five circles of diameter `=Pin` in a row 22 mm from the front edge, at the same X values. Rename the sketch to `Pin Sketch`.
8. Click **Extruded Boss**, Blind, depth `6`. Rename it to `Pins`.

## Check your result

1. Choose File, Open, go to the samples folder and open `fit_test_plate.fdprt`.
2. Compare the two parts with **Mass Properties** or the feature tree. Both have the same volume, 8495.19 mm³.

## Try this

- Change `Step` to `0.05mm` for a finer test. All five holes update.
- Change `Pin` to `3mm` for small pins.
- Print two plates and try the pins of one in the holes of the other: the first hole the pin slides into is your fit gap.
