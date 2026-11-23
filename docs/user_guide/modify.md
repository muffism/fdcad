# Modify

These tools change a solid you already have. Fillet rounds edges, Chamfer bevels them, Shell hollows the part and Draft tilts faces for moulding. Move Face, Offset Face and Delete Face edit faces directly, which also works on imported STEP bodies.

Where to find it: the Features command tab, group Modify (a Fillet and Chamfer dropdown, and buttons of their own for Rib, Draft and Shell) and group Direct Editing (Move Face, Offset Face, Delete Face), and the Insert menu. Right click a face for Move Face, Offset Face and Delete Face with that face already picked.

## How these panels work

1. Select edges or faces first if you like, then run the command. The panel opens with them already picked.
2. Click edges or faces in the view to add them to the list. Select a row and click Remove to take it out.
3. You cannot pick geometry made by this feature or a later one. FDCAD says so and asks for another pick.
4. If a pick is lost after an earlier edit, it is listed first in red as "Lost: ...". Pick it again or remove it.
5. The preview shows the new and changed faces. Click OK to apply.

## Fillet

**Fillet** (Shift+F) rounds the picked edges with a constant or varying radius.

**Steps**

1. Run Fillet.
2. Click edges, or faces (a face adds all its edges).
3. Type the radius and click OK.

**Options**

1. Fillet Type: Constant Size or Variable Size.
2. Items to Fillet: the picked edges and faces. Add Feature adds every edge of an earlier feature.
3. Radius. Tick Multiple radius to give each picked edge its own radius. Edges that come from picked faces, Add Feature or the fillet assistant use the common radius.
4. Variable Radii (Variable Size): a radius at each end of each edge and at its control points. Control points start evenly spaced; type a position in percent of the edge for each point to move it. Add Point puts a new point in the middle of the widest gap, and Delete Point removes the point with the chosen number (later points move up one place). Transition is Smooth or Straight. Set All copies one radius to every point.
5. Preview: Full preview, Partial preview (outlines only the new faces, which is quicker on large parts) or No preview (fastest).
6. Face fillet (Fillet Type Face): pick faces for Face Set 1 and Face Set 2. The edges where the two sets meet are rounded with the radius. Method Hold Line: press Pick Hold Lines and click edges on one face set. Each round meets that face along the hold line, so its size follows the gap, and the face between the hold line and the other set is used up. Hold Line works on straight edges between flat faces.
7. Full Round fillet (Fillet Type Full Round): click a side face, the centre face and the other side face. The centre face is replaced by a half round that touches both sides. The sides must be flat and parallel, and the radius is half the distance between them.
8. Fillet assistant: in Items to Fillet, choose Whole Part or a feature, then click Add Convex Edges or Add Concave Edges. The list keeps one item that finds the edges again when the part changes. Fillet rules work the same way: choose a feature in the scope list, choose Attach Edges (where it meets the earlier body), Free Edges (its other edges), Feature Edges (all its edges) or Edges Parallel to X, Y or Z (of the feature, or of the whole part), and click Add Rule. Tick Own radius first to give the rule its own radius. To leave edges out of a rule, select it in the list, press Pick Exclusions and click the edges.
9. Partial Edges (Constant Size): tick the group, choose Distance or Percent and type a start and an end. Only that part of each edge is rounded. Flip measures from the other end of the edge. Choose Reference to set the start and end by picks instead: click two vertices, or press Pick Ends and click flat faces. A vertex sets the end at the nearest point of each edge, a face where the edge crosses its plane. A reference plane works too when stored in the file.
10. Tangent propagation (on by default): edges joined smoothly to a picked edge are rounded with it. Turn it off to round only the picked edges; each round then ends square where a smooth edge joins it. This works with Constant Size and Variable Size fillets on a part with one body.
11. Method and Profile (Constant Size). Method: Radius (one radius), Asymmetric (a distance on each face; Reverse distances swaps the faces) or Chord Width (the straight width across the round; each edge gets the radius that gives that width). Profile: Circular, Conic (a shape value from 0.05 to 0.95: small is flat, large is close to the sharp corner, about 0.41 is a circle on a square corner), Curvature Continuous (no jump in curvature where the round meets the faces) or Elliptic (Asymmetric only). Circular with Radius or Chord Width works on any edge. Asymmetric, Conic and Curvature Continuous work on straight edges between flat faces; the error names any other edge.
12. Limits (Constant Size). Edges to keep: press Pick Kept Edges and click edges a round may not swallow. If a round would remove one, the fillet stops, names it and offers the largest radius that keeps it. Limiting plane: press Pick Limit and click a flat face; each round stops square at that plane, and edges wholly in front of it are not rounded. Keep the other side rounds the front part instead.
13. Select through faces (Items to Fillet, also on Chamfer): while it is ticked, a click in the view takes the nearest edge under the cursor, even an edge hidden behind a face. Use it to pick back edges without turning the part. The tick is kept for the session and does not change the part.

