"""User visible text for imports, curves and print tools (PHASE3_SPEC P3.5 to P3.9).

Kept apart from ``strings.py`` so parallel work on other panels does not clash.
Title case for commands, sentence case for messages (CLAUDE.md section 8).
"""

from __future__ import annotations

from fdcad.ui import strings

FILTER_OPENABLE = "Parts and imports (*.fdprt *.fdef *.step *.stp *.igs *.iges *.stl *.3mf *.obj)"
FILTER_STEP_IGES = "STEP and IGES files (*.step *.stp *.igs *.iges)"  # TR31
HEAL = "Heal..."
HEAL_TITLE = "Heal {name}"
HEAL_PROMPT = "Close gaps between faces up to (mm, at most {most}):"
FILTER_MESH = "Mesh files (*.stl *.3mf *.obj)"
IMPORT_STEP_TITLE = "Import STEP Body"
IMPORT_MESH_TITLE = "Import Mesh"
READ_FAILED = "Could not read {name}: {reason}. Check the file and try again."
IMPORTED = "{feature}: {name} imported."
IMPORTED_REPORT = "{feature}: {name} imported. {report}"

GROUP_CURVES = "Curves"
MENU_CURVES = "Curves"

# Curves (P3.6) --------------------------------------------------------------------------

GROUP_DEFINITION = "Defined By"
GROUP_PARAMETERS = "Parameters"
GROUP_SOURCE = "Sketch and Faces"
GROUP_ITEMS = "Items to Join"
DEFINITIONS = {
    "pitch_turns": "Pitch and Turns",
    "height_turns": "Height and Turns",
    "height_pitch": "Height and Pitch",
    "spiral": "Spiral",
}
PITCH_TYPES = {"constant": "Constant Pitch", "variable": "Variable Pitch"}
PROJECTION_MODES = {"faces": "Sketch on Faces", "sketches": "Sketch on Sketch"}
FIELD_REVERSE = "Reverse"
FIELD_CLOCKWISE = "Clockwise"
FIELD_TAPER_OUTWARD = "Taper Outward"
FIELD_CLOSED_ENDS = "Closed Ends"  # TR162 (D1923)
FIELD_BOTH = "Both Directions"
FIELD_FACES = "Faces to project onto"
FIELD_SECOND_SKETCH = "Second sketch"
FIELD_DIRECTION = "Direction (sketch normal when empty)"
ADD_ROW = "Add Row"
REMOVE_ROW = "Remove Row"
ROW_LABEL = "Row {k}"
ROW_HEIGHT = "height {height}"
CHOOSE_CURVE_SKETCH = "Choose a sketch with one circle"
NEEDS_SKETCH = "Choose a sketch."
ADD_SKETCH_OR_CURVE = "Add a sketch or curve"
NEEDS_SECOND_SKETCH = "Choose the second sketch."
NEEDS_FACES = "Pick faces in the view to project onto."
NEEDS_ITEMS = "Pick sketches, curves or edges to join."
PICK_FACES_ONLY = "Pick faces for the projection."
PICK_EDGES_ONLY = "Pick edges, or choose sketches and curves in the list."
CURVE_TIPS = {
    "helix_sketch": "Sketch: a sketch with one circle. Its centre, plane and diameter "
    "place the curve.",
    "definition": "Defined by: which two sizes set the helix, or a flat spiral.",
    "pitch_type": "Pitch: constant, or a table of rows where pitch and diameter change.",
    "pitch": "Pitch: the rise per turn (the gap between turns for a spiral).",
    "turns": "Turns: how many times the curve goes round.",
    "height": "Height: the total rise of the helix.",
    "reverse": "Reverse: grow the helix the other way, or wind a spiral inward.",
    "clockwise": "Clockwise: wind clockwise seen from the side the helix grows toward.",
    "start_angle": "Start angle: where the curve starts, from the sketch X direction.",
    "taper_angle": "Taper angle: widen or narrow the helix as it rises (constant pitch only).",
    "taper_outward": "Taper outward: the helix widens as it rises; untick to narrow it.",
    "closed_ends": "Closed ends: a spring's end coils. The pitch is the End Pitch (about the "
    "wire's diameter) at each end and grows to the pitch over the first and last turn.",
    "end_pitch": "End pitch: the pitch where the helix starts and ends, about the wire's "
    "diameter so the end coil sits on the next.",
    "rows": "Variable pitch rows: the turn where each row applies, its pitch and diameter.",
    "projection_mode": "Projection: a sketch onto faces, or where two sketches meet.",
    "projection_sketch": "Sketch: the curves to project.",
    "projection_faces": "Faces: click the faces to project onto in the view.",
    "projection_direction": "Direction: a plane or axis from the list, or a flat face or "
    "straight edge clicked in the view after ticking the box. Unticked uses the sketch normal.",
    "both": "Both directions: project to both sides of the sketch.",
    "composite_items": "Items: sketches and curves from the list, and edges clicked in the "
    "view. They must join end to end.",
}

