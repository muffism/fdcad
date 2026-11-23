"""User interface text for the Phase 3 tools (DECISIONS D236).

Kept beside ``strings.py`` instead of inside it while several sessions add
tools at the same time; it moves into ``strings.py`` when Phase 3 is merged.
Commands are in title case, messages in sentence case (CLAUDE.md section 8).
"""

from __future__ import annotations

# Command tab groups ------------------------------------------------------------------

GROUP_DIRECT = "Direct Editing"
GROUP_PATTERN = "Pattern"
GROUP_BODIES = "Bodies"

TOOLTIP_TEXT = {
    "feature.move_face": (
        "Moves, offsets or turns faces. The faces around them stretch to stay joined."
    ),
    "feature.offset_face": "Moves faces along their own normals by a distance.",
    "feature.delete_face": (
        "Removes faces and heals the body, for example to remove a fillet or hole."
    ),
    "feature.merge_faces": "Makes one face of faces on one surface, removing the edges between.",
    "feature.linear_pattern": "Copies features, faces or bodies along one or two directions.",
    "feature.circular_pattern": "Copies features, faces or bodies around an axis.",
    "feature.pattern_chain": "Copies features, faces or bodies through several pattern steps "
    "in order: mirror, linear, circular and scale.",
    "feature.sketch_pattern": "Copies features, faces or bodies to the points of a sketch.",
    "feature.point_pattern": "Copies features, faces or bodies to vertices, round edges and "
    "holes of the part.",
    "feature.table_pattern": "Copies features, faces or bodies to X and Y positions from a table.",
    "feature.fill_pattern": "Fills a flat face with copies of a feature or a cut shape.",
    "feature.mirror": "Copies features, faces or bodies to the other side of a plane.",
    "feature.combine": "Joins bodies, subtracts bodies, or keeps only where they overlap.",
    "feature.intersect": "Makes bodies from the regions where bodies and planes overlap.",
    "feature.split": "Cuts bodies into pieces with planes, faces or sketches.",
    "feature.move_copy_body": "Moves, turns or copies whole bodies.",
    "feature.transform_handles": (
        "Shows move arrows and turn rings on the selected body. Drag them to move it."
    ),
    "feature.delete_body": "Deletes bodies, or keeps only the picked ones.",
    "feature.scale": "Scales bodies, the same in every direction or per axis.",
    "feature.mould_cavity": "Cuts the shape of a part, scaled for shrinkage, out of a block.",
    "feature.offset_body": "Grows or shrinks every face of a body by one distance.",
    "feature.shaft_shape": "Hex, D flat, double D or keyway on a shaft or in a bore.",
    "feature.inlay": "Cuts a sketch into a face and keeps the cut piece as a second colour body.",
    "feature.ring_groove": "Cuts a retaining ring or E clip groove on a shaft or in a bore.",
    "feature.oring_groove": "Cuts an O ring groove on a shaft, in a bore, or along a sketch "
    "on a face.",
    "feature.cable_tie": "Cuts a loop under a face at sketch points to tie cables down.",
    "feature.half_lap": "Notches two crossing plates so they slot together.",
    "feature.indent": "Reshapes one body round another: a wall that follows it, or a "
    "pocket with a clearance.",
    "feature.twist_lock": "Lugs on a lid's plug and L shaped slots round it: push in "
    "and twist to lock.",
    "feature.finger_joint": "Cuts interlocking fingers where two plates meet at a corner.",
    "feature.crush_ribs": "Adds small wedge ribs in a hole or on a pin for a press fit.",
    "feature.knurl": "Cuts a straight or diamond knurl into a cylinder face for grip.",
    "feature.joint_helper": "Cuts a groove, rabbet, mortise and tenon or dowel holes "
    "where two bodies touch, with a clearance.",
    "feature.landing_pad": "Makes a flat pad raised from or pressed into a sloped or "
    "curved wall, for screw bosses on curved housings.",
    "feature.lightening_pockets": "Pockets a plate face as triangles between ribs, keeping "
    "a border, to save weight.",
    "feature.edge_profile": "Cuts a router shape, such as a round over, cove, rabbet or "
    "ogee, round a face or along edges.",
    "feature.transition_spiral": "Draws a transition spiral from the end of a sketch line, "
    "for track and road pieces that turn in smoothly.",
    "feature.insert_part": "Brings the bodies of another FDCAD part into this part, linked "
    "to its file so they follow its changes.",
    "feature.face_relation": "Keeps a relation between faces, such as coplanar or concentric, "
    "that later Move Face edits hold.",
    "feature.linked_copy": "Copies bodies with their own position; the copy follows every "
    "later change of the original until you break the link.",
    "feature.roof": "Adds a roof of one slope over a closed sketch outline, with hips, "
    "valleys and ridges.",
    "feature.stone_setting": "Cuts a seat for a round stone in a flat face and adds the "
    "prongs that hold it, for ring and pendant masters.",
    "feature.sprue_tree": "Joins casting sprues from a pouring cup to picked points, or a "
    "kit frame runner round them.",
    "feature.face_seats": "Sets copies of a seed body over a curved face, each turned to "
    "the face, for studs, rivets and dimples.",
    "feature.hinge": "Adds a knuckle hinge where two bodies meet, with a pin hole or as "
    "a print in place hinge.",
    "feature.mark": "Puts the text and lines of a sketch on a face as marks for etching, "
    "with no depth or a small one.",
    "feature.lattice_fill": "Fills bodies with a gyroid, diamond or honeycomb lattice, "
    "with a solid skin if you like.",
    "feature.interlock": "Adds a checkerboard of teeth where two bodies of different "
    "materials meet, so they lock together.",
    "feature.base_pad": "Adds a thin pad body under the bed face with an air gap, to peel "
    "off after printing.",
    "feature.polygon_holes": "Makes round holes into polygons whose flats sit at the "
    "hole's size, so they print true.",
    "feature.drain_holes": "Cuts a hole from the lowest point of each closed hollow out "
    "through the wall, so resin drains.",
    "feature.corner_ears": "Adds thin discs at the sharp corners of the bed face, so the "
    "corners do not lift while printing.",
    "feature.living_hinge": "Cuts staggered slits through a plate so it bends.",
    "feature.hose_fitting": "Adds a hose barb or a luer fitting with a bore on a face.",
}

#: Feature type to the command (and icon) that makes it.
TYPE_COMMANDS = {
    "move_face": "feature.move_face",
    "delete_face": "feature.delete_face",
    "merge_faces": "feature.merge_faces",
    "linear_pattern": "feature.linear_pattern",
    "circular_pattern": "feature.circular_pattern",
    "pattern_chain": "feature.pattern_chain",  # TR141 (D1901)
    "sketch_pattern": "feature.sketch_pattern",
    "point_pattern": "feature.point_pattern",
    "table_pattern": "feature.table_pattern",
    "fill_pattern": "feature.fill_pattern",
    "bounding_box": "feature.bounding_box",
    "sensor": "feature.sensor",
    "primitive": "feature.primitive",
    "mirror": "feature.mirror",
    "combine": "feature.combine",
    "intersect": "feature.intersect",
    "split": "feature.split",
    "move_copy_body": "feature.move_copy_body",
    "delete_body": "feature.delete_body",
    "scale": "feature.scale",
    "mould_cavity": "feature.mould_cavity",
    "offset_body": "feature.offset_body",
    "shaft_shape": "feature.shaft_shape",
    "inlay": "feature.inlay",
    "ring_groove": "feature.ring_groove",
    "oring_groove": "feature.oring_groove",
    "cable_tie": "feature.cable_tie",
    "half_lap": "feature.half_lap",
    "twist_lock": "feature.twist_lock",
    "indent": "feature.indent",
    "finger_joint": "feature.finger_joint",
    "crush_ribs": "feature.crush_ribs",
    "corner_ears": "feature.corner_ears",
    "drain_holes": "feature.drain_holes",
    "polygon_holes": "feature.polygon_holes",
    "base_pad": "feature.base_pad",
    "interlock": "feature.interlock",
    "lattice_fill": "feature.lattice_fill",
    "mark": "feature.mark",
    "hinge": "feature.hinge",
    "face_seats": "feature.face_seats",
    "stone_setting": "feature.stone_setting",
    "roof": "feature.roof",
    "linked_copy": "feature.linked_copy",
    "face_relation": "feature.face_relation",
    "insert_part": "feature.insert_part",
    "sprue_tree": "feature.sprue_tree",
    "transition_spiral": "feature.transition_spiral",
    "edge_profile": "feature.edge_profile",
    "lightening_pockets": "feature.lightening_pockets",
    "landing_pad": "feature.landing_pad",
    "joint_helper": "feature.joint_helper",
    "knurl": "feature.knurl",
    "living_hinge": "feature.living_hinge",
    "hose_fitting": "feature.hose_fitting",
    "section_cut": "feature.section_cut",  # TR151 item 2 (D2205)
}

