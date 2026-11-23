# Boss and cut

These tools turn sketches into solids. A boss adds material and a cut removes it. Extrude pushes a sketch straight out, Revolve turns it around an axis, Sweep moves it along a path, and Loft joins several profiles with a smooth shape.

Where to find it: the Features command tab, groups Add Material and Remove Material, and the Insert menu.

## Starting a feature

Extrude and Revolve start this way. Sweep and Loft need sketches that are already drawn (a profile and a path, or several profiles): draw them first, then run the command and choose them in its panel.

1. Select a finished sketch and run the command. The property panel opens with a live preview.
2. Or select a plane or flat face, or nothing, and run the command. FDCAD starts a sketch first. Draw the profile and exit the sketch. The feature panel then opens on that sketch.
3. With nothing selected and exactly one unused sketch in the part, the feature uses that sketch.
4. Click OK, press Enter, or click the check mark in the confirmation corner to finish. Cancel or Esc removes the preview.

The new feature appears in the feature tree, for example "Extrude 1" or "Cut 1". Its sketch moves under it.

## Extruded Boss and Extruded Cut

**Extruded Boss** (Shift+E) pushes a sketch straight out to make a solid. **Extruded Cut** (Shift+C) removes material the same way.

**Steps**

1. Start the feature on a sketch with a closed profile.
2. Choose the end condition in Direction 1 and type the depth.
3. Or drag the arrow handle in the view. Near the ruler the depth snaps to the ticks. Click the value beside the handle to type it. Dragging past the start flips the direction only when Blind is the one direction; with Direction 2 on it does not flip.
4. Click OK.

**From group**

The Sketch box chooses the sketch. The start list sets where the feature starts:

1. Sketch Plane: on the sketch plane. This is the default.
2. Surface/Face/Plane: on a picked face or plane. On a curved face the start follows its shape.
3. Vertex: on a plane through a picked vertex or sketch point, parallel to the sketch.
4. Offset: at a distance from the sketch plane, with its own Reverse direction button.

The depth is measured from the start.

**Direction 1**

1. Reverse direction flips the feature to the other side.
2. End conditions, in list order:
   1. Blind: a set depth.
   2. Through All: through the whole part. Offered for cuts, and for bosses once a body exists.
   3. Through All Both: Through All in both directions at once. Direction 2 is hidden.
   4. Up to Next: ends at the first face of the part the profile meets. Each part of the profile stops at its own first face. For a cut, the cut goes through the material until it first comes out.
   5. Up to Vertex: up to a plane through a picked vertex or sketch point.
   6. Up to Face: up to a picked face or plane. The face must cover the whole profile.
   7. Offset from Face: as Up to Face, plus a distance. Reverse offset puts the end beyond the face. Translate surface moves the face instead of offsetting it. Drag the arrow on the face to change the offset.
   8. Up to Body: click any face of a body. A boss runs up to that body and joins it, its end following the body's surface. A cut goes right through it.
   9. Mid Plane: the depth split equally on both sides.

   Through All, Through All Both, Up to Next and Up to Body need a body, so a boss offers them once the part has one. Up to and Through All ends have no drag arrow.
3. Draft: lean the side faces by an angle. Draft outward leans them out instead of in. Draft is offered for Blind, Mid Plane, Through All and Up to Vertex ends only.
4. Merge result: join the boss to the part. Untick it to keep a separate body. Shown once the part has a body.
   **Pick operation from where it sits**: the extrusion chooses for itself on each rebuild. Mostly inside the part (more than half of it), it cuts; touching the part, it joins as a boss; apart from the part, it makes a new body. The panel shows "Chosen:" with the last choice. Tick **Alternate solution** when the choice is not what you meant: a cut becomes a boss, and a boss or new body becomes a cut.
5. Cut outside (cuts only): remove the material outside the profile, within the cut depth.
6. Print Top (cuts only): give every round hole the cut makes sideways a **Teardrop** or **Flat Bridge** top toward the printer's up, as the Hole Tool does, so it prints without supports.

**Direction 2**

Tick Direction 2 to extend the feature the other way too, with its own end condition and depth. Its list is the same less Through All Both and Mid Plane. It is not available with Mid Plane or Through All Both.

**Thin Feature**

Tick Thin Feature to make a wall around the sketch curves instead of a filled solid. Open sketches need it. For an open sketch, tick **Auto fillet corners** and type the inside **Corner radius**: each corner of the wall is rounded, and the outside radius is the inside radius plus the wall, so a bracket or channel comes out with an even wall. The two ends of the wall stay square.

