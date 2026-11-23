# Reference geometry

Reference geometry is construction help for modelling. Planes give you new places to sketch. Axes, points and coordinate systems give later features a direction, a centre or an origin to work from. Reference geometry adds no material.

Where to find it: Features tab, Reference and Curves group, one dropdown button for all four. The Insert menu has a Reference Geometry submenu with the same four commands. They have no default keys.

## How the reference panel works

All four tools share one panel layout.

1. The panel has up to three reference boxes. Click a box, then click a face, edge, vertex, plane or point in the view. You can also choose an earlier plane, axis or point from the list.
2. FDCAD guesses the **Method** from what you pick. You can change it in the Method list.
3. The message line says what is still missing, for example "Pick a plane or flat face for reference 1."
4. The preview shows in the preview colour. When everything is set, the message says "Fully defined. Click OK to add it." OK only works then.
5. To clear a box, use **Clear this reference**.

New features are named Plane 1, Axis 1, Point 1 and Coordinate System 1, and so on. They show in the feature tree. Hide and show them with **Hide or Show** (H). **Hide All Reference Geometry** (Ctrl+H) hides them all.

## Plane

**Plane** adds a reference plane. You can sketch on it like on the default planes.

1. Click **Plane**.
2. Pick the references for the method you want: click faces, edges and vertices in the view, or use a reference box's menu to choose a reference feature, the origin, or a point, line, arc or circle of an earlier sketch (an arc or circle gives its axis).
3. Type any values and click OK.

Methods:

* **Offset distance**: a plane or flat face, and a **Distance**. Tick **Flip side** to place it on the other side.
* **At angle**: a plane or flat face, and a straight edge, sketch line or axis, with an **Angle**. The line must lie in or parallel to the plane.
* **Three points**: three vertices, sketch points or reference points.
* **Normal to curve**: an edge or curve, and optionally a point. The plane is square to the curve. **Set origin on curve** puts the plane's origin on the curve.
* **Mid plane**: two planes or flat faces. When they are parallel the new plane is halfway between them. When they are not, it goes through the line where they meet and halves the angle between them, with the two faces on opposite sides; Flip side takes the other halving plane.
* **Parallel through a point**: a plane or flat face, and a point.

Where a point is asked for, an edge counts as its start point and a round edge or face as its centre.

**Offset by dragging:** hold Ctrl and drag the border of a plane shown in the view. A copy of the plane follows the mouse. When you let go, the Plane panel opens with Offset distance and the dragged distance, rounded. Type another value if you like, then click OK.

Every method has **Flip normal**, which turns the plane over.

**How many** (Offset distance and At angle, new planes only): make several planes at once, each the distance or angle further on, such as three planes 5 mm apart. Each is its own plane; the later ones follow the first, so changing its distance respaces them all. The same box on a new Point along a curve makes several points, spaced by the distance, by the percent, or spread evenly over the curve.

After any method, planes, axes and coordinate systems can be moved further in their own directions: **Extra offset X, Y and Z** (Z is the plane's normal, the axis direction or the frame's Z), **Extra turn about X, Y and Z** (in that order), and **Flip after the extra offset**. Leave them at 0 to keep the method's placement.

Common errors:

* "The three points lie on one line." Pick a point off that line.
* "The axis must lie in or parallel to the plane." Pick another edge.

**Two more plane methods**

1. Project onto a face: pick a point and a face. The plane goes through the point moved onto the face and is normal to the face there. For a sketch point, tick Along Sketch Normal to move it along the sketch normal instead of to the nearest point.
2. Parallel to screen: pick a point. The plane goes through it and faces you. The view direction is kept when you choose the method, so turning the view later does not move the plane. Press Use Current View to take the view again.

## Axis

**Axis** adds a reference axis.

1. Click **Axis**.
2. Pick the references and click OK.

Methods:

* **Along a line or edge**: a straight edge, sketch line or axis.
* **Two planes**: two planes or flat faces. The axis is where they cross.
* **Two points**: two vertices, sketch points or reference points.
* **Cylinder or round edge axis**: a cylinder or cone face, or a round edge.
* **Point and face**: a point and a plane or face. The axis goes through the point, square to the face.

Every method has **Reverse direction**.

Tip: an axis is handy for a Circular Pattern. See [Patterns and bodies](patterns-and-bodies.md).

Common errors: "The two planes are parallel." Pick planes that cross. "The two points are the same." Pick two different points.

## Point

**Point** adds a reference point.

1. Click **Point**.
2. Pick the references, or type values, and click OK.

Methods:

* **Arc centre**: a round edge.
* **Centre of face**: a face.
* **Intersection**: two items that cross, such as two edges, an axis and a plane, or an axis, line or edge and a curved face such as a hole. When they cross more than once, **Crossing number** picks which crossing, counted along the line from its start.
* **Projection**: a point, and a plane, face or edge to project it onto.
* **Along curve**: an edge or curve, and a **Distance** from its start. Tick **Distance as percent** to type a **Percent of length** instead. **Reverse direction** measures from the other end.
* **On a point**: a vertex or sketch point.
* **X, Y and Z values**: type the coordinates. This is the starting method.
* **Centre of mass**: no picks. The point sits at the centre of mass of the bodies built above it in the tree, and moves with them after every change. When the part has typed mass properties with a centre (Mass Properties, **Override**), it uses that centre. Hide or show it like any reference point.

Common errors:

* "The distance is longer than the edge." Enter a smaller value.
* "The two lines do not cross." Pick lines that meet.

## Coordinate System

**Coordinate System** adds an origin with three axes that later features and sketches can pick as a reference.

1. Click **Coordinate System**.
2. Pick or type the origin.
3. Set the directions and click OK.

Methods:

* **Origin and directions**: pick the origin (a vertex, point or round edge centre), or type X, Y and Z. Then pick the X direction and the Z direction. A straight edge or axis points along it, a point points towards it, and a plane or flat face uses its normal. **Reverse X** and **Reverse Z** flip them. An empty direction keeps the model axis; with only Z set, X is the model X axis turned square to Z. A face or plane picked as the origin uses its centre.
* **Rotation angles**: pick or type the origin, then type **Rotation about X**, **Rotation about Y** and **Rotation about Z**. They are applied in that order: X, then Y, then Z.

Tip: all three references are optional in Origin and directions. With nothing picked, the coordinate system matches the model axes at the typed origin.

## Move Part Origin

An imported part can sit far from the origin. Right click **Origin** in the feature tree and choose **Move Part Origin**, then where it goes: the box centre of the bodies, the centre of their volume, the selected vertex or face, or back to the model origin. The origin and the three main planes move there; the bodies stay where they are. New sketches on the main planes then sit at the new origin, and features already built on the main planes follow them, so every reference still works. Undo puts the origin back.

## Tips for all reference geometry

* Values accept units and formulas. See [Typing values](typing-values.md).
* Edit a reference feature from the feature tree like any other feature. Features that use it rebuild.
* If a picked face or edge disappears after an edit, the feature turns red with "missing reference". Edit it and pick again.
* To start a sketch on a reference plane, select it and click **Sketch** (S). See [Sketching](sketching.md).

### Two more plane methods

- **Tangent to a cylinder**: pick a cylinder face and a point or a plane. With a point, the plane touches the cylinder on the side facing the point. With a plane, it touches the cylinder and lies parallel to that plane. Handy for sketching on the side of a round shaft.
- **Through a line and a point**: pick a straight edge, sketch line or axis and a point off it; the plane holds both.