**Tips**

1. Edges joined smoothly to a picked edge are rounded with it, unless you turn off Tangent propagation.
2. Where three rounded edges meet at a corner, FDCAD adds a smooth corner blend that joins each round without a crease.
3. The panel remembers your last settings for the next fillet in the same session.
4. Use No preview on large parts to stay fast.
5. A corner that already has rounds on two of its edges: round the third edge with the same radius and the three meet in a ball corner. With another radius, or where the edge ends at a chamfer, the new round is cut straight through to the end of the part.

**Common errors**

1. "Pick edges, faces or features to fillet."
2. Some edges cannot take the radius. FDCAD lists them with the largest radius that works and offers two buttons: "Fillet the rest (skip N edges)" or "Reduce the radius to X mm". Nothing changes until you click one and then OK.
3. An edge too short, or a radius larger than the faces next to it allow. Reduce the radius or pick fewer edges. When part of a failing edge can take the radius, the errors panel also offers **Limit failing areas**: the stretch of the edge that works is rounded and the rest stays sharp. Each such edge becomes its own Partial Edges fillet after this one, in one undo step, so you can change its start and end later.
4. All edges work alone but not together. The message marks each such edge "(rounds on its own)" and says the kernel cannot round them together with the others in one fillet. FDCAD tries other ways and offers the ones that build as buttons in the errors panel: Fillet each chain as its own feature, Fillet in smaller groups, Larger radius first (with Multiple radius) and One fillet per edge. Each splits the fillet into several fillets in one undo step.
5. The rounds of neighbouring edges run into each other, as on the four upright corners of a square plate at half its width. Every such edge is named with the largest radius that works, and the message says the rounds run into each other. Click **Reduce the Radius**, or fillet some of these edges and leave the others out.

When you pick a whole feature to round, tick **Omit attach edges** to round only its own edges and leave sharp the edges where it meets the rest of the part.

To change one rounded edge without opening the fillet, right click its round face in the view and choose **Change Fillet Edge**. Type a radius for that edge and click OK, or click Remove from Fillet. This works for edges you picked one by one, not for edges that came from a picked face or feature.

To change many fillets together, right click a fillet in the tree and choose **Change Fillets**. Type a radius range to list only the constant size fillets inside it, type the new radius and click Apply to Listed. All of them change in one undo step.

Rounds on an imported body have no fillet feature to edit. In **Change Fillets**, the count below the list shows every round face in the radius range on the part. Type the range and a new radius and click Add Remove Fillets: a **Remove Fillets** feature removes those rounds, smallest first, a few at a time, and makes them again at the new radius. Edit it to pick round faces instead of a range, or to only remove them. Rounds that cannot be removed stay and are named in a warning.

To try a bevel instead, right click a constant size fillet in the tree and choose **Change to Chamfer**: it becomes an equal distance chamfer of the same size on the same edges. An equal distance chamfer has **Change to Fillet**. Undo changes it back.

## Chamfer

**Chamfer** (Ctrl+Shift+F) bevels the picked edges, or a corner, with a flat face.

**Steps**

1. Run Chamfer and choose the chamfer type.
2. Click edges or faces. For Vertex, click a corner.
3. Type the sizes and click OK.

