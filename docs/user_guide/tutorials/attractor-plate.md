# Attractor plate

## What you will make

A 120 by 80 by 6 mm plate with a grid of 77 holes, 11 across and 7 down. The holes are small near one point and grow larger further away: 1 mm radius at the point, up to 4 mm at 70 mm or more.

## What you will learn

- Opening the **Node Editor** and adding nodes.
- Wiring a Point Grid, an Attractor and a Cylinder.
- Cutting the result from the part with **Add as Feature**.

## Steps

### Build the plate

1. Choose File, **New Part** (Ctrl+N) and pick millimetres.
2. Select Front Plane and click **Sketch** (S). Draw a **Corner Rectangle** (R) from the origin and dimension it 120 by 80 with **Smart Dimension** (D).
3. Exit the sketch and rename it to `Plate Sketch`.
4. Click **Extruded Boss** (Shift+E). Choose Blind and a depth of `6`. Click OK. Rename it to `Plate`.

### Build the graph

5. Open the Graph tab and click **Node Editor**. The panel opens beside the view.
6. Double click empty canvas, type `point` in Search nodes and add a Point node. In its settings, type X `10`, Y `10` and Z `-5`. This is the first grid point, 5 mm below the plate.
7. Add a Plane node. Drag from the Point node's output to the Plane node's Origin input.
8. Add a Point Grid node. Wire the Plane output into its Plane input. In its settings, type Count X `11`, Count Y `7`, Spacing X `10` and Spacing Y `10`. The grid now runs from 10 to 110 mm across and 10 to 70 mm up.
9. Add a second Point node, below the first. Type X `35`, Y `40` and Z `-5`. This is the attractor point.
10. Add an Attractor node. Wire the Point Grid output into its Points input, and the second Point into its Attractors input. Type Radius `70`, Near `1` and Far `4`.
11. Add a Cylinder node. Wire the Attractor's Points output into its Base input, and the Attractor's Values output into its Radius input. Type Height `16`. The cylinders stand on Z = -5 and pass through the whole plate. The preview shows 77 ghost cylinders.
12. Add an Add as Feature node. A Graph Body 1 feature appears at the end of the feature tree. Wire the Cylinder's Body output into its Body input. Set its operation to subtract.
13. If you like, click **Add Comment** and type a note such as "Holes grow from 1 mm radius near the point to 4 mm far away."
14. Check the feature tree. The graph row, Graph 1 (node graph), sits right below Plate. Graph Body 1 is below it, as the cycle rule needs.

## Check your result

1. Choose File, Open, go to the samples folder, open the `graphs` folder and open `attractor_plate.fdprt`.
2. Compare the feature tree: Plate Sketch, Plate, Graph 1, Graph Body 1.
3. Open the Node Editor in the sample and compare the nodes and wires with yours. Click **Fit Graph** to see them all.
4. Click **Print Estimate** on the 3D Print tab. The volume should be about 46.14 cm³.

## Try this

- Select the attractor Point node and change X to `90`. The small holes move to the right side of the plate.
- Select the Attractor node and swap Near and Far: type Near `4` and Far `1`. The holes are now large near the point and small far away.
- Add a Number Slider with kind length, min `10`, max `110` and step `5`. Wire it into the attractor Point's X input, then drag the slider to move the attractor live.

See also [../node-editor.md](../node-editor.md).
