# Icon names

Every icon in this folder, one per line in the lists below. The file for a name is `<name>.svg`. A test checks that each listed name has a valid SVG and that every `icon("...")` call in `src` uses a listed name. Command icons use the command id from `fdcad/ui/input/commands.py`.

## Style

- 24 by 24 grid, drawn by hand for FDCAD. Never traced or copied from any other program.
- Lines 1.5 wide with rounded caps and joins. `currentColor` for the main lines.
- `#ACCENT` marks the active part only: the new geometry, the constrained item, the face being looked at.
- `#CUT` takes the place of `#ACCENT` on tools that take material away (cuts, holes, trims, deletes), so adding and removing never look alike (D1034).
- A closed outline has a light fill in its own line colour, so parts and faces read as solid. Dashed and half strength outlines stay empty. The main tools are drawn as lit solids: a light left face and a darker right face. See `docs/DESIGN_LANGUAGE.md` section 4.
- `#DANGER` is used only for the cancel mark.
- Keep shapes inside 2 to 22 so they still read at 16 px.
- `tools/icon_sheet.py` draws every icon at 16, 24 and 48 px in both themes for review.

## Sketch tools

- sketch.sketch
- sketch.exit
- sketch.discard
- sketch.select
- sketch.line
- sketch.centerline
- sketch.corner_rectangle
- sketch.center_rectangle
- sketch.circle
- sketch.center_arc
- sketch.tangent_arc
- sketch.three_point_arc
- sketch.point
- sketch.construction
- sketch.dimension
- sketch.snap_options
- sketch.text
- sketch.line_arc
- sketch.relations
- sketch.edit_plane

## Phase 2 sketch tools

- sketch.trim
- sketch.extend
- sketch.offset
- sketch.mirror
- sketch.fillet
- sketch.chamfer
- sketch.convert
- sketch.linear_pattern
- sketch.circular_pattern
- sketch.slot
- sketch.polygon
- sketch.spline
- sketch.ellipse
- sketch.partial_ellipse
- sketch.picture
- sketch.three_point_corner_rectangle
- sketch.three_point_center_rectangle
- sketch.parallelogram
- sketch.perimeter_circle
- sketch.two_point_circle
- sketch.tangent_circle
- sketch.blend_curve
- sketch.jog_line
- sketch.parabola
- sketch.hyperbola
- sketch.turned_outline
- sketch.close_to_model
- sketch.dynamic_mirror
- sketch.move_entities
- sketch.copy_entities
- sketch.rotate_entities
- sketch.scale_entities
- sketch.stretch_entities
- sketch.midpoint_line
- sketch.infinite_line
- sketch.split
- sketch.insert_dxf
- sketch.insert_svg
- sketch.cut_away
- sketch.hide_construction
- sketch.show_construction

## Relations

- relation.horizontal
- relation.vertical
- relation.length_ratio
- relation.length_difference
- relation.equal_angle
- relation.equal_distance
- relation.coincident
- relation.collinear
- relation.parallel
- relation.perpendicular
- relation.tangent
- relation.concentric
- relation.equal
- relation.midpoint
- relation.symmetric
- relation.merge
- relation.on_segment
- relation.coradial
- relation.intersection
- relation.fixed
- relation.offset

## Features

- feature.extrude
- feature.extruded_cut
- feature.revolve
- feature.revolved_cut
- feature.fillet
- feature.chamfer
- feature.shell
- feature.draft
- feature.sweep
- feature.swept_cut
- feature.loft
- feature.lofted_cut
- feature.hole
- feature.cosmetic_thread
- feature.modeled_thread
- feature.mounting_boss
- feature.snap_hook
- feature.snap_groove
- feature.lip_groove
- feature.vent
- feature.rib
- feature.dome
- feature.corner_relief
- feature.merge_faces
- feature.fill_pattern
- feature.wrap

## Phase 3 tools

- feature.move_face
- feature.offset_face
- feature.delete_face
- feature.linear_pattern
- feature.pattern_chain
- feature.circular_pattern
- feature.sketch_pattern
- feature.mirror
- feature.combine
- feature.intersect
- feature.split
- feature.move_copy_body
- feature.transform_handles
- feature.delete_body
- feature.scale

## Face helper bar

