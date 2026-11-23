"""Features tab groups for the Phase 3 tools (layout format of ``command_tabs/tabs.py``)."""

from __future__ import annotations

from fdcad.ui import strings_phase3 as text

PHASE3_GROUPS: list[tuple[str, list[str | list[str]], list[list[str | list[str]]]]] = [
    (
        text.GROUP_DIRECT,
        ["feature.move_face", "feature.delete_face"],
        [["feature.offset_face"]],
    ),
    (
        text.GROUP_PATTERN,
        ["feature.linear_pattern"],
        [
            [
                "feature.circular_pattern",
                "feature.sketch_pattern",
                "feature.table_pattern",
                "feature.mirror",
            ]
        ],
    ),
    (
        text.GROUP_BODIES,
        [],
        [
            ["feature.combine", "feature.intersect", "feature.split"],
            [
                "feature.move_copy_body",
                "feature.delete_body",
                "feature.scale",
                "feature.offset_body",
            ],
            ["feature.transform_handles"],
        ],
    ),
    (
        "Deform",
        ["feature.flow"],
        [["feature.bend", "feature.twist"], ["feature.taper", "feature.stretch"]],
    ),
]
