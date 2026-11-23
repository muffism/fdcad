"""Evaluate tab groups of the Phase 2 print and evaluate tools (D350 to D357).

Pure layout data; commands that do not exist are skipped by the tab builder.
"""

from __future__ import annotations

from typing import Any

GROUP_PRINT = "Print"
GROUP_CHECK = "Check"
GROUP_ANALYSIS = "Print Analysis"

#: Groups in the format of ``command_tabs.tabs.Group``.
EVALUATE_PRINT_GROUPS: list[tuple[str, list[Any], list[list[Any]]]] = [
    (
        GROUP_PRINT,
        ["print.open_slicer"],
        [
            [
                "evaluate.build_volume",
                [
                    "print.lay_flat",
                    "print.clear_orientation",
                    "print.scale_to_fit",
                    "print.clear_fit",
                    "print.save_fit",
                    "print.suggest_orientation",  # TR301 (D1210)
                    "print.arrange",
                ],
                ["print.bed_chamfer", "print.fix_overhangs", "print.coating"],  # TR410, TR307
            ],
            [["print.fit_calibration", "print.keep_fit"]],  # TR358 (D2000)
        ],
    ),
    (  # its own group, so no group is wider than a small screen (D1027)
        GROUP_ANALYSIS,
        [],
        [
            ["evaluate.overhang", "evaluate.wall_thickness", "evaluate.print_estimate"],
            ["print.height_changes", "evaluate.layer_fit", "evaluate.cups_islands"],
        ],
    ),
    (
        GROUP_CHECK,
        ["evaluate.geometry_check"],
        [
            [
                "evaluate.draft_analysis",
                "evaluate.undercut",
                ["evaluate.cavities", "evaluate.edge_angles", "evaluate.layer_preview"],
            ]
        ],
    ),
]
