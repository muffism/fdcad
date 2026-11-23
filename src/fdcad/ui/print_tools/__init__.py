"""Phase 2 print and evaluate tools: DXF and SVG export, open in slicer, print
orientation, build volume, overhang analysis, print estimate and geometry check.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any

from fdcad.ui import strings, strings_print

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow

strings.TOOLTIP_TEXT.update(strings_print.TOOLTIPS)


def install(window: MainWindow, export_menu: Any) -> None:
    """Create the commands and put the export ones in File, Export."""
    from fdcad.ui.print_tools import (
        build_volume,
        estimate,
        flat_export,
        geometry_check,
        orientation,
        overhang,
        slicer,
    )

    a = window.commands
    export_menu.addSeparator()
    for cid, kind in (("file.export_dxf", "dxf"), ("file.export_svg", "svg")):
        export_menu.addAction(a.add(cid, partial(flat_export.export, window, kind)))
    from fdcad.ui.print_tools import section_export

    export_menu.addAction(  # TR300 (D1204)
        a.add("file.export_section", partial(section_export.export, window))
    )
    from fdcad.ui.print_tools.export_bodies import export_bodies

    export_menu.addAction(a.add("file.export_bodies", partial(export_bodies, window)))
    menu = export_menu.parent()
    slicer_action = a.add("print.open_slicer", partial(slicer.open_in_slicer, window))
    if hasattr(menu, "insertAction"):
        menu.insertAction(export_menu.menuAction(), slicer_action)
    window.print_orientation = orientation.OrientationTool(window)
    a.add("print.lay_flat", window.print_orientation.lay_flat)
    a.add("print.clear_orientation", window.print_orientation.clear)
    from fdcad.ui.print_tools.fit_tool import FitTool

    window.print_fit = FitTool(window)  # TR185 (D828)
    a.add("print.scale_to_fit", window.print_fit.scale_to_fit)
    a.add("print.clear_fit", window.print_fit.clear)
    a.add("print.save_fit", window.print_fit.save_as_feature)
    from fdcad.ui.print_tools.bed_chamfer_tool import bed_chamfer

    a.add("print.bed_chamfer", partial(bed_chamfer, window))  # TR177
    from fdcad.ui.print_tools.overhang_fix_tool import fix_overhangs

    a.add("print.fix_overhangs", partial(fix_overhangs, window))  # TR410
    from fdcad.ui.print_tools.heights_tool import edit_heights

    a.add("print.height_changes", partial(edit_heights, window))  # TR384 (D1208)
    from fdcad.ui.print_tools.layer_fit_tool import layer_fit

    a.add("evaluate.layer_fit", partial(layer_fit, window))  # TR187 (D1209)
    from fdcad.ui.print_tools import arrange_tool

    a.add("print.suggest_orientation", partial(arrange_tool.suggest_orientation, window))
    a.add("print.arrange", partial(arrange_tool.arrange_bodies, window))  # TR301 (D1210)
    from fdcad.ui.print_tools.islands_tool import cups_and_islands

    a.add("evaluate.cups_islands", partial(cups_and_islands, window))  # TR409 (D1213)
    from fdcad.ui.print_tools.coating_tool import set_coating

    a.add("print.coating", partial(set_coating, window))  # TR307 (D1214)
    from fdcad.ui.print_tools import calibration_tool

    a.add("print.fit_calibration", partial(calibration_tool.make_calibration_part, window))
    a.add("print.keep_fit", partial(calibration_tool.keep_measured_fit, window))  # TR358
    volume = build_volume.BuildVolume(window)
    window.build_volume = volume
    volume_action = a.add(
        "evaluate.build_volume", lambda: volume.set_on(volume_action.isChecked()), checkable=True
    )
    analysis = overhang.OverhangAnalysis(window)
    window.overhang_analysis = analysis
    overhang_action = a.add(
        "evaluate.overhang", lambda: analysis.set_on(overhang_action.isChecked()), checkable=True
    )
    from fdcad.ui.print_tools import wall_thickness

    walls = wall_thickness.WallThicknessAnalysis(window)
    window.wall_thickness = walls
    wall_action = a.add(
        "evaluate.wall_thickness", lambda: walls.set_on(wall_action.isChecked()), checkable=True
    )
    from fdcad.ui.print_tools import draft_analysis

    drafts = draft_analysis.DraftAnalysis(window)
    window.draft_analysis = drafts
    draft_action = a.add(
        "evaluate.draft_analysis", lambda: drafts.set_on(draft_action.isChecked()), checkable=True
    )
    from fdcad.ui.print_tools.undercut import UndercutAnalysis

    undercut = UndercutAnalysis(window)  # TR83 (D864)
    window.undercut_analysis = undercut
    undercut_action = a.add(
        "evaluate.undercut", lambda: undercut.set_on(undercut_action.isChecked()), checkable=True
    )
    from fdcad.ui.print_tools.edge_angles import EdgeAngleAnalysis

    edges = EdgeAngleAnalysis(window)  # TR420 (D929)
    window.edge_angle_analysis = edges
    edge_action = a.add(
        "evaluate.edge_angles", lambda: edges.set_on(edge_action.isChecked()), checkable=True
    )
    from fdcad.ui.print_tools.layer_preview import LayerPreview

    layers = LayerPreview(window)  # TR315 (D993)
    window.layer_preview = layers
    layers_action = a.add(
        "evaluate.layer_preview", lambda: layers.set_on(layers_action.isChecked()), checkable=True
    )
    window.print_estimate = estimate.PrintEstimate(window)
    a.add("evaluate.print_estimate", window.print_estimate.open)
    window.geometry_check = geometry_check.GeometryCheck(window)
    a.add("evaluate.geometry_check", window.geometry_check.open)