1. Type: One Direction, Mid Plane or Two Direction.
2. Thickness, and Thickness 2 for Two Direction.
3. Reverse direction puts the wall on the other side of the curves.
4. Cap ends closes both ends of a closed thin wall with a lid of the cap thickness.

**Selected Regions**

Use only some regions of the sketch.

1. Click in the Selected Regions list.
2. Hover the view. The region under the cursor is lit. Click it to add it, click again to remove it.
3. Leave the list empty to use the whole sketch. Clear removes every pick.

The same sketch can be used by several features with different regions. The tree then shows "(shared)" with a link icon under the later features.

**Tips**

1. Every number field accepts units and formulas. See [Typing values](typing-values.md).
2. Dragging the handle past the sketch plane flips the direction.
3. Double click a dimension of a selected feature in the view to change it.

**Common errors**

1. "Sketch the profile, then exit the sketch to set up the feature." The feature needs a finished sketch.
2. The From face was lost after an edit. Pick the face again or choose Sketch Plane.
3. The profile does not land fully on the start or end face. Pick another face, or use Sketch Plane or Blind.
4. A sketch with open ends, branches or duplicate curves fails unless Thin Feature is on or you pick regions. Fix the sketch, see [Sketching](sketching.md).
5. "... cannot end on geometry made by itself or a later feature." Pick a face made before this feature.
6. "Up to Next finds no face for the whole profile in Direction 1. Choose Blind or Through All." Part of the profile meets nothing in that direction.

**Snapping and dragging without the panel**

1. Hold Alt while you drag a depth arrow. Move over a vertex or a face of the part and the end snaps to it. A marker shows the point, and the value says "to vertex" or "to face". A flat face parallel to the sketch gives its exact distance. When you let go on a vertex, a Blind direction becomes **Up to Vertex** on that vertex, so the depth follows the point when the part changes. Choose Blind again to keep a fixed depth instead.
2. You can extrude without opening the panel. With no tool open, click inside a closed region of a finished sketch. An arrow appears on it. A region on the part starts as a cut into the part; a region off the part starts as a boss.
3. Drag the arrow to set the depth. When you let go, a small bar appears. Choose Boss or Cut, then OK to add the feature, or Cancel. Edit in Panel opens the full Extrude panel. Escape or a click elsewhere cancels.

### Extruding at an angle

**Along** in Direction 1 sets which way the profile goes: **Square to the sketch** (the default), a plane's normal or an axis from the list, or **An edge picked in the view**, then click a straight edge. **Depth measured** says whether the depth runs along that direction or is the distance square to the sketch. A direction lying in the sketch's plane is refused.

### Twist and taper

**End twist** turns the profile by that angle from the start to the end, about its own centre; **End scale** makes it that many times bigger (or smaller, below 1) at the end. They work with a Blind extrusion from the sketch plane, without draft or Thin Feature, and are left out of the part when they are 0 and 1.

## Revolved Boss and Revolved Cut

**Revolved Boss** (Shift+R) turns a sketch around an axis to make a solid. **Revolved Cut** (Ctrl+Shift+R) removes material the same way. Use it for turned parts such as shafts.

**Steps**

1. Draw the profile on one side of a centerline.
2. Start the feature. With exactly one centerline in the sketch, it becomes the axis.
3. Otherwise click a sketch line, a straight part edge or a round face (its axis, as shown by Temporary Axes) as the axis, or choose a reference axis or the origin's X, Y or Z axis in the Axis list. The axis must lie in the sketch plane.
4. Set the angle and click OK.

**Options**

1. Axis of Revolution: the line or straight edge the profile turns around.
2. Direction 1: Reverse direction and an end condition:
   1. Blind: the angle, 360 degrees by default. Both directions together can turn at most 360 degrees.
   2. Through All: a full turn. The angle and Direction 2 are hidden.
   3. Up to Vertex: the turn stops where the profile's plane passes through a picked vertex or sketch point.
   4. Up to Face: the turn stops at a picked flat face or plane. The face must hold the axis or be crossed by the turning profile.
   5. Offset from Face: as Up to Face, but the turn stops short of the face by an angle. Drag the curved arrow to change it.
   6. Mid Plane: the angle split both ways.
