# Node editor

The node editor builds geometry and values from a graph of nodes joined by wires. Use it for patterns that are hard to sketch by hand, such as holes that grow with their distance from a point, or to drive the part's variables from sliders. Each part has one graph. Its results go into the feature tree as normal features, so the rest of FDCAD works with them.

Where to find it: the Graph command tab; Tools, Node Editor.

## Node Editor

**Node Editor** opens the node editor panel beside the viewport. Click it again to hide the panel.

1. Open a part.
2. Click **Node Editor** on the Graph tab, or choose Tools, Node Editor.
3. The panel shows the canvas on the left and, on the right, the node search above the settings of the selected node.
4. Double click empty canvas to add your first node. The part's graph, Graph 1, is made with it.

Tips:

- Wheel zooms about the cursor. Middle drag or Space drag pans.
- Drag a box on empty canvas to select several nodes.
- Every graph edit is one undo step, like any other change.
- The graph shows in the feature tree as a row named Graph 1 (node graph). Double click it to open the editor.
- The panel's title bar has two buttons. **Float** puts the editor in a window of its own, and the same button, now **Dock**, puts it back. **Close** hides the panel.
- Double click the title bar to float or dock the editor. Drag the title bar to dock it at another side of the window.

## Graph tab commands

| Command | Key | What it does |
| --- | --- | --- |
| **Node Editor** | | Show or hide the panel. |
| **Set Graph Position** | | Run the graph after the feature selected in the tree. |
| **Add Node** | Shift+A | Focus the node search. The chosen node goes in the middle of the view; double click empty canvas to place it where you click. |
| **Add Comment** | | Add a note on the canvas. |
| **Group Nodes** | Ctrl+G | Put the selected nodes in a named frame. |
| **Ungroup Nodes** | Ctrl+Shift+G | Remove the frame round the selected nodes. |
| **Fit Graph** | | Show every node. |
| **Delete Nodes** | Backspace | Delete the selected nodes and wires. Delete works too. |
| **Copy Nodes** | none | Copy the selected nodes and the wires between them. Set a key in the shortcut editor. |
| **Paste Nodes** | none | Paste copied nodes a little down and to the right. Set a key in the shortcut editor. Delete, copy and paste keys leave a text field in the settings pane alone. |

The keys work only while the canvas has focus, so they never take keys from the rest of FDCAD.

## Adding nodes

1. Double click empty canvas, or press Shift+A.
2. Type part of a name in Search nodes, for example `grid`.
3. Pick the node. It appears where you clicked.

Node categories, in the order the list shows them:

- Input: Number Slider, Value, Boolean Toggle, Point, Read Variable, Read Feature Parameter, Model Reference.
- Math: Arithmetic, Trigonometry, Range, Series, Remap, Random Numbers, Expression.
- List: List Item, List Length, Reverse List, Sort List, Shift List, Cull by Pattern, Flatten List.
- Point and Vector: Vector, Deconstruct Point, Plane, Distance, Closest Point, Point Grid, Divide Curve, Populate Region.
- Curve: Line, Polyline, Arc, Circle, Interpolated Curve, Offset Curve.
- Solid: Box, Cylinder, Sphere, Extrude Curve, Pipe, Boolean Union, Boolean Difference, Boolean Intersection, Move, Rotate, Scale, Mirror, Linear Array.
- Pattern: Attractor, Voronoi Cells, Strut Lattice.
- Output: Set Variable, Set Feature Parameter, Add as Feature.
- Display: Comment.

Tips:

- A graph can have up to 500 nodes.
- Each category has its own colour band on the node card.
- Model Reference reads a face, edge, curve or body of the part. Select it in the view, then click Use Selection in the node settings.
- Read Variable and Read Feature Parameter bring the part's values into the graph.

## Wiring

Inputs are on the left of a node card and outputs on the right. Port colours show the type of value.

