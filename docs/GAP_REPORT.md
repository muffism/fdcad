# Gap report: TOOL_SPEC.md against the phase1 code

Audit of every [P1] item in `docs/TOOL_SPEC.md` and owner test notes 1 to 10, against branch `phase1` at commit `9aab8fb`. Audit only: no code in `src/` or `tests/` was changed.

## How this was checked

1. Read `CLAUDE.md`, `SHORTCUTS.md`, `docs/WORKFLOW_SPEC.md`, `docs/TOOL_SPEC.md`, `PLAN.md`, `DECISIONS.md` and the code under `src/fdcad`.
2. Ran the full test suite on the Qt offscreen platform: 526 passed, 1 failed. The failure is `tests/perf/test_budgets.py::test_startup_and_empty_part_memory` (456 MB against a 400 MB budget) in this Linux container. CI targets are Mac and Windows, so this may be specific to the container; it should be checked on CI.
3. Drove the main window and the sketch canvas with throwaway offscreen scripts (`QT_QPA_PLATFORM=offscreen`) to prove each finding. The scripts are not committed. Their results are quoted below as "probe".

Status words: **DONE** works as written. **PARTIAL** some of it works; the gap is named. **MISSING** not built. **BUG** built but wrong, with steps to reproduce.

## Summary

| Status | Count |
|---|---|
| DONE | 36 |
| PARTIAL | 59 |
| MISSING | 52 |
| BUG | 5 |
| Total rows | 152 |

Counts cover the rows of the table in section 1 (spec items and owner notes). Rule only items (T12.1) are not counted.

Top problems:

1. Owner note 8 (bug): model circle centres only snap if a mouse move event lands within 8 px of the circle edge first. Real mice skip pixels, so the reveal often fails. Even when it works, no relation is added, so the circle is not tied to the part. Root cause in section 1A.
2. Owner note 2 (bug): the value box of a new dimension opens near the middle of the sketch canvas, not at the dimension. `SketchCanvas.edit_dimension` reads label positions before they are painted.
3. Selected regions (note 9) cannot be built as written: crossing curves are a sketch error today (D68), and there is no trim tool in Phase 1.
4. No right click menus in the 3D view or the sketch canvas (note 6). Right click in the 3D view opens the shortcut bar instead.
5. Smart Dimension is missing most of T4: no Dimension panel (note 3), no circle rules beyond circle plus line (note 10), no preview before placement, no wheel stepping, no reference toggle or over define prompt, and Esc keeps a new dimension.

## 1. Item by item

Evidence names a file and function, then the test that covers it where one exists. "canvas" means `src/fdcad/ui/sketch_tools/canvas.py`, "tools" `src/fdcad/ui/sketch_tools/tools.py`, "edit" `src/fdcad/ui/sketch_tools/edit.py`, "inference" `src/fdcad/ui/sketch_tools/inference.py`, "panel" `src/fdcad/ui/property_panel/panel.py`, "sketch panel" `src/fdcad/ui/sketch_tools/panel.py`.

### T1. Common sketch behaviour

