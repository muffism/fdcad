# View and selection

These tools turn, move and zoom the 3D view, change how the part is drawn, hide and show items, and control what a click selects. You will use them all the time, so the keys are worth learning.

Where to find it: the View menu, the small view toolbar at the top of the 3D view (Zoom to Fit, Zoom to Area, Previous View, Section View, standard views and display style), and the right click menu in the empty 3D view.

On a Mac, read Ctrl as Cmd. These keys keep Control: View Selector (Control+Space), Hide All Reference Geometry (Control+H), Show All Hidden Bodies (Control+Shift+Tab) and Force Rebuild (Control+Q).

## Mouse and keys

Use the mouse or the keyboard to move around the part.

**Mouse**

1. Wheel: zoom at the cursor.
2. Middle drag: rotate.
3. Ctrl and middle drag: pan.
4. Shift and middle drag: zoom (drag up to zoom in).
5. Alt and middle drag: roll.
6. Double middle click: zoom to fit.

The middle button can work three ways (Preferences, View, Middle button): drag turns with Shift to zoom and Ctrl to pan (the default), drag turns with Shift to pan and Ctrl to zoom, or drag pans with Shift to turn and Ctrl to zoom. Alt and middle drag always rolls.

Preferences, View sets the mouse and keys: reverse the wheel, zoom about the pointer or the view centre, how far an arrow key turns the view, how fast a mouse drag turns it, and whether choosing a standard view zooms to fit.

**Trackpad**

Two finger drag rotates, Shift and two finger drag pans, and pinch zooms, with either navigation setting. On a Mac trackpad the two finger rotate gesture rolls the view, a two finger double tap zooms to fit, and a swipe left goes to the previous view (right goes forward again). Choosing Trackpad under Preferences, General, Navigation also turns on the Control and drag gestures (the Windows key and drag on Windows) for a trackpad with no right button.

**Keys (with the 3D view focused)**

1. Arrow keys rotate the view 15 degrees a step.
2. Ctrl and arrow keys pan the view.
3. Shift and arrow keys rotate the view 90 degrees.
4. Alt+Left and Alt+Right roll the view 15 degrees.

**Mouse gestures**

Hold the right mouse button, drag in a direction and release. On a Mac trackpad, hold Control and drag. A guide with the commands appears after a short drag. Release inside the inner circle to cancel. A plain right click, with no drag, opens the right click menu instead.

| Direction | In a part | In a sketch |
| --- | --- | --- |
| Up | Top | Smart Dimension |
| Left | Left | Line |
| Right | Right | Circle |
| Down | Bottom | Corner Rectangle |

Change the gestures in Preferences, on the Gestures tab. You can use 4 or 8 directions.

## Standard views

The standard views look at the part from a fixed direction.

**Steps**

1. Press a key, or choose the view in the View menu or the view toolbar.
2. **Front** (Ctrl+1), **Back** (Ctrl+2), **Left** (Ctrl+3), **Right** (Ctrl+4), **Top** (Ctrl+5), **Bottom** (Ctrl+6), **Isometric** (Ctrl+7), **Dimetric** and **Trimetric** (no keys; set them in the shortcut editor). Dimetric shows two sides alike and the top smaller; Trimetric shows each side at its own angle.

**Tips**

1. Turning to a view is animated. Tick Reduce motion in Preferences, General for instant turns; it also turns off the other interface animations. Until you set it, Reduce motion follows your system: it is on when animations are turned off in Windows, or Reduce motion is on in the Mac's Accessibility settings.

### Your own Front and Home

When a part was drawn lying the wrong way, turn the view until it looks the way the front should, then choose **View > Set Current View As** and pick Front (or another standard view). Every standard view turns with it; the part itself does not move. Pick **Home** in the same list to keep the current direction for **View > Home**, which otherwise shows the isometric view. **View > Reset Standard Views** puts all of them back. The choice is saved in the part, and each change is one undo step.

## Split View

View, Split View shows **One View**, **Two Views Side by Side**, **Two Views Stacked** or **Four Views** of the part. Four views start as Front, Top, Right and Isometric. Each view has its own camera: rotate with the middle button, Ctrl and middle button to pan, the wheel to zoom.

A pick in any view picks the same item in all of them. The view you clicked last is the active view: the standard views, Normal To, Zoom to Fit and Redraw go to it. The other view commands and the arrow keys act on the main view (top left).

## Mirror Image

**Mirror Image** (View menu) shows a see through copy of the part reflected about a plane, to judge whether the part is symmetric. It uses the plane picked in the feature tree, or the Right plane when none is picked. The image follows each rebuild, cannot be picked and is not saved; the part does not change. Choose it again to hide the image.

## Temporary Axes

