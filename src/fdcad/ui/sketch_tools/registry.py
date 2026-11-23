"""The Phase 2 sketch tools (PHASE2_SPEC P2.8, P2.9) by name.

``make_tool`` in ``tools.py`` looks names up here, so new tools need no change
to the Phase 1 tool table. Pure Python, no Qt.
"""

from __future__ import annotations

from fdcad.ui.sketch_tools.tools import Tool


def extra_tools() -> dict[str, type[Tool]]:
    """Tool classes by name, in the order of the Sketch tab."""
    from fdcad.ui.sketch_tools.blend_tool import BlendCurveTool
    from fdcad.ui.sketch_tools.check_tool import CheckSketchTool
    from fdcad.ui.sketch_tools.circle_tools import TangentCircleTool, TwoPointCircleTool
    from fdcad.ui.sketch_tools.close_model_tool import CloseToModelTool
    from fdcad.ui.sketch_tools.conic_tools import (
        ConicTool,
        EquationCurveTool,
        HyperbolaTool,
        ParabolaTool,
    )
    from fdcad.ui.sketch_tools.convert_tool import ConvertTool
    from fdcad.ui.sketch_tools.corner_tools import SketchChamferTool, SketchFilletTool
    from fdcad.ui.sketch_tools.curve_tools import EllipseTool, PartialEllipseTool, SplineTool
    from fdcad.ui.sketch_tools.datum_dimensions import (
        BaselineDimensionTool,
        OrdinateDimensionTool,
    )
    from fdcad.ui.sketch_tools.fully_define_tool import FullyDefineTool
    from fdcad.ui.sketch_tools.infinite_line import InfiniteLineTool
    from fdcad.ui.sketch_tools.jog_tool import JogLineTool
    from fdcad.ui.sketch_tools.midpoint_line import MidpointLineTool
    from fdcad.ui.sketch_tools.mirror_tool import MirrorTool
    from fdcad.ui.sketch_tools.model_curve_tools import (
        IntersectionCurvesTool,
        SilhouetteTool,
        TurnedOutlineTool,
    )
    from fdcad.ui.sketch_tools.offset_tool import OffsetTool
    from fdcad.ui.sketch_tools.pattern_tools import CircularPatternTool, LinearPatternTool
    from fdcad.ui.sketch_tools.picture_tool import PictureTool
    from fdcad.ui.sketch_tools.repair_tool import RepairSketchTool
    from fdcad.ui.sketch_tools.shape_tools import PolygonTool, SlotTool
    from fdcad.ui.sketch_tools.spline_tools import (
        FitSplineTool,
        InsertSplinePointTool,
        SimplifySplineTool,
    )
    from fdcad.ui.sketch_tools.split_tool import SplitTool
    from fdcad.ui.sketch_tools.three_point_tools import (
        ParallelogramTool,
        PerimeterCircleTool,
        ThreePointCenterRectangleTool,
        ThreePointCornerRectangleTool,
    )
    from fdcad.ui.sketch_tools.transform_tools import TRANSFORM_TOOLS
    from fdcad.ui.sketch_tools.trim_tools import ExtendTool, TrimTool

    return {
        "trim": TrimTool,
        "extend": ExtendTool,
        "offset": OffsetTool,
        "mirror": MirrorTool,
        "fillet": SketchFilletTool,
        "chamfer": SketchChamferTool,
        "convert": ConvertTool,
        "linear_pattern": LinearPatternTool,
        "circular_pattern": CircularPatternTool,
        "slot": SlotTool,
        "polygon": PolygonTool,
        "spline": SplineTool,
        "ellipse": EllipseTool,
        "partial_ellipse": PartialEllipseTool,
        "picture": PictureTool,
        "three_point_corner_rectangle": ThreePointCornerRectangleTool,
        "three_point_center_rectangle": ThreePointCenterRectangleTool,
        "parallelogram": ParallelogramTool,
        "perimeter_circle": PerimeterCircleTool,
        "two_point_circle": TwoPointCircleTool,  # TR317
        "tangent_circle": TangentCircleTool,  # TR317
        "blend_curve": BlendCurveTool,  # TR318
        "jog_line": JogLineTool,  # TR52
        "parabola": ParabolaTool,  # TR52
        "hyperbola": HyperbolaTool,  # TR374
        **TRANSFORM_TOOLS,
        "midpoint_line": MidpointLineTool,
        "infinite_line": InfiniteLineTool,  # TR115 item 1
        "split": SplitTool,
        "conic": ConicTool,  # TR28
        "equation_curve": EquationCurveTool,
        "intersection_curves": IntersectionCurvesTool,  # TR6
        "silhouette": SilhouetteTool,
        "turned_outline": TurnedOutlineTool,  # TR319
        "close_to_model": CloseToModelTool,  # TR106
        "fully_define": FullyDefineTool,  # TR35
        "check_sketch": CheckSketchTool,  # TR36
        "repair_sketch": RepairSketchTool,  # TR37
        "insert_spline_point": InsertSplinePointTool,  # TR42
        "fit_spline": FitSplineTool,
        "simplify_spline": SimplifySplineTool,
        "baseline_dimension": BaselineDimensionTool,  # TR45
        "ordinate_dimension": OrdinateDimensionTool,
    }


#: Names of the Phase 2 tools, in command order (matches ``extra_tools``).
EXTRA_TOOL_NAMES = [
    "trim",
    "extend",
    "offset",
    "mirror",
    "fillet",
    "chamfer",
    "convert",
    "linear_pattern",
    "circular_pattern",
    "slot",
    "polygon",
    "spline",
    "ellipse",
    "partial_ellipse",
    "picture",
    "three_point_corner_rectangle",
    "three_point_center_rectangle",
    "parallelogram",
    "perimeter_circle",
    "two_point_circle",
    "tangent_circle",
    "blend_curve",
    "jog_line",
    "parabola",
    "hyperbola",
    "move_entities",
    "copy_entities",
    "rotate_entities",
    "scale_entities",
    "stretch_entities",
    "midpoint_line",
    "infinite_line",
    "split",
    "conic",
    "equation_curve",
    "intersection_curves",
    "silhouette",
    "turned_outline",
    "close_to_model",
    "fully_define",
    "check_sketch",
    "repair_sketch",
    "insert_spline_point",
    "fit_spline",
    "simplify_spline",
    "baseline_dimension",
    "ordinate_dimension",
]
