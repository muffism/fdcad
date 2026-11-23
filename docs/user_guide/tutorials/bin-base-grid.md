# Bin base grid

## What you will make

The base plate the storage bins sit on: 3 by 2 cells of 42 mm, each a 3 mm deep pocket 1.2 mm in from the cell's sides. A bin from [storage-bin.md](storage-bin.md) drops into a cell and stays put.

## What you will learn

- Formulas that place shapes on a grid, such as `=Grid * 2 + Lip`.
- One sketch with several closed shapes cut in one Extruded Cut.

## Steps

1. Choose File, **New Part** (Ctrl+N) and pick millimetres. In **Equations** add `Grid = 42mm`, `Lip = 1.2mm` and `Base = 5mm`.
2. Sketch on Front Plane: a rectangle from the origin, `=Grid * 3` by `=Grid * 2`. Extrude it `=Base`. Rename it to `Base`.
3. Sketch on the top face: six rectangles `=Grid - 2 * Lip` square. Place the corner of each at `=Grid * i + Lip` and `=Grid * j + Lip` from the origin, for column i (0 to 2) and row j (0 or 1). Rename it to `Cell Sketch`.
4. Click **Extruded Cut**, Blind, 3 mm into the plate. Rename it to `Cells`.

## Check your result

1. Open `bin_base_grid.fdprt` from the samples folder.
2. The volume is 24693.12 mm³.

## Try this

- Set `Grid` to `40mm`: the plate and every cell follow.
- Set `Lip` to `1.5mm` for a looser fit of the bins.