**Options**

1. Chamfer Type:
   1. Angle Distance: a distance and an angle, measured from the face the distance is on. The angle is between 0 and 90 degrees.
   2. Distance Distance: Symmetric (one distance on both faces) or Asymmetric (two distances).
   3. Vertex: three distances along the three edges at a corner, or tick Equal distance for one value.
   4. Offset Face: the distances are measured square to each face, as if each face moved inward by its distance.
   5. Face to Face: pick two face sets. The edges where they meet are chamfered by one distance, two distances (the first along Face Set 1), or the width of the chamfer face.
2. Flip direction: measure the first distance on the other face of each edge. Which face is first is chosen by FDCAD, not by the order you click, and it can change after an edit that adds faces. Check the preview after edits.
3. Preview: Full preview, Partial preview or No preview.
4. Partial Edges (symmetric Distance Distance): tick the group, choose Distance or Percent and type a start and an end. Only that part of each edge is bevelled, with square ends. Flip measures from the other end of the edge. Reference sets the start and end by two picks, as on Fillet.
5. Tangent propagation (symmetric Distance Distance, on by default): turn it off to bevel only the picked edges, each ending square where a smooth edge joins it.
6. Corners: where three bevels meet at a corner. Patch (the default) leaves a small flat triangle; Mitre runs the three bevels on until they meet in one point, with no extra face; Blend replaces the triangle with a curved face that meets the three bevels smoothly along their edges (a slight crease stays at its three points). A corner that is not a triangle between three bevels of the chamfer stays a patch, with a warning. A setback (the corner pulled back along the edges) is not available.

**Common errors**

1. "Pick edges or faces to chamfer." or "Pick a vertex to chamfer."
2. The Vertex type needs a corner where exactly three straight edges meet, and a distance shorter than each edge.
3. Some edges fail. Use the "Chamfer the rest" button, or reduce the distance.

## Shell

**Shell** hollows the part, leaving walls of a set thickness. It has no default key.

**Steps**

1. Run Shell.
2. Type the thickness.
3. Click the faces to remove, for example the top face of a box. Pick none for a closed hollow part.
4. Click OK.

**Options**

1. Parameters: Thickness, Faces to remove, Shell outward (the wall grows outside the part), Show preview.
2. Multi Thickness: click faces that need their own thickness, then type it for each.
3. Body to Shell: shown when the part has several bodies and no face is removed. Click a face of the body to shell.
4. **Check Walls**: before building, finds the faces that bend too tightly for the wall thickness and names them with the smallest bend radius, or says every face fits.
5. Both sides: half the wall inside the part and half outside, centred on its faces. It works on a part with one body.
6. Wall: Exact (the default), Never thinner or Never thicker. The wall is measured from each point of the new wall to the nearest face of the part. Never thinner keeps the wall at least the thickness everywhere (sharp corners reach a little past it). Never thicker uses rounded corners, so the wall is never more than the thickness. After the shell, FDCAD measures the wall at its corners and edges and warns, with the measured value, when the rule is not kept. Never thicker cannot be used with Sharp corners.

**Tips**

1. Add fillets before Shell, so the inside follows the rounds.
2. Turn off Show preview on large parts while you set up the faces.

**Common errors**

1. A face bends with a radius smaller than the wall. FDCAD names the face and highlights it, for example "face X bends with a radius of R mm, smaller than the T mm wall". Use a thinner wall or a larger fillet on that face.
2. "The part has several bodies. Pick a face of the body to shell."
3. Two faces are too close for a wall on each, for example two holes 2 mm apart with a 1 mm shell. FDCAD names both faces and highlights them: "faces A and B are 2 mm apart, too close for a 1 mm wall on each. Use a wall thinner than 1 mm, or move those faces apart." This check is made only after an inward shell fails, so it never stops a shell that can be made.
4. The kernel cannot make the wall of one face. FDCAD tries leaving each face out, tightest bend first, and names the first one that lets the shell build. Click "Skip face X (leave it open)" to leave that face open. To treat every face again, right click the shell in the tree and choose **Reset Skipped Faces**. On a part with many faces FDCAD tries fewer faces, so it may find none; then the message says what to change. Cancel stops the search at once.

