"""User text for the Phase 2 sketch tools (PHASE2_SPEC P2.8, P2.9). No imports, so
``fdcad.ui.strings`` can merge it."""

#: One sentence per command for the command tab tooltips.
TOOLTIPS = {
    "sketch.trim": "Removes pieces of curves up to where they cross, in five modes.",
    "sketch.extend": "Carries a line or arc on along its path to the next curve.",
    "sketch.offset": "Copies curves at a distance to one side; the copies follow the originals.",
    "sketch.mirror": "Copies curves to the other side of a mirror line with Symmetric relations.",
    "sketch.fillet": "Rounds the corner between two lines with a tangent arc.",
    "sketch.chamfer": "Cuts the corner between two lines with a straight line.",
    "sketch.convert": "Copies part edges into the sketch as fixed curves.",
    "sketch.linear_pattern": "Repeats curves in a row or a grid at an even spacing.",
    "sketch.circular_pattern": "Repeats curves around a center point.",
    "sketch.slot": "Draws a straight or arc slot from its centers and width.",
    "sketch.polygon": "Draws a regular polygon from its center and a vertex.",
    "sketch.spline": "Draws a smooth curve through the points you click.",
    "sketch.ellipse": "Draws an ellipse from its center and the ends of its axes.",
    "sketch.partial_ellipse": "Draws part of an ellipse, swept along its outline.",
    "sketch.picture": "Places an image in the sketch to trace over, scaled to a known length.",
    "sketch.three_point_corner_rectangle": (
        "Draws a rectangle at any angle from two corners and the size of the other side."
    ),
    "sketch.three_point_center_rectangle": (
        "Draws a rectangle at any angle from its center, the middle of one side and the other size."
    ),
    "sketch.parallelogram": "Draws a parallelogram from three of its corners.",
    "sketch.perimeter_circle": "Draws a circle through three points you click.",
    "sketch.two_point_circle": "Draws a circle from the two ends of a diameter.",
    "sketch.blend_curve": "Joins the ends of two curves with a smooth spline.",
    "sketch.jog_line": "Steps part of a line sideways, with a short line between.",
    "sketch.parabola": "Draws a parabola from its focus, its apex and two ends.",
    "sketch.hyperbola": "Draws a partial hyperbola from its centre, its vertex and one end.",
    "sketch.tangent_circle": "Draws a circle touching three lines or curves, or two and a "
    "radius you type.",
    "sketch.dynamic_mirror": "Mirrors each new shape about a line as you draw. Click to stop.",
    "sketch.move_entities": (
        "Moves picked sketch entities from a base point to a target, or by a distance."
    ),
    "sketch.copy_entities": (
        "Copies picked sketch entities one or more times, each copy one step further."
    ),
    "sketch.rotate_entities": "Turns picked sketch entities about a center point.",
    "sketch.scale_entities": "Scales picked sketch entities about a base point.",
    "sketch.stretch_entities": (
        "Moves the points inside a box, so curves that cross it get longer or shorter."
    ),
    "sketch.insert_dxf": "Adds the lines, arcs and curves of a DXF drawing to the sketch.",
    "sketch.split": "Splits a curve into two at the points you click.",
    "sketch.midpoint_line": "Draws a line from its middle: click the middle, then one end.",
    "sketch.infinite_line": "Draws a construction line through two points that runs on far "
    "beyond them, to trim later.",
    "sketch.conic": "Draws a conic: click both ends, then the top point. Shape sets how full.",
    "sketch.equation_curve": "Adds a curve from x(t) and y(t) typed in the panel.",
    "sketch.intersection_curves": "Copies the curves where the sketch plane cuts the part.",
    "sketch.silhouette": "Copies the outline of the part as seen square to the sketch.",
    "sketch.turned_outline": "Copies the outline of the part as if spun about the sketch X "
    "axis, for lathe drawings and revolve profiles.",
    "sketch.close_to_model": "Closes an open profile whose ends sit on part edges, by those "
    "edges. Click inside the shape to keep.",
    "sketch.fully_define": "Adds the relations and dimensions the sketch still needs.",
    "sketch.check_sketch": "Checks whether the sketch suits a feature: gaps, extra curves.",
    "sketch.repair_sketch": "Finds small gaps, overlaps and tiny segments, and fixes them.",
    "sketch.insert_spline_point": "Adds a through point to a spline where you click.",
    "sketch.fit_spline": "Replaces a chain of lines and arcs with one spline.",
    "sketch.simplify_spline": "Removes spline points while the curve stays within a tolerance.",
    "sketch.baseline_dimension": "Dimensions several items from one base, stacked.",
    "sketch.ordinate_dimension": "Dimensions points from a zero point along one axis.",
    "view.curvature_combs": "Shows curvature combs on the splines of the open sketch.",
}
#: Tool names shown in panels.
TOOL_NAMES = {
    "trim": "Trim",
    "extend": "Extend",
    "offset": "Offset",
    "mirror": "Mirror",
    "fillet": "Sketch Fillet",
    "chamfer": "Sketch Chamfer",
    "convert": "Convert Entities",
    "linear_pattern": "Linear Sketch Pattern",
    "circular_pattern": "Circular Sketch Pattern",
    "slot": "Slot",
    "polygon": "Polygon",
    "spline": "Spline",
    "ellipse": "Ellipse",
    "partial_ellipse": "Partial Ellipse",
    "picture": "Sketch Picture",
    "three_point_corner_rectangle": "3 Point Corner Rectangle",
    "three_point_center_rectangle": "3 Point Center Rectangle",
    "parallelogram": "Parallelogram",
    "perimeter_circle": "Perimeter Circle",
    "two_point_circle": "2 Point Circle",
    "blend_curve": "Blend Curve",
    "jog_line": "Jog Line",
    "parabola": "Parabola",
    "hyperbola": "Partial Hyperbola",
    "tangent_circle": "Tangent Circle",
    "move_entities": "Move Entities",
    "copy_entities": "Copy Entities",
    "rotate_entities": "Rotate Entities",
    "scale_entities": "Scale Entities",
    "stretch_entities": "Stretch Entities",
    "midpoint_line": "Midpoint Line",
    "infinite_line": "Infinite Construction Line",
    "conic": "Conic",
    "equation_curve": "Equation Curve",
    "intersection_curves": "Intersection Curves",
    "silhouette": "Silhouette",
    "turned_outline": "Turned Outline",
    "close_to_model": "Close Sketch to Model",
    "fully_define": "Fully Define Sketch",
    "check_sketch": "Check Sketch",
    "repair_sketch": "Repair Sketch",
    "insert_spline_point": "Insert Spline Point",
    "fit_spline": "Fit Spline",
    "simplify_spline": "Simplify Spline",
    "baseline_dimension": "Baseline Dimension",
    "ordinate_dimension": "Ordinate Dimension",
    "split": "Split Entities",
}
#: Hints shown in the tool options of the three click shapes (D511, D512).
THREE_POINT_HINTS = {
    "three_point_corner_rectangle": (
        "Click two corners for the first side, then click to set the other side. "
        "Hold Shift on the last click for a square."
    ),
    "three_point_center_rectangle": (
        "Click the center, then the middle of one side, then click to set the other size. "
        "Hold Shift on the last click for a square."
    ),
    "parallelogram": "Click two corners, then click the third corner.",
    "perimeter_circle": "Click three points on the circle.",
    "two_point_circle": "Click both ends of a diameter.",
    "jog_line": "Click a line where the step goes, then click to one side for its depth.",
    "parabola": "Click the focus, the apex, then the two ends.",
    "hyperbola": "Click the centre, the vertex, then one end.",
    "blend_curve": "Click two curves near the ends to join. Drag the handles to change "
    "how far each end reaches.",
    "tangent_circle": "Click three lines or curves, or two and then a spot to set the radius "
    "there.",
}
#: The three points of a perimeter circle were in a line (D512).
PERIMETER_IN_LINE = (
    "The three points are in a line, so no circle goes through them. Click a point off the line."
)
#: A rectangle with no width or height was dropped without a word (audit D2 item 7, D743).
FLAT_RECTANGLE = (
    "A rectangle needs a width and a height. Click the second corner away from the first, "
    "not straight across or up from it."
)
#: Typed sizes that could not become driving dimensions (audit D2 item 13, D743).
TYPED_NOT_DIMENSIONED = (
    "The shape was drawn, but {n} typed size(s) could not be added as dimensions. "
    "Add them with Smart Dimension."
)
TYPED_REFERENCE = (
    "The shape was drawn; {n} typed size(s) would over define the sketch, so they were "
    "added as reference dimensions. Delete a relation or dimension to make them driving."
)
GROUP_MODIFY = "Modify"
#: The offset relation that links offset copies to their sources (DECISIONS D272).
RELATION_NAMES = {"offset": "Offset"}
RELATION_TAGS = {"offset": "Of"}