# Tooltips of the commands (shown in the command tabs and menus).
strings.TOOLTIP_TEXT.update(
    {
        "feature.import_step": "Adds a body read from a STEP file, healed and with its colours.",
        "feature.helix": "Makes a helix or flat spiral from a sketch circle.",
        "feature.projected_curve": "Projects a sketch onto faces, or finds where two "
        "sketches meet.",
        "feature.composite_curve": "Joins sketch curves, curves and edges into one curve.",
        "feature.point_curve": "A smooth curve through typed, loaded or picked points.",
        "feature.sketch3d": "A path in space from sketches on several planes and 3D lines.",
    }
)

# Pipe, array along curve, contour curves, curvature graph (P3.7) --------------------------

GROUP_PATH = "Path"
GROUP_PIPE = "Pipe"
GROUP_ARRAY_ITEMS = "Items to Copy"
GROUP_ARRAY = "Instances"
GROUP_CONTOUR = "Sections"
ARRAY_MODES = {"count": "Spread Over Curve", "spacing": "Set Spacing"}
FIELD_HOLLOW = "Hollow"
FIELD_CAP_ENDS = "Cap Ends"
FIELD_MERGE = "Merge result"
FIELD_ORIENT = "Orient to Curve"
FIELD_SKIP = "Instances to skip"
FIELD_PATH_EDGES = "Path edges (click in the view)"
FIELD_BODIES = "Bodies (click a face of each)"
FIELD_FEATURES = "Features"
FIELD_DIRECTION_PICK = "Plane, axis, flat face or edge"
NEEDS_PATH = "Choose a sketch or curve for the path, or pick edges."
CHOOSE_PATH = "Choose a sketch or curve"
ADD_FEATURE = "Add a feature to copy"
NEEDS_COPY_ITEMS = "Choose features, or click a face of each body to copy."
NEEDS_DIRECTION = "Choose a plane or axis, or click a flat face or straight edge."
PICK_PATH_EDGES = "Pick edges for the path."
CURVATURE_TITLE = "Curvature Graph"
CURVATURE_SCALE = "Scale"
CURVATURE_DENSITY = "Density"
CURVATURE_NOTHING = "Select edges, or add a curve, to show its curvature graph."
CURVATURE_SHOWN = "Curvature graph shown for {count} {items}."
CURVATURE_FAILED = (
    "The curvature graph could not be worked out for these curves. "
    "Pick other edges, or rebuild the part."
)
CURVE_TIPS.update(
    {  # TR373 (D979)
        "start_offset": "How far along the curve the copies start. The seed stays where it is.",
        "end_offset": "How far before the end of the curve the copies stop.",
    }
)
CURVE_TIPS.update(
    {
        "pipe_path": "Path: a sketch or curve whose pieces join end to end.",
        "path_edges": "Path edges: click edges in the view that join end to end.",
        "outer_diameter": "Outer diameter of the pipe.",
        "inner_diameter": "Inner diameter: leaves a hollow tube.",
        "hollow": "Hollow: give the pipe an inner diameter.",
        "cap_ends": "Cap ends: close both ends of a hollow pipe with a wall as thick as "
        "the pipe wall.",
        "merge": "Merge result: join the result to the bodies it touches.",
        "array_curve": "Curve: the sketch or curve the copies follow.",
        "array_features": "Features: their own solid is copied and added or cut like them.",
        "array_bodies": "Bodies: click any face of each body to copy.",
        "array_mode": "Spread over the curve, or a set spacing between copies.",
        "count": "Instances: how many, the original included.",
        "spacing": "Spacing: the distance along the curve between copies.",
        "orient": "Orient to curve: each copy turns with the curve. Untick to only move them.",
        "skip": "Instances to skip: their numbers, separated by commas. The original is 1.",
        "contour_direction": "Direction: sections are square to it, counted from the plane, "
        "axis, face or edge.",
        "contour_spacing": "Spacing: the distance between section planes.",
        "curvature_scale": "Scale: how long the teeth are for a given curvature.",
        "curvature_density": "Density: how many teeth on each edge.",
    }
)
strings.TOOLTIP_TEXT.update(
    {
        "feature.pipe": "Makes a round solid or hollow tube along a curve or edges.",
        "feature.curve_array": "Copies features or bodies along a curve.",
        "feature.contour": "Makes section curves of the part at a set spacing.",
        "evaluate.curvature_graph": "Shows curvature combs on the selected edges and curves.",
        "evaluate.curvature_colors": "Colours faces by curvature, with a scale and the value "
        "under the cursor.",
    }
)

