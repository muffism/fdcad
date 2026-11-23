# .fdef File Format Specification

Schema version 2 (DECISIONS D391), used for parts with configured values, a design table (section 9) or node graphs (section 12A). Files are written with the lowest schema that holds their data: a part without them is written as schema 1, exactly as before. This document is published under the same license as FDCAD so anyone can read and write `.fdef` files.

Contents: 1 Overview, 2 Top level object, 3 Parameter values, 4 Variables, 5 Features, 6 Sketches, 7 References, 8 Naming grammar, 9 Configurations and design tables, 10 Appearance, 11 Embedded data, 12 Expressions, 12A Graphs, 13 Local solid cache, 14 Canonical form, 15 Versioning and migration, 16 Complete minimal example.

## 1. Overview

1. A `.fdef` file is a single UTF8 JSON document. Part files are saved with the extension `.fdprt` (DECISIONS D575); files named `.fdef` by builds before v1.0 have the same content and open the same way. The `format` key stays `"fdef"`.
2. It stores the full feature tree, sketches, parameters, variables, configurations, colours and any embedded imported geometry.
3. The tree is the part. It may also carry the finished solid of the last rebuild before it was saved (`solid`, section 13A, DECISIONS D1102), so a part shows at once on its first open anywhere; that solid is used only while it matches the tree, and the part is still rebuilt from the tree and cached locally (section 13).
4. Files are written in canonical form (section 14) so they diff cleanly in Git.

## 2. Top level object

```json
{
  "format": "fdef",
  "schema": 1,
  "app_version": "0.1.0",
  "units": "mm",
  "next_id": 6,
  "variables": [],
  "configurations": { "active": "Default", "items": [], "design_table": null },
  "features": [],
  "rollback": null,
  "appearance": { "part_color": "#B4BCC4", "faces": {} },
  "print_setup": { "down_face": null },
  "embedded": {}
}
```

1. `format`: always `"fdef"`.
2. `schema`: integer schema version: 1, or 2 when the configurations need it (section 9).
3. `app_version`: version of FDCAD that last saved the file.
4. `units`: display unit system of the part, `"mm"` or `"in"`. Does not affect stored values.
5. `next_id`: next free feature number. IDs are never reused.
6. `variables`: global variables (section 4).
7. `configurations`: configurations and design table (section 9).
8. `features`: ordered feature tree (section 5).
9. `rollback`: ID of the last active feature, or `null` when the rollback bar is at the end.
10. `appearance`: part colour and per face colours (section 10).
11. `print_setup`: print orientation. `down_face` is a face reference (section 7) laid flat on the printer bed, or `null`. Affects export orientation only (Phase 2). Set by Lay Face Flat and cleared by Clear Print Orientation (DECISIONS D353); STL, 3MF and Open in Slicer use it, STEP does not. No schema change.
12. `graphs` (schema 2 only, right after `features`): node graphs (section 12A). Left out of parts without graphs.
13. `embedded`: embedded data blocks such as imported STEP files, meshes and sketch images (section 11).
14. `views` (optional, right after `print_setup`): saved camera views (TR14, DECISIONS D690), a list in the order they were saved. Each is `{"name": "Side", "center": [x, y, z], "direction": [x, y, z], "up": [x, y, z], "distance": d, "scale": s}`: the target point, the view direction from the eye to the target, the up vector, the eye distance and the view scale (the size of the visible area), all in millimetres. Names are unique, ignoring case. Left out of parts with no saved views, so older parts save unchanged; readers before v1.2 keep the key as an unknown key. Display only: not part of the rebuild cache key. No schema change.
15. `tree` (optional, right after `views`): tree folders and feature comments (TR23, DECISIONS D692): `{"folders": [{"name": "Holes", "features": ["f8", "f10"]}], "comments": {"f8": "Clearance for M6"}}`. A folder lists top level features in tree order; only members that sit next to each other are shown in it. Comments are plain text keyed by feature id. Either part is left out when empty, and the key is left out of parts with neither, so older parts save unchanged. Display only: not part of the rebuild cache key. No schema change.
16. `solid` (optional, after every other key of this section and before unknown keys): the finished solid of the last rebuild (section 13A, DECISIONS D1102). Written by Save; left out when there is none, so parts saved without it are unchanged. Not part of the rebuild cache key, and not part of a part's content: two files that differ only in it hold the same part. Readers before it keep it as an unknown key. No schema change.

## 3. Parameter values

Every user editable value is stored as a parameter object:

```json
{ "expr": "7/8 in", "value": 22.225 }
```

1. `expr`: exactly what the user typed.
2. `value`: evaluated result in internal units. Lengths in millimetres, angles in radians, plain numbers (counts, ratios) unitless.
3. On load, `expr` is evaluated again. If the result differs from `value` (for example because a variable changed), the new result wins and the feature is rebuilt.

## 4. Variables

```json
{ "name": "Width", "kind": "length", "expr": "2 1/2in", "value": 63.5 }
```

1. `name`: letters, digits and underscores, starting with a letter. Case sensitive. Unique.
2. `kind`: `"length"`, `"angle"` or `"number"`.
3. Variables may reference other variables. Circular references are an error.
4. `comment` (optional, added in Phase 4, DECISIONS D390): the equations manager note. Left out when empty. Schema note: an optional addition to schema 1; files without it open and save unchanged.

## 5. Features

Contents: 5.1 Common fields, 5.2 Built in features, 5.3 Feature types, with one subsection per type group:

- 5.3.1 Extrude parameters
- 5.3.2 Revolve parameters
- 5.3.3 Selected regions
- 5.3.4 Fillet parameters
- 5.3.5 Chamfer parameters
- 5.3.6 Shell parameters
- 5.3.7 Draft parameters
- 5.3.8 Sweep parameters
- 5.3.9 Loft parameters
- 5.3.10 Phase 3 features: common rules
- 5.3.11 Move Face
- 5.3.12 Delete Face
- 5.3.13 Patterns and mirror
- 5.3.14 Multibody and scale
- 5.3.15 Imported STEP body
- 5.3.16 Curves: helix, projected curve, composite curve
- 5.3.17 Pipe, array along curve, contour curves
- 5.3.18 Split for printing
- 5.3.19 Imported mesh
- 5.3.20 Reference geometry
- 5.3.21 Hole parameters
- 5.3.22 Cosmetic thread parameters
- 5.3.23 Modelled thread parameters
- 5.3.24 Mounting boss parameters
- 5.3.25 Snap hook parameters
- 5.3.26 Snap hook groove parameters
- 5.3.27 Lip and groove parameters
- 5.3.28 Vent parameters
- 5.3.29 Rib parameters
- 5.3.30 Dome parameters
- 5.3.31 Wrap parameters
- 5.3.32 Sheet metal
- 5.3.33 Deformation features

### 5.1 Common fields

```json
{
  "id": "f5",
  "type": "extrude",
  "name": "Extrude 1",
  "suppressed": false,
  "params": {},
  "refs": {}
}
```

1. `id`: `"f"` followed by an integer from `next_id`. Permanent.
2. `type`: feature type string (section 5.3).
3. `name`: display name, user editable.
4. `suppressed`: boolean, in the active configuration context (configurations may override it).
5. `params`: parameter objects keyed by parameter name.
6. `refs`: references to sketches, faces, edges, vertices or other features (section 7).
7. `suppression` (optional, Phase 4, DECISIONS D390): a formula that sets `suppressed`, for example `"=if(\"Width\" > 40mm, suppressed, unsuppressed)"`. Nonzero means suppressed; `suppressed` and `unsuppressed` are names for 1 and 0.
8. `comments` (optional, Phase 4, DECISIONS D390): equations manager notes, value name to text (`"suppressed"` for the suppression formula), sorted by name. Both keys are left out when not used; they are optional additions to schema 1.
9. `keep_separate_body` (optional, DECISIONS D527): `true` when the user chose "Keep separate body" for the separate body this feature made; its separate body warning is then not shown. Written only when true, so it is an optional addition to schema 1 and files without it save unchanged. It changes no geometry.
10. `value_names` (optional, DECISIONS D698): `{ "<value>": "<name>" }`, names the user gave to the feature's values for formulas (`"wall@Shell 1"`). Left out when no value is named. Display and formula names only; it changes no geometry.

### 5.2 Built in features

Every file starts with these four features, in this order:

1. `f1`, type `origin`, name "Origin".
2. `f2`, type `plane`, name "Front Plane", XY plane.
3. `f3`, type `plane`, name "Top Plane", XZ plane.
4. `f4`, type `plane`, name "Right Plane", YZ plane.

Y is up.

### 5.3 Feature types

Each phase adds types. Each type documents its `params` and `refs` in `fdcad/core/features/<type>.py` and in this file when it is introduced.

Planned types by phase:

1. Phase 1: `origin`, `plane`, `sketch`, `extrude`, `revolve`.
2. Phase 2: `sweep`, `loft`, `fillet`, `chamfer`, `shell`, `draft`, `ref_plane`, `ref_axis`, `ref_point`, `coord_system`. Sketch entity `picture` (references an embedded image).
3. Phase 3: `linear_pattern`, `circular_pattern`, `sketch_pattern`, `mirror`, `combine`, `intersect`, `split`, `move_copy_body`, `delete_body`, `import_step`, `helix`, `projected_curve`, `composite_curve`, `pipe`, `curve_array`, `contour`, `offset_face`, `move_face`, `delete_face`, `split_for_print`, `scale`, `import_mesh`.
4. Phase 4: `hole` (types: simple, counterbore, countersink, tapped, heat_set_insert, nut_trap; option `modeled_thread`), `cosmetic_thread`, `modeled_thread`, `rib`, `dome`, `wrap`, `flow`, `twist`, `bend`, `taper`, `stretch`, `mounting_boss`, `snap_hook`, `snap_groove`, `lip_groove`, `vent`.
5. Phase 5: `sheet_metal`, `base_flange`, `edge_flange`, `sketched_bend`, `flatten`. Later sheet metal tools (DECISIONS D530 to D545): `hem`, `miter_flange`, `jog`, `closed_corner`, `break_corner`, `rip`, `tab_slot`, `convert_sheet`, `insert_bends`, `cross_break`, `unfold`, `fold`, `form_tool`.
6. Phase 7: `graph_body`.

Example extrude:

```json
{
  "id": "f6",
  "type": "extrude",
  "name": "Extruded Cut 1",
  "suppressed": false,
  "params": {
    "operation": "cut",
    "end_condition": "blind",
    "depth": { "expr": "=Width/2", "value": 31.75 },
    "reverse": false
  },
  "refs": { "sketch": { "feature": "f5" } }
}
```

Non numeric settings such as `operation` and `end_condition` are stored as plain strings or booleans, not parameter objects.

#### 5.3.1 Extrude parameters

1. `operation`: `"boss"` or `"cut"`.
2. `end_condition`: Direction 1. `"blind"`, `"through_all"`, `"mid_plane"`, or `"two_directions"` (Blind plus Direction 2, kept from the first Phase 1 files).
3. `depth`: length from the start. `depth2`: length in Direction 2 when it is Blind.
4. `reverse`: boolean, flips the direction.
5. `merge`: optional boolean, default true. False keeps a boss as a separate body.
6. `end_condition2`: optional, `"blind"` or `"through_all"`: Direction 2's end condition. Direction 2 is on when `end_condition` is `"two_directions"` or this key is present. It is written only when it is needed: Direction 1 Through All, or Direction 2 Through All. Not allowed with `"mid_plane"`.
7. `start_condition`: optional, where the feature starts (the From list). `"sketch_plane"` (the default when the key is missing), `"surface"`, `"vertex"` or `"offset"`. Written only when it is not `"sketch_plane"`.
8. `start_offset`: length, for `"offset"`: distance from the sketch plane along its normal. `start_reverse`: optional boolean, puts the offset on the other side; written only when true.
9. `cut_outside`: optional boolean for cuts; written only when true. The cut removes the material outside the profile within the depth range.
10. `refs.start`, for `"surface"`: a face reference (section 7) or a plane feature (`{ "feature": "f2" }`). For `"vertex"`: a vertex reference, or a sketch point `{ "feature": "f7", "sketch_entity": "e3" }`.

11. Phase 2 end conditions (DECISIONS D210): `end_condition` and `end_condition2` also take `"up_to_vertex"`, `"up_to_face"` and `"offset_from_face"`. `refs.end` (Direction 1) and `refs.end2` (Direction 2) hold the pick: a vertex reference or a sketch point for Up to Vertex, a face reference or a plane feature for the others. Offset from Face adds `end_offset` (length), and optional `end_offset_reverse` and `end_translate` booleans written only when true; Direction 2 uses the same names with the suffix `2`.
12. Draft while extruding (D212): optional `draft_angle` (angle) and `draft_outward` (boolean, written only when true), and `draft_angle2`, `draft_outward2` for Direction 2. Draft is on for a direction when its angle is present.
13. Thin Feature (D211): optional `thin_type` (`"one_direction"`, `"mid_plane"` or `"two_direction"`), `thin_thickness`, `thin_thickness2` (Two Direction only), `thin_reverse`, `thin_cap` (booleans written only when true) and `thin_cap_thickness` (with `thin_cap`). All are left out while Thin Feature is off. Thin side faces are named `side/<entity>/outer`, `side/<entity>/inner`, `side/<entity>/start` and `side/<entity>/end`.
14. More end conditions (TOOL_SPEC T16, DECISIONS D460 and D461): `end_condition` also takes `"through_all_both"` (Through All both ways from the start; `end_condition2` is not allowed with it), `"up_to_next"` and `"up_to_body"`; `end_condition2` also takes `"up_to_next"` and `"up_to_body"`. Up to Body keeps the body pick in `refs.end` (Direction 1) or `refs.end2` (Direction 2): a face reference to any face of the body (section 5.3.10 item 2). Up to Next needs no pick. These are new values of existing optional keys, so files without them open and save unchanged.

Example with a start offset and Direction 2 Through All:

```json
"params": {
  "operation": "cut",
  "end_condition": "blind",
  "depth": { "expr": "2", "value": 2.0 },
  "reverse": false,
  "end_condition2": "through_all",
  "start_condition": "offset",
  "start_offset": { "expr": "5", "value": 5.0 }
}
```

#### 5.3.2 Revolve parameters

1. `operation`: `"boss"` or `"cut"`.
2. `direction`: `"one_direction"`, `"mid_plane"` or `"two_directions"`.
3. `angle`, `angle2`: angles; the total is at most 360 degrees.
4. `reverse`: boolean. `merge`: optional boolean, default true.
5. `cut_outside`: optional boolean for cuts; written only when true. The cut removes the material outside the profile within the revolved angle.
6. `refs.sketch` and `refs.axis` (a sketch line `{ "sketch_entity": "e9" }` or an edge reference).
7. `refs.regions`: optional Selected Regions picks (5.3.3).
8. End conditions (TOOL_SPEC T16 item 2, DECISIONS D462 to D464), all optional and written only when needed, so files with only `direction` open, rebuild and save unchanged:
   - `end_condition`: Direction 1. `"through_all"` (a full turn; `angle` is kept but not used and Direction 2 is not allowed), `"up_to_vertex"`, `"up_to_face"` or `"offset_from_face"`. Left out it is Blind, or Mid Plane when `direction` is `"mid_plane"`. The panel writes Blind and Mid Plane through `direction` only. With the Up to ends `angle` is kept but not used.
   - `end_condition2`: Direction 2. `"up_to_vertex"`, `"up_to_face"` or `"offset_from_face"`, with `direction` `"two_directions"`. Left out, Direction 2 is Blind (with `angle2`) when `direction` is `"two_directions"`.
   - `refs.end_ref` and `refs.end_ref2`: a vertex reference or a sketch point `{ "feature": "f7", "sketch_entity": "e3" }` for Up to Vertex; a flat face reference or a plane feature `{ "feature": "f4" }` for the other two.
   - `end_offset` and `end_offset2`: angles, Offset from Face only. The end face is turned back about the axis, toward the start, by the offset.
   - These keys are optional additions within schema 2 (section 14 item 4): older readers keep them on save.
9. Thin Feature (TOOL_SPEC T6.1 item 5, DECISIONS D523): the `thin_type`, `thin_thickness`, `thin_thickness2`, `thin_reverse`, `thin_cap` and `thin_cap_thickness` keys of 5.3.1 item 13, with the same rules, left out while Thin Feature is off. The wall must stay on one side of the axis. Open profiles are allowed only with Thin Feature on; a sketch line used as the axis is not part of the chain. `thin_cap` needs a closed profile and less than a full turn with ends given by angles; each lid's inner face is `thin_cap/start` or `thin_cap/end`, its other faces `lid_side/...` and `lid_clip/...`.

Example, Direction 1 up to a plane through the axis and Direction 2 Blind:

```json
"params": {
  "operation": "boss",
  "direction": "two_directions",
  "angle": { "expr": "90", "value": 1.5707963267948966 },
  "angle2": { "expr": "30", "value": 0.5235987755982988 },
  "reverse": false,
  "end_condition": "up_to_face"
},
"refs": {
  "sketch": { "feature": "f5" },
  "axis": { "sketch_entity": "e9" },
  "end_ref": { "feature": "f4" }
}
```

#### 5.3.3 Selected regions

Extrude and Revolve may use only some regions of their sketch (DECISIONS D190 to D193). `refs.regions` lists the picks in the order the Selected Regions box shows them:

```json
"refs": {
  "sketch": { "feature": "f5" },
  "regions": [
    { "kind": "region", "name": "region(e3+|e9+)", "snapshot": { "point": [42.3, 10.0], "area": 100.53 } }
  ]
}
```

1. `name`: the region name (section 8 item 6).
2. `snapshot`: area centre in sketch coordinates (mm) and area (mm squared) when picked. Shown to the user only; a pick is never resolved by position.
3. A missing or empty list uses the whole sketch. The key is left out when nothing is picked.
4. Several features may use the same sketch with different picks.

Schema note: every key added in 5.3.1 and 5.3.2 after the first Phase 1 build, including the Phase 2 keys of items 11 to 13, is optional and left out at its default, so older files open and save unchanged. This is not a schema change (DECISIONS D145).

#### 5.3.4 Fillet parameters (Phase 2, DECISIONS D213)