## Draft

**Draft** (Shift+D) tilts faces by an angle from a neutral plane, so a part can leave a mould.

**Steps**

1. Run Draft.
2. Type the draft angle.
3. Choose the neutral plane from the list, or click Pick Neutral Face and click a flat face.
4. Click the faces to draft, then click OK.

**Options**

1. Draft Angle: measured from the pull direction, less than 89 degrees. The pull is the normal of the neutral plane.
2. Neutral Plane: faces turn about where they meet it. Reverse direction flips the pull.
3. Faces to Draft, and Propagation: None, Along tangent, All faces, Inner faces (holes and pockets) or Outer faces.
4. Show changed faces: the preview shows only the drafted faces. Untick it to see the whole part.
5. Type of Draft chooses the method:
   - Neutral Plane: faces tilt about a plane you pick.
   - Parting Line: pick the direction of pull and the parting edges. The faces next to the edges on the pull side tilt about the edges, so the edges stay where they are. Tick Other side to draft the faces on the other side, or Draft both sides to draft both (Other angle sets the angle of the other side).
   - Step Draft: as Parting Line, but the parting edges may lie at different heights. Each height is drafted about its own plane.
   - Neutral Plane options: the angle list chooses Angle from the pull (every face ends at the angle) or Angle added to the lean (a flat face that already leans tilts by the angle more). Tick Other angle below the neutral plane and type it to tilt the faces below the plane by their own angle.
   - Fixed Edge: pick the direction of pull, the faces to draft and, for each face, one of its edges under Fixed edges. Each face turns about its own edge, so that edge stays where it is. The edges must be straight and square to the direction of pull.
   - Allow reduced angle (Parting Line and Step Draft): when the full angle fails, the faces are drafted at the largest angle that works, and a warning says which angle was used.
6. Parting edges must lie square to the direction of pull. A split part (two features stacked on the same outline) gives such edges.
7. Add Faces That Need Draft adds every face whose draft is smaller than the draft angle.
8. Reapply fillets (Neutral Plane and Fixed Edge, with Propagation None or Along tangent): the rounds next to the faces to draft are removed first and made again after the draft, with the same radius. References to the old round faces become lost references.

**Detailed preview**: tick it to see the whole result with the faces the draft changes in a second colour. Faces a feature adds get the preview colour, and when it makes new bodies only those show. The setting lasts for the session. Extrude (in its Direction 1 group) and Rib have the same tick.

**Common errors**

1. "Choose a neutral plane or click a flat face."
2. "Pick faces to draft, or choose All, Inner or Outer faces."
3. A flat face square to the pull cannot be drafted. FDCAD names the face. Remove it from the list.

To change several drafts at once, right click a draft in the tree and choose **Change Drafts**. The list shows every draft with its angle and pull direction. Select rows, type a new angle and click Set Angle, or click Remove Selected. Each change is one undo step.

## Move Face

**Move Face** moves, offsets or turns faces. The faces around them stretch to stay joined, so the body stays closed. It has no default key.

**Steps**

1. Run Move Face, or right click a face and choose Move Face.
2. Choose the type: Offset, Translate or Rotate.
3. Click the faces to move.
4. Set the distance or angle, or drag the transform handles in the view. Click OK.

**Options**

1. Offset: each face moves along its own normal by the Distance. A hole wall grows or shrinks the hole. Reverse moves the other way.
2. Translate: the faces move as a group. Move by: Distance along a direction (click a straight edge, flat face or plane), Delta X, Y, Z, Up to Vertex, Up to Face, Offset from Face or Up to Body.
3. Rotate: the faces turn as a group. Turn about an Axis (click a straight edge, round edge or cylinder) by an Angle, or about a Rotation origin with an angle about X, Y and Z.
4. Copy (Translate and Rotate): keep the faces and add a moved copy that joins the body.

**Tips**