**Temporary Axes** (View menu) shows a thin dash and dot line through every cylindrical and conical face of the part, drawn over the part. Click one to use it wherever an axis is asked for: a circular pattern axis, a revolve axis (when it lies in the sketch plane), or a plane through an axis. Clicking it picks its round face. While they are shown, sketch tools also snap to the axes that lie in, or show on, the sketch plane.

## Saved views

**Save View** (View menu) keeps the current view under a name in the part file. Saved views are listed after the standard views in the View menu (Saved Views), the view toolbar's views list and the right click View Orientation menu; pick one to go back to it.

View, Saved Views, Manage Saved Views lists them with Go To, Update (store the current view in it), Rename and Delete. Each change can be undone.

## Normal To

**Normal To** (Ctrl+8 or N) turns the view to look straight at the selected item.

**Steps**

1. Select a plane, a flat face, a cylindrical or conical face, or a feature made from one sketch.
2. Press N.

**Tips**

1. Run it again on the same item to turn the view 180 degrees.
2. With nothing selected, the view snaps to the nearest standard direction.
3. On a round face, the view looks along its axis.

**Common errors**

1. "Select a flat face or a plane first, then use Normal To." Select one and try again.

## View Selector

**View Selector** (Ctrl+Space) shows a small cube at the cursor.

**Steps**

1. Press Ctrl+Space.
2. Click a face of the cube for that view, an edge for the view across that edge, or a corner for a corner view.
3. Use the Back, Left and Bottom buttons below the cube for the hidden faces.

## Corner triad

The small axis triad in the lower left corner of the view is also a set of buttons.

**Steps**

1. Click the X, Y or Z arrow to look along that axis from its end.
2. Click the same arrow again to look from the other side.
3. Hold Shift and click an arrow to turn the view a quarter turn about that axis.

## Orientation popup

**View > Orientation** opens a list at the cursor with the standard views, your saved views, the split view layouts and **New View...**, which saves the current view under a name. It has no key yet; set one in the shortcut editor.

## Zoom commands

1. **Zoom to Fit** (F) fits the whole part in the view.
2. **Zoom In** (Shift+Z) zooms in one step. **Zoom Out** zooms out one step; it has no key yet, so set one in the shortcut editor.
3. **Zoom to Area**: drag a box around the area to zoom to.
4. **Zoom to Selection** fits the view to the selected faces, edges or sketch items.
5. **Previous View** (Ctrl+Shift+Z; on a Mac Control+Shift+Z) goes back to the view before the last change.
6. **Redraw** (Ctrl+R) draws the view again.

**Common errors**

1. "Select faces, edges or sketch items first, then use Zoom to Selection." Select something first.

## Display styles

The display style sets how the part is drawn. Choose it in View, Display Style, or in the view toolbar.

1. **Shaded With Edges**: shaded, with its edges drawn. This is the default.
2. **Shaded**: shaded, without edges.
3. **Hidden Lines Removed** (Shift+Q): only the edges you can see.
4. **Hidden Lines Visible** (Shift+H): the edges you can see, and the hidden ones as thin dashed lines in a lighter colour.
5. **Wireframe** (Shift+W): every edge, also the hidden ones.
6. **Toggle Transparency** (Shift+T): makes the part see through, or solid again.
7. **Perspective** (View menu): shows every open part in perspective, so far away edges look smaller. Choose it again for the parallel view. Measure and dimensions show true sizes either way.

The display style is a view setting. It does not change the part and is not an undo step.

### Display quality

**View > Display Quality** sets how finely this part's curved faces are drawn, from 1 (coarse and fast) to 10 (fine). The dialog shows how far the drawn faces may stray from the true shape. Raise it when small round details look jagged. The choice is saved in the part and is one undo step. On parts with many faces the view draws with less smoothing while you turn it, and smooths again when you let go.

### Edge options

Preferences, View sets how edges are drawn.

1. **Smooth edges**: Shown, Dashed or Removed. These are the edges where two faces meet smoothly, such as the sides of a fillet. The choice applies to Shaded with Edges.
2. **Hidden edges**: Dashed or Solid, for Hidden Lines Visible.
3. **Highlight all edges of the feature selected in the tree**: when ticked, picking a feature in the tree draws all its edges in the selection colour.

## Section View

**Section View** cuts the view open so you can see inside. The part does not change. See [Evaluate](evaluate.md) for its options.

## Hide and show

**Hide or Show** (H) hides the selected sketch, plane, axis, point or coordinate system, or shows it again.

**Steps**

1. Select the item in the feature tree.
2. Press H, or right click it and choose Hide or Show.

**Options**

The View menu has a Hide or Show submenu with tick boxes:

1. **Planes**: draw the shown planes.
2. **Origins**: draw the origin.
3. **Sketches**: draw finished sketches.
4. **Sketch Relations**: draw relation tags in sketches.

**Hide All Reference Geometry** (Ctrl+H) hides every shown plane at once. Press it again to show them.