| Item | Status | Evidence | What is missing or wrong |
|---|---|---|---|
| T1.1.1 tool stays active | DONE | tools `Tool.after_commit`, `LineTool.after_commit`; test `test_line_chain_with_auto_relations` | |
| T1.1.2 ways to end a tool | PARTIAL | canvas `keyPressEvent`, `mouseReleaseEvent`; `sketch_mode.SketchMode._panel_ok`; test `test_ways_to_end_a_sketch_tool` | Esc, button again, other tool, Select and panel OK work. Right click ends the tool at once (or drops the shape in progress) instead of showing a menu with "Select" first. |
| T1.1.3 click click and click drag | MISSING | canvas `mouseReleaseEvent` does nothing for tools | Only click click works. Press, drag, release places the first point and ignores the release. |
| T1.1.4 left panel shows the tool panel | PARTIAL | `sketch_mode.SketchMode.open` shows `SketchPanel` | The same sketch panel shows for every tool. There is no per tool panel (see T7.2). |
| T1.2 intro: snapping in every tool, Smart Dimension and drag | PARTIAL | canvas `_snap_at` is called only when `self.tool` is set | Drawing tools snap. Smart Dimension uses `pick` (no snap marker, no model centres). Dragging geometry (`_drag_move`) never snaps. |
| T1.2.1 snap targets | BUG | inference `find_snap`, canvas `_snap_at`, `reveal_centres`; tests `test_midpoint_center_quadrant`, `test_hovering_a_circle_reveals_its_centre` | Origin, end points, sketch circle and arc centres, line midpoints, quadrants, intersections and nearest point work (probe: 12 of 12 centre snaps in Line, Circle, Point and Center Rectangle). Bug: model circle centres reveal unreliably (owner note 8, section 1A). Missing: arc midpoints. Sketch centres are always snappable and always drawn as a dot, not hidden until the curve is hovered. Fixed later: the snap fixes worker (WP0), D124 and D250. |
| T1.2.2 model geometry snaps | PARTIAL | canvas `_snap_at` (revealed model centres), `reference_line_at` and edit `reference_line` (D113) | Only edges cut by the sketch plane are known (`core/sketch/reference.plane_section`), nothing is projected. Model vertices and edges are not snap targets for drawing. Model centres snap with no relation (D110 item 6 says so, the spec says add a relation to a fixed copy). Straight edges work only as Smart Dimension picks. |
| T1.2.3 priority | DONE | inference `find_snap` rank and score | Midpoints rank above quadrants; the spec puts them in one tier. Harmless. |
| T1.2.4 feedback | DONE | canvas `_paint_snap`, `strings.SNAP_LABELS` | A square plus a text label ("Center") rather than a symbol. The origin is labelled "Endpoint". |
| T1.2.5 alignment guides | PARTIAL | inference `_aligned` | Guides only to sketch points and only when no other snap is in range. No guides to revealed model centres. |
| T1.2.6 direction snaps | PARTIAL | inference `line_direction` (3 degrees) | Horizontal and vertical only, Line tool only. No parallel or perpendicular snaps. |
| T1.2.7 Ctrl turns snapping off | MISSING | canvas `mouseMoveEvent` ignores modifiers in tools | |
| T1.2.8 snap settings (first three) | MISSING | `ui/preferences/settings.py`, `ui/preferences/dialog.py` have no Sketch page | |
| T1.3.1 automatic relations | PARTIAL | edit `attach`, `SketchEdit.add_line`, tools `TangentArcTool.commit`; test `test_line_chain_with_auto_relations` | Coincident, point on curve, midpoint, centre coincident, horizontal and vertical (Line tool) and tangent arc work. Missing: parallel and perpendicular. A circle drawn from a centre gets coincident centres, not Concentric (same geometry). |
| T1.3.2 relation tags | PARTIAL | canvas `tag_items`, `_paint_relations`, `tag_at`; test `test_relation_tags_and_ctrl_click_relations` | Tags and hover names work. Clicking a tag does not select the relation, so Delete cannot remove it. Point to point coincident tags are hidden by design (D110 item 7). |
| T1.3.3 automatic relations off | MISSING | no setting | |
| T1.4.1 state colours | DONE | canvas `_color`, `_paint_dimensions`; `ui/themes/theme.py` | Selected uses a fixed orange (`_SELECT`), not the theme accent from D111. |
| T1.4.2 end point dots | DONE | canvas `_paint_sketch` | |
| T1.4.3 status bar and tree marks | PARTIAL | `sketch_mode.SketchMode._edited` | Status bar works. The tree has no "(-)" or "(+)" prefix. |
| T1.4.4 over define prompt, reference dimensions | MISSING | no code sets `Dimension.driving` to False; solver `add_dimension` already skips driven ones (`test_driven_dimension_only_measures`) | No prompt, no Make Reference, no driven value update in the UI. An over defining dimension just turns the sketch red. |
| T1.5.1 exit and keep | PARTIAL | `window.MainWindow.confirm_ok`, `sketch.exit` command | Corner and Exit Sketch work. No right click item. |
| T1.5.2 exit and discard | PARTIAL | `sketch_mode.SketchMode.cancel` | Confirmation works. The view does not return to where it was before the sketch opened. |

### T2. Sketch tools

| Item | Status | Evidence | What is missing or wrong |
|---|---|---|---|
| T2.1.1 line chain | DONE | tools `LineTool`; test `test_line_chain_with_auto_relations` | |
| T2.1.2 end chain, close loop | PARTIAL | canvas `mouseDoubleClickEvent`, `keyPressEvent`; tools `LineTool.after_commit` | Double click and Esc end the chain; ending on any existing point stops it. No "End Chain" menu item (right click ends the chain directly). |
| T2.1.3 line to arc switch | MISSING | | No switch, no command for the shortcut editor. |
| T2.1.4 line panel options and values | MISSING | sketch panel has only Construction | No orientation, no length or angle fields. |
| T2.1.5 length and angle at the cursor | MISSING | canvas `_paint_preview` draws no text | |
| T2.2.1 centerline | DONE | tools `make_tool("centerline")` | Drawn dash dot rather than dashed. |
| T2.2.2 centerline uses | PARTIAL | panel `_fill_axes`; test `test_revolve_uses_a_lone_centerline` | Revolve axis works. Symmetric works only for two points. Doubled distance is missing. |
| T2.3.1 corner rectangle | DONE | tools `CornerRectangleTool`, `add_closed_rectangle`; test `test_corner_rectangle_closes_and_extrudes` | |
| T2.3.2 centre rectangle | PARTIAL | tools `CenterRectangleTool`; test `test_center_rectangle_is_symmetric` | Diagonals and centre point work. Shift for a square (with Equal) is missing. |
| T2.3.3 corners snappable | DONE | corners are sketch points | |
| T2.4.1 centre circle | PARTIAL | tools `CircleTool`; test `test_circle_and_arcs` | Works. The centre is a dot, not a plus mark. |
| T2.4.3 circle panel values | MISSING | sketch panel | No centre X, Y or radius fields. |
| T2.5.1 centre point arc | DONE | tools `CenterArcTool`; test `test_circle_and_arcs` | |
| T2.5.2 tangent arc | PARTIAL | tools `TangentArcTool`; test `test_tangent_arc_continues_a_line` | Tangent only. No normal arc, no switch by returning to the end point. |
| T2.5.3 3 point arc | DONE | tools `ThreePointArcTool` | |
| T2.5.4 arc centres shown and snappable | PARTIAL | canvas `_paint_sketch`, `_paint_preview` | Centre dot always shown and snappable; the revealed cross shows only while a drawing tool is active. |
| T2.6 point | DONE | tools `PointTool` | Points are stored with `construction` False; they never join profiles because profiles use curves only. |
| T2.7 construction toggle | PARTIAL | edit `toggle_construction`, sketch panel `_toggle_construction`, command `sketch.construction`; test `test_undo_redo_delete_and_construction` | Panel and command work. Not on a context toolbar or right click menu (neither exists in a sketch). |
| T2.8 dragging geometry | DONE | canvas `_drag_move`, edit `drag_to`, `drag_radius`; tests `test_drag_keeps_relations`, `test_edit_existing_sketch_and_drag` | No snapping while dragging (see T1.2 intro). |