#: Default names of new features (D110 item 4: a word and a number).
TYPE_NAMES = {
    "move_face": "Move Face",
    "delete_face": "Delete Face",
    "merge_faces": "Merge Faces",
    "linear_pattern": "Linear Pattern",
    "circular_pattern": "Circular Pattern",
    "pattern_chain": "Pattern Chain",
    "follow_pattern": "Follow Pattern",  # TR399 (D1904)
    "sketch_pattern": "Sketch Pattern",
    "point_pattern": "Point Pattern",
    "table_pattern": "Table Pattern",
    "offset_body": "Offset Body",
    "shaft_shape": "Shaft Shape",
    "inlay": "Inlay",
    "ring_groove": "Ring Groove",
    "oring_groove": "O Ring Groove",
    "cable_tie": "Cable Tie",
    "half_lap": "Half Lap",
    "twist_lock": "Twist Lock",
    "indent": "Indent",
    "finger_joint": "Finger Joint",
    "crush_ribs": "Crush Ribs",
    "corner_ears": "Corner Ears",
    "drain_holes": "Drain Holes",
    "polygon_holes": "Polygon Holes",
    "base_pad": "Base Pad",
    "interlock": "Material Interlock",
    "lattice_fill": "Lattice Fill",
    "mark": "Mark",
    "hinge": "Hinge",
    "face_seats": "Face Seats",
    "stone_setting": "Stone Setting",  # TR408 (D2410)
    "roof": "Roof",  # TR258 (D2414)
    "linked_copy": "Linked Copy",  # TR154 (D2417)
    "face_relation": "Face Relation",  # TR266 (D2418)
    "insert_part": "Insert Part",  # TR71 (D2420)
    "sprue_tree": "Sprue Tree",  # TR408 (D2411)
    "transition_spiral": "Transition Spiral",
    "edge_profile": "Edge Profile",
    "lightening_pockets": "Lightening Pockets",
    "landing_pad": "Landing Pad",
    "joint_helper": "Joint",
    "knurl": "Knurl",
    "living_hinge": "Living Hinge",
    "hose_fitting": "Hose Fitting",
    "section_cut": "Section Cut",  # TR151 item 2 (D2205)
    "derived_sketch": "Derived Sketch",
    "fill_pattern": "Fill Pattern",
    "bounding_box": "Bounding Box",
    "sensor": "Sensor",
    "primitive": "Primitive Solid",
    "measurement": "Measurement",
    "mirror": "Mirror",
    "combine": "Combine",
    "intersect": "Intersect",
    "split": "Split",
    "move_copy_body": "Move Body",
    "delete_body": "Delete Body",
    "scale": "Scale",
    "mould_cavity": "Mould Cavity",
}

# Property panel groups -----------------------------------------------------------------

GROUP_MOVE = "Move"
GROUP_FACES = "Faces"
GROUP_RULES = "Rules"  # TR263
GROUP_FILL = "Fill"  # TR57
GROUP_BOUNDING = "Bounding Box"  # TR69
GROUP_SENSOR = "Sensor"  # TR86
GROUP_TWIST_LOCK = "Twist Lock"  # TR357
GROUP_INDENT = "Indent"  # TR68
GROUP_PRIMITIVE = "Shape and Size"  # TR127
GROUP_FOLLOW = "Neighbouring Faces"  # TR264
# What a ticked rule does, from the preview (TR263 item 2, D798)
RULE_ADDS = "{label}: adds {count}"
RULE_HOLDS = "{label}: holds {count}"
RULE_IDLE = "{label}: no effect"
FOLLOW_PREVIOUS = "Previous Solution"
FOLLOW_NEXT = "Next Solution"
FOLLOW_STEP_TIP = "Steps to the next way the faces around can rejoin the moved faces."
FILL_COUNT = "Copies"
FILL_COUNT_PENDING = "Not counted yet"
FILL_COUNT_TIP = 'How many copies fit on the face. Formulas can use it as "count@{name}".'
GROUP_OPTIONS = "Options"
GROUP_DIRECTION1 = "Direction 1"
GROUP_DIRECTION2 = "Direction 2"
GROUP_SEED = "Items to Copy"
GROUP_TABLE = "Table"
GROUP_OFFSET_BODY = "Offset"
GROUP_SHAFT_SHAPE = "Shape"
GROUP_INLAY = "Inlay"
GROUP_RING_GROOVE = "Ring Groove"
GROUP_ORING_GROOVE = "O Ring Groove"
GROUP_CABLE_TIE = "Cable Tie"
GROUP_HALF_LAP = "Half Lap"
GROUP_FINGER_JOINT = "Finger Joint"
GROUP_CRUSH_RIBS = "Crush Ribs"
GROUP_CORNER_EARS = "Corner Ears"
GROUP_DRAIN_HOLES = "Drain Holes"
GROUP_POLYGON_HOLES = "Polygon Holes"
GROUP_BASE_PAD = "Base Pad"
GROUP_INTERLOCK = "Material Interlock"
GROUP_LATTICE_FILL = "Lattice Fill"  # TR390 (D2004)
GROUP_MARK = "Mark"  # TR330 (D2006)
GROUP_HINGE = "Hinge"  # TR404 (D2008)
GROUP_FACE_SEATS = "Face Seats"  # TR405 (D2009)
GROUP_STONE_SETTING = "Stone Setting"  # TR408 item 2 (D2410)
GROUP_ROOF = "Roof"  # TR258 (D2414)
GROUP_LINKED_COPY = "Linked Body Copy"  # TR154 (D2417)
GROUP_FACE_RELATION = "Face Relation"  # TR266 (D2418)
GROUP_INSERT_PART = "Insert Part"  # TR71 (D2420)
INSERT_PART_FILTER = "FDCAD parts (*.fdprt *.fdef)"
GROUP_SPRUE_TREE = "Sprue Tree"  # TR408 item 3 (D2411)
GROUP_TRANSITION_SPIRAL = "Transition Spiral"  # TR408 (D2010)
GROUP_EDGE_PROFILE = "Edge Profile"  # TR243 (D2011)
GROUP_LIGHTENING = "Lightening Pockets"  # TR245 (D2012)
GROUP_LANDING_PAD = "Landing Pad"  # TR325 (D2013)
GROUP_JOINT = "Joint"  # TR401 (D2014)
GROUP_KNURL = "Knurl"  # TR163 (D2015)
GROUP_LIVING_HINGE = "Living Hinge"
GROUP_HOSE_FITTING = "Hose Fitting"
TABLE_NOT_NUMBERS = "Every row needs two numbers. Fix the table."
GROUP_SKIP = "Instances to Skip"
GROUP_MIRROR = "Mirror Plane"
GROUP_BODIES_PANEL = "Bodies"
GROUP_TOOLS = "Trim Tools"
GROUP_REGIONS = "Regions"
GROUP_RESULT = "Resulting Bodies"
GROUP_SCALE = "Scale"
GROUP_MOULD_CAVITY = "Mould Cavity"  # TR85 (D2111)