1. Drag from an output port to an input port.
2. Release on the port. The wire is drawn.
3. To remove a wire, select it and press Backspace or Delete.

Rules:

- Number, length and angle ports mix freely. Point and vector ports mix. Curve and body ports mix, and the node checks what it gets.
- Square ports take a whole list. Round ports take one value.
- A list wired into a round port runs the node once per item.
- Several wires into a square port make one list, in wire order.
- When two round ports get lists of different lengths, the node runs as many times as the longest list, and the shorter list repeats its last item. An empty list gives an empty result.
- A new wire into a round port replaces the old wire.
- Wires can never form a loop.

Tips:

- An input with no wire takes its value from the node settings. Values there accept the full expression syntax, including variables, as in [typing-values.md](typing-values.md).
- The value of a node's first output shows under its card.

## Sliders

The Number Slider node gives a value you drag.

1. Add a Number Slider.
2. In its settings, set the kind (number, length or angle), min, max and step.
3. Drag the slider in the settings. The preview updates as you drag.

Tips:

- The value snaps to whole steps from the minimum.
- One drag is one undo step.
- Wire a slider into Set Variable or Set Feature Parameter to drive the part.

Common errors:

- "The slider maximum is below its minimum. Swap them.": max must be larger than min.

## Preview

A short moment after each edit, the graph runs in the background and shows a see through ghost in the view.

- The ghost shows the geometry of the selected nodes, and of nodes whose geometry feeds nothing else.
- The body from Add as Feature is shown in the part itself, not as a ghost.
- Nodes with errors get a red frame. Hover a red node to see why. The settings show the message too.

## Set Graph Position and the cycle rule

The graph has a position in the feature tree. It runs after that feature, and it may read model geometry only from features at or above that position.

1. Select a feature in the feature tree.
2. Click **Set Graph Position** on the Graph tab.
3. The status bar says the graph now runs after that feature. The graph row moves to just below it in the tree.

The cycle rule:

- A feature at or above the graph's position must not use a value that the graph sets. If it does, that feature shows an error that names both and says to move the graph.
- A feature made by Add as Feature must be below its graph.

Tips:

- A new graph starts at the end of the tree.
- To drive a feature with a slider, put the graph above that feature. The graph cannot then read that feature's geometry.
- The typed text in the part never changes. Remove the graph and the part goes back to its typed values.

Common errors:

- "Select a feature in the feature tree first.": select a row in the tree before Set Graph Position.

## Add as Feature

The Add as Feature node puts a body from the graph into the feature tree.

1. Add an Add as Feature node. A Graph Body feature is added at the end of the tree in the same step.
2. Wire a body into its Body input.
3. Choose its operation in the settings: new keeps a new body, add joins it to the part, subtract cuts it from the part.

Tips:

- Later features can use the faces of a Graph Body like any other faces.
- Several bodies wired in are added as one feature.

## Run Anyway

Booleans on many bodies can take a long time. Boolean Union, Boolean Difference, Boolean Intersection and Strut Lattice stop before running on more than 200 bodies or struts.

1. The node shows a warning that it may take a long time.
2. Select the node and click Run Anyway in its settings to go on.
3. Or use fewer bodies.

Run Anyway is saved on the node and can be undone.

## Sample graphs

Four sample graphs are in the `graphs` folder inside the samples folder. Open them with File, Open.

- `attractor_plate.fdprt`: a 120 by 80 by 6 mm plate with a grid of holes that grow from 1 mm radius near a point to 4 mm far away. See [attractor-plate.md](tutorials/attractor-plate.md).
- `voronoi_panel.fdprt`: a panel with 24 seeded random Voronoi cells cut through it.
- `slider_bracket.fdprt`: an L bracket whose leg lengths and width come from three sliders.
- `lattice_block.fdprt`: a base with a cubic strut lattice filling a block on it.

Random nodes use a seed, so a graph gives the same result every time it runs.