### T3. Relations

| Item | Status | Evidence | What is missing or wrong |
|---|---|---|---|
| T3.1 Horizontal and Vertical | PARTIAL | edit `relations_for`; solver `_orient`; test `test_horizontal_and_vertical_points` | Lines work. Points work only as exactly two; the spec says two or more. |
| T3.1 Collinear | PARTIAL | solver `rel_collinear` | Two lines only. |
| T3.1 Parallel | DONE | solver `rel_parallel`; test `test_parallel_perpendicular_collinear` | |
| T3.1 Perpendicular | DONE | solver `rel_perpendicular` | |
| T3.1 Tangent | DONE | solver `rel_tangent`; test `test_tangent_concentric_equal` | |
| T3.1 Coincident | PARTIAL | solver `rel_coincident`; test `test_point_on_line_circle_and_arc` | Sketch points, curves and the origin work. No model points. |
| T3.1 Midpoint | PARTIAL | solver `rel_midpoint` | Point and line only. Point and arc is missing in the solver and in `relations_for`. |
| T3.1 Concentric | PARTIAL | solver `rel_concentric` accepts a point; edit `relations_for` | Offered for exactly two circles or arcs. Point plus circle is not offered; three or more is not allowed. |
| T3.1 Coradial | MISSING | not in `core/sketch/model.RELATION_TYPES` | |
| T3.1 Equal | DONE | solver `rel_equal`; test `test_equal_circles_and_lines` | |
| T3.1 Symmetric | PARTIAL | solver `rel_symmetric`; test `test_midpoint_and_symmetric` | Two points and a line only. No lines or arcs. |
| T3.1 Intersection | MISSING | not in `RELATION_TYPES` | |
| T3.1 Fix | DONE | solver `rel_fixed` | |
| T3.1 note 1 infinite line | DONE | probe: a point made coincident with a 10 mm line moved to x 20 on its extension | |
| T3.1 note 2 full circle of an arc | DONE | probe: a point went to the lower half of an upper half arc's circle | |
| T3.1 note 3 model geometry | PARTIAL | edit `reference_line` (D113) | Straight edges in the plane only, as fixed copies, through Smart Dimension. |
| T3.2.1 Ctrl click, Add Relations | PARTIAL | sketch panel `_fill_relations`, `add_relation`; test `test_relation_tags_and_ctrl_click_relations` | Works for sketch items. Model edges and vertices cannot be selected in the sketch. |
| T3.2.2 relations on the context toolbar | MISSING | `main_window/context_bar.py` hides while editing (`_busy`) | |
| T3.2.3 origin plus point | PARTIAL | edit `relations_for` | Probe: Ctrl click origin and a point offers Horizontal, Vertical, Coincident and Fix. The owner's failure did not reproduce (see note 5). |
| T3.2.4 existing relations and selection state | PARTIAL | sketch panel `_fill_existing`, `_delete_relation` | List works with one Delete button (deletes the current row) rather than a button per row. The selection's own state is not shown. |
| T3.3.1 Relations panel with filter | MISSING | | The only relations control is the View menu toggle for tags. |
| T3.3.2 select row, Delete, Delete All | MISSING | | |

### T4. Dimensions

| Item | Status | Evidence | What is missing or wrong |
|---|---|---|---|
| T4.1 tool behaviour (stays active, Esc) | PARTIAL | canvas `_dimension_click`, `keyPressEvent` | Stays active. First Esc clears all picks, not just the last one. |
| T4.1 line length | PARTIAL | edit `smart_dimension` | A single line also gets horizontal or vertical projections from the text position, like two points. The spec says a line gives its length. |
| T4.1 straight model edge | DONE | canvas `reference_line_at`; test `test_box` | |
| T4.1 two parallel lines | DONE | edit `smart_dimension`, `_parallel` | |
| T4.1 angle between lines | PARTIAL | edit `smart_dimension` | Angle is added but the text position does not choose which of the four angles. |
| T4.1 point and line | DONE | edit `smart_dimension` | |
| T4.1 two points by placement | DONE | edit `smart_dimension`; test `test_block` | |
| T4.1 circle diameter | DONE | edit `smart_dimension` | |
| T4.1 arc radius | DONE | edit `smart_dimension` | |
| T4.1 circle or arc with any other item | PARTIAL | edit `centres_for_distance` | Only circle or arc plus line. Probe: circle plus point, circle plus circle and circle plus origin all give "not possible". |
| T4.1 doubled distance to a centerline | MISSING | | |
| T4.2.1 dimension follows the cursor before placing | MISSING | canvas `_dimension_click` adds the dimension on the placing click | |
| T4.2.2 value box beside the dimension | BUG | canvas `edit_dimension`; test `test_smart_dimension_value_box` does not check the position | New dimensions: the box opens near the canvas centre (section 1A, note 2). Double click opens it correctly. No Reverse and no spin increment control. Fixed later (D117). |
| T4.2.3 wheel and arrows step | MISSING | `value_box.ValueBox` | |
| T4.2.4 expressions, Enter, Esc | BUG | canvas `_commit_editor`, `_close_editor` | Expressions, units and Enter work. Esc closes the box but keeps the new dimension. Steps: Smart Dimension, pick a line, place, press Esc; the dimension stays (probe). Fixed later (D117): Esc removes a new dimension. |
| T4.2.5 Dimension panel | MISSING | | Owner note 3. |
| T4.3.1 measure to the centre by default | PARTIAL | edit `centres_for_distance` | Only with a line. |
| T4.3.2 Measure to: Centre, Nearest, Farthest | MISSING | | Needs a new dimension field and solver support. |
| T4.4.1 double click opens the box | DONE | canvas `mouseDoubleClickEvent`; `main_window/feature_dims.py`; tests `test_smart_dimension_value_box`, `test_feature_dimensions_on_the_model` | |
| T4.4.2 drag dimensions | MISSING | canvas `_dimension_geometry` uses a fixed offset | D72 says label positions are automatic and not stored. |
| T4.4.3 Delete removes a dimension | DONE | canvas `delete_selection`, edit `delete` | |
| T4.4.4 right click on a dimension | MISSING | | |

