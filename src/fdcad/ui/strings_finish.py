"""UI text for fillet, chamfer, draft, shell and checks added in round 13 (cloud H)."""

from __future__ import annotations

FIELD_PICK_THROUGH = "Select through faces"
FIELD_PICK_THROUGH_TIP = (
    "Clicks in the view take the nearest edge under the cursor, even when a face is "
    "in front of it. Use it to pick hidden edges without turning the part."
)
LIMIT_FAILING_UNDO = "Limit failing areas of {name}"
SHELL_WALL_RULE = "Wall"
SHELL_WALL_RULE_TIP = (
    "Exact follows the thickness. Never thinner keeps every point of the wall at least "
    "the thickness; Never thicker keeps it at most the thickness, with rounded corners. "
    "Both are checked after the shell and a warning names the point that misses."
)
SHELL_WALL_RULES = {
    None: "Exact",
    "never_thinner": "Never thinner",
    "never_thicker": "Never thicker",
}
FIXED_EDGES = "Fixed edges"
FIXED_EDGES_TIP = (
    "One edge on each face to draft. The face turns about it, so the edge stays where it is. "
    "Click straight edges square to the direction of pull."
)
DRAFT_NEEDS_FIXED = "No fixed edges are picked. Pick one edge on each face to draft."
DOME_DIRECTION = "Direction"
DOME_DIRECTION_TIP = (
    "Optional: a straight edge, flat face or plane. The dome rises along it instead of "
    "square to the face; the base stays on the face. Leave it empty for a straight dome."
)
DOME_PROFILE = "Profile sketch"
DOME_PROFILE_NONE = "No profile"
DOME_PROFILE_TIP = (
    "Optional: a sketch with a closed outline that sets the dome's section. "
    "X is the distance out from the middle of the face, Y the height. "
    "The Distance is then not used."
)
CHECK_HEALED = "{name} closes the gaps and refits loose edges. Check Again to see what is left."
PREF_WALL_TARGET = "Wall analysis target"
PREF_WALL_TARGET_PROFILE = "Minimum wall"
PREF_WALL_TARGET_TIP = (
    "The thickness Wall Thickness Analysis looks for. At 0 it uses the profile's minimum wall."
)
WALL_HERE = "Wall here: {value} mm (target {wall} mm)."
SPLIT_LINE_BODY = "Splitting body"
SPLIT_LINE_BODY_TIP = (
    "Optional, instead of a plane: click a face of another body. The faces are split where "
    "that body's faces cross them."
)
SPLIT_LINE_PULL = "Direction of pull"
SPLIT_LINE_PULL_TIP = (
    "A plane, flat face or straight edge. Cylinders, cones and spheres are split along their "
    "outline seen along it."
)
PARTING_SPLIT = "Split faces at the line"
PARTING_SPLIT_TIP = (
    "Cylinders, cones and spheres with both kinds of draft are split along their outline, "
    "so the parting line runs across them. The part keeps the split faces."
)
CHAMFER_CORNER = "Corners"
CHAMFER_CORNER_TIP = (
    "Where three bevels meet. Patch: a small flat triangle. Mitre: the bevels run on until "
    "they meet in one point, with no extra face. Blend: a curved face that meets the "
    "bevels smoothly."
)
CHAMFER_CORNERS = {None: "Patch", "mitre": "Mitre", "blend": "Blend"}  # blend: D2304