GROUP_CHAIN = "Steps"  # TR141 (D1901)
GROUP_CHAIN_LINEAR = "Linear Step"
GROUP_CHAIN_CIRCULAR = "Circular Step"
GROUP_CHAIN_MIRROR = "Mirror Step"
GROUP_CHAIN_SCALE = "Scale Step"

# Field labels --------------------------------------------------------------------------

LABELS = {
    "layout": "Layout",  # TR57
    "spacing": "Spacing",
    "row_spacing": "Row spacing",
    "stagger_angle": "Stagger angle",
    "ring_shape": "Ring shape",
    "margin": "Margin",
    "fit": "Fit",
    "shape": "Cut shape",
    "size": "Size",
    "sides": "Sides",
    "frequency": "Frequency",
    "shape_angle": "Shape angle",
    "diameter": "Diameter",  # TR265
    "cone_angle": "Cone angle",  # D799
    "symmetric": "Symmetric",  # D800
    "lock_size": "Lock this size",
    "keep_end": "End that stays",
    "offset_by": "Move by",
    "size_from": "Measure from",
    "set_size": "Size",
    "rule_coplanar": "Keep coplanar faces",  # TR263
    "box_shape": "Shape",  # TR69
    "kind": "Shape",  # TR127
    "length": "Length",
    "width": "Width",
    "height": "Height",
    "top": "Height at the end",
    "diameter2": "Top diameter",
    "inner": "Inside diameter",
    "ring": "Ring diameter",
    "tube": "Tube diameter",
    "centred": "Centred on the frame",
    "symmetric1": "Symmetric",  # TR140
    "orient": "Directions",
    "frame": "Frame",
    "rows": "Positions",
    "make_solid": "Make solid",
    "source": "Watch",  # TR86
    "indent_mode": "Mode",  # TR68
    "indent_thickness": "Thickness",
    "indent_clearance": "Clearance",
    "lug_count": "Lugs",  # TR357
    "lug_width": "Lug width",
    "lug_height": "Lug height",
    "lug_depth": "Lug depth",
    "lock_depth": "Depth from the open end",
    "twist": "Twist",
    "lock_clearance": "Clearance",
    "other_end": "Other end is open",
    "clockwise": "Clockwise",
    "value": "Formula",
    "low": "Low limit",
    "high": "High limit",
    "rule_symmetric": "Keep symmetry",  # D798
    "symmetry_plane": "Symmetry plane",
    "rule_parallel": "Keep parallel and square faces",
    "rule_main_planes": "Keep faces on main planes",
    "rule_exclude_coplanar": "Coplanar leaves still",
    "rule_exclude_concentric": "Concentric leaves still",
    "rule_exclude_tangent": "Tangent leaves still",
    "rule_exclude_equal_radius": "Equal radii leaves still",
    "rule_exclude_symmetric": "Symmetry leaves still",
    "rule_exclude_parallel": "Parallel leaves free",
    "rule_exclude_main_planes": "Main planes leaves free",
    "follow": "Neighbours",  # TR264
    "keep_solution": "Keep this solution",
    "rounds": "Rounds on its edges",
    "rule_concentric": "Keep concentric faces",
    "rule_tangent": "Keep tangent faces",
    "rule_equal_radius": "Keep equal radii",
    "suspend_rules": "Suspend all rules",
    "rule_exclude": "Faces the rules leave still",
    "tolerance": "Tolerance",  # TR261
    "angle_tolerance": "Angle tolerance",
    "print_fit": "Printing fit",
    "fit_tolerance": "Fit tolerance",
    "mode": "Type",
    "faces": "Faces",
    "distance": "Distance",
    "reverse": "Reverse",
    "copy": "Copy",
    "translate_by": "Move by",
    "dx": "Delta X",
    "dy": "Delta Y",
    "dz": "Delta Z",
    "direction": "Direction",
    "from": "From",
    "to": "To",
    "from_frame": "Body frame",  # TR268 (D1815)
    "rel_from": "Body items",  # TR268 item 1 (D2415)
    "pivot": "Handle at",  # TR268 item 3 (D2416)
    "pivot_point": "Handle point",
    "handle_axes": "Handle axes",
    "handle_plane": "Axes plane",
    "rel_to": "Target items",
    "relations": "Relations",
    "to_frame": "Target frame",
    "body": "Body",
    "rotate_by": "Turn about",
    "axis": "Axis",
    "angle": "Angle",
    "ox": "Origin X",
    "oy": "Origin Y",
    "oz": "Origin Z",
    "rx": "Angle about X",
    "ry": "Angle about Y",
    "rz": "Angle about Z",
    "option": "Option",
    "tangent": "Tangent fill",
    "features": "Features",
    "bodies": "Bodies",
    "inward": "Shrink",
    "keep_tools": "Keep tool bodies",
    "part": "Part",  # TR85 (D2111)
    "keep_part": "Keep part",
    "coord_system": "Coordinate system",
    "keep_largest": "Keep largest piece only",
    "from_end": "From end",
    "depth": "Depth",
    "shaft_form": "Shape",
    "key_standard": "Key standard",
    "ring_type": "Ring",
    "cross_section": "Cross section",
    "targets": "Points",
    "hole_faces": "Faces with holes",
    "use": "Use",
    "tie_width": "Tie width",
    "tie_thickness": "Tie thickness",
    "span": "Span",
    "cover": "Cover",
    "depth_percent": "Depth (%)",
    "kerf": "Kerf",
    "finger_count": "Fingers",
    "rib_count": "Ribs",
    "slit_length": "Slit length",
    "slit_width": "Slit width",
    "bridge": "Bridge",
    "rib_width": "Rib width",
    "rib_height": "Rib height",
    "rib_length": "Rib length",
    "rib_tip": "Tip width",
    "ear_diameter": "Ear diameter",  # TR189 (D1005)
    "ear_thickness": "Ear thickness",
    "max_angle": "Corners up to",
    "hole_diameter": "Hole diameter",  # TR189 (D1006)
    "toward": "Drain toward",
    "pad_thickness": "Pad thickness",  # TR414 (D1009)
    "tooth_size": "Tooth size",  # TR414 (D1216)
    "lattice": "Lattice",  # TR390 (D2004)
    "knuckles": "Knuckles",  # TR404 (D2008)
    "form": "Type",  # D2841
    "on_face": "Face to cover",  # TR405 (D2009)
    "spiral_length": "Spiral length",  # TR408 (D2010)
    "loop_face": "Face",  # TR243 (D2011)
    "plate_face": "Plate face",  # TR245 (D2012)
    "wall_face": "Wall",  # TR325 (D2013)
    "joint": "Joint",  # TR401 (D2014)
    "round_face": "Round face",  # TR163 (D2015)
    "knurl_pattern": "Pattern",
    "knurl_pitch": "Pitch",
    "knurl_depth": "Depth",
    "joint_clearance": "Clearance",
    "shoulder": "Shoulder",
    "dowel_diameter": "Dowel diameter",
    "pad_mode": "Pad",
    "cup_wall": "Cup wall",
    "border": "Border",
    "web": "Web",
    "corner_radius": "Corner radius",
    "pocket_depth": "Pocket depth",
    "edges": "Edges",
    "router_profile": "Profile",
    "profile_size": "Size",
    "profile_depth": "Depth",
    "end_radius": "End radius",
    "hand": "Turns",
    "seed": "Seed body",
    "count_u": "Copies across",
    "count_v": "Copies along",
    "sink": "Sink",
    "seat_face": "Seat face",  # TR408 (D2410, D2411)
    "slope": "Slope",  # TR258 (D2414)
    "place": "Place by",  # TR154 (D2417)
    "relation": "Relation",  # TR266 (D2418)
    "part_file": "Part file",  # TR71 (D2420)
    "link": "Link to the file",
    "keep_bodies": "Bodies to bring in",
    "with_sketches": "Bring in sketches",
    "with_planes": "Bring in planes",
    "max_height": "Max height",
    "seat_point": "Centre point",
    "stone_diameter": "Stone diameter",
    "girdle_depth": "Girdle depth",
    "pavilion_angle": "Pavilion angle",
    "prongs": "Prongs",
    "prong_diameter": "Prong diameter",
    "prong_height": "Prong height",
    "feed_points": "Feed points",
    "cup": "Cup point",
    "cup_diameter": "Cup diameter",
    "cup_height": "Cup depth",
    "sprue_diameter": "Sprue diameter",
    "gate_diameter": "Gate diameter",
    "knuckle_diameter": "Knuckle diameter",
    "pin_diameter": "Pin hole",
    "pin_cone_angle": "Cone angle",
    "detents": "Detent bumps",
    "cell": "Cell size",
    "wall": "Wall",
    "skin": "Skin",
    "tooth_depth": "Tooth depth",
    "pad_margin": "Margin",
    "air_gap": "Air gap",
    "base_face": "Face",
    "base_point": "Point",
    "fitting": "Fitting",
    "hose_diameter": "Hose inside diameter",
    "barb_diameter": "Barb diameter",
    "ring_count": "Barbs",
    "ring_length": "Barb length",
    "body_diameter": "Base diameter",
    "shank_height": "Base height",
    "bore_diameter": "Bore diameter",
    "bore_depth": "Bore depth into part",
    "position": "Position",
    "face": "Round face",
    "clearance": "Clearance",
    "corners": "Corners",
    "direction1": "Direction",
    "spacing1": "Spacing",
    "count1": "Instances",
    "reverse1": "Reverse",
    "fill1": "Fill",
    "up_to1": "Up to",
    "offset1": "Offset",
    "total1": "Total length",  # TR142 (D962)
    "min_bodies": "Number of bodies",  # TR371 (D999)
    "shear_angle": "Shear angle",  # TR371 (D1000)
    "shear_along": "Shear along",
    "shear_from": "Shear by height along",
    "hole_size": "Holes up to",  # TR388 (D990)
    "voids": "Fill voids",
    "reapply_fillets": "Reapply fillets",  # TR259 (D1420)
    "law1": "Spacing law",  # TR366 (D981)
    "ratio1": "Growth ratio",
    "jitter1": "Random move (%)",
    "seed1": "Random seed",
    "fractions1": "Fractions",  # TR366 (D1018)
    "fractions2": "Fractions",
    "angles1": "Copy angles (degrees)",  # TR366 (D1500)
    "check": "Check copies",  # TR399 (D1519)
    "gradient": "Size gradient",  # TR324 (D1518)
    "size_end": "End size",
    "gradient_from": "Gradient from",
    "increment1": "Increment",  # TR59 (D1513)
    "increment2": "Increment",
    "vary": "Vary values",
    "instance_values": "Copy values",  # TR59 (D1900)
    "surface_spacing": "Round face spacing",  # TR398 (D1903)
    "steps": "Step order",  # TR141 (D1901)
    "instances": "Instances",
    "turns": "Instances",
    "reverse_turn": "Reverse",
    "scales": "Instances",
    "centre": "Scale centre",
    "angles2": "Copy angles (degrees)",
    "seed_cell1": "Seed cell",  # TR270 (D1501)
    "seed_cell2": "Seed cell",
    "rotate": "Rotate pattern",
    "region": "Suppress region",  # TR398 (D1503)
    "region_mode": "Skip copies",
    "law2": "Spacing law",
    "ratio2": "Growth ratio",
    "jitter2": "Random move (%)",
    "seed2": "Random seed",
    "direction2": "Direction 2",
    "spacing2": "Spacing",
    "count2": "Instances",
    "reverse2": "Reverse",
    "fill2": "Fill",
    "up_to2": "Up to",
    "offset2": "Offset",
    "total2": "Total length",
    "seed_only2": "Pattern seed only",
    "angle1": "Angle",
    "angle2": "Angle",  # D2841
    "equal_spacing": "Equal spacing",
    "symmetric2": "Symmetric",
    "sketch": "Sketch",
    "point": "Reference point",
    "geometry": "Geometry pattern",
    "merge": "Merge result",
    "propagate_colours": "Propagate colours",
    "preview": "Preview",
    "plane": "Mirror plane",
    "plane2": "Second mirror plane",
    "seed_only": "Mirror seed only",
    "operation": "Operation",
    "main": "Main body",
    "planes": "Planes",
    "regions": "Regions",
    "exclude": "Keep",  # D2841: the list is ticked for what stays
    "cap": "Cap flat openings",
    "tools": "Trim tools",
    "keep": "Keep",  # D2841: short, so it stays in the column of the other labels
    "count": "Copies",
    "edge": "Edge",
    "uniform": "Uniform scaling",
    "factor": "Factor",
    "fx": "X factor",
    "fy": "Y factor",
    "fz": "Z factor",
    "about": "Scale about",
    "skip": "Instances to skip",
}