1. A helper bar appears beside the last picked face. One click adds related faces: all coplanar faces, all inner loops (every hole wall in that face), all faces around it, all tangent faces, and full cylinders with the same axis or direction.
2. While you drag a handle, a ruler or a protractor appears. Near it the value snaps to the ticks. Click the value to type it.
3. Up to Face needs a target face parallel to the moved face.

**Common errors**

1. The move cannot be healed, for example a face would leave the body. The message names the face. The preview keeps the last valid state. Use a smaller move or pick other faces.
2. Copy needs faces that form a whole boss or cut, and the copy must join the body.

Sizes: choose **Resize** in **Type** and type the new **Diameter** of the picked cylinders or spheres (a torus takes its tube diameter). For **Offset**, set **Move by** to **To a measured size**, pick the item in **Measure from** (a vertex, an edge, or a hole, which counts from its axis), and type the **Size**: the face moves until it is that far from the item.

Sizes: with Offset set to **To a measured size**, the view shows the size as an arrow from the item you measure from to the face that moves; click its value to type a new one, or drag the arrow. **Symmetric** moves both faces half each, for two faces opposite each other such as the sides of a slot. **Lock this size** keeps the size: a later Move Face that moves one of the two faces moves the other with it.

Cones: with **Resize**, a picked cone face takes the **Cone angle** you type (the angle between its side and its axis) and keeps its large or small end where it is (**End that stays**). The faces around it follow, as a hole wall below a countersink does.

Neighbouring faces: the **Neighbours** choice says how the faces around the moved faces follow them.

- **Extend** (the default): they keep their angle and grow or shrink to meet the moved faces.
- **Tip**: they tilt to meet them. Slide the top of a boss sideways and its sides lean. Tip needs flat faces around, with straight edges where they meet the moved faces, and each must stay flat.
- **Lift**: the faces move unchanged, and new side faces join them to where they were. For Translate and Offset.

**Previous Solution** and **Next Solution** step through these. If the chosen way stops working after a change, Move Face uses another and warns you; tick **Keep this solution** to get an error instead. **Rounds on its edges**: **Follow** lets the rounds grow or shrink with the move; **Remake** takes them off first and makes them again after, with the same size.

Rules: in the **Rules** group, tick **Keep coplanar faces**, **Keep concentric faces**, **Keep tangent faces** or **Keep equal radii**, and the faces in that relation to the picked faces move with them, for example both pads on one plane, or every hole of one size. **Faces the rules leave still** keeps chosen faces out. **Suspend all rules** turns the rules off for this edit and keeps the ticks. **Keep symmetry** moves the mirror image of a picked face the mirrored way (Offset and Resize; it mirrors in the **Symmetry plane** you pick, or in each main plane through the origin). **Keep parallel and square faces** and **Keep faces on main planes** add no faces: they keep the faces next to the moved ones facing the same way, so a way of following that would turn them (for example Tip) is not used. Each ticked rule has its own box of faces it leaves alone, while the other rules still apply. After the preview each ticked rule says how many faces it adds or holds, or that it has no effect. The preview shows the moved faces in the accent colour, faces next to them that stay still in grey, and faces that stretch in amber.

**Reapply fillets** (Move Face and Delete Face): tick it when the faces you move or delete have rounds next to them. The rounds are removed first, the change is made on the sharp body, and the rounds are made again with the same radius. The new rounds are named after this feature.

## Offset Face

**Offset Face** moves faces along their own normals by a distance. It opens Move Face with Offset chosen, so it has the same options and errors.

**Steps**

1. Run Offset Face, or right click a face and choose Offset Face.
2. Click the faces, type the Distance and click OK.

**Tips**

1. Use it to make a hole fit a printed peg: offset the hole wall by a small amount.
2. On a part with threads, lofts or other free form faces, or with very many faces, a flat face whose neighbours are all flat moves in a fraction of a second. Other faces on such a part can take longer, because the whole body is worked again.

## Delete Face

**Delete Face** removes faces and heals the body, for example to remove a fillet, a chamfer, a hole or a small boss. It works well on imported STEP bodies.