**Tips**

1. The default planes are hidden in a new part. Right click a plane in the tree and choose Show.
2. A sketch used by a feature is hidden. Select it in the tree and press H to see it.
3. Shown and hidden items are saved with the part, and changing them can be undone.

**Common errors**

1. "Select a body, sketch or plane to hide or show it." H hides or shows the bodies of the picked faces first; with no face picked it works on the sketch or plane selected in the feature tree.

## Colours

**Appearance** (Edit menu, no default key) opens a panel to colour the part. Its list holds the selected faces, the solid feature selected in the tree, each body when there are several, and the part.

1. Select faces, or a feature in the tree, or nothing for the whole part.
2. Run **Appearance**.
3. Pick a swatch, or More Colors for any colour. Remove Color goes back to the colour underneath.

The most specific colour wins: a face colour over a feature colour, a feature colour over a body colour, a body colour over the part colour. Colours do not change the geometry, so no rebuild runs. Each change can be undone.

**Copy Appearance** takes the shown colour of the first selected item. **Paste Appearance** puts it on the first selected item, or on the whole part when nothing is selected. Both are in the Edit menu and have no default keys.

## Selecting items

Click a face, edge or vertex in the 3D view to select it. The item under the cursor is highlighted before you click.

1. Ctrl click adds or removes items from the selection.
2. Click empty space to clear the selection.
3. Drag a box from left to right to select only items fully inside it.
4. Drag a box from right to left to also select items the box crosses.
5. Hold Shift while dragging a box to add to the selection. Hold Ctrl to toggle items.

In a part the box selects edges, unless filters are set. In a sketch it selects sketch items and dimensions. A box can start on top of the model: press anywhere and drag, and only a click that does not move picks the item under the pointer.

**Breadcrumbs:** when you pick a face, edge or vertex, the left end of the strip above the view shows where it comes from: the part, its body, the feature that made it and that feature's sketch. Click one to select it in the feature tree, or right click it for its menu.

**Lasso Selection** (Selection menu) draws a free loop instead of a box in the 3D view. Choose it again to go back to the box.

**Paint Selection** (Selection menu) makes a left drag pick every face it passes over, like a brush. Choose it again to go back to the box.

**Pick Bodies Only**, **Pick Faces Only** and **Pick Edges Only** (Selection menu) set the selection filter to that one type at once. Choose the same command again and every type picks again. Give them keys in Preferences if you switch often.

**Pick in Volume** (Selection menu) picks the faces, edges or vertices that are inside, outside or touching a box, cylinder or sphere. The dialog starts with a box round the whole part: type its **Centre** and **Size**, or a **Radius** for a sphere or cylinder (with its **Cylinder axis** and length as the third size). Inside means wholly inside; touching means partly inside and partly outside. The picking runs in the background and replaces the selection; the status bar says how many items were picked.

**Select Previous** (Selection menu) picks again what was picked before you cleared the selection, for example after a stray click in empty space. It works until the part rebuilds, because a rebuild makes new faces. **Invert Selection** picks every face, edge or vertex that is not picked now. With the selection filter on it keeps to the kinds the filter allows; otherwise it keeps to the kinds you had picked (faces when nothing was picked). **Select All** (Selection menu) picks every face of the part, or, when an edge is picked, every edge (the same for vertices); with the selection filter on, it picks every item of the kinds the filter allows. In an open sketch it picks every sketch item. Give these commands keys in the shortcut editor.

**Select Similar** (Selection menu) picks the faces like the first picked face. Choose a setting for each rule: **Same kind and size** (for example every hole wall of one diameter, or every round of one radius), **Parallel** (planes facing the same way, and round faces with parallel axes) and **Same area** (within 5%). Set a rule to Must match to use it, or to Except to take the faces it matches out. With more than one Must match rule, choose whether a face must match every one or any one. For example, Parallel as Must match and Same kind and size as Except picks the hole walls whose axes are parallel to the picked face's normal, without the picked face's own kind.

**Select Their Edges**, **Select Their Faces** and **Select Their Bodies** change what is picked: the edges of the picked faces, the faces next to the picked edges and vertices, or every face of each body that holds a pick.

**Save Selection Set** (Selection menu) keeps the picked faces, edges and vertices under a name, saved in the part. **Selection Sets** lists them. Select a set and click **Pick** (or double click it) to pick what it holds now; items that no longer exist after a change are skipped and counted in the status bar. **New Rule Set** makes a set that picks again by its rule each time: the faces of a feature, the faces of a colour, or the edges at least a length long. **Combine Sets** makes a set from two others: Add, Take away or Keep shared. A set that another set uses cannot be deleted until that set is gone. Saving, combining and deleting sets are undo steps.

1. Draw the loop clockwise to select only items fully inside it.
2. Draw it counter clockwise to also select items it crosses.
3. Shift and Ctrl add and toggle, as with the box.