TIPS = {
    "reapply_fillets": (
        "Remove the rounds next to the picked faces first and make them again after, "
        "with the same radius."
    ),  # TR259 (D1420)
    "layout": "Layout: a grid, a staggered grid, or rings out from the start point.",
    "spacing": "Spacing: the distance between copies.",
    "row_spacing": "Row spacing: between grid rows, or between rings.",
    "stagger_angle": "Stagger angle: how far each row leans; 60 gives an even triangular layout.",
    "ring_shape": "Ring shape: circular, square or polygon rings.",
    "margin": "Margin: how far every copy stays from the face's edges. Copies that do not fit "
    "are left out. A negative margin lets copies run past the edge.",
    "fit": "Fit: keep a copy when its whole shape lies on the material, or only its centre.",
    "shape": "Cut shape: copy the picked seed, or cut a circle, square, diamond or polygon.",
    "size": "Size: how wide the cut shape is.",
    "sides": "Sides: the polygon's number of sides.",
    "frequency": "Frequency: how many times each of the 20 big triangles is split along "
    "a side. Higher is rounder, with more faces.",
    "shape_angle": "Shape angle: turns the cut shape.",
    "diameter": "Diameter: the new diameter of each picked cylinder or sphere.",
    "cone_angle": "Cone angle: the new angle between each picked cone and its axis (half the "
    "angle across the cone).",
    "keep_end": "End that stays: the cone keeps its large or its small end where it is.",
    "symmetric": "Symmetric: the face and the face measured from both move, half each, so "
    "the middle stays where it is.",
    "lock_size": "Lock this size: a later Move Face that moves one of the two faces moves the "
    "other with it, so the size holds.",
    "offset_by": "Move by a distance, or to a size measured from a picked item.",
    "size_from": "Measure from: a vertex, an edge (a round edge counts from its centre) or a "
    "face (a hole counts from its axis).",
    "set_size": "Size: the distance the face ends from the measured item, along its normal.",
    "rule_coplanar": "Faces on the same plane as a picked face move with it.",
    "box_shape": "Shape: a box, or a cylinder along the frame's Z.",
    "kind": "Shape: the solid to make from the sizes below, with no sketch.",
    "centred": "Centred on the frame: the solid's middle sits on the frame's origin. Off: it "
    "stands on the frame.",
    "symmetric1": "Symmetric: as many copies, as far apart, on the other side of the seed too.",
    "symmetric2": "Symmetric: as many copies, as far apart, on the other side of the seed too.",
    "seed_cell1": "Seed cell: which cell along this direction holds the original. Cells before it "
    "are copies the other way.",  # TR270 (D1501)
    "seed_cell2": "Seed cell: which cell along this direction holds the original. Cells before it "
    "are copies the other way.",
    "rotate": "Rotate pattern: turn the whole grid in its plane by this angle.",
    "region": "Suppress region: pick faces or closed sketches. Copies whose centre lands over "
    "them are skipped, or with Outside, those that land elsewhere.",
    "region_mode": "Skip copies inside the region, or outside it.",
    "increment1": "Increment: each gap is the one before plus this. Negative closes up.",
    "increment2": "Increment: each gap is the one before plus this. Negative closes up.",
    "check": "Full tests that every copy touches the part. Fast skips that test, which "
    "saves time on large patterns whose copies sit well on the material.",
    "gradient": "Size gradient: the shapes grow or shrink across the face.",
    "size_end": "End size: the size of the copy farthest from where the gradient starts.",
    "gradient_from": "Gradient from: a vertex or point where the shapes have the first size, or "
    "an edge they grow away from. Empty: the start point.",
    "vary": "Vary values: a value name of the copied feature and its step per copy, such as "
    "depth 2 (mm, or degrees for angles). Separate several with semicolons.",
    "surface_spacing": "Round face spacing: on a cylinder face, measure the spacing along "
    "the surface, or as seen from straight on at the start point. Flat faces ignore it.",
    "steps": "Step order: the steps in the order they run, such as linear, circular. Each "
    "step copies everything the steps before it made. Steps: mirror, linear, circular, scale.",
    "instances": "Instances: how many along the direction, the original included.",
    "turns": "Instances: how many round the axis, the original included.",
    "reverse_turn": "Reverse: turn the other way.",
    "scales": "Instances: how many sizes, the original included.",
    "factor": "Factor: each copy is this many times the size of the one before.",
    "centre": "Scale centre: the point copies grow from or shrink toward. Empty: the origin.",
    "instance_values": "Copy values: an instance number, a colon and the values that one copy "
    "uses, such as 3: depth 8 or 2.2: depth 4, draft_angle 2. Separate copies with semicolons.",
    "orient": "Directions: the part's X, Y and Z, a best fit around the part, or a "
    "picked plane or face.",
    "frame": "Frame: the plane, flat face or coordinate system whose axes are used.",
    "rows": "X and Y of each copy's reference point, from the frame's origin. "
    "Untick a row to leave it out.",
    "make_solid": "Make solid: add the box as a body of its own. Off: an outline only.",
    "indent_mode": "Mode: Indent adds a wall round the tool; Cut only makes a pocket for "
    "it.",  # TR68
    "indent_thickness": "Thickness: the wall round the tool.",
    "indent_clearance": "Clearance: the gap between the tool and the target.",
    "lug_count": "Lugs: how many, evenly round the plug.",  # TR357
    "lug_width": "Lug width: each lug's size round the plug.",
    "lug_height": "Lug height: each lug's size along the axis.",
    "lug_depth": "Lug depth: how far the lugs stand out of the plug.",
    "lock_depth": "Depth from the open end: from the end of the plug's round face to the "
    "middle of the lugs.",
    "twist": "Twist: how far the lid turns to lock.",
    "lock_clearance": "Clearance: the gap left round each lug in its slot.",
    "other_end": "Other end is open: the slots open at the other end of the round face.",
    "clockwise": "Clockwise: the lid turns clockwise to lock, seen from the open end.",
    "source": "Watch: the volume, surface area or mass of the bodies above the sensor, "
    "or a formula.",  # TR86
    "value": "Formula: a variable, dimension, equation or measured value, such as "
    '="length@Bounding Box 1".',
    "low": "Low limit: warn when the value is below this. Leave empty for none.",
    "high": "High limit: warn when the value is above this. Leave empty for none.",
    "rule_symmetric": "The mirror image of a picked face moves the mirrored way. Offset and "
    "Resize only.",
    "symmetry_plane": "The plane to mirror in. Empty: each main plane through the origin.",
    "rule_parallel": "Faces next to the moved faces that are parallel or square to them keep "
    "their direction: a way of following that would turn them is not used.",
    "rule_main_planes": "Faces next to the moved faces that face along X, Y or Z keep their "
    "direction.",
    **{
        f"rule_exclude_{r}": "Faces this one rule leaves alone; the other rules still apply."
        for r in (
            "coplanar",
            "concentric",
            "tangent",
            "equal_radius",
            "symmetric",
            "parallel",
            "main_planes",
        )
    },
    "follow": "Extend: the faces around keep their angle and grow or shrink to meet the moved "
    "faces. Tip: they tilt to meet them. Lift: the faces move unchanged and new side faces "
    "join them to where they were.",
    "keep_solution": "When the chosen way does not work after a change, show an error "
    "instead of using another way.",
    "rounds": "Follow: rounds on the moved faces' edges grow or shrink with the move. "
    "Remake: they are taken off before the move and made again after it, with the same size.",
    "rule_concentric": "Round faces on the same axis as a picked round face move with it.",
    "rule_tangent": "Faces that meet a picked face smoothly move with it, along the chain.",
    "rule_equal_radius": "Cylinders with the same radius as a picked cylinder move with it.",
    "suspend_rules": "Turns every rule off for this edit, keeping the ticks.",
    "rule_exclude": "Faces no rule may add: click faces in the view.",
    "tolerance": "Tolerance: faces closer than this count as touching, or as one surface. "
    "Raise it a little for imported parts; 0 uses the kernel's own.",
    "angle_tolerance": "Angle tolerance: how far the faces may turn from each other and "
    "still count as one surface.",
    "print_fit": "Printing fit: moves the faces into the part by the printer's fit tolerance, "
    "a whole tolerance for Clearance, half for Slip, none for Press.",
    "fit_tolerance": "Fit tolerance: the gap per side a printed part needs to slide, "
    "taken from the active printer profile.",
    "faces": "Faces: click faces in the view. Use the helper bar beside the last face to add "
    "related faces in one click. Delete removes the selected row.",
    "mode": "Offset moves each face along its own normal; Translate moves the faces as a group; "
    "Rotate turns them as a group.",
    "distance": "Distance: how far the faces move. Formulas and units work here.",
    "reverse": "Reverse: move the other way.",
    "copy": "Copy: keep the faces and add a moved copy that joins the body.",
    "direction": (
        "Direction: click a straight edge, flat face or plane, or pick a plane in the list."
    ),
    "to": "To: the vertex, face or plane to move up to.",
    "from_frame": (
        "Body frame: click the origin (a vertex or round edge), then a face or edge for Z, "
        "then an edge for X if you want it."
    ),
    "to_frame": "Target frame: the origin, Z and X the body frame lands on, picked the same way.",
    "pivot": "Handle at: the bodies' centre, or a picked point. Turns about the centre go "
    "about it, and picking a point moves only the handle, not the body.",
    "pivot_point": "Handle point: a vertex, sketch point or reference point for the handle.",
    "handle_axes": "Handle axes: the model's X, Y and Z, or a plane's own X, Y and normal. "
    "Delta X, Y, Z and the turns go along these.",
    "handle_plane": "Axes plane: a plane or flat face whose axes the handle uses.",
    "rel_from": "Body items: a flat face, round face or edge of the body for each relation, "
    "in order.",
    "rel_to": "Target items: the face, edge, plane or axis each body item relates to, in the "
    "same order.",
    "relations": "Relations: one per pair, such as coincident; distance 5; angle 90; "
    "parallel. All hold at once.",
    "from": "From: the face, plane or vertex the move starts at. Empty: the first picked face.",
    "body": "Body: click a face of the body to move up to.",
    "axis": "Axis: click a straight edge, round edge or cylinder.",
    "option": "Delete and Patch grows the faces around the gap until they meet. Delete and Fill "
    "closes the gap with one new smooth face.",
    "tangent": "Tangent fill: the new face meets its neighbours smoothly.",
    "features": "Features: the boss or cut features to copy.",
    "bodies": "Bodies: click any face of each body.",
    "inward": "Shrink: move the faces inward instead of outward.",
    "keep_tools": "Keep tool bodies: the bodies used as tools stay in the part.",
    "part": "Part: click any face of the part to make the cavity of.",  # TR85 (D2111)
    "keep_part": "Keep part: the part stays as a body. Untick to leave only the block.",
    "coord_system": "Coordinate system: its origin is the centre of the scaling.",
    "keep_largest": "Keep largest piece only: when the result falls into pieces, only the "
    "biggest one stays.",
    "from_end": "From end: which end of the round face the length is measured from.",
    "depth": "Depth: how deep it goes in. A Mark with 0 has no depth.",
    "shaft_form": "Shape: hex, D flat, double D or keyway, sized from the round's diameter.",
    "key_standard": "Key standard: FDCAD rule, metric parallel, inch square or half moon "
    "key sizes.",
    "ring_type": "Ring: a retaining ring (shaft or bore) or an E clip (shafts only).",
    "targets": "Points: click vertices, round edges (their centre) or hole walls (their "
    "axis) for the copies.",
    "hole_faces": "Faces with holes: every round hole through these faces gets a copy.",
    "cross_section": "Cross section: the O ring's cord thickness, for example 1.78, 2.62, "
    "3.53 or 5.33 for the inch series.",
    "use": "Use: Static for seals that do not move, Moving for rods and pistons that "
    "slide, Face for a seal pressed between two flat faces.",
    "position": "Position: how far the groove starts from the chosen end of the face.",
    "tie_width": "Tie width: how wide the cable tie strap is.",
    "tie_thickness": "Tie thickness: how thick the strap is.",
    "span": "Span: the distance between the two slots the tie goes down and up.",
    "cover": "Cover: how much material stays over the tunnel under the face.",
    "depth_percent": "Depth: how far the first plate's notch goes into the crossing, as a "
    "percent. 50 splits it half and half.",
    "rib_count": "Ribs: how many ribs, spaced evenly round the face.",
    "slit_length": "Slit length: how long each slit is.",
    "slit_width": "Slit width: how wide each slit is; for a laser, about its cut width.",
    "bridge": "Bridge: the material left between slits in a row.",
    "rib_width": "Rib width: how wide each rib is where it meets the wall.",
    "rib_height": "Rib height: how far each rib stands off the wall. The ribs are crushed "
    "by about this much when the parts are pressed together.",
    "rib_length": "Rib length: how far along the face the ribs run. Empty: the whole face.",
    "rib_tip": "Tip width: the flat on top of each rib, so it prints cleanly.",
    "ear_diameter": "Ear diameter: how wide each disc is.",
    "ear_thickness": "Ear thickness: one or two print layers, so the ears peel off easily.",
    "max_angle": "Corners up to: corners with this inside angle or sharper get an ear.",
    "hole_diameter": "Hole diameter: 2 to 4 mm lets resin drain and is easy to plug.",
    "toward": "Drain toward: the side of the part that faces down while it drains.",
    "pad_thickness": "Pad thickness: two or three layers is enough.",
    "plate_face": "Plate face: the flat face to pocket.",
    "round_face": "Round face: the cylinder face to knurl.",
    "knurl_pattern": "Pattern: Straight grooves along the axis, or Diamond, two sets of "
    "crossing grooves.",
    "knurl_pitch": "Pitch: the groove spacing round the cylinder.",
    "knurl_depth": "Depth: how deep the V grooves go.",
    "joint": "Joint: pick the two bodies, the one to cut first. Groove and Rabbet take the "
    "second body's whole end; Mortise a tenon; Dowels two holes across.",
    "joint_clearance": "Clearance: the gap round the part that goes in.",
    "shoulder": "Shoulder: how much smaller than the end the tenon is on every side.",
    "dowel_diameter": "Dowel diameter: the dowels' size; the holes are the clearance larger.",
    "wall_face": "Wall: the sloped or curved face the pad sits on.",
    "cup_wall": "Cup wall: for Press on a thin wall, a cup this thick behind the pad keeps "
    "the wall closed. Zero for none.",
    "pad_mode": "Pad: Raise builds out from the wall to the sketch plane; Press sinks into "
    "it down to the sketch plane.",
    "border": "Border: the solid width kept along the outer edge and round holes.",
    "web": "Web: the width of the ribs between pockets.",
    "corner_radius": "Corner radius: rounds the pockets' corners. Zero for sharp corners.",
    "pocket_depth": "Pocket depth: zero cuts right through.",
    "edges": "Edges: a chain of joined edges, in place of a face.",
    "loop_face": "Face: the profile runs round this flat face's outer edge. Or pick edges.",
    "router_profile": "Profile: the router shape cut into the edge.",
    "profile_size": "Size: how far the profile reaches across the face.",
    "profile_depth": "Depth: how far a rabbet or stepped chamfer reaches down the side.",
    "spiral_length": "Spiral length: how long the spiral is, from the line's end.",
    "end_radius": "End radius: the radius the spiral ends at, the radius of the arc after it.",
    "hand": "Turns: left or right, seen on the sketch.",
    "on_face": "Face to cover: a cylinder, sphere or other curved face of the part.",
    "seed": "Seed body: a separate body modelled at the origin with +Z pointing out of "
    "the face it sits on. It is used up.",
    "count_u": "Copies across: how many copies along the face's first direction.",
    "count_v": "Copies along: how many copies along the face's second direction.",
    "sink": "Sink: how far each copy sinks into the face, so studs join and dimples bite.",
    "seat_face": "Seat face: click the flat face the stone sits in.",
    "part_file": "Part file: the FDCAD part whose bodies come in.",
    "link": "Link to the file: the bodies follow changes saved to it. Right click the "
    "feature and choose Break Link to keep them as they are.",
    "keep_bodies": "Bodies to bring in: body numbers such as 1, 3. Empty brings every body.",
    "with_sketches": "Bring in sketches: show the part's sketch outlines as reference lines.",
    "with_planes": "Bring in planes: show the part's own planes as reference outlines.",
    "relation": "Relation: how the faces stay to each other when a later Move Face moves "
    "one of them.",
    "place": "Place by: an offset and turns from the original, or a coordinate system the copy "
    "sits on as the original sits on the origin.",
    "slope": "Slope: the angle of every roof face from the sketch plane, 1 to 85 degrees.",
    "max_height": "Max height: cut the roof flat at this height. 0 goes up to the ridges.",
    "seat_point": "Centre point: click a point for the stone's centre, or leave it empty for "
    "the middle of the face.",
    "stone_diameter": "Stone diameter: the stone's widest part, its girdle.",
    "girdle_depth": "Girdle depth: how deep the seat's straight wall goes below the face.",
    "pavilion_angle": "Pavilion angle: the slope of the stone's underside; the seat narrows "
    "to a point at it. 41 degrees suits a round brilliant.",
    "prongs": "Prongs: how many prongs hold the stone, 0 to 12.",
    "prong_diameter": "Prong diameter: the thickness of each prong.",
    "prong_height": "Prong height: how far the prongs stand above the face.",
    "feed_points": "Feed points: click the points where the parts are fed.",
    "cup": "Cup point: click the point for the middle of the pouring cup's open end.",
    "cup_diameter": "Cup diameter: the width of the cup's open end.",
    "cup_height": "Cup depth: how far the cup narrows to the sprue.",
    "sprue_diameter": "Sprue diameter: the trunk of a tree, or the runner of a frame.",
    "gate_diameter": "Gate diameter: the thin rods to each feed point.",
    "knuckle_diameter": "Knuckle diameter: the outside of the knuckles round the edge.",
    "pin_diameter": "Pin hole: the diameter of the hole for the pin, right through.",
    "knuckles": "Knuckles: how many knuckles share the hinge, 2 to 15.",
    "form": "Type: Pin leaves a hole right through for a pin. Print in place makes "
    "cones and sockets, so the hinge is printed already joined.",
    "pin_cone_angle": "Cone angle: the cone pins' sides from the axis. Use your printer's "
    "overhang limit, usually 45 degrees, and print with the axis upright.",
    "detents": "Detent bumps: small bumps click into dimples so the hinge holds its place.",
    "lattice": "Lattice: Gyroid and Diamond are smooth sheets that print without supports "
    "and are strong every way; Honeycomb is straight hexagon walls along Z.",
    "cell": "Cell size: the size of one lattice cell or pocket triangle. Small cells take "
    "long to build.",
    "wall": "Wall: the thickness of the lattice walls.",
    "skin": "Skin: a solid outer wall this thick is kept round the lattice. Zero for none.",
    "tooth_size": "Tooth size: the side of each square tooth; three or more line widths.",
    "tooth_depth": "Tooth depth: how far each tooth reaches into the other body.",
    "pad_margin": "Margin: how far the pad reaches past the face on every side.",
    "air_gap": "Air gap: the space between the pad and the part, so the pad peels off.",
    "base_face": "Face: the face the fitting stands on.",
    "base_point": "Point: a vertex, or a round edge for its centre. Empty: the middle of the face.",
    "fitting": "Fitting: a hose barb, or a male or female luer taper.",
    "hose_diameter": "Hose inside diameter: the stem size, the inside of the hose.",
    "barb_diameter": "Barb diameter: how wide each barb steps out. Empty: 1.15 times the hose.",
    "ring_count": "Barbs: how many barbs along the stem.",
    "ring_length": "Barb length: how long each barb is, from its step to the stem.",
    "body_diameter": "Base diameter: the round base under the luer taper.",
    "shank_height": "Base height: the plain round part between the face and the barbs or taper.",
    "bore_diameter": "Bore diameter: the hole through the fitting. 0: no bore.",
    "bore_depth": "Bore depth into part: how far the bore goes below the face.",
    "finger_count": "Fingers: how many fingers and gaps share the corner. Odd counts "
    "look the same at both ends.",
    "kerf": "Kerf: the width a laser or saw removes. The notches are made that much "
    "narrower so the cut parts still fit.",
    "face": "Round face: click the outside of a shaft or the inside of a bore.",
    "clearance": "Clearance: how much bigger a bore's shape is on every side, so the shaft "
    "slides in. Shafts ignore it.",
    "corners": "Corners: Sharp keeps edges sharp; Rounded rounds the outside edges and "
    "corners with a radius equal to the distance.",
    "skip": "Instances to skip: the numbers of the copies to leave out, such as 3, 5 or 2.2 "
    "for the second copy in direction 2.",
    "geometry": "Geometry pattern: copy the faces exactly instead of building each feature again. "
    "Faster, but faces merged into the rest of the part cannot be copied this way.",
    "merge": "Merge result: copied bodies become one body with the seed.",
    "propagate_colours": "Propagate colours: copies take the colours of the seed's faces.",
    "preview": "Preview: Full shows every copy; Partial shows only the first copy in each "
    "direction, which is faster for large patterns.",
    "planes": "Planes: planes or flat faces that cut the bodies, treated as endless.",
    "tools": "Trim tools: planes, flat faces, curved faces or sketches. Sketches cut through "
    "all, both ways.",
    "regions": "Regions: keep where bodies overlap, the closed spaces inside them, or both.",
    "exclude": "Keep: the regions that stay. Untick a region to leave it out of the result.",
    "keep": "Keep: the bodies that stay. Press Cut, then untick a body to leave it out.",
    "cap": "Cap flat openings: close flat openings of surface bodies. Bodies are closed solids "
    "so far, so this changes nothing yet.",
    "count": "Copies: how many copies, each moved once more than the last.",
    "uniform": "Uniform scaling: one factor for every direction.",
    "about": "Scale about: the centre of the bodies, the origin or a point.",
    "plane": "Mirror plane: a plane or flat face.",
    "seed_only": "Mirror seed only: with two square planes, leave out the copy mirrored "
    "about both.",
}