# Sketch picture (P2.9).
PICK_TITLE = "Insert Picture"
PICK_FILTER = "Images (*.png *.jpg *.jpeg *.bmp)"
UNREADABLE = "Could not read {name}. Check the file and try again."
NOT_IMAGE = "{name} is not a PNG, JPEG or BMP image. Pick another file."

# Values typed in the canvas (TOOL_SPEC T15.5 to T15.7) ------------------------------

#: A count was not a whole number.
WHOLE_NUMBER = "A count must be a whole number. Type a number such as 4."
#: A count was outside what the tool allows.
COUNT_RANGE = "Type a count from {low} to {high}."
#: The names of the sizes typed while drawing, for the value box tooltip.
SIZE_NAMES = {
    "length": "Length",
    "width": "Width",
    "height": "Height",
    "radius": "Radius",
}
#: Status bar note once a size is typed.
SIZE_LOCKED = "{name} set to {value}. Move to set the direction, then click or press Enter."

# Dynamic mirror (P2.8 item 4, D514) and curvature combs (P2.8 item 10) ----------------

MIRROR_PICK = "Dynamic mirror: click a line or centerline to mirror about. Escape cancels."
MIRROR_NOT_LINE = "Dynamic mirror needs a straight line. Click a line or centerline."
MIRROR_ON = "Dynamic mirror is on. New shapes are mirrored about the line."
MIRROR_OFF = "Dynamic mirror is off."
MIRROR_STATUS = "Dynamic mirror on."
#: Mirror cannot copy splines or ellipses either, so it is no advice (audit D2 item 11).
MIRROR_SKIPPED = (
    "Dynamic mirror skips splines and ellipses, and Mirror cannot copy them either. "
    "Draw the other side yourself."
)
MIRROR_NO_SKETCH = "Open a sketch first, then turn on Dynamic Mirror."
SHOW_CURVATURE = "Show curvature"
SHOW_CURVATURE_TIP = "Draw curvature combs on the splines. Longer teeth mean a tighter bend."
# Two point and tangent circles (TR317, D877)
TWO_POINT_SAME = "Both ends are the same point. Click two different points."
TANGENT_PICK_CURVE = "Click a line, arc or circle for the circle to touch."
TANGENT_NO_CIRCLE = (
    "No circle touches those curves near where you clicked. Click closer to where the "
    "circle should go, or pick other curves."
)
# Blend curve (TR318, D884)
BLEND_PICK = "Click a line, arc or spline near the end to join."
# Jog Line (TR52, D902)
JOG_PICK_LINE = "Click a line where the step should go."