### Picking through see through bodies

A click on a body drawn see through (Make Body See Through, a body's Transparency, or See Through Bodies in Section View) picks the face, edge or vertex behind it. Hold Shift and click to pick the see through face itself.

### Before and after

While Fillet, Chamfer, Shell or Draft shows the finished part, a small After and Before slider sits at the lower right of the view. Drag it to fade to the part before the feature and back.

## Selection filters

Selection filters limit what a click or a box can select.

**Steps**

1. Press **Selection Filter Bar** (F5) to show the filter bar.
2. Click the types you want to select.
3. Press **Turn Selection Filters On or Off** (F6) to turn the chosen filters off and on again.

**Options**

1. Vertices, Edges, Faces, Solid Bodies, Planes, Axes, Sketches, Sketch Segments, Sketch Points and Dimensions.
2. Clear All and Select All.
3. **Filter Edges** (E), **Filter Faces** (X) and **Filter Vertices** (V) switch one filter quickly.

**Tips**

1. The status bar shows which filters are on.
2. The filters are also in the View menu under Selection Filter.

## Select Other

**Select Other** picks an item that is hidden behind another one.

**Steps**

1. Right click a face, edge or vertex and choose Select Other, or run the command with the cursor over the part.
2. A list shows every item under the cursor, front to back, with a type icon.
3. Hover a row to highlight it. Tab or the mouse wheel steps through the rows.
4. Click a row to select it.

**Tips**

1. Right click a face while the list is open to hide that face for a moment, so you can see what is behind it.

**Common errors**

1. "Nothing under the cursor to choose from." Move the cursor over the part and try again.

## The tree and the view together

Hover over an edge to see its length (and its radius, for a circle or arc) in the status bar, after the pointer's coordinates. Pick one flat face and hover over another to see the angle between them. **View > Collapse All** closes every folder in the feature tree; it has no key yet, so set one in the shortcut editor.

Picking a face, edge or vertex in the view opens the feature tree to the feature that made it and scrolls it into sight; clearing the pick scrolls the tree back. Right click a face or edge and choose **Go To Feature** to select that feature in the tree. Hovering a feature row in the tree shows that feature's faces in the view. Both can be turned off in Preferences, General.

If picking small edges or points is hard, or you pick the wrong thing too often, change **Pick distance** in Preferences, General: Small, Normal, Large or Extra large. It sets how close the cursor must be to a point, edge or vertex, in the 3D view and in sketches.

## Show Types

**View, Show Types** has a tick for each kind of item drawn in the view: planes, axes, points, coordinate systems, curves, and the existing sketches, origins, temporary axes, dimensions and sketch relations. **Hide All Types** turns everything off; choose it again to bring back what was showing. These are view settings and are not saved in the part. The Planes command can be given a key in the shortcut editor to show and hide all planes.

## Select Loop and Select Tangent

Right click an edge of the part:

- **Select Loop** selects the edges around a face through that edge. Choose it again on the same edge for the loop on the next face. With a face picked first, it uses that face, so an edge of a hole gives the hole's inner loop.
- **Start Partial Loop**, then right click the last edge and choose **End Partial Loop Here**: the edges between them along the loop are selected, the shorter way round.

Right click a face or an edge and choose **Select Tangent** to select every face, or every edge, joined to it smoothly. Fillet, Chamfer and the other commands use the selection as it stands.

## Select Faces Between

To pick a whole pocket or region at once:

1. Pick the boundary: the faces or edges around the region, such as the face the pocket opens into.
2. Right click one face inside the region (the seed) and choose **Select Faces Between**.

Every face reached from the seed without crossing a boundary edge or entering a boundary face is selected; the boundary faces are not. The status line says how many. If the boundary does not close the region, the pick spreads further, so check the count.

## Right click to move on

While a panel with several pick boxes is open (patterns, Move Face, Combine and the other body tools), right click in the 3D view to move to the next pick box; the status bar names it. When the last box is active, right click shows OK and Cancel.

## Turning about a point

Middle click (press and release without moving) on a face, edge or vertex: from then on, dragging with the middle button turns the view about that point. Middle click off the part to turn about the view's centre again. In Preferences, General, **Turn style** sets how the view turns: **Free** (the default), **Turntable (Z stays up)** keeps the model's Z axis pointing up while you turn, and **Arcball** rolls the model like a ball under your pointer, so a drag round the edge of the view rolls it about your line of sight.

## Screen readers and large controls

- The main areas (3D view, sketch editor, feature tree, panels) have names screen readers announce.
- View, **Describe Part** opens a summary a screen reader reads out: the part's name, the number of bodies, the overall size and every feature in order, with suppressed features and errors named.
- Tick **Large controls** in Preferences, General to make the command tab buttons and the tree rows half as large again, for easier clicking.