CHOICES = {
    "tree": "Sprue tree",  # TR408 (D2411)
    "kit_frame": "Kit frame",
    "straight": "Straight",  # TR163 (D2015)
    "groove": "Groove (dado)",  # TR401 (D2014)
    "mortise": "Mortise and tenon",
    "dowels": "Dowels",
    "raise": "Raise",  # TR325 (D2013)
    "round_over": "Round over",  # TR243 (D2011)
    "cove": "Cove",
    "rabbet": "Rabbet",
    "chamfer_flat": "Chamfer with flat",
    "ogee": "Ogee",
    "left": "Left",  # TR408 (D2010)
    "right": "Right",
    "print_in_place": "Print in place",  # TR404 (D2008)
    "pin": "Pin",  # D2841
    "gyroid": "Gyroid",  # TR390 (D2004)
    "honeycomb": "Honeycomb",
    "bottom": "Bottom (lowest point)",  # TR189 (D1006)
    "top": "Top (highest point)",
    "barb": "Hose barb",
    "luer_male": "Luer male",
    "luer_female": "Luer female",
    "start": "Start",
    "end": "End",
    "hex": "Hex",
    "d_flat": "D Flat",
    "double_d": "Double D",
    "keyway": "Keyway",
    "rule": "FDCAD Rule",
    "metric": "Metric Parallel",
    "inch": "Inch Square",
    "woodruff": "Half Moon",
    "ring": "Retaining Ring",
    "e_clip": "E Clip",
    "static": "Static",
    "moving": "Moving",
    "face": "Face Seal",
    "sharp": "Sharp",
    "rounded": "Rounded",
    "none": "None",
    "clearance": "Clearance",
    "slip": "Slip",
    "press": "Press",
    "offset": "Offset",
    "on_frame": "On a coordinate system",  # TR154 (D2417)
    "coplanar": "Coplanar",  # TR266 (D2418)
    "parallel": "Parallel",
    "concentric": "Concentric",
    "perpendicular": "Perpendicular",
    "equal_radius": "Equal radius",
    "fixed": "Fixed",
    "translate": "Translate",
    "resize": "Resize",  # TR265
    "measured": "To a measured size",
    "distance": "By a distance",
    "rotate": "Rotate",
    "frame": "Frame to frame",  # TR268 (D1815)
    "relations": "By relations",  # TR268 item 1 (D2415)
    "body_centre": "Bodies' centre",  # TR268 item 3 (D2416)
    "picked": "A picked point",
    "model": "Model axes",
    "plane_axes": "A plane's axes",
    "grid": "Grid",  # TR57
    "box": "Box",  # TR69
    "indent": "Indent",  # TR68
    "volume": "Volume (mm^3)",  # TR86
    "area": "Surface area (mm^2)",
    "mass": "Mass (g)",
    "formula": "A formula",
    "sphere": "Sphere",  # TR127
    "cone": "Cone",
    "torus": "Torus",
    "wedge": "Wedge",
    "prism": "Prism",
    "tube": "Tube",
    "geodesic_sphere": "Geodesic sphere",
    "geodesic_dome": "Geodesic dome",
    "boss": "Add",
    "cut": "Cut",
    "cylinder": "Cylinder",
    "axes": "Part Axes",
    "best_fit": "Best Fit",
    "extend": "Extend",  # TR264
    "large": "Large End",  # D799
    "small": "Small End",
    "tip": "Tip",
    "lift": "Lift",
    "follow": "Follow",
    "remake": "Remake",
    "shape": "Whole Shape",
    "centre": "Centre Only",
    "staggered": "Staggered Grid",
    "rings": "Rings",
    "diamond": "Diamond",
    "circle": "Circle",
    "square": "Square",
    "polygon": "Polygon",
    "direction": "Distance along a direction",
    "delta": "Delta X, Y, Z",
    "up_to_vertex": "Up to Vertex",
    "up_to_face": "Up to Face",
    "offset_from_face": "Offset from Face",
    "up_to_body": "Up to Body",
    "origin": "Rotation origin",
    "axis": "An axis",  # D2841: Move Face, Turn about
    "patch": "Delete and Patch",
    "fill": "Delete and Fill",
    "delete": "Delete",
    "spacing": "Spacing and instances",
    "up_to": "Up to reference",
    "total": "Total length and instances",  # TR142 (D962)
    "fit": "Spacing and overall size",  # TR398 (D1502)
    "fast": "Fast",  # TR399 (D1519)
    "mapped": "Along the surface",  # TR398 (D1903)
    "projected": "As seen from the front",
    "inside": "Inside the region",  # TR398 (D1503)
    "outside": "Outside the region",
    "even": "Even",  # TR366 (D981)
    "growing": "Growing",
    "fractions": "List of fractions",  # TR366 (D1018)
    "angles": "Per copy angles",  # TR366 (D1500)
    "increment": "Growing by an increment",  # TR59 (D1513)
    "random": "Random",
    "full": "Full",
    "partial": "Partial",
    "add": "Add",
    "subtract": "Subtract",
    "common": "Common",
    "exclusive": "Exclusive",
    "fragments": "Fragments (every piece)",  # TR371 (D999)
    "at_least": "Inside at least",
    "overlap": "Overlap regions",
    "internal": "Internal regions",
    "both": "Both",
    "edge": "Along an edge",
    "vertices": "Vertex to vertex",
    "centroid": "Centre of the bodies",
    "coord_system": "A coordinate system",  # TR85 (D2111)
    "point": "A point",
    "keep": "Keep bodies",
    "x": "X",  # TR371 (D1000)
    "y": "Y",
    "z": "Z",
}