1. `fillet_type`: `"constant"` or `"variable"`.
2. `radius`: length. For constant fillets the radius of every item, else the default.
3. `multiple_radius`: optional boolean, written only when true. Then `radius_<k>` (length) is the radius of picked edge `k`, counted from 1 in `refs.edges` order.
4. Variable size: `vr_<k>_start`, `vr_<k>_end` (lengths at the two ends of edge `k`), `control_points` (a whole number from 0 to 5) and `vr_<k>_<j>` for control point `j`, and `transition` (`"smooth"` or `"straight"`).
5. `refs.edges`: edge references. `refs.faces`: face references (every edge of each face). `refs.features`: feature references (`{ "feature": "f6" }`, every edge of that feature's faces). At least one list is present.
6. Face roles: `fillet/<edge name>`, for example `f9/fillet/edge(f6/cap/end|f6/side/e3)`, and `corner/face#k` for corner blends.
7. `fillet_type` `"face"` (DECISIONS D518): `refs.faces1` and `refs.faces2` (face references, the two face sets) and `radius`. The edges where the two sets meet are rounded; face roles as item 6.
8. `fillet_type` `"full_round"` (D518): `refs.faces1` (side 1), `refs.centre` (centre faces) and `refs.faces2` (side 2). The radius is half the distance between the sides; the stored `radius` is kept but not used. The round face is named `full_round/<first centre face name>`.
9. `refs.auto_edges` (D519, fillet assistant): optional list of `{ "convexity": "convex" }` or `{ "convexity": "concave" }`, with an optional `"feature": "f6"` to use only that feature's faces. Each item rounds every convex or concave edge found when the part rebuilds. Written only when the list has items.
10. Partial edges (D519, Constant Size only): `partial` (`"distance"` or `"percent"`, written only when partial edges are on) with `start_distance` and `end_distance` (lengths) or `start_percent` and `end_percent` (numbers, 0 to 100). The range is measured along each item edge from its first end; `partial_flip` (optional boolean, written only when true) measures from the other end. The round ends square at the start and end.

#### 5.3.5 Chamfer parameters (Phase 2, DECISIONS D216)

1. `chamfer_type`: `"angle_distance"`, `"distance_distance"` or `"vertex"`.
2. `distance`: length. `angle`: angle (Angle Distance). `method`: `"symmetric"` or `"asymmetric"` (Distance Distance), with `distance2` for asymmetric.
3. `flip`: optional boolean, written only when true: measure the first distance on the other face of each edge.
4. Vertex: `distance`, `distance2` and `distance3` along the three edges at the corner in edge name order, or `equal: true` with `distance` only.
5. `refs.edges`, `refs.faces` for the edge types; `refs.vertices` (vertex references) for the vertex type.
6. Face roles: `chamfer/<edge name>` and `chamfer/<vertex name>`.
7. `chamfer_type` `"offset_face"` (DECISIONS D520): keys as Distance Distance (`method`, `distance`, `distance2`, `flip`), but each distance is an offset measured square to a face: `distance` from the reference face, `distance2` from the other face.
8. `chamfer_type` `"face_face"` (D520): `refs.faces1` and `refs.faces2` (the two face sets; the edges where they meet are chamfered). `method`: `"symmetric"` (`distance`), `"asymmetric"` (`distance` along the set 1 face, `distance2` along the set 2 face) or `"width"`, with `width` (length, optional key written only for this method) the width of the chamfer face.

#### 5.3.6 Shell parameters (Phase 2, DECISIONS D217)

1. `thickness`: length. `outward`: optional boolean, written only when true.
2. `refs.faces`: faces to remove (optional; none gives a closed hollow part).
3. `refs.thick_faces` with `thickness_<k>` (length) for face `k`, counted from 1 (Multi Thickness).
4. `refs.body`: a list with one face reference of the body to shell, used when the part has several bodies and no face is removed.
5. Face roles: `shell/<face name>` for the wall face made from a face of the part.

#### 5.3.7 Draft parameters (Phase 2, DECISIONS D218)

1. `angle`: angle from the pull direction.
2. `reverse`: optional boolean, written only when true: flips the pull direction.
3. `propagation`: optional, `"tangent"`, `"all"`, `"inner"` or `"outer"`; left out for none.
4. `refs.neutral`: a plane feature or a flat face reference. `refs.faces`: faces to draft (may be empty for `"all"`, `"inner"` and `"outer"`).
5. Drafted faces keep their names; draft adds no face roles.
6. `draft_type` (D521): optional, `"parting_line"` or `"step"`; left out for the neutral plane method. With either, `refs.neutral` is the direction of pull, `refs.parting_lines` lists the parting edges (edge references), and `refs.faces` and `propagation` are not written. `other_side` and `both_sides`: optional booleans, written only when true. `angle2`: optional angle of the other side with `both_sides`; left out, the main angle applies.

#### 5.3.8 Sweep parameters (Phase 2, DECISIONS D219)

1. `operation`: `"boss"` or `"cut"`. `merge`: optional boolean for bosses.
2. `profile_type`: optional, `"circular"` with `diameter` (length); left out for a sketch profile.
3. `orientation`: optional, `"keep_normal"`; left out for Follow Path.
4. `twist`: optional, `"minimum"`, `"angle"` (with `twist_angle`) or `"direction"`; left out for none.
5. Thin Feature for bosses: the `thin_type`, `thin_thickness`, `thin_thickness2` and `thin_reverse` keys of 5.3.1 item 13.
6. `refs.profile` (a sketch, not with a circular profile), `refs.path` (a sketch) or `refs.path_edges` (edge references), and `refs.twist_direction` (a plane feature, a flat face or a straight edge) for the direction twist.
7. Face roles: `cap/start`, `cap/end`, `side/<entity>` with `#k` for later path segments, `side/circle` for a circular profile.

#### 5.3.9 Loft parameters (Phase 2, DECISIONS D220)

1. `operation`: `"boss"` or `"cut"`. `merge`: optional boolean for bosses.
2. `start_constraint`, `end_constraint`: optional, `"none"`, `"normal"` or `"direction"`; left out for Default. `start_length`, `end_length` (lengths) with `"normal"` and `"direction"`.
3. `connect_<k>`: optional whole number, the edge where profile `k` (counted from 1) starts; left out at 0.
4. `close_loft`: optional boolean, written only when true.
5. Thin Feature for bosses: the `thin_type`, `thin_thickness`, `thin_thickness2` and `thin_reverse` keys of 5.3.1 item 13.
6. `refs.profiles`: sketches (`{ "feature": "f5" }`) or flat face references, in order. `refs.start_direction`, `refs.end_direction`: a plane feature, a flat face or a straight edge, with `"direction"`.
7. Face roles: `cap/start`, `cap/end` and `side/<entity>` from the first profile.

#### 5.3.10 Phase 3 features: common rules

1. Every Phase 3 type adds only new `type` strings, optional `params`, `refs` and, for some types, one extra top level key of the feature (listed with the type). Files without them are unchanged, so this is not a schema change; older files open and save byte for byte the same.
2. A body is referred to by a face reference (section 7) to any face of it.
3. Lists of picks (`refs.faces`, `refs.bodies`, `refs.tools`, `refs.planes`, `refs.features`) are JSON arrays of references, in pick order.

#### 5.3.11 Move Face (`move_face`)

1. `mode`: `"offset"`, `"translate"` or `"rotate"`.
2. `distance`: length (Offset; Translate along a direction; Offset from Face). `reverse`: optional boolean. `copy`: optional boolean (Translate, Rotate).
3. `translate_by`: optional, `"direction"` (default), `"delta"`, `"up_to_vertex"`, `"up_to_face"`, `"offset_from_face"`, `"up_to_body"`. `dx`, `dy`, `dz`: lengths for `"delta"`.
4. `rotate_by`: optional, `"axis"` (default) or `"origin"`. `angle`: angle about the axis. `ox`, `oy`, `oz`: lengths, the rotation origin; `rx`, `ry`, `rz`: angles about X, then Y, then Z.
5. `refs.faces`: the faces. `refs.direction`: a straight edge, flat face, plane or axis. `refs.from`: optional face, plane or vertex. `refs.to`: a vertex, face or plane. `refs.body`: a face of the target body. `refs.axis`: a straight edge, round edge or cylinder face.
6. Face roles: moved faces keep their names; a copy adds `copy1/<name>` for each copied face and `copy1/face#k` for the rest.

Offset Face is Move Face with `mode` `"offset"`; there is no `offset_face` type.

#### 5.3.12 Delete Face (`delete_face`)

1. `option`: `"patch"` (default) or `"fill"`. `"delete"` (no healing) is reserved until surface bodies exist and is an error.
2. `tangent`: optional boolean for `"fill"`.
3. `refs.faces`: the faces. Face roles: `fill`, or `fill#k` for several openings.

#### 5.3.13 Patterns and mirror (`linear_pattern`, `circular_pattern`, `sketch_pattern`, `mirror`)

1. Seed refs: `refs.features` (`[{ "feature": "f6" }]`, boss or cut features), `refs.faces` (faces of a whole feature) or `refs.bodies` (a face of each body).
2. Options, all optional: `geometry`, `merge`, `propagate_colours` (booleans), `preview` (`"full"` or `"partial"`).
3. Top level key `skip` (not in `params`): instances to leave out, `[[i, j], ...]`, numbered from 1; `[1, 1]` is the seed. Written only when not empty.
4. `linear_pattern`: `spacing1` (length), `count1` (number), `reverse1`, `fill1` (`"spacing"` or `"up_to"`), `offset1` (length) and `refs.direction1`, `refs.up_to1`; `second_direction` (boolean) turns on the same keys ending in `2`; `seed_only2` (boolean).
5. `circular_pattern`: `count1`, `angle1`, `equal_spacing` (default true), `reverse1`; `second_direction`, `count2`, `angle2`, `symmetric2`; `refs.axis`. `skip` pairs are `[i, 1]` for direction 1 and `[i, 2]` for direction 2.
6. `sketch_pattern`: `refs.sketch` and optional `refs.point`. `skip` pairs are `[k, 1]`, `k` counting the sketch's free points from 1.
7. `mirror`: `refs.plane`, optional `refs.plane2`, `seed_only` (boolean).
8. Face roles: `instance<i>.<j>/<seed face name>` (feature and body seeds) or `instance<i>.<j>/face#k` (face seeds); a mirror uses `mirror1`, `mirror2` and `mirror3` (both planes).

#### 5.3.14 Multibody and scale (`combine`, `intersect`, `split`, `move_copy_body`, `delete_body`, `scale`)

1. `combine`: `operation` (`"add"`, `"subtract"`, `"common"`); `refs.bodies`; `refs.main` for `"subtract"`.
2. `intersect`: `regions` (`"overlap"`, `"internal"`, `"both"`), `merge` (default true), `cap` (optional boolean); `refs.bodies`, optional `refs.planes`. Top level key `exclude`: excluded region numbers from 1, ordered by centre X, then Y, then Z. Face roles: `region<k>/face#j`.
3. `split`: `refs.tools` (planes, faces, sketches `{ "feature": "f9" }`), optional `refs.bodies` (all bodies when missing). Top level key `keep`: kept piece numbers from 1 by centre position; missing means all. New cut faces: `cut/face#k`.
4. `move_copy_body`: `mode` (`"translate"`, `"rotate"`), `copy`, `count`, `translate_by` (`"delta"`, `"edge"`, `"vertices"`), `dx`, `dy`, `dz`, `distance`, `reverse`, `rotate_by` (`"edge"`, `"origin"`), `angle`, `ox`, `oy`, `oz`, `rx`, `ry`, `rz`; `refs.bodies`, `refs.edge`, `refs.from`, `refs.to`, `refs.axis`. Copies: `copy<k>/<name>`.
5. `delete_body`: `option` (`"delete"`, `"keep"`); `refs.bodies`.
6. `scale`: `uniform` (default true), `factor`, `fx`, `fy`, `fz` (numbers), `about` (`"centroid"`, `"origin"`, `"point"`), `ox`, `oy`, `oz`; optional `refs.bodies`. Faces keep their names.

#### 5.3.14.1 Turning bodies about their centre (Phase 3, DECISIONS D411)

1. `move_copy_body` also takes `rotate_by` `"centroid"`: the turns `rx`, `ry` and `rz` (about X, then Y, then Z) go through the centre of volume of the picked bodies instead of the origin fields. `ox`, `oy` and `oz` are not written with it. The transform handles write this form when a ring is dragged.
2. Schema note: a new choice of an existing parameter, not a schema change. Files without it open unchanged.

#### 5.3.14.2 Fit presets on Offset Face (Phase 4, DECISIONS D413)

1. `move_face` with `mode` `"offset"` also takes `print_fit` (`"clearance"`, `"slip"` or `"press"`) with `fit_tolerance` (length, copied from the active printer profile when the fit is chosen). Both are written only while a fit is chosen; no fit means neither key.
2. The faces move a further gap into the material on top of `distance`: one `fit_tolerance` for Clearance, half for Slip, none for Press. This matches holes, whose diameter grows by two, one or no tolerances (DECISIONS D311).
3. Schema note: optional additions to an existing feature type, not a schema change. Files without them open unchanged.

#### 5.3.15 Imported STEP body (Phase 3, DECISIONS D290)

1. `merge`: optional boolean, written only when true: join the imported solid to the part's body. Left out, an import into a part that already has a body becomes its own body.
2. `refs.source`: `{ "embedded": "b1" }`, an embedded block of type `step` (section 11).
3. Face roles: `face/<k>`, numbered from 1 in the order of the healed shape's faces. The same file always gives the same order.
4. Colours from the file are not written to the file: they are read from the embedded STEP data on every rebuild. Colours set later by the user go in `appearance.faces` as usual and win over the file's colours.
5. Schema note: a new feature type and block use, not a schema change. Files without imports open and save unchanged.

#### 5.3.16 Curves: helix, projected curve, composite curve (Phase 3, DECISIONS D291)

Curve features leave the part unchanged and make a curve that later features use through a feature reference (`{ "feature": "f9" }`), for example as a sweep path.

1. `helix`: `definition` is `"pitch_turns"`, `"height_turns"`, `"height_pitch"` or `"spiral"`. `pitch` and `height` (lengths) and `turns` (a number, kind `number`) as the definition needs. Optional: `pitch_type` (`"variable"`; left out for constant), `reverse`, `clockwise` (written only when true), `start_angle` (angle), `taper_angle` (angle) and `taper_outward` (written only when false). Variable pitch: `vp_rows` (whole number, at least 2) and per row `k` from 1: `vp_turns_<k>` (number, left out for row 1, which is at turn 0), `vp_pitch_<k>` and `vp_diameter_<k>` (lengths). `refs.sketch`: a sketch with exactly one circle.
2. `projected_curve`: `mode` is `"faces"` or `"sketches"`. Optional `reverse` and `both` (written only when true, mode `"faces"`). `refs.sketch`; `refs.faces` (face references) and optional `refs.direction` (a plane feature, a flat face or a straight edge) for `"faces"`; `refs.sketch2` for `"sketches"`.
3. `composite_curve`: `refs.items`, an ordered list of sketch and curve feature references and edge references.
4. Curves have no face roles. Schema note: new feature types only, not a schema change.

#### 5.3.17 Pipe, array along curve, contour curves (Phase 3, DECISIONS D292)

1. `pipe`: `operation` (`"boss"` or `"cut"`), optional `merge`, `outer_diameter` (length), optional `inner_diameter` (length, a hollow pipe) and `cap_ends` (written only when true, hollow open paths only). `refs.path` (a sketch or a curve feature) or `refs.path_edges` (edge references). Face roles: `pipe/outer`, `pipe/inner` (`#k` per path segment after the first), `cap/start`, `cap/end`, `cap/inner_start`, `cap/inner_end`.
2. `curve_array`: `mode` (`"count"` or `"spacing"`), `count` (number, the seed included), `spacing` (length, with `"spacing"`), optional `orient` (written only when false), `skip` (text: instance numbers separated by commas, for example `"3,5"`) and `merge` (bodies, written only when true). `refs.path` or `refs.path_edges` for the curve; `refs.features` (feature references) or `refs.bodies` (one face reference per body). Faces of copy `k` are named `<feature>/instance<k>/<seed face name>`.
3. `contour`: `spacing` (length). `refs.direction`: a plane feature, a flat face or a straight edge. No face roles; the loops are a curve for later features.
4. Schema note: new feature types only, not a schema change.

#### 5.3.18 Split for printing (Phase 3, DECISIONS D293)

1. `mode`: `"auto"` (default) or `"planes"`. `build_x`, `build_y`, `build_z` (lengths) with `"auto"`; `refs.planes` (plane features or flat face references) with `"planes"`.
2. `connector`: `"none"`, `"pins"` or `"dovetail"`. Pins: `pin_diameter`, `pin_length`. Dovetail keys: `key_width`, `key_depth`. Both: `clearance` (all lengths; only the keys the chosen connector uses are written).
3. Face roles: `cut<j>` (`#k` when the cut on plane `j` makes several faces), `pin<k>/face<i>` and `key<k>/face<i>` for connector bodies. Faces split by a cut get `#1`, `#2`.
4. `refs.bodies`: optional list of body references (a face reference of each body) to cut. Left out, every body is cut. Optional key, not a schema change (DECISIONS D621).

#### 5.3.19 Imported mesh (Phase 3, DECISIONS D294)

1. `convert`: optional boolean, written only when true: the mesh becomes a faceted solid. Left out, the mesh is a reference body shown in the view and not part of the solid.
2. `merge`: optional boolean, written only when true (converted meshes): join the solid to the part's body.
3. `refs.source`: `{ "embedded": "b1" }`, a `mesh` block with `format` `"stl"`, `"3mf"` or `"obj"` (section 11).
4. Face roles of a converted mesh: `face/<k>`, after triangles in one plane are merged into one face.
5. Schema note: new feature types only, not a schema change.

#### 5.3.19.1 A mesh as a cutting tool (Phase 3, DECISIONS D412)

1. `import_mesh` also takes `subtract`: optional boolean, written only when true, and only with `convert`. The faceted solid is cut out of the part's body instead of being kept as a body or merged. `merge` is not written with it. A mesh with nothing above it to cut from is an error.
2. Schema note: an optional addition to an existing feature type, not a schema change. Files without it open unchanged.

#### 5.3.20 Reference geometry

Types `ref_plane`, `ref_axis`, `ref_point` and `coord_system` (DECISIONS D251). None of them changes the part. Each stores a `method` string in `params` and up to three picks in `refs.first`, `refs.second` and `refs.third`. A pick is a face, edge or vertex reference (section 7), a feature (`{ "feature": "f2" }`: a plane, a reference feature or the origin `f1`) or a sketch point or line (`{ "feature": "f5", "sketch_entity": "e3" }`). Boolean options are written only when true; values are parameter objects.

1. `ref_plane` methods: `offset` (first: plane or flat face; `distance`; `flip` puts it on the other side), `angle` (a plane or flat face and a straight edge or axis lying in or parallel to it, in either order; `angle`; `flip` turns the other way), `three_points`, `normal_to_curve` (first: an edge or axis; second, optional: a point the plane passes through; `origin_on_curve` moves the origin onto the curve), `mid_plane` (two parallel planes or flat faces), `parallel_point` (a plane or flat face and a point), `project` (first: a point; second: a face, usually curved; the plane passes through the point projected onto the face, nearest point, and is normal to the face there; `along_normal`, only for a sketch point, projects along the sketch normal instead; DECISIONS D526), `screen` (first: a point; the plane passes through it, normal to the view direction captured when it was made, stored as the plain numbers `normal_x`, `normal_y` and `normal_z` of a unit vector toward the viewer, so the camera never takes part in a rebuild; D526). Every method takes `flip_normal`. A sketch can sit on a `ref_plane` with `refs.plane` set to `{ "feature": "<id>" }`.
2. `ref_axis` methods: `line` (a straight edge, sketch line or axis), `two_planes`, `two_points`, `cylinder` (a cylinder or cone face, or a round edge), `point_normal` (a point and a plane or face). Option `reverse`.
3. `ref_point` methods: `arc_centre` (a round edge), `face_centre`, `intersection` (two lines, a line and a plane, or two items that touch), `projection` (a point onto a plane, face or edge), `along_curve` (an edge; `distance`, or `percent` with `by_percent`; `reverse` measures from the other end), `sketch_point` (a vertex, sketch point, reference point or the origin), `values` (`x`, `y`, `z`).
4. `coord_system` methods: `directions` (first: the origin point, else `x`, `y`, `z` values; second: the X direction; third: the Z direction; a straight edge or axis points along it, a point towards it, a plane or flat face along its normal; options `reverse_x`, `reverse_z`; a missing direction keeps the model axis) and `angles` (`rx`, `ry`, `rz`, applied about model X, then Y, then Z; origin as for `directions`).

Example:

```json
{ "id": "f9", "type": "ref_plane", "name": "Plane 1", "suppressed": false,
  "params": { "method": "offset", "distance": { "expr": "5", "value": 5.0 } },
  "refs": { "first": { "kind": "face", "name": "f6/cap/end", "snapshot": { "surface": "plane" } } } }
```

#### 5.3.21 Hole parameters (Phase 4, DECISIONS D310 to D313)

1. `hole_type`: `"simple"`, `"counterbore"`, `"countersink"`, `"tapped"`, `"heat_set_insert"`, `"nut_trap"` or `"nut_slot"`.
2. `standard` (`"iso"`, `"ansi"`), `purpose` (`"drill"`, `"tap_drill"`, `"clearance"`), `size` (a size name such as `"M5"` or `"1/4-20"`) and `fit` (`"close"`, `"normal"`, `"loose"`): what the values were filled from. The geometry uses only the stored lengths below.
3. `diameter`: length. `end_condition`: `"blind"` (with `depth`), `"through_all"`, `"up_to_next"` (to where the hole axis first comes out of the material; TOOL_SPEC T16 item 4), `"up_to_vertex"` (with `refs.up_to_vertex`) or `"up_to_face"` (with `refs.up_to`). `bottom`: optional, `"drill_point"` with `tip_angle` (angle); left out for a flat bottom.
4. Counterbore: `cbore_diameter`, `cbore_depth`. Countersink: `csk_diameter`, `csk_angle` (included angle).
5. Options: `head_clearance` (length), `near_csk` (boolean, with `near_csk_diameter` and `near_csk_angle`, for simple, tapped and heat set insert holes), `far_csk` (boolean, with `far_csk_diameter` and `far_csk_angle`, Through All only). Booleans are written only when true.
6. Tapped: `thread_depth`, `thread_diameter` (the major diameter), `pitch` (lengths), `cosmetic_thread` and `modeled_thread` (optional booleans, sections 5.3.22 and 5.3.23).
7. Nut trap and nut slot: `nut_flats`, `nut_height` (lengths) and `nut_angle` (angle); the slot also `slot_offset` (face to the top of the slot) and `slot_length` (axis to the open end).
8. `print_fit`: optional, `"none"`, `"clearance"`, `"slip"` or `"press"`, with `fit_tolerance` (length, copied from the printer profile when chosen, D311).
9. Positions: either `refs.sketch` (an existing sketch) with the optional booleans `use_points`, `use_ends` (both default true) and `use_centres` (default false), or the hole's own points in `data.positions` (sketch data as in section 6, points only) on `refs.plane` (a plane feature or a flat face).
10. `refs.face`: optional list with one face reference (flat or curved) where the holes start. `refs.up_to`: one face reference for Up to Face. `refs.up_to_vertex`: a list with one vertex reference or sketch point for Up to Vertex (DECISIONS D466); the holes stop at the level of that point along each hole axis.
11. Face roles, per position point `p` (its sketch entity id): `hole/<p>/wall`, `bottom`, `tip`, `cbore_wall`, `cbore_floor`, `csk`, `far_csk`, `far_wall`, `head`, `head_wall`, `hex/<k>`, `hex/floor`, `slot/<k>`.
12. Slots (DECISIONS D524): `slot` (optional boolean, written only when true; simple, counterbore and countersink holes only, ignored on other types) with `slot_span` (length: the slot length), `slot_span_mode` (optional, `"overall"` when the length is measured end to end; left out for centre to centre) and `slot_angle` (optional angle in the face plane from the position sketch's X axis; left out for 0). The length key is not `slot_length`, which the nut slot uses for another length. A slot hole names its straight sides `hole/<p>/<role>/side1` and `side2` and its round ends `hole/<p>/<role>/end1` and `end2`; flat faces across the slot (`head`, `cbore_floor`, `bottom`) keep the plain role.

#### 5.3.22 Cosmetic thread parameters (Phase 4, DECISIONS D314)

1. `size`: the size name the values were filled from (shown in the thread label).
2. `diameter` (major diameter) and `pitch`: lengths.
3. `end_condition`: `"blind"` (with `length`) or `"full"` (the whole round face). `reverse`: optional boolean, written only when true.
4. `refs.edge`: a list with one edge reference, a round edge of a hole or shaft.
5. The feature makes no geometry and no face roles. Tapped holes with `cosmetic_thread: true` make the same metadata from `thread_diameter`, `pitch` and `thread_depth`.

#### 5.3.23 Modelled thread parameters (Phase 4, DECISIONS D315)

1. `size`: the size name the values were filled from. `diameter` (major diameter) and `pitch`: lengths.
2. `method`: `"cut"` or `"extrude"`. `hand`: `"right"` or `"left"`. `starts`: number, 1 to 4.
3. `end_condition`: `"blind"` (with `length`), `"revolutions"` (with `revolutions`, a number) or `"up_to"` (with `refs.up_to`).
4. `offset`: optional length, moves the start along the axis. `keep_length`: boolean, default true. `start_angle`: optional angle. `reverse`: optional boolean, written only when true.
5. `refs.edge`: one round edge of a hole or shaft. `refs.up_to`: a list with one vertex or flat face reference, or a plane feature (`{ "feature": "f3" }`).
6. Face roles: `thread/face#k`. Tapped holes with `modeled_thread: true` name the thread faces `hole/<p>/thread/face#k`.

#### 5.3.24 Mounting boss parameters (Phase 4, DECISIONS D316)

1. `boss_type`: `"screw_thread"`, `"screw_head"`, `"pin"` or `"pin_hole"`. `boss_diameter`, `boss_height` (lengths), `boss_draft` (optional angle).
2. Screw types: `hole_diameter`, `hole_depth`; head side also `head_diameter`, `head_depth`. Pin types: `pin_diameter`, `pin_height`.
3. Fins: `fin_count` (number, 0 for none), `fin_angle`, `equally_spaced` (boolean, default true) or `fin_angle2`, `fin_length`, `fin_width`, `fin_height`, `fin_draft` (optional angle), `chamfer_distance` (0 for none) and `chamfer_angle`.
4. Position (shared by the boss and the snap hook): `refs.position` (a list with one vertex, round edge or `{ "feature", "sketch_entity" }` sketch point), else the lengths `pos_x`, `pos_y`, `pos_z`. `refs.face`: the face it stands on. `refs.direction` (boss) or `refs.up` (hook): optional plane feature, flat face or straight edge.
5. `refs.fin_direction`: optional straight edge that fin angle 0 points along.
6. Face roles: `boss/side`, `boss/top`, `fin/<k>/face/<j>`, `fin/<k>/face/start`, `fin/<k>/face/end`, `hole/wall`, `hole/bottom`, `hole/cbore_wall`, `hole/cbore_floor`, `pin/side`, `pin/top`.

#### 5.3.25 Snap hook parameters (Phase 4, DECISIONS D317)

1. `body_height` (length, unless `refs.mate_face` gives it), `base_depth`, `top_depth`, `total_width`, `overhang`, `hook_height`, `lip_height` (lengths) and `top_draft` (angle).
2. `up_reverse`, `hook_reverse`: optional booleans. `hook_angle`: optional angle. `refs.hook_direction`: optional plane feature, flat face or straight edge.
3. Position as in 5.3.24 item 4: `refs.position`, else `pos_x`, `pos_y`, `pos_z` (lengths); `refs.face`; `refs.up` (optional).
4. Face roles: `hook/face/<k>` (base, back, top, lead, lip, catch, front, in that order; lip is left out when `lip_height` is 0), `hook/face/start`, `hook/face/end`.

#### 5.3.26 Snap hook groove parameters (Phase 4, DECISIONS D317)

1. `offset_height`, `hook_height`, `gap_height`, `groove_clearance`, `gap_clearance`, `offset_width`: lengths.
2. `refs.hook`: `{ "feature": <snap hook id> }`. `refs.body`: a list with one face of the body to cut.
3. Face roles: `groove/face/<k>`, `groove/face/start`, `groove/face/end`.

#### 5.3.27 Lip and groove parameters (Phase 4, DECISIONS D318)

1. `lip_width`, `lip_height` (lengths), `lip_draft` (optional angle). `link`: boolean, default true.
2. With `link`: `spacing` and `gap` (lengths). Without: `groove_width`, `groove_height` (lengths), `groove_draft` (optional angle).
3. `refs.lip_faces`, `refs.groove_faces`: flat rim face references (either list may be left out). `refs.direction`: optional.
4. Face roles: `lip/<k>/side/<j>`, `lip/<k>/top`, `groove/<k>/side/<j>`, `groove/<k>/top` (the groove floor), with `inner/` faces for the band's inner wall; `#j` is added per opening when a rim has several.

#### 5.3.28 Vent parameters (Phase 4, DECISIONS D319)

1. `rib_width`, `rib_depth`, `rib_offset`, `spar_width`, `spar_depth`, `spar_offset`, `fill_depth`, `fill_offset`: lengths.
2. `refs.sketch`: the vent sketch. `refs.face`: one flat face reference.
3. `refs.boundary`, `refs.ribs`, `refs.spars`, `refs.fill`: lists of `{ "feature": <sketch id>, "sketch_entity": <id> }`.
4. Face roles: `opening/face#k`, `rib/face#k`, `spar/face#k`, `fill/face#k`.

#### 5.3.29 Rib parameters (Phase 4, DECISIONS D320)

1. `thickness`: length. `side`: `"first"`, `"both"` or `"second"`.
2. `direction`: `"parallel"` (grows in the sketch plane) or `"normal"` (grows out of it). `flip`: optional boolean, written only when true.
3. `draft_angle`: optional angle (Normal to Sketch from one straight line); its presence turns draft on. `draft_outward`: optional boolean.
4. `extend`: `"linear"` or `"natural"`.
5. `refs.sketch`: an open chain of lines and arcs. `refs.body`: optional list with one face of the body the rib joins (needed in a part with several bodies).
6. Face roles: `rib/face#k`.

#### 5.3.30 Dome parameters (Phase 4, DECISIONS D321)

1. `distance`: length; 0 on a round face makes a dome tangent to the side.
2. `reverse`, `elliptical`, `continuous`: optional booleans, written only when true.
3. `refs.faces`: flat face references.
4. Face roles: `dome/<k>/face#j`, `k` counting the picked faces from 1.

#### 5.3.31 Wrap parameters (Phase 4, DECISIONS D322)

1. `wrap_type`: `"emboss"`, `"deboss"` or `"scribe"`. `thickness`: length (emboss and deboss). `reverse`: optional boolean, written only when true.
2. `refs.sketch`: a sketch of closed contours on a plane that touches the face. `refs.face`: one cylindrical or flat face reference.
3. Face roles: `wrap/face#k`. Scribe adds no faces of its own; the split faces keep their names with `#k`.
4. `method` (optional, DECISIONS D528): `"spline"` for the Spline surface method; left out for the default `"analytical"`. With `"spline"` the face may be any face and the sketch plane need not touch it: the sketch origin is projected onto the face and the sketch is mapped through the face's parameters, so lengths match near that point. The sketch must stay on the face. `reverse` is not used with `"spline"`. Schema note: an optional addition to an existing feature type, not a schema change. Files without it open and save unchanged.

#### 5.3.32 Sheet metal (`sheet_metal`, `base_flange`, `edge_flange`, `sketched_bend`, `flatten`; Phase 5, DECISIONS D330 to D340)

1. Like the Phase 3 types, these add only new `type` strings, optional `params` and `refs`, and one optional top level key (`bend_table`). Files without them are unchanged; this is not a schema change. Older files open and save byte for byte the same.
2. `sheet_metal` (the Sheet Metal folder, placed just below the default planes): `thickness`, `radius` (inside bend radius), `method` (`"k_factor"`, `"bend_allowance"`, `"bend_deduction"`, `"bend_table"`), `k_factor` (number, default 0.44), `allowance` (length, for the allowance and deduction methods), `relief` (`"rectangular"`, `"obround"`, `"tear"`), `relief_by` (`"ratio"` or `"size"`), `relief_ratio` (number, 0.05 to 2.0), `relief_width`, `relief_depth` (lengths). Top level key `bend_table`: CSV text, one row per thickness (mm), radius (mm), angle (degrees) and allowance (mm); an optional first header row.
3. Every other sheet metal type has `refs.sheet_metal` (`{ "feature": "f5" }`, the folder). `base_flange`, `edge_flange` and `sketched_bend` may override the folder with their own `radius`, `method`, `k_factor`, `allowance`.
4. `base_flange`: `refs.sketch`; optional `flip_side`, `symmetric`; the From keys of extrude (`start_condition`, `start_offset`, `start_reverse`, `refs.start`); for open profiles the end keys of extrude (`end_condition` `"blind"`, `"mid_plane"`, `"two_directions"`, `"up_to_vertex"`, `"up_to_face"`, `"offset_from_face"`; `depth`, `depth2`, `reverse`, `end_condition2`, `end_offset`, `end_offset2`, `end_offset_reverse`, `end_offset_reverse2`, `refs.end`, `refs.end2`). Face roles: `bottom`, `top`, `side/<entity>` (closed); `wall/<line>/<role>` and `bend/<entity>/<role>` (open).
5. `edge_flange`: `refs.edges` (edges in pick order); `angle`, `angle_mode` (`"angle"`, `"perpendicular"`, `"parallel"`, with `refs.angle_face`), `end_condition` (`"blind"`, `"up_to_vertex"` with `refs.end`), `vertex_end` (`"normal"`, `"parallel"`), `length`, `length2` to `length8` (own lengths of the 2nd to 8th edges), `length_from` (`"outer_sharp"`, `"inner_sharp"`, `"tangent"`), `reverse`, `position` (`"material_inside"`, `"material_outside"`, `"bend_outside"`, `"virtual_sharp"`), `trim_side_bends` (false when missing), `gap`, and own relief keys as the folder. Face roles: `flange<k>/<role>`, `bend<k>/<role>`, `trim<k>/<role>`, `relief<k>a/<role>`, `relief<k>b/<role>`.
6. `sketched_bend`: `refs.sketch` (one line on a flat face of the sheet); `angle`, `reverse`, `position` (`"centreline"`, `"material_inside"`, `"material_outside"`, `"bend_outside"`), `flip_fixed`. Face roles: `bend/<role>`, `split/<role>`, `moved/<old name>`.
7. `flatten` (Flat Pattern, always last): `flattened`, `bend_lines`, `bounding_box` (booleans, false when missing); optional `refs.grain` (an edge). Features after it apply to the flat state only.
8. Wall roles are `bottom`, `top`, `start`, `end`, `side1`, `side2`; bend roles `inner`, `outer`, `side1`, `side2`.

#### 5.3.32A Later sheet metal tools (`hem`, `miter_flange`, `jog`, `closed_corner`, `break_corner`, `rip`, `tab_slot`, `convert_sheet`, `insert_bends`, `cross_break`, `unfold`, `fold`, `form_tool`; DECISIONS D530 to D547)

1. Like 5.3.32, these add only new `type` strings, optional `params` and `refs`, and one optional top level key on the folder (`gauge_table`). Files without them are unchanged. Every type has `refs.sheet_metal`.
2. Folder (`sheet_metal`) additions: `corner_relief` (`"rectangular"`, `"circular"`), `corner_relief_size` (length, the circle diameter), `gauge` (a row name of `gauge_table`, stored only while a gauge is used). Top level key `gauge_table`: CSV text, one row per gauge: name, thickness (mm), then one or more inside radii (mm); an optional first header row. `edge_flange` may also have its own `corner_relief` and `corner_relief_size` (D540); face roles `corner<i>_<j>/round`.
3. `hem`: `refs.edges`; `hem_type` (`"closed"`, `"open"`, `"teardrop"`, `"rolled"`), `length`, `gap` (open hems), `radius`, `angle` (teardrop and rolled), `position` (`"material_inside"`, `"material_outside"`), `reverse`, `corner_gap`, and own relief keys as the folder. Face roles: `bend<k>/<role>`, `hem<k>/<role>`, `trim<k>/<role>`.
4. `miter_flange`: `refs.edges` (one chain on one face of one wall), `refs.sketch` (an open chain of lines); `gap`, `radius`, `method`, `k_factor`, `allowance`. Face roles: `e<i>/wall<k>/<role>`, `e<i>/bend<k>/<role>`, `trim<i>/<role>`.
5. `jog`: `refs.sketch` (one line); `offset`, `offset_from` (`"same_face"`, `"inner_faces"`, `"outer_faces"`), `angle`, `reverse`, `position` (as `sketched_bend`), `flip_fixed`, `radius`, `method`, `k_factor`, `allowance`. Face roles: `bend1/<role>`, `bend2/<role>`, `split/<role>`, `middle/<old name>`, `moved/<old name>`.
6. `closed_corner`: `refs.faces` (end faces of flange walls); `corner_type` (`"overlap"`, `"underlap"`, `"butt"`), `gap`. Face roles: `tab<k>a/<role>`, `tab<k>b/<role>`.
7. `break_corner`: `refs.edges` (corner edges through the sheet); `break_type` (`"chamfer"`, `"fillet"`), `distance`, `radius`. Face roles: `corner<k>/<role>`.
8. `rip`: `refs.sketch` (lines) and/or `refs.edges`; `gap`, `flip`. Face roles: `slit<k>/<role>`, `edge<k>/<role>`.
9. `tab_slot`: `refs.edge` (tab edge), `refs.face` (slot wall face); `tab_count` (number), `tab_length`, `depth`, `spacing`, `clearance`. Face roles: `tab<k>/<role>`, `slot<k>/<role>`.
10. `convert_sheet`: `refs.face` (fixed face), `refs.bends` (bend edges); `gap`. `insert_bends`: `refs.face`; `gap`. Face roles: `face<k>/<role>`, `bend<k>/<role>`, `trim<k>p`, `trim<k>c`, `rip<k>`.
11. `cross_break`: `refs.face`; `reverse`. No geometry; the flat pattern export adds a `CROSS_BREAKS` layer.
12. `unfold`: `all_bends` or `refs.bends` (bend faces). `fold`: optional `refs.unfold` (`{ "feature": "f9" }`). Wrapped cut faces: `<bend>/cut<k>`.
13. `form_tool`: `refs.sketch` (lines placing the forms); `tool` (`"dimple"`, `"louvre"`, `"rib"`), `diameter`, `length`, `width`, `height`, `reverse`. Face roles: `form<k>/<role>`, `lance<k>/<role>`.

#### 5.3.33 Deformation features: `bend`, `twist`, `taper`, `stretch`, `flow` (Phase 4, DECISIONS D393)

1. Common params, all optional: `axis` (`"x"`, `"y"` or `"z"`, default `"z"`: the triad's third axis; the first axis is Y, Z or X for X, Y or Z), `spin` (angle: turns the first axis about the third), `ox`, `oy`, `oz` (lengths: the triad's origin; default the centre of the picked bodies' box), `start` and `end` (lengths along the third axis from the origin: the trim planes; default where the bodies begin and end), `tolerance` (length, default 0.01 mm).
2. Refs: `bodies` (optional face references, one face per body to deform; without it every body deforms). `flow` also takes `path` (a sketch whose curves form one chain, or a curve feature, `{"feature": "f9"}`) or `path_edges` (edge references), as Pipe does.
3. `bend`: `bend_by` (`"angle"`, default, or `"radius"`), `angle` (angle) or `radius` (length). `twist`: `angle`. `taper`: `factor` (number, above zero). `stretch`: `distance` (length). `flow`: `fit` (optional boolean: spread the region over the whole curve).
4. Faces keep their names. Only the region between the trim planes deforms; beyond the end plane the part moves rigidly with it.

#### 5.3.34 Later feature types, by type name

The feature types below were added after the sections above were written. Each follows the common fields of 5.1; lengths and angles are parameter values (section 3), and `refs` hold references (section 7). Face roles are the names after the feature id (section 8).

#### 5.3.34.1 Base Pad (`base_pad`)

Base pad (TUTORIAL_REVIEW_SPEC TR414 item 2, DECISIONS D1009).

Type `base_pad`. Pick the flat face that lies on the bed (`refs.face`). A thin
removable pad, `pad_thickness` thick, is added under it as a body of its own: its
outline is the face's outline grown by `pad_margin`, and an `air_gap` separates
it from the face so it peels off after printing. With no gap the pad touches the
face but stays a separate body. New faces are `<fid>/pad/...`.

#### 5.3.34.2 Cable Tie (`cable_tie`)

Cable tie channels (TUTORIAL_REVIEW_SPEC_2 TR363, DECISIONS D879).

Type `cable_tie`. A sketch on a face of the part gives the positions
(`refs.sketch`: its points and line ends, as the Hole Tool reads them). At each
position a loop is cut for a cable tie: two entry slots down from the face,
`span` apart along the sketch X axis turned by `angle`, joined under the face
by a tunnel `cover` below it. Slots and tunnel are `tie_width` wide and
`tie_thickness` tall, each grown by `clearance`. The tunnel's top is pointed
at 45 degrees so it prints without supports; where the cover is too thin for the
point, the top is cut flat at half the cover. New faces are
`<fid>/tie/<point>/...`.

#### 5.3.34.3 Corner Ears (`corner_ears`)

Corner ears (TUTORIAL_REVIEW_SPEC TR189 item 2, DECISIONS D1005).

Type `corner_ears`. Pick the flat face that lies on the print bed (`refs.face`).
A thin round disc, `ear_diameter` across and `ear_thickness` thick, is centred on
each outer corner of that face whose inside angle is at most `max_angle` (120
degrees by default, so square and sharper corners get ears). The discs lie on the
face's plane and grow into the part, so they hold the corners down against warping
and are cut or snapped off after printing. Inside (concave) corners get none. New
faces are `<fid>/ear/<k>/...`.

#### 5.3.34.4 Crush Ribs (`crush_ribs`)

Crush ribs (TUTORIAL_REVIEW_SPEC_2 TR403, DECISIONS D891).

Type `crush_ribs`. Pick the round face of a hole or a pin (`refs.face`). Ribs
`rib_count` of them, evenly round the face, run `rib_length` along it from one end
(`from_end`; the whole face when no length). Each rib is a wedge `rib_width` wide on
the wall that stands `rib_height` off it (into a hole, out from a pin); its tip is cut
flat `rib_tip` wide so it prints cleanly, and its first `height` along the axis
ramps up from nothing, so the mating part slides in before the ribs bite. New faces
are `<fid>/rib/<k>/...`.

#### 5.3.34.5 Deform Curve (`deform_curve`)

Local deform modes: Deform Point, Curve to Curve and Surface Push (TR67, D2412).

These move part of a body and leave the rest, unlike the triad tools (bend, twist,
taper, stretch, flow), so they ignore the triad and trim planes. They share the same
NURBS deformation, tolerance check and approximate warning (feature.py, nurbs.py).
Every map works on whole arrays of points.

- `deform_point`: refs `point` (where), `direction` (optional: a direction;
  default the normal of the face the point is on, or +Z) and `fixed` (optional
  faces or edges that stay put). Params `distance`, `radius` (of influence) and
  `stiffness` (0 to 1: the part of the radius that moves the full distance).
- `deform_curve`: refs `initial` and `target` (sketches or curves) and
  `fixed`. Param `radius`: how far from the initial curve the body follows.
  Points on the initial curve move to the matching point of the target curve (by
  length along each), and the movement fades out over the radius.
- `surface_push`: refs `point` (where the tool first touches) and `direction`
  (the push, into the face). Params `tool` (sphere, ellipsoid or rectangle),
  `depth`, `tool_x` and `tool_y` (half sizes across; a sphere uses
  `tool_x`) and `reach` (how deep into the body the dent fades out; default
  three times the depth).

Parameters also written: `axis`, `spin`, `ox`, `oy`, `oz`, `start`, `end`, `tolerance`.

#### 5.3.34.6 Deform Point (`deform_point`)

Local deform modes: Deform Point, Curve to Curve and Surface Push (TR67, D2412).

These move part of a body and leave the rest, unlike the triad tools (bend, twist,
taper, stretch, flow), so they ignore the triad and trim planes. They share the same
NURBS deformation, tolerance check and approximate warning (feature.py, nurbs.py).
Every map works on whole arrays of points.

- `deform_point`: refs `point` (where), `direction` (optional: a direction;
  default the normal of the face the point is on, or +Z) and `fixed` (optional
  faces or edges that stay put). Params `distance`, `radius` (of influence) and
  `stiffness` (0 to 1: the part of the radius that moves the full distance).
- `deform_curve`: refs `initial` and `target` (sketches or curves) and
  `fixed`. Param `radius`: how far from the initial curve the body follows.
  Points on the initial curve move to the matching point of the target curve (by
  length along each), and the movement fades out over the radius.
- `surface_push`: refs `point` (where the tool first touches) and `direction`
  (the push, into the face). Params `tool` (sphere, ellipsoid or rectangle),
  `depth`, `tool_x` and `tool_y` (half sizes across; a sphere uses
  `tool_x`) and `reach` (how deep into the body the dent fades out; default
  three times the depth).

Parameters also written: `axis`, `spin`, `ox`, `oy`, `oz`, `start`, `end`, `tolerance`.

#### 5.3.34.7 Drain Holes (`drain_holes`)

Drain holes (TUTORIAL_REVIEW_SPEC TR189 item 3, DECISIONS D1006).

Type `drain_holes`. For every closed void of the part (a hollow left by Shell with
no face removed, core/cavities.py), one round hole `hole_diameter` across is cut
from the void's lowest point (`toward` "bottom") or highest point ("top") straight
down or up along Z, out through the part's wall, so liquid resin drains from where
it pools. The holes run past the part, so they always open to the outside. New
faces are `<fid>/drain/<k>/...`.

#### 5.3.34.8 Edge Profile (`edge_profile`)

Edge Profile: router shapes swept along edges (TR243, DECISIONS D2011).

Type `edge_profile`. Refs: `loop_face` (a flat face: the profile runs round its
outer loop) or `edges` (a chain of joined edges). Params:

- `router_profile`: `round_over` (default), `cove`, `rabbet`, `chamfer_flat` or
  `ogee`.
- `profile_size`: length, the profile's width across the face.
- `profile_depth`: optional length, the depth down the side (`rabbet` and
  `chamfer_flat`; the size when left out).

The cut's cross section sits in the corner between the face (the first face of
the first edge, for picked edges) and the side face, and is swept along the loop
with round joins at corners, keeping its turn to the face's normal. Faces of the
cut are `<fid>/profile#k`.

#### 5.3.34.9 Edit Bends (`edit_bends`)

Edit Bends (TR167, DECISIONS D1102): new radius and allowance for bends already made.

Type `edit_bends`. Params: `all_bends` (every bend of the sheet), `radius`,
`method`, `k_factor`, `allowance` (each optional: a value not given keeps the
bend's radius, or comes from the Sheet Metal parameters for the allowance).
Refs: `bends` (a face of each bend), `sheet_metal`.

Each chosen bend keeps the line where it starts on its parent wall; its radius and
its flat length change, and the walls after it move with it. Works on bends of
flanges, converted solids and Insert Bends parts alike, since all keep the same
sheet model.

Face roles: as the bends they change.

#### 5.3.34.10 Extend Wall (`extend_wall`)

Extend Wall (TR370 item 1, DECISIONS D1109): lengthen a wall to a distance, plane or face.

Type `extend_wall`. Pick an edge face of a wall (a face through the sheet thickness,
square to the wall). The wall grows out of that face, keeping its outline, by
`distance` (`end_condition` "blind", the default) or up to a plane or flat face
(`end_condition` "up_to", `refs.limit`), measured along the face's normal at its
centre. The new material belongs to the wall, so it folds and flattens with it.

Params: `end_condition`, `distance`. Refs: `face`, `limit`, `sheet_metal`.

Face roles: `<fid>/extend/<role>` and the wall's own.

#### 5.3.34.11 Face Relation (`face_relation`)

Lasting face relations on bodies with no history (TR266, DECISIONS D2418).

Type `face_relation`: a relation between faces of a body, often an imported one,
kept in the feature tree. It does not change the part; it checks that the relation
holds now (a warning when not) and later Move Face features keep it:

- `coplanar`: two flat faces on one plane. A move of one moves the other with it.
- `offset`: two parallel flat faces keep their distance: an offset of one moves the
  other the same way.
- `concentric`: two round faces on one axis. A translate or rotate of one takes the
  other along.
- `parallel` and `perpendicular`: two flat faces keep their angle. A rotate of one
  turns the other with it.
- `equal_radius`: two round faces keep one radius. An offset or resize of one does
  the same to the other.
- `fixed`: one or more faces that a Move Face may not move.

Refs: `faces` (two faces; one or more for `fixed`). Param: `relation`.

#### 5.3.34.12 Face Seats (`face_seats`)

Face Seats: copies of a seed body set over a curved face (TR405, DECISIONS D2009).

Type `face_seats`. Refs: `on_face` (the face to cover: a cylinder, sphere, cone,
torus or free form face) and `seed` (a face of a separate body, the seed: it is
modelled at the origin with +Z pointing out of the face it will sit on). The seed
body is used up. Params:

- `count_u` and `count_v`: copies along the face's two directions (1 to 100
  each); copies whose spot is off the face are left out.
- `sink`: optional length: how far each copy sinks into the face along the
  normal (so studs join and dimples bite).
- `operation`: `boss` (default: join the copies, for studs and rivets) or
  `cut` (cut them away, for dimples).

Each copy's origin goes to a spot on the face, its +Z to the face's outward
normal there and its +X along the face's first direction. Copy faces are
`<fid>/seat<k>/...` (boss) or `<fid>/seat#k` (cut).

#### 5.3.34.13 Fill Pattern (`fill_pattern`)

Fill Pattern: fill a flat or cylinder face with copies (TR57, D792; TR398, D1903).

Copies a seed (`features`, `faces` or `bodies`, as the other patterns) or
cuts a built-in shape at points laid out over one flat face, keeping only the
copies that fit: grilles, vents and weight reduction holes.

Params:

- `layout`: `grid`, `staggered` or `rings`.
- `spacing` (length): between copies; `row_spacing` (optional length): between
  grid rows, or between rings (else `spacing`).
- `stagger_angle` (optional angle, default 60 degrees): a staggered grid's rows
  lean by it, so 60 degrees gives an even triangular layout.
- `ring_shape` (optional): `circle`, `square` or `polygon` rings; `sides`
  (number) for polygon rings and shapes.
- `margin` (optional length): how far every copy stays from the face's edges.
  A negative margin lets copies run past the edge by that much.
- `fit` (optional): `shape` (default, the whole copy with the margin must lie
  on the material) or `centre` (only the centre, the margin away from the edge).
- `shape` (optional): `none` (copy the seed), `circle`, `square`,
  `diamond` or `polygon` with `size` (length, across), `shape_angle`
  (optional angle) and `depth` (optional length; else through the part).
- `surface_spacing` (TR398, D1903): on a cylinder face, `mapped` (default: the
  spacing round the face is measured along the surface) or `projected` (measured
  in the plane touching the face at the start, as seen from straight on).
- `size_end` (TR324, D1518): optional length; the shapes grow or shrink from
  `size` at `refs.gradient_from` (a point or vertex, or an edge; else the start
  point) to `size_end` at the farthest copy. Each copy must fit with its own size.

Refs: `face` (the flat face to fill) or `sketch` (a sketch whose closed region
is filled, with optional picked `regions`: the one holding `point`, else the
largest; cuts go against the sketch plane's normal), optional `direction` (a straight edge:
the grid's first direction, else the face plane's own) and `point` (where the
layout starts, else the face's centre), and the seed. Key `skip`: `[k, 1]`
pairs, `k` counting the kept copies from 1 in layout order.

The number of copies is in the result's `extras["count"]`. Face roles of the
built-in shape: `cut/<k>/face#j`.

Parameters also written: `geometry`, `merge`, `propagate_colours`, `preview`, `region_mode`, `vary`, `instance_values`, `check`, `gradient`.

#### 5.3.34.14 Finger Joint (`finger_joint`)

Finger joints between plates (TUTORIAL_REVIEW_SPEC_2 TR246, DECISIONS D883).

Type `finger_joint`. Pick two plate bodies that meet at an edge and overlap at
the corner (both drawn out to the outside of the box, as boxes are usually
modelled). The corner block where they overlap is split along the edge into
fingers: `finger_count` of them, or as many as fit `finger_width`. Fingers
take turns: the first plate keeps the odd ones, the second the even ones, and
each plate loses the other's. `clearance` widens every gap along the edge and
`kerf` (a laser's cut width) narrows it, so the cut parts fit. Used for laser
cut boxes. New faces are `<fid>/finger/...`.

#### 5.3.34.15 Flat Marks (`flat_marks`)

Flat Marks (TR283 item 2, DECISIONS D1112): sketch lines mapped onto the flat pattern.

Type `flat_marks`. Every line of a sketch drawn on a flat face of a wall becomes a
cosmetic mark on that wall, like Cross Break's lines (D539): it shows folded and
flat, and the flat pattern DXF and SVG write it with the other marks, so layout
lines, hole centres or part numbers drawn as lines reach the flat blank. Arcs and
circles are written as short lines through points 1 mm apart or less. The part's
shape does not change.

Params: `title` (optional text, "Mark" by default). Refs: `sketch`, `sheet_metal`.

#### 5.3.34.16 Follow Pattern (`follow_pattern`)

Follow Pattern: repeat a later feature at every copy of an existing pattern

(TR399 items 1 and 2, D1904).

Refs: `pattern` (`{"feature": <pattern id>}`) and the seed: `features`,
`faces` or `bodies`, as the other patterns. Key `on`: the `[i, j]` copy of
the pattern the seed was built on (`[1, 1]`, the original, by default). Each
rebuild reads the followed pattern's copies, so its count and layout changes carry
over. Params: the shared pattern params (`geometry` and so on).

Parameters also written: `merge`, `propagate_colours`, `preview`, `region_mode`, `vary`, `instance_values`, `check`.

#### 5.3.34.17 Gusset (`gusset`)

Gusset (TUTORIAL_REVIEW_SPEC TR12.1, DECISIONS D700): a stiffening rib pressed into a bend.

Type `gusset`. Params: `depth` (how far the rib reaches along each wall from the
bend), `width` (across the rib, along the bend), `profile` ("round", the default,
or "flat"), `rib_position` (how far the rib's middle sits from the middle of the
bend, along it; 0 when missing) and `flat_cutout` (cut the rib's place out of the
flat pattern; off leaves the flat pattern as it is).

Refs: `walls` (two face references, one on each wall the bend joins),
`sheet_metal`.

In the bend's cross section the rib fills the inside corner between the two walls,
up to `depth` along each wall; the outside gets the same shape pressed in, moved
out by the sheet thickness, so the sheet keeps its thickness at the rib's middle.
Both are folded part only, like forming tools (D546).

Face roles: `<fid>/rib/<role>` and `<fid>/press/<role>`.

#### 5.3.34.18 Half Lap (`half_lap`)

Half lap joints between crossing plates (TUTORIAL_REVIEW_SPEC_2 TR364, DECISIONS D882).

Type `half_lap`. Pick two plate bodies that cross (`refs.bodies`). Each plate's
thickness direction is the normal of its largest flat face; the joint runs along
the line where the plates meet (the cross product of the two normals). Where they
cross, the first plate is notched from one side and the second from the other, so
they slot together: the first loses the part of the crossing above the split, the
second the part below. `depth` is the split as a percent of the crossing's height
(50 is half and half). Each notch is the other plate grown by half the
`clearance` on each side and shrunk by half the `kerf` (a laser's cut width),
so the cut parts fit. New faces are `<fid>/lap/...`.

Parameters also written: `depth_percent`.

#### 5.3.34.19 Heal Edges (`heal_edges`)

Heal Edges: close small gaps and loose edges of a body (TR262, D1807).

The Geometry Check fix for edges with gaps (D356) and inexact edges (D1416). The
kernel's shape fixer runs on every solid of the part: edge curves and their face
curves are made to agree again (same parameter), vertex and edge tolerances are
cut back to what the geometry needs, and small gaps between the edges of a face
outline are closed. Only the tolerances and curve fits change: no face moves, so
every face keeps its name.

Params: `tolerance` (length, default 0.01 mm): the largest gap closed. A gap
larger than that stays and is named in a warning, with the next step.

#### 5.3.34.20 Hinge (`hinge`)

Hinge: a knuckle hinge between two bodies (TR404, DECISIONS D2008).

Type `hinge`. Pick a straight edge where two bodies meet (`refs.edge`): the
hinge axis runs along it. The edge's own body takes the first, third ... knuckle,
the body touching it the others. Params:

- `knuckles`: number of knuckles (2 to 15, default 3).
- `knuckle_diameter`: length, the knuckles' outer diameter.
- `clearance`: length, the gap round every moving part.
- `form`: `pin` (default: a hole right through for a pin) or `print_in_place`
  (cone pins on the first body's knuckles in cone sockets of the other's, so the
  hinge prints as one and turns once off the bed).
- `pin_diameter`: length, the hole for `pin`.
- `pin_cone_angle`: angle, the cone's sides from the axis for `print_in_place`
  (45 degrees by default, which prints with the axis upright at a 45 degree
  overhang limit).
- `detents`: optional flag: a small bump on each end of the first body's knuckles
  clicks into a dimple in the next knuckle.

Each body keeps its faces' names; knuckle faces are `<fid>/knuckle<k>#j`.

#### 5.3.34.21 Hose Fitting (`hose_fitting`)

Hose barbs and luer fittings (TUTORIAL_REVIEW_SPEC_2 TR406, DECISIONS D914).

Type `hose_fitting`: a round fitting standing on a face (`refs.base_face`) at
a vertex or the centre of a round edge (`refs.base_point`; the typed `pos_x/y/z`,
or the middle of the face when neither is given), square to the face or along
`refs.direction`, joined to the part, with a bore through it that goes
`bore_depth` into the part.

- `fitting` `barb`: a stem the size of the hose's inside (`hose_diameter`)
  with `ring_count` barbs, each `ring_length` long, that step out to
  `barb_diameter` (default 1.15 times the hose size) facing the part and taper
  back toward the tip, so a hose slides on and does not pull off.
- `luer_male` and `luer_female`: the 6 percent luer taper (ISO 80369-7 sizes:
  a male tip 3.925 mm across at its end, a female opening 4.27 mm, 7.5 mm long),
  on a round base `body_diameter` across.

`shank_height` is the plain round part between the face and the barbs or taper.
New faces are `<fid>/fitting/<k>` and `<fid>/bore/<k>`.

Parameters also written: `bore_diameter`.

#### 5.3.34.22 Indent (`indent`)

Indent (TR68, DECISIONS D1026): reshape a target body round a tool body.

Type `indent`. Pick the target body, then the tool body (`refs.bodies`, in that
order). The tool stays as it is. `indent_mode`:

- `indent` (default): the target gets a wall `indent_thickness` thick round the tool,
  `indent_clearance` away from it, where the tool presses into or stands beside the target;
  the space the tool takes, grown by the clearance, is taken out. Only the part of
  that wall within one thickness of the target is added, so the wall follows the
  target rather than wrapping the whole tool.
- `cut`: only the space the tool takes, grown by the clearance, is taken out of the
  target: a pocket that follows an inserted part.

New faces are `<fid>/indent/<k>`, numbered by position (D1068).

#### 5.3.34.23 Inlay (`inlay`)

Multi colour inlay (TUTORIAL_REVIEW_SPEC_2 TR184, DECISIONS D867).

Type `inlay`. A sketch on a face of the part (text or shapes, `refs.sketch`,
optionally `refs.regions`) is cut `depth` into the part, and the material it
removes becomes a separate body of the same shape: the inlay, printed in a second
colour. Its faces are named `<fid>/inlay/...`; the pocket faces use the usual
extrude names. Exports keep the inlay as its own body, so a 3MF holds both.

#### 5.3.34.24 Insert Part (`insert_part`)

Insert Part: the bodies of another FDCAD part as one feature (TR71, DECISIONS D2420).

Type `insert_part`. Params:

- `part_file`: the other part's file path. With `link` on (the
  default) the file is read and rebuilt at every rebuild of this part, so the
  inserted bodies follow changes to it; the rebuild cache keys on the file's size,
  time and contents. A missing file is an error that says where it looked.
  Since DECISIONS D2625 a writer stores the path relative to this part's file,
  with `/` between folders (`plate.fdprt`, `parts/plate.fdprt`), when the other
  part is in the same folder or a folder below it, and the full path otherwise. A
  reader takes a relative path from the folder of this part's file. A full path
  (all files written before D2625) is used as it is when its file is there; when
  it is not, a file of the same name beside this part is used. Saving to another
  folder writes the path again for the new place.
- `link`: off after Break Link: the bodies come from `refs.embedded` (a STEP
  block in this part, FDEF_SPEC 11) and the file is not read again.
- `keep_bodies`: optional text, the numbers of the source's bodies to bring in
  (from 1), such as "1, 3"; empty for all.
- `with_sketches` and `with_planes`: optional booleans: the source's sketch
  outlines and its own planes come in too, as reference lines in the view.
- Placement as Linked Body Copy (`place`, `dx` ... `rz` or `refs.frame`),
  about the source's own origin.

Opening a part never runs code: the source is read as data
with the part file reader, and a part that inserts itself, directly or through
another, is refused. Bodies are new bodies; faces are `<fid>/part/<name>`.

Parameters also written: `dy`, `dz`, `rx`, `ry`.

#### 5.3.34.25 Interlock (`interlock`)

Material interlock teeth (TUTORIAL_REVIEW_SPEC TR414 item 1, DECISIONS D1216).

Type `interlock`. Pick a flat face of one body that lies against another body
(`refs.face`), where two bodies printed in different materials meet. The
boundary gets a checkerboard of square teeth, `tooth_size` wide and
`tooth_depth` deep: on one colour of squares the picked body reaches into the
other, on the other colour the other body reaches back, so the two materials
lock together. The teeth stay inside the face's outline. Each body stays its own
body; new faces are `<fid>/teeth/...`.

#### 5.3.34.26 Joint Helper (`joint_helper`)

Joint helpers between two touching bodies (TR401, DECISIONS D2014).

Type `joint_helper`. Refs: `bodies`: two body picks (a face of each): the
first is the part cut into, the second the part that goes in. They must touch on
a flat face. Params:

- `joint`: `groove` (default: the second body's whole end goes into a groove,
  a dado; at the first body's edge it is a rabbet), `rabbet` (the same cut,
  named for a joint at an edge), `mortise` (a tenon on the second body, smaller
  than its end by the `shoulder` on every side, into a mortise) or `dowels`
  (two dowel holes across the joint, `dowel_diameter` wide, `depth` into
  each body).
- `depth`: length, how far the joint goes into the first body.
- `joint_clearance`: optional length, the gap round the part that goes in.
- `shoulder`: optional length (mortise), `dowel_diameter` (dowels).

Faces of the cuts and of the added piece are `<fid>/joint#k`.

#### 5.3.34.27 Knurl (`knurl`)

Knurl: straight or diamond knurling on a cylinder face (TR163 item 1, D2015).

Type `knurl`. Refs: `round_face` (a cylindrical face). Params:

- `knurl_pattern`: `straight` (default: V grooves along the axis) or `diamond`
  (two sets of V grooves on 30 degree helices, one each way).
- `knurl_pitch`: length, the groove spacing round the cylinder.
- `knurl_depth`: length, how deep the V grooves go.

The grooves run past both ends of the face. The count round the cylinder is
the circumference over the pitch, rounded. Groove faces are `<fid>/knurl#k`.

#### 5.3.34.28 Landing Pad (`landing_pad`)

Landing Pad: a flat pad on a sloped or curved wall (TR325, DECISIONS D2013).

Type `landing_pad`. Refs: `wall_face` (the sloped or curved wall) and
`sketch` (a closed outline; the sketch plane is the pad's flat face, its normal
pointing out of the wall). Params:

- `pad_mode`: `raise` (default: the pad is built out from the wall up to the
  sketch plane) or `press` (the pad is sunk into the wall down to the sketch
  plane).
- `cup_wall`: optional length: for `press` on a thin walled housing, a cup this
  thick is kept behind and round the sunk pad so the wall stays closed.

Used for screw bosses and labels on curved housings. New faces are
`<fid>/pad#k`.

#### 5.3.34.29 Lattice Fill (`lattice_fill`)

Lattice Fill: fill bodies with a gyroid, diamond or honeycomb lattice (TR390, D2004).

Type `lattice_fill`. Params:

- `lattice`: `gyroid` (default), `diamond` or `honeycomb`.
- `cell`: length, the size of one lattice cell (the pitch of the hexagons for
  honeycomb).
- `wall`: length, the wall thickness.
- `skin`: optional length: a solid outer skin this thick is kept round the
  lattice, so the fill is closed; zero or left out for the bare lattice.

Refs: `bodies`: optional, a face of each body to fill; without any, every
body is filled.

Gyroid and diamond are sheets found on a grid (`core/lattice_field.py`) and
made into faceted solids, so they are heavy: the grid is capped and a cell too
small for the size is an error. Honeycomb is exact: hexagonal walls along Z.

Face roles: faces of the part keep their names where they remain; lattice faces
are `<fid>/lattice#k`.

#### 5.3.34.30 Lightening Pockets (`lightening_pockets`)

Lightening Pockets: a plate face pocketed as triangles between ribs (TR245, D2012).

Type `lightening_pockets`. Refs: `plate_face` (a flat face of a plate).
Params:

- `border`: length kept solid along the face's outer edge and round its holes.
- `web`: length, the width of the ribs between pockets.
- `cell`: length, the size of the triangles (the rib spacing).
- `corner_radius`: optional length, rounding of the pockets' corners.
- `pocket_depth`: optional length: the pockets' depth; 0 or left out cuts
  right through.

The face less its border is crossed by ribs in three directions 60 degrees apart;
what is left between them are the pockets. Each pocket is shrunk by the corner
radius and grown back, which rounds its corners; pockets too small for that are
left solid. Pocket faces are `<fid>/pocket#k`.

#### 5.3.34.31 Linked Copy (`linked_copy`)

Linked Body Copy: a copy that follows the original (TR154, DECISIONS D2417).

Type `linked_copy`. Refs: `bodies` (a face of each body to copy). The copy is
made from the bodies as they are at the end of the part, so features added to the
original after the copy (also further down the tree) show on the copy too: the
rebuild builds linked copies, and the features that use their faces, after every
other feature (deferred_order). Params:

- `place`: `offset` (default: `dx`, `dy`, `dz` and turns `rx`, `ry`,
  `rz` about the bodies' centre, turned before the shift) or `on_frame` (the copy
  sits on `refs.frame`, a coordinate system or plane, as the original sits on the
  model origin).

Break Link (break_link) turns the link off (`data["link"]` false) and puts the
features in the order they are built, so the copy is built in its place from then on
and no longer follows later changes. Copy faces are
`<fid>/copy/<name>`.

#### 5.3.34.32 Living Hinge (`living_hinge`)

Living hinge patterns (TUTORIAL_REVIEW_SPEC_2 TR402, DECISIONS D908).

Type `living_hinge`. A sketch on a plate face (`refs.sketch`) outlines the area
that should bend (its closed profile). Rows of slits run along the sketch's X axis
across that area and are cut through the part: each slit `slit_length` long and
`slit_width` wide, `bridge` of material between slits in a row, rows
`row_spacing` apart, every other row shifted by half a slit so the bridges stagger.
Slits are clipped to the outline. New faces are `<fid>/slit/...`.

#### 5.3.34.33 Mark (`mark`)

Mark: text and lines put on a face for laser etching or engraving (TR330, D2006).

Type `mark`. Refs: `sketch` (`{"feature": id}`): its drawn curves and its
text are the marks. Params: `depth` (optional length): 0 or left out leaves the
part as it is and keeps the marks as lines with no depth; above 0 the closed
shapes of the sketch (letters, closed outlines) are cut that deep into the part
along the sketch normal, from the sketch plane.

The marks are kept in `extras["marks"]` (3D edges) and shown in the view. A
mark with no depth does not change the part, so it does not block sheet metal
work: the flat pattern writes marks that lie on the fixed wall to their own
`MARKS` layer in DXF and SVG.

Face roles (depth above 0): faces of the part keep their names; the cut's faces
are `<fid>/mark#k`.

#### 5.3.34.34 Measurement (`measurement`)

Saved measurement (TUTORIAL_REVIEW_SPEC_2 TR190, TR191; DECISIONS D818).

Type `measurement`. Measures the picked faces, edges or vertices of the part
(`refs.items`, one or two; none measures the whole part) on every rebuild,
using the usual naming rules, and keeps the values. Formulas read them as
measured values (D793): `"distance@Measurement 1"`, `"length@..."`,
`"diameter@..."`, `"radius@..."`, `"area@..."`, `"angle@..."` (degrees),
`"dx@..."`, `"dy@..."`, `"dz@..."` and `"volume@..."`; a value the
items do not have is 0. The view shows a label with the main value at the
items, and a line between two items' nearest points. The part is unchanged.

#### 5.3.34.35 Merge Faces (`merge_faces`)

Merge Faces: one face where picked faces lie on one surface (TR261, DECISIONS D787).

Imports and Delete Face can leave faces split by needless edges on one surface,
and later fillets and drafts fail on such edges. Merge Faces removes the edges
between the picked faces and makes one face of them; every other edge stays.

Params:

- `tolerance`: optional length, how far apart the faces may be and still count
  as one surface (default 0.001 mm, the kernel's own).
- `angle_tolerance`: optional angle, how far their directions may differ
  (default 0.1 degree).

Refs: `faces` (two or more faces), or `edges` (edges between two faces: both
faces of each edge are merged).

Face roles: the merged face keeps the name of the picked face that sorts first.

#### 5.3.34.36 Mould Cavity (`mould_cavity`)

Mould Cavity: the negative of a part in a block (TR85 item 1, D2111).

Refs: `main`: a face of the block body; `part`: a face of the part body;
`coord_system`: optional, a coordinate system feature (`{"feature": id}`).

Params:
- `uniform`: boolean (default true). `factor`: number, for uniform shrinkage
  scaling; `fx`, `fy`, `fz`: numbers along X, Y and Z otherwise.
- `about`: "centroid" (default, the part's centre of volume), "origin" or
  "coord_system" (the origin of `refs.coord_system`).
- `keep_part`: boolean (default true): the part body stays; off removes it.

The part, scaled, is subtracted from the block. Faces keep their names; the block's
new faces are named from the part's faces. Bodies not picked stay as they are.
Item 2 (a tooling split with a flat parting plane) is left to Split (D233).

#### 5.3.34.37 Offset Body (`offset_body`)

Offset Body: grow or shrink every face of a body (TUTORIAL_REVIEW_SPEC_2 TR129, D825).

Type `offset_body`. Params:

- `distance`: length, how far every face moves along its normal.
- `inward`: optional boolean, shrink instead of grow.
- `corners`: optional "sharp" (default: faces meet where they cross) or
  "rounded" (outside corners and edges become rounds of radius `distance`).

Refs: `bodies` (any face of the body; the first is used), needed when the part has
several bodies.

Each face of the body keeps its name on its moved face, so later features stay
attached; the rounds made at corners are named `<fid>/round`.

#### 5.3.34.38 O Ring Groove (`oring_groove`)

O ring grooves (TUTORIAL_REVIEW_SPEC_2 TR250, DECISIONS D886).

Type `oring_groove`. `cross_section` is the O ring's cord diameter (the
standard inch dash series and metric cords are offered in the panel). Two ways:

- Pick the round face of a shaft or a bore (`refs.face`): a groove for a piston
  seal (on a shaft) or a rod seal (in a bore) is cut `position` from one end.
- Pick a sketch on a flat face (`refs.sketch`): a face seal groove follows the
  sketch's closed curve as the ring's centre line.

Groove depth and width follow the usual design rules for the `use`: `static`
squeezes the cord about 20 percent, `moving` about 15 percent, `face` about 25
percent; the width leaves room for the ring to swell. The feature checks the
squeeze (10 to 30 percent) and how full the groove is (at most 85 percent) and
warns outside those, and reports both in `extras["oring"]`. New faces are
`<fid>/oring`.

Parameters also written: `from_end`.

#### 5.3.34.39 Parting Line (`parting_line`)

Parting Line: the edges where faces turn from positive to negative draft (TR84, D1415).

Params: `reverse` (optional boolean, the pull points the other way).
Refs: `direction`: a plane or axis feature, a flat face or a straight edge; the
pull is its normal or direction.

Each face's draft is the area weighted sine of the angle between its outward
normal and the pull, from the draft analysis triangles (D522, numpy, no loops
over triangles). Faces with no draft (square to the pull) count with the positive
side, so on an undrafted box the line runs round the bottom of the walls. The
parting edges are the edges between a positive and a negative face; they are kept
as a curve, like Projected Curve.

The result says whether the edges close into loops; open chains are listed with
the gaps between their nearest free ends. Faces with both positive and negative
draft (straddle faces) are named: the line crosses them and is not found there.
With `split_faces` (TR84, D1811) the straddle faces that are cylinders, cones or
spheres are split along their outline (Split Line Silhouette, D1810) first, so the
line runs across them; the part then carries the split faces.

#### 5.3.34.40 Pattern Chain (`pattern_chain`)

Pattern Chain: several pattern steps applied in order (TR141 item 1, D1901).

Each step's copies feed the next, so "linear, circular" spreads a row of copies and
then turns the whole row round an axis, while "circular, linear" turns the seed and
then moves every turned copy along. Each kind of step is used at most once.

Params:
- `steps`: text, the step order, such as "mirror, linear, circular, scale".
- Linear step: `spacing`, `instances` (how many along it, the seed included),
  `reverse`; refs `direction`.
- Circular step: `turns` (instances round the axis), `angle` (the total angle the
  instances share; 360 degrees or more spreads them evenly round), `reverse_turn`;
  refs `axis`.
- Mirror step: refs `plane`: the seed and its mirror image.
- Scale step: `scales` (instances), `factor` (each copy this many times the size
  of the one before), about refs `centre` (a point; the origin when empty).
- `geometry`, `merge`, `propagate_colours`, `preview`, `check` and the
  rest of the shared pattern params (see `linear_pattern.COMMON_PARAMS`).

Refs: the step refs above and the seed: `features`, `faces` or `bodies`.
Instances are numbered `(n, 1)`, `n` from 1 (the seed) in step order: the first
step counts fastest. Key `skip`: instances to skip, as `[n, 1]` pairs.

Parameters also written: `region_mode`, `vary`, `instance_values`.

#### 5.3.34.41 Perforation (`perforation`)

Perforated Fold Line (TR370 item 2, DECISIONS D1109): a row of short cuts for hand bending.

Type `perforation`. Each sketched line on a flat face of a wall gets a row of slots
through the sheet along it: `slot_length` long, `slot_width` wide, with a
`bridge` of uncut sheet between slots. The row is centred on the line, so the
ends of the line keep equal bridges. The slots are cut from the wall in its own
frame, so they fold with it and show in the flat pattern.

Params: `slot_length`, `slot_width`, `bridge` (lengths). Refs: `sketch`,
`sheet_metal`.

Face roles: `<fid>/slot<i>_<k>/<role>`.

#### 5.3.34.42 Point Curve (`point_curve`)

Curve through points (TUTORIAL_REVIEW_SPEC_2 TR61, DECISIONS D817).

Type `point_curve`. A smooth curve through points in order, which sweeps,
lofts and pipes use as a path like any curve (D291).

- Points typed in the panel: `data.points`, a list of [x, y, z] in mm; or read
  from a text file with three columns (`data.file`; the panel's Reload reads
  it again and stores the points, so the part never needs the file to rebuild).
  `refs.frame` (a coordinate system, plane or flat face) places typed points
  in its frame instead of the part's.
- Points picked: `refs.points`, vertices, sketch points or reference points in
  order (they follow the part when it changes).
- `closed`: optional boolean, joins the last point back to the first smoothly.
- `data.equation` (TR374, D1011): the x(t), y(t) and z(t) expressions, the range of t
  and the count last used to fill the points (expression_points), kept only so the
  panel shows them again; the curve is built from the stored points.

#### 5.3.34.43 Point Pattern (`point_pattern`)

Pattern at model points (TUTORIAL_REVIEW_SPEC_2 TR365, DECISIONS D887).

Type `point_pattern`. Copies the seed (`features`, `faces` or `bodies`, as
the other patterns) to points picked on the part, with no sketch:

- `refs.targets`: vertices, round edges (their centre) and round faces such as
  hole walls (their axis).
- `refs.hole_faces`: flat faces; every round hole through them is a target.

Each copy moves the seed's reference point (`refs.point`, else the seed's centre)
onto its target. For a round edge, a hole axis or a hole of a face the copy keeps
the seed's height along that axis, so a copied counterbore or boss sits on the
face like the seed does. Key `skip`: `[k, 1]` pairs, `k` counting targets
from 1 in pick order.

Parameters also written: `geometry`, `merge`, `propagate_colours`, `preview`, `region_mode`, `vary`, `instance_values`, `check`.

#### 5.3.34.44 Polygon Holes (`polygon_holes`)

Polygon holes (TUTORIAL_REVIEW_SPEC TR189 item 1, DECISIONS D1007).

Type `polygon_holes`. Pick the round faces of holes (`refs.faces`). Each hole is
cut out to a polygon with `sides` sides whose flats touch the hole's circle, so
the flats sit exactly at the nominal size: a printer lays down straight runs at
the right size more truly than a fine circle, which tends to print small. With no
`sides` the count follows the hole: twice its diameter in mm, at least 3 and at
most 64. New faces are `<fid>/polygon/<k>/...`.

#### 5.3.34.45 Primitive (`primitive`)

Primitive solids (TUTORIAL_REVIEW_SPEC_2 TR127, DECISIONS D813).

Type `primitive`. A box, cylinder, sphere, cone, torus, wedge, prism or tube
made from typed sizes, with no sketch, added or cut like any boss or cut.

Params:

- `kind`: `box`, `cylinder`, `sphere`, `cone`, `torus`, `wedge`,
  `prism` or `tube`. `operation`: `boss` (default) or `cut`;
  `merge` as for other bosses.
- Sizes (lengths): `length`, `width`, `height` (box; wedge, which slopes
  from `height` at the start to `top` (length) at the end), `diameter`
  (cylinder, sphere, prism across corners, tube outside), `diameter2` (cone
  top; 0 for a point), `inner` (tube inside diameter), `ring` and `tube`
  (torus: the diameter of the ring through the tube's middle and of the tube),
  `sides` (number, prism).
- `centred`: optional boolean: the shape is centred on the frame's origin
  (else it stands on the frame's XY plane, starting at the origin).

Refs: `frame`: a plane, flat face or coordinate system (else the part's own
axes). The shape's Z is the frame's normal.

Face roles: `<fid>/face#k` (by position).

Parameters also written: `frequency`.

#### 5.3.34.46 Push Pull (`push_pull`)

Push Pull: move a flat face or a sketch region by a signed distance (TR267, D1413).

Params: `distance` (length, signed: a positive distance adds material, a
negative one cuts; no Boss or Cut choice) and, for a region, `symmetric`
(optional boolean: the region is pushed half each way from its sketch).

Refs: `faces` (flat faces: each moves along its outward normal by the distance,
its neighbours stretch, as Move Face Offset) or `sketch` (a closed sketch on a
face: its regions are extruded out of the face or cut into it). `to_face`
(optional): a flat face parallel to the first picked face; the distance is then
measured to it (the panel's Next Parallel Face fills it, nearest first).

Every picked face takes the same distance.

#### 5.3.34.47 Remove Fillets (`remove_fillets`)

Remove Fillets: find round faces on any body and remove or resize them (TR260, D1410).

For bodies with no history (an imported part), where there is no fillet feature
to edit. Params:

- `min_radius` and `max_radius`: optional lengths, only rounds in this range.
- `new_radius`: optional length. Without it the rounds are removed; with it they
  are removed and the edges they leave are rounded again at this radius.

Refs: `faces` (optional): the round faces to treat. Without picks every round in
the range is found.

A round is a cylinder, torus or sphere face that meets at least two neighbours
smoothly and is not a whole turn (so holes and shafts are never found). Its
radius is the cylinder radius, the torus tube radius or the sphere radius.
Rounds are removed smallest first (the reverse of the order they are usually
made), a few at a time; a batch that fails is tried one face at a time, and faces
that still fail stay and are named in a warning.

Face roles: kept faces keep their names; new rounds are `fillet/<edge name>`.

Parameters also written: `use_range`, `resize`.

#### 5.3.34.48 Replace Face (`replace_face`)

Replace Face: swap faces for a plane, extending or trimming the body (TR130, D1412).

Refs: `faces` (the faces to replace) and `target` (a reference plane or a
flat face; one reference, or a list holding one). The body under the picked
faces is extended up to the target plane where the faces lie short of it, and
trimmed back to it where they stick out past it. Common use: flatten a bumpy
imported face onto a plane.

Only flat targets are built (the owner decision in the spec: a curved target is
surface work). For each picked face, with `n` the plane normal pointing the way
the face looks:

- added: the face swept along `n`, the part of that sweep short of the plane;
- removed: the face swept against `n`, the part of that sweep past the plane.

Both are cut to the picked faces' own column, so the rest of the body is left
alone. Kept faces keep their names; the new flat face is replaced.

#### 5.3.34.49 Ring Groove (`ring_groove`)

Retaining ring grooves (TUTORIAL_REVIEW_SPEC_2 TR249, DECISIONS D874).

Type `ring_groove`. Pick the round face of a shaft or a bore (`refs.face`). A
groove for a retaining ring is cut `position` from one end of the face
(`from_end`), sized from the round's diameter:

- `ring` on a shaft: an external retaining ring (DIN 471 table).
- `ring` in a bore: an internal retaining ring (DIN 472 table).
- `e_clip`: an E clip on a shaft (DIN 6799 table, by shaft range).

The tables give the groove diameter and width, compiled from the published
standards. A diameter with no ring in the table is an error naming the nearest
sizes. New faces are `<fid>/groove`.

Parameters also written: `ring_type`.

#### 5.3.34.50 Roof (`roof`)

Roof: an equal slope roof over a closed outline (TR258 item 1, DECISIONS D2414).

Type `roof`. Refs: `sketch` (`{"feature": id}`: a sketch whose regions are the
outlines; holes make courtyards). Params:

- `slope`: angle of every roof face from the sketch plane (default 30 degrees).
- `max_height`: optional length: the roof is cut flat at this height above the
  sketch (0 or empty: up to the ridges).
- `operation`: `boss` (default) or `cut`.

Every point of the roof's top is `tan(slope)` times its distance to the nearest
outline edge above the sketch plane, so all faces have the same slope and meet in
hips, valleys and ridges for any outline, also one with inside corners. It is built
as the region's prism less, for every outline edge, the space above the sloped
"tent" over that edge (two cones at its ends and a wedge along it). Curved edges
are followed as short straight pieces. Faces: `roof/base`, `roof/top` (a
Max height cut) and `roof/slope`.

#### 5.3.34.51 Section Cut (`section_cut`)

Section Cut: a section view kept as a cut body feature (TR151 item 2, D2205).

Type `section_cut`. No refs and no params. Data key `zones`: the zones the
section view cut away when the feature was made, each a list of one to three
planes, each plane a dict with `origin` and `normal` (three numbers each, mm
and a unit vector in part space). Material in front of every plane of a zone
(on the normal side) is removed, as the section view hides it (D253, D1603).

The planes are a copy of the section view, so they do not follow later changes.
Cut faces are `<fid>/zone<z>.plane<p>` (from 1).

#### 5.3.34.52 Sensor (`sensor`)

Sensor (TR86, DECISIONS D1022): a tree row that watches a value and warns when it goes

outside typed limits. It passes the part through unchanged.

Params: `source` (`volume`, `area` or `mass` of the bodies built above the
sensor, or `formula`); `value` (the formula, when `source` is `formula`: a
variable, a dimension, an equation or a measured value); `low` and `high` (the
limits, either may be left out). The watched value shows in the feature's report and
formulas can read it as `value@Sensor 1`.

#### 5.3.34.53 Shaft Shape (`shaft_shape`)

Shaft and bore shapes (TUTORIAL_REVIEW_SPEC_2 TR247, DECISIONS D841).

Type `shaft_shape`. Pick a round face (`refs.face`): the outside of a shaft
or the inside of a bore. Over a length from one end of that face, the round is
changed to a hex, a D flat, a double D or a keyway, sized from its diameter D
by FDCAD's rules:

- `hex`: across flats D * sqrt(3) / 2 (the corners on the round).
- `d_flat`: one flat 0.1 D deep. `double_d`: two opposite flats 0.1 D deep.
- `keyway`: a slot D / 4 wide and D / 8 deep, or a standard key's keyseat (shaft)
  or keyway (bore) when `key_standard` is `metric`, `inch` or `woodruff`
  (TR248, D871, sizes in `keys.py`). A half moon keyseat is the key's circle,
  centred along the length.

On a shaft the shape is cut from it. In a bore the hole takes the matching
shape grown by `clearance` on every side, so a shaft of the same size slides
in. Params: `shaft_form`, `length` (optional: the whole face), `from_end`
("start" or "end" of the face along its axis), `angle` (turns the flats or
key about the axis), `clearance` (bores). New faces are `<fid>/shape`.

#### 5.3.34.54 Sheet Corner Relief (`sheet_corner_relief`)

Sheet metal Corner Relief (TR168, DECISIONS D1103): relief cuts where bends meet.

Type `sheet_corner_relief` (`corner_relief` is the machining relief of TR244).

A corner is a pair of bends that start on the same wall and whose tangent lines
meet near an end of each. Three bends round one corner make pairs too. The relief
is drawn in the flat frame of that wall and cut through the sheet from the wall,
both bend strips (wrapped round the bends when folded) and both flange walls, so it
shows in the folded part and in the flat pattern alike.

Params:
- `all_corners`: Collect All Corners (otherwise the corners between the picked bends).
- `relief_type`: "rectangular" (default), "circular", "tear", "obround",
  "constant_width".
- `corner_types` (optional text): one type per corner in corner order, such as
  "circular, , tear"; a blank keeps `relief_type`.
- `size_by`: "ratio" (default) or "value"; `ratio` (times the thickness, default
  2) or `size` (length).
- `placement`: "bend_lines" (centred on the bend lines, default) or "tangent" (touching the
  bends' tangent lines on the wall).

Refs: `bends` (faces of bends), `sheet_metal`.

Face roles: `<fid>/corner<k>/<role>`.

#### 5.3.34.55 Sheet Tab (`sheet_tab`)

Tab (TR165, DECISIONS D1100): a sketched piece of wall joined to the sheet.

Type `sheet_tab`. A closed sketch drawn on a flat face of a wall (or on a plane
level with one) adds a piece exactly one sheet thickness thick to that wall, in
the wall's own frame, so it folds and flattens with the wall. Each closed region
of the sketch is one tab, so a sketch pattern of profiles makes a row of tabs.
Every tab must touch the wall it joins.

Params: none. Refs: `sketch`, `sheet_metal`.

Face roles: `<fid>/side/<entity>` and the wall's own roles.

#### 5.3.34.56 3D Sketch (`sketch3d`)

3D sketch (TUTORIAL_REVIEW_SPEC TR7, DECISIONS D1719).

Type `sketch3d`. A sketch that is not on one plane, used as a sweep, pipe or
loft path like any curve (D291). It is built in two forms that can be mixed:

- Plane sketch form: `data.parts`, a list of `{"plane": ref, "sketch": data}`.
  Each part is an ordinary 2D sketch (FDEF_SPEC 6 data) on its own plane (a plane
  feature or a flat face, as a sketch's `refs.plane`), solved and placed in space.
- Free form: `data.lines`, a list of ``{"kind": "line" | "spline", "points":
  [[x, y, z], ...]}`` in mm: straight segments through the points in order, or a
  smooth curve through them.

The curves of every part and line make one curve result; touching ends join into
one wire when they can. The report gives the true 3D length.

`data.relations` (TR7, D2206) holds relations and 3D lengths between the points of
the free lines, and from line points to plane sketch part points; they are solved
in space before the curves are made (`core/sketch/solve3d.py`).

#### 5.3.34.57 Split Line (`split_line`)

Split Line: divide faces into regions without changing the volume (TR60, D1414).

Params: `method` "projection" (default) or "intersection"; for projection,
`reverse` and `both` as Projected Curve (D291).

Refs: `faces` (the faces to split), `sketch` (projection: its curves are
projected onto the faces along `direction` or the sketch normal) and `plane`
(intersection: a reference plane or flat face; the faces are split where it
crosses them).

The new edges can be picked for a fillet, and the regions for Draft, Move Face or
a colour. A split face's pieces are named `<face name>#k` by position, as for
any split (PLAN section 6). Deleting the feature joins the faces again.

Silhouette (TR60, D1810): `refs.direction` (a plane, flat face or straight
edge) is the pull; each picked cylinder, cone or sphere is split along its outline
(see `silhouette`). Intersection with a body (D1810): `refs.tool_body` (a face of
another body of the part) splits the faces where that body's faces cross them.

#### 5.3.34.58 Sprue Tree (`sprue_tree`)

Sprue Tree: casting sprues, or a kit frame of parts on a runner (TR408 item 3, D2411).

Type `sprue_tree`. Refs: `feed_points`, the spots where the parts are fed (vertices,
sketch points or reference points, at least one), and for a tree `cup` (a point:
the middle of the pouring cup's open end). Params, lengths unless noted:

- `layout`: `tree` (default) or `kit_frame`.
- Tree: a pouring cup `cup_diameter` wide and `cup_height` deep narrows to the
  trunk, `sprue_diameter` thick, which runs from the cup straight toward the
  points as far as the farthest of them; a gate `gate_diameter` thick runs square
  from the trunk to each point, with a ball at each joint.
- Frame: a rectangular runner `sprue_diameter` thick round all the points, in the
  plane through their middle square to their least spread, `margin` outside them;
  a gate runs from each point straight to the nearest side of the frame. The frame's
  sides follow model X, or Y, laid in that plane.

Everything is joined to the part, so the parts and their feeds make one body, as a
casting master or a model kit sprue. Faces: `cup`, `trunk`, gate<k>,
`frame`.

#### 5.3.34.59 Stamp (`stamp`)

Stamp (TR77, D1816): a closed sketch outline pressed into a flat wall.

Type `stamp`. Params: `depth` (length), `draft` (angle from square to the
wall, 0 to under 60 degrees, default 0), `reverse` (press the other way),
`punch_radius` (the inside round at the top), `die_radius` (the round where the
press leaves the wall) and `corner_radius` (the outline's corners rounded in plan),
all optional lengths (TR77, D2309), and `drawn_cut` (the top is cut away, a drawn
cut out, TR283, D2311). Each closed outline of the sketch is its own stamp.
Refs: `sketch` (one closed outline of lines and arcs drawn on a flat face of a
wall), `sheet_metal`.

The outline is the stamp's foot. Its top is the outline moved `depth` out of the
face and shrunk by `depth * tan(draft)`; the sheet is lofted between them and the
hollow under it is the same loft one thickness lower (the way the Forming Tool
presses its dimples and ribs, D545), so the sheet keeps its thickness measured
along the press. The stamp is in the folded part only; the flat pattern shows its
outline as marks (titled "Stamp outline"), like Flat Marks (D1112).

Face roles: `<fid>/stamp/form`.

#### 5.3.34.60 Stone Setting (`stone_setting`)

Stone Setting: a seat and prongs for a round stone (TR408 item 2, DECISIONS D2410).

Type `stone_setting`, for ring and pendant masters. Refs: `seat_face` (one flat
face the stone sits in) and `seat_point` (optional: a vertex, sketch point or reference
point on it; the face's middle without one). Params, lengths unless noted:

- `stone_diameter`: the stone's girdle diameter.
- `girdle_depth`: how deep the seat's straight wall is below the face.
- `pavilion_angle`: optional angle of the stone's underside to the girdle plane
  (default 41 degrees, a round brilliant): the seat narrows below the wall at that
  angle to a point.
- `prongs`: a number, 0 to 12: prongs round the seat, evenly spaced from the
  face's first direction. `prong_diameter`, `prong_height` (above the face).
  Each prong stands with its middle a quarter of its diameter outside the girdle, so
  it holds the stone's edge, sinks a diameter into the part, and has a round tip.

The seat is cut and the prongs are added, in the body of the face. Faces:
`seat/wall`, `seat/cone` and `prong<k>/side` (k from 1).

#### 5.3.34.61 Surface Push (`surface_push`)

Local deform modes: Deform Point, Curve to Curve and Surface Push (TR67, D2412).

These move part of a body and leave the rest, unlike the triad tools (bend, twist,
taper, stretch, flow), so they ignore the triad and trim planes. They share the same
NURBS deformation, tolerance check and approximate warning (feature.py, nurbs.py).
Every map works on whole arrays of points.

- `deform_point`: refs `point` (where), `direction` (optional: a direction;
  default the normal of the face the point is on, or +Z) and `fixed` (optional
  faces or edges that stay put). Params `distance`, `radius` (of influence) and
  `stiffness` (0 to 1: the part of the radius that moves the full distance).
- `deform_curve`: refs `initial` and `target` (sketches or curves) and
  `fixed`. Param `radius`: how far from the initial curve the body follows.
  Points on the initial curve move to the matching point of the target curve (by
  length along each), and the movement fades out over the radius.
- `surface_push`: refs `point` (where the tool first touches) and `direction`
  (the push, into the face). Params `tool` (sphere, ellipsoid or rectangle),
  `depth`, `tool_x` and `tool_y` (half sizes across; a sphere uses
  `tool_x`) and `reach` (how deep into the body the dent fades out; default
  three times the depth).

Parameters also written: `axis`, `spin`, `ox`, `oy`, `oz`, `start`, `end`, `tolerance`.

#### 5.3.34.62 Table Pattern (`table_pattern`)

Table driven pattern (TUTORIAL_REVIEW_SPEC_2 TR58, DECISIONS D821).

Type `table_pattern`. One copy per row of a table of X and Y positions.

- `data.rows`: a list of `[x, y]` in mm, or `[x, y, false]` for a row that
  is ticked off (kept in the table, no copy). The copy of row k has instance
  number k, so the usual `skip` list and the Skip copies fix still work.
- `refs.frame`: optional coordinate system, plane or flat face; X and Y are
  measured along its axes from its origin. Without it, the part's XY axes.
- `refs.point`: optional reference point of the seed, else the seed's centre.
  Each copy puts the reference point at the row's position. A row at the
  reference point itself is the seed and makes no copy.
- The seed: `features`, `faces` or `bodies`, as in other patterns.
Params as linear patterns.

Parameters also written: `geometry`, `merge`, `propagate_colours`, `preview`, `region_mode`, `vary`, `instance_values`, `check`.

#### 5.3.34.63 Transition Spiral (`transition_spiral`)

Transition spiral: an easement curve from a straight to an arc (TR408 item 1, D2010).

Type `transition_spiral`. Refs: `sketch`: a sketch with one line; the spiral
starts at the line's end, along it, in the sketch plane. Params: `spiral_length`
(length of the spiral) and `end_radius` (the radius it ends at), and `hand`
(`left`, default, or `right`: the way it turns, seen on the sketch).

The curve is a clothoid: its curvature grows evenly from 0 at the start to
1 / radius at the end, so a train or car on it turns in smoothly. It is found by
summing the clothoid's direction along many short steps (numpy) and fitted with a
spline through points along it. The curve is kept in `extras["curve"]` for
Sweep and the other curve users.

#### 5.3.34.64 Twist Lock (`twist_lock`)

Twist lock (bayonet) joint for printed lids (TR357, DECISIONS D1024).

Type `twist_lock`. Pick the outer round face of the inner part, the plug
(`refs.face`). Lugs stand out of that face; every other body that the lugs' paths
reach (the socket) gets an L shaped slot for each lug: a straight entry from the
open end down to the lugs, then a turn round the axis, so the lid pushes in and
twists to lock.

Params: `lug_count` lugs, evenly round; `lug_width` (round the face), `lug_height`
(along the axis) and `lug_depth` (how far they stand out); `lock_depth`, from the
plug's open end to the lugs' centre; `twist`, the turn to lock; `lock_clearance`, the
gap left round each lug in the slot; `other_end` takes the other end of the face as
the open end; `clockwise` turns the other way. New faces are `<fid>/lug/<k>` on
the plug and `<fid>/slot/<k>` in the socket.

#### 5.3.35 Parameters added to earlier feature types

Parameters that the feature types of the sections above gained later. All are optional unless the text says otherwise, and a file without them opens as before.

#### 5.3.35.1 Bounding Box (`bounding_box`), later parameters

1. `box_shape`: `box` (default) or `cylinder` (its axis is the frame's Z).
2. `orient`: `axes` (default: square to the part's X, Y and Z, so the box never turns), `best_fit` (the box turned to fit the part closely; a cylinder's axis is along the part's longest extent), or `frame` (the plane, face or coordinate system in `refs.frame`).
3. `make_solid`: optional boolean. Off: the box is drawn as a thin outline and the part is unchanged. On: the box is added as a separate body.

#### 5.3.35.2 Break Corner (`break_corner`), later parameters

1. Type `break_corner`. Params: `break_type` ("chamfer", the default, or "fillet"), `distance` (chamfer), `radius` (fillet). `collect_all` takes every corner of the flat outline instead of picked edges, and `corner_kind` ("outside", the default, or "inside") says which (TR174 item 5, D1107). An inside corner is filled: material is added instead of cut.

#### 5.3.35.3 Chamfer (`chamfer`), later parameters

1. Vertex: `distance`, `distance2`, `distance3` along the three edges at the corner (ordered by edge name), or `equal` (one value for all three).
2. Partial edges (TR64 item 5, D1012, symmetric Distance Distance only): `partial` "distance" or "percent" with `start_distance` and `end_distance` or `start_percent` and `end_percent`, and `partial_flip`, as for Fillet (D519).
3. Tangent Propagation (TR131, D1400): `tangent_propagation` False makes the bevel of a picked edge stop square at each smooth join (symmetric Distance Distance only).
4. Corners (TR321, D1812, D2304): `corner` "patch" (default), "mitre" or "blend", see chamfer_corners.

#### 5.3.35.4 Circular Pattern (`circular_pattern`), later parameters

1. `law1`, `law2` (TR366, D1500): optional, "even" (default) or "angles": each copy turns by its own number of degrees from the seed, from the text list `angles1` or `angles2` (one per copy, such as "30, 75, 160"), or "increment" (TR59, D1513): each step is the one before plus `increment1` (an angle).
2. `vary` (TR59, D1513, every pattern of features): text such as "depth 2": values of the seed features that grow by the step at each copy (see `patterns.parse_vary`).
3. `instance_values` (TR59 item 3, D1900): text such as "3: depth 8": the values one copy uses in place of the seed's (see `patterns.parse_instance_values`).
4. Also written: `increment2` (angle, optional); `region_mode` (one of "inside", "outside", optional); `check` (one of "full", "fast", optional).

#### 5.3.35.5 Closed Corner (`closed_corner`), later parameters

1. Type `closed_corner`. Params (all optional): `corner_type` ("overlap", the default, "underlap" or "butt") and `gap`. `overlap_ratio` (0 to 1, 1 when missing): how far across the other wall's thickness an overlap or underlap reaches (TR174 item 2, D1107). `bend_region` ("open" when missing, or "closed", D2308) fills the corner between the two bends in the folded part. Several faces close several corners at once.

#### 5.3.35.6 Combine (`combine`), later parameters

1. `tolerance`: optional length: faces of the bodies closer than this count as touching, for imported bodies that nearly meet (TR261, D787).
2. Options (TR128, D865): `operation` "exclusive" keeps only what lies inside an odd number of the picked bodies; `keep_tools` keeps the tool bodies (subtract: the picked tools; add, common, exclusive: every picked body but the first); `keep_largest` keeps only the largest piece of the result.
3. `reapply_fillets` (TR259, D2302): on Add, Subtract and Common, rounds next to the change are removed first and made again after (see `reapply_fillets`).
4. `operation` "fragments" (TR371, D999) cuts the picked bodies at every crossing and keeps every piece as a body of its own; "at_least" keeps only the volume inside at least `min_bodies` of the picked bodies (2 by default), joined.

#### 5.3.35.7 Convert Sheet (`convert_sheet`), later parameters

1. Type `convert_sheet`. Params: `gap` (bend corners and rips, default 0.1 mm in the panel), `keep_body` (keep the solid beside the sheet, TR171, D2307) and `rip_type` ("overlap" default, "underlap", "open" or "butt", see `_rips`). Refs: `face` (the fixed flat face), `bends` (straight edges between flat faces), `sheet_metal`.

#### 5.3.35.8 Coord System (`coord_system`), later parameters

1. Also written: `extra_dx` (length, optional); `extra_dy` (length, optional); `extra_dz` (length, optional); `extra_rx` (angle, optional); `extra_ry` (angle, optional); `extra_rz` (angle, optional).

#### 5.3.35.9 Corner Relief (`corner_relief`), later parameters

1. `tool_diameter`: length, the cutter's diameter. `clearance`: optional length added to the relief radius (default 0).

#### 5.3.35.10 Cross Break (`cross_break`), later parameters

1. Type `cross_break`. Params: `reverse` (titles the break "down" instead of "up"), `break_angle` and `break_radius` (optional; written into each line's title, so the flat pattern export carries them, TR174 item 3, D1107). Refs: `face` (a flat face of a wall), `sheet_metal`. No geometry changes.

#### 5.3.35.11 Curve Array (`curve_array`), later parameters

1. `start_offset` and `end_offset`: optional lengths (TR373, D979): the copies start this far along the curve and stop this far before its end. The seed stays where it is.
2. `law` (TR366, D1500): optional spacing law, "even" (default), "growing" (`ratio`), "random" (`jitter` percent, `seed`) or "fractions" (`fractions`, a text list), as Linear Pattern's `law1`. The law measures from the start offset.

#### 5.3.35.12 Delete Face (`delete_face`), later parameters

1. `hole_size`: optional length (TR388, D990): every round hole up to this diameter is removed too, found by the feature. `voids`: optional boolean: enclosed voids are filled. With either, the picked faces may be left empty.
2. `reapply_fillets` (TR259, D2302): on Add, Subtract and Common, rounds next to the change are removed first and made again after (see `reapply_fillets`).

#### 5.3.35.13 Draft (`draft`), later parameters

1. `draft_type`: optional, "neutral_plane" (default), "parting_line" or "step" (D521, built in draft_parting). The parting types use `neutral` as the direction of pull and the edges in `refs.parting_lines`, with optional `other_side`, `both_sides` and `angle2` (the other side's angle), and `allow_reduced` (TR147 item 1, D1418: the largest angle that builds is used, with a warning, when the full angle fails).
2. Neutral plane options (TR323, D1419): `neutral_split` with `angle2` drafts the faces below the neutral plane at their own angle; `angle_mode` "relative" adds the angle to the lean a flat face already has ("absolute", the default, ends every face at the angle from the pull).
3. `reapply_fillets` (TR259, D2302): on Add, Subtract and Common, rounds next to the change are removed first and made again after (see `reapply_fillets`).

#### 5.3.35.14 Edge Flange (`edge_flange`), later parameters

1. `position`: "material_inside" (default), "material_outside", "bend_outside", "virtual_sharp" (D335) or "offset" (TR30.2: `offset_distance` in from the edge, with `offset_rule` applied there). `trim_side_bends` (false when missing; new flanges get it on). `gap`: length.

#### 5.3.35.15 Extrude (`extrude`), later parameters

1. `print_top`: optional, for cuts: `teardrop` or `flat` gives every round hole the cut makes along a sideways direction a pointed or flat top toward the printer's up, as the Hole Tool does (TR175, D784). Faces `top/<k>/...`.
2. `end_offset`, `end_offset2`: angles, Offset from Face only. The end face is turned back about the axis, toward the start, by the offset.
3. `flip_side`: thicken to the other side of the sketch. `symmetric`: half each side.
4. `thin_fillet`: boolean, open profiles only: round the wall's corners (TR65, D824). `thin_fillet_radius`: the inside radius; the outside radius is that plus the wall. Rounds are named `side/<e1>+<e2>/round`.
5. Also written: `auto_operation` (boolean, false when missing, optional); `auto_alternate` (boolean, false when missing, optional); `link_thickness` (boolean, false when missing, optional); `normal_cut` (boolean, true when missing, optional); `end_offset_reverse2` (boolean, false when missing, optional); `end_translate2` (boolean, false when missing, optional); `depth_along` (one of "direction", "normal", optional); `end_twist` (angle, optional); `profile_offset` (length, optional); `end_scale` (number, optional); `thin_merge_ends` (boolean, false when missing, optional).

#### 5.3.35.16 Fillet (`fillet`), later parameters

1. Limits (TR271, D1407): `refs.keep_edges` (edges a round may not swallow) and `refs.limit_plane` with `limit_flip` (rounds stop at the plane); see fillet_limits.
2. Methods and profiles (TR62, D1402, constant size): `method` "radius", "asymmetric" (`distance2`, `reverse`) or "chord"; `profile` "circular", "conic" (`rho`), "curvature" or "elliptic". See `fillet_profile`.
3. Face fillet: `faces1` and `faces2`, the edges where they meet are rounded. With `method` "hold_line" and `refs.hold_lines` the rounds follow the hold line edges (TR29, D1409, see fillet_hold). Full round: `faces1`, `centre` and `faces2` (see `fillet_faces.full_round`). Edges tangent to a picked edge are included (the kernel works on whole smooth chains), unless `tangent_propagation` is False (TR131, D1400): then the round of a picked edge stops square at each smooth join (see fillet_tangent).
4. Also written: `omit_attach` (boolean, false when missing, optional).

#### 5.3.35.17 Flatten (`flatten`), later parameters

1. Params (all optional, false when missing): `flattened`, `bend_lines` and `bounding_box`. New Flat Patterns get the last two turned on. `bend_notches` ("none", "triangle", "circle" or "rectangle") and `notch_size` (length, the thickness when missing) cut a notch at both ends of every bend line in the flat pattern only (TR169, D1104). `merge_faces` (true when missing) joins the faces of walls and bends; `corner_trim` cuts the square where two bend strips meet at a corner from the flat (TR76, D1105). Refs: `grain`, an edge whose direction sets the orientation of the bounding box; `leave_out`, faces whose walls (and the walls bent from them) are left out of the flat (TR76, D1105). `sheet_length` and `sheet_width` (lengths): a warning when the flat does not fit that sheet (TR174 item 7, D1107). The result's `extras` hold the quoting values of `quote` (TR172, D1106). `bend_order` (text, bend numbers in bending order) numbers the bends in the files (TR282, D1110). `fold_percent` (0 to 100) shows the folded part with every bend at that share of its angle while `flattened` is off (TR283 item 2, D1112).

#### 5.3.35.18 Form Tool (`form_tool`), later parameters

1. `rib_ends`: "round" (default) or "square" ends of a rib (TR283, D2311).
2. `tool` "custom" (TR279, D2313): the shape of a tool body of the part, with `refs.tool_face` (its stop face), `refs.remove_faces`, `refs.insert`, `tool_angle` and `mirror`; see custom_form.

#### 5.3.35.19 Helix (`helix`), later parameters

1. `ends` (TR162, D1923): optional, `open` (default) or `closed`: spring end coils, the pitch `end_pitch` at each end growing to the pitch over the first and last turn.

#### 5.3.35.20 Hem (`hem`), later parameters

1. `relief`, `relief_by`, `relief_ratio`, `relief_width`, `relief_depth`: own relief at shortened ends, as the Sheet Metal folder.

#### 5.3.35.21 Hole (`hole`), later parameters

1. Placed with no sketch (TR143, D1911): `refs.place_edges` (two straight edges, with `place_distance1` and `place_distance2`) or `refs.concentric` (a round edge or cylinder face) on `refs.plane` give one hole (hole_place).
2. Printing (TR175, D780): `print_top` (optional): `teardrop` or `flat` gives a hole that runs sideways a pointed or a flat top toward the printer's up, so it prints without supports; up is the model's +Z, or straight off the bed when a face is laid flat (`print_setup.down_face`). Holes along up are left round. The extra faces are `hole/<p>/top/<k>`.
3. Bridging (TR176, D781): `print_bridge` (optional), for counterbores and countersinks printed head down: `sacrificial` leaves one layer over the small bore at the head's floor, to drill out after printing; `stepped` leaves two layers that print as bridges: a slot as wide as the bore across the head, then a square as wide as the bore. `bridge_layer` (length) is one layer, copied from the printer profile's layer height.
4. `stack` is text such as `counterbore 10 3; countersink 8 90; straight 5 12`: from the face inward, each element is a kind, a diameter (mm) and a length (mm), or for a countersink its included angle (degrees): the cone runs from that diameter down to the next element's. Kinds: `straight`, `counterbore` (both a plain bore), `tapped` (a bore at the tap drill diameter that also gets a cosmetic thread mark in a later version) and `countersink`. The last element must be a bore. The order is the text's order, so elements are reordered by editing it.
5. Also written: `place_by` (one of "points", "edges", "concentric", "radial", "point", optional); `thread_relief` (boolean, false when missing, optional); `thread_chamfer` (boolean, false when missing, optional); `radial_distance` (length, optional); `radial_angle` (angle, optional); `cbore_head` (one of "socket", "button", "low_head", "pan", "cheese", "washer", optional); `csk_head` (one of "flat", "recessed", optional).

#### 5.3.35.22 Import Mesh (`import_mesh`), later parameters

1. Params: `convert` (optional boolean): turn the mesh into a faceted solid that joins the part like an imported STEP body. Left out, the mesh is a reference body: it is shown but is not part of the part's solid. `merge` (optional boolean, converted meshes): join the solid to the part's body. `subtract` (optional boolean, converted meshes): cut the solid out of the part's body, so the mesh works as a boolean tool (DECISIONS D412). `parts` (optional boolean, converted 3MF meshes, TR386, D1205): one body per part of a slicer 3MF, named and given the print role the slicer stored; `keep_roles` (optional boolean): keep the modifier, negative and support parts as bodies with their roles, else they are left out. TR186 (D1212): `repair` (optional boolean) fills holes, drops repeated triangles, extra triangles on edges shared by more than two, and tiny pieces; `reduce_percent` (optional number, 1 to 99) or `reduce_target` (optional whole number) lowers the triangle count, `reduce_error` (optional length) caps how far a vertex moves and `keep_boundary` (optional boolean) keeps open edges in place. Part faces are `part<k>/face/<j>`; `extras["body_titles"]` and `extras["body_roles"]` give each part's first face name its name and role.
2. Also written: `file_unit` (one of "mm", "cm", "m", "in", optional).

#### 5.3.35.23 Import Step (`import_step`), later parameters

1. Params: `merge` (optional boolean): when the part already has a body, join the imported solid to it. Off by default, so an inserted file becomes its own body. `heal_gap` (optional length): the largest gap healing closes, set by Heal (TR31, D760); without it the usual 0.001 mm.
2. `keep_bodies` (optional text, TR302 item 2, D1203): the numbers of the file's bodies that come in, from 1 in the healed shape's order, such as "1, 3"; empty or missing for all of them. Faces keep the names they have in the whole file.

#### 5.3.35.24 Linear Pattern (`linear_pattern`), later parameters

1. `reverse1`: boolean. `fill1`: optional, "spacing" (default) or "up_to": fill up to `refs.up_to1` (a vertex, edge, face or plane) less `offset1` (length), or "total" (TR142, D962): `count1` instances spread evenly over `total1` (length, from the seed to the last copy), or "fit" (TR398, D1502): as many copies `spacing1` apart as fit in the overall size `total1`, the seed included.
2. `law1`, `law2`: optional spacing law (TR366, D981): "even" (default), "growing" (each gap `ratio1` times the one before; the first gap is the spacing) or "random" (each copy moved by up to `jitter1` percent of the spacing either way, the same every rebuild for one `seed1`), or "fractions" (TR366, D1018: copy `k + 1` sits at the `k`-th number of `fractions1`, a text list such as "0.1, 0.3, 1", times the run from the seed to the last copy, `spacing1` times the copies; one number per copy), or "increment" (TR59, D1513: each gap is the one before plus `increment1`, a length; the first gap is the spacing).
3. `vary` (TR59, D1513, every pattern of features): text such as "depth 2": values of the seed features that grow by the step at each copy (see `patterns.parse_vary`).
4. `instance_values` (TR59 item 3, D1900): text such as "3: depth 8": the values one copy uses in place of the seed's (see `patterns.parse_instance_values`).
5. `second_direction`: optional boolean, turns on direction 2 with `spacing2`, `count2`, `reverse2`, `fill2`, `offset2` and `refs.up_to2`.
6. `symmetric1`, `symmetric2`: optional booleans (TR140, D811): the same number of copies at the same spacing on the other side of the seed too. Copies on the far side are numbered after the near side's (count + 1, count + 2...) for Skip.
7. `seed_cell1`, `seed_cell2`: optional numbers (TR270, D1501): the cell of the grid that holds the seed, 1 (default) to the count; earlier cells are copies the other way. Not with Symmetric.
8. `rotate`: optional angle (TR270, D1501): with direction 2, both directions turn by it about their common normal, so the whole grid turns in its plane.
9. Also written: `increment2` (length, optional); `total2` (length, optional); `ratio2` (number, optional); `jitter2` (number, optional); `seed2` (number, optional); `fractions2` (boolean or text, optional); `region_mode` (one of "inside", "outside", optional); `check` (one of "full", "fast", optional).

#### 5.3.35.25 Loft (`loft`), later parameters

1. `show_section` (a whole number, 0 for none) picks section `k` of `COUNT`, evenly spaced from the start (1) to the end (`COUNT`). A sweep's section is its profile carried along the path with the least turning, worked out without the kernel's sweep, so it shows even when the sweep fails; a loft's is a slice of the built loft square to the line from its first profile's centre to its last. The section is drawn as reference geometry (`extras["reference"]`) with a report line.
2. Centerline: each added section is turned square to the centerline and centred on it. `sections` sets how many are added in each span.

#### 5.3.35.26 Mirror (`mirror`), later parameters

1. `vary` (TR59, D1513, every pattern of features): text such as "depth 2": values of the seed features that grow by the step at each copy (see `patterns.parse_vary`).
2. `instance_values` (TR59 item 3, D1900): text such as "3: depth 8": the values one copy uses in place of the seed's (see `patterns.parse_instance_values`).
3. Also written: `region_mode` (one of "inside", "outside", optional); `check` (one of "full", "fast", optional).

#### 5.3.35.27 Miter Flange (`miter_flange`), later parameters

1. Params (all optional): `gap` (space at each mitre), `radius`, `method`, `k_factor`, `allowance` (own bend values), `propagate` (add the edges joined smoothly to the picked ones, TR30.3). `offset_start` and `offset_end` (lengths) stop the flange short of the chain's free start and end, for a partial miter flange (TR170, D1113); the chain starts at its free end with the smallest X, then Y, in the wall's frame.
2. `relief` (TR256, D1922): optional boolean: a run out groove (undercut) where the thread ends, sized from the pitch after DIN 76-1. `lead_in` is the end chamfer.
3. `relief_by`: "ratio" (default) or "size". `relief_ratio`: number between 0.05 and 2.0 (default 0.5). `relief_width`, `relief_depth`: lengths.
4. `relief`, `relief_by`, `relief_ratio`, `relief_width`, `relief_depth`: own relief at shortened ends, as the Sheet Metal folder.
5. Also written: `relief_width` (length, optional).

#### 5.3.35.28 Modeled Thread (`modeled_thread`), later parameters

1. `form`: optional, `iso` (default, the 60 degree V), `printable` (a 90 degree V: flanks at 45 degrees, so the thread prints upright without supports) or `round` (a coarse round groove for caps and jars, half the pitch wide).
2. `form` "sketch" (TR254, D1918): the section from `refs.profile_sketch`, one closed region whose X runs along the axis and Y is the depth into the material.
3. `end_finish` (TR254, D1918): optional, `square` (default), `chamfer` (the depth runs out at 45 degrees) or `fade` (it runs out over the last pitch).
4. `relief` (TR256, D1922): optional boolean: a run out groove (undercut) where the thread ends, sized from the pitch after DIN 76-1. `lead_in` is the end chamfer.

#### 5.3.35.29 Move Copy Body (`move_copy_body`), later parameters

1. Also written: `pivot` (one of "body_centre", "picked", optional); `handle_axes` (one of "model", "plane_axes", optional).

#### 5.3.35.30 Move Face (`move_face`), later parameters

1. `mode` "resize": `diameter` (length) is the new diameter of each picked cylinder or sphere face, or the tube diameter of a torus; the face is offset by the difference, so neighbouring rounds follow as for Offset.
2. Offset with `set_size` (optional length) and `refs.size_from` (a vertex, edge or face): the one flat picked face moves until it is `set_size` from that item, measured along the face's normal (a round edge or face counts from its centre or axis); `distance` is not used.
3. Rules (TR263, D788): `rule_coplanar`, `rule_concentric`, `rule_tangent`, `rule_equal_radius` (optional booleans) add the faces in that relation to the move; `suspend_rules` turns them all off; `refs.rule_exclude` lists faces no rule adds (see face_rules).
4. `symmetric` (D798): the mirror image of a picked face about a symmetry plane (`refs.symmetry_plane`, else each main plane through the origin) joins the move, moving the mirrored way. Offset and Resize only: the mirror face gets the same offset.
5. `reapply_fillets` (TR259, D2302): on Add, Subtract and Common, rounds next to the change are removed first and made again after (see `reapply_fillets`).
6. Also written: `rule_symmetric` (boolean, false when missing, optional); `rule_parallel` (boolean, false when missing, optional); `rule_main_planes` (boolean, false when missing, optional); `offset_by` (one of "distance", "measured", optional); `follow` (one of "extend", "tip", "lift", optional); `keep_solution` (boolean, false when missing, optional); `rounds` (one of "follow", "remake", optional); `cone_angle` (angle, optional); `lock_size` (boolean, false when missing, optional); `keep_end` (one of "large", "small", optional).

#### 5.3.35.31 Ref Axis (`ref_axis`), later parameters

1. Also written: `extra_dx` (length, optional); `extra_dy` (length, optional); `extra_dz` (length, optional); `extra_rx` (angle, optional); `extra_ry` (angle, optional); `extra_rz` (angle, optional).

#### 5.3.35.32 Ref Plane (`ref_plane`), later parameters

1. Also written: `extra_dx` (length, optional); `extra_dy` (length, optional); `extra_dz` (length, optional); `extra_rx` (angle, optional); `extra_ry` (angle, optional); `extra_rz` (angle, optional).
2. Method `tangent` (first: a cylinder face; second: a plane or a point): the plane touches the cylinder on the side the second pick's normal points to, or the side facing the point. `flip` (optional boolean, DECISIONS D2629) touches the opposite side; left out, it is the side above.

#### 5.3.35.33 Ref Point (`ref_point`), later parameters

1. Also written: `crossing` (number, optional).

#### 5.3.35.34 Rip (`rip`), later parameters

1. Refs: `sketch` (lines on flat faces: sketched rips), `edges` (edges where two walls touch: edge rips), `sheet_metal`. Either or both. Or `tube_faces` (TR174, D1813) with `tube_angle` and `tube_offset`: slits along cylinders and cones of a plain solid, see tube_rip.

#### 5.3.35.35 Scale (`scale`), later parameters

1. Shear (TR371 item 3, D1000): `shear_angle` (angle, optional) slides the bodies along `shear_along` ("x", "y" or "z") by the distance from the centre along `shear_from` (another axis) times the tangent of the angle. It is applied after the scale factors.

#### 5.3.35.36 Sheet Metal (`sheet_metal`), later parameters

1. `kerf` (optional length): the width the laser or cutter takes away; Tab and Slot and finger joints draw their slots narrower by it (D802).
2. Also written: `rule_name` (boolean or text, optional).

#### 5.3.35.37 Shell (`shell`), later parameters

1. `both_sides`: optional boolean (TR322, D1411): half the wall inside the part and half outside; the outer wall faces are `outer/<face name>`.
2. `corners`: optional "sharp" or "rounded" (TR129, D825): how the wall's outside corners join. Without it, sharp first and rounded when sharp fails.
3. `wall_rule`: optional "never_thinner" or "never_thicker" (TR322, D1803): the wall is kept at least or at most the thickness; see `shell_wall_rule`.

#### 5.3.35.38 Sketch Pattern (`sketch_pattern`), later parameters

1. `vary` (TR59, D1513, every pattern of features): text such as "depth 2": values of the seed features that grow by the step at each copy (see `patterns.parse_vary`).
2. `instance_values` (TR59 item 3, D1900): text such as "3: depth 8": the values one copy uses in place of the seed's (see `patterns.parse_instance_values`).
3. Also written: `region_mode` (one of "inside", "outside", optional); `check` (one of "full", "fast", optional).

#### 5.3.35.39 Split (`split`), later parameters

1. `tolerance`: optional length: faces closer than this count as touching (TR261).

#### 5.3.35.40 Split For Print (`split_for_print`), later parameters

1. Dovetail keys: `key_width` (at the seam) and `key_depth` (into each piece). A key is a separate body shaped like two dovetails back to back that slides in from the side; its pocket is `clearance` larger. `key_draft` (optional angle, TR181, D2002) tapers the key and its pocket along the slide, so the key wedges tight as it goes in from the wide end.
2. Magnets (TR181, D1211): `magnet_diameter` and `magnet_depth`. A round pocket `magnet_depth` plus `clearance` deep goes into each piece; no body is added.
3. Screws (TR181, D1211): `screw_diameter` (a hole `clearance` wider, right through the part along the cut's normal), and a hexagon nut pocket `nut_size` across flats and `nut_height` deep where the hole leaves the part on the normal's side, both `clearance` larger.
4. `glue_gap` (optional length, TR181): each piece on the normal's side of a cut is trimmed back this far from the seam, so the joint has room for glue.

#### 5.3.35.41 Sweep (`sweep`), later parameters

1. `twist`: "none" (default), "minimum", "angle" (`twist_angle`) or "direction" (the section's up direction follows `refs.twist_direction`) or "turns" (TR56, D1504: `twist_turns` whole or part turns, the angle times 360 degrees). On a closed path an angle or turns twist must be whole turns.
2. `corners` (TR137, D1515): optional, how the section passes a sharp corner of the path: "smooth" (default, the kernel turns the section), "mitre" (the two sweeps meet in a sharp edge on the corner's bisector) or "round" (a rounded corner about the path's corner point).
3. `start_tangency` (TR56, D1905): optional, "none" (default: the section is the profile as drawn, even where the path leaves its plane at a slant) or "path_tangent" (the section is turned square to the path's start).
4. `sweep_direction` (TR137, D1906): optional, for a profile part way along the path (the path crosses its plane): "forward" (default, along the path), "backward" or "both"; `twist_angle2` or `twist_turns2` twist the backward side on its own.
5. `merge_faces` (TR56, D1905): optional boolean: a smooth path of several pieces is swept as one spline, so each profile edge makes one side face.
6. `show_section` (a whole number, 0 for none) picks section `k` of `COUNT`, evenly spaced from the start (1) to the end (`COUNT`). A sweep's section is its profile carried along the path with the least turning, worked out without the kernel's sweep, so it shows even when the sweep fails; a loft's is a slice of the built loft square to the line from its first profile's centre to its last. The section is drawn as reference geometry (`extras["reference"]`) with a report line.
7. `section_values` is text such as `d1 = 10 + 10 * t; d2 = 4`: profile sketch dimensions (by id, `d1`, or by the user's name) and formulas of `t`, the position along the path from 0 at the start to 1 at the end, in the units of the dimension (mm or degrees; variables of the part may be used too). The profile sketch is solved again at each of `STEPS` stations with those values, carried along the path with the least turning, and the sections are joined with a smooth loft.
8. Also written: `scale_start` (number, optional); `scale_end` (number, optional); `scale_law` (one of "linear", "smooth", optional).

#### 5.3.35.42 Tab Slot (`tab_slot`), later parameters

1. Type `tab_slot`. Params (all optional): `tab_count` (default 2), `tab_length`, `depth` (default the thickness), `spacing` (0: spread over the edge), `clearance`. `edge_offset` (length): the tabs spread between two equal offsets in from the ends of the edge; with a spacing they stay centred on the edge. `skip_tabs` (text such as "2, 4"): tab numbers left out, with their slots (TR174 item 6, D1107). The Sheet Metal feature's `kerf` makes each slot that much narrower on each side in the sheet's plane (D802).

#### 5.3.36 References and keys of the types above

Keys that the sections above name only in passing.

1. Deform Point (`deform_point`), Curve to Curve (`deform_curve`) and Surface Push (`surface_push`): `refs.bodies`, a face of each body to deform; every body when the list is empty.
2. Finger Joint (`finger_joint`) and Half Lap (`half_lap`): `refs.bodies`, a face of each of the two plates.
3. Hose Fitting (`hose_fitting`): `pos_x`, `pos_y`, `pos_z` (lengths), the typed position when `refs.base_point` is empty, as for the mounting boss (5.3.24 item 4).
4. Linear Pattern (`linear_pattern`): `refs.direction2`, the second direction (a straight edge, flat face, plane, axis or sketch line), used when `second_direction` is on.
5. Modelled Thread (`modeled_thread`): `lead_in`, optional boolean: a 45 degree cone at the start of the thread removes its thin first turn.
6. 3D Sketch (`sketch3d`): the feature's `lines` key, beside `params`, holds the free lines: a list of `{ "kind", "points" }` objects, where `kind` is `"line"` or `"spline"` and `points` is a list of `[x, y, z]` in mm.

#### 5.3.37 Choices and references of the types above

The choices and references below are read by the feature types but were not named in their sections (DECISIONS D2631). Each list gives every value a choice may hold, so a file can be read without the code. Nothing about the format changed.

#### 5.3.37.1 Base Flange (`base_flange`), start choices

1. `start_condition`: `"sketch_plane"` (the default when the key is missing), `"surface"`, `"vertex"` or `"offset"`, as Extrude (5.3.1 item 7). The start must be parallel to the sketch plane.

#### 5.3.37.2 Chamfer (`chamfer`) and Fillet (`fillet`), partial by reference

1. `partial`: `"distance"`, `"percent"` or `"reference"`. With `"reference"` (TR64, D1401) the two picks in `refs.partial_ends` (vertices, points or planes) mark where the bevel or round starts and ends along each edge.

#### 5.3.37.3 Corner Relief (`corner_relief`), relief types

1. `relief_type`: `"dogbone"` (the default: a round cut along the corner's diagonal, into both walls), `"t_bone"` (a round cut into one wall only; `flip` picks the other wall) or `"fillet"` (the corner rounded to the tool).

#### 5.3.37.4 Crush Ribs (`crush_ribs`), Ring Groove (`ring_groove`) and O Ring Groove (`oring_groove`), the end measured from

1. `from_end`: `"start"` (the default) or `"end"`: the end of the picked round face, along its axis, that the length or position is measured from.

#### 5.3.37.5 Curve Array (`curve_array`), square to a face

1. `refs.square_face` (TR373, D1017): optional, a face. Each copy turns so that the face's normal under it stays its up direction and the curve stays its forward direction, for copies along a curve on a curved face. It wins over `orient`.

#### 5.3.37.6 Deform Point (`deform_point`), Curve to Curve (`deform_curve`) and Surface Push (`surface_push`), choices

1. `axis`: `"x"`, `"y"` or `"z"`, the shared triad key of 5.3.33 item 1. These local modes move part of a body and ignore the triad, so the key is written but not used.
2. Surface Push `tool`: `"sphere"` (the default; it uses `tool_x` and cannot push deeper than its radius), `"ellipsoid"` (`tool_x` and `tool_y` are its half sizes across) or `"rectangle"` (a flat bottom with rounded sides a fifth of its size).

#### 5.3.37.7 Dome (`dome`), direction

1. `refs.direction` (TR147, D1805): optional, a straight edge, flat face or plane that the dome rises along, turned to leave the face. Without it the dome rises square to the face.

#### 5.3.37.8 Draft (`draft`), choices

1. `propagation`: `"none"` (the default: only the picked faces), `"tangent"` (and the faces joined smoothly to them), `"all"`, `"inner"` or `"outer"`. `refs.faces` may be empty for the last three.
2. `draft_type` `"fixed_edge"` (TR323, D1804): with `refs.fixed_edges`, each face turns about its own picked edge instead of about the neutral plane.

#### 5.3.37.9 Sheet metal bend values (`edit_bends`, `hem`, `jog`, `miter_flange`)

1. `method`: `"k_factor"`, `"bend_allowance"`, `"bend_deduction"` or `"bend_table"`, as the Sheet Metal folder (5.3.32 item 2). The first uses `k_factor`, the next two `allowance`, and the last the part's top level `bend_table`. When left out, the folder's method is used.
2. Hem and Miter Flange `relief`: `"rectangular"`, `"obround"` or `"tear"`. Hem `relief_by`: `"ratio"` (the default: the relief is `relief_ratio` times the thickness, wide and deep) or `"size"` (from `relief_width` and `relief_depth`).
3. Jog `position`, where the bend sits against the sketched line, as Sketched Bend: `"centreline"` (the default: the bend's flat length is centred on the line), `"material_inside"` (the bend lies on the fixed side of the line), `"material_outside"` (on the moving side) or `"bend_outside"` (the fixed side ends and the moving side starts at the line).

#### 5.3.37.10 Extrude (`extrude`), print top

1. `print_top`: `"none"` (the default: holes stay round), `"teardrop"` or `"flat"` (5.3.35 Extrude item 1).

#### 5.3.37.11 Helix (`helix`), pitch type

1. `pitch_type`: `"constant"` (the default when the key is missing) or `"variable"` (helix only, with the `vp_` rows).

#### 5.3.37.12 Hole (`hole`), later types and references

1. `hole_type` also takes:
   - `"self_tapping"` (TR255, D840): a hole for a screw that cuts its own thread, sized by FDCAD's rule, with an entry bevel (the near side countersink) unless `near_csk` is false.
   - `"magnet"` (TR179, D869): a pocket for a magnet. `diameter` is the magnet's diameter or a block's width, `depth` its thickness and `magnet_length` a block's length (0 for a round magnet).
   - `"dowel"` (TR252, D872): a hole for a dowel pin, sized from the pin and its fit.
   - `"bearing"` (TR251, D873): a bearing seat built as a counterbore. `cbore_diameter` is the bearing's outside diameter, `cbore_depth` its width and `diameter` the shoulder hole below it. `bearing_groove` adds a retaining ring groove (`bearing_width`).
   - `"counterdrill"` (TR144, D1506): a counterbore with a cone at its floor (`cdrill_angle`).
   - `"pipe_tapped"` (TR145, D1511): as tapped, with the wall tapered 1 in 16 on the diameter.
   - `"custom"` (TR144 item 1, D1912): the hole is the text `stack` (5.3.35 Hole item 4) and uses no table sizes.
2. `refs.hole_axis` (TR397 item 1, D1915): optional, a pick that gives an axis, such as a straight edge or a reference axis. Each hole keeps its start point and turns to this direction, the way that goes into the part, instead of square to the face.
3. `refs.start_plane` (TR144 item 3, D1913): optional, a plane or flat face. Every hole moves along its axis to start there, in place of the face it is placed on.

#### 5.3.37.13 Insert Part (`insert_part`), placement

1. `place`: `"offset"` (the default: moved by `dx`, `dy`, `dz` and turned by `rx`, `ry`, `rz`) or `"on_frame"` (on `refs.frame`), as Linked Copy.

#### 5.3.37.14 Loft (`loft`), constraints, thin feature and guides

1. `start_constraint` and `end_constraint`: `"default"` (smooth through the profiles), `"none"`, `"normal"`, `"direction"`, `"tangent"` or `"curvature"`. `"tangent"` and `"curvature"` (TR136 item 2, D1924) are for an end profile that is a face of the part: the direction comes from the faces next to it, as Direction with `start_length` or `end_length`; curvature adds a second guiding copy.
2. `thin_type`: `"one_direction"`, `"mid_plane"` or `"two_direction"`, with the other thin keys of 5.3.1 item 13 (bosses only).
3. `refs.guides` (TR55, D804): optional, any number of sketches, curves or edges. Each must touch every profile, and the added sections between profiles follow them.
4. `refs.centerline` (TR55, D804): optional, one sketch, curve or edge. The `sections` added in each span are turned square to it and centred on it. Guides and a centerline need an open, solid loft.

#### 5.3.37.15 Modelled Thread (`modeled_thread`), flat sided forms

1. `form` also takes `"trapezoidal"` (metric trapezoidal, 30 degrees included, depth half the pitch), `"acme"` (29 degrees included, depth half the pitch) and `"buttress"` (a 7 degree load flank and a 45 degree back, depth 0.6 of the pitch) (TR254, D1510).

#### 5.3.37.16 Mounting Boss (`mounting_boss`), mating references

1. `refs.height_face` (TR146, D1517): optional, the mating face. The boss reaches it less `height_clearance`, in place of `boss_height`.
2. `refs.pin_edge` (TR146): optional, a round edge of the mating hole or pin. The pin is that edge's diameter less twice `pin_clearance` (a pin hole: plus).

#### 5.3.37.17 Move/Copy Body (`move_copy_body`), modes and handles

1. `mode`: `"translate"` (the default), `"rotate"`, `"frame"` (TR268, D1815: `refs.from_frame` onto `refs.to_frame`) or `"relations"` (TR268 item 1, D2415: `refs.rel_from` and `refs.rel_to` pairs with the `relations` text, solved together).
2. `refs.pivot_point` (TR268 item 3, D2416): with `pivot` `"picked"`, the point where the handles sit and turns about the centre go. Picking it moves only the handle, not the bodies.
3. `refs.handle_plane` (TR268 item 3, D2416): with `handle_axes` `"plane_axes"`, the plane whose X, Y and normal the handles' axes follow.

#### 5.3.37.18 Move Face (`move_face`), fit

1. `print_fit`: `"none"` (the default: no fit gap), `"clearance"`, `"slip"` or `"press"`.

#### 5.3.37.19 Pattern options (`fill_pattern`, `follow_pattern`, `pattern_chain`, `point_pattern`, `table_pattern`)

1. `preview`: `"full"` (the default) or `"partial"`. With partial the live preview builds only the first copies: one for Point Pattern and Table Pattern, three for Pattern Chain. Fill Pattern and Follow Pattern take the key with the other shared pattern keys and always preview every copy.
2. `region_mode` (TR398, D1503): with `refs.region` (faces or sketches), `"inside"` (the default) leaves out every copy whose seed centre lands over a region face, and `"outside"` every copy that lands over none of them.
3. `check` (TR399, D1519): `"full"` (the default: each copy must touch the part, or overlap it for a cut) or `"fast"` (those tests per copy are skipped; the one boolean of all copies still runs).

#### 5.3.37.20 Primitive (`primitive`), geodesic kinds

1. `kind` also takes `"geodesic_sphere"` and `"geodesic_dome"` (TR371 item 4, D936), with `diameter` and `frequency`: a sphere of flat triangles, made from an icosahedron with each face split `frequency` times. The dome keeps the top half, cut flat at the middle.

#### 5.3.37.21 Reference Plane (`ref_plane`), later methods

1. `method` also takes `"tangent"` (TR74, D903: touching a cylinder face, on the side of a picked point, or parallel to a picked plane) and `"line_point"` (through a straight edge or axis and a point off it). Both take two picks, `refs.first` and `refs.second`.

#### 5.3.37.22 Reference Point (`ref_point`), centre of mass

1. `method` also takes `"centre_of_mass"` (TR80, D1021). It needs no picks: the point is the centre of the solids built so far, or the part's typed centre of mass when Mass Properties has one.

#### 5.3.37.23 Revolve (`revolve`), thin feature

1. `thin_type`: `"one_direction"`, `"mid_plane"` or `"two_direction"`, with the other thin keys of 5.3.1 item 13.

#### 5.3.37.24 Shaft Shape (`shaft_shape`), key sizes

1. `key_standard`: `"rule"` (the default: a slot a quarter of the diameter wide and an eighth deep), `"metric"`, `"inch"` or `"woodruff"`.

#### 5.3.37.25 Split for Printing (`split_for_print`), later connectors and path

1. `connector` also takes `"magnets"` (TR181, D1211: `magnet_diameter`, `magnet_depth`; a round pocket in each piece, no body added) and `"screws"` (`screw_diameter`, `nut_size`, `nut_height`: a hole right through along the cut's normal and a hexagon nut pocket where it leaves the part).
2. `refs.path` (TR181, D2002): with `mode` `"sketch"`, the sketch whose curves are swept through the part along its normal to make the cut.

#### 5.3.37.26 Sweep (`sweep`), choices and references

1. `profile_type`: `"sketch"` (the default), `"circular"`, `"face"` (TR138, D1516: the flat model face in `refs.profile_face`, holes included) or `"body"` (TR138 item 3, D2405: cuts only, `refs.tool_body` moved along the path).
2. `orientation`: `"follow_path"` (the default), `"keep_normal"`, `"curvature"` (TR56, D1504: the section turns with the path's curvature, with no twist), `"face"` (TR396, D1514: the section's up direction keeps to the normal of `refs.orient_face`, the face under the path) or `"second_path"` (TR396, D1514: the section's X axis points at `refs.x_path`, a sketch or curve beside the path).
3. `thin_type`: `"one_direction"`, `"mid_plane"` or `"two_direction"`, with the other thin keys of 5.3.1 item 13 (bosses only).
4. `refs.profiles` (TR137 item 2, D1907): optional, later sketches the section passes through, sorted by where they sit along the path. Each must be one closed outline that the path passes through.

#### 5.3.37.27 Wrap (`wrap`), project method and pull

1. `method`: `"analytical"` (the default when the key is missing), `"spline"` or `"project"` (TR156, D2113: the sketch projected along `refs.pull` or the sketch normal, onto any face).
2. `refs.pull` (TR75 item 2, D2112): optional, a line, edge or plane. With it, emboss and deboss walls run along that direction instead of square to the face.

## 6. Sketches

```json
{
  "id": "f5",
  "type": "sketch",
  "name": "Sketch 1",
  "suppressed": false,
  "params": {},
  "refs": { "plane": { "feature": "f2" } },
  "next_entity": 5,
  "entities": [
    { "id": "e1", "type": "point", "x": 0, "y": 0, "construction": false },
    { "id": "e2", "type": "point", "x": 50, "y": 0, "construction": false },
    { "id": "e3", "type": "line", "p1": "e1", "p2": "e2", "construction": false },
    { "id": "e4", "type": "circle", "center": "e1", "radius": 10, "construction": false }
  ],
  "relations": [
    { "type": "horizontal", "entities": ["e3"] },
    { "type": "fixed", "entities": ["e1"] }
  ],
  "dimensions": [
    { "id": "d1", "type": "distance", "entities": ["e1", "e2"], "driving": true,
      "param": { "expr": "50", "value": 50 } }
  ]
}
```

1. Entity IDs are `"e"` plus an integer from `next_entity`. Never reused, even after deletion.
2. Coordinates are in millimetres in the sketch plane's local system and store the last solved position.
3. Entity types (Phase 1): `point`, `line`, `circle`, `arc` (center, start, end, `ccw` boolean). Phase 2 adds (DECISIONS D278):
   - `ellipse`: `center`, `major` and `minor`, three point ids: the centre and the ends of the major and minor semi axes (the minor end lies a quarter turn counter clockwise from the major end). `{ "id": "e9", "type": "ellipse", "center": "e6", "major": "e7", "minor": "e8", "construction": false }`
   - `ellipse_arc`: as `ellipse`, plus `start` and `end` point ids on it; it runs counter clockwise from `start` to `end`.
   - `spline`: `points` (two or more point ids the curve passes through) and `handles` (one point id per point: the end of its tangent handle). Between two points the curve is the cubic Bezier piece with poles point, its handle, the next point's handle mirrored through the next point, and the next point.
   Slots and polygons are stored as lines, arcs and relations (D277), not as entity types of their own. A later phase adds `text`.
4. Relation types (Phase 1): `horizontal`, `vertical`, `coincident`, `collinear`, `parallel`, `perpendicular`, `tangent`, `concentric`, `coradial`, `equal`, `midpoint`, `symmetric`, `intersection`, `fixed`. What `entities` holds for each:
   - `horizontal`, `vertical`: one or more lines, or two or more points (the points line up with the first).
   - `coincident`: a point, then a point, line, circle or arc.
   - `collinear`, `parallel`: two or more lines. `perpendicular`: two lines.
   - `tangent`: two curves, at least one a circle or arc.
   - `concentric`: two or more circles or arcs, or a point and one or more circles or arcs.
   - `coradial`: two or more circles or arcs (same centre and same radius).
   - `equal`: two or more lines, or two or more circles and arcs.
   - `midpoint`: a point and a line or an arc.
   - `symmetric`: two points, two lines, two circles or two arcs, then the mirror line last. Mirrored lines and arcs pair their end points so that the mirrored ends lie closest.
   - `intersection`: a point, then two lines.
   - `fixed`: any entities.
   - `offset`: pairs of a source curve and its offset copy, `[source1, copy1, source2, copy2, ...]`, all at one distance, plus `"value": <mm>` after `entities`. A line copy stays parallel at that distance; a circle or arc copy shares the source's centre and its radius differs by the distance. Without `value` the distance is free and a sketch dimension sets it. Written by the Offset tool (DECISIONS D272).
   Schema note: `offset` and the optional relation key `value` were added in Phase 2 (DECISIONS D272) as additions to schema 1; a relation without `value` saves exactly as before, so older files open and save unchanged.
   Schema note: `coradial`, `intersection` and the wider lists above (more than two points or lines, a midpoint on an arc, symmetric lines, circles and arcs) were added during Phase 1 (DECISIONS D122). They are additions to schema 1, not a schema change: every older file opens unchanged.
5. Dimension types (Phase 1): `distance`, `horizontal_distance`, `vertical_distance`, `angle`, `radius`, `diameter`, `doubled_distance`. `driving: false` marks a reference (driven) dimension.
   - A `distance` to the centre of a circle or arc names the centre point. A `distance` to the near or far side of a circle or arc names the circle or arc itself and adds `"measure_to": { "<id>": "nearest" | "farthest" }` after `param`. The key is left out when every circle is measured to its centre.
   - An `angle` adds `"supplement": false` or `true` after `param`: false measures the angle between the two lines' directions (first point to second point), true the angle beside it (180 degrees less). Without the key (files saved before it existed) the solver keeps whichever of the two is closer to the current shape.
   - `doubled_distance` names a line or point, then an axis line, and holds twice the distance between them (a diameter on a revolve profile).
   - `arc_length` (Phase 2, DECISIONS D515) names one arc and holds its length along the curve: radius times the counter clockwise sweep from its start to its end point. Smart Dimension makes it from an arc and its two end points; only the arc is stored, since its end points are its own. Example: `{ "id": "d4", "type": "arc_length", "entities": ["e9"], "driving": true, "param": { "expr": "25", "value": 25 } }`.
   - Any dimension may add `"label": [dx, dy]` after its other keys: where the user placed or dragged the dimension text, as an offset in millimetres in the sketch plane from the dimension's anchor. The anchor is the middle of the two measured points for `distance`, `horizontal_distance`, `vertical_distance` and `doubled_distance`; the centre of the circle or arc for `radius` and `diameter`; the middle of the two lines' midpoints for `angle`; and the point halfway along the arc for `arc_length`. Because the offset is from the anchor, the text moves with the geometry. Without the key the text is placed automatically beside the geometry.
   - Any dimension may add `"name": "<name>"` (DECISIONS D698): the user's name for it in formulas, written only when set. A letter, then letters, digits or underscores.
   Schema note: `doubled_distance`, `measure_to` and `supplement` were added during Phase 1 (DECISIONS D123), and `label` (DECISIONS D150), as optional additions to schema 1. Files without them open unchanged. `arc_length` (DECISIONS D515) is a new value in the existing list of dimension types, also an addition to schema 1: files without it open and save unchanged. A dimension type the app does not know is still read and written back unchanged, but the solver stops at it and the sketch shows the error "Unknown dimension type", so a file that uses `arc_length` opened in an older FDCAD loses nothing on save.
6. A sketch on a model face stores the face reference in `refs.plane` instead of a plane feature.
7. Sketch pictures (Phase 2, DECISIONS D279): an optional `pictures` list after `dimensions`, left out when the sketch has none, so older sketches save unchanged. Each picture is `{ "id": "p1", "embedded": "img3f2a...", "origin": [x, y], "angle": a, "width": w, "height": h, "flip_h": false, "flip_v": false, "transparency": 0.0, "lock_aspect": true }`: `embedded` names an `image` block (section 11), `origin` is the image's lower left corner in sketch millimetres, `angle` turns it about that corner (radians), `width` and `height` are in millimetres, the flips mirror the image within that rectangle, and `transparency` runs from 0 (opaque) to 1. Pictures are display only: nothing snaps to them and they never form profiles.
8. Curves may cross (DECISIONS D116 item 1). They split the sketch into regions, which features can pick (5.3.3). Nothing about crossings is stored in the sketch.
9. A `point`, `line` or `circle` that is a fixed construction copy of part geometry (snapping to the part, TOOL_SPEC T1.2.2, DECISIONS D250) may add `"source"` after `construction`: what it was copied from, as `{ "kind": "vertex", "name": "vertex(...)" }` (a point on a part corner), `{ "kind": "edge", "name": "edge(...)" }` (a line on a straight edge, a circle on a round edge, or a point on a round edge's centre) or `{ "kind": "origin" }` (a point on the part origin). Names follow section 8. The copy holds its own position; `source` is only used to find copies that no longer match the part, which the app reports as a warning with an Update Copies button. The copy never moves without the user's confirmation. The key is left out for ordinary geometry and for copies made before it existed.
   Schema note: `source` was added during Phase 2 work (DECISIONS D250) as an optional addition to schema 1. Files without it open and save unchanged.
10. Text (Phase 4, DECISIONS D323): an optional `texts` list, written only when the sketch has text, so sketches without text save unchanged. Each item has `id` (`"t"` plus an integer) and `text`, and only the keys that differ from their defaults: `x`, `y` (always written), `height` (5), `angle` (0, radians), `font` (`"sans-serif"`), `bold`, `italic`, `flip_h`, `flip_v` (false), `align` (`"left"`, `"center"`, `"right"` or `"full"`), `box` (0, text box width), `width` and `spacing` (100, percent), `char_angle` (0, radians, each character's own turn) and `curve` (empty, or the id of a sketch line or arc the text follows). Text becomes closed regions of the profile; it is not an entity and takes no relations or dimensions.
11. Derived sketch (TR49, DECISIONS D845): `refs.derived_from` (`{ "feature": <sketch id> }`) makes the sketch a linked copy of that sketch. It keeps no geometry of its own: on every rebuild it takes the other sketch's solved geometry, moved by `data.derived_place` (`dx`, `dy` in mm and `angle` in radians, about the sketch origin, in its own plane), and holds every point with a Fixed relation. Break Link turns it into an ordinary sketch.
12. Pierce points (TR101, DECISIONS D843): `refs.pierce` is a list of `{ "point": <point id>, "curve": <ref> }`. The curve is a curve feature, another sketch or an edge of the part. On every rebuild the point moves to the crossing of the curve with the sketch plane nearest to where it is, before the sketch is solved, and a Fixed relation holds it there. A point whose curve no longer crosses the plane stays where it is, with a warning.

## 7. References

References point at features or at topology produced by features.

```json
{
  "kind": "edge",
  "name": "edge(f6/cap/end|f6/side/e3)",
  "snapshot": {
    "curve": "line",
    "midpoint": [25.0, 0.0, 10.0],
    "direction": [1.0, 0.0, 0.0],
    "length": 50.0,
    "face_normals": [[0.0, 0.0, 1.0], [0.0, 1.0, 0.0]]
  }
}
```

1. `kind`: `feature`, `face`, `edge` or `vertex`. A feature reference uses `{ "feature": "f5" }` instead.
   A sketch entity reference uses `{ "sketch_entity": "e9" }` (for example a revolve axis in its sketch).
2. `name`: persistent name (section 8).
3. `snapshot`: geometry at the time the reference was made. Used only when the name cannot be resolved.
   1. Face snapshot: `surface` type, `point` (centroid), `normal` (planar faces) or `axis` (cylindrical and conical faces), `area`.
   2. Edge snapshot: `curve` type, `midpoint`, `direction` (lines) or `axis` and `radius` (circles and arcs), `length`, `face_normals`.
   3. Vertex snapshot: `point`.
4. Resolution: name first. If the name fails, use the snapshot to find one clear match and mark the feature with a warning. If there is no confident match, mark the feature with an error. Never pick between equally good matches.

## 8. Naming grammar

1. Face: `<feature>/<role>` or `<feature>/<role>/<source>`. Examples: `f6/cap/start`, `f6/cap/end`, `f6/side/e3`, `f9/fillet/edge(f6/cap/end|f6/side/e3)`.
2. When a later feature splits a face, the pieces get suffixes `#1`, `#2` and so on, ordered by centroid position (X, then Y, then Z).
3. Edge: `edge(<face>|<face>)`, the two neighbouring face names sorted alphabetically.
4. Vertex: `vertex(<face>|<face>|<face>)`, three or more neighbouring face names sorted alphabetically.
5. Each feature type documents the roles it creates.
6. Sketch region: `region(<side>|<side>|...)`, one side for each sketch curve around the region (outer loop and holes): the entity id plus `+` or `-`. For a line `+` is the left of its `p1` to `p2` direction; for a circle or arc `+` is the side of its centre. Sides are sorted by entity number, then sign. Regions with the same sides get `#1`, `#2` by area centre X, then Y. Example: `region(e3+|e5+|e6+|e7+|e9-)`.
7. When a curve split by crossings gives several side faces, they are `<feature>/side/e3`, `<feature>/side/e3#2` and so on, in order along the curve.

## 9. Configurations and design tables

Schema 2 form (DECISIONS D391):

```json
{
  "active": "Long",
  "items": [
    { "name": "Default",
      "overrides": { "f6.depth": { "expr": "40", "value": 40 }, "f9.suppressed": false,
                     "var.Width": { "expr": "2in", "value": 50.8 } } },
    { "name": "Long",
      "overrides": { "f6.depth": { "expr": "60", "value": 60 }, "f9.suppressed": true,
                     "var.Width": { "expr": "3in", "value": 76.2 } } }
  ],
  "design_table": null
}
```

1. The features and variables in the file hold the values of the `active` configuration.
2. `overrides`: every configured path (a value that differs between configurations) mapped to that configuration's value. Every configuration lists the same paths, sorted. Path forms: `<feature id>.<param>` (a parameter object, string, boolean or number), `<sketch feature id>.<dimension id>` (a sketch dimension, for example `f5.d1`), `<feature id>.suppressed` (a boolean) and `var.<variable name>` (a parameter object). Paths that name nothing are ignored and kept. A value no configuration overrides is shared by all of them.
3. On load the active configuration's overrides are written into the features and variables. A path that some configurations lack gets the value in the file.
4. `design_table` (Phase 4, DECISIONS D392): `null`, or `{ "columns": ["var.Width", "f6.depth", "f9.suppressed"], "rows": [{ "config": "Long", "values": ["3in", "60", "S"] }] }`. Values are typed text: expressions for typed values, `S` or `U` for suppression, `true` or `false` for tick box settings, the plain word for choices. The rows are written from the configurations, so they always agree with `items`.
5. Schema 1 form (still written when no configuration has an override and there is no design table): each item is `{ "name": "Default", "overrides": {}, "suppressed": [] }`. In schema 1 files written by other programs, `suppressed` lists feature IDs suppressed in that configuration; migration to schema 2 turns each listed feature into a `<id>.suppressed` override in every configuration (true where listed, false elsewhere).

## 10. Appearance

1. Colours are hex strings `#RRGGBB`, or `#RRGGBBAA` when transparency is set.
2. `part_color`: default colour for all faces.
3. `faces`: face name mapped to colour. Faces that can no longer be resolved keep their entry but are ignored until they resolve again.
4. `hidden` (optional, added in 0.1.0): IDs of sketches the user hid on purpose. A finished sketch shows in the 3D view until a feature uses it. Reference geometry features (5.3.20) also show until they are listed here (DECISIONS D251).
5. `shown` (optional, added in 0.1.0): IDs of sketches and planes the user showed on purpose. A used sketch or a plane is hidden unless listed here.
6. Both lists are sorted by ID number and left out while empty, so a part that never used them saves exactly as before. Keys order: `part_color`, `faces`, `features`, `bodies`, `hidden`, `shown`.
7. `features` (optional): feature ID mapped to the colour of every face that feature made (the first part of the face name, section 8 item 1). `bodies` (optional): body number, from `"1"` in the order of the Solid Bodies folder, mapped to the colour of its faces. Both are left out while empty (DECISIONS D254). The most specific colour wins: `faces`, then `features`, then `bodies`, then `part_color`. Keys are sorted by length, then text. Schema note: optional additions to schema 1; files without them open and save unchanged. Schema note: these keys are optional additions to schema 1, not a schema change. Files without them open unchanged, and older versions of FDCAD keep them on save (section 14 item 4). Show and hide state is not part of the cache key (section 13 item 2).

### 10.1 Hidden bodies (Phase 3, DECISIONS D410)

1. `hidden_bodies` (optional): face names (section 8), one for each body the user hid on purpose. A body is hidden while any of its face names is listed, so the choice follows the body when features above it change and the bodies are numbered again. Names that no longer resolve are kept and ignored.
2. Sorted by length, then text, and left out while empty. It is the last key of `appearance`, after `shown`.
3. Display only: hidden bodies still take part in every feature, measurement and export. Isolating bodies is a view state and is not saved.
4. Schema note: an optional addition to schema 1, not a schema change. Files without it open and save unchanged.

## 11. Embedded data

```json
{
  "b1": { "type": "step", "encoding": "gzip+base64", "filename": "bracket.step", "data": "H4sIA..." }
}
```

1. Embedded files are stored gzip compressed and base64 encoded.
2. Block types: `step` (imported STEP), `mesh` (imported STL, 3MF or OBJ; `format` field gives which), `image` (sketch picture; `format` is `png`, `jpeg` or `bmp`). Image block ids written by FDCAD are `img` plus the first 12 hex digits of the SHA-1 of the image file, so one image used twice is stored once; readers treat ids as opaque. An image block that no sketch picture uses any more leaves the file when the sketch is written back (D279).
3. Features and sketch entities reference a block by ID, for example `"refs": { "source": { "embedded": "b1" } }`.
4. The original filename is kept for display only. The file is never read from disk again.
5. Block keys in order: `type`, `format` (mesh blocks only), `encoding`, `filename`, `data`. Block IDs are `b1`, `b2` and so on, never reused in a file. The gzip header carries no time stamp, so the same file always encodes to the same text (DECISIONS D290).
6. A block stays in the file after its feature is deleted, so undo can bring the feature back. Blocks no feature uses are harmless.

## 12. Expressions

Contents: 12.1 Units, 12.2 Forms, 12.3 Disambiguation rules.

### 12.1 Units

1. Lengths: `mm`, `cm`, `m`, `in`, `ft`, plus `"` for inches and `'` for feet.
2. Conversions to millimetres: 1 cm is 10 mm, 1 m is 1000 mm, 1 in is 25.4 mm, 1 ft is 304.8 mm.
3. Angles: `deg` and `rad`. A number without a suffix in an angle field is degrees.
4. A length without a suffix uses the part's unit system.
5. Unit names are case insensitive. Whitespace between number and unit is optional.

### 12.2 Forms

1. Decimal: `20`, `20.5`, `.5in`. A decimal may end in an exponent (DECISIONS D2620): `e` or `E`, an optional `+` or `-`, and digits, for example `2e6`, `2E+06`, `1.5e-3`, `2e3 mm`. The exponent needs its digits, so `2e` alone is the number 2 followed by an unknown unit `e`.
2. Fraction: `7/8 mm`, `2/3in`.
3. Mixed number: `1 3/4in` (one and three quarter inches).
4. Feet and inches: `1' 3"`, `1ft 3in`, `1' 3 1/2"`.
5. Arithmetic: `20mm + 1/4in`. Operators are `+` (add), the U+002D minus sign (subtract and negate), `*` (multiply), `/` (divide), and parentheses. Each length term may carry its own unit.
6. Variables and formulas: an expression starting with `=` may reference variables by name, for example `=Width/2`, `=(Width + 5mm)*2`.
7. Functions allowed after `=`: `sin`, `cos`, `tan`, `sqrt`, `abs`, `min`, `max`, `round`, and the constant `pi`. Trigonometric functions take and return radians. Added in Phase 4 (DECISIONS D390): `asin`, `acos`, `atan`, `atan2` (they return angles), `floor`, `ceil`, `if(condition, then, else)`, `and`, `or`, `not`.
8. Quoted names (Phase 4, DECISIONS D390): after `=`, a name in double quotes, for example `="Width"/2`. Quoted names may also name a feature value as `<value>@<feature name>` or `<value>@<feature id>`, for example `="depth@Extrude 1"` or `="d1@Sketch 1"` (a sketch dimension). A double quote right after a number is still the inch symbol.
9. Comparisons (Phase 4, DECISIONS D390): `<`, `>`, `<=`, `>=`, `==`, `!=` give 1 (true) or 0 (false). Both sides need the same kind of unit.

### 12.3 Disambiguation rules

1. A space between an integer and a fraction followed by a unit means a mixed number: `1 3/4in` is 1.75 in.
2. A fraction binds before arithmetic: `1/4in + 2` is 0.25 in plus 2 part units.
3. Dimensional consistency is checked: adding a length to an angle, or a unitless number to a length inside a formula that starts with `=`, is an error. Outside formulas, a unitless number is treated as the part unit.

## 12A. Graphs (Phase 7, schema 2)

A part with at least one graph is written as schema 2 and adds a top level `graphs` array right after `features` (DECISIONS D27, D370). A part without graphs is still written as schema 1 with no `graphs` key, so it opens and saves byte for byte as before. Reading a schema 1 file migrates it in memory by adding an empty `graphs` array (`migrate_1_to_2`). FDCAD versions before the node editor refuse schema 2 files with the newer version message (section 15 item 4). Schema 2 also carries the configurations change of section 9 (DECISIONS D391); a schema 2 file without a `graphs` array has no graphs.

```json
{
  "id": "g1",
  "name": "Graph 1",
  "position": "f12",
  "next_node": 5,
  "nodes": [
    { "id": "n1", "type": "slider", "params": { "kind": "length", "min": 2, "max": 10, "step": 0.5, "value": { "expr": "4", "value": 4 } }, "ui": { "x": 40, "y": 60 } },
    { "id": "n2", "type": "cylinder", "params": { "height": { "expr": "10", "value": 10 } }, "ui": { "x": 220, "y": 60 } },
    { "id": "n3", "type": "add_as_feature", "params": { "operation": "subtract" }, "ui": { "x": 420, "y": 60 } }
  ],
  "wires": [
    { "from": "n1.out", "to": "n2.radius" },
    { "from": "n2.body", "to": "n3.body" }
  ],
  "groups": [ { "id": "k4", "name": "Holes", "nodes": ["n1", "n2"] } ],
  "seed": 1
}
```

1. `id`: `"g"` plus an integer. Node IDs are `"n"` plus an integer from `next_node`; group IDs are `"k"` plus an integer from the same counter. IDs are never reused.
2. `position`: the feature after which the graph is evaluated (DECISIONS D26). `null` means the end of the tree. A position that names a deleted feature also means the end of the tree.
3. `nodes`: node `type`, its `params` and its position `ui` (`x`, `y` in editor units). Keys in that order.
   1. An input port with no wire takes its value from `params` under the port's name: a parameter object (section 3) for numbers, lengths and angles, `[x, y, z]` (mm) for points and vectors, a list of those for list inputs. A port with no stored value uses the node type's default.
   2. Settings are stored in `params` too: parameter objects for typed values, plain strings, numbers and booleans otherwise, and a reference (section 7) for `model_ref`.
   3. Typed values keep the typed text. A text starting with `=` is worked out again with the part's variables on every evaluation.
4. `wires`: connections written as `<node>.<port>`, from an output to an input. Several wires into one input make a list, in wire order. Wires never form a loop in the editor; a file whose wires loop still opens, and the nodes on the loop show an error.
5. `groups`: named frames around nodes in the editor. Display only.
6. `seed`: base seed for every random node, so results repeat exactly. Each random node also has its own `seed` setting.
7. A `graph_body` feature references its graph output: `"refs": { "graph": { "graph": "g1", "output": "n3" } }`. The output is an `add_as_feature` node; its `operation` (`"new"`, `"add"` or `"subtract"`) says what happens to the body. Face roles: `face/<k>`, numbered from 1 in the order of the graph body's faces. A `graph_body` feature must be below its graph's position.
8. Opening a file never runs code (DECISIONS D24). A node `type` that is not one of the types below shows an error on that node; nothing is evaluated from the text.
9. Values inside the graph use internal units (mm, radians). Comment nodes (`comment`, setting `text`) are notes on the canvas with no ports.
10. Unknown keys in a graph are preserved on save (section 14 item 4).

Node types, with their inputs, outputs and settings. Inputs marked list take a whole list; other inputs given a list run the node once per item.

Curve:

- `arc`: inputs `start` (point), `middle` (point), `end` (point); outputs `out` (curve); settings none.
- `circle`: inputs `plane` (plane), `centre` (point), `radius` (length); outputs `out` (curve); settings none.
- `interpolate`: inputs `points` (point, list); outputs `out` (curve); settings `closed`.
- `line`: inputs `start` (point), `end` (point); outputs `out` (curve); settings none.
- `offset_curve`: inputs `curve` (curve), `distance` (length); outputs `out` (curve); settings none.
- `polyline`: inputs `points` (point, list); outputs `out` (curve); settings `closed`.

Display:

- `comment`: inputs none; outputs none; settings `text`.

Input:

- `toggle`: inputs none; outputs `out` (boolean); settings `value`.
- `model_ref`: inputs none; outputs `curve` (curve), `body` (body), `plane` (plane); settings `kind`, `ref`.
- `slider`: inputs none; outputs `out` (number); settings `kind`, `min`, `max`, `step`, `value`.
- `point`: inputs `x` (length), `y` (length), `z` (length); outputs `out` (point); settings none.
- `read_param`: inputs none; outputs `out` (number); settings `feature`, `param`.
- `read_variable`: inputs none; outputs `out` (number); settings `variable`.
- `value`: inputs none; outputs `out` (number); settings `kind`, `value`.

List:

- `list_cull`: inputs `list` (list), `pattern` (list); outputs `out` (list); settings none.
- `list_flatten`: inputs `list` (list); outputs `out` (list); settings none.
- `list_item`: inputs `list` (list), `index` (number); outputs `out` (list); settings `wrap`.
- `list_length`: inputs `list` (list); outputs `out` (number); settings none.
- `list_reverse`: inputs `list` (list); outputs `out` (list); settings none.
- `list_shift`: inputs `list` (list), `offset` (number); outputs `out` (list); settings `wrap`.
- `list_sort`: inputs `list` (list), `keys` (list); outputs `out` (list), `indices` (list); settings none.

Math:

- `arithmetic`: inputs `a` (number), `b` (number); outputs `out` (number); settings `operation`.
- `expression`: inputs `a` (number), `b` (number), `c` (number), `d` (number); outputs `out` (number); settings `formula`, `kind`, `a_kind`, `b_kind`, `c_kind`, `d_kind`.
- `random`: inputs `count` (number), `min` (number), `max` (number); outputs `out` (list); settings `seed`.
- `range`: inputs `start` (number), `end` (number), `count` (number); outputs `out` (list); settings none.
- `remap`: inputs `value` (number), `source_min` (number), `source_max` (number), `target_min` (number), `target_max` (number); outputs `out` (number); settings `clamp`.
- `series`: inputs `start` (number), `step` (number), `count` (number); outputs `out` (list); settings none.
- `trig`: inputs `x` (angle); outputs `out` (number); settings `function`.

Output:

- `add_as_feature`: inputs `body` (body, list); outputs `out` (body); settings `operation`.
- `set_param`: inputs `value` (number); outputs `out` (number); settings `feature`, `param`.
- `set_variable`: inputs `value` (number); outputs `out` (number); settings `variable`.

Pattern:

- `attractor`: inputs `points` (point, list), `attractors` (point, list), `radius` (length), `near` (number), `far` (number), `shift` (length); outputs `values` (number), `points` (point), `distances` (length); settings none.
- `lattice`: inputs `body` (body), `cell` (length), `radius` (length); outputs `body` (body), `count` (number); settings `type`, `allow_many`.
- `voronoi`: inputs `boundary` (curve), `points` (point, list), `gap` (length); outputs `cells` (curve); settings none.

Point and Vector:

- `closest_point`: inputs `point` (point), `points` (point, list); outputs `out` (point), `index` (number), `distance` (length); settings none.
- `deconstruct`: inputs `point` (point); outputs `x` (length), `y` (length), `z` (length); settings none.
- `distance`: inputs `a` (point), `b` (point); outputs `out` (length); settings none.
- `divide_curve`: inputs `curve` (curve), `count` (number); outputs `points` (point), `tangents` (vector); settings none.
- `plane`: inputs `origin` (point), `normal` (vector); outputs `out` (plane); settings none.
- `point_grid`: inputs `plane` (plane), `count_x` (number), `count_y` (number), `spacing_x` (length), `spacing_y` (length); outputs `out` (point); settings none.
- `populate_region`: inputs `boundary` (curve), `count` (number); outputs `out` (point); settings `seed`.
- `vector`: inputs `x` (number), `y` (number), `z` (number); outputs `out` (vector); settings none.

Solid:

- `difference`: inputs `body` (body), `tools` (body, list); outputs `body` (body); settings `allow_many`.
- `intersection`: inputs `body` (body), `others` (body, list); outputs `body` (body); settings `allow_many`.
- `union`: inputs `bodies` (body, list); outputs `body` (body); settings `allow_many`.
- `box`: inputs `corner` (point), `size_x` (length), `size_y` (length), `size_z` (length); outputs `body` (body); settings none.
- `cylinder`: inputs `base` (point), `axis` (vector), `radius` (length), `height` (length); outputs `body` (body); settings none.
- `extrude`: inputs `curve` (curve), `distance` (length), `direction` (vector); outputs `body` (body); settings none.
- `array`: inputs `geometry` (body), `step` (vector), `count` (number); outputs `out` (body); settings none.
- `mirror`: inputs `geometry` (body), `plane` (plane); outputs `out` (body); settings none.
- `move`: inputs `geometry` (body), `vector` (vector); outputs `out` (body); settings none.
- `pipe`: inputs `curve` (curve), `radius` (length); outputs `body` (body); settings none.
- `rotate`: inputs `geometry` (body), `origin` (point), `axis` (vector), `angle` (angle); outputs `out` (body); settings none.
- `scale`: inputs `geometry` (body), `centre` (point), `factor` (number); outputs `out` (body); settings none.
- `sphere`: inputs `centre` (point), `radius` (length); outputs `body` (body); settings none.

## 13. Local solid cache

1. Location: macOS `~/Library/Caches/FDCAD`, Windows `%LOCALAPPDATA%\FDCAD\Cache`.
2. Key: SHA256 of the canonical JSON of `units`, `variables`, `configurations`, `features`, `graphs`, `rollback` and `embedded`. Appearance, `print_setup` and `app_version` are excluded because they do not change geometry.
3. Content: the rebuilt solid per configuration in OpenCascade binary BRep format, plus naming maps, plus intermediate solids for fast partial rebuilds. The intermediate solids (DECISIONS D1097) are `<key>.history.brep`, one compound of the result body of each feature that makes solids, the faces the steps share written once, and `<key>.history.json`, each result's feature key, body index, face names, issues, cosmetic threads and plain display data, with a stamp of the FDCAD build that wrote them: a history written by another build is never used.
4. Size limit 2 GB, least recently used entries removed first. Clearable from preferences.
5. A missing or corrupt cache entry is never an error; the part is rebuilt.

## 13A. Solid saved in the part file

1. The `solid` key (DECISIONS D1102) holds `{"format": 1, "key": k, "brep": b, "names": [[name, index], ...], "states": {fid: {"state": s, "messages": [...], "seconds": t}}}`. `k` is the cache key of the document it was built from (section 13 item 2). `b` is the finished body in OpenCascade binary BRep format, without display meshes, gzip compressed and base64 encoded. `names` gives each face name and the index of its face in the body's face order. `states` gives each feature's state (`ok`, `warning`, `error`), messages and the seconds it took to build (`seconds`, optional, DECISIONS D1106).
2. On open the solid is shown at once, while the tree is rebuilt behind it, but only when `format` is 1 and `k` equals the cache key of the document as read. Otherwise it is ignored: a file whose features were changed outside FDCAD, or by a reader that kept `solid` as an unknown key, is built from its tree. When the `seconds` of all features add up to more than 30 and no stored results (section 13 item 3) would make the rebuild quick, the tree is not rebuilt on open: the part is shown as saved, and the next change or Rebuild builds it (DECISIONS D1106).
3. Save writes it from the last rebuild when that rebuild finished for the document being saved, and leaves it out otherwise (a rebuild running, stopped early at a checkpoint or held feature, or a part shown from a cache only). A part shown from its saved solid and not rebuilt keeps that solid when saved unchanged. A missing or damaged `solid` is never an error.

## 14. Canonical form

1. Two space indentation, keys in the order shown in this document, a newline at the end of the file.
2. Floats rounded to 12 significant digits.
3. Arrays keep tree and entity order.
4. Unknown keys found on load are preserved on save, so files from newer minor versions are not damaged.

## 15. Versioning and migration

1. `schema` increases whenever a change is not backward compatible.
2. Migrations live in `fdcad/core/io/migrations`, one step per version (`migrate_1_to_2`, and so on), each with tests. `migrate_1_to_2` (DECISIONS D391) changes only the configurations block (section 9 item 5) and adds an empty `graphs` array (section 12A).
3. Opening an older schema migrates in memory; saving writes the lowest schema that holds the data (item 5; DECISIONS D370 and D391).
4. Opening a newer schema than the app supports shows: "This file was made with a newer version of FDCAD. Please update FDCAD to open it." The file is not modified.
5. A file is written with the lowest schema that holds its data, so saving a part that uses nothing new keeps its schema and its bytes.
6. Optional keys added within a schema (for example `keep_separate_body`, section 5.1, DECISIONS D527) are written only when not default, so they never raise the schema and files without them save byte for byte the same.

## 16. Complete minimal example

A 50 mm square plate, 10 mm thick:

```json
{
  "format": "fdef",
  "schema": 1,
  "app_version": "0.1.0",
  "units": "mm",
  "next_id": 7,
  "variables": [
    { "name": "Size", "kind": "length", "expr": "50", "value": 50 }
  ],
  "configurations": { "active": "Default", "items": [ { "name": "Default", "overrides": {}, "suppressed": [] } ], "design_table": null },
  "features": [
    { "id": "f1", "type": "origin", "name": "Origin", "suppressed": false, "params": {}, "refs": {} },
    { "id": "f2", "type": "plane", "name": "Front Plane", "suppressed": false, "params": { "basis": "xy" }, "refs": {} },
    { "id": "f3", "type": "plane", "name": "Top Plane", "suppressed": false, "params": { "basis": "xz" }, "refs": {} },
    { "id": "f4", "type": "plane", "name": "Right Plane", "suppressed": false, "params": { "basis": "yz" }, "refs": {} },
    { "id": "f5", "type": "sketch", "name": "Sketch 1", "suppressed": false, "params": {},
      "refs": { "plane": { "feature": "f2" } },
      "next_entity": 9,
      "entities": [
        { "id": "e1", "type": "point", "x": 0, "y": 0, "construction": false },
        { "id": "e2", "type": "point", "x": 50, "y": 0, "construction": false },
        { "id": "e3", "type": "point", "x": 50, "y": 50, "construction": false },
        { "id": "e4", "type": "point", "x": 0, "y": 50, "construction": false },
        { "id": "e5", "type": "line", "p1": "e1", "p2": "e2", "construction": false },
        { "id": "e6", "type": "line", "p1": "e2", "p2": "e3", "construction": false },
        { "id": "e7", "type": "line", "p1": "e3", "p2": "e4", "construction": false },
        { "id": "e8", "type": "line", "p1": "e4", "p2": "e1", "construction": false }
      ],
      "relations": [
        { "type": "fixed", "entities": ["e1"] },
        { "type": "horizontal", "entities": ["e5"] },
        { "type": "horizontal", "entities": ["e7"] },
        { "type": "vertical", "entities": ["e6"] },
        { "type": "vertical", "entities": ["e8"] },
        { "type": "equal", "entities": ["e5", "e6"] }
      ],
      "dimensions": [
        { "id": "d1", "type": "distance", "entities": ["e1", "e2"], "driving": true,
          "param": { "expr": "=Size", "value": 50 } }
      ]
    },
    { "id": "f6", "type": "extrude", "name": "Extrude 1", "suppressed": false,
      "params": { "operation": "boss", "end_condition": "blind",
                  "depth": { "expr": "10", "value": 10 }, "reverse": false },
      "refs": { "sketch": { "feature": "f5" } } }
  ],
  "rollback": null,
  "appearance": { "part_color": "#B4BCC4", "faces": { "f6/cap/end": "#2E6FD8" } },
  "print_setup": { "down_face": null },
  "embedded": {}
}
```