- helper.coplanar
- helper.inner_loops
- helper.loops
- helper.around
- helper.tangent
- helper.coplanar_connected
- helper.same_direction
- helper.same_axis
- feature.ref_plane
- feature.ref_axis
- feature.ref_point
- feature.coord_system

## Evaluate

- evaluate.measure
- view.section

## Feature tree rows

Feature rows use the feature icons above and `tree.sketch` for sketches.

- tree.part
- tree.solid_bodies
- tree.folder
- tree.body
- tree.plane
- tree.origin
- tree.sketch
- tree.material
- tree.find
- tree.flat
- tree.link
- tree.graph
- tree.graph_body

## View

- view.fit
- view.zoom_area
- view.zoom_in
- view.zoom_out
- view.previous
- view.redraw
- view.front
- view.back
- view.top
- view.bottom
- view.left
- view.right
- view.iso
- view.standard_views
- view.visibility
- view.dimetric
- view.trimetric
- view.save_view
- view.home
- help.tool
- view.set_view_as
- view.reset_views
- view.temporary_axes
- view.mirror_image
- view.perspective
- evaluate.zebra
- evaluate.curvature_colors
- evaluate.compare_bodies
- evaluate.mass_properties
- evaluate.interference
- evaluate.cavities
- evaluate.undercut
- evaluate.edge_angles
- evaluate.layer_preview
- tools.expected_values
- tools.bodies_by_size
- tools.slice
- tools.hole_table
- tools.named_items
- feature.mould_cavity
- tools.insert_library
- tools.bodies_to_files
- tools.part_notes
- tools.goal_seek
- file.mirror_part
- file.batch_export
- print.fix_overhangs
- evaluate.change_test
- evaluate.model_health
- evaluate.repair_references
- feature.bounding_box
- feature.sensor
- feature.twist_lock
- feature.indent
- feature.primitive
- feature.point_curve
- feature.sketch3d
- feature.table_pattern
- feature.offset_body
- feature.shaft_shape
- feature.ring_groove
- feature.point_pattern
- feature.oring_groove
- feature.inlay
- feature.cable_tie
- feature.half_lap
- feature.finger_joint
- feature.crush_ribs
- feature.corner_ears
- feature.drain_holes
- feature.polygon_holes
- feature.base_pad
- feature.interlock
- feature.lattice_fill
- feature.mark
- feature.hinge
- feature.face_seats
- feature.stone_setting
- feature.sprue_tree
- feature.roof
- feature.deform_point
- feature.deform_curve
- feature.surface_push
- feature.linked_copy
- feature.face_relation
- feature.insert_part
- feature.transition_spiral
- feature.edge_profile
- feature.lightening_pockets
- feature.landing_pad
- feature.joint_helper
- feature.knurl
- feature.hose_fitting
- feature.living_hinge
- feature.section_cut
- tools.material
- tools.properties
- evaluate.manufacturing
- print.bed_chamfer
- print.height_changes
- evaluate.layer_fit
- print.suggest_orientation
- print.arrange
- evaluate.cups_islands
- print.coating
- print.fit_calibration
- print.keep_fit
- select.lasso
- select.only_bodies
- select.only_faces
- select.only_edges
- select.paint
- select.in_volume
- sketch.conic
- sketch.equation_curve
- sketch.intersection_curves
- sketch.silhouette
- sketch.fully_define
- sketch.check_sketch
- sketch.repair_sketch
- sketch.insert_spline_point
- sketch.fit_spline
- sketch.simplify_spline
- sketch.baseline_dimension
- sketch.ordinate_dimension
- view.all_dimensions
- view.split_one
- view.split_side
- view.split_stacked
- view.split_four
- view.normal_to
- view.shaded_edges
- view.shaded
- view.hidden_lines
- view.hidden_lines_visible
- view.wireframe
- view.transparency
- view.sketch_relations
- view.before_after
- view.curvature_combs
- view.describe_part
- view.selector
- tree.collapse_all
- view.orientation
- view.display_quality
- view.display_states
- view.hide_show
- view.isolate
- view.show_hovered
- view.show_all_bodies
- view.hide_reference

## File and edit

