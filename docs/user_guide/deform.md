# Deform

Deform tools change the shape of whole bodies: they bend, twist, taper or stretch a region, or lay a body along a curve. Use them for shapes that are hard to model with sketches, such as a twisted bar or a handle that follows a path.

Where to find it: Bodies tab, Deform group. **Flow Along Curve**, **Bend**, **Twist**, **Taper** and **Stretch** share one dropdown button. All five are in the Insert menu. They have no default keys.

## How the deform tools work

All five tools share the same panel parts.

1. **Bodies**: click any face of each body to deform. With no body picked, every body is deformed.
2. **Triad and Trim Planes**: the triad is a small frame of three axes. The tool works along or about these axes.
3. Two trim planes, square to the triad's third axis, set where the deformation starts and stops. Only the region between them deforms. Below the start plane the part stays where it is. Beyond the end plane it moves with the end of the region, so there are no gaps.
4. **Tolerance** in the Options group: how far the result may be from the exact shape. The default is 0.01 mm.

A new deform feature centres the triad on the picked bodies and puts the trim planes at their ends. The live preview shows the deformed bodies and the two trim planes.

Triad and trim plane fields:

* **Axis**: which model axis, Z, X or Y, is the triad's third axis.
* **Turn first axis**: turns the first and second axes about the third axis.
* **Origin X**, **Origin Y**, **Origin Z**: where the triad sits.
* **Start plane** and **End plane**: distances along the third axis from the origin.

In the view:

* Drag the red, green and blue arrows to move the triad along X, Y and Z.
* Drag the arrow on a trim plane to move that limit.
* The panel values follow your drag. Click a value beside a handle to type it.
* The triad's turn and axis are set in the panel only. There is no rotation ring.

### Tolerance and the approximate warning

FDCAD rebuilds the deformed surfaces to pass within the tolerance of the exact shape. If it cannot, the feature still builds but turns yellow with a warning such as: "Twist 1 is approximate: the surfaces are up to 0.03 mm from the exact shape (tolerance 0.01 mm). Raise the tolerance or reduce the angle."

1. To clear the warning, raise the tolerance or reduce the main value, such as the angle.
2. The feature's report always gives the largest distance from the exact shape.
3. If the result is not a valid solid, the feature fails with an error that says what to change. The rest of the tree still builds.

## Bend

**Bend** bends bodies about the triad's first axis, between the trim planes.

1. Click **Bend** and pick the bodies.
2. Place the triad and the trim planes round the region to bend.
3. Choose **Set**: Angle or Radius, and type it.
4. Click OK.

Tips: angle and radius are linked, so the length between the trim planes stays the same when bent. Set one and the other follows. The angle must be 360 degrees or less, also when it comes from the radius.

Common errors:

* "The bend radius must not be zero." Type a radius, or set the angle instead.
* "The bend angle is more than 360 degrees." Enter a smaller angle or a larger radius.
* "The bodies reach past the bend centre." Enter a smaller angle or a larger radius, or move the triad.

## Twist

**Twist** turns bodies about the triad's third axis. The turn grows evenly from the start plane to the end plane.

1. Click **Twist** and pick the bodies.
2. Line up the third axis with the length of the part.
3. Type the **Angle** and click OK.

Tip: a large angle over a short region gives tight twisting and may need a larger tolerance.

## Taper

**Taper** scales bodies across the triad's third axis, from full size at the start plane to the **Taper factor** at the end plane.

1. Click **Taper** and pick the bodies.
2. Place the trim planes at the two ends of the region.
3. Type the **Taper factor** and click OK. For example 0.5 makes the end half as wide.

Common error: "The taper factor must be above zero."

## Stretch

**Stretch** makes the region between the trim planes longer along the triad's third axis.

1. Click **Stretch** and pick the bodies.
2. Place the trim planes round the part of the body to stretch.
3. Type the **Distance**, or drag the distance arrow in the view. Click OK.

Tip: a negative distance shortens the region.

Common error: "The distance would squash the region to nothing." Use a smaller negative distance.

## Flow Along Curve

**Flow Along Curve** lays bodies along a curve. The triad's third axis is laid onto the curve from its start, and the first axis sets which way the body faces at the start.

1. Draw a sketch whose curves join end to end, or make a curve feature. See [Curves](curves.md).
2. Click **Flow Along Curve** and pick the bodies.
3. Choose the **Curve**.
4. Put the start trim plane at the end of the body that should sit at the curve's start: that plane goes to the start of the curve. The triad sets which way the body faces.
5. Click OK.

Options:

* **Fit to curve length**: spreads the region between the trim planes over the whole curve. Without it, one millimetre of body follows one millimetre of curve.
* Past the ends of the curve, the body goes on straight along the end directions.

Common errors:

* "Flow 1 has no curve. Choose a sketch or curve."
* "The curve bends tighter than the bodies are wide." Use a curve with larger bends, move the triad or turn it with Turn first axis.

## Deform Point

**Deform Point** pulls part of a body round a point, along a direction, and leaves the rest as it is. It has no triad or trim planes.

1. Click **Deform Point** (Bodies tab, Deform group, in the dropdown under the triad tools).
2. Click the **Point**: a vertex, sketch point or reference point. Optionally click a **Direction** (an edge, face or axis); without one, the body moves along the normal of the face the point is on.
3. Enter the **Distance** to move and the **Radius** of influence. **Stiffness** (0 to just under 1) is the part of the radius that moves the whole distance; the rest fades out smoothly to nothing at the radius.
4. Optionally pick **Fixed faces and edges**: they stay where they are, and the movement fades out near them.

## Curve to Curve

**Deform Curve to Curve** moves the body near one curve onto another. Pick the **Initial curve** (a sketch or curve on or near the body) and the **Target curve**. Points match by length along each curve, so the start of one goes to the start of the other. The movement fades out over the **Radius** from the initial curve. Fixed faces and edges work as in Deform Point.

## Surface Push

**Surface Push** presses a tool into a face as a smooth dent. Click the **Point** where the tool first touches; the push goes into the face there, or along a picked **Direction**. Choose the **Tool**: a **Sphere** (Tool size across is its radius), an **Ellipsoid** or a **Rectangle** with rounded sides (half sizes across and along). Enter the **Depth**. **Reach into the body** is how deep below the face the dent fades out, so the far side of a thin wall does not move; empty is three times the depth.

These three use the same tolerance and approximate warning as the other deform tools.

## Common errors for all deform tools

* "The end trim plane must lie beyond the start trim plane." Drag a trim plane, or change Start plane and End plane.
* "The part has no bodies to deform. Add a boss first."
* "The tolerance must be above zero."
* "The result is not a valid solid." Reduce the main value, move the trim planes or raise the tolerance.

See also: [Patterns and bodies](patterns-and-bodies.md) for picking bodies, and [Typing values](typing-values.md).