### T5. Extrude and Extruded Cut

| Item | Status | Evidence | What is missing or wrong |
|---|---|---|---|
| T5.1.1 header | DONE | panel `PropertyPanel.__init__`; test `test_extrude_layout_groups_and_tooltips` | |
| T5.1.2 From group | PARTIAL | panel `_build` | From holds the sketch choice. No Sketch plane or Offset option. |
| T5.1.3 Direction 1 | PARTIAL | panel `_build`; `core/features/extrude.ExtrudeFeature.tool`; tests `test_cut_offers_through_all_and_hides_depth`, `test_through_all_needs_cut` | Reverse, Blind, Mid Plane, Through All for cuts and Merge work. Through All for bosses is refused by the core. The depth field has no wheel or arrow stepping. |
| T5.1.4 Direction 2 | PARTIAL | panel `_build`, `_update_visibility`; test `test_direction2_tick_sets_two_directions` | Tick box and a second depth work. No end condition list in Direction 2 (Blind only). |
| T5.1.5 Cut Outside | MISSING | | |
| T5.1.6 Selected Regions group | MISSING | | See T5.3. |
| T5.2.1 preview on every change | DONE | `viewport/preview.py` `PreviewController`; test `test_preview_follows_panel_values` | |
| T5.2.2 arrow handle and ruler | PARTIAL | `viewport/widget.py` `_drag_handle`; test `test_dragged_handle_updates_the_typed_value` | Live drag works. No ruler, no tick snapping. |
| T5.2.3 clickable value beside the handle | MISSING | widget `_show_callout` draws a text label only | Owner note 7. |
| T5.2.5 drag past the plane flips | MISSING | preview `value_limits` clamps at 0.01 mm | |
| T5.3.1 regions from crossing and nested curves | MISSING | `core/sketch/topology.check` rejects crossings | Probe: two overlapping circles give "Curves cross each other". Nested loops already become a face with a hole. |
| T5.3.2 hover and click regions | MISSING | | |
| T5.3.3 several regions, empty means all | MISSING | | The "empty" behaviour is today's only behaviour. |
| T5.3.4 picks stored by name, lost pick error | MISSING | | |
| T5.3.5 shared sketch and link icon | PARTIAL | D110 item 3 allows a used sketch to be picked again | No link icon under the second feature. |
| T5.3.6 for all four features | MISSING | | |

### T6. Revolve and Revolved Cut

| Item | Status | Evidence | What is missing or wrong |
|---|---|---|---|
| T6.1.1 axis box | DONE | panel `_fill_axes`, `set_axis_edge`; tests `test_revolve_picks_the_only_centerline`, `test_clicking_a_straight_edge_sets_the_axis` | |
| T6.1.2 Direction 1 | PARTIAL | panel `_build`; `main_window/new_feature.py` default 360 | Works. Angle field has no wheel or arrow stepping. |
| T6.1.3 Direction 2, total at most 360 | DONE | `core/features/revolve.RevolveFeature._build` | No test checks the 360 degree limit. |
| T6.1.4 Merge, Cut Outside, Selected Regions | PARTIAL | panel `_merge_applies` | Merge works. Cut Outside and Selected Regions are missing. |
| T6.2.1 profile crosses the axis | PARTIAL | revolve `_check_one_side`; test `test_profile_crossing_axis_is_rejected` | Error text lacks "or pick regions on one side". The crossing is not highlighted. |
| T6.2.2 profile touching the axis | DONE | revolve `_check_one_side` skips points on the axis; test `test_turned` | |
| T6.2.3 several centerlines | PARTIAL | `strings.CHOOSE_AXIS` | A message shows, but with different wording from "Pick the axis of revolution". |
| T6.3.1 arc handle and angular ruler | PARTIAL | widget `_drag_handle`, D112; test `test_revolve_preview_has_a_curved_angle_handle` | Handle works. No ruler, no 5 degree snapping. |
| T6.3.2 clickable angle value | MISSING | | Owner note 7. |
| T6.4 radius or diameter to the axis | MISSING | | |