**Steps**

1. Run Delete Face, or right click a face and choose Delete Face.
2. Click the faces to remove. The helper bar can add every hole wall at once.
3. Choose the option and click OK.

**Options**

1. Delete and Patch: grow the faces around the gap until they meet. This is the usual choice.
2. Delete and Fill: close the gap with one new smooth face. Tangent fill makes it meet its neighbours smoothly.
3. Delete: shown greyed. It would leave an open surface body, which FDCAD does not have yet.
4. **Holes up to**: every round hole of this diameter or smaller is filled too, without picking it. Leave it at 0 to fill only the picked faces.
5. **Fill voids**: closed hollow spaces inside the body are filled, so the solid keeps only its outer skin.

With Holes up to or Fill voids you can leave the picked faces empty, to make a simpler body for export or sharing.

**Common errors**

1. A face cannot be removed. The message names it. With several faces, the "Keep the faces that worked" button removes the others. Nothing changes until you click it.
2. "The faces around X cannot grow to close the gap." The faces round the gap would only grow into an open tube, as on the flat end of a boss or a loft. Pick the whole feature (every face of a boss or hole) or pick fewer faces. On a part with free form faces, such as a loft or a thread, or with very many faces, this is said at once instead of after minutes of work.
3. The feature "changed nothing": removing the picked faces let the faces next to them grow back into their place, for example when only one face of a hole in two faces was picked. Pick every face of the hole or boss.

The same help comes with other tools that take many picks. Move Face with several faces names the faces that cannot move and offers "Keep the faces that worked". A Hole on the points of an existing sketch says how many holes cannot be cut and offers "Cut the holes that work", which skips those points; click a skipped point in the Hole panel to cut it again.

Next, see [Patterns and bodies](patterns-and-bodies.md) to repeat features and work with several bodies.

## Split Line

**Split Line** divides faces into regions with new edges. The volume does not change. Use the new edges for a fillet, or the regions for Draft, Move Face or a colour.

**Steps**

1. Right click a face in the view and choose Split Line. Click more faces to split.
2. Choose the method. Projection: choose a sketch; its curves are projected onto the faces along the sketch normal (Reverse and Both directions as for Projected Curve). Intersection: click the Plane list, then a flat face; the faces are split where its plane crosses them. Or click the Splitting body list and a face of another body: the faces are split where that body's faces cross them. Silhouette: click the Direction of pull list and a plane, flat face or straight edge; each picked cylinder, cone or sphere is split along its outline seen along that direction (a cone only when its axis is square to the pull).
3. Click OK. Deleting the feature joins the faces again.

## Push Pull

**Push Pull** moves flat faces, or the regions of a closed sketch on a face, by a signed distance. A positive distance adds material and a negative one cuts, so there is no Boss or Cut choice.

**Steps**

1. Right click a flat face in the view and choose Push Pull. Click more faces to give them the same distance, or choose a sketch on a face instead.
2. Type the distance, or click Next Parallel Face to step through the faces parallel to the first one, nearest first. The chosen face becomes the target and the distance is measured to it.
3. For a sketch, tick Symmetric to push the region half each way from its sketch.
4. Click OK.

## Replace Face

**Replace Face** swaps faces for a flat target. The body under the faces is extended up to the target where the faces lie short of it, and trimmed back where they stick out past it. A common use is flattening a bumpy imported face onto a plane.

**Steps**

1. Right click a face in the view and choose Replace Face. The face is listed in Faces to Replace.
2. Click more faces to replace if needed, then click a flat face as the target. Click a list first to send the next picks to it.
3. Click OK.

**Common errors**

1. "The target must be a plane or a flat face." A curved target is not supported.
2. The picked faces already lie on the target. Pick other faces or another target.

## Face Relations

**Face Relation** (Features tab, Direct Editing group, beside Merge Faces) keeps a relation between faces of a body, which is most useful on an imported body with no history. Choose the **Relation**, click the faces and click OK. The relation shows in the feature tree; it does not change the part, and it warns when the faces no longer meet it. Every Move Face below it in the tree keeps it:

* **Coplanar**: two flat faces on one plane. Moving one moves the other with it.
* **Offset**: two parallel flat faces keep their distance, so an offset of one face of a wall moves the whole wall.
* **Concentric**: two round faces on one axis. Translating or rotating one takes the other along.
* **Parallel** and **Perpendicular**: rotating one flat face turns the other with it.
* **Equal radius**: two round faces keep one radius when one is offset or resized.
* **Fixed**: the faces may not move; a Move Face that picks one fails and says which relation holds it.

Suppress or delete a relation to stop it. To list the relations together, put them in a folder of the feature tree.

## Merge Faces

**Merge Faces** (Direct Edit group, beside Delete Face) makes one face of faces that lie on one surface and removes the edges between them. Imports and Delete Face can leave such edges, and later fillets and drafts can fail on them.

1. Pick the faces, or an edge between two faces, and choose **Merge Faces**.
2. Click OK. Every other edge stays.

Options: **Tolerance** and **Angle tolerance** say how far apart, and how far turned, faces may be and still count as one surface. Raise them a little for imported parts.

Common error: "The faces do not lie on one surface." Raise the tolerance, or pick only faces on one surface.

## Edge Profile

**Edge Profile** cuts a router shape round a face or along edges, as a woodworker's router would.

1. Click **Edge Profile** on the 3D Print tab.
2. Click a flat face to run the profile round its outer edge, or pick a chain of joined edges in **Edges**.
3. Pick the **Profile**: Round over (a rounded corner), Cove (a hollow), Rabbet (a step), Chamfer with flat (a 45 degree chamfer ending in a small flat) or Ogee (an S curve).
4. Enter the **Size** across the face and, for Rabbet and Chamfer with flat, the **Depth** down the side.
5. Click OK.

Tips:

- Corners of the loop get round joins, so the profile wraps round a rectangle's corners.
- The profile starts on a straight edge between flat faces. On a face with rounded corners it follows the curves.

## Lightening Pockets

**Lightening Pockets** takes weight out of a plate: the face is pocketed as triangles between ribs, with a solid border kept round the edge and the holes.

1. Click **Lightening Pockets** on the 3D Print tab and click the flat face of the plate.
2. Set the **Border** kept solid along the outer edge and round holes, the **Web** (rib width) and the **Cell size** (the triangles' side).
3. Set a **Corner radius** to round the pockets' corners, and a **Pocket depth**, or 0 to cut right through.
4. Click OK.

Tips:

- The cell must be more than twice the web. Pockets too small to round are left solid.
- Triangles make a stiff plate for their weight. Larger cells save more weight; thicker webs keep more strength.

## Landing Pad

**Landing Pad** gives a sloped or curved wall a flat spot, for a screw boss, a switch or a label on a curved housing.

1. Make a plane where the flat face of the pad should be, its normal pointing out of the wall, and sketch the pad's outline on it.
2. Click **Landing Pad** on the 3D Print tab. Click the **Wall** and pick the **Sketch**.
3. Pick the **Pad**: Raise builds out from the wall up to the sketch plane; Press sinks into the wall down to the sketch plane.
4. For Press on a thin walled housing, set a **Cup wall**: a cup this thick is kept behind and round the pad so the wall stays closed.
5. Click OK.

Tips:

- Put the boss or hole on the pad's flat face afterwards with a sketch on that face.
- A plane that does not stand off the wall (for Raise) is an error: move the plane outward.

## Knurl

**Knurl** cuts a grip pattern into a round face, such as a knob or a thumb screw.

1. Click **Knurl** on the 3D Print tab and click the cylinder face.
2. Pick the **Pattern**: Straight (V grooves along the axis) or Diamond (two sets of grooves on 30 degree helices that cross).
3. Set the **Pitch**, the groove spacing round the cylinder, and the **Depth** of the grooves.
4. Click OK.

Tips:

- Diamond knurls take some seconds to build: each groove is a helix.
- For printing, a pitch of 1.5 mm or more and a depth of 0.4 to 0.6 mm come out cleanly.

