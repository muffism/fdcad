# Curves

Curve tools make 3D curves that later features can follow: a helix for a spring or thread, a sketch projected onto a curved face, or several pieces joined into one sweep path. Pipe and Array Along Curve use a curve to build solids. Contour Curves and Curvature Graph help you check a shape.

Where to find it: Features tab, Reference and Curves group, the Curves button. Helix and Spiral, Projected Curve, Composite Curve, Contour Curves, Pipe and Array Along Curve share one dropdown button, which shows the tool you used last. The Insert menu has a Curves submenu with the same commands. Curvature Graph is on the Evaluate tab, Curves group. None has a default key.

Curve features show in the feature tree like any other feature. Later features pick them from a list, like a sketch. Curves cannot be clicked in the 3D view yet. Curve panels have no live preview: the curve shows after OK.

## Helix and Spiral

**Helix and Spiral** makes a helix, or a flat spiral, from a sketch with one circle. The circle's centre, plane and diameter place the curve.

**Closed Ends** (constant pitch helix): for a spring, the pitch is the **End Pitch** (about the wire's diameter) where the helix starts and ends, and grows to the pitch over the first and last turn, so the end coils sit on the next ones. For ground flat ends, tick **Ground ends** in the Swept Boss's options: the wire is cut flat at both ends of the helix, square to its axis, so the spring stands square.

1. Draw a sketch with exactly one circle. See [Sketching](sketching.md).
2. Click **Helix and Spiral** and choose the sketch.
3. Choose how it is **Defined By**: Pitch and Turns, Height and Turns, Height and Pitch, or Spiral.
4. Type the two values that show.
5. Click OK.

Options in the property panel:

* **Pitch**: Constant Pitch or Variable Pitch. Variable pitch shows a table of rows. Each row has the turn where it applies, a pitch and a diameter. Use **Add Row** and **Remove Row**. The height of each row is shown beside it. The first row is always at turn 0, and its diameter is used instead of the sketch circle's.
* **Reverse**: grow the helix the other way, or wind a spiral inward.
* **Clockwise**: wind clockwise, seen from the side the helix grows toward.
* **Start angle**: where the curve starts, measured from the sketch X direction.
* **Taper angle** and **Taper Outward**: widen or narrow the helix as it rises. Constant pitch helices only, not spirals, and less than 89 degrees.

Tips: a helix can have at most 1000 turns. A constant pitch helix is exact at any count; a spiral or a variable pitch helix is built through points and warns that it is less exact past about 62 turns. Use the helix as the path of a sweep or a pipe.

Common errors:

* "The sketch must hold exactly one circle." Delete the extra curves or make them construction geometry.
* "The spiral reaches its centre." Use fewer turns or a smaller pitch.
* "Taper works with a constant pitch helix only." Set the taper to 0 or choose Constant Pitch.

A sweep along a helix with a round profile wider than the pitch fails with a message, because the coils would run into each other. Use a thinner profile or a larger pitch.

## Projected Curve

**Projected Curve** puts a sketch onto faces, or finds the 3D curve where two sketches meet.

Sketch on Faces:

1. Click **Projected Curve** and choose **Sketch on Faces**.
2. Choose the sketch.
3. Click the faces to project onto in the view.
4. Optional: tick the direction box and click a plane, flat face or straight edge. Without it, the sketch normal is used. Only pieces in front of the sketch plane are kept; tick **Reverse** to project the other way, or **Both** to keep pieces on both sides.
5. Click OK.

Sketch on Sketch:

1. Draw two sketches on planes that cross.
2. Choose **Sketch on Sketch**, then the sketch and the **Second sketch**.
3. Click OK. The curve is where the two sketches meet when each is pulled along its own normal.

Options: **Reverse** projects to the other side of the sketch. **Both Directions** projects to both sides.

Common errors:

* "The sketch does not land on the picked faces." Pick other faces, or turn on Reverse or Both Directions.
* "The two sketches are on parallel planes." Put them on crossing planes.

## Parting Line

**Parting Line** finds the edges where the part's faces turn from positive to negative draft for a pull direction, and keeps them as a curve, for example to plan a mould split.

**Steps**

1. Right click a flat face square to the pull in the view and choose Parting Line, or pick a flat face or straight edge in the Pull direction list.
2. Tick Reverse to pull the other way.
3. Click OK.

Faces with no draft count with the positive side, so on a box without draft the line runs round the bottom of the walls. When the edges do not close, a warning gives the number of free ends and the gaps. Faces with both kinds of draft are named: the line crosses them and is not found there; add draft to them first, or tick **Split faces at the line**: cylinders, cones and spheres with both kinds of draft are split along their outline, so the line runs across them, and the part keeps the split faces.

## Composite Curve

**Composite Curve** joins sketch curves, curve features and model edges into one curve, for example to use as a sweep path.

1. Click **Composite Curve**.
2. In Items to Join, choose sketches and curves from the list, and click edges in the view.
3. Click OK.

Tip: the pieces must join end to end, in any order. Construction geometry is left out.

Common error: the pieces make more than one curve. Close the gaps so every piece touches the next.

## Contour Curves

**Contour Curves** cuts the part with parallel planes at a set spacing and keeps the section loops as curves.

1. Click **Contour Curves**.
2. Choose a plane, or click a flat face or straight edge, for the direction. The planes are square to it.
3. Type the **Spacing** and click OK.

Tip: at most 500 sections are made. The contours can be used by later sketches and features.

Common errors: "No section fits inside the part." Use a smaller spacing. "More than 500 sections." Use a larger spacing.

## Pipe

**Pipe** makes a round solid, or a hollow tube, along a curve or a chain of edges.

1. Click **Pipe**.
2. Choose a sketch or curve for the path, or click path edges in the view. The pieces must join end to end.
3. Type the outer diameter.
4. Optional: tick **Hollow** and type the inner diameter.
5. Click OK.

Options:

* **Cap Ends**: close both ends of a hollow pipe with a wall as thick as the pipe wall.
* **Merge result**: join the pipe to the bodies it touches.

Tips: sharp corners in the path get mitred corners, like a welded tube frame. A closed path has no ends, so Cap Ends does nothing there.

Common errors:

* "The pipe intersects itself." Use a smaller diameter or a gentler path.
* "The inner diameter must be smaller than the outer diameter."

## Array Along Curve

**Array Along Curve** copies features or bodies along a curve.

1. Click **Array Along Curve**.
2. Choose the curve: a sketch or curve feature, or pick edges.
3. In Items to Copy, tick features, or click a face of each body to copy.
4. Choose **Spread Over Curve** and type the number of instances, or **Set Spacing** and type the spacing.
5. Click OK.

Options:

* **Start offset** and **End offset**: the copies start this far along the curve and stop this far before its end. The seed stays where it is.
* **Orient to Curve**: each copy turns with the curve. Untick it to only move the copies.
* **Spacing law**: Even (the usual), Growing (each gap is the **Growth ratio** times the one before), Random (each copy moves by up to **Random move** percent of the gap; the same **Random seed** gives the same layout), or List of fractions (one number per copy, such as `0.1, 0.5, 1`: each copy sits at that share of the run). The law measures from the start offset. Copies that would run past the end of an open curve give an error.
* **Square to face**: tick it and click the face the curve runs on, such as a round or curved face. Each copy keeps that face's normal as its up direction and the curve as its forward direction, so copies stand square on the face all the way round.
* **Instances to skip**: their numbers, separated by commas. The original is 1 and cannot be skipped.
* **Merge result**: copied bodies join the original. Otherwise they stay separate bodies.

Tips: the count includes the original. At most 1000 instances.

Common error: with Set Spacing, the message says the copies need more length than the curve has. Reduce the count or the spacing.

## Curvature Graph

**Curvature Graph** shows curvature combs on edges and curves. It is for checking only and changes nothing in the part, so it is not an undo step.

1. Select edges in the view. With nothing selected, the graph shows on every curve feature.
2. On the Evaluate tab, click **Curvature Graph**. A small window opens.
3. Drag **Scale** to make the teeth longer or shorter.
4. Drag **Density** to show more or fewer teeth on each edge.
5. Click **Curvature Graph** again to turn it off.

Tips: long teeth mean tight curvature. A sudden jump in tooth length shows where two curves meet without a smooth join.

See also: [Boss and cut](boss-and-cut.md) for sweeps that follow these curves.

## 3D Sketch

A **3D Sketch** (Insert, Curves, or the Reference and Curves dropdown) is a path that does not lie on one plane, for a sweep, pipe or loft. It has two kinds of content, which can be mixed:

1. **Plane Sketches**: draw ordinary 2D sketches, each on the plane you want, then pick one under **Sketch** and press **Add Part**. Its curves are copied into the 3D sketch on that plane. To take a later change to the 2D sketch, remove the part and add it again.
2. **3D Lines**: type points, one "x y z" a line in the part's units, choose **Join by** Lines or Spline, and press **Add 3D Line**.

Touching ends join into one path. The feature's report gives the number of curves and the true length in space. Hide or delete the 2D sketches you copied if you do not need them.

**3D Relations** hold the points of the 3D lines in place. Pick a **Relation**, a **First point** and a **Second point**, then press **Add Relation**:

- **Along X**, **Along Y**, **Along Z**: the segment between the two points runs along that axis.
- **Coincident**: the two points are at one place. Pick a part point as the second point to tie a 3D line to a plane sketch, so paths on different planes join.
- **Fix**: the first point stays where it is now.
- **3D Length**: the straight distance in space between the two points is the **Length**. This is a 3D dimension.

The points move as little as they can to meet every relation, each time the part rebuilds. The report says how many free movements are left; 0 means the 3D lines are fully set. Relations that cannot all hold give an error that says to delete one or change a length. Removing a 3D line or a part removes its relations.

**Common errors**

1. A 3D sketch with no parts and no 3D lines cannot be made. Add one of them.
2. A 3D line needs at least two points, and two points in a row may not be in the same place.
3. 3D relations that conflict cannot be met. Delete a relation or change a 3D length.

## Curve Through Points

**Curve Through Points** (Insert, Curves, or the Reference and Curves dropdown) makes a smooth curve through points in order. Type X, Y and Z for each point in the table, or **Load File** to read a text file with three numbers a line (spaces, commas, tabs or semicolons; other lines are skipped), in the part's units. **Reload** reads the same file again; the points are kept in the part, so it rebuilds without the file. **Frame** places the typed points on a plane or coordinate system. Or click vertices in the view, in order: picked points follow the part when it changes. Tick **Closed** to join the ends smoothly. Sweeps, lofts and pipes can use the curve as a path.

To make a 3D curve from equations, type **X(t)**, **Y(t)** and **Z(t)** (for example `10*cos(t)`, `10*sin(t)` and `2*t` for a coil), the range of t and the number of points, then click **Fill Points**. The table is filled with the points and the curve passes through them. Plain numbers are in the part's unit, and variables and functions work as in any value field. The points stay as they are until you click Fill Points again.

## Transition Spiral

A **Transition Spiral** turns smoothly from a straight into an arc, as track and road pieces do: its bend grows evenly from nothing at the start to the arc's radius at the end.

1. Sketch one line, the straight the spiral starts from. It starts at the line's end point, along the line.
2. Click **Transition Spiral** in the Reference Curves group and pick the sketch.
3. Enter the **Spiral length** and the **End radius**, the radius of the arc that follows, and pick which way it **Turns**.
4. Click OK. Sweep a rail or road profile along the spiral, then carry on with an arc of the end radius.

The spiral may turn at most two right angles: a length up to four times the end radius.