### T7 to T12. Panels, toolbars, menus, shortcuts, preferences

| Item | Status | Evidence | What is missing or wrong |
|---|---|---|---|
| T7.1 panel replaces the tree, tab strip to peek | DONE | `window.MainWindow.show_side_panel`, left tab widget | |
| T7.2 sketch tool panels | MISSING | | |
| T7.3 entity panel with no tool | PARTIAL | sketch panel | Relations, add relations, Construction and Fix (as a relation button) work. No parameter fields. |
| T7.4 Dimension panel on selection | MISSING | | |
| T8.1 context toolbar shows and fades | PARTIAL | `context_bar.ContextBar.offer`, `_fade`; test `test_context_toolbar_for_planes_sketches_faces_and_features` | Works for tree rows and faces. Never shows inside a sketch. |
| T8.2 contents by selection | PARTIAL | `ContextBar.for_tree`, `for_faces` | Plane: has Extrude, lacks Hide or Show. Feature: Edit Feature only. Sketch: lacks Revolve. Sketch entities: nothing. Contents follow D110 item 9, not the spec. |
| T8.3 right click adds the full menu | MISSING | | |
| T9.1 empty viewport menu | MISSING | `window.MainWindow.viewport_menu` opens the shortcut bar | |
| T9.2 empty viewport in a sketch | MISSING | canvas has no menu | |
| T9.3 while a sketch tool is active | MISSING | canvas `mouseReleaseEvent` ends the tool | |
| T9.4 while a feature panel is open | PARTIAL | `window.MainWindow.corner_at_cursor` | OK and Cancel only. No Reverse Direction or view items. |
| T9.5 plane menu | PARTIAL | `tree/feature_tree.FeatureTree._context_menu` | Tree only: Sketch, Hide or Show. No Normal To, no Rename, nothing in the viewport. |
| T9.6 face menu | MISSING | | |
| T9.7 edge or vertex menu | MISSING | | |
| T9.8 sketch entity menu | MISSING | | |
| T9.9 dimension menu | MISSING | | |
| T9.10 feature menu | PARTIAL | `FeatureTree._context_menu`, `FeatureTree.delete` | Tree only: Edit Feature, Edit Sketch, Rename, Delete, Roll Back. No Hide or Show Sketch. Delete warns about children but does not ask whether to keep the sketch. Nothing in the viewport. |
| T9.11 sketch in tree menu | DONE | `FeatureTree._context_menu` | |
| T9.12 Shift+F10 and Menu key | MISSING | | |
| T9.13 Select Other | MISSING | widget `mouseReleaseEvent` Alt click cycles the next detected shape only | |
| T10.1 shortcut bar | PARTIAL | `main_window/actions.Actions.shortcut_bar`; test `test_shortcut_bar_lists_context_commands` | A plain menu: arrows, Enter and Esc work. No search box. |
| T10.2 right drag gestures | PARTIAL | widget `mouseReleaseEvent`, canvas `mouseReleaseEvent`, `Actions.gesture`; test `test_gestures_run_commands` | Gestures run. No guide is shown while dragging, so "release inside the guide cancels" cannot work. Plain right click is kept apart by a 6 px threshold. |
| T12.2 shortcut editor | PARTIAL | `preferences/input_editors.py` (owner warning, `reset_all`); test `test_shortcut_editor_moves_a_key_and_saves` | Editor works. The new commands in T12.4 and the line to arc switch are not registered. |
| T12.3 built keys | DONE | `input/commands.COMMANDS`; test `test_window_uses_shortcuts_md` | Every key listed in T12.3 is present. |
| T12.4 missing keys and commands | MISSING | `input/commands.COMMANDS` | None of Ctrl+Space (view selector), H, Ctrl+H, F3, I, Ctrl+T, Shift+Tab, Ctrl+Shift+Tab exist, and their commands do not exist either. |
| T12.5 keys inside tools | PARTIAL | canvas `keyPressEvent`, panel `keyPressEvent` | Esc and Enter work. Line to arc command missing. |
| T11.1 normal to on open (setting) | PARTIAL | `sketch_mode.SketchMode.open` always turns | Behaviour is on; there is no setting. |
| T11.2 show centres (setting) | MISSING | | |
| T11.3 end point dots (setting) | MISSING | | Dots always drawn. |
| T11.4 snapping, model snaps, auto relations (settings) | MISSING | | Same gap as T1.2.8. |
| T11.5 over defining dimension choice | MISSING | | |

### Owner test notes

