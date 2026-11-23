# Storage bin

## What you will make

A storage bin 2 by 1 grid units of 42 mm, 30 mm tall, with 1.6 mm walls and a 2 mm floor. Every size comes from a variable, so the same part makes bins of any size on the same grid.

## What you will learn

- Number variables (`Wide`, `Deep`) next to length variables (`Grid`, `Height`, `Wall`, `Floor`).
- Dimensions typed as formulas, such as `=Grid * Wide - 2 * Wall`.

## Steps

1. Choose File, **New Part** (Ctrl+N) and pick millimetres.
2. Open **Equations** and add the length variables `Grid = 42mm`, `Height = 30mm`, `Wall = 1.6mm` and `Floor = 2mm`, and the number variables `Wide = 2` and `Deep = 1`.
3. Select Front Plane and click **Sketch** (S). Draw a rectangle from the origin and dimension it `=Grid * Wide` by `=Grid * Deep`. Exit and rename it to `Bin Sketch`.
4. Click **Extruded Boss** (Shift+E). Blind, depth `=Height`. Rename it to `Bin`.
5. Sketch on the top face. Draw a rectangle `=Grid * Wide - 2 * Wall` by `=Grid * Deep - 2 * Wall`, its corner `=Wall` from both edges. Rename it to `Cavity Sketch`.
6. Click **Extruded Cut**, Blind, depth `=Height - Floor`, into the bin. Rename it to `Cavity`.

## Check your result

1. Open `storage_bin.fdprt` from the samples folder.
2. Both parts have a volume of 18058.88 mm³.

## Try this

- Set `Wide` to `3` and `Deep` to `2` for a larger bin on the same grid.
- Set `Height` to `60mm`: the cavity follows, and the floor stays 2 mm.