3. Direction 2: Blind (a second angle the other way round), Up to Vertex, Up to Face or Offset from Face. Not available with Through All or Mid Plane.
4. Corners: where the path has a sharp corner, Smooth (the usual) lets the section turn, Mitre makes the two runs meet in a sharp edge on the corner's bisector, and Round rounds the outside of the corner.
4. Start tangency (Sweep): Path Tangent turns the profile square to the path where it starts, so a path that leaves the sketch plane at a slant still sweeps the full profile. None sweeps the profile as drawn, so a slanted path gives a thinner section.
4. Merge tangent faces (Sweep): on a smooth path made of several pieces, such as a line running into an arc, each profile edge makes one side face instead of one per piece. On a path with a sharp corner the faces stay separate and the sweep warns.
4. Direction (Sweep): the profile may sit part way along the path, where the path passes through the profile's sketch plane. Choose Along the Path, Against the Path or Both. With Both and a twist, the second twist field sets the twist of the side swept against the path.
4. More Profiles (Sweep): choose sketches further along the path and click Add. The section changes smoothly from the first profile into each one in turn. Each sketch needs one closed outline, the path must pass through its plane, and the first profile must have no holes.
4. Show section (Sweep and Loft): type a number from 1 (the start) to 11 (the end) to draw that section in the view, and step through them to find where the shape goes wrong. A sweep's section shows even when the sweep fails. 0 shows none.
4. Section values (Sweep): make profile dimensions change along the path. Type the dimension and a formula of t, which runs from 0 at the start to 1 at the end, such as `d1 = 10 + 10 * t` for a width that doubles. Separate several with semicolons. The sweep solves the profile at 9 places along the path and joins them smoothly. It needs a profile of one region without holes.
5. Merge result (bosses) and Thin Feature (bosses).
5. Selected Regions, as for Extrude.
6. Thin Feature: revolve a wall around the sketch curves instead of the regions they enclose, as for Extrude. An open profile, such as an L shaped line, makes a cup or a dish. The wall must not cross the axis. Cap ends closes both ends of a revolve of less than 360 degrees with a lid.

**Tips**

1. The profile may touch the axis along an edge.
2. Dimension from a line to the centerline with the text past the centerline to get a diameter.
3. Drag the curved handle to set the angle. It snaps to 5 degree steps near the ruler.

**Common errors**

1. "Revolve 1 failed: the profile crosses the axis. Move the profile to one side of the axis or pick regions on one side."
2. "Revolve 1 failed: the thin wall crosses the axis. Make the wall thinner, put it on the other side with Reverse, or move the profile away from the axis."
2. "The sketch needs a centerline to revolve around. Add one in the sketch."
3. "Pick the axis of revolution: a line or centerline in the sketch, or a straight edge of the part." The sketch has more than one centerline. Pick one.
4. "Only a straight edge can be the axis. Click a straight edge."
5. "Revolve 1: the Direction 1 end face cannot be reached by the turning profile. Pick a face that holds the axis or that the profile crosses, or choose Up to Vertex or Blind."

## Swept Boss and Swept Cut

**Swept Boss** (Shift+S) moves a profile along a path to make a solid. **Swept Cut** removes material the same way. It has no default key.

**Steps**

1. Make two sketches: a closed profile, and a path whose curves join end to end. Lines, arcs, splines and partial ellipses can join; a circle, a full ellipse or a closed spline is a path on its own. The path must start on the profile's plane.
2. Run the command.
3. Choose the profile sketch and the path sketch. Or click joined edges of the part instead. They go in the Path edges list.
4. Click OK.

**Options**