# Mesh import and split for printing (P3.9) ------------------------------------------------

GROUP_IMPORTED = "Imported File"
GROUP_SPLIT = "Cuts"
GROUP_CONNECTORS = "Connectors"
GROUP_PRINT = "Import and Print"
FIELD_CONVERT = "Convert to Solid"
FIELD_MERGE_BODY = "Merge with the part"
FIELD_SUBTRACT = "Subtract from the part"
SECTION_MESH = "{name}: cut area {area}, outline {length}."
SECTION_MESH_OPEN = "{name}: outline {length}. The mesh has holes, so the cut has no area."
FIELD_BUILD = "Build volume (X, Y, Z)"
FIELD_PLANES = "Planes and flat faces to cut at"
FILE_LABEL = "File: {name}"
TRIANGLES_LABEL = "{count:,} triangles"
SPLIT_MODES = {
    "auto": "Fit Build Volume",
    "planes": "At Planes",
    "sketch": "Along Sketch",  # TR181 (D2002)
}
FIELD_SPLIT_PATH = "Path sketch"
SPLIT_NEEDS_PATH = "Pick a sketch to cut along."
CONNECTOR_TYPES = {
    "none": "None",
    "pins": "Alignment Pins",
    "dovetail": "Dovetail Keys",
    "magnets": "Magnet Pockets",  # TR181 (D1211)
    "screws": "Screws and Nuts",
}
NEEDS_PLANES = "Choose planes, or click flat faces to cut at."
GROUP_SPLIT_BODIES = "Bodies to Cut"
SPLIT_NEEDS_BODIES = "Click a face of each body to cut, or untick Bodies to Cut to cut every body."
SPLIT_FACES_ONLY = "Click faces: flat faces to cut at, or a face of each body to cut."
CURVE_TIPS.update(
    {
        "convert": "Convert to solid: turn the mesh into a solid with flat faces, so "
        "features can use it. Large meshes take a while.",
        "merge_body": "Merge with the part: join the imported solid to the part's body.",
        "subtract": "Subtract from the part: cut the converted mesh out of the part's body, "
        "using the mesh as a cutting tool.",
        "split_mode": "Fit build volume cuts evenly so every piece fits the printer; "
        "At planes cuts at the planes and faces you pick; Along sketch cuts along the "
        "curves of a sketch, for a stepped or shaped seam.",
        "split_path": "Path sketch: its curves are pushed through the part along the "
        "sketch's normal. Connectors go on the flat faces of the cut.",
        "key_draft": "Key draft: the key and its pocket narrow by this angle along the "
        "slide, so the key wedges tight. Zero for a straight key.",
        "build": "Build volume: the printer's largest part in X, Y and Z.",
        "planes": "Planes: pick planes in the list, or click flat faces in the view.",
        "split_bodies": "Bodies to cut: tick, then click a face of each body to cut. "
        "Unticked, every body the cuts cross is cut.",
        "connector": "Connectors: pins or dovetail keys that line the pieces up. Each is "
        "printed as its own body.",
        "pin_diameter": "Pin diameter.",
        "pin_length": "Pin length: half of it goes into each piece.",
        "key_width": "Key width at the seam.",
        "key_depth": "Key depth into each piece.",
        "clearance": "Clearance: extra room all round each pin or key so it fits.",
        "magnet_diameter": "Magnet diameter.",
        "magnet_depth": "Magnet depth: each piece gets a pocket this deep.",
        "screw_diameter": "Screw diameter: the hole goes right through the part.",
        "nut_size": "Nut size across the flats, for the hexagon pocket where the hole leaves.",
        "nut_height": "Nut height: the depth of the nut pocket.",
        "glue_gap": "Glue gap: each piece on the far side of a cut is trimmed back this "
        "much, so the joint has room for glue. Zero for none.",
    }
)
strings.TOOLTIP_TEXT.update(
    {
        "feature.import_mesh": "Adds an STL, 3MF or OBJ mesh as a reference body.",
        "feature.split_for_print": "Cuts the part into pieces that fit the printer, with "
        "pins or keys.",
    }
)