- file.new
- file.open
- file.save
- file.save_as
- file.save_increment
- file.save_copy
- file.save_copy_open
- file.export_configs
- file.save_template
- file.save_image
- file.close
- edit.undo
- edit.redo
- edit.repeat
- edit.delete
- edit.copy
- edit.paste
- edit.rebuild
- edit.force_rebuild
- edit.pause_rebuilds
- edit.rebuild_stay
- edit.discard_paused
- edit.continue_rebuild
- edit.appearance
- edit.copy_appearance
- edit.paste_appearance

## Interface

- ui.preferences
- ui.toggle_left
- ui.toggle_toolbars
- ui.fullscreen
- ui.shortcut_bar
- ui.close_tab
- ui.info_mark
- ui.question_mark
- ui.pin
- ui.pin_on
- ui.float_panel
- ui.dock_panel
- tools.stats

## Property panel fields

- field.sketch
- field.axis
- field.depth
- field.angle
- field.regions
- ui.reverse_direction

## Context toolbar

The context toolbar uses the command icons for Sketch, Extrude and Normal To.

- context.edit
- context.show
- context.hide

## Confirmation corner

- corner.ok
- corner.cancel
- corner.exit_sketch

## Selection (TOOL_SPEC T14.3)

Type icons in the Select Other list, and the selection filter bar.

- select.face
- select.edge
- select.vertex
- select.plane
- select.sketch
- select.other
- select.previous
- select.invert
- select.all
- select.similar
- select.to_edges
- select.to_faces
- select.to_bodies
- select.save_set
- select.sets
- select.filter_bar
- select.filters_toggle
- select.filter_faces
- select.filter_edges
- select.filter_vertices
- filter.body
- filter.plane
- filter.axis
- filter.sketch
- filter.segment
- filter.point
- filter.dimension

## Menus, view toggles and the tree (TOOL_SPEC T9, T14.4, T14.5)

- ui.context_menu
- context.edit_sketch
- view.zoom_selection
- view.show_planes
- view.show_origins
- view.show_sketches
- tree.roll_back
- tree.roll_forward
- tree.roll_previous
- tree.roll_end
- tree.purge_unused
- edit.edit_by_rule
- file.save_all
- file.close_all
- file.revert
- file.open_view_only
- tree.delete_below_bar
- tree.remove_history
- tree.error_mark
- tree.warning_mark

## Value fields (TOOL_SPEC T14.6)

- field.expression
- field.value

## Imports, curves and print tools (Phase 3)

- feature.import_step
- feature.helix
- feature.projected_curve
- feature.composite_curve
- feature.pipe
- feature.curve_array
- feature.contour
- evaluate.curvature_graph
- feature.import_mesh
- feature.split_for_print
## Sheet metal (PHASE5_SPEC, Sheet Metal tab)

- feature.base_flange
- feature.edge_flange
- feature.sketched_bend
- feature.sheet_metal
- feature.bend_table
- feature.flatten
- file.export_flat
- feature.hem
- feature.miter_flange
- feature.jog
- feature.closed_corner
- feature.break_corner
- feature.rip
- feature.gusset
- feature.tab_slot
- feature.convert_sheet
- feature.insert_bends
- feature.cross_break
- feature.unfold
- feature.fold
- feature.form_tool
- feature.gauge_table
- feature.flat_marks
- feature.stamp
- feature.bend_list
- feature.sheet_rules
- feature.perforation
- feature.extend_wall
- feature.sheet_corner_relief
- feature.edit_bends
- feature.sheet_tab

## Print and evaluate tools (Phase 2, D350 to D357)

- file.export_dxf
- file.export_svg
- file.export_section
- file.export_bodies
- print.open_slicer
- print.lay_flat
- print.clear_orientation
- print.scale_to_fit
- print.clear_fit
- print.save_fit
- evaluate.build_volume
- evaluate.overhang
- evaluate.wall_thickness
- evaluate.print_estimate
- evaluate.geometry_check
- evaluate.draft_analysis

## Node editor (PLAN Phase 7)

- graph.editor
- graph.add_node
- graph.delete
- graph.copy
- graph.paste
- graph.group
- graph.ungroup
- graph.comment
- graph.fit
- graph.set_position

## Equations, configurations and design tables (Phase 4)

- tools.equations
- tools.configurations
- tools.design_table

## Deformation features (Phase 4)

- feature.bend
- feature.twist
- feature.taper
- feature.stretch
- feature.flow