DELETE_GREYED = "Delete without healing leaves an open surface body, which FDCAD does not have yet."
NO_PLANE = "(none)"
#: The origin's axes in axis lists (D712).
ORIGIN_AXES = {"x": "X Axis (origin)", "y": "Y Axis (origin)", "z": "Z Axis (origin)"}
PICKED = "Picked: {name}"
PICK_BODY = "Body {index}"
PICK_PROMPT = "Click in the view"
SKIP_INVALID = "Type copy numbers separated by commas, such as 3, 5 or 2.2."
CUT_BUTTON = "Cut"
CUT_HINT = "Press Cut to list the bodies the split makes."
PIECE = "Body {index}"
# Saving split bodies to files (D528)
SAVE_BODIES = "Save Bodies"
SAVE_BODIES_TIP = "Save each ticked body to its own file in a folder you pick."
SAVE_FORMATS = {"fdef": "FDCAD Part", "step": "STEP", "stl": "STL", "3mf": "3MF"}
SAVE_FORMAT_TIP = "File format for Save Bodies. An FDCAD Part holds the body as an imported body."
PIECE_NAME_TIP = "Double click to type the file name for this body."
SAVE_FOLDER_TITLE = "Save Bodies to Folder"
SAVE_DEFAULT_NAME = "{part} body {index}"
SAVE_PART = "Part"
SAVE_NONE = "Tick at least one body to save."
SAVED_BODIES = "Saved {count} files to {folder}."
SAVE_FAILED = "The bodies could not be saved. Check the folder and try again."
REGION = "Region {index}"
NO_REGIONS = "No regions to list. Pick two bodies that overlap, or a body and a plane."
SELECT_ALL = "Select All"
INVERT = "Invert"
FACE_MENU_TITLE = "Face"
NEEDS_BODY = "{tool} needs a body. Add a boss first."
NEEDS_BODIES = "{tool} needs two or more bodies. Add another body first."
FIX_DROPPED = "Removed {count} picks that failed. Rebuilding."
FIX_SKIPPED = "Skipped {count} copies that failed. Rebuilding."