# Replace From File (TR11) ---------------------------------------------------------

REPLACE = "Replace From File..."
REPLACE_TITLE = "Replace {name} From File"

#: Pick Bodies for a STEP or IGES import (TR302 item 2, D1203).
PICK_BODIES = "Pick Bodies..."
PICK_BODIES_TITLE = "Pick Bodies: {name}"
PICK_BODIES_PROMPT = "Tick the bodies that come in. The ticked ones are shown in the view."
PICK_BODY_ROW = "Body {index}: {volume} mm\u00b3, {size} mm"
PICK_BODIES_READING = "Reading the bodies of {name}..."
PICK_BODIES_ONE = "{name} has one body, so there is nothing to pick."
PICK_BODIES_FAILED = (
    "{name}: the file could not be read: {reason}. Use Replace From File to pick another file."
)

#: Slicer 3MF parts (TR386, D1205).
FIELD_PARTS = "One body per part"
TIP_PARTS = "Make each part of a slicer 3MF its own body, with the part's name."
FIELD_KEEP_ROLES = "Keep slicer roles"
TIP_KEEP_ROLES = (
    "Also bring in modifier, negative and support parts, with their print roles. "
    "Left off, they are left out."
)

#: Mesh repair and reduce (TR186, D1212).
FIELD_REPAIR = "Repair"
TIP_REPAIR = (
    "Fill holes, remove repeated triangles, triangles on edges shared by more than two, "
    "and tiny loose pieces, before showing or converting the mesh."
)
REDUCE_MODES = {"off": "Keep every triangle", "percent": "Keep percent", "target": "Keep count"}
TIP_REDUCE = "Reduce: lower the triangle count, by percent of the triangles or to a count."
FIELD_KEEP_BOUNDARY = "Keep open edges"
TIP_KEEP_BOUNDARY = "Keep the vertices on open edges where they are, so rims stay true."
TIP_REDUCE_LIMIT = "Largest move: how far a vertex may move, or zero for no limit."