| Note | Status | Evidence | What is missing or wrong |
|---|---|---|---|
| 1 snap to model geometry | PARTIAL | canvas `_snap_at`, `reference_line_at` | Model centres in the plane only (unreliable, no relation); straight in plane edges only for Smart Dimension. No projection of off plane edges, vertices or the part origin. |
| 2 value box beside a new dimension | BUG | canvas `edit_dimension` | Section 1A. Fixed later (D117). |
| 3 Dimension panel | MISSING | | |
| 4 snap to the origin with Coincident | PARTIAL | inference `find_snap`, edit `attach` | Probe: all 7 drawing tools snap to the origin and add Coincident. Not reproduced. Likely causes of the report: the origin is a 3.5 px dot under the axis lines with no symbol; the snap label says "Endpoint"; the Coincident tag is hidden (D110 item 7), so nothing confirms the relation. On worker/snap-fixes. |
| 5 origin plus point relations | PARTIAL | edit `relations_for`, sketch panel | Probe: Ctrl click origin and a point offers Horizontal, Vertical, Coincident. Not reproduced. Likely cause: the origin is hard to see and hit; the tree's Origin row is not the sketch origin. On worker/snap-fixes. |
| 6 right click menus everywhere | PARTIAL | `FeatureTree._context_menu` | Tree menus exist. Viewport and sketch menus missing (T9). |
| 7 clickable value at the handle | MISSING | widget `_show_callout` | |
| 8 snapping to circle and arc centres | BUG | canvas `_snap_at`, `reveal_centres` | Section 1A. On worker/snap-fixes. Fixed later: WP0, D124 and D250. |
| 9 selected regions | MISSING | | Blocked by spec question Q1. |
| 10 circle dimensions | PARTIAL | edit `smart_dimension`, `centres_for_distance` | Diameter alone and circle plus line (to the centre) work. Circle plus point, circle, origin or edge does not. No Measure to. |

## 1A. Root causes of the two bugs

### Owner note 8: no snapping to circle and arc centres

What works (probe): in a sketch, circle, centre point arc and 3 point arc centres snap in Line, Circle, Point and Center Rectangle, with a Coincident to the centre point. Sketch centres are ordinary sketch points, so `find_snap` always offers them.

What fails, all in `SketchCanvas._snap_at` and `SketchCanvas.reveal_centres`:

1. **The reveal needs a mouse event right on the edge.** A model circle (from `plane_section`, the case in the Block test) becomes snappable only after one `mouseMoveEvent` lands within `PICK_PX` (8 px) of its edge. Mouse moves arrive in jumps. Probe, 200 straight approaches from outside to the centre at zoom 4: steps of 10 px 100 percent revealed, 16 px 94, 24 px 64, 32 px 44, 48 px 26. The tests `test_block` and `test_hovering_a_circle_reveals_its_centre` pass because they put the cursor exactly on the edge.
2. **No relation.** The model centre snap is `Snap("center", x, y)` with no relations (by D110 item 6). The circle lands on the centre but is free: a drag moves it off, and the sketch can never be fully defined against the part. The spec (T1.2.2) asks for a relation to a fixed copy, like D113 does for edges.
3. **Only while a drawing tool is active.** Smart Dimension and plain selection never call `_snap_at`; `pick` ignores `reference_circles`, so a model centre cannot be dimensioned to.
4. **Short memory.** `revealed` keeps the newest 3 centres and sketch circles share it, so hovering sketch circles pushes model centres out.
5. **Only circles in the plane.** `plane_section` finds only edges that lie in the sketch plane. A hole on another face never reveals (this is note 1).

Suggested fix for the worker: test the reveal band against the segment between the previous and current cursor positions (or widen it), keep reveals until the tool ends, add a fixed construction point on a model centre with Coincident (as `reference_line` does for edges, needs D110 item 6 changed), and let `pick` in Smart Dimension use revealed centres.

### Owner note 2: value box away from the new dimension

`SketchCanvas.edit_dimension` calls `self.update()` "to lay out labels" and then reads `self._labels`. `update()` only schedules a paint, so the new dimension has no label rectangle yet and the code falls back to `QRectF(self.width() / 2, self.height() / 2, 80, 20)`. Probe on an 894 x 538 canvas: box at (379, 265), label at (326, 116). Double click on an existing dimension is fine because its label was painted before. Fix: call `repaint()` first, or compute the rectangle from `_dimension_geometry`.

## 2. Proposed build plan

Packages are in build order: each one only needs packages above it. "Weak model OK" marks packages that are small, self contained and well specified enough for a weaker coding model.

