# Sketching

A sketch is a flat drawing on a plane or a flat face. Most features start from one: you draw the shape, give it sizes with dimensions and relations, then exit and extrude or revolve it. This page covers every tool on the Sketch tab.

Where to find it: the Sketch command tab (groups Sketch, Draw, Modify, Tools and Text), and the shortcut bar (Q) while a sketch is open.

## How sketch tools work

You can choose a sketch tool, such as Line, before any sketch is open: the planes show, the status bar asks for a plane or flat face to draw on, and the one under the cursor lights up. Click it and the sketch opens there with the tool ready.

1. A drawing tool stays active, so you can draw several shapes in a row.
2. End a tool with Esc, by clicking its button again, by picking another tool or by clicking **Select**. Right click and choose Select also ends it.
3. Draw two click shapes by click, move, click, or by press, drag, release.
4. While a tool is active, the left panel shows its options and the values of the last shape. Type a value and press Enter to change the shape.
5. Every step can be undone with Ctrl+Z while the sketch is open. In an open sketch, undo, redo, copy and paste always use the standard keys (Ctrl+Z, Ctrl+Y or Ctrl+Shift+Z, Ctrl+C, Ctrl+V), and Delete or Backspace deletes, even if you change those keys in the shortcut editor.
6. You can type sizes and tool values right in the sketch, next to the cursor. See [Typing sizes while you draw](#typing-sizes-while-you-draw) and [Tool values in the sketch](#tool-values-in-the-sketch).

## Typing sizes while you draw

While a line, rectangle, circle, arc or slot is being drawn, type a number. A value box opens at the cursor.

1. Line, Centerline and Midpoint Line: after the first click, the number is the length (for Midpoint Line, the whole length).
2. Corner Rectangle and Center Rectangle: after the first click, the number is the width. Press Enter and the box asks for the height. Tab and Shift+Tab switch between width and height.
3. Circle and Centerpoint Arc: after the centre, the number is the radius.
4. Straight slots: after the first click, the number is the length between the end centres. After the second click, it is the width.

Press Enter to fix the size. The shape keeps following the cursor for its direction, but its size stays. Click to finish the shape, or press Enter again to finish it where the cursor is. The shape gets a driving dimension with the value you typed, as if you had used Smart Dimension. The shape and its dimension are one undo step.

Values accept units and formulas, see [Typing values](typing-values.md). A size must be greater than zero. A wrong value turns the box red with a message and nothing changes. Esc closes the box without changing anything.

To see the box without typing first, turn on Preferences > Sketch > On screen value input while drawing. The size box then opens at the cursor as soon as a shape starts. Type a size and press Enter, or keep drawing with the mouse: a click places the point as normal.

## Tool values in the sketch

Tools with a length, angle or count in their panel show those values in the sketch too: Offset, Sketch Fillet, Sketch Chamfer, Linear and Circular Sketch Pattern, Polygon and Sketch Picture. The values appear as labels beside the first curve you pick (or the curve under the cursor, or the first click) as soon as there is something to preview.

1. Click a label, or type a digit, a minus sign, a dot or `=`, to open the value box there. While drawing, typing a size works for lines, centerlines, rectangles (all kinds), parallelograms, circles, centre point arcs and straight slots; the tangent arc, three point arc, ellipse, polygon, arc slots and spline take their sizes from clicks only. Typing opens the label you used last, or the first one.
2. Enter applies the value to the preview and the tool keeps going. Click the tool's own button (such as Make Pattern) or click in the sketch to finish as before.
3. Tab and Shift+Tab apply the value and move to the next or previous label.
4. Esc closes the box and puts back every value it changed.
5. The panel field and the label always show the same value.
6. Counts are whole numbers without a unit. Angles are in degrees unless you type a unit. Lengths use the part's units.

## Sketch

**Sketch** (S) opens a new sketch.

**Steps**

1. Select a plane or a flat face, then press S. The sketch opens at once.
2. Or press S with nothing selected. The three default planes appear. Click one, or click a flat face. Esc cancels.
3. The view turns to face the sketch and the Sketch tab opens.

**Tips**

1. To edit a finished sketch, right click it in the tree and choose **Edit Sketch**. A sketch on a part with spline faces, such as a thread, a loft or a spring, opens in under a second.
2. **Edit Sketch Plane** moves a finished sketch to another plane or flat face. Select the sketch in the tree, run the command, pick the new plane and click OK.
3. To leave the sketch, use **Exit Sketch**, which saves it. **Exit Without Saving** (under Exit Sketch on the Sketch tab) drops every change made since the sketch was opened, after asking. Two Sketch preferences, both off at first, add quicker ways out: **Double click empty space to exit the sketch**, and **Esc with nothing to cancel exits the sketch** (Esc first stops the tool and clears the picks, then one more Esc saves and leaves).

## Line and Centerline

**Line** (L) draws straight lines. **Centerline** (Alt+C) draws dashed construction lines, used as revolve axes and for symmetry.

**Steps**

1. Click the start point, then click the end point.
2. The line continues from the end point, so each click adds a segment.
3. Double click, or press Esc, to end the chain. Clicking the start of the chain closes it.

Options: Orientation (As drawn, Horizontal, Vertical or Angle), For construction, and the Length and Angle of the last line. Tip: move back onto the end point and away again to draw a tangent arc from it.

**Switch Line and Arc** (no default key) does the same from the keyboard while the Line tool is drawing: the next segment becomes an arc from the last end point, and running it again goes back to a line. Give it a key in Preferences if you use it often. The status bar says when there is no segment to continue.

**Midpoint Line** draws a line from its middle: click the middle, then one end, and the other end mirrors it. The middle gets a Midpoint relation, so the line stays centred when you change its length. A typed length is the whole length.

**Infinite Construction Line** (in the Line dropdown) draws a construction line through two clicks that runs on far beyond both (1 m each way from the first click), for layout lines you trim later to the length you need. Both clicked points stay on the line, and a horizontal or vertical snap gives the line that relation.

## Rectangles

When you click quickly with the Line tool, a second click within the pick distance of the first is ignored, so no tiny segment is made.

**Corner Rectangle** (R) draws a rectangle from two opposite corners. **Center Rectangle** draws one from its centre and a corner, with construction diagonals.

Both have extras in the tool panel, made with the rectangle in one undo step: **Construction lines** (corner to corner, or midpoint to midpoint of opposite sides), **Corner radius** (rounds all four corners, with one radius dimension) and **Inner frame offset** (a second rectangle inside, at that distance, with its dimension). Leave a value at 0 for none.

Click the first corner (or the centre), then the opposite corner. Hold Shift while placing the second click for a square. The sides get Horizontal and Vertical relations.

Three more rectangle tools sit in the same dropdown. Their sides get Parallel and Perpendicular relations instead, so they can sit at any angle.

1. **3 Point Corner Rectangle**: click two corners to set one side at any angle, then click to set the other side.
2. **3 Point Center Rectangle**: click the centre, click the middle of one side, then click to set the other size. It gets construction diagonals.
3. **Parallelogram**: click two corners, then click the third corner anywhere. Only opposite sides stay parallel.

Hold Shift on the last click of a 3 point rectangle to make a square. Three points in a line make nothing.

## Circle and arcs

**Circle** (C): click the centre, then a point to set the radius. Its panel has Center X, Center Y, Radius and For construction.

1. **Centerpoint Arc**: click the centre, click the start (sets the radius), then click the end.
2. **Tangent Arc**: click the end of a line or arc, then move and click. Leave the end along the curve for a tangent arc, or sideways for an arc at right angles. Go back to the end point to choose again. Tick **Flip direction** in the tool panel to leave the end backward along the curve, so the arc turns back over it.
3. **3 Point Arc**: click the start, click the end, then move to set the bulge and click.
4. **Perimeter Circle** (in the Circle dropdown): click three points on the circle. After two clicks the circle follows the cursor. Points in a line give no circle.

**Point** (P) places a sketch point, for example to mark a hole centre. Points are not part of profiles, but you can dimension and relate them.

## Slot and Polygon

**Slot** draws a slot. Choose its type in the panel: straight, centre straight, 3 point arc or centre point arc. The prompt line tells you what to click next. Options: Add dimensions, and Length measured centre to centre or overall.

**Polygon** draws a regular polygon from its centre and a corner. Options: Sides (3 to 40), Corners on the circle (on by default; off makes the sides touch the circle), Triangle (sets three sides) and New Polygon. Change the size through the construction circle. For a hex nut drawn by its size across the flats, turn Corners on the circle off, so the circle's diameter is the size across the flats. To change a polygon later, right click one of its sides and choose **Edit Polygon**: change the sides, Corners on the circle, the circle diameter or the angle of the first corner (or of the middle of the first side). The polygon is made again about the same centre and circle, in one undo step; dimensions and relations on the centre and the circle stay, those on the old sides go.

## Spline, Ellipse and Partial Ellipse

1. **Spline**: click points, then double click to finish. Press and drag at a point to set its tangent handle. Each point and handle can be dragged, related and dimensioned.
   Tick Show curvature in the sketch panel with a spline selected, or use View > Hide or Show > Curvature Combs, to see curvature combs. Longer teeth mean a tighter bend.
2. **Ellipse**: click the centre, the end of the major axis, then set the minor size. Both axes are added as construction lines through the centre, so you can dimension the axis lengths or the ellipse's angle with them; untick **Construction axes** in the tool panel to leave them out.
3. **Partial Ellipse**: click the centre and the two axes, then move along the outline and click to end.
4. **Conic**: click the start, then the end, then the top point where the two end tangents meet. **Shape** in the tool panel sets how full the curve is: 0.5 is a parabola, a smaller value is flatter (part of an ellipse), a larger one is fuller. The conic becomes a spline you can edit like any other.
5. **Equation Curve**: type **x(t)** and **y(t)**, for example `20*cos(t)` and `10*sin(t)`, the range of **t** and the number of points, then click **Add Curve**. Plain numbers use the part's unit. The curve is a spline through points on your equations.
6. **Partial Hyperbola**: click the centre, the vertex (the tip of the branch), then one end. The branch runs through the vertex to that end and to its mirror across the axis.

Only Coincident and Fixed work on ellipses. Smart Dimension measures between their axis points.

Offset, Mirror, Trim, Extend, the sketch patterns, Sketch Fillet and Sketch Chamfer work on lines, circles and arcs (Sketch Fillet and Chamfer on lines, arcs and splines). Clicking a spline or an ellipse with one of them says so in the status bar. Select Chain in Offset stops at a spline and says so. Swept paths, Pipe, Thin Feature and Rib use splines and ellipses, and a spline or ellipse shape can sit beside curves that cross.

## Trim and Extend

**Trim** removes pieces of curves up to where they cross. Choose a mode in the panel:

1. Drag trim: hold and drag across curves. Each crossed curve loses the piece between its nearest crossings.
2. Corner: pick two curves. Both are trimmed or extended to meet.
3. Trim inside: pick two boundary curves, then the curves to cut between them.
4. Trim outside: pick two boundary curves, then keep only what lies between them.
5. Trim to nearest: click a piece to remove it up to the nearest crossings.

**Extend** carries a line or arc on to the next curve. Hover to preview, click to apply.

Relations and dimensions on removed pieces are removed too. The status bar lists them.

## Split Entities

**Split Entities** (in the Trim dropdown) splits a curve where you click. The two pieces share one sketch point, which you can dimension and drag along the curve: two lines stay collinear, two arcs keep their centre and radius.

1. Lines, arcs and partial ellipses: one click.
2. Circles and ellipses: two clicks, so they become two pieces.
3. Splines: the split goes to the nearest through point between the ends.

Select the split point and press Delete to join the pieces again. When the point has a relation or dimension, Delete removes it like any other point.

## Offset

**Offset** copies curves at a distance to one side. The copies follow the originals when they change.

**Steps**

1. Click a curve, or a straight or round part edge. Select chain adds all joined curves.
2. Move the cursor to choose the side and distance, or type a Distance.
3. Click, or press Place Offset.

**Options**

Distance, Add dimension, Reverse, Select chain, Both directions, Make base construction, Make offset construction, Cap ends (None, Arcs or Lines), and Outside corners. Outside corners is Sharp (the curves are extended until they meet, as before) or Round (an arc goes round each outside corner, with its centre on the source corner and a radius equal to the offset distance). Inside corners always meet sharp.

**Common errors**

1. Curves that would cross themselves at that distance are refused. Use a smaller distance.

## Mirror

**Mirror** copies curves to the other side of a mirror line, with Symmetric relations.

**Steps**

1. Click the curves to mirror.
2. Click a centerline or a straight part edge as the mirror line. Pick Mirror Line lets you use a solid line.

Option: Copy. On keeps the originals, off replaces them.

**Dynamic Mirror** (in the Mirror dropdown) mirrors while you draw. Select a line or centerline and click Dynamic Mirror, or click it and then click the line. Every line, arc, circle or rectangle you draw is mirrored about the line with Symmetric relations, in the same undo step, until you click Dynamic Mirror again or close the sketch. Splines and ellipses are not mirrored, and the status bar says so; Mirror cannot copy them either, so draw the other side yourself.

## Direction arrows

When the direction matters, the preview shows a short arrow. Offset points from the picked curves to the side the offset goes (both sides with Both directions). Linear Sketch Pattern points along Direction 1, and along Direction 2 when there is more than one row; Reverse turns the arrow round. Circular Sketch Pattern points from the original toward the next copy, so you see which way it turns. The arrows keep their size on screen at any zoom. They are display only.

## Sketch Fillet and Sketch Chamfer

**Sketch Fillet** rounds the corner between two lines, or where an arc or a spline meets a line or an arc end to end. **Sketch Chamfer** cuts such a corner with a straight line.

Click a corner point where two curves meet, or click the two curves on the side to keep.

To size a fillet by hand, press on the corner point and drag before you let go: the radius is the distance from the corner to the cursor, and the Radius field follows. A radius that does not fit keeps the last one that did. The new fillet gets its own radius dimension. It is one undo step.

On arcs and splines, each chamfer distance is the straight distance from the corner to the chamfer's end. A construction point keeps the corner and the two distances are dimensioned from it. Angle and distance needs two lines.

When a spline is cut back for a fillet or a chamfer, its new end and its direction there are exact. If more of the spline is kept beyond the cut piece, the cut piece bends a little between its ends.

**Options**

1. Sketch Fillet: Radius, Keep constrained corners, Dimension each fillet.
2. Sketch Chamfer: Type (Angle and distance, or Distance and distance), Equal distance, distances and Angle.

**Common errors**

1. A radius larger than the lines allow is refused. The message gives the largest radius that fits.
2. Two splines cannot be rounded or chamfered together. Pick a spline with a line or an arc.

## Convert Entities

**Convert Entities** copies part edges into the sketch as fixed curves. Click an edge of the part outline. Straight and round part edges can be converted; other part edges cannot. Select chain copies every joined edge. For construction makes construction curves. Click inside a face of the part outline (not on an edge) to copy the face's outer loop and its inner loops (holes) at once; the face lights up as you move over it. Untick **Inner loops** to copy the outer loop only. Hold Ctrl and click an edge to copy just the loop it belongs to.

Convert Entities also copies curve features, such as contour curves, projected curves and helices. While the tool is active, click the curve feature in the feature tree, or click its dotted outline in the sketch. Only curve features above the sketch in the tree are offered. Each edge is projected straight onto the sketch plane. Straight and round edges become lines, arcs and circles; other edges become splines. Edges that project to a point are skipped, and the status bar says how many. Contour loops that land on top of each other are copied once. The copies are fixed and do not follow later changes to the curve.

## Close Sketch to Model

An open profile whose two ends sit on the part's edges in the sketch plane can be closed by those edges. Draw the profile so each end lies on a part edge (snap to the edge), then run **Close Sketch to Model** (Sketch tab, with Convert Entities). The edges the ends sit on make a loop, and the profile cuts it into two shapes. Move the cursor inside the shape to keep: the part edges that would close it are previewed. Click to close the profile that way. The edges are copied into the sketch as fixed curves, joined to the profile's ends, in one undo step.

**Common errors**

1. The sketch must have one open profile with exactly two open ends. Delete or join curves until one is left.
2. Both ends must be on one loop of part edges in the sketch plane. Move each end onto a part edge.

## Slice Body

**Slice Body** (Tools menu) cuts the part with parallel planes and keeps each cut as a sketch, for a stack of laser cut sheets. Pick the **Base plane**, how many **Slices**, their **Spacing**, and a **Start offset** from the base plane (negative goes behind it). For each plane that meets the part you get an offset reference plane and a sketch on it holding the cut as fixed curves, all in one new tree folder, Slices. It is one undo step. The sketches do not follow later changes to the part; delete the folder and slice again.

To slice round an axis instead, for a turned or radial part, pick a reference axis in **Around axis**. The axis must lie in the base plane or run parallel to it. Then set the **Angle step** between planes and the **Start angle** from the base plane. Each slice gets an angle reference plane through the axis and its sketch.

## Intersection Curves and Silhouette

Both copy curves from the part into the sketch, as fixed curves. They are next to Convert Entities.

1. **Intersection Curves**: the curves where the sketch plane cuts the part.
2. **Silhouette**: the outline of the part as seen looking straight at the sketch.

Choose the tool: the curves show in the sketch. Click **Add Curves** in the tool panel to copy them. If you change the part later, open the tool and click Add Curves again; curves already in the sketch are not copied twice.

The silhouette is worked out only when you choose Silhouette (or Close Sketch to Model), not when the sketch opens. Until it is ready the tool says "Working out the silhouette curves...". When the part cannot be meshed, the tool says "Silhouette failed" and why, for example that the part's mesh is incomplete, so rebuild and try again. A flat end of a slanted part stays a straight line with sharp corners. On a part with free form faces, such as a thread, a loft or a spring, or with very many faces, the outline is found from the shaded mesh, so it comes in under a second. It is made of lines, arcs, circles and splines, and it follows the exact outline to within the mesh's accuracy. Details narrower than about a thousandth of the part's size are left out. On other parts the outline is exact.

## Insert DXF

**Insert DXF** (Sketch Tools group, with Convert Entities and Sketch Picture) reads the lines, arcs, circles, polylines, ellipses and splines of an ASCII DXF file into the open sketch, at true size.

1. Choose the file. Then choose the units (the file's own, or one you pick when the file gives none), a scale, an angle, the base point (the drawing's origin or its middle) and, when the drawing has several layers, which layers to take.
2. The drawing follows the cursor, held by its base point. Click to place it, or press Escape to cancel.
3. The new entities are under defined: ends that meet are joined, nothing is fixed, so you can dimension and move them. Text, hatches and blocks are not inserted; the options window says how many were left out.

## Sketch patterns

1. **Linear Sketch Pattern** repeats curves in a row or grid. Options: instances, spacing and angle for Direction 1 and Direction 2, Reverse, Pick Direction 1, Add spacing dimension, Fix direction and Make Pattern. Pick Direction 1 takes a sketch line or a straight edge of the part; with Fix direction on, a fixed copy of the part edge holds the direction.
2. **Circular Sketch Pattern** repeats curves around a centre. Options: Center X, Center Y, Pick Center Point, Radius, Angle from center, Instances, Total angle, Equal spacing, Reverse, Add radius and angle dimensions and Make Pattern. Radius and Angle from center say where the picked curves sit from the centre: type them to move the centre instead of typing its X and Y.

Pick the curves first, set the options, then press Make Pattern.

## Move, copy, rotate, scale and stretch

The Modify group has a dropdown with five tools that change sketch entities you pick, or that were selected before the tool started.

1. **Move Entities**: click the entities, then a base point, then the target point. Delta X and Delta Y follow the cursor and show in the view; type one and press Enter to move by it without a click.
2. **Copy Entities**: the same as Move, but the originals stay. Copies sets how many; each copy is one more step away. Tick **Linked** (with Keep relations on) and each copied dimension shares its value with the original: change either and all of them change.
3. **Rotate Entities**: click the entities, then the center of rotation (or type Center X and Y). The angle follows the cursor from the X direction; type it and press Enter.
4. **Scale Entities**: click the entities, then the base point, type the scale factor and press Enter or click. Tick Copy to keep the originals and add scaled copies.
5. **Stretch Entities**: drag a box across the ends to move (or click two corners). Points inside the box move by the base point to target distance, or the typed Delta X and Y; lines that cross the box get longer or shorter.

Keep relations (on by default) keeps the relations and dimensions among the moved entities and removes the ones to entities that stayed; the status bar names what was removed. Rotating drops Horizontal and Vertical (a quarter turn swaps them), and scaling scales length dimensions. Turn Keep relations off to remove every relation and dimension of the moved entities. Each change is one undo step, and Escape steps back: the base point, then the picks.

## Smart Dimension

**Smart Dimension** (D) adds a size that drives the sketch. It picks the kind of dimension from what you click. When it copies a part edge into the sketch as a construction line to measure to, Esc, or leaving the tool, takes that line away again.

**Steps**

1. Click one or two items: lines, points, circles, arcs, the origin or part edges.
2. Move the cursor and click to place the text.
3. A value box opens beside the dimension. Type the value and press Enter.

**What you get**

1. One line: its length. A circle: its diameter. An arc: its radius.
2. Two parallel lines: the distance between them. Two other lines: the angle.
3. Two points: a horizontal, vertical or true distance, by where you place the text.
4. A circle with another item: the distance to its centre. Change this with Measure To (Center, Nearest or Farthest) in the Dimension panel.
5. A line and a centerline, with the text past the centerline: a doubled distance, shown as a diameter, for revolve profiles. After the first one, diameter mode stays on: click just a line parallel to that centerline and place the text anywhere to get its diameter. Esc turns diameter mode off with the tool.
6. An arc and both of its end points, in any order: the arc length.
7. Turn on **Smart Dimension picks midpoints** on the Sketch page of Preferences to dimension to the middle of a line, an arc or a part edge: where the midpoint snap shows, the click picks the midpoint, and FDCAD adds a construction point held there, shared by later dimensions to the same midpoint. It is off by default, so a click on the middle of a line gives its length. Two more switches there turn end point and centre picks off, so the click picks the curve instead.
8. Hold Shift when you click a circle or arc to measure to its near or far side instead of its centre. Click the side that faces the other item for the nearest distance, or the far side for the farthest. This works with a line or another circle, not with a point.

**Tips**

1. In the value box, the mouse wheel or Up and Down change the value by the spin step. Hold Ctrl for ten steps or Alt for a tenth.
2. Double click any dimension to change it; with Smart Dimension active one click on its text is enough. Drag its text to move it.
3. Values accept units and formulas. See [Typing values](typing-values.md).
4. A horizontal or vertical distance keeps its side: when other values change, the point stays on the same side of what it is measured from. Type a negative value to move it to the other side.
5. To keep a sketched shape's proportions, turn on Preferences > Sketch > Keep proportions on the first dimension. The first length you type then scales the whole sketch about the sketch origin, so a rough outline keeps its shape at the new size. It only works while no other driving dimension, Fix or model geometry sizes the sketch. Undo returns the old size.
6. To keep what you have sized in place while you drag the rest, turn on Preferences > Sketch > Lock changed dimensions while dragging. The curves and points of every dimension whose value you changed since the sketch opened then stay still during a drag. Closing and opening the sketch starts the list again.
7. Pick several dimensions and right click for **Make Reference**: they all become grey, measuring only dimensions in one step. Pick reference ones for **Make Driving** to make them drive again at their current sizes; any that would over define the sketch stay reference.
8. While a distance between two points follows the cursor, it turns horizontal, vertical or aligned with where you move. Right click to lock the type it shows now; then move the label anywhere and click to place it. Right click again to unlock.
9. To measure without driving anything, right click an empty spot and tick **New Dimensions Are Reference**: every dimension you place then only measures, in every sketch, until you untick it.
10. Pick several dimensions and right click for **Link Values** to give them one shared name. They take the first one's value, show the name on their labels, and from then on changing any one of them changes the others, with no formula. **Unlink Values** lets them go their own way again.

**Common errors**

1. "This dimension over defines the sketch. Make it a reference dimension?" Choose Make Reference to keep it as a grey, measuring only dimension, or Keep Driving and then delete another dimension or relation.
2. "These items cannot be dimensioned together. Pick other items." It also shows when one picked item takes no dimension by itself.

## Construction Geometry

**Construction Geometry** turns the selected items into construction geometry or back. Construction curves are dashed and never form a profile. You can also tick For construction in a tool panel.

## Fully Define Sketch

**Fully Define Sketch** (under Construction Geometry) adds the relations and dimensions a sketch still needs, at the sizes it has now. Nothing moves.

1. Choose the tool. To work on part of the sketch, select those items first.
2. In the tool panel, choose **Use** (the whole sketch or the selected entities), tick **Add relations** and **Add dimensions**, and pick a **Dimension scheme**:
   - **Baseline**: every point measured from the datum.
   - **Chain**: each point measured from the one before it.
   - **Datum Pairs**: a horizontal and a vertical distance from the datum for each point.
3. The datum is the sketch origin. Click a point to use it instead.
4. Click **Calculate** to see what would be added, then **Apply**. Undo removes it all in one step.

Items that are already fully defined are left alone. A sketch with conflicting dimensions or relations is not changed: fix those first.

## Baseline, ordinate, chamfer and path length dimensions

These make ordinary dimensions: they are driving, and you can make any of them a reference dimension.

* **Baseline Dimension** (in the Smart Dimension dropdown): click a base point or line, then each point or line to measure from it. From a base point the distances run along the **Direction** you pick in the tool panel; to or from a line they are square to it. The texts stack, each row one step further out. Press Escape to start again from a new base.
* **Ordinate Dimension** (same dropdown): click the zero point, then each point. Each point gets a short leader with its distance from the zero point along the axis you pick. The texts of one group sit in one row; drag any of them and the whole row moves.
* **Chamfer Dimension**: right click a chamfer line that has a line at each end and pick **Length and Angle** (its length and its angle to the first line) or **Two Lengths** (the distances from the corner the chamfer cut off to each end; a construction point marks the corner).
* **Path Length Dimension**: select a connected chain of lines and arcs, right click and pick **Path Length Dimension**. The value is the total length of the chain. Change it, or use it in equations, like any other dimension.

## Check Sketch for Feature

**Check Sketch** (under Relations) tells you whether the sketch will work for a feature before you make it.

1. Choose the tool, then pick the **Feature** in the tool panel: Boss, Cut, Revolve, Sweep profile, Sweep path, Loft profile, Rib, Thin feature, Wrap, Split or Flange.
2. Click **Check**. The panel lists the problems: open contours with the size of the gap, end points that nearly meet, three or more curves at one point, curves on top of each other, and the wrong number of contours. Or it says no problems were found.
3. Click **Zoom to Next Problem** to go to each problem in turn. Its curves are selected.

Crossing curves are not a problem: they make regions. Construction geometry is ignored.

**Use only fully defined sketches** (Preferences, Sketch) makes features refuse a sketch that is not fully defined. The feature's error names the sketch. It is off until you turn it on.

## When a sketch jumps to another solution

A sketch can often be solved in more than one way: a corner can fold to the other side, or an arc can turn inside out. After you change a dimension, add a relation or drag, the solver may land on another of these. When a corner or an arc flips this way, the status bar says where. Use **Undo** to go back.

To stop it happening again, right click in empty space and choose **Keep This Side**. This undoes the change and locks the corners and arcs that flipped on the side they had before. A later change that would flip a locked item is undone with a message. **Remove Side Locks** in the same menu removes the locks.

## Sketch problem list

The sketch status at the bottom of the window says Under defined, Fully defined or Over defined. It can also say:

* **Dangling** (in the warning colour): a relation or dimension names an item that no longer exists. The rest of the sketch still solves.
* **Invalid geometry**: a line of zero length, a circle or arc of zero radius, or a spline that crosses itself.
* **No solution**: the solver found no answer, although nothing conflicts.

Click the status to open the **Sketch Problems** list. It stays open while you work in the sketch. Click a row to select its items.

* **Zoom to Item** centres the sketch on the row's items.
* **Pick New Item**: for a dangling row, select the item it should name in the sketch, then click this.
* **Delete** deletes the row's relations and dimensions, or the invalid curve.
* **Repair All Dangling** looks for the one item each dangling relation or dimension could name where it already holds, so nothing moves. It asks you about each one.
* Conflicting items are grouped in sets. **Diagnose** steps through the ways out of a set: make one dimension a reference dimension, or delete one relation. It says how far points would move. A duplicate dimension is offered first. **Apply Way Out** makes the change shown.
* Redundant items are listed apart: they are harmless, the sketch still solves.
* **Select Under Defined** selects everything that can still move.

Each change is one undo step.

## Repair Sketch

**Repair Sketch** (under Check Sketch) finds small faults and fixes them when you ask. It helps most with a sketch brought in from a DXF file that does not quite close.

1. Choose the tool and type the **Tolerance**. Gaps and segments shorter than this count as faults. The default is 0.05 mm.
2. Click **Find**. The panel lists gaps between end points, overlapping lines, curves on top of each other, tiny segments, points at the same place, zero length lines, zero radius arcs and circles, and relations or dimensions that name a missing item or the wrong kind of item.
3. Click **Zoom to Next Fault** to go to each fault. Its items are selected.
4. Click **Fix** to repair the fault shown, or **Fix All** to repair them all. A fix joins the ends at their middle, merges overlapping lines into one, removes a tiny segment and joins its ends, or deletes a broken relation or dimension. The message says how far points moved.

Nothing changes until you click Fix or Fix All. Undo puts everything back in one step.

## Relations

Relations hold geometry in place: Horizontal, Vertical, Coincident, Collinear, Parallel, Perpendicular, Tangent, Concentric, Coradial, Equal, Midpoint, Symmetric, Intersection and Fixed.

**Steps**

1. Ctrl click two or more items, including the origin or part edges.
2. The panel lists only the relations that fit. Click one to add it. Before anything is picked, the card says "Relations that fit what you select show here." When something is selected and no relation fits, it says "No relation fits this selection. Select other items."
3. The panel also lists the relations of the selection, each with a delete button. The empty list says "Select an item to see its relations." or "The selection has no relations yet."

**Relations** (the command) lists every relation in the sketch. Filter by All, Over defining or not solved, or Model references. Select a row to highlight its items. Delete and Delete All remove relations.

**Tips**

1. Many relations are added for you when a click lands on a snap.
2. Relation tags show beside the geometry. Hover a tag for its name. Turn tags off with View, Hide or Show, Sketch Relations. Right click a tag and choose **Explain** to read in the status bar what the relation holds and which items it links, for example "Keeps line e3 and line e7 pointing the same way."


**Relation groups.** Parallel, Equal, Collinear and Coradial can hold many items at once. Adding one of these to items when one of them already has that relation joins the existing group, so the sketch keeps one relation instead of a chain of pairs. A group of three or more items shows its tag at every member with a number, such as the first and second parallel group.

**Equal Length of lines and arcs.** Equal on a mix of lines and arcs makes their lengths equal (the arc length along the curve).

**Ellipses and splines.** An ellipse or partial ellipse takes Tangent (to a line, circle, arc or another ellipse), Concentric (with circles, arcs, ellipses or a point), Equal (the same axes, between ellipses) and Midpoint (a point halfway along a partial ellipse, as far from both ends). A spline takes Tangent to a line, circle, arc or ellipse at one of its ends: the end that touches the other curve, or else the nearer end. The end's handle then points along the other curve.

**Negative sizes and angles to an axis.** Type a negative value for a horizontal or vertical distance to put the second item on the other side, at the size typed; zero lines the two up. Right click a line and choose **Angle to Horizontal** or **Angle to Vertical** to dimension its angle to a construction line through its first end.

**Symmetric angles.** Dimension a line and a centerline that cross. Put the text on the line's side to get the half angle, the line's angle to the centerline. Put the text across the centerline to get the full angle: the angle between the line and its mirror image, twice the half angle. A third leader shows where the mirror image lies.

**Limits.** Right click a driving dimension and use **Limit** to make it a **Minimum** or a **Maximum** instead of an **Exact Value**. The size is then free while it stays on the right side of the value, and held at the value when a drag or another change would pass it. **Point on Segment** (a point and a line) keeps the point on the line between its two ends, not on the line carried on past them.

**Spline handles.** Select a spline, or one of its points, to see a dashed tangent handle at each through point. Drag the handle's end to change the tangent direction and how far it reaches. Right click a through point or a handle end:

* **Pin Handle** fixes the handle where it is, so it stays while other points move. A pinned handle shows a filled square.
* **Reset Handle** removes the pin.
* **Add Handle Line** adds a construction line along the handle. Dimension its angle and length like any line, or relate it, for example Parallel to a line.

**Relax Spline.** Right click a spline and choose **Relax Spline** to smooth it: every inner handle becomes the even handle a new spline through the same points would have. The points, the two end handles and pinned handles stay.

**Spline Length.** Right click a spline and choose **Spline Length** to dimension its length. The dimension drives the spline: type a new length and the points and handles that are free move to fit it. A Path Length on a chain can include splines too.

**Spline edit tools** (in the spline dropdown):

* **Insert Spline Point**: click a spline to add a through point there. The curve keeps its shape as closely as it can until you drag the new point.
* **Fit Spline**: select a connected open chain of lines, arcs and splines (or click them with the tool), type the **Tolerance**, and click **Fit**. One spline replaces the chain, no further than the tolerance from it. Tick **Keep originals as construction** to keep the old curves as construction geometry instead of removing them. The spline uses the chain's two end points, so what was joined to them stays joined.
* **Simplify Spline**: click a spline, type the **Tolerance** and click **Preview**. The panel says how many points are left and the preview shows the new curve. Click **Apply** to use it.


## Sketch status colours

1. Blue: under defined. It can still move.
2. Black (white in the dark theme): fully defined.
3. Red: over defined or cannot be solved.
4. Grey: reference dimensions.

The status bar shows Under defined (with the degrees of freedom left), Fully defined or Over defined. Drag under defined geometry to see how it can move.

## Snapping and part geometry

The cursor snaps to end points, the origin, centres, midpoints, quadrants, crossings and curves. Midpoint, quadrant, on curve and crossing snaps work on lines, circles and arcs, not on splines and ellipses. Centres of sketch circles and arcs always snap; part circle centres show when you hover the edge. A small symbol shows the snap kind. Dotted guides show when the cursor lines up with a point.

1. Hover a circle or arc to show its centre, then snap to it.
2. Temporary guides: while drawing, rest the cursor on a sketch point for a moment (a ring marks it), then rest it on a second point. A dashed guide joins them, and its ends, middle, thirds and quarters snap (labelled Guide). These snaps add no relations. Guides go when the tool ends.
3. Part vertices, edges and round edge centres seen through the sketch plane are snap targets too. Snapping to them adds a relation to a fixed construction copy.
4. If the part changes later, the sketch warns that copies no longer match. Click Update to move them. They never move on their own.
5. Hold Ctrl while moving to snap to nothing for that move.
   When the cursor snaps onto a line, a faint dashed extension of the line shows: a point placed on the line beyond its ends still lies on it.
6. **Snap Options** (F3) turns snapping, snap to model geometry and automatic relations on or off. Preferences, Sketch has the same switches.
7. Preferences, Sketch also has a switch for each kind of automatic relation: Horizontal, Vertical, Parallel, Perpendicular, Tangent, Equal, Midpoint and Coincident. Turn one off and drawing no longer adds that kind; the others still come.
8. While drawing, press **Tab** to skip the automatic relations of the next click: the point still lands on the snap, but nothing ties it there. Press Tab again to keep them. Joins that are part of the shape, such as the corners of a rectangle, always stay.
9. Relations added automatically while drawing are weak, and their tags are dotted. If you later add a relation or dimension that conflicts with a weak relation, the weak one is removed instead of over defining the sketch, and the status bar says which. Right click a weak relation's tag and choose **Keep Relation** to make it an ordinary relation that stays.
10. Once the cursor has snapped to a point, centre or midpoint, the snap holds for a short way as the mouse drifts, so the click lands where the symbol was shown.
11. The grid is hidden by default. Turn on Show the grid in Preferences, Sketch to see it.

## Crossing curves and regions

Curves that cross are allowed. They split the sketch into closed regions. With no regions picked, a feature uses every outline with its holes. In a feature panel, the Selected Regions group lets you use only some regions. See [Boss and cut](boss-and-cut.md).

Open ends, branches and duplicate curves are errors when no regions are picked. Two lines that partly overlap give "Two lines overlap. Trim or delete one of them." Other curves that overlap give "Check for tiny or overlapping curves in the sketch."

## Sketch Picture

**Sketch Picture** puts an image in the sketch to trace over.

**Steps**

1. Run the command and click Insert Picture. Pick a PNG, JPEG or BMP file.
2. Drag the picture to move it. Drag a corner to resize it.
3. Type a colour in **See-through colour**, such as #FFFFFF for a white background, to show that colour clear; **Colour tolerance** also clears colours close to it. A picture's own transparent areas (a PNG with alpha) always show clear.
4. To scale it, tick Enable scale tool. Drag the two handles onto two known points and type the true length in Scale line length.
5. To turn part of the picture into sketch lines, press **Trace Colour Region** and click a shape: every touching pixel of about that colour is traced. Or press **Trace Box** and click two corners of a box round the shape: the pixels in the box that differ from the colour at its first corner (the background) are traced. **Trace colour tolerance** sets how close a colour must be. Each outline becomes a closed loop of lines you can edit, in one undo step. Escape drops a trace you started. Large images are traced at up to 400 pixels on the longer side, so fine detail is smoothed.

**Options**

Origin X, Origin Y, Angle, Width, Height, Lock aspect ratio, Flip horizontally, Flip vertically, Transparency (%) and Delete Picture.

The image is saved inside the part file. It has no snaps.

## Text

**Text** adds text to the open sketch. It can be extruded, cut or wrapped like any closed profile.

**Steps**

1. Open a sketch, then run Text. A dialog opens.
2. Type the text and choose a font, height, Bold and Italic.
3. Choose Along: Straight From a Point (with X, Y and Angle), or a sketch line, arc, circle or spline. On a circle the letters stand outward and Centre puts the text on top. **Start Offset** moves the text along the curve by that many mm.
4. Click OK. The text shows in the 3D view after Exit Sketch.
5. To edit the letter shapes themselves, right click empty sketch space and choose **Explode Text**. Every text item of the sketch becomes plain lines, arcs and splines along the letter outlines, joined where they meet and not fixed, so you can drag, trim and dimension them. The text items go. It is one undo step.
6. To style single characters, select them in the Text box of the Text dialog, then click **Bold** or **Italic** beside **Selected characters** to switch that style for them, or set an angle and click **Turn** to turn each of them by it. **Clear Styles** removes the character styles of that text. Styles stay with the character positions, so retype the styles after adding characters before them.

**Options**

Alignment (Left, Centre, Right, Full), Text Box Width, Width Factor, Spacing, Rotate Each Character, Flip Horizontal, Flip Vertical and Delete Text.

**Common errors**

1. "Open a sketch first, then add text to it."
2. A font that is not installed gives an error naming it. Choose an installed font.

## Exit Sketch

**Exit Sketch** saves the sketch and goes back to the 3D view.

1. Click Exit Sketch, or OK in the confirmation corner, to keep your changes.
2. Click the red X in the confirmation corner to discard them. FDCAD asks first when there are changes. The view goes back to where it was.
3. If you started the sketch from a feature command, the feature panel opens next.

## Merge

Pick two points (ends, centres or free points) and choose **Merge** in the relations list, the context bar or the right click menu. The two points become one point: every curve, relation and dimension of the second point now uses the first. Relations or dimensions that would join the point to itself are removed. This differs from **Coincident**, which keeps two points that sit together. Merge is not offered for the two ends of one curve. Undo brings the two points back.

## Turning a relation or dimension off

Right click a relation tag or a dimension and choose **Turn Off** to try the sketch without it. It stays in the sketch, drawn greyed and dashed (a dimension shows "(off)"), but has no effect. Choose **Turn On** to bring it back. A configuration can keep a relation or dimension off while others keep it on: its path in the configuration table is the sketch's id with `r<number>:off` (relations, counting from 0) or `d<number>:off` (dimensions), for example `f5.d3:off`.

## Round All Corners

Select the lines of a profile (for example with Select Chain; the sketch's right click menu offers Select Chain for selected items even when you open it with Shift+F10 or away from the items), right click and choose **Round All Corners**. Type the **Radius**; every corner where two of the lines meet gets a sketch fillet. The first fillet has the radius dimension and the others are Equal to it, so changing that one dimension changes them all. To give a corner its own size, type it in that corner's **Own radius**; it gets its own dimension. Corners whose lines are too short for the radius are left as they are and named in the status bar. Undo removes them all at once.

## Airfoil

Right click in empty sketch space and choose **Airfoil**. Type a four digit code (such as 0012 or 2412) or a five digit code (such as 23012), or **Load File** to use a text file with x and y columns. Set the **Chord** (the length from nose to tail), the **Angle** (nose up for a positive angle) and the **Trailing edge** thickness (0 for a sharp edge). **Close the trailing edge** joins the tail with a line, or a shared point when it is sharp. The nose sits at the sketch origin. The shape is one smooth spline through 17 points, closer together at the nose, so it stays easy to edit; drag its points or add dimensions like any spline.

## Pierce

To start a sweep profile exactly on its path, or a spring profile on a helix, draw a point in the profile sketch, right click it and choose **Pierce**. Pick the curve feature or the other sketch that crosses this sketch's plane. After you exit the sketch, the point sits where that curve passes through the plane, and it moves there again whenever the curve changes. The point is held by a Fixed relation while pierced; draw the rest of the profile around it. **Remove Pierce** lets it go. If the curve no longer crosses the plane, the sketch warns and the point stays where it was.

## Sketches on part faces

A sketch drawn on a part face never splits that face: a closed sketch is drawn over the part for show only and cannot be picked, so clicking the face still picks the whole face. A sketch's regions take clicks only while a feature's Selected Regions box is waiting for picks.

## Construction geometry in the part

A closed sketch shows only its normal curves in the part. To keep its construction lines and points visible after you close it, tick **Show Construction in Part**: right click the sketch in the feature tree, or run the Sketch command while the sketch is open. Each sketch has its own tick; the tree tick is one undo step.

With the tick on:

1. The sketch's construction lines, arcs and free construction points are drawn in the 3D view.
2. Later sketches can copy them with Convert Entities: while the tool is active, click the sketch in the feature tree, or its dotted outline in the new sketch.
3. Its construction points are offered as picks for Up to Vertex and for a start at a vertex, like its normal points.

## Cut Away in Front

When a sketch lies inside the part, the part's edges in front of the sketch plane get in the way. Right click in empty sketch space and tick **Cut Away in Front** (or give the command a key in the shortcut editor): the part's edges, outline and snap points in front of the plane are left out while you sketch, and only what lies on and behind the plane shows. It is display only; the part does not change. Each sketch remembers its own setting.

## Derived sketches

Right click a sketch in the tree and choose **Derived Sketch**, then pick a plane. The new sketch is a linked copy: it has the same shape as the original and follows it when the original changes, but it cannot be edited on its own. Right click it and choose **Edit Placement** to move it (X, Y) or turn it (Angle) in its plane, or **Break Link** to make it an ordinary sketch you can edit, keeping its current shape.

## Replacing a curve

Draw the new curve, then select the old curve first and the new curve second. Right click and choose **Replace First with Second**, or **Replace, Keep First as Construction** to keep the old curve as a construction guide. The new curve takes the old one's place: relations and dimensions move to it when they still make sense (a Horizontal relation does not fit an arc, a radius does not fit a line), and the old curve's end points hand their relations to the nearest points of the new one. Features built from the old curve's edges keep working. The status bar names anything that could not move.

## Segment

Right click one line or arc and choose **Segment** to split it into a number of equal pieces. Line pieces get Equal relations, so they stay equal when the line's length changes. **Equally Spaced Points** leaves the curve whole and puts points evenly along it: a construction copy on top of it is split, and the points between its pieces are the ones you use. To change the count, undo and segment again.

## Selecting a region

With no tool active, click inside a closed shape to select every curve around it; the shape is shaded. If it does not shade, its outline has a gap somewhere, so it is not closed. Drag one of its curves to move the whole shape; the relations hold. The same works for anything you pick with a box or Ctrl: drag any picked item, also a point or a circle, and every picked item moves with it. A click in empty space while something is selected clears the selection first, so click again to pick the region. Hold Ctrl and choose Select Chain to add another chain to the selection.

## Grid, steps and the snap filter

- **Hide Construction Geometry** (a Sketch command; give it a key in the shortcut editor) hides the open sketch's construction lines and curves, so a busy layout gets out of the way. Hidden curves cannot be picked; points and snaps still work. Run it again to show them. Nothing in the sketch changes.
- **Recent Sketch Tools** (right click in empty sketch space, once you have used two tools) lists the last eight sketch tools, newest first. Part commands are not in it, so they do not push your sketch tools out.
- **Show Formulas on Dimensions** (right click in empty sketch space) shows a dimension's formula beside its value, such as `width/2 = 20.00`, in every sketch until you turn it off. Without it, a dimension driven by a formula shows `= 20.00`.
- **Grid Spacing** (right click in empty sketch space) sets this part's major grid spacing and the minor lines between; 0 goes back to the automatic grid.
- **Snap to grid** (Preferences, Sketch): Off, While the grid shows, or Always. A click that does not snap to the sketch lands on the nearest grid point.
- **Grid** (Preferences, Sketch): Square, or Polar for rings round the sketch origin at the grid spacing and spokes every **Polar grid angle** degrees. With Snap to grid on, a click on a polar grid lands where the nearest ring meets the nearest spoke, which suits bolt circles and round parts.
- Hold **Alt** while drawing to step the length and the angle from your last click, by the Length step and Angle step in Preferences, Sketch.
- While a tool is active, right click and choose **Snap Next Click To** (End Point, Midpoint, Centre or Nearest) to make only that kind of snap count for the next click.

## Dimensioning a selection

Select one or two sketch items with no tool active and move the cursor near them: a faint dimension follows the cursor. Click to place it; the value box opens so you can type the size. Where you place it decides which dimension you get, for example the distance or the angle between two lines. Click further away (more than about 40 pixels from the items) to clear the selection instead.

## Insert SVG

**Insert SVG** (Sketch tab, with Insert DXF) reads a vector drawing such as a logo into the open sketch. It uses the same options as Insert DXF: scale, base point, angle, and a preview that follows the cursor until you click. Lines and rectangles become sketch lines, circles become circles, and curves (paths, ellipses, arcs) become smooth splines. Sizes come from the file's width and height when they are given in mm, cm, inches or points; otherwise 96 drawing units are one inch. Text in the file is not read: convert text to paths in your drawing program first.

## Code Tag

Right click in empty sketch space and choose **Code Tag** to draw a QR code of a text, for a printed tag with a part number, a web address or a note.

1. Type the **Text** (up to 213 letters).
2. Set the **Module size**, the side of one square of the code. The window shows how large the tag will be. 0.8 to 1 mm modules scan well from a 0.4 mm nozzle print.
3. Click OK. The code is drawn with its bottom left corner at the sketch origin, as one region.

Extrude the region a layer or two up from a plate, or cut it in, in a colour that stands out. Leave a light border of four modules round the code. Where two squares of the code touch only at a corner, the outline leaves a hair of a gap, so the sketch stays one clean region; it does not stop the code from scanning.

## Gear

Right click in empty sketch space and choose **Gear**. Pick the **Kind**:

- **Spur gear**: set the size by **Module** (mm) or **Diametral pitch** (teeth per inch), the number of **Teeth**, the **Pressure angle** (usually 20 degrees) and an optional **Profile shift**. **Rounded roots** rounds the bottom of each tooth space. Leave **Root fillet radius** at Automatic for a rounding of about 0.38 times the module, or type a radius for a true round root that meets the root circle and the tooth flank smoothly. A radius too large for the gap between teeth is refused.
- **Internal gear**: the outline of the toothed hole of a ring gear. Draw the ring's outer edge yourself.
- **Chain sprocket**: pick the **Chain** size and the number of teeth.
- **Timing pulley**: pick the **Belt** (GT2, GT3, HTD 3M, HTD 5M, MXL, XL, T2.5 or T5) and the number of teeth. The outside diameter is the pitch diameter less the belt's pitch line offset. Curved tooth belts get round bottomed grooves, trapezoid belts straight flanked ones. The grooves carry about 0.1 mm of clearance for printing. Add flanges as separate sketches if the belt should not run off.

The outline is centred on the sketch origin. Extrude it, add a bore, twist it for a helical look, or pattern it as usual. Two gears mesh when they share the module and pressure angle and their centres are (teeth 1 + teeth 2) times the module, divided by 2, apart.

## Ratio, difference, equal angle and equal distance

Select items, right click and open **Add Relation**:

- **Length Ratio**: two lines or arcs. Type how many times longer the first is than the second; it starts at today's ratio.
- **Length Difference**: two lines or arcs. Type how much longer the first is than the second, in mm (negative when it is shorter).
- **Equal Angle**: four lines. The angle between the first two equals the angle between the last two.
- **Equal Distance**: a point and two lines. The point stays the same distance from both lines.

Arcs use their length along the curve.

## More circles

The **Circle** list on the Sketch tab has two more tools:

- **2 Point Circle**: click both ends of a diameter.
- **Tangent Circle**: click three lines, arcs or circles and the circle touches all three (for example the circle inside a triangle). Or click two of them, then click empty space where the circle should sit: it touches the two and gets a radius dimension you can type a new value into. Click near where the circle should go, since several circles can touch the same curves.

## Blend Curve

**Blend Curve** (in the Spline list) joins two curves with a smooth spline. Click a line, arc or spline near the end you want to join, then the other curve near its end. The spline starts and ends on those end points and leaves each one in the direction the curve was going, so the join is smooth. Drag the spline's two handles to change how far each end reaches before it turns (its weight). When a line moves, the blend's handle stays on it, so the join stays smooth.

## Detach from the model

Geometry you made with Convert Entities, projection or by snapping to the part follows the part's edges. To make it ordinary sketch geometry, select it, right click and choose **Detach from Model**. It keeps its shape and its dimensions, but it is no longer held in place and no longer changes when the part does, so the sketch stops depending on those edges.

## Turned Outline

**Turned Outline** (with Intersection Curves and Silhouette) shows the part as it would look spun about the sketch's X axis: at each point along the axis, how far the part reaches from it. Put the sketch on a plane that contains the turning axis, with the sketch's X axis along it, then press **Add Curves**. You get the half profile above the axis, closed along the axis, as fixed lines: ready for a lathe drawing or for a Revolve. Steps between diameters come out within about a quarter of a percent of the part's length.

## Keeping trimmed pieces

Trim has a tick box, **Keep Trimmed Pieces as Construction**. With it on, the parts a trim takes away stay in the sketch as construction lines and arcs, so you keep the reference shape (and dimensions to it still have something to measure). The trim and the kept pieces are one undo step.

## Modify Sketch

To change a whole sketch at once, right click empty space and choose **Modify Sketch**. Type a **Scale** (lengths and their dimensions grow by it), a **Turn** angle, a **Flip** (left to right, top to bottom or both) and a **Move X** and **Move Y**. Scale, turn and flip work about the sketch origin, then the move is applied. Geometry held to the part (copied edges, the origin) stays where it is. It is one undo step.

## Add Relations to existing geometry

Geometry from a DXF or SVG, or drawn with relations off, is often nearly right but not held. Right click empty space and choose **Add Relations**. FDCAD lists the relations that fit within 1 degree and 0.05 mm and are not there yet: lines that are nearly horizontal or vertical, nearly parallel or square to each other, ends that nearly meet, lines leaving an arc's end along its tangent, and circles or arcs of nearly the same size. Everything starts ticked; untick what you do not want and press OK. They are added in one undo step.

## Text that shows a value

Sketch text can include a value of the part. Type its name in braces: `{width}` for a global variable, `{d3}` or the dimension's own name for a dimension in the same sketch, or the name of a custom property such as `{PartNumber}`. Lengths show in the part's units and angles in degrees. Add a format after a colon for a fixed number of decimals: `{width:.1f}`. The text changes whenever the value does, so an engraved size label stays right. A name FDCAD does not know stays as typed, braces and all.

**Copy numbers.** Type `{copy}` in a text to number the copies of a pattern. Extrude or cut the text, then pattern that feature (not with Geometry pattern on): each copy builds the text again and shows its own number, 1 for the original. Copies count along the first direction, then row by row. Add a format for leading zeros: `{copy:03d}` shows 001, 002 and so on. Outside a pattern `{copy}` shows 1.

## Sketch square to an edge

To draw a profile for a sweep along an edge, right click the edge near the end where the profile should go and choose **Sketch Square to Edge**. FDCAD adds a reference plane square to the edge at that end (the Normal to Curve plane method) and opens a sketch on it. The plane stays in the tree, so the sketch follows the edge if the part changes.

## Spline analysis

When you tick **Curvature combs** for a spline, three more aids appear with the combs:

- the **control polygon** (dashed), the frame of points that shapes each piece of the spline;
- small squares at the **inflection points**, where the bend changes from one side to the other;
- a circle at the **tightest point**, labelled with its radius (R).

They are for looking only: they are not part of the sketch and are not saved.

## Dimension tolerance and display

Right click a dimension and choose **Display** to change how its label reads, without changing its value:

- **Tolerance**: **Plus and minus** (10.00 +0.10/-0.05), **Limits** (the largest and smallest size, 10.10/9.95) or **Plus or minus** (10.00 ±0.05), with the **Plus** and **Minus** values.
- **Decimals**: how many decimal places the label shows.
- **Show as**: for a radius or diameter dimension, show it as the other one.
- **Hide extension lines** and **Hide dimension line**: for a distance, leave out the lines from the measured points, or the line with the text, so a crowded drawing reads more easily.

**Mean Dimensions**: when a dimension has an uneven tolerance (such as +0.2/-0), right click in empty sketch space and choose **Mean Dimensions**. Every such dimension moves to the middle of its range (10.10 +0.10/-0.10), so a printed or machined part aims at the middle. The largest and smallest sizes stay the same. Choose **Typed Dimensions** to put the typed values back.

**Step Through Values**: right click a driving dimension to check that the sketch moves as you mean. Type **From**, **To** and how many **Steps**; the sketch is solved at each value in turn, about two a second, with the value in the status bar. Then it goes back exactly as it was. Nothing is kept and nothing goes on the undo list. The status bar says if any value did not solve. Let it finish before you edit.

To see which angle an angle dimension measures, drag its label to the other side; that already picks the inner angle or the one beside it.

## Points from File

Right click in empty sketch space and choose **Points from File** to read a text file of X and Y values, one pair per line, split by commas, spaces, tabs or semicolons. Each pair becomes a plain sketch point in the part's units, which you can dimension, pattern or draw through. A third number on a line (Z) is ignored, and lines that are not two numbers, such as a header, are skipped; the status bar says how many. One undo removes the points.

## Sketch colours

Right click a sketch in the feature tree and choose **Sketch Colour** to draw its lines in the 3D view in a colour of your own, so a layout sketch or a traced picture is easy to tell apart from the others. **Usual Sketch Colour** puts it back. The colour is saved with the part and is one undo step. While you edit the sketch, the usual status colours show instead.

## Shapes

Right click in empty sketch space and choose **Shapes** for a ready made outline centred on the sketch origin:

- **Triangle by three sides**, **by two sides and the angle between**, or **by a side and two angles** (the angles at its two ends). The first side lies level.
- **Trapezoid**: bottom width, top width and height, the same slope on both sides. A top width of 0 gives a triangle.
- **Keyhole**: a round hole with a slot running down from it, by the hole diameter, slot width and how far the slot reaches below the hole's centre.
- **Constant width triangle**: three arcs that measure the same width in every direction.
- **Egg** by width and height, blunter at the bottom.
- **Superellipse** by width, height and squareness: 2 is an ellipse, larger values are squarer.
- Standard sections for brackets and adapters: **Angle (L) section**, **Channel (C) section**, **I beam**, **Rectangular tube** and **Round tube** (an outside and an inside outline), by their sizes, so you can type a catalogue size; and the **DIN rail** (35 mm top hat, 7.5 mm high) by its sheet thickness. Rolled corner radii are not drawn; add Sketch Fillet where you need them.

The outline is joined curves you can dimension, move or edit like any other. One undo removes it.

## Slot Along Curves

Pick one or more lines and arcs, right click and choose **Slot Along Curves**, then type the width. FDCAD draws a slot of that width round them: the two sides follow the curves, the ends are round, and a chain of curves gives one slot whose sides meet at each join. The picked curves become construction geometry, the centre line of the slot. One width dimension across the slot sets both sides; change it to change the width. One undo removes the slot. A closed loop has no ends, so use Offset with Both directions instead. Splines and ellipses cannot be followed; replace them with lines and arcs first.

## Shading regions and hiding points

Right click an empty spot in a sketch for two switches that last for every sketch until FDCAD closes. **Shade Closed Regions** fills every closed area faintly, so a gap in an outline shows at once: an area with a gap is not shaded. **Show Sketch Points** hides every point when you turn it off, except the ones you pick or hover, so a busy sketch is easier to read.

## Merge Into Sketch

Right click a sketch in the feature tree and choose **Merge Into Sketch...** to move all its curves, relations, dimensions, pictures and text into another sketch on the same plane. The merged sketch is then deleted. A sketch that a feature uses cannot be merged away: merge the other one into it instead. One undo brings both back.

## Layers

Layers keep sets of curves apart, for example guide lines and the outline. Pick curves, right click and open **Layers**, then **New Layer...**: type a name, choose a colour and a line style (solid or dashed); the picked curves go on it. **Put on** a layer moves picked curves there and **Take Off Layer** takes them off. With nothing picked, the Layers menu has a **Show** tick for each layer: a hidden layer's curves are not drawn and cannot be picked. **Pick** a layer to pick all its curves at once, for example to move them together, and tick **Lock** to stop its curves from being dragged. Layers only change how curves look: the sketch is solved as one, and curves on a hidden layer still count in the shape you extrude. Each change is one undo step and the layers are saved with the sketch.

## Shake Sketch and Lock All Points

Right click an empty spot and choose **Shake Sketch** to see what is still free: FDCAD pushes every point that is not held a little, on a copy, and picks the items that moved. Your sketch does not change. Circles and arcs whose size is still free are picked too. **Lock All Points** stops every drag in this sketch, so you can compare; untick it to drag again.

## Sketch blocks

A block is a group of sketch curves saved once and placed as copies, for layout sketches of mechanisms (a link, a slider, a bracket outline).

1. Pick the curves and right click: **Make Block**. They become the block's first copy.
2. Right click a curve of a copy: **Insert Copy of** the block places another copy beside it, picked, so you can move or rotate it with Move or Rotate Entities, or by dragging.
3. To change every copy, edit one copy (drag, dimension, resize), then right click one of its curves: **Update Block from This Copy**. Every other copy is made again in its own place and turn. Relations from other curves to the other copies are lost when they are made again.
4. **Select Block Copy** picks all the curves of one copy. **Explode Block Copy** makes a copy plain geometry that no longer follows the block.
5. Each copy is ordinary sketch geometry, so features use it as usual. Deleting all the curves of a copy removes the copy.

## Drag without solving

Normally a drag keeps every relation and dimension. Three choices change that:

1. **Drag Without Solving** (right click an empty spot): points go straight where you drag them and nothing else moves. When you let go, FDCAD lists how many relations and dimensions no longer hold and asks whether to delete them. Pick No to keep them; the sketch then shows them as conflicts. Untick it to drag as usual. It lasts until the sketch closes.
2. **Detach Segment on Drag** (right click an empty spot): dragging an end point that joins curves breaks the join. The picked curve (or the first one) goes with the point; the others keep their own point where the corner was.
3. Preferences, Sketch, **Dragging changes dimensions**: dragging geometry with driving dimensions gives those dimensions the sizes the drag leaves, instead of holding them. Off by default.

## Show in Sketch

Open end points, where only one curve ends, get an orange ring while you draw, so a gap shows before a feature fails on it. Where two curves cross away from a shared end there is an orange X, and where three or more curves meet an orange square, so a profile that crosses itself or forks shows too. Right click an empty spot and open **Show in Sketch** to choose what the sketch shows, for every sketch until FDCAD closes: **Open Ends**, **Crossings and Forks**, **Driving Dimensions**, **Reference Dimensions**, the tags of each kind of relation in the sketch, and Normal or Large tags, apart from the dimension text size. **Thin Lines**, **Normal Lines**, **Bold Lines** and **Extra Bold Lines** set how thick sketch lines and point marks are drawn, for very high resolution screens or projectors. Lines already follow the screen's display scale.

## Swap Axis Relations

Pick the lines of a shape drawn square to the axes, such as a rectangle, right click and choose **Swap Axis Relations**. Their Horizontal and Vertical relations become Parallel and Perpendicular relations to the first picked line, so the shape stays square but can turn. Drag it, or add an angle dimension to set the turn. Relations you switched off stay as they are. One undo puts the old relations back.

## Convex Hull

Pick two or more curves or points, right click and choose **Convex Hull**. FDCAD adds the outline you would get by stretching a rubber band around them. Circles and arcs keep their exact shape: the outline runs along them and the lines touching two of them get tangent relations. Ellipses and splines are followed by short lines. The picked curves stay; delete the ones inside if you do not need them. One undo removes the outline.

## Parabola and Jog Line

**Parabola** (in the Spline list): click the focus, then the apex (the tip of the curve), then where the curve starts and ends. The ends land on the parabola level with your clicks. The curve is an exact parabola, kept as a spline you can edit.

**Jog Line** (in the Line list): click a line where the step should go, then click to one side. The line breaks there: the rest of it moves over by that much, joined by a short step line. The two pieces stay parallel, and you can dimension the step's depth and width.