HELPER_TIPS = {
    "coplanar": "All coplanar faces",
    "inner_loops": "All inner loops (for example every hole wall in this face)",
    "loops": "All outer and inner loops",
    "around": "All faces around it",
    "tangent": "All tangent faces",
    "coplanar_connected": "All coplanar and connected faces",
    "same_direction": "All full cylinders and cones with the same axis direction",
    "same_axis": "All full cylinders and cones on the same axis",
}

# The command tabs read tooltips from ``strings.TOOLTIP_TEXT``.
from fdcad.ui import strings as _strings  # noqa: E402

_strings.TOOLTIP_TEXT.update(TOOLTIP_TEXT)

# Body visibility (P3.4 item 6, D410) --------------------------------------------------

HIDE_BODY = "Hide Body"
SHOW_BODY = "Show Body"
ISOLATE = "Isolate"
EXIT_ISOLATE = "Exit Isolate"
SHOW_ALL_BODIES = "Show All Hidden Bodies"
# Body roles for printing (TR382, D796)
PRINT_ROLE = "Print Role"
PRINT_ROLES = {
    "part": "Part",
    "modifier": "Modifier",
    "negative": "Negative Volume",
    "support_enforcer": "Support Enforcer",
    "support_blocker": "Support Blocker",
}
PRINT_ROLE_TIP = (
    "How slicers use this body when the part is exported as 3MF: printed as a Part, as a "
    "Modifier with its own settings, cut away as a Negative Volume, or as a region that "
    "adds or blocks support. Cura prints a support enforcer as support in the body's shape."
)
PRINT_ROLE_UNDO = "Set Print Role"
BODY_WITH_ROLE = "{body} ({role})"
HIDE_BODIES_UNDO = "Hide {count} bodies"
SHOW_BODIES_UNDO = "Show {count} bodies"
HIDE_ONE_UNDO = "Hide Body {index}"
SHOW_ONE_UNDO = "Show Body {index}"
SHOW_ALL_UNDO = "Show all hidden bodies"
# See through for one body (TR21, D753).
SEE_THROUGH_BODY = "Make Body See Through"
SOLID_BODY = "Make Body Solid"
SEE_THROUGH_ONE_UNDO = "See Through Body {index}"
SOLID_ONE_UNDO = "Solid Body {index}"
BODY_HIDDEN = "Body {index} is hidden. Press Ctrl+Shift+Tab to show all hidden bodies."
BODIES_HIDDEN = "{count} bodies are hidden. Press Ctrl+Shift+Tab to show all hidden bodies."
BODIES_SHOWN = "Showing {count} hidden bodies."
BODY_SHOWN = "Showing the hidden body."
NO_HIDDEN_BODIES = "No bodies are hidden."
ISOLATING = "Showing only the isolated bodies. Press I again to show the others."
ISOLATE_OFF = "Showing every body that is not hidden."
ISOLATE_NOTHING = (
    "Select a face, edge or body that is not hidden, then press I to isolate its body."
)
HOVER_NOTHING = "No hidden body under the cursor. Point at where a hidden body is."
HOVER_NO_VIEW = "Point at a hidden body in the 3D view, then press Shift+Tab."
HOVER_SHOWN = "Body {index} is shown again."
BODIES_MENU = "Bodies"
TRANSFORM_HANDLES = "Transform Handles"
# Lock a body (TR269, D836)
LOCK_BODY = "Lock Body"
UNLOCK_BODY = "Unlock Body"
LOCK_ONE_UNDO = "Lock Body {index}"
UNLOCK_ONE_UNDO = "Unlock Body {index}"
BODY_LOCKED = (
    "Body {index} is locked: it stays visible but cannot be picked. Unlock it in the tree."
)