| # | Package | Items | Files likely touched | New tests | Size | Risks | Weak model OK |
|---|---|---|---|---|---|---|---|
| WP0 | Snap fixes (already on worker/snap-fixes) | Notes 4, 5, 8; T1.2.1 centre reveal, origin marker and label, T3.2.3 | canvas, inference, edit | Sampled mouse path test for reveal; origin label; relation on model centre | S to M | Model centre relation needs D110 item 6 changed (Q8) | Separate worker |
| WP1 | Value box fixes | Note 2, T4.2.2 position, T4.2.4 Esc removes a new dimension, T4.2.3 wheel and arrows with Ctrl and Alt, spin step | canvas `edit_dimension`, `_close_editor`; `value_box.py` | Box opens at the label of a new dimension; Esc removes it; wheel and arrow steps | S | Must not break double click edit on the model (`feature_dims.py`) | Yes |
| WP2 | Sketch preferences and snap switch | T11.1 to T11.5, T1.2.8 (first three), T1.3.3, T1.2.7 Ctrl | `preferences/settings.py`, `preferences/dialog.py`, canvas | Settings round trip; Ctrl move gives a free snap; auto relations off adds none | S | Settings must reach an open canvas | Yes |
| WP3 | Polish | T1.4.3 tree prefix, T1.5.2 restore view on discard, T10.1 search box, T10.2 gesture guide, T1.4.1 accent colour, T6.2.1 and T6.2.3 wording, T2.4.1 plus mark | `tree/feature_tree.py`, `sketch_mode.py`, `actions.py`, viewport widget, canvas, `strings.py` | One per item | S each | Gesture guide must not slow right drag | Yes, item by item |
| WP4 | Small shortcuts | T12.4 H, Ctrl+H, Ctrl+T, F3 popup; register line to arc command (T12.5) | `input/commands.py`, `window.py`, `tree/feature_tree.py`, `visibility.py` | Each key runs its command and appears in the editor | S | I, Shift+Tab, Ctrl+Shift+Tab depend on Q11 (bodies are Phase 3) | Yes |
| WP5 | Relations completion | T3.1 rows (2 or more points, collinear 2 or more, midpoint on arc, concentric with a point, symmetric lines and arcs, Coradial, Intersection), T1.3.2 tag click and delete, T3.2.4 state, T3.3 Relations panel | `core/sketch/model.py`, `core/sketch/solver.py`, edit `relations_for`, sketch panel, new relations panel, `FDEF_SPEC.md` | Solver test per relation; file round trip; old files open | M | New relation types change the file format (Q5); planegcs support for each | Partly (relations_for and panel yes; solver no) |
| WP6 | Smart Dimension rules | Note 10 and T4.1 circle with any item, T4.3.1, T4.1 Esc drops last pick, T4.1 single line gives length, T4.1 angle quadrant by placement | edit `smart_dimension`, `centres_for_distance`, canvas `_dimension_click`, solver angle | Table driven test over every row of T4.1 | M | Angle quadrant needs a solver change for supplementary angles | Yes, except the angle quadrant |
| WP7 | Snapping completion | T1.2 snapping in Smart Dimension and drag, arc midpoints, T1.2.5 guides to centres, T1.2.6 and T1.3.1 parallel and perpendicular, T2.5.4 | inference, canvas | Unit tests in `test_inference.py`; drag snaps | M | Too many snaps get in the way; keep priority rules | No |
| WP8 | Dimension panel, preview, reference | Note 3, T4.2.1, T4.2.5, T7.4, T1.4.4, T4.3.2 Measure to, T4.1 and T6.4 doubled distance, T4.4.2 drag | canvas, new `sketch_tools/dimension_panel.py`, edit, solver, `FDEF_SPEC.md`, `DECISIONS.md` | Panel shows on tool start and on selection; reference toggle; over define prompt; measure to nearest and farthest; doubled distance | L | D72 (positions not stored) must change for drag (Q4); new dimension data needs file format work (Q5) | No |
| WP9 | Tool panels and line tool | T1.1.3 click drag, T1.1.4, T7.2, T7.3 parameters, T2.1.3 to T2.1.5, T2.3.2 Shift square, T2.4.3, T2.5.2 normal arc | tools, canvas, sketch panel | Click drag equals click click per tool; typed values move geometry; line to arc | L | Typed values must go through the solver, not move points directly | Partly (click drag, Shift square) |
| WP10 | Feature panel completion | T5.1.2 Offset, T5.1.3 Through All for bosses, T5.1.4 Direction 2 end conditions, T5.1.5 and T6.1.4 Cut Outside, value box stepping in fields | panel, `core/features/extrude.py`, `revolve.py`, `solids.py`, `FDEF_SPEC.md` | Volume tests per option; old files open | M | New params change saved files (Q5); Through All boss meaning (Q3) | No |
| WP11 | Drag handle ruler and typed value | Note 7, T5.2.2 ruler, T5.2.3, T5.2.5 flip, T6.3.1, T6.3.2 | viewport widget, `viewport/preview.py` | Click on value opens box; ruler snap steps; flip sets Reverse | M | AIS overlay widgets on a native OpenGL view; no GPU in CI | No |
| WP12 | Context toolbar and right click menus | Note 6, T8, T9, T1.1.2, T1.5.1, T2.1.2, T2.7 menus, T3.2.2, T4.4.4, T9.12, T9.13 | `context_bar.py`, `window.py`, canvas, viewport widget, `feature_tree.py` | Menu content per context (build without exec, as `_context_menu` does) | L | Right click today opens the shortcut bar and ends tools; changes habits; must not clash with gestures (T10.2) | Partly (menu building per context yes; Select Other no) |
| WP13 | View selector | T12.4 Ctrl+Space and its command (W7.2) | new viewport overlay, `views.py`, `commands.py` | Clicking a face, edge or corner sets the view | M | Original artwork needed; high DPI | No |
| WP14 | Model geometry snapping | Note 1, T1.2.2, T3.1 note 3, T3.2.1 model items | `core/sketch/reference.py` (projection off the UI thread), canvas, edit | Projected edges for a face sketch; snaps add relations to fixed copies | L | Kernel work off the UI thread (rule 2); performance budgets; D113 fixed copies go stale (Q8) | No (Opus for design) |
| WP15 | Selected regions | Note 9, T5.3.1 to T5.3.6, T5.1.6, T6.1.4 regions | `core/sketch/topology.py`, `profiles.py`, naming, panel, canvas or viewport hover, `FDEF_SPEC.md`, `DECISIONS.md` | Region split for crossing curves; picks survive edits; lost pick error; shared sketch | L | Needs D68 changed (Q1); topological naming of regions (Opus per CLAUDE.md 1A.2); hover must be fast | No (Opus) |

Suggested order: WP0 in parallel; then WP1, WP2, WP3, WP4 (all small); WP5 and WP6; WP7; WP8; WP9; WP10; WP11; WP12; WP13; WP14; WP15 last because it waits on decisions.

## 3. Spec questions