1. Profile: Sketch profile, Circular profile with a Diameter for a round rod (no profile sketch needed), or Face profile: click a flat face of the part, holes included, to sweep it along the path (the path must start on the face's plane; Thin Feature is not offered).
2. Orientation: Follow Path keeps the section's angle to the path. Keep Normal Constant keeps it parallel to the start. Follow Curvature turns the section with the path's bend, which suits a helix; it cannot be used with a twist. Normal to Face keeps the section's up direction on the normal of a face under the path: click the face. Follow Second Path points the section's X axis at a second sketch or curve beside the path: choose it in the list. Neither can be used with a twist.
3. Twist: None (flat paths), Minimum Twist (3D paths), Specify Twist Angle, Number of Turns (type the turns, such as 2 or 0.5), or Specify Direction Vector (pick a plane, flat face or straight edge). On a closed path the twist must be whole turns, so the ends meet.
4. Merge result (bosses) and Thin Feature (bosses).

**Tips**

1. For a pipe or a tube along a curve, see also Pipe in [Curves](curves.md).

**Common errors**

1. "Choose the profile sketch." and "Choose the path sketch, or click edges of the part for the path."
2. The path does not start or end on the profile's plane. Move the path or the profile.
3. "the path crosses itself" or "the swept result crosses itself about 24 mm along the path (40% of its length), where it bends with a radius of 5 mm". The message names the tightest bend of the path and says when the profile reaches further from the path than that radius. Make that bend gentler, make the profile smaller, or split the path there and sweep each part.

**Scale at start** and **Scale at end** grow or shrink the profile along the path (as factors of its drawn size), **Even**ly or **Smooth**ly. A scaled sweep cannot also twist by an angle.

### Guide curves for a sweep

In **Guide Curves**, add one or two sketches or curves (choose one and click **Add**), or tick **Pick edges as guides** and click model edges. Each guide must start on the profile's outline, away from the path. Along the path the section turns and grows or shrinks so it stays on the guides: one guide sets its turn and size about the path, two guides set its turn, size and place. The sweep stops where the shortest guide ends, and says so. With guides, Orientation and Twist are not used.

### Swept Cut with a tool body

For a milling cutter path, choose **Tool body** as the profile type of a Swept Cut and click a face of the body to move, such as a cylinder for a flat end mill or a cylinder with a ball end. Place the body at one end of the path. It moves along the path without turning and removes everything it passes through, and the tool body itself is used up. Straight moves are cut exactly; curves are followed as short straight moves within 0.05 mm. The tool body must be round about an axis or flat sided, so that its outline stays the same along a move.

## Lofted Boss and Lofted Cut

**Lofted Boss** joins two or more profiles with a smooth solid. **Lofted Cut** (Shift+L) removes material the same way. Lofted Boss has no default key.

**Steps**

1. Make each profile as a closed sketch, usually on parallel planes.
2. Run the command.
3. Choose a sketch and click Add Profile for each one, in order. You can also click flat faces of the part.
4. Use Move Up and Move Down to fix the order, then click OK.

**Options**

1. Start and End Constraints: Default, None, Normal to Profile or Direction Vector. Tangent length sets roughly how far the start or end direction reaches. None on one end only behaves like Default; set both ends to None for straight faces between two profiles.
   Tangent to Faces and Curvature to Faces work when that end's profile is a face of the part: the loft leaves the face in the direction its neighbouring faces run, so it carries on from the sides of a box, for example. Curvature to Faces holds that direction for longer, so the loft starts straight.
2. Connection point: the corner where the selected profile starts. Change it to untwist the loft. In a thin loft it applies to the outer outline only.
3. Connectors: more corners of the selected profile that must meet the matching corners of the other profiles, typed as vertex numbers such as `3, 6` (counted like the connection point). Every profile needs the same number of connectors; the loft joins the first to the first, the second to the second, in the order they come round each profile, so you can untwist one part of a loft without changing the rest. **Reset** clears the connection points and connectors of every profile.
3. Close loft: join the last profile back to the first.
4. Merge result (bosses) and Thin Feature (bosses).

**Tips**

1. With both constraints set to None, the faces are straight between profiles.
2. If the loft looks twisted, change the connection point of one profile.

**Common errors**

1. "Add at least two profiles."
2. Each profile must be one closed region. Holes inside a profile are not joined.
3. "Choose a plane, or click a flat face or straight edge for the direction." Direction Vector needs a pick.

Next, round and shape your part with [Modify](modify.md).

### Guide curves and a centerline for a loft

**Guide Curves** takes any number of guides; each must touch every profile, and the sides of the loft follow them. **Centerline** keeps the middle sections square to one curve, with **Number of Sections** sections added between each pair of profiles. With guides or a centerline every profile needs the same number of edges (split an edge in the sketch when they differ), and the loft cannot be closed or thin.

## Primitive Solid

**Primitive Solid** (Features tab, in the dropdown with Lofted Boss) adds or cuts a simple solid from typed sizes, with no sketch: a box, cylinder, sphere, cone (a top diameter of 0 makes a point), torus, wedge (its top slopes from the height to the height at the end), prism (a number of sides), tube, geodesic sphere or geodesic dome. A geodesic shape is made of flat triangles: its **Frequency** (1 to 8) sets how many times each of the 20 big triangles is split along a side, so higher is rounder with more faces. The dome is the top half, cut flat at the middle and standing on its base. Pick a plane, flat face or coordinate system for the **Frame**; the solid stands on it, or is centred on it when **Centred on the frame** is ticked. On a face the frame's origin is the middle of the face. Choose **Add** or **Cut**.

## Corner Relief

**Corner Relief** (Features tab, Remove Material group, under Lofted Cut) lets a round milling tool reach the inside corners of a pocket or slot, so a square part still fits in it.

1. Choose **Corner Relief**.
2. Pick the inside corner edges, or choose a cut in **All Corners Of** to relieve every upright inside corner it made.
3. Choose the **Relief**: **Dogbone** cuts a round notch along the corner's diagonal, **T-Bone** cuts a round notch into one wall (tick **Other Wall** for the other one), and **Corner Fillet** rounds the corner to the tool.
4. Type the **Tool Diameter** and a **Clearance** if the tool should not rub. A variable in Tool Diameter keeps every relief on one tool size.

Common error: "A picked edge is not a straight inside corner between two flat faces." Pick only inside corner edges.

## Add Loft Section

Right click a loft in the feature tree and choose **Add Loft Section** to put a new profile between two others. Enter where it goes: 1.5 is halfway between profiles 1 and 2, 2.25 a quarter of the way from profile 2 to 3. The two profiles on either side must be sketches on parallel planes. FDCAD adds a plane at that place and a sketch on it that holds the loft's own cross section there, so the shape does not change yet, and opens the sketch so you can edit it. Curved parts of the section are drawn as short lines. Undo removes the plane, the sketch and the new profile together.

## Loft to a point

The first or the last profile of a loft can be a point: click a vertex of the part, or pick a sketch point or a reference point. The loft narrows to that point, like a cone or a pyramid. Only the ends can be points. A pointed end has no tangency of its own, so leave its start or end constraint at Default. Close Loft, Thin Feature and guide curves do not work with a pointed end.

A profile can also be a loop of edges of the part: with Pick Edges as Guides off, select the edges of the loop together (Select Loop helps) and they become one profile, listed as Edge loop. The edges must join all the way round and lie flat.

## A depth per region

With regions picked in **Selected Regions**, tick **Own depth per region** to give each region its own depth in the same extrude or cut. Type a depth for a region in the table, or leave it empty to use the feature's depth. Each region keeps its depth: removing a region drops its depth, and a newly picked region starts with the feature's depth. This works with one Blind direction, without Thin Feature or Cut Outside. Faces of the second and later regions are named with the region number, so features after it can tell them apart.

## Profile offset

Extruded Boss and Extruded Cut have a **Profile offset** field. A positive value grows the sketch's profile by that much on every side (outside corners get rounded); a negative value shrinks it. Use it to make two parts that fit together from one sketch: cut a pocket with the sketch as drawn, and extrude the matching plug from the same sketch with an offset of minus your print clearance. Typing a variable such as `fit` lets you change the clearance for every part at once. Leave it at 0 for no change.

A pocket for a tool or a part (a tool holder or a foam style insert): sketch the outline of the tool on the top face, or trace it from a picture, and add a circle over one edge for a finger notch so you can lift the tool out. Extruded Cut the sketch with the pocket's depth and a **Profile offset** of the clearance, for example 0.5 mm. The outline and the notch join and grow together.

## Switching between boss and cut

Right click an extrude, revolve, sweep or loft in the feature tree and choose **Switch to Cut** (or **Switch to Boss**). The feature keeps its sketch, end conditions and references; only whether it adds or removes material changes. A name FDCAD gave it, such as "Extrude 3", changes to match ("Cut 4"); a name you typed stays. For extrudes and revolves, **Make Thin** turns it into a 1 mm thin wall (edit it to change the thickness), and **Make Solid** turns Thin off again. Each switch is one undo step.

## Cutting with an open line

An **Extruded Cut** can use a sketch that is one open line or chain of lines and arcs, with no closed shape. The material on one side of the line is removed, **Through All** or to any other end. The line's ends carry on straight, along their end direction, to well past the part, so a line that stops short of an edge still splits the part there. Tick **Flip side** to cut the other side. Use it to trim a part along a curved edge without drawing round the waste. A line that crosses itself, or whose carried on ends cross it, is refused: draw a simpler line or use **Thin Feature**. Thin Feature still makes a slot along an open line, and a boss still needs a closed shape.

## Walls that meet the part

With **Thin Feature** on an open line, tick **Merge ends** to make the wall meet the part at its ends. Each end carries on straight until it reaches material and stops there; a wall drawn too long is cut back to the material instead of poking out the far side. An end with nothing to meet stays where it was drawn. Use it for ribs and partitions between walls, so you need not draw the line exactly to the wall. Merge ends works on Extruded Boss only.