1. **Regions against D68 (T5.3.1).** D68 and PLAN.md section 5A item 9 make crossing curves a sketch error and build profiles only from sketches with no issues. T5.3.1 wants crossing curves to split the plane into pickable regions. Trim is Phase 2. Which wins, and does D68 change?
2. **Region names (T5.3.4).** There is no naming scheme for sketch regions in PLAN section 6 or FDEF_SPEC. How is a region named so it survives edits, and where is the pick list stored in `.fdef`?
3. **Through All for bosses (T5.1.3).** The core refuses it today and W6.2 lists it without saying for which. For a boss, what is the far end: the far side of the existing body along the direction?
4. **Dimension placement (T4.2.1, T4.4.2).** D72 says labels are placed automatically and their position is not stored. Dragging dimensions needs a stored position, so D72 and FDEF_SPEC must change. Confirm.
5. **File format changes.** Coradial and Intersection relations, symmetric with lines or arcs, Measure to (T4.3.2), Direction 2 end conditions (T5.1.4), Offset From (T5.1.2), Cut Outside (T5.1.5), region picks and dimension positions all add data to `.fdef`. CLAUDE.md section 4 item 4 requires older files to open. Is a format version bump planned for these, and who updates FDEF_SPEC?
6. **Reverse in the value box (T4.2.2).** No sketch dimension is signed today (the canvas rejects values of 0 or less except angles). Which dimensions are "signed distances"?
7. **Centres hidden until hover (T1.2.1).** Does this apply to sketch circles too? Today their centres are always snappable and drawn. W3.2 says hovering centres shows a marker but does not say they are hidden.
8. **Model snaps and relations (T1.2.2) against D110 item 6 and D113.** D110 item 6 says model centres snap without a relation. T1.2.2 says snapping to model geometry adds a relation to a fixed copy. D113 copies do not follow later part changes, so the relation goes stale silently. Is a stale copy acceptable, or should a changed part warn?
9. **Context toolbar contents (T8.2) against D110 item 9 and D106.** The spec drops Extrude for planes and faces and adds Hide or Show, Revolve, Delete and Edit Sketch elsewhere. D106 lists Zoom to Selection, which neither the code nor the spec has. Which list is final?
10. **Right click in the empty 3D view (T9.1).** Today it opens the shortcut bar (`MainWindow.viewport_menu`). T9.1 wants a context menu, and T10.1 keeps Q for the shortcut bar. Should right click stop opening the shortcut bar?
11. **Body commands in Phase 1 (T12.4).** I, H for bodies, Shift+Tab and Ctrl+Shift+Tab are in PLAN Phase 3 ("Isolate, hide and show bodies, show hovered body, show all hidden"). D48 freezes scope. Are they moved into Phase 1, and does PLAN need a new decision entry? Also T9.6 "Hide or Show Body".
12. **View selector key (T12.4).** WORKFLOW_SPEC W7.2 says "Space or Ctrl+Space"; SHORTCUTS.md 3.3 says Ctrl+Space only, and SHORTCUTS.md wins (T12.1). Should Space be dropped from W7.2?
13. **F8 (SHORTCUTS.md 3.17).** The feature tree display column toggle is in SHORTCUTS.md but not in T12.3 or T12.4. Is it Later?
14. **Delete asks whether to keep the sketch (T9.10).** Today Delete removes only the feature and warns about children. What does "keep the sketch" mean when the sketch is shared by another feature (T5.3.5)?
15. **Direction 2 rules (T5.1.4).** "Not available with Mid Plane" is clear. Is Direction 2 allowed when Direction 1 is Through All? The code allows it only after Blind.
16. **Ruler steps (T5.2.2).** The length tick step is not given (angles say 5 degrees). Fixed, or tied to zoom?
17. **Flip past the plane (T5.2.5).** For Mid Plane, and for a second direction, what does flipping do? Does it toggle the Reverse button?
18. **Highlight the crossing (T6.2.1).** In the sketch, the 3D view, or the errors panel highlight (`MainWindow.highlight_names`)?
19. **Points as construction (T2.6).** Should new points be stored with `construction` True? It changes nothing for profiles, but the colour and the construction toggle depend on it.
20. **Line length dimension (T4.1).** Should a single slanted line ever give a horizontal or vertical projection when the text is placed outside it, as two points do?
21. **Relation of an alignment guide (T1.2.5, T1.3.1).** T1.3.1 says "along a horizontal or vertical snap gives Horizontal or Vertical". Does snapping onto a dotted alignment guide to another point add a Horizontal or Vertical relation between the two points, or only the line direction snap?
22. **Section order.** T11 comes after T12 and there is no T11 before T10. Only numbering, but the task asked for "T1.1.1 through T12.6", so it is worth tidying.
23. **Architecture checks.** WP14 (projection of model edges) and WP15 (region hover) involve kernel work; both must run off the UI thread (rule 2) and inside the budgets of PLAN section 11 (rule 5A.1). Hover highlighting of regions needs regions computed once in the background, not per mouse move. None of the spec items asks to change geometry without confirmation (rule 12): the over define prompt (T1.4.4) and lost region pick (T5.3.4) already ask.

## Clean room note

This audit used only this repository and `docs/`. No web lookups were made and nothing outside the repository was read. The manager may want to log this session in the clean room record (kept privately, outside this repository) (this commit changes only this file, as instructed).
